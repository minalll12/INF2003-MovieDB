"""One shared, pooled MongoClient (pymongo clients are thread-safe)."""
from pymongo import MongoClient

from .config import MONGO_DB, MONGO_URI

_client = None


def get_client():
    global _client
    if _client is None:
        _client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    return _client


def set_client(client) -> None:
    """Inject a client (tests use mongomock)."""
    global _client
    _client = client


def get_db():
    return get_client()[MONGO_DB]
