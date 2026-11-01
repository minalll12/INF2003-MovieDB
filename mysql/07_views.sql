-- =====================================================================
-- 07_views.sql
-- Purpose : Reusable read models for movie discovery and user activity.
-- Safety  : Existing views are dropped in dependency order before creation.
-- =====================================================================

USE movie_platform;

DROP VIEW IF EXISTS v_movie_catalog;
DROP VIEW IF EXISTS v_user_activity_summary;
DROP VIEW IF EXISTS v_movie_review_stats;

-- One row per reviewed movie. Kept separate so other queries can reuse it.
CREATE VIEW v_movie_review_stats AS
SELECT r.movie_id,
       COUNT(*) AS review_count,
       ROUND(AVG(r.rating), 2) AS average_rating,
       AVG(r.rating) AS avg_rating, -- full precision for the Python/UI adapter
       MIN(r.rating) AS lowest_rating,
       MAX(r.rating) AS highest_rating,
       MAX(r.updated_at) AS latest_review_at
FROM reviews r
GROUP BY r.movie_id;

-- Aggregate child tables separately to avoid a genres x watchlists product.
-- Keep average_rating for existing consumers; avg_rating is the UI name.
CREATE VIEW v_movie_catalog AS
SELECT m.movie_id, m.title, m.release_year, m.certificate, m.duration,
       m.description, m.director, m.`cast`, m.imdb_votes, m.poster_url,
       COALESCE(gs.genres, '') AS genres,
       COALESCE(rs.review_count, 0) AS review_count,
       rs.average_rating, rs.avg_rating,
       COALESCE(ws.watchlist_count, 0) AS watchlist_count
FROM movies m
LEFT JOIN (
    SELECT mg.movie_id, GROUP_CONCAT(g.genre_name ORDER BY g.genre_name SEPARATOR ', ') AS genres
    FROM movie_genres mg JOIN genres g ON g.genre_id = mg.genre_id GROUP BY mg.movie_id
) gs ON gs.movie_id = m.movie_id
LEFT JOIN v_movie_review_stats rs ON rs.movie_id = m.movie_id
LEFT JOIN (
    SELECT movie_id, COUNT(*) AS watchlist_count FROM watchlists GROUP BY movie_id
) ws ON ws.movie_id = m.movie_id;

-- One row per user for profile/dashboard reporting.
CREATE VIEW v_user_activity_summary AS
SELECT u.user_id, u.username, u.created_at,
       COALESCE(r.review_count, 0) AS review_count,
       r.average_rating_given,
       COALESCE(w.watchlist_count, 0) AS watchlist_count,
       r.latest_review_at,
       w.latest_watchlist_addition
FROM users u
LEFT JOIN (
    SELECT user_id, COUNT(*) AS review_count, ROUND(AVG(rating), 2) AS average_rating_given,
           MAX(updated_at) AS latest_review_at FROM reviews GROUP BY user_id
) r ON r.user_id = u.user_id
LEFT JOIN (
    SELECT user_id, COUNT(*) AS watchlist_count, MAX(added_at) AS latest_watchlist_addition
    FROM watchlists GROUP BY user_id
) w ON w.user_id = u.user_id;

-- Quick verification after creation.
SELECT * FROM v_movie_catalog
ORDER BY average_rating DESC, review_count DESC
LIMIT 10;

SELECT * FROM v_user_activity_summary
ORDER BY review_count + watchlist_count DESC, username
LIMIT 10;
