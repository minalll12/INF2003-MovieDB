from html import escape

import streamlit as st

from backends import ENGINES
from components import html
from session import (
    backend,
    current_user,
    engine_name,
    get_store,
    log_in,
    log_out,
    pages,
    set_engine,
)
from styles import apply_theme
from views import benchmarks, browse, details, discover, login, profile, watchlist

APP_NAME = "Reelhouse"
WORDMARK = 'Reel<em>house</em>'
NAV_LINKS = "DISCOVER<span>·</span>BROWSE<span>·</span>WATCHLIST<span>·</span>PROFILE"


def build_pages():
    pages.update({
        "discover": st.Page(discover.render, title="Discover", url_path="discover", default=True),
        "browse": st.Page(browse.render, title="Browse", url_path="browse"),
        "watchlist": st.Page(watchlist.render, title="Watchlist", url_path="watchlist"),
        "profile": st.Page(profile.render, title="Profile", url_path="profile"),
        "details": st.Page(details.render, title="Film", url_path="film", visibility="hidden"),
        "benchmarks": st.Page(benchmarks.render, title="Performance", url_path="performance", visibility="hidden"),
    })


def switch_user():
    users = backend().list_users()
    chosen = st.session_state["switch_user"]
    user_id = users.loc[users["username"] == chosen, "user_id"].iloc[0]
    log_in(backend().get_user(user_id))
    st.session_state.pop("selected_movie", None)


def reset_demo_data():
    get_store().reset()
    st.toast("Demo data restored")


def account_menu(user):
    with st.popover(user["username"], icon=":material/person:"):
        html(f'<div class="mono">{escape(user["email"])}</div>')
        usernames = backend().list_users()["username"].tolist()
        st.session_state["switch_user"] = user["username"]
        st.selectbox("Switch user", usernames, key="switch_user", on_change=switch_user)

        html('<div class="double-rule" style="margin:8px 0 16px"></div>')
        st.session_state.setdefault("menu_engine", engine_name())
        st.segmented_control(
            "Data source", list(ENGINES), key="menu_engine",
            format_func=lambda name: name.split(" ")[0].upper(),
            on_change=set_engine, args=("menu_engine",),
        )
        st.page_link(pages["benchmarks"], label="Performance comparison")
        st.button("Reset demo data", type="tertiary", on_click=reset_demo_data)
        if st.button("Log out", type="tertiary"):
            log_out()
            st.rerun()


def masthead(user):
    with st.container(key="wordmark"):
        html(f'<span class="wordmark">{WORDMARK}</span>')
    with st.container(key="account"):
        account_menu(user)


def footer():
    html(
        '<div class="footer"><div class="double-rule"></div>'
        f'<div class="footer-row"><span class="wordmark">{WORDMARK}</span>'
        f'<span class="links">{NAV_LINKS}</span>'
        '<span class="links">© 2026 Reelhouse</span></div></div>'
    )


def main():
    st.set_page_config(page_title=APP_NAME, page_icon="◆", layout="wide")
    apply_theme()
    try:
        get_store()
    except (OSError, ValueError) as error:
        st.error(f"Couldn't load the film data: {error}")
        st.stop()

    user = current_user()
    if user is None:
        st.navigation([st.Page(login.render, url_path="welcome")], position="hidden").run()
        return

    build_pages()
    navigation = st.navigation(list(pages.values()), position="top")
    masthead(user)
    navigation.run()
    footer()


if __name__ == "__main__":
    main()
