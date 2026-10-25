# MySQL database

This folder contains the MySQL 8 implementation for the INF2003 Group 28 Movie Review and Discovery System. The schema uses the same string IDs as the MongoDB dataset so equivalent operations can be compared directly.

## Connection settings

Copy the repository-root `.env.example` to `.env` and replace the placeholders locally. `.env` is ignored by Git; never commit passwords or other credentials.

The example port is the MySQL default, `3306`. If your local server listens on `3307`, set `DB_PORT=3307` in `.env` and use port `3307` in Workbench or the CLI, for example:

```powershell
mysql -h localhost -P 3307 -u root -p --local-infile=1
```

Changing the client port does not require any SQL script changes.

## Streamlit integration status

The current `app/` implementation still uses CSV-backed stand-ins for both database engines. The first three operations in `09_comparison_queries.sql` match the relational benchmark methods in `app/backends.py`, but the app will not use `.env` or connect to MySQL until its backend is wired to a MySQL driver.

## Setup and execution order

Choose one import route. Both routes rebuild `movie_platform`, so do not run them against a database containing data you need to keep.

### Route A: MySQL Workbench server-side import

1. Connect to the intended MySQL 8 server in Workbench (port `3307` for the current local setup).
2. Run `SHOW VARIABLES LIKE 'secure_file_priv';`.
3. Copy all six files from `data/cleaned/` into the returned directory.
4. Open `00_workbench_server_import.sql` and replace every `@@DATA_PATH@@` with that directory using forward slashes and no trailing slash.
5. Run the whole script. It rebuilds the database, creates the tables, imports the CSVs and runs validation queries.
6. Continue with scripts `05` through `09` in numeric order. Script `04c` is optional and intentionally produces constraint errors.

If `secure_file_priv` is `NULL`, server-side import is disabled; use Route B.

### Route B: modular CLI import

From the repository root, connect with local infile enabled:

```powershell
mysql -h localhost -P 3307 -u root -p --local-infile=1
```

Then run:

```sql
SOURCE mysql/01_create_database.sql;
SOURCE mysql/02_create_tables.sql;
SOURCE mysql/04_import_clean_data.sql;
SOURCE mysql/04b_validate_import.sql;
SOURCE mysql/05_crud_queries.sql;
SOURCE mysql/06_advanced_queries.sql;
SOURCE mysql/07_views.sql;
SOURCE mysql/08_indexes.sql;
SOURCE mysql/09_comparison_queries.sql;
```

`SOURCE` paths in this sequence assume the client was started from the repository root. If `LOAD DATA LOCAL INFILE` is rejected, verify both the client option and the server value with `SHOW VARIABLES LIKE 'local_infile';`.

## Script reference

| Script | Purpose | Data changes |
|---|---|---|
| `00_workbench_server_import.sql` | All-in-one Workbench rebuild, server-side CSV import and validation | Drops/recreates the database and imports data |
| `01_create_database.sql` | Creates `movie_platform` with Unicode settings | Drops/recreates the database |
| `02_create_tables.sql` | Creates the six tables, keys and constraints | Drops/recreates tables |
| `04_import_clean_data.sql` | Loads the six cleaned CSV files with `LOCAL INFILE` | Inserts source data |
| `04b_validate_import.sql` | Checks row counts, relationships, rules and character import | Read-only |
| `04c_constraint_tests.sql` | Demonstrates rejected PK, FK, UNIQUE and CHECK violations | Statements are expected to fail |
| `05_crud_queries.sql` | Demonstrates users, reviews and watchlists CRUD plus movie search | Demo writes are rolled back |
| `06_advanced_queries.sql` | Eight joins/aggregations for discovery, recommendations and reporting | Read-only |
| `07_views.sql` | Creates movie statistics/catalogue and user activity views | Recreates three views |
| `08_indexes.sql` | Adds four query-driven indexes and includes `EXPLAIN` examples | Creates missing indexes |
| `09_comparison_queries.sql` | Five labelled MySQL/MongoDB operations; the first three match the Streamlit benchmark screen | Read-only |

## Validation checklist

After import, `04b_validate_import.sql` should report 21 genres, 1,000 movies, 2,541 movie-genre links, 30 users, 750 reviews and 300 watchlist entries. Every orphan/business-rule problem count should be zero.

For submission evidence in Workbench:

- run the validation queries and capture row-count/orphan results;
- run `05_crud_queries.sql` and confirm the final `ROLLBACK` leaves no `UDEMO001`, `RDEMO001` or `WDEMO001` row;
- run `07_views.sql`, then inspect the three views in the schema navigator;
- run `08_indexes.sql` twice to confirm it is rerunnable, and review the `key` column in each `EXPLAIN` result;
- run the advanced and comparison queries and check that their result sets are meaningful before collecting screenshots or timings.
