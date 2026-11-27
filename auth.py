import sqlite3
import hashlib

DB_PATH = "data/students.db"

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def init_auth_table():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('Admin', 'Faculty', 'Student')),
            full_name TEXT NOT NULL,
            roll_no TEXT
        )
    """)
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        default_users = [
            ("admin", hash_password("admin123"), "Admin", "Campus Administrator", None),
            ("faculty", hash_password("faculty123"), "Faculty", "Prof. Sharma", None),
            ("student1", hash_password("student123"), "Student", "Aarav Verma", "CS202401"),
        ]
        c.executemany(
            "INSERT INTO users (username, password_hash, role, full_name, roll_no) VALUES (?, ?, ?, ?, ?)",
            default_users
        )
    conn.commit()
    conn.close()

def authenticate_user(username: str, password: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT id, username, role, full_name, roll_no FROM users WHERE username = ? AND password_hash = ?",
        (username.strip(), hash_password(password))
    )
    user = c.fetchone()
    conn.close()
    if user:
        return {
            "id": user[0],
            "username": user[1],
            "role": user[2],
            "full_name": user[3],
            "roll_no": user[4]
        }
    return None

def register_user(username: str, password: str, role: str, full_name: str, roll_no: str = None):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "INSERT INTO users (username, password_hash, role, full_name, roll_no) VALUES (?, ?, ?, ?, ?)",
            (username.strip(), hash_password(password), role, full_name.strip(), roll_no.strip() if roll_no else None)
        )
        conn.commit()
        conn.close()
        return True, "Account created successfully."
    except sqlite3.IntegrityError:
        return False, "Username already exists."

def get_or_create_oauth_user(email: str, full_name: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT id, username, role, full_name, roll_no FROM users WHERE username = ?",
        (email.strip(),)
    )
    user = c.fetchone()
    if not user:
        c.execute(
            "INSERT INTO users (username, password_hash, role, full_name, roll_no) VALUES (?, ?, ?, ?, ?)",
            (email.strip(), "OAUTH_USER", "Student", full_name.strip() or email.split("@")[0], None)
        )
        conn.commit()
        c.execute(
            "SELECT id, username, role, full_name, roll_no FROM users WHERE username = ?",
            (email.strip(),)
        )
        user = c.fetchone()
    conn.close()
    return {
        "id": user[0],
        "username": user[1],
        "role": user[2],
        "full_name": user[3],
        "roll_no": user[4]
    }
