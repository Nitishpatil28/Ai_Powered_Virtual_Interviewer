"""
Intelligent Question Selection Module
Provides adaptive, non-repeating, balanced question selection for HR and GD interviews
"""

import sqlite3
from typing import List, Dict, Optional
import random

QUESTIONS_DB = "questions.db"
USERS_DB = "users.db"

# Configuration
RECENCY_WINDOW = 30  # Exclude last N questions served to user
MIN_DIFFICULTY_MIX = {
    'beginner': {'Easy': 0.50, 'Medium': 0.40, 'Hard': 0.10},
    'intermediate': {'Easy': 0.20, 'Medium': 0.60, 'Hard': 0.20},
    'advanced': {'Easy': 0.10, 'Medium': 0.40, 'Hard': 0.50}
}


def get_user_level(email: str, question_type: str) -> str:
    """
    Determine user's proficiency level based on recent performance

    Args:
        email: Student email
        question_type: 'hr' or 'gd'

    Returns:
        'beginner', 'intermediate', or 'advanced'
    """
    conn = sqlite3.connect(USERS_DB)
    c = conn.cursor()

    try:
        if question_type == 'hr':
            # Get last HR attempt score
            c.execute("""
                SELECT overall_score
                FROM hr_attempts
                WHERE student_email = ? AND status = 'completed'
                ORDER BY completed_at DESC
                LIMIT 1
            """, (email,))
        elif question_type == 'gd':
            # Get last GD result score
            c.execute("""
                SELECT overall_score
                FROM gd_results
                WHERE student_email = ?
                ORDER BY submitted_at DESC
                LIMIT 1
            """, (email,))
        else:
            return 'intermediate'

        result = c.fetchone()
        if not result:
            return 'intermediate'  # Default for new users

        score = result[0]
        if score < 60:
            return 'beginner'
        elif score < 80:
            return 'intermediate'
        else:
            return 'advanced'

    finally:
        conn.close()


def get_difficulty_mix(level: str, total: int) -> Dict[str, int]:
    """
    Calculate number of questions per difficulty

    Args:
        level: User proficiency level
        total: Total questions needed

    Returns:
        Dict with counts per difficulty
    """
    mix = MIN_DIFFICULTY_MIX.get(level, MIN_DIFFICULTY_MIX['intermediate'])

    result = {}
    remaining = total

    for difficulty in ['Easy', 'Medium', 'Hard']:
        count = int(total * mix[difficulty])
        result[difficulty] = count
        remaining -= count

    # Distribute remainder to Medium
    if remaining > 0:
        result['Medium'] += remaining

    return result


def get_recent_question_ids(email: str, question_type: str, limit: int = RECENCY_WINDOW) -> List[int]:
    """Get recently served question IDs to avoid repetition"""
    conn = sqlite3.connect(USERS_DB)
    c = conn.cursor()

    c.execute("""
        SELECT DISTINCT question_id
        FROM question_usage_events
        WHERE student_email = ? AND question_type = ?
        ORDER BY created_at DESC
        LIMIT ?
    """, (email, question_type, limit))

    ids = [row[0] for row in c.fetchall()]
    conn.close()
    return ids


def select_hr_questions(company_id: int, email: str, total: int = 10) -> List[Dict]:
    """
    Select HR questions with balanced difficulty and variety

    Args:
        company_id: Company ID in questions.db
        email: Student email
        total: Number of questions to select

    Returns:
        List of question dicts
    """
    # Determine user level and difficulty mix
    level = get_user_level(email, 'hr')
    mix = get_difficulty_mix(level, total)

    # Get recently served questions to avoid
    recent_ids = get_recent_question_ids(email, 'hr')

    conn_q = sqlite3.connect(QUESTIONS_DB)
    conn_u = sqlite3.connect(USERS_DB)

    selected_questions = []

    try:
        cq = conn_q.cursor()
        cu = conn_u.cursor()

        for difficulty, count in mix.items():
            if count == 0:
                continue

            # Build exclusion clause
            exclusion = ""
            if recent_ids:
                ids_str = ','.join(str(id) for id in recent_ids)
                exclusion = f"AND id NOT IN ({ids_str})"

            # Get usage counts for all questions first
            cu.execute("""
                SELECT question_id, COUNT(*) as usage_count
                FROM question_usage_events
                WHERE question_type = 'hr'
                GROUP BY question_id
            """)
            usage_counts = {row[0]: row[1] for row in cu.fetchall()}

            # Select questions with balanced criteria
            query = f"""
                SELECT
                    id, question_text, expected_answer,
                    evaluation_rubric, tags, quality_score, difficulty
                FROM hr_questions
                WHERE company_id = ?
                    AND active = 1
                    AND difficulty = ?
                    {exclusion}
                ORDER BY
                    -- Prefer questions with better quality scores
                    quality_score DESC,
                    RANDOM()
                LIMIT ?
            """

            cq.execute(query, (company_id, difficulty, count))
            rows = cq.fetchall()

            for row in rows:
                selected_questions.append({
                    'id': row[0],
                    'question': row[1],
                    'expected_answer': row[2],
                    'evaluation_rubric': row[3],
                    'tags': row[4],
                    'quality_score': row[5],
                    'difficulty': row[6],
                    'time_limit': 60
                })

            # If we couldn't get enough of this difficulty, try fallback
            shortage = count - len(rows)
            if shortage > 0:
                # Try adjacent difficulty
                fallback_diff = 'Medium' if difficulty in ['Easy', 'Hard'] else 'Hard'
                fallback_query = f"""
                    SELECT
                        id, question_text, expected_answer,
                        evaluation_rubric, tags, quality_score, difficulty
                    FROM hr_questions
                    WHERE company_id = ?
                        AND active = 1
                        AND difficulty = ?
                        {exclusion}
                    ORDER BY
                        quality_score DESC,
                        RANDOM()
                    LIMIT ?
                """
                cq.execute(fallback_query, (company_id, fallback_diff, shortage))
                fallback_rows = cq.fetchall()

                for row in fallback_rows:
                    selected_questions.append({
                        'id': row[0],
                        'question': row[1],
                        'expected_answer': row[2],
                        'evaluation_rubric': row[3],
                        'tags': row[4],
                        'quality_score': row[5],
                        'difficulty': row[6],
                        'time_limit': 60
                    })

        # If we don't have enough questions, allow some repetition from older questions
        if len(selected_questions) < total:
            shortage = total - len(selected_questions)
            print(
                f"Warning: Only {len(selected_questions)} fresh questions available, allowing {shortage} repeated questions")

            # Get additional questions without recency exclusion
            for difficulty, count in mix.items():
                if len(selected_questions) >= total:
                    break

                needed = min(count, total - len(selected_questions))

                # Select questions without recency exclusion
                query = f"""
                    SELECT
                        id, question_text, expected_answer,
                        evaluation_rubric, tags, quality_score, difficulty
                    FROM hr_questions
                    WHERE company_id = ?
                        AND active = 1
                        AND difficulty = ?
                    ORDER BY
                        -- Prefer questions with better quality scores
                        quality_score DESC,
                        RANDOM()
                    LIMIT ?
                """

                cq.execute(query, (company_id, difficulty, needed))
                rows = cq.fetchall()

                for row in rows:
                    # Check if we already have this question
                    if not any(q['id'] == row[0] for q in selected_questions):
                        selected_questions.append({
                            'id': row[0],
                            'question': row[1],
                            'expected_answer': row[2],
                            'evaluation_rubric': row[3],
                            'tags': row[4],
                            'quality_score': row[5],
                            'difficulty': row[6],
                            'time_limit': 60
                        })

                        if len(selected_questions) >= total:
                            break

        # Shuffle to avoid predictable difficulty ordering
        random.shuffle(selected_questions)

        return selected_questions[:total]

    finally:
        conn_q.close()
        conn_u.close()


def select_gd_topic(company_id: int, email: str) -> Optional[Dict]:
    """
    Select a GD topic based on user level and recency

    Args:
        company_id: Company ID in questions.db
        email: Student email

    Returns:
        Topic dict or None
    """
    level = get_user_level(email, 'gd')
    recent_ids = get_recent_question_ids(email, 'gd', limit=5)  # Smaller window for GD

    conn_q = sqlite3.connect(QUESTIONS_DB)
    conn_u = sqlite3.connect(USERS_DB)

    try:
        cq = conn_q.cursor()

        # Determine preferred difficulties based on level
        if level == 'beginner':
            preferred = ['Easy', 'Medium']
        elif level == 'intermediate':
            preferred = ['Medium', 'Hard']
        else:
            preferred = ['Medium', 'Hard']

        # Build exclusion clause
        exclusion = ""
        if recent_ids:
            ids_str = ','.join(str(id) for id in recent_ids)
            exclusion = f"AND id NOT IN ({ids_str})"

        # Select topic
        query = f"""
            SELECT
                id, topic, description, difficulty, tags,
                quality_score, sensitivity
            FROM gd_topics
            WHERE company_id = ?
                AND active = 1
                AND difficulty IN (?, ?)
                {exclusion}
            ORDER BY
                quality_score DESC,
                RANDOM()
            LIMIT 1
        """

        cq.execute(query, (company_id, preferred[0], preferred[1]))
        row = cq.fetchone()

        if not row:
            # Fallback: try any active topic
            cq.execute(f"""
                SELECT
                    id, topic, description, difficulty, tags,
                    quality_score, sensitivity
                FROM gd_topics
                WHERE company_id = ? AND active = 1
                ORDER BY RANDOM()
                LIMIT 1
            """, (company_id,))
            row = cq.fetchone()

        if row:
            return {
                'id': row[0],
                'topic': row[1],
                'description': row[2],
                'difficulty': row[3] or 'Medium',
                'tags': row[4],
                'quality_score': row[5],
                'sensitivity': row[6],
                'time_limit': 180
            }

        return None

    finally:
        conn_q.close()
        conn_u.close()


def record_event(
    email: str,
    company_name: str,
    question_type: str,
    question_id: int,
    event: str,
    score: Optional[float] = None,
    time_spent: Optional[int] = None,
    correct: Optional[int] = None
):
    """
    Record a question usage event for analytics

    Args:
        email: Student email
        company_name: Company name
        question_type: 'aptitude', 'technical', 'gd', or 'hr'
        question_id: Question/topic ID
        event: 'served', 'answered', 'skipped', 'timeout', 'rated'
        score: Optional score (0-100)
        time_spent: Optional time in seconds
        correct: Optional correctness (1/0) for MCQ
    """
    conn = sqlite3.connect(USERS_DB)
    c = conn.cursor()

    try:
        c.execute("""
            INSERT INTO question_usage_events (
                student_email, company_name, question_type, question_id,
                event, score, time_spent, correct, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (email, company_name, question_type, question_id, event, score, time_spent, correct))

        conn.commit()
    finally:
        conn.close()


def get_question_analytics(question_type: str, question_id: int) -> Dict:
    """
    Get analytics for a specific question

    Args:
        question_type: Type of question
        question_id: Question ID

    Returns:
        Analytics dict with served_count, answered_count, avg_score, avg_time
    """
    conn = sqlite3.connect(USERS_DB)
    c = conn.cursor()

    c.execute("""
        SELECT
            COUNT(*) FILTER (WHERE event='served') as served,
            COUNT(*) FILTER (WHERE event='answered') as answered,
            AVG(CASE WHEN event='answered' THEN score END) as avg_score,
            AVG(CASE WHEN event='answered' THEN time_spent END) as avg_time
        FROM question_usage_events
        WHERE question_type = ? AND question_id = ?
    """, (question_type, question_id))

    row = c.fetchone()
    conn.close()

    return {
        'served_count': row[0] or 0,
        'answered_count': row[1] or 0,
        'avg_score': round(row[2], 2) if row[2] else None,
        'avg_time_spent': round(row[3], 2) if row[3] else None
    }


def get_user_performance_summary(email: str, question_type: str) -> Dict:
    """
    Get performance summary for a user

    Args:
        email: Student email
        question_type: Type of questions

    Returns:
        Summary dict with counts and averages
    """
    conn = sqlite3.connect(USERS_DB)
    c = conn.cursor()

    c.execute("""
        SELECT
            COUNT(*) FILTER (WHERE event='answered') as total_answered,
            AVG(CASE WHEN event='answered' THEN score END) as avg_score,
            AVG(CASE WHEN event='answered' THEN time_spent END) as avg_time
        FROM question_usage_events
        WHERE student_email = ? AND question_type = ?
    """, (email, question_type))

    row = c.fetchone()
    conn.close()

    return {
        'total_answered': row[0] or 0,
        'avg_score': round(row[1], 2) if row[1] else 0,
        'avg_time_spent': round(row[2], 2) if row[2] else 0
    }
