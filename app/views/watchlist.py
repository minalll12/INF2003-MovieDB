from components import empty_state, html, page_title, paged_grid
from session import backend, current_user, open_browse


def render():
    page_title("Watchlist")
    movies = backend().user_watchlist(current_user()["user_id"])
    if movies.empty:
        html('<div class="double-rule"></div>')
        empty_state(
            "Nothing saved yet. Keep the films you mean to get to here.",
            "BROWSE FILMS →", open_browse, key="watchlist_empty",
        )
        return
    html(f'<div class="label">{len(movies)} FILM{"S" if len(movies) != 1 else ""} SAVED</div>')
    html('<div class="double-rule" style="margin-bottom:32px"></div>')
    paged_grid(movies, "watchlist_page")
