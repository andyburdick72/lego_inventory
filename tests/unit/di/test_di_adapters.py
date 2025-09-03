import pytest

from app import di
from app.errors import DuplicateError


# Simulate repo-level duplicate error class that real drawers_repo raises
class FakeDBDuplicate(Exception):
    pass


class FakeDrawersImpl:
    def __init__(self, *, mode="ok", return_id=111):
        self.mode = mode
        self.return_id = return_id

    def list_drawers_with_counts(self):
        return []

    def list_drawers(self):
        return []

    def create_drawer(self, **kwargs):
        if self.mode == "dup":
            raise FakeDBDuplicate("duplicate drawer")
        if self.mode == "int":
            return self.return_id  # bare int
        return {"id": self.return_id, "label": kwargs.get("name") or kwargs.get("label")}

    def create_container(self, *args, **kwargs):
        if self.mode == "dup":
            raise FakeDBDuplicate("duplicate container")
        return {"id": self.return_id, "drawer_id": kwargs.get("drawer_id")}


def test_drawers_create_duplicate_translated(monkeypatch):
    impl = FakeDrawersImpl(mode="dup")
    adapter = di._DrawersRepoAdapter(impl)  # type: ignore[attr-defined]
    # monkeypatch the imported DB Duplicate type in di.py to our fake
    monkeypatch.setattr(di, "_DBDuplicateLabelError", FakeDBDuplicate, raising=True)
    with pytest.raises(DuplicateError):
        adapter.create(label="A1")


def test_drawers_create_normalizes_id(monkeypatch):
    impl = FakeDrawersImpl(mode="int", return_id=222)
    adapter = di._DrawersRepoAdapter(impl)  # type: ignore[attr-defined]
    row = adapter.create(label="A1")
    assert row["id"] == 222  # bare int normalized to mapping


def test_containers_create_duplicate_translated(monkeypatch):
    impl = FakeDrawersImpl(mode="dup")
    adapter = di._ContainersRepoAdapter(impl)  # type: ignore[attr-defined]
    monkeypatch.setattr(di, "_DBDuplicateLabelError", FakeDBDuplicate, raising=True)
    with pytest.raises(DuplicateError):
        adapter.create(label="C1", drawer_id=1)
