-- =====================================================================
-- 08_indexes.sql
-- Purpose : Add only indexes tied to application query patterns.
-- Safety  : The helper creates each named index only when it is absent.
-- Note    : PK, UNIQUE and FK indexes from 02_create_tables.sql are not
--           duplicated here.
-- =====================================================================

USE movie_platform;

DROP PROCEDURE IF EXISTS add_index_if_missing;

DELIMITER //
CREATE PROCEDURE add_index_if_missing(
    IN p_table_name VARCHAR(64),
    IN p_index_name VARCHAR(64),
    IN p_index_columns VARCHAR(255)
)
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.statistics
        WHERE table_schema = DATABASE()
          AND table_name = p_table_name
          AND index_name = p_index_name
    ) THEN
        SET @index_sql = CONCAT(
            'CREATE INDEX `', p_index_name, '` ON `', p_table_name,
            '` (', p_index_columns, ')'
        );
        PREPARE index_statement FROM @index_sql;
        EXECUTE index_statement;
        DEALLOCATE PREPARE index_statement;
    END IF;
END//
DELIMITER ;

-- Supports release-year filtering/order. A leading-wildcard literal title
-- search cannot use a title B-tree for a seek.
CALL add_index_if_missing(
    'movies', 'idx_movies_release_year_title', 'release_year, title'
);

-- Covers per-movie COUNT/AVG rating calculations used across discovery views.
CALL add_index_if_missing(
    'reviews', 'idx_reviews_movie_rating', 'movie_id, rating'
);

-- Supports the latest-review feed used by the Streamlit discovery page.
CALL add_index_if_missing(
    'reviews', 'idx_reviews_created_at', 'created_at'
);

-- Equality on the parent ID, then newest-updated review ordering.
CALL add_index_if_missing(
    'reviews', 'idx_reviews_movie_updated', 'movie_id, updated_at'
);
CALL add_index_if_missing(
    'reviews', 'idx_reviews_user_updated', 'user_id, updated_at'
);

-- Supports a user's watchlist ordered by most recently added.
CALL add_index_if_missing(
    'watchlists', 'idx_watchlists_user_added', 'user_id, added_at'
);

DROP PROCEDURE add_index_if_missing;

-- ---------------------------------------------------------------------
-- EXPLAIN examples
-- Look for the named key in the `key` column. Optimiser choices may differ
-- on this small dataset; indexes become more valuable as row counts grow.
-- ---------------------------------------------------------------------
EXPLAIN
SELECT movie_id, title, release_year
FROM movies
WHERE release_year BETWEEN 1990 AND 1999
  AND title LIKE 'The%'
ORDER BY release_year, title;

EXPLAIN
SELECT movie_id, COUNT(*) AS review_count, AVG(rating) AS average_rating
FROM reviews
GROUP BY movie_id;

EXPLAIN
SELECT review_id, user_id, movie_id, rating, created_at
FROM reviews
ORDER BY created_at DESC
LIMIT 25;

EXPLAIN
SELECT watchlist_id, movie_id, added_at
FROM watchlists
WHERE user_id = 'U001'
ORDER BY added_at DESC;

EXPLAIN
SELECT review_id, user_id, rating, review_text, updated_at
FROM reviews WHERE movie_id = 'M0001'
ORDER BY updated_at DESC, review_id DESC;

EXPLAIN
SELECT review_id, movie_id, rating, updated_at
FROM reviews WHERE user_id = 'U001'
ORDER BY updated_at DESC, review_id DESC;

-- Core comparison op 1: the genre FK index on movie_genres already exists.
EXPLAIN
SELECT m.movie_id, m.title, m.release_year
FROM genres g JOIN movie_genres mg ON mg.genre_id = g.genre_id
JOIN movies m ON m.movie_id = mg.movie_id
WHERE g.genre_name = 'Drama';

-- Multi-genre intersection, grouped rating statistics and literal title filter.
EXPLAIN
SELECT m.movie_id, m.title, rs.avg_rating, COALESCE(rs.review_count, 0) AS review_count
FROM movies m
LEFT JOIN (SELECT movie_id, AVG(rating) AS avg_rating, COUNT(*) AS review_count
           FROM reviews GROUP BY movie_id) rs ON rs.movie_id = m.movie_id
WHERE m.release_year BETWEEN 1990 AND 2020
  AND LOCATE('the', m.title) > 0
  AND m.movie_id IN (
      SELECT mg.movie_id FROM movie_genres mg JOIN genres g ON g.genre_id = mg.genre_id
      WHERE g.genre_name IN ('Drama', 'Crime') GROUP BY mg.movie_id HAVING COUNT(*) = 2
  )
ORDER BY rs.avg_rating DESC, review_count DESC;
