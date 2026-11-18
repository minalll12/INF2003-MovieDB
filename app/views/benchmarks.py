import statistics
import time
from html import escape

import pandas as pd
import streamlit as st

from backends import ENGINES
from components import html, page_title, section_head
from session import backend, engine_name, get_engine, set_engine

RUNS_PER_QUERY = 25


def timed(query, *args):
    query(*args)  # warm-up so one-off cache builds don't skew the first sample
    samples = []
    for _ in range(RUNS_PER_QUERY):
        start = time.perf_counter()
        result = query(*args)
        samples.append((time.perf_counter() - start) * 1000)
    return statistics.median(samples), result


def _queries(engine, genre, movie_id, user_id):
    return {
        "Movies by genre": timed(engine.movies_by_genre, genre),
        "Average rating for a film": timed(engine.average_rating, movie_id),
        "Watchlist with genres": timed(engine.watchlist_with_genres, user_id),
    }


def _inputs():
    db = backend()
    movies = db.catalogue().sort_values("title")
    users = db.list_users()
    genre, movie, user = st.columns(3, gap="large")
    with genre:
        chosen_genre = st.selectbox("Genre", db.genre_names())
    with movie:
        chosen_movie = st.selectbox(
            "Film", movies["movie_id"],
            format_func=lambda mid: movies.loc[movies["movie_id"] == mid, "title"].iloc[0],
        )
    with user:
        chosen_user = st.selectbox(
            "Account", users["user_id"],
            format_func=lambda uid: users.loc[users["user_id"] == uid, "username"].iloc[0],
        )
    return chosen_genre, chosen_movie, chosen_user


def _single_engine(genre, movie_id, user_id):
    section_head("No. 01 — SINGLE ENGINE")
    st.session_state.setdefault("bench_engine", engine_name())
    st.radio(
        "Data source", list(ENGINES), key="bench_engine", horizontal=True,
        on_change=set_engine, args=("bench_engine",),
    )
    if not st.button("RUN QUERIES →"):
        return
    results = _queries(backend(), genre, movie_id, user_id)
    captions = ["Rows returned", "Average rating", "Watchlist rows"]
    for slot, caption, (name, (elapsed, value)) in zip(st.columns(3), captions, results.items()):
        with slot:
            st.metric(name, f"{elapsed:.3f} ms")
            shown = value if caption == "Average rating" else len(value)
            html(f'<div class="mono">{caption.upper()}: {"NONE" if shown is None else shown}</div>')


def _comparison_table(rows):
    html(
        '<div class="bench-row head"><span class="h">Query</span>'
        '<span class="h right">MySQL (ms)</span><span class="h right">MongoDB (ms)</span>'
        '<span class="h right">Winner</span></div>'
    )
    for row in rows:
        html(
            f'<div class="bench-row"><span class="q">{escape(row["Query"])}</span>'
            f'<span class="n">{row["MySQL time (ms)"]:.3f}</span>'
            f'<span class="n">{row["MongoDB time (ms)"]:.3f}</span>'
            f'<span class="w">{escape(row["Winner"])}</span></div>'
        )


def _comparison(genre, movie_id, user_id):
    section_head("No. 02 — HEAD TO HEAD")
    if not st.button("RUN ALL COMPARISONS →", type="primary"):
        return
    names = list(ENGINES)
    timings = {name: _queries(get_engine(name), genre, movie_id, user_id) for name in names}
    rows = []
    for query in timings[names[0]]:
        mysql_ms = timings[names[0]][query][0]
        mongo_ms = timings[names[1]][query][0]
        rows.append({
            "Query": query,
            "MySQL time (ms)": mysql_ms,
            "MongoDB time (ms)": mongo_ms,
            "Winner": "MySQL" if mysql_ms < mongo_ms else "MongoDB",
        })
    _comparison_table(rows)
    st.write("")
    try:
        chart = pd.DataFrame(rows).set_index("Query")[["MySQL time (ms)", "MongoDB time (ms)"]]
        st.bar_chart(chart, stack=False, horizontal=True, color=["#d4af37", "#c4532f"])
    except Exception:
        pass  # pyarrow native DLL may be blocked on some machines; results still shown above
    for row in rows:
        fast, slow = sorted([row["MySQL time (ms)"], row["MongoDB time (ms)"]])
        gain = (slow - fast) / slow * 100 if slow else 0
        html(
            f'<div class="read" style="padding:4px 0">{escape(row["Query"])} — '
            f'<b style="color:var(--gold)">{escape(row["Winner"])}</b> '
            f'answered {gain:.0f}% faster.</div>'
        )


def render():
    page_title("Performance")
    html(
        '<div class="read" style="max-width:640px;margin-bottom:32px">Each query runs against both '
        f'data models with the same inputs. We discard a warm-up run, time {RUNS_PER_QUERY} executions '
        "and report the median.</div>"
    )
    genre, movie_id, user_id = _inputs()
    st.write("")
    _single_engine(genre, movie_id, user_id)
    st.write("")
    _comparison(genre, movie_id, user_id)
