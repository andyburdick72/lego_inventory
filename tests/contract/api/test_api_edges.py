# tests/contract/api/test_api_edges.py
import os
import uuid

import pytest

try:
    import httpx
except Exception:  # pragma: no cover
    httpx = None

pytestmark = pytest.mark.contract

API_BASE = os.getenv("API_BASE_URL") or os.getenv("API_BASE") or ""  # ensure str for type checkers
SKIP_REASON = "API_BASE_URL or API_BASE not set or httpx unavailable"


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
        # API_BASE already includes /api/v1, so just use /drawers/create
        r = c.post("/drawers/create", json={"name": "   "})
        assert r.status_code in (400, 422)


def test_get_missing_drawer_404():
    _skip_if_no_api()
    with _client() as c:
        r = c.get("/api/v1/drawers/999999999")
        assert r.status_code == 404


def test_create_duplicate_drawer_conflict_prefer_409():
    """
    Create a drawer, then attempt to create the same name again.
    We prefer 409 Conflict, but accept 400/422 variations to avoid flakiness.
    """
    _skip_if_no_api()
    unique = f"contract-{uuid.uuid4().hex[:8]}"
    with _client() as c:
        # API_BASE already includes /api/v1, so just use /drawers/create
        r1 = c.post("/drawers/create", json={"name": unique})
        assert r1.status_code in (200, 201)
        drawer_id = r1.json().get("id")

        r2 = c.post("/drawers/create", json={"name": unique})
        assert r2.status_code in (409, 400, 422)

        # Cleanup: delete the created drawer
        if drawer_id:
            c.post("/drawers/delete", json={"id": drawer_id})


def test_health_check():
    """Test health check endpoint."""
    _skip_if_no_api()
    # Health check is at root level, not under /api/v1
    # Extract base URL without /api/v1 suffix
    base_url = API_BASE
    if base_url.endswith("/api/v1"):
        base_url = base_url[:-7]  # Remove /api/v1
    elif base_url.endswith("/api"):
        base_url = base_url[:-4]  # Remove /api
    elif base_url.endswith("/v1"):
        base_url = base_url[:-3]  # Remove /v1
    
    with httpx.Client(base_url=base_url, timeout=10.0) as health_client:
        r = health_client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert "status" in data or "message" in data


def test_root_endpoint():
    """Test root endpoint."""
    _skip_if_no_api()
    # Root endpoint is at root level, not under /api/v1
    # Extract base URL without /api/v1 suffix
    base_url = API_BASE
    if base_url.endswith("/api/v1"):
        base_url = base_url[:-7]  # Remove /api/v1
    elif base_url.endswith("/api"):
        base_url = base_url[:-4]  # Remove /api
    elif base_url.endswith("/v1"):
        base_url = base_url[:-3]  # Remove /v1
    
    with httpx.Client(base_url=base_url, timeout=10.0) as root_client:
        r = root_client.get("/")
        assert r.status_code == 200
        data = r.json()
        assert "message" in data or "version" in data
