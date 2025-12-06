"""API endpoints for location-based inventory reconciliation."""

from fastapi import APIRouter, Depends, HTTPException

from app.di import get_location_reconciliation_service
from app.errors import NotFoundError, ValidationError
from core.dtos import InventoryLocationDTO, LocationReconciliationItemDTO
from core.services.location_reconciliation_service import LocationReconciliationService

router = APIRouter(prefix="/location-reconciliation", tags=["location-reconciliation"])


@router.get("/items/loose-parts", response_model=list[LocationReconciliationItemDTO])
def list_loose_parts_reconciliation_items(
    service: LocationReconciliationService = Depends(get_location_reconciliation_service),
) -> list[LocationReconciliationItemDTO]:
    """
    List reconciliation items for Loose Parts sets.
    Parts should be in inventory but NOT in Put Away bin.
    """
    try:
        items = service.compute_loose_parts_reconciliation_items()
        result = []
        for item in items:
            # Convert current_locations to DTOs
            current_locations = [
                InventoryLocationDTO(**loc) for loc in item.get("current_locations", [])
            ]
            item_dict = dict(item)
            item_dict["current_locations"] = current_locations
            result.append(LocationReconciliationItemDTO(**item_dict))
        return result
    except Exception as e:
        import traceback
        error_detail = f"Error computing loose parts reconciliation items: {str(e)}\n{traceback.format_exc()}"
        print(error_detail)  # Log to console for debugging
        raise HTTPException(status_code=500, detail=f"Error computing loose parts reconciliation items: {str(e)}") from e


@router.get("/items/teardown", response_model=list[LocationReconciliationItemDTO])
def list_teardown_reconciliation_items(
    service: LocationReconciliationService = Depends(get_location_reconciliation_service),
) -> list[LocationReconciliationItemDTO]:
    """
    List reconciliation items for Teardown sets.
    Parts should be in Put Away bin.
    """
    try:
        items = service.compute_teardown_reconciliation_items()
        result = []
        for item in items:
            # Convert current_locations to DTOs
            current_locations = [
                InventoryLocationDTO(**loc) for loc in item.get("current_locations", [])
            ]
            item_dict = dict(item)
            item_dict["current_locations"] = current_locations
            result.append(LocationReconciliationItemDTO(**item_dict))
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error computing teardown reconciliation items: {str(e)}") from e


@router.patch("/items/{design_id}/{color_id}")
def update_inventory_location(
    design_id: str,
    color_id: int,
    quantity: int,
    drawer_id: int | None = None,
    container_id: int | None = None,
    is_teardown: bool = False,
    service: LocationReconciliationService = Depends(get_location_reconciliation_service),
) -> dict[str, str]:
    """
    Update inventory location for a part+color.
    
    This will:
    - Set the quantity at the specified location
    - Remove inventory from other locations for this part+color
    - Quantity should match the required quantity from set_parts
    
    Args:
        is_teardown: If True, allows putting parts in Put Away bin. If False, prevents it.
    """
    try:
        service.update_inventory_location(design_id, color_id, quantity, drawer_id, container_id, is_teardown=is_teardown)
        return {"message": "Inventory location updated successfully"}
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating inventory location: {str(e)}") from e

