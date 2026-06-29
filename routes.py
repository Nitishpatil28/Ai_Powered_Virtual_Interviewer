from flask import Blueprint, jsonify, request, session, render_template, redirect, url_for, flash
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

# Blueprint setup
routes_bp = Blueprint('routes', __name__)
aptitude_bp = Blueprint('aptitude', __name__, url_prefix='/aptitude')

USERS_DB_PATH = 'users.db'
QUESTIONS_DB_PATH = 'questions.db'


# -----------------------------
# UTILITY: Ensure user login
# -----------------------------
def require_login():
    if 'email' not in session:
        flash('Please log in first.', 'danger')
        return False
    return True


def require_selected_company():
    """Ensure company is selected before accessing rounds."""
    if 'email' not in session:
        return False

    from utils import get_selected_company
    selected = get_selected_company(session['email'])
    if not selected:
        flash('Please select a company first to start practicing interview rounds.', 'info')
        return False
    return True


# -----------------------------
# DASHBOARD
# -----------------------------
@routes_bp.route('/dashboard')
def dashboard():
    if not require_login():
        return redirect(url_for('auth.login'))

    email = session["email"]
    from dashboard import get_resume_by_email
    resume_path = get_resume_by_email(email)
    has_resume = resume_path is not None
    resume_filename = None
    if has_resume:
        import os
        resume_filename = os.path.basename(resume_path) if resume_path else None

    # Get selected company
    from utils import get_selected_company
    selected_company = get_selected_company(email)

    from database import get_user
    user = get_user(email)

    return render_template('dashboard.html',
                           username=session.get('name'),
                           has_resume=has_resume,
                           resume_filename=resume_filename,
                           selected_company=selected_company,
                           user=user)


# -----------------------------
# COMPANY RECOMMENDATION FLOW
# -----------------------------
@routes_bp.route('/companies')
def companies():
    if not require_login():
        return redirect(url_for('auth.login'))

    from database import get_user, get_all_companies
    from utils import get_selected_company
    try:
        from ml_company_matcher import get_company_recommendations
    except ImportError:
        get_company_recommendations = None

    email = session['email']
    username = session.get('name', email)
    user = get_user(email)
    cgpa = user.get('cgpa', 0) if user else 0
    all_companies = get_all_companies()
    selected_company = get_selected_company(email)

    # Always show all companies for practice mode
    # Users can practice with ANY company without resume
    recommendations, recommended_ids = [], set()
    if get_company_recommendations:
        try:
            # Get recommendations for ALL companies, not just top ones
            recommendations = get_company_recommendations(email, top_k=100)  # Large number to get all
            recommended_ids = {r.get('company_id', r.get('id')) for r in recommendations}
        except Exception as e:
            print(f"⚠️ ML Recommendation Error: {e}")

    # Show all companies always - practice mode enabled
    companies_list = all_companies

    # Add recommendation data to companies
    rec_dict = {r['company_id']: r for r in recommendations}
    for company in companies_list:
        if company['id'] in rec_dict:
            rec = rec_dict[company['id']]
            company['match_percentage'] = rec['score_percent']
            company['rf_prediction'] = rec.get('rf_score', rec['score_percent'])  # Use RF score if available
            company['matching_features'] = rec['matching_features']
        else:
            # For companies without recommendations, set a default low score
            company['match_percentage'] = 5.0  # Minimum score for practice
            company['rf_prediction'] = 0
            company['dt_prediction'] = 0
            company['matching_features'] = []

    # For practice mode, show all companies with their match scores
    # Users can practice with ANY company regardless of match percentage
    eligible_companies = companies_list

    # Optional: Show info message about personalized recommendations
    from database import get_resume_by_email
    if not get_resume_by_email(email) and not recommendations:
        flash('Showing all companies for practice. Upload your resume for personalized recommendations.', 'info')

    return render_template('companies.html',
                           username=username,
                           companies=eligible_companies,
                           all_companies=all_companies,
                           selected_company=selected_company,
                           recommended_ids=recommended_ids,
                           cgpa=cgpa,
                           practice_mode=True)  # Enable practice mode flag


@routes_bp.route("/select_company/<int:company_id>", methods=["POST"])
def select_company(company_id):
    """
    User selects a company after resume match.
    Generates a company-specific test package from datasets.
    """
    if not session.get('email'):
        flash("Please login first!")
        return redirect(url_for('auth.login'))

    email = session['email']
    from database import get_all_companies
    from utils import set_selected_company
    companies = get_all_companies()
    company = next((c for c in companies if c['id'] == company_id), None)

    if not company:
        flash("Company not found!")
        return redirect(url_for("routes.companies"))

    # Store selected company in database and session
    set_selected_company(email, company_id)
    session["selected_company"] = company

    # Redirect back to companies page to show selected company and start buttons
    flash(f"Successfully selected {company['name']} for interview preparation!")
    return redirect(url_for("routes.companies"))


@routes_bp.route('/aptitude')
def aptitude():
    if not require_login():
        return redirect(url_for('auth.login'))
    if not require_selected_company():
        return redirect(url_for('routes.companies'))

    from utils import get_selected_company
    selected_company = get_selected_company(session['email'])
    practice_mode = session.get('practice_mode', True)

    return render_template('aptitude.html',
                           username=session.get('name'),
                           company=selected_company,
                           practice_mode=practice_mode)


@routes_bp.route('/technical')
def technical():
    if not require_login():
        return redirect(url_for('auth.login'))
    if not require_selected_company():
        return redirect(url_for('routes.companies'))

    from utils import get_selected_company
    selected_company = get_selected_company(session['email'])
    practice_mode = session.get('practice_mode', True)

    return render_template('technical.html',
                           username=session.get('name'),
                           company=selected_company,
                           practice_mode=practice_mode)


@routes_bp.route('/gd')
def gd():
    if not require_login():
        return redirect(url_for('auth.login'))
    if not require_selected_company():
        return redirect(url_for('routes.companies'))

    from utils import get_selected_company
    selected_company = get_selected_company(session['email'])
    practice_mode = session.get('practice_mode', True)

    return render_template('gd.html',
                           username=session.get('name'),
                           company=selected_company,
                           practice_mode=practice_mode)


@routes_bp.route('/hr_round')
def hr_round():
    if not require_login():
        return redirect(url_for('auth.login'))
    if not require_selected_company():
        return redirect(url_for('routes.companies'))

    from utils import get_selected_company
    selected_company = get_selected_company(session['email'])
    practice_mode = session.get('practice_mode', True)

    return render_template('hr.html',
                           username=session.get('name'),
                           company=selected_company,
                           practice_mode=practice_mode)


@routes_bp.route('/feedback')
def feedback():
    if not require_login():
        return redirect(url_for('auth.login'))
    if not require_selected_company():
        return redirect(url_for('routes.companies'))
    return render_template('feedback.html', username=session.get('name'))


# -----------------------------
# SETTINGS MODULE
# -----------------------------
@routes_bp.route('/settings', methods=['GET', 'POST'])
def settings():
    if not require_login():
        return redirect(url_for('auth.login'))

    from database import get_user, get_student, update_student, update_user_password

    email = session['email']
    username = session.get('name', email)
    user = get_user(email)
    student = get_student(email)

    # Merge user and student data for template
    if user and student:
        user.update(student)
    elif student:
        user = student

    if request.method == 'POST':
        # Handle profile updates (name and/or profile picture)
        if 'full_name' in request.form or 'profile_pic' in request.files:
            updated = False

            # Update full name if provided
            if 'full_name' in request.form:
                full_name = request.form.get('full_name').strip()
                if full_name:
                    update_student(email, name=full_name)
                    session['name'] = full_name
                    updated = True

            # Update profile picture if provided
            if 'profile_pic' in request.files:
                file = request.files['profile_pic']
                if file and file.filename:
                    filename = f"{email}_profile_{file.filename}"
                    filepath = os.path.join('static', 'images', 'profiles', filename)
                    os.makedirs(os.path.dirname(filepath), exist_ok=True)
                    file.save(filepath)
                    update_student(email, profile_pic=f'images/profiles/{filename}')
                    updated = True

            if updated:
                flash('Profile updated successfully!', 'success')

        # Handle password change
        elif 'current_password' in request.form:
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_new = request.form.get('confirm_new_password')
            if not check_password_hash(user['password'], current_password):
                flash('Current password incorrect.', 'danger')
            elif new_password != confirm_new:
                flash('Passwords do not match.', 'danger')
            elif len(new_password) < 6:
                flash('Password too short.', 'danger')
            else:
                update_user_password(email, generate_password_hash(new_password))
                flash('Password changed successfully.', 'success')

        return redirect(url_for('routes.settings'))

    return render_template('settings.html', username=username, user=user)


# -----------------------------
# APTITUDE MODULE - MOVED TO aptitude_routes.py
# -----------------------------
