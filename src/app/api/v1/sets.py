"""FastAPI router for sets endpoints."""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.adapters import row_to_set, row_to_set_copy, rows_to
from app.di import get_db_connection, get_inventory_service, get_set_parts_service
from app.errors import NotFoundError, ValidationError
from core.dtos import LEGOSetCopyDTO, LEGOSetDTO
from core.enums import Status
from core.services.inventory_service import InventoryService
from core.services.set_parts_service import SetPartsService
from infra.db.repositories.drawers_repo import DrawersRepo
from infra.db.repositories.sets_repo import SetsRepo
from app.settings import get_settings

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


def _apply_set_status_change_triggers(
    *,
    conn: sqlite3.Connection,
    inventory_service: InventoryService,
    previous_status: str | None,
    new_status: str,
    set_number: str,
) -> None:
    """
    Apply the inventory side-effects for set status changes.

    IMPORTANT: This operates on *one physical copy* worth of parts (one `set_parts` bill of materials).
    """
    drawers_repo = DrawersRepo(conn)

    # Get putaway bin container_id if needed
    putaway_bin = drawers_repo.get_put_away_bin()
    putaway_bin_container_id = putaway_bin.get("container_id") if putaway_bin else None

    sets_repo = SetsRepo(conn)
    set_parts = list(sets_repo.list_parts_for_set(set_number))

    # Trigger 1: Loose → Teardown: Move all set parts from storage to Put Away bin
    if previous_status in ("loose_parts", "loose") and new_status == "teardown":
        if putaway_bin_container_id:
            for part in set_parts:
                design_id = str(part.get("design_id", ""))
                color_id = int(part.get("color_id", 0))
                # Get all inventory items for this part+color (with IDs)
                inventory_rows = conn.execute(
                    """
                    SELECT i.id, i.container_id, i.quantity
                    FROM inventory i
                    WHERE i.design_id = ? AND i.color_id = ? AND i.status = 'loose'
                    """,
                    (design_id, color_id),
                ).fetchall()
                for row in inventory_rows:
                    inventory_id = row["id"] if isinstance(row, dict) else row[0]
                    container_id = row["container_id"] if isinstance(row, dict) else row[1]
                    quantity = row["quantity"] if isinstance(row, dict) else row[2]
                    # Only move if not already in putaway bin
                    if (
                        inventory_id
                        and container_id != putaway_bin_container_id
                        and quantity > 0
                    ):
                        inventory_service.move_inventory(
                            from_inventory_id=inventory_id,
                            to_container_id=putaway_bin_container_id,
                            quantity=quantity,
                        )

    # Trigger 2: Loose → Other: Remove all set parts from storage locations
    elif previous_status in ("loose_parts", "loose") and new_status not in (
        "loose_parts",
        "loose",
        "teardown",
    ):
        for part in set_parts:
            design_id = str(part.get("design_id", ""))
            color_id = int(part.get("color_id", 0))
            # Get all inventory items for this part+color (with IDs)
            inventory_rows = conn.execute(
                """
                SELECT i.id
                FROM inventory i
                WHERE i.design_id = ? AND i.color_id = ? AND i.status = 'loose'
                """,
                (design_id, color_id),
            ).fetchall()
            for row in inventory_rows:
                inventory_id = row["id"] if isinstance(row, dict) else row[0]
                if inventory_id:
                    inventory_service.delete_inventory_item(inventory_id=inventory_id)

    # Trigger 3: Other → Teardown: Add all set parts to Put Away bin
    elif previous_status not in ("loose_parts", "loose", "teardown") and new_status == "teardown":
        if putaway_bin_container_id:
            for part in set_parts:
                design_id = str(part.get("design_id", ""))
                color_id = int(part.get("color_id", 0))
                quantity = int(part.get("quantity", 0))
                # Check if ignore_in_inventory flag is set
                if part.get("ignore_in_inventory", 0) == 1:
                    continue
                # Check if inventory item already exists for this part+color in putaway bin
                existing_row = conn.execute(
                    """
                    SELECT i.id, i.quantity
                    FROM inventory i
                    WHERE i.design_id = ? AND i.color_id = ? AND i.status = 'loose'
                      AND i.container_id = ?
                    LIMIT 1
                    """,
                    (design_id, color_id, putaway_bin_container_id),
                ).fetchone()
                if existing_row:
                    # Update quantity
                    existing_id = (
                        existing_row["id"] if isinstance(existing_row, dict) else existing_row[0]
                    )
                    existing_qty = (
                        existing_row["quantity"]
                        if isinstance(existing_row, dict)
                        else existing_row[1]
                    )
                    new_qty = existing_qty + quantity
                    inventory_service.update_inventory_quantity(inventory_id=existing_id, quantity=new_qty)
                else:
                    # Create new inventory item
                    conn.execute(
                        """
                        INSERT INTO inventory (design_id, color_id, quantity, status, container_id)
                        VALUES (?, ?, ?, 'loose', ?)
                        """,
                        (design_id, color_id, quantity, putaway_bin_container_id),
                    )
                    conn.commit()

    # Trigger 4: Teardown → Loose: Move all set parts from storage to Put Away bin
    elif previous_status == "teardown" and new_status in ("loose_parts", "loose"):
        if putaway_bin_container_id:
            for part in set_parts:
                design_id = str(part.get("design_id", ""))
                color_id = int(part.get("color_id", 0))
                # Check if ignore_in_inventory flag is set
                if part.get("ignore_in_inventory", 0) == 1:
                    continue
                # Get all inventory items for this part+color
                inventory_rows = conn.execute(
                    """
                    SELECT i.id, i.container_id, i.quantity
                    FROM inventory i
                    WHERE i.design_id = ? AND i.color_id = ? AND i.status = 'loose'
                    """,
                    (design_id, color_id),
                ).fetchall()
                for row in inventory_rows:
                    inventory_id = row["id"] if isinstance(row, dict) else row[0]
                    container_id = row["container_id"] if isinstance(row, dict) else row[1]
                    quantity = row["quantity"] if isinstance(row, dict) else row[2]
                    # Only move if not already in putaway bin
                    if (
                        inventory_id
                        and container_id != putaway_bin_container_id
                        and quantity > 0
                    ):
                        inventory_service.move_inventory(
                            from_inventory_id=inventory_id,
                            to_container_id=putaway_bin_container_id,
                            quantity=quantity,
                        )


@router.get("/count")
def get_sets_count(conn: sqlite3.Connection = Depends(get_db_connection)):  # noqa: B008
    """Get the total count of sets."""
    row = conn.execute("SELECT COUNT(*) AS count FROM sets").fetchone()
    count = row["count"] if isinstance(row, dict) else row[0] if row else 0
    return {"count": count}


@router.get("/copies", response_model=list[LEGOSetCopyDTO])
def list_set_copies(conn: sqlite3.Connection = Depends(get_db_connection)):  # noqa: B008
    """List all set copies (one row per physical copy)."""
    sets_repo = SetsRepo(conn)
    rows = sets_repo.list_set_copies()
    rows_as_dicts = [dict(r) for r in rows]
    items = rows_to(row_to_set_copy, [{"set_number": r.get("set_num"), **r} for r in rows_as_dicts])
    return [d.model_dump() for d in items]


@router.get("/{set_number}/copies", response_model=list[LEGOSetCopyDTO])
def list_set_copies_for_set(
    set_number: str, conn: sqlite3.Connection = Depends(get_db_connection)  # noqa: B008
):
    """List all copies for a specific set number (one row per physical copy)."""
    sets_repo = SetsRepo(conn)
    rows = sets_repo.list_set_copies_by_num(set_number)
    if not rows:
        raise HTTPException(
            status_code=404,
            detail={
                "message": f"Set {set_number} not found",
                "code": "not_found",
            },
        )
    rows_as_dicts = [dict(r) for r in rows]
    items = rows_to(row_to_set_copy, [{"set_number": r.get("set_num"), **r} for r in rows_as_dicts])
    return [d.model_dump() for d in items]


@router.get("", response_model=list[LEGOSetDTO])
def list_sets(conn: sqlite3.Connection = Depends(get_db_connection)):  # noqa: B008
    """List all sets with their metadata."""
    rows = conn.execute(
        """
        SELECT
            s.set_num AS set_number,
            s.name,
            s.year,
            s.theme_id,
            t.name AS theme_name,
            -- Use the most recent status (or first one if all have same added_at)
            (SELECT status FROM sets s2 WHERE s2.set_num = s.set_num ORDER BY s2.added_at DESC LIMIT 1) AS status,
            s.image_url,
            s.rebrickable_url,
            (
              SELECT COALESCE(SUM(sp.quantity), 0)
              FROM set_parts sp
              WHERE sp.set_num = s.set_num
            ) AS total_parts,
            COUNT(*) AS quantity
        FROM sets s
        LEFT JOIN themes t ON t.id = s.theme_id
        GROUP BY s.set_num, s.name, s.year, s.theme_id, t.name, s.image_url, s.rebrickable_url
        ORDER BY MAX(s.added_at) DESC
        """
    ).fetchall()

    # Convert rows to dict format expected by row_to_set
    rows_as_dicts = [dict(row) for row in rows]
    items = rows_to(row_to_set, rows_as_dicts)
    return [d.model_dump() for d in items]


@router.get("/{set_number}", response_model=LEGOSetDTO)
def get_set(
    set_number: str,
    service: SetPartsService = Depends(get_set_parts_service),  # noqa: B008
    conn: sqlite3.Connection = Depends(get_db_connection),  # noqa: B008
):
    """Get a specific set by set number."""
    try:
        set_data = service.get_set(set_number=set_number)
        # Convert to DTO format
        status_value = set_data.get("status")
        status_enum = Status.from_any(status_value) if status_value else Status.IN_BOX

        # Get quantity (count of rows for this set_num)
        quantity_row = conn.execute(
            "SELECT COUNT(*) AS quantity FROM sets WHERE set_num = ?",
            (set_number,),
        ).fetchone()
        quantity = quantity_row["quantity"] if isinstance(quantity_row, dict) else (quantity_row[0] if quantity_row else 1)

        dto = LEGOSetDTO(
            set_number=str(set_data.get("set_number") or set_data.get("set_num") or ""),
            name=str(set_data.get("name") or ""),
            year=set_data.get("year"),
            theme_id=set_data.get("theme_id"),
            theme_name=set_data.get("theme_name"),
            status=status_enum,
            total_parts=None,  # Not included in get_set response
            quantity=quantity,
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
        ) from e
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.get("/{set_number}/parts", response_model=list[SetPartDTO])
def get_set_parts(
    set_number: str,
    service: SetPartsService = Depends(get_set_parts_service),  # noqa: B008
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
        raise HTTPException(status_code=422, detail=str(e)) from e
    except NotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail={
                "message": str(e),
                "code": "not_found",
                "details": getattr(e, "details", None),
            },
        ) from e


@router.patch("/{set_number}/status")
def update_set_status(
    set_number: str,
    request: UpdateSetStatusRequest,
    conn: sqlite3.Connection = Depends(get_db_connection),  # noqa: B008
    inventory_service: InventoryService = Depends(get_inventory_service),  # noqa: B008
):
    """
    Update the status of a set.

    NOTE: If multiple copies exist for this set number, this endpoint returns 409 and you must
    update a specific copy via PATCH /sets/copies/{set_id}/status.
    """
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
        ) from e

    # Check if set exists and whether it's ambiguous (multiple copies)
    copies_row = conn.execute(
        "SELECT COUNT(*) AS quantity FROM sets WHERE set_num = ?",
        (set_number,),
    ).fetchone()
    copies = (
        copies_row["quantity"]
        if isinstance(copies_row, dict)
        else (copies_row[0] if copies_row else 0)
    )
    if copies == 0:
        raise HTTPException(
            status_code=404,
            detail={
                "message": f"Set {set_number} not found",
                "code": "not_found",
            },
        )
    if copies > 1:
        raise HTTPException(
            status_code=409,
            detail={
                "message": (
                    f"Set {set_number} has {copies} copies; update a specific copy via "
                    "PATCH /sets/copies/{set_id}/status"
                ),
                "code": "conflict",
            },
        )

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
            ) from e
        # Other operational errors
        raise HTTPException(
            status_code=500,
            detail={
                "message": f"Database error: {error_msg}",
                "code": "internal_error",
            },
        ) from e
    except Exception as e:
        # Other database errors - return 500
        raise HTTPException(
            status_code=500,
            detail={
                "message": f"Error checking set existence: {str(e)}",
                "code": "internal_error",
            },
        ) from e

    if not existing_set:
        raise HTTPException(
            status_code=404,
            detail={
                "message": f"Set {set_number} not found",
                "code": "not_found",
            },
        )

    # Get previous status for status change triggers
    previous_status = existing_set.get("status")
    new_status = status_enum.value

    # Update status (single copy)
    try:
        set_id = int(existing_set.get("id") or 0)
        if set_id <= 0:
            raise ValueError("Invalid set id")
        sets_repo.update_set_by_id(set_id, status=new_status)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "message": f"Error updating set status: {str(e)}",
                "code": "internal_error",
            },
        ) from e

    # In set-centric safe mode we keep set status updates functional, but we *skip*
    # any location-dependent inventory side-effects.
    if get_settings().safe_mode:
        return {"updated": set_number, "status": status_enum.value}

    # Handle status change triggers (location-dependent)
    try:
        _apply_set_status_change_triggers(
            conn=conn,
            inventory_service=inventory_service,
            previous_status=previous_status,
            new_status=new_status,
            set_number=set_number,
        )
    except Exception as e:
        # Log error but don't fail the status update
        import traceback

        print(f"Warning: Error handling status change triggers: {e}")
        traceback.print_exc()

    return {"updated": set_number, "status": status_enum.value}


@router.patch("/copies/{set_id}/status")
def update_set_copy_status(
    set_id: int,
    request: UpdateSetStatusRequest,
    conn: sqlite3.Connection = Depends(get_db_connection),  # noqa: B008
    inventory_service: InventoryService = Depends(get_inventory_service),  # noqa: B008
):
    """Update the status for a specific set copy (by id)."""
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
        ) from e

    sets_repo = SetsRepo(conn)
    existing = sets_repo.get_set(set_id)
    if not existing:
        raise HTTPException(
            status_code=404,
            detail={"message": f"Set copy {set_id} not found", "code": "not_found"},
        )

    previous_status = existing.get("status")
    new_status = status_enum.value
    set_number = str(existing.get("set_num") or "")
    if not set_number:
        raise HTTPException(
            status_code=500,
            detail={"message": "Set copy is missing set_num", "code": "internal_error"},
        )

    try:
        sets_repo.update_set_by_id(set_id, status=new_status)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "message": f"Error updating set copy status: {str(e)}",
                "code": "internal_error",
            },
        ) from e

    if get_settings().safe_mode:
        return {"updated": set_id, "set_number": set_number, "status": new_status}

    try:
        _apply_set_status_change_triggers(
            conn=conn,
            inventory_service=inventory_service,
            previous_status=previous_status,
            new_status=new_status,
            set_number=set_number,
        )
    except Exception as e:
        import traceback

        print(f"Warning: Error handling status change triggers: {e}")
        traceback.print_exc()

    return {"updated": set_id, "set_number": set_number, "status": new_status}


@router.get("/{set_number}/parts-locations", response_model=list[SetPartWithLocationsDTO])
def get_set_parts_with_locations(
    set_number: str,
    set_parts_service: SetPartsService = Depends(get_set_parts_service),  # noqa: B008
    inventory_service: InventoryService = Depends(get_inventory_service),  # noqa: B008
):
    """Get all parts for a set with their inventory locations.

    For each part required by the set, returns:
    - Required quantity (from set_parts)
    - Available quantity (sum of loose inventory)
    - List of locations where the part is stored (drawer/container)
    """
    try:
        # First verify the set exists
        set_parts_service.get_set(set_number=set_number)

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
        raise HTTPException(status_code=422, detail=str(e)) from e
    except NotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail={
                "message": str(e),
                "code": "not_found",
                "details": getattr(e, "details", None),
            },
        ) from e
