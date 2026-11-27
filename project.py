import os
import io
import csv
import sqlite3
import hashlib
import math
import smtplib
from email.message import EmailMessage
from datetime import datetime
from zoneinfo import ZoneInfo
import streamlit as st
import streamlit.components.v1 as components
from database import (
    create_table,
    add_student,
    update_student_marks,
    get_students,
    delete_student,
    init_notices_table,
    add_notice,
    get_notices,
    delete_notice,
    init_email_logs_table,
    log_email_sent,
    get_email_logs,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSS_PATH = os.path.join(BASE_DIR, "style.css")
DB_PATH = os.path.join(BASE_DIR, "data", "students.db")

JECRC_LOGO_URL = "https://jecrcuniversity.edu.in/wp-content/uploads/2023/02/Website-Logo-557x258-1-1-1-1024x505.webp"
CAMPUS_IMAGE_URL = "https://jecrcuniversity.edu.in/wp-content/uploads/2023/02/building-1.jpg"
ROTATING_IMG_URL = CAMPUS_IMAGE_URL

SOCIAL_LINKS = [
    ("IG", "instagram", "Instagram", "https://www.instagram.com/jecrcuniversity/", "@jecrcuniversity"),
    ("IN", "linkedin", "LinkedIn", "https://www.linkedin.com/school/jecrcuniversity/", "JECRC University"),
    ("YT", "youtube", "YouTube", "https://www.youtube.com/@jecrcuvideo", "@jecrcuvideo"),
    ("FB", "facebook", "Facebook", "https://www.facebook.com/JECRCUniversity/", "JECRC University, Rajasthan"),
    ("X", "x", "X", "https://x.com/jecrcuniversity", "@jecrcuniversity"),
]


def load_css():
    if os.path.exists(CSS_PATH):
        with open(CSS_PATH, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()


def init_auth_table():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            roll_no TEXT DEFAULT ''
        )
    """)
    defaults = [
        ("Admin User", "admin", hash_password("admin123"), "Admin", ""),
        ("Faculty User", "faculty", hash_password("faculty123"), "Faculty", ""),
        ("Student One", "student1", hash_password("student123"), "Student", "24BCA101"),
    ]
    for full_name, uname, pw_hash, role, roll in defaults:
        cursor.execute(
            "INSERT OR IGNORE INTO users (full_name, username, password, role, roll_no) VALUES (?, ?, ?, ?, ?)",
            (full_name, uname, pw_hash, role, roll)
        )
    conn.commit()
    conn.close()


def authenticate_user(username: str, password: str):
    init_auth_table()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, full_name, username, password, role, roll_no FROM users WHERE username = ?",
        (str(username).strip(),)
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    stored_pw = row[3]
    if stored_pw == password or stored_pw == hash_password(password):
        return {
            "id": row[0],
            "full_name": row[1],
            "username": row[2],
            "role": row[4],
            "roll_no": row[5] or "",
        }
    return None


def register_user(username: str, password: str, role: str, full_name: str, roll_no: str = ""):
    init_auth_table()
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (full_name, username, password, role, roll_no) VALUES (?, ?, ?, ?, ?)",
            (full_name.strip(), username.strip(), hash_password(password), role, roll_no.strip())
        )
        conn.commit()
        conn.close()
        return True, "Account registered successfully. Please login."
    except sqlite3.IntegrityError:
        return False, "Username already exists."
    except Exception as e:
        return False, f"Registration error: {e}"


def update_user_password(username: str, current_pw: str, new_pw: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT password FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False, "User record not found."

    stored_pw = row[0]
    matches = (stored_pw == current_pw) or (stored_pw == hash_password(current_pw))
    if not matches:
        conn.close()
        return False, "Current password is incorrect."

    updated_hash = hash_password(new_pw)
    cursor.execute("UPDATE users SET password = ? WHERE username = ?", (updated_hash, username))
    conn.commit()
    conn.close()
    return True, "Password updated successfully."


def get_all_users_rows():
    init_auth_table()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT id, full_name, username, role, roll_no FROM users ORDER BY id ASC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_user_role_in_db(target_user_id: int, new_role: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, int(target_user_id)))
    conn.commit()
    conn.close()


def delete_user_from_db(target_user_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = ?", (int(target_user_id),))
    conn.commit()
    conn.close()


def send_marks_email(recipient_email: str, subject: str, body: str, sent_by: str):
    smtp_cfg = {}
    try:
        if "smtp" in st.secrets:
            smtp_cfg = dict(st.secrets["smtp"])
    except Exception:
        smtp_cfg = {}

    host = smtp_cfg.get("host") or os.environ.get("SMTP_HOST", "")
    port = int(smtp_cfg.get("port") or os.environ.get("SMTP_PORT", 587))
    username = smtp_cfg.get("username") or os.environ.get("SMTP_USER", "")
    password = smtp_cfg.get("password") or os.environ.get("SMTP_PASS", "")
    sender = smtp_cfg.get("sender") or username or "noreply@jecrcuniversity.edu.in"

    if host and username and password:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = recipient_email
        msg.set_content(body)

        with smtplib.SMTP(host, port, timeout=15) as server:
            server.starttls()
            server.login(username, password)
            server.send_message(msg)

        log_email_sent(recipient_email, subject, body, "SMTP Sent", sent_by)
        return True, f"Email sent via SMTP to {recipient_email}."

    log_email_sent(recipient_email, subject, body, "Logged (Demo/No SMTP)", sent_by)
    return True, f"SMTP not configured; email details logged for {recipient_email}."


def dicts_to_csv_bytes(rows: list[dict], fieldnames: list[str] | None = None) -> bytes:
    if not rows:
        cols = fieldnames or ["id", "name", "roll_no", "department"]
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=cols)
        writer.writeheader()
        return buf.getvalue().encode("utf-8")

    cols = fieldnames or list(rows[0].keys())
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        writer.writerow({k: r.get(k, "") for k in cols})
    return buf.getvalue().encode("utf-8")


def import_students_from_csv_bytes(raw_bytes: bytes):
    text = raw_bytes.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return False, "CSV file has no headers."

    header_map = {str(h).strip().lower().replace(" ", "_"): h for h in reader.fieldnames if h}
    required_cols = {"name", "roll_no", "department"}
    if not required_cols.issubset(set(header_map.keys())):
        missing = sorted(list(required_cols - set(header_map.keys())))
        return False, f"Missing CSV columns: {', '.join(missing)}"

    def _get_val(row_dict, key, default_val):
        orig_h = header_map.get(key)
        if not orig_h:
            return default_val
        raw = str(row_dict.get(orig_h, "")).strip()
        if raw == "":
            return default_val
        return raw

    added_count = 0
    for r in reader:
        name = str(_get_val(r, "name", "")).strip()
        roll_no = str(_get_val(r, "roll_no", "")).strip()
        dept = str(_get_val(r, "department", "")).strip()
        if not name or not roll_no or not dept:
            continue

        base_mark = float(_get_val(r, "marks", 75.0))
        s1 = float(_get_val(r, "sem1_marks", base_mark))
        s2 = float(_get_val(r, "sem2_marks", base_mark))
        et = float(_get_val(r, "end_term_marks", base_mark))
        att = float(_get_val(r, "attendance", 80.0))
        hrs = float(_get_val(r, "study_hours", 12.0))
        email = str(_get_val(r, "email", "")).strip()

        add_student(
            name=name,
            roll_no=roll_no,
            department=dept,
            attendance=att,
            study_hours=hrs,
            sem1_marks=s1,
            sem2_marks=s2,
            end_term_marks=et,
            email=email,
        )
        added_count += 1

    if added_count == 0:
        return False, "No valid rows found in CSV."
    return True, f"Imported {added_count} student records successfully."


def predict_performance_fallback(att, marks, hours):
    return round((float(att) * 0.4) + (float(marks) * 0.45) + (min(float(hours) * 2.5, 100.0) * 0.15), 1)


def render_notices_board(can_manage: bool):
    selected_cat = st.selectbox(
        "Filter Notices by Category",
        ["All", "General", "Exam", "Event", "Urgent"],
        key="notice_category_filter"
    )
    notices = get_notices(selected_cat)

    if notices:
        for idx, row in enumerate(notices):
            cat = row.get("category") or "General"
            new_badge = '<span class="notice-new">LATEST</span>' if (idx == 0 and selected_cat == "All") else ""
            st.markdown(
                f'<div class="dash-card">'
                f'<div style="margin-bottom:6px;"><span class="notice-tag">{cat}</span>{new_badge}</div>'
                f'<div style="font-size:16px; font-weight:700; color:#f3b859;">{row["title"]}</div>'
                f'<div style="font-size:14px; color:#f3f4f6; margin-top:6px;">{row["message"]}</div>'
                f'<div style="font-size:12px; color:#cbd5e1; margin-top:8px;">By {row["posted_by"]} · {row["created_at"]}</div>'
                f'</div>',
                unsafe_allow_html=True
            )

        if can_manage:
            with st.expander("Delete Notice"):
                del_map = {
                    f"#{int(r['id'])} — {r['title']} ({r['category']})": int(r["id"])
                    for r in notices
                }
                chosen_notice = st.selectbox("Select Notice to Delete", list(del_map.keys()), key="del_notice_select")
                if st.button("Delete Selected Notice", key="btn_del_notice"):
                    delete_notice(del_map[chosen_notice])
                    st.success("Notice deleted.")
                    st.rerun()
    else:
        st.markdown(
            f'<div class="dash-card"><div style="color:#cbd5e1;">No notices found for category: <strong>{selected_cat}</strong>.</div></div>',
            unsafe_allow_html=True
        )


def render_campus_info_page():
    st.markdown(
        '<div class="dash-card">'
        '<div style="font-size:20px; font-weight:700; color:#f3b859;">JECRC University · Campus Directory</div>'
        '<div style="font-size:13.5px; color:#cbd5e1; margin-top:4px;">Build Your World — Jaipur | NCR Alwar · Founded: 2012, Jaipur</div>'
        '<div class="campus-meta-grid">'
        '<div><span class="meta-label">Phone:</span> 091166 42285</div>'
        '<div><span class="meta-label">Hours:</span> Opens at 8:00 AM</div>'
        '<div><span class="meta-label">School type:</span> Private university</div>'
        '<div><span class="meta-label">Colors:</span> White, Red</div>'
        '<div><span class="meta-label">Total enrollment:</span> 5,212 (2026)</div>'
        '</div>'
        '<div style="margin-top:12px; font-size:13.5px; color:#e5e7eb;">'
        '<strong>Address:</strong> Plot No. IS-2036 to 2039, Ramchandrapura Industrial Area, Vidhani, Sitapura Extension, Jaipur – 303905 Rajasthan, India'
        '</div>'
        '</div>',
        unsafe_allow_html=True
    )

    social_html_items = "".join(
        f'<a class="social-link" href="{url}" target="_blank" rel="noopener noreferrer" title="{platform}: {handle}">'
        f'<span class="social-icon-wrap">'
        f'<img class="social-icon-img" src="https://cdn.simpleicons.org/{slug}/f3b859" alt="{platform} logo" '
        f'onerror="this.style.display=\'none\'; this.nextElementSibling.style.display=\'inline-flex\';" />'
        f'<span class="social-badge" style="display:none;">{badge}</span>'
        f'</span>'
        f'<span>{platform}</span></a>'
        for badge, slug, platform, url, handle in SOCIAL_LINKS
    )
    st.markdown(
        f'<div class="social-strip">{social_html_items}</div>',
        unsafe_allow_html=True
    )


def _match_student_record(rows: list[dict], user_obj: dict) -> list[dict]:
    if not rows:
        return []
    roll_no = str(user_obj.get("roll_no") or "").strip().lower()
    full_name = str(user_obj.get("full_name") or "").strip().lower()

    if roll_no:
        matched = [r for r in rows if str(r.get("roll_no") or "").strip().lower() == roll_no]
        if matched:
            return matched

    if full_name:
        matched = [r for r in rows if str(r.get("name") or "").strip().lower() == full_name]
        if matched:
            return matched

    return []


st.set_page_config(
    page_title="IntelliCampus AI",
    page_icon="🎓",
    layout="wide"
)
load_css()

create_table()
init_auth_table()
init_notices_table()
init_email_logs_table()

if "user" not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    st.markdown('<div class="brand-bar">', unsafe_allow_html=True)
    logo_col, title_col = st.columns([0.22, 0.78], vertical_alignment="center")
    with logo_col:
        try:
            st.image(JECRC_LOGO_URL, use_container_width=True)
        except Exception:
            st.write("JECRC")
    with title_col:
        st.markdown('<div class="brand-name">JECRC University</div>', unsafe_allow_html=True)
        st.markdown('<div class="brand-sub">Build Your World — Jaipur | NCR Alwar</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    left_col, right_col = st.columns([1.25, 1], gap="large")

    with left_col:
        st.markdown('<div class="campus-frame">', unsafe_allow_html=True)
        try:
            st.image(CAMPUS_IMAGE_URL, use_container_width=True)
        except Exception:
            st.info("Could not load the campus image from the URL.")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown(
            '<div class="campus-info">'
            '<div><strong>JECRC University Campus:</strong> Plot No. IS-2036 to 2039, Ramchandrapura Industrial Area, Vidhani, Sitapura Extension, Jaipur – 303905 Rajasthan, India</div>'
            '<div class="campus-info-sub">Private University Estd. Under 2 (F) and 12(B) of UGC Act 1956 · Founded: 2012, Jaipur · Motto: Build Your World</div>'
            '<div class="campus-meta-grid">'
            '<div><span class="meta-label">Phone:</span> 091166 42285</div>'
            '<div><span class="meta-label">Hours:</span> Opens at 8:00 AM</div>'
            '<div><span class="meta-label">School type:</span> Private university</div>'
            '<div><span class="meta-label">Colors:</span> White, Red</div>'
            '<div><span class="meta-label">Total enrollment:</span> 5,212 (2026)</div>'
            '</div>'
            '</div>',
            unsafe_allow_html=True
        )

        social_html_items = "".join(
            f'<a class="social-link" href="{url}" target="_blank" rel="noopener noreferrer" title="{platform}: {handle}">'
            f'<span class="social-icon-wrap">'
            f'<img class="social-icon-img" src="https://cdn.simpleicons.org/{slug}/f3b859" alt="{platform} logo" '
            f'onerror="this.style.display=\'none\'; this.nextElementSibling.style.display=\'inline-flex\';" />'
            f'<span class="social-badge" style="display:none;">{badge}</span>'
            f'</span>'
            f'<span>{platform}</span></a>'
            for badge, slug, platform, url, handle in SOCIAL_LINKS
        )
        st.markdown(
            f'<div class="social-strip">{social_html_items}</div>',
            unsafe_allow_html=True
        )

    with right_col:
        st.markdown('<div class="login-card">', unsafe_allow_html=True)
        tab1, tab2 = st.tabs(["Login", "Register"])

        with tab1:
            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                login_btn = st.form_submit_button("Login", use_container_width=True)

                if login_btn:
                    user_data = authenticate_user(username, password)
                    if user_data:
                        st.session_state.user = user_data
                        st.rerun()
                    else:
                        st.error("Invalid username or password.")

            with st.expander("Demo Credentials"):
                st.write("Admin: admin / admin123")
                st.write("Faculty: faculty / faculty123")
                st.write("Student: student1 / student123")

        with tab2:
            with st.form("register_form"):
                full_name = st.text_input("Full Name")
                new_username = st.text_input("Username")
                new_password = st.text_input("Password", type="password")
                role = st.selectbox("Role", ["Student", "Faculty"])
                roll_no = st.text_input("Roll Number")
                reg_btn = st.form_submit_button("Register", use_container_width=True)

                if reg_btn:
                    if not full_name or not new_username or not new_password:
                        st.warning("Please fill in all required fields.")
                    elif role == "Student" and not roll_no:
                        st.warning("Roll number is required for students.")
                    else:
                        ok, msg = register_user(new_username, new_password, role, full_name, roll_no)
                        if ok:
                            st.success(msg)
                        else:
                            st.error(msg)
        st.markdown("</div>", unsafe_allow_html=True)

    st.stop()

user = st.session_state.user
st.markdown('<div class="dashboard-watermark"></div>', unsafe_allow_html=True)

now_ist = datetime.now(ZoneInfo("Asia/Kolkata"))
time_str = now_ist.strftime("%I:%M %p · %d %b %Y")
campus_open_status = "Campus Open (8:00 AM+)" if now_ist.hour >= 8 else "Opens at 8:00 AM"

st.markdown(
    f'<div class="top-status-bar">'
    f'<div class="spin-badge-wrap">'
    f'<img class="spin-img-360" src="{ROTATING_IMG_URL}" alt="Rotating Campus Emblem" />'
    f'<span class="spin-badge-text">IntelliCampus AI · JECRC Jaipur</span>'
    f'</div>'
    f'<div class="status-pills">'
    f'<span class="status-pill"><span class="status-dot"></span>{campus_open_status}</span>'
    f'<span class="status-pill">🕒 {time_str}</span>'
    f'<span class="status-pill">👤 {user["full_name"]} ({user["role"]})</span>'
    f'</div>'
    f'</div>',
    unsafe_allow_html=True
)

with st.sidebar:
    roll_line = f"<div style='font-size:12.5px; color:#cbd5e1; margin-top:4px;'>Roll No: {user['roll_no']}</div>" if user["roll_no"] else ""
    st.markdown(
        f"<div class='dash-card'>"
        f"<div style='font-size:16px; font-weight:700; color:#f3b859;'>{user['full_name']}</div>"
        f"<div style='font-size:13px; color:#e5e7eb; margin-top:2px;'>Role: {user['role']}</div>"
        f"{roll_line}"
        f"</div>",
        unsafe_allow_html=True
    )

    if user["role"] == "Admin":
        page = st.radio("Menu", [
            "Analytics",
            "Students",
            "CSV Import",
            "Prediction",
            "Notices",
            "Campus Info",
            "Users",
            "Profile"
        ])
    elif user["role"] == "Faculty":
        page = st.radio("Menu", [
            "Analytics",
            "Students",
            "Manage Marks",
            "CSV Import",
            "Prediction",
            "Notices",
            "Campus Info",
            "Profile"
        ])
    else:
        page = st.radio("Menu", [
            "My Record",
            "Semester Result",
            "Attendance Calculator",
            "Notices",
            "Campus Info",
            "Profile"
        ])

    st.divider()
    if st.button("Logout", use_container_width=True):
        st.session_state.user = None
        st.rerun()

if page == "Profile":
    p1, p2 = st.columns([1, 1.1], gap="large")
    with p1:
        st.markdown(
            f'<div class="dash-card">'
            f'<div style="font-size:18px; font-weight:700; color:#f3b859; margin-bottom:10px;">Account Details</div>'
            f'<div style="font-size:14px; color:#f3f4f6; margin-bottom:6px;"><strong>Full Name:</strong> {user.get("full_name", "")}</div>'
            f'<div style="font-size:14px; color:#f3f4f6; margin-bottom:6px;"><strong>Username:</strong> {user.get("username", "")}</div>'
            f'<div style="font-size:14px; color:#f3f4f6; margin-bottom:6px;"><strong>Role:</strong> {user.get("role", "")}</div>'
            f'<div style="font-size:14px; color:#f3f4f6;"><strong>Roll Number:</strong> {user.get("roll_no") or "N/A"}</div>'
            f'</div>',
            unsafe_allow_html=True
        )
    with p2:
        st.markdown('<div class="dash-card">', unsafe_allow_html=True)
        st.subheader("Change Password")
        with st.form("change_pw_form", clear_on_submit=True):
            curr_pw = st.text_input("Current Password", type="password")
            new_pw = st.text_input("New Password", type="password")
            conf_pw = st.text_input("Confirm New Password", type="password")
            save_pw = st.form_submit_button("Update Password")
            if save_pw:
                if not curr_pw or not new_pw or not conf_pw:
                    st.warning("Please fill in all password fields.")
                elif new_pw != conf_pw:
                    st.error("New password and confirm password do not match.")
                elif len(new_pw) < 6:
                    st.warning("New password should be at least 6 characters.")
                else:
                    ok, msg = update_user_password(user.get("username", ""), curr_pw, new_pw)
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)
        st.markdown("</div>", unsafe_allow_html=True)

elif page == "Campus Info":
    render_campus_info_page()

elif user["role"] in ["Admin", "Faculty"]:
    if page == "Analytics":
        rows = get_students()
        if rows:
            avg_s1 = sum(float(r.get("sem1_marks", 0.0)) for r in rows) / len(rows)
            avg_et = sum(float(r.get("end_term_marks", 0.0)) for r in rows) / len(rows)

            k1, k2, k3 = st.columns(3)
            with k1:
                st.markdown(
                    f'<div class="kpi-box"><div class="kpi-label">Total Students</div>'
                    f'<div class="kpi-value">{len(rows)}</div>'
                    f'<div class="kpi-sub">Active campus records</div></div>',
                    unsafe_allow_html=True
                )
            with k2:
                st.markdown(
                    f'<div class="kpi-box"><div class="kpi-label">Avg I Sem Marks</div>'
                    f'<div class="kpi-value">{avg_s1:.1f}%</div>'
                    f'<div class="kpi-sub">Semester I cohort average</div></div>',
                    unsafe_allow_html=True
                )
            with k3:
                st.markdown(
                    f'<div class="kpi-box"><div class="kpi-label">Avg End Term Marks</div>'
                    f'<div class="kpi-value">{avg_et:.1f}%</div>'
                    f'<div class="kpi-sub">End term examination standing</div></div>',
                    unsafe_allow_html=True
                )

            st.markdown('<div class="dash-card">', unsafe_allow_html=True)
            st.subheader("End Term Marks Overview")
            chart_map = {f"{r['name']} ({r['roll_no']})": float(r.get("end_term_marks", 0.0)) for r in rows}
            st.bar_chart(chart_map)
            st.markdown("</div>", unsafe_allow_html=True)

            st.dataframe(rows, use_container_width=True)
        else:
            st.markdown(
                '<div class="dash-card"><div style="color:#cbd5e1;">No student records found yet. Use <strong>Manage Marks</strong> or <strong>CSV Import</strong> to load records.</div></div>',
                unsafe_allow_html=True
            )

    elif page == "Students":
        st.markdown(
            '<div class="dash-card">'
            '<div style="font-size:18px; font-weight:700; color:#f3b859;">Student Directory (View Only)</div>'
            '<div style="font-size:13px; color:#cbd5e1; margin-top:2px;">Showing I Sem, II Sem, and End Term marks for review.</div>'
            '</div>',
            unsafe_allow_html=True
        )
        rows = get_students()
        if rows:
            c_search, c_filter = st.columns([2, 1])
            with c_search:
                search_q = st.text_input("Search students", placeholder="Type name, roll number, or department...")
            with c_filter:
                only_low_att = st.checkbox("Attendance < 75% (At-Risk)")

            filtered = rows
            if search_q:
                q_low = search_q.strip().lower()
                filtered = [
                    r for r in filtered
                    if any(q_low in str(v).lower() for v in r.values())
                ]
            if only_low_att:
                filtered = [r for r in filtered if float(r.get("attendance", 100.0)) < 75.0]

            st.dataframe(filtered, use_container_width=True)

            st.download_button(
                label="Export Filtered CSV",
                data=dicts_to_csv_bytes(filtered),
                file_name="intellicampus_students.csv",
                mime="text/csv"
            )
        else:
            st.info("No student records found.")

    elif page == "Manage Marks" and user["role"] == "Faculty":
        st.markdown('<div class="dash-card">', unsafe_allow_html=True)
        st.subheader("Add Student Marks (I Sem · II Sem · End Term)")
        with st.form("faculty_add_marks_form", clear_on_submit=True):
            f1, f2, f3 = st.columns(3)
            with f1:
                m_name = st.text_input("Student Name")
                m_roll = st.text_input("Roll Number")
            with f2:
                m_dept = st.text_input("Department / Branch", value="BCA (AI & DS)")
                m_email = st.text_input("Student Email (Optional)")
            with f3:
                m_att = st.number_input("Attendance (%)", min_value=0.0, max_value=100.0, value=82.0)
                m_hours = st.number_input("Weekly Study Hours", min_value=0.0, max_value=80.0, value=14.0)

            s1_col, s2_col, et_col = st.columns(3)
            with s1_col:
                m_sem1 = st.number_input("I Sem Marks (%)", min_value=0.0, max_value=100.0, value=78.0)
            with s2_col:
                m_sem2 = st.number_input("II Sem Marks (%)", min_value=0.0, max_value=100.0, value=81.0)
            with et_col:
                m_end = st.number_input("End Term Marks (%)", min_value=0.0, max_value=100.0, value=84.0)

            add_marks_btn = st.form_submit_button("Add Marks")
            if add_marks_btn:
                if m_name.strip() and m_roll.strip() and m_dept.strip():
                    add_student(
                        name=m_name.strip(),
                        roll_no=m_roll.strip(),
                        department=m_dept.strip(),
                        attendance=m_att,
                        study_hours=m_hours,
                        sem1_marks=m_sem1,
                        sem2_marks=m_sem2,
                        end_term_marks=m_end,
                        email=m_email.strip(),
                    )
                    st.success(f"Marks added for {m_name.strip()} ({m_roll.strip()}).")
                    st.rerun()
                else:
                    st.warning("Please enter Student Name, Roll Number, and Department.")
        st.markdown("</div>", unsafe_allow_html=True)

        student_rows = get_students()
        if student_rows:
            st.dataframe(student_rows, use_container_width=True)

            with st.expander("Update Existing Student Marks"):
                edit_map = {
                    f"ID {int(r['id'])} — {r['name']} ({r['roll_no']})": int(r["id"])
                    for r in student_rows
                }
                sel_edit_key = st.selectbox("Select Student", list(edit_map.keys()), key="fac_edit_sel")
                edit_id = edit_map[sel_edit_key]
                cur_r = next(r for r in student_rows if int(r["id"]) == edit_id)

                with st.form(f"fac_update_form_{edit_id}"):
                    u1, u2, u3 = st.columns(3)
                    with u1:
                        u_name = st.text_input("Name", value=str(cur_r.get("name", "")), key=f"f_uname_{edit_id}")
                        u_roll = st.text_input("Roll No", value=str(cur_r.get("roll_no", "")), key=f"f_uroll_{edit_id}")
                    with u2:
                        u_dept = st.text_input("Department", value=str(cur_r.get("department", "BCA (AI & DS)")), key=f"f_udept_{edit_id}")
                        u_email = st.text_input("Email", value=str(cur_r.get("email", "")), key=f"f_uemail_{edit_id}")
                    with u3:
                        u_att = st.number_input("Attendance (%)", 0.0, 100.0, float(cur_r.get("attendance", 80.0)), key=f"f_uatt_{edit_id}")
                        u_hrs = st.number_input("Study Hours", 0.0, 80.0, float(cur_r.get("study_hours", 12.0)), key=f"f_uhrs_{edit_id}")

                    us1, us2, uet = st.columns(3)
                    with us1:
                        u_s1 = st.number_input("I Sem Marks (%)", 0.0, 100.0, float(cur_r.get("sem1_marks", 75.0)), key=f"f_us1_{edit_id}")
                    with us2:
                        u_s2 = st.number_input("II Sem Marks (%)", 0.0, 100.0, float(cur_r.get("sem2_marks", 78.0)), key=f"f_us2_{edit_id}")
                    with uet:
                        u_et = st.number_input("End Term Marks (%)", 0.0, 100.0, float(cur_r.get("end_term_marks", 80.0)), key=f"f_uet_{edit_id}")

                    if st.form_submit_button("Save Updated Marks"):
                        update_student_marks(edit_id, u_name, u_roll, u_dept, u_s1, u_s2, u_et, u_att, u_hrs, u_email)
                        st.success(f"Updated marks for ID {edit_id}.")
                        st.rerun()

            st.markdown('<div class="dash-card">', unsafe_allow_html=True)
            st.subheader("Delete Student Marks Record")
            del_map = {
                f"ID {int(r['id'])} — {r['name']} ({r['roll_no']}) · Avg: {r.get('marks', '')}%": int(r["id"])
                for r in student_rows
            }
            sel_del_key = st.selectbox("Select Record to Delete", list(del_map.keys()), key="fac_del_sel")
            if st.button("Delete Marks Record", key="fac_btn_delete"):
                delete_student(del_map[sel_del_key])
                st.success("Student marks record deleted.")
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.info("No student records in database yet. Add a student record above.")

    elif page == "CSV Import":
        st.markdown('<div class="dash-card">', unsafe_allow_html=True)
        st.subheader("Bulk Import Students via CSV")
        st.caption("Columns supported: name, roll_no, department, email, sem1_marks, sem2_marks, end_term_marks, attendance, study_hours")

        sample_rows = [{
            "name": "Sample Student",
            "roll_no": "24BCA101",
            "department": "BCA (AI & DS)",
            "email": "student@jecrcuniversity.edu.in",
            "sem1_marks": 82.0,
            "sem2_marks": 85.0,
            "end_term_marks": 88.0,
            "attendance": 86.0,
            "study_hours": 15.0
        }]
        st.download_button(
            label="Download Sample CSV Template",
            data=dicts_to_csv_bytes(sample_rows),
            file_name="students_marks_template.csv",
            mime="text/csv"
        )

        uploaded_file = st.file_uploader("Upload CSV File", type=["csv"])
        if uploaded_file is not None:
            raw_bytes = uploaded_file.getvalue()
            preview_text = raw_bytes.decode("utf-8-sig", errors="replace")
            preview_rows = list(csv.DictReader(io.StringIO(preview_text)))[:10]
            if preview_rows:
                st.dataframe(preview_rows, use_container_width=True)
            if st.button("Import Records into Database"):
                ok, msg = import_students_from_csv_bytes(raw_bytes)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
        st.markdown("</div>", unsafe_allow_html=True)

    elif page == "Prediction":
        st.markdown('<div class="dash-card">', unsafe_allow_html=True)
        att_val = st.slider("Attendance (%)", 0, 100, 82)
        marks_val = st.slider("Internal Assessment (%)", 0, 100, 76)
        hours_val = st.slider("Weekly Study Hours", 0, 40, 14)

        readiness = predict_performance_fallback(att_val, marks_val, hours_val)
        st.metric("Predicted Performance", f"{readiness}%")
        st.progress(min(max(int(round(readiness)), 0), 100))
        st.markdown("</div>", unsafe_allow_html=True)

    elif page == "Notices":
        st.markdown('<div class="dash-card">', unsafe_allow_html=True)
        st.subheader("Post Campus Notice")
        with st.form("notice_form", clear_on_submit=True):
            n_col1, n_col2 = st.columns([2, 1])
            with n_col1:
                notice_title = st.text_input("Notice Title")
            with n_col2:
                notice_cat = st.selectbox("Category", ["General", "Exam", "Event", "Urgent"])
            notice_msg = st.text_area("Notice Message")
            submit_notice = st.form_submit_button("Publish Notice")
            if submit_notice:
                if notice_title.strip() and notice_msg.strip():
                    add_notice(notice_title.strip(), notice_msg.strip(), user["full_name"], notice_cat)
                    st.success("Notice published.")
                    st.rerun()
                else:
                    st.warning("Please enter both a title and a message.")
        st.markdown("</div>", unsafe_allow_html=True)

        render_notices_board(can_manage=True)

    elif page == "Users" and user["role"] == "Admin":
        users_rows = get_all_users_rows()
        st.dataframe(users_rows, use_container_width=True)

        if users_rows:
            u_col1, u_col2 = st.columns(2, gap="large")
            with u_col1:
                st.markdown('<div class="dash-card">', unsafe_allow_html=True)
                st.subheader("Update User Role")
                role_map = {
                    f"ID {int(r['id'])} — {r['full_name']} (@{r['username']}) · Current: {r['role']}": int(r["id"])
                    for r in users_rows
                }
                sel_role_user = st.selectbox("Select User", list(role_map.keys()), key="role_user_select")
                target_role_id = role_map[sel_role_user]
                target_user = next(r for r in users_rows if int(r["id"]) == target_role_id)
                curr_user_role = str(target_user["role"])
                role_choices = ["Student", "Faculty"]
                default_idx = role_choices.index(curr_user_role) if curr_user_role in role_choices else 0
                new_role = st.selectbox("New Role", role_choices, index=default_idx, key="new_role_select")
                if st.button("Save Role Change", key="btn_save_role"):
                    update_user_role_in_db(target_role_id, new_role)
                    st.success(f"Updated user ID {target_role_id} role to {new_role}.")
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

            with u_col2:
                st.markdown('<div class="dash-card">', unsafe_allow_html=True)
                st.subheader("Delete User Account")
                deletable_rows = [r for r in users_rows if str(r.get("username", "")) != str(user.get("username", ""))]
                if deletable_rows:
                    del_user_map = {
                        f"ID {int(r['id'])} — {r['full_name']} (@{r['username']}) [{r['role']}]": int(r["id"])
                        for r in deletable_rows
                    }
                    sel_del_user = st.selectbox("Select Account to Remove", list(del_user_map.keys()), key="del_user_select")
                    if st.button("Delete Account", key="btn_del_user"):
                        delete_user_from_db(del_user_map[sel_del_user])
                        st.success("User account removed.")
                        st.rerun()
                else:
                    st.info("No other user accounts available to delete.")
                st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="dash-card">', unsafe_allow_html=True)
        st.subheader("Send Student Marks via Email")
        student_rows = get_students()
        if student_rows:
            stu_map = {
                f"{r['name']} ({r['roll_no']}) — I Sem: {r.get('sem1_marks', 0)}% | II Sem: {r.get('sem2_marks', 0)}% | End Term: {r.get('end_term_marks', 0)}%": int(r["id"])
                for r in student_rows
            }
            chosen_stu_label = st.selectbox("Select Student Record", list(stu_map.keys()), key="admin_email_stu_sel")
            stu_id = stu_map[chosen_stu_label]
            stu_row = next(r for r in student_rows if int(r["id"]) == stu_id)

            default_email = str(stu_row.get("email") or "").strip()
            if not default_email:
                roll_clean = str(stu_row.get("roll_no") or "student").strip().lower().replace(" ", "")
                default_email = f"{roll_clean}@jecrcuniversity.edu.in"

            s1_val = float(stu_row.get("sem1_marks", 0.0))
            s2_val = float(stu_row.get("sem2_marks", 0.0))
            et_val = float(stu_row.get("end_term_marks", 0.0))
            avg_val = round((s1_val + s2_val + et_val) / 3.0, 2)

            default_subject = f"JECRC University · Marks Statement ({stu_row['name']} | {stu_row['roll_no']})"
            default_body = (
                f"Dear {stu_row['name']},\n\n"
                f"Here are your recorded academic marks from IntelliCampus AI (JECRC University):\n"
                f"- Roll Number: {stu_row['roll_no']}\n"
                f"- Department: {stu_row['department']}\n"
                f"- I Sem Marks: {s1_val:.1f}%\n"
                f"- II Sem Marks: {s2_val:.1f}%\n"
                f"- End Term Marks: {et_val:.1f}%\n"
                f"- Overall Average: {avg_val:.1f}%\n"
                f"- Attendance: {float(stu_row.get('attendance', 0.0)):.1f}%\n\n"
                f"Regards,\n"
                f"Administration · JECRC University"
            )

            with st.form("admin_send_marks_email_form"):
                to_email = st.text_input("Recipient Email", value=default_email)
                email_subj = st.text_input("Email Subject", value=default_subject)
                email_body = st.text_area("Email Body", value=default_body, height=180)
                send_btn = st.form_submit_button("Send Marks via Email")

                if send_btn:
                    if not to_email.strip() or "@" not in to_email:
                        st.warning("Please enter a valid recipient email address.")
                    elif not email_subj.strip() or not email_body.strip():
                        st.warning("Please enter both subject and message body.")
                    else:
                        try:
                            ok_mail, mail_msg = send_marks_email(
                                recipient_email=to_email.strip(),
                                subject=email_subj.strip(),
                                body=email_body.strip(),
                                sent_by=user.get("full_name", "Admin"),
                            )
                            if ok_mail:
                                st.success(mail_msg)
                                st.rerun()
                            else:
                                st.error(mail_msg)
                        except Exception as e:
                            st.error(f"Failed to send email: {e}")
        else:
            st.info("No student records available to email.")

        logs_rows = get_email_logs()
        if logs_rows:
            st.markdown("#### Sent / Logged Emails")
            st.dataframe(logs_rows, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

elif user["role"] == "Student":
    if page == "My Record":
        st.markdown(
            f'<div class="kpi-box"><div class="kpi-label">Student Profile (View Only)</div>'
            f'<div class="kpi-value">{user["full_name"]} ({user["roll_no"]})</div>'
            f'<div class="kpi-sub">JECRC University · I Sem, II Sem & End Term Marks</div></div>',
            unsafe_allow_html=True
        )
        rows = get_students()
        my_rows = _match_student_record(rows, user)

        if my_rows:
            rec = my_rows[0]
            s1 = float(rec.get("sem1_marks", 0.0))
            s2 = float(rec.get("sem2_marks", 0.0))
            et = float(rec.get("end_term_marks", 0.0))
            overall = round((s1 + s2 + et) / 3.0, 2)

            sec1, sec2, sec3 = st.columns(3, gap="medium")
            with sec1:
                st.markdown(
                    f'<div class="kpi-box"><div class="kpi-label">I Sem Marks</div>'
                    f'<div class="kpi-value">{s1:.1f}%</div>'
                    f'<div class="kpi-sub">Semester I Assessment</div></div>',
                    unsafe_allow_html=True
                )
            with sec2:
                st.markdown(
                    f'<div class="kpi-box"><div class="kpi-label">II Sem Marks</div>'
                    f'<div class="kpi-value">{s2:.1f}%</div>'
                    f'<div class="kpi-sub">Semester II Assessment</div></div>',
                    unsafe_allow_html=True
                )
            with sec3:
                st.markdown(
                    f'<div class="kpi-box"><div class="kpi-label">End Term Marks</div>'
                    f'<div class="kpi-value">{et:.1f}%</div>'
                    f'<div class="kpi-sub">Overall Avg: {overall:.1f}%</div></div>',
                    unsafe_allow_html=True
                )

            view_cols = ["name", "roll_no", "department", "sem1_marks", "sem2_marks", "end_term_marks", "marks", "attendance", "study_hours"]
            slim_rows = [{k: r.get(k, "") for k in view_cols if k in r} for r in my_rows]
            st.dataframe(slim_rows, use_container_width=True)
        else:
            st.info(f"No academic record matched Roll No: {user.get('roll_no') or 'N/A'}.")

    elif page == "Semester Result":
        st.markdown(
            f'<div class="dash-card">'
            f'<div style="font-size:19px; font-weight:700; color:#f3b859;">Semester-Wise Result & Printout</div>'
            f'<div style="font-size:13px; color:#cbd5e1; margin-top:2px;">Select a section to view your marks and print your result sheet.</div>'
            f'</div>',
            unsafe_allow_html=True
        )
        rows = get_students()
        my_rows = _match_student_record(rows, user)

        if my_rows:
            rec = my_rows[0]
            s1 = float(rec.get("sem1_marks", 0.0))
            s2 = float(rec.get("sem2_marks", 0.0))
            et = float(rec.get("end_term_marks", 0.0))
            overall = round((s1 + s2 + et) / 3.0, 2)

            section_choice = st.radio(
                "Select Result Section",
                ["All Semesters", "I Sem", "II Sem", "End Term"],
                horizontal=True,
                key="sem_result_choice"
            )

            rows_html = ""
            summary_rows = []
            if section_choice in ["All Semesters", "I Sem"]:
                status_s1 = "Pass" if s1 >= 40 else "Needs Improvement"
                rows_html += f"<tr><td>I Sem</td><td>{s1:.1f}%</td><td>{status_s1}</td></tr>"
                summary_rows.append({"Section": "I Sem", "Marks (%)": round(s1, 1), "Status": status_s1})
            if section_choice in ["All Semesters", "II Sem"]:
                status_s2 = "Pass" if s2 >= 40 else "Needs Improvement"
                rows_html += f"<tr><td>II Sem</td><td>{s2:.1f}%</td><td>{status_s2}</td></tr>"
                summary_rows.append({"Section": "II Sem", "Marks (%)": round(s2, 1), "Status": status_s2})
            if section_choice in ["All Semesters", "End Term"]:
                status_et = "Pass" if et >= 40 else "Needs Improvement"
                rows_html += f"<tr><td>End Term</td><td>{et:.1f}%</td><td>{status_et}</td></tr>"
                summary_rows.append({"Section": "End Term", "Marks (%)": round(et, 1), "Status": status_et})

            aggregate_line = (
                f"<div style='margin-top:12px; font-size:14px; color:#f3b859; font-weight:700;'>"
                f"Aggregate (I Sem + II Sem + End Term): {overall:.1f}%"
                f"</div>"
                if section_choice == "All Semesters"
                else ""
            )

            st.markdown(
                f'<div class="printable-sheet">'
                f'<div style="font-size:18px; font-weight:700; color:#f3b859;">JECRC University · Official Result View</div>'
                f'<div style="font-size:13px; color:#cbd5e1; margin-top:4px;">'
                f'<strong>Student:</strong> {rec.get("name", user["full_name"])} &nbsp;|&nbsp; '
                f'<strong>Roll No:</strong> {rec.get("roll_no", user.get("roll_no", ""))} &nbsp;|&nbsp; '
                f'<strong>Department:</strong> {rec.get("department", "")}'
                f'</div>'
                f'<table class="print-table">'
                f'<thead><tr><th>Examination Section</th><th>Marks</th><th>Status</th></tr></thead>'
                f'<tbody>{rows_html}</tbody>'
                f'</table>'
                f'{aggregate_line}'
                f'</div>',
                unsafe_allow_html=True
            )

            btn_c1, btn_c2 = st.columns([1, 1])
            with btn_c1:
                if st.button("Print Result", key="btn_print_result", use_container_width=True):
                    components.html("<script>window.parent.print();</script>", height=0)
            with btn_c2:
                st.download_button(
                    label="Download Result CSV",
                    data=dicts_to_csv_bytes(summary_rows, ["Section", "Marks (%)", "Status"]),
                    file_name=f"result_{rec.get('roll_no', 'student')}_{section_choice.lower().replace(' ', '_')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
        else:
            st.info(f"No semester marks found for Roll No: {user.get('roll_no') or 'N/A'}.")

    elif page == "Attendance Calculator":
        st.markdown('<div class="dash-card">', unsafe_allow_html=True)
        total = st.number_input("Total Classes", min_value=1, value=40)
        attended = st.number_input("Attended Classes", min_value=0, max_value=total, value=32)

        target_preset = st.radio(
            "Target Attendance (%)",
            [75, 80, 85, "Custom"],
            horizontal=True
        )
        if target_preset == "Custom":
            target_pct = float(st.number_input("Custom Target (%)", min_value=1.0, max_value=99.0, value=78.0, step=1.0))
        else:
            target_pct = float(target_preset)

        weekly_study_goal = st.slider("Weekly Study Goal (Hours)", min_value=2, max_value=50, value=15)
        daily_target_hrs = round(weekly_study_goal / 7, 1)

        pct = (attended / total) * 100
        target_ratio = target_pct / 100.0

        st.metric("Current Attendance", f"{pct:.2f}%")
        st.progress(min(max(int(round(pct)), 0), 100))

        if pct >= target_pct:
            if target_ratio < 1.0:
                safe_bunk = int(math.floor((attended - target_ratio * total) / target_ratio))
            else:
                safe_bunk = 0
            st.success(f"Target ({target_pct:.0f}%) achieved! Safe bunks available: {max(0, safe_bunk)} classes.")
        else:
            if target_ratio < 1.0:
                need = int(math.ceil((target_ratio * total - attended) / (1.0 - target_ratio)))
            else:
                need = 0
            st.error(f"To reach {target_pct:.0f}%, attend {max(0, need)} consecutive classes next.")

        st.markdown(
            f'<div class="kpi-box" style="margin-top:12px;">'
            f'<div class="kpi-label">Study Goal Plan</div>'
            f'<div class="kpi-value">{weekly_study_goal} hrs / week</div>'
            f'<div class="kpi-sub">Approx. {daily_target_hrs} hrs/day consistency target</div>'
            f'</div>',
            unsafe_allow_html=True
        )
        st.markdown("</div>", unsafe_allow_html=True)

    elif page == "Notices":
        render_notices_board(can_manage=False)