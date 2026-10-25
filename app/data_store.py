import shutil
import threading
from pathlib import Path

import pandas as pd

APP_DIR = Path(__file__).resolve().parent
SOURCE_DIR = APP_DIR.parent / "data" / "cleaned"
STORE_DIR = APP_DIR / "store"

TABLES = {
    "movies": "movies.csv",
    "genres": "genres.csv",
    "movie_genres": "movie_genres.csv",
    "users": "users.csv",
    "reviews": "reviews.csv",
    "watchlists": "watchlists.csv",
}


class DataStore:
    # The cleaned CSVs are owned by the data team, so the app works on its own
    # copy in app/store/ and never writes back to data/cleaned/.

    def __init__(self):
        self._lock = threading.Lock()
        self.version = 0
        self.tables = {}
        self._seed()
        self._load()

    def _seed(self, overwrite=False):
        STORE_DIR.mkdir(exist_ok=True)
        for filename in TABLES.values():
            target = STORE_DIR / filename
            if overwrite or not target.exists():
                shutil.copyfile(SOURCE_DIR / filename, target)

    def _load(self):
        for name, filename in TABLES.items():
            self.tables[name] = pd.read_csv(STORE_DIR / filename, dtype={"rating": float})
        self.version += 1

    def reset(self):
        with self._lock:
            self._seed(overwrite=True)
            self._load()

    def __getitem__(self, name):
        return self.tables[name]

    def next_id(self, name, column):
        ids = self.tables[name][column]
        prefix = ids.iloc[0][0]
        width = len(ids.iloc[0]) - 1
        highest = ids.str[1:].astype(int).max() if len(ids) else 0
        return f"{prefix}{highest + 1:0{width}d}"

    def append(self, name, row):
        with self._lock:
            frame = pd.DataFrame([row], columns=self.tables[name].columns)
            frame.to_csv(STORE_DIR / TABLES[name], mode="a", header=False, index=False)
            self.tables[name] = pd.concat([self.tables[name], frame], ignore_index=True)
            self.version += 1

    def replace(self, name, frame):
        with self._lock:
            frame = frame.reset_index(drop=True)
            frame.to_csv(STORE_DIR / TABLES[name], index=False)
            self.tables[name] = frame
            self.version += 1
