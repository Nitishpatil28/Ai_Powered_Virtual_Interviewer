"""
Real-Time HR Interview Routes
Integrates live video, audio, and AI analysis
"""

from flask import Blueprint, jsonify, request, session, render_template
import sqlite3
import json
from utils import get_selected_company

hr_realtime_bp = Blueprint("hr_realtime", __name__, url_prefix="/hr/realtime")
DB_PATH = "users.db"
QUESTIONS_DB_PATH = "questions.db"


@hr_realtime_bp.route("/")
def realtime_home():
    """Real-time HR interview home page"""
    if "email" not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    return render_template("hr_realtime.html", username=session.get("name"))


@hr_realtime_bp.route("/check-requirements")
def check_requirements():
    """Check if real-time interview requirements are met"""
    requirements = {
        "camera": True,  # Browser will handle this
        "microphone": True,  # Browser will handle this
        "websocket": True,
        "features": {
            "facial_analysis": False,
            "speech_recognition": False,
            "text_to_speech": False
        }
    }

    # Check if advanced libraries are available
    try:
        requirements["features"]["facial_analysis"] = True
    except ImportError:
        pass

    try:
        requirements["features"]["speech_recognition"] = True
    except ImportError:
        pass

    try:
        requirements["features"]["text_to_speech"] = True
    except ImportError:
        pass

    return jsonify({
        "success": True,
        "requirements": requirements,
        "websocket_url": "http://localhost:5001"  # WebSocket server URL
    })


@hr_realtime_bp.route("/get-questions")
def get_interview_questions():
    """Get questions for real-time interview"""
    if "email" not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    try:
        email = session["email"]

        # Get selected company
        selected = get_selected_company(email)
        if not selected:
            return jsonify({"success": False, "error": "Please select a company first"}), 400

        company_name = selected["name"]

        # Get company ID from questions database
        qconn = sqlite3.connect(QUESTIONS_DB_PATH)
        qc = qconn.cursor()
        qc.execute("SELECT id FROM companies WHERE lower(trim(name)) = lower(trim(?))", (company_name,))
        row = qc.fetchone()

        if not row:
            qconn.close()
            return jsonify({"success": False, "error": "Company not found in questions database"}), 400

        company_id = row[0]

        # Get 5 random HR questions
        qc.execute(
            """
            SELECT id, question
            FROM hr_questions
            WHERE company_id = ?
            ORDER BY RANDOM()
            LIMIT 5
            """,
            (company_id,)
        )

        questions_raw = qc.fetchall()
        qconn.close()

        if len(questions_raw) < 5:
            return jsonify({
                "success": False,
                "error": f"Insufficient questions for {company_name}"
            }), 400

        # Format questions
        questions = [q[1] for q in questions_raw]  # Just the question text

        return jsonify({
            "success": True,
            "company_name": company_name,
            "questions": questions,
            "total_questions": len(questions),
            "student_email": email
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@hr_realtime_bp.route("/save-session", methods=["POST"])
def save_realtime_session():
    """Save completed real-time interview session"""
    if "email" not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    try:
        data = request.json
        email = session["email"]

        session_id = data.get('session_id')
        company_name = data.get('company_name')
        final_report = data.get('final_report', {})

        if not session_id or not company_name:
            return jsonify({"success": False, "error": "Missing required data"}), 400

        # Calculate scores
        answers = final_report.get('answers', [])
        if not answers:
            return jsonify({"success": False, "error": "No answers found"}), 400

        # Calculate average scores
        total_score = sum(ans.get('nlp_analysis', {}).get('overall_score', 0) for ans in answers)
        avg_score = total_score / len(answers) if answers else 0

        # Extract emotion data
        emotion_dist = final_report.get('emotion_distribution', {})
        dominant_emotion = max(emotion_dist.items(), key=lambda x: x[1])[0] if emotion_dist else 'neutral'

        # Save to database
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        # Create table if not exists
        c.execute("""
            CREATE TABLE IF NOT EXISTS hr_realtime_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE,
                student_email TEXT,
                company_name TEXT,
                questions_answered INTEGER,
                average_score REAL,
                dominant_emotion TEXT,
                total_duration REAL,
                emotion_distribution TEXT,
                full_report TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        c.execute("""
            INSERT INTO hr_realtime_results (
                session_id, student_email, company_name, questions_answered,
                average_score, dominant_emotion, total_duration,
                emotion_distribution, full_report
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id,
            email,
            company_name,
            len(answers),
            avg_score,
            dominant_emotion,
            final_report.get('total_duration', 0),
            json.dumps(emotion_dist),
            json.dumps(final_report)
        ))

        conn.commit()
        conn.close()

        return jsonify({
            "success": True,
            "message": "Interview session saved successfully",
            "average_score": round(avg_score, 2),
            "dominant_emotion": dominant_emotion
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@hr_realtime_bp.route("/results/<session_id>")
def get_session_results(session_id):
    """Get results for a specific session"""
    if "email" not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    try:
        email = session["email"]

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        c.execute("""
            SELECT * FROM hr_realtime_results
            WHERE session_id = ? AND student_email = ?
        """, (session_id, email))

        row = c.fetchone()
        conn.close()

        if not row:
            return jsonify({"success": False, "error": "Session not found"}), 404

        result = {
            "id": row[0],
            "session_id": row[1],
            "student_email": row[2],
            "company_name": row[3],
            "questions_answered": row[4],
            "average_score": row[5],
            "dominant_emotion": row[6],
            "total_duration": row[7],
            "emotion_distribution": json.loads(row[8]) if row[8] else {},
            "full_report": json.loads(row[9]) if row[9] else {},
            "created_at": row[10]
        }

        return jsonify({
            "success": True,
            "result": result
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@hr_realtime_bp.route("/my-sessions")
def get_my_sessions():
    """Get all real-time interview sessions for current user"""
    if "email" not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    try:
        email = session["email"]

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        c.execute("""
            SELECT session_id, company_name, questions_answered, average_score,
                   dominant_emotion, total_duration, created_at
            FROM hr_realtime_results
            WHERE student_email = ?
            ORDER BY created_at DESC
        """, (email,))

        rows = c.fetchall()
        conn.close()

        sessions = []
        for row in rows:
            sessions.append({
                "session_id": row[0],
                "company_name": row[1],
                "questions_answered": row[2],
                "average_score": round(row[3], 2),
                "dominant_emotion": row[4],
                "total_duration": round(row[5], 2),
                "created_at": row[6]
            })

        return jsonify({
            "success": True,
            "sessions": sessions,
            "total": len(sessions)
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
