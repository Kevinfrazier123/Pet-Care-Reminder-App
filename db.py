import sqlite3
from pathlib import Path
from datetime import datetime, date

DB_PATH = Path("app.db")

# --- Updated Database Schema (Users + Pets + Care Tasks) ---
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

CREATE TABLE IF NOT EXISTS pets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    species TEXT NOT NULL,
    breed TEXT,
    birthdate TEXT,
    weight TEXT,
    vet_name TEXT,
    notes TEXT,
    avatar_filename TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS care_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    pet_id INTEGER,
    title TEXT NOT NULL,
    category TEXT,
    description TEXT,
    due_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    completed_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (pet_id) REFERENCES pets(id)
);
"""


# -----------------------------
#  BASIC DB FUNCTIONS
# -----------------------------
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    print("Database initialized (users, pets, care_tasks tables ready).")


# -----------------------------
#  USER FUNCTIONS
# -----------------------------
def create_user(email, password_hash, is_admin=0):
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


# -----------------------------
#  PET FUNCTIONS
# -----------------------------
def create_pet(user_id, name, species, breed=None, birthdate=None,
               weight=None, vet_name=None, notes=None, avatar_filename=None):
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO pets (
            user_id, name, species, breed, birthdate,
            weight, vet_name, notes, avatar_filename, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            name,
            species,
            breed,
            birthdate,
            weight,
            vet_name,
            notes,
            avatar_filename,
            datetime.utcnow().isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def get_pets_for_user(user_id):
    conn = get_conn()
    cur = conn.execute(
        """
        SELECT *
        FROM pets
        WHERE user_id = ?
        ORDER BY created_at ASC
        """,
        (user_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


# -----------------------------
#  CARE TASK FUNCTIONS
# -----------------------------
def create_care_task(user_id, title, due_date, pet_id=None,
                     category=None, description=None):
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO care_tasks (
            user_id, pet_id, title, category, description,
            due_date, status, created_at, completed_at
        )
        VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, NULL)
        """,
        (
            user_id,
            pet_id,
            title,
            category,
            description,
            due_date,  # 'YYYY-MM-DD'
            datetime.utcnow().isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def get_upcoming_tasks_for_user(user_id, limit=5):
    today_str = date.today().isoformat()
    conn = get_conn()
    cur = conn.execute(
        """
        SELECT ct.*, p.name AS pet_name
        FROM care_tasks ct
        LEFT JOIN pets p ON ct.pet_id = p.id
        WHERE ct.user_id = ?
          AND ct.status = 'pending'
          AND ct.due_date >= ?
        ORDER BY ct.due_date ASC
        LIMIT ?
        """,
        (user_id, today_str, limit),
    )
    rows = cur.fetchall()
    conn.close()
    return rows
