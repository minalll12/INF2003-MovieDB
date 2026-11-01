"""MongoDB configuration. Secrets come from the repo-root .env (gitignored) - never hard-code them."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "movie_platform")  # same name as the MySQL database
DATA_DIR = Path(os.getenv("DATA_DIR", ROOT / "data" / "cleaned"))

# Same business rules as the MySQL CHECK constraints (02_create_tables.sql)
MIN_RATING, MAX_RATING = 1.0, 10.0
MAX_REVIEW_LEN = 1000
