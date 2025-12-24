from fastapi.testclient import TestClient

from app.api.main import SAFE_MODE_DETAIL, app
from app.settings import get_settings


def test_safe_mode_gates_legacy_endpoints(monkeypatch):
    monkeypatch.setenv("APP_SAFE_MODE", "true")
    get_settings.cache_clear()

    client = TestClient(app)

    # Not gated
    r = client.get("/health")
    assert r.status_code == 200

    # Gated (legacy / location-dependent)
    r = client.get("/api/v1/drawers")
    assert r.status_code == 410
    assert r.json() == {"detail": SAFE_MODE_DETAIL}

    r = client.get("/api/v1/inventory/loose")
    assert r.status_code == 410
    assert r.json() == {"detail": SAFE_MODE_DETAIL}


def test_safe_mode_can_be_disabled(monkeypatch):
    monkeypatch.setenv("APP_SAFE_MODE", "false")
    get_settings.cache_clear()

    client = TestClient(app)

    # We don't assert drawers is 200 here because it depends on DB availability in the test env;
    # we only assert it's not being forced to 410 by the safe-mode middleware.
    r = client.get("/api/v1/drawers")
    assert r.status_code != 410
