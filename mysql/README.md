# MySQL database

This folder contains the MySQL 8 implementation for the INF2003 Group 28 Movie Review and Discovery System. The schema uses the same string IDs as the MongoDB dataset so equivalent operations can be compared directly.

## Connection settings

If the repository-root `.env` does not exist, copy `.env.example` to `.env` and replace the placeholders locally. If it already exists, edit only the relevant entries without overwriting it. `.env` is ignored by Git; never commit passwords or other credentials.

The local defaults and example use `localhost:3307`. Set `DB_PORT` explicitly if your server uses another port (for example, the standard MySQL port `3306`). Use the same port in Workbench or the CLI, for example:

```powershell
mysql -h localhost -P 3307 -u root -p --local-infile=1
```

Changing the client port does not require any SQL script changes.

### Railway Cloud MySQL

The existing PyMySQL connection also supports Railway through the same `.env` variables:

```dotenv
DB_HOST=your-railway-public-hostname
DB_PORT=your-railway-public-port
DB_USER=moviedb_app
DB_PASSWORD='replace_with_your_app_user_password'
DB_NAME=movie_platform
```

Replace the hostname and port placeholders with Railway's public TCP endpoint, and use the restricted app user's password. The port must be an integer. For a backend running on your computer, use the public hostname rather than a Railway private hostname. Keep credentials only in your ignored `.env` or process environment. Existing process environment variables take precedence over `.env`; restart the backend after changing settings. To switch back to local MySQL, restore `DB_HOST=localhost`, `DB_PORT=3307` and your local user's credentials.

From the repository root, verify the configured connection safely:

```powershell
python -m mysql.verify_connection
```

This starts a read-only transaction, runs `SELECT DATABASE()` and `SELECT COUNT(*) FROM movies`, then rolls back and closes the connection. It prints only the selected database and movie count on success, or a generic configuration error on failure (exit code 1). It does not print credentials or create/change database objects or data.

The existing Railway schema is already imported. Do not run the setup/import scripts or the opt-in real database tests against the shared Railway service. Use only this read-only check for Railway verification.

## Streamlit integration status

The current `app/` still uses CSV-backed stand-ins. Xue's callable database layer is now in `crud.py`, `analytics.py` and `backend.py`. It does not import Streamlit or change the frontend. Minal owns registering `MySQLBackend` in `app/backends.py` and the application's session, switching, error handling and reset behaviour.

Install from the repository root:

```powershell
python -m pip install -r mysql/requirements.txt
```

The driver is PyMySQL (`import pymysql`), avoiding a package-name clash between this repository's `mysql/` folder and `mysql.connector`. It loads the existing root `.env` keys `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`. It creates no database/tables on import; run the SQL setup first.

```python
from mysql import crud, analytics
from mysql.backend import MySQLBackend

movies = crud.search_movies(title="the", genres=["Drama", "Crime"],
                            years=(1990, 2020), ratings=(7.0, 9.0), sort_by="Newest")
movie = crud.get_movie_details("M0001")
reviews = crud.movie_reviews("M0001")
db = MySQLBackend()  # also accepts store=None for the existing engine constructor
frame = db.search_movies(genres=("Drama",))
```

`crud` / `analytics` return `list[dict]`, a single `dict` / `None`, booleans, IDs or scalar values as documented below. `MySQLBackend` supplies the DataFrames/dicts/sets expected by every current `CsvBackend` public method; Minal can import it once the repository root is on the application import path. No frontend registration is performed by this folder.

### Callable API and data contract

| Functions | Result / behaviour |
|---|---|
| `search_movies(title="", genres=(), years=None, ratings=None, sort_by=None)` | Movie rows; all selected genres must match; duplicate genre selections are ignored. Case-insensitive, accent-sensitive literal substring search, including `%`, `_`, `!`, backslashes and quotes. Inclusive year/rating ranges. |
| `get_movie_details(movie_id)` / `get_movie(movie_id)` | Movie dict or `None` |
| `movie_reviews(movie_id)`, `user_reviews(user_id)` | Review rows, newest `updated_at` first, including `review_id`, `user_id`, `movie_id`, `rating`, `review_text`, both timestamps, `username`, `title`, `release_year` |
| `user_review_for(user_id, movie_id)` | Review dict or `None` |
| `add_review(user_id, movie_id, rating, text="")` | New review ID; duplicate user/movie, invalid rating/text or unknown FK raises `ValueError` |
| `update_review(review_id, rating, text, user_id=None)`, `delete_review(review_id, user_id=None)` | Boolean; pass `user_id` to restrict the mutation to the owner |
| `get_watchlist(user_id)` | Full movie rows plus formatted `added_at`, newest first |
| `watchlist_ids(user_id)` | Set of movie IDs |
| `add_to_watchlist(user_id, movie_id)` | `True` when inserted, `False` when already saved; invalid FK raises `ValueError` |
| `remove_from_watchlist(user_id, movie_id)` | Boolean, safe to repeat |
| `register_user(username, email, password)` | Public user dict; PBKDF2 hash compatible with `app/auth.py`, no plaintext storage |
| `authenticate(username, password)` | `{user_id, username, email}` or `None`; case-insensitive username |
| `get_user(user_id)`, `list_users()`, `username_taken()`, `email_taken()` | Account lookup/availability; hashes never returned |
| `update_user(user_id, username, email)`, `delete_user(user_id)` | Boolean; existing FK cascades remove deleted users' reviews/watchlists |

Movie rows contain the existing movie columns (excluding the redundant CSV `genre` string), `genres: list[str]`, `avg_rating`, integer `review_count`, and `poster_large`. `crud` keeps full-precision averages (`None` for no reviews); `MySQLBackend` produces pandas floats rounded to one decimal (`NaN` for no reviews), matching the UI. It adds `rating_mine` in `reviewed_movies()`. Empty frames retain their expected columns. All timestamps are local `YYYY-MM-DD HH:MM:SS` strings, matching the CSVs' naive `DATETIME` convention.

Sort modes are exactly `Highest rated`, `Most reviewed`, `Newest`, `Oldest`, `Title A–Z`. An omitted mode means `Highest rated`. The adapter sorts displayed one-decimal averages as the CSV backend does. Rating filters also use the displayed value with pandas/NumPy half-even rounding; `(0, 10)` disables the filter and includes unrated films. The SQL search narrows the candidate range and Python settles exact rounding boundaries. The standalone SQL demo uses MySQL's approximate-number `ROUND`, so use the callable tests for pandas boundary parity.

New IDs are the existing `U` / `R` / `W` prefix plus nine random hexadecimal characters, within `VARCHAR(10)`. Seed IDs are preserved. The frontend treats IDs as opaque strings and requires no numeric sequence. PK uniqueness and bounded collision retries therefore suffice; no `id_counters` table or schema migration is needed. Tests/benchmark comparisons should compare content/business keys, not expect matching newly generated IDs across engines.

Every input value is bound with `%s`; user input never supplies an identifier or an SQL clause. Sort clauses are chosen from a fixed allowlist. Mutations validate the 1–10 finite numeric rating and 1,000-character review limit, and use the existing PK/FK/UNIQUE/CHECK rules. Registration follows the UI's 3–30 character username rule and eight-character password minimum. Database failures become `OSError`; validation/constraint conflicts become `ValueError`.

### Handoff to Minal

Register `from mysql.backend import MySQLBackend` under the existing `"MySQL (Relational)"` engine key, install `mysql/requirements.txt` and configure `.env`. The class implements the current public backend methods and ignores the CSV-store constructor argument.

Pass the signed-in user ID to `update_review(..., user_id=...)` and `delete_review(..., user_id=...)` when enforcing ownership. The existing UI passes only the review ID, so the optional argument preserves that signature but cannot independently identify the actor. Handle `ValueError` for validation/duplicate conflicts in addition to the current `OSError` handling. These functions provide database operations; authorization/session decisions remain in the application layer.

The existing CSV reset button does not reset MySQL. Engine switching also needs an explicit account policy: users registered in one database are not automatically created in the other. Those application behaviours are left to Minal.

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
| `07_views.sql` | Creates movie statistics/catalogue and user activity views; preserves `average_rating` and adds UI `avg_rating` | Recreates three views |
| `08_indexes.sql` | Adds six query-driven indexes and eight `EXPLAIN` examples | Creates missing indexes |
| `09_comparison_queries.sql` | Five labelled MySQL/MongoDB operations; the first three match the Streamlit benchmark screen | Read-only |
| `db.py`, `security.py` | Connection/transaction handling, numeric/timestamp formatting and compatible PBKDF2 | No setup on import |
| `crud.py` | Parameterized users/reviews/watchlists CRUD and movie search | Commits each owned call |
| `analytics.py` | Callable forms of all five comparison operations and eight advanced queries | Read-only |
| `backend.py` | DataFrame adapter for the existing integration contract | Calls the database; no result cache |
| `DESIGN.md` | ERD, functional dependencies, normalization, constraints and index rationale | Documentation |

## Testing and comparison handoff to Leticia

```powershell
python -m pip install -r mysql/requirements-test.txt
python -m pytest tests/test_mysql.py -q

# Opt in to the real server tests. Use your local test server/account settings.
$env:MYSQL_TEST_REAL = '1'
$env:MYSQL_TEST_HOST = '127.0.0.1'
$env:MYSQL_TEST_PORT = '3307'
$env:MYSQL_TEST_USER = 'root'
# Set MYSQL_TEST_PASSWORD locally if required; do not commit credentials.
python -m pytest tests/test_mysql.py -q
```

The default tests need no server. Run from the repository root. The real suite requires MySQL 8.0.17+ (enforced CHECKs and the SQL demo's `CAST AS DOUBLE`), `local_infile=ON`, and an account permitted to create/drop a database. It creates a unique `movie_platform_test_<random>` database, runs the shipped CSV importer/schema/views/indexes, and drops only its own database in teardown. It never targets `DB_NAME`. Real tests check all filters/sorts against `CsvBackend`, complete CRUD, constraints, injection literals, rounding boundaries, empty frames, timestamps, all comparison/advanced functions, and rerun the SQL demos/index script. The standard CSV import routes above remain available for submission screenshots.

`analytics.py` exposes the same names as MongoDB: `movies_by_genre`, `average_rating`, `watchlist_with_genres`, `filtered_discovery` / `filtered_discovery_live`, `top_in_genre`, `discovery_ranking`, `top_per_genre`, `genre_health`, `recommend_movies`, `engagement_leaderboard`, `director_stats`, `genre_trends_by_decade`, `latest_review_feed`. It uses `movie_id` / `user_id` instead of MongoDB's raw `_id`, and `genre` for grouped genre names; normalize IDs before comparison. Genre lists are sorted. Analytics ratings are rounded to two decimal places; tolerate 0.01 when comparing MongoDB floating-point aggregates. Unrated averages are `None`, not zero.

For fair timing, use identical CSV snapshots/parameters and consume all returned rows. These simple functions open/close a connection per call by default, whereas MongoDB uses a shared client. Exclude connection setup by reusing a caller-owned connection for the timed SQL calls:

```python
from mysql import db, analytics

with db.session() as connection:
    # warm up, then time repeated calls with this same connection
    rows = analytics.movies_by_genre("Drama", connection=connection)
    value = analytics.average_rating("M0001", connection=connection)
    watchlist = analytics.watchlist_with_genres("U001", connection=connection)
```

Supplied connections stay open and the caller controls commit/rollback. Do not share a PyMySQL connection across threads. All backend reads are fresh; benchmark methods do not cache results. The existing Streamlit timing screen will include per-call MySQL connection overhead unless Minal adopts a connection/pool policy; use the functions above for database-query timings.

Operations 1–3 do equivalent live work in both engines. Pair MySQL `filtered_discovery_live` with MongoDB `filtered_discovery_live` for operation 4. MongoDB `filtered_discovery` and `top_in_genre` read precomputed statistics; MySQL aggregates reviews live. Label those as design trade-off comparisons and include review-write costs rather than treating the work as identical. Full-text search is outside the shared app contract and has not been added.

`08_indexes.sql` supplies plans for year filtering, per-movie AVG/COUNT, newest reviews, ordered watchlists, movie/user review lists, genre joins and multi-genre discovery. Record actual `key`, `rows` and `Extra` (or `EXPLAIN ANALYZE` on supported servers); the optimizer may prefer a scan for a tiny result set. Compare original 1,000-film data and any larger, consistently replicated datasets separately.

## Validation checklist

After import, `04b_validate_import.sql` should report 21 genres, 1,000 movies, 2,541 movie-genre links, 30 users, 750 reviews and 300 watchlist entries. Every orphan/business-rule problem count should be zero.

For submission evidence in Workbench:

- run the validation queries and capture row-count/orphan results;
- run `05_crud_queries.sql` and confirm the final `ROLLBACK` leaves no `UDEMO001`, `RDEMO001` or `WDEMO001` row;
- run `07_views.sql`, then inspect the three views in the schema navigator;
- run `08_indexes.sql` twice to confirm it is rerunnable, and review the `key` column in each `EXPLAIN` result;
- run the advanced and comparison queries and check that their result sets are meaningful before collecting screenshots or timings.
