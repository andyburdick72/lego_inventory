"""FastAPI router for inventory endpoints."""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.adapters import row_to_inventory_item, rows_to
from app.di import get_db_connection, get_inventory_service
from app.errors import NotFoundError, ValidationError
from core.dtos import InventoryItemDTO
from core.services.inventory_service import InventoryService
from infra.db.repositories.inventory_repo import InventoryRepo

router = APIRouter(prefix="/inventory", tags=["inventory"])


# Response models
class PartCountDTO(BaseModel):
    design_id: str
    part_name: str
    total_qty: int
    part_url: str | None = None
    part_img_url: str | None = None
    part_category_id: int | None = None
    part_category_name: str | None = None


class PartColorCountDTO(BaseModel):
    design_id: str
    part_name: str
    color_id: int
    color_name: str
    hex: str | None = None
    total_qty: int
    part_url: str | None = None
    part_img_url: str | None = None


class LocationCountDTO(BaseModel):
    location: str
    total_qty: int
    drawer_id: int | None = None
    drawer_name: str | None = None
    container_id: int | None = None
    container_name: str | None = None


class ElementLocationDTO(BaseModel):
    drawer_id: int | None = None
    drawer_name: str | None = None
    container_id: int | None = None
    container_name: str | None = None
    quantity: int
    inventory_id: int | None = None


class MultipleLocationsElementDTO(BaseModel):
    design_id: str
    part_name: str
    color_id: int
    color_name: str
    color_hex: str | None = None
    part_url: str | None = None
    part_img_url: str | None = None
    location_count: int
    total_quantity: int
    locations: list[ElementLocationDTO]


class TotalPartCountDTO(BaseModel):
    total_count: int


@router.get("/total-count", response_model=TotalPartCountDTO)
def get_total_part_count(conn: sqlite3.Connection = Depends(get_db_connection)):
    """Get total part count across all sets (all set parts, regardless of set status)."""
    # Match the calculation used by the Sets API: sum total_parts for each set
    row = conn.execute(
        """
        SELECT 
            COALESCE(SUM(
                (SELECT COALESCE(SUM(sp.quantity), 0)
                 FROM set_parts sp
                 WHERE sp.set_num = s.set_num)
            ), 0) AS total_count
        FROM sets s
        """
    ).fetchone()

    total_count = int(row["total_count"] or 0) if row else 0
    return TotalPartCountDTO(total_count=total_count)


@router.get("/loose", response_model=list[InventoryItemDTO])
def list_loose_inventory(conn: sqlite3.Connection = Depends(get_db_connection)):
    """List all loose inventory items."""
    rows = conn.execute(
        """
        SELECT  i.id,
                i.design_id AS part_id,
                i.color_id,
                c.name AS color_name,
                c.hex AS color_hex,
                i.quantity,
                i.status,
                COALESCE(d.name, i.drawer) AS drawer_name,
                d.id AS drawer_id,
                COALESCE(c2.name, i.container) AS container_label,
                c2.id AS container_id,
                NULL AS set_number,
                NULL AS set_name,
                p.name AS part_name,
                p.part_img_url AS image_url,
                p.part_url AS rebrickable_url
        FROM inventory i
        JOIN parts  p ON p.design_id = i.design_id
        JOIN colors c ON c.id = i.color_id
        LEFT JOIN containers c2 ON i.container_id = c2.id
        LEFT JOIN drawers d ON c2.drawer_id = d.id
        WHERE i.status = 'loose'
        ORDER BY i.quantity DESC, p.design_id, i.color_id
        """
    ).fetchall()

    rows_as_dicts = [dict(row) for row in rows]
    items = rows_to(row_to_inventory_item, rows_as_dicts)
    return [d.model_dump() for d in items]


@router.get("/part-counts", response_model=list[PartCountDTO])
def get_part_counts(conn: sqlite3.Connection = Depends(get_db_connection)):
    """Get total part counts across all sets (all set parts, regardless of set status).

    This matches the calculation used by the Part Detail page: join with sets table.
    """
    rows = conn.execute(
        """
        SELECT sp.design_id,
               MAX(p.name) AS part_name,
               MAX(p.part_url) AS part_url,
               MAX(p.part_img_url) AS part_img_url,
               MAX(p.part_category_id) AS part_category_id,
               MAX(pc.name) AS part_category_name,
               SUM(sp.quantity) AS total_qty
        FROM set_parts sp
        JOIN sets s ON s.set_num = sp.set_num
        LEFT JOIN parts p ON sp.design_id = p.design_id
        LEFT JOIN part_categories pc ON pc.id = p.part_category_id
        GROUP BY sp.design_id
        ORDER BY total_qty DESC
        """
    ).fetchall()

    result = []
    for r in rows:
        # Convert Row to dict for easier access
        row_dict = dict(r)
        part_url = row_dict.get("part_url")
        if not part_url and row_dict.get("design_id"):
            part_url = f"https://rebrickable.com/parts/{row_dict['design_id']}/"

        part_img_url = row_dict.get("part_img_url")
        if not part_img_url:
            part_img_url = "https://rebrickable.com/static/img/nil.png"

        part_category_id = row_dict.get("part_category_id")
        part_category_name = row_dict.get("part_category_name")

        result.append(
            PartCountDTO(
                design_id=str(row_dict.get("design_id", "")),
                part_name=str(row_dict.get("part_name", "")),
                total_qty=int(row_dict.get("total_qty", 0)),
                part_url=part_url,
                part_img_url=part_img_url,
                part_category_id=int(part_category_id) if part_category_id is not None else None,
                part_category_name=str(part_category_name) if part_category_name else None,
            )
        )
    return result


@router.get("/part-color-counts", response_model=list[PartColorCountDTO])
def get_part_color_counts(conn: sqlite3.Connection = Depends(get_db_connection)):
    """Get part counts grouped by part and color across all sets (all set parts, regardless of set status).

    This matches the calculation used by the Part Counts page: join with sets table.
    """
    rows = conn.execute(
        """
        SELECT sp.design_id,
               MAX(p.name) AS part_name,
               sp.color_id,
               MAX(c.name) AS color_name,
               MAX(c.hex) AS color_hex,
               MAX(p.part_url) AS part_url,
               MAX(p.part_img_url) AS part_img_url,
               SUM(sp.quantity) AS total_qty
        FROM set_parts sp
        JOIN sets s ON s.set_num = sp.set_num
        LEFT JOIN parts p ON sp.design_id = p.design_id
        LEFT JOIN colors c ON c.id = sp.color_id
        GROUP BY sp.design_id, sp.color_id
        ORDER BY total_qty DESC
        """
    ).fetchall()

    result = []
    for r in rows:
        # Convert Row to dict for easier access
        row_dict = dict(r)
        design_id = str(row_dict.get("design_id", ""))
        color_id = row_dict.get("color_id")
        hex_value = row_dict.get("color_hex")
        if hex_value:
            hex_value = hex_value.lstrip("#")

        part_url = row_dict.get("part_url")
        if not part_url and design_id and color_id:
            part_url = f"https://rebrickable.com/parts/{design_id}/{int(color_id)}/"
        elif not part_url and design_id:
            part_url = f"https://rebrickable.com/parts/{design_id}/"

        part_img_url = row_dict.get("part_img_url")
        if not part_img_url:
            part_img_url = "https://rebrickable.com/static/img/nil.png"

        result.append(
            PartColorCountDTO(
                design_id=design_id,
                part_name=str(row_dict.get("part_name", "")),
                color_id=int(color_id or 0),
                color_name=str(row_dict.get("color_name", "") or "(unknown)"),
                hex=hex_value,
                total_qty=int(row_dict.get("total_qty", 0)),
                part_url=part_url,
                part_img_url=part_img_url,
            )
        )
    return result


@router.get("/location-counts", response_model=list[LocationCountDTO])
def get_location_counts(conn: sqlite3.Connection = Depends(get_db_connection)):
    """Get inventory totals grouped by storage location, sorted by quantity descending."""
    rows = conn.execute(
        """
        SELECT
            d.id AS drawer_id,
            d.name AS drawer_name,
            c.id AS container_id,
            c.name AS container_name,
            SUM(i.quantity) AS total_quantity
        FROM inventory i
        LEFT JOIN containers c ON c.id = i.container_id
        LEFT JOIN drawers d ON d.id = c.drawer_id
        WHERE i.status = 'loose'
            AND (c.deleted_at IS NULL OR c.id IS NULL)
            AND (d.deleted_at IS NULL OR d.id IS NULL)
        GROUP BY d.id, d.name, c.id, c.name
        ORDER BY total_quantity DESC
        """
    ).fetchall()

    result = []
    for r in rows:
        row_dict = dict(r)
        drawer_id = row_dict.get("drawer_id")
        drawer_name = row_dict.get("drawer_name") or ""
        container_id = row_dict.get("container_id")
        container_name = row_dict.get("container_name") or ""

        if drawer_name and container_name:
            location = f"{drawer_name} / {container_name}"
        elif drawer_name:
            location = drawer_name
        elif container_name:
            location = container_name
        else:
            location = "(unknown)"

        result.append(
            LocationCountDTO(
                location=location,
                total_qty=int(row_dict.get("total_quantity", 0) or 0),
                drawer_id=int(drawer_id) if drawer_id else None,
                drawer_name=drawer_name if drawer_name else None,
                container_id=int(container_id) if container_id else None,
                container_name=container_name if container_name else None,
            )
        )
    return result


# Request models for CRUD operations
class UpdateInventoryQuantityRequest(BaseModel):
    quantity: int


class UpdateInventoryLocationRequest(BaseModel):
    container_id: int | None = None


class MoveInventoryRequest(BaseModel):
    to_container_id: int | None = None
    quantity: int


# Response models
class InventoryUpdatedResponse(BaseModel):
    id: int
    message: str = "Inventory updated successfully"


class InventoryDeletedResponse(BaseModel):
    id: int
    message: str = "Inventory deleted successfully"


class InventoryMovedResponse(BaseModel):
    from_id: int
    to_container_id: int | None = None
    quantity: int
    message: str = "Inventory moved successfully"


@router.get("/loose/{inventory_id}", response_model=InventoryItemDTO)
def get_loose_inventory_item(
    inventory_id: int,
    service: InventoryService = Depends(get_inventory_service),
):
    """Get a single loose inventory item by ID."""
    try:
        item = service.get_inventory_item(inventory_id)
        return row_to_inventory_item(item)
    except NotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail={
                "message": str(e),
                "code": "not_found",
                "details": getattr(e, "details", None),
            },
        )
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.patch("/loose/{inventory_id}/quantity", response_model=InventoryUpdatedResponse)
def update_inventory_quantity(
    inventory_id: int,
    request: UpdateInventoryQuantityRequest,
    service: InventoryService = Depends(get_inventory_service),
):
    """Update the quantity of a loose inventory item."""
    try:
        service.update_inventory_quantity(inventory_id=inventory_id, quantity=request.quantity)
        return InventoryUpdatedResponse(id=inventory_id)
    except NotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail={
                "message": str(e),
                "code": "not_found",
                "details": getattr(e, "details", None),
            },
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=422,
            detail={
                "message": str(e),
                "code": "validation_error",
            },
        )


@router.patch("/loose/{inventory_id}/location", response_model=InventoryUpdatedResponse)
def update_inventory_location(
    inventory_id: int,
    request: UpdateInventoryLocationRequest,
    service: InventoryService = Depends(get_inventory_service),
):
    """Update the location (container_id) of a loose inventory item."""
    try:
        service.update_inventory_location(
            inventory_id=inventory_id, container_id=request.container_id
        )
        return InventoryUpdatedResponse(id=inventory_id)
    except NotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail={
                "message": str(e),
                "code": "not_found",
                "details": getattr(e, "details", None),
            },
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=422,
            detail={
                "message": str(e),
                "code": "validation_error",
            },
        )


@router.delete("/loose/{inventory_id}", response_model=InventoryDeletedResponse)
def delete_inventory_item(
    inventory_id: int,
    service: InventoryService = Depends(get_inventory_service),
):
    """Delete a loose inventory item."""
    try:
        service.delete_inventory_item(inventory_id=inventory_id)
        return InventoryDeletedResponse(id=inventory_id)
    except NotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail={
                "message": str(e),
                "code": "not_found",
                "details": getattr(e, "details", None),
            },
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=422,
            detail={
                "message": str(e),
                "code": "validation_error",
            },
        )


@router.post("/loose/{inventory_id}/move", response_model=InventoryMovedResponse)
def move_inventory(
    inventory_id: int,
    request: MoveInventoryRequest,
    service: InventoryService = Depends(get_inventory_service),
):
    """Move a quantity of parts from one inventory item to another location."""
    try:
        service.move_inventory(
            from_inventory_id=inventory_id,
            to_container_id=request.to_container_id,
            quantity=request.quantity,
        )
        return InventoryMovedResponse(
            from_id=inventory_id,
            to_container_id=request.to_container_id,
            quantity=request.quantity,
        )
    except NotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail={
                "message": str(e),
                "code": "not_found",
                "details": getattr(e, "details", None),
            },
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=422,
            detail={
                "message": str(e),
                "code": "validation_error",
            },
        )


@router.get("/multiple-locations", response_model=list[MultipleLocationsElementDTO])
def get_elements_in_multiple_locations(conn: sqlite3.Connection = Depends(get_db_connection)):
    """Get elements (part + color) that exist in multiple non-put-away-bin locations."""
    repo = InventoryRepo(conn)
    elements = repo.elements_in_multiple_locations()

    # Convert to DTOs
    result = []
    for elem in elements:
        locations = [
            ElementLocationDTO(
                drawer_id=loc.get("drawer_id"),
                drawer_name=loc.get("drawer_name"),
                container_id=loc.get("container_id"),
                container_name=loc.get("container_name"),
                quantity=int(loc.get("quantity", 0)),
                inventory_id=loc.get("inventory_id"),
            )
            for loc in elem.get("locations", [])
        ]

        result.append(
            MultipleLocationsElementDTO(
                design_id=elem["design_id"],
                part_name=elem["part_name"],
                color_id=int(elem["color_id"]),
                color_name=elem["color_name"],
                color_hex=elem.get("color_hex"),
                part_url=elem.get("part_url"),
                part_img_url=elem.get("part_img_url"),
                location_count=int(elem["location_count"]),
                total_quantity=int(elem["total_quantity"]),
                locations=locations,
            )
        )

    return result
