# secure_judge0_executor.py
import os
import time
import json
import requests
import sqlite3
from datetime import datetime
from flask import Blueprint, request, jsonify

judge_bp = Blueprint("judge0", __name__)

# ---------------- CONFIG ----------------
JUDGE0_API = os.getenv("JUDGE0_API_URL", "https://judge0-ce.p.rapidapi.com/submissions")
JUDGE0_KEY = os.getenv("JUDGE0_API_KEY")  # optional
TECH_DB_PATH = "technical_attempts.db"
FEEDBACK_DB_PATH = "feedback.db"  # ✅ sync into feedback DB
LANGUAGE_MAP = {
    "python": 71, "cpp": 54, "c": 50, "java": 62, "javascript": 63
}


# ---------------- HELPER: Judge0 EXECUTION ----------------
def execute_with_judge0(source_code, language, testcases, timeout=10):
    if language not in LANGUAGE_MAP:
        return {"error": f"Unsupported language: {language}"}

    lang_id = LANGUAGE_MAP[language]
    headers = {"Content-Type": "application/json"}
    if JUDGE0_KEY:
        headers["X-RapidAPI-Key"] = JUDGE0_KEY
        headers["X-RapidAPI-Host"] = "judge0-ce.p.rapidapi.com"

    results = []
    for tc in testcases:
        payload = {
            "language_id": lang_id,
            "source_code": source_code,
            "stdin": tc.get("input", ""),
            "expected_output": tc.get("output", ""),
            "cpu_time_limit": 2,
            "memory_limit": 128000
        }

        try:
            res = requests.post(f"{JUDGE0_API}?base64_encoded=false&wait=false",
                                headers=headers, json=payload, timeout=timeout)
            token = res.json().get("token")
            if not token:
                results.append({"passed": False, "error": "Submission failed"})
                continue

            # Poll for result
            for _ in range(12):
                time.sleep(1)
                poll = requests.get(f"{JUDGE0_API}/{token}?base64_encoded=false", headers=headers)
                if poll.status_code != 200:
                    continue
                data = poll.json()
                status = data.get("status", {}).get("description", "")
                if status not in ["In Queue", "Processing"]:
                    results.append({
                        "input": tc.get("input", ""),
                        "expected_output": tc.get("output", ""),
                        "actual_output": data.get("stdout") or "",
                        "passed": status == "Accepted",
                        "status": status,
                        "error": data.get("stderr") or ""
                    })
                    break
            else:
                results.append({"passed": False, "error": "Timeout"})
        except Exception as e:
            results.append({"passed": False, "error": str(e)})

    return {"results": results, "passed": sum(r["passed"] for r in results), "total": len(results)}


# ---------------- HELPER: AI FEEDBACK GENERATOR ----------------
def generate_ai_feedback(score, results, question):
    """Generate AI-style feedback summary"""
    categories = question.get("category", "General Problem Solving")

    if score >= 85:
        level = "Excellent"
        note = "Outstanding code quality and logic clarity."
        reco = "Tackle advanced algorithmic problems next."
    elif score >= 60:
        level = "Good"
        note = "Solid foundation. Focus on optimizing edge cases."
        reco = "Revise data structures and common algorithmic traps."
    elif score >= 40:
        level = "Moderate"
        note = "Some logic flaws or incomplete handling of test cases."
        reco = "Reattempt similar category problems."
    else:
        level = "Needs Improvement"
        note = "Significant logic errors or failed outputs detected."
        reco = "Revisit problem understanding and dry-run logic."

    strengths = []
    if score >= 60:
        strengths.append("Logical approach")
        if all(r["passed"] for r in results):
            strengths.append("Complete accuracy")
    else:
        strengths.append("Good code structure")

    weak_areas = []
    if score < 85:
        weak_areas.append(categories)
    if any("Time Limit" in r["status"] for r in results):
        weak_areas.append("Optimization and time complexity")

    return {
        "overall": level,
        "note": note,
        "recommendation": reco,
        "strengths": strengths,
        "weak_areas": weak_areas
    }


# ---------------- MAIN ROUTE ----------------
@judge_bp.route("/technical/run-code/<company>", methods=["POST"])
def run_code(company):
    data = request.get_json(force=True)
    code = data.get("code", "")
    language = data.get("language", "python").lower()
    question_id = data.get("question_id")
    attempt_id = data.get("attempt_id")

    # Safety filter
    if any(x in code for x in ["import os", "subprocess", "open(", "system("]):
        return jsonify({"success": False, "error": "Unsafe code detected"}), 400

    # Load testcases
    try:
        with open(f"datasets/{company.lower()}_technical.json") as f:
            dataset = json.load(f)
        question = next((q for q in dataset["technical"] if q["id"] == question_id), None)
        if not question:
            return jsonify({"success": False, "error": "Question not found"}), 404
        testcases = question.get("testcases", [])
    except Exception as e:
        return jsonify({"success": False, "error": f"Dataset load error: {e}"}), 500

    result = execute_with_judge0(code, language, testcases)
    total, passed = result["total"], result["passed"]
    score = round((passed / total) * 100, 2) if total else 0

    ai_feedback = generate_ai_feedback(score, result["results"], question)

    # ---------- Store in Technical DB ----------
    try:
        conn = sqlite3.connect(TECH_DB_PATH)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS technical_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                attempt_id TEXT,
                company_name TEXT,
                question_id TEXT,
                language TEXT,
                score REAL,
                passed_count INTEGER,
                total_count INTEGER,
                feedback_json TEXT,
                submitted_at TEXT
            )
        """)
        cur.execute("""
            INSERT INTO technical_attempts (attempt_id, company_name, question_id, language, score,
            passed_count, total_count, feedback_json, submitted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            attempt_id or f"{company}_{int(time.time())}",
            company,
            question_id,
            language,
            score,
            passed,
            total,
            json.dumps(ai_feedback),
            datetime.now().isoformat()
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        print("⚠️ Failed saving technical_attempts:", e)

    # ---------- Store in Unified Feedback DB ----------
    try:
        conn = sqlite3.connect(FEEDBACK_DB_PATH)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS feedback_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT,
                section TEXT,
                company TEXT,
                score REAL,
                strengths TEXT,
                weaknesses TEXT,
                recommendation TEXT,
                feedback_json TEXT,
                timestamp TEXT
            )
        """)
        cur.execute("""
            INSERT INTO feedback_summary (email, section, company, score, strengths, weaknesses, recommendation, feedback_json, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "msmsmallikarjuna@gmail.com",  # can replace with session email
            "Technical",
            company,
            score,
            ", ".join(ai_feedback["strengths"]),
            ", ".join(ai_feedback["weak_areas"]),
            ai_feedback["recommendation"],
            json.dumps(ai_feedback),
            datetime.now().isoformat()
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        print("⚠️ Failed saving feedback_summary:", e)

    return jsonify({
        "success": True,
        "results": result["results"],
        "passed": passed,
        "total": total,
        "score": score,
        "feedback": ai_feedback
    })
