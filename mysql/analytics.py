"""Callable equivalents of 09_comparison_queries.sql (ops 1-5) and 06_advanced_queries.sql.

Every call executes SQL; there is no result cache. Pass connection= for warm-connection
timings or to group operations in a caller-owned transaction.
"""
from . import crud, db


def _rows(sql, params=(), *, connection=None):
    rows = db.fetch(sql, params, connection=connection)
    for row in rows:
        if "genres" in row:
            row["genres"] = row["genres"].split(", ") if row["genres"] else []
        for key, value in row.items():
            if value is not None and (key.endswith("_count") or key in ("genre_rank", "matching_genres", "total_actions", "release_decade")):
                row[key] = int(value)
    return rows


def movies_by_genre(genre_name, *, connection=None):
    return _rows("""SELECT m.movie_id, m.title, m.release_year FROM genres g
        JOIN movie_genres mg ON mg.genre_id = g.genre_id JOIN movies m ON m.movie_id = mg.movie_id
        WHERE g.genre_name = %s ORDER BY m.movie_id""", (crud.string(genre_name, "genre", 50),), connection=connection)


def average_rating(movie_id, *, connection=None):
    return _rows("SELECT ROUND(AVG(rating), 2) AS avg_rating FROM reviews WHERE movie_id = %s",
                 (crud.string(movie_id, "movie_id", 10),), connection=connection)[0]["avg_rating"]


def watchlist_with_genres(user_id, *, connection=None):
    return _rows("""SELECT m.movie_id, m.title,
        GROUP_CONCAT(g.genre_name ORDER BY g.genre_name SEPARATOR ', ') AS genres
        FROM watchlists w JOIN movies m ON m.movie_id = w.movie_id
        JOIN movie_genres mg ON mg.movie_id = m.movie_id JOIN genres g ON g.genre_id = mg.genre_id
        WHERE w.user_id = %s GROUP BY m.movie_id, m.title ORDER BY m.movie_id""",
        (crud.string(user_id, "user_id", 10),), connection=connection)


def filtered_discovery(genre, year_from, year_to, limit=25, *, connection=None):
    years = crud.bounds((year_from, year_to), "years", 1888, 2100, whole=True)
    return _rows("""SELECT m.movie_id, m.title, m.release_year, COUNT(r.review_id) AS review_count,
        ROUND(AVG(r.rating), 2) AS avg_rating FROM genres g
        JOIN movie_genres mg ON mg.genre_id = g.genre_id JOIN movies m ON m.movie_id = mg.movie_id
        LEFT JOIN reviews r ON r.movie_id = m.movie_id
        WHERE g.genre_name = %s AND m.release_year BETWEEN %s AND %s
        GROUP BY m.movie_id, m.title, m.release_year
        ORDER BY AVG(r.rating) DESC, review_count DESC, m.title COLLATE utf8mb4_bin, m.movie_id LIMIT %s""",
        (crud.string(genre, "genre", 50), *years, crud.integer(limit, "limit")), connection=connection)


# MySQL always aggregates live; this name gives Leticia an explicit live/live pairing.
filtered_discovery_live = filtered_discovery


def top_in_genre(genre, min_reviews=2, limit=10, *, connection=None):
    return _rows("""SELECT m.movie_id, m.title, COUNT(r.review_id) AS review_count,
        ROUND(AVG(r.rating), 2) AS avg_rating FROM genres g
        JOIN movie_genres mg ON mg.genre_id = g.genre_id JOIN movies m ON m.movie_id = mg.movie_id
        LEFT JOIN reviews r ON r.movie_id = m.movie_id WHERE g.genre_name = %s
        GROUP BY m.movie_id, m.title HAVING COUNT(r.review_id) >= %s
        ORDER BY AVG(r.rating) DESC, review_count DESC, m.title COLLATE utf8mb4_bin, m.movie_id LIMIT %s""",
        (crud.string(genre, "genre", 50), crud.integer(min_reviews, "min_reviews"), crud.integer(limit, "limit")), connection=connection)


def discovery_ranking(limit=20, *, connection=None):
    return _rows("""WITH review_stats AS (
            SELECT movie_id, AVG(rating) AS avg_rating, COUNT(*) AS review_count FROM reviews GROUP BY movie_id
        ), saves AS (SELECT movie_id, COUNT(*) AS watchlist_count FROM watchlists GROUP BY movie_id)
        SELECT m.movie_id, m.title, m.release_year,
            GROUP_CONCAT(g.genre_name ORDER BY g.genre_name SEPARATOR ', ') AS genres,
            ROUND(rs.avg_rating, 2) AS avg_rating, COALESCE(rs.review_count, 0) AS review_count,
            COALESCE(s.watchlist_count, 0) AS watchlist_count
        FROM movies m JOIN movie_genres mg ON mg.movie_id = m.movie_id JOIN genres g ON g.genre_id = mg.genre_id
        LEFT JOIN review_stats rs ON rs.movie_id = m.movie_id LEFT JOIN saves s ON s.movie_id = m.movie_id
        GROUP BY m.movie_id, m.title, m.release_year, rs.avg_rating, rs.review_count, s.watchlist_count
        ORDER BY rs.avg_rating DESC, review_count DESC, watchlist_count DESC, m.title COLLATE utf8mb4_bin, m.movie_id LIMIT %s""",
        (crud.integer(limit, "limit"),), connection=connection)


def top_per_genre(per_genre=3, min_reviews=2, *, connection=None):
    return _rows("""WITH stats AS (
            SELECT movie_id, AVG(rating) AS avg_rating, COUNT(*) AS review_count FROM reviews GROUP BY movie_id
        ), ranked AS (
            SELECT g.genre_name AS genre, m.movie_id, m.title, s.avg_rating, s.review_count,
                ROW_NUMBER() OVER (PARTITION BY g.genre_id ORDER BY s.avg_rating DESC, s.review_count DESC,
                                   m.title COLLATE utf8mb4_bin, m.movie_id) AS genre_rank
            FROM genres g JOIN movie_genres mg ON mg.genre_id = g.genre_id
            JOIN movies m ON m.movie_id = mg.movie_id JOIN stats s ON s.movie_id = m.movie_id
            WHERE s.review_count >= %s
        ) SELECT genre, genre_rank, movie_id, title, ROUND(avg_rating, 2) AS avg_rating, review_count
        FROM ranked WHERE genre_rank <= %s ORDER BY genre, genre_rank""",
        (crud.integer(min_reviews, "min_reviews", 1), crud.integer(per_genre, "per_genre", 1)), connection=connection)


def genre_health(*, connection=None):
    return _rows("""WITH stats AS (
            SELECT movie_id, SUM(rating) AS rating_sum, COUNT(*) AS review_count FROM reviews GROUP BY movie_id
        ), saves AS (SELECT movie_id, COUNT(*) AS watchlist_count FROM watchlists GROUP BY movie_id)
        SELECT g.genre_name AS genre, COUNT(*) AS movie_count, SUM(COALESCE(s.review_count, 0)) AS review_count,
            SUM(COALESCE(w.watchlist_count, 0)) AS watchlist_count,
            ROUND(SUM(s.rating_sum) / NULLIF(SUM(s.review_count), 0), 2) AS average_rating
        FROM genres g JOIN movie_genres mg ON mg.genre_id = g.genre_id
        LEFT JOIN stats s ON s.movie_id = mg.movie_id LEFT JOIN saves w ON w.movie_id = mg.movie_id
        GROUP BY g.genre_id, g.genre_name ORDER BY watchlist_count DESC, review_count DESC, genre""", connection=connection)


def recommend_movies(user_id, liked_threshold=7.0, limit=20, *, connection=None):
    user_id = crud.string(user_id, "user_id", 10)
    return _rows("""WITH preferred AS (
            SELECT mg.genre_id FROM reviews r JOIN movie_genres mg ON mg.movie_id = r.movie_id
            WHERE r.user_id = %s AND r.rating >= %s
            UNION SELECT mg.genre_id FROM watchlists w JOIN movie_genres mg ON mg.movie_id = w.movie_id WHERE w.user_id = %s
        ), stats AS (SELECT movie_id, AVG(rating) AS avg_rating, COUNT(*) AS review_count FROM reviews GROUP BY movie_id)
        SELECT m.movie_id, m.title, m.release_year, COUNT(*) AS matching_genres,
            ROUND(s.avg_rating, 2) AS avg_rating, COALESCE(s.review_count, 0) AS review_count
        FROM movies m JOIN movie_genres mg ON mg.movie_id = m.movie_id JOIN preferred p ON p.genre_id = mg.genre_id
        LEFT JOIN stats s ON s.movie_id = m.movie_id
        WHERE NOT EXISTS (SELECT 1 FROM reviews r WHERE r.user_id = %s AND r.movie_id = m.movie_id)
          AND NOT EXISTS (SELECT 1 FROM watchlists w WHERE w.user_id = %s AND w.movie_id = m.movie_id)
        GROUP BY m.movie_id, m.title, m.release_year, s.avg_rating, s.review_count
        ORDER BY matching_genres DESC, s.avg_rating DESC, review_count DESC, m.movie_id LIMIT %s""",
        (user_id, crud.rating_value(liked_threshold), user_id, user_id, user_id, crud.integer(limit, "limit")), connection=connection)


def engagement_leaderboard(limit=0, *, connection=None):
    limit = crud.integer(limit, "limit")
    sql = """SELECT user_id, username, review_count, average_rating_given, watchlist_count,
        latest_review_at AS last_review_at, latest_watchlist_addition AS last_saved_at,
        review_count + watchlist_count AS total_actions
        FROM v_user_activity_summary ORDER BY total_actions DESC, username"""
    return _rows(sql + (" LIMIT %s" if limit else ""), (limit,) if limit else (), connection=connection)


def director_stats(min_movies=3, *, connection=None):
    return _rows("""SELECT m.director, COUNT(DISTINCT m.movie_id) AS reviewed_movie_count,
        COUNT(*) AS review_count, ROUND(AVG(r.rating), 2) AS average_rating
        FROM movies m JOIN reviews r ON r.movie_id = m.movie_id
        WHERE m.director IS NOT NULL AND m.director <> '' GROUP BY m.director
        HAVING COUNT(DISTINCT m.movie_id) >= %s ORDER BY average_rating DESC, review_count DESC, director""",
        (crud.integer(min_movies, "min_movies", 1),), connection=connection)


def genre_trends_by_decade(min_movies=3, *, connection=None):
    return _rows("""WITH stats AS (
            SELECT movie_id, SUM(rating) AS rating_sum, COUNT(*) AS review_count FROM reviews GROUP BY movie_id
        ) SELECT (m.release_year DIV 10) * 10 AS release_decade, g.genre_name AS genre,
            COUNT(*) AS movie_count, SUM(COALESCE(s.review_count, 0)) AS review_count,
            ROUND(SUM(s.rating_sum) / NULLIF(SUM(s.review_count), 0), 2) AS average_rating
        FROM movies m JOIN movie_genres mg ON mg.movie_id = m.movie_id JOIN genres g ON g.genre_id = mg.genre_id
        LEFT JOIN stats s ON s.movie_id = m.movie_id GROUP BY release_decade, g.genre_id, g.genre_name
        HAVING COUNT(*) >= %s ORDER BY release_decade DESC, movie_count DESC, genre""",
        (crud.integer(min_movies, "min_movies", 1),), connection=connection)


def latest_review_feed(limit=25, *, connection=None):
    return _rows(crud.REVIEW_SELECT + " ORDER BY r.created_at DESC, r.review_id LIMIT %s",
                 (crud.integer(limit, "limit"),), connection=connection)


def latest_review_feed_with_posters(limit=25, *, connection=None):
    """Single-query version that includes poster_url and genres, avoiding a second catalogue fetch."""
    return _rows("""
        SELECT r.review_id, r.user_id, r.movie_id, r.rating,
               COALESCE(r.review_text, '') AS review_text,
               r.created_at, r.updated_at, u.username, m.title, m.release_year,
               COALESCE(m.poster_url, '') AS poster_url,
               COALESCE(gs.genres, '') AS genres
        FROM reviews r
        JOIN users u ON u.user_id = r.user_id
        JOIN movies m ON m.movie_id = r.movie_id
        LEFT JOIN (
            SELECT mg.movie_id,
                   GROUP_CONCAT(g.genre_name ORDER BY g.genre_name SEPARATOR ', ') AS genres
            FROM movie_genres mg JOIN genres g ON g.genre_id = mg.genre_id
            GROUP BY mg.movie_id
        ) gs ON gs.movie_id = m.movie_id
        ORDER BY r.created_at DESC, r.review_id LIMIT %s
    """, (crud.integer(limit, "limit"),), connection=connection)
