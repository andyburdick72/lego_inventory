from pydantic import BaseModel, ConfigDict

from core.enums import Status


class DTOBase(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        alias_generator=lambda s: "".join(
            ["_" + c.lower() if c.isupper() else c for c in s]
        ).lstrip("_"),
        str_strip_whitespace=True,
        strict=True,
    )


class DrawerDTO(DTOBase):
    id: int
    name: str
    deleted: bool
    container_count: int


class ContainerDTO(DTOBase):
    id: int
    label: str
    drawer_id: int
    drawer_name: str
    deleted: bool
    parts_count: int


class LEGOSetDTO(DTOBase):
    set_number: str
    name: str
    year: int
    theme: str
    status: Status
    total_parts: int
    image_url: str | None = None
    rebrickable_url: str | None = None


class InventoryItemDTO(DTOBase):
    part_id: str
    color_id: int
    color_name: str
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
    total_items: int
    total_pages: int


class InventoryFilters(DTOBase):
    set_number: str | None = None
    status: Status | None = None
    drawer_id: int | None = None
    container_id: int | None = None
    color_id: int | None = None


class PaginatedResponse[T](DTOBase):
    items: list[T]
    meta: PageMeta
