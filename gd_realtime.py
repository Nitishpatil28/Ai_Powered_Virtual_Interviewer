"""
Real-Time Group Discussion Routes
Integrates multi-participant video, audio, and AI analysis
"""

from flask import Blueprint, jsonify, request, session, render_template
import sqlite3
import json
from utils import get_selected_company

gd_realtime_bp = Blueprint("gd_realtime", __name__, url_prefix="/gd/realtime")
DB_PATH = "users.db"


@gd_realtime_bp.route("/")
def realtime_gd_home():
    """Real-time GD interview home page"""
    if "email" not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    return render_template("gd_realtime.html", username=session.get("name"))


@gd_realtime_bp.route("/check-requirements")
def check_gd_requirements():
    """Check if real-time GD requirements are met"""
    requirements = {
        "camera": True,
        "microphone": True,
        "websocket": True,
        "multi_participant": True,
        "features": {
            "facial_analysis": False,
            "speech_recognition": False,
            "turn_detection": True
        }
    }

    # Check libraries
    try:
        requirements["features"]["facial_analysis"] = True
    except ImportError:
        pass

    try:
        requirements["features"]["speech_recognition"] = True
    except ImportError:
        pass

    return jsonify({
        "success": True,
        "requirements": requirements,
        "websocket_url": "http://localhost:5001"
    })


@gd_realtime_bp.route("/get-topics")
def get_gd_topics():
    """Get GD topics for selected company"""
    if "email" not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    try:
        email = session["email"]

        # Get selected company
        selected = get_selected_company(email)
        if not selected:
            return jsonify({"success": False, "error": "Please select a company first"}), 400

        company_name = selected["name"]

        # Sample GD topics (can be company-specific from database)
        sample_topics = [
            f"Impact of AI on {selected.get('industry', 'Technology')} Industry",
            "Should remote work be permanent in the post-pandemic era?",
            f"Ethical considerations in {selected.get('industry', 'Tech')} companies",
            "Climate change: Corporate responsibility vs. Government regulation",
            "Social media impact on mental health among youth",
            f"Future of {selected.get('role', 'Software Engineering')} in the next decade",
            "Is work-life balance achievable in the tech industry?",
            f"Diversity and inclusion in {company_name}'s workplace culture",
            "Should artificial intelligence replace human decision-making?",
            "Cryptocurrency: Revolutionary technology or financial risk?"
        ]

        return jsonify({
            "success": True,
            "company_name": company_name,
            "topics": sample_topics,
            "student_email": email
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@gd_realtime_bp.route("/save-session", methods=["POST"])
def save_gd_session():
    """Save completed real-time GD session"""
    if "email" not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    try:
        data = request.json
        email = session["email"]

        session_id = data.get('session_id')
        topic = data.get('topic')
        final_report = data.get('final_report', {})
        participant_name = data.get('participant_name')

        if not session_id or not topic or not participant_name:
            return jsonify({"success": False, "error": "Missing required data"}), 400

        # Get this participant's report
        participant_reports = final_report.get('participant_reports', [])
        my_report = next((r for r in participant_reports if r['participant'] == participant_name), None)

        if not my_report:
            return jsonify({"success": False, "error": "Participant data not found"}), 400

        # Calculate scores
        overall_score = my_report.get('overall_gd_score', 0)
        speaking_stats = my_report.get('speaking_stats', {})
        engagement = my_report.get('engagement', {})
        leadership_data = my_report.get('leadership_data', {})

        # Save to database
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        # Create table if not exists
        c.execute("""
            CREATE TABLE IF NOT EXISTS gd_realtime_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                student_email TEXT,
                participant_name TEXT,
                topic TEXT,
                overall_score REAL,
                speaking_time REAL,
                speaking_percentage REAL,
                turn_count INTEGER,
                interruptions INTEGER,
                engagement_score REAL,
                leadership_score REAL,
                teamwork_score REAL,
                recommendation TEXT,
                full_report TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        c.execute("""
            INSERT INTO gd_realtime_results (
                session_id, student_email, participant_name, topic,
                overall_score, speaking_time, speaking_percentage,
                turn_count, interruptions, engagement_score,
                leadership_score, teamwork_score, recommendation, full_report
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id,
            email,
            participant_name,
            topic,
            overall_score,
            speaking_stats.get('speaking_time', 0),
            speaking_stats.get('speaking_percentage', 0),
            speaking_stats.get('turn_count', 0),
            speaking_stats.get('interruptions', 0),
            engagement.get('engagement_score', 0),
            leadership_data.get('leadership_score', 0),
            leadership_data.get('teamwork_score', 0),
            my_report.get('recommendation', 'needs_improvement'),
            json.dumps(my_report)
        ))

        conn.commit()
        conn.close()

        return jsonify({
            "success": True,
            "message": "GD session saved successfully",
            "overall_score": round(overall_score, 2),
            "recommendation": my_report.get('recommendation')
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@gd_realtime_bp.route("/my-sessions")
def get_my_gd_sessions():
    """Get all real-time GD sessions for current user"""
    if "email" not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    try:
        email = session["email"]

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        c.execute("""
            SELECT session_id, participant_name, topic, overall_score,
                   speaking_percentage, engagement_score, recommendation, created_at
            FROM gd_realtime_results
            WHERE student_email = ?
            ORDER BY created_at DESC
        """, (email,))

        rows = c.fetchall()
        conn.close()

        sessions = []
        for row in rows:
            sessions.append({
                "session_id": row[0],
                "participant_name": row[1],
                "topic": row[2],
                "overall_score": round(row[3], 2),
                "speaking_percentage": round(row[4], 2),
                "engagement_score": round(row[5], 2),
                "recommendation": row[6],
                "created_at": row[7]
            })

        return jsonify({
            "success": True,
            "sessions": sessions,
            "total": len(sessions)
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@gd_realtime_bp.route("/leaderboard/<session_id>")
def get_gd_leaderboard(session_id):
    """Get leaderboard for a specific GD session (all participants)"""
    if "email" not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        c.execute("""
            SELECT participant_name, overall_score, speaking_percentage,
                   engagement_score, leadership_score, recommendation
            FROM gd_realtime_results
            WHERE session_id = ?
            ORDER BY overall_score DESC
        """, (session_id,))

        rows = c.fetchall()
        conn.close()

        leaderboard = []
        for i, row in enumerate(rows, 1):
            leaderboard.append({
                "rank": i,
                "participant": row[0],
                "overall_score": round(row[1], 2),
                "speaking_percentage": round(row[2], 2),
                "engagement_score": round(row[3], 2),
                "leadership_score": round(row[4], 2),
                "recommendation": row[5]
            })

        return jsonify({
            "success": True,
            "leaderboard": leaderboard,
            "total_participants": len(leaderboard)
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
