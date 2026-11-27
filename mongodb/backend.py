"""MongoBackend - drop-in replacement for app/backends.py `DocumentBackend`.

Same public methods, same return shapes (DataFrames / dicts / sets) as the CSV stand-in, so no
Streamlit page has to change. In app/backends.py:

    import sys; sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # repo root
    from mongodb.backend import MongoBackend
    ENGINES = {"MySQL (Relational)": <Minal/Xue E's MySQL backend>, "MongoDB (Document)": MongoBackend}

The three benchmark methods hit the database on every call (no caching) so timings are honest;
catalogue() is cached and invalidated by any write made through this object.
"""
import re

import numpy as np
import pandas as pd

from . import analytics, crud
from .db import get_db

TS = "%Y-%m-%d %H:%M:%S"


def _poster_large(url):
    return re.sub(r"\._V1_.*\.jpg$", "._V1_SX400.jpg", url) if isinstance(url, str) else ""


def _ts(value):
    return value.strftime(TS) if hasattr(value, "strftime") else value


class MongoBackend:
    label = "MongoDB (Document)"

    def __init__(self, store=None):          # `store` accepted for signature parity; unused
        self._catalogue = None

    # ---------------------------------------------------------------- frames
    def _movie_frame(self, docs):
        cols = ["movie_id", "poster_url", "title", "release_year", "certificate", "duration", "description",
                "director", "cast", "imdb_votes", "genres", "avg_rating", "review_count", "poster_large"]
        rows = [{
            "movie_id": d["_id"], "poster_url": d.get("poster_url"), "title": d["title"], "release_year": d["release_year"],
            "certificate": d.get("certificate"), "duration": d["duration"], "description": d.get("description", ""),
            "director": d.get("director"), "cast": ", ".join(d.get("cast", [])), "imdb_votes": d["imdb_votes"],
            "genres": list(d.get("genres", [])),
            "avg_rating": float("nan") if d.get("avg_rating") is None else float(np.round(d["avg_rating"], 1)),
            "review_count": int(d.get("review_count", 0)),
            "poster_large": _poster_large(d.get("poster_url"))} for d in docs]
        return pd.DataFrame(rows, columns=cols)

    def _review_frame(self, reviews, titles=None):
        cols = ["review_id", "user_id", "movie_id", "rating", "review_text", "created_at", "updated_at",
                "username", "title", "release_year"]
        ids = {r["movie_id"] for r in reviews}
        movies = {m["_id"]: m for m in get_db().movies.find({"_id": {"$in": list(ids)}}, {"title": 1, "release_year": 1})}
        rows = [{"review_id": r["_id"], "user_id": r["user_id"], "movie_id": r["movie_id"], "rating": r["rating"],
                 "review_text": r.get("review_text", ""), "created_at": _ts(r["created_at"]), "updated_at": _ts(r["updated_at"]),
                 "username": r["username"], "title": movies.get(r["movie_id"], {}).get("title"),
                 "release_year": movies.get(r["movie_id"], {}).get("release_year")} for r in reviews]
        return pd.DataFrame(rows, columns=cols)

    def _dirty(self):
        self._catalogue = None

    # ---------------------------------------------------------------- movies
    def catalogue(self):
        if self._catalogue is None:
            self._catalogue = self._movie_frame(get_db().movies.find())
        return self._catalogue

    def genre_names(self):
        return crud.genre_names()

    def top_rated(self):
        return self._movie_frame(crud.search_movies(sort_by="Highest rated"))

    def search_movies(self, title="", genres=(), years=None, ratings=None, sort_by=None):
        frame = self._movie_frame(crud.search_movies(title, genres, years, ratings, sort_by))
        if ratings and tuple(ratings) != (0.0, 10.0):        # settle rounding ties on the value the UI displays
            frame = frame[frame["avg_rating"].between(*ratings)]
        return frame

    def well_rated(self, min_reviews):
        docs = get_db().movies.find({"review_count": {"$gte": min_reviews}}).sort(
            [("avg_rating", -1), ("review_count", -1)])
        return self._movie_frame(docs)

    def most_reviewed(self):
        return self._movie_frame(crud.search_movies(sort_by="Most reviewed"))

    def most_voted(self, limit):
        return self._movie_frame(get_db().movies.find().sort("imdb_votes", -1).limit(int(limit)))

    def year_bounds(self):
        return crud.year_bounds()

    def latest_reviews(self, limit):
        rows = analytics.latest_review_feed(int(limit))
        cat = self.catalogue()[["movie_id", "poster_large", "genres"]]
        frame = pd.DataFrame([{**r, "review_id": r["_id"], "created_at": _ts(r["created_at"]), "updated_at": _ts(r["updated_at"])}
                              for r in rows]).drop(columns=["_id"], errors="ignore")
        return frame.merge(cat, on="movie_id", how="left")

    def get_movie(self, movie_id):
        doc = crud.get_movie(movie_id)
        return None if doc is None else self._movie_frame([doc]).iloc[0].to_dict()

    # ---------------------------------------------------------------- reviews
    def movie_reviews(self, movie_id):
        return self._review_frame(crud.get_reviews_for_movie(movie_id))

    def user_reviews(self, user_id):
        return self._review_frame(crud.get_reviews_by_user(user_id))

    def user_review_for(self, user_id, movie_id):
        doc = crud.get_user_review_for(user_id, movie_id)
        return None if doc is None else self._review_frame([doc]).iloc[0].to_dict()

    def add_review(self, user_id, movie_id, rating, text):
        crud.add_review(user_id, movie_id, rating, text)
        self._dirty()

    def update_review(self, review_id, rating, text):
        crud.update_review(review_id, rating, text)
        self._dirty()

    def delete_review(self, review_id):
        crud.delete_review(review_id)
        self._dirty()

    # ---------------------------------------------------------------- watchlist
    def watchlist_ids(self, user_id):
        return crud.watchlist_ids(user_id)

    def user_watchlist(self, user_id):
        rows = crud.get_watchlist(user_id)
        frame = self._movie_frame(rows)
        frame.insert(1, "added_at", [_ts(r["added_at"]) for r in rows])
        return frame

    def add_to_watchlist(self, user_id, movie_id):
        crud.add_to_watchlist(user_id, movie_id)

    def remove_from_watchlist(self, user_id, movie_id):
        crud.remove_from_watchlist(user_id, movie_id)

    # ---------------------------------------------------------------- users
    def list_users(self):
        return pd.DataFrame(crud.list_users(), columns=["user_id", "username", "email"])

    def get_user(self, user_id):
        u = crud.get_user(user_id)
        return None if u is None else {k: u[k] for k in ("user_id", "username", "email")}

    def get_user_by_username(self, username):
        u = crud.get_user_by_username(username)
        return None if u is None else {k: u[k] for k in ("user_id", "username", "email")}

    def member_since(self, user_id):
        u = crud.get_user(user_id)
        return None if u is None else _ts(u["created_at"])

    def reviewed_movies(self, user_id):
        mine = pd.DataFrame([{"movie_id": r["movie_id"], "rating_mine": r["rating"]} for r in crud.get_reviews_by_user(user_id)],
                            columns=["movie_id", "rating_mine"])
        return mine.merge(self.catalogue(), on="movie_id").sort_values("rating_mine", ascending=False)

    def authenticate(self, username, password):
        return crud.authenticate(username, password)

    def username_taken(self, username):
        return crud.username_taken(username)

    def email_taken(self, email):
        return crud.email_taken(email)

    def register_user(self, username, email, password):
        return self.get_user(crud.register_user(username, email, password)["user_id"])

    # ---------------------------------------------------------------- benchmark queries (uncached)
    def movies_by_genre(self, genre_name):
        return analytics.movies_by_genre(genre_name)

    def average_rating(self, movie_id):
        return analytics.average_rating(movie_id)

    def watchlist_with_genres(self, user_id):
        return analytics.watchlist_with_genres(user_id)
