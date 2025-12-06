"""Service for computing inventory/set mismatches."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Protocol

from app.errors import ValidationError
from core.dtos import MismatchSummaryDTO, PartMismatchDTO, PartColorMismatchDTO, SetMismatchDTO
from core.enums import Status


class SetsRepo(Protocol):
    """Protocol for sets repository operations."""

    def get(self, *, set_number: str) -> Mapping[str, Any] | None: ...

    def list_sets_with_statuses(self, statuses: list[str]) -> list[Mapping[str, Any]]: ...


class SetPartsRepo(Protocol):
    """Protocol for set parts repository operations."""

    def list_for_set(self, *, set_number: str) -> Iterable[Mapping[str, Any]]: ...


class InventoryRepo(Protocol):
    """Protocol for inventory repository operations."""

    def loose_inventory_for_part_color(self, design_id: str, color_id: int) -> list[dict]: ...

    def get_loose_inventory_totals(self) -> list[dict]: ...

    def get_part_color_info(self, design_id: str, color_id: int) -> dict | None: ...

    def update_loose_inventory_quantity(
        self, design_id: str, color_id: int, new_quantity: int
    ) -> None: ...


class MismatchService:
    """
    Service for computing mismatches between set parts and loose inventory.
    
    For sets with status 'loose' or 'teardown', compares the parts required
    by the set against available loose inventory to identify missing/excess parts.
    """

    def __init__(
        self,
        sets: SetsRepo,
        set_parts: SetPartsRepo,
        inventory: InventoryRepo,
    ) -> None:
        self._sets = sets
        self._set_parts = set_parts
        self._inventory = inventory

    def compute_mismatches(
        self,
        *,
        set_number: str | None = None,
        statuses: list[str] | None = None,
    ) -> list[SetMismatchDTO]:
        """
        Compute mismatches for sets.
        
        Args:
            set_number: If provided, only compute for this specific set
            statuses: If provided, only compute for sets with these statuses.
                     Defaults to ['loose', 'teardown']
        
        Returns:
            List of SetMismatchDTO objects, one per set with mismatches
        """
        if statuses is None:
            statuses = ["loose", "teardown"]

        # Get sets to analyze
        if set_number:
            # For a specific set, get it from the sets repo
            # We need to check if it has the right status
            set_data = self._sets.get(set_number=set_number)
            if not set_data:
                return []
            # Check if status matches
            set_status = str(set_data.get("status", ""))
            if set_status not in statuses:
                return []
            sets_to_analyze = [set_data]
        else:
            sets_to_analyze = self._sets.list_sets_with_statuses(statuses)

        results: list[SetMismatchDTO] = []

        for set_data in sets_to_analyze:
            # Handle both "set_num" and "set_number" field names
            set_num = str(set_data.get("set_num") or set_data.get("set_number") or "")
            if not set_num:
                continue

            mismatch = self._compute_set_mismatch(set_num, set_data)
            if mismatch:
                results.append(mismatch)

        return results

    def _compute_set_mismatch(
        self, set_number: str, set_data: Mapping[str, Any]
    ) -> SetMismatchDTO | None:
        """Compute mismatch for a single set."""
        # Get all parts required by the set
        set_parts = list(self._set_parts.list_for_set(set_number=set_number))
        if not set_parts:
            return None

        mismatches: list[PartMismatchDTO] = []
        total_parts = 0
        missing_parts_count = 0
        excess_parts_count = 0
        total_missing_quantity = 0
        total_excess_quantity = 0

        for part in set_parts:
            design_id = str(part.get("design_id", ""))
            color_id = int(part.get("color_id", 0))
            required_qty = int(part.get("quantity", 0))
            total_parts += required_qty

            # Get available quantity from loose inventory
            locations = self._inventory.loose_inventory_for_part_color(design_id, color_id)
            available_qty = sum(loc.get("quantity", 0) for loc in locations)

            delta = available_qty - required_qty

            # Only include if there's a mismatch
            if delta != 0:
                if delta < 0:
                    missing_parts_count += 1
                    total_missing_quantity += abs(delta)
                else:
                    excess_parts_count += 1
                    total_excess_quantity += delta

                # Get part URLs
                part_url = part.get("part_url")
                if not part_url:
                    part_url = f"https://rebrickable.com/parts/{design_id}/"

                part_img_url = part.get("part_img_url")
                if not part_img_url:
                    part_img_url = "https://rebrickable.com/static/img/nil.png"

                hex_value = part.get("hex")
                if hex_value:
                    hex_value = str(hex_value).lstrip("#")

                mismatches.append(
                    PartMismatchDTO(
                        design_id=design_id,
                        part_name=str(part.get("name", "")),
                        color_id=color_id,
                        color_name=str(part.get("color_name", "")),
                        color_hex=hex_value,
                        required_quantity=required_qty,
                        available_quantity=available_qty,
                        delta=delta,
                        part_url=part_url,
                        part_img_url=part_img_url,
                    )
                )

        # Only return if there are mismatches
        if not mismatches:
            return None

        # Parse status
        status_str = str(set_data.get("status", "in_box"))
        try:
            status = Status.from_any(status_str)
        except ValueError:
            status = Status.IN_BOX

        return SetMismatchDTO(
            set_number=set_number,
            set_name=str(set_data.get("name", "")),
            status=status,
            total_parts=total_parts,
            missing_parts_count=missing_parts_count,
            excess_parts_count=excess_parts_count,
            total_missing_quantity=total_missing_quantity,
            total_excess_quantity=total_excess_quantity,
            mismatches=mismatches,
            image_url=set_data.get("image_url"),
            rebrickable_url=set_data.get("rebrickable_url"),
        )

    def compute_summary(
        self, *, statuses: list[str] | None = None
    ) -> MismatchSummaryDTO:
        """
        Compute overall summary of mismatches.
        
        Args:
            statuses: Set statuses to analyze. Defaults to ['loose', 'teardown']
        
        Returns:
            MismatchSummaryDTO with aggregate statistics
        """
        if statuses is None:
            statuses = ["loose", "teardown"]

        sets_to_analyze = self._sets.list_sets_with_statuses(statuses)
        total_sets = len(sets_to_analyze)

        sets_with_mismatches = 0
        total_missing_parts = 0
        total_excess_parts = 0
        total_missing_quantity = 0
        total_excess_quantity = 0

        for set_data in sets_to_analyze:
            set_num = str(set_data.get("set_num") or set_data.get("set_number") or "")
            if not set_num:
                continue

            mismatch = self._compute_set_mismatch(set_num, set_data)
            if mismatch:
                sets_with_mismatches += 1
                total_missing_parts += mismatch.missing_parts_count
                total_excess_parts += mismatch.excess_parts_count
                total_missing_quantity += mismatch.total_missing_quantity
                total_excess_quantity += mismatch.total_excess_quantity

        return MismatchSummaryDTO(
            total_sets=total_sets,
            sets_with_mismatches=sets_with_mismatches,
            total_missing_parts=total_missing_parts,
            total_excess_parts=total_excess_parts,
            total_missing_quantity=total_missing_quantity,
            total_excess_quantity=total_excess_quantity,
        )

    def compute_part_color_mismatches(
        self, *, statuses: list[str] | None = None
    ) -> list[PartColorMismatchDTO]:
        """
        Compute mismatches at the part+color level (like inventory_sanity_checks.py).
        
        Compares:
        - Loose inventory totals (grouped by design_id, color_id)
        - Set parts totals for loose/teardown sets (grouped by design_id, color_id)
        
        Args:
            statuses: Set statuses to analyze. Defaults to ['loose', 'teardown']
        
        Returns:
            List of PartColorMismatchDTO objects for each part+color with a mismatch
        """
        if statuses is None:
            statuses = ["loose", "teardown"]

        # Get loose inventory totals grouped by part+color
        inv_totals = self._inventory.get_loose_inventory_totals()
        inv_map: dict[tuple[str, int], int] = {}
        for row in inv_totals:
            design_id = str(row.get("design_id", ""))
            color_id = int(row.get("color_id", 0))
            qty = int(row.get("quantity", 0))
            inv_map[(design_id, color_id)] = qty

        # Get set parts totals for loose/teardown sets
        sets_to_analyze = self._sets.list_sets_with_statuses(statuses)
        set_parts_map: dict[tuple[str, int], int] = {}
        part_info_map: dict[tuple[str, int], dict[str, Any]] = {}

        for set_data in sets_to_analyze:
            set_num = str(set_data.get("set_num") or set_data.get("set_number") or "")
            if not set_num:
                continue

            set_parts = list(self._set_parts.list_for_set(set_number=set_num))
            for part in set_parts:
                design_id = str(part.get("design_id", ""))
                color_id = int(part.get("color_id", 0))
                qty = int(part.get("quantity", 0))
                key = (design_id, color_id)

                set_parts_map[key] = set_parts_map.get(key, 0) + qty

                # Store part info if not already stored
                if key not in part_info_map:
                    part_url = part.get("part_url")
                    if not part_url:
                        part_url = f"https://rebrickable.com/parts/{design_id}/"

                    part_img_url = part.get("part_img_url")
                    if not part_img_url:
                        part_img_url = "https://rebrickable.com/static/img/nil.png"

                    hex_value = part.get("hex")
                    if hex_value:
                        hex_value = str(hex_value).lstrip("#")

                    part_info_map[key] = {
                        "part_name": str(part.get("name", "")),
                        "color_name": str(part.get("color_name", "")),
                        "color_hex": hex_value,
                        "part_url": part_url,
                        "part_img_url": part_img_url,
                    }

        # Find mismatches
        mismatches: list[PartColorMismatchDTO] = []
        all_keys = set(inv_map.keys()) | set(set_parts_map.keys())

        for key in all_keys:
            design_id, color_id = key
            inv_qty = inv_map.get(key, 0)
            required_qty = set_parts_map.get(key, 0)
            delta = inv_qty - required_qty

            # Only include if there's a mismatch
            if delta != 0:
                part_info = part_info_map.get(key, {})
                
                # If we don't have part info (e.g., inventory exists but no set parts),
                # try to fetch it from the database
                if not part_info:
                    try:
                        db_info = self._inventory.get_part_color_info(design_id, color_id)
                        if db_info:
                            part_info = {
                                "part_name": str(db_info.get("part_name", design_id)),
                                "color_name": str(db_info.get("color_name", f"Color {color_id}")),
                                "color_hex": db_info.get("color_hex"),
                                "part_url": db_info.get("part_url"),
                                "part_img_url": db_info.get("part_img_url"),
                            }
                        else:
                            # Fallback if we can't find part info
                            part_info = {
                                "part_name": design_id,
                                "color_name": f"Color {color_id}",
                                "color_hex": None,
                                "part_url": f"https://rebrickable.com/parts/{design_id}/",
                                "part_img_url": "https://rebrickable.com/static/img/nil.png",
                            }
                    except Exception:
                        # Fallback if there's an error fetching part info
                        part_info = {
                            "part_name": design_id,
                            "color_name": f"Color {color_id}",
                            "color_hex": None,
                            "part_url": f"https://rebrickable.com/parts/{design_id}/",
                            "part_img_url": "https://rebrickable.com/static/img/nil.png",
                        }
                
                # Determine if auto-update is safe
                # Safe cases:
                # 1. No inventory but required > 0 (we can add)
                # 2. Inventory > required (we can reduce to match)
                # 3. Inventory < required but we have some (manual review needed - might be in other locations)
                can_auto_update = (
                    inv_qty == 0 and required_qty > 0
                ) or (
                    inv_qty > required_qty
                )

                mismatches.append(
                    PartColorMismatchDTO(
                        design_id=design_id,
                        part_name=part_info.get("part_name", design_id),
                        color_id=color_id,
                        color_name=part_info.get("color_name", f"Color {color_id}"),
                        color_hex=part_info.get("color_hex"),
                        inventory_quantity=inv_qty,
                        required_quantity=required_qty,
                        delta=delta,
                        can_auto_update=can_auto_update,
                        part_url=part_info.get("part_url"),
                        part_img_url=part_info.get("part_img_url"),
                    )
                )

        return sorted(mismatches, key=lambda x: (x.design_id, x.color_id))

    def update_inventory_quantity(
        self, design_id: str, color_id: int, new_quantity: int
    ) -> None:
        """
        Update the total loose inventory quantity for a part+color.
        
        This will adjust all inventory records for this part+color to sum to new_quantity.
        If new_quantity is 0, all records are removed.
        If there are multiple inventory records, they are consolidated.
        """
        if new_quantity < 0:
            raise ValidationError("Quantity cannot be negative")

        self._inventory.update_loose_inventory_quantity(design_id, color_id, new_quantity)

