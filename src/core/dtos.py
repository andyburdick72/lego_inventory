from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, ConfigDict

from core.enums import Status

T = TypeVar("T")


class DTOBase(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore",
    )


class DrawerSummaryDTO(DTOBase):
    id: int
    name: str
    description: Optional[str] = ""
    kind: Optional[str] = None
    cols: Optional[int] = None
    rows: Optional[int] = None
    sort_index: int  # required per snapshot
    container_count: int  # required per snapshot
    part_count: int  # required per snapshot


class ContainerSummaryDTO(DTOBase):
    id: int
    name: str
    description: Optional[str] = None
    row_index: Optional[int] = None
    col_index: Optional[int] = None
    sort_index: int  # required per snapshot
    is_put_away_bin: Optional[int] = None  # 1 if this is the put away bin, 0 or None otherwise
    part_count: int  # required per snapshot
    unique_parts: int  # required per snapshot


class DrawerDTO(DTOBase):
    id: int
    name: str
    deleted: bool = False
    container_count: Optional[int] = None


class ContainerDTO(DTOBase):
    id: int
    label: str
    drawer_id: int
    drawer_name: Optional[str] = None
    deleted: bool = False
    parts_count: Optional[int] = None


class LEGOSetDTO(DTOBase):
    set_number: str
    name: str
    year: Optional[int] = None
    theme_id: Optional[int] = None
    theme_name: Optional[str] = None
    status: Status = Status.IN_BOX
    total_parts: Optional[int] = None
    image_url: Optional[str] = None
    rebrickable_url: Optional[str] = None


class InventoryItemDTO(DTOBase):
    part_id: str
    color_id: int
    color_name: Optional[str] = None
    color_hex: Optional[str] = None
    quantity: int
    status: Status
    drawer_id: Optional[int] = None
    drawer_name: Optional[str] = None
    container_id: Optional[int] = None
    container_label: Optional[str] = None
    set_number: Optional[str] = None
    set_name: Optional[str] = None
    part_name: Optional[str] = None
    image_url: Optional[str] = None
    rebrickable_url: Optional[str] = None


class PageMeta(DTOBase):
    page: int
    page_size: int
    total: int


class InventoryFilters(DTOBase):
    set_number: Optional[str] = None
    status: Optional[Status] = None
    drawer_id: Optional[int] = None
    container_id: Optional[int] = None
    color_id: Optional[int] = None


class PaginatedResponse(DTOBase, Generic[T]):
    items: list[T]
    meta: PageMeta


class PartMismatchDTO(DTOBase):
    """Mismatch for a specific part+color in a set."""
    design_id: str
    part_name: str
    color_id: int
    color_name: str
    color_hex: Optional[str] = None
    required_quantity: int  # From set_parts
    available_quantity: int  # From loose inventory
    delta: int  # available - required (negative = missing, positive = excess)
    part_url: Optional[str] = None
    part_img_url: Optional[str] = None


class SetMismatchDTO(DTOBase):
    """Mismatch summary for a single set."""
    set_number: str
    set_name: str
    status: Status
    total_parts: int  # Total parts in set
    missing_parts_count: int  # Number of parts with negative delta
    excess_parts_count: int  # Number of parts with positive delta
    total_missing_quantity: int  # Sum of negative deltas
    total_excess_quantity: int  # Sum of positive deltas
    mismatches: list[PartMismatchDTO]
    image_url: Optional[str] = None
    rebrickable_url: Optional[str] = None


class MismatchSummaryDTO(DTOBase):
    """Overall summary of mismatches."""
    total_sets: int
    sets_with_mismatches: int
    total_missing_parts: int
    total_excess_parts: int
    total_missing_quantity: int
    total_excess_quantity: int


class PartColorMismatchDTO(DTOBase):
    """Mismatch at the part+color level (like sanity_checks.py output)."""
    design_id: str
    part_name: str
    color_id: int
    color_name: str
    color_hex: Optional[str] = None
    inventory_quantity: int  # Current loose inventory total
    required_quantity: int  # Sum from set_parts for loose/teardown sets
    delta: int  # inventory - required (negative = missing, positive = excess)
    can_auto_update: bool  # True if we can safely auto-update (e.g., inv=0 and required>0, or inv>required)
    part_url: Optional[str] = None
    part_img_url: Optional[str] = None


class InventoryLocationDTO(DTOBase):
    """A single inventory location with quantity."""
    drawer_id: Optional[int] = None
    drawer_name: str
    container_id: Optional[int] = None
    container_name: str
    quantity: int


class LocationReconciliationItemDTO(DTOBase):
    """Reconciliation item for Loose Parts sets showing required vs current inventory locations."""
    design_id: str
    part_name: str
    color_id: int
    color_name: str
    color_hex: Optional[str] = None
    required_quantity: int  # From set_parts for Loose Parts sets
    current_locations: list[InventoryLocationDTO]  # Current inventory locations (excluding Put Away)
    current_total: int  # Sum of quantities in current_locations
    put_away_quantity: int  # Quantity in Put Away bin (should be 0)
    delta: int  # required_quantity - current_total (negative = missing, positive = excess)
    needs_update: bool  # True if delta != 0 or put_away_quantity > 0 or no locations
    part_url: Optional[str] = None
    part_img_url: Optional[str] = None
