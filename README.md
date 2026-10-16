# INF2003-MovieDB
**Movie Review and Discovery System** · INF2003 Database Systems · Team 28 (SIT)

## Application Description
A centralised platform where users can discover movies, view movie information
and share their opinions through ratings and reviews. Users can browse, search
and filter movies, and view movie details and other users' reviews.

Registered users can log in to submit, edit and delete their own reviews and
ratings, and add or remove movies from a personal watchlist.

The same functionalities are implemented with both a **relational (MySQL)** and a
**non-relational (MongoDB)** database, so their data management, querying
capabilities and performance can be compared.

## System Architecture
Streamlit (frontend) → Python application layer → MySQL | MongoDB
- A shared Python **data access layer** exposes the same functions
  (e.g. `search_movies()`, `add_review()`) with separate MySQL and MongoDB
  implementations, so users can **switch databases from the interface**
  without changing frontend code.
- All queries are parameterised to prevent SQL injection.

## Data
- [IMDb Dataset of Top 1000 Movies and TV Shows (Kaggle)](https://www.kaggle.com/datasets/harshitshankhdhar/imdb-dataset-of-top-1000-movies-and-tv-shows):
  title, release year, genre, runtime, description, director, cast
- Cleaned and preprocessed, with unique movie IDs generated and genres extracted
  into separate `genres` and `movie_genres` datasets
- **Synthetic data:** users, reviews (rating + written feedback) and watchlists
- The same underlying data is used for both database implementations

## Database Design
| | MySQL | MongoDB |
|---|---|---|
| Stores | users, movies, genres, movie_genres, reviews, watchlists | users, movies, reviews, watchlists |
| Design | PKs, FKs, associative `movie_genres` table | Genres + cast **embedded** in each movie document |
| Advanced | Joins, aggregation, views, indexes | Aggregation pipelines, indexes |

## Functionalities
- Register / log in
- Browse, search and filter movies
- View movie details, reviews and average ratings
- Create, edit and delete your own reviews and ratings
- Add / remove movies from your watchlist
- Switch between MySQL and MongoDB from the UI
- Performance comparison of equivalent queries across dataset sizes

## Tech Stack
Python · Streamlit · MySQL · MongoDB · pandas

## Team
| Member | Role |
|---|---|
| Minal | Frontend + Overall Integration |
| Xue E | Relational Database – MySQL |
| Chu Ying | Non-Relational Database – MongoDB |
| Abinaya | Dataset + Data Processing & Analysis |
| Leticia | Testing + Database Comparison/Performance |

## Repo Structure
```
INF2003-MovieDB/
├── data/
│   └── cleaned/     # cleaned + synthetic CSVs (Abinaya)
├── notebooks/       # data processing & analysis (Abinaya, Leticia)
├── mysql/           # schema, seed, CRUD + advanced queries (Xue E)
├── mongodb/         # schema, seed, CRUD + aggregation pipelines (Chu Ying)
├── app/             # Streamlit UI + data access layer (Minal)
├── tests/           # CRUD tests, performance benchmarks (Leticia)
└── docs/            # report, architecture diagram, ERD, document model
```

## Team Rules
1. Work on your own branch, then open a Pull Request into `main`.
2. Only edit files in your own folder unless agreed in the group chat.
3. Never commit passwords or DB credentials. Use `.env` (it's gitignored).
4. Don't edit someone else's `.ipynb`.
5. Pull before you start, and commit small changes with clear messages.
