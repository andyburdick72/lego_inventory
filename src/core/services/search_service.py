from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from app.errors import ValidationError


class SearchRepo(Protocol):
    def search_parts(self, query: str, limit: int = 10) -> list[Mapping[str, Any]]: ...
    def search_sets(self, query: str, limit: int = 10) -> list[Mapping[str, Any]]: ...
    def search_drawers(self, query: str, limit: int = 10) -> list[Mapping[str, Any]]: ...
    def search_containers(self, query: str, limit: int = 10) -> list[Mapping[str, Any]]: ...
    def search_categories(self, query: str, limit: int = 10) -> list[Mapping[str, Any]]: ...


class SearchService:
    """Service for global search across all entities."""

    def __init__(self, search_repo: SearchRepo) -> None:
        self._search_repo = search_repo

    def search(self, *, query: str, limit_per_type: int = 10):
        """
        Search across all entity types.

        Args:
            query: Search query string
            limit_per_type: Maximum number of results per entity type

        Returns:
            Dictionary with results grouped by type
        """
        query = (query or "").strip()
        if not query:
            raise ValidationError("Search query is required")

        if len(query) < 2:
            raise ValidationError("Search query must be at least 2 characters")

        return {
            "parts": self._search_repo.search_parts(query, limit=limit_per_type),
            "sets": self._search_repo.search_sets(query, limit=limit_per_type),
            "drawers": self._search_repo.search_drawers(query, limit=limit_per_type),
            "containers": self._search_repo.search_containers(query, limit=limit_per_type),
            "categories": self._search_repo.search_categories(query, limit=limit_per_type),
        }
