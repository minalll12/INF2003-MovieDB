import streamlit as st

from backends import SORT_OPTIONS
from components import empty_state, html, page_title, paged_grid
from session import backend

RATING_BOUNDS = (0.0, 10.0)
MIN_REVIEWS_FOR_RATING_SORT = 3
FILTER_KEYS = ("browse_title", "browse_genres", "browse_years", "browse_ratings", "browse_sort")


def _clear_filters():
    for key in FILTER_KEYS:
        st.session_state.pop(key, None)


def _filters():
    years = backend().year_bounds()
    genres, year_range, rating_range, sort_by, clear = st.columns(
        [2.2, 1.6, 1.6, 1.4, 1.1], gap="medium", vertical_alignment="bottom"
    )
    with genres:
        st.multiselect("Genres", backend().genre_names(), key="browse_genres", placeholder="Any")
    with year_range:
        st.slider("Years", *years, value=years, key="browse_years")
    with rating_range:
        st.slider("Rating", *RATING_BOUNDS, value=RATING_BOUNDS, step=0.5, key="browse_ratings")
    with sort_by:
        st.selectbox("Sort", list(SORT_OPTIONS), key="browse_sort")
    with clear:
        st.button("✕ CLEAR", key="browse_clear", type="tertiary", on_click=_clear_filters)


def render():
    page_title("Browse")
    st.text_input(
        "Search", key="browse_title", label_visibility="collapsed",
        placeholder="Search every film…",
    )
    _filters()

    state = st.session_state
    criteria = (
        state["browse_title"].strip(), tuple(state["browse_genres"]),
        tuple(state["browse_years"]), tuple(state["browse_ratings"]), state["browse_sort"],
    )
    if state.get("browse_criteria") != criteria:
        state["browse_criteria"] = criteria
        state["browse_page"] = 1

    results = backend().search_movies(*criteria)
    rating_sort_active = state.get("browse_sort", "Highest rated") == "Highest rated"
    if rating_sort_active:
        results = results[results["review_count"] >= MIN_REVIEWS_FOR_RATING_SORT]
    count_line = f'{len(results)} FILM{"S" if len(results) != 1 else ""}'
    if rating_sort_active:
        count_line += f' · FILMS WITH FEWER THAN {MIN_REVIEWS_FOR_RATING_SORT} REVIEWS HIDDEN'
    html(f'<div class="mono" style="padding:4px 0 16px">{count_line}</div>')
    if results.empty:
        empty_state(
            "Nothing in the archive matches that combination.",
            "CLEAR FILTERS", _clear_filters, key="empty_clear",
        )
        return
    paged_grid(results, "browse_page")
