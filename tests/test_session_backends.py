"""Regression test: get_engine() must return instances of the class in ENGINES[name].

Protects against stale st.cache_resource entries or frozen ENGINES references in
session.py returning CSV-fallback instances when real backend classes are selected.
"""
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "app")]


def _no_op_cache(fn=None, **_kwargs):
    """Stand-in for st.cache_resource that just returns the function unchanged."""
    if fn is not None:
        return fn
    def decorator(f):
        return f
    return decorator


def test_get_engine_matches_engines_dict():
    """get_engine(name) must return an instance of ENGINES[name] for every engine."""
    # Patch st.cache_resource before importing session so the decorator is a no-op.
    with patch("streamlit.cache_resource", side_effect=_no_op_cache):
        with patch("streamlit.cache_data", side_effect=_no_op_cache):
            # Also stub out the DataStore / get_store dependency.
            import backends as _backends_mod
            from unittest.mock import MagicMock
            fake_store = MagicMock()

            # Re-import session with patched streamlit so cache_resource is no-op.
            if "session" in sys.modules:
                del sys.modules["session"]

            import streamlit as st
            st.cache_resource = _no_op_cache  # type: ignore[attr-defined]
            st.cache_data = _no_op_cache       # type: ignore[attr-defined]

            import session
            # Replace get_store with a stub.
            session.get_store = lambda: fake_store

            for name, expected_cls in _backends_mod.ENGINES.items():
                instance = session.get_engine(name)
                assert isinstance(instance, expected_cls), (
                    f"get_engine({name!r}) returned {type(instance).__name__!r} "
                    f"but ENGINES[{name!r}] is {expected_cls.__name__!r}. "
                    "Stale cache or wrong ENGINES reference."
                )


def test_engines_contains_real_backend_classes():
    """ENGINES must map to MySQLBackend and MongoBackend when imports succeed."""
    import backends as _backends_mod
    from mysql.backend import MySQLBackend
    from mongodb.backend import MongoBackend

    assert _backends_mod.ENGINES["MySQL (Relational)"] is MySQLBackend, (
        f"Expected MySQLBackend, got {_backends_mod.ENGINES['MySQL (Relational)'].__name__}"
    )
    assert _backends_mod.ENGINES["MongoDB (Document)"] is MongoBackend, (
        f"Expected MongoBackend, got {_backends_mod.ENGINES['MongoDB (Document)'].__name__}"
    )
    assert _backends_mod._mysql_ok is True
    assert _backends_mod._mongo_ok is True
    assert _backends_mod._mysql_error is None
    assert _backends_mod._mongo_error is None
