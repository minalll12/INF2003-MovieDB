"""MongoDB implementation of the data-access operations (users, movies, reviews, watchlists).

Security: every filter is a typed query document built from validated values - no string-built
queries, no $where, search text is regex-escaped, and user input must be a plain string/number
(so {"$ne": ""} operator-injection payloads are rejected). Only a review's owner may edit/delete it
when user_id is supplied.
"""
import re
from datetime import datetime

from pymongo import ASCENDING, DESCENDING, ReturnDocument
from pymongo.errors import DuplicateKeyError

from .config import MAX_RATING, MAX_REVIEW_LEN, MIN_RATING
from .db import get_db
from .security import hash_password, verify_password

EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


def _now() -> datetime:
    return datetime.now().replace(microsecond=0)  # naive local time, like the CSVs / MySQL DATETIME


def _s(value, name, max_len=None) -> str:
    """Operator-injection guard: user-supplied text must be a plain string."""
    if not isinstance(value, str):
        raise ValueError(f"{name} must be text")
    value = value.strip()
    if max_len and len(value) > max_len:
        raise ValueError(f"{name} is too long (max {max_len})")
    return value


def _rating(value) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("rating must be a number")
    value = round(float(value), 1)
    if not MIN_RATING <= value <= MAX_RATING:
        raise ValueError(f"rating must be between {MIN_RATING} and {MAX_RATING}")
    return value


def next_id(collection: str, prefix: str, width: int = 4) -> str:
    """Atomic sequence ($inc on a counters document) - the MongoDB answer to AUTO_INCREMENT."""
    doc = get_db().counters.find_one_and_update({"_id": collection}, {"$inc": {"seq": 1}}, upsert=True,
                                                return_document=ReturnDocument.AFTER)
    return f"{prefix}{doc['seq']:0{width}d}"


# ------------------------------------------------------------------ users
def username_taken(username: str) -> bool:
    return get_db().users.count_documents({"username_lower": _s(username, "username").lower()}, limit=1) > 0


def email_taken(email: str) -> bool:
    return get_db().users.count_documents({"email": _s(email, "email").lower()}, limit=1) > 0


def register_user(username: str, email: str, password: str) -> dict:
    username, email = _s(username, "username", 50), _s(email, "email", 255).lower()
    if len(username) < 3:
        raise ValueError("username must be at least 3 characters")
    if not EMAIL_RE.fullmatch(email):
        raise ValueError("invalid email address")
    if len(_s(password, "password")) < 8:
        raise ValueError("password must be at least 8 characters")
    uid = next_id("users", "U", 3)
    try:
        get_db().users.insert_one({"_id": uid, "username": username, "username_lower": username.lower(), "email": email,
                                   "password_hash": hash_password(password), "created_at": _now()})
    except DuplicateKeyError:
        raise ValueError("username or email already registered")
    return get_user(uid)


def authenticate(username: str, password: str):
    user = get_db().users.find_one({"username_lower": _s(username, "username").lower()})
    if user and verify_password(_s(password, "password"), user["password_hash"]):
        return {"user_id": user["_id"], "username": user["username"], "email": user["email"]}
    return None


def get_user(user_id: str):
    u = get_db().users.find_one({"_id": _s(user_id, "user_id")}, {"password_hash": 0})
    return {"user_id": u["_id"], "username": u["username"], "email": u["email"], "created_at": u["created_at"]} if u else None


def list_users():
    return [{"user_id": u["_id"], "username": u["username"], "email": u["email"]}
            for u in get_db().users.find({}, {"username": 1, "email": 1}).sort("_id", ASCENDING)]


# ------------------------------------------------------------------ movies
SORTS = {
    "Highest rated": [("avg_rating", DESCENDING), ("review_count", DESCENDING), ("imdb_votes", DESCENDING)],
    "Most reviewed": [("review_count", DESCENDING), ("avg_rating", DESCENDING)],
    "Newest": [("release_year", DESCENDING), ("title", ASCENDING)],
    "Oldest": [("release_year", ASCENDING), ("title", ASCENDING)],
    "Title A–Z": [("title", ASCENDING)],
}


def search_movies(title: str = "", genres=(), years=None, ratings=None, sort_by=None, limit: int = 0):
    """Browse / search / filter. genres = ALL of the selected genres (like the UI); ratings = (lo, hi)."""
    flt = {}
    if title:
        flt["title"] = {"$regex": re.escape(_s(title, "title", 100)), "$options": "i"}
    if genres:
        flt["genres"] = {"$all": [_s(g, "genre") for g in genres]}   # multikey index
    if years:
        flt["release_year"] = {"$gte": int(years[0]), "$lte": int(years[1])}
    if ratings and tuple(ratings) != (0.0, 10.0):
        # UI shows ratings rounded to 1 dp, so pre-filter on the widened window (a superset - exact
        # rounding ties are settled by MongoBackend on the displayed value)
        flt["avg_rating"] = {"$gte": float(ratings[0]) - 0.05, "$lte": float(ratings[1]) + 0.05}
    return list(get_db().movies.find(flt).sort(SORTS.get(sort_by, SORTS["Highest rated"])).limit(limit))


def text_search_movies(text: str, limit: int = 20):
    """Ranked full-text search ($text index, weighted title > director > cast > description)."""
    return list(get_db().movies.find({"$text": {"$search": _s(text, "text", 100)}}, {"score": {"$meta": "textScore"}})
                .sort([("score", {"$meta": "textScore"})]).limit(limit))


def get_movie(movie_id: str):
    return get_db().movies.find_one({"_id": _s(movie_id, "movie_id")})


def genre_names():
    return sorted(get_db().movies.distinct("genres"))


def year_bounds():
    agg = next(iter(get_db().movies.aggregate([{"$group": {"_id": None, "lo": {"$min": "$release_year"},
                                                              "hi": {"$max": "$release_year"}}}])))
    return agg["lo"], agg["hi"]


# ------------------------------------------------------------------ reviews
def refresh_movie_stats(movie_id: str) -> None:
    """Recompute avg_rating / review_count from reviews (idempotent - safe under concurrent writes)."""
    db = get_db()
    agg = next(iter(db.reviews.aggregate([{"$match": {"movie_id": movie_id}},
                                          {"$group": {"_id": None, "avg": {"$avg": "$rating"}, "n": {"$sum": 1}}}])), None)
    has = bool(agg and agg["n"])
    db.movies.update_one({"_id": movie_id}, {"$set": {
        "avg_rating": agg["avg"] if has else None, "review_count": agg["n"] if has else 0}})


def add_review(user_id: str, movie_id: str, rating, text: str = "") -> str:
    db = get_db()
    user = db.users.find_one({"_id": _s(user_id, "user_id")}, {"username": 1})
    if not user or not db.movies.count_documents({"_id": _s(movie_id, "movie_id")}, limit=1):
        raise ValueError("unknown user or movie")          # app-level foreign-key check
    rid, now = None, _now()
    doc = {"movie_id": movie_id, "user_id": user_id, "username": user["username"], "rating": _rating(rating),
           "review_text": _s(text or "", "review text", MAX_REVIEW_LEN), "created_at": now, "updated_at": now}
    try:
        doc["_id"] = rid = next_id("reviews", "R")
        db.reviews.insert_one(doc)
    except DuplicateKeyError:
        raise ValueError("you have already reviewed this movie - edit your review instead")
    refresh_movie_stats(movie_id)
    return rid


def update_review(review_id: str, rating, text: str, user_id: str = None) -> bool:
    flt = {"_id": _s(review_id, "review_id")}
    if user_id is not None:
        flt["user_id"] = _s(user_id, "user_id")             # owner-only
    doc = get_db().reviews.find_one_and_update(
        flt, {"$set": {"rating": _rating(rating), "review_text": _s(text or "", "review text", MAX_REVIEW_LEN),
                       "updated_at": _now()}}, return_document=ReturnDocument.AFTER)
    if doc:
        refresh_movie_stats(doc["movie_id"])
    return doc is not None


def delete_review(review_id: str, user_id: str = None) -> bool:
    flt = {"_id": _s(review_id, "review_id")}
    if user_id is not None:
        flt["user_id"] = _s(user_id, "user_id")
    doc = get_db().reviews.find_one_and_delete(flt)
    if doc:
        refresh_movie_stats(doc["movie_id"])
    return doc is not None


def get_user_review_for(user_id: str, movie_id: str):
    return get_db().reviews.find_one({"user_id": _s(user_id, "user_id"), "movie_id": _s(movie_id, "movie_id")})


def get_reviews_for_movie(movie_id: str):
    return list(get_db().reviews.find({"movie_id": _s(movie_id, "movie_id")}).sort("updated_at", DESCENDING))


def get_reviews_by_user(user_id: str):
    return list(get_db().reviews.find({"user_id": _s(user_id, "user_id")}).sort("updated_at", DESCENDING))


# ------------------------------------------------------------------ watchlist
def watchlist_ids(user_id: str) -> set:
    return {w["movie_id"] for w in get_db().watchlists.find({"user_id": _s(user_id, "user_id")}, {"movie_id": 1})}


def add_to_watchlist(user_id: str, movie_id: str) -> bool:
    """True if added, False if already saved (unique index makes it idempotent)."""
    db = get_db()
    if not db.movies.count_documents({"_id": _s(movie_id, "movie_id")}, limit=1) or \
            not db.users.count_documents({"_id": _s(user_id, "user_id")}, limit=1):
        raise ValueError("unknown user or movie")
    if db.watchlists.count_documents({"user_id": user_id, "movie_id": movie_id}, limit=1):
        return False
    try:
        db.watchlists.insert_one({"_id": next_id("watchlists", "W"), "user_id": user_id, "movie_id": movie_id, "added_at": _now()})
        return True
    except DuplicateKeyError:
        return False


def remove_from_watchlist(user_id: str, movie_id: str) -> bool:
    return get_db().watchlists.delete_one({"user_id": _s(user_id, "user_id"), "movie_id": _s(movie_id, "movie_id")}).deleted_count == 1


def get_watchlist(user_id: str):
    """Watchlist entries with the full movie document (one $lookup), newest first."""
    rows = get_db().watchlists.aggregate([
        {"$match": {"user_id": _s(user_id, "user_id")}}, {"$sort": {"added_at": -1}},
        {"$lookup": {"from": "movies", "localField": "movie_id", "foreignField": "_id", "as": "movie"}},
        {"$unwind": "$movie"}])
    return [{**r["movie"], "added_at": r["added_at"]} for r in rows]
