"""FastAPI router for containers endpoints."""

import sqlite3
from typing import Optional

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
    description: Optional[str] = None
    row_index: Optional[int] = None
    col_index: Optional[int] = None
    sort_index: Optional[int] = None


class RenameContainerRequest(BaseModel):
    id: int
    new_name: str


class MoveContainerRequest(BaseModel):
    id: int
    new_drawer_id: Optional[int] = None
    row_index: Optional[int] = None
    col_index: Optional[int] = None
    sort_index: Optional[int] = None


class UpdateContainerRequest(BaseModel):
    id: int
    name: Optional[str] = None
    description: Optional[str] = None
    row_index: Optional[int] = None
    col_index: Optional[int] = None


class DeleteContainerRequest(BaseModel):
    id: int


# Response models
class ContainerIdResponse(BaseModel):
    id: int


class ContainerUpdatedResponse(BaseModel):
    updated: int


class ContainerDeletedResponse(BaseModel):
    deleted: int


class PutAwayBinResponse(BaseModel):
    container_id: Optional[int] = None
    drawer_id: Optional[int] = None
    drawer_name: Optional[str] = None
    container_name: Optional[str] = None


class SetPutAwayBinRequest(BaseModel):
    container_id: int


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


@router.post("/update", response_model=ContainerUpdatedResponse)
def update_container(
    request: UpdateContainerRequest,
    conn: sqlite3.Connection = Depends(get_db_connection),
):
    """Update a container (name, description, row_index, col_index)."""
    # Check if at least one field is provided
    if all(
        [
            request.name is None,
            request.description is None,
            request.row_index is None,
            request.col_index is None,
        ]
    ):
        raise HTTPException(
            status_code=400, detail="At least one field must be provided to update"
        )

    try:
        # Use inventory_db.update_container which can update any fields
        fields = {}
        if request.name is not None:
            fields["name"] = request.name.strip()
        if request.description is not None:
            # Allow clearing description by sending empty string (which becomes None)
            # or explicitly sending None
            desc_value = request.description.strip() if request.description else None
            fields["description"] = desc_value
        if request.row_index is not None:
            fields["row_index"] = request.row_index
        if request.col_index is not None:
            fields["col_index"] = request.col_index

        inventory_db.update_container(conn, request.id, **fields)
        return ContainerUpdatedResponse(updated=request.id)
    except DuplicateLabelError as e:
        raise HTTPException(
            status_code=409,
            detail={
                "message": str(e) or "Duplicate label in this drawer",
                "code": "duplicate",
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update container: {str(e)}")


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


@router.get("/{container_id}")
def get_container(
    container_id: int,
    conn: sqlite3.Connection = Depends(get_db_connection),
):
    """Get container details including drawer information."""
    container = inventory_db.get_container(container_id)
    if not container:
        raise HTTPException(status_code=404, detail="Container not found")
    return container


@router.get("/{container_id}/parts")
def get_container_parts(
    container_id: int,
    conn: sqlite3.Connection = Depends(get_db_connection),
):
    """Get all parts in a container with full details."""
    parts = inventory_db.list_parts_in_container(container_id)
    
    # Enhance parts with URLs and images from parts table
    result = []
    for part in parts:
        design_id = part.get("design_id")
        if design_id:
            # Get part metadata for URLs and images
            part_row = conn.execute(
                "SELECT part_url, part_img_url FROM parts WHERE design_id = ?",
                (design_id,),
            ).fetchone()
            
            part_url = None
            part_img_url = None
            if part_row:
                part_url = part_row.get("part_url") if isinstance(part_row, dict) else part_row[0] if part_row else None
                part_img_url = part_row.get("part_img_url") if isinstance(part_row, dict) else part_row[1] if part_row else None
            
            # Fallback to Rebrickable URL if not in DB
            if not part_url and design_id:
                part_url = f"https://rebrickable.com/parts/{design_id}/"
            
            # Fallback to default image if not in DB
            if not part_img_url:
                part_img_url = "https://rebrickable.com/static/img/nil.png"
        
        result.append({
            "design_id": design_id,
            "part_name": part.get("part_name"),
            "color_id": part.get("color_id"),
            "color_name": part.get("color_name"),
            "hex": part.get("hex"),
            "quantity": part.get("qty") or part.get("quantity") or 0,
            "part_url": part_url,
            "part_img_url": part_img_url,
        })
    
    return result


@router.get("/put-away-bin", response_model=PutAwayBinResponse)
def get_put_away_bin(
    conn: sqlite3.Connection = Depends(get_db_connection),
):
    """Get the container marked as the put away bin."""
    try:
        repo = DrawersRepo(conn)
        put_away = repo.get_put_away_bin()
        if put_away:
            # Ensure we handle None values properly - convert to appropriate types
            container_id = put_away.get("container_id")
            drawer_id = put_away.get("drawer_id")
            drawer_name = put_away.get("drawer_name")
            container_name = put_away.get("container_name")
            
            return PutAwayBinResponse(
                container_id=int(container_id) if container_id is not None else None,
                drawer_id=int(drawer_id) if drawer_id is not None else None,
                drawer_name=str(drawer_name) if drawer_name is not None else None,
                container_name=str(container_name) if container_name is not None else None,
            )
        return PutAwayBinResponse(container_id=None, drawer_id=None, drawer_name=None, container_name=None)
    except Exception as e:
        import traceback
        error_detail = f"Error getting put away bin: {str(e)}\n{traceback.format_exc()}"
        print(error_detail)  # Log to console for debugging
        raise HTTPException(status_code=500, detail=f"Error getting put away bin: {str(e)}") from e


@router.post("/put-away-bin", response_model=dict[str, str])
def set_put_away_bin(
    request: SetPutAwayBinRequest,
    conn: sqlite3.Connection = Depends(get_db_connection),
):
    """Set a container as the put away bin. This will unset any other container with this flag."""
    repo = DrawersRepo(conn)
    repo.set_put_away_bin(request.container_id)
    return {"message": "Put away bin updated successfully"}

