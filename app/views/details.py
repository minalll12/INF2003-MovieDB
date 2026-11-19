from html import escape

import pandas as pd
import streamlit as st

from components import (
    empty_state,
    genre_tags,
    html,
    poster_frame,
    review_dialog,
    review_row,
    section_head,
)
from session import backend, current_user, open_browse, toggle_watchlist


def _backdrop(movie):
    raw_art = movie.get("poster_large")
    if raw_art is None or pd.isna(raw_art) or str(raw_art).strip().lower() in ("", "none", "nan"):
        art_style = ""
    else:
        art_style = f"background-image:url('{escape(str(raw_art).strip())}')"
    html(
        '<div class="backdrop">'
        f'<div class="art" style="{art_style}"></div>'
        '<div class="veil"></div></div>'
    )


def _rating_block(movie):
    if pd.isna(movie["avg_rating"]):
        return '<div class="detail-rating"><span class="of">NOT YET RATED</span></div>'
    count = movie["review_count"]
    return (
        '<div class="detail-rating">'
        f'<span class="score">★ {movie["avg_rating"]:.1f}</span>'
        f'<span class="of">/10 · FROM {count} REVIEW{"S" if count != 1 else ""}</span></div>'
    )


def _header(movie):
    with st.container(key="detail_block"):
        poster, info = st.columns([1, 2.2], gap="large")
        with poster:
            html(poster_frame(movie, class_name="detail-poster"))
        with info:
            html(
                f'<div class="eyebrow">{escape(", ".join(movie["genres"]) or "Uncategorised")}</div>'
                f'<div class="detail-title">{escape(movie["title"])}</div>'
                f'<div class="hero-meta">{movie["release_year"]} · '
                f'{escape(str(movie["certificate"]))} · {movie["duration"]} MIN</div>'
                + _rating_block(movie)
                + f'<p class="detail-desc">{escape(movie["description"])}</p>'
                + f'<div class="credit"><div class="label">Director</div>'
                f'<div class="value">{escape(movie["director"])}</div></div>'
                f'<div class="credit"><div class="label">Cast</div>'
                f'<div class="value">{escape(movie["cast"])}</div></div>'
                + genre_tags(movie["genres"])
            )
            saved = movie["movie_id"] in backend().watchlist_ids(current_user()["user_id"])
            st.button(
                "♥ ON YOUR WATCHLIST" if saved else "♡ ADD TO WATCHLIST",
                key="detail_save",
                on_click=toggle_watchlist,
                args=(movie["movie_id"],),
            )


def _reviews(movie):
    user_id = current_user()["user_id"]
    reviews = backend().movie_reviews(movie["movie_id"])
    mine = backend().user_review_for(user_id, movie["movie_id"])
    label = "EDIT YOUR REVIEW →" if mine else "WRITE A REVIEW →"
    section_head(
        f"REVIEWS ({len(reviews)})", label, "write_review",
        lambda: review_dialog(movie["movie_id"], mine),
    )
    if reviews.empty:
        empty_state("No one has written about this one yet.")
        return
    ordered = pd.concat([reviews[reviews["user_id"] == user_id], reviews[reviews["user_id"] != user_id]])
    for _, review in ordered.iterrows():
        review_row(review, "film")


def render():
    movie_id = st.session_state.get("selected_movie")
    movie = backend().get_movie(movie_id) if movie_id else None
    if movie is None:
        empty_state("Pick a film to read about it.", "BROWSE FILMS →", open_browse, key="no_film")
        return
    html(
        '<script>try{'
        'var c=window.parent.document.querySelector("[data-testid=stAppViewBlockWrapper]")'
        '||window.parent.document.documentElement;'
        'c.scrollTop=0;'
        '}catch(e){}</script>'
    )
    _backdrop(movie)
    _header(movie)
    st.write("")
    _reviews(movie)