"""FastAPI router for sets endpoints."""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.adapters import row_to_set, rows_to
from app.di import get_db_connection, get_inventory_service, get_set_parts_service
from app.errors import NotFoundError, ValidationError
from core.dtos import LEGOSetDTO
from core.enums import Status
from core.services.inventory_service import InventoryService
from core.services.set_parts_service import SetPartsService
from infra.db.repositories.sets_repo import SetsRepo

router = APIRouter(prefix="/sets", tags=["sets"])


# Response models for parts
class SetPartDTO(BaseModel):
    design_id: str
    name: str
    color_id: int
    color_name: str
    hex: str | None = None
    quantity: int
    part_url: str | None = None
    part_img_url: str | None = None


class PartLocationDTO(BaseModel):
    drawer_id: int | None = None
    drawer_name: str | None = None
    container_id: int | None = None
    container_name: str | None = None
    quantity: int


class SetPartWithLocationsDTO(BaseModel):
    design_id: str
    name: str
    color_id: int
    color_name: str
    hex: str | None = None
    required_quantity: int
    available_quantity: int
    locations: list[PartLocationDTO]
    part_url: str | None = None
    part_img_url: str | None = None


# Request models
class UpdateSetStatusRequest(BaseModel):
    status: str


@router.get("/count")
def get_sets_count(conn: sqlite3.Connection = Depends(get_db_connection)):
    """Get the total count of sets."""
    row = conn.execute("SELECT COUNT(*) AS count FROM sets").fetchone()
    count = row["count"] if isinstance(row, dict) else row[0] if row else 0
    return {"count": count}


@router.get("", response_model=list[LEGOSetDTO])
def list_sets(conn: sqlite3.Connection = Depends(get_db_connection)):
    """List all sets with their metadata."""
    rows = conn.execute(
        """
        SELECT
            s.set_num AS set_number,
            s.name,
            s.year,
            s.theme,
            s.status,
            s.image_url,
            s.rebrickable_url,
            (
              SELECT COALESCE(SUM(sp.quantity), 0)
              FROM set_parts sp
              WHERE sp.set_num = s.set_num
            ) AS total_parts
        FROM sets s
        ORDER BY s.added_at DESC
        """
    ).fetchall()

    # Convert rows to dict format expected by row_to_set
    rows_as_dicts = [dict(row) for row in rows]
    items = rows_to(row_to_set, rows_as_dicts)
    return [d.model_dump() for d in items]


@router.get("/{set_number}", response_model=LEGOSetDTO)
def get_set(
    set_number: str,
    service: SetPartsService = Depends(get_set_parts_service),
):
    """Get a specific set by set number."""
    try:
        set_data = service.get_set(set_number=set_number)
        # Convert to DTO format
        status_value = set_data.get("status")
        status_enum = Status.from_any(status_value) if status_value else Status.IN_BOX

        dto = LEGOSetDTO(
            set_number=str(set_data.get("set_number") or set_data.get("set_num") or ""),
            name=str(set_data.get("name") or ""),
            year=set_data.get("year"),
            theme=set_data.get("theme"),
            status=status_enum,
            total_parts=None,  # Not included in get_set response
            image_url=set_data.get("image_url"),
            rebrickable_url=set_data.get("rebrickable_url"),
        )
        return dto.model_dump()
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


@router.get("/{set_number}/parts", response_model=list[SetPartDTO])
def get_set_parts(
    set_number: str,
    service: SetPartsService = Depends(get_set_parts_service),
):
    """Get all parts for a specific set."""
    try:
        parts = list(service.list_parts(set_number=set_number))
        result = []
        for part in parts:
            # Ensure URLs are present
            part_url = part.get("part_url")
            if not part_url:
                part_url = f"https://rebrickable.com/parts/{part.get('design_id', '')}/"

            part_img_url = part.get("part_img_url")
            if not part_img_url:
                part_img_url = "https://rebrickable.com/static/img/nil.png"

            result.append(
                SetPartDTO(
                    design_id=str(part.get("design_id", "")),
                    name=str(part.get("name", "")),
                    color_id=int(part.get("color_id", 0)),
                    color_name=str(part.get("color_name", "")),
                    hex=part.get("hex"),
                    quantity=int(part.get("quantity", 0)),
                    part_url=part_url,
                    part_img_url=part_img_url,
                )
            )
        return [p.model_dump() for p in result]
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail={
                "message": str(e),
                "code": "not_found",
                "details": getattr(e, "details", None),
            },
        )


@router.patch("/{set_number}/status")
def update_set_status(
    set_number: str,
    request: UpdateSetStatusRequest,
    conn: sqlite3.Connection = Depends(get_db_connection),
):
    """Update the status of a set."""
    # Validate status first
    try:
        status_enum = Status.from_any(request.status)
    except ValueError as e:
        raise HTTPException(
            status_code=422,
            detail={
                "message": f"Invalid status: {str(e)}",
                "code": "validation_error",
            },
        )

    # Check if set exists
    sets_repo = SetsRepo(conn)
    try:
        existing_set = sets_repo.get_set_by_num(set_number)
    except sqlite3.OperationalError as e:
        # Database schema error (e.g., table doesn't exist) - return 500
        error_msg = str(e)
        if "no such table" in error_msg.lower():
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "Database schema error: sets table not found",
                    "code": "internal_error",
                },
            )
        # Other operational errors
        raise HTTPException(
            status_code=500,
            detail={
                "message": f"Database error: {error_msg}",
                "code": "internal_error",
            },
        )
    except Exception as e:
        # Other database errors - return 500
        raise HTTPException(
            status_code=500,
            detail={
                "message": f"Error checking set existence: {str(e)}",
                "code": "internal_error",
            },
        )

    if not existing_set:
        raise HTTPException(
            status_code=404,
            detail={
                "message": f"Set {set_number} not found",
                "code": "not_found",
            },
        )

    # Update status
    try:
        sets_repo.update_set_by_num(set_number, status=status_enum.value)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "message": f"Error updating set status: {str(e)}",
                "code": "internal_error",
            },
        )

    return {"updated": set_number, "status": status_enum.value}


@router.get("/{set_number}/parts-locations", response_model=list[SetPartWithLocationsDTO])
def get_set_parts_with_locations(
    set_number: str,
    set_parts_service: SetPartsService = Depends(get_set_parts_service),
    inventory_service: InventoryService = Depends(get_inventory_service),
):
    """Get all parts for a set with their inventory locations.

    For each part required by the set, returns:
    - Required quantity (from set_parts)
    - Available quantity (sum of loose inventory)
    - List of locations where the part is stored (drawer/container)
    """
    try:
        # Get all parts required by the set
        parts = list(set_parts_service.list_parts(set_number=set_number))

        result = []
        for part in parts:
            design_id = str(part.get("design_id", ""))
            color_id = int(part.get("color_id", 0))
            required_qty = int(part.get("quantity", 0))

            # Get inventory locations for this part+color
            locations = inventory_service.loose_inventory_for_part_color(design_id, color_id)

            # Calculate total available quantity
            available_qty = sum(loc.get("quantity", 0) for loc in locations)

            # Format locations
            location_dtos = [
                PartLocationDTO(
                    drawer_id=loc.get("drawer_id"),
                    drawer_name=loc.get("drawer_name"),
                    container_id=loc.get("container_id"),
                    container_name=loc.get("container_name"),
                    quantity=int(loc.get("quantity", 0)),
                )
                for loc in locations
            ]

            # Ensure URLs are present
            part_url = part.get("part_url")
            if not part_url:
                part_url = f"https://rebrickable.com/parts/{design_id}/"

            part_img_url = part.get("part_img_url")
            if not part_img_url:
                part_img_url = "https://rebrickable.com/static/img/nil.png"

            hex_value = part.get("hex")
            if hex_value:
                hex_value = hex_value.lstrip("#")

            result.append(
                SetPartWithLocationsDTO(
                    design_id=design_id,
                    name=str(part.get("name", "")),
                    color_id=color_id,
                    color_name=str(part.get("color_name", "")),
                    hex=hex_value,
                    required_quantity=required_qty,
                    available_quantity=available_qty,
                    locations=location_dtos,
                    part_url=part_url,
                    part_img_url=part_img_url,
                )
            )

        return [p.model_dump() for p in result]
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail={
                "message": str(e),
                "code": "not_found",
                "details": getattr(e, "details", None),
            },
        )
