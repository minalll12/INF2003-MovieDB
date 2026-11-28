import re
from html import escape

import streamlit as st
import streamlit.components.v1 as components

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
    with st.form("sign_in_form", clear_on_submit=False, border=False):
        username = st.text_input("Username", key="login_username", autocomplete="username")
        password = st.text_input("Password", type="password", key="login_password", autocomplete="current-password")
        submitted = st.form_submit_button("SIGN IN →", type="primary", width="stretch")
    if not submitted:
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
    with st.form("create_account_form", clear_on_submit=False, border=False):
        username = st.text_input("Username", key="reg_username", autocomplete="username").strip()
        email = st.text_input("Email", type="email", key="reg_email", autocomplete="email").strip()
        password = st.text_input("Password", type="password", key="reg_password", autocomplete="new-password")
        confirm = st.text_input("Confirm password", type="password", key="reg_confirm", autocomplete="new-password")
        submitted = st.form_submit_button("CREATE ACCOUNT →", type="primary", width="stretch")
    if not submitted:
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


def _inject_autofill_script():
    components.html(
        """
        <script>
        (function() {
            function applyAutofillAttributes() {
                try {
                    var doc = window.parent.document;
                    if (!doc) return;

                    var configs = [
                        {
                            find: function() {
                                return doc.querySelector('[class*="st-key-login_username"] input') ||
                                       doc.querySelector('input[aria-label="Username"]');
                            },
                            name: 'username',
                            autocomplete: 'username',
                            id: 'username'
                        },
                        {
                            find: function() {
                                return doc.querySelector('[class*="st-key-login_password"] input') ||
                                       doc.querySelector('input[aria-label="Password"]');
                            },
                            name: 'password',
                            autocomplete: 'current-password',
                            id: 'password'
                        },
                        {
                            find: function() {
                                return doc.querySelector('[class*="st-key-reg_username"] input');
                            },
                            name: 'username',
                            autocomplete: 'username',
                            id: 'reg_username'
                        },
                        {
                            find: function() {
                                return doc.querySelector('[class*="st-key-reg_email"] input') ||
                                       doc.querySelector('input[aria-label="Email"]');
                            },
                            name: 'email',
                            autocomplete: 'email',
                            type: 'email',
                            id: 'reg_email'
                        },
                        {
                            find: function() {
                                return doc.querySelector('[class*="st-key-reg_password"] input');
                            },
                            name: 'new-password',
                            autocomplete: 'new-password',
                            id: 'reg_password'
                        },
                        {
                            find: function() {
                                return doc.querySelector('[class*="st-key-reg_confirm"] input') ||
                                       doc.querySelector('input[aria-label="Confirm password"]');
                            },
                            name: 'confirm-password',
                            autocomplete: 'new-password',
                            id: 'reg_confirm'
                        }
                    ];

                    configs.forEach(function(cfg) {
                        var el = cfg.find();
                        if (el) {
                            if (cfg.name && el.getAttribute('name') !== cfg.name) el.setAttribute('name', cfg.name);
                            if (cfg.autocomplete && el.getAttribute('autocomplete') !== cfg.autocomplete) el.setAttribute('autocomplete', cfg.autocomplete);
                            if (cfg.id && (!el.id || el.id.indexOf('text_input') !== -1)) el.setAttribute('id', cfg.id);
                            if (cfg.type && el.getAttribute('type') !== cfg.type) el.setAttribute('type', cfg.type);
                        }
                    });

                    // Ensure forms have method="POST" for browser password manager detection
                    var forms = doc.querySelectorAll('form[data-testid="stForm"]');
                    forms.forEach(function(f) {
                        if (!f.getAttribute('method')) f.setAttribute('method', 'POST');
                        if (!f.getAttribute('action')) f.setAttribute('action', '#');
                        if (!f._hasAutofillSubmit) {
                            f._hasAutofillSubmit = true;
                            f.addEventListener('submit', function() {
                                var inputs = f.querySelectorAll('input');
                                inputs.forEach(function(inp) {
                                    inp.dispatchEvent(new Event('input', { bubbles: true }));
                                    inp.dispatchEvent(new Event('change', { bubbles: true }));
                                });
                                var u = f.querySelector('input[autocomplete="username"]');
                                var p = f.querySelector('input[type="password"]');
                                if (u && p && u.value && p.value && window.parent.PasswordCredential && window.parent.navigator.credentials) {
                                    try {
                                        var cred = new window.parent.PasswordCredential({
                                            id: u.value,
                                            password: p.value,
                                            name: u.value
                                        });
                                        window.parent.navigator.credentials.store(cred);
                                    } catch(err) {}
                                }
                            }, true);
                        }
                    });
                } catch(e) {}
            }

            applyAutofillAttributes();
            if (window.parent && !window.parent._autofillObserver) {
                try {
                    var doc = window.parent.document;
                    window.parent._autofillObserver = new MutationObserver(applyAutofillAttributes);
                    window.parent._autofillObserver.observe(doc.body, { childList: true, subtree: true });
                } catch(e) {}
            }
            setInterval(applyAutofillAttributes, 200);
        })();
        </script>
        """,
        height=0,
        width=0,
    )


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
    _inject_autofill_script()
