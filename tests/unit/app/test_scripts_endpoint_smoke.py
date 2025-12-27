"""Smoke tests for script endpoints (no subprocess execution)."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient

from app.api.main import app


@dataclass
class _FakeCompleted:
    returncode: int = 0
    stdout: str = "Rebrickable load summary: ok\n"
    stderr: str = ""


def test_sync_rebrickable_parts_success(monkeypatch):
    # Patch subprocess.run inside the endpoint module.
    from app.api.v1 import scripts as scripts_router

    monkeypatch.setattr(scripts_router.subprocess, "run", lambda *args, **kwargs: _FakeCompleted())

    with TestClient(app) as client:
        r = client.post("/api/v1/scripts/sync-rebrickable-parts")
        assert r.status_code == 200
        payload = r.json()
        assert payload["success"] is True
        assert "Parts synced successfully" in payload["message"]


