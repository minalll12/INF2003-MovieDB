"""Database-side adapter matching app/backends.py. Minal registers this class in ENGINES.

No Streamlit imports, frontend writes, application session logic or result cache.
"""
import pandas as pd

from . import analytics, crud, db

MOVIE_COLUMNS = ["movie_id", "poster_url", "title", "release_year", "certificate", "duration", "description",
                 "director", "cast", "imdb_votes", "genres", "avg_rating", "review_count", "poster_large"]
REVIEW_COLUMNS = ["review_id", "user_id", "movie_id", "rating", "review_text", "created_at", "updated_at",
                  "username", "title", "release_year"]
SORTS = {
    "Highest rated": (["avg_rating", "review_count", "imdb_votes"], [False, False, False]),
    "Most reviewed": (["review_count", "avg_rating"], [False, False]),
    "Newest": (["release_year", "title"], [False, True]),
    "Oldest": (["release_year", "title"], [True, True]),
    "Title A–Z": (["title"], [True]),
}


def movie_frame(rows, extra=()):
    frame = pd.DataFrame(rows, columns=[*extra, *MOVIE_COLUMNS])
    frame["avg_rating"] = pd.to_numeric(frame["avg_rating"]).astype(float).round(1)
    frame["review_count"] = pd.to_numeric(frame["review_count"]).astype(int)
    return frame


class MySQLBackend:
    label = "MySQL (Relational)"

    def __init__(self, store=None):
        # Existing get_engine(name) passes a CSV store. MySQL ignores it.
        pass

    def catalogue(self):
        return movie_frame(crud.search_movies())

    def search_movies(self, title="", genres=(), years=None, ratings=None, sort_by=None):
        frame = movie_frame(crud.search_movies(title, genres, years, ratings, sort_by))
        columns, ascending = SORTS[sort_by or "Highest rated"]
        return frame.sort_values(columns, ascending=ascending, na_position="last").reset_index(drop=True)

    def get_movie(self, movie_id):
        row = crud.get_movie_details(movie_id)
        return None if row is None else movie_frame([row]).iloc[0].to_dict()

    get_movie_details = get_movie

    def genre_names(self):
        return crud.genre_names()

    def year_bounds(self):
        return crud.year_bounds()

    def top_rated(self):
        return self.search_movies()

    def well_rated(self, min_reviews):
        crud.integer(min_reviews, "min_reviews")
        rows = crud.movie_rows(db.fetch(crud.MOVIE_SELECT + " WHERE COALESCE(rs.review_count, 0) >= %s", (min_reviews,)))
        return movie_frame(rows).sort_values(["avg_rating", "review_count"], ascending=False)

    def most_reviewed(self):
        return self.search_movies(sort_by="Most reviewed")

    def most_voted(self, limit):
        rows = crud.movie_rows(db.fetch(crud.MOVIE_SELECT + " ORDER BY m.imdb_votes DESC, m.movie_id LIMIT %s",
                                       (crud.integer(limit, "limit"),)))
        return movie_frame(rows)

    def movie_reviews(self, movie_id):
        return pd.DataFrame(crud.movie_reviews(movie_id), columns=REVIEW_COLUMNS)

    def user_reviews(self, user_id):
        return pd.DataFrame(crud.user_reviews(user_id), columns=REVIEW_COLUMNS)

    def user_review_for(self, user_id, movie_id):
        return crud.user_review_for(user_id, movie_id)

    def latest_reviews(self, limit):
        reviews = pd.DataFrame(analytics.latest_review_feed(limit), columns=REVIEW_COLUMNS)
        return reviews.merge(self.catalogue()[["movie_id", "poster_large", "genres"]], on="movie_id", how="left")

    def reviewed_movies(self, user_id):
        rows = crud.movie_rows(db.fetch(crud.MOVIE_SELECT.replace("SELECT m.movie_id", "SELECT r.rating AS rating_mine, m.movie_id", 1) +
            " JOIN reviews r ON r.movie_id = m.movie_id WHERE r.user_id = %s ORDER BY r.rating DESC, m.movie_id",
            (crud.string(user_id, "user_id", 10),)))
        return movie_frame(rows, ("rating_mine",))

    def user_watchlist(self, user_id):
        return movie_frame(crud.get_watchlist(user_id), ("added_at",))

    get_watchlist = user_watchlist

    def watchlist_ids(self, user_id):
        return crud.watchlist_ids(user_id)

    def list_users(self):
        return pd.DataFrame(crud.list_users(), columns=["user_id", "username", "email"])

    def get_user(self, user_id):
        row = crud.get_user(user_id)
        return None if row is None else {k: row[k] for k in ("user_id", "username", "email")}

    def member_since(self, user_id):
        row = crud.get_user(user_id)
        return None if row is None else row["created_at"]

    # Static forwarding methods preserve the database functions' signatures and return values.
    add_review = staticmethod(crud.add_review)
    update_review = staticmethod(crud.update_review)
    delete_review = staticmethod(crud.delete_review)
    add_to_watchlist = staticmethod(crud.add_to_watchlist)
    remove_from_watchlist = staticmethod(crud.remove_from_watchlist)
    authenticate = staticmethod(crud.authenticate)
    username_taken = staticmethod(crud.username_taken)
    email_taken = staticmethod(crud.email_taken)
    register_user = staticmethod(crud.register_user)
    update_user = staticmethod(crud.update_user)
    delete_user = staticmethod(crud.delete_user)
    movies_by_genre = staticmethod(analytics.movies_by_genre)
    average_rating = staticmethod(analytics.average_rating)
    watchlist_with_genres = staticmethod(analytics.watchlist_with_genres)
