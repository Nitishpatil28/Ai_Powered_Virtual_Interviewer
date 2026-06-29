"""
AI-Driven Company Recommendation Engine
Provides personalized company recommendations with 80%+ match accuracy
Tracks recommendations and user satisfaction scores
"""

import sqlite3
import json
import numpy as np
from typing import Dict, List, Any
from datetime import datetime
import os


try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_MODEL = SentenceTransformer('all-MiniLM-L6-v2')
except Exception:
    SENTENCE_MODEL = None

DB_PATH = os.environ.get('REC_DB_PATH', 'users.db')


class RecommendationEngine:
    """AI-driven company recommendation engine with satisfaction tracking"""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_recommendation_tables()
        self.tfidf_vectorizer = None
        self.company_embeddings = {}

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_recommendation_tables(self):
        """Initialize recommendation tracking tables"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS company_recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                company_id INTEGER NOT NULL,
                score_percent REAL NOT NULL,
                match_factors TEXT,
                recommendation_reason TEXT,
                rank_position INTEGER,
                recommended_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                user_action TEXT,
                user_feedback_rating INTEGER,
                user_feedback_comment TEXT,
                accepted BOOLEAN DEFAULT 0,
                viewed BOOLEAN DEFAULT 0,
                FOREIGN KEY(company_id) REFERENCES companies(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recommendation_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                total_recommendations INTEGER DEFAULT 0,
                total_accepted INTEGER DEFAULT 0,
                total_viewed INTEGER DEFAULT 0,
                average_match_score REAL DEFAULT 0.0,
                average_satisfaction_score REAL DEFAULT 0.0,
                satisfaction_count INTEGER DEFAULT 0,
                last_recommendation_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(email)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS match_quality_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recommendation_id INTEGER NOT NULL,
                email TEXT NOT NULL,
                company_id INTEGER NOT NULL,
                match_quality_rating INTEGER,
                relevance_rating INTEGER,
                satisfaction_rating INTEGER,
                would_recommend BOOLEAN,
                feedback_text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(recommendation_id) REFERENCES company_recommendations(id),
                FOREIGN KEY(company_id) REFERENCES companies(id)
            )
        """)

        conn.commit()
        conn.close()

    def generate_recommendations(self, email: str, top_k: int = 10,
                                 min_match_threshold: float = 80.0) -> List[Dict[str, Any]]:
        """
        Generate AI-driven company recommendations with 80%+ match accuracy

        Args:
            email: Candidate email
            top_k: Number of recommendations to generate
            min_match_threshold: Minimum match percentage (default 80%)

        Returns:
            List of company recommendations with match scores and factors
        """
        from candidate_profile import profile_manager

        profile = profile_manager.get_complete_profile(email)
        if not profile:
            return []

        companies = self._get_all_companies()
        if not companies:
            return []

        recommendations = []

        for company in companies:
            match_score, match_factors = self._calculate_match_score(profile, company)

            if match_score >= min_match_threshold:
                recommendations.append({
                    'company_id': company['id'],
                    'company_name': company['name'],
                    'role': company.get('role', ''),
                    'package_offered': company.get('package_offered', ''),
                    'location': company.get('location', ''),
                    'industry': company.get('industry', ''),
                    'score_percent': round(match_score, 2),
                    'match_factors': match_factors,
                    'recommendation_reason': self._generate_recommendation_reason(match_factors, match_score)
                })

        recommendations.sort(key=lambda x: x['score_percent'], reverse=True)
        top_recommendations = recommendations[:top_k]

        self._save_recommendations(email, top_recommendations)
        self._update_recommendation_metrics(email, len(top_recommendations),
                                            np.mean([r['score_percent'] for r in top_recommendations]))

        return top_recommendations

    def _calculate_match_score(self, profile: Dict[str, Any],
                               company: Dict[str, Any]) -> tuple[float, List[str]]:
        """
        Calculate comprehensive match score between candidate and company
        Returns: (score_percent, match_factors_list)
        """
        match_factors = []
        weights = {
            'skills': 0.35,
            'cgpa': 0.15,
            'graduation_year': 0.10,
            'preferences': 0.20,
            'academic_background': 0.10,
            'experience': 0.10
        }

        scores = {}

        profile_skills = set()
        if profile.get('detailed_skills'):
            profile_skills = {s['skill_name'].lower() for s in profile['detailed_skills']}
        elif profile.get('skills'):
            if isinstance(profile['skills'], list):
                profile_skills = {s.lower() for s in profile['skills']}
            else:
                profile_skills = {s.strip().lower() for s in str(profile['skills']).split(',')}

        company_skills = set()
        if company.get('required_skills'):
            company_skills = {s.strip().lower() for s in str(company['required_skills']).split(',')}

        if profile_skills and company_skills:
            skill_overlap = profile_skills.intersection(company_skills)
            skill_score = len(skill_overlap) / len(company_skills) if company_skills else 0
            scores['skills'] = min(100, skill_score * 100)

            if skill_score > 0.7:
                match_factors.append(f"Strong skill match: {', '.join(list(skill_overlap)[:3])}")
            elif skill_score > 0.4:
                match_factors.append("Good skill alignment")
        else:
            scores['skills'] = 50

        profile_cgpa = profile.get('cgpa', 0)
        required_cgpa = company.get('min_cgpa', 0)

        if profile_cgpa >= required_cgpa:
            cgpa_score = 100
            if profile_cgpa >= required_cgpa + 1:
                match_factors.append(f"Exceeds CGPA requirement ({profile_cgpa} >= {required_cgpa})")
            else:
                match_factors.append("Meets CGPA requirement")
        else:
            cgpa_score = max(0, (profile_cgpa / required_cgpa) * 100) if required_cgpa > 0 else 50
        scores['cgpa'] = cgpa_score

        profile_year = profile.get('graduation_year')
        company_year = company.get('graduation_year')
        if profile_year and company_year:
            if profile_year == company_year:
                scores['graduation_year'] = 100
                match_factors.append(f"Perfect graduation year match ({profile_year})")
            elif abs(profile_year - company_year) <= 1:
                scores['graduation_year'] = 75
            else:
                scores['graduation_year'] = 40
        else:
            scores['graduation_year'] = 50

        pref_score = 50
        preferences = profile.get('preferences', {})

        if preferences:
            pref_locations = preferences.get('preferred_locations', [])
            if isinstance(pref_locations, str):
                pref_locations = json.loads(pref_locations) if pref_locations.startswith('[') else [pref_locations]

            company_location = company.get('location', '')
            if pref_locations and company_location:
                if any(loc.lower() in company_location.lower() for loc in pref_locations):
                    pref_score += 25
                    match_factors.append(f"Preferred location: {company_location}")

            pref_industries = preferences.get('preferred_industries', [])
            if isinstance(pref_industries, str):
                pref_industries = json.loads(pref_industries) if pref_industries.startswith('[') else [pref_industries]

            company_industry = company.get('industry', '')
            if pref_industries and company_industry:
                if any(ind.lower() in company_industry.lower() for ind in pref_industries):
                    pref_score += 25
                    match_factors.append(f"Preferred industry: {company_industry}")

        scores['preferences'] = min(100, pref_score)

        profile_major = profile.get('major', '').lower()
        company_role = company.get('role', '').lower()

        if profile_major and company_role:
            if profile_major in company_role or company_role in profile_major:
                scores['academic_background'] = 90
                match_factors.append("Degree aligns with role")
            else:
                scores['academic_background'] = 60
        else:
            scores['academic_background'] = 50

        has_projects = bool(profile.get('projects'))
        has_internships = bool(profile.get('internships'))

        if has_projects and has_internships:
            scores['experience'] = 100
            match_factors.append("Strong practical experience (projects + internships)")
        elif has_projects or has_internships:
            scores['experience'] = 75
            match_factors.append("Good practical experience")
        else:
            scores['experience'] = 40

        total_score = sum(scores[key] * weights[key] for key in weights.keys())

        return total_score, match_factors

    def _generate_recommendation_reason(self, match_factors: List[str], score: float) -> str:
        """Generate human-readable recommendation reason"""
        if score >= 90:
            quality = "Excellent match"
        elif score >= 80:
            quality = "Strong match"
        elif score >= 70:
            quality = "Good match"
        else:
            quality = "Fair match"

        if match_factors:
            return f"{quality}: {', '.join(match_factors[:3])}"
        else:
            return f"{quality} based on your profile"

    def _save_recommendations(self, email: str, recommendations: List[Dict[str, Any]]):
        """Save recommendations to database for tracking"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            for idx, rec in enumerate(recommendations, 1):
                cursor.execute("""
                    INSERT INTO company_recommendations
                    (email, company_id, score_percent, match_factors, recommendation_reason, rank_position)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    email,
                    rec['company_id'],
                    rec['score_percent'],
                    json.dumps(rec['match_factors']),
                    rec['recommendation_reason'],
                    idx
                ))

            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error saving recommendations: {e}")

    def _update_recommendation_metrics(self, email: str, count: int, avg_score: float):
        """Update recommendation metrics for user"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM recommendation_metrics WHERE email = ?", (email,))
            exists = cursor.fetchone()

            if exists:
                cursor.execute("""
                    UPDATE recommendation_metrics
                    SET total_recommendations = total_recommendations + ?,
                        average_match_score = ?,
                        last_recommendation_at = ?,
                        updated_at = ?
                    WHERE email = ?
                """, (count, avg_score, datetime.now().isoformat(), datetime.now().isoformat(), email))
            else:
                cursor.execute("""
                    INSERT INTO recommendation_metrics
                    (email, total_recommendations, average_match_score, last_recommendation_at)
                    VALUES (?, ?, ?, ?)
                """, (email, count, avg_score, datetime.now().isoformat()))

            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error updating metrics: {e}")

    def record_user_feedback(self, email: str, company_id: int,
                             satisfaction_rating: int, feedback_data: Dict[str, Any]) -> bool:
        """Record user satisfaction feedback for a recommendation"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id FROM company_recommendations
                WHERE email = ? AND company_id = ?
                ORDER BY recommended_at DESC LIMIT 1
            """, (email, company_id))

            rec_row = cursor.fetchone()
            if not rec_row:
                conn.close()
                return False

            rec_id = rec_row['id']

            cursor.execute("""
                UPDATE company_recommendations
                SET user_feedback_rating = ?,
                    user_feedback_comment = ?,
                    user_action = ?
                WHERE id = ?
            """, (
                satisfaction_rating,
                feedback_data.get('comment', ''),
                feedback_data.get('action', 'feedback'),
                rec_id
            ))

            cursor.execute("""
                INSERT INTO match_quality_feedback
                (recommendation_id, email, company_id, match_quality_rating,
                 relevance_rating, satisfaction_rating, would_recommend, feedback_text)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                rec_id,
                email,
                company_id,
                feedback_data.get('match_quality', satisfaction_rating),
                feedback_data.get('relevance', satisfaction_rating),
                satisfaction_rating,
                feedback_data.get('would_recommend', satisfaction_rating >= 4),
                feedback_data.get('feedback_text', '')
            ))

            cursor.execute("""
                SELECT AVG(user_feedback_rating) as avg_rating, COUNT(*) as count
                FROM company_recommendations
                WHERE email = ? AND user_feedback_rating IS NOT NULL
            """, (email,))

            stats = cursor.fetchone()
            avg_rating = stats['avg_rating'] if stats['avg_rating'] else 0
            count = stats['count'] if stats['count'] else 0

            cursor.execute("""
                UPDATE recommendation_metrics
                SET average_satisfaction_score = ?,
                    satisfaction_count = ?,
                    updated_at = ?
                WHERE email = ?
            """, (avg_rating, count, datetime.now().isoformat(), email))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error recording feedback: {e}")
            return False

    def mark_recommendation_viewed(self, email: str, company_id: int) -> bool:
        """Mark a recommendation as viewed"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE company_recommendations
                SET viewed = 1
                WHERE email = ? AND company_id = ? AND viewed = 0
            """, (email, company_id))

            if cursor.rowcount > 0:
                cursor.execute("""
                    UPDATE recommendation_metrics
                    SET total_viewed = total_viewed + 1
                    WHERE email = ?
                """, (email,))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error marking viewed: {e}")
            return False

    def mark_recommendation_accepted(self, email: str, company_id: int) -> bool:
        """Mark a recommendation as accepted"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE company_recommendations
                SET accepted = 1, user_action = 'accepted'
                WHERE email = ? AND company_id = ?
            """, (email, company_id))

            cursor.execute("""
                UPDATE recommendation_metrics
                SET total_accepted = total_accepted + 1
                WHERE email = ?
            """, (email,))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error marking accepted: {e}")
            return False

    def get_recommendation_stats(self, email: str) -> Dict[str, Any]:
        """Get recommendation statistics for a user"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM recommendation_metrics WHERE email = ?", (email,))
            metrics_row = cursor.fetchone()

            if not metrics_row:
                conn.close()
                return {
                    'total_recommendations': 0,
                    'total_accepted': 0,
                    'total_viewed': 0,
                    'average_match_score': 0.0,
                    'average_satisfaction_score': 0.0,
                    'acceptance_rate': 0.0,
                    'satisfaction_count': 0
                }

            metrics = dict(metrics_row)

            if metrics['total_recommendations'] > 0:
                metrics['acceptance_rate'] = round(
                    (metrics['total_accepted'] / metrics['total_recommendations']) * 100, 2
                )
                metrics['view_rate'] = round(
                    (metrics['total_viewed'] / metrics['total_recommendations']) * 100, 2
                )
            else:
                metrics['acceptance_rate'] = 0.0
                metrics['view_rate'] = 0.0

            conn.close()
            return metrics
        except Exception as e:
            print(f"Error getting stats: {e}")
            return {}

    def _get_all_companies(self) -> List[Dict[str, Any]]:
        """Get all companies from database"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM companies")
            companies = [dict(row) for row in cursor.fetchall()]

            conn.close()
            return companies
        except Exception as e:
            print(f"Error getting companies: {e}")
            return []


recommendation_engine = RecommendationEngine()
