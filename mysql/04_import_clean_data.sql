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
LOAD DATA LOCAL INFILE 'data/cleaned/genres.csv'
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
LOAD DATA LOCAL INFILE 'data/cleaned/movies.csv'
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
LOAD DATA LOCAL INFILE 'data/cleaned/movie_genres.csv'
INTO TABLE movie_genres
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(movie_id, @genre_id)
SET genre_id = REPLACE(@genre_id, '\r', '');
SHOW WARNINGS;

-- 4) users (no dependencies)
LOAD DATA LOCAL INFILE 'data/cleaned/users.csv'
INTO TABLE users
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(user_id, username, email, password_hash, @created_at)
SET created_at = REPLACE(@created_at, '\r', '');
SHOW WARNINGS;

-- 5) reviews (needs users + movies)
LOAD DATA LOCAL INFILE 'data/cleaned/reviews.csv'
INTO TABLE reviews
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(review_id, user_id, movie_id, rating, review_text, created_at, @updated_at)
SET updated_at = REPLACE(@updated_at, '\r', '');
SHOW WARNINGS;

-- 6) watchlists (needs users + movies)
LOAD DATA LOCAL INFILE 'data/cleaned/watchlists.csv'
INTO TABLE watchlists
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(watchlist_id, user_id, movie_id, @added_at)
SET added_at = REPLACE(@added_at, '\r', '');
SHOW WARNINGS;
