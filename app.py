import streamlit as st
import sqlite3
import pandas as pd
import hashlib

# ----- DB SETUP -----
conn = sqlite3.connect("sqlite.db", check_same_thread=False)
cursor = conn.cursor()

# Create user table if it doesn't exist
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    password TEXT NOT NULL
)
""")
conn.commit()

# ----- PASSWORD UTILS -----
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, hashed):
    return hash_password(password) == hashed

# ----- AUTH SYSTEM -----
def sign_up(username, password):
    try:
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hash_password(password)))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False

def login(username, password):
    cursor.execute("SELECT password FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    if row and verify_password(password, row[0]):
        return True
    return False

# ----- SESSION -----
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = None

# ----- LOGIN / SIGNUP PAGE -----
def login_signup_ui():
    st.title("Login / Sign Up")

    tab1, tab2 = st.tabs(["Login", "Sign Up"])

    with tab1:
        username = st.text_input("Username", key="login_user")
        password = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login"):
            if login(username, password):
                st.session_state.logged_in = True
                st.session_state.username = username
                st.success(f"Welcome back, {username}!")
                st.rerun()
            else:
                st.error("Invalid username or password.")

    with tab2:
        new_username = st.text_input("New Username", key="signup_user")
        new_password = st.text_input("New Password", type="password", key="signup_pass")
        if st.button("Sign Up"):
            if sign_up(new_username, new_password):
                st.success("Account created! You can now log in.")
                st.session_state.logged_in = True
                st.session_state.username = new_username
                st.rerun()
            else:
                st.error("Username already taken.")

# ----- MAIN APP -----
def main_app():
    st.title(f"Welcome, {st.session_state.username} 👋")

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall() if row[0] != 'users']

    if not tables:
        st.warning("No tables found in the database.")
        return

    selected_table = st.selectbox("Choose a table", tables)
    df = pd.read_sql_query(f"SELECT * FROM {selected_table}", conn)
    st.dataframe(df)

    if st.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.username = None
        st.rerun()

# ----- RENDER -----
if st.session_state.logged_in:
    main_app()
else:
    login_signup_ui()

conn.close()
