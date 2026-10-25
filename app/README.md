# Streamlit App

## Running it

```bash
cd app
pip install -r requirements.txt
streamlit run app.py
```

Run from inside `app/` so `.streamlit/config.toml` (dark theme) is picked up.

## Layout

| File | Purpose |
|---|---|
| `app.py` | Entry point: page config, sidebar, navigation |
| `session.py` | Session state helpers (current user, selected engine, page links) |
| `backends.py` | Data access layer shared by every page |
| `data_store.py` | Loads and saves the working CSV copy |
| `auth.py` | PBKDF2 password hashing and verification |
| `components.py` | Movie cards, pagination, review cards and dialogs |
| `styles.py` | Theme CSS |
| `views/` | One module per page |

## Data

On first run the six CSVs in `data/cleaned/` are copied into `app/store/`, and every write
(new users, reviews, watchlist changes) goes to that copy. `data/cleaned/` is never modified.
**System settings → Reset demo data** in the sidebar restores the copy from `data/cleaned/`.
`app/store/` is gitignored.

## Database switch

`backends.py` defines `RelationalBackend` (MySQL) and `DocumentBackend` (MongoDB). Both
currently read the CSV store; the three benchmark queries are written in each data model's style
(joins across normalised tables vs. documents with embedded genres). Once the `mysql/` and
`mongodb/` modules are ready, each class should call them instead. Pages only talk to
`backend()`, so no UI code needs to change.

The benchmark numbers are only meaningful once the real databases are connected. The
CSV stand-ins compare pandas joins against plain Python lists, not MySQL against MongoDB.

## Passwords

Passwords are stored as `pbkdf2_sha256$200000$<salt hex>$<hash hex>`, with the salt hex-decoded
to bytes before hashing. Registration and login use real hash verification; no plaintext is stored.

The seeded accounts in `users.csv` only ship with hashes, so their passwords are unknown. To test
as one of them, use **Demo accounts** on the sign-in page, or **Switch user** in the sidebar once
signed in. If the seed hashes were generated with the salt used as a raw string rather than
hex-decoded, change `hash_password` in `auth.py` to match.
