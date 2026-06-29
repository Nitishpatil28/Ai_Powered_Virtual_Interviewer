"""
Dashboard Blueprint with Enhanced Resume Upload
Automatically parses resume and extracts skills using ML
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, send_file, flash
import os
import sqlite3

dashboard_bp = Blueprint("dashboard", __name__)
UPLOAD_FOLDER = os.path.abspath("uploads/resumes")
DB_PATH = "users.db"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def save_resume(email, file_path):
    """Save resume path to database"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Ensure resume_path column exists
    c.execute("PRAGMA table_info(students)")
    columns = [col[1] for col in c.fetchall()]

    if 'resume_path' not in columns:
        c.execute("ALTER TABLE students ADD COLUMN resume_path TEXT")

    # Ensure student exists
    c.execute("INSERT OR IGNORE INTO students (email) VALUES (?)", (email,))

    c.execute("UPDATE students SET resume_path = ? WHERE email = ?", (file_path, email))
    conn.commit()
    conn.close()


def get_resume_by_email(email):
    """Get resume path for student"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("PRAGMA table_info(students)")
    columns = [col[1] for col in c.fetchall()]

    if 'resume_path' not in columns:
        conn.close()
        return None

    c.execute("SELECT resume_path FROM students WHERE email = ?", (email,))
    result = c.fetchone()
    conn.close()

    return result[0] if result else None


def update_student_profile(email, skills=None, cgpa=None, graduation_year=None):
    """Update student profile"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Ensure student exists
    c.execute("INSERT OR IGNORE INTO students (email) VALUES (?)", (email,))

    updates = []
    params = []

    if skills is not None:
        updates.append("skills = ?")
        params.append(skills)

    if cgpa is not None:
        updates.append("cgpa = ?")
        params.append(cgpa)

    if graduation_year is not None:
        updates.append("graduation_year = ?")
        params.append(graduation_year)

    if updates:
        query = f"UPDATE students SET {', '.join(updates)} WHERE email = ?"
        params.append(email)
        c.execute(query, params)
        conn.commit()

    conn.close()


@dashboard_bp.route("/")
def dashboard():
    """Dashboard home page"""
    if "email" not in session:
        flash("Please log in first.", "danger")
        return redirect(url_for("auth.login"))

    email = session["email"]
    resume_path = get_resume_by_email(email)
    has_resume = resume_path is not None
    resume_filename = None
    if has_resume:
        resume_filename = os.path.basename(resume_path) if resume_path else None

    # Get selected company
    from utils import get_selected_company
    selected_company = get_selected_company(email)

    from database import get_user
    user = get_user(email)

    return render_template("dashboard.html",
                           username=session.get("name", email),
                           has_resume=has_resume,
                           resume_filename=resume_filename,
                           selected_company=selected_company,
                           user=user)


@dashboard_bp.route("/upload_resume", methods=["GET", "POST"])
def upload_resume():
    """Upload and parse resume with ML extraction"""
    if "email" not in session:
        flash("Please log in first.", "danger")
        return redirect(url_for("auth.login"))

    email = session["email"]
    resume_path = get_resume_by_email(email)

    if request.method == "POST":
        file = request.files.get("resume")
        if not file or file.filename == "":
            flash("No file selected.", "danger")
            return redirect(request.url)

        if not file.filename.lower().endswith(".pdf"):
            flash("Only PDF files are allowed.", "danger")
            return redirect(request.url)

        # Save file
        filename = f"{email}_resume.pdf"
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)

        print(f"Resume saved: {file_path}")

        # Parse resume using ml_company_matcher
        try:
            from ml_company_matcher import parse_resume
            print("Parsing resume with ML extraction...")

            parsed = parse_resume(file_path)

            if not parsed:
                flash("Resume uploaded but could not be parsed. Please ensure it's a valid PDF.", "warning")
                save_resume(email, file_path)
                return redirect(request.url)

            # Extract skills as comma-separated string
            skills_list = parsed.get('skills', [])
            skills_str = ", ".join(skills_list)

            if not skills_str:
                flash(
                    "Resume uploaded but no skills detected. Please ensure your resume contains programming languages and technologies.",
                    "warning")
                save_resume(email, file_path)
                return redirect(request.url)

            # Log extracted info
            cgpa = parsed.get('cgpa', 0) or 7.0
            grad_year = parsed.get('graduation_year', 0) or 2025

            print(f"Extracted CGPA: {cgpa}")
            print(f"Extracted Year: {grad_year}")
            print(f"Extracted Skills count: {len(skills_list)}")

            # Save to database
            save_resume(email, file_path)
            update_student_profile(
                email,
                skills=skills_str,
                cgpa=cgpa,
                graduation_year=grad_year
            )

            # Success messages
            flash("Resume uploaded and processed successfully!", "success")
            flash(f"Detected CGPA: {cgpa}", "info")
            flash(f"Graduation Year: {grad_year}", "info")
            flash(f"Skills Extracted: {len(skills_list)} skills", "info")
            flash("Visit Companies page to see your personalized recommendations!", "success")

            return redirect(url_for("dashboard.upload_resume"))

        except Exception as e:
            print(f"Error parsing resume: {e}")
            import traceback
            traceback.print_exc()

            flash(f"Resume uploaded but error during parsing: {str(e)}", "warning")
            save_resume(email, file_path)
            return redirect(request.url)

    return render_template("upload.html", resume=resume_path)


@dashboard_bp.route("/view_resume/<email>")
def view_resume(email):
    """View uploaded resume"""
    resume_path = get_resume_by_email(email)
    if not resume_path or not os.path.exists(resume_path):
        flash("No resume found.", "danger")
        return redirect(url_for("dashboard.upload_resume"))
    return send_file(resume_path, mimetype="application/pdf")


@dashboard_bp.route("/reparse_resume", methods=["POST"])
def reparse_resume():
    """Re-parse existing resume"""
    if "email" not in session:
        flash("Please log in first.", "danger")
        return redirect(url_for("auth.login"))

    email = session["email"]
    resume_path = get_resume_by_email(email)

    if not resume_path or not os.path.exists(resume_path):
        flash("No resume found. Please upload first.", "danger")
        return redirect(url_for("dashboard.upload_resume"))

    try:
        from ml_company_matcher import parse_resume

        print(f"Re-parsing resume for {email}...")
        parsed = parse_resume(resume_path)

        if not parsed:
            flash("Could not parse resume. Please upload a new one.", "danger")
            return redirect(url_for("dashboard.upload_resume"))

        # Extract skills
        skills_list = parsed.get('skills', [])
        skills_str = ", ".join(skills_list)
        cgpa = parsed.get('cgpa', 0) or 7.0
        grad_year = parsed.get('graduation_year', 0) or 2025

        update_student_profile(
            email,
            skills=skills_str,
            cgpa=cgpa,
            graduation_year=grad_year
        )

        flash("Resume re-parsed successfully!", "success")
        flash(f"Updated: {len(skills_list)} skills, CGPA: {cgpa}", "info")

    except Exception as e:
        print(f"Error re-parsing: {e}")
        flash(f"Error re-parsing resume: {str(e)}", "danger")

    return redirect(url_for("dashboard.upload_resume"))
