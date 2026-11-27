import os
import sqlite3
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "students.db")


def _migrate_students_table(cursor):
    cursor.execute("PRAGMA table_info(students)")
    cols = {row[1] for row in cursor.fetchall()}

    if "sem1_marks" not in cols:
        cursor.execute("ALTER TABLE students ADD COLUMN sem1_marks REAL NOT NULL DEFAULT 75.0")
    if "sem2_marks" not in cols:
        cursor.execute("ALTER TABLE students ADD COLUMN sem2_marks REAL NOT NULL DEFAULT 78.0")
    if "end_term_marks" not in cols:
        cursor.execute("ALTER TABLE students ADD COLUMN end_term_marks REAL NOT NULL DEFAULT 80.0")
    if "email" not in cols:
        cursor.execute("ALTER TABLE students ADD COLUMN email TEXT NOT NULL DEFAULT ''")

    if "marks" in cols:
        cursor.execute(
            """
            UPDATE students
            SET sem1_marks = COALESCE(NULLIF(sem1_marks, 0), marks, 75.0),
                sem2_marks = COALESCE(NULLIF(sem2_marks, 0), marks, 78.0),
                end_term_marks = COALESCE(NULLIF(end_term_marks, 0), marks, 80.0)
            """
        )


def create_table():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            roll_no TEXT NOT NULL,
            department TEXT NOT NULL,
            email TEXT NOT NULL DEFAULT '',
            sem1_marks REAL NOT NULL DEFAULT 75.0,
            sem2_marks REAL NOT NULL DEFAULT 78.0,
            end_term_marks REAL NOT NULL DEFAULT 80.0,
            marks REAL NOT NULL DEFAULT 77.7,
            attendance REAL NOT NULL DEFAULT 80.0,
            study_hours REAL NOT NULL DEFAULT 12.0
        )
    """)
    _migrate_students_table(cursor)
    conn.commit()
    conn.close()


def add_student(
    name,
    roll_no,
    department,
    attendance=80.0,
    marks=None,
    study_hours=12.0,
    sem1_marks=75.0,
    sem2_marks=78.0,
    end_term_marks=80.0,
    email=""
):
    create_table()
    s1 = float(sem1_marks if sem1_marks is not None else (marks if marks is not None else 75.0))
    s2 = float(sem2_marks if sem2_marks is not None else (marks if marks is not None else 78.0))
    et = float(end_term_marks if end_term_marks is not None else (marks if marks is not None else 80.0))
    overall = round((s1 + s2 + et) / 3.0, 2) if marks is None else round(float(marks), 2)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO students (
            name, roll_no, department, email,
            sem1_marks, sem2_marks, end_term_marks,
            marks, attendance, study_hours
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(name).strip(),
            str(roll_no).strip(),
            str(department).strip(),
            str(email).strip(),
            s1,
            s2,
            et,
            overall,
            float(attendance),
            float(study_hours),
        )
    )
    conn.commit()
    conn.close()


def update_student_marks(
    student_id,
    name,
    roll_no,
    department,
    sem1_marks,
    sem2_marks,
    end_term_marks,
    attendance,
    study_hours,
    email=""
):
    create_table()
    s1 = float(sem1_marks)
    s2 = float(sem2_marks)
    et = float(end_term_marks)
    overall = round((s1 + s2 + et) / 3.0, 2)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE students
        SET name = ?, roll_no = ?, department = ?, email = ?,
            sem1_marks = ?, sem2_marks = ?, end_term_marks = ?,
            marks = ?, attendance = ?, study_hours = ?
        WHERE id = ?
        """,
        (
            str(name).strip(),
            str(roll_no).strip(),
            str(department).strip(),
            str(email).strip(),
            s1,
            s2,
            et,
            overall,
            float(attendance),
            float(study_hours),
            int(student_id),
        )
    )
    conn.commit()
    conn.close()


def get_students():
    create_table()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM students ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_student(student_id):
    create_table()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM students WHERE id = ?", (int(student_id),))
    conn.commit()
    conn.close()


def init_notices_table():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'General',
            message TEXT NOT NULL,
            posted_by TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    cursor.execute("PRAGMA table_info(notices)")
    cols = [c[1] for c in cursor.fetchall()]
    if "category" not in cols:
        cursor.execute("ALTER TABLE notices ADD COLUMN category TEXT NOT NULL DEFAULT 'General'")
    conn.commit()
    conn.close()


def add_notice(title, message, posted_by, category="General"):
    init_notices_table()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO notices (title, category, message, posted_by, created_at) VALUES (?, ?, ?, ?, ?)",
        (title, category, message, posted_by, now_str)
    )
    conn.commit()
    conn.close()


def get_notices(category=None):
    init_notices_table()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    if category and category != "All":
        rows = conn.execute(
            "SELECT id, title, category, message, posted_by, created_at FROM notices WHERE category = ? ORDER BY id DESC",
            (category,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, title, category, message, posted_by, created_at FROM notices ORDER BY id DESC"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_notice(notice_id):
    init_notices_table()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM notices WHERE id = ?", (int(notice_id),))
    conn.commit()
    conn.close()


def init_email_logs_table():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS email_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipient_email TEXT NOT NULL,
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            delivery_mode TEXT NOT NULL,
            sent_by TEXT NOT NULL,
            sent_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def log_email_sent(recipient_email, subject, body, delivery_mode, sent_by):
    init_email_logs_table()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO email_logs (recipient_email, subject, body, delivery_mode, sent_by, sent_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (recipient_email, subject, body, delivery_mode, sent_by, now_str)
    )
    conn.commit()
    conn.close()


def get_email_logs():
    init_email_logs_table()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM email_logs ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def init_timetable_table():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS timetable (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            department TEXT NOT NULL,
            day_of_week TEXT NOT NULL,
            time_slot TEXT NOT NULL,
            subject TEXT NOT NULL,
            faculty_name TEXT NOT NULL,
            room_no TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def add_timetable_slot(department, day_of_week, time_slot, subject, faculty_name, room_no, created_by):
    init_timetable_table()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO timetable (department, day_of_week, time_slot, subject, faculty_name, room_no, created_by, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(department).strip(),
            str(day_of_week).strip(),
            str(time_slot).strip(),
            str(subject).strip(),
            str(faculty_name).strip(),
            str(room_no).strip(),
            str(created_by).strip(),
            now_str,
        )
    )
    conn.commit()
    conn.close()


def get_timetable_slots(day_of_week=None, department=None):
    init_timetable_table()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    query = "SELECT * FROM timetable WHERE 1=1"
    params = []
    if day_of_week and day_of_week != "All":
        query += " AND day_of_week = ?"
        params.append(day_of_week)
    if department and department != "All":
        query += " AND department = ?"
        params.append(department)
    query += " ORDER BY id DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_timetable_slot(slot_id):
    init_timetable_table()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM timetable WHERE id = ?", (int(slot_id),))
    conn.commit()
    conn.close()


def init_assignments_table():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            subject TEXT NOT NULL,
            department TEXT NOT NULL DEFAULT 'BCA (AI & DS)',
            due_date TEXT NOT NULL,
            description TEXT NOT NULL,
            posted_by TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS assignment_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id INTEGER NOT NULL,
            student_username TEXT NOT NULL,
            student_name TEXT NOT NULL,
            roll_no TEXT NOT NULL DEFAULT '',
            submission_note TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'Submitted',
            submitted_at TEXT NOT NULL,
            UNIQUE(assignment_id, student_username)
        )
    """)
    conn.commit()
    conn.close()


def add_assignment(title, subject, department, due_date, description, posted_by):
    init_assignments_table()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO assignments (title, subject, department, due_date, description, posted_by, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(title).strip(),
            str(subject).strip(),
            str(department).strip(),
            str(due_date).strip(),
            str(description).strip(),
            str(posted_by).strip(),
            now_str,
        )
    )
    conn.commit()
    conn.close()


def get_assignments(subject=None):
    init_assignments_table()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    if subject and subject != "All":
        rows = conn.execute(
            "SELECT * FROM assignments WHERE subject = ? ORDER BY id DESC",
            (subject,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM assignments ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_assignment(assignment_id):
    init_assignments_table()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM assignment_submissions WHERE assignment_id = ?", (int(assignment_id),))
    cursor.execute("DELETE FROM assignments WHERE id = ?", (int(assignment_id),))
    conn.commit()
    conn.close()


def upsert_assignment_submission(assignment_id, student_username, student_name, roll_no, submission_note, status="Submitted"):
    init_assignments_table()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO assignment_submissions (
            assignment_id, student_username, student_name, roll_no, submission_note, status, submitted_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(assignment_id, student_username) DO UPDATE SET
            student_name = excluded.student_name,
            roll_no = excluded.roll_no,
            submission_note = excluded.submission_note,
            status = excluded.status,
            submitted_at = excluded.submitted_at
        """,
        (
            int(assignment_id),
            str(student_username).strip(),
            str(student_name).strip(),
            str(roll_no).strip(),
            str(submission_note).strip(),
            str(status).strip(),
            now_str,
        )
    )
    conn.commit()
    conn.close()


def get_student_submissions_map(student_username):
    init_assignments_table()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM assignment_submissions WHERE student_username = ?",
        (str(student_username).strip(),)
    ).fetchall()
    conn.close()
    return {int(r["assignment_id"]): dict(r) for r in rows}


def get_all_submissions():
    init_assignments_table()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT s.id, s.assignment_id, a.title AS assignment_title, a.subject,
               s.student_name, s.roll_no, s.status, s.submission_note, s.submitted_at
        FROM assignment_submissions s
        LEFT JOIN assignments a ON s.assignment_id = a.id
        ORDER BY s.id DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]