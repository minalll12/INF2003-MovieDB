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

The app connects to **MySQL** (Railway Cloud) and **MongoDB** (Atlas) via the `mysql/` and
`mongodb/` backend modules. The engine selector in the sidebar switches between them at runtime.

If a real database backend fails to import (missing driver or config), the app falls back to
CSV-based stand-ins (`RelationalBackend` / `DocumentBackend`) that read from `app/store/`.
On first run the six CSVs in `data/cleaned/` are copied into `app/store/`; `data/cleaned/`
is never modified. `app/store/` is gitignored.

## Database switch

`backends.py` registers the real `MySQLBackend` and `MongoBackend` classes when their
imports succeed, with CSV fallbacks otherwise. Pages only talk to `backend()`, so no UI
code changes when switching engines. The **Performance** page benchmarks three comparison
queries head-to-head against both live databases.

## Passwords

Passwords are stored as `pbkdf2_sha256$200000$<salt hex>$<hash hex>`, with the salt hex-decoded
to bytes before hashing. Registration and login use real hash verification; no plaintext is stored.

The seeded accounts in `users.csv` only ship with hashes, so their passwords are unknown. To test
as one of them, use **Demo accounts** on the sign-in page, or **Switch user** in the sidebar once
signed in. If the seed hashes were generated with the salt used as a raw string rather than
hex-decoded, change `hash_password` in `auth.py` to match.
