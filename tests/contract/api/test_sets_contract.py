"""Contract tests for sets endpoints."""
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


def test_sets_count():
    """Test sets count endpoint."""
    _skip_if_no_api()
    with _client() as c:
        r = c.get("/sets/count")
        assert r.status_code == 200
        data = r.json()
        assert "count" in data
        assert isinstance(data["count"], int)
        assert data["count"] >= 0


def test_list_sets():
    """Test listing all sets."""
    _skip_if_no_api()
    with _client() as c:
        r = c.get("/sets")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        if data:
            set_item = data[0]
            assert "set_number" in set_item
            assert "name" in set_item
            assert "status" in set_item
            assert "total_parts" in set_item or "total_parts" in set_item


def test_get_set_by_number():
    """Test getting a specific set."""
    _skip_if_no_api()
    with _client() as c:
        # First get a list to find a valid set number
        sets_r = c.get("/sets")
        if sets_r.status_code != 200 or not sets_r.json():
            pytest.skip("No sets available for testing")
        
        set_number = sets_r.json()[0]["set_number"]
        r = c.get(f"/sets/{set_number}")
        assert r.status_code == 200
        data = r.json()
        assert data["set_number"] == set_number
        assert "name" in data
        assert "status" in data


def test_get_set_404():
    """Test 404 for invalid set number."""
    _skip_if_no_api()
    with _client() as c:
        r = c.get("/sets/invalid-set-number-99999")
        assert r.status_code == 404


def test_get_set_parts():
    """Test getting parts for a set."""
    _skip_if_no_api()
    with _client() as c:
        # First get a list to find a valid set number
        sets_r = c.get("/sets")
        if sets_r.status_code != 200 or not sets_r.json():
            pytest.skip("No sets available for testing")
        
        set_number = sets_r.json()[0]["set_number"]
        r = c.get(f"/sets/{set_number}/parts")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        if data:
            part = data[0]
            assert "design_id" in part
            assert "name" in part
            assert "color_id" in part
            assert "color_name" in part
            assert "quantity" in part
            assert isinstance(part["quantity"], int)
            assert part["quantity"] > 0


def test_update_set_status():
    """Test updating set status."""
    _skip_if_no_api()
    with _client() as c:
        # First get a valid set
        sets_r = c.get("/sets")
        if sets_r.status_code != 200 or not sets_r.json():
            pytest.skip("No sets available for testing")
        
        set_num = sets_r.json()[0]["set_number"]
        original_status = sets_r.json()[0]["status"]
        
        # Try updating to a different status
        new_status = "built" if original_status != "built" else "in_box"
        r = c.patch(
            f"/sets/{set_num}/status",
            json={"status": new_status}
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == new_status
        
        # Restore original status
        c.patch(
            f"/sets/{set_num}/status",
            json={"status": original_status}
        )


def test_update_set_status_invalid():
    """Test updating set status with invalid value."""
    _skip_if_no_api()
    with _client() as c:
        # First get a valid set
        sets_r = c.get("/sets")
        if sets_r.status_code != 200 or not sets_r.json():
            pytest.skip("No sets available for testing")
        
        set_num = sets_r.json()[0]["set_number"]
        r = c.patch(
            f"/sets/{set_num}/status",
            json={"status": "invalid-status"}
        )
        assert r.status_code in (400, 422)


def test_update_set_status_404():
    """Test updating status for non-existent set."""
    _skip_if_no_api()
    with _client() as c:
        r = c.patch(
            "/sets/invalid-set-number-99999/status",
            json={"status": "built"}
        )
        assert r.status_code == 404

