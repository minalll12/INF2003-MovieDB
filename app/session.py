from html import escape

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


def _user_qp():
    user = current_user()
    if user and isinstance(user, dict) and "username" in user:
        return {"user": str(user["username"])}
    if "user" in st.query_params:
        return {"user": str(st.query_params["user"])}
    return {}


def get_back_target():
    user = current_user()
    if user and isinstance(user, dict) and "username" in user:
        u_name = user["username"]
    elif "user" in st.query_params:
        u_name = st.query_params["user"]
    else:
        u_name = None
    user_param = f"?user={escape(str(u_name))}" if u_name else ""

    history = st.session_state.get("page_history", [])
    prev_page = "discover"
    if len(history) > 1:
        for p, _ in reversed(history[:-1]):
            if p != "details" and p in ("discover", "browse", "watchlist"):
                prev_page = p
                break

    if prev_page == "browse":
        return f"./browse{user_param}", "browse"
    elif prev_page == "watchlist":
        return f"./watchlist{user_param}", "watchlist"
    else:
        return f"./{user_param}", "discover"


def go_back():
    history = st.session_state.get("page_history", [])
    if len(history) > 1:
        history.pop()  # remove current active page (film details)
        prev_name, prev_movie = history[-1]
    else:
        history.clear()
        prev_name, prev_movie = "discover", None

    if prev_name == "details":
        prev_name = "discover"

    qp = _user_qp()
    st.session_state.pop("selected_movie", None)
    qp.pop("film", None)

    target = pages.get(prev_name) or pages.get("discover")
    if target:
        try:
            st.switch_page(target, query_params=qp)
            return
        except TypeError:
            try:
                st.switch_page(target)
                return
            except BaseException:
                pass
        except BaseException:
            pass

    st.query_params.clear()
    for k, v in qp.items():
        st.query_params[k] = v
    if target:
        try:
            st.switch_page(target)
            return
        except BaseException:
            pass
    st.rerun()


def open_discover():
    qp = _user_qp()
    target = pages.get("discover")
    if target:
        st.switch_page(target, query_params=qp)


def open_movie(movie_id):
    st.session_state["selected_movie"] = movie_id
    qp = _user_qp()
    qp["film"] = str(movie_id)
    target = pages.get("details")
    if target:
        st.switch_page(target, query_params=qp)


def open_browse(genre=None, sort_by=None):
    st.session_state["browse_title"] = ""
    st.session_state["browse_genres"] = [genre] if genre else []
    if sort_by:
        st.session_state["browse_sort"] = sort_by
    qp = _user_qp()
    target = pages.get("browse")
    if target:
        st.switch_page(target, query_params=qp)


def open_profile():
    qp = _user_qp()
    target = pages.get("profile")
    if target:
        st.switch_page(target, query_params=qp)


def open_benchmarks():
    target = pages.get("benchmarks")
    if target:
        st.switch_page(target)


def toggle_watchlist(movie_id):
    user = current_user()
    db = backend()
    if movie_id in db.watchlist_ids(user["user_id"]):
        db.remove_from_watchlist(user["user_id"], movie_id)
        st.toast("Removed from your watchlist")
    else:
        db.add_to_watchlist(user["user_id"], movie_id)
        st.toast("Saved to your watchlist", icon=":material/favorite:")
