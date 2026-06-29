"""
AI-Powered Feedback Generation Engine
Generates personalized feedback within 5 minutes post-completion
Analyzes responses and behaviors with 85%+ positive user feedback target
"""

import os
import json
import requests
from typing import Dict, Any, Optional
from datetime import datetime
import sqlite3
import time

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
DB_PATH = os.environ.get('FEEDBACK_DB_PATH', 'simulations.db')


class AIFeedbackEngine:
    """Generate AI-powered personalized feedback for all simulation stages"""

    def __init__(self, api_key: str = OPENAI_API_KEY, db_path: str = DB_PATH):
        self.api_key = api_key
        self.db_path = db_path
        self._init_feedback_tables()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_feedback_tables(self):
        """Initialize feedback tracking tables"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_feedback_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                email TEXT NOT NULL,
                simulation_type TEXT NOT NULL,
                feedback_generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                generation_time_seconds REAL,
                feedback_content TEXT NOT NULL,
                strengths TEXT,
                weaknesses TEXT,
                recommendations TEXT,
                action_items TEXT,
                performance_summary TEXT,
                user_rating INTEGER,
                usefulness_rating INTEGER,
                clarity_rating INTEGER,
                user_feedback_text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feedback_quality_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                total_feedbacks_received INTEGER DEFAULT 0,
                avg_user_rating REAL DEFAULT 0.0,
                avg_usefulness_rating REAL DEFAULT 0.0,
                avg_clarity_rating REAL DEFAULT 0.0,
                positive_feedback_count INTEGER DEFAULT 0,
                positive_feedback_percentage REAL DEFAULT 0.0,
                avg_generation_time_seconds REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()

    def generate_aptitude_test_feedback(self, session_id: str, email: str,
                                        test_results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate AI feedback for aptitude test within 5 minutes"""
        start_time = time.time()

        try:
            score = test_results.get('score_percentage', 0)
            correct = test_results.get('correct_answers', 0)
            total = test_results.get('total_questions', 1)
            category_perf = test_results.get('category_performance', {})

            prompt = f"""You are an expert aptitude test coach. Analyze this student's performance and provide personalized, actionable feedback.

Performance Data:
- Score: {score:.1f}%
- Questions Correct: {correct}/{total}
- Category Performance: {json.dumps(category_perf, indent=2)}

Provide comprehensive feedback in JSON format:
{{
    "performance_summary": "2-3 sentences summarizing overall performance",
    "strengths": ["List 3-5 specific strengths demonstrated"],
    "areas_for_improvement": ["List 3-5 specific areas to improve"],
    "category_insights": {{
        "category_name": "Specific insight and recommendation"
    }},
    "action_items": ["5-7 immediate actionable steps to improve"],
    "study_recommendations": ["Specific resources or topics to study"],
    "motivation_message": "Encouraging message to keep student motivated",
    "next_steps": "What the student should do next",
    "estimated_improvement_timeline": "Realistic timeline to see improvement"
}}

Be specific, encouraging, and actionable. Focus on growth mindset."""

            feedback_data = self._call_openai_api(prompt, max_tokens=1200)

            if not feedback_data:
                feedback_data = self._generate_fallback_aptitude_feedback(test_results)

            generation_time = time.time() - start_time

            self._save_feedback_record(
                session_id, email, 'aptitude_test',
                feedback_data, generation_time
            )

            return {
                **feedback_data,
                'generation_time_seconds': round(generation_time, 2),
                'feedback_delivered_within_sla': generation_time < 300
            }

        except Exception as e:
            print(f"Error generating aptitude feedback: {e}")
            return self._generate_fallback_aptitude_feedback(test_results)

    def generate_gd_feedback(self, session_id: str, email: str,
                             gd_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate AI feedback for group discussion within 5 minutes"""
        start_time = time.time()

        try:
            topic = gd_data.get('topic', 'Unknown Topic')
            transcript = gd_data.get('transcript', '')
            scores = gd_data.get('scores', {})

            prompt = f"""You are an expert group discussion evaluator. Analyze this participant's performance and provide detailed feedback.

Discussion Topic: {topic}

Participant Transcript:
{transcript[:1500]}

Performance Scores:
- Clarity: {scores.get('clarity_score', 0)}/5
- Relevance: {scores.get('relevance_score', 0)}/5
- Teamwork: {scores.get('teamwork_score', 0)}/5
- Leadership: {scores.get('leadership_score', 0)}/5

Provide comprehensive feedback in JSON format:
{{
    "performance_summary": "Overall assessment of GD performance",
    "strengths": ["3-5 specific strengths shown in the discussion"],
    "areas_for_improvement": ["3-5 specific areas to work on"],
    "communication_analysis": "Assessment of communication style and effectiveness",
    "content_quality": "Evaluation of ideas and arguments presented",
    "team_dynamics": "How well they collaborated and led",
    "action_items": ["5 specific things to practice for next GD"],
    "improvement_tips": ["Practical tips to enhance GD skills"],
    "motivation_message": "Encouraging message"
}}

Be specific and constructive."""

            feedback_data = self._call_openai_api(prompt, max_tokens=1200)

            if not feedback_data:
                feedback_data = self._generate_fallback_gd_feedback(gd_data)

            generation_time = time.time() - start_time

            self._save_feedback_record(
                session_id, email, 'group_discussion',
                feedback_data, generation_time
            )

            return {
                **feedback_data,
                'generation_time_seconds': round(generation_time, 2),
                'feedback_delivered_within_sla': generation_time < 300
            }

        except Exception as e:
            print(f"Error generating GD feedback: {e}")
            return self._generate_fallback_gd_feedback(gd_data)

    def generate_hr_interview_feedback(self, session_id: str, email: str,
                                       interview_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate AI feedback for HR interview within 5 minutes"""
        start_time = time.time()

        try:
            answers = interview_data.get('answers', [])
            overall_scores = interview_data.get('overall_scores', {})

            qa_summary = []
            for i, qa in enumerate(answers[:5], 1):
                qa_summary.append(f"Q{i}: {qa.get('question', '')[:100]}...")
                qa_summary.append(f"A{i}: {qa.get('answer', '')[:150]}...")

            prompt = f"""You are an expert HR interview coach. Analyze this candidate's interview performance and provide actionable feedback.

Overall Scores:
{json.dumps(overall_scores, indent=2)}

Sample Q&A:
{chr(10).join(qa_summary)}

Total Questions: {len(answers)}

Provide comprehensive feedback in JSON format:
{{
    "performance_summary": "Overall interview assessment",
    "strengths": ["4-6 specific strengths demonstrated"],
    "areas_for_improvement": ["4-6 specific areas to develop"],
    "answer_quality_analysis": "Assessment of response quality",
    "communication_effectiveness": "Evaluation of communication skills",
    "behavioral_insights": "Insights from behavioral responses",
    "technical_competency": "Assessment of technical knowledge shared",
    "action_items": ["6-8 specific practice recommendations"],
    "interview_tips": ["Practical tips for next interview"],
    "recommended_role_fit": "Types of roles that would be good fit",
    "motivation_message": "Encouraging and constructive message"
}}

Be thorough, specific, and constructive."""

            feedback_data = self._call_openai_api(prompt, max_tokens=1500)

            if not feedback_data:
                feedback_data = self._generate_fallback_hr_feedback(interview_data)

            generation_time = time.time() - start_time

            self._save_feedback_record(
                session_id, email, 'hr_interview',
                feedback_data, generation_time
            )

            return {
                **feedback_data,
                'generation_time_seconds': round(generation_time, 2),
                'feedback_delivered_within_sla': generation_time < 300
            }

        except Exception as e:
            print(f"Error generating HR feedback: {e}")
            return self._generate_fallback_hr_feedback(interview_data)

    def generate_technical_test_feedback(self, session_id: str, email: str,
                                         tech_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate AI feedback for technical test within 5 minutes"""
        start_time = time.time()

        try:
            score = tech_data.get('score_percentage', 0)
            problems_solved = tech_data.get('problems_solved', 0)
            total_problems = tech_data.get('total_problems', 1)
            test_cases_passed = tech_data.get('test_cases_passed', 0)
            total_test_cases = tech_data.get('total_test_cases', 1)

            prompt = f"""You are an expert technical interview coach. Analyze this candidate's coding performance and provide detailed feedback.

Performance Metrics:
- Overall Score: {score:.1f}%
- Problems Solved: {problems_solved}/{total_problems}
- Test Cases Passed: {test_cases_passed}/{total_test_cases}
- Code Quality Score: {tech_data.get('code_quality_score', 0)}/5
- Efficiency Score: {tech_data.get('efficiency_score', 0)}/5

Provide comprehensive feedback in JSON format:
{{
    "performance_summary": "Overall technical assessment",
    "strengths": ["4-6 coding strengths demonstrated"],
    "areas_for_improvement": ["4-6 technical areas to improve"],
    "code_quality_analysis": "Assessment of code quality and style",
    "problem_solving_approach": "Evaluation of problem-solving methodology",
    "efficiency_insights": "Analysis of algorithmic efficiency",
    "debugging_skills": "Assessment of debugging approach",
    "action_items": ["6-8 specific practice recommendations"],
    "study_topics": ["Topics and concepts to study"],
    "recommended_resources": ["Specific resources to improve"],
    "practice_problems": "Types of problems to practice",
    "motivation_message": "Encouraging technical growth message"
}}

Be specific about code improvements and learning paths."""

            feedback_data = self._call_openai_api(prompt, max_tokens=1500)

            if not feedback_data:
                feedback_data = self._generate_fallback_technical_feedback(tech_data)

            generation_time = time.time() - start_time

            self._save_feedback_record(
                session_id, email, 'technical_test',
                feedback_data, generation_time
            )

            return {
                **feedback_data,
                'generation_time_seconds': round(generation_time, 2),
                'feedback_delivered_within_sla': generation_time < 300
            }

        except Exception as e:
            print(f"Error generating technical feedback: {e}")
            return self._generate_fallback_technical_feedback(tech_data)

    def _call_openai_api(self, prompt: str, max_tokens: int = 1000) -> Optional[Dict[str, Any]]:
        """Call OpenAI API to generate feedback"""
        if not self.api_key:
            return None

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json={
                    "model": "gpt-4",
                    "messages": [
                        {"role": "system", "content": "You are an expert interview coach and evaluator. Provide detailed, constructive, and personalized feedback."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.7,
                    "max_tokens": max_tokens
                },
                timeout=30
            )

            if response.status_code == 200:
                result_text = response.json()["choices"][0]["message"]["content"]
                result_text = result_text.strip()

                if result_text.startswith("```json"):
                    result_text = result_text[7:]
                if result_text.startswith("```"):
                    result_text = result_text[3:]
                if result_text.endswith("```"):
                    result_text = result_text[:-3]
                result_text = result_text.strip()

                return json.loads(result_text)
            else:
                print(f"OpenAI API error: {response.status_code}")
                return None

        except Exception as e:
            print(f"Error calling OpenAI API: {e}")
            return None

    def _save_feedback_record(self, session_id: str, email: str, simulation_type: str,
                              feedback_data: Dict[str, Any], generation_time: float):
        """Save feedback record to database"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO ai_feedback_records
                (session_id, email, simulation_type, generation_time_seconds,
                 feedback_content, strengths, weaknesses, recommendations,
                 action_items, performance_summary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                email,
                simulation_type,
                generation_time,
                json.dumps(feedback_data),
                json.dumps(feedback_data.get('strengths', [])),
                json.dumps(feedback_data.get('areas_for_improvement', [])),
                json.dumps(feedback_data.get('action_items', [])),
                json.dumps(feedback_data.get('action_items', [])),
                feedback_data.get('performance_summary', '')
            ))

            cursor.execute("""
                INSERT OR IGNORE INTO feedback_quality_metrics (email)
                VALUES (?)
            """, (email,))

            cursor.execute("""
                UPDATE feedback_quality_metrics
                SET total_feedbacks_received = total_feedbacks_received + 1,
                    avg_generation_time_seconds = (
                        (avg_generation_time_seconds * total_feedbacks_received + ?) /
                        (total_feedbacks_received + 1)
                    ),
                    updated_at = ?
                WHERE email = ?
            """, (generation_time, datetime.now().isoformat(), email))

            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error saving feedback record: {e}")

    def record_feedback_rating(self, session_id: str, email: str,
                               ratings: Dict[str, int]) -> bool:
        """Record user ratings for the AI-generated feedback"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE ai_feedback_records
                SET user_rating = ?,
                    usefulness_rating = ?,
                    clarity_rating = ?,
                    user_feedback_text = ?
                WHERE session_id = ? AND email = ?
            """, (
                ratings.get('overall_rating'),
                ratings.get('usefulness_rating'),
                ratings.get('clarity_rating'),
                ratings.get('feedback_text', ''),
                session_id,
                email
            ))

            positive_threshold = 4

            cursor.execute("""
                SELECT
                    AVG(user_rating) as avg_rating,
                    AVG(usefulness_rating) as avg_usefulness,
                    AVG(clarity_rating) as avg_clarity,
                    SUM(CASE WHEN user_rating >= ? THEN 1 ELSE 0 END) as positive_count,
                    COUNT(*) as total_count
                FROM ai_feedback_records
                WHERE email = ? AND user_rating IS NOT NULL
            """, (positive_threshold, email))

            stats = cursor.fetchone()

            if stats:
                positive_percentage = (
                    stats['positive_count'] /
                    stats['total_count'] *
                    100) if stats['total_count'] > 0 else 0

                cursor.execute("""
                    UPDATE feedback_quality_metrics
                    SET avg_user_rating = ?,
                        avg_usefulness_rating = ?,
                        avg_clarity_rating = ?,
                        positive_feedback_count = ?,
                        positive_feedback_percentage = ?,
                        updated_at = ?
                    WHERE email = ?
                """, (
                    stats['avg_rating'],
                    stats['avg_usefulness'],
                    stats['avg_clarity'],
                    stats['positive_count'],
                    positive_percentage,
                    datetime.now().isoformat(),
                    email
                ))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error recording feedback rating: {e}")
            return False

    def get_feedback_quality_stats(self, email: str = None) -> Dict[str, Any]:
        """Get feedback quality statistics"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            if email:
                cursor.execute("""
                    SELECT * FROM feedback_quality_metrics WHERE email = ?
                """, (email,))
                stats = cursor.fetchone()
                result = dict(stats) if stats else {}
            else:
                cursor.execute("""
                    SELECT
                        AVG(avg_user_rating) as platform_avg_rating,
                        AVG(avg_usefulness_rating) as platform_avg_usefulness,
                        AVG(avg_clarity_rating) as platform_avg_clarity,
                        AVG(positive_feedback_percentage) as platform_positive_percentage,
                        AVG(avg_generation_time_seconds) as platform_avg_gen_time,
                        SUM(total_feedbacks_received) as total_feedbacks_generated
                    FROM feedback_quality_metrics
                """)
                stats = cursor.fetchone()
                result = dict(stats) if stats else {}

            conn.close()
            return result
        except Exception as e:
            print(f"Error getting feedback stats: {e}")
            return {}

    def _generate_fallback_aptitude_feedback(self, test_results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate fallback feedback when AI is unavailable"""
        score = test_results.get('score_percentage', 0)

        if score >= 80:
            summary = f"Excellent performance! You scored {score:.1f}%, showing strong aptitude."
        elif score >= 60:
            summary = f"Good effort! You scored {score:.1f}%. Focused practice will help you excel."
        else:
            summary = f"You scored {score:.1f}%. With dedicated practice, you'll see significant improvement."

        return {
            "performance_summary": summary,
            "strengths": ["Completed the test", "Showed determination"],
            "areas_for_improvement": ["Review incorrect answers", "Practice weak areas"],
            "action_items": ["Review mistakes", "Practice daily", "Take more mock tests"],
            "motivation_message": "Keep practicing and you'll improve!",
            "generation_time_seconds": 0.1
        }

    def _generate_fallback_gd_feedback(self, gd_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate fallback GD feedback"""
        return {
            "performance_summary": "You participated in the group discussion",
            "strengths": ["Active participation", "Engagement with topic"],
            "areas_for_improvement": ["Improve clarity", "Enhance content quality"],
            "action_items": ["Practice speaking clearly", "Research topics", "Listen actively"],
            "motivation_message": "Keep practicing GD skills!",
            "generation_time_seconds": 0.1
        }

    def _generate_fallback_hr_feedback(self, interview_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate fallback HR interview feedback"""
        return {
            "performance_summary": "You completed the HR interview",
            "strengths": ["Answered all questions", "Professional demeanor"],
            "areas_for_improvement": ["Provide more examples", "Improve answer structure"],
            "action_items": ["Use STAR method", "Practice common questions", "Research company"],
            "motivation_message": "Keep improving your interview skills!",
            "generation_time_seconds": 0.1
        }

    def _generate_fallback_technical_feedback(self, tech_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate fallback technical feedback"""
        return {
            "performance_summary": "You completed the technical assessment",
            "strengths": ["Attempted problems", "Showed problem-solving approach"],
            "areas_for_improvement": ["Improve algorithmic efficiency", "Practice more problems"],
            "action_items": ["Study algorithms", "Practice on coding platforms", "Review solutions"],
            "motivation_message": "Keep coding and learning!",
            "generation_time_seconds": 0.1
        }


ai_feedback_engine = AIFeedbackEngine()
