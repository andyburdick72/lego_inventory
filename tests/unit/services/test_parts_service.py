"""Unit tests for PartsService."""
from collections.abc import Mapping
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.errors import NotFoundError, ValidationError
from core.services.parts_service import PartsService


class MockPartsRepo:
    """Mock parts repository for testing."""
    
    def __init__(self):
        self.parts: dict[str, dict[str, Any]] = {}
        self.update_calls: list[tuple[str, dict[str, Any]]] = []
    
    def get_part(self, design_id: str) -> Mapping[str, Any] | None:
        return self.parts.get(design_id)
    
    def update_part(self, design_id: str, **fields: Any) -> None:
        self.update_calls.append((design_id, fields))
        if design_id in self.parts:
            self.parts[design_id].update(fields)


def test_get_part_success():
    """Test successfully getting a part."""
    repo = MockPartsRepo()
    repo.parts["3001"] = {
        "design_id": "3001",
        "name": "Brick 2 x 4",
        "part_url": "https://rebrickable.com/parts/3001/",
        "part_img_url": "https://rebrickable.com/parts/3001.jpg",
        "ignore_in_inventory": 0,
    }
    
    service = PartsService(repo)
    result = service.get_part(design_id="3001")
    
    assert result is not None
    assert result["design_id"] == "3001"
    assert result["name"] == "Brick 2 x 4"


def test_get_part_not_found():
    """Test getting a part that doesn't exist."""
    repo = MockPartsRepo()
    service = PartsService(repo)
    
    with pytest.raises(NotFoundError, match="Part not found"):
        service.get_part(design_id="99999")


def test_get_part_empty_design_id():
    """Test getting a part with empty design_id."""
    repo = MockPartsRepo()
    service = PartsService(repo)
    
    with pytest.raises(ValidationError, match="design_id is required"):
        service.get_part(design_id="")


def test_update_part_success():
    """Test successfully updating a part."""
    repo = MockPartsRepo()
    repo.parts["3001"] = {
        "design_id": "3001",
        "name": "Brick 2 x 4",
        "ignore_in_inventory": 0,
    }
    
    service = PartsService(repo)
    result = service.update_part(design_id="3001", ignore_in_inventory=1)
    
    assert result is not None
    assert result["ignore_in_inventory"] == 1
    assert len(repo.update_calls) == 1
    assert repo.update_calls[0][0] == "3001"
    assert repo.update_calls[0][1]["ignore_in_inventory"] == 1


def test_update_part_not_found():
    """Test updating a part that doesn't exist."""
    repo = MockPartsRepo()
    service = PartsService(repo)
    
    with pytest.raises(NotFoundError, match="Part not found"):
        service.update_part(design_id="99999", ignore_in_inventory=1)


def test_update_part_empty_design_id():
    """Test updating a part with empty design_id."""
    repo = MockPartsRepo()
    service = PartsService(repo)
    
    with pytest.raises(ValidationError, match="design_id is required"):
        service.update_part(design_id="", ignore_in_inventory=1)


def test_update_part_multiple_fields():
    """Test updating multiple fields at once."""
    repo = MockPartsRepo()
    repo.parts["3001"] = {
        "design_id": "3001",
        "name": "Brick 2 x 4",
        "ignore_in_inventory": 0,
    }
    
    service = PartsService(repo)
    result = service.update_part(
        design_id="3001",
        ignore_in_inventory=1,
        name="Updated Name"
    )
    
    assert result is not None
    assert len(repo.update_calls) == 1
    update_fields = repo.update_calls[0][1]
    assert update_fields["ignore_in_inventory"] == 1
    assert update_fields["name"] == "Updated Name"

