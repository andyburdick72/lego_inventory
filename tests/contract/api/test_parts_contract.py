"""Contract tests for parts endpoints."""
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


@pytest.mark.parametrize("design_id", ["3001", "3023"])  # Common parts that should exist
def test_get_part_by_id(design_id):
    """Test getting part by design_id."""
    _skip_if_no_api()
    with _client() as c:
        r = c.get(f"/parts/{design_id}")
        assert r.status_code == 200
        data = r.json()
        assert data["design_id"] == design_id
        assert "name" in data
        assert isinstance(data["name"], str)


def test_get_part_404():
    """Test 404 for invalid part."""
    _skip_if_no_api()
    with _client() as c:
        r = c.get("/parts/invalid-part-id-99999")
        assert r.status_code == 404


@pytest.mark.parametrize("design_id", ["3001", "3023"])
def test_get_part_loose_inventory(design_id):
    """Test getting loose inventory for a part."""
    _skip_if_no_api()
    with _client() as c:
        r = c.get(f"/parts/{design_id}/loose")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        # Verify all items are for the correct part
        for item in data:
            assert item["part_id"] == design_id
            # Status can be 'loose' or 'loose_parts' depending on data
            assert item["status"] in ("loose", "loose_parts")
            assert "color_id" in item
            assert "quantity" in item
            assert isinstance(item["quantity"], int)


@pytest.mark.parametrize("design_id", ["3001", "3023"])
def test_get_part_sets(design_id):
    """Test getting sets containing a part."""
    _skip_if_no_api()
    with _client() as c:
        r = c.get(f"/parts/{design_id}/sets")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        # Verify all items reference the part
        for item in data:
            assert "set_number" in item
            assert "set_name" in item
            assert "color_id" in item
            assert "quantity" in item
            assert isinstance(item["quantity"], int)
            assert item["quantity"] > 0


def test_get_part_sets_404():
    """Test that invalid part returns empty list (not 404)."""
    _skip_if_no_api()
    with _client() as c:
        r = c.get("/parts/invalid-part-id-99999/sets")
        # API returns empty list for parts not in any sets, not 404
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) == 0

