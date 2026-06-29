"""
Simulation Performance Tracking Module
Tracks all simulation completions, performance data, and user engagement
Ensures 90%+ completion rate tracking and real-world scenario feedback
"""

import sqlite3
import json
from typing import Dict, Any
from datetime import datetime
import os

DB_PATH = os.environ.get('SIMULATION_DB_PATH', 'simulations.db')


class SimulationTracker:
    """Track performance and engagement across all simulation types"""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_tracking_tables()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tracking_tables(self):
        """Initialize comprehensive tracking tables"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS simulation_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                session_id TEXT UNIQUE NOT NULL,
                simulation_type TEXT NOT NULL,
                company_name TEXT,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                status TEXT DEFAULT 'in_progress',
                duration_seconds INTEGER,
                completion_percentage REAL DEFAULT 0.0,
                performance_score REAL DEFAULT 0.0,
                performance_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS aptitude_test_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                email TEXT NOT NULL,
                company_id INTEGER,
                total_questions INTEGER,
                answered_questions INTEGER,
                correct_answers INTEGER,
                incorrect_answers INTEGER,
                skipped_questions INTEGER,
                time_taken_seconds INTEGER,
                score_percentage REAL,
                difficulty_level TEXT,
                category_performance TEXT,
                completed BOOLEAN DEFAULT 0,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY(session_id) REFERENCES simulation_sessions(session_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gd_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                email TEXT NOT NULL,
                topic TEXT,
                participant_role TEXT,
                total_turns INTEGER DEFAULT 0,
                speaking_time_seconds INTEGER DEFAULT 0,
                clarity_score REAL DEFAULT 0.0,
                relevance_score REAL DEFAULT 0.0,
                teamwork_score REAL DEFAULT 0.0,
                leadership_score REAL DEFAULT 0.0,
                overall_score REAL DEFAULT 0.0,
                performance_metrics TEXT,
                completed BOOLEAN DEFAULT 0,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY(session_id) REFERENCES simulation_sessions(session_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hr_interview_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                email TEXT NOT NULL,
                company_name TEXT,
                total_questions INTEGER DEFAULT 0,
                questions_answered INTEGER DEFAULT 0,
                avg_response_time_seconds REAL DEFAULT 0.0,
                content_richness_score REAL DEFAULT 0.0,
                clarity_score REAL DEFAULT 0.0,
                problem_solving_score REAL DEFAULT 0.0,
                honesty_score REAL DEFAULT 0.0,
                overall_score REAL DEFAULT 0.0,
                performance_metrics TEXT,
                completed BOOLEAN DEFAULT 0,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY(session_id) REFERENCES simulation_sessions(session_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS technical_test_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                email TEXT NOT NULL,
                company_name TEXT,
                total_problems INTEGER DEFAULT 0,
                problems_attempted INTEGER DEFAULT 0,
                problems_solved INTEGER DEFAULT 0,
                test_cases_passed INTEGER DEFAULT 0,
                total_test_cases INTEGER DEFAULT 0,
                avg_time_per_problem REAL DEFAULT 0.0,
                code_quality_score REAL DEFAULT 0.0,
                efficiency_score REAL DEFAULT 0.0,
                overall_score REAL DEFAULT 0.0,
                performance_metrics TEXT,
                completed BOOLEAN DEFAULT 0,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY(session_id) REFERENCES simulation_sessions(session_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS simulation_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                email TEXT NOT NULL,
                simulation_type TEXT NOT NULL,
                realism_rating INTEGER,
                engagement_rating INTEGER,
                difficulty_rating INTEGER,
                usefulness_rating INTEGER,
                overall_rating INTEGER,
                feedback_text TEXT,
                improvements_suggested TEXT,
                would_recommend BOOLEAN,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(session_id) REFERENCES simulation_sessions(session_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_simulation_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                total_simulations_started INTEGER DEFAULT 0,
                total_simulations_completed INTEGER DEFAULT 0,
                completion_rate REAL DEFAULT 0.0,
                avg_performance_score REAL DEFAULT 0.0,
                total_time_spent_minutes INTEGER DEFAULT 0,
                aptitude_count INTEGER DEFAULT 0,
                technical_count INTEGER DEFAULT 0,
                gd_count INTEGER DEFAULT 0,
                hr_count INTEGER DEFAULT 0,
                last_simulation_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()

    def start_simulation(self, email: str, session_id: str, simulation_type: str,
                         company_name: str = None) -> bool:
        """Record simulation start"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO simulation_sessions (email, session_id, simulation_type, company_name, status)
                VALUES (?, ?, ?, ?, 'in_progress')
            """, (email, session_id, simulation_type, company_name))

            cursor.execute("""
                INSERT OR IGNORE INTO user_simulation_stats (email)
                VALUES (?)
            """, (email,))

            cursor.execute("""
                UPDATE user_simulation_stats
                SET total_simulations_started = total_simulations_started + 1,
                    last_simulation_at = ?,
                    updated_at = ?
                WHERE email = ?
            """, (datetime.now().isoformat(), datetime.now().isoformat(), email))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error starting simulation: {e}")
            return False

    def complete_simulation(self, session_id: str, performance_data: Dict[str, Any]) -> bool:
        """Mark simulation as completed with performance data"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT started_at, email, simulation_type FROM simulation_sessions
                WHERE session_id = ?
            """, (session_id,))
            session = cursor.fetchone()

            if not session:
                conn.close()
                return False

            started_at = datetime.fromisoformat(session['started_at'])
            duration = (datetime.now() - started_at).total_seconds()

            cursor.execute("""
                UPDATE simulation_sessions
                SET completed_at = ?,
                    status = 'completed',
                    duration_seconds = ?,
                    completion_percentage = 100.0,
                    performance_score = ?,
                    performance_data = ?
                WHERE session_id = ?
            """, (
                datetime.now().isoformat(),
                int(duration),
                performance_data.get('overall_score', 0),
                json.dumps(performance_data),
                session_id
            ))

            cursor.execute("""
                UPDATE user_simulation_stats
                SET total_simulations_completed = total_simulations_completed + 1,
                    total_time_spent_minutes = total_time_spent_minutes + ?,
                    updated_at = ?
                WHERE email = ?
            """, (int(duration / 60), datetime.now().isoformat(), session['email']))

            cursor.execute("""
                SELECT total_simulations_started, total_simulations_completed
                FROM user_simulation_stats
                WHERE email = ?
            """, (session['email'],))

            stats = cursor.fetchone()
            if stats:
                completion_rate = (stats['total_simulations_completed'] / stats['total_simulations_started']) * 100
                cursor.execute("""
                    UPDATE user_simulation_stats
                    SET completion_rate = ?
                    WHERE email = ?
                """, (completion_rate, session['email']))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error completing simulation: {e}")
            return False

    def track_aptitude_test(self, session_id: str, email: str, test_data: Dict[str, Any]) -> bool:
        """Track aptitude test performance"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO aptitude_test_tracking
                (session_id, email, company_id, total_questions, answered_questions,
                 correct_answers, incorrect_answers, skipped_questions, time_taken_seconds,
                 score_percentage, difficulty_level, category_performance, completed, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                email,
                test_data.get('company_id'),
                test_data.get('total_questions', 0),
                test_data.get('answered_questions', 0),
                test_data.get('correct_answers', 0),
                test_data.get('incorrect_answers', 0),
                test_data.get('skipped_questions', 0),
                test_data.get('time_taken_seconds', 0),
                test_data.get('score_percentage', 0),
                test_data.get('difficulty_level', 'Medium'),
                json.dumps(test_data.get('category_performance', {})),
                test_data.get('completed', True),
                datetime.now().isoformat() if test_data.get('completed') else None
            ))

            cursor.execute("""
                UPDATE user_simulation_stats
                SET aptitude_count = aptitude_count + 1
                WHERE email = ?
            """, (email,))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error tracking aptitude test: {e}")
            return False

    def track_gd_session(self, session_id: str, email: str, gd_data: Dict[str, Any]) -> bool:
        """Track group discussion performance"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO gd_tracking
                (session_id, email, topic, participant_role, total_turns, speaking_time_seconds,
                 clarity_score, relevance_score, teamwork_score, leadership_score, overall_score,
                 performance_metrics, completed, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                email,
                gd_data.get('topic'),
                gd_data.get('participant_role', 'participant'),
                gd_data.get('total_turns', 0),
                gd_data.get('speaking_time_seconds', 0),
                gd_data.get('clarity_score', 0),
                gd_data.get('relevance_score', 0),
                gd_data.get('teamwork_score', 0),
                gd_data.get('leadership_score', 0),
                gd_data.get('overall_score', 0),
                json.dumps(gd_data.get('performance_metrics', {})),
                gd_data.get('completed', True),
                datetime.now().isoformat() if gd_data.get('completed') else None
            ))

            cursor.execute("""
                UPDATE user_simulation_stats
                SET gd_count = gd_count + 1
                WHERE email = ?
            """, (email,))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error tracking GD: {e}")
            return False

    def track_hr_interview(self, session_id: str, email: str, hr_data: Dict[str, Any]) -> bool:
        """Track HR interview performance"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO hr_interview_tracking
                (session_id, email, company_name, total_questions, questions_answered,
                 avg_response_time_seconds, content_richness_score, clarity_score,
                 problem_solving_score, honesty_score, overall_score, performance_metrics,
                 completed, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                email,
                hr_data.get('company_name'),
                hr_data.get('total_questions', 0),
                hr_data.get('questions_answered', 0),
                hr_data.get('avg_response_time_seconds', 0),
                hr_data.get('content_richness_score', 0),
                hr_data.get('clarity_score', 0),
                hr_data.get('problem_solving_score', 0),
                hr_data.get('honesty_score', 0),
                hr_data.get('overall_score', 0),
                json.dumps(hr_data.get('performance_metrics', {})),
                hr_data.get('completed', True),
                datetime.now().isoformat() if hr_data.get('completed') else None
            ))

            cursor.execute("""
                UPDATE user_simulation_stats
                SET hr_count = hr_count + 1
                WHERE email = ?
            """, (email,))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error tracking HR interview: {e}")
            return False

    def track_technical_test(self, session_id: str, email: str, tech_data: Dict[str, Any]) -> bool:
        """Track technical test performance"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO technical_test_tracking
                (session_id, email, company_name, total_problems, problems_attempted,
                 problems_solved, test_cases_passed, total_test_cases, avg_time_per_problem,
                 code_quality_score, efficiency_score, overall_score, performance_metrics,
                 completed, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                email,
                tech_data.get('company_name'),
                tech_data.get('total_problems', 0),
                tech_data.get('problems_attempted', 0),
                tech_data.get('problems_solved', 0),
                tech_data.get('test_cases_passed', 0),
                tech_data.get('total_test_cases', 0),
                tech_data.get('avg_time_per_problem', 0),
                tech_data.get('code_quality_score', 0),
                tech_data.get('efficiency_score', 0),
                tech_data.get('overall_score', 0),
                json.dumps(tech_data.get('performance_metrics', {})),
                tech_data.get('completed', True),
                datetime.now().isoformat() if tech_data.get('completed') else None
            ))

            cursor.execute("""
                UPDATE user_simulation_stats
                SET technical_count = technical_count + 1
                WHERE email = ?
            """, (email,))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error tracking technical test: {e}")
            return False

    def save_simulation_feedback(self, session_id: str, email: str,
                                 simulation_type: str, feedback_data: Dict[str, Any]) -> bool:
        """Save user feedback about simulation realism and engagement"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO simulation_feedback
                (session_id, email, simulation_type, realism_rating, engagement_rating,
                 difficulty_rating, usefulness_rating, overall_rating, feedback_text,
                 improvements_suggested, would_recommend)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                email,
                simulation_type,
                feedback_data.get('realism_rating'),
                feedback_data.get('engagement_rating'),
                feedback_data.get('difficulty_rating'),
                feedback_data.get('usefulness_rating'),
                feedback_data.get('overall_rating'),
                feedback_data.get('feedback_text', ''),
                feedback_data.get('improvements_suggested', ''),
                feedback_data.get('would_recommend', True)
            ))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error saving feedback: {e}")
            return False

    def get_user_stats(self, email: str) -> Dict[str, Any]:
        """Get comprehensive user simulation statistics"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM user_simulation_stats WHERE email = ?", (email,))
            stats_row = cursor.fetchone()

            if not stats_row:
                conn.close()
                return {}

            stats = dict(stats_row)

            cursor.execute("""
                SELECT
                    AVG(realism_rating) as avg_realism,
                    AVG(engagement_rating) as avg_engagement,
                    AVG(overall_rating) as avg_overall,
                    COUNT(*) as feedback_count
                FROM simulation_feedback
                WHERE email = ?
            """, (email,))

            feedback_stats = cursor.fetchone()
            if feedback_stats:
                stats['avg_realism_rating'] = round(feedback_stats['avg_realism'] or 0, 2)
                stats['avg_engagement_rating'] = round(feedback_stats['avg_engagement'] or 0, 2)
                stats['avg_overall_rating'] = round(feedback_stats['avg_overall'] or 0, 2)
                stats['feedback_count'] = feedback_stats['feedback_count']

            conn.close()
            return stats
        except Exception as e:
            print(f"Error getting user stats: {e}")
            return {}

    def get_global_completion_metrics(self) -> Dict[str, Any]:
        """Get platform-wide completion metrics"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    COUNT(DISTINCT email) as total_users,
                    AVG(completion_rate) as avg_completion_rate,
                    SUM(total_simulations_completed) as total_completions,
                    SUM(total_simulations_started) as total_started
                FROM user_simulation_stats
            """)

            metrics = dict(cursor.fetchone())

            cursor.execute("""
                SELECT
                    AVG(realism_rating) as avg_realism,
                    AVG(engagement_rating) as avg_engagement,
                    AVG(overall_rating) as avg_overall
                FROM simulation_feedback
            """)

            feedback = cursor.fetchone()
            if feedback:
                metrics['platform_avg_realism'] = round(feedback['avg_realism'] or 0, 2)
                metrics['platform_avg_engagement'] = round(feedback['avg_engagement'] or 0, 2)
                metrics['platform_avg_overall'] = round(feedback['avg_overall'] or 0, 2)

            conn.close()
            return metrics
        except Exception as e:
            print(f"Error getting global metrics: {e}")
            return {}


simulation_tracker = SimulationTracker()
