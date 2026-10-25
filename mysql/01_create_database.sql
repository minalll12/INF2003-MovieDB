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
