from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import random
import secrets
import json

from authlib.integrations.flask_client import OAuth
from database import add_user, get_user
from utils import send_email

auth_bp = Blueprint("auth", __name__)
oauth = OAuth()


def init_oauth(app):
    """Initialize Google OAuth with client_secret.json"""
    try:
        with open("client_secret.json") as f:
            google_config = json.load(f)["web"]

        oauth.init_app(app)
        oauth.register(
            name="google",
            client_id=google_config["client_id"],
            client_secret=google_config["client_secret"],
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )
    except FileNotFoundError:
        print("client_secret.json not found. Google OAuth disabled.")
    except Exception as e:
        print(f"Error initializing OAuth: {e}")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    # Check if user came from Google login
    google_email = session.get("email")
    google_name = session.get("name")
    if google_email:
        if not get_user(google_email):
            add_user(google_name, google_email, provider="google")
        flash("Registration successful via Google!", "success")
        return redirect(url_for("routes.dashboard"))

    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")

        # Step 1: Send OTP
        if "send_otp" in request.form:
            otp = str(random.randint(1000, 9999))
            session["otp"] = otp
            session["temp_user"] = {"name": name, "email": email}
            sent = send_email(email, otp)
            if not sent:
                flash("Failed to send OTP. Please check email configuration and try again.", "danger")
                return render_template("register.html", email=email, name=name)

            flash("OTP sent to your email. Please verify.", "info")
            return render_template("register.html", show_otp=True, email=email, name=name)

        # Step 2: Verify OTP
        elif "verify_otp" in request.form:
            user_otp = request.form.get("otp")
            if user_otp == session.get("otp"):
                flash("OTP verified! Please set your password.", "success")
                temp_user = session.get("temp_user")
                return render_template(
                    "register.html",
                    show_password=True,
                    email=temp_user["email"],
                    name=temp_user["name"]
                )
            else:
                flash("Invalid OTP!", "danger")
                temp_user = session.get("temp_user")
                return render_template(
                    "register.html",
                    show_otp=True,
                    email=temp_user["email"],
                    name=temp_user["name"]
                )

        # Step 3: Set password & create account
        elif "register" in request.form:
            temp_user = session.pop("temp_user", None)
            session.pop("otp", None)

            if not temp_user:
                flash("Session expired. Please try again.", "danger")
                return redirect(url_for("auth.register"))

            password = request.form.get("password")
            confirm_password = request.form.get("confirmPassword")

            if not password or password != confirm_password:
                flash("Passwords do not match or empty!", "danger")
                return render_template(
                    "register.html",
                    show_password=True,
                    email=temp_user["email"],
                    name=temp_user["name"]
                )

            hashed_pw = generate_password_hash(password)
            add_user(temp_user["name"], temp_user["email"], hashed_pw)

            session["email"] = temp_user["email"]
            session["name"] = temp_user["name"]

            flash("Registration successful!", "success")
            return redirect(url_for("routes.dashboard"))

    # GET request
    return render_template("register.html")

# ----------------- Login (Email + Google) -----------------


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email").strip()
        password = request.form.get("password").strip()

        user = get_user(email)
        if not user or not user.get('password'):
            flash("Invalid email and password")
            return redirect(url_for("auth.login"))

        if not check_password_hash(user['password'], password):
            flash("Incorrect password!", "danger")
            return redirect(url_for("auth.login"))

        # Successful login
        session['email'] = user["email"]
        session['name'] = user["name"]
        flash("Logged in successfully!", "success")
        return redirect(url_for("routes.dashboard"))

    return render_template("login.html")


# Step 1: Request password reset (send OTP)
@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email").strip()
        user = get_user(email)
        if not user:
            flash("Email not registered!", "danger")
            return redirect(url_for("auth.forgot_password"))

        otp = str(secrets.randbelow(1000000)).zfill(6)
        session["reset_otp"] = otp
        session["reset_email"] = email
        # send raw otp; utils.send_email will craft the message body.
        sent = send_email(email, otp)
        if not sent:
            flash("Failed to send OTP for password reset. Please check email configuration.", "danger")
            return redirect(url_for("auth.forgot_password"))

        flash("OTP sent to your email.", "info")
        return redirect(url_for("auth.verify_reset_otp"))

    return render_template("forgot_password.html")


# Step 2: Verify OTP
@auth_bp.route("/verify-reset-otp", methods=["GET", "POST"])
def verify_reset_otp():
    if request.method == "POST":
        entered_otp = request.form.get("otp").strip()
        if entered_otp == session.get("reset_otp"):
            flash("OTP verified! You can reset your password now.", "success")
            return redirect(url_for("auth.reset_password"))
        else:
            flash("Incorrect OTP, try again.", "danger")
            return redirect(url_for("auth.verify_reset_otp"))

    return render_template("verify_reset_otp.html")


# Step 3: Reset Password
@auth_bp.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    if request.method == "POST":
        password = request.form.get("password").strip()
        confirm_password = request.form.get("confirm_password").strip()

        if password != confirm_password:
            flash("Passwords do not match!", "danger")
            return redirect(url_for("auth.reset_password"))

        email = session.get("reset_email")
        from database import update_user_password
        if update_user_password(email, generate_password_hash(password)):
            flash("Password reset successfully!", "success")
            session.pop("reset_email", None)
            session.pop("reset_otp", None)
            return redirect(url_for("auth.login"))
        else:
            flash("Failed to reset password. Please try again.", "danger")

    return render_template("reset_password.html")


# ----------------- Google OAuth -----------------
@auth_bp.route("/google-login")
def google_login():
    try:
        redirect_uri = url_for("auth.google_authorize", _external=True)
        nonce = secrets.token_urlsafe(16)
        session["nonce"] = nonce
        return oauth.google.authorize_redirect(redirect_uri, nonce=nonce)
    except Exception as e:
        print(f"Google login error: {e}")
        flash("Google login is not configured properly.", "danger")
        return redirect(url_for("auth.login"))


@auth_bp.route("/callback")
def google_authorize():
    try:
        token = oauth.google.authorize_access_token()
        user_info = oauth.google.parse_id_token(token, nonce=session.get("nonce"))
        session["email"] = user_info["email"]
        session["name"] = user_info.get("name")

        # Auto-register if first time
        if not get_user(session["email"]):
            add_user(session["name"], session["email"], provider="google")

        flash(f"Logged in as {session['name']}", "success")
        return redirect(url_for("routes.dashboard"))
    except Exception as e:
        print(f"OAuth error: {e}")
        flash("Google login failed. Please try again.", "danger")
        return redirect(url_for("auth.login"))

# ----------------- Logout -----------------


@auth_bp.route("/logout")
def logout():
    # Clear company selection and practice mode before logout
    if 'email' in session:
        from utils import clear_selected_company
        try:
            clear_selected_company(session['email'])
        except Exception as e:
            print(f"Error clearing company selection: {e}")

    # Clear session (including practice_mode flag)
    session.clear()
    flash("Logged out successfully! You can select any company for practice on next login.", "info")
    return redirect(url_for("auth.login"))
