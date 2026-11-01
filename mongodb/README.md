# MongoDB implementation (Chu Ying)

Document-model implementation of the same system MySQL implements: **users, movies, reviews, watchlists**
(genres + cast embedded in each movie). Uses the same six cleaned CSVs and the same string keys
(`M0001`, `U001`, `R0001`, `W0001` become each document's `_id`), so results are directly comparable.

## Setup
```bash
pip install -r mongodb/requirements.txt
# add to the repo-root .env (never commit it):
#   MONGO_URI=mongodb://localhost:27017
#   MONGO_DB=movie_platform
python -m mongodb.seed          # run from the repo root: builds collections, validators, indexes, view, loads the CSVs
```
Expected output: `{'users': 30, 'movies': 1000, 'reviews': 750, 'watchlists': 300}` (same counts as `mysql/04b_validate_import.sql`).
Needs MongoDB 5.0+ (local install, Docker `mongo:7`, or an Atlas URI). Seeding **drops and rebuilds** the database.

## Files
| File | Purpose |
|---|---|
| `schema.py` | `$jsonSchema` validators (= CHECK/NOT NULL/types), unique + multikey + compound + text indexes, `counters`, view `v_movie_catalog` |
| `seed.py` | CSV -> documents; embeds genres/cast; computes `avg_rating`/`review_count` |
| `crud.py` | Register/login, search/filter, review CRUD, watchlist CRUD (validated, injection-safe, owner-only edits) |
| `analytics.py` | Aggregation pipelines: MySQL comparison ops 1-5 (`09_comparison_queries.sql`) and advanced queries 1-8 (`06_advanced_queries.sql`) |
| `backend.py` | `MongoBackend` - same methods/return shapes as `app/backends.py` so Streamlit needs no changes |
| `security.py` | PBKDF2 hashing, byte-for-byte compatible with `app/auth.py` and `users.csv` |
| `explain_demo.py` | Query plans (IXSCAN vs COLLSCAN) for the efficiency section |
| `validation_demo.py` | Counterpart of `04c_constraint_tests.sql`: 7 writes that must be rejected |
| `../tests/test_mongodb.py` | 58 tests (57 pass on mongomock, 1 needs a real server) incl. parity with the CSV backend and pandas ground truth |

## Plugging into the app (Minal)
In `app/backends.py` (or `session.py`), add the repo root to `sys.path` and register the class:
```python
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from mongodb.backend import MongoBackend
ENGINES = {"MySQL (Relational)": RelationalBackend, "MongoDB (Document)": MongoBackend}
```
`MongoBackend(store)` ignores the CSV store. The 3 benchmark methods query the DB on every call (no cache);
`catalogue()` is cached and invalidated by writes made through the same object.

## Design decisions (for the report)
| MySQL | MongoDB | Trade-off |
|---|---|---|
| `genres` + `movie_genres` + 2 JOINs | `genres[]` embedded, multikey index | no join on the hottest read; renaming a genre touches many documents |
| FOREIGN KEYs | `_id` references checked in `crud.py` | MongoDB has no FK enforcement - integrity is the application's job |
| `UNIQUE(user_id, movie_id)`, `UNIQUE(username/email)` | unique compound/single indexes (`username_lower` for case-insensitivity) | same guarantee |
| `CHECK (rating BETWEEN 1 AND 10)`, types, lengths | `$jsonSchema` validator (+ checks in code) | same guarantee, enforced by the server |
| `AVG(rating)` computed per query / view | `avg_rating` + `review_count` stored on movie and recomputed on every review write (computed pattern) | O(1) reads; every review write costs one extra aggregate. `filtered_discovery` vs `filtered_discovery_live` benchmarks both |
| `reviews JOIN users` for the name | `username` denormalised into each review | no join; stale if usernames became editable (they are not) |
| `AUTO_INCREMENT` / generated ids | atomic `counters` document (`$inc`) -> `R0751` | works across processes |
| `ROW_NUMBER() OVER (PARTITION BY ...)` | `$unwind` -> `$sort` -> `$group/$push` -> `$slice` | works on any MongoDB version |
| `CREATE VIEW v_movie_catalog` | `create_collection(viewOn=...)` | read-only, computed per query |
| parameterised SQL | typed query documents, `re.escape`, string-type guards, no `$where` | blocks NoSQL operator injection |

## Tests
```bash
pytest tests/test_mongodb.py                      # in-memory (mongomock), no server
MONGO_TEST_REAL=1 pytest tests/test_mongodb.py    # real MongoDB: also checks the $jsonSchema validators
python -m mongodb.explain_demo && python -m mongodb.validation_demo   # screenshots for the report
```
**Known gap:** mongomock does not enforce validators, `$text` or views, so run the `MONGO_TEST_REAL=1` suite
and the two demos once on a real server before recording the demo.
