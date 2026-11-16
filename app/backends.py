import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from auth import hash_password, verify_password

# Wire in the real database backends. Both accept store=None and ignore it.
# If a package is missing or the database is unreachable, we fall back to the CSV classes below.
try:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from mysql.backend import MySQLBackend
    _mysql_ok = True
except Exception:
    _mysql_ok = False

try:
    from mongodb.backend import MongoBackend
    _mongo_ok = True
except Exception:
    _mongo_ok = False


SORT_OPTIONS = {
    "Highest rated": (["avg_rating", "review_count", "imdb_votes"], [False, False, False]),
    "Most reviewed": (["review_count", "avg_rating"], [False, False]),
    "Newest": (["release_year", "title"], [False, True]),
    "Oldest": (["release_year", "title"], [True, True]),
    "Title A–Z": (["title"], [True]),
}


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def poster_large(url):
    if not isinstance(url, str):
        return ""
    return re.sub(r"\._V1_.*\.jpg$", "._V1_SX400.jpg", url)


class CsvBackend:
    # Shared data access layer. The MySQL and MongoDB modules will implement
    # these same methods; until then both engines read the CSV store.

    label = "CSV"

    def __init__(self, store):
        self.store = store
        self._cache_version = None
        self._catalogue = None

    def catalogue(self):
        if self._cache_version != self.store.version:
            self._catalogue = self._build_catalogue()
            self._cache_version = self.store.version
        return self._catalogue

    def _build_catalogue(self):
        movies = self.store["movies"]
        genre_lists = (
            self.store["movie_genres"]
            .merge(self.store["genres"], on="genre_id")
            .groupby("movie_id")["genre_name"]
            .agg(list)
            .rename("genres")
        )
        stats = (
            self.store["reviews"]
            .groupby("movie_id")["rating"]
            .agg(avg_rating="mean", review_count="count")
        )
        catalogue = movies.join(genre_lists, on="movie_id").join(stats, on="movie_id")
        catalogue["genres"] = catalogue["genres"].apply(lambda g: g if isinstance(g, list) else [])
        catalogue["review_count"] = catalogue["review_count"].fillna(0).astype(int)
        catalogue["avg_rating"] = catalogue["avg_rating"].round(1)
        catalogue["poster_large"] = catalogue["poster_url"].map(poster_large)
        return catalogue

    # Movies

    def genre_names(self):
        return sorted(self.store["genres"]["genre_name"])

    def top_rated(self):
        return self.catalogue().sort_values(
            ["avg_rating", "review_count", "imdb_votes"], ascending=False, na_position="last"
        )

    def search_movies(self, title="", genres=(), years=None, ratings=None, sort_by=None):
        results = self.catalogue()
        if title:
            results = results[results["title"].str.contains(title, case=False, regex=False)]
        if genres:
            wanted = set(genres)
            results = results[results["genres"].map(wanted.issubset).astype(bool)]
        if years:
            results = results[results["release_year"].between(*years)]
        if ratings and tuple(ratings) != (0.0, 10.0):
            results = results[results["avg_rating"].between(*ratings)]
        columns, ascending = SORT_OPTIONS.get(sort_by, SORT_OPTIONS["Highest rated"])
        return results.sort_values(columns, ascending=ascending, na_position="last")

    def well_rated(self, min_reviews):
        catalogue = self.catalogue()
        return catalogue[catalogue["review_count"] >= min_reviews].sort_values(
            ["avg_rating", "review_count"], ascending=False
        )

    def most_reviewed(self):
        return self.catalogue().sort_values(["review_count", "avg_rating"], ascending=False)

    def most_voted(self, limit):
        return self.catalogue().nlargest(limit, "imdb_votes")

    def year_bounds(self):
        years = self.store["movies"]["release_year"]
        return int(years.min()), int(years.max())

    def latest_reviews(self, limit):
        reviews = self.store["reviews"].sort_values("created_at", ascending=False).head(limit)
        return self._with_context(reviews).merge(
            self.catalogue()[["movie_id", "poster_large", "genres"]], on="movie_id", how="left"
        )

    def get_movie(self, movie_id):
        match = self.catalogue()[self.catalogue()["movie_id"] == movie_id]
        return None if match.empty else match.iloc[0].to_dict()

    # Reviews

    def _with_context(self, reviews):
        users = self.store["users"][["user_id", "username"]]
        movies = self.store["movies"][["movie_id", "title", "release_year"]]
        return reviews.merge(users, on="user_id", how="left").merge(movies, on="movie_id", how="left")

    def movie_reviews(self, movie_id):
        reviews = self.store["reviews"]
        reviews = reviews[reviews["movie_id"] == movie_id]
        return self._with_context(reviews).sort_values("updated_at", ascending=False)

    def user_reviews(self, user_id):
        reviews = self.store["reviews"]
        reviews = reviews[reviews["user_id"] == user_id]
        return self._with_context(reviews).sort_values("updated_at", ascending=False)

    def user_review_for(self, user_id, movie_id):
        reviews = self.store["reviews"]
        match = reviews[(reviews["user_id"] == user_id) & (reviews["movie_id"] == movie_id)]
        return None if match.empty else match.iloc[0].to_dict()

    def add_review(self, user_id, movie_id, rating, text):
        timestamp = now()
        self.store.append("reviews", {
            "review_id": self.store.next_id("reviews", "review_id"),
            "user_id": user_id,
            "movie_id": movie_id,
            "rating": round(float(rating), 1),
            "review_text": text,
            "created_at": timestamp,
            "updated_at": timestamp,
        })

    def update_review(self, review_id, rating, text):
        reviews = self.store["reviews"].copy()
        row = reviews["review_id"] == review_id
        reviews.loc[row, ["rating", "review_text", "updated_at"]] = [round(float(rating), 1), text, now()]
        self.store.replace("reviews", reviews)

    def delete_review(self, review_id):
        reviews = self.store["reviews"]
        self.store.replace("reviews", reviews[reviews["review_id"] != review_id])

    # Watchlist

    def watchlist_ids(self, user_id):
        watchlists = self.store["watchlists"]
        return set(watchlists.loc[watchlists["user_id"] == user_id, "movie_id"])

    def user_watchlist(self, user_id):
        watchlists = self.store["watchlists"]
        entries = watchlists[watchlists["user_id"] == user_id][["movie_id", "added_at"]]
        return entries.merge(self.catalogue(), on="movie_id").sort_values("added_at", ascending=False)

    def add_to_watchlist(self, user_id, movie_id):
        if movie_id in self.watchlist_ids(user_id):
            return
        self.store.append("watchlists", {
            "watchlist_id": self.store.next_id("watchlists", "watchlist_id"),
            "user_id": user_id,
            "movie_id": movie_id,
            "added_at": now(),
        })

    def remove_from_watchlist(self, user_id, movie_id):
        watchlists = self.store["watchlists"]
        keep = ~((watchlists["user_id"] == user_id) & (watchlists["movie_id"] == movie_id))
        self.store.replace("watchlists", watchlists[keep])

    # Users

    def list_users(self):
        return self.store["users"][["user_id", "username", "email"]]

    def get_user(self, user_id):
        users = self.store["users"]
        match = users[users["user_id"] == user_id]
        return None if match.empty else match.iloc[0][["user_id", "username", "email"]].to_dict()

    def member_since(self, user_id):
        users = self.store["users"]
        match = users[users["user_id"] == user_id]
        return None if match.empty else match.iloc[0]["created_at"]

    def reviewed_movies(self, user_id):
        reviews = self.store["reviews"]
        mine = (
            reviews[reviews["user_id"] == user_id][["movie_id", "rating"]]
            .rename(columns={"rating": "rating_mine"})
        )
        return mine.merge(self.catalogue(), on="movie_id").sort_values(
            "rating_mine", ascending=False
        )

    def authenticate(self, username, password):
        users = self.store["users"]
        match = users[users["username"].str.lower() == username.strip().lower()]
        if match.empty or not verify_password(password, match.iloc[0]["password_hash"]):
            return None
        return self.get_user(match.iloc[0]["user_id"])

    def username_taken(self, username):
        return username.strip().lower() in set(self.store["users"]["username"].str.lower())

    def email_taken(self, email):
        return email.strip().lower() in set(self.store["users"]["email"].str.lower())

    def register_user(self, username, email, password):
        user_id = self.store.next_id("users", "user_id")
        self.store.append("users", {
            "user_id": user_id,
            "username": username.strip(),
            "email": email.strip(),
            "password_hash": hash_password(password),
            "created_at": now(),
        })
        return self.get_user(user_id)

    # Benchmark queries

    def movies_by_genre(self, genre_name):
        raise NotImplementedError

    def average_rating(self, movie_id):
        raise NotImplementedError

    def watchlist_with_genres(self, user_id):
        raise NotImplementedError


class RelationalBackend(CsvBackend):
    label = "MySQL (Relational)"

    def movies_by_genre(self, genre_name):
        genres = self.store["genres"]
        joined = (
            genres[genres["genre_name"] == genre_name]
            .merge(self.store["movie_genres"], on="genre_id")
            .merge(self.store["movies"], on="movie_id")
        )
        return joined[["movie_id", "title", "release_year"]]

    def average_rating(self, movie_id):
        reviews = self.store["reviews"]
        ratings = reviews.loc[reviews["movie_id"] == movie_id, "rating"]
        return None if ratings.empty else round(ratings.mean(), 2)

    def watchlist_with_genres(self, user_id):
        watchlists = self.store["watchlists"]
        joined = (
            watchlists[watchlists["user_id"] == user_id]
            .merge(self.store["movies"][["movie_id", "title"]], on="movie_id")
            .merge(self.store["movie_genres"], on="movie_id")
            .merge(self.store["genres"], on="genre_id")
        )
        return joined.groupby(["movie_id", "title"])["genre_name"].agg(", ".join).reset_index()


class DocumentBackend(CsvBackend):
    label = "MongoDB (Document)"

    def __init__(self, store):
        super().__init__(store)
        self._docs_version = None
        self._docs = {}

    def collections(self):
        # Mirrors the planned MongoDB model: genres embedded in each movie document.
        if self._docs_version != self.store.version:
            movies = self.catalogue()[["movie_id", "title", "release_year", "genres"]]
            self._docs = {
                "movies": movies.to_dict("records"),
                "reviews": self.store["reviews"][["movie_id", "rating"]].to_dict("records"),
                "watchlists": self.store["watchlists"][["user_id", "movie_id"]].to_dict("records"),
            }
            self._docs["movies_by_id"] = {doc["movie_id"]: doc for doc in self._docs["movies"]}
            self._docs_version = self.store.version
        return self._docs

    def movies_by_genre(self, genre_name):
        docs = self.collections()["movies"]
        return [doc for doc in docs if genre_name in doc["genres"]]

    def average_rating(self, movie_id):
        ratings = [doc["rating"] for doc in self.collections()["reviews"] if doc["movie_id"] == movie_id]
        return round(sum(ratings) / len(ratings), 2) if ratings else None

    def watchlist_with_genres(self, user_id):
        docs = self.collections()
        movie_ids = [doc["movie_id"] for doc in docs["watchlists"] if doc["user_id"] == user_id]
        return [docs["movies_by_id"][movie_id] for movie_id in movie_ids if movie_id in docs["movies_by_id"]]


ENGINES = {
    "MySQL (Relational)": MySQLBackend if _mysql_ok else RelationalBackend,
    "MongoDB (Document)": MongoBackend if _mongo_ok else DocumentBackend,
}