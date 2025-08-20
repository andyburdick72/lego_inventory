from pydantic import BaseModel, ConfigDict

from core.enums import Status


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
    theme: str | None = None
    status: Status = Status.IN_BOX
    total_parts: int | None = None
    image_url: str | None = None
    rebrickable_url: str | None = None


class InventoryItemDTO(DTOBase):
    part_id: str
    color_id: int
    color_name: str | None = None
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


class PaginatedResponse[T](DTOBase):
    items: list[T]
    meta: PageMeta
