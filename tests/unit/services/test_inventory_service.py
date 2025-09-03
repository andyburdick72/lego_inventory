from collections.abc import Mapping
from typing import Any

import pytest

from app.errors import ValidationError
from core.services.inventory_service import InventoryService


class DummyDrawersRepo:
    def __init__(self):
        self.calls: list[tuple[str, str, Any]] = []

    # Protocol requires list(...)
    def list(self, *, filters: Mapping[str, Any] | None = None):
        return []

    # Must return a Mapping
    def create(self, *, label: str, description: Any | None = None) -> Mapping[str, Any]:
        self.calls.append(("create", label, description))
        return {"id": 123, "label": label, "description": description}

    def soft_delete(self, drawer_id: int) -> None:
        return None

    def restore(self, drawer_id: int) -> None:
        return None


class DummyContainersRepo:
    # Protocol requires list(...)
    def list(self, *, filters: Mapping[str, Any] | None = None):
        return []

    # Signature accepts drawer_id: int | None = None and returns Mapping
    def create(self, *, label: str, drawer_id: int | None = None) -> Mapping[str, Any]:
        assert isinstance(drawer_id, int)  # mimic service validation post-check
        return {"id": 456, "label": label, "drawer_id": drawer_id}

    def soft_delete(self, container_id: int) -> None:
        return None

    def restore(self, container_id: int) -> None:
        return None


class DummyInventoryRepo:
    def counts_by_storage_location(self):
        return []

    def loose_inventory_for_part(self, design_id: str):
        return []


def make_service():
    return InventoryService(
        drawers=DummyDrawersRepo(), containers=DummyContainersRepo(), inventory=DummyInventoryRepo()
    )


def test_create_drawer_requires_label():
    svc = make_service()
    with pytest.raises(ValidationError):
        svc.create_drawer(label="  ")
    with pytest.raises(ValidationError):
        svc.create_drawer(label="")
    # ok path
    row = svc.create_drawer(label="A1", description="Wall-1")
    assert row["id"] == 123
    assert row["description"] == "Wall-1"


def test_create_container_validates_inputs():
    svc = make_service()
    with pytest.raises(ValidationError):
        svc.create_container(label="", drawer_id=1)
    with pytest.raises(ValidationError):
        svc.create_container(label="C1", drawer_id=None)
    with pytest.raises(ValidationError):
        svc.create_container(label="C1", drawer_id="not-int")  # type: ignore[arg-type]
    row = svc.create_container(label="C1", drawer_id=7)
    assert row["id"] == 456
    assert row["drawer_id"] == 7
