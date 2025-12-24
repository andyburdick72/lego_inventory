"""Contract tests for sets endpoints."""

import os

import httpx
import pytest

pytestmark = pytest.mark.contract

API_BASE = os.getenv("API_BASE_URL") or os.getenv("API_BASE") or ""
SKIP_REASON = "API_BASE_URL or API_BASE not set"
SAFE_MODE_DETAIL = "Temporarily disabled while physical storage system is being rebuilt."


def _skip_if_no_api():
    if not API_BASE:
        pytest.skip(SKIP_REASON)


def _client():
    if not API_BASE:
        pytest.skip(SKIP_REASON)
    # Increased timeout for operations that may hit database locks or trigger long-running operations
    return httpx.Client(base_url=API_BASE, timeout=30.0)


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
        r = c.patch(f"/sets/{set_num}/status", json={"status": new_status})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == new_status

        # Restore original status
        c.patch(f"/sets/{set_num}/status", json={"status": original_status})


def test_update_set_status_invalid():
    """Test updating set status with invalid value."""
    _skip_if_no_api()
    with _client() as c:
        # First get a valid set
        sets_r = c.get("/sets")
        if sets_r.status_code != 200 or not sets_r.json():
            pytest.skip("No sets available for testing")

        set_num = sets_r.json()[0]["set_number"]
        r = c.patch(f"/sets/{set_num}/status", json={"status": "invalid-status"})
        assert r.status_code in (400, 422)


def test_update_set_status_404():
    """Test updating status for non-existent set."""
    _skip_if_no_api()
    with _client() as c:
        r = c.patch("/sets/invalid-set-number-99999/status", json={"status": "built"})
        assert r.status_code == 404


def test_get_set_parts_locations():
    """Test getting parts with locations for a set."""
    _skip_if_no_api()
    with _client() as c:
        # First get a list to find a valid set number
        sets_r = c.get("/sets")
        if sets_r.status_code != 200 or not sets_r.json():
            pytest.skip("No sets available for testing")

        set_number = sets_r.json()[0]["set_number"]
        r = c.get(f"/sets/{set_number}/parts-locations")
        if os.getenv("APP_SAFE_MODE") == "true":
            assert r.status_code == 410
            assert r.json() == {"detail": SAFE_MODE_DETAIL}
            return
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

        if data:
            part = data[0]
            # Required fields
            assert "design_id" in part
            assert "name" in part
            assert "color_id" in part
            assert "color_name" in part
            assert "required_quantity" in part
            assert "available_quantity" in part
            assert "locations" in part

            # Type checks
            assert isinstance(part["required_quantity"], int)
            assert isinstance(part["available_quantity"], int)
            assert isinstance(part["locations"], list)
            assert part["required_quantity"] > 0
            assert part["available_quantity"] >= 0

            # Location structure
            if part["locations"]:
                location = part["locations"][0]
                assert "quantity" in location
                assert isinstance(location["quantity"], int)
                assert location["quantity"] > 0
                # drawer_name and container_name are optional
                assert "drawer_id" in location or "drawer_name" in location
                assert "container_id" in location or "container_name" in location


def test_get_set_parts_locations_404():
    """Test 404 for parts-locations with invalid set number."""
    _skip_if_no_api()
    with _client() as c:
        r = c.get("/sets/invalid-set-number-99999/parts-locations")
        if os.getenv("APP_SAFE_MODE") == "true":
            assert r.status_code == 410
            assert r.json() == {"detail": SAFE_MODE_DETAIL}
            return
        assert r.status_code == 404


def test_get_set_parts_locations_empty_set():
    """Test parts-locations for a set with no parts."""
    _skip_if_no_api()
    with _client() as c:
        # First get a list to find a valid set number
        sets_r = c.get("/sets")
        if sets_r.status_code != 200 or not sets_r.json():
            pytest.skip("No sets available for testing")

        set_number = sets_r.json()[0]["set_number"]
        r = c.get(f"/sets/{set_number}/parts-locations")
        if os.getenv("APP_SAFE_MODE") == "true":
            assert r.status_code == 410
            assert r.json() == {"detail": SAFE_MODE_DETAIL}
            return
        assert r.status_code == 200
        data = r.json()
        # Should return empty list if set has no parts, or list of parts
        assert isinstance(data, list)
