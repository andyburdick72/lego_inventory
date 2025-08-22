# tests/test_api_containers.py
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


def _get_json(url):
    resp = requests.get(url, timeout=10)
    return resp.status_code, resp.headers.get("Content-Type", ""), resp


def _assert_container_shape(obj):
    assert isinstance(obj, dict)
    assert _has_key(obj, "id")
    assert _has_key(obj, "label", "name")
    assert isinstance(obj["id"], int)
    label = _get_first(obj, "label", "name")
    assert isinstance(label, str) and label

    # Drawer linkage may be omitted in filtered views; if present, validate
    drawer_val = obj.get("drawer_id") or obj.get("drawerId") or obj.get("drawer")
    if isinstance(drawer_val, dict):
        assert _has_key(drawer_val, "id")
        assert isinstance(drawer_val["id"], int)
    elif drawer_val is not None:
        assert isinstance(drawer_val, int)


def _assert_json_list(status_code, content_type, resp, url_for_msg):
    assert (
        status_code == 200
    ), f"Expected 200 from {url_for_msg}, got {status_code}: {getattr(resp, 'text', '')[:300]}"
    assert "json" in content_type.lower(), f"Expected JSON from {url_for_msg}, got {content_type}"
    data = resp.json()
    assert isinstance(
        data, list
    ), f"Expected JSON list from {url_for_msg}, got: {type(data).__name__}"
    return data


def test_contract_containers_list(api_base_url):
    if not api_base_url:
        pytest.skip("Set API_BASE_URL to run contract tests, e.g. http://localhost:8000/api")

    base = api_base_url.rstrip("/")

    # 1) Try plain list first: GET /containers
    url = f"{base}/containers"
    sc, ct, resp = _get_json(url)
    if sc in (200,):
        data = _assert_json_list(sc, ct, resp, url)
        if data:
            _assert_container_shape(data[0])
        return

    # 2) If API requires a drawer filter, fetch one drawer and retry
    if sc in (400, 422):
        drawers_url = f"{base}/drawers"
        dsc, dct, dresp = _get_json(drawers_url)
        drawers = _assert_json_list(dsc, dct, dresp, drawers_url)
        if not drawers:
            pytest.skip("No drawers available to use for container filter")
        drawer_id = drawers[0]["id"]

        # 2a) Try query param style: /containers?drawer_id=<id>
        url_q = f"{base}/containers?drawer_id={drawer_id}"
        qsc, qct, qresp = _get_json(url_q)
        if qsc == 200:
            data = _assert_json_list(qsc, qct, qresp, url_q)
            if data:
                _assert_container_shape(data[0])
            return

        # 2b) Try nested route style: /drawers/<id>/containers
        url_nested = f"{base}/drawers/{drawer_id}/containers"
        nsc, nct, nresp = _get_json(url_nested)
        data = _assert_json_list(nsc, nct, nresp, url_nested)
        if data:
            _assert_container_shape(data[0])
        return

    # If we got here, surface the original failure
    assert sc == 200, f"GET {url} failed with {sc}: {getattr(resp, 'text', '')[:300]}"
