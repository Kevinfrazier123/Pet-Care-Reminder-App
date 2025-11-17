import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path("app.db")

# --- Database schema: now includes full_name, home_address, avatar_filename ---
SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    full_name TEXT,
    home_address TEXT,
    avatar_filename TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    is_admin INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
"""


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    print("Database initialized (users table ready).")


def create_user(email, password_hash, is_admin=0):
    """Create a new user with just email + password; other fields can be updated later."""
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO users (email, password_hash, full_name, home_address, avatar_filename,
                           is_active, is_admin, created_at)
        VALUES (?, ?, NULL, NULL, NULL, 1, ?, ?)
        """,
        (email, password_hash, is_admin, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def get_user_by_email(email):
    conn = get_conn()
    cur = conn.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cur.fetchone()
    conn.close()
    return user


def get_user_by_id(user_id: int):
    conn = get_conn()
    cur = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cur.fetchone()
    conn.close()
    return user


def update_user_profile(user_id, email, full_name, home_address, avatar_filename=None):
    """Update name, email, address, and optionally avatar filename."""
    conn = get_conn()
    if avatar_filename is not None:
        conn.execute(
            """
            UPDATE users
            SET email = ?, full_name = ?, home_address = ?, avatar_filename = ?
            WHERE id = ?
            """,
            (email, full_name, home_address, avatar_filename, user_id),
        )
    else:
        conn.execute(
            """
            UPDATE users
            SET email = ?, full_name = ?, home_address = ?
            WHERE id = ?
            """,
            (email, full_name, home_address, user_id),
        )
    conn.commit()
    conn.close()


def change_user_password(user_id, new_password_hash):
    conn = get_conn()
    conn.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (new_password_hash, user_id),
    )
    conn.commit()
    conn.close()
