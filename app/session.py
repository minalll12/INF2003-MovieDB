import streamlit as st

from backends import ENGINES
from data_store import DataStore

DEFAULT_ENGINE = "MySQL (Relational)"

# Filled in by app.py so views can link to each other without circular imports.
pages = {}


@st.cache_resource(show_spinner=False)
def get_store():
    return DataStore()


@st.cache_resource
def get_engine(name):
    return ENGINES[name](get_store())


def engine_name():
    return st.session_state.setdefault("engine", DEFAULT_ENGINE)


def set_engine(source_key):
    choice = st.session_state[source_key]
    if not choice:
        return
    st.session_state["engine"] = choice
    for key in ("menu_engine", "bench_engine"):
        st.session_state[key] = choice


def backend():
    return get_engine(engine_name())


def current_user():
    return st.session_state.get("user")


def log_in(user):
    st.session_state["user"] = user


def log_out():
    for key in ("user", "selected_movie", "switch_user", "page_history"):
        st.session_state.pop(key, None)


def record_page(page_name):
    history = st.session_state.setdefault("page_history", [])
    entry = (page_name, st.session_state.get("selected_movie")) if page_name == "details" else (page_name, None)
    if not history or history[-1] != entry:
        history.append(entry)
        if len(history) > 50:
            history.pop(0)


def go_back():
    history = st.session_state.get("page_history", [])
    if len(history) > 1:
        history.pop()  # remove current active page
        prev_name, prev_movie = history[-1]
        if prev_movie is not None:
            st.session_state["selected_movie"] = prev_movie
        else:
            st.session_state.pop("selected_movie", None)
        st.switch_page(pages[prev_name])
    else:
        history.clear()
        st.session_state.pop("selected_movie", None)
        st.switch_page(pages["discover"])


def open_movie(movie_id):
    st.session_state["selected_movie"] = movie_id
    st.switch_page(pages["details"])


def open_browse(genre=None, sort_by=None):
    st.session_state["browse_title"] = ""
    st.session_state["browse_genres"] = [genre] if genre else []
    if sort_by:
        st.session_state["browse_sort"] = sort_by
    st.switch_page(pages["browse"])


def open_profile():
    st.switch_page(pages["profile"])


def open_benchmarks():
    st.switch_page(pages["benchmarks"])


def toggle_watchlist(movie_id):
    user = current_user()
    db = backend()
    if movie_id in db.watchlist_ids(user["user_id"]):
        db.remove_from_watchlist(user["user_id"], movie_id)
        st.toast("Removed from your watchlist")
    else:
        db.add_to_watchlist(user["user_id"], movie_id)
        st.toast("Saved to your watchlist", icon=":material/favorite:")
