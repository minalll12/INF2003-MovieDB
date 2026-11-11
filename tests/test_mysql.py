"""MySQL callable-contract tests plus opt-in tests on a disposable real database.

python -m pytest tests/test_mysql.py -q
MYSQL_TEST_REAL=1 python -m pytest tests/test_mysql.py -q

Real tests CREATE a unique movie_platform_test_<random> database, seed the six
CSVs, test the shipped SQL, and DROP only that database in teardown.
"""
import os
import re
import sys
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from threading import Event, Lock
from unittest.mock import MagicMock

import pandas as pd
import pymysql
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from mysql import analytics, crud, db, security  # noqa: E402
from mysql.backend import MOVIE_COLUMNS, REVIEW_COLUMNS, MySQLBackend, movie_frame  # noqa: E402

REAL = pytest.mark.skipif(os.getenv("MYSQL_TEST_REAL") != "1", reason="set MYSQL_TEST_REAL=1 for an isolated real MySQL database")


@pytest.fixture(autouse=True)
def isolated_read_pool(monkeypatch):
    db.close_read_pool()
    if os.getenv("MYSQL_TEST_REAL") != "1":
        def no_database_connection(*args, **kwargs):
            pytest.fail("Offline tests must not open a database connection")
        monkeypatch.setattr(pymysql, "connect", no_database_connection)
    yield
    db.close_read_pool()


def read_connection(rows=None):
    connection = MagicMock()
    cursor = connection.cursor.return_value
    cursor.__enter__.return_value = cursor
    cursor.fetchall.return_value = [{"value": 1}] if rows is None else rows
    return connection


@pytest.fixture
def install_pool(monkeypatch):
    pools = []

    def install(factory, **options):
        pool = db._ReadPool(factory, **options)
        pools.append(pool)
        monkeypatch.setattr(db, "_read_pool", pool)
        return pool

    yield install
    for pool in pools:
        pool.close()


class ReadCancelled(BaseException):
    pass


def test_read_pool_is_lazy_and_reuses_normalised_reads(install_pool):
    connection = read_connection([{"rating": Decimal("8.5"), "created_at": datetime(2026, 1, 2)}])
    factory = MagicMock(return_value=connection)
    install_pool(factory)
    factory.assert_not_called()
    for _ in range(10):
        assert db.fetch("SELECT rating, created_at WHERE movie_id = %s", ("M0001",)) == [
            {"rating": 8.5, "created_at": "2026-01-02 00:00:00"}]
    factory.assert_called_once_with()
    assert connection.commit.call_count == 10
    assert connection.ping.call_count == 9
    connection.ping.assert_called_with(reconnect=False)
    connection.rollback.assert_not_called()
    connection.close.assert_not_called()
    assert connection.cursor.return_value.__exit__.call_count == 10


def test_read_pool_default_bounds():
    assert db.READ_POOL_SIZE == 3
    assert db.READ_POOL_WAIT_TIMEOUT == 5.0


@pytest.mark.parametrize("failure", [None, pymysql.OperationalError(2006, "offline failure")])
def test_fetch_supplied_connection_bypasses_pool(monkeypatch, failure):
    connection = read_connection()
    forbidden = MagicMock(side_effect=AssertionError("Pool must not be used"))
    monkeypatch.setattr(db, "_get_read_pool", forbidden)
    if failure:
        connection.cursor.return_value.execute.side_effect = failure
        with pytest.raises(OSError):
            db.fetch("SELECT 1", connection=connection)
    else:
        assert db.fetch("SELECT 1", connection=connection) == [{"value": 1}]
    forbidden.assert_not_called()
    for name in ("commit", "rollback", "close", "ping"):
        getattr(connection, name).assert_not_called()


def test_writes_and_explicit_sessions_keep_fresh_connections(monkeypatch, install_pool):
    reader = read_connection()
    read_factory = MagicMock(return_value=reader)
    install_pool(read_factory)
    db.fetch("SELECT 1")
    writers = [read_connection() for _ in range(3)]
    writers[0].cursor.return_value.rowcount = 1
    fresh = MagicMock(side_effect=writers)
    monkeypatch.setattr(db, "connect", fresh)
    assert db.execute("UPDATE reviews SET rating = %s WHERE review_id = %s", (8, "R0001")) == 1
    assert crud.add_review("U001", "M0001", 8, "offline").startswith("R")
    with db.session() as explicit:
        db.fetch("SELECT 1", connection=explicit)
    assert fresh.call_count == 3
    for writer in writers:
        writer.commit.assert_called_once_with()
        writer.close.assert_called_once_with()
        writer.ping.assert_not_called()
    db.fetch("SELECT 1")
    read_factory.assert_called_once_with()
    reader.close.assert_not_called()


@pytest.mark.parametrize("phase", ["cursor", "execute", "fetchall", "cursor_exit", "commit"])
def test_read_failure_rolls_back_discards_and_never_replays(install_pool, phase):
    failed, healthy = read_connection(), read_connection()
    cursor = failed.cursor.return_value
    target = {"cursor": failed.cursor, "execute": cursor.execute, "fetchall": cursor.fetchall,
              "cursor_exit": cursor.__exit__, "commit": failed.commit}[phase]
    target.side_effect = pymysql.OperationalError(2013, "private-driver-detail")
    factory = MagicMock(side_effect=[failed, healthy])
    install_pool(factory, max_size=1, wait_timeout=0)
    with pytest.raises(OSError) as caught:
        db.fetch("SELECT 1")
    assert "private-driver-detail" not in "".join(traceback.format_exception(caught.value))
    failed.rollback.assert_called_once_with()
    failed.close.assert_called_once_with()
    assert cursor.execute.call_count <= 1
    factory.assert_called_once_with()  # No replay on a replacement connection.
    assert db.fetch("SELECT 1") == [{"value": 1}]
    assert factory.call_count == 2


def test_read_integrity_error_preserves_type_and_code_without_private_details(install_pool):
    connection = read_connection()
    connection.cursor.return_value.execute.side_effect = pymysql.IntegrityError(1062, "private-driver-detail")
    install_pool(lambda: connection)
    with pytest.raises(pymysql.IntegrityError) as caught:
        db.fetch("SELECT 1")
    assert caught.value.args[0] == 1062
    assert "private-driver-detail" not in "".join(traceback.format_exception(caught.value))
    connection.rollback.assert_called_once_with()
    connection.close.assert_called_once_with()


@pytest.mark.parametrize("phase", ["execute", "fetchall", "commit"])
def test_read_cancellation_releases_capacity(install_pool, phase):
    failed, healthy = read_connection(), read_connection()
    cancelled = ReadCancelled()
    target = failed.commit if phase == "commit" else getattr(failed.cursor.return_value, phase)
    target.side_effect = cancelled
    factory = MagicMock(side_effect=[failed, healthy])
    install_pool(factory, max_size=1, wait_timeout=0)
    with pytest.raises(ReadCancelled) as caught:
        db.fetch("SELECT 1")
    assert caught.value is cancelled
    failed.rollback.assert_called_once_with()
    failed.close.assert_called_once_with()
    assert db.fetch("SELECT 1") == [{"value": 1}]


def test_cleanup_failures_do_not_mask_original_error_or_leak_capacity(install_pool):
    failed, healthy = read_connection(), read_connection()
    original = ValueError("invalid result")
    failed.cursor.return_value.fetchall.side_effect = original
    failed.rollback.side_effect = ReadCancelled()
    failed.close.side_effect = pymysql.OperationalError(2006, "private-close-detail")
    install_pool(MagicMock(side_effect=[failed, healthy]), max_size=1, wait_timeout=0)
    with pytest.raises(ValueError) as caught:
        db.fetch("SELECT 1")
    assert caught.value is original
    assert db.fetch("SELECT 1") == [{"value": 1}]


@pytest.mark.parametrize("error", [pymysql.OperationalError(1045, "private-driver-detail"),
                                  ValueError("private-config-detail"), ReadCancelled()])
def test_failed_or_cancelled_creation_releases_reservation(install_pool, error):
    healthy = read_connection()
    factory = MagicMock(side_effect=[error, healthy])
    install_pool(factory, max_size=1, wait_timeout=0)
    expected = ReadCancelled if isinstance(error, ReadCancelled) else OSError
    with pytest.raises(expected) as caught:
        db.fetch("SELECT 1")
    assert "private-" not in "".join(traceback.format_exception(caught.value))
    factory.assert_called_once_with()
    assert db.fetch("SELECT 1") == [{"value": 1}]


def test_stale_connection_is_replaced_before_query(install_pool):
    stale, healthy = read_connection(), read_connection()
    factory = MagicMock(side_effect=[stale, healthy])
    install_pool(factory, max_size=1)
    db.fetch("SELECT 1")
    stale.ping.side_effect = pymysql.OperationalError(2006, "expired")
    assert db.fetch("SELECT 1") == [{"value": 1}]
    stale.ping.assert_called_once_with(reconnect=False)
    stale.close.assert_called_once_with()
    assert stale.cursor.return_value.execute.call_count == 1
    healthy.ping.assert_not_called()
    assert factory.call_count == 2


def test_stale_replacement_failure_is_not_retried(install_pool):
    stale, healthy = read_connection(), read_connection()
    factory = MagicMock(side_effect=[stale, pymysql.OperationalError(1045, "private-driver-detail"), healthy])
    install_pool(factory, max_size=1, wait_timeout=0)
    db.fetch("SELECT 1")
    stale.ping.side_effect = pymysql.OperationalError(2006, "expired")
    with pytest.raises(OSError):
        db.fetch("SELECT 1")
    assert factory.call_count == 2
    assert stale.cursor.return_value.execute.call_count == 1
    assert db.fetch("SELECT 1") == [{"value": 1}]


def test_cancelled_ping_discards_without_replacement(install_pool):
    stale, healthy = read_connection(), read_connection()
    factory = MagicMock(side_effect=[stale, healthy])
    install_pool(factory, max_size=1, wait_timeout=0)
    db.fetch("SELECT 1")
    stale.ping.side_effect = ReadCancelled()
    with pytest.raises(ReadCancelled):
        db.fetch("SELECT 1")
    factory.assert_called_once_with()
    stale.close.assert_called_once_with()
    assert db.fetch("SELECT 1") == [{"value": 1}]


def test_wait_uses_one_deadline_despite_spurious_wakeups(monkeypatch, install_pool):
    factory = MagicMock(side_effect=read_connection)
    pool = install_pool(factory, max_size=1)
    borrowed = pool.acquire()
    clock = iter([0.0, 1.0, 3.0, 5.1])
    monkeypatch.setattr(db, "monotonic", lambda: next(clock))
    wait = MagicMock()
    monkeypatch.setattr(pool._condition, "wait", wait)
    with pytest.raises(OSError, match="Timed out"):
        pool.acquire()
    assert [call.args[0] for call in wait.call_args_list] == [4.0, 2.0]
    factory.assert_called_once_with()
    pool.release(borrowed, reusable=True)


def test_cancelled_wait_does_not_release_another_borrowers_slot(monkeypatch, install_pool):
    pool = install_pool(read_connection, max_size=1)
    borrowed = pool.acquire()
    monkeypatch.setattr(pool._condition, "wait", MagicMock(side_effect=ReadCancelled()))
    with pytest.raises(ReadCancelled):
        pool.acquire()
    borrowed.close.assert_not_called()
    pool.release(borrowed, reusable=True)
    assert db.fetch("SELECT 1") == [{"value": 1}]


def test_limit_includes_connections_still_being_created(install_pool):
    all_opening, finish_opening = Event(), Event()
    lock, created = Lock(), []

    def factory():
        connection = read_connection()
        with lock:
            created.append(connection)
            if len(created) == 3:
                all_opening.set()
        assert finish_opening.wait(5)
        return connection

    pool = install_pool(factory, wait_timeout=0.01)
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(pool.acquire) for _ in range(3)]
        try:
            assert all_opening.wait(5)  # Creation must not hold the pool lock.
            with pytest.raises(OSError, match="Timed out"):
                pool.acquire()
            assert len(created) == 3
        finally:
            finish_opening.set()
        for future in futures:
            pool.release(future.result(timeout=5), reusable=True)


def test_concurrent_fetches_have_exclusive_bounded_leases(install_pool):
    all_reading, finish_reading = Event(), Event()
    lock, connections, active = Lock(), [], set()

    def factory():
        connection = read_connection()
        cursor = connection.cursor.return_value
        with lock:
            index = len(connections)
            connections.append(connection)
        value = {}

        def execute(sql, params):
            with lock:
                assert index not in active, "Connection was shared concurrently"
                active.add(index)
                if len(active) == 3:
                    all_reading.set()
            value["result"] = params[0]
            assert finish_reading.wait(5)

        def finish():
            with lock:
                active.remove(index)

        cursor.execute.side_effect = execute
        cursor.fetchall.side_effect = lambda: [{"value": value["result"]}]
        connection.commit.side_effect = finish
        return connection

    install_pool(factory)
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(db.fetch, "SELECT %s", (i,)) for i in range(6)]
        try:
            assert all_reading.wait(5)
            assert len(connections) == 3
        finally:
            finish_reading.set()
        assert [future.result(timeout=5) for future in futures] == [[{"value": i}] for i in range(6)]
    assert not active
    assert len(connections) == 3
    assert sum(connection.commit.call_count for connection in connections) == 6


def test_disposal_wakes_waiters_and_closes_borrowers_on_return(monkeypatch, install_pool):
    pool = install_pool(read_connection, max_size=1)
    borrowed = pool.acquire()
    waiting = Event()
    original_wait = pool._condition.wait

    def observed_wait(timeout):
        waiting.set()
        return original_wait(timeout)

    monkeypatch.setattr(pool._condition, "wait", observed_wait)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(pool.acquire)
        try:
            assert waiting.wait(5)
        finally:
            pool.close()
        with pytest.raises(OSError, match="closed"):
            future.result(timeout=5)
    borrowed.close.assert_not_called()
    assert not pool.drained
    pool.release(borrowed, reusable=True)
    borrowed.close.assert_called_once_with()
    assert pool.drained


def test_disposal_during_creation_closes_new_connection(install_pool):
    opening, finish = Event(), Event()
    connection = read_connection()

    def factory():
        opening.set()
        assert finish.wait(5)
        return connection

    pool = install_pool(factory)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(pool.acquire)
        try:
            assert opening.wait(5)
            pool.close()
        finally:
            finish.set()
        with pytest.raises(OSError, match="closed"):
            future.result(timeout=5)
    connection.close.assert_called_once_with()
    assert pool.drained


def test_global_disposal_drains_before_creating_another_pool(monkeypatch, install_pool):
    pool = install_pool(read_connection)
    borrowed = pool.acquire()
    fresh = MagicMock(side_effect=read_connection)
    monkeypatch.setattr(db, "connect", fresh)
    db.close_read_pool()
    with pytest.raises(OSError, match="closed"):
        db.fetch("SELECT 1")
    fresh.assert_not_called()
    pool.release(borrowed, reusable=True)
    assert db.fetch("SELECT 1") == [{"value": 1}]
    fresh.assert_called_once_with()
    db.close_read_pool()
    db.close_read_pool()  # Repeated disposal is safe.


def test_close_failure_after_successful_commit_does_not_fail_read(install_pool):
    connection = read_connection()
    pool = install_pool(lambda: connection)
    connection.commit.side_effect = pool.close
    connection.close.side_effect = OSError("private-close-detail")
    assert db.fetch("SELECT 1") == [{"value": 1}]
    connection.commit.assert_called_once_with()
    connection.rollback.assert_not_called()
    assert pool.drained


def test_password_format_matches_app():
    from app.auth import hash_password
    hashed = hash_password("testpassword", salt="ab" * 16)
    assert hashed == security.hash_password("testpassword", salt="ab" * 16)
    assert security.verify_password("testpassword", hashed)
    assert not security.verify_password("wrong", hashed)
    for bad in (None, "x", "pbkdf2_sha256$bad$zz$hash"):
        assert not security.verify_password("x", bad)


@pytest.mark.parametrize("value", [True, "9", None, float("nan"), float("inf"), 0.9, 10.1])
def test_invalid_rating_rejected_before_sql(value):
    with pytest.raises(ValueError):
        crud.add_review("U001", "M0001", value, "review")


@pytest.mark.parametrize("kw", [
    {"title": {"$ne": ""}}, {"genres": "Drama"}, {"genres": [None]}, {"years": (2000, 1990)},
    {"ratings": (8, 7)}, {"ratings": (float("nan"), 9)}, {"years": (1990.5, 2000)},
    {"sort_by": "title; DROP TABLE users"},
])
def test_invalid_search_rejected_before_sql(kw):
    with pytest.raises(ValueError):
        crud.search_movies(**kw)


def test_search_binds_literals_and_requires_all_genres(monkeypatch):
    query = MagicMock(return_value=[])
    monkeypatch.setattr(db, "fetch", query)
    title = "50%_!\\' OR 1=1 --"
    crud.search_movies(title, ["Drama", "Crime", "Drama"], (1990, 2020), (7, 8), "Newest")
    sql, params = query.call_args.args
    assert title not in sql and "Drama" not in sql and "Crime" not in sql
    assert "HAVING COUNT(*) = %s" in sql and "ESCAPE '!'" in sql
    assert params == ("%50!%!_!!\\' OR 1=1 --%", "Crime", "Drama", 2, 1990, 2020, Decimal("6.95"), Decimal("8.05"))


def test_normalise_and_empty_frames():
    assert db.normalise({"rating": Decimal("8.5"), "created_at": datetime(2026, 1, 2, 3, 4, 5)}) == {
        "rating": 8.5, "created_at": "2026-01-02 03:04:05"}
    assert list(movie_frame([]).columns) == MOVIE_COLUMNS
    assert movie_frame([]).empty
    assert crud.display_rating(6.65) == 6.6  # pandas half-even presentation


def test_connection_ownership_and_rollback(monkeypatch):
    conn = MagicMock()
    monkeypatch.setattr(db, "connect", lambda: conn)
    with db.session():
        pass
    conn.commit.assert_called_once()
    conn.close.assert_called_once()
    conn.reset_mock()
    with pytest.raises(RuntimeError), db.session():
        raise RuntimeError("failure")
    conn.rollback.assert_called_once()
    conn.close.assert_called_once()
    conn.reset_mock()
    with db.session(conn):
        pass
    conn.commit.assert_not_called()
    conn.close.assert_not_called()


def test_id_collision_retried_without_counter_table(monkeypatch):
    cursor = MagicMock()
    cursor.execute.side_effect = [pymysql.IntegrityError(1062, "duplicate primary key"), None, None]
    cursor.fetchone.return_value = {"review_id": "R111111111"}
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor
    ids = iter([MagicMock(hex="1" * 32), MagicMock(hex="2" * 32)])
    monkeypatch.setattr(crud.uuid, "uuid4", lambda: next(ids))
    assert crud.add_review("U001", "M0001", 8, "test", connection=conn) == "R222222222"
    assert cursor.execute.call_args_list[0].args[1][0] == "R111111111"
    assert cursor.execute.call_args_list[2].args[1][0] == "R222222222"


def statements(path):
    """Read the team's SQL scripts, including the DELIMITER-based index helper."""
    delimiter, pending = ";", []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.split("--", 1)[0].strip()
        if not line:
            continue
        if line.upper().startswith("DELIMITER "):
            assert not pending
            delimiter = line.split()[1]
            continue
        pending.append(line)
        if line.endswith(delimiter):
            yield "\n".join(pending)[:-len(delimiter)]
            pending = []
    assert not pending


def run_script(conn, filename):
    results = []
    with conn.cursor() as cursor:
        for statement in statements(ROOT / "mysql" / filename):
            if statement.upper().startswith("USE "):
                continue  # isolate scripts in the unique test schema
            cursor.execute(statement)
            if cursor.description:
                results.append(cursor.fetchall())
    return results


@pytest.fixture(scope="module")
def source():
    return {name: pd.read_csv(ROOT / "data" / "cleaned" / f"{name}.csv")
            for name in ("movies", "genres", "movie_genres", "users", "reviews", "watchlists")}


@pytest.fixture(scope="module")
def database():
    if os.getenv("MYSQL_TEST_REAL") != "1":
        pytest.skip("real MySQL tests are opt-in")
    db.close_read_pool()
    original_connect = db.connect
    options = dict(host=os.getenv("MYSQL_TEST_HOST", "127.0.0.1"), port=int(os.getenv("MYSQL_TEST_PORT", "3306")),
                   user=os.getenv("MYSQL_TEST_USER", "root"), password=os.getenv("MYSQL_TEST_PASSWORD", ""))
    # Trusted generated identifier, never derived from user input or DB_NAME.
    name = "movie_platform_test_" + uuid.uuid4().hex[:12]
    admin = original_connect(database=None, **options)
    with admin.cursor() as cursor:
        cursor.execute(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
    patch = pytest.MonkeyPatch()
    patch.setattr(db, "connect", lambda **kw: original_connect(**(options | {"database": name, "local_infile": True} | kw)))
    try:
        with db.session() as conn:
            run_script(conn, "02_create_tables.sql")
            run_script(conn, "04_import_clean_data.sql")
            run_script(conn, "07_views.sql")
            run_script(conn, "08_indexes.sql")
        yield name
    finally:
        db.close_read_pool()  # Dispose test-schema reads before restoring the app factory.
        patch.undo()
        with admin.cursor() as cursor:
            cursor.execute(f"DROP DATABASE `{name}`")
        admin.close()


@pytest.fixture()
def backend(database):
    return MySQLBackend()


@pytest.fixture()
def transaction(database):
    conn = db.connect()
    try:
        yield conn
    finally:
        conn.rollback()
        conn.close()


@pytest.fixture(scope="module")
def csv_backend(source):
    # Reuse the actual app contract, without creating app/store or importing Streamlit.
    sys.path.insert(0, str(ROOT / "app"))
    from backends import CsvBackend

    class Store(dict):
        version = 1
    return CsvBackend(Store(source))


@REAL
def test_import_schema_views_and_scripts(database, source):
    with db.session() as conn:
        counts = run_script(conn, "04b_validate_import.sql")
        assert all(r["actual_rows"] == r["expected_rows"] for r in counts[0])
        assert all(r["problems"] == 0 for r in counts[1])
        run_script(conn, "05_crud_queries.sql")  # rollback must leave baseline intact
        run_script(conn, "06_advanced_queries.sql")
        run_script(conn, "09_comparison_queries.sql")
        plans = run_script(conn, "08_indexes.sql")  # rerunnable
        assert len(plans) == 8 and all(plans)
        assert not db.fetch("SELECT user_id FROM users WHERE user_id = %s", ("UDEMO001",), connection=conn)
        assert len(db.fetch("SELECT * FROM v_movie_catalog", connection=conn)) == 1000
        with conn.cursor() as cursor:
            for statement in statements(ROOT / "mysql" / "04c_constraint_tests.sql"):
                if statement.startswith("USE "):
                    continue
                with pytest.raises(pymysql.MySQLError) as rejected:
                    cursor.execute(statement)
                assert rejected.value.args[0] in (1062, 1451, 1452, 3819)


@REAL
@pytest.mark.parametrize("kw", [
    {}, {"title": "the"}, {"genres": ["Drama"]}, {"genres": ["Drama", "Crime"]},
    {"genres": ["Drama", "Drama", "Crime"]}, {"genres": ["No such genre"]},
    {"years": (1990, 2000)}, {"ratings": (7, 8)}, {"ratings": (0, 10)},
    {"title": "a", "genres": ["Comedy"], "years": (1980, 2010), "ratings": (5, 9)},
])
@pytest.mark.parametrize("sort_by", list(crud.SORTS))
def test_search_parity(backend, csv_backend, kw, sort_by):
    got = backend.search_movies(sort_by=sort_by, **kw)
    expected = csv_backend.search_movies(sort_by=sort_by, **kw)
    assert set(got.movie_id) == set(expected.movie_id)
    if got.empty:
        return
    from mysql.backend import SORTS
    columns, _ = SORTS[sort_by]
    # Tied movies may appear in either order; sort keys and complete field values must agree.
    assert got[columns].fillna(-1).to_numpy().tolist() == expected[columns].fillna(-1).to_numpy().tolist()
    a, b = got.set_index("movie_id").sort_index(), expected.set_index("movie_id").sort_index()
    pd.testing.assert_series_equal(a.avg_rating, b.avg_rating, check_names=False, atol=0.11)
    assert a.review_count.tolist() == b.review_count.tolist()


@REAL
def test_backend_shapes_and_values(backend, csv_backend):
    pairs = [(backend.catalogue(), csv_backend.catalogue()), (backend.well_rated(2), csv_backend.well_rated(2)),
             (backend.most_reviewed(), csv_backend.most_reviewed()), (backend.most_voted(5), csv_backend.most_voted(5)),
             (backend.latest_reviews(5), csv_backend.latest_reviews(5)), (backend.movie_reviews("M0001"), csv_backend.movie_reviews("M0001")),
             (backend.user_reviews("U001"), csv_backend.user_reviews("U001")),
             (backend.user_watchlist("U001"), csv_backend.user_watchlist("U001")),
             (backend.reviewed_movies("U001"), csv_backend.reviewed_movies("U001"))]
    for got, expected in pairs:
        assert set(got.columns) >= set(expected.columns) - {"genre"}
        assert len(got) == len(expected)
    assert list(backend.latest_reviews(10).review_id) == list(csv_backend.latest_reviews(10).review_id)
    assert backend.get_user("U001") == csv_backend.get_user("U001")
    assert backend.member_since("U001") == csv_backend.member_since("U001")
    assert backend.genre_names() == csv_backend.genre_names()
    assert backend.year_bounds() == csv_backend.year_bounds()
    assert backend.watchlist_ids("U001") == csv_backend.watchlist_ids("U001")
    got = backend.get_movie_details("M0001")
    assert isinstance(got["genres"], list) and isinstance(got["avg_rating"], float)
    assert "._V1_SX400.jpg" in got["poster_large"]
    assert backend.get_movie("M9999") is None
    assert list(backend.movie_reviews("M9999").columns) == REVIEW_COLUMNS
    assert backend.user_watchlist("U999").empty and backend.reviewed_movies("U999").empty


@REAL
def test_review_watchlist_user_lifecycle(transaction):
    conn = transaction
    u = crud.register_user("mysql_test_user", "MYSQL@example.com", "supersecret", connection=conn)
    uid = u["user_id"]
    assert re.fullmatch(r"U[0-9a-f]{9}", uid)
    assert crud.authenticate("MYSQL_TEST_USER", "supersecret", connection=conn) == u
    assert crud.authenticate("mysql_test_user", "wrong", connection=conn) is None
    assert crud.username_taken("MYSQL_TEST_USER", connection=conn) and crud.email_taken("mysql@example.com", connection=conn)
    with pytest.raises(ValueError):
        crud.register_user("MYSQL_TEST_USER", "other@example.com", "supersecret", connection=conn)
    rid = crud.add_review(uid, "M0001", 8.5, "review", connection=conn)
    assert re.fullmatch(r"R[0-9a-f]{9}", rid)
    assert crud.user_review_for(uid, "M0001", connection=conn)["review_id"] == rid
    with pytest.raises(ValueError):
        crud.add_review(uid, "M0001", 7, "duplicate", connection=conn)
    assert not crud.update_review(rid, 5, "wrong owner", user_id="U001", connection=conn)
    assert not crud.delete_review(rid, user_id="U001", connection=conn)
    assert crud.update_review(rid, 5, "changed", user_id=uid, connection=conn)
    assert crud.update_review(rid, 5, "changed", user_id=uid, connection=conn)  # no-op still matches
    assert crud.user_review_for(uid, "M0001", connection=conn)["rating"] == 5.0
    assert crud.add_to_watchlist(uid, "M0002", connection=conn)
    assert not crud.add_to_watchlist(uid, "M0002", connection=conn)
    assert crud.get_watchlist(uid, connection=conn)[0]["movie_id"] == "M0002"
    assert crud.remove_from_watchlist(uid, "M0002", connection=conn)
    assert not crud.remove_from_watchlist(uid, "M0002", connection=conn)
    assert crud.update_user(uid, "mysql_changed", "changed@example.com", connection=conn)
    assert crud.movie_reviews("M0001", connection=conn)[0]["username"] == "mysql_changed"
    assert crud.delete_review(rid, user_id=uid, connection=conn)
    assert not crud.delete_review(rid, user_id=uid, connection=conn)
    crud.add_review(uid, "M0002", 9, "cascade", connection=conn)
    crud.add_to_watchlist(uid, "M0003", connection=conn)
    assert crud.delete_user(uid, connection=conn)
    assert not crud.user_reviews(uid, connection=conn) and not crud.watchlist_ids(uid, connection=conn)


@REAL
def test_validation_injection_and_live_stats(transaction):
    conn = transaction
    for uid, mid in [("U999", "M0001"), ("U001", "M9999")]:
        with pytest.raises(ValueError):
            crud.add_review(uid, mid, 8, "bad reference", connection=conn)
        with pytest.raises(ValueError):
            crud.add_to_watchlist(uid, mid, connection=conn)
    with pytest.raises(ValueError):
        crud.add_review("U001", "M0001", 8, "x" * 1001, connection=conn)
    for literal in [".*", "' OR 1=1 --", "%", "_", "!", "\\"]:
        rows = crud.search_movies(title=literal, connection=conn)
        assert all(literal.lower() in row["title"].lower() for row in rows)
    # Exercise literal %, _, !, backslash and a rounding boundary with controlled data.
    title = "50%_!\\ movie"
    db.execute("INSERT INTO movies (movie_id, title, release_year, duration) VALUES (%s, %s, %s, %s)",
               ("MTEST", title, 2020, 90), connection=conn)
    assert crud.search_movies(title=title, connection=conn)[0]["movie_id"] == "MTEST"
    assert crud.get_movie_details("MTEST", connection=conn)["genres"] == []
    r1 = crud.add_review("U001", "MTEST", 6.6, "a", connection=conn)
    r2 = crud.add_review("U002", "MTEST", 6.7, "b", connection=conn)
    assert crud.search_movies(title=title, ratings=(6.6, 6.6), connection=conn)
    assert not crud.search_movies(title=title, ratings=(6.7, 6.7), connection=conn)
    crud.update_review(r1, 10, "changed", connection=conn)
    assert analytics.average_rating("MTEST", connection=conn) == 8.35
    crud.delete_review(r1, connection=conn)
    crud.delete_review(r2, connection=conn)
    assert crud.get_movie_details("MTEST", connection=conn)["avg_rating"] is None
    assert crud.get_movie_details("MTEST", connection=conn)["review_count"] == 0


@REAL
def test_comparison_and_advanced_queries(database, source):
    rv, mg, genres = source["reviews"], source["movie_genres"], source["genres"]
    with db.session() as conn:
        gid = genres.set_index("genre_name").loc["Drama", "genre_id"]
        assert {r["movie_id"] for r in analytics.movies_by_genre("Drama", connection=conn)} == set(mg[mg.genre_id == gid].movie_id)
        ratings = rv[rv.movie_id == "M0001"].rating
        expected_avg = None if ratings.empty else round(ratings.mean(), 2)
        assert analytics.average_rating("M0001", connection=conn) == expected_avg
        watch = analytics.watchlist_with_genres("U001", connection=conn)
        assert {r["movie_id"] for r in watch} == set(source["watchlists"].query("user_id == 'U001'").movie_id)
        assert all(isinstance(r["genres"], list) and r["genres"] for r in watch)
        filtered = analytics.filtered_discovery("Drama", 1990, 2020, connection=conn)
        assert all(1990 <= r["release_year"] <= 2020 for r in filtered) and len(filtered) == 25
        top = analytics.top_in_genre("Drama", connection=conn)
        assert all(r["review_count"] >= 2 for r in top) and len(top) == 10
        assert len(analytics.discovery_ranking(connection=conn)) == 20
        assert all(r["genre_rank"] <= 3 and r["review_count"] >= 2 for r in analytics.top_per_genre(connection=conn))
        health = analytics.genre_health(connection=conn)
        assert len(health) == 21 and sum(r["movie_count"] for r in health) == 2541
        expected = mg.merge(rv.groupby("movie_id").size().rename("n"), on="movie_id").n.sum()
        assert sum(r["review_count"] for r in health) == expected
        lb = analytics.engagement_leaderboard(connection=conn)
        assert len(lb) == 30 and sum(r["review_count"] for r in lb) == 750 and sum(r["watchlist_count"] for r in lb) == 300
        joined = rv.merge(source["movies"][["movie_id", "director"]], on="movie_id")
        ref = joined.groupby("director").agg(n=("movie_id", "nunique"), avg=("rating", "mean"))
        got = analytics.director_stats(connection=conn)
        assert {r["director"] for r in got} == set(ref[ref.n >= 3].index)
        for row in got:
            assert row["average_rating"] == pytest.approx(ref.loc[row["director"], "avg"], abs=0.006)
        assert all(r["movie_count"] >= 3 and r["release_decade"] % 10 == 0 for r in analytics.genre_trends_by_decade(connection=conn))
        recs = analytics.recommend_movies("U001", connection=conn)
        seen = set(rv[rv.user_id == "U001"].movie_id) | crud.watchlist_ids("U001", connection=conn)
        assert recs and not ({r["movie_id"] for r in recs} & seen)
        assert [r["matching_genres"] for r in recs] == sorted((r["matching_genres"] for r in recs), reverse=True)
        assert len(analytics.latest_review_feed(connection=conn)) == 25
