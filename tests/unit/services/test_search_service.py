"""Unit tests for SearchService."""

from collections.abc import Mapping
from typing import Any

import pytest

from app.errors import ValidationError
from core.services.search_service import SearchService


class MockSearchRepo:
    """Mock search repository for testing."""

    def __init__(self):
        self.search_parts_calls: list[tuple[str, int]] = []
        self.search_sets_calls: list[tuple[str, int]] = []
        self.search_drawers_calls: list[tuple[str, int]] = []
        self.search_containers_calls: list[tuple[str, int]] = []
        self.search_categories_calls: list[tuple[str, int]] = []

    def search_parts(self, query: str, limit: int = 10) -> list[Mapping[str, Any]]:
        self.search_parts_calls.append((query, limit))
        return [
            {
                "design_id": "3001",
                "name": "Brick 2 x 4",
                "part_category_id": 1,
                "part_category_name": "Bricks",
            }
        ]

    def search_sets(self, query: str, limit: int = 10) -> list[Mapping[str, Any]]:
        self.search_sets_calls.append((query, limit))
        return [
            {
                "set_number": "75192",
                "name": "Millennium Falcon",
                "year": 2017,
                "theme_name": "Star Wars",
            }
        ]

    def search_drawers(self, query: str, limit: int = 10) -> list[Mapping[str, Any]]:
        self.search_drawers_calls.append((query, limit))
        return [{"id": 1, "name": "Drawer A", "description": "Test drawer"}]

    def search_containers(self, query: str, limit: int = 10) -> list[Mapping[str, Any]]:
        self.search_containers_calls.append((query, limit))
        return [{"id": 1, "name": "Container 1", "drawer_id": 1, "drawer_name": "Drawer A"}]

    def search_categories(self, query: str, limit: int = 10) -> list[Mapping[str, Any]]:
        self.search_categories_calls.append((query, limit))
        return [{"id": 1, "name": "Bricks"}]


def test_search_success():
    """Test successfully searching across all entity types."""
    repo = MockSearchRepo()
    service = SearchService(repo)

    result = service.search(query="test", limit_per_type=10)

    assert "parts" in result
    assert "sets" in result
    assert "drawers" in result
    assert "containers" in result
    assert "categories" in result

    assert len(result["parts"]) == 1
    assert len(result["sets"]) == 1
    assert len(result["drawers"]) == 1
    assert len(result["containers"]) == 1
    assert len(result["categories"]) == 1

    # Verify all search methods were called
    assert len(repo.search_parts_calls) == 1
    assert len(repo.search_sets_calls) == 1
    assert len(repo.search_drawers_calls) == 1
    assert len(repo.search_containers_calls) == 1
    assert len(repo.search_categories_calls) == 1

    # Verify correct parameters were passed
    assert repo.search_parts_calls[0] == ("test", 10)
    assert repo.search_sets_calls[0] == ("test", 10)


def test_search_with_custom_limit():
    """Test searching with a custom limit per type."""
    repo = MockSearchRepo()
    service = SearchService(repo)

    result = service.search(query="brick", limit_per_type=5)

    assert len(result["parts"]) == 1
    # Verify limit was passed correctly
    assert repo.search_parts_calls[0] == ("brick", 5)
    assert repo.search_sets_calls[0] == ("brick", 5)


def test_search_empty_query():
    """Test searching with empty query raises ValidationError."""
    repo = MockSearchRepo()
    service = SearchService(repo)

    with pytest.raises(ValidationError, match="Search query is required"):
        service.search(query="", limit_per_type=10)


def test_search_whitespace_only_query():
    """Test searching with whitespace-only query raises ValidationError."""
    repo = MockSearchRepo()
    service = SearchService(repo)

    with pytest.raises(ValidationError, match="Search query is required"):
        service.search(query="   ", limit_per_type=10)


def test_search_single_character():
    """Test searching with single character raises ValidationError."""
    repo = MockSearchRepo()
    service = SearchService(repo)

    with pytest.raises(ValidationError, match="Search query must be at least 2 characters"):
        service.search(query="a", limit_per_type=10)


def test_search_minimum_length():
    """Test that search accepts queries of minimum length (2 characters)."""
    repo = MockSearchRepo()
    service = SearchService(repo)

    result = service.search(query="ab", limit_per_type=10)

    assert "parts" in result
    assert len(repo.search_parts_calls) == 1
    assert repo.search_parts_calls[0][0] == "ab"


def test_search_strips_whitespace():
    """Test that search query is stripped of leading/trailing whitespace."""
    repo = MockSearchRepo()
    service = SearchService(repo)

    # Query with whitespace should be stripped and validated
    result = service.search(query="  test  ", limit_per_type=10)

    # The service strips whitespace before validation
    assert len(repo.search_parts_calls) == 1
    # The repo receives the stripped query
    assert repo.search_parts_calls[0][0] == "test"
