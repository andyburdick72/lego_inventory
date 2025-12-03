"""FastAPI router for containers endpoints."""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.adapters import row_to_container_summary, rows_to
from app.di import get_db_connection, get_inventory_service
from app.errors import ConflictError, DuplicateError, ValidationError
from core.dtos import ContainerSummaryDTO
from core.services.inventory_service import InventoryService
from infra.db import inventory_db
from infra.db.inventory_db import InventoryConstraintError
from infra.db.repositories.drawers_repo import DrawersRepo, DuplicateLabelError

router = APIRouter(prefix="/containers", tags=["containers"])


# Request models
class CreateContainerRequest(BaseModel):
    drawer_id: int
    name: str
    description: str | None = None
    row_index: int | None = None
    col_index: int | None = None
    sort_index: int | None = None


class RenameContainerRequest(BaseModel):
    id: int
    new_name: str


class MoveContainerRequest(BaseModel):
    id: int
    new_drawer_id: int | None = None
    row_index: int | None = None
    col_index: int | None = None
    sort_index: int | None = None


class DeleteContainerRequest(BaseModel):
    id: int


# Response models
class ContainerIdResponse(BaseModel):
    id: int


class ContainerUpdatedResponse(BaseModel):
    updated: int


class ContainerDeletedResponse(BaseModel):
    deleted: int


@router.get("", response_model=list[ContainerSummaryDTO])
def list_containers(
    drawer_id: int = Query(..., description="Drawer ID to list containers for"),
    service: InventoryService = Depends(get_inventory_service),
):
    """List all containers for a drawer with their part counts."""
    rows = service.list_containers(filters={"drawer_id": drawer_id})
    items = rows_to(row_to_container_summary, rows)
    return [d.model_dump() for d in items]


@router.post("/create", response_model=ContainerIdResponse, status_code=status.HTTP_201_CREATED)
def create_container(
    request: CreateContainerRequest,
    conn: sqlite3.Connection = Depends(get_db_connection),
):
    """Create a new container in a drawer."""
    try:
        repo = DrawersRepo(conn)
        container_id = repo.create_container(
            drawer_id=request.drawer_id,
            name=request.name.strip(),
            description=request.description,
            row_index=request.row_index,
            col_index=request.col_index,
            sort_index=request.sort_index,
        )
        return ContainerIdResponse(id=container_id)
    except DuplicateLabelError as e:
        raise HTTPException(
            status_code=409,
            detail={
                "message": str(e) or "Duplicate label in this drawer",
                "code": "duplicate",
            },
        )
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


@router.post("/rename", response_model=ContainerUpdatedResponse)
def rename_container(
    request: RenameContainerRequest,
    conn: sqlite3.Connection = Depends(get_db_connection),
):
    """Rename a container."""
    new_name = request.new_name.strip()
    if not new_name:
        raise HTTPException(status_code=422, detail="new_name is required")

    try:
        repo = DrawersRepo(conn)
        repo.rename_container(container_id=request.id, new_name=new_name)
        return ContainerUpdatedResponse(updated=request.id)
    except DuplicateLabelError as e:
        raise HTTPException(
            status_code=409,
            detail={
                "message": str(e) or "Duplicate label in this drawer",
                "code": "duplicate",
            },
        )


@router.post("/move", response_model=ContainerUpdatedResponse)
def move_container(
    request: MoveContainerRequest,
    conn: sqlite3.Connection = Depends(get_db_connection),
):
    """Move a container (update drawer_id, row_index, col_index, or sort_index)."""
    # Check if at least one field is provided
    if all(
        [
            request.new_drawer_id is None,
            request.row_index is None,
            request.col_index is None,
            request.sort_index is None,
        ]
    ):
        raise HTTPException(
            status_code=400, detail="At least one field must be provided to update"
        )

    try:
        # Use repository method for move
        repo = DrawersRepo(conn)
        repo.move_container(
            container_id=request.id,
            new_drawer_id=request.new_drawer_id,
            row_index=request.row_index,
            col_index=request.col_index,
            sort_index=request.sort_index,
        )
        return ContainerUpdatedResponse(updated=request.id)
    except DuplicateLabelError as e:
        raise HTTPException(
            status_code=409,
            detail={
                "message": str(e) or "Duplicate label or position conflict",
                "code": "duplicate",
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to move container: {str(e)}")


@router.post("/delete", response_model=ContainerDeletedResponse)
def delete_container(
    request: DeleteContainerRequest,
    conn: sqlite3.Connection = Depends(get_db_connection),
):
    """Soft delete a container. Returns 409 if container has inventory."""
    # Pre-check: if inventory exists, request merge/move
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM inventory WHERE container_id=?",
        (request.id,),
    ).fetchone()
    has_inv = bool(row and (row["n"] or 0) > 0)
    if has_inv:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Container has inventory; merge/move required",
                "code": "conflict",
                "details": {"needed": "merge_move"},
            },
        )

    try:
        inventory_db.soft_delete_container(conn, request.id)
        return ContainerDeletedResponse(deleted=request.id)
    except InventoryConstraintError as e:
        raise HTTPException(
            status_code=409,
            detail={
                "message": str(e),
                "code": "conflict",
                "details": {"needed": "merge_move"},
            },
        )
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

