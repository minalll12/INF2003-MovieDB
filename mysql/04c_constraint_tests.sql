-- =====================================================================
-- 04c_constraint_tests.sql
-- Purpose : Show that PK / FK / UNIQUE / CHECK rules REJECT bad data.
--           Every statement below is EXPECTED TO FAIL - screenshot the errors
--           for the report. Run with:  mysql -u root -p -f < ...  (or in
--           Workbench, run one statement at a time). Nothing is changed.
-- =====================================================================
USE movie_platform;

-- 1) Duplicate primary key
INSERT INTO genres (genre_id, genre_name) VALUES ('G001', 'Duplicate PK');

-- 2) UNIQUE: second review by the same user for the same movie
INSERT INTO reviews (review_id, user_id, movie_id, rating, review_text)
SELECT 'R9001', user_id, movie_id, 5.0, 'duplicate review' FROM reviews LIMIT 1;

-- 3) CHECK: rating outside 1-10
INSERT INTO reviews (review_id, user_id, movie_id, rating, review_text)
VALUES ('R9002', 'U001', 'M0001', 11.5, 'invalid rating');

-- 4) FK: review for a movie that does not exist
INSERT INTO reviews (review_id, user_id, movie_id, rating, review_text)
VALUES ('R9003', 'U001', 'M9999', 7.0, 'orphan movie');

-- 5) UNIQUE: same movie added twice to one user's watchlist
INSERT INTO watchlists (watchlist_id, user_id, movie_id)
SELECT 'W9001', user_id, movie_id FROM watchlists LIMIT 1;

-- 6) FK RESTRICT: cannot delete a genre that movies still use
DELETE FROM genres WHERE genre_id = 'G007';

-- 7) UNIQUE: duplicate email
INSERT INTO users (user_id, username, email, password_hash)
SELECT 'U999', 'newname', email, 'x' FROM users LIMIT 1;
