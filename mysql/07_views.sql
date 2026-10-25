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
       MIN(r.rating) AS lowest_rating,
       MAX(r.rating) AS highest_rating,
       MAX(r.updated_at) AS latest_review_at
FROM reviews r
GROUP BY r.movie_id;

-- One discovery-ready row per movie, including genres and engagement.
CREATE VIEW v_movie_catalog AS
SELECT m.movie_id, m.title, m.release_year, m.certificate, m.duration,
       m.description, m.director, m.`cast`, m.imdb_votes, m.poster_url,
       GROUP_CONCAT(DISTINCT g.genre_name
                    ORDER BY g.genre_name SEPARATOR ', ') AS genres,
       COALESCE(rs.review_count, 0) AS review_count,
       rs.average_rating,
       COUNT(DISTINCT w.watchlist_id) AS watchlist_count
FROM movies m
JOIN movie_genres mg ON mg.movie_id = m.movie_id
JOIN genres g        ON g.genre_id = mg.genre_id
LEFT JOIN v_movie_review_stats rs ON rs.movie_id = m.movie_id
LEFT JOIN watchlists w            ON w.movie_id = m.movie_id
GROUP BY m.movie_id, m.title, m.release_year, m.certificate, m.duration,
         m.description, m.director, m.`cast`, m.imdb_votes, m.poster_url,
         rs.review_count, rs.average_rating;

-- One row per user for profile/dashboard reporting.
CREATE VIEW v_user_activity_summary AS
SELECT u.user_id, u.username, u.created_at,
       COUNT(DISTINCT r.review_id) AS review_count,
       ROUND(AVG(r.rating), 2) AS average_rating_given,
       COUNT(DISTINCT w.watchlist_id) AS watchlist_count,
       MAX(r.updated_at) AS latest_review_at,
       MAX(w.added_at) AS latest_watchlist_addition
FROM users u
LEFT JOIN reviews r    ON r.user_id = u.user_id
LEFT JOIN watchlists w ON w.user_id = u.user_id
GROUP BY u.user_id, u.username, u.created_at;

-- Quick verification after creation.
SELECT * FROM v_movie_catalog
ORDER BY average_rating DESC, review_count DESC
LIMIT 10;

SELECT * FROM v_user_activity_summary
ORDER BY review_count + watchlist_count DESC, username
LIMIT 10;
