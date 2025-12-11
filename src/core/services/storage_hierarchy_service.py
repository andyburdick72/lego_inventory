"""
Storage hierarchy analysis service.

Analyzes existing inventory to infer storage patterns and provide location suggestions
for putaway operations. Supports multiple storage hierarchy levels:
- Element-level (design_id + color_id)
- Part-level (design_id only)
- Category-level (part_category_id)
"""

from __future__ import annotations

from typing import Any, Protocol

from app.errors import ValidationError


class InventoryRepo(Protocol):
    """Protocol for inventory repository with storage analysis methods."""

    def find_element_location(self, design_id: str, color_id: int) -> list[dict]: ...
    def find_part_location(self, design_id: str) -> list[dict]: ...
    def find_category_location(self, part_category_id: int) -> list[dict]: ...

    # Optional analysis methods (checked with hasattr at runtime)
    def analyze_element_storage_patterns(self) -> list[dict]: ...
    def analyze_part_storage_patterns(self) -> list[dict]: ...
    def analyze_category_storage_patterns(self) -> list[dict]: ...
    def analyze_element_storage_strategies(self) -> list[dict]: ...


class PartsRepo(Protocol):
    """Protocol for parts repository."""

    def get_part(self, design_id: str) -> dict | None: ...


class StorageSuggestion:
    """A storage location suggestion with confidence level."""

    def __init__(
        self,
        container_id: int | None,
        drawer_id: int | None,
        drawer_name: str | None,
        container_name: str | None,
        confidence: str,
        reason: str,
        quantity: int = 0,
    ):
        self.container_id = container_id
        self.drawer_id = drawer_id
        self.drawer_name = drawer_name
        self.container_name = container_name
        self.confidence = confidence  # 'high', 'medium', 'low', 'none'
        self.reason = reason
        self.quantity = quantity

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "container_id": self.container_id,
            "drawer_id": self.drawer_id,
            "drawer_name": self.drawer_name,
            "container_name": self.container_name,
            "confidence": self.confidence,
            "reason": self.reason,
            "quantity": self.quantity,
        }


class StorageHierarchyService:
    """
    Service for analyzing storage patterns and suggesting locations for putaway.

    Analyzes existing inventory to infer storage hierarchy:
    - Element-level: containers storing specific design_id + color_id
    - Part-level: containers storing a design_id (any color)
    - Category-level: containers storing parts from a part_category_id
    """

    def __init__(self, inventory: InventoryRepo, parts: PartsRepo) -> None:
        self._inventory = inventory
        self._parts = parts

    def suggest_location(self, design_id: str, color_id: int) -> StorageSuggestion | None:
        """
        Suggest a storage location for a specific element (design_id + color_id).

        Returns a StorageSuggestion with confidence level:
        - 'high': Exact element match found (highest confidence)
        - 'medium': Part match found (same design_id, different color)
        - 'low': Category match found
        - 'none': No match found (returns None)

        Args:
            design_id: Part design ID
            color_id: Color ID

        Returns:
            StorageSuggestion or None if no suggestion can be made
        """
        if not design_id or not isinstance(color_id, int):
            raise ValidationError("design_id and color_id are required")

        # Level 1: Check for exact element match (high confidence)
        element_locations = self._inventory.find_element_location(design_id, color_id)
        if element_locations:
            # Use the location with the highest quantity
            best_location = max(element_locations, key=lambda x: x.get("quantity", 0))
            color_name = best_location.get("color_name", f"color {color_id}")
            return StorageSuggestion(
                container_id=best_location.get("container_id"),
                drawer_id=best_location.get("drawer_id"),
                drawer_name=best_location.get("drawer_name"),
                container_name=best_location.get("container_name"),
                confidence="high",
                reason=f"Exact element match: {design_id} in {color_name} already stored here",
                quantity=best_location.get("quantity", 0),
            )

        # Level 2: Check for part match (medium confidence)
        part_locations = self._inventory.find_part_location(design_id)
        if part_locations:
            # Use the location with the highest total quantity
            best_location = max(part_locations, key=lambda x: x.get("total_quantity", 0))
            return StorageSuggestion(
                container_id=best_location.get("container_id"),
                drawer_id=best_location.get("drawer_id"),
                drawer_name=best_location.get("drawer_name"),
                container_name=best_location.get("container_name"),
                confidence="medium",
                reason=f"Part match: {design_id} (any color) already stored here",
                quantity=best_location.get("total_quantity", 0),
            )

        # Level 3: Check for category match (low confidence)
        part_info = self._parts.get_part(design_id)
        if part_info and part_info.get("part_category_id"):
            category_id = part_info["part_category_id"]
            category_locations = self._inventory.find_category_location(category_id)
            if category_locations:
                # Use the location with the highest total quantity
                best_location = max(category_locations, key=lambda x: x.get("total_quantity", 0))
                category_name = part_info.get("part_category_name", "Unknown")
                return StorageSuggestion(
                    container_id=best_location.get("container_id"),
                    drawer_id=best_location.get("drawer_id"),
                    drawer_name=best_location.get("drawer_name"),
                    container_name=best_location.get("container_name"),
                    confidence="low",
                    reason=f"Category match: parts from '{category_name}' category stored here",
                    quantity=best_location.get("total_quantity", 0),
                )

        # No match found
        return None

    def get_all_suggestions(self, design_id: str, color_id: int) -> list[StorageSuggestion]:
        """
        Get all possible location suggestions for an element, ordered by confidence.

        Returns a list of suggestions from highest to lowest confidence.
        """
        suggestions: list[StorageSuggestion] = []

        # Level 1: Element matches (high confidence)
        element_locations = self._inventory.find_element_location(design_id, color_id)
        for loc in element_locations:
            suggestions.append(
                StorageSuggestion(
                    container_id=loc.get("container_id"),
                    drawer_id=loc.get("drawer_id"),
                    drawer_name=loc.get("drawer_name"),
                    container_name=loc.get("container_name"),
                    confidence="high",
                    reason=f"Exact element match: {design_id} in color {color_id}",
                    quantity=loc.get("quantity", 0),
                )
            )

        # Level 2: Part matches (high)
        part_locations = self._inventory.find_part_location(design_id)
        for loc in part_locations:
            # Skip if we already have this container as an element match
            if any(
                s.container_id == loc.get("container_id")
                for s in suggestions
                if s.container_id is not None
            ):
                continue
            suggestions.append(
                StorageSuggestion(
                    container_id=loc.get("container_id"),
                    drawer_id=loc.get("drawer_id"),
                    drawer_name=loc.get("drawer_name"),
                    container_name=loc.get("container_name"),
                    confidence="medium",
                    reason=f"Part match: {design_id} (any color)",
                    quantity=loc.get("total_quantity", 0),
                )
            )

        # Level 3: Category matches (medium)
        part_info = self._parts.get_part(design_id)
        if part_info and part_info.get("part_category_id"):
            category_id = part_info["part_category_id"]
            category_locations = self._inventory.find_category_location(category_id)
            for loc in category_locations:
                # Skip if we already have this container
                if any(
                    s.container_id == loc.get("container_id")
                    for s in suggestions
                    if s.container_id is not None
                ):
                    continue
                category_name = part_info.get("part_category_name", "Unknown")
                suggestions.append(
                    StorageSuggestion(
                        container_id=loc.get("container_id"),
                        drawer_id=loc.get("drawer_id"),
                        drawer_name=loc.get("drawer_name"),
                        container_name=loc.get("container_name"),
                        confidence="low",
                        reason=f"Category match: '{category_name}' category",
                        quantity=loc.get("total_quantity", 0),
                    )
                )

        # Sort by confidence (high > medium > low) and then by quantity
        confidence_order = {"high": 0, "medium": 1, "low": 2}
        suggestions.sort(
            key=lambda s: (
                confidence_order.get(s.confidence, 99),
                -s.quantity,
            )
        )

        return suggestions

    def get_element_storage_patterns(self) -> list[dict]:
        """
        Get all element-level storage patterns (containers storing specific design_id + color_id).

        Returns containers where specific elements are stored, with statistics.
        """
        if hasattr(self._inventory, "analyze_element_storage_patterns"):
            return self._inventory.analyze_element_storage_patterns()
        return []

    def get_part_storage_patterns(self) -> list[dict]:
        """
        Get all part-level storage patterns (containers storing specific design_id, any color).

        Returns containers where specific parts are stored.
        """
        if hasattr(self._inventory, "analyze_part_storage_patterns"):
            return self._inventory.analyze_part_storage_patterns()
        return []

    def get_category_storage_patterns(self) -> list[dict]:
        """
        Get all category-level storage patterns (containers storing parts from specific categories).

        Returns containers where parts from specific categories are stored.
        """
        if hasattr(self._inventory, "analyze_category_storage_patterns"):
            return self._inventory.analyze_category_storage_patterns()
        return []

    def get_element_storage_strategies(self) -> list[dict]:
        """
        Analyze how each element is stored based on container/drawer naming patterns.

        Returns a list of elements with their storage strategy:
        - 'by_element': Container name contains part number AND color description
        - 'by_part': Container name contains part number but NO color description
        - 'by_category_size': Drawer is "Really Useful" AND container has size description
        - 'by_category': Drawer is "Really Useful" AND container has NO size description
        - 'unknown': Doesn't match any pattern
        """
        if hasattr(self._inventory, "analyze_element_storage_strategies"):
            return self._inventory.analyze_element_storage_strategies()
        return []
