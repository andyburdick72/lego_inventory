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
    def __init__(self):
        self.calls: list[tuple[str, Any]] = []
        self.inventory_items: dict[int, dict] = {}
        self.next_id = 1

    def counts_by_storage_location(self):
        return []

    def loose_inventory_for_part(self, design_id: str):
        return []

    def loose_inventory_for_part_color(self, design_id: str, color_id: int):
        return []

    def get_inventory_by_id(self, inventory_id: int) -> dict | None:
        self.calls.append(("get_inventory_by_id", inventory_id))
        return self.inventory_items.get(inventory_id)

    def update_inventory_quantity(self, inventory_id: int, quantity: int) -> None:
        self.calls.append(("update_inventory_quantity", inventory_id, quantity))
        if inventory_id not in self.inventory_items:
            raise ValueError(f"Inventory item {inventory_id} not found")
        if quantity == 0:
            del self.inventory_items[inventory_id]
        else:
            self.inventory_items[inventory_id]["quantity"] = quantity

    def update_inventory_location(self, inventory_id: int, container_id: int | None) -> None:
        self.calls.append(("update_inventory_location", inventory_id, container_id))
        if inventory_id not in self.inventory_items:
            raise ValueError(f"Inventory item {inventory_id} not found")
        self.inventory_items[inventory_id]["container_id"] = container_id

    def delete_inventory(self, inventory_id: int) -> None:
        self.calls.append(("delete_inventory", inventory_id))
        if inventory_id not in self.inventory_items:
            raise ValueError(f"Inventory item {inventory_id} not found")
        del self.inventory_items[inventory_id]

    def move_inventory(
        self, from_inventory_id: int, to_container_id: int | None, quantity: int
    ) -> None:
        self.calls.append(("move_inventory", from_inventory_id, to_container_id, quantity))
        if from_inventory_id not in self.inventory_items:
            raise ValueError(f"Source inventory item {from_inventory_id} not found")
        source = self.inventory_items[from_inventory_id]
        if source["quantity"] < quantity:
            raise ValueError(f"Insufficient quantity. Available: {source['quantity']}, requested: {quantity}")
        source["quantity"] -= quantity
        if source["quantity"] == 0:
            del self.inventory_items[from_inventory_id]


def make_service(inventory_repo: DummyInventoryRepo | None = None):
    return InventoryService(
        drawers=DummyDrawersRepo(),
        containers=DummyContainersRepo(),
        inventory=inventory_repo or DummyInventoryRepo()
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


def test_get_inventory_item():
    """Test getting an inventory item by ID."""
    repo = DummyInventoryRepo()
    repo.inventory_items[1] = {
        "id": 1,
        "part_id": "3001",
        "color_id": 1,
        "quantity": 10,
        "container_id": 5,
    }
    svc = make_service(repo)
    
    # Test successful get
    item = svc.get_inventory_item(1)
    assert item["id"] == 1
    assert item["part_id"] == "3001"
    
    # Test 404 for non-existent item
    with pytest.raises(Exception):  # Should raise NotFoundError
        svc.get_inventory_item(999)
    
    # Test validation
    with pytest.raises(ValidationError):
        svc.get_inventory_item(0)
    with pytest.raises(ValidationError):
        svc.get_inventory_item(-1)  # type: ignore[arg-type]


def test_update_inventory_quantity():
    """Test updating inventory quantity."""
    repo = DummyInventoryRepo()
    repo.inventory_items[1] = {
        "id": 1,
        "part_id": "3001",
        "color_id": 1,
        "quantity": 10,
    }
    svc = make_service(repo)
    
    # Test successful update
    svc.update_inventory_quantity(inventory_id=1, quantity=20)
    assert repo.inventory_items[1]["quantity"] == 20
    
    # Test setting to 0 (deletes item)
    svc.update_inventory_quantity(inventory_id=1, quantity=0)
    assert 1 not in repo.inventory_items
    
    # Test validation
    with pytest.raises(ValidationError):
        svc.update_inventory_quantity(inventory_id=0, quantity=5)
    with pytest.raises(ValidationError):
        svc.update_inventory_quantity(inventory_id=1, quantity=-1)
    with pytest.raises(ValidationError):
        svc.update_inventory_quantity(inventory_id=1, quantity="not-int")  # type: ignore[arg-type]


def test_update_inventory_location():
    """Test updating inventory location."""
    repo = DummyInventoryRepo()
    repo.inventory_items[1] = {
        "id": 1,
        "part_id": "3001",
        "color_id": 1,
        "quantity": 10,
        "container_id": 5,
    }
    svc = make_service(repo)
    
    # Test successful update
    svc.update_inventory_location(inventory_id=1, container_id=10)
    assert repo.inventory_items[1]["container_id"] == 10
    
    # Test removing location
    svc.update_inventory_location(inventory_id=1, container_id=None)
    assert repo.inventory_items[1]["container_id"] is None
    
    # Test validation
    with pytest.raises(ValidationError):
        svc.update_inventory_location(inventory_id=0, container_id=5)
    with pytest.raises(ValidationError):
        svc.update_inventory_location(inventory_id=1, container_id=0)


def test_delete_inventory_item():
    """Test deleting an inventory item."""
    repo = DummyInventoryRepo()
    repo.inventory_items[1] = {
        "id": 1,
        "part_id": "3001",
        "color_id": 1,
        "quantity": 10,
    }
    svc = make_service(repo)
    
    # Test successful deletion
    svc.delete_inventory_item(inventory_id=1)
    assert 1 not in repo.inventory_items
    
    # Test validation
    with pytest.raises(ValidationError):
        svc.delete_inventory_item(inventory_id=0)
    with pytest.raises(ValidationError):
        svc.delete_inventory_item(inventory_id=-1)  # type: ignore[arg-type]


def test_move_inventory():
    """Test moving inventory between locations."""
    repo = DummyInventoryRepo()
    repo.inventory_items[1] = {
        "id": 1,
        "part_id": "3001",
        "color_id": 1,
        "quantity": 10,
        "container_id": 5,
    }
    svc = make_service(repo)
    
    # Test successful move
    svc.move_inventory(from_inventory_id=1, to_container_id=10, quantity=3)
    assert repo.inventory_items[1]["quantity"] == 7
    
    # Test moving all quantity (should delete source)
    svc.move_inventory(from_inventory_id=1, to_container_id=10, quantity=7)
    assert 1 not in repo.inventory_items
    
    # Test validation
    repo.inventory_items[2] = {
        "id": 2,
        "part_id": "3001",
        "color_id": 1,
        "quantity": 5,
    }
    
    with pytest.raises(ValidationError):
        svc.move_inventory(from_inventory_id=0, to_container_id=10, quantity=1)
    with pytest.raises(ValidationError):
        svc.move_inventory(from_inventory_id=2, to_container_id=10, quantity=0)
    with pytest.raises(ValidationError):
        svc.move_inventory(from_inventory_id=2, to_container_id=10, quantity=-1)
    
    # Test insufficient quantity
    with pytest.raises(Exception):  # Should raise ValidationError from ValueError
        svc.move_inventory(from_inventory_id=2, to_container_id=10, quantity=100)
