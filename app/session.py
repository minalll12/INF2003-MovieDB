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
def _get_engine_cached(name, class_key):
    # class_key = "<module>.<qualname>" of ENGINES[name] at call time.
    # Including it in the cache key means a class change (e.g. CSV fallback →
    # real backend) produces a cache miss and a fresh instance.
    return ENGINES[name](get_store())


def get_engine(name):
    cls = ENGINES[name]
    return _get_engine_cached(name, f"{cls.__module__}.{cls.__qualname__}")


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
    # Only restore movie selection from URL — never restore user identity from URL parameters.
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


def get_back_target():
    history = st.session_state.get("page_history", [])
    prev_page = "discover"
    if len(history) > 1:
        for p, _ in reversed(history[:-1]):
            if p != "details" and p in ("discover", "browse", "watchlist"):
                prev_page = p
                break

    if prev_page == "browse":
        return "./browse", "browse"
    elif prev_page == "watchlist":
        return "./watchlist", "watchlist"
    else:
        return "./", "discover"


def go_back():
    history = st.session_state.get("page_history", [])
    if len(history) > 1:
        history.pop()
        prev_name, prev_movie = history[-1]
    else:
        history.clear()
        prev_name, prev_movie = "discover", None

    if prev_name == "details":
        prev_name = "discover"

    st.session_state.pop("selected_movie", None)
    st.query_params.pop("film", None)

    target = pages.get(prev_name) or pages.get("discover")
    if target:
        try:
            st.switch_page(target)
            return
        except BaseException:
            pass

    st.query_params.clear()
    if target:
        try:
            st.switch_page(target)
            return
        except BaseException:
            pass
    st.rerun()


def open_discover():
    target = pages.get("discover")
    if target:
        st.switch_page(target)


def open_movie(movie_id):
    st.session_state["selected_movie"] = movie_id
    target = pages.get("details")
    if target:
        st.switch_page(target, query_params={"film": str(movie_id)})


def open_browse(genre=None, sort_by=None):
    years = backend().year_bounds()
    st.session_state["browse_title"] = ""
    st.session_state["browse_genres"] = [genre] if genre else []
    st.session_state["browse_years"] = years
    st.session_state["browse_ratings"] = (0.0, 10.0)
    st.session_state["browse_sort"] = sort_by or "Highest rated"
    st.session_state["browse_page"] = 1
    target = pages.get("browse")
    if target:
        st.switch_page(target)


def open_profile():
    target = pages.get("profile")
    if target:
        st.switch_page(target)


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
