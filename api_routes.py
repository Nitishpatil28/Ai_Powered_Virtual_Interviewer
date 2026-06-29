"""
API Routes for AI-Powered Virtual Interviewer
Handles all API endpoints for the interview system
"""

from flask import Blueprint, jsonify, request, session
import sqlite3
from datetime import datetime

api_bp = Blueprint("api", __name__, url_prefix="/api")

DB_PATH = "users.db"


@api_bp.route("/health")
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    })


@api_bp.route("/student/profile", methods=["GET"])
def get_student_profile():
    """Get student profile information"""
    if "email" not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    try:
        email = session["email"]

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT * FROM students WHERE email = ?", (email,))
        student = c.fetchone()
        conn.close()

        if not student:
            return jsonify({"success": False, "error": "Student not found"}), 404

        return jsonify({
            "success": True,
            "profile": {
                "id": student[0],
                "email": student[1],
                "name": student[2],
                "cgpa": student[3],
                "graduation_year": student[4],
                "skills": student[5]
            }
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/student/profile", methods=["PUT"])
def update_student_profile():
    """Update student profile information"""
    if "email" not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    try:
        data = request.json
        email = session["email"]

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        # Update profile
        updates = []
        params = []

        if 'name' in data:
            updates.append("name = ?")
            params.append(data['name'])
        if 'cgpa' in data:
            updates.append("cgpa = ?")
            params.append(data['cgpa'])
        if 'graduation_year' in data:
            updates.append("graduation_year = ?")
            params.append(data['graduation_year'])
        if 'skills' in data:
            updates.append("skills = ?")
            params.append(data['skills'])

        if updates:
            params.append(email)
            query = f"UPDATE students SET {', '.join(updates)} WHERE email = ?"
            c.execute(query, params)
            conn.commit()

        conn.close()

        return jsonify({"success": True, "message": "Profile updated successfully"})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/companies/recommendations", methods=["GET"])
def get_company_recommendations():
    """Get AI-powered company recommendations"""
    if "email" not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    try:
        from utils import match_companies
        email = session["email"]

        # Get ML-based recommendations
        recommendations = match_companies(email, use_ml=True)

        return jsonify({
            "success": True,
            "recommendations": recommendations,
            "total": len(recommendations)
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/interview/status", methods=["GET"])
def get_interview_status():
    """Get overall interview completion status"""
    if "email" not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    try:
        email = session["email"]

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        # Check completion status for each round
        status = {
            "aptitude": {"completed": False, "score": 0, "attempts": 0},
            "technical": {"completed": False, "score": 0, "attempts": 0},
            "gd": {"completed": False, "score": 0, "attempts": 0},
            "hr": {"completed": False, "score": 0, "attempts": 0}
        }

        # Aptitude status
        c.execute("""
            SELECT COUNT(*), AVG(score)
            FROM test_attempts
            WHERE student_email = ? AND status = 'completed'
        """, (email,))
        apt_result = c.fetchone()
        if apt_result[0] > 0:
            status["aptitude"]["completed"] = True
            status["aptitude"]["score"] = apt_result[1] or 0
            status["aptitude"]["attempts"] = apt_result[0]

        # Technical status
        c.execute("""
            SELECT COUNT(*), AVG(score)
            FROM technical_results
            WHERE student_email = ?
        """, (email,))
        tech_result = c.fetchone()
        if tech_result[0] > 0:
            status["technical"]["completed"] = True
            status["technical"]["score"] = tech_result[1] or 0
            status["technical"]["attempts"] = tech_result[0]

        # GD status
        c.execute("""
            SELECT COUNT(*), AVG(overall_score)
            FROM gd_results
            WHERE student_email = ?
        """, (email,))
        gd_result = c.fetchone()
        if gd_result[0] > 0:
            status["gd"]["completed"] = True
            status["gd"]["score"] = gd_result[1] or 0
            status["gd"]["attempts"] = gd_result[0]

        # HR status
        c.execute("""
            SELECT COUNT(*), AVG(overall_score)
            FROM hr_results
            WHERE student_email = ?
        """, (email,))
        hr_result = c.fetchone()
        if hr_result[0] > 0:
            status["hr"]["completed"] = True
            status["hr"]["score"] = hr_result[1] or 0
            status["hr"]["attempts"] = hr_result[0]

        conn.close()

        # Calculate overall completion
        completed_rounds = sum(1 for round_status in status.values() if round_status["completed"])
        total_rounds = len(status)
        overall_progress = (completed_rounds / total_rounds) * 100

        return jsonify({
            "success": True,
            "status": status,
            "overall_progress": round(overall_progress, 2),
            "completed_rounds": completed_rounds,
            "total_rounds": total_rounds
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/analytics/performance", methods=["GET"])
def get_performance_analytics():
    """Get detailed performance analytics"""
    if "email" not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    try:
        email = session["email"]

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        analytics = {
            "aptitude_analytics": [],
            "technical_analytics": [],
            "gd_analytics": [],
            "hr_analytics": []
        }

        # Aptitude analytics by topic
        c.execute("""
            SELECT topic, AVG(score), COUNT(*), MAX(score), MIN(score)
            FROM test_attempts
            WHERE student_email = ? AND status = 'completed'
            GROUP BY topic
        """, (email,))
        for row in c.fetchall():
            analytics["aptitude_analytics"].append({
                "topic": row[0],
                "avg_score": round(row[1], 2),
                "attempts": row[2],
                "max_score": row[3],
                "min_score": row[4]
            })

        # Technical analytics by domain
        c.execute("""
            SELECT domain, AVG(score), COUNT(*), MAX(score), MIN(score)
            FROM technical_results
            WHERE student_email = ?
            GROUP BY domain
        """, (email,))
        for row in c.fetchall():
            analytics["technical_analytics"].append({
                "domain": row[0],
                "avg_score": round(row[1], 2),
                "attempts": row[2],
                "max_score": row[3],
                "min_score": row[4]
            })

        # GD analytics
        c.execute("""
            SELECT AVG(fluency_score), AVG(clarity_score), AVG(confidence_score),
                   AVG(overall_score), COUNT(*)
            FROM gd_results
            WHERE student_email = ?
        """, (email,))
        gd_row = c.fetchone()
        if gd_row[4] > 0:
            analytics["gd_analytics"] = {
                "avg_fluency": round(gd_row[0], 2),
                "avg_clarity": round(gd_row[1], 2),
                "avg_confidence": round(gd_row[2], 2),
                "avg_overall": round(gd_row[3], 2),
                "total_attempts": gd_row[4]
            }

        # HR analytics
        c.execute("""
            SELECT AVG(clarity_score), AVG(relevance_score), AVG(confidence_score),
                   AVG(overall_score), COUNT(*)
            FROM hr_results
            WHERE student_email = ?
        """, (email,))
        hr_row = c.fetchone()
        if hr_row[4] > 0:
            analytics["hr_analytics"] = {
                "avg_clarity": round(hr_row[0], 2),
                "avg_relevance": round(hr_row[1], 2),
                "avg_confidence": round(hr_row[2], 2),
                "avg_overall": round(hr_row[3], 2),
                "total_attempts": hr_row[4]
            }

        conn.close()

        return jsonify({
            "success": True,
            "analytics": analytics
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/dashboard/summary", methods=["GET"])
def get_dashboard_summary():
    """Get comprehensive dashboard summary"""
    if "email" not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    try:
        email = session["email"]

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        # Get student info
        c.execute("SELECT * FROM students WHERE email = ?", (email,))
        student = c.fetchone()

        # Get selected company
        c.execute("""
            SELECT c.name FROM companies c
            JOIN selected_companies sc ON c.id = sc.company_id
            WHERE sc.student_email = ?
            ORDER BY sc.selected_at DESC
            LIMIT 1
        """, (email,))
        company_result = c.fetchone()
        selected_company = company_result[0] if company_result else None

        # Get recent activity
        recent_activity = []

        # Recent aptitude attempts
        c.execute("""
            SELECT 'aptitude' as type, topic, score, submitted_at
            FROM test_attempts
            WHERE student_email = ? AND status = 'completed'
            ORDER BY submitted_at DESC
            LIMIT 3
        """, (email,))
        for row in c.fetchall():
            recent_activity.append({
                "type": row[0],
                "description": f"Aptitude test in {row[1]}",
                "score": row[2],
                "date": row[3]
            })

        # Recent technical attempts
        c.execute("""
            SELECT 'technical' as type, domain, score, submitted_at
            FROM technical_results
            WHERE student_email = ?
            ORDER BY submitted_at DESC
            LIMIT 3
        """, (email,))
        for row in c.fetchall():
            recent_activity.append({
                "type": row[0],
                "description": f"Technical interview in {row[1]}",
                "score": row[2],
                "date": row[3]
            })

        # Sort by date
        recent_activity.sort(key=lambda x: x['date'], reverse=True)
        recent_activity = recent_activity[:5]

        conn.close()

        return jsonify({
            "success": True,
            "student": {
                "name": student[2] if student else "Unknown",
                "email": student[1] if student else email,
                "cgpa": student[3] if student else 0,
                "skills": student[5] if student else ""
            },
            "selected_company": selected_company,
            "recent_activity": recent_activity
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
