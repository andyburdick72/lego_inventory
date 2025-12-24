# tests/contract/api/test_search_contract.py
import os

import pytest
import requests

pytestmark = pytest.mark.contract

if os.getenv("APP_SAFE_MODE") == "true":
    pytest.skip("Global search is disabled in set-centric safe mode.", allow_module_level=True)


def _get_json(url):
    resp = requests.get(url, timeout=10)
    return resp.status_code, resp.headers.get("Content-Type", ""), resp


def _assert_search_results_shape(data):
    """Assert that search results have the expected structure."""
    assert isinstance(data, dict), "Search results should be a dictionary"

    # Check that all expected keys are present
    expected_keys = ["parts", "sets", "drawers", "containers", "categories"]
    for key in expected_keys:
        assert key in data, f"Search results should have '{key}' key"
        assert isinstance(data[key], list), f"'{key}' should be a list"

    # Validate parts structure if any exist
    if data["parts"]:
        part = data["parts"][0]
        assert isinstance(part, dict)
        assert "design_id" in part
        assert "name" in part
        assert isinstance(part["design_id"], str)
        assert isinstance(part["name"], str)

    # Validate sets structure if any exist
    if data["sets"]:
        set_item = data["sets"][0]
        assert isinstance(set_item, dict)
        assert "set_number" in set_item
        assert "name" in set_item
        assert isinstance(set_item["set_number"], str)
        assert isinstance(set_item["name"], str)

    # Validate drawers structure if any exist
    if data["drawers"]:
        drawer = data["drawers"][0]
        assert isinstance(drawer, dict)
        assert "id" in drawer
        assert "name" in drawer
        assert isinstance(drawer["id"], int)
        assert isinstance(drawer["name"], str)

    # Validate containers structure if any exist
    if data["containers"]:
        container = data["containers"][0]
        assert isinstance(container, dict)
        assert "id" in container
        assert "name" in container
        assert "drawer_id" in container
        assert isinstance(container["id"], int)
        assert isinstance(container["name"], str)
        assert isinstance(container["drawer_id"], int)

    # Validate categories structure if any exist
    if data["categories"]:
        category = data["categories"][0]
        assert isinstance(category, dict)
        assert "id" in category
        assert "name" in category
        assert isinstance(category["id"], int)
        assert isinstance(category["name"], str)


@pytest.mark.contract
def test_contract_search_endpoint(api_base_url, skip_if_no_api):
    """Test the global search endpoint."""
    base = api_base_url.rstrip("/")
    if base.endswith("/api/v1"):
        base_api = base
    elif base.endswith("/api"):
        base_api = f"{base}/v1"
    else:
        base_api = f"{base}/api/v1"

    # Test search with a common query
    url = f"{base_api}/search?q=test"
    sc, ct, resp = _get_json(url)

    if sc == 404:
        pytest.xfail(f"GET {url} returned 404 - endpoint not found")
        return

    assert sc == 200, f"GET {url} failed with {sc}: {getattr(resp, 'text', '')[:300]}"
    assert "json" in ct.lower(), f"Expected JSON from {url}, got {ct}"

    data = resp.json()
    _assert_search_results_shape(data)


@pytest.mark.contract
def test_contract_search_requires_query(api_base_url, skip_if_no_api):
    """Test that search endpoint requires a query parameter."""
    base = api_base_url.rstrip("/")
    if base.endswith("/api/v1"):
        base_api = base
    elif base.endswith("/api"):
        base_api = f"{base}/v1"
    else:
        base_api = f"{base}/api/v1"

    url = f"{base_api}/search"
    sc, ct, resp = _get_json(url)

    # Should return 422 (validation error) or 400 (bad request) when query is missing
    assert sc in (400, 422), f"Expected 400 or 422 from {url} without query, got {sc}"


@pytest.mark.contract
def test_contract_search_min_length(api_base_url, skip_if_no_api):
    """Test that search requires at least 2 characters."""
    base = api_base_url.rstrip("/")
    if base.endswith("/api/v1"):
        base_api = base
    elif base.endswith("/api"):
        base_api = f"{base}/v1"
    else:
        base_api = f"{base}/api/v1"

    # Test with single character (should fail validation)
    url = f"{base_api}/search?q=a"
    sc, ct, resp = _get_json(url)

    # Should return 422 (validation error) for query that's too short
    assert sc in (400, 422), f"Expected 400 or 422 from {url} with single char, got {sc}"


@pytest.mark.contract
def test_contract_search_limit_parameter(api_base_url, skip_if_no_api):
    """Test that search accepts limit parameter."""
    base = api_base_url.rstrip("/")
    if base.endswith("/api/v1"):
        base_api = base
    elif base.endswith("/api"):
        base_api = f"{base}/v1"
    else:
        base_api = f"{base}/api/v1"

    # Test with limit parameter
    url = f"{base_api}/search?q=test&limit=5"
    sc, ct, resp = _get_json(url)

    if sc == 404:
        pytest.xfail(f"GET {url} returned 404 - endpoint not found")
        return

    assert sc == 200, f"GET {url} failed with {sc}: {getattr(resp, 'text', '')[:300]}"
    assert "json" in ct.lower(), f"Expected JSON from {url}, got {ct}"

    data = resp.json()
    _assert_search_results_shape(data)

    # Verify that results are limited (each category should have at most 5 items)
    for key in ["parts", "sets", "drawers", "containers", "categories"]:
        assert len(data[key]) <= 5, f"Expected at most 5 {key}, got {len(data[key])}"
