"""
Group Discussion (GD) Module
Handles GD topics, speech recognition, and AI-powered evaluation
"""

import os
from flask import Blueprint, jsonify, request, session, render_template
import sqlite3
import json
import random
from ai_service import SpeechToTextService, NLPAnalysisService
from utils import get_selected_company
import selection

gd_bp = Blueprint("gd", __name__, url_prefix="/gd")

DB_PATH = "users.db"
QUESTIONS_DB_PATH = "questions.db"
speech_service = SpeechToTextService()
nlp_service = NLPAnalysisService()


def init_gd_topics():
    """
    Initialize GD topics from JSON datasets (e.g., datasets/accenture_gd.json).
    Runs once at startup if gd_topics table is empty.
    """
    try:
        conn = sqlite3.connect(QUESTIONS_DB_PATH)
        c = conn.cursor()

        # Ensure gd_topics table exists
        c.execute("""
            CREATE TABLE IF NOT EXISTS gd_topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER,
                topic TEXT,
                description TEXT,
                category TEXT,
                difficulty TEXT,
                tags TEXT,
                time_limit INTEGER DEFAULT 180,
                active INTEGER DEFAULT 1,
                quality_score REAL DEFAULT 0.0,
                FOREIGN KEY(company_id) REFERENCES companies(id)
            )
        """)

        # Check if already loaded
        c.execute("SELECT COUNT(*) FROM gd_topics")
        count = c.fetchone()[0]
        if count > 0:
            print(f"[GD INIT] {count} topics already loaded. Skipping import.")
            conn.close()
            return

        print("[GD INIT] Loading GD topics from datasets/...")

        DATASET_DIR = "datasets"
        for file in os.listdir(DATASET_DIR):
            if file.endswith("_gd.json"):
                company_name = file.replace("_gd.json", "").capitalize()
                file_path = os.path.join(DATASET_DIR, file)

                # Fetch company_id
                c.execute("SELECT id FROM companies WHERE lower(name)=lower(?)", (company_name,))
                row = c.fetchone()
                if not row:
                    print(f"[GD INIT] ⚠️ Company '{company_name}' not found in DB. Skipping.")
                    continue

                company_id = row[0]
                print(f"[GD INIT] → Importing GD topics for {company_name}")

                # Load JSON
                with open(file_path, "r", encoding="utf-8") as f:
                    topics = json.load(f)

                for topic in topics:
                    c.execute("""
                        INSERT INTO gd_topics (
                            company_id, topic, description, category, difficulty, tags,
                            time_limit, active, quality_score
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        company_id,
                        topic.get("topic", "Untitled Topic"),
                        topic.get("description", ""),
                        topic.get("category", "General"),
                        topic.get("difficulty", "Medium"),
                        ", ".join(topic.get("tags", [])) if isinstance(topic.get("tags"), list) else "",
                        topic.get("time_limit", 180),
                        1,
                        topic.get("quality_score", 0.0)
                    ))

        conn.commit()
        conn.close()
        print("[GD INIT] ✅ All GD topics loaded successfully!")

    except Exception as e:
        print(f"[GD INIT] ❌ Error loading GD topics: {e}")


@gd_bp.route("/")
def gd_home():
    """GD simulation home page"""
    if "email" not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    return render_template("gd.html", username=session.get("name"))


@gd_bp.route("/preview", methods=["GET"])
def preview_gd_topic():
    """Preview multiple GD topics for the simulation session"""
    if "email" not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    try:
        email = session["email"]

        selected = get_selected_company(email)
        if not selected:
            return jsonify({"success": False, "error": "Please select a company first"}), 400
        company_name = selected["name"]

        # Map to company_id in questions.db
        qconn = sqlite3.connect(QUESTIONS_DB_PATH)
        qc = qconn.cursor()
        company_id = None
        if company_name:
            qc.execute("SELECT id FROM companies WHERE lower(trim(name)) = lower(trim(?))", (company_name,))
            cid_row = qc.fetchone()
            company_id = cid_row[0] if cid_row else None

        if not company_id:
            qconn.close()
            return jsonify({"success": False, "error": "Please select a company first"}), 400

        # Load multiple topics for the GD session (at least 2, up to 3)
        topics = []
        for i in range(3):  # Try to get up to 3 topics
            try:
                topic_data = selection.select_gd_topic(company_id, email)
                if topic_data:
                    topics.append({
                        'id': topic_data['id'],
                        'topic': topic_data['topic'],
                        'description': topic_data['description'],
                        'time_limit': topic_data['time_limit'] if topic_data['time_limit'] else 180
                    })
                    # Log served event for analytics
                    selection.record_event(
                        email=email,
                        company_name=company_name,
                        question_type='gd',
                        question_id=topic_data['id'],
                        event='served'
                    )
                else:
                    break
            except Exception as e:
                print(f"Error selecting topic {i+1}: {e}")
                break

        qconn.close()

        if len(topics) < 2:
            return jsonify({"success": False, "error": "Need at least 2 topics for GD simulation"}), 404

        return jsonify({
            "success": True,
            "company": company_name,
            "topics": topics,
            "current_topic_index": 0,
            "total_topics": len(topics)
        })

    except Exception as e:
        print(f"Error previewing GD topics: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@gd_bp.route("/company-questions/<company_name>", methods=["GET"])
def get_company_gd_questions(company_name):
    """Get company-specific GD questions/topics"""
    if "email" not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    try:
        # Map to company_id in questions.db
        qconn = sqlite3.connect(QUESTIONS_DB_PATH)
        qc = qconn.cursor()
        company_id = None
        if company_name:
            qc.execute("SELECT id FROM companies WHERE lower(trim(name)) = lower(trim(?))", (company_name,))
            cid_row = qc.fetchone()
            company_id = cid_row[0] if cid_row else None

        if not company_id:
            qconn.close()
            return jsonify({"success": False, "error": "Company not found"}), 404

        # Get GD topics for this company
        qc.execute("""
            SELECT id, topic, description, category, difficulty, tags
            FROM gd_topics
            WHERE company_id = ? AND active = 1
            ORDER BY quality_score DESC, RANDOM()
            LIMIT 10
        """, (company_id,))

        questions = []
        for row in qc.fetchall():
            questions.append({
                'id': row[0],
                'topic': row[1],
                'description': row[2] or '',
                'category': row[3] or 'General',
                'difficulty': row[4] or 'Medium',
                'tags': row[5] or ''
            })

        qconn.close()

        return jsonify({
            "success": True,
            "company": company_name,
            "questions": questions
        })

    except Exception as e:
        print(f"Error getting company GD questions: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@gd_bp.route("/start", methods=["POST"])
def start_gd_session():
    """Start a GD session with a random topic"""
    if "email" not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    try:
        email = session["email"]

        selected = get_selected_company(email)
        if not selected:
            return jsonify({"success": False, "error": "Please select a company first"}), 400
        company_name = selected["name"]

        # Map to company_id in questions.db
        qconn = sqlite3.connect(QUESTIONS_DB_PATH)
        qc = qconn.cursor()
        company_id = None
        if company_name:
            qc.execute("SELECT id FROM companies WHERE lower(trim(name)) = lower(trim(?))", (company_name,))
            cid_row = qc.fetchone()
            company_id = cid_row[0] if cid_row else None

        if not company_id:
            qconn.close()
            return jsonify({"success": False, "error": "Please select a company first"}), 400

        qconn.close()

        # Use intelligent selection for GD topic (adaptive, non-repeating, balanced)
        topic_data = selection.select_gd_topic(company_id, email)

        if not topic_data:
            return jsonify({"success": False, "error": "No topics available"}), 404

        # Log served event for analytics
        selection.record_event(
            email=email,
            company_name=company_name,
            question_type='gd',
            question_id=topic_data['id'],
            event='served'
        )

        topic_id = topic_data['id']
        topic = topic_data['topic']
        description = topic_data['description']
        time_limit = topic_data['time_limit']

        return jsonify({
            "success": True,
            "company": company_name,
            "topic_id": topic_id,
            "topic": topic,
            "description": description,
            "difficulty": "Medium",
            "time_limit": time_limit if time_limit else 180
        })

    except Exception as e:
        print(f"Error starting GD session: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@gd_bp.route("/transcribe", methods=["POST"])
def transcribe_audio():
    """Transcribe audio to text using speech recognition"""
    if "email" not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    try:
        # In a real implementation, you would handle file upload here
        # For now, we'll simulate transcription
        data = request.json
        audio_data = data.get('audio_data', '')

        # Simulate transcription (in real app, use speech_service.transcribe_audio)
        # For demo purposes, return a sample transcript
        sample_transcripts = [
            "I believe that artificial intelligence will revolutionize the way we work. However, we need to ensure that it complements human skills rather than replacing them entirely. The key is to focus on upskilling and reskilling the workforce.",
            "From my perspective, remote work has both advantages and disadvantages. While it offers flexibility and work-life balance, it can also lead to isolation and communication challenges. Companies need to find the right balance.",
            "Digital transformation is crucial for India's growth. We need to bridge the digital divide between urban and rural areas and ensure that technology benefits everyone, not just the privileged few."]

        transcript = random.choice(sample_transcripts)

        return jsonify({
            "success": True,
            "transcript": transcript,
            "confidence": random.uniform(0.85, 0.95)
        })

    except Exception as e:
        print(f"Error transcribing audio: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@gd_bp.route("/evaluate", methods=["POST"])
def evaluate_gd_performance():
    """Evaluate GD performance using rigorous AI-driven analysis for realistic group discussions"""
    if "email" not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    try:
        data = request.json
        transcript = data.get('transcript', '')
        topic_id = data.get('topic_id')
        duration = data.get('duration', 0)
        participant_transcripts = data.get('participant_transcripts', {})
        discussion_flow = data.get('discussion_flow', [])
        rounds_completed = data.get('rounds_completed', 0)
        topics_discussed = data.get('topics_discussed', [])
        total_topics = data.get('total_topics', 1)

        if not transcript.strip():
            return jsonify({"success": False, "error": "No transcript provided"}), 400

        # Get user's transcript specifically
        user_transcript = participant_transcripts.get('You (User)', '')
        user_transcript_length = len(user_transcript.split()) if user_transcript else 0

        # Analyze transcript using NLP with more rigorous criteria
        analysis_result = nlp_service.analyze_text(user_transcript) if user_transcript else {}

        # Calculate participation metrics
        user_entries = [entry for entry in discussion_flow if entry.get('isUser')]
        total_possible_entries = rounds_completed * \
            len([p for p in [{'name': 'You (User)', 'isUser': True}] if p['isUser']])
        participation_rate = len(user_entries) / max(total_possible_entries, 1)

        # Rigorous scoring algorithm - much tougher standards
        base_clarity = 30  # Start low, require excellence to reach high scores
        base_confidence = 25
        base_content = 20
        base_teamwork = 35
        base_leadership = 25

        # Content analysis - very strict
        if user_transcript_length > 200:  # Substantial contribution required
            content_score = min(95, base_content + (user_transcript_length * 0.15))
        elif user_transcript_length > 100:
            content_score = min(80, base_content + (user_transcript_length * 0.25))
        else:
            content_score = max(10, base_content + (user_transcript_length * 0.3))

        # Clarity analysis - check for sophisticated vocabulary and structure
        clarity_score = base_clarity
        if user_transcript:
            # Check for complex sentences (contains semicolons, dashes, etc.)
            complex_indicators = [';', '—', 'however', 'therefore', 'moreover', 'consequently']
            complex_count = sum(1 for indicator in complex_indicators if indicator in user_transcript.lower())
            clarity_score += complex_count * 8

            # Check for filler words (penalty)
            filler_words = ['um', 'uh', 'like', 'you know', 'sort of', 'kind of', 'basically']
            filler_count = sum(1 for filler in filler_words if filler in user_transcript.lower())
            clarity_score -= filler_count * 5

            # Length bonus for detailed explanations
            clarity_score += min(20, user_transcript_length / 10)

        clarity_score = max(5, min(100, clarity_score))

        # Confidence analysis - based on assertiveness and lack of hesitation
        confidence_score = base_confidence
        if user_transcript:
            # Confident language indicators
            confident_words = ['certainly', 'definitely', 'absolutely', 'clearly', 'obviously', 'believe', 'convince']
            confident_count = sum(1 for word in confident_words if word in user_transcript.lower())
            confidence_score += confident_count * 6

            # Penalty for tentative language
            tentative_words = ['maybe', 'perhaps', 'might', 'could', 'possibly', 'i think', 'i feel']
            tentative_count = sum(1 for phrase in tentative_words if phrase in user_transcript.lower())
            confidence_score -= tentative_count * 4

            # Participation bonus
            confidence_score += participation_rate * 25

        confidence_score = max(5, min(100, confidence_score))

        # Teamwork analysis - based on engagement and collaboration
        teamwork_score = base_teamwork
        if user_transcript:
            # Check for collaborative language
            collaborative_words = [
                'agree',
                'building on',
                'similarly',
                'also',
                'additionally',
                'together',
                'collectively']
            collab_count = sum(1 for word in collaborative_words if word in user_transcript.lower())
            teamwork_score += collab_count * 7

            # Check for engagement with others' points
            engagement_indicators = ['previous speaker', 'colleague', 'point', 'perspective', 'view']
            engagement_count = sum(1 for indicator in engagement_indicators if indicator in user_transcript.lower())
            teamwork_score += engagement_count * 5

            # Participation consistency
            teamwork_score += participation_rate * 30

        teamwork_score = max(10, min(100, teamwork_score))

        # Leadership analysis - based on initiative and influence
        leadership_score = base_leadership
        if user_transcript:
            # Leadership indicators
            leadership_words = [
                'suggest',
                'propose',
                'recommend',
                'important',
                'crucial',
                'key',
                'essential',
                'therefore']
            leadership_count = sum(1 for word in leadership_words if word in user_transcript.lower())
            leadership_score += leadership_count * 8

            # Initiative indicators
            initiative_words = ['let me', 'i would like to', 'consider', 'think about', 'approach', 'solution']
            initiative_count = sum(1 for phrase in initiative_words if phrase in user_transcript.lower())
            leadership_score += initiative_count * 6

            # Content volume bonus
            leadership_score += min(15, user_transcript_length / 15)

        leadership_score = max(5, min(100, leadership_score))

        # Grammar score - maintained separately
        grammar_score = min(100, max(40, 70 + (user_transcript_length / 6)))

        # Calculate overall with weighted scoring (tougher standards)
        weights = {
            'clarity': 0.20,
            'confidence': 0.20,
            'content': 0.25,
            'teamwork': 0.20,
            'leadership': 0.15
        }

        overall_score = (
            clarity_score * weights['clarity'] +
            confidence_score * weights['confidence'] +
            content_score * weights['content'] +
            teamwork_score * weights['teamwork'] +
            leadership_score * weights['leadership']
        )

        # Additional penalties for poor performance
        if participation_rate < 0.6:  # Less than 60% participation
            overall_score -= 25
        if user_transcript_length < 50:  # Very short contribution
            overall_score -= 30
        if clarity_score < 40:  # Poor clarity
            overall_score -= 15

        overall_score = max(0, min(100, overall_score))

        # Get topic details from questions.db
        qconn = sqlite3.connect(QUESTIONS_DB_PATH)
        qc = qconn.cursor()
        qc.execute(
            """
            SELECT t.topic, c.name
            FROM gd_topics t
            JOIN companies c ON t.company_id = c.id
            WHERE t.id = ?
            """,
            (topic_id,)
        )
        topic_result = qc.fetchone()
        qconn.close()
        topic_name = topic_result[0] if topic_result else "General Topic"
        company_name = topic_result[1] if topic_result else "General"

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            INSERT INTO gd_results
            (student_email, company_name, topic_id, transcript, fluency_score,
             clarity_score, confidence_score, grammar_score, content_score,
             teamwork_score, leadership_score, overall_score, feedback)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session["email"], company_name, topic_id, transcript,
            round(grammar_score, 2), round(clarity_score, 2),  # fluency_score -> grammar_score
            round(confidence_score, 2), round(grammar_score, 2),
            round(content_score, 2), round(teamwork_score, 2),
            round(leadership_score, 2), round(overall_score, 2),
            json.dumps({
                'participation_rate': participation_rate,
                'rounds_completed': rounds_completed,
                'user_transcript_length': user_transcript_length,
                'discussion_flow': discussion_flow,
                'topics_discussed': topics_discussed,
                'total_topics': total_topics,
                'rigorous_evaluation': True,
                'feedback': analysis_result.get('feedback', {})
            })
        ))

        conn.commit()
        conn.close()

        # Log answer event for analytics
        selection.record_event(
            email=session["email"],
            company_name=company_name,
            question_type='gd',
            question_id=topic_id,
            event='answered',
            score=overall_score,
            time_spent=int(duration)
        )

        return jsonify({
            "success": True,
            "scores": {
                "fluency": round(grammar_score, 2),  # Map grammar to fluency for frontend
                "clarity": round(clarity_score, 2),
                "confidence": round(confidence_score, 2),
                "grammar": round(grammar_score, 2),
                "content": round(content_score, 2),
                "teamwork": round(teamwork_score, 2),
                "leadership": round(leadership_score, 2),
                "overall": round(overall_score, 2)
            },
            "feedback": {
                'participation_rate': f"{participation_rate*100:.1f}%",
                'transcript_quality': 'excellent' if overall_score >= 80 else 'good' if overall_score >= 60 else 'needs_improvement',
                'strengths': [],
                'areas_for_improvement': [],
                'recommendations': []
            },
            "topic": topic_name,
            "company": company_name,
            "rounds_completed": rounds_completed,
            "participation_rate": participation_rate,
            "can_continue": True
        })

    except Exception as e:
        print(f"Error evaluating GD performance: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@gd_bp.route("/history", methods=["GET"])
def get_gd_history():
    """Get student's GD performance history"""
    if "email" not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    try:
        email = session["email"]

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            SELECT gr.overall_score, gr.fluency_score, gr.clarity_score,
                   gr.confidence_score, gr.submitted_at, t.topic, c.name
            FROM gd_results gr
            JOIN gd_topics t ON gr.topic_id = t.id
            JOIN companies c ON t.company_id = c.id
            WHERE gr.student_email = ?
            ORDER BY gr.submitted_at DESC
            LIMIT 10
        """, (email,))

        history = []
        for row in c.fetchall():
            history.append({
                "overall_score": row[0],
                "fluency_score": row[1],
                "clarity_score": row[2],
                "confidence_score": row[3],
                "submitted_at": row[4],
                "topic": row[5],
                "company": row[6]
            })

        conn.close()

        return jsonify({
            "success": True,
            "history": history
        })

    except Exception as e:
        print(f"Error getting GD history: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


def generate_gd_feedback(scores, transcript):
    """Generate personalized feedback for GD performance"""
    feedback = {
        "strengths": [],
        "improvements": [],
        "recommendations": []
    }

    overall_score = scores.get('overall', 0)

    if overall_score >= 80:
        feedback["strengths"].append("Excellent communication skills")
        feedback["strengths"].append("Clear and confident expression")
        feedback["recommendations"].append("Ready for leadership roles")
    elif overall_score >= 60:
        feedback["strengths"].append("Good communication foundation")
        feedback["improvements"].append("Work on confidence and clarity")
        feedback["recommendations"].append("Practice more group discussions")
    else:
        feedback["improvements"].append("Focus on improving communication skills")
        feedback["improvements"].append("Practice speaking clearly and confidently")
        feedback["recommendations"].append("Join public speaking clubs or courses")

    # Analyze specific aspects
    if scores.get('fluency', 0) < 60:
        feedback["improvements"].append("Work on speech fluency and flow")
    if scores.get('clarity', 0) < 60:
        feedback["improvements"].append("Improve pronunciation and articulation")
    if scores.get('confidence', 0) < 60:
        feedback["improvements"].append("Build confidence in expressing opinions")

    return feedback

# Topics are sourced from questions.db datasets
