"""One-off migration: recompute avg_rating and review_count on all movie documents.

The seed script inserted reviews directly into the reviews collection without going
through crud.add_review(), so refresh_movie_stats() was never called. This script
reproduces exactly what refresh_movie_stats() would have done for every movie.

Safe to run repeatedly: uses $set only, never deletes or recreates documents.

Usage (from repo root):
    python mongodb/migrate_refresh_stats.py
"""
import sys
from pathlib import Path

# Allow importing project modules from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from pymongo import UpdateOne
from mongodb.db import get_db


def main():
    db = get_db()

    # ------------------------------------------------------------------ before
    total_movies = db.movies.count_documents({})
    before_nonzero = db.movies.count_documents({"review_count": {"$gt": 0}})
    before_zero    = total_movies - before_nonzero
    total_reviews  = db.reviews.count_documents({})

    print("=== BEFORE ===")
    print(f"  Total movie documents  : {total_movies}")
    print(f"  Total review documents : {total_reviews}")
    print(f"  Movies with review_count  > 0 : {before_nonzero}")
    print(f"  Movies with review_count == 0 : {before_zero}")
    print()

    # ------------------------------------------------------------------ compute
    # Single aggregation over the entire reviews collection, grouped by movie_id.
    # Equivalent to calling refresh_movie_stats() for every distinct movie_id,
    # but in one round-trip instead of one per movie.
    pipeline = [
        {"$group": {
            "_id": "$movie_id",
            "avg_rating":   {"$avg": "$rating"},
            "review_count": {"$sum": 1}
        }}
    ]
    stats_by_movie = {doc["_id"]: doc for doc in db.reviews.aggregate(pipeline)}
    print(f"  Distinct movie_ids found in reviews: {len(stats_by_movie)}")
    print()

    # ------------------------------------------------------------------ build bulk ops
    # UpdateOne with $set for every movie that has reviews.
    # Movies with no reviews keep their existing review_count=0 / avg_rating=None — no op needed.
    ops = [
        UpdateOne(
            {"_id": movie_id},
            {"$set": {
                "avg_rating":   round(s["avg_rating"], 2),
                "review_count": int(s["review_count"]),
            }}
        )
        for movie_id, s in stats_by_movie.items()
    ]

    print(f"  Bulk write operations prepared: {len(ops)}")
    print()

    # ------------------------------------------------------------------ execute
    result = db.movies.bulk_write(ops, ordered=False)
    print(f"  Matched  : {result.matched_count}")
    print(f"  Modified : {result.modified_count}  (0 = already up to date, safe on re-run)")
    unmatched = len(ops) - result.matched_count
    if unmatched:
        print(f"  WARNING  : {unmatched} movie_id(s) in reviews had no matching movie document")
    print()

    # ------------------------------------------------------------------ after
    after_nonzero = db.movies.count_documents({"review_count": {"$gt": 0}})
    after_zero    = total_movies - after_nonzero

    print("=== AFTER ===")
    print(f"  Movies with review_count  > 0 : {after_nonzero}")
    print(f"  Movies with review_count == 0 : {after_zero}")
    print()

    # ------------------------------------------------------------------ spot-check
    print("=== SPOT CHECK (3 movies with reviews) ===")
    sample_ids = list(stats_by_movie.keys())[:3]
    for mid in sample_ids:
        doc = db.movies.find_one({"_id": mid}, {"title": 1, "avg_rating": 1, "review_count": 1})
        expected = stats_by_movie[mid]
        ok = (
            doc["review_count"] == int(expected["review_count"])
            and abs((doc["avg_rating"] or 0) - round(expected["avg_rating"], 2)) < 0.01
        )
        print(f"  {mid} '{doc['title']}': "
              f"review_count={doc['review_count']}, avg_rating={doc['avg_rating']}  "
              f"{'OK' if ok else 'MISMATCH'}")
    print()
    print("Migration complete.")


if __name__ == "__main__":
    main()
