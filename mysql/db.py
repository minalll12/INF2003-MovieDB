"""Pooled reads; fresh write/explicit sessions; supplied connections remain caller-owned."""
import atexit
import os
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from threading import Condition, Lock
from time import monotonic

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


READ_POOL_SIZE = 3
READ_POOL_WAIT_TIMEOUT = 5.0
_READ_ERROR = "MySQL read failed; check the connection and installed schema."


def _close_quietly(connection):
    if connection is not None:
        try:
            connection.close()
        except BaseException:
            # Cleanup must not mask an error/cancellation or strand a pool slot.
            pass


class _ReadPool:
    """Exclusive leases; the bound includes idle, borrowed and opening connections."""

    def __init__(self, factory, max_size=READ_POOL_SIZE, wait_timeout=READ_POOL_WAIT_TIMEOUT):
        self._factory = factory
        self._max_size = max_size
        self._wait_timeout = wait_timeout
        self._condition = Condition()
        self._idle = []
        self._size = 0
        self._closed = False

    @property
    def drained(self):
        with self._condition:
            return self._closed and self._size == 0

    def _open(self):
        try:
            return self._factory()
        except Exception:
            # Driver/configuration messages can contain private connection details.
            raise OSError("MySQL read connection could not be established.") from None

    def acquire(self):
        deadline = monotonic() + self._wait_timeout
        connection = None
        reserved = False
        try:
            with self._condition:
                while True:
                    if self._closed:
                        raise OSError("MySQL read pool is closed.")
                    if self._idle:
                        connection = self._idle.pop()
                        reserved = True
                        break
                    if self._size < self._max_size:
                        self._size += 1
                        reserved = True
                        break
                    remaining = deadline - monotonic()
                    if remaining <= 0:
                        raise OSError("Timed out waiting for a MySQL read connection.")
                    self._condition.wait(remaining)

            # Network work happens outside the lock, with the slot still reserved.
            if connection is not None:
                try:
                    connection.ping(reconnect=False)
                except Exception:
                    _close_quietly(connection)
                    connection = None
            if connection is None:
                connection = self._open()  # At most one replacement, before SQL starts.
            with self._condition:
                if self._closed:
                    raise OSError("MySQL read pool is closed.")
            return connection
        except BaseException:
            if reserved:
                self._discard(connection)
            raise

    def _discard(self, connection):
        try:
            _close_quietly(connection)
        finally:
            with self._condition:
                self._size -= 1
                self._condition.notify_all()

    def release(self, connection, *, reusable):
        with self._condition:
            if reusable and not self._closed:
                self._idle.append(connection)
                self._condition.notify()
                return
        self._discard(connection)

    def close(self):
        """Reject new leases; close idle connections now and borrowed ones on return."""
        with self._condition:
            self._closed = True
            idle, self._idle = self._idle, []
            self._condition.notify_all()
        for connection in idle:
            self._discard(connection)


_read_pool = None
_read_pool_lock = Lock()


def _get_read_pool():
    global _read_pool
    with _read_pool_lock:
        # A disposed generation must drain before a new one can use its capacity.
        if _read_pool is None or _read_pool.drained:
            _read_pool = _ReadPool(connect)
        return _read_pool


def close_read_pool():
    """Dispose pooled reads without interrupting borrowers; next use recreates a drained pool."""
    with _read_pool_lock:
        pool = _read_pool
    if pool is not None:
        pool.close()


atexit.register(close_read_pool)


@contextmanager
def _read_session():
    pool = _get_read_pool()
    connection = pool.acquire()
    reusable = False
    try:
        yield connection
        connection.commit()
        reusable = True
    except BaseException as exc:
        try:
            connection.rollback()
        except BaseException:
            pass
        # Conservatively discard every failed read, even after a successful rollback.
        if isinstance(exc, pymysql.IntegrityError):
            code = exc.args[0] if exc.args and isinstance(exc.args[0], int) else None
            args = (code, "MySQL read integrity check failed.") if code is not None else (_READ_ERROR,)
            raise pymysql.IntegrityError(*args) from None
        if isinstance(exc, (pymysql.MySQLError, OSError)):
            raise OSError(_READ_ERROR) from None
        raise
    finally:
        pool.release(connection, reusable=reusable)


def normalise(row):
    return {k: float(v) if isinstance(v, Decimal) else
            v.strftime("%Y-%m-%d %H:%M:%S") if isinstance(v, (datetime, date)) else v
            for k, v in row.items()}


def fetch(sql, params=(), *, connection=None):
    scope = _read_session() if connection is None else session(connection)
    with scope as conn, conn.cursor() as cursor:
        cursor.execute(sql, params)
        return [normalise(row) for row in cursor.fetchall()]


def execute(sql, params=(), *, connection=None):
    with session(connection) as conn, conn.cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.rowcount
