"""Print query plans (IXSCAN vs COLLSCAN) - evidence for the efficiency section. Needs a real MongoDB.

    python explain_demo.py
"""
from .db import get_db


def plan(db, coll, flt, sort=None):
    cur = db[coll].find(flt)
    if sort:
        cur = cur.sort(sort)
    node, stages = cur.explain()["queryPlanner"]["winningPlan"], []
    while node:
        stages.append(node["stage"] + (f"({node['indexName']})" if "indexName" in node else ""))
        node = node.get("inputStage")
    return " -> ".join(stages)


if __name__ == "__main__":
    db = get_db()
    print("movies by genre     :", plan(db, "movies", {"genres": "Drama"}))
    print("year range + title  :", plan(db, "movies", {"release_year": {"$gte": 1990, "$lte": 1999}}, [("release_year", 1), ("title", 1)]))
    print("reviews of a movie  :", plan(db, "reviews", {"movie_id": "M0001"}))
    print("latest review feed  :", plan(db, "reviews", {}, [("created_at", -1)]))
    print("user's watchlist    :", plan(db, "watchlists", {"user_id": "U001"}, [("added_at", -1)]))
    print("no index (cast)     :", plan(db, "movies", {"cast": "Tom Hanks"}))
