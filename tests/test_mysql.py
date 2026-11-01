"""MySQL callable-contract tests plus opt-in tests on a disposable real database.

python -m pytest tests/test_mysql.py -q
MYSQL_TEST_REAL=1 python -m pytest tests/test_mysql.py -q

Real tests CREATE a unique movie_platform_test_<random> database, seed the six
CSVs, test the shipped SQL, and DROP only that database in teardown.
"""
import os
import re
import sys
import uuid
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pymysql
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from mysql import analytics, crud, db, security  # noqa: E402
from mysql.backend import MOVIE_COLUMNS, REVIEW_COLUMNS, MySQLBackend, movie_frame  # noqa: E402

REAL = pytest.mark.skipif(os.getenv("MYSQL_TEST_REAL") != "1", reason="set MYSQL_TEST_REAL=1 for an isolated real MySQL database")


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
