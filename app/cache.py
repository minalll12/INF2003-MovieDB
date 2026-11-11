"""Shared result cache for non-user-specific DB reads.

Each function wraps a MySQLBackend method in @st.cache_data so the query
runs at most once per TTL window, shared across all Streamlit sessions on
this server. User-specific data (watchlist_ids) is NOT cached here — it
must reflect watchlist toggles immediately.
"""
import streamlit as st

from session import get_engine

# Always talk to MySQL — bypasses session_state so @st.cache_data works cleanly.
_ENGINE = "MySQL (Relational)"


def _db():
    return get_engine(_ENGINE)


@st.cache_data(ttl=300, show_spinner=False)
def well_rated(min_reviews):
    return _db().well_rated(min_reviews)


@st.cache_data(ttl=300, show_spinner=False)
def most_reviewed():
    return _db().most_reviewed()


@st.cache_data(ttl=120, show_spinner=False)
def latest_reviews(limit):
    return _db().latest_reviews(limit)
