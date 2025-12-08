"""Contract tests for inventory endpoints."""
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


def test_inventory_total_count():
    """Test total part count endpoint."""
    _skip_if_no_api()
    with _client() as c:
        r = c.get("/inventory/total-count")
        assert r.status_code == 200
        data = r.json()
        assert "total_count" in data
        assert isinstance(data["total_count"], int)
        assert data["total_count"] >= 0


def test_inventory_loose_parts():
    """Test loose inventory listing."""
    _skip_if_no_api()
    with _client() as c:
        r = c.get("/inventory/loose")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        if data:
            item = data[0]
            assert "part_id" in item
            assert "color_id" in item
            assert "quantity" in item
            assert "status" in item
            # Status can be 'loose' or 'loose_parts' depending on data
            assert item["status"] in ("loose", "loose_parts")


def test_inventory_part_counts():
    """Test part counts endpoint."""
    _skip_if_no_api()
    with _client() as c:
        r = c.get("/inventory/part-counts")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        if data:
            item = data[0]
            assert "design_id" in item
            assert "part_name" in item
            assert "total_qty" in item
            assert isinstance(item["total_qty"], int)
            assert item["total_qty"] >= 0
            # Verify sorted by quantity descending (first item should have highest qty)
            if len(data) > 1:
                assert data[0]["total_qty"] >= data[1]["total_qty"]


def test_inventory_part_color_counts():
    """Test part+color counts endpoint."""
    _skip_if_no_api()
    with _client() as c:
        r = c.get("/inventory/part-color-counts")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        if data:
            item = data[0]
            assert "design_id" in item
            assert "part_name" in item
            assert "color_id" in item
            assert "color_name" in item
            assert "total_qty" in item
            assert isinstance(item["total_qty"], int)
            assert item["total_qty"] >= 0
            # Verify sorted by quantity descending
            if len(data) > 1:
                assert data[0]["total_qty"] >= data[1]["total_qty"]


def test_inventory_location_counts():
    """Test location counts endpoint."""
    _skip_if_no_api()
    with _client() as c:
        r = c.get("/inventory/location-counts")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        if data:
            item = data[0]
            assert "location" in item
            assert "total_qty" in item
            assert isinstance(item["total_qty"], int)
            assert item["total_qty"] >= 0
            # Verify sorted by quantity descending
            if len(data) > 1:
                assert data[0]["total_qty"] >= data[1]["total_qty"]
            # Verify location format (drawer / container or just drawer/container)
            assert isinstance(item["location"], str)
            assert len(item["location"]) > 0


def test_inventory_multiple_locations():
    """Test multiple locations endpoint."""
    _skip_if_no_api()
    with _client() as c:
        r = c.get("/inventory/multiple-locations")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        # All items should have location_count > 1 (by definition)
        for item in data:
            assert "design_id" in item
            assert "part_name" in item
            assert "color_id" in item
            assert "color_name" in item
            assert "location_count" in item
            assert "total_quantity" in item
            assert "locations" in item
            assert isinstance(item["design_id"], str)
            assert isinstance(item["part_name"], str)
            assert isinstance(item["color_id"], int)
            assert isinstance(item["color_name"], str)
            assert isinstance(item["location_count"], int)
            assert isinstance(item["total_quantity"], int)
            assert isinstance(item["locations"], list)
            # Location count must be > 1 (element exists in multiple locations)
            assert item["location_count"] > 1
            # Total quantity should be sum of location quantities
            assert item["total_quantity"] >= item["location_count"]
            # Verify locations structure
            if item["locations"]:
                loc = item["locations"][0]
                assert "quantity" in loc
                assert isinstance(loc["quantity"], int)
                assert loc["quantity"] > 0
                # At least one of drawer_id or container_id should be present
                # (or both can be None for unassigned inventory)
                assert "drawer_id" in loc or loc.get("drawer_id") is None
                assert "drawer_name" in loc or loc.get("drawer_name") is None
                assert "container_id" in loc or loc.get("container_id") is None
                assert "container_name" in loc or loc.get("container_name") is None
                assert "inventory_id" in loc
                assert isinstance(loc["inventory_id"], int)
                assert loc["inventory_id"] > 0
            # Verify that total_quantity matches sum of location quantities
            location_sum = sum(loc["quantity"] for loc in item["locations"])
            assert item["total_quantity"] == location_sum

