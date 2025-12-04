"""FastAPI router for sets endpoints."""

import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.adapters import row_to_set, rows_to
from app.di import get_db_connection, get_set_parts_service
from app.errors import NotFoundError, ValidationError
from core.dtos import LEGOSetDTO
from core.enums import Status
from core.services.set_parts_service import SetPartsService
from infra.db.repositories.sets_repo import SetsRepo

router = APIRouter(prefix="/sets", tags=["sets"])


# Response models for parts
class SetPartDTO(BaseModel):
    design_id: str
    name: str
    color_id: int
    color_name: str
    hex: Optional[str] = None
    quantity: int
    part_url: Optional[str] = None
    part_img_url: Optional[str] = None


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

