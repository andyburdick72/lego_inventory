"""Contract tests for putaway wizard endpoints."""

import os

import httpx
import pytest

pytestmark = pytest.mark.contract

if os.getenv("APP_SAFE_MODE") == "true":
    pytest.skip("Putaway endpoints are disabled in set-centric safe mode.", allow_module_level=True)

API_BASE = os.getenv("API_BASE_URL") or os.getenv("API_BASE") or ""
SKIP_REASON = "API_BASE_URL or API_BASE not set"


def _skip_if_no_api():
    if not API_BASE:
        pytest.skip(SKIP_REASON)


def _client():
    if not API_BASE:
        pytest.skip(SKIP_REASON)
    return httpx.Client(base_url=API_BASE, timeout=10.0)


def test_putaway_parts_from_set_invalid_set():
    """Test that invalid set number returns 404."""
    _skip_if_no_api()
    with _client() as c:
        r = c.get("/putaway/parts-from-set/invalid-set-99999")
        assert r.status_code == 404
        data = r.json()
        assert "message" in data or "detail" in data


def test_putaway_parts_from_set_valid_set():
    """Test getting parts from a valid set."""
    _skip_if_no_api()
    with _client() as c:
        # First, get a valid set number
        sets_r = c.get("/sets")
        if sets_r.status_code != 200 or not sets_r.json():
            pytest.skip("No sets available for testing")

        set_number = sets_r.json()[0]["set_number"]
        r = c.get(f"/putaway/parts-from-set/{set_number}")

        # Should succeed if set exists
        if r.status_code == 404:
            pytest.skip(f"Set {set_number} not found (may have been deleted)")

        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

        # Validate part structure if parts exist
        if data:
            part = data[0]
            assert "design_id" in part
            assert "part_name" in part
            assert "color_id" in part
            assert "color_name" in part
            assert "quantity" in part
            assert isinstance(part["quantity"], int)
            assert part["quantity"] > 0

            # Check suggestion structure if present
            if part.get("suggestion"):
                suggestion = part["suggestion"]
                assert "confidence" in suggestion
                assert suggestion["confidence"] in ["high", "medium", "low", "none"]
                assert "drawer_name" in suggestion or suggestion.get("drawer_id")
                assert "container_name" in suggestion or suggestion.get("container_id")


def test_putaway_parts_in_bin_no_putaway_bin():
    """Test parts in bin when no putaway bin is configured."""
    _skip_if_no_api()
    with _client() as c:
        r = c.get("/putaway/parts-in-bin")

        # Either returns empty list or 404 if bin not configured
        if r.status_code == 404:
            assert (
                "putaway bin" in r.json().get("message", "").lower()
                or "putaway bin" in str(r.json().get("detail", "")).lower()
            )
        else:
            assert r.status_code == 200
            data = r.json()
            assert isinstance(data, list)


def test_putaway_parts_in_bin_with_search():
    """Test parts in bin with search filter."""
    _skip_if_no_api()
    with _client() as c:
        r = c.get("/putaway/parts-in-bin?search=test")
        # Should succeed even if no results
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            data = r.json()
            assert isinstance(data, list)


def test_putaway_batch_assign_empty():
    """Test batch assign with empty assignments list."""
    _skip_if_no_api()
    with _client() as c:
        r = c.post("/putaway/batch-assign", json={"assignments": []})
        assert r.status_code == 422  # Validation error


def test_putaway_batch_assign_invalid_format():
    """Test batch assign with invalid request format."""
    _skip_if_no_api()
    with _client() as c:
        r = c.post("/putaway/batch-assign", json={})
        assert r.status_code == 422  # Missing assignments field


def test_putaway_batch_assign_invalid_container():
    """Test batch assign with invalid container ID."""
    _skip_if_no_api()
    with _client() as c:
        # Use a very large container ID that doesn't exist
        invalid_container_id = 999999
        r = c.post(
            "/putaway/batch-assign",
            json={
                "assignments": [
                    {
                        "design_id": "3001",
                        "color_id": 1,
                        "quantity": 1,
                        "container_id": invalid_container_id,
                    }
                ]
            },
        )
        # Should return 200 with errors in response (non-blocking errors)
        assert r.status_code == 200
        data = r.json()
        assert "total_requested" in data
        assert "total_assigned" in data
        assert "total_skipped" in data
        assert "assignments" in data
        assert "errors" in data
        assert isinstance(data["errors"], list)


def test_putaway_batch_assign_skip():
    """Test batch assign with skipped assignments (container_id = null)."""
    _skip_if_no_api()
    with _client() as c:
        r = c.post(
            "/putaway/batch-assign",
            json={
                "assignments": [
                    {
                        "design_id": "3001",
                        "color_id": 1,
                        "quantity": 1,
                        "container_id": None,
                    }
                ]
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total_requested"] == 1
        assert data["total_skipped"] == 1
        assert data["total_assigned"] == 0
        assert len(data["assignments"]) == 1
        assert data["assignments"][0]["success"] is True
        assert (
            "skip" in data["assignments"][0]["message"].lower()
            or data["assignments"][0]["container_id"] is None
        )


def test_putaway_batch_assign_invalid_quantity():
    """Test batch assign with invalid quantity (0 or negative)."""
    _skip_if_no_api()
    with _client() as c:
        # Get a valid container first
        drawers_r = c.get("/drawers")
        if drawers_r.status_code != 200 or not drawers_r.json():
            pytest.skip("No drawers available for testing")

        drawer_id = drawers_r.json()[0]["id"]
        containers_r = c.get(f"/containers?drawer_id={drawer_id}")

        if containers_r.status_code != 200 or not containers_r.json():
            pytest.skip("No containers available for testing")

        container_id = containers_r.json()[0]["id"]

        r = c.post(
            "/putaway/batch-assign",
            json={
                "assignments": [
                    {
                        "design_id": "3001",
                        "color_id": 1,
                        "quantity": 0,  # Invalid quantity
                        "container_id": container_id,
                    }
                ]
            },
        )
        # Should return 200 with errors
        assert r.status_code == 200
        data = r.json()
        assert len(data["errors"]) > 0 or data["total_assigned"] == 0


def test_putaway_integration_full_flow():
    """Integration test for full putaway wizard flow."""
    _skip_if_no_api()
    with _client() as c:
        # 1. Get a valid set
        sets_r = c.get("/sets")
        if sets_r.status_code != 200 or not sets_r.json():
            pytest.skip("No sets available for testing")

        # Find a set that's not already loose
        test_set = None
        for s in sets_r.json():
            if s.get("status") not in ("loose_parts", "loose", "teardown"):
                test_set = s
                break

        if not test_set:
            pytest.skip("No suitable set found (all are already loose)")

        set_number = test_set["set_number"]

        # 2. Get parts from set
        parts_r = c.get(f"/putaway/parts-from-set/{set_number}")
        if parts_r.status_code != 200:
            pytest.skip(f"Could not get parts for set {set_number}")

        parts = parts_r.json()
        if not parts:
            pytest.skip(f"Set {set_number} has no parts")

        # 3. Get drawers and containers
        drawers_r = c.get("/drawers")
        if drawers_r.status_code != 200 or not drawers_r.json():
            pytest.skip("No drawers available")

        drawer_id = drawers_r.json()[0]["id"]
        containers_r = c.get(f"/containers?drawer_id={drawer_id}")

        if containers_r.status_code != 200 or not containers_r.json():
            pytest.skip("No containers available")

        container_id = containers_r.json()[0]["id"]

        # 4. Create assignments (assign first part if suggestion exists, otherwise skip)
        assignments = []
        for part in parts[:1]:  # Just test with first part
            assignment = {
                "design_id": part["design_id"],
                "color_id": part["color_id"],
                "quantity": part["quantity"],
            }

            # Use suggestion if available, otherwise use test container
            if part.get("suggestion") and part["suggestion"].get("container_id"):
                assignment["container_id"] = part["suggestion"]["container_id"]
            else:
                assignment["container_id"] = container_id

            assignments.append(assignment)

        # 5. Batch assign
        assign_r = c.post("/putaway/batch-assign", json={"assignments": assignments})
        assert assign_r.status_code == 200
        result = assign_r.json()
        assert "total_requested" in result
        assert "total_assigned" in result
        assert "assignments" in result
        assert len(result["assignments"]) == 1
