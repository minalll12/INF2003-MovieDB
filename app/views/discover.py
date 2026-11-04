from html import escape

import pandas as pd
import streamlit as st
import streamlit.components.v1 as stcomp

from components import (
    html,
    poster_frame,
    poster_grid,
    score_text,
    stars,
)
from session import backend, current_user, open_browse, open_movie, toggle_watchlist

MIN_REVIEWS = 3
ROW_SIZE = 5

_GENRE_STRIP_CSS = (
    '<style>'
    '[data-testid="stHorizontalBlock"]:has([class*="st-key-genre_pill_"]) {'
    '  overflow-x: auto !important; flex-wrap: nowrap !important;'
    '  scrollbar-width: none; gap: 8px !important;'
    '  margin: 32px 0 16px !important; padding-bottom: 4px;'
    '}'
    '[data-testid="stHorizontalBlock"]:has([class*="st-key-genre_pill_"])::-webkit-scrollbar { display: none; }'
    '[data-testid="stHorizontalBlock"]:has([class*="st-key-genre_pill_"]) > [data-testid="stColumn"] {'
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
  var DONE = 'rhArrowsDone';
  function setup() {
    try {
      var p = window.parent.document;
      var strip = p.querySelector('[data-testid="stHorizontalBlock"]:has([class*="st-key-genre_pill_"])');
      if (!strip || strip[DONE]) return;
      strip[DONE] = true;

      var wrap = p.createElement('div');
      wrap.className = 'genre-arrow-wrap';
      strip.parentNode.insertBefore(wrap, strip);
      wrap.appendChild(strip);

      function makeArrow(cls, html, delta) {
        var b = p.createElement('button');
        b.className = 'genre-scroll-btn ' + cls;
        b.innerHTML = html;
        b.addEventListener('click', function(e) {
          e.preventDefault();
          strip.scrollBy({left: delta, behavior: 'smooth'});
        });
        return b;
      }

      wrap.insertBefore(makeArrow('genre-scroll-left',  '&#8249;', -240), strip);
      wrap.appendChild(makeArrow('genre-scroll-right', '&#8250;',  240));
    } catch(e) {}
  }

  setTimeout(setup, 250);
  try {
    new window.parent.MutationObserver(function(m) {
      for (var i = 0; i < m.length; i++) {
        if (m[i].addedNodes.length) { setup(); break; }
      }
    }).observe(window.parent.document.body, {childList: true, subtree: true});
  } catch(e) {}
})();
</script>
"""


def _genre_strip():
    genres = backend().genre_names()
    html(_GENRE_STRIP_CSS)
    cols = st.columns(len(genres), gap="small")
    for i, (col, genre) in enumerate(zip(cols, genres)):
        with col:
            with st.container(key=f"genre_pill_{i}"):
                if st.button(genre, key=f"gpill_{i}", type="tertiary"):
                    open_browse(genre=genre)
    stcomp.html(_GENRE_ARROWS_JS, height=0)


def _editorial_section(movies):
    html('<div class="double-rule" style="margin:12px 0 0"></div>')
    html('<div class="editorial-label">EDITOR\'S PICKS</div>')
    html('<div class="editorial-title">This Week on Reelhouse</div>')
    saved_ids = backend().watchlist_ids(current_user()["user_id"])
    slots = st.columns([1, 1, 1], gap="medium")
    for slot, (_, movie) in zip(slots, movies.iterrows()):
        with slot:
            movie_id = movie["movie_id"]
            desc = str(movie.get("description", "") or "")
            rating_text = score_text(movie["avg_rating"])
            saved = movie_id in saved_ids
            with st.container(key=f"card_editorial_{movie_id}"):
                html('<div class="editorial-poster-wrap">' + poster_frame(movie) + '</div>')
                if st.button(movie["title"], key=f"editorial_open_{movie_id}", type="tertiary"):
                    open_movie(movie_id)
                year_col, score_col, heart_col = st.columns([4, 1, 1], vertical_alignment="center")
                with year_col:
                    html(f'<div class="meta-year">{movie["release_year"]}</div>')
                with score_col:
                    html(f'<div class="meta-score">{escape(rating_text)}</div>')
                with heart_col:
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
        label_col, action_col = st.columns([4, 1], vertical_alignment="center")
        with label_col:
            html(f'<div class="section-head-label">{escape(title)}</div>')
        with action_col:
            with st.container(key=f"see_all_{action_key}"):
                if st.button("SEE ALL →", key=action_key, type="tertiary"):
                    on_action()
        html('<div class="double-rule"></div>')


def _poster_row(movies, prefix, title, sort_by):
    _section_header(title, f"all_{prefix}", lambda: open_browse(sort_by=sort_by))
    poster_grid(movies.head(ROW_SIZE), prefix, columns=ROW_SIZE)


def _fresh_reviews():
    html(
        '<style>'
        '.fresh-card { display: block; }'
        '.fresh-top-row {'
        ' display: flex; align-items: flex-start; gap: 8px; margin-top: 16px;'
        '}'
        '.fresh-card-title {'
        ' flex: 1;'
        ' font-family: "DM Serif Display", Georgia, serif !important;'
        ' font-size: 15px; font-weight: 400; color: #efe8d8; line-height: 1.35;'
        ' display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;'
        ' overflow: hidden;'
        '}'
        '.fresh-rating {'
        ' flex-shrink: 0;'
        ' font-family: "DM Mono", monospace; font-size: 11px;'
        ' color: #d4af37; letter-spacing: 0.06em; white-space: nowrap;'
        ' margin-top: 2px;'
        '}'
        '.fresh-who {'
        ' font-family: "DM Mono", monospace; font-size: 10px;'
        ' letter-spacing: 0.12em; text-transform: uppercase; color: #9a917f;'
        ' margin-top: 8px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;'
        '}'
        '.poster-frame.no-image .fallback .name,'
        '.poster-frame.no-image .fallback .year { display: none !important; }'
        '.poster-frame.no-image .fallback-icon { font-size: 36px !important; opacity: 0.18 !important; }'
        '</style>'
    )
    _section_header("FRESH REVIEWS", "all_fresh", lambda: open_browse(sort_by="Newest"))
    reviews = backend().latest_reviews(ROW_SIZE)
    slots = st.columns(ROW_SIZE, gap="medium")
    for slot, (_, review) in zip(slots, reviews.iterrows()):
        with slot:
            r = review.get("rating", None)
            try:
                rating_str = f"★ {float(r):.1f}" if r is not None and not pd.isna(r) else ""
            except (ValueError, TypeError):
                rating_str = ""
            html(
                '<div class="fresh-card">'
                + poster_frame(review)
                + '<div class="fresh-top-row">'
                + f'<div class="fresh-card-title">{escape(str(review["title"]))}</div>'
                + f'<div class="fresh-rating">{escape(rating_str)}</div>'
                + '</div>'
                + f'<div class="fresh-who">{escape(str(review["username"]))}</div>'
                + '</div>'
            )


def render():
    db = backend()
    top_picks = db.well_rated(MIN_REVIEWS).head(3)
    _genre_strip()
    _editorial_section(top_picks)
    _poster_row(db.well_rated(MIN_REVIEWS), "top", "TOP RATED", "Highest rated")
    _poster_row(db.most_reviewed(), "disc", "MOST DISCUSSED", "Most reviewed")
    _fresh_reviews()
