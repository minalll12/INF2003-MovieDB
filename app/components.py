import math
from datetime import datetime
from html import escape

import pandas as pd
import streamlit as st

from session import backend, current_user, open_movie, toggle_watchlist


def _fmt_date(stamp):
    try:
        return datetime.strptime(str(stamp), "%Y-%m-%d %H:%M:%S").strftime("%d %b %Y")
    except (ValueError, TypeError):
        return str(stamp)

PAGE_SIZE = 20
GRID_COLUMNS = 5
MIN_REVIEW_CHARS = 10
MAX_REVIEW_CHARS = 1000


def html(markup):
    st.markdown(markup, unsafe_allow_html=True)


def eyebrow(text, plain=False):
    html(f'<div class="eyebrow{" plain" if plain else ""}">{escape(text)}</div>')


def page_title(text):
    html(f'<div class="page-title">{escape(text)}</div>')


def section_head(title, action_label=None, action_key=None, on_action=None):
    # Newsprint heading: label left, optional link right-aligned, double rule beneath.
    if action_label:
        head, link = st.columns([4, 1], vertical_alignment="bottom")
        with head:
            html(f'<div class="section-head"><span class="title">{escape(title)}</span></div>')
        with link:
            with st.container(key=f"see_all_{action_key}"):
                if st.button(action_label, key=action_key, type="tertiary"):
                    on_action()
    else:
        html(f'<div class="section-head"><span class="title">{escape(title)}</span></div>')
    html('<div class="double-rule"></div>')


def empty_state(line, button_label=None, on_click=None, key=None):
    html(f'<div class="empty"><div class="line">{escape(line)}</div></div>')
    if button_label:
        _, middle, _ = st.columns([2, 1, 2])
        with middle:
            if st.button(button_label, key=key, type="primary", width="stretch"):
                on_click()


def stars(rating):
    # Width-based fill so half stars land exactly on the score.
    percent = max(0.0, min(100.0, rating / 10 * 100))
    return (
        '<span class="stars"><span class="rail">★★★★★'
        f'<span class="fill" style="width:{percent:.1f}%">★★★★★</span></span>'
        f'<span class="exact">{rating:.1f}/10</span></span>'
    )


def score_text(avg_rating):
    return "" if pd.isna(avg_rating) else f"★ {avg_rating:.1f}"


def poster_frame(movie, class_name="poster-frame"):
    art = escape(str(movie.get("poster_large") or ""))
    extra = " no-image" if not art else ""
    fallback = (
        '<div class="fallback">'
        '<div class="fallback-icon">🎬</div>'
        f'<div class="name">{escape(str(movie["title"]))}</div>'
        f'<div class="year">{movie["release_year"]}</div>'
        '</div>'
    )
    return (
        f'<div class="{class_name}{extra}">'
        f'{fallback}'
        f'<div class="art" style="background-image:url(\'{art}\')"></div>'
        "</div>"
    )


def genre_tags(names):
    tags = "".join(f'<span class="genre-tag">{escape(n)}</span>' for n in names)
    return f'<div class="tag-row">{tags}</div>'


def poster_card(movie, saved, prefix):
    movie_id = movie["movie_id"]
    rating_text = score_text(movie["avg_rating"])
    with st.container(key=f"card_{prefix}_{movie_id}"):
        html('<div class="card-poster-wrap">' + poster_frame(movie) + '</div>')
        title_col, right_col = st.columns([3, 1], vertical_alignment="top")
        with title_col:
            if st.button(movie["title"], key=f"title_{prefix}_{movie_id}", type="tertiary"):
                open_movie(movie_id)
            html(f'<div class="card-year">{movie["release_year"]}</div>')
        with right_col:
            with st.container(key=f"right_{prefix}_{movie_id}"):
                html(f'<div class="card-score">{escape(rating_text)}</div>')
                with st.container(key=f"save_{prefix}_{movie_id}"):
                    st.button(
                        "♥" if saved else "♡",
                        key=f"savebtn_{prefix}_{movie_id}",
                        help="Remove from watchlist" if saved else "Save to watchlist",
                        on_click=toggle_watchlist,
                        args=(movie_id,),
                    )


def poster_grid(movies, prefix, columns=GRID_COLUMNS):
    saved_ids = backend().watchlist_ids(current_user()["user_id"])
    rows = [movies.iloc[i:i + columns] for i in range(0, len(movies), columns)]
    for index, row in enumerate(rows):
        slots = st.columns(columns, gap="medium")
        for slot, (_, movie) in zip(slots, row.iterrows()):
            with slot:
                poster_card(movie, movie["movie_id"] in saved_ids, f"{prefix}{index}")


def _set_page(key, page):
    st.session_state[key] = page


def paginate(frame, key):
    total_pages = max(1, math.ceil(len(frame) / PAGE_SIZE))
    page = min(st.session_state.get(key, 1), total_pages)
    st.session_state[key] = page
    start = (page - 1) * PAGE_SIZE
    return frame.iloc[start:start + PAGE_SIZE], page, total_pages


def pagination(key, page, total_pages):
    if total_pages <= 1:
        return
    with st.container(key=f"pagination_{key}"):
        html('<div style="margin-top:32px"></div>')
        _, prev, label, following, _ = st.columns([3, 1, 1.4, 1, 3], vertical_alignment="center")
        with prev:
            st.button(
                "← PREV", key=f"{key}_prev", type="tertiary", disabled=page <= 1,
                on_click=_set_page, args=(key, page - 1),
            )
        with label:
            html(f'<div class="mono" style="text-align:center">PAGE {page} OF {total_pages}</div>')
        with following:
            st.button(
                "NEXT →", key=f"{key}_next", type="tertiary", disabled=page >= total_pages,
                on_click=_set_page, args=(key, page + 1),
            )


def paged_grid(movies, key, columns=GRID_COLUMNS):
    visible, page, total_pages = paginate(movies, key)
    poster_grid(visible, key, columns)
    pagination(key, page, total_pages)


def review_row(review, prefix, show_movie=False):
    own = review["user_id"] == current_user()["user_id"]
    heading = escape(str(review["title"])) if show_movie else escape(str(review["username"]))
    html(
        '<div class="review">'
        f'<div class="review-top"><span class="review-who{" own" if own else ""}">{heading}</span>'
        f'{stars(review["rating"])}</div>'
        f'<div class="review-text">{escape(str(review["review_text"]))}</div>'
        f'<div class="review-date">{_fmt_date(review["updated_at"])}</div>'
        "</div>"
    )
    if not own:
        return
    slots = st.columns([1, 1, 6] if not show_movie else [1, 1, 1, 5])
    offset = 0
    if show_movie:
        with slots[0]:
            if st.button("VIEW FILM", key=f"goto_{prefix}_{review['review_id']}", type="tertiary"):
                open_movie(review["movie_id"])
        offset = 1
    with slots[offset]:
        if st.button("EDIT", key=f"edit_{prefix}_{review['review_id']}", type="tertiary"):
            review_dialog(review["movie_id"], review.to_dict())
    with slots[offset + 1]:
        with st.container(key=f"del_{prefix}_{review['review_id']}"):
            if st.button("DELETE", key=f"delbtn_{prefix}_{review['review_id']}", type="tertiary"):
                delete_dialog(review.to_dict())


@st.dialog("Your review", width="large")
def review_dialog(movie_id, existing=None):
    movie = backend().get_movie(movie_id)
    text_key = f"review_text_{movie_id}"
    if text_key not in st.session_state:
        st.session_state[text_key] = existing["review_text"] if existing else ""

    html(f'<div class="eyebrow">{escape(movie["title"])} · {movie["release_year"]}</div>')
    rating = st.slider(
        "Rating", min_value=1.0, max_value=10.0, step=0.1, format="%.1f",
        value=float(existing["rating"]) if existing else 7.0,
    )
    st.text_area(
        "Review", key=text_key, height=180, max_chars=MAX_REVIEW_CHARS,
        placeholder="What stayed with you after the credits rolled?",
    )
    text = st.session_state[text_key]
    html(f'<div class="mono">{len(text)} / {MAX_REVIEW_CHARS} CHARACTERS</div>')
    st.write("")

    if not st.button("SAVE REVIEW →" if existing else "POST REVIEW →", type="primary"):
        return
    if len(text.strip()) < MIN_REVIEW_CHARS:
        st.error(f"Reviews need at least {MIN_REVIEW_CHARS} characters.")
        return
    try:
        if existing:
            backend().update_review(existing["review_id"], rating, text.strip())
        else:
            backend().add_review(current_user()["user_id"], movie_id, rating, text.strip())
    except OSError:
        st.error("Couldn't save your review. Please try again.")
        return
    st.session_state.pop(text_key, None)
    st.toast("Review saved", icon=":material/check:")
    st.rerun()


@st.dialog("Delete review")
def delete_dialog(review):
    html('<div class="read">This removes your review and rating for good.</div>')
    st.write("")
    keep, remove = st.columns(2)
    with keep:
        if st.button("KEEP IT", width="stretch"):
            st.rerun()
    with remove:
        if st.button("DELETE", type="primary", width="stretch"):
            try:
                backend().delete_review(review["review_id"])
            except OSError:
                st.error("Couldn't delete the review. Please try again.")
                return
            st.toast("Review deleted")
            st.rerun()
