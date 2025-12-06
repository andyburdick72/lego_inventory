"""FastAPI router for inventory/set mismatch endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from pydantic import BaseModel

from app.di import get_mismatch_service, get_set_parts_service
from app.errors import NotFoundError, ValidationError
from core.dtos import MismatchSummaryDTO, PartColorMismatchDTO, SetMismatchDTO
from core.services.mismatch_service import MismatchService
from core.services.set_parts_service import SetPartsService

router = APIRouter(prefix="/mismatches", tags=["mismatches"])


class UpdateInventoryQuantityRequest(BaseModel):
    new_quantity: int


@router.get("/summary", response_model=MismatchSummaryDTO)
def get_mismatch_summary(
    statuses: Optional[str] = Query(
        None,
        description="Comma-separated list of set statuses to analyze (default: loose,teardown)",
    ),
    service: MismatchService = Depends(get_mismatch_service),
):
    """Get overall summary of inventory/set mismatches."""
    status_list = None
    if statuses:
        status_list = [s.strip() for s in statuses.split(",") if s.strip()]

    try:
        summary = service.compute_summary(statuses=status_list)
        return summary.model_dump()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "message": f"Error computing mismatch summary: {str(e)}",
                "code": "internal_error",
            },
        )


@router.get("", response_model=list[SetMismatchDTO])
def list_mismatches(
    set_number: Optional[str] = Query(
        None, description="Filter by specific set number"
    ),
    statuses: Optional[str] = Query(
        None,
        description="Comma-separated list of set statuses to analyze (default: loose,teardown)",
    ),
    service: MismatchService = Depends(get_mismatch_service),
):
    """List all sets with inventory mismatches.

    Returns sets where the parts required by the set don't match
    the available loose inventory (missing or excess parts).
    """
    status_list = None
    if statuses:
        status_list = [s.strip() for s in statuses.split(",") if s.strip()]

    try:
        mismatches = service.compute_mismatches(
            set_number=set_number, statuses=status_list
        )
        return [m.model_dump() for m in mismatches]
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
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "message": f"Error computing mismatches: {str(e)}",
                "code": "internal_error",
            },
        )


# IMPORTANT: /part-color routes must come BEFORE /{set_number} route
# because FastAPI matches routes in order and {set_number} would match "part-color"
@router.get("/part-color/test")
def test_part_color_endpoint():
    """Test endpoint to verify the route is working."""
    return {"status": "ok", "message": "part-color endpoint is accessible"}


@router.get("/part-color", name="list_part_color_mismatches")
def list_part_color_mismatches(
    statuses: Optional[str] = Query(
        None,
        description="Comma-separated list of set statuses to analyze (default: loose,teardown)",
    ),
):
    """List part+color level mismatches (like inventory_sanity_checks.py output).

    Returns mismatches where loose inventory doesn't match the sum of set_parts
    for loose/teardown sets, grouped by part+color.
    """
    import traceback
    import sys
    
    print(f"[DEBUG] list_part_color_mismatches called with statuses={statuses}", flush=True)
    
    try:
        # Get service manually to catch DI errors
        from app.di import get_db_connection, get_mismatch_service
        print("[DEBUG] Getting DB connection...", flush=True)
        conn = get_db_connection()
        print("[DEBUG] Getting mismatch service...", flush=True)
        service = get_mismatch_service(conn)
        print("[DEBUG] Service obtained successfully", flush=True)
        
        status_list = None
        if statuses:
            status_list = [s.strip() for s in statuses.split(",") if s.strip()]
        
        print(f"[DEBUG] Calling compute_part_color_mismatches with status_list={status_list}", flush=True)
        mismatches = service.compute_part_color_mismatches(statuses=status_list)
        print(f"[DEBUG] Got {len(mismatches)} mismatches", flush=True)
        result = [m.model_dump() for m in mismatches]
        print(f"[DEBUG] Returning {len(result)} items", flush=True)
        return result
    except Exception as e:
        # Log the full traceback to console for debugging
        exc_type, exc_value, exc_traceback = sys.exc_info()
        error_details = traceback.format_exception(exc_type, exc_value, exc_traceback)
        error_str = "".join(error_details)
        
        # Print to both stdout and stderr to ensure we see it
        print("=" * 80, flush=True)
        print("ERROR in list_part_color_mismatches:", flush=True)
        print(error_str, flush=True)
        print("=" * 80, flush=True)
        
        # Also log via Python's logging if available
        import logging
        logger = logging.getLogger(__name__)
        logger.error("Error in list_part_color_mismatches", exc_info=True)
        
        raise HTTPException(
            status_code=500,
            detail={
                "message": f"Error computing part-color mismatches: {str(e)}",
                "code": "internal_error",
                "error_type": str(type(e).__name__),
            },
        )


@router.patch("/part-color/{design_id}/{color_id}")
def update_inventory_quantity(
    design_id: str,
    color_id: int,
    request: UpdateInventoryQuantityRequest,
    service: MismatchService = Depends(get_mismatch_service),
):
    """Update the loose inventory quantity for a specific part+color."""
    try:
        service.update_inventory_quantity(design_id, color_id, request.new_quantity)
        return {
            "updated": True,
            "design_id": design_id,
            "color_id": color_id,
            "new_quantity": request.new_quantity,
        }
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "message": f"Error updating inventory: {str(e)}",
                "code": "internal_error",
            },
        )


@router.get("/{set_number}", response_model=SetMismatchDTO)
def get_set_mismatch(
    set_number: str,
    service: MismatchService = Depends(get_mismatch_service),
    set_parts_service: SetPartsService = Depends(get_set_parts_service),
):
    """Get mismatch details for a specific set."""
    try:
        # First check if set exists
        from core.enums import Status

        try:
            set_data = set_parts_service.get_set(set_number=set_number)
        except NotFoundError:
            raise HTTPException(
                status_code=404,
                detail={
                    "message": f"Set {set_number} not found",
                    "code": "not_found",
                },
            )

        # Compute mismatch for this set
        mismatches = service.compute_mismatches(set_number=set_number, statuses=None)

        if not mismatches:
            # Set exists but has no mismatches or wrong status
            status_str = str(set_data.get("status", "in_box"))
            try:
                status = Status.from_any(status_str)
            except ValueError:
                status = Status.IN_BOX

            return SetMismatchDTO(
                set_number=set_number,
                set_name=str(set_data.get("name", "")),
                status=status,
                total_parts=0,
                missing_parts_count=0,
                excess_parts_count=0,
                total_missing_quantity=0,
                total_excess_quantity=0,
                mismatches=[],
                image_url=set_data.get("image_url"),
                rebrickable_url=set_data.get("rebrickable_url"),
            ).model_dump()

        return mismatches[0].model_dump()
    except HTTPException:
        # Re-raise HTTP exceptions (like 404)
        raise
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
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "message": f"Error computing mismatch: {str(e)}",
                "code": "internal_error",
            },
        )

