-- =====================================================================
-- 00_workbench_server_import.sql  (MySQL Workbench - NO local_infile needed)
-- Rebuilds database + tables, imports all CSVs, then validates.
--
-- BEFORE RUNNING (once):
--   1) In a query tab run:   SHOW VARIABLES LIKE 'secure_file_priv';
--      -> note the folder shown (e.g. C:\ProgramData\MySQL\MySQL Server 26.7\Uploads\)
--   2) Copy the 6 CSV files from data/cleaned/ INTO that folder.
--   3) Ctrl+H: replace   @@DATA_PATH@@   with that folder, FORWARD slashes,
--      no trailing slash, e.g.
--         C:/ProgramData/MySQL/MySQL Server 26.7/Uploads
--   4) Click Run (runs the WHOLE script).
-- If 'secure_file_priv' is NULL, import is disabled: use the terminal method.
-- =====================================================================

-- =====================================================================
-- 01_create_database.sql
-- Purpose : Create the MySQL database for INF2003 Group 28
--           (Movie Review and Discovery System).
-- Run from: project root  ->  mysql -u root -p --local-infile=1
--           then:  SOURCE mysql/01_create_database.sql;
-- =====================================================================

DROP DATABASE IF EXISTS movie_platform;   -- allows a clean rebuild from scratch

CREATE DATABASE movie_platform
    CHARACTER SET utf8mb4          -- full Unicode (accents in names/titles)
    COLLATE utf8mb4_0900_ai_ci;

USE movie_platform;


-- =====================================================================
-- 02_create_tables.sql
-- Purpose : Create all tables, PK / FK / UNIQUE / CHECK constraints.
-- Tables  : genres, movies, movie_genres, users, reviews, watchlists
-- Note    : IDs are the string IDs from the cleaned CSVs (M0001, G001,
--           U001, R0001, W0001) so the SAME keys can be used in MongoDB.
-- =====================================================================

USE movie_platform;

-- Drop in reverse dependency order so the script can be re-run safely
DROP TABLE IF EXISTS watchlists;
DROP TABLE IF EXISTS reviews;
DROP TABLE IF EXISTS movie_genres;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS genres;
DROP TABLE IF EXISTS movies;

-- ---------------------------------------------------------------------
-- genres : one row per genre (lookup table)
-- ---------------------------------------------------------------------
CREATE TABLE genres (
    genre_id    VARCHAR(10)  NOT NULL,
    genre_name  VARCHAR(50)  NOT NULL,
    CONSTRAINT pk_genres      PRIMARY KEY (genre_id),
    CONSTRAINT uq_genre_name  UNIQUE (genre_name)
) ENGINE = InnoDB;

-- ---------------------------------------------------------------------
-- movies : core catalogue.
--   NO genre column here -> genres live in genres + movie_genres (3NF).
--   director / `cast` kept as text: the cleaned data has no people table.
-- ---------------------------------------------------------------------
CREATE TABLE movies (
    movie_id      VARCHAR(10)    NOT NULL,
    title         VARCHAR(255)   NOT NULL,
    release_year  SMALLINT UNSIGNED NOT NULL,
    certificate   VARCHAR(20)    NULL,
    duration      SMALLINT UNSIGNED NOT NULL COMMENT 'runtime in minutes',
    description   TEXT           NULL,
    director      VARCHAR(255)   NULL,
    `cast`        TEXT           NULL COMMENT 'comma-separated actor names',
    imdb_votes    INT UNSIGNED   NOT NULL DEFAULT 0,
    poster_url    VARCHAR(500)   NULL,
    CONSTRAINT pk_movies          PRIMARY KEY (movie_id),
    CONSTRAINT ck_movie_year      CHECK (release_year BETWEEN 1888 AND 2100),
    CONSTRAINT ck_movie_duration  CHECK (duration > 0)
) ENGINE = InnoDB;

-- ---------------------------------------------------------------------
-- movie_genres : associative table (movies M:N genres)
-- ---------------------------------------------------------------------
CREATE TABLE movie_genres (
    movie_id  VARCHAR(10) NOT NULL,
    genre_id  VARCHAR(10) NOT NULL,
    CONSTRAINT pk_movie_genres PRIMARY KEY (movie_id, genre_id),  -- no duplicate pairs
    CONSTRAINT fk_mg_movie FOREIGN KEY (movie_id) REFERENCES movies (movie_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_mg_genre FOREIGN KEY (genre_id) REFERENCES genres (genre_id)
        ON DELETE RESTRICT ON UPDATE CASCADE      -- cannot delete a genre still in use
) ENGINE = InnoDB;

-- ---------------------------------------------------------------------
-- users
-- ---------------------------------------------------------------------
CREATE TABLE users (
    user_id        VARCHAR(10)  NOT NULL,
    username       VARCHAR(50)  NOT NULL,
    email          VARCHAR(255) NOT NULL,
    password_hash  VARCHAR(255) NOT NULL COMMENT 'PBKDF2 hash, never plain text',
    created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_users     PRIMARY KEY (user_id),
    CONSTRAINT uq_username  UNIQUE (username),
    CONSTRAINT uq_email     UNIQUE (email)
) ENGINE = InnoDB;

-- ---------------------------------------------------------------------
-- reviews : one review (rating + text) per user per movie
--   Rating scale in the cleaned data is 1.0 - 10.0 (IMDb style).
-- ---------------------------------------------------------------------
CREATE TABLE reviews (
    review_id    VARCHAR(10)   NOT NULL,
    user_id      VARCHAR(10)   NOT NULL,
    movie_id     VARCHAR(10)   NOT NULL,
    rating       DECIMAL(3,1)  NOT NULL,
    review_text  VARCHAR(1000) NULL,
    created_at   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP
                               ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT pk_reviews         PRIMARY KEY (review_id),
    CONSTRAINT uq_review_user_movie UNIQUE (user_id, movie_id),   -- 1 review per user/movie
    CONSTRAINT ck_review_rating   CHECK (rating BETWEEN 1.0 AND 10.0),
    CONSTRAINT ck_review_dates    CHECK (updated_at >= created_at),
    CONSTRAINT fk_review_user  FOREIGN KEY (user_id)  REFERENCES users (user_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_review_movie FOREIGN KEY (movie_id) REFERENCES movies (movie_id)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE = InnoDB;

-- ---------------------------------------------------------------------
-- watchlists : a user saves a movie at most once
-- ---------------------------------------------------------------------
CREATE TABLE watchlists (
    watchlist_id  VARCHAR(10) NOT NULL,
    user_id       VARCHAR(10) NOT NULL,
    movie_id      VARCHAR(10) NOT NULL,
    added_at      DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_watchlists PRIMARY KEY (watchlist_id),
    CONSTRAINT uq_watchlist_user_movie UNIQUE (user_id, movie_id),
    CONSTRAINT fk_wl_user  FOREIGN KEY (user_id)  REFERENCES users (user_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_wl_movie FOREIGN KEY (movie_id) REFERENCES movies (movie_id)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE = InnoDB;

SHOW TABLES;


-- =====================================================================
-- 04_import_clean_data.sql
-- Purpose : Load the cleaned CSVs into MySQL (parents first, then children).
-- Needs   : CSVs in  data/cleaned/   (relative to where you start `mysql`)
--           Start the client from the PROJECT ROOT with:
--               mysql -u root -p --local-infile=1
--           and server setting local_infile = ON (see README step 3).
--
-- WHY the REPLACE(@x, '\r', '') on the LAST column of every file:
--   genres/movies/movie_genres CSVs use Windows line endings (CRLF), the others
--   use LF. Without this, a hidden \r sticks to the last value, FK checks fail
--   and LOAD DATA LOCAL silently skips rows (it downgrades errors to warnings).
--   This version works for both LF and CRLF files.
-- =====================================================================

USE movie_platform;

SET FOREIGN_KEY_CHECKS = 1;     -- keep FK checking ON: bad data should fail loudly
SET sql_mode = 'STRICT_TRANS_TABLES,NO_ENGINE_SUBSTITUTION';

-- 1) genres (no dependencies)
LOAD DATA INFILE '@@DATA_PATH@@/genres.csv'
INTO TABLE genres
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(genre_id, @genre_name)
SET genre_name = REPLACE(@genre_name, '\r', '');
SHOW WARNINGS;

-- 2) movies (no dependencies)
--    CSV column order: movie_id, poster_url, title, release_year, certificate,
--                      duration, genre, description, director, cast, imdb_votes
--    The CSV `genre` text is read into a throw-away variable (@genre_text):
--    genres are stored via movie_genres instead.
LOAD DATA INFILE '@@DATA_PATH@@/movies.csv'
INTO TABLE movies
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(movie_id, poster_url, title, release_year, certificate, duration,
 @genre_text, description, director, `cast`, @imdb_votes)
SET imdb_votes = CAST(REPLACE(@imdb_votes, '\r', '') AS UNSIGNED);
SHOW WARNINGS;

-- 3) movie_genres (needs movies + genres)
LOAD DATA INFILE '@@DATA_PATH@@/movie_genres.csv'
INTO TABLE movie_genres
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(movie_id, @genre_id)
SET genre_id = REPLACE(@genre_id, '\r', '');
SHOW WARNINGS;

-- 4) users (no dependencies)
LOAD DATA INFILE '@@DATA_PATH@@/users.csv'
INTO TABLE users
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(user_id, username, email, password_hash, @created_at)
SET created_at = REPLACE(@created_at, '\r', '');
SHOW WARNINGS;

-- 5) reviews (needs users + movies)
LOAD DATA INFILE '@@DATA_PATH@@/reviews.csv'
INTO TABLE reviews
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(review_id, user_id, movie_id, rating, review_text, created_at, @updated_at)
SET updated_at = REPLACE(@updated_at, '\r', '');
SHOW WARNINGS;

-- 6) watchlists (needs users + movies)
LOAD DATA INFILE '@@DATA_PATH@@/watchlists.csv'
INTO TABLE watchlists
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(watchlist_id, user_id, movie_id, @added_at)
SET added_at = REPLACE(@added_at, '\r', '');
SHOW WARNINGS;



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
