"""Advanced MongoDB features: aggregation pipelines.

Each function is the MongoDB counterpart of a MySQL query:
  mysql/09_comparison_queries.sql  ops 1-5   -> movies_by_genre, average_rating, watchlist_with_genres,
                                                filtered_discovery, top_in_genre
  mysql/06_advanced_queries.sql    1-8       -> discovery_ranking, top_per_genre, genre_health,
                                                recommend_movies, engagement_leaderboard, director_stats,
                                                genre_trends_by_decade, latest_review_feed
"""
from .db import get_db


def _round(rows, *fields, nd=2):
    """Round in Python so pipelines stay portable ($round needs MongoDB 4.2+)."""
    for r in rows:
        for f in fields:
            if r.get(f) is not None:
                r[f] = round(r[f], nd)
    return rows


# ====================================================== comparison operations 1-5 (09_comparison_queries.sql)
def movies_by_genre(genre: str):
    """Op 1. MySQL: 3-table JOIN.  Mongo: one multikey-index lookup on the embedded array."""
    return list(get_db().movies.find({"genres": genre}, {"title": 1, "release_year": 1}))


def average_rating(movie_id: str):
    """Op 2. Computed LIVE from reviews (same work as MySQL AVG), not from the stored avg_rating."""
    r = next(iter(get_db().reviews.aggregate([{"$match": {"movie_id": movie_id}},
                                              {"$group": {"_id": None, "avg": {"$avg": "$rating"}, "n": {"$sum": 1}}}])), None)
    return round(r["avg"], 2) if r and r["n"] else None


def watchlist_with_genres(user_id: str):
    """Op 3. MySQL: 4-table JOIN + GROUP_CONCAT.  Mongo: one $lookup - genres already embedded."""
    return list(get_db().watchlists.aggregate([
        {"$match": {"user_id": user_id}},
        {"$lookup": {"from": "movies", "localField": "movie_id", "foreignField": "_id", "as": "m"}},
        {"$unwind": "$m"},
        {"$project": {"_id": 0, "movie_id": "$m._id", "title": "$m.title", "genres": "$m.genres"}}]))


def filtered_discovery(genre: str, year_from: int, year_to: int, limit: int = 25):
    """Op 4 using the precomputed avg_rating/review_count (computed pattern): a single indexed find."""
    return list(get_db().movies.find(
        {"genres": genre, "release_year": {"$gte": year_from, "$lte": year_to}},
        {"title": 1, "release_year": 1, "review_count": 1, "avg_rating": 1}
    ).sort([("avg_rating", -1), ("review_count", -1), ("title", 1)]).limit(limit))


def filtered_discovery_live(genre: str, year_from: int, year_to: int, limit: int = 25):
    """Op 4 WITHOUT the computed pattern: $lookup reviews and $group, i.e. what MySQL does. Benchmark both."""
    rows = get_db().movies.aggregate([
        {"$match": {"genres": genre, "release_year": {"$gte": year_from, "$lte": year_to}}},
        {"$lookup": {"from": "reviews", "localField": "_id", "foreignField": "movie_id", "as": "r"}},
        {"$project": {"title": 1, "release_year": 1, "review_count": {"$size": "$r"}, "avg_rating": {"$avg": "$r.rating"}}},
        {"$sort": {"avg_rating": -1, "review_count": -1, "title": 1}}, {"$limit": limit}])
    return _round(list(rows), "avg_rating")


def top_in_genre(genre: str, min_reviews: int = 2, limit: int = 10):
    """Op 5. MySQL: JOIN/GROUP BY/HAVING.  Mongo: filter on the precomputed fields."""
    return list(get_db().movies.find({"genres": genre, "review_count": {"$gte": min_reviews}},
                                     {"title": 1, "review_count": 1, "avg_rating": 1})
                .sort([("avg_rating", -1), ("review_count", -1), ("title", 1)]).limit(limit))


# ====================================================== advanced queries 1-8 (06_advanced_queries.sql)
def discovery_ranking(limit: int = 20):
    """Q1: rating, review volume, saves and genres in one pass ($lookup counts saves)."""
    return list(get_db().movies.aggregate([
        {"$lookup": {"from": "watchlists", "localField": "_id", "foreignField": "movie_id", "as": "w"}},
        {"$addFields": {"watchlist_count": {"$size": "$w"}}},
        {"$sort": {"avg_rating": -1, "review_count": -1, "watchlist_count": -1, "title": 1}}, {"$limit": limit},
        {"$project": {"title": 1, "release_year": 1, "genres": 1, "avg_rating": 1, "review_count": 1, "watchlist_count": 1}}]))


def top_per_genre(per_genre: int = 3, min_reviews: int = 2):
    """Q2: top N reviewed movies in every genre. MySQL uses ROW_NUMBER() OVER (PARTITION BY genre);
    Mongo uses $unwind -> $sort -> $group/$push -> $slice (works on any MongoDB version)."""
    groups = get_db().movies.aggregate([
        {"$match": {"review_count": {"$gte": min_reviews}}}, {"$unwind": "$genres"},
        {"$sort": {"avg_rating": -1, "review_count": -1, "title": 1}},
        {"$group": {"_id": "$genres", "movies": {"$push": {"movie_id": "$_id", "title": "$title",
                                                           "avg_rating": "$avg_rating", "review_count": "$review_count"}}}},
        {"$project": {"top": {"$slice": ["$movies", per_genre]}}}, {"$sort": {"_id": 1}}])
    return _round([{"genre": g["_id"], "genre_rank": i, **m} for g in groups for i, m in enumerate(g["top"], 1)], "avg_rating")


def genre_health():
    """Q3: movies, reviews, saves and review-weighted rating per genre."""
    rows = get_db().movies.aggregate([
        {"$lookup": {"from": "watchlists", "localField": "_id", "foreignField": "movie_id", "as": "w"}},
        {"$unwind": "$genres"},
        {"$group": {"_id": "$genres", "movie_count": {"$sum": 1}, "review_count": {"$sum": "$review_count"},
                    "watchlist_count": {"$sum": {"$size": "$w"}},
                    "weighted": {"$sum": {"$multiply": [{"$ifNull": ["$avg_rating", 0]}, "$review_count"]}}}},
        {"$project": {"_id": 0, "genre": "$_id", "movie_count": 1, "review_count": 1, "watchlist_count": 1,
                      "average_rating": {"$cond": [{"$gt": ["$review_count", 0]}, {"$divide": ["$weighted", "$review_count"]}, None]}}},
        {"$sort": {"watchlist_count": -1, "review_count": -1, "genre": 1}}])
    return _round(list(rows), "average_rating")


def recommend_movies(user_id: str, liked_threshold: float = 7.0, limit: int = 20):
    """Q4: unseen movies in genres the user rated >= 7 or watchlisted, ranked by matching genres."""
    db = get_db()
    liked = db.reviews.distinct("movie_id", {"user_id": user_id, "rating": {"$gte": liked_threshold}})
    saved = db.watchlists.distinct("movie_id", {"user_id": user_id})
    preferred = sorted(set(db.movies.distinct("genres", {"_id": {"$in": liked + saved}})))
    if not preferred:
        return []
    seen = set(db.reviews.distinct("movie_id", {"user_id": user_id})) | set(saved)
    rows = db.movies.aggregate([
        {"$match": {"genres": {"$in": preferred}, "_id": {"$nin": sorted(seen)}}},
        {"$addFields": {"matching_genres": {"$size": {"$filter": {"input": "$genres", "as": "g", "cond": {"$in": ["$$g", preferred]}}}}}},
        {"$sort": {"matching_genres": -1, "avg_rating": -1, "review_count": -1}}, {"$limit": limit},
        {"$project": {"title": 1, "release_year": 1, "matching_genres": 1, "avg_rating": 1, "review_count": 1}}])
    return list(rows)


def engagement_leaderboard(limit: int = 0):
    """Q5: per-user reviews + saves, without a review x watchlist cross product ($lookup each separately)."""
    pipe = [
        {"$lookup": {"from": "reviews", "localField": "_id", "foreignField": "user_id", "as": "r"}},
        {"$lookup": {"from": "watchlists", "localField": "_id", "foreignField": "user_id", "as": "w"}},
        {"$project": {"username": 1, "review_count": {"$size": "$r"}, "watchlist_count": {"$size": "$w"},
                      "average_rating_given": {"$avg": "$r.rating"}, "last_review_at": {"$max": "$r.updated_at"},
                      "last_saved_at": {"$max": "$w.added_at"},
                      "total_actions": {"$add": [{"$size": "$r"}, {"$size": "$w"}]}}},
        {"$sort": {"total_actions": -1, "username": 1}}]
    if limit:
        pipe.append({"$limit": limit})
    return _round(list(get_db().users.aggregate(pipe)), "average_rating_given")


def director_stats(min_movies: int = 3):
    """Q6: directors with >= N reviewed films and their review-weighted rating."""
    rows = get_db().movies.aggregate([
        {"$match": {"review_count": {"$gt": 0}, "director": {"$nin": [None, ""]}}},
        {"$group": {"_id": "$director", "reviewed_movie_count": {"$sum": 1}, "review_count": {"$sum": "$review_count"},
                    "weighted": {"$sum": {"$multiply": ["$avg_rating", "$review_count"]}}}},
        {"$match": {"reviewed_movie_count": {"$gte": min_movies}}},
        {"$project": {"_id": 0, "director": "$_id", "reviewed_movie_count": 1, "review_count": 1,
                      "average_rating": {"$divide": ["$weighted", "$review_count"]}}},
        {"$sort": {"average_rating": -1, "review_count": -1, "director": 1}}])
    return _round(list(rows), "average_rating")


def genre_trends_by_decade(min_movies: int = 3):
    """Q7: movies/reviews/rating per (decade, genre)."""
    rows = get_db().movies.aggregate([
        {"$unwind": "$genres"},
        {"$group": {"_id": {"decade": {"$multiply": [{"$floor": {"$divide": ["$release_year", 10]}}, 10]}, "genre": "$genres"},
                    "movie_count": {"$sum": 1}, "review_count": {"$sum": "$review_count"},
                    "weighted": {"$sum": {"$multiply": [{"$ifNull": ["$avg_rating", 0]}, "$review_count"]}}}},
        {"$match": {"movie_count": {"$gte": min_movies}}},
        {"$project": {"_id": 0, "release_decade": "$_id.decade", "genre": "$_id.genre", "movie_count": 1, "review_count": 1,
                      "average_rating": {"$cond": [{"$gt": ["$review_count", 0]}, {"$divide": ["$weighted", "$review_count"]}, None]}}},
        {"$sort": {"release_decade": -1, "movie_count": -1, "genre": 1}}])
    return _round(list(rows), "average_rating")


def latest_review_feed(limit: int = 25):
    """Q8: newest reviews with user (denormalised - no join) and movie context (one $lookup)."""
    return list(get_db().reviews.aggregate([
        {"$sort": {"created_at": -1}}, {"$limit": limit},
        {"$lookup": {"from": "movies", "localField": "movie_id", "foreignField": "_id", "as": "m"}}, {"$unwind": "$m"},
        {"$project": {"rating": 1, "review_text": 1, "created_at": 1, "updated_at": 1, "user_id": 1, "username": 1,
                      "movie_id": 1, "title": "$m.title", "release_year": "$m.release_year"}}]))
