"""FastAPI router for drawers endpoints."""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.adapters import row_to_drawer_summary, rows_to
from app.di import get_db_connection, get_inventory_service
from app.errors import ConflictError, DuplicateError, ValidationError
from core.dtos import DrawerSummaryDTO
from core.services.inventory_service import InventoryService
from infra.db.repositories.drawers_repo import (
    DrawersRepo,
    DuplicateLabelError,
)

router = APIRouter(prefix="/drawers", tags=["drawers"])


# Request models
class CreateDrawerRequest(BaseModel):
    name: str
    description: str | None = None


class RenameDrawerRequest(BaseModel):
    id: int
    new_name: str


class MoveDrawerRequest(BaseModel):
    id: int
    new_sort_index: int | None = None


class DeleteDrawerRequest(BaseModel):
    id: int


# Response models
class DrawerIdResponse(BaseModel):
    id: int


class DrawerUpdatedResponse(BaseModel):
    updated: int


class DrawerDeletedResponse(BaseModel):
    deleted: int


@router.get("", response_model=list[DrawerSummaryDTO])
def list_drawers(service: InventoryService = Depends(get_inventory_service)):
    """List all drawers with their container and part counts."""
    rows = service.list_drawers()
    items = rows_to(row_to_drawer_summary, rows)
    return [d.model_dump() for d in items]


@router.post("/create", response_model=DrawerIdResponse, status_code=status.HTTP_201_CREATED)
def create_drawer(
    request: CreateDrawerRequest,
    service: InventoryService = Depends(get_inventory_service),
):
    """Create a new drawer."""
    try:
        result = service.create_drawer(label=request.name, description=request.description)
        # Extract ID from result (could be dict, int, or row-like)
        drawer_id = None
        if isinstance(result, dict):
            drawer_id = result.get("id") or result.get("drawer_id") or result.get("value")
        elif isinstance(result, int):
            drawer_id = result
        else:
            # Try to get id attribute
            try:
                drawer_id = result["id"]  # type: ignore[index]
            except (KeyError, TypeError):
                try:
                    drawer_id = result["drawer_id"]  # type: ignore[index]
                except (KeyError, TypeError):
                    pass

        if drawer_id is None:
            # Fallback: try to convert to dict
            try:
                as_dict = dict(result)  # type: ignore[arg-type]
                drawer_id = as_dict.get("id") or as_dict.get("drawer_id")
            except Exception:
                raise HTTPException(
                    status_code=500, detail="Created drawer but could not extract ID"
                )

        return DrawerIdResponse(id=int(drawer_id))
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except DuplicateError as e:
        raise HTTPException(
            status_code=409,
            detail={
                "message": str(e),
                "code": "duplicate",
                "details": getattr(e, "details", None),
            },
        )


@router.post("/rename", response_model=DrawerUpdatedResponse)
def rename_drawer(
    request: RenameDrawerRequest,
    conn: sqlite3.Connection = Depends(get_db_connection),
):
    """Rename a drawer."""
    new_name = request.new_name.strip()
    if not new_name:
        raise HTTPException(status_code=422, detail="new_name is required")

    try:
        repo = DrawersRepo(conn)
        repo.rename_drawer(drawer_id=request.id, new_name=new_name)
        return DrawerUpdatedResponse(updated=request.id)
    except DuplicateLabelError as e:
        raise HTTPException(
            status_code=409,
            detail={
                "message": str(e) or "Duplicate drawer name",
                "code": "duplicate",
                "details": {"field": "name", "value": new_name},
            },
        )


@router.post("/move", response_model=DrawerUpdatedResponse)
def move_drawer(
    request: MoveDrawerRequest,
    conn: sqlite3.Connection = Depends(get_db_connection),
):
    """Move a drawer (update sort_index)."""
    try:
        repo = DrawersRepo(conn)
        repo.move_drawer(drawer_id=request.id, new_sort_index=request.new_sort_index)
        return DrawerUpdatedResponse(updated=request.id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to move drawer: {str(e)}")


@router.post("/delete", response_model=DrawerDeletedResponse)
def delete_drawer(
    request: DeleteDrawerRequest,
    service: InventoryService = Depends(get_inventory_service),
):
    """Soft delete a drawer."""
    try:
        service.delete_drawer(drawer_id=request.id)
        return DrawerDeletedResponse(deleted=request.id)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except ConflictError as e:
        raise HTTPException(
            status_code=409,
            detail={
                "message": str(e),
                "code": "conflict",
                "details": getattr(e, "details", None),
            },
        )

