"""
Backend API routes for Aptitude Test System
Handles test attempts, question serving, and result calculation
"""

from flask import Blueprint, jsonify, request, session, redirect, url_for, flash, render_template
import sqlite3
from datetime import datetime
import json
from typing import Dict, List

# Import question generator
# from question_generator import (
#     initialize_question_bank,
#     get_questions_for_company,
#     get_adaptive_questions
# )
from utils import get_selected_company

# Import AI evaluation service
from ai_service import aptitude_evaluator

aptitude_bp = Blueprint("aptitude", __name__, url_prefix="/aptitude")

# ✅ FIX 1: Use correct database paths
USERS_DB_PATH = "users.db"  # For storing test attempts and results
QUESTIONS_DB_PATH = "questions.db"  # For fetching questions


def init_aptitude_tables():
    """Initialize database tables for aptitude tests"""
    conn = sqlite3.connect(USERS_DB_PATH)
    c = conn.cursor()

    # ✅ Aptitude attempts table (stores in users.db)
    c.execute("""
        CREATE TABLE IF NOT EXISTS aptitude_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_email TEXT NOT NULL,
            company_name TEXT,
            total_questions INTEGER DEFAULT 30,
            correct_answers INTEGER DEFAULT 0,
            score REAL DEFAULT 0,
            time_taken INTEGER,
            status TEXT DEFAULT 'completed',
            completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ai_feedback TEXT,
            FOREIGN KEY(student_email) REFERENCES students(email)
        )
    """)

    # ✅ Aptitude responses table (stores in users.db)
    c.execute("""
        CREATE TABLE IF NOT EXISTS aptitude_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attempt_id INTEGER NOT NULL,
            question_id INTEGER,
            question_text TEXT,
            selected_answer TEXT,
            correct_answer TEXT,
            is_correct BOOLEAN,
            time_spent INTEGER,
            FOREIGN KEY(attempt_id) REFERENCES aptitude_attempts(id)
        )
    """)

    conn.commit()
    conn.close()

    # ✅ Initialize question bank in questions.db
    # initialize_question_bank()
    print("Aptitude test tables initialized!")


@aptitude_bp.route("/get-questions/<topic>", methods=["GET"])
def get_test_questions(topic):
    """Get 30 questions for the test with AI-driven adaptive generation"""
    print(f"Debug: Session data: {dict(session)}")
    if "email" not in session:
        print("Debug: No email in session")
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    try:
        email = session["email"]

        # Get selected company
        selected_company = get_selected_company(email)
        if not selected_company:
            flash("Please select a company first to start the aptitude test.")
            return redirect(url_for("routes.companies"))

        company_name = selected_company['name']

        print(f"✅ Fetching questions for company: {company_name}")

        # Get student's performance history for adaptive generation
        student_performance = get_student_performance_history(email)

        # Check if we need AI-generated questions (if database has insufficient questions or for personalization)
        use_ai_generation = should_use_ai_generation(email, company_name, student_performance)

        if use_ai_generation:
            print("🤖 Using AI-driven adaptive question generation")
            questions = aptitude_evaluator.generate_adaptive_questions(
                student_performance, company_name, 30
            )
            # Save AI-generated questions to database for future use
            save_ai_generated_questions(questions, company_name)
        else:
            # Use existing database questions
            questions = get_database_questions(company_name)

        # Ensure we have exactly 30 questions
        if len(questions) < 30:
            print(f"⚠️ Warning: Only {len(questions)} questions available. Supplementing with AI generation.")
            # Generate additional questions using AI
            additional_questions = aptitude_evaluator.generate_adaptive_questions(
                student_performance, company_name, 30 - len(questions)
            )
            questions.extend(additional_questions)
            save_ai_generated_questions(additional_questions, company_name)

        # Shuffle questions for randomization
        import random
        random.shuffle(questions)

        # Ensure questions have sequential IDs starting from 1
        for i, question in enumerate(questions[:30], 1):
            question['id'] = i

        # Store questions in session for evaluation during completion
        final_questions = questions[:30]
        session['aptitude_questions'] = final_questions

        return jsonify({
            "success": True,
            "questions": final_questions,  # Ensure exactly 30
            "total_questions": 30,
            "company": company_name,
            "generation_method": "ai_adaptive" if use_ai_generation else "database"
        })

    except Exception as e:
        print(f"❌ Error fetching questions: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


def get_student_performance_history(email: str) -> Dict:
    """Get student's aptitude performance history for adaptive generation."""
    try:
        conn = sqlite3.connect(USERS_DB_PATH)
        c = conn.cursor()

        # Get recent attempts
        c.execute("""
            SELECT score, correct_answers, total_questions, ai_feedback
            FROM aptitude_attempts
            WHERE student_email = ?
            ORDER BY completed_at DESC
            LIMIT 5
        """, (email,))

        attempts = c.fetchall()
        conn.close()

        if not attempts:
            return {"attempts": 0, "overall_score": 0, "category_performance": {}}

        # Calculate average performance
        total_score = sum(row[0] for row in attempts if row[0] is not None)
        avg_score = total_score / len(attempts) if attempts else 0

        # Analyze category performance from AI feedback if available
        category_performance = {}
        for attempt in attempts:
            if attempt[3]:  # ai_feedback
                try:
                    feedback = json.loads(attempt[3])
                    if "category_performance" in feedback:
                        for cat, perf in feedback["category_performance"].items():
                            if cat not in category_performance:
                                category_performance[cat] = {"correct": 0, "total": 0}
                            category_performance[cat]["correct"] += perf.get("correct", 0)
                            category_performance[cat]["total"] += perf.get("total", 0)
                except BaseException:
                    pass

        # Convert to percentages
        for cat in category_performance:
            correct = category_performance[cat]["correct"]
            total = category_performance[cat]["total"]
            category_performance[cat]["percentage"] = (correct / total * 100) if total > 0 else 0

        return {
            "attempts": len(attempts),
            "overall_score": avg_score,
            "category_performance": category_performance
        }

    except Exception as e:
        print(f"Warning: Could not get performance history: {e}")
        return {"attempts": 0, "overall_score": 0, "category_performance": {}}


def should_use_ai_generation(email: str, company_name: str, performance: Dict) -> bool:
    """Determine if AI question generation should be used."""
    try:
        # First check if JSON dataset exists and has enough questions
        import os
        company_file_map = {
            "google": "google_aptitude.json",
            "microsoft": "microsoft_aptitude.json",
            "amazon": "amazon_aptitude.json",
            "infosys": "infosys_aptitude.json",
            "wipro": "wipro_aptitude.json",
            "flipkart": "flipkart_aptitude.json",
            "swiggy": "swiggy_aptitude.json",
            "razorpay": "razorpay_aptitude.json",
            "deloitte": "deloitte_aptitude.json",
            "accenture": "accenture_aptitude.json"
        }

        file_name = company_file_map.get(company_name.lower(), "generic.json")
        file_path = os.path.join("datasets", file_name)

        if os.path.exists(file_path):
            import json
            with open(file_path, 'r') as f:
                data = json.load(f)
                question_count = len(data.get("aptitude", []))
                if question_count >= 30:
                    # Use dataset questions if available and sufficient
                    return False

        # Check database question count as fallback
        conn = sqlite3.connect(USERS_DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id FROM companies WHERE lower(trim(name)) = lower(trim(?))", (company_name,))
        company_result = c.fetchone()

        if not company_result:
            conn.close()
            return True  # Generate if company not found

        company_id = company_result[0]

        # Check questions.db for question count
        questions_conn = sqlite3.connect(QUESTIONS_DB_PATH)
        questions_c = questions_conn.cursor()
        questions_c.execute("SELECT COUNT(*) FROM aptitude_questions WHERE company_id = ?", (company_id,))
        db_question_count = questions_c.fetchone()[0]
        questions_conn.close()
        conn.close()

        # Use AI generation if:
        # 1. Less than 30 questions in database AND no JSON dataset
        # 2. Student has poor performance (needs personalized questions)
        # 3. Student has taken many tests (needs fresh content)
        use_ai = (
            db_question_count < 30 or
            performance.get("overall_score", 100) < 70 or
            performance.get("attempts", 0) > 3
        )

        return use_ai

    except Exception as e:
        print(f"Warning: Error checking AI generation need: {e}")
        return False  # Default to database questions


def get_database_questions(company_name: str) -> List[Dict]:
    """Get questions from datasets JSON files."""
    import os
    import json

    # Map company names to file names
    company_file_map = {
        "google": "google_aptitude.json",
        "microsoft": "microsoft_aptitude.json",
        "amazon": "amazon_aptitude.json",
        "infosys": "infosys_aptitude.json",
        "wipro": "wipro_aptitude.json",
        "flipkart": "flipkart_aptitude.json",
        "swiggy": "swiggy_aptitude.json",
        "razorpay": "razorpay_aptitude.json",
        "deloitte": "deloitte_aptitude.json",
        "accenture": "accenture_aptitude.json"
    }

    file_name = company_file_map.get(company_name.lower(), "generic.json")
    file_path = os.path.join("datasets", file_name)

    if not os.path.exists(file_path):
        print(f"Dataset file not found: {file_path}")
        return []

    try:
        with open(file_path, 'r') as f:
            data = json.load(f)

        questions = []
        for q in data.get("aptitude", []):
            questions.append({
                "id": q["id"],
                "question": q["q"],
                "options": q["options"],
                "correct_answer": q["correct_answer"],
                "explanation": "",  # No explanation in current datasets
                "difficulty": "Medium",
                "category": q.get("topic", "General"),
                "time_limit": 60
            })

        return questions
    except Exception as e:
        print(f"Error loading questions from {file_path}: {e}")
        return []


def save_ai_generated_questions(questions: List[Dict], company_name: str):
    """Save AI-generated questions to database for future use."""
    try:
        # Get company ID from users.db
        users_conn = sqlite3.connect(USERS_DB_PATH)
        users_c = users_conn.cursor()
        users_c.execute("SELECT id FROM companies WHERE lower(trim(name)) = lower(trim(?))", (company_name,))
        company_result = users_c.fetchone()

        if not company_result:
            # Insert company if not exists in users.db
            users_c.execute("INSERT INTO companies (name) VALUES (?)", (company_name,))
            company_id = users_c.lastrowid
        else:
            company_id = company_result[0]
        users_conn.close()

        # Save questions to questions.db
        conn = sqlite3.connect(QUESTIONS_DB_PATH)
        c = conn.cursor()

        # Insert questions
        for q in questions:
            c.execute("""
                INSERT INTO aptitude_questions (
                    company_id, category, difficulty, question,
                    option_a, option_b, option_c, option_d,
                    correct_answer, explanation, time_limit, year_asked
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                company_id,
                q.get("category", "General"),
                q.get("difficulty", "Medium"),
                q.get("question", ""),
                q.get("options", ["", "", "", ""])[0],
                q.get("options", ["", "", "", ""])[1],
                q.get("options", ["", "", "", ""])[2],
                q.get("options", ["", "", "", ""])[3],
                q.get("correct_answer", "A"),
                q.get("explanation", ""),
                q.get("time_limit", 60),
                2024
            ))

        conn.commit()
        conn.close()
        print(f"✅ Saved {len(questions)} AI-generated questions to database")

    except Exception as e:
        print(f"Warning: Could not save AI-generated questions: {e}")


@aptitude_bp.route("/complete-test", methods=["POST"])
def complete_test():
    """Complete test and save results"""
    if "email" not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    try:
        data = request.json
        email = session["email"]

        if not data:
            print("ERROR: No data received")
            return jsonify({"success": False, "error": "No data received"}), 400

        responses = data.get('responses', [])  # List of {question_id, selected_answer, time_spent}
        time_taken = data.get('time_taken', 0)

        print(f"DEBUG: Received {len(responses)} responses, time_taken={time_taken}")

        if not responses or len(responses) == 0:
            print("ERROR: No responses provided")
            return jsonify({"success": False, "error": "No responses provided. Please answer all questions."}), 400

        # Check if at least some questions are answered
        answered_count = sum(1 for resp in responses if resp.get('selected_answer'))
        print(f"DEBUG: {answered_count} questions answered out of {len(responses)}")

        if answered_count == 0:
            print("ERROR: No questions answered")
            return jsonify({"success": False, "error": "All questions must be answered."}), 400

        print(f"✅ Completing test for {email} with {len(responses)} responses")

        # Get selected company
        selected_company = get_selected_company(email)
        company_name = selected_company['name'] if selected_company else "General"

        # ✅ FIX 6: Save to users.db
        try:
            users_conn = sqlite3.connect(USERS_DB_PATH)
            users_c = users_conn.cursor()

            # ✅ Create aptitude attempt
            users_c.execute("""
                INSERT INTO aptitude_attempts
                (student_email, company_name, total_questions, time_taken, status)
                VALUES (?, ?, ?, ?, 'completed')
            """, (email, company_name, len(responses), time_taken))

            attempt_id = users_c.lastrowid
            print(f"✅ Created attempt_id: {attempt_id}")
        except sqlite3.Error as db_err:
            print(f"ERROR: Database error creating attempt: {db_err}")
            if users_conn:
                users_conn.close()
            return jsonify({"success": False, "error": f"Database error: {str(db_err)}"}), 500

        # Get questions from session (stored during test start)
        stored_questions = session.get('aptitude_questions', [])

        # Prepare questions for AI batch evaluation
        questions_for_ai = []

        # Calculate score and save each response
        correct_count = 0
        answered_with_keys = 0

        for resp in responses:
            question_id = resp.get('question_id')
            selected = resp.get('selected_answer')  # A, B, C, D
            time_spent = resp.get('time_spent', 0)

            # Find the question in stored questions
            question_data = None
            for q in stored_questions:
                if q.get('id') == question_id:
                    question_data = q
                    break

            if question_data:
                correct_answer = question_data.get('correct_answer', '')
                question_text = question_data.get('question', '')
                options = question_data.get('options', [])
                category = question_data.get('category', 'General')

                # Simple evaluation for now (can be enhanced with AI later)
                is_correct = (selected == correct_answer) if selected and correct_answer else False
                if is_correct:
                    correct_count += 1

                # Add to AI evaluation batch (for future enhancement)
                questions_for_ai.append({
                    "question_id": question_id,
                    "question": question_text,
                    "options": options,
                    "selected_answer": selected,
                    "correct_answer": correct_answer,
                    "category": category,
                    "time_spent": time_spent,
                    "is_correct": is_correct
                })

                # Save response
                users_c.execute("""
                    INSERT INTO aptitude_responses
                    (attempt_id, question_id, question_text, selected_answer, correct_answer, is_correct, time_spent)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (attempt_id, question_id, question_text, selected, correct_answer, is_correct, time_spent))
            else:
                print(f"WARNING: Question ID {question_id} not found in session")
                # Still save the response with minimal data
                users_c.execute("""
                    INSERT INTO aptitude_responses
                    (attempt_id, question_id, question_text, selected_answer, time_spent)
                    VALUES (?, ?, ?, ?, ?)
                """, (attempt_id, question_id, f"Question {question_id}", selected, time_spent))

        # Calculate final score (percentage)
        total_answered = len([q for q in questions_for_ai if q.get('selected_answer')])
        score = (correct_count / 30 * 100) if 30 > 0 else 0

        print(f"✅ Test completed: {correct_count}/{total_answered} correct answers, Score: {score:.1f}%")

        # Generate simple feedback based on performance
        if score >= 80:
            feedback = "Excellent performance! You have strong aptitude skills."
        elif score >= 60:
            feedback = "Good performance! Keep practicing to improve further."
        elif score >= 40:
            feedback = "Fair performance. Focus on fundamental concepts and practice more."
        else:
            feedback = "Needs improvement. Consider reviewing basic aptitude concepts."

        # ✅ Generate performance feedback
        print("Generating performance feedback...")

        # Prepare feedback data
        ai_feedback_json = json.dumps({
            "feedback": feedback,
            "score": score,
            "correct_answers": correct_count,
            "total_questions": 30,
            "generated_at": datetime.now().isoformat(),
            "evaluation_method": "simple"
        })

        # ✅ Update attempt with final score and AI feedback (if available)
        try:
            if ai_feedback_json:
                users_c.execute("""
                    UPDATE aptitude_attempts
                    SET correct_answers = ?, score = ?, ai_feedback = ?
                    WHERE id = ?
                """, (correct_count, score, ai_feedback_json, attempt_id))
            else:
                # Fallback: update without ai_feedback if column doesn't exist or feedback failed
                users_c.execute("""
                    UPDATE aptitude_attempts
                    SET correct_answers = ?, score = ?
                    WHERE id = ?
                """, (correct_count, score, attempt_id))
        except sqlite3.OperationalError as db_error:
            # If ai_feedback column doesn't exist, update without it
            print(f"Warning: Database column issue: {db_error}")
            users_c.execute("""
                UPDATE aptitude_attempts
                SET correct_answers = ?, score = ?
                WHERE id = ?
            """, (correct_count, score, attempt_id))

        users_conn.commit()
        users_conn.close()

        print(f"✅ Test completed: Score={score:.2f}%, Correct={correct_count}/{len(responses)}")

        # Clear questions from session
        session.pop('aptitude_questions', None)

        return jsonify({
            "success": True,
            "message": "Test completed successfully",
            "score": round(score, 2),
            "correct_answers": correct_count,
            "total_questions": len(responses),
            "attempt_id": attempt_id,
            "feedback": feedback
        })

    except Exception as e:
        print(f"❌ Error completing test: {e}")
        import traceback
        traceback.print_exc()

        # Provide more detailed error message
        error_msg = str(e)
        if "UNIQUE constraint failed" in error_msg:
            error_msg = "You have already submitted this test. Please refresh the page."
        elif "NOT NULL constraint failed" in error_msg:
            error_msg = f"Database error: {error_msg}. Please ensure all required fields are filled."

        return jsonify({"success": False, "error": error_msg}), 500


def generate_evaluation_notes(test_results: Dict, student_name: str, company_name: str) -> Dict:
    """
    Generate comprehensive evaluation notes for continuous improvement and professional assessment.
    """
    try:
        results = test_results.get("results", [])
        score = test_results.get("score", 0)
        correct_count = test_results.get("correct_count", 0)
        total_count = test_results.get("total_count", 0)

        # Analyze performance patterns
        category_performance = {}
        time_analysis = {"fast_correct": 0, "slow_correct": 0, "fast_wrong": 0, "slow_wrong": 0}
        difficulty_analysis = {
            "easy": {
                "correct": 0, "total": 0}, "medium": {
                "correct": 0, "total": 0}, "hard": {
                "correct": 0, "total": 0}}

        for result in results:
            category = result.get("category", "General")
            if category not in category_performance:
                category_performance[category] = {"correct": 0, "total": 0}
            category_performance[category]["total"] += 1
            if result.get("is_correct"):
                category_performance[category]["correct"] += 1

        # Calculate percentages and insights
        evaluation_notes = {
            "student_name": student_name,
            "company_name": company_name,
            "test_date": datetime.now().isoformat(),
            "overall_performance": {
                "score_percentage": score,
                "correct_answers": correct_count,
                "total_questions": total_count,
                "performance_level": "Excellent" if score >= 85 else "Good" if score >= 70 else "Needs Improvement" if score >= 50 else "Critical Review Required"
            },
            "category_analysis": {},
            "recommendations": [],
            "professional_assessment": "",
            "improvement_plan": [],
            "next_steps": []
        }

        # Category-wise analysis
        for category, perf in category_performance.items():
            percentage = (perf["correct"] / perf["total"] * 100) if perf["total"] > 0 else 0
            evaluation_notes["category_analysis"][category] = {
                "score": round(percentage, 1),
                "correct": perf["correct"],
                "total": perf["total"],
                "strength": percentage >= 80,
                "needs_focus": percentage < 60
            }

        # Generate professional recommendations
        weak_categories = [cat for cat, perf in evaluation_notes["category_analysis"].items() if perf["needs_focus"]]
        strong_categories = [cat for cat, perf in evaluation_notes["category_analysis"].items() if perf["strength"]]

        evaluation_notes["recommendations"] = [
            f"Focus on improving {', '.join(weak_categories)} skills" if weak_categories else "Maintain strong performance across all categories",
            f"Leverage strengths in {', '.join(strong_categories)} for other areas" if strong_categories else "Build foundational skills first",
            "Practice with company-specific question patterns",
            "Review incorrect answers and understand reasoning",
            "Time management is crucial for competitive exams"]

        # Professional assessment
        if score >= 90:
            evaluation_notes["professional_assessment"] = f"{student_name} demonstrates exceptional aptitude skills suitable for senior technical roles at {company_name}. Ready for advanced technical interviews."
        elif score >= 80:
            evaluation_notes["professional_assessment"] = f"{student_name} shows strong analytical abilities with good potential for {company_name} technical positions. Minor improvements needed in weak areas."
        elif score >= 70:
            evaluation_notes["professional_assessment"] = f"{student_name} has solid foundational skills for {company_name} roles. Focused practice in identified weak areas will enhance performance."
        elif score >= 60:
            evaluation_notes["professional_assessment"] = f"{student_name} needs significant improvement in aptitude skills. Additional preparation and practice recommended before {company_name} interviews."
        else:
            evaluation_notes["professional_assessment"] = f"{student_name} requires comprehensive aptitude skill development. Consider additional training and mentorship before pursuing {company_name} opportunities."

        # Improvement plan
        evaluation_notes["improvement_plan"] = [
            "Daily practice sessions (1-2 hours) focusing on weak categories",
            "Review fundamental concepts in struggling areas",
            "Take regular mock tests to track progress",
            "Study company-specific interview patterns and requirements",
            "Seek mentorship or additional training resources",
            "Practice time management techniques for better efficiency"
        ]

        # Next steps
        evaluation_notes["next_steps"] = [
            "Schedule next practice test within 1 week",
            "Focus on 2-3 weak categories for intensive practice",
            "Review company job descriptions and requirements",
            "Consider additional certification or training programs",
            "Connect with professionals in target roles for insights"
        ]

        return evaluation_notes

    except Exception as e:
        print(f"Warning: Could not generate evaluation notes: {e}")
        return {
            "error": "Could not generate evaluation notes",
            "basic_assessment": f"Score: {test_results.get('score', 0):.1f}%"
        }


@aptitude_bp.route("/history", methods=["GET"])
def get_aptitude_history():
    """Get student's aptitude test history"""
    if "email" not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    try:
        email = session["email"]

        conn = sqlite3.connect(USERS_DB_PATH)
        c = conn.cursor()

        c.execute("""
            SELECT id, company_name, score, correct_answers, total_questions,
                   time_taken, completed_at
            FROM aptitude_attempts
            WHERE student_email = ?
            ORDER BY completed_at DESC
            LIMIT 10
        """, (email,))

        history = []
        for row in c.fetchall():
            history.append({
                "attempt_id": row[0],
                "company": row[1],
                "score": row[2],
                "correct_answers": row[3],
                "total_questions": row[4],
                "time_taken": row[5],
                "completed_at": row[6]
            })

        conn.close()

        return jsonify({
            "success": True,
            "history": history
        })

    except Exception as e:
        print(f"Error getting aptitude history: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@aptitude_bp.route("/attempt/<attempt_id>", methods=["GET"])
def get_attempt_details(attempt_id):
    """Get detailed results for an aptitude attempt with AI feedback"""
    if "email" not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    try:
        email = session["email"]

        conn = sqlite3.connect(USERS_DB_PATH)
        c = conn.cursor()

        # Get attempt info with AI feedback
        c.execute("""
            SELECT company_name, score, correct_answers, total_questions,
                   time_taken, completed_at, ai_feedback
            FROM aptitude_attempts
            WHERE id = ? AND student_email = ?
        """, (attempt_id, email))

        attempt = c.fetchone()
        if not attempt:
            conn.close()
            return jsonify({"success": False, "error": "Attempt not found"}), 404

        # Get responses
        c.execute("""
            SELECT question_text, selected_answer, correct_answer, is_correct, time_spent
            FROM aptitude_responses
            WHERE attempt_id = ?
        """, (attempt_id,))

        responses = []
        for row in c.fetchall():
            responses.append({
                "question": row[0],
                "selected": row[1],
                "correct": row[2],
                "is_correct": row[3],
                "time_spent": row[4]
            })

        conn.close()

        # Parse AI feedback from JSON
        ai_feedback = None
        if attempt[6]:  # ai_feedback column
            try:
                ai_feedback = json.loads(attempt[6])
            except BaseException:
                pass

        return jsonify({
            "success": True,
            "attempt": {
                "company": attempt[0],
                "score": attempt[1],
                "correct_answers": attempt[2],
                "total_questions": attempt[3],
                "time_taken": attempt[4],
                "completed_at": attempt[5],
                "ai_feedback": ai_feedback
            },
            "responses": responses
        })

    except Exception as e:
        print(f"Error getting attempt details: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@aptitude_bp.route("/feedback/<attempt_id>", methods=["GET"])
def get_aptitude_feedback(attempt_id):
    """Get AI-generated feedback for an aptitude test attempt (API endpoint)"""
    if "email" not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    try:
        email = session["email"]

        conn = sqlite3.connect(USERS_DB_PATH)
        c = conn.cursor()

        # Get AI feedback
        c.execute("""
            SELECT ai_feedback, score, correct_answers, total_questions, company_name
            FROM aptitude_attempts
            WHERE id = ? AND student_email = ?
        """, (attempt_id, email))

        result = c.fetchone()
        conn.close()

        if not result:
            return jsonify({"success": False, "error": "Attempt not found"}), 404

        # Parse feedback
        ai_feedback = None
        if result[0]:
            try:
                ai_feedback = json.loads(result[0])
            except BaseException:
                ai_feedback = {"error": "Unable to parse feedback"}

        if not ai_feedback:
            # Generate feedback if not already present
            ai_feedback = {
                "motivational_message": f"You scored {result[1]:.1f}% on your {result[4]} aptitude test.",
                "strengths": ["Completed the test"],
                "areas_for_improvement": ["Practice more questions"],
                "study_plan": ["Review incorrect answers", "Practice daily"],
                "next_steps": ["Take another practice test"],
                "encouragement": "Keep practicing to improve!"
            }

        return jsonify({
            "success": True,
            "feedback": ai_feedback,
            "score": result[1],
            "correct_answers": result[2],
            "total_questions": result[3],
            "company_name": result[4]
        })

    except Exception as e:
        print(f"Error getting feedback: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@aptitude_bp.route("/feedback-page", methods=["GET"])
def aptitude_feedback_page():
    """Render the professional feedback page"""
    if "email" not in session:
        return redirect(url_for("login"))

    return render_template("aptitude_feedback.html")
