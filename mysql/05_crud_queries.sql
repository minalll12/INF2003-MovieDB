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
-- D. MOVIE SEARCH: optional title, genre, year and minimum-rating filters
-- Set an optional filter to NULL to disable it.
-- ---------------------------------------------------------------------
SET @title_text    = 'godfather';
SET @genre_filter = 'Crime';
SET @year_from     = 1970;
SET @year_to       = 2000;
SET @minimum_rating = NULL;

SELECT m.movie_id, m.title, m.release_year, m.duration, m.poster_url,
       GROUP_CONCAT(g.genre_name ORDER BY g.genre_name SEPARATOR ', ') AS genres,
       ROUND(rs.average_rating, 2) AS average_rating,
       COALESCE(rs.review_count, 0) AS review_count
FROM movies m
JOIN movie_genres mg ON mg.movie_id = m.movie_id
JOIN genres g        ON g.genre_id = mg.genre_id
LEFT JOIN (
    SELECT movie_id, AVG(rating) AS average_rating, COUNT(*) AS review_count
    FROM reviews
    GROUP BY movie_id
) rs ON rs.movie_id = m.movie_id
WHERE (@title_text IS NULL
       OR m.title LIKE CONCAT('%', @title_text, '%'))
  AND (@year_from IS NULL OR m.release_year >= @year_from)
  AND (@year_to IS NULL OR m.release_year <= @year_to)
  AND (@minimum_rating IS NULL
       OR rs.average_rating >= @minimum_rating)
  AND (@genre_filter IS NULL OR EXISTS (
      SELECT 1
      FROM movie_genres mg_filter
      JOIN genres g_filter ON g_filter.genre_id = mg_filter.genre_id
      WHERE mg_filter.movie_id = m.movie_id
        AND g_filter.genre_name = @genre_filter
  ))
GROUP BY m.movie_id, m.title, m.release_year, m.duration, m.poster_url,
         rs.average_rating, rs.review_count
ORDER BY COALESCE(rs.average_rating, 0) DESC,
         COALESCE(rs.review_count, 0) DESC,
         m.title;

-- A. USERS: delete (after child rows have been removed above)
DELETE FROM users
WHERE user_id = @demo_user_id;

-- Keep the file safe and rerunnable: none of the demo writes are persisted.
ROLLBACK;
