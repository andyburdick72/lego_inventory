"""Unit tests for storage hierarchy service."""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock

import pytest

from core.services.storage_hierarchy_service import StorageHierarchyService, StorageSuggestion


class DummyInventoryRepo:
    """Dummy inventory repository for testing."""

    def __init__(self, element_locations=None, part_locations=None, category_locations=None):
        self.element_locations = element_locations or []
        self.part_locations = part_locations or []
        self.category_locations = category_locations or []

    def find_element_location(self, design_id: str, color_id: int) -> list[dict]:
        return self.element_locations

    def find_part_location(self, design_id: str) -> list[dict]:
        return self.part_locations

    def find_category_location(self, part_category_id: int) -> list[dict]:
        return self.category_locations


class DummyPartsRepo:
    """Dummy parts repository for testing."""

    def __init__(self, part_info: dict[str, Any] | None = None):
        self.part_info = part_info

    def get_part(self, design_id: str) -> dict | None:
        return self.part_info


def test_suggest_location_definitive_match():
    """Test that definitive match (element-level) is returned."""
    element_locations = [
        {
            "container_id": 1,
            "drawer_id": 1,
            "drawer_name": "Drawer A",
            "container_name": "Container 1",
            "quantity": 10,
        }
    ]
    inventory = DummyInventoryRepo(element_locations=element_locations)
    parts = DummyPartsRepo()
    service = StorageHierarchyService(inventory=inventory, parts=parts)

    suggestion = service.suggest_location("3001", 1)
    assert suggestion is not None
    assert suggestion.confidence == "definitive"
    assert suggestion.container_id == 1
    assert suggestion.drawer_id == 1
    assert suggestion.quantity == 10
    assert "Exact element match" in suggestion.reason


def test_suggest_location_part_match():
    """Test that part match (high confidence) is returned when no element match."""
    part_locations = [
        {
            "container_id": 2,
            "drawer_id": 2,
            "drawer_name": "Drawer B",
            "container_name": "Container 2",
            "total_quantity": 20,
        }
    ]
    inventory = DummyInventoryRepo(part_locations=part_locations)
    parts = DummyPartsRepo()
    service = StorageHierarchyService(inventory=inventory, parts=parts)

    suggestion = service.suggest_location("3001", 5)
    assert suggestion is not None
    assert suggestion.confidence == "high"
    assert suggestion.container_id == 2
    assert "Part match" in suggestion.reason


def test_suggest_location_category_match():
    """Test that category match (medium confidence) is returned when no element/part match."""
    category_locations = [
        {
            "container_id": 3,
            "drawer_id": 3,
            "drawer_name": "Drawer C",
            "container_name": "Container 3",
            "total_quantity": 30,
        }
    ]
    part_info = {"part_category_id": 1, "part_category_name": "Bricks"}
    inventory = DummyInventoryRepo(category_locations=category_locations)
    parts = DummyPartsRepo(part_info=part_info)
    service = StorageHierarchyService(inventory=inventory, parts=parts)

    suggestion = service.suggest_location("3001", 1)
    assert suggestion is not None
    assert suggestion.confidence == "medium"
    assert suggestion.container_id == 3
    assert "Category match" in suggestion.reason
    assert "Bricks" in suggestion.reason


def test_suggest_location_no_match():
    """Test that None is returned when no matches are found."""
    inventory = DummyInventoryRepo()
    parts = DummyPartsRepo()
    service = StorageHierarchyService(inventory=inventory, parts=parts)

    suggestion = service.suggest_location("3001", 1)
    assert suggestion is None


def test_suggest_location_validation_error():
    """Test that validation error is raised for invalid input."""
    inventory = DummyInventoryRepo()
    parts = DummyPartsRepo()
    service = StorageHierarchyService(inventory=inventory, parts=parts)

    with pytest.raises(Exception):  # ValidationError
        service.suggest_location("", 1)


def test_get_all_suggestions_ordered():
    """Test that all suggestions are returned ordered by confidence."""
    element_locations = [
        {
            "container_id": 1,
            "drawer_id": 1,
            "drawer_name": "Drawer A",
            "container_name": "Container 1",
            "quantity": 10,
        }
    ]
    part_locations = [
        {
            "container_id": 2,
            "drawer_id": 2,
            "drawer_name": "Drawer B",
            "container_name": "Container 2",
            "total_quantity": 20,
        }
    ]
    category_locations = [
        {
            "container_id": 3,
            "drawer_id": 3,
            "drawer_name": "Drawer C",
            "container_name": "Container 3",
            "total_quantity": 30,
        }
    ]
    part_info = {"part_category_id": 1, "part_category_name": "Bricks"}

    inventory = DummyInventoryRepo(
        element_locations=element_locations,
        part_locations=part_locations,
        category_locations=category_locations,
    )
    parts = DummyPartsRepo(part_info=part_info)
    service = StorageHierarchyService(inventory=inventory, parts=parts)

    suggestions = service.get_all_suggestions("3001", 1)
    assert len(suggestions) == 3
    assert suggestions[0].confidence == "definitive"
    assert suggestions[1].confidence == "high"
    assert suggestions[2].confidence == "medium"


def test_get_all_suggestions_deduplicates():
    """Test that duplicate containers are not included in multiple confidence levels."""
    element_locations = [
        {
            "container_id": 1,
            "drawer_id": 1,
            "drawer_name": "Drawer A",
            "container_name": "Container 1",
            "quantity": 10,
        }
    ]
    part_locations = [
        {
            "container_id": 1,  # Same container as element match
            "drawer_id": 1,
            "drawer_name": "Drawer A",
            "container_name": "Container 1",
            "total_quantity": 20,
        }
    ]

    inventory = DummyInventoryRepo(
        element_locations=element_locations, part_locations=part_locations
    )
    parts = DummyPartsRepo()
    service = StorageHierarchyService(inventory=inventory, parts=parts)

    suggestions = service.get_all_suggestions("3001", 1)
    # Should only have one suggestion (element match), not duplicate from part match
    assert len(suggestions) == 1
    assert suggestions[0].confidence == "definitive"

