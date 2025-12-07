"""Contract tests for location reconciliation endpoints."""
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


def test_list_loose_parts_reconciliation_items():
    """Test listing loose parts reconciliation items."""
    _skip_if_no_api()
    with _client() as c:
        r = c.get("/location-reconciliation/items/loose-parts")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        if data:
            item = data[0]
            assert "design_id" in item
            assert "part_name" in item
            assert "color_id" in item
            assert "color_name" in item
            assert "required_quantity" in item
            assert "current_locations" in item
            assert "current_total" in item
            assert "put_away_quantity" in item
            assert "delta" in item
            assert "needs_update" in item
            assert isinstance(item["current_locations"], list)
            assert isinstance(item["required_quantity"], int)
            assert isinstance(item["current_total"], int)
            assert isinstance(item["put_away_quantity"], int)
            assert isinstance(item["delta"], int)
            assert isinstance(item["needs_update"], bool)
            # Verify location structure if present
            if item["current_locations"]:
                loc = item["current_locations"][0]
                assert "drawer_id" in loc or loc.get("drawer_id") is None
                assert "drawer_name" in loc
                assert "container_id" in loc or loc.get("container_id") is None
                assert "container_name" in loc
                assert "quantity" in loc
                assert isinstance(loc["quantity"], int)


def test_list_teardown_reconciliation_items():
    """Test listing teardown reconciliation items."""
    _skip_if_no_api()
    with _client() as c:
        r = c.get("/location-reconciliation/items/teardown")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        if data:
            item = data[0]
            assert "design_id" in item
            assert "part_name" in item
            assert "color_id" in item
            assert "color_name" in item
            assert "required_quantity" in item
            assert "current_locations" in item
            assert "current_total" in item
            assert "put_away_quantity" in item
            assert "delta" in item
            assert "needs_update" in item
            assert isinstance(item["current_locations"], list)
            assert isinstance(item["required_quantity"], int)
            assert isinstance(item["current_total"], int)
            assert isinstance(item["put_away_quantity"], int)
            assert isinstance(item["delta"], int)
            assert isinstance(item["needs_update"], bool)


def test_update_inventory_location_validation():
    """Test that updating inventory location validates inputs."""
    _skip_if_no_api()
    with _client() as c:
        # Test with negative quantity (should fail)
        r = c.patch(
            "/location-reconciliation/items/TEST123/1",
            params={"quantity": -1},
        )
        assert r.status_code == 400
        data = r.json()
        assert "detail" in data


def test_update_inventory_location_loose_parts_prevents_put_away():
    """Test that loose parts cannot be put in Put Away bin."""
    _skip_if_no_api()
    # First, get a loose parts reconciliation item if available
    with _client() as c:
        loose_r = c.get("/location-reconciliation/items/loose-parts")
        if loose_r.status_code == 200:
            loose_data = loose_r.json()
            if loose_data:
                item = loose_data[0]
                design_id = item["design_id"]
                color_id = item["color_id"]
                
                # Try to update to Put Away bin (should fail for loose parts)
                # We need to find the Put Away bin container_id first
                containers_r = c.get("/containers")
                if containers_r.status_code == 200:
                    containers = containers_r.json()
                    # Look for Put Away bin (usually has is_put_away_bin=1)
                    put_away = next(
                        (c for c in containers if c.get("is_put_away_bin") == 1),
                        None
                    )
                    if put_away:
                        r = c.patch(
                            f"/location-reconciliation/items/{design_id}/{color_id}",
                            params={
                                "quantity": 1,
                                "drawer_id": put_away["drawer_id"],
                                "container_id": put_away["id"],
                                "is_teardown": False,
                            },
                        )
                        # Should fail validation
                        assert r.status_code == 400
                        data = r.json()
                        assert "detail" in data
                        assert "Put Away bin" in data["detail"] or "put away" in data["detail"].lower()


def test_update_inventory_location_teardown_requires_put_away():
    """Test that teardown parts must be in Put Away bin."""
    _skip_if_no_api()
    # First, get a teardown reconciliation item if available
    with _client() as c:
        teardown_r = c.get("/location-reconciliation/items/teardown")
        if teardown_r.status_code == 200:
            teardown_data = teardown_r.json()
            if teardown_data:
                item = teardown_data[0]
                design_id = item["design_id"]
                color_id = item["color_id"]
                
                # Get a non-Put-Away container
                containers_r = c.get("/containers")
                if containers_r.status_code == 200:
                    containers = containers_r.json()
                    # Find a container that's NOT the Put Away bin
                    regular_container = next(
                        (c for c in containers if c.get("is_put_away_bin") != 1),
                        None
                    )
                    if regular_container:
                        r = c.patch(
                            f"/location-reconciliation/items/{design_id}/{color_id}",
                            params={
                                "quantity": 1,
                                "drawer_id": regular_container["drawer_id"],
                                "container_id": regular_container["id"],
                                "is_teardown": True,
                            },
                        )
                        # Should fail validation
                        assert r.status_code == 400
                        data = r.json()
                        assert "detail" in data
                        assert "Put Away bin" in data["detail"] or "put away" in data["detail"].lower()

