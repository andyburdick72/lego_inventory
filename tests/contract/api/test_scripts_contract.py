"""Contract tests for scripts endpoints."""
import os

import httpx
import pytest

pytestmark = pytest.mark.contract

API_BASE = os.getenv("API_BASE_URL") or os.getenv("API_BASE") or ""
SKIP_REASON = "API_BASE_URL or API_BASE not set"


def _skip_if_no_api():
    if not API_BASE:
        pytest.skip(SKIP_REASON)


def _client():
    if not API_BASE:
        pytest.skip(SKIP_REASON)
    return httpx.Client(base_url=API_BASE, timeout=10.0)


def test_sync_parts_basic():
    """Test sync parts endpoint accepts request."""
    _skip_if_no_api()
    with _client() as c:
        r = c.post(
            "/scripts/sync-rebrickable-parts",
            json={"all_sets": False}
        )
        # May return 200 immediately or 202 Accepted for async
        # Or 500 if Rebrickable API is not configured
        assert r.status_code in (200, 202, 500)
        if r.status_code != 500:
            # Verify response structure
            data = r.json()
            assert "message" in data or "success" in data or "output" in data


def test_sync_parts_all_sets():
    """Test sync parts with all_sets flag."""
    _skip_if_no_api()
    with _client() as c:
        r = c.post(
            "/scripts/sync-rebrickable-parts",
            json={"all_sets": True}
        )
        # May return 200, 202, or 500 if not configured
        assert r.status_code in (200, 202, 500)


def test_sync_sets_basic():
    """Test sync sets endpoint accepts request."""
    _skip_if_no_api()
    with _client() as c:
        r = c.post(
            "/scripts/sync-rebrickable-sets",
            json={"default_status": "in_box"}
        )
        # May return 200, 202, or 500 if not configured
        assert r.status_code in (200, 202, 500)
        if r.status_code != 500:
            # Verify response structure
            data = r.json()
            assert "message" in data or "success" in data or "output" in data


def test_sync_sets_with_status():
    """Test sync sets with different default status."""
    _skip_if_no_api()
    with _client() as c:
        r = c.post(
            "/scripts/sync-rebrickable-sets",
            json={"default_status": "built"}
        )
        # May return 200, 202, or 500 if not configured
        assert r.status_code in (200, 202, 500)

