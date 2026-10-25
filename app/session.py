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
    for key in ("user", "selected_movie"):
        st.session_state.pop(key, None)


def open_movie(movie_id):
    st.session_state["selected_movie"] = movie_id
    st.switch_page(pages["details"])


def open_browse(genre=None, sort_by=None):
    st.session_state["browse_title"] = ""
    st.session_state["browse_genres"] = [genre] if genre else []
    if sort_by:
        st.session_state["browse_sort"] = sort_by
    st.switch_page(pages["browse"])


def toggle_watchlist(movie_id):
    user = current_user()
    db = backend()
    if movie_id in db.watchlist_ids(user["user_id"]):
        db.remove_from_watchlist(user["user_id"], movie_id)
        st.toast("Removed from your watchlist")
    else:
        db.add_to_watchlist(user["user_id"], movie_id)
        st.toast("Saved to your watchlist", icon=":material/favorite:")
