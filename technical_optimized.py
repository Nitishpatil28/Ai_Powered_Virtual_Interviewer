"""
Technical Interview Module - Optimized Backend
- Enhanced code validation
- Better error handling
- Improved Judge0 integration
- Optimized response formats
- Comprehensive logging
"""

from flask import Blueprint, jsonify, request, session, render_template
import sqlite3
import json
import re
import logging
from utils import get_selected_company

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

technical_bp = Blueprint("technical", __name__, url_prefix="/technical")
DB_PATH = "users.db"
QUESTIONS_DB_PATH = "questions.db"

# Constants
TOTAL_TIME_LIMIT = 3600  # 1 hour
MIN_CODE_LENGTH = 10
MAX_CODE_LENGTH = 10000


@technical_bp.route("/")
def technical_home():
    """Technical interview home page"""
    if "email" not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401
    return render_template("technical.html", username=session.get("name"))


@technical_bp.route("/start", methods=["POST"])
def start_technical_interview():
    """
    Start technical interview with 2 company-specific coding questions

    Returns:
        - attempt_id: Unique attempt identifier
        - company: Selected company name
        - questions: Array of 2 coding problems with test cases
        - time_limit: Total time limit (3600 seconds = 1 hour)
    """
    if "email" not in session:
        logger.warning("Unauthenticated access to start technical interview")
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
        logger.info(f"Starting technical interview for {email} at {company_name}")

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
                    "error": f"Company '{company_name}' not found"
                }), 404

            company_id = row[0]

        # Fetch 2 random coding questions
        with sqlite3.connect(QUESTIONS_DB_PATH) as qconn:
            qc = qconn.cursor()
            qc.execute("""
                SELECT
                    id, question_title, question_description, difficulty,
                    input_format, output_format, constraints,
                    sample_input, sample_output, test_cases,
                    time_limit, tags, hints
                FROM technical_questions
                WHERE company_id = ?
                ORDER BY RANDOM()
                LIMIT 2
            """, (company_id,))

            rows = qc.fetchall()

        if len(rows) < 2:
            logger.warning(f"Insufficient questions for {company_name}: {len(rows)} found")
            return jsonify({
                "success": False,
                "error": f"Insufficient coding questions for {company_name}. Need 2, found {len(rows)}."
            }), 400

        # Format questions with all details
        questions = []
        for idx, row in enumerate(rows):
            test_cases = []
            try:
                test_cases = json.loads(row[9]) if row[9] else []
            except json.JSONDecodeError:
                logger.warning(f"Invalid test_cases JSON for question {row[0]}")
                test_cases = []

            questions.append({
                "id": row[0],
                "title": row[1],
                "description": row[2],
                "difficulty": row[3] or "Medium",
                "input_format": row[4],
                "output_format": row[5],
                "constraints": row[6],
                "sample_input": row[7],
                "sample_output": row[8],
                "test_cases": test_cases,  # Include for frontend display
                "time_limit": row[10] or 1800,  # 30 min per question
                "tags": row[11],
                "hints": row[12],
                "score": 50  # 50 points per question
            })

        # Create technical attempt
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("""
                INSERT INTO technical_attempts (
                    student_email, company_name, total_questions, status
                ) VALUES (?, ?, 2, 'in_progress')
            """, (email, company_name))

            attempt_id = c.lastrowid
            conn.commit()

        logger.info(f"Technical interview started - Attempt ID: {attempt_id}, User: {email}")

        return jsonify({
            "success": True,
            "attempt_id": attempt_id,
            "company": company_name,
            "questions": questions,
            "time_limit": TOTAL_TIME_LIMIT,
            "total_questions": 2,
            "points_per_question": 50
        })

    except sqlite3.Error as e:
        logger.error(f"Database error in start_technical_interview: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Database error. Please try again."
        }), 500

    except Exception as e:
        logger.error(f"Error in start_technical_interview: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "An unexpected error occurred."
        }), 500


def validate_code_advanced(code, language):
    """
    Advanced code validation with multiple checks

    Returns dict with:
        - valid: Boolean
        - errors: List of error messages
        - warnings: List of warning messages
        - metrics: Code quality metrics
    """
    result = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "metrics": {}
    }

    code = code.strip()

    # Check minimum length
    if len(code) < MIN_CODE_LENGTH:
        result["valid"] = False
        result["errors"].append(f"Code too short. Minimum {MIN_CODE_LENGTH} characters required.")
        return result

    # Check maximum length
    if len(code) > MAX_CODE_LENGTH:
        result["valid"] = False
        result["errors"].append(f"Code too long. Maximum {MAX_CODE_LENGTH} characters allowed.")
        return result

    # Check for placeholder patterns
    placeholders = [
        r'\bpass\s*$',
        r'//\s*Write your code here',
        r'//\s*TODO',
        r'#\s*TODO',
        r'return\s+\{\}',
        r'return\s+\[\]',
        r'return\s+None',
        r'return\s+null',
        r'return\s*;'
    ]

    for pattern in placeholders:
        if re.search(pattern, code, re.MULTILINE | re.IGNORECASE):
            result["errors"].append("Please implement the solution. Placeholder code detected.")
            result["valid"] = False
            break

    # Language-specific validation
    if language == 'python':
        try:
            compile(code, '<string>', 'exec')
        except SyntaxError as e:
            result["valid"] = False
            result["errors"].append(f"Python Syntax Error: {str(e)}")

    # Code quality metrics
    lines = code.split('\n')
    result["metrics"] = {
        "lines": len(lines),
        "characters": len(code),
        "blank_lines": sum(1 for line in lines if not line.strip()),
        "comment_lines": sum(1 for line in lines if line.strip().startswith(('#', '//'))),
    }

    # Warnings for code quality
    if result["metrics"]["lines"] > 200:
        result["warnings"].append("Code is quite long. Consider simplifying.")

    if result["metrics"]["comment_lines"] == 0 and result["metrics"]["lines"] > 20:
        result["warnings"].append("Consider adding comments for better readability.")

    return result


@technical_bp.route("/validate-code", methods=["POST"])
def validate_code():
    """
    Validate code before execution

    Request Body:
        - code: Source code string
        - language: Programming language

    Returns validation result with errors and warnings
    """
    if "email" not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    try:
        data = request.json
        code = data.get('code', '').strip()
        language = data.get('language', 'python')

        result = validate_code_advanced(code, language)
        return jsonify(result)

    except Exception as e:
        logger.error(f"Error validating code: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Validation failed"
        }), 500


@technical_bp.route("/run-code", methods=["POST"])
def run_code():
    """
    Execute code against test cases using Judge0 API

    Request Body:
        - attempt_id: Attempt ID
        - question_id: Question ID
        - code: Source code
        - language: Programming language

    Returns execution results with test case outcomes
    """
    if "email" not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    try:
        data = request.json
        code = data.get('code', '').strip()
        question_id = data.get('question_id')
        language = data.get('language', 'python')
        attempt_id = data.get('attempt_id')

        # Validate inputs
        if not all([code, question_id, attempt_id]):
            return jsonify({
                "success": False,
                "error": "Missing required fields"
            }), 400

        # Advanced code validation
        validation = validate_code_advanced(code, language)
        if not validation["valid"]:
            return jsonify({
                "success": False,
                "error": "Code validation failed",
                "errors": validation["errors"],
                "warnings": validation["warnings"]
            }), 400

        # Get test cases
        with sqlite3.connect(QUESTIONS_DB_PATH) as conn:
            c = conn.cursor()
            c.execute("""
                SELECT test_cases, question_title
                FROM technical_questions
                WHERE id = ?
            """, (question_id,))

            result = c.fetchone()

            if not result:
                return jsonify({
                    "success": False,
                    "error": "Question not found"
                }), 404

            test_cases_json, question_title = result
            test_cases = json.loads(test_cases_json) if test_cases_json else []

        if not test_cases:
            return jsonify({
                "success": False,
                "error": "No test cases available for this question"
            }), 400

        # Execute code using Judge0 API
        from ai_service import code_executor

        logger.info(f"Executing code for question {question_id}, attempt {attempt_id}")

        execution_result = code_executor.execute_code(code, language, test_cases)

        if "error" in execution_result:
            logger.warning(f"Code execution error: {execution_result['error']}")
            return jsonify({
                "success": False,
                "error": execution_result["error"],
                "message": execution_result.get("message", "Code execution failed")
            }), 200  # Return 200 with error in body for better frontend handling

        # Format results for frontend
        results = execution_result.get("results", [])
        passed_count = execution_result.get("passed", 0)
        total_count = execution_result.get("total", len(test_cases))
        score = execution_result.get("score", 0)

        logger.info(f"Code execution completed: {passed_count}/{total_count} tests passed")

        return jsonify({
            "success": True,
            "results": {
                "results": results,
                "passed": passed_count,
                "total": total_count,
                "score": score,
                "all_passed": passed_count == total_count,
                "percentage": round((passed_count / total_count * 100) if total_count > 0 else 0, 2)
            },
            "warnings": validation.get("warnings", []),
            "metrics": validation.get("metrics", {})
        })

    except sqlite3.Error as e:
        logger.error(f"Database error in run_code: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Database error occurred"
        }), 500

    except Exception as e:
        logger.error(f"Error in run_code: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "Code execution failed. Please try again."
        }), 500


@technical_bp.route("/submit", methods=["POST"])
def submit_technical_interview():
    """
    Submit complete technical interview with all solutions

    Request Body:
        - attempt_id: Attempt ID
        - solutions: Array of {question_id, code, language}
        - total_time: Time spent in seconds

    Returns final score and detailed results
    """
    if "email" not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    try:
        data = request.json
        attempt_id = data.get('attempt_id')
        solutions = data.get('solutions', [])
        total_time = data.get('total_time', 0)

        # Validation
        if not attempt_id or not solutions:
            return jsonify({
                "success": False,
                "error": "Missing attempt_id or solutions"
            }), 400

        if len(solutions) != 2:
            return jsonify({
                "success": False,
                "error": f"Expected 2 solutions, got {len(solutions)}"
            }), 400

        email = session["email"]

        # Verify attempt ownership and status
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("""
                SELECT student_email, company_name, status
                FROM technical_attempts
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
                    "error": "Test already submitted"
                }), 400

            company_name = attempt[1]

        # Validate and execute all solutions
        from ai_service import code_executor

        total_score = 0
        total_passed = 0
        total_tests = 0
        results_detail = []

        for idx, solution in enumerate(solutions):
            question_id = solution.get('question_id')
            code = solution.get('code', '').strip()
            language = solution.get('language', 'python')

            # Validate solution
            if not code:
                return jsonify({
                    "success": False,
                    "error": f"Solution {idx + 1} is empty"
                }), 400

            validation = validate_code_advanced(code, language)
            if not validation["valid"]:
                return jsonify({
                    "success": False,
                    "error": f"Solution {idx + 1} validation failed",
                    "details": validation["errors"]
                }), 400

            # Get test cases and execute
            with sqlite3.connect(QUESTIONS_DB_PATH) as qconn:
                qc = qconn.cursor()
                qc.execute("""
                    SELECT question_title, test_cases
                    FROM technical_questions
                    WHERE id = ?
                """, (question_id,))

                q_result = qc.fetchone()

                if not q_result:
                    continue

                question_title, test_cases_json = q_result
                test_cases = json.loads(test_cases_json) if test_cases_json else []

            # Execute code
            execution_result = code_executor.execute_code(code, language, test_cases)

            if "error" in execution_result:
                # Give 0 score for failed execution
                question_score = 0
                passed = 0
                total = len(test_cases)
            else:
                passed = execution_result.get("passed", 0)
                total = execution_result.get("total", len(test_cases))
                question_score = execution_result.get("score", 0)

            total_passed += passed
            total_tests += total
            total_score += question_score

            results_detail.append({
                "question_id": question_id,
                "question_title": question_title,
                "passed": passed,
                "total": total,
                "score": question_score,
                "percentage": round((passed / total * 100) if total > 0 else 0, 1)
            })

            # Save individual solution
            with sqlite3.connect(DB_PATH) as conn:
                c = conn.cursor()
                c.execute("""
                    INSERT INTO technical_answers (
                        attempt_id, question_id, code, language,
                        test_cases_passed, total_test_cases, score
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    attempt_id, question_id, code, language,
                    passed, total, question_score
                ))
                conn.commit()

        # Calculate final score (out of 100)
        final_score = total_score / 2  # Average of 2 questions

        # Update attempt with final results
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("""
                UPDATE technical_attempts
                SET score = ?,
                    test_cases_passed = ?,
                    total_test_cases = ?,
                    time_taken = ?,
                    status = 'completed',
                    completed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                final_score, total_passed, total_tests,
                total_time, attempt_id
            ))
            conn.commit()

        logger.info(f"Technical interview completed - Attempt: {attempt_id}, Score: {final_score:.2f}")

        # Generate feedback
        feedback = generate_technical_feedback(final_score, total_passed, total_tests)

        return jsonify({
            "success": True,
            "score": round(final_score, 2),
            "passed": total_passed,
            "total": total_tests,
            "failed": total_tests - total_passed,
            "percentage": round((total_passed / total_tests * 100) if total_tests > 0 else 0, 1),
            "results": results_detail,
            "feedback": feedback,
            "company": company_name,
            "time_spent": total_time
        })

    except sqlite3.Error as e:
        logger.error(f"Database error in submit_technical_interview: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Failed to submit. Database error."
        }), 500

    except Exception as e:
        logger.error(f"Error in submit_technical_interview: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "Submission failed. Please try again."
        }), 500


def generate_technical_feedback(score, passed, total):
    """Generate comprehensive technical feedback"""
    feedback = {
        "performance_level": "",
        "summary": "",
        "strengths": [],
        "improvements": [],
        "recommendations": []
    }

    pass_rate = (passed / total * 100) if total > 0 else 0

    if score >= 85:
        feedback["performance_level"] = "Excellent"
        feedback["summary"] = "Outstanding coding performance! Your solutions demonstrate strong problem-solving skills."
        feedback["strengths"] = [
            "Excellent test case pass rate",
            "Strong algorithmic thinking",
            "Clean code implementation"
        ]
        feedback["recommendations"] = [
            "Continue practicing advanced algorithms",
            "Explore competitive programming platforms",
            "You're ready for technical interviews"
        ]
    elif score >= 70:
        feedback["performance_level"] = "Good"
        feedback["summary"] = "Solid coding skills with room for optimization."
        feedback["strengths"] = [
            "Good understanding of problem-solving",
            "Functional code implementation"
        ]
        feedback["improvements"] = [
            "Work on edge case handling",
            "Optimize time complexity"
        ]
        feedback["recommendations"] = [
            "Practice more medium-difficulty problems",
            "Focus on algorithmic efficiency",
            "Review data structures concepts"
        ]
    elif score >= 50:
        feedback["performance_level"] = "Average"
        feedback["summary"] = "Basic coding skills demonstrated. Significant improvement needed."
        feedback["improvements"] = [
            "Strengthen data structures knowledge",
            "Improve problem-solving approach",
            "Practice test case coverage"
        ]
        feedback["recommendations"] = [
            "Complete a data structures course",
            "Solve 50+ easy-medium problems",
            "Learn common algorithm patterns"
        ]
    else:
        feedback["performance_level"] = "Needs Improvement"
        feedback["summary"] = "Coding skills need substantial development."
        feedback["improvements"] = [
            "Master programming language basics",
            "Learn fundamental data structures",
            "Practice problem decomposition"
        ]
        feedback["recommendations"] = [
            "Start with beginner-level problems",
            "Take a programming fundamentals course",
            "Practice daily coding exercises",
            "Seek mentorship or tutoring"
        ]

    return feedback


def init_technical_tables():
    """Initialize technical interview tables with proper schema"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()

            # Create technical_answers table if not exists
            c.execute("""
                CREATE TABLE IF NOT EXISTS technical_answers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    attempt_id INTEGER NOT NULL,
                    question_id INTEGER NOT NULL,
                    code TEXT NOT NULL,
                    language TEXT NOT NULL,
                    test_cases_passed INTEGER DEFAULT 0,
                    total_test_cases INTEGER DEFAULT 0,
                    score REAL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(attempt_id) REFERENCES technical_attempts(id)
                )
            """)

            # Check and add missing columns to technical_attempts
            c.execute("PRAGMA table_info(technical_attempts)")
            columns = {col[1] for col in c.fetchall()}

            required_columns = {
                'score': 'ALTER TABLE technical_attempts ADD COLUMN score REAL DEFAULT 0',
                'test_cases_passed': 'ALTER TABLE technical_attempts ADD COLUMN test_cases_passed INTEGER DEFAULT 0',
                'total_test_cases': 'ALTER TABLE technical_attempts ADD COLUMN total_test_cases INTEGER DEFAULT 0',
                'time_taken': 'ALTER TABLE technical_attempts ADD COLUMN time_taken INTEGER DEFAULT 0',
                'completed_at': 'ALTER TABLE technical_attempts ADD COLUMN completed_at TIMESTAMP'
            }

            for col, alter_sql in required_columns.items():
                if col not in columns:
                    c.execute(alter_sql)

            # Create indexes
            c.execute("""
                CREATE INDEX IF NOT EXISTS idx_technical_attempts_email
                ON technical_attempts(student_email)
            """)

            c.execute("""
                CREATE INDEX IF NOT EXISTS idx_technical_answers_attempt
                ON technical_answers(attempt_id)
            """)

            conn.commit()
            logger.info("Technical tables initialized successfully")

    except Exception as e:
        logger.error(f"Error initializing technical tables: {str(e)}")


# Initialize tables on module import
init_technical_tables()
