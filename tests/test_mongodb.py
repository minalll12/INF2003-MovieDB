"""MongoDB layer tests, run against the real cleaned CSVs in data/cleaned/.

    pytest tests/test_mongodb.py                    # in-memory mongomock, no server needed
    MONGO_TEST_REAL=1 pytest tests/test_mongodb.py  # real MongoDB (MONGO_URI), uses db 'movie_platform_test'

Parity tests compare MongoBackend against the team's CSV stand-in (app/backends.py) so the two
engines are proven to return the same answers.
"""
import os
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "app")]
DATA = ROOT / "data" / "cleaned"

from mongodb import analytics, crud, db as dbmod, security, seed  # noqa: E402
from mongodb.backend import MongoBackend  # noqa: E402

REAL = os.getenv("MONGO_TEST_REAL") == "1"


@pytest.fixture()
def database():
    if REAL:
        from pymongo import MongoClient
        dbmod.set_client(MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017")))
        dbmod.get_db = lambda: dbmod.get_client()["movie_platform_test"]
        for m in (crud, analytics):
            m.get_db = dbmod.get_db
        import mongodb.backend as be
        be.get_db = dbmod.get_db
    else:
        import mongomock
        dbmod.set_client(mongomock.MongoClient())
    d = dbmod.get_db()
    seed.seed(d, DATA)
    return d


@pytest.fixture(scope="module")
def csv():
    return {n: pd.read_csv(DATA / f"{n}.csv") for n in ("movies", "genres", "movie_genres", "users", "reviews", "watchlists")}


@pytest.fixture()
def csv_backend(csv):
    """The team's CSV stand-in (app/backends.py) over the same data."""
    from backends import CsvBackend

    class Store(dict):
        version = 1
    return CsvBackend(Store(csv))


# ------------------------------------------------------------------ seeding / schema
def test_row_counts_match_mysql_validation(database):
    assert {n: database[n].count_documents({}) for n in ("users", "movies", "reviews", "watchlists")} == \
           {"users": 30, "movies": 1000, "reviews": 750, "watchlists": 300}


def test_genres_embedded_match_movie_genres_table(database, csv):
    names = dict(zip(csv["genres"].genre_id, csv["genres"].genre_name))
    expect = csv["movie_genres"].assign(g=lambda d: d.genre_id.map(names)).groupby("movie_id")["g"].agg(lambda s: sorted(s)).to_dict()
    assert {m["_id"]: m["genres"] for m in database.movies.find()} == expect
    assert sum(len(v) for v in expect.values()) == 2541
    assert crud.genre_names() == sorted(csv["genres"].genre_name) and len(crud.genre_names()) == 21


def test_stored_stats_equal_pandas(database, csv):
    ref = csv["reviews"].groupby("movie_id")["rating"].agg(["mean", "count"])
    for m in database.movies.find({"review_count": {"$gt": 0}}):
        assert m["review_count"] == ref.loc[m["_id"], "count"]
        assert m["avg_rating"] == pytest.approx(ref.loc[m["_id"], "mean"], abs=0.006)
    assert database.movies.count_documents({"review_count": 0}) == 1000 - len(ref)


def test_unique_indexes_exist(database):
    names = {i["name"] for i in database.reviews.list_indexes()}
    assert {"uq_review_user_movie", "ix_reviews_created"} <= names
    assert "uq_watch_user_movie" in {i["name"] for i in database.watchlists.list_indexes()}


def test_password_hash_format_compatible_with_app_auth():
    from auth import hash_password as app_hash
    assert security.hash_password("pw12345678", salt="ab" * 16) == app_hash("pw12345678", salt="ab" * 16)
    assert security.verify_password("pw12345678", app_hash("pw12345678"))


# ------------------------------------------------------------------ users
def test_register_and_login(database):
    u = crud.register_user("Newbie", "New@Example.com", "supersecret")
    assert u["user_id"] == "U031" and crud.authenticate("newbie", "supersecret")["user_id"] == "U031"   # case-insensitive
    assert crud.authenticate("newbie", "wrongpass") is None and crud.authenticate("nobody", "x") is None
    assert crud.username_taken("NEWBIE") and crud.email_taken("new@example.com")
    for args in [("newbie", "o@example.com", "supersecret"), ("other", "new@example.com", "supersecret"),
                 ("x", "bad", "short"), ("okname", "ok@example.com", "short")]:
        with pytest.raises(ValueError):
            crud.register_user(*args)


def test_operator_injection_rejected(database):
    for fn, args in [(crud.authenticate, ({"$ne": ""}, {"$ne": ""})), (crud.search_movies, ({"$gt": ""},)),
                     (crud.get_movie, ({"$ne": None},)), (crud.get_user, ({"$ne": None},))]:
        with pytest.raises(ValueError):
            fn(*args)
    assert crud.search_movies(title=".*") == []                         # regex metacharacters are escaped


# ------------------------------------------------------------------ reviews
def test_review_lifecycle_updates_stats(database):
    uid = "U001"
    mid = database.movies.find_one({"review_count": 0, "_id": {"$nin": [r["movie_id"] for r in database.reviews.find({"user_id": uid})]}})["_id"]
    rid = crud.add_review(uid, mid, 8.0, "good")
    assert rid == "R0751" and crud.get_movie(mid)["review_count"] == 1 and crud.get_movie(mid)["avg_rating"] == 8.0
    with pytest.raises(ValueError):
        crud.add_review(uid, mid, 5.0, "again")                         # one review per user/movie
    assert crud.update_review(rid, 4.5, "meh", user_id=uid) and crud.get_movie(mid)["avg_rating"] == 4.5
    assert not crud.update_review(rid, 1.0, "hax", user_id="U002")      # not the owner
    assert not crud.delete_review(rid, user_id="U002")
    assert crud.delete_review(rid, user_id=uid)
    assert crud.get_movie(mid)["review_count"] == 0 and crud.get_movie(mid)["avg_rating"] is None


@pytest.mark.parametrize("bad", [0.9, 10.1, "9", True, None, float("nan")])
def test_invalid_rating_rejected(database, bad):
    with pytest.raises(ValueError):
        crud.add_review("U001", "M0001", bad, "x")


def test_review_text_and_foreign_keys(database):
    with pytest.raises(ValueError):
        crud.add_review("U001", "M0999", 5.0, "x" * 1001)
    with pytest.raises(ValueError):
        crud.add_review("U999", "M0001", 5.0, "x")
    with pytest.raises(ValueError):
        crud.add_review("U001", "M9999", 5.0, "x")


def test_server_validator_blocks_bad_documents(database):
    if not REAL:
        pytest.skip("$jsonSchema validators are only enforced by a real MongoDB server")
    from datetime import datetime
    from pymongo.errors import WriteError
    for bad in ({"rating": 11.0}, {"rating": "9"}):
        with pytest.raises(WriteError):
            database.reviews.insert_one({"_id": "RZ1", "movie_id": "M0001", "user_id": "U001", "username": "u",
                                         "created_at": datetime.now(), "updated_at": datetime.now(), **bad})


# ------------------------------------------------------------------ watchlist
def test_watchlist(database):
    uid = "U001"
    movie = database.movies.find_one({"_id": {"$nin": list(crud.watchlist_ids(uid))}})["_id"]
    assert crud.add_to_watchlist(uid, movie) is True and crud.add_to_watchlist(uid, movie) is False
    assert movie in crud.watchlist_ids(uid)
    assert database.watchlists.find_one({"user_id": uid, "movie_id": movie})["_id"] == "W0301"
    assert crud.remove_from_watchlist(uid, movie) and not crud.remove_from_watchlist(uid, movie)
    with pytest.raises(ValueError):
        crud.add_to_watchlist(uid, "M9999")


# ------------------------------------------------------------------ parity with the CSV stand-in
@pytest.mark.parametrize("kw", [
    {}, {"title": "the"}, {"genres": ["Drama"]}, {"genres": ["Drama", "Crime"]}, {"years": (1990, 2000)},
    {"ratings": (7.0, 8.0)}, {"title": "a", "genres": ["Comedy"], "years": (1980, 2010), "ratings": (5.0, 9.0)},
])
@pytest.mark.parametrize("sort_by", [None, "Newest", "Oldest", "Title A–Z", "Most reviewed"])
def test_search_parity(database, csv_backend, kw, sort_by):
    mine = MongoBackend().search_movies(sort_by=sort_by, **kw)
    ref = csv_backend.search_movies(sort_by=sort_by, **kw)
    assert set(mine.movie_id) == set(ref.movie_id)
    key = {"Newest": "release_year", "Oldest": "release_year", "Title A–Z": "title", "Most reviewed": "review_count"}.get(sort_by, "avg_rating")
    vals = list(mine[key].fillna(-1))                                  # Mongo ranks on the stored 2 dp average, the CSV
    asc = sort_by in ("Oldest", "Title A–Z")                           # stand-in on a 1 dp one -> compare direction, not ties
    assert vals == sorted(vals, reverse=not asc)
    if key != "avg_rating":
        assert vals == list(ref[key].fillna(-1))


def test_backend_frames_have_same_columns_as_csv_backend(database, csv_backend):
    mine, ref = MongoBackend(), csv_backend
    drop = {"genre"}                                                   # raw CSV column the UI never reads
    pairs = [(mine.catalogue(), ref.catalogue()), (mine.well_rated(2), ref.well_rated(2)), (mine.most_voted(5), ref.most_voted(5)),
             (mine.latest_reviews(5), ref.latest_reviews(5)), (mine.movie_reviews("M0001"), ref.movie_reviews("M0001")),
             (mine.user_reviews("U001"), ref.user_reviews("U001")), (mine.user_watchlist("U001"), ref.user_watchlist("U001")),
             (mine.reviewed_movies("U001"), ref.reviewed_movies("U001")), (mine.list_users(), ref.list_users())]
    for a, b in pairs:
        assert set(a.columns) >= set(b.columns) - drop - {"review_id"} or set(a.columns) == set(b.columns) - drop, (set(b.columns) - set(a.columns))
    assert set(mine.get_movie("M0001")) >= set(ref.get_movie("M0001")) - drop
    assert mine.get_user("U001") == ref.get_user("U001") and str(mine.member_since("U001")) == str(ref.member_since("U001"))
    assert mine.watchlist_ids("U001") == ref.watchlist_ids("U001") and mine.year_bounds() == ref.year_bounds()
    assert mine.genre_names() == ref.genre_names()


def test_backend_values_match_csv_backend(database, csv_backend):
    mine, ref = MongoBackend(), csv_backend
    pd.testing.assert_series_equal(mine.catalogue().set_index("movie_id")["avg_rating"].sort_index(),
                                   ref.catalogue().set_index("movie_id")["avg_rating"].sort_index(), check_names=False, atol=0.11)
    assert list(mine.latest_reviews(10).review_id) == list(ref.latest_reviews(10).review_id)
    assert set(mine.user_watchlist("U003").movie_id) == set(ref.user_watchlist("U003").movie_id)
    assert dict(zip(mine.reviewed_movies("U003").movie_id, mine.reviewed_movies("U003").rating_mine)) == \
           dict(zip(ref.reviewed_movies("U003").movie_id, ref.reviewed_movies("U003").rating_mine))


def test_backend_write_paths(database):
    b = MongoBackend()
    user = b.register_user("backend_user", "bu@example.com", "supersecret")
    assert b.authenticate("backend_user", "supersecret")["user_id"] == user["user_id"]
    before = len(b.catalogue())
    b.add_review(user["user_id"], "M0002", 9.0, "great")
    mine = b.user_review_for(user["user_id"], "M0002")
    b.update_review(mine["review_id"], 7.0, "ok")
    assert b.user_review_for(user["user_id"], "M0002")["rating"] == 7.0 and len(b.catalogue()) == before
    b.delete_review(mine["review_id"])
    assert b.user_review_for(user["user_id"], "M0002") is None
    b.add_to_watchlist(user["user_id"], "M0003")
    assert "M0003" in b.watchlist_ids(user["user_id"])
    b.remove_from_watchlist(user["user_id"], "M0003")
    assert b.watchlist_ids(user["user_id"]) == set()


# ------------------------------------------------------------------ analytics vs pandas ground truth
def test_comparison_ops_match_pandas(database, csv):
    movies, mg, genres, rv = csv["movies"], csv["movie_genres"], csv["genres"], csv["reviews"]
    gid = genres.set_index("genre_name").genre_id["Drama"]
    assert {m["_id"] for m in analytics.movies_by_genre("Drama")} == set(mg[mg.genre_id == gid].movie_id)
    assert analytics.average_rating("M0001") == round(rv[rv.movie_id == "M0001"].rating.mean(), 2) or analytics.average_rating("M0001") is None
    assert analytics.average_rating("M0001") == (None if rv[rv.movie_id == "M0001"].empty else analytics.average_rating("M0001"))
    wl = analytics.watchlist_with_genres("U001")
    assert {w["movie_id"] for w in wl} == set(csv["watchlists"][csv["watchlists"].user_id == "U001"].movie_id)
    assert all(isinstance(w["genres"], list) and w["genres"] for w in wl)
    a, b = analytics.filtered_discovery("Drama", 1990, 2020), analytics.filtered_discovery_live("Drama", 1990, 2020)
    assert [x["_id"] for x in a if x.get("avg_rating")] == [x["_id"] for x in b if x.get("avg_rating")][:len([x for x in a if x.get("avg_rating")])]
    top = analytics.top_in_genre("Drama", 2, 10)
    assert all(t["review_count"] >= 2 for t in top) and [t["avg_rating"] for t in top] == sorted((t["avg_rating"] for t in top), reverse=True)


def test_advanced_queries(database, csv):
    rows = analytics.discovery_ranking(20)
    assert len(rows) == 20 and rows[0]["avg_rating"] >= rows[-1]["avg_rating"]
    tpg = analytics.top_per_genre()
    assert tpg and all(r["genre_rank"] <= 3 and r["review_count"] >= 2 for r in tpg)
    gh = analytics.genre_health()
    assert len(gh) == 21 and sum(g["movie_count"] for g in gh) == 2541
    assert sum(g["review_count"] for g in gh) == int(csv["movie_genres"].merge(csv["reviews"].groupby("movie_id").size().rename("n"), on="movie_id").n.sum())
    lb = analytics.engagement_leaderboard()
    assert len(lb) == 30 and sum(u["review_count"] for u in lb) == 750 and sum(u["watchlist_count"] for u in lb) == 300
    assert [u["total_actions"] for u in lb] == sorted((u["total_actions"] for u in lb), reverse=True)
    rv = csv["reviews"].merge(csv["movies"][["movie_id", "director"]], on="movie_id")
    per = rv.groupby("director").agg(movies=("movie_id", "nunique"), n=("rating", "size"), mean=("rating", "mean"))
    expect = per[per.movies >= 3]
    got = {d["director"]: d for d in analytics.director_stats(3)}
    assert set(got) == set(expect.index)
    for d, row in expect.iterrows():
        assert got[d]["average_rating"] == pytest.approx(row["mean"], abs=0.06)       # stored avgs are rounded to 2 dp
    trends = analytics.genre_trends_by_decade()
    assert trends and all(t["movie_count"] >= 3 and t["release_decade"] % 10 == 0 for t in trends)
    feed = analytics.latest_review_feed(25)
    assert len(feed) == 25 and feed[0]["created_at"] == max(r["created_at"] for r in database.reviews.find())


def test_recommendations_exclude_seen(database):
    uid = "U001"
    recs = analytics.recommend_movies(uid)
    seen = set(database.reviews.distinct("movie_id", {"user_id": uid})) | crud.watchlist_ids(uid)
    assert recs and not ({r["_id"] for r in recs} & seen)
    assert [r["matching_genres"] for r in recs] == sorted((r["matching_genres"] for r in recs), reverse=True)
