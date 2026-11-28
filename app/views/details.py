from html import escape

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from components import (
    empty_state,
    genre_tags,
    html,
    poster_frame,
    review_dialog,
    review_row,
    section_head,
)
from session import backend, current_user, get_back_target, go_back, open_browse, open_discover, toggle_watchlist


def _backdrop(movie):
    raw_art = movie.get("poster_large")
    if raw_art is None or pd.isna(raw_art) or str(raw_art).strip().lower() in ("", "none", "nan"):
        art_style = ""
    else:
        art_style = f"background-image:url('{escape(str(raw_art).strip())}')"
    target_url, page_name = get_back_target()
    html(
        '<div class="backdrop">'
        f'<div class="art" style="{art_style}"></div>'
        '<div class="veil"></div>'
        '<div class="backdrop-content">'
        f'<a href="{target_url}" target="_self" class="film-back-btn" data-page="{page_name}" '
        f'onclick="var fn = window.filmGoBack || (window.parent && window.parent.filmGoBack); if(fn){{return fn(event,\'{target_url}\',\'{page_name}\');}}">← BACK</a>'
        '</div>'
        '</div>'
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
    if not movie_id and "film" in st.query_params:
        film_id = str(st.query_params["film"]).strip()
        if film_id:
            st.session_state["selected_movie"] = film_id
            movie_id = film_id
    elif movie_id:
        st.query_params["film"] = str(movie_id)

    movie = backend().get_movie(movie_id) if movie_id else None
    if movie is None:
        target_url, page_name = get_back_target()
        components.html(
            f"""
            <script>
            (function() {{
                try {{
                    var pwin = window.parent;
                    var fn = (pwin && pwin.filmGoBack) || window.filmGoBack;
                    if (fn) {{
                        fn(null, "{target_url}", "{page_name}");
                    }} else {{
                        pwin.location.href = "{target_url}";
                    }}
                }} catch(e) {{
                    window.parent.location.href = "{target_url}";
                }}
            }})();
            </script>
            """,
            height=0,
            width=0,
        )
        return
    _backdrop(movie)
    _header(movie)
    st.write("")
    _reviews(movie)

    components.html(
        f"""
        <script>
        (function() {{
            try {{
                var win = window.parent;
                var doc = win.document;
                var currentId = "{escape(str(movie_id))}";
                if (win._currentFilmId !== currentId) {{
                    win._currentFilmId = currentId;
                    function scrollToTop() {{
                        var targets = [
                            win,
                            doc.documentElement,
                            doc.body,
                            doc.querySelector('.stApp'),
                            doc.querySelector('[data-testid="stAppViewContainer"]'),
                            doc.querySelector('[data-testid="stMain"]'),
                            doc.querySelector('.stMain'),
                            doc.getElementById('stMain'),
                            doc.querySelector('main'),
                            doc.querySelector('section.main'),
                            doc.querySelector('[data-testid="stMainBlockContainer"]')
                        ];
                        targets.forEach(function(t) {{
                            if (!t) return;
                            try {{ t.scrollTop = 0; }} catch(e) {{}}
                            try {{ if (t.scrollTo) t.scrollTo(0, 0); }} catch(e) {{}}
                        }});
                        try {{
                            var header = doc.querySelector('[data-testid="stHeader"]');
                            if (header && header.scrollIntoView) {{
                                header.scrollIntoView({{ block: 'start', inline: 'nearest', behavior: 'instant' }});
                            }}
                        }} catch(e) {{}}
                    }}
                    scrollToTop();
                    if (win.requestAnimationFrame) win.requestAnimationFrame(scrollToTop);
                    setTimeout(scrollToTop, 20);
                    setTimeout(scrollToTop, 80);
                    setTimeout(scrollToTop, 200);
                    setTimeout(scrollToTop, 400);
                }}
            }} catch(e) {{}}
        }})();
        </script>
        """,
        height=0,
        width=0,
    )