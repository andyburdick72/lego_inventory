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
    theme: Optional[str] = None
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
