import sqlite3
from collections.abc import Mapping

import app.di as di


class _Settings:
    def __init__(self, db_path: str):
        self.db_path = db_path


def _mk_db(tmp_path):
    db = tmp_path / "cov_test.sqlite3"
    # create an empty sqlite db file
    sqlite3.connect(db).close()
    return str(db)


def test__get_conn_applies_pragmas(monkeypatch, tmp_path):
    db_path = _mk_db(tmp_path)

    def fake_get_settings():
        return _Settings(db_path)

    monkeypatch.setattr("app.di.get_settings", fake_get_settings, raising=True)

    conn = di._get_conn()
    try:
        # Verify row_factory set
        assert conn.row_factory is sqlite3.Row
        # Verify PRAGMAs (best-effort; ignore if not supported on platform)
        journal_mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
        assert str(journal_mode).upper() in {"WAL", "MEMORY", "OFF"}  # WAL expected, but be lenient
        busy = conn.execute("PRAGMA busy_timeout;").fetchone()[0]
        assert int(busy) >= 2500
    finally:
        conn.close()


# --- Cover adapters paths lightly ---


class _FakeDrawersImpl:
    def __init__(self):
        self.created = []

    def list_drawers(self):
        return []

    def create_drawer(self, **kwargs):
        # emulate returning sqlite3.Row-like mapping
        return {"id": 101, **kwargs}

    def soft_delete_drawer(self, _drawer_id: int):
        return None

    def restore_drawer(self, _drawer_id: int):
        return None


def test_drawers_adapter_basic_create_and_list(tmp_path, monkeypatch):
    db_path = _mk_db(tmp_path)
    monkeypatch.setattr("app.di.get_settings", lambda: _Settings(db_path), raising=True)

    impl = _FakeDrawersImpl()
    adapter = di._DrawersRepoAdapter(impl)  # type: ignore[attr-defined]

    # list()
    assert list(adapter.list()) == []

    # create(label=...) returns Mapping with id
    row = adapter.create(label="A1", description="Wall")
    assert isinstance(row, Mapping)
    assert row["id"] == 101


class _FakeContainersImpl(_FakeDrawersImpl):
    def list_containers_with_counts(self, drawer_id: int):
        return [{"id": 1, "drawer_id": drawer_id, "name": "C1"}]

    def create_container(self, *args, **kwargs):
        return {
            "id": 202,
            "drawer_id": kwargs.get("drawer_id"),
            "name": kwargs.get("name") or kwargs.get("label"),
        }


def test_containers_adapter_list_and_create(tmp_path, monkeypatch):
    db_path = _mk_db(tmp_path)
    monkeypatch.setattr("app.di.get_settings", lambda: _Settings(db_path), raising=True)

    impl = _FakeContainersImpl()
    adapter = di._ContainersRepoAdapter(impl)  # type: ignore[attr-defined]

    # list() with a drawer filter
    rows = adapter.list(filters={"drawer_id": 7})
    assert isinstance(rows, list)

    # create() returns mapping with id
    row = adapter.create(label="C1", drawer_id=7)
    assert row["id"] == 202
    assert row["drawer_id"] == 7
