import random
import json
import pdfplumber
import re
import sqlite3
import os
import smtplib
import ssl
from email.message import EmailMessage

# Ensure environment variables from .env are loaded when this module is imported
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    # dotenv is optional; if not present the app should have env vars set by other means
    pass

DB_PATH = "users.db"
# --- utils.py additions (paste after imports) ---

# Directory where company JSON files live (make sure this exists)
DATASET_DIR = r"C:\AI_Powered_Virtual_Interviewer\company_datasets"


def normalize_company_name(name: str) -> str:
    """Normalize DB company name to dataset filename (lowercase, underscores)."""
    return name.strip().lower().replace(" ", "_")


def get_company_name_by_id(company_id):
    """Return company name (string) for a given company_id from companies table."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name FROM companies WHERE id = ?", (company_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


def load_company_round(company, round_name, limit=None):
    """
    Load questions/topics for a company and round from company JSON file.

    - company: can be a dict (get_selected_company result) or a string name.
    - round_name: 'aptitude' | 'technical' | 'gd' | 'hr'
    - limit: number of items to return (random sample), or None -> return all
    """
    # Accept either a company dict, or a name string
    if isinstance(company, dict):
        company_name = company.get("name", "")
    else:
        company_name = company or ""

    if not company_name:
        return []

    filename = normalize_company_name(company_name) + ".json"
    path = os.path.join(DATASET_DIR, filename)

    if not os.path.exists(path):
        # no dataset found
        print(f"[load_company_round] dataset missing: {path}")
        return []

    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as e:
        print(f"[load_company_round] failed to load {path}: {e}")
        return []

    rounds = data.get("rounds", {})
    items = rounds.get(round_name, []) or []

    # Normalize items: ensure each item has id and expected keys
    normalized = []
    for idx, it in enumerate(items):
        new = dict(it)  # copy
        if "id" not in new:
            new["id"] = idx + 1
        # Standard fields for aptitude questions:
        # question, options (optional), correct_answer (optional), difficulty, category
        # for GD topics use 'topic' key
        normalized.append(new)

    if limit:
        if len(normalized) > limit:
            try:
                normalized = random.sample(normalized, limit)
            except Exception:
                normalized = normalized[:limit]

    return normalized
# --- end additions ---

# -------------------- Send Email (OTP demo) --------------------


def send_email(receiver_email, otp):
    """Send OTP email via configured SMTP server.

    This function requires the following environment variables to be set (for example
    in a `.env` file):
      - MAIL_SERVER (required)
      - MAIL_PORT (optional, default 587)
      - MAIL_USERNAME (optional)
      - MAIL_PASSWORD (optional)
      - MAIL_USE_TLS (optional, true/false)
      - MAIL_USE_SSL (optional, true/false)
      - MAIL_DEFAULT_SENDER (optional)

    Returns True on success, False on failure. No terminal printing or local OTP logging
    is performed — if SMTP is not configured or sending fails the caller should handle
    the error (and inform the user). This enforces sending via the configured email
    account instead of a console fallback.
    """
    mail_server = os.environ.get("MAIL_SERVER")
    if not mail_server:
        # Try loading .env now in case it was added after the app started
        try:
            from dotenv import load_dotenv
            load_dotenv()
            mail_server = os.environ.get("MAIL_SERVER")
        except Exception:
            pass

    if not mail_server:
        # Do not fallback to terminal logging — require proper SMTP configuration.
        print("[send_email] MAIL_SERVER not configured; cannot send OTP via email.")
        return False

    try:
        mail_port = int(os.environ.get("MAIL_PORT", 587))
    except ValueError:
        mail_port = 587

    mail_username = os.environ.get("MAIL_USERNAME")
    mail_password = os.environ.get("MAIL_PASSWORD")
    mail_use_tls = os.environ.get("MAIL_USE_TLS", "true").lower() in ("1", "true", "yes")
    mail_use_ssl = os.environ.get("MAIL_USE_SSL", "false").lower() in ("1", "true", "yes")
    mail_default_sender = os.environ.get("MAIL_DEFAULT_SENDER", mail_username or f"no-reply@{mail_server}")

    subject = "Your verification OTP"
    body = f"Your OTP code is: {otp}\nThis code is valid for a short time. Do not share it with anyone."

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = mail_default_sender
    msg["To"] = receiver_email
    msg.set_content(body)

    try:
        if mail_use_ssl:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(mail_server, mail_port, context=context) as server:
                if mail_username and mail_password:
                    server.login(mail_username, mail_password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(mail_server, mail_port, timeout=10) as server:
                if mail_use_tls:
                    server.starttls()
                if mail_username and mail_password:
                    server.login(mail_username, mail_password)
                server.send_message(msg)
        return True
    except Exception as e:
        # For production, we avoid printing OTPs. Log the error and return False.
        print(f"[send_email] failed to send OTP to {receiver_email}: {e}")
        return False

# -------------------- Initialize Company Database --------------------


def init_company_data():
    """Initialize company database with real companies and their criteria."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Check if companies already exist
    c.execute("SELECT COUNT(*) FROM companies")
    if c.fetchone()[0] > 0:
        conn.close()
        return

    companies_data = [
        # Tech Giants
        ("Google", 8.0, "Python,Machine Learning,Data Structures,Algorithms",
         2025, "Software Engineer", "25-30 LPA", "Bangalore", "Tech"),
        ("Microsoft", 7.5, "C++,Data Structures,Cloud Computing,Azure",
         2025, "Software Developer", "20-25 LPA", "Hyderabad", "Tech"),
        ("Amazon", 7.5, "Java,Python,AWS,System Design", 2025, "SDE-1", "18-24 LPA", "Bangalore", "Tech"),
        ("Meta", 8.5, "Python,React,Data Structures,System Design",
         2025, "Software Engineer", "28-35 LPA", "Bangalore", "Tech"),

        # Indian Tech Companies
        ("TCS", 6.0, "Java,SQL,C++", 2025, "Assistant System Engineer", "3.5-4 LPA", "Multiple", "IT Services"),
        ("Infosys", 6.5, "Python,Java,SQL", 2025, "System Engineer", "4-5 LPA", "Pune", "IT Services"),
        ("Wipro", 6.5, "Java,Python,Cloud", 2025, "Project Engineer", "3.5-4.5 LPA", "Bangalore", "IT Services"),
        ("Tech Mahindra", 6.0, "Java,Testing,SQL", 2025, "Software Engineer", "3.5-4 LPA", "Hyderabad", "IT Services"),

        # Product Companies
        ("Flipkart", 7.0, "Java,Python,System Design,Algorithms", 2025, "SDE-1", "12-18 LPA", "Bangalore", "E-commerce"),
        ("Swiggy", 7.0, "Python,Java,Data Structures", 2025, "Software Engineer", "10-15 LPA", "Bangalore", "Food Tech"),
        ("Paytm", 6.8, "Java,Python,SQL,API Development", 2025, "Software Developer", "8-12 LPA", "Noida", "Fintech"),
        ("Zomato", 7.0, "Python,Java,React", 2025, "Software Engineer", "10-14 LPA", "Gurgaon", "Food Tech"),

        # Startups
        ("Razorpay", 7.2, "Python,Java,Payment Systems,API", 2025,
         "Software Engineer", "12-18 LPA", "Bangalore", "Fintech"),
        ("CRED", 7.5, "Python,Kotlin,System Design", 2025, "Software Engineer", "15-20 LPA", "Bangalore", "Fintech"),
        ("Zerodha", 7.0, "Python,Trading Systems,Algorithms", 2025,
         "Software Developer", "12-16 LPA", "Bangalore", "Fintech"),

        # Consulting
        ("Deloitte", 7.0, "Data Analysis,SQL,Python,Business Intelligence",
         2025, "Analyst", "6-8 LPA", "Multiple", "Consulting"),
        ("Accenture", 6.5, "Java,Cloud,Testing", 2025, "Associate Software Engineer", "4.5-6 LPA", "Multiple", "Consulting"),
        ("Cognizant", 6.0, "Java,Python,Testing", 2025, "Programmer Analyst", "4-5 LPA", "Multiple", "IT Services"),
    ]

    c.executemany("""
        INSERT INTO companies (name, min_cgpa, required_skills, graduation_year, role, package_offered, location, industry)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, companies_data)

    conn.commit()
    conn.close()
    print("✅ Company database initialized with real companies!")


# -------------------- Parse Resume --------------------
def parse_resume(file_path, student_email):
    """Extract information from resume PDF."""
    text = ""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

    # Extract information using regex
    name_match = re.search(r"(?:Name|NAME)[:\-\s]*([\w\s]+)", text, re.I)
    email_match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
    cgpa_match = re.search(r"(\d\.\d{1,2})\s*(?:CGPA|GPA)", text, re.I)
    year_match = re.search(r"(?:Graduation|Expected|20)\s*(20\d{2})", text)

    # Skills extraction (expanded list)
    skill_keywords = [
        "Python", "Java", "C++", "JavaScript", "SQL", "React", "Node.js", "Angular",
        "Machine Learning", "AI", "Artificial Intelligence", "Data Science", "Deep Learning",
        "AWS", "Azure", "Cloud", "Docker", "Kubernetes",
        "Data Structures", "Algorithms", "System Design", "API",
        "HTML", "CSS", "MongoDB", "PostgreSQL", "MySQL",
        "Testing", "Selenium", "Jenkins", "Git", "GitHub",
        "Android", "iOS", "Flutter", "React Native", "Kotlin", "Swift"
    ]

    found_skills = []
    for skill in skill_keywords:
        if re.search(r'\b' + re.escape(skill) + r'\b', text, re.I):
            found_skills.append(skill)

    # Extract values
    student_name = name_match.group(1).strip() if name_match else "Unknown"
    extracted_email = email_match.group(0) if email_match else student_email
    student_cgpa = float(cgpa_match.group(1)) if cgpa_match else 7.0
    grad_year = int(year_match.group(1)) if year_match else 2025
    student_skills = ",".join(set(found_skills)) if found_skills else "General"

    # Save to database
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        INSERT INTO students (email, name, cgpa, graduation_year, skills)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(email) DO UPDATE SET
            name=excluded.name,
            cgpa=excluded.cgpa,
            graduation_year=excluded.graduation_year,
            skills=excluded.skills
    """, (student_email, student_name, student_cgpa, grad_year, student_skills))

    conn.commit()
    conn.close()

    return {
        "name": student_name,
        "email": extracted_email,
        "cgpa": student_cgpa,
        "graduation_year": grad_year,
        "skills": student_skills
    }


# -------------------- Match Companies (Rule-Based - Fallback) --------------------
def match_companies(student_email, use_ml=True):
    """
    Match student profile with suitable companies.

    Args:
        student_email: Student's email
        use_ml: If True, use ML models; if False, use rule-based approach
    """
    if use_ml:
        try:
            from ml_company_matcher import ml_recommend_companies
            return ml_recommend_companies(student_email, model_type="random_forest")
        except ImportError:
            print("ML company matcher not available in utils")
            return []
        except Exception as e:
            print(f"ML recommendation failed: {e}. Falling back to rule-based.")

    # Fallback to rule-based approach
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Get student details
    c.execute("SELECT * FROM students WHERE email=?", (student_email,))
    student = c.fetchone()

    if not student:
        conn.close()
        return []

    _, email, name, cgpa, grad_year, skills = student
    student_skills = set([s.strip().lower() for s in (skills or "").split(",")])

    # Get all companies
    c.execute("SELECT * FROM companies WHERE graduation_year=?", (grad_year,))
    companies = c.fetchall()
    conn.close()

    eligible_companies = []

    for comp in companies:
        comp_id, cname, min_cgpa, req_skills, comp_year, role, package, location, industry = comp
        required_skills = set([s.strip().lower() for s in (req_skills or "").split(",")])

        # Calculate skill match percentage
        matched_skills = student_skills.intersection(required_skills)
        skill_match_percent = (len(matched_skills) / len(required_skills) * 100) if required_skills else 0

        # Check eligibility
        is_eligible = cgpa >= min_cgpa and skill_match_percent >= 30

        if is_eligible:
            eligible_companies.append({
                "id": comp_id,
                "name": cname,
                "role": role,
                "package": package,
                "location": location,
                "industry": industry,
                "min_cgpa": min_cgpa,
                "required_skills": req_skills,
                "skill_match": round(skill_match_percent, 1),
                "matched_skills": list(matched_skills),
                "recommendation_type": "rule_based"
            })

    # Sort by skill match percentage
    eligible_companies.sort(key=lambda x: x.get('skill_match', 0), reverse=True)

    return eligible_companies


# -------------------- Set Selected Company (NEW LOCKING MECHANISM) --------------------
def set_selected_company(student_email, company_id):
    """Set the selected company for interview preparation (locked until logout)."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Get company name
    c.execute("SELECT name FROM companies WHERE id = ?", (company_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        raise ValueError("Invalid company ID")

    company_name = row[0]

    # Ensure student exists
    c.execute("INSERT OR IGNORE INTO students (email) VALUES (?)", (student_email,))

    # Update student's selected company
    c.execute("""
        UPDATE students
        SET selected_company_id = ?, selected_company_name = ?
        WHERE email = ?
    """, (company_id, company_name, student_email))

    conn.commit()
    conn.close()

    return {'id': company_id, 'name': company_name}


def clear_selected_company(student_email):
    """Clear the selected company (called on logout)."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        UPDATE students
        SET selected_company_id = NULL, selected_company_name = NULL
        WHERE email = ?
    """, (student_email,))

    conn.commit()
    conn.close()


# -------------------- Get Selected Company (NEW LOCKING MECHANISM) --------------------
def get_selected_company(student_email):
    """Get the student's selected company using new locking mechanism."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Read from students table
    c.execute("SELECT selected_company_id, selected_company_name FROM students WHERE email = ?", (student_email,))
    row = c.fetchone()

    if not row or not row[0]:
        conn.close()
        return None

    company_id, company_name = row

    # Get full company details
    c.execute("SELECT * FROM companies WHERE id = ?", (company_id,))
    company = c.fetchone()
    conn.close()

    if company:
        return {
            "id": company[0],
            "name": company[1],
            "min_cgpa": company[2],
            "required_skills": company[3] if len(company) > 3 else "",
            "graduation_year": company[4] if len(company) > 4 else 2025,
            "role": company[5] if len(company) > 5 else "",
            "package": company[6] if len(company) > 6 else "",
            "location": company[7] if len(company) > 7 else "",
            "industry": company[8] if len(company) > 8 else ""
        }
    elif company_name:
        # Return minimal data using stored name
        return {
            "id": company_id,
            "name": company_name,
            "min_cgpa": 0,
            "required_skills": "",
            "graduation_year": 2025,
            "role": "",
            "package": "",
            "location": "",
            "industry": ""
        }
    return None
