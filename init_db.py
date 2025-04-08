# init_db.py

import sqlite3

def init_db():
    conn = sqlite3.connect('proposals.db')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS proposals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url_id TEXT UNIQUE,
            your_name TEXT,
            crush_name TEXT,
            message TEXT,
            theme TEXT,
            paid INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("✅ Database initialized.")
