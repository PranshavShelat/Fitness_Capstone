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
                occurred_at REAL NOT NULL,
                rep_index INTEGER,
                measured REAL
            )
        """)
        # Older mishaps.db files predate rep_index/measured - add them in place.
        cols = {row[1] for row in conn.execute("PRAGMA table_info(fault_events)")}
        for col, kind in (("rep_index", "INTEGER"), ("measured", "REAL")):
            if col not in cols:
                conn.execute(f"ALTER TABLE fault_events ADD COLUMN {col} {kind}")
        conn.commit()
    finally:
        conn.close()


def log_fault(session_id, mode, message, rep_index=None, measured=None):
    """Returns the new row id, so the measured value can be refined (see
    update_fault_measured) as the same fault streak continues."""
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.execute(
            "INSERT INTO fault_events (session_id, mode, message, occurred_at, rep_index, measured) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, mode, message, time.time(), rep_index, measured),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def update_fault_measured(row_id, measured):
    """Stores the worst value seen over a whole fault streak (not just the
    frame where it was first logged)."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("UPDATE fault_events SET measured = ? WHERE id = ?", (measured, row_id))
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


def get_fault_details(session_id):
    """Like get_faults, plus rep_index and measured:
    (mode, message, occurred_at, rep_index, measured)."""
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.execute(
            "SELECT mode, message, occurred_at, rep_index, measured FROM fault_events "
            "WHERE session_id = ? ORDER BY occurred_at",
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
