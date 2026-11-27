from html import escape

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from components import (
    html,
    poster_frame,
    poster_grid,
    score_text,
    stars,
)
from cache import latest_reviews as _cached_latest_reviews
from cache import most_reviewed as _cached_most_reviewed
from cache import well_rated as _cached_well_rated
from session import backend, current_user, engine_name, open_browse, open_movie, toggle_watchlist



MIN_REVIEWS = 3
ROW_SIZE = 5

_GENRE_STRIP_CSS = (
    '<style>'
    '[class*="st-key-genre_strip_wrap"],'
    'div[class*="st-key-genre_strip_wrap"],'
    '[data-testid="stVerticalBlock"][class*="st-key-genre_strip_wrap"] {'
    '  position: relative !important;'
    '  width: 100% !important;'
    '  margin: 32px 0 16px !important;'
    '  overflow: visible !important;'
    '}'
    '[class*="st-key-genre_strip_wrap"] [data-testid="stHorizontalBlock"] {'
    '  overflow-x: auto !important; flex-wrap: nowrap !important;'
    '  scrollbar-width: none !important; gap: 8px !important;'
    '  margin: 0 !important;'
    '  padding: 4px 44px 8px 44px !important;'
    '  scroll-behavior: smooth !important;'
    '}'
    '[class*="st-key-genre_strip_wrap"] [data-testid="stHorizontalBlock"]::-webkit-scrollbar { display: none !important; }'
    '[class*="st-key-genre_strip_wrap"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {'
    '  flex: 0 0 auto !important; min-width: 0 !important; width: auto !important; padding: 0 !important;'
    '}'
    '[class*="st-key-genre_pill_"] button {'
    '  font-family: "DM Mono", monospace !important; font-size: 11px !important;'
    '  letter-spacing: 0.08em; text-transform: uppercase !important;'
    '  padding: 5px 14px !important; border: 1px solid #2e2a23 !important;'
    '  border-radius: 20px !important; background: transparent !important;'
    '  color: #9a917f !important; white-space: nowrap; min-height: 0 !important; line-height: 1 !important;'
    '}'
    '[class*="st-key-genre_pill_"] button:hover {'
    '  border-color: #d4af37 !important; color: #d4af37 !important; background: transparent !important;'
    '}'
    '</style>'
)

_GENRE_ARROWS_JS = """
<script>
(function() {
  function setupGenreChevrons() {
    try {
      var doc = window.parent.document;
      if (!doc) return;
      var wrap = doc.querySelector('[class*="st-key-genre_strip_wrap"]');
      if (!wrap) return;
      var strip = wrap.querySelector('[data-testid="stHorizontalBlock"]');
      if (!strip) return;

      var prevBtn = wrap.querySelector('.genre-scroll-left');
      var nextBtn = wrap.querySelector('.genre-scroll-right');

      if (!prevBtn) {
        prevBtn = doc.createElement('button');
        prevBtn.className = 'genre-scroll-btn genre-scroll-left';
        prevBtn.setAttribute('aria-label', 'Previous genres');
        prevBtn.setAttribute('type', 'button');
        prevBtn.innerHTML = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"></polyline></svg>';
        prevBtn.addEventListener('click', function(e) {
          e.preventDefault();
          e.stopPropagation();
          strip.scrollBy({left: -280, behavior: 'smooth'});
        });
        wrap.appendChild(prevBtn);
      }

      if (!nextBtn) {
        nextBtn = doc.createElement('button');
        nextBtn.className = 'genre-scroll-btn genre-scroll-right';
        nextBtn.setAttribute('aria-label', 'Next genres');
        nextBtn.setAttribute('type', 'button');
        nextBtn.innerHTML = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>';
        nextBtn.addEventListener('click', function(e) {
          e.preventDefault();
          e.stopPropagation();
          strip.scrollBy({left: 280, behavior: 'smooth'});
        });
        wrap.appendChild(nextBtn);
      }
    } catch(e) {}
  }

  setupGenreChevrons();
  setTimeout(setupGenreChevrons, 80);
  setTimeout(setupGenreChevrons, 200);
  setTimeout(setupGenreChevrons, 500);

  try {
    var doc = window.parent.document;
    if (doc && !window.parent._genreChevronsObserver) {
      window.parent._genreChevronsObserver = new MutationObserver(setupGenreChevrons);
      window.parent._genreChevronsObserver.observe(doc.body, {childList: true, subtree: true});
    }
  } catch(e) {}
})();
</script>
"""


def _genre_strip():
    genres = backend().genre_names()
    html(_GENRE_STRIP_CSS)
    with st.container(key="genre_strip_wrap"):
        cols = st.columns(len(genres), gap="small")
        for i, (col, genre) in enumerate(zip(cols, genres)):
            with col:
                with st.container(key=f"genre_pill_{i}"):
                    if st.button(genre, key=f"gpill_{i}", type="tertiary"):
                        open_browse(genre=genre)
    components.html(_GENRE_ARROWS_JS, height=0, width=0)


def _editorial_section(movies, saved_ids):
    html('<div class="double-rule" style="margin:12px 0 0"></div>')
    html('<div class="editorial-label">EDITOR\'S PICKS</div>')
    html('<div class="editorial-title">This Week on Reelhouse</div>')
    slots = st.columns([1, 1, 1], gap="medium")
    for slot, (_, movie) in zip(slots, movies.iterrows()):
        with slot:
            movie_id = movie["movie_id"]
            desc = str(movie.get("description", "") or "")
            rating_text = score_text(movie["avg_rating"])
            saved = movie_id in saved_ids
            with st.container(key=f"card_editorial_{movie_id}"):
                with st.container(key=f"poster_btn_editorial_{movie_id}"):
                    if st.button(
                        f"poster_editorial_{movie_id}",
                        key=f"pbtn_editorial_{movie_id}",
                        on_click=open_movie,
                        args=(movie_id,),
                    ):
                        pass
                    html(f'<div class="editorial-poster-wrap">{poster_frame(movie)}</div>')
                if st.button(movie["title"], key=f"editorial_open_{movie_id}", type="tertiary"):
                    open_movie(movie_id)
                year_col, score_col, heart_col = st.columns([4, 1, 1], vertical_alignment="center")
                with year_col:
                    html(f'<div class="meta-year">{movie["release_year"]}</div>')
                with score_col:
                    html(f'<div class="meta-score">{escape(rating_text)}</div>')
                with heart_col:
                    with st.container(key=f"editorial_heart_wrap_{movie_id}"):
                        with st.container(key=f"save_editorial_{movie_id}"):
                            st.button(
                                "♥" if saved else "♡",
                                key=f"savebtn_editorial_{movie_id}",
                                help="Remove from watchlist" if saved else "Save to watchlist",
                                on_click=toggle_watchlist,
                                args=(movie_id,),
                            )
                html(f'<p class="editorial-blurb">{escape(desc)}</p>')


def _section_header(title, action_key, on_action):
    with st.container(key=f"section_hdr_{action_key}"):
        html('<div class="section-gap"></div>')
        label_col, action_col = st.columns([4, 1], vertical_alignment="bottom")
        with label_col:
            html(f'<div class="section-head-label">{escape(title)}</div>')
        with action_col:
            with st.container(key=f"see_all_{action_key}"):
                if st.button("SEE ALL →", key=action_key, type="tertiary"):
                    on_action()
        html('<div class="double-rule"></div>')


def _poster_row(movies, prefix, title, sort_by, saved_ids=None):
    _section_header(title, f"all_{prefix}", lambda: open_browse(sort_by=sort_by))
    poster_grid(movies.head(ROW_SIZE), prefix, columns=ROW_SIZE, saved_ids=saved_ids)


def _fresh_reviews():
    _section_header("FRESH REVIEWS", "all_fresh", lambda: open_browse(sort_by="Newest"))
    reviews = _cached_latest_reviews(engine_name(), ROW_SIZE)
    slots = st.columns(ROW_SIZE, gap="medium")
    for index, (slot, (_, review)) in enumerate(zip(slots, reviews.iterrows())):
        with slot:
            movie_id = review["movie_id"]
            r = review.get("rating", None)
            try:
                rating_str = f"★ {float(r):.1f}" if r is not None and not pd.isna(r) else ""
            except (ValueError, TypeError):
                rating_str = ""
            with st.container(key=f"card_fresh_{movie_id}_{index}"):
                with st.container(key=f"poster_btn_fresh_{movie_id}_{index}"):
                    if st.button(
                        f"poster_fresh_{movie_id}_{index}",
                        key=f"pbtn_fresh_{movie_id}_{index}",
                        on_click=open_movie,
                        args=(movie_id,),
                    ):
                        pass
                    html(f'<div class="card-poster-wrap">{poster_frame(review)}</div>')
                title_col, rating_col = st.columns([3, 1], vertical_alignment="top")
                with title_col:
                    if st.button(
                        review["title"],
                        key=f"title_fresh_{movie_id}_{index}",
                        type="tertiary",
                        on_click=open_movie,
                        args=(movie_id,),
                    ):
                        pass
                with rating_col:
                    with st.container(key=f"fresh_rating_{movie_id}_{index}"):
                        if rating_str:
                            html(f'<div class="fresh-rating">{escape(rating_str)}</div>')
                html(f'<div class="fresh-who">{escape(str(review["username"]))}</div>')


def render():
    eng = engine_name()
    top_movies = _cached_well_rated(eng, MIN_REVIEWS)
    saved_ids = backend().watchlist_ids(current_user()["user_id"])
    _genre_strip()
    _editorial_section(top_movies.head(3), saved_ids)
    _poster_row(top_movies, "top", "TOP RATED", "Highest rated", saved_ids)
    _poster_row(_cached_most_reviewed(eng), "disc", "MOST DISCUSSED", "Most reviewed", saved_ids)
    _fresh_reviews()
