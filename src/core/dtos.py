from typing import Generic, TypeVar

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
    description: str | None = ""
    kind: str | None = None
    cols: int | None = None
    rows: int | None = None
    sort_index: int  # required per snapshot
    container_count: int  # required per snapshot
    part_count: int  # required per snapshot


class ContainerSummaryDTO(DTOBase):
    id: int
    name: str
    description: str | None = None
    row_index: int | None = None
    col_index: int | None = None
    sort_index: int  # required per snapshot
    is_put_away_bin: int | None = None  # 1 if this is the put away bin, 0 or None otherwise
    part_count: int  # required per snapshot
    unique_parts: int  # required per snapshot


class DrawerDTO(DTOBase):
    id: int
    name: str
    deleted: bool = False
    container_count: int | None = None


class ContainerDTO(DTOBase):
    id: int
    label: str
    drawer_id: int
    drawer_name: str | None = None
    deleted: bool = False
    parts_count: int | None = None


class LEGOSetDTO(DTOBase):
    set_number: str
    name: str
    year: int | None = None
    theme_id: int | None = None
    theme_name: str | None = None
    status: Status = Status.IN_BOX
    total_parts: int | None = None
    quantity: int = 1  # Number of copies owned
    image_url: str | None = None
    rebrickable_url: str | None = None


class InventoryItemDTO(DTOBase):
    id: int
    part_id: str
    color_id: int
    color_name: str | None = None
    color_hex: str | None = None
    quantity: int
    status: Status
    drawer_id: int | None = None
    drawer_name: str | None = None
    container_id: int | None = None
    container_label: str | None = None
    set_number: str | None = None
    set_name: str | None = None
    part_name: str | None = None
    image_url: str | None = None
    rebrickable_url: str | None = None


class PageMeta(DTOBase):
    page: int
    page_size: int
    total: int


class InventoryFilters(DTOBase):
    set_number: str | None = None
    status: Status | None = None
    drawer_id: int | None = None
    container_id: int | None = None
    color_id: int | None = None


class PaginatedResponse(DTOBase, Generic[T]):
    items: list[T]
    meta: PageMeta


class PartMismatchDTO(DTOBase):
    """Mismatch for a specific part+color in a set."""

    design_id: str
    part_name: str
    color_id: int
    color_name: str
    color_hex: str | None = None
    required_quantity: int  # From set_parts
    available_quantity: int  # From loose inventory
    delta: int  # available - required (negative = missing, positive = excess)
    part_url: str | None = None
    part_img_url: str | None = None


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
    image_url: str | None = None
    rebrickable_url: str | None = None


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
    color_hex: str | None = None
    inventory_quantity: int  # Current loose inventory total
    required_quantity: int  # Sum from set_parts for loose/teardown sets
    delta: int  # inventory - required (negative = missing, positive = excess)
    can_auto_update: (
        bool  # True if we can safely auto-update (e.g., inv=0 and required>0, or inv>required)
    )
    part_url: str | None = None
    part_img_url: str | None = None


class InventoryLocationDTO(DTOBase):
    """A single inventory location with quantity."""

    drawer_id: int | None = None
    drawer_name: str
    container_id: int | None = None
    container_name: str
    quantity: int


class LocationReconciliationItemDTO(DTOBase):
    """Reconciliation item for Loose Parts sets showing required vs current inventory locations."""

    design_id: str
    part_name: str
    color_id: int
    color_name: str
    color_hex: str | None = None
    required_quantity: int  # From set_parts for Loose Parts sets
    current_locations: list[
        InventoryLocationDTO
    ]  # Current inventory locations (excluding Put Away)
    current_total: int  # Sum of quantities in current_locations
    put_away_quantity: int  # Quantity in Put Away bin (should be 0)
    delta: int  # required_quantity - current_total (negative = missing, positive = excess)
    needs_update: bool  # True if delta != 0 or put_away_quantity > 0 or no locations
    part_url: str | None = None
    part_img_url: str | None = None


class StorageSuggestionDTO(DTOBase):
    """A storage location suggestion with confidence level."""

    container_id: int | None = None
    drawer_id: int | None = None
    drawer_name: str | None = None
    container_name: str | None = None
    confidence: str  # 'high', 'medium', 'low', 'none'
    reason: str
    quantity: int = 0


class ElementStoragePatternDTO(DTOBase):
    """Element-level storage pattern (design_id + color_id stored in a container)."""

    container_id: int
    drawer_id: int
    drawer_name: str
    container_name: str
    element_count: int  # Number of distinct elements stored here
    total_quantity: int
    is_exclusive: int  # 1 if container only stores one element, 0 otherwise (SQL returns int)


class PartStoragePatternDTO(DTOBase):
    """Part-level storage pattern (design_id stored in a container, any color)."""

    container_id: int
    drawer_id: int
    drawer_name: str
    container_name: str
    design_id: str
    part_name: str
    color_count: int  # Number of distinct colors for this part
    total_quantity: int


class CategoryStoragePatternDTO(DTOBase):
    """Category-level storage pattern (parts from a category stored in a container)."""

    container_id: int
    drawer_id: int
    drawer_name: str
    container_name: str
    part_category_id: int
    part_category_name: str | None = None
    part_count: int  # Number of distinct parts in this category
    element_count: int  # Number of distinct elements
    total_quantity: int


class ElementStorageStrategyDTO(DTOBase):
    """How a specific element (design_id + color_id) is stored based on naming patterns."""

    design_id: str
    color_id: int
    part_name: str
    part_img_url: str | None = None
    part_category_id: int | None = None
    part_category_name: str | None = None
    color_name: str
    color_hex: str | None = None
    storage_strategy: str  # 'by_element', 'by_part', 'by_category_size', 'by_category', 'unassigned', 'unknown', 'in_putaway_bin'
    drawer_id: int | None = None
    drawer_name: str | None = None
    container_id: int | None = None
    container_name: str | None = None
    quantity: int
    evidence: str  # Explanation of why it was categorized this way


class PutawayPartDTO(DTOBase):
    """A part that needs to be put away (from set part-out or putaway bin)."""

    design_id: str
    part_name: str
    color_id: int
    color_name: str
    color_hex: str | None = None
    quantity: int
    part_url: str | None = None
    part_img_url: str | None = None
    inventory_id: int | None = None  # Only for putaway bin entry point


class PutawayPartWithSuggestionDTO(PutawayPartDTO):
    """A part with its location suggestion."""

    suggestion: StorageSuggestionDTO | None = None


class BatchAssignmentRequestDTO(DTOBase):
    """Request to assign multiple parts to containers."""

    assignments: list["PartAssignmentDTO"]


class PartAssignmentDTO(DTOBase):
    """Assignment of a part to a container."""

    design_id: str
    color_id: int
    quantity: int
    container_id: int | None = None  # None = unassign (skip)
    inventory_id: int | None = (
        None  # Only for putaway bin entry point (to identify source inventory item)
    )


class BatchAssignmentResultDTO(DTOBase):
    """Result of a batch assignment operation."""

    total_requested: int
    total_assigned: int
    total_skipped: int
    assignments: list["AssignmentResultDTO"]
    errors: list[str]


class AssignmentResultDTO(DTOBase):
    """Result of a single part assignment."""

    design_id: str
    color_id: int
    quantity: int
    container_id: int | None = None
    success: bool
    message: str | None = None


# Search DTOs
class SearchPartDTO(DTOBase):
    """Search result for a part."""

    design_id: str
    name: str
    part_url: str | None = None
    part_img_url: str | None = None
    part_category_id: int | None = None
    part_category_name: str | None = None


class SearchSetDTO(DTOBase):
    """Search result for a set."""

    set_number: str
    name: str
    year: int | None = None
    theme_id: int | None = None
    theme_name: str | None = None
    status: str | None = None
    image_url: str | None = None
    rebrickable_url: str | None = None


class SearchDrawerDTO(DTOBase):
    """Search result for a drawer."""

    id: int
    name: str
    description: str | None = None


class SearchContainerDTO(DTOBase):
    """Search result for a container."""

    id: int
    name: str
    description: str | None = None
    drawer_id: int
    drawer_name: str | None = None


class SearchCategoryDTO(DTOBase):
    """Search result for a part category."""

    id: int
    name: str


class SearchResultsDTO(DTOBase):
    """Unified search results across all entity types."""

    parts: list[SearchPartDTO]
    sets: list[SearchSetDTO]
    drawers: list[SearchDrawerDTO]
    containers: list[SearchContainerDTO]
    categories: list[SearchCategoryDTO]
