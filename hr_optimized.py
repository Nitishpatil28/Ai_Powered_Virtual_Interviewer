"""
HR Interview Module - Optimized Backend
- Enhanced error handling
- Better validation
- Improved response formats
- Logging support
- Optimized database queries
"""

from flask import Blueprint, jsonify, request, session, render_template
import sqlite3
import logging
from ai_service import EnhancedNLPAnalysisService
from utils import get_selected_company

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

hr_bp = Blueprint("hr", __name__, url_prefix="/hr")
DB_PATH = "users.db"
QUESTIONS_DB_PATH = "questions.db"
nlp_service = EnhancedNLPAnalysisService()

# Constants
MIN_ANSWER_LENGTH = 20
MAX_ANSWER_LENGTH = 5000
TIME_PER_QUESTION = 60  # seconds


@hr_bp.route("/")
def hr_home():
    """HR interview home page"""
    if "email" not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401
    return render_template("hr.html", username=session.get("name"))


@hr_bp.route("/start", methods=["POST"])
def start_hr_interview():
    """
    Start HR interview with company-specific questions

    Returns:
        - attempt_id: Unique attempt identifier
        - company: Selected company name
        - questions: Array of 10 company-specific questions
        - time_per_question: Time limit per question (60 seconds)
        - total_time: Total time for interview (600 seconds)
    """
    if "email" not in session:
        logger.warning("Unauthenticated access attempt to start HR interview")
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    try:
        email = session["email"]

        # Get selected company
        selected = get_selected_company(email)
        if not selected:
            logger.warning(f"No company selected for user: {email}")
            return jsonify({
                "success": False,
                "error": "Please select a company first"
            }), 400

        company_name = selected["name"]
        logger.info(f"Starting HR interview for {email} at {company_name}")

        # Get company_id from questions.db
        with sqlite3.connect(QUESTIONS_DB_PATH) as qconn:
            qc = qconn.cursor()
            qc.execute(
                "SELECT id FROM companies WHERE lower(trim(name)) = lower(trim(?))",
                (company_name,)
            )
            row = qc.fetchone()

            if not row:
                logger.error(f"Company not found in questions DB: {company_name}")
                return jsonify({
                    "success": False,
                    "error": f"Company '{company_name}' not found in questions database"
                }), 404

            company_id = row[0]

        # Fetch 10 random HR questions
        with sqlite3.connect(QUESTIONS_DB_PATH) as qconn:
            qc = qconn.cursor()
            qc.execute("""
                SELECT id, question, category, difficulty
                FROM hr_questions
                WHERE company_id = ?
                ORDER BY RANDOM()
                LIMIT 10
            """, (company_id,))

            rows = qc.fetchall()

        if len(rows) < 10:
            logger.warning(f"Insufficient questions for {company_name}: {len(rows)} found")
            return jsonify({
                "success": False,
                "error": f"Insufficient questions available for {company_name}. Found {len(rows)}, need 10."
            }), 400

        # Format questions
        questions = []
        for row in rows:
            questions.append({
                "id": row[0],
                "question": row[1],
                "category": row[2] or "General",
                "difficulty": row[3] or "Medium",
                "time_limit": TIME_PER_QUESTION
            })

        # Create HR attempt in database
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("""
                INSERT INTO hr_attempts (
                    student_email, company_name, total_questions, status
                ) VALUES (?, ?, 10, 'in_progress')
            """, (email, company_name))

            attempt_id = c.lastrowid
            conn.commit()

        logger.info(f"HR interview started - Attempt ID: {attempt_id}, User: {email}")

        return jsonify({
            "success": True,
            "attempt_id": attempt_id,
            "company": company_name,
            "questions": questions,
            "time_per_question": TIME_PER_QUESTION,
            "total_time": TIME_PER_QUESTION * 10,
            "total_questions": 10
        })

    except sqlite3.Error as e:
        logger.error(f"Database error in start_hr_interview: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Database error occurred. Please try again."
        }), 500

    except Exception as e:
        logger.error(f"Error in start_hr_interview: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "An unexpected error occurred. Please try again."
        }), 500


@hr_bp.route("/submit-answer", methods=["POST"])
def submit_answer():
    """
    Submit and evaluate single HR answer with NLP analysis

    Request Body:
        - attempt_id: Interview attempt ID
        - question_id: Question ID
        - answer: User's answer text
        - time_spent: Time taken to answer (seconds)

    Returns:
        - success: Boolean
        - scores: Dict with clarity, confidence, relevance, grammar, answer_score
        - feedback: Detailed feedback text
        - word_count: Number of words in answer
    """
    if "email" not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    try:
        data = request.json

        # Validate request data
        if not data:
            return jsonify({
                "success": False,
                "error": "Invalid request: No data provided"
            }), 400

        attempt_id = data.get('attempt_id')
        question_id = data.get('question_id')
        answer = data.get('answer', '').strip()
        time_spent = data.get('time_spent', 0)

        # Validation
        if not all([attempt_id, question_id, answer]):
            return jsonify({
                "success": False,
                "error": "Missing required fields: attempt_id, question_id, or answer"
            }), 400

        if len(answer) < MIN_ANSWER_LENGTH:
            return jsonify({
                "success": False,
                "error": f"Answer too short. Please provide at least {MIN_ANSWER_LENGTH} characters."
            }), 400

        if len(answer) > MAX_ANSWER_LENGTH:
            return jsonify({
                "success": False,
                "error": f"Answer too long. Maximum {MAX_ANSWER_LENGTH} characters allowed."
            }), 400

        email = session["email"]

        # Verify attempt ownership and status
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("""
                SELECT student_email, status, company_name
                FROM hr_attempts
                WHERE id = ?
            """, (attempt_id,))

            attempt = c.fetchone()

            if not attempt:
                logger.warning(f"Invalid attempt_id: {attempt_id}")
                return jsonify({
                    "success": False,
                    "error": "Invalid attempt ID"
                }), 404

            if attempt[0] != email:
                logger.warning(f"Attempt ownership mismatch: {email} vs {attempt[0]}")
                return jsonify({
                    "success": False,
                    "error": "Unauthorized access to this attempt"
                }), 403

            if attempt[2] == 'completed':
                return jsonify({
                    "success": False,
                    "error": "Interview already completed. Cannot submit new answers."
                }), 400

        # AI-powered NLP evaluation
        try:
            logger.info(f"Running NLP analysis for attempt {attempt_id}, question {question_id}")
            analysis = nlp_service.analyze_text(answer)

            clarity_score = analysis.get('clarity_score', 0)
            confidence_score = analysis.get('confidence_score', 0)
            relevance_score = analysis.get('relevance_score', 0)
            grammar_score = analysis.get('grammar_score', 0)

            # Calculate weighted overall score
            answer_score = (
                clarity_score * 0.30 +
                confidence_score * 0.25 +
                relevance_score * 0.30 +
                grammar_score * 0.15
            )

            feedback = analysis.get('feedback', 'Answer evaluated successfully.')
            word_count = analysis.get('word_count', len(answer.split()))

        except Exception as e:
            logger.error(f"NLP analysis failed: {str(e)}")
            # Fallback scores if NLP fails
            clarity_score = 50.0
            confidence_score = 50.0
            relevance_score = 50.0
            grammar_score = 50.0
            answer_score = 50.0
            feedback = "Answer received. Detailed evaluation temporarily unavailable."
            word_count = len(answer.split())

        # Save answer to database
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("""
                INSERT INTO hr_answers (
                    attempt_id, question_id, answer, clarity_score,
                    confidence_score, relevance_score, grammar_score,
                    answer_score, time_spent
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                attempt_id, question_id, answer, clarity_score,
                confidence_score, relevance_score, grammar_score,
                answer_score, time_spent
            ))
            conn.commit()

        logger.info(f"Answer saved - Attempt: {attempt_id}, Score: {answer_score:.2f}")

        return jsonify({
            "success": True,
            "scores": {
                "clarity": round(clarity_score, 2),
                "confidence": round(confidence_score, 2),
                "relevance": round(relevance_score, 2),
                "grammar": round(grammar_score, 2),
                "answer_score": round(answer_score, 2)
            },
            "feedback": feedback,
            "word_count": word_count,
            "strengths": analysis.get('strengths', []),
            "improvements": analysis.get('improvements', [])
        })

    except sqlite3.Error as e:
        logger.error(f"Database error in submit_answer: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Failed to save answer. Please try again."
        }), 500

    except Exception as e:
        logger.error(f"Error in submit_answer: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "An unexpected error occurred. Please try again."
        }), 500


@hr_bp.route("/submit", methods=["POST"])
def submit_hr_interview():
    """
    Complete HR interview and calculate final results

    Request Body:
        - attempt_id: Interview attempt ID
        - total_time: Total time spent (seconds)

    Returns:
        - success: Boolean
        - overall_score: Final average score
        - scores breakdown: All individual metric averages
        - total_questions: Number of questions
        - answered: Number of questions answered
        - feedback: Comprehensive feedback
    """
    if "email" not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    try:
        data = request.json
        attempt_id = data.get('attempt_id')
        total_time = data.get('total_time', 0)

        if not attempt_id:
            return jsonify({
                "success": False,
                "error": "Missing attempt_id"
            }), 400

        email = session["email"]

        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()

            # Verify attempt
            c.execute("""
                SELECT student_email, company_name, status
                FROM hr_attempts
                WHERE id = ?
            """, (attempt_id,))

            attempt = c.fetchone()

            if not attempt:
                return jsonify({
                    "success": False,
                    "error": "Invalid attempt ID"
                }), 404

            if attempt[0] != email:
                return jsonify({
                    "success": False,
                    "error": "Unauthorized access"
                }), 403

            if attempt[2] == 'completed':
                return jsonify({
                    "success": False,
                    "error": "Interview already submitted"
                }), 400

            company_name = attempt[1]

            # Calculate overall scores
            c.execute("""
                SELECT
                    AVG(clarity_score),
                    AVG(confidence_score),
                    AVG(relevance_score),
                    AVG(grammar_score),
                    AVG(answer_score),
                    COUNT(*),
                    MIN(answer_score),
                    MAX(answer_score)
                FROM hr_answers
                WHERE attempt_id = ?
            """, (attempt_id,))

            scores = c.fetchone()

            if not scores or scores[5] == 0:
                return jsonify({
                    "success": False,
                    "error": "No answers found. Please answer at least one question."
                }), 400

            answered_count = scores[5]
            if answered_count < 10:
                logger.warning(f"Incomplete interview: {answered_count}/10 questions")
                # Allow submission but note it's incomplete

            avg_clarity = scores[0] or 0
            avg_confidence = scores[1] or 0
            avg_relevance = scores[2] or 0
            avg_grammar = scores[3] or 0
            overall_score = scores[4] or 0
            min_score = scores[6] or 0
            max_score = scores[7] or 0

            # Update attempt with final scores
            c.execute("""
                UPDATE hr_attempts
                SET clarity_score = ?,
                    confidence_score = ?,
                    relevance_score = ?,
                    grammar_score = ?,
                    overall_score = ?,
                    total_time = ?,
                    status = 'completed',
                    completed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                avg_clarity, avg_confidence, avg_relevance,
                avg_grammar, overall_score, total_time, attempt_id
            ))

            conn.commit()

        # Generate comprehensive feedback
        feedback = generate_comprehensive_feedback(
            overall_score, avg_clarity, avg_confidence,
            avg_relevance, avg_grammar, answered_count,
            min_score, max_score
        )

        logger.info(f"HR interview completed - Attempt: {attempt_id}, Score: {overall_score:.2f}")

        return jsonify({
            "success": True,
            "overall_score": round(overall_score, 2),
            "average_clarity": round(avg_clarity, 2),
            "average_confidence": round(avg_confidence, 2),
            "average_relevance": round(avg_relevance, 2),
            "average_grammar": round(avg_grammar, 2),
            "total_questions": 10,
            "answered": answered_count,
            "min_score": round(min_score, 2),
            "max_score": round(max_score, 2),
            "company": company_name,
            "feedback": feedback,
            "completion_percentage": round((answered_count / 10) * 100, 1)
        })

    except sqlite3.Error as e:
        logger.error(f"Database error in submit_hr_interview: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Failed to complete interview. Please try again."
        }), 500

    except Exception as e:
        logger.error(f"Error in submit_hr_interview: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "An unexpected error occurred. Please try again."
        }), 500


def generate_comprehensive_feedback(overall, clarity, confidence, relevance,
                                    grammar, answered, min_score, max_score):
    """
    Generate detailed, actionable feedback based on performance metrics

    Returns structured feedback dict with performance level, strengths,
    improvements, and recommendations
    """
    feedback = {
        "performance_level": "",
        "summary": "",
        "strengths": [],
        "areas_for_improvement": [],
        "recommendations": [],
        "next_steps": []
    }

    # Determine performance level
    if overall >= 85:
        feedback["performance_level"] = "Excellent"
        feedback["summary"] = "Outstanding interview performance! You demonstrated strong communication skills and professional presence."
    elif overall >= 70:
        feedback["performance_level"] = "Good"
        feedback["summary"] = "Solid interview performance with clear strengths. Minor refinements will make you even more competitive."
    elif overall >= 55:
        feedback["performance_level"] = "Average"
        feedback["summary"] = "Decent performance with significant room for improvement. Focus on the areas highlighted below."
    else:
        feedback["performance_level"] = "Needs Improvement"
        feedback["summary"] = "Your interview skills need development. Follow the recommendations to strengthen your performance."

    # Identify strengths
    if clarity >= 75:
        feedback["strengths"].append("Clear and articulate communication")
    if confidence >= 75:
        feedback["strengths"].append("Confident delivery and strong presence")
    if relevance >= 75:
        feedback["strengths"].append("Relevant and focused responses")
    if grammar >= 80:
        feedback["strengths"].append("Excellent language proficiency")

    # Consistency strength
    score_range = max_score - min_score
    if score_range < 20:
        feedback["strengths"].append("Consistent performance across questions")

    if not feedback["strengths"]:
        feedback["strengths"].append("Completed the interview with determination")

    # Areas for improvement
    if clarity < 70:
        feedback["areas_for_improvement"].append(
            "Improve clarity: Structure your answers with clear introduction, body, and conclusion"
        )
    if confidence < 70:
        feedback["areas_for_improvement"].append(
            "Build confidence: Practice speaking decisively and avoid hesitant language"
        )
    if relevance < 70:
        feedback["areas_for_improvement"].append(
            "Enhance relevance: Stay focused on the question and provide specific examples"
        )
    if grammar < 70:
        feedback["areas_for_improvement"].append(
            "Polish grammar: Review proper sentence structure and punctuation"
        )

    if answered < 10:
        feedback["areas_for_improvement"].append(
            f"Complete all questions: You answered {answered}/10 questions"
        )

    # Score-based recommendations
    if overall >= 80:
        feedback["recommendations"] = [
            "You're interview-ready! Focus on company-specific preparation",
            "Research the company's culture and values thoroughly",
            "Prepare 2-3 insightful questions for the interviewer"
        ]
        feedback["next_steps"] = [
            "Apply to target companies with confidence",
            "Continue practicing to maintain your skills",
            "Consider mock interviews to stay sharp"
        ]
    elif overall >= 60:
        feedback["recommendations"] = [
            "Practice the STAR method (Situation, Task, Action, Result) for behavioral questions",
            "Record yourself answering common questions and review",
            "Focus on providing concrete examples from your experience"
        ]
        feedback["next_steps"] = [
            "Take 5 more practice interviews",
            "Work specifically on your weak areas",
            "Seek feedback from mentors or career counselors"
        ]
    else:
        feedback["recommendations"] = [
            "Study common HR interview questions and prepare structured answers",
            "Practice answering questions out loud daily",
            "Read articles on effective communication techniques",
            "Consider interview coaching or workshops"
        ]
        feedback["next_steps"] = [
            "Complete a communication skills course",
            "Practice with a study partner or mentor",
            "Retake this interview after 1 week of preparation"
        ]

    return feedback


@hr_bp.route("/history", methods=["GET"])
def get_hr_history():
    """Get HR interview history for the logged-in user"""
    if "email" not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    try:
        email = session["email"]

        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("""
                SELECT
                    id, overall_score, clarity_score, confidence_score,
                    relevance_score, grammar_score, completed_at,
                    company_name, total_time
                FROM hr_attempts
                WHERE student_email = ? AND status = 'completed'
                ORDER BY completed_at DESC
                LIMIT 20
            """, (email,))

            history = []
            for row in c.fetchall():
                history.append({
                    "attempt_id": row[0],
                    "overall_score": round(row[1], 2) if row[1] else 0,
                    "clarity_score": round(row[2], 2) if row[2] else 0,
                    "confidence_score": round(row[3], 2) if row[3] else 0,
                    "relevance_score": round(row[4], 2) if row[4] else 0,
                    "grammar_score": round(row[5], 2) if row[5] else 0,
                    "completed_at": row[6],
                    "company": row[7],
                    "time_spent": row[8]
                })

        return jsonify({
            "success": True,
            "history": history,
            "total_attempts": len(history)
        })

    except Exception as e:
        logger.error(f"Error in get_hr_history: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Failed to retrieve history"
        }), 500


# Initialize HR tables if needed
def init_hr_tables():
    """Initialize HR interview tables with proper indexes"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()

            # Ensure columns exist
            c.execute("PRAGMA table_info(hr_attempts)")
            columns = {col[1] for col in c.fetchall()}

            required_columns = {
                'clarity_score': 'ALTER TABLE hr_attempts ADD COLUMN clarity_score REAL',
                'confidence_score': 'ALTER TABLE hr_attempts ADD COLUMN confidence_score REAL',
                'relevance_score': 'ALTER TABLE hr_attempts ADD COLUMN relevance_score REAL',
                'grammar_score': 'ALTER TABLE hr_attempts ADD COLUMN grammar_score REAL',
                'overall_score': 'ALTER TABLE hr_attempts ADD COLUMN overall_score REAL',
                'total_time': 'ALTER TABLE hr_attempts ADD COLUMN total_time INTEGER',
                'completed_at': 'ALTER TABLE hr_attempts ADD COLUMN completed_at TIMESTAMP'
            }

            for col, alter_sql in required_columns.items():
                if col not in columns:
                    c.execute(alter_sql)

            # Create indexes for better query performance
            c.execute("""
                CREATE INDEX IF NOT EXISTS idx_hr_attempts_email
                ON hr_attempts(student_email)
            """)

            c.execute("""
                CREATE INDEX IF NOT EXISTS idx_hr_answers_attempt
                ON hr_answers(attempt_id)
            """)

            conn.commit()
            logger.info("HR tables initialized successfully")

    except Exception as e:
        logger.error(f"Error initializing HR tables: {str(e)}")


# Initialize tables on module import
init_hr_tables()
