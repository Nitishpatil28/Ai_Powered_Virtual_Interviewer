"""
Database setup and connection for GD and HR simulations
"""

import sqlite3
import os
from typing import List, Dict, Any, Optional
import json

# Legacy functions for Flask app compatibility


def add_user(name: str, email: str, password: str = None, provider: str = "local") -> bool:
    """Add a new user to the database (legacy function for Flask app)"""
    try:
        conn = sqlite3.connect("users.db")
        c = conn.cursor()
        c.execute("""
            INSERT INTO users (name, email, password, provider)
            VALUES (?, ?, ?, ?)
        """, (name, email, password, provider))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error adding user: {e}")
        return False


def get_user(email: str) -> Optional[Dict[str, Any]]:
    """Get user by email (legacy function for Flask app)"""
    try:
        conn = sqlite3.connect("users.db")
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE email = ?", (email,))
        row = c.fetchone()
        conn.close()

        if row:
            columns = ['id', 'name', 'email', 'password', 'provider', 'created_at']
            return dict(zip(columns, row))
        return None
    except Exception as e:
        print(f"Error getting user: {e}")
        return None


def update_user_password(email: str, hashed_password: str) -> bool:
    """Update user password (legacy function for Flask app)"""
    try:
        conn = sqlite3.connect("users.db")
        c = conn.cursor()
        c.execute("UPDATE users SET password = ? WHERE email = ?", (hashed_password, email))
        conn.commit()
        conn.close()

        return c.rowcount > 0
    except Exception as e:
        print(f"Error updating password: {e}")
        return False


def get_student(email: str) -> Optional[Dict[str, Any]]:
    """Get student by email"""
    try:
        conn = sqlite3.connect("users.db")
        c = conn.cursor()
        c.execute("SELECT * FROM students WHERE email = ?", (email,))
        row = c.fetchone()
        conn.close()

        if row:
            columns = ['id', 'email', 'name', 'cgpa', 'graduation_year', 'skills', 'selected_company_id', 'selected_company_name', 'profile_pic', 'created_at']
            return dict(zip(columns, row))
        return None
    except Exception as e:
        print(f"Error getting student: {e}")
        return None


class DatabaseManager:
    """Manages SQLite database operations for GD and HR sessions"""

    def __init__(self, db_path: str = None):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.db_path = db_path or os.path.join(base_dir, "simulations.db")
        self.init_database()

    def get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory and foreign keys enabled"""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init_database(self):
        """Initialize database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # GD Sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gd_sessions (
                id TEXT PRIMARY KEY,
                topic TEXT NOT NULL,
                participants TEXT NOT NULL,  -- JSON array of participant names
                current_turn INTEGER DEFAULT 0,
                transcripts TEXT DEFAULT '[]',  -- JSON array of turn transcripts
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # GD Turns table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gd_turns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                participant TEXT NOT NULL,
                transcript TEXT NOT NULL,
                duration REAL NOT NULL,
                scores TEXT NOT NULL,  -- JSON object with scores
                feedback TEXT,
                turn_number INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(session_id) REFERENCES gd_sessions(id)
            )
        """)

        # HR Sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hr_sessions (
                id TEXT PRIMARY KEY,
                candidate_name TEXT NOT NULL,
                skills TEXT NOT NULL,  -- JSON array of skills
                questions_asked TEXT DEFAULT '[]',  -- JSON array of questions
                answers TEXT DEFAULT '[]',  -- JSON array of answers with scores
                current_question_index INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # HR Answers table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hr_answers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                scores TEXT NOT NULL,  -- JSON object with scores
                feedback TEXT,
                question_type TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(session_id) REFERENCES hr_sessions(id)
            )
        """)

        conn.commit()
        conn.close()
        print("Database initialized successfully!")

    # GD Operations
    def create_gd_session(self, session_id: str, topic: str, participants: List[str]) -> bool:
        """Create a new GD session"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO gd_sessions (id, topic, participants, status)
                VALUES (?, ?, ?, 'active')
            """, (session_id, topic, json.dumps(participants)))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error creating GD session: {e}")
            return False

    def save_gd_turn(self, session_id: str, participant: str, transcript: str,
                     duration: float, scores: Dict[str, float], feedback: str,
                     turn_number: int) -> bool:
        """Save a GD turn"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO gd_turns (session_id, participant, transcript, duration,
                                    scores, feedback, turn_number)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (session_id, participant, transcript, duration, json.dumps(scores),
                  feedback, turn_number))

            # Update session timestamp
            cursor.execute("""
                UPDATE gd_sessions SET updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (session_id,))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error saving GD turn: {e}")
            return False

    def get_gd_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get GD session data"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM gd_sessions WHERE id = ?
            """, (session_id,))
            row = cursor.fetchone()
            conn.close()

            if row:
                return dict(row)
            return None
        except Exception as e:
            print(f"Error getting GD session: {e}")
            return None

    def get_gd_turns(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all turns for a GD session"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM gd_turns WHERE session_id = ?
                ORDER BY turn_number
            """, (session_id,))
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]
        except Exception as e:
            print(f"Error getting GD turns: {e}")
            return []

    def end_gd_session(self, session_id: str) -> bool:
        """Mark GD session as completed"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE gd_sessions SET status = 'completed',
                updated_at = CURRENT_TIMESTAMP WHERE id = ?
            """, (session_id,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error ending GD session: {e}")
            return False

    # HR Operations
    def create_hr_session(self, session_id: str, candidate_name: str, skills: List[str]) -> bool:
        """Create a new HR session"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO hr_sessions (id, candidate_name, skills, status)
                VALUES (?, ?, ?, 'active')
            """, (session_id, candidate_name, json.dumps(skills)))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error creating HR session: {e}")
            return False

    def save_hr_answer(self, session_id: str, question: str, answer: str,
                       scores: Dict[str, float], feedback: str, question_type: str) -> bool:
        """Save an HR answer"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO hr_answers (session_id, question, answer, scores,
                                      feedback, question_type)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (session_id, question, answer, json.dumps(scores), feedback, question_type))

            # Update session
            cursor.execute("""
                UPDATE hr_sessions SET
                current_question_index = current_question_index + 1,
                updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (session_id,))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error saving HR answer: {e}")
            return False

    def get_hr_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get HR session data"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM hr_sessions WHERE id = ?
            """, (session_id,))
            row = cursor.fetchone()
            conn.close()

            if row:
                return dict(row)
            return None
        except Exception as e:
            print(f"Error getting HR session: {e}")
            return None

    def get_hr_answers(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all answers for an HR session"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM hr_answers WHERE session_id = ?
                ORDER BY created_at
            """, (session_id,))
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]
        except Exception as e:
            print(f"Error getting HR answers: {e}")
            return []

    def end_hr_session(self, session_id: str) -> bool:
        """Mark HR session as completed"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE hr_sessions SET status = 'completed',
                updated_at = CURRENT_TIMESTAMP WHERE id = ?
            """, (session_id,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error ending HR session: {e}")
            return False

# Legacy functions for Flask app compatibility


def get_connection():
    """Legacy function for Flask app compatibility"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    users_db_path = os.path.join(base_dir, "users.db")
    conn = sqlite3.connect(users_db_path, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Legacy database initialization for Flask app"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    users_db_path = os.path.join(base_dir, "users.db")
    conn = sqlite3.connect(users_db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    c = conn.cursor()

    # Create users table
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT,
            provider TEXT DEFAULT 'local',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create students table
    c.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            name TEXT,
            cgpa REAL DEFAULT 0.0,
            graduation_year INTEGER DEFAULT 2025,
            skills TEXT,
            selected_company_id INTEGER,
            selected_company_name TEXT,
            profile_pic TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(selected_company_id) REFERENCES companies(id)
        )
    """)

    # Create companies table
    c.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            min_cgpa REAL DEFAULT 0.0,
            required_skills TEXT,
            graduation_year INTEGER DEFAULT 2025,
            role TEXT,
            package_offered TEXT,
            location TEXT,
            industry TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create question_usage_events table for analytics
    c.execute("""
        CREATE TABLE IF NOT EXISTS question_usage_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_email TEXT NOT NULL,
            company_name TEXT NOT NULL,
            question_type TEXT NOT NULL,
            question_id INTEGER NOT NULL,
            event TEXT NOT NULL,
            score REAL,
            time_spent INTEGER,
            correct INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create gd_results table for GD performance tracking
    c.execute("""
        CREATE TABLE IF NOT EXISTS gd_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_email TEXT NOT NULL,
            company_name TEXT NOT NULL,
            topic_id INTEGER NOT NULL,
            transcript TEXT,
            fluency_score REAL,
            clarity_score REAL,
            confidence_score REAL,
            grammar_score REAL,
            content_score REAL,
            teamwork_score REAL,
            leadership_score REAL,
            overall_score REAL,
            feedback TEXT,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
    print("Database initialized successfully!")

# Global database instance


def get_all_companies() -> List[Dict[str, Any]]:
    conn = sqlite3.connect("users.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM companies ORDER BY name")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def update_student(current_email: str, **fields) -> bool:
    if not fields:
        return False
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO students (email) VALUES (?)", (current_email,))
    cursor.execute("PRAGMA table_info(students)")
    valid_columns = {col[1] for col in cursor.fetchall()}
    updates = []
    values = []
    for key, value in fields.items():
        if key in valid_columns:
            updates.append(f"{key} = ?")
            values.append(value)
    if not updates:
        conn.close()
        return False
    values.append(current_email)
    cursor.execute(f"UPDATE students SET {', '.join(updates)} WHERE email = ?", values)
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated


def get_resume_by_email(email: str) -> Optional[str]:
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(students)")
    columns = {col[1] for col in cursor.fetchall()}
    if "resume_path" not in columns:
        conn.close()
        return None
    cursor.execute("SELECT resume_path FROM students WHERE email = ?", (email,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return row[0]


def select_company_for_student(email: str, company_id: int) -> bool:
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS selected_companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_email TEXT NOT NULL,
            company_id INTEGER NOT NULL,
            selected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            user_id INTEGER,
            FOREIGN KEY(company_id) REFERENCES companies(id)
        )
        """
    )
    cursor.execute("INSERT OR IGNORE INTO students (email) VALUES (?)", (email,))
    cursor.execute("SELECT id FROM students WHERE email = ?", (email,))
    student_row = cursor.fetchone()
    student_id = student_row[0] if student_row else None
    cursor.execute("PRAGMA table_info(selected_companies)")
    existing_columns = {col[1] for col in cursor.fetchall()}
    alterations = [
        ("student_email", "ALTER TABLE selected_companies ADD COLUMN student_email TEXT"),
        ("company_id", "ALTER TABLE selected_companies ADD COLUMN company_id INTEGER NOT NULL"),
        ("selected_at", "ALTER TABLE selected_companies ADD COLUMN selected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ("user_id", "ALTER TABLE selected_companies ADD COLUMN user_id INTEGER"),
    ]
    for column, statement in alterations:
        if column not in existing_columns:
            try:
                cursor.execute(statement)
            except sqlite3.OperationalError:
                pass
    cursor.execute("PRAGMA table_info(selected_companies)")
    columns = {col[1] for col in cursor.fetchall()}
    if "student_email" in columns:
        cursor.execute("DELETE FROM selected_companies WHERE student_email = ?", (email,))
    elif "user_id" in columns and student_id is not None:
        cursor.execute("DELETE FROM selected_companies WHERE user_id = ?", (student_id,))
    if "student_email" in columns and "user_id" in columns and student_id is not None:
        cursor.execute(
            "INSERT INTO selected_companies (student_email, company_id, user_id) VALUES (?, ?, ?)",
            (email, company_id, student_id),
        )
    elif "student_email" in columns:
        cursor.execute(
            "INSERT INTO selected_companies (student_email, company_id) VALUES (?, ?)",
            (email, company_id),
        )
    elif "user_id" in columns and student_id is not None:
        cursor.execute(
            "INSERT INTO selected_companies (user_id, company_id) VALUES (?, ?)",
            (student_id, company_id),
        )
    else:
        conn.close()
        return False
    conn.commit()
    conn.close()
    return True


# Global database instance
db_manager = DatabaseManager()
