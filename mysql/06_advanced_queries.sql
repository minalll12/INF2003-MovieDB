-- =====================================================================
-- 06_advanced_queries.sql
-- Purpose : Eight read-only joins and aggregations for movie discovery,
--           recommendations, engagement reporting and catalogue analysis.
-- Requires: MySQL 8.0+ (CTEs and window functions are used).
-- =====================================================================

USE movie_platform;

-- ---------------------------------------------------------------------
-- 1. Discovery ranking: rating, review volume, saves and all genres
-- ---------------------------------------------------------------------
WITH review_stats AS (
    SELECT movie_id, AVG(rating) AS average_rating, COUNT(*) AS review_count
    FROM reviews
    GROUP BY movie_id
),
watchlist_stats AS (
    SELECT movie_id, COUNT(*) AS watchlist_count
    FROM watchlists
    GROUP BY movie_id
)
SELECT m.movie_id, m.title, m.release_year,
       GROUP_CONCAT(g.genre_name ORDER BY g.genre_name SEPARATOR ', ') AS genres,
       ROUND(rs.average_rating, 2) AS average_rating,
       COALESCE(rs.review_count, 0) AS review_count,
       COALESCE(ws.watchlist_count, 0) AS watchlist_count
FROM movies m
JOIN movie_genres mg ON mg.movie_id = m.movie_id
JOIN genres g        ON g.genre_id = mg.genre_id
LEFT JOIN review_stats rs    ON rs.movie_id = m.movie_id
LEFT JOIN watchlist_stats ws ON ws.movie_id = m.movie_id
GROUP BY m.movie_id, m.title, m.release_year,
         rs.average_rating, rs.review_count, ws.watchlist_count
ORDER BY COALESCE(rs.average_rating, 0) DESC,
         COALESCE(rs.review_count, 0) DESC,
         COALESCE(ws.watchlist_count, 0) DESC
LIMIT 20;

-- ---------------------------------------------------------------------
-- 2. Top three sufficiently reviewed movies in every genre
-- ---------------------------------------------------------------------
WITH review_stats AS (
    SELECT movie_id, AVG(rating) AS average_rating, COUNT(*) AS review_count
    FROM reviews
    GROUP BY movie_id
),
ranked AS (
    SELECT g.genre_name, m.movie_id, m.title,
           rs.average_rating, rs.review_count,
           ROW_NUMBER() OVER (
               PARTITION BY g.genre_id
               ORDER BY rs.average_rating DESC, rs.review_count DESC, m.title
           ) AS genre_rank
    FROM genres g
    JOIN movie_genres mg ON mg.genre_id = g.genre_id
    JOIN movies m        ON m.movie_id = mg.movie_id
    JOIN review_stats rs ON rs.movie_id = m.movie_id
    WHERE rs.review_count >= 2
)
SELECT genre_name, genre_rank, movie_id, title,
       ROUND(average_rating, 2) AS average_rating, review_count
FROM ranked
WHERE genre_rank <= 3
ORDER BY genre_name, genre_rank;

-- ---------------------------------------------------------------------
-- 3. Genre health: catalogue size, engagement and weighted rating
-- ---------------------------------------------------------------------
WITH movie_activity AS (
    SELECT m.movie_id,
           COUNT(DISTINCT r.review_id) AS review_count,
           AVG(r.rating) AS average_rating,
           COUNT(DISTINCT w.watchlist_id) AS watchlist_count
    FROM movies m
    LEFT JOIN reviews r    ON r.movie_id = m.movie_id
    LEFT JOIN watchlists w ON w.movie_id = m.movie_id
    GROUP BY m.movie_id
)
SELECT g.genre_id, g.genre_name,
       COUNT(*) AS movie_count,
       SUM(ma.review_count) AS review_count,
       ROUND(
           SUM(ma.average_rating * ma.review_count)
           / NULLIF(SUM(ma.review_count), 0), 2
       ) AS average_rating,
       SUM(ma.watchlist_count) AS watchlist_count
FROM genres g
JOIN movie_genres mg  ON mg.genre_id = g.genre_id
JOIN movie_activity ma ON ma.movie_id = mg.movie_id
GROUP BY g.genre_id, g.genre_name
ORDER BY watchlist_count DESC, review_count DESC, g.genre_name;

-- ---------------------------------------------------------------------
-- 4. Personalised recommendations from a user's positively rated or
--    watchlisted genres; already reviewed/watchlisted movies are excluded.
-- ---------------------------------------------------------------------
SET @recommend_user_id = 'U001';

WITH preferred_genres AS (
    SELECT DISTINCT mg.genre_id
    FROM reviews r
    JOIN movie_genres mg ON mg.movie_id = r.movie_id
    WHERE r.user_id = @recommend_user_id
      AND r.rating >= 7.0
    UNION
    SELECT DISTINCT mg.genre_id
    FROM watchlists w
    JOIN movie_genres mg ON mg.movie_id = w.movie_id
    WHERE w.user_id = @recommend_user_id
),
review_stats AS (
    SELECT movie_id, AVG(rating) AS average_rating, COUNT(*) AS review_count
    FROM reviews
    GROUP BY movie_id
)
SELECT m.movie_id, m.title, m.release_year,
       COUNT(DISTINCT pg.genre_id) AS matching_genres,
       ROUND(rs.average_rating, 2) AS average_rating,
       COALESCE(rs.review_count, 0) AS review_count
FROM movies m
JOIN movie_genres mg   ON mg.movie_id = m.movie_id
JOIN preferred_genres pg ON pg.genre_id = mg.genre_id
LEFT JOIN review_stats rs ON rs.movie_id = m.movie_id
WHERE NOT EXISTS (
          SELECT 1 FROM reviews r
          WHERE r.user_id = @recommend_user_id
            AND r.movie_id = m.movie_id
      )
  AND NOT EXISTS (
          SELECT 1 FROM watchlists w
          WHERE w.user_id = @recommend_user_id
            AND w.movie_id = m.movie_id
      )
GROUP BY m.movie_id, m.title, m.release_year,
         rs.average_rating, rs.review_count
ORDER BY matching_genres DESC,
         COALESCE(rs.average_rating, 0) DESC,
         COALESCE(rs.review_count, 0) DESC
LIMIT 20;

-- ---------------------------------------------------------------------
-- 5. User engagement leaderboard without review/watchlist cross-products
-- ---------------------------------------------------------------------
WITH review_activity AS (
    SELECT user_id, COUNT(*) AS review_count,
           AVG(rating) AS average_rating, MAX(updated_at) AS last_review_at
    FROM reviews
    GROUP BY user_id
),
watchlist_activity AS (
    SELECT user_id, COUNT(*) AS watchlist_count, MAX(added_at) AS last_saved_at
    FROM watchlists
    GROUP BY user_id
)
SELECT u.user_id, u.username,
       COALESCE(ra.review_count, 0) AS review_count,
       ROUND(ra.average_rating, 2) AS average_rating_given,
       COALESCE(wa.watchlist_count, 0) AS watchlist_count,
       ra.last_review_at, wa.last_saved_at,
       COALESCE(ra.review_count, 0) + COALESCE(wa.watchlist_count, 0)
           AS total_actions
FROM users u
LEFT JOIN review_activity ra    ON ra.user_id = u.user_id
LEFT JOIN watchlist_activity wa ON wa.user_id = u.user_id
ORDER BY total_actions DESC, u.username;

-- ---------------------------------------------------------------------
-- 6. Directors with at least three reviewed films
-- ---------------------------------------------------------------------
WITH movie_reviews AS (
    SELECT m.movie_id, m.director,
           AVG(r.rating) AS average_rating, COUNT(r.review_id) AS review_count
    FROM movies m
    LEFT JOIN reviews r ON r.movie_id = m.movie_id
    WHERE m.director IS NOT NULL
      AND m.director <> ''
    GROUP BY m.movie_id, m.director
)
SELECT director,
       COUNT(*) AS reviewed_movie_count,
       SUM(review_count) AS review_count,
       ROUND(
           SUM(average_rating * review_count) / NULLIF(SUM(review_count), 0), 2
       ) AS average_rating
FROM movie_reviews
WHERE review_count > 0
GROUP BY director
HAVING COUNT(*) >= 3
ORDER BY average_rating DESC, review_count DESC, director;

-- ---------------------------------------------------------------------
-- 7. Genre trends by release decade
-- ---------------------------------------------------------------------
WITH movie_reviews AS (
    SELECT movie_id, AVG(rating) AS average_rating, COUNT(*) AS review_count
    FROM reviews
    GROUP BY movie_id
)
SELECT (m.release_year DIV 10) * 10 AS release_decade,
       g.genre_name,
       COUNT(DISTINCT m.movie_id) AS movie_count,
       SUM(COALESCE(mr.review_count, 0)) AS review_count,
       ROUND(
           SUM(mr.average_rating * mr.review_count)
           / NULLIF(SUM(mr.review_count), 0), 2
       ) AS average_rating
FROM movies m
JOIN movie_genres mg ON mg.movie_id = m.movie_id
JOIN genres g        ON g.genre_id = mg.genre_id
LEFT JOIN movie_reviews mr ON mr.movie_id = m.movie_id
GROUP BY release_decade, g.genre_id, g.genre_name
HAVING movie_count >= 3
ORDER BY release_decade DESC, movie_count DESC, g.genre_name;

-- ---------------------------------------------------------------------
-- 8. Latest review feed with user and movie context
-- ---------------------------------------------------------------------
SELECT r.review_id, r.rating, r.review_text, r.created_at, r.updated_at,
       u.user_id, u.username,
       m.movie_id, m.title, m.release_year
FROM reviews r
JOIN users u  ON u.user_id = r.user_id
JOIN movies m ON m.movie_id = r.movie_id
ORDER BY r.created_at DESC
LIMIT 25;
