"""Shared result cache for non-user-specific DB reads.

Each function wraps a backend method in @st.cache_data so the query
runs at most once per TTL window per engine, shared across all Streamlit
sessions on this server. User-specific data (watchlist_ids) is NOT cached
here — it must reflect watchlist toggles immediately.

The engine name is part of every cache key so switching databases never
serves stale results from the other engine.
"""
import streamlit as st

from session import engine_name, get_engine


def _db():
    return get_engine(engine_name())


@st.cache_data(ttl=300, show_spinner=False)
def well_rated(_engine_name, min_reviews):
    return get_engine(_engine_name).well_rated(min_reviews)


@st.cache_data(ttl=300, show_spinner=False)
def most_reviewed(_engine_name):
    return get_engine(_engine_name).most_reviewed()


@st.cache_data(ttl=120, show_spinner=False)
def latest_reviews(_engine_name, limit):
    return get_engine(_engine_name).latest_reviews(limit)
