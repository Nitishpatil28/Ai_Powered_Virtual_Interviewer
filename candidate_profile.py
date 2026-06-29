"""
Candidate Profile Data Collection and Management Module
Collects academic records, skills, preferences, and other data for AI-driven recommendations
"""

import sqlite3
import json
from typing import Dict, Optional, Any
from datetime import datetime
import os

DB_PATH = os.environ.get('PROFILE_DB_PATH', 'users.db')


class CandidateProfileManager:
    """Manages candidate profiles for AI-driven company matching"""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_profile_tables()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_profile_tables(self):
        """Initialize enhanced profile tables"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS candidate_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                name TEXT,
                phone TEXT,
                cgpa REAL DEFAULT 0.0,
                graduation_year INTEGER,
                degree TEXT,
                major TEXT,
                university TEXT,
                skills TEXT,
                certifications TEXT,
                projects TEXT,
                internships TEXT,
                achievements TEXT,
                preferred_roles TEXT,
                preferred_locations TEXT,
                preferred_industries TEXT,
                min_salary_expectation REAL,
                work_authorization TEXT,
                resume_path TEXT,
                profile_completeness REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS academic_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                institution_name TEXT,
                degree_type TEXT,
                field_of_study TEXT,
                cgpa REAL,
                max_cgpa REAL DEFAULT 10.0,
                start_year INTEGER,
                end_year INTEGER,
                achievements TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(email) REFERENCES candidate_profiles(email)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS candidate_skills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                skill_name TEXT NOT NULL,
                proficiency_level TEXT,
                years_experience REAL,
                verified BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(email) REFERENCES candidate_profiles(email)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS candidate_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                preferred_company_size TEXT,
                work_mode_preference TEXT,
                relocation_willing BOOLEAN DEFAULT 1,
                notice_period_days INTEGER DEFAULT 0,
                career_goals TEXT,
                additional_preferences TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(email) REFERENCES candidate_profiles(email)
            )
        """)

        conn.commit()
        conn.close()

    def create_or_update_profile(self, email: str, profile_data: Dict[str, Any]) -> bool:
        """Create or update candidate profile with comprehensive data"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT email FROM candidate_profiles WHERE email = ?", (email,))
            exists = cursor.fetchone()

            profile_data['email'] = email
            profile_data['updated_at'] = datetime.now().isoformat()

            if exists:
                update_fields = []
                update_values = []
                for key, value in profile_data.items():
                    if key != 'email':
                        if isinstance(value, (list, dict)):
                            value = json.dumps(value)
                        update_fields.append(f"{key} = ?")
                        update_values.append(value)

                if update_fields:
                    update_values.append(email)
                    query = f"UPDATE candidate_profiles SET {', '.join(update_fields)} WHERE email = ?"
                    cursor.execute(query, update_values)
            else:
                allowed_fields = [
                    'email', 'name', 'phone', 'cgpa', 'graduation_year', 'degree', 'major',
                    'university', 'skills', 'certifications', 'projects', 'internships',
                    'achievements', 'preferred_roles', 'preferred_locations',
                    'preferred_industries', 'min_salary_expectation', 'work_authorization',
                    'resume_path'
                ]

                insert_data = {}
                for field in allowed_fields:
                    if field in profile_data:
                        value = profile_data[field]
                        if isinstance(value, (list, dict)):
                            value = json.dumps(value)
                        insert_data[field] = value

                fields = list(insert_data.keys())
                placeholders = ', '.join(['?' for _ in fields])
                query = f"INSERT INTO candidate_profiles ({', '.join(fields)}) VALUES ({placeholders})"
                cursor.execute(query, list(insert_data.values()))

            completeness = self._calculate_profile_completeness(profile_data)
            cursor.execute(
                "UPDATE candidate_profiles SET profile_completeness = ?, updated_at = ? WHERE email = ?",
                (completeness, datetime.now().isoformat(), email)
            )

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error updating profile: {e}")
            return False

    def add_academic_record(self, email: str, academic_data: Dict[str, Any]) -> bool:
        """Add academic record to candidate profile"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            academic_data['email'] = email
            fields = ['email', 'institution_name', 'degree_type', 'field_of_study',
                      'cgpa', 'max_cgpa', 'start_year', 'end_year', 'achievements']

            insert_data = {k: academic_data.get(k) for k in fields if k in academic_data}
            if 'achievements' in insert_data and isinstance(insert_data['achievements'], list):
                insert_data['achievements'] = json.dumps(insert_data['achievements'])

            field_names = list(insert_data.keys())
            placeholders = ', '.join(['?' for _ in field_names])
            query = f"INSERT INTO academic_records ({', '.join(field_names)}) VALUES ({placeholders})"
            cursor.execute(query, list(insert_data.values()))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error adding academic record: {e}")
            return False

    def add_skill(self, email: str, skill_data: Dict[str, Any]) -> bool:
        """Add skill to candidate profile"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO candidate_skills (email, skill_name, proficiency_level, years_experience, verified)
                VALUES (?, ?, ?, ?, ?)
            """, (
                email,
                skill_data.get('skill_name'),
                skill_data.get('proficiency_level', 'Intermediate'),
                skill_data.get('years_experience', 0),
                skill_data.get('verified', 0)
            ))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error adding skill: {e}")
            return False

    def update_preferences(self, email: str, preferences: Dict[str, Any]) -> bool:
        """Update candidate preferences"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            preferences['email'] = email
            preferences['updated_at'] = datetime.now().isoformat()

            if 'additional_preferences' in preferences and isinstance(preferences['additional_preferences'], dict):
                preferences['additional_preferences'] = json.dumps(preferences['additional_preferences'])

            cursor.execute("SELECT email FROM candidate_preferences WHERE email = ?", (email,))
            exists = cursor.fetchone()

            if exists:
                update_fields = []
                update_values = []
                for key, value in preferences.items():
                    if key != 'email':
                        update_fields.append(f"{key} = ?")
                        update_values.append(value)

                if update_fields:
                    update_values.append(email)
                    query = f"UPDATE candidate_preferences SET {', '.join(update_fields)} WHERE email = ?"
                    cursor.execute(query, update_values)
            else:
                fields = list(preferences.keys())
                placeholders = ', '.join(['?' for _ in fields])
                query = f"INSERT INTO candidate_preferences ({', '.join(fields)}) VALUES ({placeholders})"
                cursor.execute(query, list(preferences.values()))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error updating preferences: {e}")
            return False

    def get_complete_profile(self, email: str) -> Optional[Dict[str, Any]]:
        """Get complete candidate profile with all related data"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM candidate_profiles WHERE email = ?", (email,))
            profile_row = cursor.fetchone()

            if not profile_row:
                conn.close()
                return None

            profile = dict(profile_row)

            for field in ['skills', 'certifications', 'projects', 'internships', 'achievements',
                          'preferred_roles', 'preferred_locations', 'preferred_industries']:
                if profile.get(field):
                    try:
                        profile[field] = json.loads(profile[field])
                    except BaseException:
                        pass

            cursor.execute("SELECT * FROM academic_records WHERE email = ?", (email,))
            profile['academic_records'] = [dict(row) for row in cursor.fetchall()]

            cursor.execute("SELECT * FROM candidate_skills WHERE email = ?", (email,))
            profile['detailed_skills'] = [dict(row) for row in cursor.fetchall()]

            cursor.execute("SELECT * FROM candidate_preferences WHERE email = ?", (email,))
            pref_row = cursor.fetchone()
            profile['preferences'] = dict(pref_row) if pref_row else {}

            conn.close()
            return profile
        except Exception as e:
            print(f"Error getting complete profile: {e}")
            return None

    def _calculate_profile_completeness(self, profile_data: Dict[str, Any]) -> float:
        """Calculate profile completeness percentage"""
        required_fields = [
            'name', 'email', 'phone', 'cgpa', 'graduation_year', 'degree', 'major',
            'skills', 'resume_path', 'preferred_roles', 'preferred_locations'
        ]

        completed = 0
        for field in required_fields:
            value = profile_data.get(field)
            if value and value != '' and value != 0:
                completed += 1

        return round((completed / len(required_fields)) * 100, 2)

    def get_profile_analytics(self, email: str) -> Dict[str, Any]:
        """Get analytics about candidate profile"""
        profile = self.get_complete_profile(email)
        if not profile:
            return {}

        return {
            'completeness': profile.get('profile_completeness', 0),
            'total_skills': len(profile.get('detailed_skills', [])),
            'verified_skills': sum(1 for s in profile.get('detailed_skills', []) if s.get('verified')),
            'academic_records_count': len(profile.get('academic_records', [])),
            'has_preferences': bool(profile.get('preferences')),
            'profile_strength': self._calculate_profile_strength(profile)
        }

    def _calculate_profile_strength(self, profile: Dict[str, Any]) -> str:
        """Calculate overall profile strength"""
        completeness = profile.get('profile_completeness', 0)
        skills_count = len(profile.get('detailed_skills', []))
        has_projects = bool(profile.get('projects'))
        has_internships = bool(profile.get('internships'))

        score = 0
        if completeness >= 80:
            score += 40
        elif completeness >= 60:
            score += 30
        elif completeness >= 40:
            score += 20

        if skills_count >= 10:
            score += 30
        elif skills_count >= 5:
            score += 20
        elif skills_count >= 1:
            score += 10

        if has_projects:
            score += 15
        if has_internships:
            score += 15

        if score >= 80:
            return "Excellent"
        elif score >= 60:
            return "Good"
        elif score >= 40:
            return "Average"
        else:
            return "Needs Improvement"


profile_manager = CandidateProfileManager()
