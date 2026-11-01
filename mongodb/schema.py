"""Collections, $jsonSchema validators, indexes, counters and the view.

Document model - same string keys as MySQL (M0001, U001, R0001, W0001) become each document's _id:

users       {_id, username, username_lower, email, password_hash, created_at}
movies      {_id, title, release_year, certificate, duration, genres[], description, director,
             cast[], imdb_votes, poster_url, avg_rating, review_count}
reviews     {_id, movie_id, user_id, username*, rating, review_text, created_at, updated_at}
watchlists  {_id, user_id, movie_id, added_at}
counters    {_id: "reviews"|"watchlists"|"users", seq}      # replaces AUTO_INCREMENT

* denormalised so a movie's review list needs no join.
  avg_rating / review_count on movies is the "computed pattern": recomputed (unrounded) from reviews on every
  review write, so the hottest read (browse/sort by rating) never aggregates.
MySQL's genres + movie_genres tables disappear: genres[] is embedded and indexed (multikey).
"""
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import CollectionInvalid, OperationFailure, PyMongoError

from .config import MAX_RATING, MAX_REVIEW_LEN, MIN_RATING

VALIDATORS = {
    "users": {
        "bsonType": "object",
        "required": ["username", "username_lower", "email", "password_hash", "created_at"],
        "properties": {
            "_id": {"bsonType": "string"},
            "username": {"bsonType": "string", "minLength": 3, "maxLength": 50},
            "email": {"bsonType": "string", "maxLength": 255, "pattern": r"^[^@\s]+@[^@\s]+\.[^@\s]+$"},
            "password_hash": {"bsonType": "string", "pattern": r"^pbkdf2_sha256\$"},
            "created_at": {"bsonType": "date"},
        },
    },
    "movies": {
        "bsonType": "object",
        "required": ["title", "release_year", "duration", "genres", "imdb_votes", "review_count"],
        "properties": {
            "_id": {"bsonType": "string"},
            "title": {"bsonType": "string", "minLength": 1, "maxLength": 255},
            "release_year": {"bsonType": ["int", "long"], "minimum": 1888, "maximum": 2100},
            "duration": {"bsonType": ["int", "long"], "minimum": 1},
            "genres": {"bsonType": "array", "uniqueItems": True, "items": {"bsonType": "string"}},
            "cast": {"bsonType": "array", "items": {"bsonType": "string"}},
            "imdb_votes": {"bsonType": ["int", "long"], "minimum": 0},
            "avg_rating": {"bsonType": ["double", "null"], "minimum": MIN_RATING, "maximum": MAX_RATING},
            "review_count": {"bsonType": ["int", "long"], "minimum": 0},
        },
    },
    "reviews": {
        "bsonType": "object",
        "required": ["movie_id", "user_id", "username", "rating", "created_at", "updated_at"],
        "properties": {
            "_id": {"bsonType": "string"},
            "movie_id": {"bsonType": "string"},
            "user_id": {"bsonType": "string"},
            "username": {"bsonType": "string"},
            "rating": {"bsonType": "double", "minimum": MIN_RATING, "maximum": MAX_RATING},
            "review_text": {"bsonType": ["string", "null"], "maxLength": MAX_REVIEW_LEN},
            "created_at": {"bsonType": "date"},
            "updated_at": {"bsonType": "date"},
        },
    },
    "watchlists": {
        "bsonType": "object",
        "required": ["user_id", "movie_id", "added_at"],
        "properties": {
            "_id": {"bsonType": "string"},
            "user_id": {"bsonType": "string"},
            "movie_id": {"bsonType": "string"},
            "added_at": {"bsonType": "date"},
        },
    },
}

# (collection, keys, options). Each one is tied to a query pattern, like mysql/08_indexes.sql.
INDEXES = [
    ("users", [("username_lower", ASCENDING)], {"unique": True, "name": "uq_username"}),
    ("users", [("email", ASCENDING)], {"unique": True, "name": "uq_email"}),
    ("movies", [("genres", ASCENDING)], {"name": "ix_genres"}),                       # multikey: movies_by_genre
    ("movies", [("release_year", ASCENDING), ("title", ASCENDING)], {"name": "ix_year_title"}),
    ("movies", [("avg_rating", DESCENDING), ("review_count", DESCENDING)], {"name": "ix_rating"}),
    ("movies", [("director", ASCENDING)], {"name": "ix_director"}),
    ("reviews", [("user_id", ASCENDING), ("movie_id", ASCENDING)], {"unique": True, "name": "uq_review_user_movie"}),
    ("reviews", [("movie_id", ASCENDING), ("rating", ASCENDING)], {"name": "ix_reviews_movie_rating"}),
    ("reviews", [("created_at", DESCENDING)], {"name": "ix_reviews_created"}),         # latest-review feed
    ("watchlists", [("user_id", ASCENDING), ("movie_id", ASCENDING)], {"unique": True, "name": "uq_watch_user_movie"}),
    ("watchlists", [("user_id", ASCENDING), ("added_at", DESCENDING)], {"name": "ix_watch_user_added"}),
    ("watchlists", [("movie_id", ASCENDING)], {"name": "ix_watch_movie"}),
]

TEXT_INDEX = ("movies", [("title", "text"), ("director", "text"), ("cast", "text"), ("description", "text")],
              {"name": "tx_movies", "weights": {"title": 10, "director": 5, "cast": 3, "description": 1}})

# MongoDB counterpart of mysql/07_views.sql: v_movie_catalog
VIEW_NAME = "v_movie_catalog"
VIEW_PIPELINE = [
    {"$project": {"title": 1, "release_year": 1, "certificate": 1, "duration": 1, "genres": 1,
                  "avg_rating": 1, "review_count": 1}},
]


def create_schema(db, drop_existing: bool = False) -> None:
    """Create collections with validators, indexes and the view (idempotent)."""
    if drop_existing:
        for name in [VIEW_NAME, *VALIDATORS, "counters"]:
            db.drop_collection(name)

    for name, schema in VALIDATORS.items():
        try:
            db.create_collection(name, validator={"$jsonSchema": schema}, validationAction="error")
        except NotImplementedError:
            pass  # mongomock (tests) has no validators; real MongoDB does
        except CollectionInvalid:  # already exists -> refresh the validator
            try:
                db.command("collMod", name, validator={"$jsonSchema": schema}, validationAction="error")
            except (OperationFailure, NotImplementedError):
                pass

    for coll, keys, opts in INDEXES:
        db[coll].create_index(keys, **opts)
    coll, keys, opts = TEXT_INDEX
    try:
        db[coll].create_index(keys, **opts)
    except (PyMongoError, NotImplementedError):
        pass  # mongomock has no text indexes

    if VIEW_NAME not in db.list_collection_names():
        try:
            db.create_collection(VIEW_NAME, viewOn="movies", pipeline=VIEW_PIPELINE)
        except Exception:  # views unsupported by mongomock
            pass


if __name__ == "__main__":
    from .db import get_db

    create_schema(get_db())
    print("Collections, validators, indexes and view created.")
