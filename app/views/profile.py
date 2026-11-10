from collections import Counter
from datetime import datetime
from html import escape

import pandas as pd
import streamlit as st

from components import (
    empty_state,
    html,
    paginate,
    pagination,
    poster_grid,
    review_row,
    section_head,
)
from session import backend, current_user, open_browse

FAVOURITE_COUNT = 4


def _initials(username):
    letters = [part[0] for part in username.replace(".", " ").replace("_", " ").split() if part]
    return "".join(letters[:2]).upper() or username[:2].upper()


def _member_since(user_id):
    stamp = backend().member_since(user_id)
    if not stamp:
        return ""
    return datetime.strptime(str(stamp), "%Y-%m-%d %H:%M:%S").strftime("%B %Y").upper()


def _banner(user, favourites):
    art = favourites.iloc[0]["poster_large"] if not favourites.empty else ""
    html(
        '<div class="backdrop">'
        f'<div class="art" style="background-image:url(\'{escape(str(art))}\')"></div>'
        '<div class="veil"></div></div>'
    )
    with st.container(key="profile_head"):
        avatar, name = st.columns([1, 6], gap="medium", vertical_alignment="center")
        with avatar:
            html(f'<div class="avatar">{escape(_initials(user["username"]))}</div>')
        with name:
            html(
                f'<div class="page-title" style="margin:0">{escape(user["username"])}</div>'
                f'<div class="label">MEMBER SINCE {_member_since(user["user_id"])}</div>'
            )


def _stats(reviews, watchlist_count):
    average = f"{reviews['rating'].mean():.1f}" if not reviews.empty else "—"
    genres = Counter(genre for row in reviews["genres"].dropna() for genre in row) if not reviews.empty else Counter()
    top_genre = genres.most_common(1)[0][0].upper() if genres else "—"
    figures = [
        (len(reviews), "FILMS REVIEWED"),
        (average, "AVERAGE RATING"),
        (watchlist_count, "ON WATCHLIST"),
        (top_genre, "TOP GENRE"),
    ]
    html('<div class="double-rule" style="margin:32px 0 24px"></div>')
    for slot, (figure, name) in zip(st.columns(4), figures):
        with slot:
            html(f'<div class="stat"><div class="figure">{escape(str(figure))}</div>'
                 f'<div class="name">{name}</div></div>')
    html('<div class="double-rule" style="margin:24px 0 40px"></div>')


def _favourites(favourites):
    section_head("FAVOURITES")
    st.write("")
    if favourites.empty:
        empty_state("Rate a few films and your favourites will gather here.")
        return
    with st.container(key="profile_heart_wrap"):
        poster_grid(favourites.head(FAVOURITE_COUNT), "fav", columns=FAVOURITE_COUNT)


def _reviews(reviews_with_titles):
    section_head("YOUR REVIEWS")
    if reviews_with_titles.empty:
        with st.container(key="profile_empty_wrap"):
            empty_state("You haven't written anything yet.", "BROWSE FILMS →", open_browse, key="profile_empty")
        return
    visible, page, total_pages = paginate(reviews_with_titles, "profile_page")
    for _, review in visible.iterrows():
        review_row(review, "profile", show_movie=True)
    st.write("")
    pagination("profile_page", page, total_pages)


def render():
    user = current_user()
    db = backend()
    rated = db.reviewed_movies(user["user_id"]).rename(columns={"rating_mine": "rating"})
    written = db.user_reviews(user["user_id"])
    watchlist_count = len(db.watchlist_ids(user["user_id"]))
    _banner(user, rated)
    _stats(rated, watchlist_count)
    _favourites(rated)
    st.write("")
    _reviews(written)
