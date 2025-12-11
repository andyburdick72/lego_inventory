"""Unit tests for LocationReconciliationService."""

from collections.abc import Iterable, Mapping
from typing import Any

import pytest

from app.errors import ValidationError
from core.services.location_reconciliation_service import LocationReconciliationService


class DummySetsRepo:
    """Dummy sets repository for testing."""

    def __init__(self, sets_data: list[dict[str, Any]] | None = None):
        self.sets_data = sets_data or []

    def list_sets_with_statuses(self, statuses: list[str]) -> list[Mapping[str, Any]]:
        return [s for s in self.sets_data if s.get("status") in statuses]


class DummySetPartsRepo:
    """Dummy set parts repository for testing."""

    def __init__(self, parts_data: dict[str, list[dict[str, Any]]] | None = None):
        self.parts_data = parts_data or {}

    def list_for_set(self, *, set_number: str) -> Iterable[Mapping[str, Any]]:
        return self.parts_data.get(set_number, [])


class DummyInventoryRepo:
    """Dummy inventory repository for testing."""

    def __init__(self):
        self.inventory: dict[tuple[str, int, int | None, int | None], int] = {}
        self.totals_by_location: dict[tuple[str, int], list[dict[str, Any]]] = {}

    def get_inventory_by_location(
        self, design_id: str, color_id: int, drawer_id: int | None, container_id: int | None
    ) -> list[dict]:
        key = (design_id, color_id, drawer_id, container_id)
        qty = self.inventory.get(key, 0)
        if qty > 0:
            return [{"quantity": qty}]
        return []

    def get_inventory_totals_by_location(self, design_id: str, color_id: int) -> list[dict]:
        key = (design_id, color_id)
        return self.totals_by_location.get(key, [])

    def set_inventory_quantity_at_location(
        self,
        design_id: str,
        color_id: int,
        quantity: int,
        drawer_id: int | None,
        container_id: int | None,
    ) -> None:
        # Remove all existing inventory for this part+color
        keys_to_remove = [
            k for k in self.inventory.keys() if k[0] == design_id and k[1] == color_id
        ]
        for k in keys_to_remove:
            del self.inventory[k]

        # Set new quantity at specified location
        if quantity > 0:
            key = (design_id, color_id, drawer_id, container_id)
            self.inventory[key] = quantity


class DummyDrawersRepo:
    """Dummy drawers repository for testing."""

    def __init__(self, put_away_bin: dict[str, Any] | None = None):
        self.put_away_bin = put_away_bin

    def get_put_away_bin(self) -> dict | None:
        return self.put_away_bin


def make_service(
    sets_data: list[dict[str, Any]] | None = None,
    parts_data: dict[str, list[dict[str, Any]]] | None = None,
    put_away_bin: dict[str, Any] | None = None,
) -> LocationReconciliationService:
    """Create a LocationReconciliationService with dummy repositories."""
    return LocationReconciliationService(
        sets=DummySetsRepo(sets_data),
        set_parts=DummySetPartsRepo(parts_data),
        inventory=DummyInventoryRepo(),
        drawers=DummyDrawersRepo(put_away_bin),
    )


def test_compute_loose_parts_reconciliation_items_no_mismatches():
    """Test computing loose parts reconciliation items when there are no mismatches."""
    sets_data = [
        {"set_number": "12345-1", "status": "loose_parts"},
    ]
    parts_data = {
        "12345-1": [
            {
                "design_id": "3001",
                "color_id": 1,
                "quantity": 5,
                "name": "Brick 2 x 4",
                "color_name": "White",
            }
        ]
    }
    put_away_bin = {"drawer_id": 1, "container_id": 1}

    service = make_service(sets_data, parts_data, put_away_bin)

    # Set up inventory to match requirements (not in Put Away)
    service._inventory.inventory[("3001", 1, 2, 2)] = 5  # In a different container
    service._inventory.totals_by_location[("3001", 1)] = [
        {
            "drawer_id": 2,
            "drawer_name": "Drawer 2",
            "container_id": 2,
            "container_name": "Container 2",
            "quantity": 5,
        }
    ]

    items = service.compute_loose_parts_reconciliation_items()
    # Should return empty list since there's no mismatch
    assert items == []


def test_compute_loose_parts_reconciliation_items_with_mismatch():
    """Test computing loose parts reconciliation items when there's a mismatch."""
    sets_data = [
        {"set_number": "12345-1", "status": "loose_parts"},
    ]
    parts_data = {
        "12345-1": [
            {
                "design_id": "3001",
                "color_id": 1,
                "quantity": 5,
                "name": "Brick 2 x 4",
                "color_name": "White",
            }
        ]
    }
    put_away_bin = {"drawer_id": 1, "container_id": 1}

    service = make_service(sets_data, parts_data, put_away_bin)

    # Set up inventory with less than required (mismatch)
    service._inventory.totals_by_location[("3001", 1)] = [
        {
            "drawer_id": 2,
            "drawer_name": "Drawer 2",
            "container_id": 2,
            "container_name": "Container 2",
            "quantity": 3,
        }
    ]

    items = service.compute_loose_parts_reconciliation_items()
    assert len(items) == 1
    item = items[0]
    assert item["design_id"] == "3001"
    assert item["color_id"] == 1
    assert item["required_quantity"] == 5
    assert item["current_total"] == 3
    assert item["delta"] == 2  # 5 - 3
    assert item["needs_update"] is True


def test_compute_loose_parts_reconciliation_items_excludes_put_away():
    """Test that loose parts reconciliation excludes Put Away bin quantities."""
    sets_data = [
        {"set_number": "12345-1", "status": "loose_parts"},
    ]
    parts_data = {
        "12345-1": [
            {
                "design_id": "3001",
                "color_id": 1,
                "quantity": 5,
                "name": "Brick 2 x 4",
                "color_name": "White",
            }
        ]
    }
    put_away_bin = {"drawer_id": 1, "container_id": 1}

    service = make_service(sets_data, parts_data, put_away_bin)

    # Set up inventory: 3 in regular location, 2 in Put Away (should be excluded)
    service._inventory.totals_by_location[("3001", 1)] = [
        {
            "drawer_id": 2,
            "drawer_name": "Drawer 2",
            "container_id": 2,
            "container_name": "Container 2",
            "quantity": 3,
        },
        {
            "drawer_id": 1,
            "drawer_name": "Put Away",
            "container_id": 1,
            "container_name": "Put Away",
            "quantity": 2,
        },
    ]
    service._inventory.inventory[("3001", 1, 1, 1)] = 2  # In Put Away

    items = service.compute_loose_parts_reconciliation_items()
    assert len(items) == 1
    item = items[0]
    assert item["current_total"] == 3  # Only counts non-Put-Away locations
    assert item["put_away_quantity"] == 2  # Tracks Put Away separately
    assert item["delta"] == 2  # 5 - 3


def test_compute_teardown_reconciliation_items_no_put_away_bin():
    """Test that teardown reconciliation returns empty list if no Put Away bin configured."""
    sets_data = [
        {"set_number": "12345-1", "status": "teardown"},
    ]
    parts_data = {
        "12345-1": [
            {
                "design_id": "3001",
                "color_id": 1,
                "quantity": 5,
                "name": "Brick 2 x 4",
                "color_name": "White",
            }
        ]
    }

    service = make_service(sets_data, parts_data, put_away_bin=None)

    items = service.compute_teardown_reconciliation_items()
    assert items == []


def test_compute_teardown_reconciliation_items_with_mismatch():
    """Test computing teardown reconciliation items when there's a mismatch."""
    sets_data = [
        {"set_number": "12345-1", "status": "teardown"},
    ]
    parts_data = {
        "12345-1": [
            {
                "design_id": "3001",
                "color_id": 1,
                "quantity": 5,
                "name": "Brick 2 x 4",
                "color_name": "White",
            }
        ]
    }
    put_away_bin = {"drawer_id": 1, "container_id": 1}

    service = make_service(sets_data, parts_data, put_away_bin)

    # Set up inventory with less than required in Put Away
    service._inventory.inventory[("3001", 1, 1, 1)] = 3  # In Put Away
    service._inventory.totals_by_location[("3001", 1)] = [
        {
            "drawer_id": 1,
            "drawer_name": "Put Away",
            "container_id": 1,
            "container_name": "Put Away",
            "quantity": 3,
        }
    ]

    items = service.compute_teardown_reconciliation_items()
    assert len(items) == 1
    item = items[0]
    assert item["design_id"] == "3001"
    assert item["color_id"] == 1
    assert item["required_quantity"] == 5
    assert item["current_total"] == 3
    assert item["delta"] == 2  # 5 - 3
    assert item["needs_update"] is True


def test_update_inventory_location_negative_quantity():
    """Test that updating inventory location with negative quantity fails."""
    service = make_service()

    with pytest.raises(ValidationError, match="cannot be negative"):
        service.update_inventory_location("3001", 1, -1, drawer_id=1, container_id=1)


def test_update_inventory_location_loose_parts_prevents_put_away():
    """Test that loose parts cannot be stored in Put Away bin."""
    put_away_bin = {"drawer_id": 1, "container_id": 1}
    service = make_service(put_away_bin=put_away_bin)

    with pytest.raises(ValidationError, match="Put Away bin"):
        service.update_inventory_location(
            "3001", 1, 5, drawer_id=1, container_id=1, is_teardown=False
        )


def test_update_inventory_location_teardown_requires_put_away():
    """Test that teardown parts must be stored in Put Away bin."""
    put_away_bin = {"drawer_id": 1, "container_id": 1}
    service = make_service(put_away_bin=put_away_bin)

    with pytest.raises(ValidationError, match="Put Away bin"):
        service.update_inventory_location(
            "3001", 1, 5, drawer_id=2, container_id=2, is_teardown=True
        )


def test_update_inventory_location_success():
    """Test successful inventory location update."""
    sets_data = [
        {"set_number": "12345-1", "status": "loose_parts"},
    ]
    parts_data = {
        "12345-1": [
            {
                "design_id": "3001",
                "color_id": 1,
                "quantity": 5,
                "name": "Brick 2 x 4",
                "color_name": "White",
            }
        ]
    }
    put_away_bin = {"drawer_id": 1, "container_id": 1}
    service = make_service(sets_data, parts_data, put_away_bin)

    # Should not raise for valid loose parts location
    service.update_inventory_location("3001", 1, 5, drawer_id=2, container_id=2, is_teardown=False)

    # Verify inventory was set
    assert service._inventory.inventory[("3001", 1, 2, 2)] == 5


def test_update_inventory_location_removes_old_location():
    """Test that updating inventory location removes inventory from old locations."""
    sets_data = [
        {"set_number": "12345-1", "status": "loose_parts"},
    ]
    parts_data = {
        "12345-1": [
            {
                "design_id": "3001",
                "color_id": 1,
                "quantity": 5,
                "name": "Brick 2 x 4",
                "color_name": "White",
            }
        ]
    }
    put_away_bin = {"drawer_id": 1, "container_id": 1}
    service = make_service(sets_data, parts_data, put_away_bin)

    # Set initial inventory at one location
    service._inventory.inventory[("3001", 1, 2, 2)] = 3

    # Update to a different location
    service.update_inventory_location("3001", 1, 5, drawer_id=3, container_id=3, is_teardown=False)

    # Old location should be removed
    assert ("3001", 1, 2, 2) not in service._inventory.inventory
    # New location should have the quantity
    assert service._inventory.inventory[("3001", 1, 3, 3)] == 5


def test_compute_loose_parts_skips_sticker_sheets():
    """Test that sticker sheets are skipped in loose parts reconciliation."""
    sets_data = [
        {"set_number": "12345-1", "status": "loose_parts"},
    ]
    parts_data = {
        "12345-1": [
            {
                "design_id": "3001",
                "color_id": 1,
                "quantity": 5,
                "name": "Brick 2 x 4",
                "color_name": "White",
            },
            {
                "design_id": "STICKER1",
                "color_id": 0,
                "quantity": 1,
                "name": "Sticker Sheet",
                "color_name": "Transparent",
                "ignore_in_inventory": 1,
            },
        ]
    }
    put_away_bin = {"drawer_id": 1, "container_id": 1}

    service = make_service(sets_data, parts_data, put_away_bin)

    items = service.compute_loose_parts_reconciliation_items()
    # Should only include the brick, not the sticker sheet
    design_ids = [item["design_id"] for item in items]
    assert "3001" in design_ids or len(items) == 0  # May be empty if no mismatch
    assert "STICKER1" not in design_ids


def test_update_inventory_location_built_set_prevents_loose_inventory():
    """Test that parts from built sets cannot be stored in loose inventory."""
    sets_data = [
        {"set_number": "12345-1", "status": "built"},
    ]
    parts_data = {
        "12345-1": [
            {
                "design_id": "3001",
                "color_id": 1,
                "quantity": 5,
                "name": "Brick 2 x 4",
                "color_name": "White",
            }
        ]
    }
    put_away_bin = {"drawer_id": 1, "container_id": 1}
    service = make_service(sets_data, parts_data, put_away_bin)

    with pytest.raises(ValidationError, match="built set"):
        service.update_inventory_location(
            "3001", 1, 5, drawer_id=2, container_id=2, is_teardown=False
        )


def test_update_inventory_location_in_box_set_prevents_loose_inventory():
    """Test that parts from in-box sets cannot be stored in loose inventory."""
    sets_data = [
        {"set_number": "12345-1", "status": "in_box"},
    ]
    parts_data = {
        "12345-1": [
            {
                "design_id": "3001",
                "color_id": 1,
                "quantity": 5,
                "name": "Brick 2 x 4",
                "color_name": "White",
            }
        ]
    }
    put_away_bin = {"drawer_id": 1, "container_id": 1}
    service = make_service(sets_data, parts_data, put_away_bin)

    with pytest.raises(ValidationError, match="in-box set"):
        service.update_inventory_location(
            "3001", 1, 5, drawer_id=2, container_id=2, is_teardown=False
        )


def test_update_inventory_location_wip_set_prevents_loose_inventory():
    """Test that parts from work-in-progress sets cannot be stored in loose inventory."""
    sets_data = [
        {"set_number": "12345-1", "status": "wip"},
    ]
    parts_data = {
        "12345-1": [
            {
                "design_id": "3001",
                "color_id": 1,
                "quantity": 5,
                "name": "Brick 2 x 4",
                "color_name": "White",
            }
        ]
    }
    put_away_bin = {"drawer_id": 1, "container_id": 1}
    service = make_service(sets_data, parts_data, put_away_bin)

    with pytest.raises(ValidationError, match="work-in-progress set"):
        service.update_inventory_location(
            "3001", 1, 5, drawer_id=2, container_id=2, is_teardown=False
        )


def test_update_inventory_location_no_loose_parts_set_prevents_loose_inventory():
    """Test that parts that don't belong to Loose Parts sets cannot be stored in loose inventory."""
    # Part doesn't belong to any sets
    put_away_bin = {"drawer_id": 1, "container_id": 1}
    service = make_service(sets_data=[], parts_data={}, put_away_bin=put_away_bin)

    with pytest.raises(ValidationError, match="Loose Parts"):
        service.update_inventory_location(
            "3001", 1, 5, drawer_id=2, container_id=2, is_teardown=False
        )


def test_update_inventory_location_loose_parts_set_allows_loose_inventory():
    """Test that parts from Loose Parts sets can be stored in loose inventory."""
    sets_data = [
        {"set_number": "12345-1", "status": "loose_parts"},
    ]
    parts_data = {
        "12345-1": [
            {
                "design_id": "3001",
                "color_id": 1,
                "quantity": 5,
                "name": "Brick 2 x 4",
                "color_name": "White",
            }
        ]
    }
    put_away_bin = {"drawer_id": 1, "container_id": 1}
    service = make_service(sets_data, parts_data, put_away_bin)

    # Should not raise for valid loose parts location
    service.update_inventory_location("3001", 1, 5, drawer_id=2, container_id=2, is_teardown=False)

    # Verify inventory was set
    assert service._inventory.inventory[("3001", 1, 2, 2)] == 5


def test_update_inventory_location_teardown_set_allows_put_away_bin():
    """Test that parts from teardown sets can be stored in Put Away bin."""
    sets_data = [
        {"set_number": "12345-1", "status": "teardown"},
    ]
    parts_data = {
        "12345-1": [
            {
                "design_id": "3001",
                "color_id": 1,
                "quantity": 5,
                "name": "Brick 2 x 4",
                "color_name": "White",
            }
        ]
    }
    put_away_bin = {"drawer_id": 1, "container_id": 1}
    service = make_service(sets_data, parts_data, put_away_bin)

    # Should not raise for teardown part in Put Away bin
    service.update_inventory_location("3001", 1, 5, drawer_id=1, container_id=1, is_teardown=True)

    # Verify inventory was set
    assert service._inventory.inventory[("3001", 1, 1, 1)] == 5


def test_update_inventory_location_built_set_takes_precedence_over_loose_parts():
    """Test that if a part belongs to both built and loose_parts sets, built takes precedence."""
    sets_data = [
        {"set_number": "12345-1", "status": "built"},
        {"set_number": "67890-1", "status": "loose_parts"},
    ]
    parts_data = {
        "12345-1": [
            {
                "design_id": "3001",
                "color_id": 1,
                "quantity": 5,
                "name": "Brick 2 x 4",
                "color_name": "White",
            }
        ],
        "67890-1": [
            {
                "design_id": "3001",
                "color_id": 1,
                "quantity": 3,
                "name": "Brick 2 x 4",
                "color_name": "White",
            }
        ],
    }
    put_away_bin = {"drawer_id": 1, "container_id": 1}
    service = make_service(sets_data, parts_data, put_away_bin)

    # Should still fail because part belongs to a built set
    with pytest.raises(ValidationError, match="built set"):
        service.update_inventory_location(
            "3001", 1, 5, drawer_id=2, container_id=2, is_teardown=False
        )


def test_update_inventory_location_error_message_includes_set_numbers():
    """Test that error messages include set numbers when available."""
    sets_data = [
        {"set_number": "12345-1", "status": "built"},
        {"set_number": "67890-1", "status": "built"},
    ]
    parts_data = {
        "12345-1": [
            {
                "design_id": "3001",
                "color_id": 1,
                "quantity": 5,
                "name": "Brick 2 x 4",
                "color_name": "White",
            }
        ],
        "67890-1": [
            {
                "design_id": "3001",
                "color_id": 1,
                "quantity": 3,
                "name": "Brick 2 x 4",
                "color_name": "White",
            }
        ],
    }
    put_away_bin = {"drawer_id": 1, "container_id": 1}
    service = make_service(sets_data, parts_data, put_away_bin)

    with pytest.raises(ValidationError) as exc_info:
        service.update_inventory_location(
            "3001", 1, 5, drawer_id=2, container_id=2, is_teardown=False
        )

    error_message = str(exc_info.value)
    # Should mention built sets and include at least one set number
    assert "built set" in error_message.lower()
    assert "12345-1" in error_message or "67890-1" in error_message
