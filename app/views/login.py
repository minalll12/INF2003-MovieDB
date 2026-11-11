import re
from html import escape

import streamlit as st

from components import html
from session import backend, log_in

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.]{3,30}$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LENGTH = 8
WALL_SIZE = 48


def _poster_wall():
    # Pull a larger pool than we need, drop any movie without a poster, then
    # cycle the remaining ones to fill every tile — otherwise a missing
    # poster_large leaves a bare black rectangle in the grid.
    pool = backend().most_voted(WALL_SIZE * 5)["poster_large"]
    _skip = {"", "none", "nan", "null", "n/a"}
    urls = [s for url in pool if (s := str(url).strip()) and s.lower() not in _skip]
    if not urls:
        html('<div class="wall"><div class="wall-veil"></div></div>')
        return
    while len(urls) < WALL_SIZE * 2:
        urls += urls
    primary = urls[:WALL_SIZE]
    # Offset backup by WALL_SIZE so each tile has a different movie as its fallback.
    backup = urls[WALL_SIZE: WALL_SIZE * 2]
    art = "".join(
        f'<div class="art" style="background-image:url(\'{escape(p)}\'),url(\'{escape(b)}\'),linear-gradient(135deg,#3d2d1a,#291d10)"></div>'
        for p, b in zip(primary, backup)
    )
    html(f'<div class="wall"><div class="wall-grid">{art}</div><div class="wall-veil"></div></div>')


def _masthead():
    html(
        '<div class="masthead-plate">'
        '<div class="rule"></div>'
        '<div class="name">Reel<em>house</em></div>'
        '<div class="rule"></div>'
        '<div class="tagline">Your next favourite film.</div>'
        "</div>"
    )


def _sign_in():
    username = st.text_input("Username", key="login_username")
    password = st.text_input("Password", type="password", key="login_password")
    if not st.button("SIGN IN →", type="primary", width="stretch", key="do_sign_in"):
        return
    user = backend().authenticate(username, password)
    if user is None:
        st.error("That username and password don't match our records.")
        return
    log_in(user)
    st.rerun()


def _registration_error(username, email, password, confirm):
    db = backend()
    if not USERNAME_PATTERN.match(username):
        return "Usernames are 3–30 characters: letters, numbers, dots or underscores."
    if db.username_taken(username):
        return "That username is already taken."
    if not EMAIL_PATTERN.match(email):
        return "Please enter a valid email address."
    if db.email_taken(email):
        return "An account with that email already exists."
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Passwords need at least {MIN_PASSWORD_LENGTH} characters."
    if password != confirm:
        return "The two passwords don't match."
    return None


def _create_account():
    username = st.text_input("Username", key="reg_username").strip()
    email = st.text_input("Email", key="reg_email").strip()
    password = st.text_input("Password", type="password", key="reg_password")
    confirm = st.text_input("Confirm password", type="password", key="reg_confirm")
    if not st.button("CREATE ACCOUNT →", type="primary", width="stretch", key="do_register"):
        return
    error = _registration_error(username, email, password, confirm)
    if error:
        st.error(error)
        return
    try:
        user = backend().register_user(username, email, password)
    except OSError:
        st.error("We couldn't save your account right now. Please try again.")
        return
    log_in(user)
    st.rerun()


def _demo_entry():
    with st.container(key="demo_entry"):
        with st.expander("Browse as a demo user"):
            users = backend().list_users()
            with st.form("demo_form"):
                choice = st.selectbox("Account", users["username"], index=None,
                                      placeholder="Choose an account")
                submitted = st.form_submit_button("ENTER →", type="primary",
                                                  use_container_width=True)
            if submitted:
                if choice is None:
                    st.error("Please select an account first.")
                    return
                try:
                    user_id = users.loc[users["username"] == choice, "user_id"].iloc[0]
                    user = backend().get_user(user_id)
                    if user is None:
                        st.error("Could not load that account. Please try another.")
                        return
                    log_in(user)
                    st.rerun()
                except OSError:
                    st.error("Database connection error. Please try again.")


def render():
    _poster_wall()
    _masthead()
    _, middle, _ = st.columns([1, 1.1, 1])
    with middle:
        with st.container(key="auth_panel"):
            sign_in, create = st.tabs(["SIGN IN", "CREATE ACCOUNT"])
            with sign_in:
                _sign_in()
            with create:
                _create_account()
        _demo_entry()
