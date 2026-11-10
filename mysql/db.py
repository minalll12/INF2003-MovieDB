"""Short-lived connections by default; callers may supply a connection for a benchmark/transaction."""
import os
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pymysql
from dotenv import load_dotenv
from pymysql.constants import CLIENT

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def connect(**overrides):
    """Connect using DB_* environment variables (Railway public endpoint or local MySQL).

    Process environment variables take precedence over the repository-root .env.
    Return an independent connection, never shared between Streamlit threads.
    """
    options = dict(
        host=os.getenv("DB_HOST", "localhost"), port=int(os.getenv("DB_PORT", "3307")),
        user=os.getenv("DB_USER", "root"), password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "movie_platform"), charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor, autocommit=False,
        client_flag=CLIENT.FOUND_ROWS, connect_timeout=5, read_timeout=30, write_timeout=30,
    )
    options.update(overrides)
    return pymysql.connect(**options)


@contextmanager
def session(connection=None):
    """Own commit/rollback/close only for connections created here.

    An explicitly supplied connection belongs to the caller, including its transaction.
    Integrity errors remain distinguishable; connection/query failures become OSError,
    which the existing frontend already handles.
    """
    owned = connection is None
    conn = connection
    try:
        if owned:
            conn = connect()
        yield conn
        if owned:
            conn.commit()
    except Exception as exc:
        if owned and conn is not None:
            conn.rollback()
        if isinstance(exc, pymysql.MySQLError) and not isinstance(exc, pymysql.IntegrityError):
            raise OSError("MySQL operation failed; check the connection and installed schema.") from exc
        raise
    finally:
        if owned and conn is not None:
            conn.close()


def normalise(row):
    return {k: float(v) if isinstance(v, Decimal) else
            v.strftime("%Y-%m-%d %H:%M:%S") if isinstance(v, (datetime, date)) else v
            for k, v in row.items()}


def fetch(sql, params=(), *, connection=None):
    with session(connection) as conn, conn.cursor() as cursor:
        cursor.execute(sql, params)
        return [normalise(row) for row in cursor.fetchall()]


def execute(sql, params=(), *, connection=None):
    with session(connection) as conn, conn.cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.rowcount
