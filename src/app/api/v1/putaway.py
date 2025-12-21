"""FastAPI router for Put-Away Wizard endpoints."""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query

from app.di import (
    get_db_connection,
    get_inventory_service,
    get_set_parts_service,
    get_storage_hierarchy_service,
)
from app.errors import NotFoundError, ValidationError
from core.dtos import (
    AssignmentResultDTO,
    BatchAssignmentRequestDTO,
    BatchAssignmentResultDTO,
    PutawayPartWithSuggestionDTO,
    StorageSuggestionDTO,
)
from core.services.inventory_service import InventoryService
from core.services.set_parts_service import SetPartsService
from core.services.storage_hierarchy_service import StorageHierarchyService
from infra.db.repositories.drawers_repo import DrawersRepo
from infra.db.repositories.inventory_repo import InventoryRepo
from infra.db.repositories.sets_repo import SetsRepo

router = APIRouter(prefix="/putaway", tags=["putaway"])


@router.get("/parts-from-set/{set_number}", response_model=list[PutawayPartWithSuggestionDTO])
def get_parts_from_set_for_putaway(
    set_number: str,
    set_parts_service: SetPartsService = Depends(get_set_parts_service),
    storage_service: StorageHierarchyService = Depends(get_storage_hierarchy_service),
):
    """
    Get parts from a set for part-out wizard entry point.

    Returns parts from set_parts with location suggestions for each part.
    This endpoint is used when parting out a set (moving from built/in_box/wip/teardown to loose_parts).
    """
    try:
        # Verify set exists
        set_parts_service.get_set(set_number=set_number)

        # Get all parts for the set
        parts = list(set_parts_service.list_parts(set_number=set_number))

        result = []
        for part in parts:
            # Skip parts flagged to ignore in inventory
            if part.get("ignore_in_inventory", 0) == 1:
                continue
            design_id = str(part.get("design_id", ""))
            color_id = int(part.get("color_id", 0))
            quantity = int(part.get("quantity", 0))

            # Get location suggestion
            suggestion = storage_service.suggest_location(design_id, color_id)
            suggestion_dto = None
            if suggestion:
                suggestion_dto = StorageSuggestionDTO(**suggestion.to_dict())

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
                PutawayPartWithSuggestionDTO(
                    design_id=design_id,
                    part_name=str(part.get("name", "")),
                    color_id=color_id,
                    color_name=str(part.get("color_name", "")),
                    color_hex=hex_value,
                    quantity=quantity,
                    part_url=part_url,
                    part_img_url=part_img_url,
                    suggestion=suggestion_dto,
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


@router.get("/parts-in-bin", response_model=list[PutawayPartWithSuggestionDTO])
def get_parts_in_putaway_bin(
    search: str | None = Query(None, description="Search filter for part name or design_id"),
    conn: sqlite3.Connection = Depends(get_db_connection),
    storage_service: StorageHierarchyService = Depends(get_storage_hierarchy_service),
):
    """
    Get all parts currently in the putaway bin container.

    Returns parts with their location suggestions. This endpoint is used for the putaway bin entry point.
    """
    try:
        repo = InventoryRepo(conn)
        parts = repo.get_putaway_bin_parts(search=search)

        if not parts:
            # Check if putaway bin exists
            drawers_repo = DrawersRepo(conn)
            putaway_bin = drawers_repo.get_put_away_bin()
            if not putaway_bin:
                raise NotFoundError(
                    "Putaway bin not configured. Please set a container as the putaway bin.",
                    details={},
                )
            return []

        result = []
        for part in parts:
            design_id = str(part.get("design_id", ""))
            color_id = int(part.get("color_id", 0))
            quantity = int(part.get("quantity", 0))
            inventory_id = part.get("inventory_id")

            # Get location suggestion
            suggestion = storage_service.suggest_location(design_id, color_id)
            suggestion_dto = None
            if suggestion:
                suggestion_dto = StorageSuggestionDTO(**suggestion.to_dict())

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
                PutawayPartWithSuggestionDTO(
                    design_id=design_id,
                    part_name=str(part.get("part_name", "")),
                    color_id=color_id,
                    color_name=str(part.get("color_name", "")),
                    color_hex=hex_value,
                    quantity=quantity,
                    part_url=part_url,
                    part_img_url=part_img_url,
                    inventory_id=int(inventory_id) if inventory_id else None,
                    suggestion=suggestion_dto,
                )
            )

        return [p.model_dump() for p in result]
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


@router.post("/batch-assign", response_model=BatchAssignmentResultDTO)
def batch_assign_parts(
    request: BatchAssignmentRequestDTO,
    service: InventoryService = Depends(get_inventory_service),
    set_parts_service: SetPartsService = Depends(get_set_parts_service),
    conn: sqlite3.Connection = Depends(get_db_connection),
):
    """
    Batch assign parts to containers.

    This endpoint handles both:
    - Part-out entry point: Creates new inventory items from set parts
    - Putaway bin entry point: Updates existing inventory items' container_id

    All assigned parts will have status='loose'.
    """
    assignments = request.assignments
    if not assignments:
        raise HTTPException(
            status_code=422,
            detail={"message": "At least one assignment is required", "code": "validation_error"},
        )

    total_requested = len(assignments)
    total_assigned = 0
    total_skipped = 0
    assignment_results: list[AssignmentResultDTO] = []
    errors: list[str] = []

    repo = InventoryRepo(conn)

    for assignment in assignments:
        design_id = assignment.design_id
        color_id = assignment.color_id
        quantity = assignment.quantity
        container_id = assignment.container_id
        inventory_id = assignment.inventory_id

        # Validate assignment
        if not design_id or not isinstance(color_id, int) or not isinstance(quantity, int):
            errors.append(f"Invalid assignment for {design_id}/{color_id}: missing required fields")
            assignment_results.append(
                AssignmentResultDTO(
                    design_id=design_id,
                    color_id=color_id,
                    quantity=quantity,
                    container_id=container_id,
                    success=False,
                    message="Invalid assignment: missing required fields",
                )
            )
            continue

        if quantity <= 0:
            errors.append(f"Invalid quantity for {design_id}/{color_id}: {quantity}")
            assignment_results.append(
                AssignmentResultDTO(
                    design_id=design_id,
                    color_id=color_id,
                    quantity=quantity,
                    container_id=container_id,
                    success=False,
                    message=f"Invalid quantity: {quantity}",
                )
            )
            continue

        try:
            # If no container_id provided, skip (user chose to skip this part)
            if container_id is None:
                total_skipped += 1
                assignment_results.append(
                    AssignmentResultDTO(
                        design_id=design_id,
                        color_id=color_id,
                        quantity=quantity,
                        container_id=None,
                        success=True,
                        message="Skipped (no container assigned)",
                    )
                )
                continue

            # Validate container exists
            drawers_repo = DrawersRepo(conn)
            container = drawers_repo.get_container_with_drawer(container_id)
            if not container:
                errors.append(f"Container {container_id} not found for {design_id}/{color_id}")
                assignment_results.append(
                    AssignmentResultDTO(
                        design_id=design_id,
                        color_id=color_id,
                        quantity=quantity,
                        container_id=container_id,
                        success=False,
                        message=f"Container {container_id} not found",
                    )
                )
                continue

            # If inventory_id is provided, this is from putaway bin - update existing inventory
            if inventory_id is not None:
                # Check if inventory item exists and is in putaway bin
                inventory_item = repo.get_inventory_by_id(inventory_id)
                if not inventory_item:
                    errors.append(
                        f"Inventory item {inventory_id} not found for {design_id}/{color_id}"
                    )
                    assignment_results.append(
                        AssignmentResultDTO(
                            design_id=design_id,
                            color_id=color_id,
                            quantity=quantity,
                            container_id=container_id,
                            success=False,
                            message=f"Inventory item {inventory_id} not found",
                        )
                    )
                    continue

                # Validate quantity matches
                if inventory_item.get("quantity") != quantity:
                    errors.append(
                        f"Quantity mismatch for {design_id}/{color_id}: "
                        f"requested {quantity}, but inventory has {inventory_item.get('quantity')}"
                    )
                    assignment_results.append(
                        AssignmentResultDTO(
                            design_id=design_id,
                            color_id=color_id,
                            quantity=quantity,
                            container_id=container_id,
                            success=False,
                            message=f"Quantity mismatch: inventory has {inventory_item.get('quantity')}",
                        )
                    )
                    continue

                # Update inventory location
                service.update_inventory_location(
                    inventory_id=inventory_id, container_id=container_id
                )
                total_assigned += 1
                assignment_results.append(
                    AssignmentResultDTO(
                        design_id=design_id,
                        color_id=color_id,
                        quantity=quantity,
                        container_id=container_id,
                        success=True,
                        message="Assigned from putaway bin",
                    )
                )
            else:
                # This is from part-out - create new inventory or merge with existing
                # Check if inventory already exists at target location for this part+color
                existing = repo.loose_inventory_for_part_color(design_id, color_id)
                target_inv = None
                for inv in existing:
                    if inv.get("container_id") == container_id:
                        target_inv = inv
                        break

                if target_inv:
                    # Find the inventory row ID to update
                    inv_row = conn.execute(
                        """
                        SELECT id, quantity FROM inventory
                        WHERE design_id = ? AND color_id = ? AND container_id = ? AND status = 'loose'
                        LIMIT 1
                        """,
                        (design_id, color_id, container_id),
                    ).fetchone()
                    if inv_row:
                        inv_id = inv_row["id"] if isinstance(inv_row, dict) else inv_row[0]
                        current_qty = (
                            inv_row["quantity"] if isinstance(inv_row, dict) else inv_row[1]
                        )
                        # Update quantity by adding
                        new_qty = current_qty + quantity
                        service.update_inventory_quantity(inventory_id=inv_id, quantity=new_qty)
                        total_assigned += 1
                        assignment_results.append(
                            AssignmentResultDTO(
                                design_id=design_id,
                                color_id=color_id,
                                quantity=quantity,
                                container_id=container_id,
                                success=True,
                                message=f"Merged with existing (total: {new_qty})",
                            )
                        )
                        continue

                # Create new inventory item
                conn.execute(
                    """
                    INSERT INTO inventory (design_id, color_id, quantity, status, container_id)
                    VALUES (?, ?, ?, 'loose', ?)
                    """,
                    (design_id, color_id, quantity, container_id),
                )
                conn.commit()
                total_assigned += 1
                assignment_results.append(
                    AssignmentResultDTO(
                        design_id=design_id,
                        color_id=color_id,
                        quantity=quantity,
                        container_id=container_id,
                        success=True,
                        message="Created from set part-out",
                    )
                )
        except Exception as e:
            error_msg = f"Error assigning {design_id}/{color_id}: {str(e)}"
            errors.append(error_msg)
            assignment_results.append(
                AssignmentResultDTO(
                    design_id=design_id,
                    color_id=color_id,
                    quantity=quantity,
                    container_id=container_id,
                    success=False,
                    message=str(e),
                )
            )

    # Update set status based on entry point and completion
    sets_repo = SetsRepo(conn)
    drawers_repo = DrawersRepo(conn)
    putaway_bin = drawers_repo.get_put_away_bin()
    putaway_bin_id = putaway_bin.get("container_id") if putaway_bin else None

    if request.entry_point == "set" and request.set_number:
        # Part-out entry point: If all parts were assigned, update set status to "loose_parts"
        # Check if all parts from the set were assigned
        try:
            set_parts = list(set_parts_service.list_parts(set_number=request.set_number))
            total_set_parts = sum(
                int(p.get("quantity", 0)) for p in set_parts if p.get("ignore_in_inventory", 0) != 1
            )
            total_assigned_qty = sum(a.quantity for a in assignments if a.container_id is not None)

            # If we assigned all parts (or close to it), update set status
            if total_assigned_qty >= total_set_parts * 0.95:  # Allow 5% tolerance
                try:
                    sets_repo.update_set_by_num(request.set_number, status="loose_parts")
                except Exception as e:
                    errors.append(f"Failed to update set status: {str(e)}")
        except Exception as e:
            # If we can't check set parts, don't fail the whole operation
            errors.append(f"Warning: Could not check set parts for status update: {str(e)}")

    elif request.entry_point == "bin" and putaway_bin_id:
        # Putaway bin entry point: Check if all items were moved out
        remaining_in_bin = conn.execute(
            """
            SELECT COUNT(*) FROM inventory
            WHERE status = 'loose' AND container_id = ?
            """,
            (putaway_bin_id,),
        ).fetchone()
        remaining_count = (
            remaining_in_bin[0]
            if isinstance(remaining_in_bin, tuple)
            else remaining_in_bin["COUNT(*)"]
        )

        # If putaway bin is now empty, update all Teardown sets to "loose_parts"
        if remaining_count == 0:
            try:
                conn.execute("UPDATE sets SET status = 'loose_parts' WHERE status = 'teardown'")
                conn.commit()
            except Exception as e:
                errors.append(f"Failed to update teardown set statuses: {str(e)}")

    return BatchAssignmentResultDTO(
        total_requested=total_requested,
        total_assigned=total_assigned,
        total_skipped=total_skipped,
        assignments=assignment_results,
        errors=errors,
    )
