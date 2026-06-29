"""
Comprehensive Feedback and Report Generation System
Generates detailed reports combining all interview rounds
"""

from flask import Blueprint, jsonify, request, session, render_template
import sqlite3
import json
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from utils import get_selected_company
import io

feedback_bp = Blueprint("feedback", __name__, url_prefix="/feedback")

DB_PATH = "users.db"


@feedback_bp.route("/")
def feedback_home():
    """Feedback dashboard home page"""
    if "email" not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    return render_template("feedback.html", username=session.get("name"))


@feedback_bp.route("/generate", methods=["POST"])
def generate_comprehensive_feedback():
    """Generate comprehensive feedback report for all rounds"""
    if "email" not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    try:
        email = session["email"]

        # Get selected company context
        selected = get_selected_company(email)
        selected_company = selected["name"] if selected else None

        # Get all scores from different rounds (scoped to selected company)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        # Get latest aptitude attempt for selected company
        if selected_company:
            c.execute(
                """
                SELECT score FROM aptitude_attempts
                WHERE student_email = ? AND company_name = ?
                ORDER BY completed_at DESC
                LIMIT 1
                """,
                (email, selected_company),
            )
            row = c.fetchone()
            aptitude_score = row[0] if row else 0
            aptitude_attempts = 1 if row else 0
        else:
            aptitude_score = 0
            aptitude_attempts = 0

        # Get technical scores for selected company
        if selected_company:
            c.execute(
                """
                SELECT AVG(score), COUNT(*)
                FROM technical_attempts
                WHERE student_email = ? AND company_name = ? AND status = 'completed'
                """,
                (email, selected_company),
            )
            technical_result = c.fetchone()
            technical_score = technical_result[0] if technical_result and technical_result[0] else 0
            technical_attempts = technical_result[1] if technical_result and technical_result[1] else 0
        else:
            technical_score = 0
            technical_attempts = 0

        # Get GD scores for selected company
        if selected_company:
            c.execute(
                """
                SELECT AVG(overall_score), COUNT(*)
                FROM gd_results
                WHERE student_email = ? AND company_name = ?
                """,
                (email, selected_company),
            )
            gd_result = c.fetchone()
            gd_score = gd_result[0] if gd_result and gd_result[0] else 0
            gd_attempts = gd_result[1] if gd_result and gd_result[1] else 0
        else:
            gd_score = 0
            gd_attempts = 0

        # Get HR scores for selected company
        if selected_company:
            c.execute(
                """
                SELECT AVG(overall_score), COUNT(*)
                FROM hr_attempts
                WHERE student_email = ? AND company_name = ? AND status = 'completed'
                """,
                (email, selected_company),
            )
            hr_result = c.fetchone()
            hr_score = hr_result[0] if hr_result and hr_result[0] else 0
            hr_attempts = hr_result[1] if hr_result and hr_result[1] else 0
        else:
            hr_score = 0
            hr_attempts = 0

        # Use selected company name
        company_name = selected_company if selected_company else "General"

        # Calculate weighted overall score
        # Aptitude: 30%, Technical: 40%, GD: 15%, HR: 15%
        overall_score = (
            (aptitude_score * 0.30) +
            (technical_score * 0.40) +
            (gd_score * 0.15) +
            (hr_score * 0.15)
        )

        # Generate detailed feedback
        feedback_analysis = generate_detailed_feedback(
            aptitude_score, technical_score, gd_score, hr_score, overall_score
        )

        # Save comprehensive report (table doesn't exist yet)
        # c.execute("""
        #     INSERT INTO feedback_reports
        #     (student_email, company_name, aptitude_score, technical_score,
        #      gd_score, hr_score, overall_score, strengths, improvements, recommendations)
        #     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        # """, (email, company_name, aptitude_score, technical_score,
        #       gd_score, hr_score, overall_score,
        #       json.dumps(feedback_analysis['strengths']),
        #       json.dumps(feedback_analysis['improvements']),
        #       json.dumps(feedback_analysis['recommendations'])))

        # conn.commit()
        conn.close()

        return jsonify({
            "success": True,
            "scores": {
                "aptitude": round(aptitude_score, 2),
                "technical": round(technical_score, 2),
                "gd": round(gd_score, 2),
                "hr": round(hr_score, 2),
                "overall": round(overall_score, 2)
            },
            "attempts": {
                "aptitude": aptitude_attempts,
                "technical": technical_attempts,
                "gd": gd_attempts,
                "hr": hr_attempts
            },
            "feedback": feedback_analysis,
            "company": company_name
        })

    except Exception as e:
        print(f"Error generating feedback: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@feedback_bp.route("/detailed-analysis", methods=["GET"])
def get_detailed_analysis():
    """Get detailed analysis for each round"""
    if "email" not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    try:
        email = session["email"]

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        # Get aptitude analysis
        c.execute("""
            SELECT topic, AVG(score), COUNT(*)
            FROM test_attempts
            WHERE student_email = ? AND status = 'completed'
            GROUP BY topic
        """, (email,))
        aptitude_analysis = [{"topic": row[0], "avg_score": row[1], "attempts": row[2]}
                             for row in c.fetchall()]

        # Get technical analysis
        c.execute("""
            SELECT company_name, AVG(score), COUNT(*)
            FROM technical_attempts
            WHERE student_email = ? AND status = 'completed'
            GROUP BY company_name
        """, (email,))
        technical_analysis = [{"company_name": row[0], "avg_score": row[1], "attempts": row[2]}
                              for row in c.fetchall()]

        # Get GD analysis
        c.execute("""
            SELECT fluency_score, clarity_score, confidence_score, overall_score
            FROM gd_results
            WHERE student_email = ?
            ORDER BY submitted_at DESC
            LIMIT 5
        """, (email,))
        gd_analysis = [{"fluency": row[0], "clarity": row[1], "confidence": row[2], "overall": row[3]}
                       for row in c.fetchall()]

        # Get HR analysis
        c.execute("""
            SELECT clarity_score, relevance_score, confidence_score, overall_score
            FROM hr_attempts
            WHERE student_email = ? AND status = 'completed'
            ORDER BY completed_at DESC
            LIMIT 5
        """, (email,))
        hr_analysis = [{"clarity": row[0], "relevance": row[1], "confidence": row[2], "overall": row[3]}
                       for row in c.fetchall()]

        conn.close()

        return jsonify({
            "success": True,
            "aptitude_analysis": aptitude_analysis,
            "technical_analysis": technical_analysis,
            "gd_analysis": gd_analysis,
            "hr_analysis": hr_analysis
        })

    except Exception as e:
        print(f"Error getting detailed analysis: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@feedback_bp.route("/download-pdf", methods=["GET"])
def download_pdf_report():
    """Download comprehensive PDF report"""
    if "email" not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    try:
        email = session["email"]

        # Feedback reports table doesn't exist yet
        # conn = sqlite3.connect(DB_PATH)
        # c = conn.cursor()
        # c.execute("""
        #     SELECT * FROM feedback_reports
        #     WHERE student_email = ?
        #     ORDER BY generated_at DESC
        #     LIMIT 1
        # """, (email,))

        # report = c.fetchone()
        # if not report:
        return jsonify({"success": False, "error": "Feedback reports feature is not yet available"}), 404

        # # Get student details
        # c.execute("SELECT * FROM students WHERE email = ?", (email,))
        # student = c.fetchone()
        # conn.close()
        #
        # # Generate PDF
        # pdf_buffer = generate_pdf_report(report, student)
        #
        # return send_file(
        #     pdf_buffer,
        #     as_attachment=True,
        #     download_name=f"Interview_Report_{email}_{datetime.now().strftime('%Y%m%d')}.pdf",
        #     mimetype='application/pdf'
        # )

    except Exception as e:
        print(f"Error generating PDF: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


def generate_aptitude_feedback(score, correct, total, time_taken):
    """Generate specific feedback for aptitude test"""
    feedback = {
        "performance": "",
        "strengths": [],
        "improvements": [],
        "recommendations": []
    }

    # Performance analysis
    if score >= 80:
        feedback["performance"] = "Excellent performance! You have strong aptitude skills."
        feedback["strengths"].append("Outstanding logical reasoning abilities")
        feedback["strengths"].append("Quick problem-solving skills")
    elif score >= 60:
        feedback["performance"] = "Good performance with room for improvement."
        feedback["strengths"].append("Solid foundation in aptitude concepts")
        feedback["improvements"].append("Focus on time management")
    else:
        feedback["performance"] = "Needs improvement. Consider more practice."
        feedback["improvements"].append("Strengthen basic aptitude concepts")
        feedback["improvements"].append("Practice more sample questions")

    # Time management analysis
    avg_time_per_question = time_taken / total if total > 0 else 0
    if avg_time_per_question <= 60:
        feedback["strengths"].append("Good time management")
    else:
        feedback["improvements"].append("Improve time management skills")

    # Accuracy analysis
    accuracy = (correct / total * 100) if total > 0 else 0
    if accuracy >= 80:
        feedback["strengths"].append("High accuracy in answers")
    else:
        feedback["improvements"].append("Focus on accuracy over speed")

    # Recommendations
    if score >= 80:
        feedback["recommendations"].append("Ready for advanced aptitude challenges")
        feedback["recommendations"].append("Consider competitive exam preparation")
    elif score >= 60:
        feedback["recommendations"].append("Practice more medium-difficulty questions")
        feedback["recommendations"].append("Work on speed and accuracy balance")
    else:
        feedback["recommendations"].append("Start with basic aptitude concepts")
        feedback["recommendations"].append("Practice regularly with timed tests")

    return feedback


def generate_technical_feedback(score, domain):
    """Generate specific feedback for technical test"""
    feedback = {
        "performance": "",
        "strengths": [],
        "improvements": [],
        "recommendations": []
    }

    if score >= 80:
        feedback["performance"] = f"Excellent technical skills in {domain}!"
        feedback["strengths"].append("Strong coding abilities")
        feedback["strengths"].append("Good problem-solving approach")
    elif score >= 60:
        feedback["performance"] = f"Good technical foundation in {domain}."
        feedback["strengths"].append("Basic understanding of concepts")
        feedback["improvements"].append("Practice more complex problems")
    else:
        feedback["performance"] = f"Needs improvement in {domain}."
        feedback["improvements"].append("Strengthen fundamental concepts")
        feedback["improvements"].append("Practice basic coding problems")

    feedback["recommendations"].append(f"Focus on {domain} specific practice")
    feedback["recommendations"].append("Review data structures and algorithms")

    return feedback


def generate_gd_feedback(fluency, clarity, confidence, overall):
    """Generate specific feedback for group discussion"""
    feedback = {
        "performance": "",
        "strengths": [],
        "improvements": [],
        "recommendations": []
    }

    if overall >= 80:
        feedback["performance"] = "Excellent communication skills!"
        feedback["strengths"].append("Clear and fluent expression")
        feedback["strengths"].append("High confidence level")
    elif overall >= 60:
        feedback["performance"] = "Good communication with room for improvement."
        feedback["strengths"].append("Basic communication skills")
        feedback["improvements"].append("Work on fluency and clarity")
    else:
        feedback["performance"] = "Needs improvement in communication."
        feedback["improvements"].append("Practice public speaking")
        feedback["improvements"].append("Work on confidence building")

    if fluency >= 80:
        feedback["strengths"].append("Fluent speech delivery")
    else:
        feedback["improvements"].append("Practice speaking fluently")

    if clarity >= 80:
        feedback["strengths"].append("Clear and understandable speech")
    else:
        feedback["improvements"].append("Focus on clear articulation")

    if confidence >= 80:
        feedback["strengths"].append("High confidence in expression")
    else:
        feedback["improvements"].append("Build confidence through practice")

    feedback["recommendations"].append("Practice group discussions regularly")
    feedback["recommendations"].append("Read current affairs for better content")

    return feedback


def generate_hr_feedback(clarity, relevance, confidence, overall):
    """Generate specific feedback for HR interview"""
    feedback = {
        "performance": "",
        "strengths": [],
        "improvements": [],
        "recommendations": []
    }

    if overall >= 80:
        feedback["performance"] = "Excellent interview performance!"
        feedback["strengths"].append("Clear and relevant answers")
        feedback["strengths"].append("High confidence level")
    elif overall >= 60:
        feedback["performance"] = "Good interview skills with room for improvement."
        feedback["strengths"].append("Basic interview skills")
        feedback["improvements"].append("Work on answer relevance")
    else:
        feedback["performance"] = "Needs improvement in interview skills."
        feedback["improvements"].append("Practice common HR questions")
        feedback["improvements"].append("Work on confidence and clarity")

    if clarity >= 80:
        feedback["strengths"].append("Clear and articulate answers")
    else:
        feedback["improvements"].append("Practice clear communication")

    if relevance >= 80:
        feedback["strengths"].append("Relevant and focused responses")
    else:
        feedback["improvements"].append("Work on staying on topic")

    if confidence >= 80:
        feedback["strengths"].append("Confident and composed demeanor")
    else:
        feedback["improvements"].append("Build confidence through mock interviews")

    feedback["recommendations"].append("Practice common HR interview questions")
    feedback["recommendations"].append("Prepare STAR method examples")

    return feedback


def generate_ai_technical_feedback(
        score,
        tests_passed,
        total_tests,
        time_taken,
        questions_str,
        codes_str,
        languages_str):
    """Generate AI-powered feedback for technical round using OpenAI"""
    from ai_service import OPENAI_API_KEY
    import requests

    if not OPENAI_API_KEY:
        # Fallback to basic feedback
        return generate_technical_feedback(score, "Programming")

    try:
        # Parse the data
        questions = questions_str.split(',') if questions_str else []
        codes = codes_str.split(',') if codes_str else []
        languages = languages_str.split(',') if languages_str else []

        # Prepare code analysis
        code_analysis = []
        for i, (q, code, lang) in enumerate(zip(questions, codes, languages)):
            code_analysis.append(f"Question {i+1}: {q[:100]}...\nLanguage: {lang}\nCode Length: {len(code)} chars")

        code_summary = "\n".join(code_analysis[:3])  # Limit to first 3 for token efficiency

        prompt = f"""You are an expert technical interviewer and coding coach. Analyze this student's technical interview performance and provide detailed, actionable feedback.

Student Performance:
- Overall Score: {score:.1f}%
- Tests Passed: {tests_passed}/{total_tests}
- Time Taken: {time_taken} seconds
- Average Time per Question: {time_taken/max(len(questions),1):.1f} seconds

Code Submissions Summary:
{code_summary}

Provide a comprehensive analysis in the following JSON format:
{{
    "performance": "Overall performance assessment (2-3 sentences)",
    "strengths": ["3-5 specific technical strengths identified"],
    "improvements": ["3-5 areas that need improvement"],
    "code_quality_analysis": {{
        "readability": "Assessment of code readability and structure",
        "efficiency": "Assessment of algorithmic efficiency",
        "best_practices": "Adherence to coding best practices"
    }},
    "recommendations": ["5-7 specific, actionable recommendations"],
    "learning_path": ["3-4 next steps for improvement"],
    "motivational_message": "Encouraging message to inspire continued learning"
}}

Focus on being specific, constructive, and encouraging. Base your analysis on the actual performance metrics provided."""

        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json={
                "model": "gpt-4",
                "messages": [
                    {"role": "system", "content": "You are an expert technical interviewer providing detailed feedback."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 1200
            },
            timeout=20
        )

        if response.status_code == 200:
            result_text = response.json()["choices"][0]["message"]["content"]
            # Extract JSON from potential markdown code blocks
            result_text = result_text.strip()
            if result_text.startswith("```json"):
                result_text = result_text[7:]
            if result_text.startswith("```"):
                result_text = result_text[3:]
            if result_text.endswith("```"):
                result_text = result_text[:-3]
            result_text = result_text.strip()

            ai_feedback = json.loads(result_text)
            ai_feedback["feedback_method"] = "ai_openai"
            return ai_feedback
        else:
            print(f"OpenAI API error: {response.status_code}")
            return generate_technical_feedback(score, "Programming")

    except Exception as e:
        print(f"Error generating AI technical feedback: {e}")
        return generate_technical_feedback(score, "Programming")


def generate_detailed_feedback(aptitude_score, technical_score, gd_score, hr_score, overall_score):
    """Generate detailed feedback analysis"""
    feedback = {
        "strengths": [],
        "improvements": [],
        "recommendations": []
    }

    # Overall performance analysis
    if overall_score >= 85:
        feedback["strengths"].append("Excellent overall performance across all rounds")
        feedback["strengths"].append("Strong technical and communication skills")
        feedback["recommendations"].append("Ready for senior technical roles")
        feedback["recommendations"].append("Consider leadership positions")
    elif overall_score >= 70:
        feedback["strengths"].append("Good performance with room for improvement")
        feedback["improvements"].append("Focus on weaker areas identified below")
        feedback["recommendations"].append("Continue practicing and learning")
    else:
        feedback["improvements"].append("Significant improvement needed across multiple areas")
        feedback["recommendations"].append("Consider additional training and practice")

    # Round-specific analysis
    if aptitude_score >= 80:
        feedback["strengths"].append("Strong aptitude and logical reasoning skills")
    elif aptitude_score < 60:
        feedback["improvements"].append("Improve aptitude and logical reasoning")
        feedback["recommendations"].append("Practice more aptitude questions and puzzles")

    if technical_score >= 80:
        feedback["strengths"].append("Excellent technical and coding skills")
    elif technical_score < 60:
        feedback["improvements"].append("Strengthen technical and coding abilities")
        feedback["recommendations"].append("Practice more coding problems and algorithms")

    if gd_score >= 80:
        feedback["strengths"].append("Strong communication and group discussion skills")
    elif gd_score < 60:
        feedback["improvements"].append("Improve communication and group discussion skills")
        feedback["recommendations"].append("Practice public speaking and group discussions")

    if hr_score >= 80:
        feedback["strengths"].append("Excellent interpersonal and HR interview skills")
    elif hr_score < 60:
        feedback["improvements"].append("Improve interpersonal and interview skills")
        feedback["recommendations"].append("Practice HR interview questions and scenarios")

    # Career recommendations based on scores
    if technical_score > aptitude_score and technical_score > 75:
        feedback["recommendations"].append("Consider technical specialist roles")
    elif gd_score > hr_score and gd_score > 75:
        feedback["recommendations"].append("Consider roles requiring strong communication")
    elif hr_score > technical_score and hr_score > 75:
        feedback["recommendations"].append("Consider management and leadership roles")

    return feedback


def generate_pdf_report(report, student):
    """Generate PDF report using ReportLab"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=1  # Center alignment
    )
    story.append(Paragraph("AI-Powered Virtual Interview Report", title_style))
    story.append(Spacer(1, 20))

    # Student Information
    story.append(Paragraph("Student Information", styles['Heading2']))
    student_info = [
        ["Name:", student[2] if student else "N/A"],
        ["Email:", student[1] if student else "N/A"],
        ["CGPA:", str(student[3]) if student else "N/A"],
        ["Graduation Year:", str(student[4]) if student else "N/A"],
        ["Skills:", student[5] if student else "N/A"]
    ]

    student_table = Table(student_info, colWidths=[2 * inch, 4 * inch])
    student_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('BACKGROUND', (1, 0), (1, -1), colors.beige),
    ]))
    story.append(student_table)
    story.append(Spacer(1, 20))

    # Scores Summary
    story.append(Paragraph("Performance Summary", styles['Heading2']))
    scores_data = [
        ["Round", "Score", "Weight", "Weighted Score"],
        ["Aptitude", f"{report[3]:.1f}%", "30%", f"{report[3] * 0.30:.1f}%"],
        ["Technical", f"{report[4]:.1f}%", "40%", f"{report[4] * 0.40:.1f}%"],
        ["Group Discussion", f"{report[5]:.1f}%", "15%", f"{report[5] * 0.15:.1f}%"],
        ["HR Interview", f"{report[6]:.1f}%", "15%", f"{report[6] * 0.15:.1f}%"],
        ["", "", "Total", f"{report[7]:.1f}%"]
    ]

    scores_table = Table(scores_data, colWidths=[1.5 * inch, 1 * inch, 1 * inch, 1.5 * inch])
    scores_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(scores_table)
    story.append(Spacer(1, 20))

    # Feedback
    story.append(Paragraph("Detailed Feedback", styles['Heading2']))

    strengths = json.loads(report[8]) if report[8] else []
    improvements = json.loads(report[9]) if report[9] else []
    recommendations = json.loads(report[10]) if report[10] else []

    if strengths:
        story.append(Paragraph("Strengths:", styles['Heading3']))
        for strength in strengths:
            story.append(Paragraph(f"• {strength}", styles['Normal']))
        story.append(Spacer(1, 10))

    if improvements:
        story.append(Paragraph("Areas for Improvement:", styles['Heading3']))
        for improvement in improvements:
            story.append(Paragraph(f"• {improvement}", styles['Normal']))
        story.append(Spacer(1, 10))

    if recommendations:
        story.append(Paragraph("Recommendations:", styles['Heading3']))
        for recommendation in recommendations:
            story.append(Paragraph(f"• {recommendation}", styles['Normal']))
        story.append(Spacer(1, 10))

    # Footer
    story.append(Spacer(1, 30))
    story.append(Paragraph(f"Report Generated on: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}",
                           styles['Normal']))
    story.append(Paragraph("AI-Powered Virtual Interview System", styles['Normal']))

    doc.build(story)
    buffer.seek(0)
    return buffer


@feedback_bp.route("/individual", methods=["POST"])
def generate_individual_feedback():
    """Generate individual feedback for specific test type"""
    if "email" not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    try:
        data = request.json
        test_type = data.get('test_type', 'aptitude')  # aptitude, technical, gd, hr
        email = session["email"]

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        feedback_data = {}

        if test_type == 'aptitude':
            # Get selected company context
            selected = get_selected_company(email)
            company = selected['name'] if selected else None

            # Get latest aptitude attempt with AI feedback for selected company
            if company:
                c.execute("""
                    SELECT score, correct_answers, total_questions, time_taken, company_name, ai_feedback
                    FROM aptitude_attempts
                    WHERE student_email = ? AND company_name = ?
                    ORDER BY id DESC
                    LIMIT 1
                """, (email, company))
            else:
                c.execute("""
                    SELECT score, correct_answers, total_questions, time_taken, company_name, ai_feedback
                    FROM aptitude_attempts
                    WHERE student_email = ?
                    ORDER BY id DESC
                    LIMIT 1
                """, (email,))

            result = c.fetchone()
            if result:
                score, correct, total, time_taken, company, ai_feedback_json = result

                # Try to parse AI feedback from database
                ai_feedback = None
                if ai_feedback_json:
                    try:
                        ai_feedback = json.loads(ai_feedback_json)
                    except BaseException:
                        pass

                # If no AI feedback, use fallback
                if not ai_feedback:
                    ai_feedback = generate_aptitude_feedback(score, correct, total, time_taken)

                feedback_data = {
                    "test_type": "Aptitude Test",
                    "score": score,
                    "correct_answers": correct,
                    "total_questions": total,
                    "time_taken": time_taken,
                    "company": company,
                    "feedback": ai_feedback  # Use AI feedback from database
                }

        elif test_type == 'technical':
            # Get selected company context
            selected = get_selected_company(email)
            company = selected['name'] if selected else None

            # Get latest technical attempt with detailed analysis for selected company
            if company:
                c.execute("""
                    SELECT ta.score, ta.time_taken, ta.tests_passed, ta.total_tests,
                           GROUP_CONCAT(ts.question_title) as questions,
                           GROUP_CONCAT(ts.code_submitted) as codes,
                           GROUP_CONCAT(ts.language) as languages
                    FROM technical_attempts ta
                    LEFT JOIN technical_solutions ts ON ta.id = ts.attempt_id
                    WHERE ta.student_email = ? AND ta.company_name = ?
                    ORDER BY ta.completed_at DESC
                    LIMIT 1
                """, (email, company))
            else:
                c.execute("""
                    SELECT ta.score, ta.time_taken, ta.tests_passed, ta.total_tests,
                           GROUP_CONCAT(ts.question_title) as questions,
                           GROUP_CONCAT(ts.code_submitted) as codes,
                           GROUP_CONCAT(ts.language) as languages
                    FROM technical_attempts ta
                    LEFT JOIN technical_solutions ts ON ta.id = ts.attempt_id
                    WHERE ta.student_email = ?
                    ORDER BY ta.completed_at DESC
                    LIMIT 1
                """, (email,))

            result = c.fetchone()
            if result:
                score, time_taken, tests_passed, total_tests, questions_str, codes_str, languages_str = result

                # Generate AI-powered feedback for technical round
                ai_feedback = generate_ai_technical_feedback(
                    score, tests_passed, total_tests, time_taken,
                    questions_str, codes_str, languages_str
                )

                feedback_data = {
                    "test_type": "Technical Test",
                    "score": score,
                    "tests_passed": tests_passed,
                    "total_tests": total_tests,
                    "time_taken": time_taken,
                    "feedback": ai_feedback
                }

        elif test_type == 'gd':
            # Get selected company context
            selected = get_selected_company(email)
            company = selected['name'] if selected else None

            # Get latest GD attempt for selected company
            if company:
                c.execute("""
                    SELECT fluency_score, clarity_score, confidence_score, overall_score, transcript
                    FROM gd_results
                    WHERE student_email = ? AND company_name = ?
                    ORDER BY submitted_at DESC
                    LIMIT 1
                """, (email, company))
            else:
                c.execute("""
                    SELECT fluency_score, clarity_score, confidence_score, overall_score, transcript
                    FROM gd_results
                    WHERE student_email = ?
                    ORDER BY submitted_at DESC
                    LIMIT 1
                """, (email,))

            result = c.fetchone()
            if result:
                fluency, clarity, confidence, overall, transcript = result
                feedback_data = {
                    "test_type": "Group Discussion",
                    "fluency_score": fluency,
                    "clarity_score": clarity,
                    "confidence_score": confidence,
                    "overall_score": overall,
                    "company": company,
                    "feedback": generate_gd_feedback(fluency, clarity, confidence, overall)
                }

        elif test_type == 'hr':
            # Get selected company context
            selected = get_selected_company(email)
            company = selected['name'] if selected else None

            # Get latest HR attempt for selected company
            if company:
                c.execute("""
                    SELECT clarity_score, confidence_score, relevance_score, overall_score
                    FROM hr_attempts
                    WHERE student_email = ? AND company_name = ? AND status = 'completed'
                    ORDER BY completed_at DESC
                    LIMIT 1
                """, (email, company))
            else:
                c.execute("""
                    SELECT clarity_score, confidence_score, relevance_score, overall_score
                    FROM hr_attempts
                    WHERE student_email = ? AND status = 'completed'
                    ORDER BY completed_at DESC
                    LIMIT 1
                """, (email,))

            result = c.fetchone()
            if result:
                clarity, confidence, relevance, overall = result
                feedback_data = {
                    "test_type": "HR Interview",
                    "clarity_score": clarity,
                    "relevance_score": relevance,
                    "confidence_score": confidence,
                    "overall_score": overall,
                    "company": company,
                    "feedback": generate_hr_feedback(clarity, relevance, confidence, overall)
                }

        conn.close()

        if not feedback_data:
            return jsonify({"success": False, "error": f"No {test_type} test found"}), 404

        return jsonify({
            "success": True,
            "feedback_data": feedback_data
        })

    except Exception as e:
        print(f"Error generating individual feedback: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@feedback_bp.route("/history", methods=["GET"])
def get_feedback_history():
    """Get feedback report history"""
    if "email" not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    try:
        email = session["email"]

        # Feedback reports table doesn't exist yet, return empty history
        # conn = sqlite3.connect(DB_PATH)
        # c = conn.cursor()
        # c.execute("""
        #     SELECT company_name, aptitude_score, technical_score, gd_score,
        #            hr_score, overall_score, generated_at
        #     FROM feedback_reports
        #     WHERE student_email = ?
        #     ORDER BY generated_at DESC
        # """, (email,))

        history = []  # Return empty history for now
        # for row in c.fetchall():
        #     history.append({
        #         "company": row[0],
        #         "aptitude_score": row[1],
        #         "technical_score": row[2],
        #         "gd_score": row[3],
        #         "hr_score": row[4],
        #         "overall_score": row[5],
        #         "generated_at": row[6]
        #     })

        # conn.close()

        return jsonify({
            "success": True,
            "history": history
        })

    except Exception as e:
        print(f"Error getting feedback history: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
