"""Unit tests for Rebrickable API helper utilities (no network)."""

from __future__ import annotations

import pytest

from app.errors import AppError, ExternalServiceError, ValidationError
from app.settings import get_settings
from integrations import rebrickable_api


class _FakeResp:
    def __init__(self, status_code: int, payload=None, text: str = "", headers=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text
        self.headers = headers or {}

    def json(self):
        return self._payload


def test_api_key_missing_raises(monkeypatch):
    monkeypatch.setenv("APP_REBRICKABLE_API_KEY", "")
    get_settings.cache_clear()
    with pytest.raises(AppError):
        rebrickable_api._api_key()


def test_get_json_success(monkeypatch):
    monkeypatch.setenv("APP_REBRICKABLE_API_KEY", "dummy")
    get_settings.cache_clear()

    def fake_get(url, headers, params, timeout):  # noqa: ANN001
        assert url.startswith(rebrickable_api.RB_API_BASE)
        assert "Authorization" in headers
        return _FakeResp(200, payload={"ok": True})

    monkeypatch.setattr(rebrickable_api.requests, "get", fake_get)
    data = rebrickable_api.get_json("/colors/", params={"page_size": 1})
    assert data == {"ok": True}


def test_get_json_4xx_maps_to_validation_error(monkeypatch):
    monkeypatch.setenv("APP_REBRICKABLE_API_KEY", "dummy")
    get_settings.cache_clear()

    def fake_get(url, headers, params, timeout):  # noqa: ANN001
        return _FakeResp(404, payload={"detail": "not found"}, text="not found")

    monkeypatch.setattr(rebrickable_api.requests, "get", fake_get)
    with pytest.raises(ValidationError):
        rebrickable_api.get_json("/sets/does-not-exist/")


def test_paginate_yields_all_results(monkeypatch):
    monkeypatch.setenv("APP_REBRICKABLE_API_KEY", "dummy")
    get_settings.cache_clear()

    calls: list[str] = []

    def fake_get_json(url, params=None, timeout=30):  # noqa: ANN001
        calls.append(url)
        if len(calls) == 1:
            return {"results": [{"id": 1}, {"id": 2}], "next": "https://example.com/next"}
        return {"results": [{"id": 3}], "next": None}

    monkeypatch.setattr(rebrickable_api, "get_json", fake_get_json)
    out = list(rebrickable_api.paginate("/colors/"))
    assert out == [{"id": 1}, {"id": 2}, {"id": 3}]


def test_bulk_parts_falls_back_when_get_json_fails(monkeypatch):
    monkeypatch.setenv("APP_REBRICKABLE_API_KEY", "dummy")
    get_settings.cache_clear()

    def boom(*_args, **_kwargs):  # noqa: ANN001
        raise ExternalServiceError("boom")

    monkeypatch.setattr(rebrickable_api, "get_json", boom)
    monkeypatch.setattr(rebrickable_api, "_single_part_name", lambda pid: f"Name {pid}")

    mapping = rebrickable_api.bulk_parts(["3001", "3023"])
    assert mapping == {"3001": "Name 3001", "3023": "Name 3023"}


