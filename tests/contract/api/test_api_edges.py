# tests/contract/api/test_api_edges.py
import os
import uuid

import pytest

try:
    import httpx
except Exception:  # pragma: no cover
    httpx = None

pytestmark = pytest.mark.contract

API_BASE = os.getenv("API_BASE") or ""  # ensure str for type checkers
SKIP_REASON = "API_BASE not set or httpx unavailable"


def _skip_if_no_api():
    if httpx is None or not API_BASE:
        pytest.skip(SKIP_REASON)


def _client():
    if httpx is None or not API_BASE:
        pytest.skip(SKIP_REASON)
    return httpx.Client(base_url=API_BASE, timeout=10.0)


def test_create_drawer_blank_name_400():
    _skip_if_no_api()
    with _client() as c:
        r = c.post("/api/drawers", json={"name": "   "})
        assert r.status_code in (400, 422)


def test_get_missing_drawer_404():
    _skip_if_no_api()
    with _client() as c:
        r = c.get("/api/drawers/999999999")
        assert r.status_code == 404


def test_create_duplicate_drawer_conflict_prefer_409():
    """
    Create a drawer, then attempt to create the same name again.
    We prefer 409 Conflict, but accept 400/422 variations to avoid flakiness.
    """
    _skip_if_no_api()
    unique = f"contract-{uuid.uuid4().hex[:8]}"
    with _client() as c:
        r1 = c.post("/api/drawers", json={"name": unique})
        assert r1.status_code in (200, 201)

        r2 = c.post("/api/drawers", json={"name": unique})
        assert r2.status_code in (409, 400, 422)
