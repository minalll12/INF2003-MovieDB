-- =====================================================================
-- 09_comparison_queries.sql
-- Purpose : Five labelled MySQL operations for equivalent MongoDB tests.
--           Operations 1-3 match the benchmark methods in app/backends.py.
-- Guidance: Use the same parameters, result fields and dataset for both
--           databases; run each operation repeatedly after a warm-up.
-- =====================================================================

USE movie_platform;

SET @comparison_genre = 'Drama';
SET @comparison_movie_id = 'M0001';
SET @comparison_user_id = 'U001';

-- ---------------------------------------------------------------------
-- OPERATION 1: Movies by genre
-- App method: RelationalBackend.movies_by_genre()
-- MongoDB equivalent: movies.find({ genres: "Drama" }) when genres are
--                     embedded in each movie document.
-- Measures: normalised join versus an embedded-array lookup.
-- ---------------------------------------------------------------------
SELECT m.movie_id, m.title, m.release_year
FROM genres g
JOIN movie_genres mg ON mg.genre_id = g.genre_id
JOIN movies m        ON m.movie_id = mg.movie_id
WHERE g.genre_name = @comparison_genre;

-- ---------------------------------------------------------------------
-- OPERATION 2: Average rating for one movie
-- App method: RelationalBackend.average_rating()
-- MongoDB equivalent: reviews.aggregate with $match then $group/$avg.
-- Measures: indexed filtering and a single-group aggregation.
-- ---------------------------------------------------------------------
SELECT ROUND(AVG(r.rating), 2) AS average_rating
FROM reviews r
WHERE r.movie_id = @comparison_movie_id;

-- ---------------------------------------------------------------------
-- OPERATION 3: User watchlist with movie titles and genres
-- App method: RelationalBackend.watchlist_with_genres()
-- MongoDB equivalent: $match watchlists by user_id, $lookup movies; genres
--                     are already embedded in the movie documents.
-- Measures: relationship lookup plus genre assembly.
-- ---------------------------------------------------------------------
SELECT m.movie_id, m.title,
       GROUP_CONCAT(g.genre_name
                    ORDER BY g.genre_name SEPARATOR ', ') AS genres
FROM watchlists w
JOIN movies m        ON m.movie_id = w.movie_id
JOIN movie_genres mg ON mg.movie_id = m.movie_id
JOIN genres g        ON g.genre_id = mg.genre_id
WHERE w.user_id = @comparison_user_id
GROUP BY m.movie_id, m.title;

-- ---------------------------------------------------------------------
-- OPERATION 4: Filtered movie discovery with review statistics
-- MongoDB equivalent: $match on year/genre, then $lookup and $group for
--                     review statistics (or use precomputed fields).
-- Measures: filtering a many-to-many relationship plus aggregation.
-- ---------------------------------------------------------------------
SET @comparison_year_from = 1990;
SET @comparison_year_to = 2020;

SELECT m.movie_id, m.title, m.release_year,
       COUNT(r.review_id) AS review_count,
       ROUND(AVG(r.rating), 2) AS average_rating
FROM genres g
JOIN movie_genres mg ON mg.genre_id = g.genre_id
JOIN movies m        ON m.movie_id = mg.movie_id
LEFT JOIN reviews r  ON r.movie_id = m.movie_id
WHERE g.genre_name = @comparison_genre
  AND m.release_year BETWEEN @comparison_year_from AND @comparison_year_to
GROUP BY m.movie_id, m.title, m.release_year
ORDER BY average_rating DESC, review_count DESC, m.title
LIMIT 25;

-- ---------------------------------------------------------------------
-- OPERATION 5: Top-rated movies in one genre (minimum two reviews)
-- MongoDB equivalent: $match genre, $lookup reviews, $unwind, $group,
--                     $match review_count and $sort.
-- Measures: filtered join plus grouped ranking.
-- ---------------------------------------------------------------------
SELECT m.movie_id, m.title,
       COUNT(r.review_id) AS review_count,
       ROUND(AVG(r.rating), 2) AS average_rating
FROM genres g
JOIN movie_genres mg ON mg.genre_id = g.genre_id
JOIN movies m        ON m.movie_id = mg.movie_id
JOIN reviews r       ON r.movie_id = m.movie_id
WHERE g.genre_name = @comparison_genre
GROUP BY m.movie_id, m.title
HAVING COUNT(r.review_id) >= 2
ORDER BY average_rating DESC, review_count DESC, m.title
LIMIT 10;
