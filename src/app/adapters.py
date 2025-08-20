from collections.abc import Callable, Iterable, Mapping

from core.dtos import ContainerDTO, DrawerDTO, InventoryItemDTO, LEGOSetDTO
from core.enums import Status


def row_to_drawer(row: Mapping) -> DrawerDTO:
    return DrawerDTO(
        id=int(row.get("id") or 0),
        name=row.get("name") or "",
        deleted=bool(row.get("deleted", 0)),
        container_count=row.get("container_count"),
    )


def row_to_container(row: Mapping) -> ContainerDTO:
    return ContainerDTO(
        id=int(row.get("id") or 0),
        label=row.get("label") or "",
        drawer_id=int(row.get("drawer_id") or 0),
        drawer_name=row.get("drawer_name"),
        deleted=bool(row.get("deleted", 0)),
        parts_count=row.get("parts_count"),
    )


def row_to_set(row: Mapping) -> LEGOSetDTO:
    return LEGOSetDTO(
        set_number=str(row.get("set_number") or ""),
        name=str(row.get("name") or ""),
        year=row.get("year"),
        theme=row.get("theme"),
        status=Status.from_any(row.get("status")) or Status.IN_BOX,
        total_parts=row.get("total_parts"),
        image_url=row.get("image_url"),
        rebrickable_url=row.get("rebrickable_url"),
    )


def row_to_inventory_item(row: Mapping) -> InventoryItemDTO:
    status = Status.from_any(row.get("status")) or Status.LOOSE
    return InventoryItemDTO(
        part_id=str(row.get("part_id") or ""),
        color_id=int(row.get("color_id") or 0),
        color_name=row.get("color_name"),
        quantity=row.get("quantity", row.get("qty", 0)),
        status=status,
        drawer_id=row.get("drawer_id"),
        drawer_name=row.get("drawer_name"),
        container_id=row.get("container_id"),
        container_label=row.get("container_label"),
        set_number=row.get("set_number"),
        set_name=row.get("set_name"),
        part_name=row.get("part_name"),
        image_url=row.get("image_url"),
        rebrickable_url=row.get("rebrickable_url"),
    )


def rows_to(dto_fn: Callable[[Mapping], object], rows: Iterable[Mapping]) -> list[object]:
    return [dto_fn(row) for row in rows]
