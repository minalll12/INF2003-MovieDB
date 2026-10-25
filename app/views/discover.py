from html import escape

import pandas as pd
import streamlit as st

from components import (
    html,
    poster_frame,
    poster_grid,
    score_text,
    section_head,
    stars,
)
from session import backend, current_user, open_browse, open_movie, toggle_watchlist

MIN_REVIEWS = 3
ROW_SIZE = 5


def _genre_strip():
    genres = backend().genre_names()
    pills = "".join(
        f'<span class="genre-pill">{escape(g.upper())}</span>' for g in genres
    )
    html(
        '<div class="genre-scroll-wrap">'
        f'<div class="genre-scroll">{pills}</div>'
        '</div>'
    )


def _editorial_section(movies):
    html('<div class="double-rule" style="margin:48px 0 0"></div>')
    html('<div class="editorial-label">EDITOR\'S PICKS</div>')
    html('<div class="editorial-title">This Week on Reelhouse</div>')
    st.write("")
    saved_ids = backend().watchlist_ids(current_user()["user_id"])
    slots = st.columns(3, gap="large")
    for slot, (_, movie) in zip(slots, movies.iterrows()):
        with slot:
            movie_id = movie["movie_id"]
            desc = str(movie.get("description", "") or "")
            snippet = (desc[:110].rstrip() + "…") if len(desc) > 110 else desc
            rating_text = score_text(movie["avg_rating"])
            saved = movie_id in saved_ids
            with st.container(key=f"card_editorial_{movie_id}"):
                html(poster_frame(movie))
                if st.button(movie["title"], key=f"editorial_open_{movie_id}", type="tertiary"):
                    open_movie(movie_id)
                meta_col, save_col = st.columns([4, 1], vertical_alignment="center")
                with meta_col:
                    html(
                        '<div class="card-meta">'
                        f'<span>{movie["release_year"]}</span>'
                        f'<span class="score">{escape(rating_text)}</span></div>'
                    )
                with save_col:
                    with st.container(key=f"save_editorial_{movie_id}"):
                        st.button(
                            "♥" if saved else "♡",
                            key=f"savebtn_editorial_{movie_id}",
                            help="Remove from watchlist" if saved else "Save to watchlist",
                            on_click=toggle_watchlist,
                            args=(movie_id,),
                        )
                if snippet:
                    html(f'<p class="editorial-blurb">{escape(snippet)}</p>')


def _poster_row(movies, prefix, title, sort_by):
    section_head(title, "See all →", f"all_{prefix}", lambda: open_browse(sort_by=sort_by))
    poster_grid(movies.head(ROW_SIZE), prefix, columns=ROW_SIZE)


def _fresh_reviews():
    section_head("No. 03 — FRESH REVIEWS", "See all →", "all_fresh", lambda: open_browse(sort_by="Newest"))
    reviews = backend().latest_reviews(ROW_SIZE)
    slots = st.columns(ROW_SIZE, gap="medium")
    for slot, (_, review) in zip(slots, reviews.iterrows()):
        with slot:
            with st.container(key=f"fresh_{review['review_id']}"):
                html(poster_frame(review))
                if st.button(review["title"], key=f"freshopen_{review['review_id']}", type="tertiary"):
                    open_movie(review["movie_id"])
                html(
                    f'<div class="review-who">{escape(str(review["username"]))}</div>'
                    f'{stars(review["rating"])}'
                )


def render():
    db = backend()
    top_picks = db.well_rated(MIN_REVIEWS).head(3)
    _editorial_section(top_picks)
    _genre_strip()
    _poster_row(db.well_rated(MIN_REVIEWS), "top", "No. 01 — TOP RATED", "Highest rated")
    _poster_row(db.most_reviewed(), "disc", "No. 02 — MOST DISCUSSED", "Most reviewed")
    _fresh_reviews()
