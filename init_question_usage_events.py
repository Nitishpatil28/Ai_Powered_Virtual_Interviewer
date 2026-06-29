import sqlite3

DB_PATH = "questions.db"


def init_question_usage_events():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS question_usage_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            company_name TEXT,
            question_type TEXT,
            question_id INTEGER,
            event TEXT,
            score REAL,
            time_spent INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
    print("[DB INIT] ✅ question_usage_events table created successfully!")


if __name__ == "__main__":
    init_question_usage_events()
