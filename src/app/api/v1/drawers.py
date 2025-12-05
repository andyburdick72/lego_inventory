"""FastAPI router for drawers endpoints."""

import sqlite3
from typing import Optional

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
    description: Optional[str] = None
    rows: Optional[int] = None
    cols: Optional[int] = None


class RenameDrawerRequest(BaseModel):
    id: int
    new_name: str
    description: Optional[str] = None
    rows: Optional[int] = None
    cols: Optional[int] = None


class MoveDrawerRequest(BaseModel):
    id: int
    new_sort_index: Optional[int] = None


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


@router.get("/{drawer_id}", response_model=DrawerSummaryDTO)
def get_drawer(
    drawer_id: int,
    service: InventoryService = Depends(get_inventory_service),
):
    """Get a single drawer by ID with its container and part counts."""
    rows = service.list_drawers()
    items = rows_to(row_to_drawer_summary, rows)
    drawer = next((d for d in items if d.id == drawer_id), None)
    if not drawer:
        raise HTTPException(status_code=404, detail="Drawer not found")
    return drawer.model_dump()


@router.post("/create", response_model=DrawerIdResponse, status_code=status.HTTP_201_CREATED)
def create_drawer(
    request: CreateDrawerRequest,
    conn: sqlite3.Connection = Depends(get_db_connection),
):
    """Create a new drawer."""
    # Validate name is not blank or whitespace-only
    if not request.name or not request.name.strip():
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Drawer name cannot be blank",
                "code": "validation_error",
                "details": {"field": "name", "value": request.name},
            },
        )
    
    try:
        repo = DrawersRepo(conn)
        drawer_id = repo.create_drawer(
            name=request.name.strip(),
            description=request.description,
            rows=request.rows,
            cols=request.cols,
        )
        return DrawerIdResponse(id=drawer_id)
    except ValueError as e:
        # Repository-level validation (e.g., blank name after normalization)
        raise HTTPException(
            status_code=422,
            detail={
                "message": str(e),
                "code": "validation_error",
                "details": {"field": "name", "value": request.name},
            },
        )
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except DuplicateLabelError as e:
        raise HTTPException(
            status_code=409,
            detail={
                "message": str(e) or "Duplicate drawer name",
                "code": "duplicate",
                "details": {"field": "name", "value": request.name},
            },
        )


@router.post("/rename", response_model=DrawerUpdatedResponse)
def rename_drawer(
    request: RenameDrawerRequest,
    conn: sqlite3.Connection = Depends(get_db_connection),
):
    """Update a drawer's name and optionally description."""
    new_name = request.new_name.strip()
    if not new_name:
        raise HTTPException(status_code=422, detail="new_name is required")

    try:
        repo = DrawersRepo(conn)
        # Always use update_drawer since it properly excludes the current drawer from duplicate check
        # and supports updating both name and description
        description = None
        if request.description is not None:
            description = request.description.strip() or None
        repo.update_drawer(
            drawer_id=request.id,
            new_name=new_name,
            description=description,
            rows=request.rows,
            cols=request.cols,
        )
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

