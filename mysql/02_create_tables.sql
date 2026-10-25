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
