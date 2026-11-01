-- =====================================================================
-- 05_crud_queries.sql
-- Purpose : Runnable CRUD examples for users, reviews and watchlists,
--           plus a parameterised-style movie discovery query.
-- Safety  : Demo writes run inside one transaction and are rolled back.
--           Applications must bind parameters rather than concatenate input.
-- =====================================================================

USE movie_platform;

-- Workbench demo values. The IDs fit the existing VARCHAR(10) columns.
SET @demo_user_id      = 'UDEMO001';
SET @demo_review_id    = 'RDEMO001';
SET @demo_watchlist_id = 'WDEMO001';
SET @demo_movie_id     = 'M0001';

START TRANSACTION;

-- ---------------------------------------------------------------------
-- A. USERS: create, read and update
-- Store only a password hash produced by the application, never a password.
-- ---------------------------------------------------------------------
INSERT INTO users (user_id, username, email, password_hash)
VALUES (@demo_user_id, 'demo_user', 'demo.user@example.invalid',
        'demo_hash_not_for_authentication');

SELECT user_id, username, email, created_at
FROM users
WHERE user_id = @demo_user_id;

UPDATE users
SET username = 'demo_user_updated',
    email = 'demo.user.updated@example.invalid'
WHERE user_id = @demo_user_id;

-- ---------------------------------------------------------------------
-- B. REVIEWS: create, read, update and delete
-- The UNIQUE (user_id, movie_id) rule permits one review per user/movie.
-- ---------------------------------------------------------------------
INSERT INTO reviews (review_id, user_id, movie_id, rating, review_text)
VALUES (@demo_review_id, @demo_user_id, @demo_movie_id, 8.5,
        'A concise demonstration review.');

SELECT r.review_id, r.rating, r.review_text, r.created_at, r.updated_at,
       u.username, m.title
FROM reviews r
JOIN users u  ON u.user_id = r.user_id
JOIN movies m ON m.movie_id = r.movie_id
WHERE r.review_id = @demo_review_id;

UPDATE reviews
SET rating = 9.0,
    review_text = 'Updated after a second viewing.'
WHERE review_id = @demo_review_id
  AND user_id = @demo_user_id; -- ownership check used by the application

DELETE FROM reviews
WHERE review_id = @demo_review_id
  AND user_id = @demo_user_id;

-- ---------------------------------------------------------------------
-- C. WATCHLISTS: create, read and delete
-- ---------------------------------------------------------------------
INSERT INTO watchlists (watchlist_id, user_id, movie_id)
VALUES (@demo_watchlist_id, @demo_user_id, @demo_movie_id);

SELECT w.watchlist_id, w.added_at,
       m.movie_id, m.title, m.release_year, m.poster_url
FROM watchlists w
JOIN movies m ON m.movie_id = w.movie_id
WHERE w.user_id = @demo_user_id
ORDER BY w.added_at DESC;

DELETE FROM watchlists
WHERE watchlist_id = @demo_watchlist_id
  AND user_id = @demo_user_id; -- ownership check used by the application

-- ---------------------------------------------------------------------
-- D. MOVIE SEARCH: literal title, ALL selected genres, year/rating ranges
-- Current sort modes match app/backends.py. Callable search_movies() binds
-- inputs and settles one-decimal rounding ties with pandas/NumPy.
-- The @variables below are only convenient Workbench demo inputs.
-- ---------------------------------------------------------------------
SET @title_text    = 'godfather';
SET @selected_genres = JSON_ARRAY('Crime', 'Drama'); -- JSON_ARRAY() disables
SET @year_from     = 1970;
SET @year_to       = 2000;
SET @rating_from   = 0.0; -- full 0-10 range includes films without reviews
SET @rating_to     = 10.0;
SET @sort_mode     = 'Highest rated';

WITH selected_genres AS (
    SELECT DISTINCT genre_name
    FROM JSON_TABLE(@selected_genres, '$[*]'
        COLUMNS (genre_name VARCHAR(50) PATH '$')) selected
), review_stats AS (
    SELECT movie_id, AVG(rating) AS avg_rating, COUNT(*) AS review_count
    FROM reviews GROUP BY movie_id
)
SELECT m.movie_id, m.title, m.release_year, m.duration, m.poster_url,
       GROUP_CONCAT(g.genre_name ORDER BY g.genre_name SEPARATOR ', ') AS genres,
       ROUND(CAST(rs.avg_rating AS DOUBLE), 1) AS avg_rating,
       COALESCE(rs.review_count, 0) AS review_count
FROM movies m
LEFT JOIN movie_genres mg ON mg.movie_id = m.movie_id
LEFT JOIN genres g        ON g.genre_id = mg.genre_id
LEFT JOIN review_stats rs ON rs.movie_id = m.movie_id
WHERE (@title_text IS NULL
       OR LOCATE(@title_text COLLATE utf8mb4_0900_as_ci,
                 m.title COLLATE utf8mb4_0900_as_ci) > 0)
  AND (@year_from IS NULL OR m.release_year >= @year_from)
  AND (@year_to IS NULL OR m.release_year <= @year_to)
  AND ((@rating_from = 0 AND @rating_to = 10)
       OR ((@rating_from IS NULL OR ROUND(CAST(rs.avg_rating AS DOUBLE), 1) >= @rating_from)
           AND (@rating_to IS NULL OR ROUND(CAST(rs.avg_rating AS DOUBLE), 1) <= @rating_to)))
  AND NOT EXISTS (
      SELECT 1 FROM selected_genres selected
      WHERE NOT EXISTS (
          SELECT 1 FROM movie_genres mg_filter
          JOIN genres g_filter ON g_filter.genre_id = mg_filter.genre_id
          WHERE mg_filter.movie_id = m.movie_id
            AND g_filter.genre_name = selected.genre_name
      )
  )
GROUP BY m.movie_id, m.title, m.release_year, m.duration, m.poster_url,
         rs.avg_rating, rs.review_count
ORDER BY CASE WHEN @sort_mode = 'Highest rated' THEN avg_rating END DESC,
         CASE WHEN @sort_mode IN ('Highest rated', 'Most reviewed') THEN review_count END DESC,
         CASE WHEN @sort_mode = 'Most reviewed' THEN avg_rating END DESC,
         CASE WHEN @sort_mode = 'Highest rated' THEN m.imdb_votes END DESC,
         CASE WHEN @sort_mode = 'Newest' THEN m.release_year END DESC,
         CASE WHEN @sort_mode = 'Oldest' THEN m.release_year END ASC,
         CASE WHEN @sort_mode IN ('Newest', 'Oldest', 'Title A–Z') THEN m.title END COLLATE utf8mb4_bin ASC,
         m.movie_id;

-- A. USERS: delete (after child rows have been removed above)
DELETE FROM users
WHERE user_id = @demo_user_id;

-- Keep the file safe and rerunnable: none of the demo writes are persisted.
ROLLBACK;
