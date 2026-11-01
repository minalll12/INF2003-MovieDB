"""Counterpart of mysql/04c_constraint_tests.sql: every statement below SHOULD be rejected.
Needs a real MongoDB (validators + unique indexes).     python validation_demo.py"""
from datetime import datetime

from pymongo.errors import PyMongoError

from . import crud
from .db import get_db

now = datetime.now()
db = get_db()
existing = db.reviews.find_one()          # a review that really exists, so a copy of its (user, movie) must be rejected
cases = {
    "duplicate review (user, movie) -> unique index": lambda: db.reviews.insert_one(
        {"_id": "RX001", "user_id": existing["user_id"], "movie_id": existing["movie_id"], "username": "x", "rating": 5.0,
         "created_at": now, "updated_at": now}),
    "rating 11 -> $jsonSchema maximum": lambda: db.reviews.insert_one(
        {"_id": "RX002", "user_id": "U001", "movie_id": "M0999", "username": "x", "rating": 11.0, "created_at": now, "updated_at": now}),
    "rating stored as string -> $jsonSchema type": lambda: db.reviews.insert_one(
        {"_id": "RX003", "user_id": "U001", "movie_id": "M0998", "username": "x", "rating": "9", "created_at": now, "updated_at": now}),
    "duplicate username -> unique index": lambda: db.users.insert_one(
        {"_id": "UX01", "username": "dup", "username_lower": db.users.find_one()["username_lower"], "email": "a@b.co",
         "password_hash": "pbkdf2_sha256$1$aa$bb", "created_at": now}),
    "plain-text password -> $jsonSchema pattern": lambda: db.users.insert_one(
        {"_id": "UX02", "username": "abc", "username_lower": "abc", "email": "q@b.co", "password_hash": "secret", "created_at": now}),
    "release_year 1500 -> $jsonSchema minimum": lambda: db.movies.insert_one(
        {"_id": "MX01", "title": "t", "release_year": 1500, "duration": 90, "genres": [], "imdb_votes": 0, "review_count": 0}),
    "review for unknown movie -> app-level FK check": lambda: crud.add_review("U001", "M9999", 5.0, "x"),
}
for label, fn in cases.items():
    try:
        fn()
        print("ACCEPTED (unexpected):", label)
    except (PyMongoError, ValueError) as e:
        print("rejected as expected :", label, "|", type(e).__name__)

# remove anything a wrongly accepted case could have left behind
db.reviews.delete_many({"_id": {"$regex": "^RX"}})
db.users.delete_many({"_id": {"$regex": "^UX"}})
db.movies.delete_many({"_id": {"$regex": "^MX"}})
