"""Seed MongoDB from data/cleaned/*.csv - the same six files MySQL imports.

    python seed.py [--data-dir PATH]      (DROPS and rebuilds the MongoDB database)

Relational -> document conversion:
  movies + genres + movie_genres  ->  one movie document with an embedded genres[] array
  movies.cast "A, B, C"           ->  embedded cast[] array
  reviews.csv                     ->  reviews collection (username denormalised from users)
  review/watchlist/user counters  ->  counters collection (replaces AUTO_INCREMENT)
Finally movies.avg_rating / review_count are computed from reviews in one pass.
"""
import argparse
from pathlib import Path

import pandas as pd
from pymongo import UpdateOne

from .config import DATA_DIR
from .schema import create_schema


def _read(data_dir: Path, name: str) -> pd.DataFrame:
    path = data_dir / name
    if not path.exists():
        raise FileNotFoundError(f"{path} not found - expected the six cleaned CSVs in data/cleaned/")
    return pd.read_csv(path)


def _dt(value):
    return pd.to_datetime(value).to_pydatetime()


def _split(text):
    return [p.strip() for p in str(text).split(",") if p.strip()] if pd.notna(text) else []


def build_users(df):
    return [{"_id": r.user_id, "username": r.username, "username_lower": r.username.lower(),
             "email": r.email.lower(), "password_hash": r.password_hash, "created_at": _dt(r.created_at)}
            for r in df.itertuples()]


def build_movies(df, genres, movie_genres):
    names = dict(zip(genres.genre_id, genres.genre_name))
    by_movie = {}
    for r in movie_genres.itertuples():
        by_movie.setdefault(r.movie_id, []).append(names[r.genre_id])
    return [{
        "_id": r.movie_id, "title": r.title, "release_year": int(r.release_year),
        "certificate": None if pd.isna(r.certificate) else r.certificate,
        "duration": int(r.duration),
        "genres": sorted(by_movie.get(r.movie_id) or _split(r.genre)),
        "description": "" if pd.isna(r.description) else r.description,
        "director": None if pd.isna(r.director) else r.director,
        "cast": _split(r.cast), "imdb_votes": int(r.imdb_votes),
        "poster_url": None if pd.isna(r.poster_url) else r.poster_url,
        "avg_rating": None, "review_count": 0,
    } for r in df.itertuples()]


def build_reviews(df, usernames):
    return [{"_id": r.review_id, "movie_id": r.movie_id, "user_id": r.user_id, "username": usernames[r.user_id],
             "rating": round(float(r.rating), 1), "review_text": "" if pd.isna(r.review_text) else r.review_text,
             "created_at": _dt(r.created_at), "updated_at": _dt(r.updated_at)} for r in df.itertuples()]


def build_watchlists(df):
    return [{"_id": r.watchlist_id, "user_id": r.user_id, "movie_id": r.movie_id, "added_at": _dt(r.added_at)}
            for r in df.itertuples()]


def recompute_all_movie_stats(db) -> None:
    """One aggregation computes every movie's avg_rating / review_count (computed pattern)."""
    rows = db.reviews.aggregate([{"$group": {"_id": "$movie_id", "avg": {"$avg": "$rating"}, "n": {"$sum": 1}}}])
    updates = [({"_id": s["_id"]}, {"$set": {"avg_rating": s["avg"], "review_count": s["n"]}}) for s in rows]
    try:
        if updates:
            db.movies.bulk_write([UpdateOne(f, u) for f, u in updates], ordered=False)
    except TypeError:  # mongomock/pymongo version mismatch (tests only)
        for f, u in updates:
            db.movies.update_one(f, u)


def seed(db, data_dir: Path = DATA_DIR) -> dict:
    create_schema(db, drop_existing=True)
    users = build_users(_read(data_dir, "users.csv"))
    movies = build_movies(_read(data_dir, "movies.csv"), _read(data_dir, "genres.csv"), _read(data_dir, "movie_genres.csv"))
    usernames = {u["_id"]: u["username"] for u in users}
    reviews = build_reviews(_read(data_dir, "reviews.csv"), usernames)
    watch = build_watchlists(_read(data_dir, "watchlists.csv"))

    db.users.insert_many(users)
    db.movies.insert_many(movies)
    db.reviews.insert_many(reviews)
    db.watchlists.insert_many(watch)
    for name, docs in (("users", users), ("reviews", reviews), ("watchlists", watch)):
        db.counters.replace_one({"_id": name}, {"_id": name, "seq": max(int(d["_id"][1:]) for d in docs)}, upsert=True)
    recompute_all_movie_stats(db)
    return {n: db[n].count_documents({}) for n in ("users", "movies", "reviews", "watchlists")}


if __name__ == "__main__":
    from .db import get_db

    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=DATA_DIR)
    print(seed(get_db(), ap.parse_args().data_dir))
