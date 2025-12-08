"""Service for reconciling inventory with set parts based on storage locations.

Rules:
- Teardown sets: parts should be in Put Away bin
- Loose Parts sets: parts should be in inventory but NOT in Put Away bin
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Protocol

from app.errors import ValidationError
from core.enums import Status


class SetsRepo(Protocol):
    """Protocol for sets repository operations."""

    def list_sets_with_statuses(self, statuses: list[str]) -> list[Mapping[str, Any]]: ...


class SetPartsRepo(Protocol):
    """Protocol for set parts repository operations."""

    def list_for_set(self, *, set_number: str) -> Iterable[Mapping[str, Any]]: ...


class InventoryRepo(Protocol):
    """Protocol for inventory repository operations."""

    def get_inventory_by_location(
        self, design_id: str, color_id: int, drawer_id: int | None, container_id: int | None
    ) -> list[dict]: ...

    def get_inventory_totals_by_location(
        self, design_id: str, color_id: int
    ) -> list[dict]: ...

    def set_inventory_quantity_at_location(
        self,
        design_id: str,
        color_id: int,
        quantity: int,
        drawer_id: int | None,
        container_id: int | None,
    ) -> None: ...


class DrawersRepo(Protocol):
    """Protocol for drawers repository operations."""

    def get_put_away_bin(self) -> dict | None: ...


class LocationReconciliationService:
    """
    Service for reconciling inventory with set parts based on storage location rules.
    
    Rules:
    - Teardown sets: parts should be in Put Away bin
    - Loose Parts sets: parts should be in inventory but NOT in Put Away bin
    """

    def __init__(
        self,
        sets: SetsRepo,
        set_parts: SetPartsRepo,
        inventory: InventoryRepo,
        drawers: DrawersRepo,
    ) -> None:
        self._sets = sets
        self._set_parts = set_parts
        self._inventory = inventory
        self._drawers = drawers

    def _get_put_away_bin(self) -> tuple[int | None, int | None]:
        """Get the put away bin drawer_id and container_id from the database."""
        put_away = self._drawers.get_put_away_bin()
        if put_away:
            return (put_away.get("drawer_id"), put_away.get("container_id"))
        return (None, None)

    def compute_loose_parts_reconciliation_items(
        self,
    ) -> list[dict[str, Any]]:
        """
        Compute reconciliation items for Loose Parts sets showing:
        - Required quantity from set_parts
        - Current inventory locations and quantities (excluding Put Away bin)
        - Delta
        """
        put_away_drawer_id, put_away_container_id = self._get_put_away_bin()
        
        # Get all Loose Parts sets
        loose_sets = self._sets.list_sets_with_statuses(["loose_parts"])

        # Build map of required quantities from set_parts
        # Key: (design_id, color_id)
        # Value: required_quantity
        required_map: dict[tuple[str, int], int] = {}
        part_info_map: dict[tuple[str, int], dict[str, Any]] = {}

        # Process Loose Parts sets
        for set_data in loose_sets:
            set_num = str(set_data.get("set_num") or set_data.get("set_number") or "")
            if not set_num:
                continue

            set_parts = list(self._set_parts.list_for_set(set_number=set_num))
            for part in set_parts:
                # Skip parts marked to ignore in inventory
                if part.get("ignore_in_inventory", 0) == 1:
                    continue

                design_id = str(part.get("design_id", ""))
                color_id = int(part.get("color_id", 0))
                qty = int(part.get("quantity", 0))
                key = (design_id, color_id)

                required_map[key] = required_map.get(key, 0) + qty

                # Store part info
                if key not in part_info_map:
                    part_info_map[key] = {
                        "part_name": str(part.get("name", "")),
                        "color_name": str(part.get("color_name", "")),
                        "color_hex": part.get("hex"),
                        "part_url": part.get("part_url") or f"https://rebrickable.com/parts/{design_id}/",
                        "part_img_url": part.get("part_img_url") or "https://rebrickable.com/static/img/nil.png",
                    }

        # Now get current inventory locations for each part+color
        reconciliation_items: list[dict[str, Any]] = []

        for (design_id, color_id), required_qty in required_map.items():
            part_info = part_info_map.get((design_id, color_id), {})

            # Get all current inventory locations for this part+color
            all_locations = self._inventory.get_inventory_totals_by_location(design_id, color_id)
            
            # Filter out Put Away bin (shouldn't be there for Loose Parts)
            current_locations = [
                {
                    "drawer_id": loc.get("drawer_id"),
                    "drawer_name": loc.get("drawer_name") or "Unknown",
                    "container_id": loc.get("container_id"),
                    "container_name": loc.get("container_name") or "Unknown",
                    "quantity": int(loc.get("quantity", 0)),
                }
                for loc in all_locations
                if not (
                    put_away_drawer_id is not None
                    and put_away_container_id is not None
                    and loc.get("drawer_id") == put_away_drawer_id
                    and loc.get("container_id") == put_away_container_id
                )
            ]

            # Get quantity in Put Away (should be 0 for Loose Parts)
            put_away_quantity = 0
            if put_away_drawer_id is not None and put_away_container_id is not None:
                put_away_locations = self._inventory.get_inventory_by_location(
                    design_id, color_id, put_away_drawer_id, put_away_container_id
                )
                put_away_quantity = sum(loc.get("quantity", 0) for loc in put_away_locations)

            # Calculate totals
            current_total = sum(loc["quantity"] for loc in current_locations)
            delta = required_qty - current_total
            
            # Only include if there's a mismatch: loose sets total != non-put-away total
            if delta != 0:
                reconciliation_items.append({
                    "design_id": design_id,
                    "part_name": part_info.get("part_name", design_id),
                    "color_id": color_id,
                    "color_name": part_info.get("color_name", f"Color {color_id}"),
                    "color_hex": part_info.get("color_hex"),
                    "required_quantity": required_qty,
                    "current_locations": current_locations,
                    "current_total": current_total,
                    "put_away_quantity": put_away_quantity,
                    "delta": delta,
                    "needs_update": True,
                    "part_url": part_info.get("part_url"),
                    "part_img_url": part_info.get("part_img_url"),
                })

        return sorted(reconciliation_items, key=lambda x: (x["design_id"], x["color_id"]))

    def compute_teardown_reconciliation_items(
        self,
    ) -> list[dict[str, Any]]:
        """
        Compute reconciliation items for Teardown sets showing:
        - Required quantity from set_parts
        - Current inventory locations and quantities (should be in Put Away bin)
        - Delta
        """
        put_away_drawer_id, put_away_container_id = self._get_put_away_bin()
        
        if put_away_drawer_id is None or put_away_container_id is None:
            # No put away bin configured, return empty list
            return []

        # Get all Teardown sets
        teardown_sets = self._sets.list_sets_with_statuses(["teardown"])

        # Build map of required quantities from set_parts
        # Key: (design_id, color_id)
        # Value: required_quantity
        required_map: dict[tuple[str, int], int] = {}
        part_info_map: dict[tuple[str, int], dict[str, Any]] = {}

        # Process Teardown sets
        for set_data in teardown_sets:
            set_num = str(set_data.get("set_num") or set_data.get("set_number") or "")
            if not set_num:
                continue

            set_parts = list(self._set_parts.list_for_set(set_number=set_num))
            for part in set_parts:
                # Skip parts marked to ignore in inventory
                if part.get("ignore_in_inventory", 0) == 1:
                    continue

                design_id = str(part.get("design_id", ""))
                color_id = int(part.get("color_id", 0))
                qty = int(part.get("quantity", 0))
                key = (design_id, color_id)

                required_map[key] = required_map.get(key, 0) + qty

                # Store part info
                if key not in part_info_map:
                    part_info_map[key] = {
                        "part_name": str(part.get("name", "")),
                        "color_name": str(part.get("color_name", "")),
                        "color_hex": part.get("hex"),
                        "part_url": part.get("part_url") or f"https://rebrickable.com/parts/{design_id}/",
                        "part_img_url": part.get("part_img_url") or "https://rebrickable.com/static/img/nil.png",
                    }

        # Now get current inventory locations for each part+color
        reconciliation_items: list[dict[str, Any]] = []

        for (design_id, color_id), required_qty in required_map.items():
            part_info = part_info_map.get((design_id, color_id), {})

            # Get all current inventory locations for this part+color
            all_locations = self._inventory.get_inventory_totals_by_location(design_id, color_id)
            
            # Get quantity in Put Away bin (required location for Teardown)
            put_away_locations = self._inventory.get_inventory_by_location(
                design_id, color_id, put_away_drawer_id, put_away_container_id
            )
            current_qty_at_location = sum(loc.get("quantity", 0) for loc in put_away_locations)

            # Get quantity elsewhere (should be 0 for Teardown)
            current_locations_elsewhere = [
                {
                    "drawer_id": loc.get("drawer_id"),
                    "drawer_name": loc.get("drawer_name") or "Unknown",
                    "container_id": loc.get("container_id"),
                    "container_name": loc.get("container_name") or "Unknown",
                    "quantity": int(loc.get("quantity", 0)),
                }
                for loc in all_locations
                if not (
                    loc.get("drawer_id") == put_away_drawer_id
                    and loc.get("container_id") == put_away_container_id
                )
            ]
            current_qty_elsewhere = sum(loc["quantity"] for loc in current_locations_elsewhere)

            # Calculate totals
            delta = required_qty - current_qty_at_location
            
            # Only include if there's a mismatch: teardown sets total != put-away total
            if delta != 0:
                reconciliation_items.append({
                    "design_id": design_id,
                    "part_name": part_info.get("part_name", design_id),
                    "color_id": color_id,
                    "color_name": part_info.get("color_name", f"Color {color_id}"),
                    "color_hex": part_info.get("color_hex"),
                    "required_quantity": required_qty,
                    "current_locations": [
                        {
                            "drawer_id": put_away_drawer_id,
                            "drawer_name": "Put Away",
                            "container_id": put_away_container_id,
                            "container_name": "Put Away",
                            "quantity": current_qty_at_location,
                        }
                    ] if current_qty_at_location > 0 else [],
                    "current_total": current_qty_at_location,
                    "put_away_quantity": current_qty_elsewhere,  # For Teardown, this is quantity in wrong locations
                    "delta": delta,
                    "needs_update": True,
                    "part_url": part_info.get("part_url"),
                    "part_img_url": part_info.get("part_img_url"),
                })

        return sorted(reconciliation_items, key=lambda x: (x["design_id"], x["color_id"]))

    def update_inventory_location(
        self,
        design_id: str,
        color_id: int,
        quantity: int,
        drawer_id: int | None,
        container_id: int | None,
        is_teardown: bool = False,
    ) -> None:
        """
        Update inventory location for a part+color.
        
        This will:
        - Set the quantity at the specified location
        - Remove inventory from other locations for this part+color
        
        Args:
            is_teardown: If True, allows putting parts in Put Away bin. If False, prevents it.
        """
        if quantity < 0:
            raise ValidationError("Quantity cannot be negative")
        
        # Check if trying to put in Put Away bin
        put_away_drawer_id, put_away_container_id = self._get_put_away_bin()
        if put_away_drawer_id is not None and put_away_container_id is not None:
            if drawer_id == put_away_drawer_id and container_id == put_away_container_id:
                if not is_teardown:
                    raise ValidationError("Loose Parts cannot be stored in Put Away bin")
            elif is_teardown:
                # Teardown parts must be in Put Away bin
                raise ValidationError("Teardown parts must be stored in Put Away bin")

        self._inventory.set_inventory_quantity_at_location(
            design_id, color_id, quantity, drawer_id, container_id
        )
