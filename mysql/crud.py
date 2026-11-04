"""Parameterized MySQL operations returning lists/dicts, numeric values and formatted timestamps.

All catalogue statistics are computed from reviews. No movie statistics or usernames
are denormalised. Optional connection= is caller-owned (including commit/rollback).
"""
import math
import re
import uuid
from decimal import Decimal
from numbers import Real

import numpy as np
import pymysql

from . import db
from .security import hash_password, verify_password

# Only fixed SQL fragments are composed. All user values are passed to execute separately.
MOVIE_SELECT = """
SELECT m.movie_id, m.poster_url, m.title, m.release_year, m.certificate, m.duration,
       COALESCE(m.description, '') AS description, COALESCE(m.director, '') AS director,
       COALESCE(m.`cast`, '') AS `cast`, m.imdb_votes,
       COALESCE(gs.genres, '') AS genres,
       rs.avg_rating, COALESCE(rs.review_count, 0) AS review_count
FROM movies m
LEFT JOIN (
    SELECT mg.movie_id, GROUP_CONCAT(g.genre_name ORDER BY g.genre_name SEPARATOR ', ') AS genres
    FROM movie_genres mg JOIN genres g ON g.genre_id = mg.genre_id GROUP BY mg.movie_id
) gs ON gs.movie_id = m.movie_id
LEFT JOIN (
    SELECT movie_id, AVG(rating) AS avg_rating, COUNT(*) AS review_count
    FROM reviews GROUP BY movie_id
) rs ON rs.movie_id = m.movie_id
"""
REVIEW_SELECT = """
SELECT r.review_id, r.user_id, r.movie_id, r.rating, COALESCE(r.review_text, '') AS review_text,
       r.created_at, r.updated_at, u.username, m.title, m.release_year
FROM reviews r JOIN users u ON u.user_id = r.user_id JOIN movies m ON m.movie_id = r.movie_id
"""
SORTS = {
    "Highest rated": "rs.avg_rating DESC, review_count DESC, m.imdb_votes DESC, m.movie_id",
    "Most reviewed": "review_count DESC, rs.avg_rating DESC, m.movie_id",
    "Newest": "m.release_year DESC, m.title COLLATE utf8mb4_bin, m.movie_id",
    "Oldest": "m.release_year, m.title COLLATE utf8mb4_bin, m.movie_id",
    "Title A–Z": "m.title COLLATE utf8mb4_bin, m.movie_id",
}


def string(value, name, max_len=255, *, empty=False):
    if not isinstance(value, str) or (not empty and not value.strip()) or len(value) > max_len:
        raise ValueError(f"{name} must be a string of at most {max_len} characters")
    return value


def rating_value(value):
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value) or not 1 <= value <= 10:
        raise ValueError("rating must be a finite number between 1 and 10")
    return round(float(value), 1)


def integer(value, name, minimum=0):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def bounds(values, name, lo, hi, *, whole=False):
    if not isinstance(values, (tuple, list)) or len(values) != 2:
        raise ValueError(f"{name} must contain two bounds")
    if any(isinstance(v, bool) or not isinstance(v, Real) or not math.isfinite(v) for v in values):
        raise ValueError(f"{name} bounds must be finite numbers")
    if not lo <= values[0] <= values[1] <= hi or (whole and any(int(v) != v for v in values)):
        raise ValueError(f"invalid {name} range")
    return tuple(int(v) if whole else float(v) for v in values)


def movie_rows(rows):
    for row in rows:
        row["genres"] = row["genres"].split(", ") if row.get("genres") else []
        row["review_count"] = int(row["review_count"])
        url = row.get("poster_url")
        row["poster_large"] = re.sub(r"\._V1_.*\.jpg$", "._V1_SX400.jpg", url) if isinstance(url, str) else ""
    return rows


def display_rating(value):
    """Same half-even, one-decimal presentation as pandas/CsvBackend."""
    return None if value is None else float(np.round(value, 1))


def search_movies(title="", genres=(), years=None, ratings=None, sort_by=None, *, connection=None):
    string(title, "title", empty=True)
    if not isinstance(genres, (tuple, list, set)):
        raise ValueError("genres must be a collection of names")
    selected = sorted({string(g, "genre", 50) for g in genres})
    if sort_by is not None and sort_by not in SORTS:
        raise ValueError("unknown sort mode")
    where, params = [], []
    if title:
        # Explicit escape character keeps %, _, ! and backslashes literal.
        pattern = title.replace("!", "!!").replace("%", "!%").replace("_", "!_")
        where.append("m.title COLLATE utf8mb4_0900_as_ci LIKE %s ESCAPE '!'")
        params.append(f"%{pattern}%")
    if selected:
        placeholders = ", ".join(["%s"] * len(selected))
        where.append("""m.movie_id IN (
            SELECT mg.movie_id FROM movie_genres mg JOIN genres g ON g.genre_id = mg.genre_id
            WHERE g.genre_name IN (""" + placeholders + ") GROUP BY mg.movie_id HAVING COUNT(*) = %s)")
        params.extend([*selected, len(selected)])
    if years is not None:
        where.append("m.release_year BETWEEN %s AND %s")
        params.extend(bounds(years, "years", 1888, 2100, whole=True))
    active_ratings = None
    if ratings is not None:
        pair = bounds(ratings, "ratings", 0, 10)
        if pair != (0.0, 10.0):
            active_ratings = pair
            # SQL reduces the candidates; exact half-even boundary ties are settled below.
            where.append("rs.avg_rating BETWEEN %s AND %s")
            params.extend([Decimal(str(pair[0])) - Decimal("0.05"),
                           Decimal(str(pair[1])) + Decimal("0.05")])
    sql = MOVIE_SELECT + (" WHERE " + " AND ".join(where) if where else "")
    sql += " ORDER BY " + SORTS[sort_by or "Highest rated"]
    rows = movie_rows(db.fetch(sql, tuple(params), connection=connection))
    if active_ratings:
        rows = [r for r in rows if r["avg_rating"] is not None and
                active_ratings[0] <= display_rating(r["avg_rating"]) <= active_ratings[1]]
    return rows


def get_movie_details(movie_id, *, connection=None):
    rows = movie_rows(db.fetch(MOVIE_SELECT + " WHERE m.movie_id = %s",
                              (string(movie_id, "movie_id", 10),), connection=connection))
    return rows[0] if rows else None


get_movie = get_movie_details


def genre_names(*, connection=None):
    return [r["genre_name"] for r in db.fetch("SELECT genre_name FROM genres ORDER BY genre_name", connection=connection)]


def year_bounds(*, connection=None):
    row = db.fetch("SELECT MIN(release_year) AS lo, MAX(release_year) AS hi FROM movies", connection=connection)[0]
    return row["lo"], row["hi"]


def movie_reviews(movie_id, *, connection=None):
    return db.fetch(REVIEW_SELECT + " WHERE r.movie_id = %s ORDER BY r.updated_at DESC, r.review_id DESC",
                    (string(movie_id, "movie_id", 10),), connection=connection)


def user_reviews(user_id, *, connection=None):
    return db.fetch(REVIEW_SELECT + " WHERE r.user_id = %s ORDER BY r.updated_at DESC, r.review_id DESC",
                    (string(user_id, "user_id", 10),), connection=connection)


def user_review_for(user_id, movie_id, *, connection=None):
    rows = db.fetch(REVIEW_SELECT + " WHERE r.user_id = %s AND r.movie_id = %s",
                    (string(user_id, "user_id", 10), string(movie_id, "movie_id", 10)), connection=connection)
    return rows[0] if rows else None


# Fixed table/column metadata only; neither is supplied by external input.
INSERTS = {
    "users": ("U", "user_id", "INSERT INTO users (user_id, username, email, password_hash) VALUES (%s, %s, %s, %s)"),
    "reviews": ("R", "review_id", "INSERT INTO reviews (review_id, user_id, movie_id, rating, review_text) VALUES (%s, %s, %s, %s, %s)"),
    "watchlists": ("W", "watchlist_id", "INSERT INTO watchlists (watchlist_id, user_id, movie_id) VALUES (%s, %s, %s)"),
}


def _insert(table, values, *, connection=None):
    prefix, column, sql = INSERTS[table]
    with db.session(connection) as conn, conn.cursor() as cursor:
        for _ in range(5):
            new_id = prefix + uuid.uuid4().hex[:9]
            try:
                cursor.execute(sql, (new_id, *values))
                return new_id
            except pymysql.IntegrityError as exc:
                if exc.args[0] == 1062:
                    cursor.execute(f"SELECT {column} FROM {table} WHERE {column} = %s", (new_id,))
                    if cursor.fetchone():
                        continue  # retry an ID collision; business-key duplicates remain errors
                raise ValueError("duplicate entry or unknown related user/movie") from exc
        raise OSError("Could not allocate a unique identifier; retry the operation.")


def add_review(user_id, movie_id, rating, text="", *, connection=None):
    return _insert("reviews", (string(user_id, "user_id", 10), string(movie_id, "movie_id", 10),
                               rating_value(rating), string(text, "review text", 1000, empty=True)), connection=connection)


def update_review(review_id, rating, text, user_id=None, *, connection=None):
    params = [rating_value(rating), string(text, "review text", 1000, empty=True), string(review_id, "review_id", 10)]
    sql = "UPDATE reviews SET rating = %s, review_text = %s, updated_at = CURRENT_TIMESTAMP WHERE review_id = %s"
    if user_id is not None:
        sql += " AND user_id = %s"
        params.append(string(user_id, "user_id", 10))
    return db.execute(sql, tuple(params), connection=connection) > 0


def delete_review(review_id, user_id=None, *, connection=None):
    params = [string(review_id, "review_id", 10)]
    sql = "DELETE FROM reviews WHERE review_id = %s"
    if user_id is not None:
        sql += " AND user_id = %s"
        params.append(string(user_id, "user_id", 10))
    return db.execute(sql, tuple(params), connection=connection) > 0


def get_watchlist(user_id, *, connection=None):
    return movie_rows(db.fetch(MOVIE_SELECT.replace("SELECT m.movie_id", "SELECT w.added_at, m.movie_id", 1) +
        " JOIN watchlists w ON w.movie_id = m.movie_id WHERE w.user_id = %s ORDER BY w.added_at DESC, m.movie_id",
        (string(user_id, "user_id", 10),), connection=connection))


def watchlist_ids(user_id, *, connection=None):
    return {r["movie_id"] for r in db.fetch("SELECT movie_id FROM watchlists WHERE user_id = %s",
                                          (string(user_id, "user_id", 10),), connection=connection)}


def add_to_watchlist(user_id, movie_id, *, connection=None):
    user_id, movie_id = string(user_id, "user_id", 10), string(movie_id, "movie_id", 10)
    try:
        _insert("watchlists", (user_id, movie_id), connection=connection)
        return True
    except ValueError:
        # Only the existing business key makes this operation an idempotent no-op.
        if db.fetch("SELECT watchlist_id FROM watchlists WHERE user_id = %s AND movie_id = %s",
                    (user_id, movie_id), connection=connection):
            return False
        raise


def remove_from_watchlist(user_id, movie_id, *, connection=None):
    return db.execute("DELETE FROM watchlists WHERE user_id = %s AND movie_id = %s",
                      (string(user_id, "user_id", 10), string(movie_id, "movie_id", 10)), connection=connection) > 0


def get_user(user_id, *, connection=None):
    rows = db.fetch("SELECT user_id, username, email, created_at FROM users WHERE user_id = %s",
                    (string(user_id, "user_id", 10),), connection=connection)
    return rows[0] if rows else None


def list_users(*, connection=None):
    return db.fetch("SELECT user_id, username, email FROM users ORDER BY user_id", connection=connection)


def username_taken(username, *, connection=None):
    return bool(db.fetch("SELECT user_id FROM users WHERE username = %s", (string(username, "username", 50).strip(),), connection=connection))


def email_taken(email, *, connection=None):
    return bool(db.fetch("SELECT user_id FROM users WHERE email = %s", (string(email, "email").strip().lower(),), connection=connection))


def _account(username, email):
    username, email = string(username, "username", 50).strip(), string(email, "email").strip().lower()
    if not re.fullmatch(r"[A-Za-z0-9_.]{3,30}", username) or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise ValueError("invalid username or email")
    return username, email


def register_user(username, email, password, *, connection=None):
    username, email = _account(username, email)
    if not isinstance(password, str) or len(password) < 8:
        raise ValueError("password must have at least 8 characters")
    uid = _insert("users", (username, email, hash_password(password)), connection=connection)
    return {"user_id": uid, "username": username, "email": email}


def authenticate(username, password, *, connection=None):
    if not isinstance(password, str):
        raise ValueError("password must be a string")
    rows = db.fetch("SELECT user_id, username, email, password_hash FROM users WHERE username = %s",
                    (string(username, "username", 50, empty=True).strip(),), connection=connection)
    if not rows or not verify_password(password, rows[0].pop("password_hash")):
        return None
    return rows[0]


def update_user(user_id, username, email, *, connection=None):
    username, email = _account(username, email)
    try:
        return db.execute("UPDATE users SET username = %s, email = %s WHERE user_id = %s",
                          (username, email, string(user_id, "user_id", 10)), connection=connection) > 0
    except pymysql.IntegrityError as exc:
        raise ValueError("username or email already exists") from exc


def delete_user(user_id, *, connection=None):
    """Related reviews/watchlists are removed by the existing ON DELETE CASCADE constraints."""
    return db.execute("DELETE FROM users WHERE user_id = %s", (string(user_id, "user_id", 10),), connection=connection) > 0
