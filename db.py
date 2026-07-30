import sqlite3
import time

DB_PATH = "mishaps.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS fault_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                mode TEXT NOT NULL,
                message TEXT NOT NULL,
                occurred_at REAL NOT NULL
            )
        """)
        conn.commit()
    finally:
        conn.close()


def log_fault(session_id, mode, message):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT INTO fault_events (session_id, mode, message, occurred_at) VALUES (?, ?, ?, ?)",
            (session_id, mode, message, time.time()),
        )
        conn.commit()
    finally:
        conn.close()


def get_faults(session_id):
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.execute(
            "SELECT mode, message, occurred_at FROM fault_events WHERE session_id = ? ORDER BY occurred_at",
            (session_id,),
        )
        return cursor.fetchall()
    finally:
        conn.close()


def delete_faults(session_id):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DELETE FROM fault_events WHERE session_id = ?", (session_id,))
        conn.commit()
    finally:
        conn.close()
