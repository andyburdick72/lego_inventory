# tests/test_api_drawers.py
import pytest
import requests

pytestmark = pytest.mark.contract


def _has_key(d, *candidates):
    return any(k in d for k in candidates)


def _get_first(d, *candidates):
    for k in candidates:
        if k in d:
            return d[k]
    raise KeyError(candidates)


def test_drawers_basic_shape_optional_empty(api_base_url, skip_if_no_api):
    # skip_if_no_api is handled automatically by the fixture
    base = api_base_url.rstrip("/")
    base_api = base if base.endswith("/api") else f"{base}/api"
    url = f"{base_api}/drawers"
    resp = requests.get(url, timeout=10)

    # Basic contract checks
    assert resp.status_code == 200
    ct = resp.headers.get("Content-Type", "")
    assert "application/json" in ct or "json" in ct.lower()

    data = resp.json()
    assert isinstance(data, list)

    # If empty, we're done—contract still holds
    if not data:
        return

    first = data[0]
    assert isinstance(first, dict)
    # Accept either "name" or "label" for drawer text
    assert _has_key(first, "id")
    assert _has_key(first, "name", "label")

    # Basic type/shape checks (tolerant across refactors)
    assert isinstance(first["id"], int)
    text = _get_first(first, "name", "label")
    assert isinstance(text, str) and len(text) > 0
