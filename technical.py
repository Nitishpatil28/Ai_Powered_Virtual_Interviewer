"""
Improved Technical Interview Module
- 2 coding questions from company-specific dataset
- 1 hour time limit (30 min per question)
- Proper code validation
- Test case execution and verification
"""

from flask import Blueprint, jsonify, request, session, render_template
import sqlite3
import json
from utils import get_selected_company

technical_bp = Blueprint("technical", __name__, url_prefix="/technical")
DB_PATH = "users.db"
QUESTIONS_DB_PATH = "questions.db"


@technical_bp.route("/")
def technical_home():
    """Technical interview home page"""
    if "email" not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    return render_template("technical.html", username=session.get("name"))


@technical_bp.route("/start", methods=["POST"])
def start_technical_interview():
    """Start technical interview with 2 company-specific coding questions"""
    if "email" not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    try:
        email = session["email"]

        selected = get_selected_company(email)
        if not selected:
            return jsonify({"success": False, "error": "Please select a company first"}), 400
        company_name = selected["name"]

        # Load questions from datasets JSON files
        import os
        company_file_map = {
            "google": "google_technical.json",
            "microsoft": "microsoft_technical.json",
            "amazon": "amazon_technical.json",
            "infosys": "infosys_technical.json",
            "wipro": "wipro_technical.json",
            "flipkart": "flipkart_technical.json",
            "swiggy": "swiggy_technical.json",
            "razorpay": "razorpay_technical.json",
            "deloitte": "deloitte_technical.json",
            "accenture": "accenture_technical.json"
        }
        file_name = company_file_map.get(company_name.lower(), "generic.json")
        file_path = os.path.join("datasets", file_name)

        if not os.path.exists(file_path):
            return jsonify({"success": False, "error": f"Dataset file not found for {company_name}"}), 400

        try:
            with open(file_path, 'r') as f:
                data = json.load(f)

            questions = []
            for q in data.get("technical", []):
                questions.append({
                    "id": q["id"],
                    "title": q["title"],
                    "description": q["description"],
                    "difficulty": q.get("difficulty", "Medium"),
                    "input_format": q["input_format"],
                    "output_format": q["output_format"],
                    "constraints": q["constraints"],
                    "sample_input": q.get("sample_input", ""),
                    "sample_output": q.get("sample_output", ""),
                    "test_cases": q["testcases"],
                    "time_limit": 1800,  # 30 min per question
                    "tags": "",
                    "starter_code": q.get("starter_code", """def solve():
                pass

if __name__=='__main__':
                solve()""")
                })
        except Exception as e:
            return jsonify({"success": False, "error": f"Error loading questions: {str(e)}"}), 500

        if len(questions) < 2:
            return jsonify({
                "success": False,
                "error": f"Insufficient questions for {company_name}"
            }), 400
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        # Create technical attempt
        c.execute("""
            INSERT INTO technical_attempts (
                student_email, company_name, total_questions, status
            ) VALUES (?, ?, 2, 'in_progress')
        """, (email, company_name))

        attempt_id = c.lastrowid
        conn.commit()
        conn.close()

        return jsonify({
            "success": True,
            "attempt_id": attempt_id,
            "company": company_name,
            "questions": questions,
            "time_limit": 3600  # 1 hour
        })

    except Exception as e:
        print(f"Error starting technical interview: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


def validate_code_logic(code, language):
    """Validate code submission - ensure it's not empty or placeholder"""
    code = code.strip()

    if not code:
        return {
            "success": False,
            "error": "Code cannot be empty",
            "valid": False
        }

    # Check for placeholder patterns
    placeholders = [
        'pass',
        '// Write your code here',
        '// TODO',
        'return {}',
        'return []',
        'return None',
        'return null',
        'return;'
    ]

    # Check if code is just placeholder
    code_lines = [line.strip() for line in code.split('\n') if line.strip()]
    actual_code_lines = []

    for line in code_lines:
        # Skip comments and function definitions
        if line.startswith('#') or line.startswith(
                '//') or line.startswith('def ') or line.startswith('function ') or line.startswith('class '):
            continue
        actual_code_lines.append(line)

    # Check if there's actual implementation
    has_implementation = False
    for line in actual_code_lines:
        is_placeholder = any(p in line for p in placeholders)
        if not is_placeholder and len(line) > 5:
            has_implementation = True
            break

    if not has_implementation:
        return {
            "success": False,
            "error": "Please implement the solution. Your code appears to contain only placeholders.",
            "valid": False
        }

    # Basic syntax validation for Python
    if language == 'python':
        try:
            compile(code, '<string>', 'exec')
        except SyntaxError as e:
            return {
                "success": False,
                "error": f"Syntax Error: {str(e)}",
                "valid": False
            }

    return {
        "success": True,
        "valid": True,
        "message": "Code validation passed"
    }


@technical_bp.route("/validate-code", methods=["POST"])
def validate_code():
    """Validate code submission - ensure it's not empty or placeholder"""
    if "email" not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    try:
        data = request.json
        code = data.get('code', '').strip()
        language = data.get('language', 'python')

        result = validate_code_logic(code, language)
        return jsonify(result)

    except Exception as e:
        print(f"Error validating code: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@technical_bp.route("/run-code", methods=["POST"])
def run_code():
    """Run code against sample test cases using Judge0 API"""
    if "email" not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    try:
        data = request.json
        code = data.get('code', '')
        question_id = data.get('question_id')
        language = data.get('language', 'python')

        # Validate code first
        validation_result = validate_code_logic(code, language)
        if not validation_result.get('valid', False):
            return jsonify(validation_result), 400

        # Get test cases from questions.db
        conn = sqlite3.connect(QUESTIONS_DB_PATH)
        c = conn.cursor()
        c.execute(
            """
            SELECT test_cases FROM technical_questions WHERE id = ?
            """,
            (question_id,)
        )

        result = c.fetchone()
        conn.close()

        if not result:
            return jsonify({"success": False, "error": "Question not found"}), 404

        test_cases = json.loads(result[0])

        # Use Judge0 API for actual code execution
        from ai_service import code_executor
        execution_result = code_executor.execute_code(code, language, test_cases)

        if "error" in execution_result:
            return jsonify({
                "success": False,
                "error": execution_result["error"],
                "message": execution_result.get("message", "Code execution failed")
            }), 500

        return jsonify({
            "success": True,
            "result": execution_result
        })

    except Exception as e:
        print(f"Error running code: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@technical_bp.route("/submit", methods=["POST"])
def submit_technical_interview():
    """Submit technical interview with code validation"""
    if "email" not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    try:
        data = request.json
        attempt_id = data.get('attempt_id')
        solutions = data.get('solutions', [])  # [{question_id, code, language, test_passed}]
        time_taken = data.get('time_taken', 0)

        if not attempt_id or not solutions:
            return jsonify({"success": False, "error": "Invalid submission"}), 400

        email = session["email"]

        # Validate each solution
        for solution in solutions:
            code = solution.get('code', '').strip()
            if not code:
                return jsonify({
                    "success": False,
                    "error": f"Code for question {solution.get('question_id')} is empty"
                }), 400

            # Check for placeholders
            if code == 'pass' or 'pass' in code and len(code.strip()) < 10:
                return jsonify({
                    "success": False,
                    "error": "Please implement all solutions. Placeholder code detected."
                }), 400

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        # Verify attempt
        c.execute("""
            SELECT student_email, company_name, status
            FROM technical_attempts
            WHERE id = ?
        """, (attempt_id,))

        attempt = c.fetchone()
        if not attempt or attempt[0] != email:
            return jsonify({"success": False, "error": "Invalid attempt"}), 403

        if attempt[2] == 'completed':
            return jsonify({"success": False, "error": "Test already submitted"}), 400

        company_name = attempt[1]

        # Load questions from JSON file to get test cases
        import os
        company_file_map = {
            "google": "google_technical.json",
            "microsoft": "microsoft_technical.json",
            "amazon": "amazon_technical.json",
            "infosys": "infosys_technical.json",
            "wipro": "wipro_technical.json",
            "flipkart": "flipkart_technical.json",
            "swiggy": "swiggy_technical.json",
            "razorpay": "razorpay_technical.json",
            "deloitte": "deloitte_technical.json",
            "accenture": "accenture_technical.json"
        }
        file_name = company_file_map.get(company_name.lower(), "generic.json")
        file_path = os.path.join("datasets", file_name)

        # Load question data
        question_data = {}
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                data = json.load(f)
                for q in data.get("technical", []):
                    question_data[q["id"]] = {
                        "title": q["title"],
                        "test_cases": q["testcases"]
                    }

        # Calculate score using Judge0 API
        from ai_service import CodeExecutionService
        code_executor = CodeExecutionService()
        total_passed = 0
        total_tests = 0

        for solution in solutions:
            question_id = solution.get('question_id')
            code = solution.get('code')
            language = solution.get('language', 'python')

            # Get question data from loaded JSON
            if question_id not in question_data:
                continue

            question_title = question_data[question_id]["title"]
            test_cases = question_data[question_id]["test_cases"]

            # Execute code using Judge0 API
            execution_result = code_executor.execute_code(code, language, test_cases)

            if "error" in execution_result:
                # If execution fails, give 0 score for this question
                passed_tests = 0
                total_tests += len(test_cases)
            else:
                passed_tests = execution_result.get("passed", 0)
                total_passed += passed_tests
                total_tests += execution_result.get("total", len(test_cases))

            # Save solution
            c.execute("""
                INSERT INTO technical_solutions (
                    attempt_id, question_id, question_title, code_submitted,
                    language, tests_passed, total_tests
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (attempt_id, question_id, question_title, code,
                  language, passed_tests, len(test_cases)))

        # Calculate final score
        score = (total_passed / total_tests * 100) if total_tests > 0 else 0

        # Update attempt
        c.execute("""
            UPDATE technical_attempts
            SET tests_passed = ?,
                total_tests = ?,
                score = ?,
                time_taken = ?,
                status = 'completed',
                completed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (total_passed, total_tests, score, time_taken, attempt_id))

        conn.commit()
        conn.close()

        return jsonify({
            "success": True,
            "score": round(score, 2),
            "tests_passed": total_passed,
            "total_tests": total_tests,
            "time_taken": time_taken,
            "message": "Technical interview submitted successfully!"
        })

    except Exception as e:
        print(f"Error submitting technical interview: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# Create necessary tables
def init_technical_tables():
    """Initialize technical interview tables"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS technical_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_email TEXT NOT NULL,
            company_name TEXT,
            total_questions INTEGER DEFAULT 2,
            tests_passed INTEGER DEFAULT 0,
            total_tests INTEGER DEFAULT 0,
            score REAL DEFAULT 0,
            time_taken INTEGER,
            status TEXT DEFAULT 'in_progress',
            completed_at TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS technical_solutions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attempt_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            question_title TEXT,
            code_submitted TEXT,
            language TEXT,
            tests_passed INTEGER DEFAULT 0,
            total_tests INTEGER DEFAULT 0,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(attempt_id) REFERENCES technical_attempts(id)
        )
    """)

    conn.commit()
    conn.close()
    print("Technical interview tables initialized!")


# Initialize tables when module loads
init_technical_tables()
