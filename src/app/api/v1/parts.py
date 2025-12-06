"""FastAPI router for parts endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.adapters import row_to_inventory_item, rows_to
from app.di import get_db_connection, get_inventory_service, get_parts_service, get_set_parts_service
from app.errors import NotFoundError, ValidationError
from core.dtos import DTOBase, InventoryItemDTO
from core.services.inventory_service import InventoryService
from core.services.parts_service import PartsService
from core.services.set_parts_service import SetPartsService

router = APIRouter(prefix="/parts", tags=["parts"])


# Response models
class PartDTO(DTOBase):
    """Part metadata DTO."""

    design_id: str
    name: str
    part_url: str
    part_img_url: str
    # TODO: Add part categories later - API fetching is too slow
    # part_category_id: Optional[int] = None
    # part_category_name: Optional[str] = None


class PartInSetDTO(DTOBase):
    """Part in set DTO."""

    set_number: str
    set_name: str
    status: Optional[str] = None
    color_id: int
    color_name: str
    hex: Optional[str] = None
    quantity: int
    part_category_id: Optional[int] = None
    part_category_name: Optional[str] = None


@router.get("/{design_id}", response_model=PartDTO)
def get_part(
    design_id: str,
    service: PartsService = Depends(get_parts_service),
):
    """Get part metadata by design ID."""
    try:
        part_data = service.get_part(design_id=design_id)
        # Ensure URLs are present
        part_url = part_data.get("part_url")
        if not part_url:
            part_url = f"https://rebrickable.com/parts/{part_data.get('design_id', '')}/"

        part_img_url = part_data.get("part_img_url")
        if not part_img_url:
            part_img_url = "https://rebrickable.com/static/img/nil.png"

        part = PartDTO(
            design_id=str(part_data.get("design_id", "")),
            name=str(part_data.get("name", "")),
            part_url=part_url,
            part_img_url=part_img_url,
            # TODO: Add part categories later
            # part_category_id=part_data.get("part_category_id"),
            # part_category_name=part_data.get("part_category_name"),
        )
        return part.model_dump()
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


@router.get("/{design_id}/loose", response_model=list[InventoryItemDTO])
def get_loose_inventory_for_part(
    design_id: str,
    service: InventoryService = Depends(get_inventory_service),
):
    """Get all loose inventory items for a specific part."""
    try:
        rows = service.loose_inventory_for_part(design_id)
        items = rows_to(row_to_inventory_item, rows)
        return [d.model_dump() for d in items]
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/{design_id}/sets", response_model=list[PartInSetDTO])
def get_sets_for_part(
    design_id: str,
    service: SetPartsService = Depends(get_set_parts_service),
):
    """Get all sets that contain a specific part, with per-color detail."""
    try:
        sets_data = service.sets_for_part_with_colors(design_id=design_id)
        result = [
            PartInSetDTO(
                set_number=str(s.get("set_num", "") or s.get("set_number", "")),
                set_name=str(s.get("set_name", "") or s.get("name", "")),
                status=s.get("status"),
                color_id=int(s.get("color_id", 0)),
                color_name=str(s.get("color_name", "")),
                hex=s.get("hex"),
                quantity=int(s.get("quantity", 0)),
                part_category_id=s.get("part_category_id"),
                part_category_name=s.get("part_category_name"),
            )
            for s in sets_data
        ]
        return [s.model_dump() for s in result]
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))

