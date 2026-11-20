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


def rehydrate_session():
    if not st.session_state.get("user") and "user" in st.query_params:
        db = backend()
        ident = str(st.query_params["user"]).strip()
        user = getattr(db, "get_user_by_username", lambda u: None)(ident)
        if not user:
            try:
                user = db.get_user(ident)
            except Exception:
                user = None
        if user:
            st.session_state["user"] = user
        else:
            st.query_params.pop("user", None)

    if not st.session_state.get("selected_movie") and "film" in st.query_params:
        film_id = str(st.query_params["film"]).strip()
        if film_id:
            st.session_state["selected_movie"] = film_id


def current_user():
    user = st.session_state.get("user")
    if user is None:
        rehydrate_session()
        user = st.session_state.get("user")
    return user


def log_in(user):
    st.session_state["user"] = user
    if user and isinstance(user, dict) and "username" in user:
        st.query_params["user"] = user["username"]


def log_out():
    for key in ("user", "selected_movie", "switch_user", "page_history"):
        st.session_state.pop(key, None)
    st.query_params.clear()


def record_page(page_name):
    history = st.session_state.setdefault("page_history", [])
    entry = (page_name, st.session_state.get("selected_movie")) if page_name == "details" else (page_name, None)
    if not history or history[-1] != entry:
        history.append(entry)
        if len(history) > 50:
            history.pop(0)
    if page_name != "details":
        st.query_params.pop("film", None)
    else:
        movie_id = st.session_state.get("selected_movie")
        if movie_id:
            st.query_params["film"] = str(movie_id)


def go_back():
    user = current_user()
    history = st.session_state.get("page_history", [])
    if len(history) > 1:
        history.pop()  # remove current active page
        prev_name, prev_movie = history[-1]
        if prev_movie is not None:
            st.session_state["selected_movie"] = prev_movie
            st.query_params["film"] = str(prev_movie)
        else:
            st.session_state.pop("selected_movie", None)
            st.query_params.pop("film", None)
        target = pages.get(prev_name)
        if target:
            try:
                st.switch_page(target)
                return
            except Exception:
                pass
    history.clear()
    st.session_state.pop("selected_movie", None)
    st.query_params.pop("film", None)
    if user and "discover" in pages:
        try:
            st.switch_page(pages["discover"])
            return
        except Exception:
            pass
    st.query_params.clear()
    st.rerun()


def open_discover():
    st.switch_page(pages["discover"])


def open_movie(movie_id):
    st.session_state["selected_movie"] = movie_id
    st.query_params["film"] = str(movie_id)
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
