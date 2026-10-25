-- =====================================================================
-- 04b_validate_import.sql
-- Purpose : Prove the import is correct (screenshot these for the report).
-- =====================================================================
USE movie_platform;

-- 1) Row counts vs the CSV files (expected in the last column)
SELECT 'genres'       AS table_name, COUNT(*) AS actual_rows,   21 AS expected_rows FROM genres
UNION ALL SELECT 'movies',       COUNT(*), 1000 FROM movies
UNION ALL SELECT 'movie_genres', COUNT(*), 2541 FROM movie_genres
UNION ALL SELECT 'users',        COUNT(*),   30 FROM users
UNION ALL SELECT 'reviews',      COUNT(*),  750 FROM reviews
UNION ALL SELECT 'watchlists',   COUNT(*),  300 FROM watchlists;

-- 2) Orphan checks (every result below must be 0)
SELECT 'movie_genres -> movies' AS check_name, COUNT(*) AS problems
FROM movie_genres mg LEFT JOIN movies m ON m.movie_id = mg.movie_id WHERE m.movie_id IS NULL
UNION ALL
SELECT 'movie_genres -> genres', COUNT(*)
FROM movie_genres mg LEFT JOIN genres g ON g.genre_id = mg.genre_id WHERE g.genre_id IS NULL
UNION ALL
SELECT 'reviews -> users', COUNT(*)
FROM reviews r LEFT JOIN users u ON u.user_id = r.user_id WHERE u.user_id IS NULL
UNION ALL
SELECT 'reviews -> movies', COUNT(*)
FROM reviews r LEFT JOIN movies m ON m.movie_id = r.movie_id WHERE m.movie_id IS NULL
UNION ALL
SELECT 'watchlists -> users', COUNT(*)
FROM watchlists w LEFT JOIN users u ON u.user_id = w.user_id WHERE u.user_id IS NULL
UNION ALL
SELECT 'watchlists -> movies', COUNT(*)
FROM watchlists w LEFT JOIN movies m ON m.movie_id = w.movie_id WHERE m.movie_id IS NULL
UNION ALL
-- 3) Business-rule checks
SELECT 'movies with no genre', COUNT(*)
FROM movies m LEFT JOIN movie_genres mg ON mg.movie_id = m.movie_id WHERE mg.movie_id IS NULL
UNION ALL
SELECT 'ratings outside 1-10', COUNT(*) FROM reviews WHERE rating NOT BETWEEN 1 AND 10
UNION ALL
SELECT 'updated_at before created_at', COUNT(*) FROM reviews WHERE updated_at < created_at
UNION ALL
SELECT 'hidden CR in genre_name', COUNT(*) FROM genres WHERE genre_name LIKE CONCAT('%', CHAR(13), '%');

-- 4) Spot check: one movie with its genres (shows the M:N join works)
SELECT m.movie_id, m.title, m.release_year,
       GROUP_CONCAT(g.genre_name ORDER BY g.genre_name SEPARATOR ', ') AS genres
FROM movies m
JOIN movie_genres mg ON mg.movie_id = m.movie_id
JOIN genres g        ON g.genre_id  = mg.genre_id
WHERE m.movie_id IN ('M0001', 'M0002')
GROUP BY m.movie_id, m.title, m.release_year;

-- 5) Spot check: special characters survived (utf8mb4)
SELECT movie_id, title FROM movies WHERE title REGEXP '[^ -~]' LIMIT 5;
