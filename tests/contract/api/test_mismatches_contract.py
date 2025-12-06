"""Contract tests for mismatches endpoints."""
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


def test_get_mismatch_summary():
    """Test mismatch summary endpoint."""
    _skip_if_no_api()
    with _client() as c:
        r = c.get("/mismatches/summary")
        assert r.status_code == 200
        data = r.json()
        assert "total_sets" in data
        assert "sets_with_mismatches" in data
        assert "total_missing_parts" in data
        assert "total_excess_parts" in data
        assert "total_missing_quantity" in data
        assert "total_excess_quantity" in data
        assert isinstance(data["total_sets"], int)
        assert isinstance(data["sets_with_mismatches"], int)
        assert isinstance(data["total_missing_parts"], int)
        assert isinstance(data["total_excess_parts"], int)
        assert isinstance(data["total_missing_quantity"], int)
        assert isinstance(data["total_excess_quantity"], int)
        assert data["total_sets"] >= 0
        assert data["sets_with_mismatches"] >= 0
        assert data["total_missing_parts"] >= 0
        assert data["total_excess_parts"] >= 0
        assert data["total_missing_quantity"] >= 0
        assert data["total_excess_quantity"] >= 0


def test_get_mismatch_summary_with_statuses():
    """Test mismatch summary endpoint with status filter."""
    _skip_if_no_api()
    with _client() as c:
        r = c.get("/mismatches/summary?statuses=loose,teardown")
        assert r.status_code == 200
        data = r.json()
        assert "total_sets" in data
        assert isinstance(data["total_sets"], int)


def test_list_mismatches():
    """Test listing all mismatches."""
    _skip_if_no_api()
    with _client() as c:
        r = c.get("/mismatches")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        if data:
            mismatch = data[0]
            assert "set_number" in mismatch
            assert "set_name" in mismatch
            assert "status" in mismatch
            assert "missing_parts_count" in mismatch
            assert "excess_parts_count" in mismatch
            assert "total_missing_quantity" in mismatch
            assert "total_excess_quantity" in mismatch
            assert "mismatches" in mismatch
            assert isinstance(mismatch["mismatches"], list)
            if mismatch["mismatches"]:
                part_mismatch = mismatch["mismatches"][0]
                assert "design_id" in part_mismatch
                assert "part_name" in part_mismatch
                assert "color_id" in part_mismatch
                assert "required_quantity" in part_mismatch
                assert "available_quantity" in part_mismatch
                assert "delta" in part_mismatch


def test_list_mismatches_with_statuses():
    """Test listing mismatches with status filter."""
    _skip_if_no_api()
    with _client() as c:
        r = c.get("/mismatches?statuses=loose")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)


def test_list_mismatches_with_set_number():
    """Test listing mismatches filtered by set number."""
    _skip_if_no_api()
    # First, get a list of sets to find a valid set number
    with _client() as c:
        sets_r = c.get("/sets")
        if sets_r.status_code == 200:
            sets_data = sets_r.json()
            if sets_data:
                # Try to find a set with loose or teardown status
                test_set = None
                for s in sets_data:
                    if s.get("status") in ["loose", "teardown"]:
                        test_set = s["set_number"]
                        break
                
                if test_set:
                    r = c.get(f"/mismatches?set_number={test_set}")
                    assert r.status_code == 200
                    data = r.json()
                    assert isinstance(data, list)
                    # If there are results, verify they're for the correct set
                    if data:
                        assert all(m["set_number"] == test_set for m in data)


def test_get_set_mismatch():
    """Test getting mismatch for a specific set."""
    _skip_if_no_api()
    # First, get a list of sets to find a valid set number
    with _client() as c:
        sets_r = c.get("/sets")
        if sets_r.status_code == 200:
            sets_data = sets_r.json()
            if sets_data:
                # Use the first set
                test_set = sets_data[0]["set_number"]
                r = c.get(f"/mismatches/{test_set}")
                assert r.status_code == 200
                data = r.json()
                assert "set_number" in data
                assert data["set_number"] == test_set
                assert "set_name" in data
                assert "status" in data
                assert "mismatches" in data
                assert isinstance(data["mismatches"], list)


def test_get_set_mismatch_404():
    """Test getting mismatch for non-existent set."""
    _skip_if_no_api()
    with _client() as c:
        r = c.get("/mismatches/INVALID-SET-12345")
        assert r.status_code == 404
        data = r.json()
        assert "detail" in data

