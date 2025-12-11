"""FastAPI router for storage hierarchy endpoints."""

from fastapi import APIRouter, Depends, HTTPException

from app.errors import NotFoundError, ValidationError
from core.dtos import (
    StorageSuggestionDTO,
    ElementStoragePatternDTO,
    PartStoragePatternDTO,
    CategoryStoragePatternDTO,
    ElementStorageStrategyDTO,
)
from core.services.storage_hierarchy_service import StorageHierarchyService
from app.di import get_storage_hierarchy_service

router = APIRouter(prefix="/storage-hierarchy", tags=["storage-hierarchy"])


@router.get("/suggest/{design_id}/{color_id}", response_model=StorageSuggestionDTO | None)
def suggest_location(
    design_id: str,
    color_id: int,
    service: StorageHierarchyService = Depends(get_storage_hierarchy_service),
):
    """
    Get a storage location suggestion for a specific element (design_id + color_id).

    Returns the best suggestion based on storage hierarchy:
    - High: Exact element match found
    - Medium: Part match found (same design_id, different color)
    - Low: Category match found
    - None: No match found

    Args:
        design_id: Part design ID
        color_id: Color ID

    Returns:
        StorageSuggestionDTO or None if no suggestion can be made
    """
    try:
        suggestion = service.suggest_location(design_id, color_id)
        if suggestion:
            return StorageSuggestionDTO(**suggestion.to_dict())
        return None
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


@router.get("/suggest-all/{design_id}/{color_id}", response_model=list[StorageSuggestionDTO])
def suggest_all_locations(
    design_id: str,
    color_id: int,
    service: StorageHierarchyService = Depends(get_storage_hierarchy_service),
):
    """
    Get all possible storage location suggestions for an element, ordered by confidence.

    Returns a list of suggestions from highest to lowest confidence:
    - High: Exact element matches
    - Medium: Part matches (same design_id, different color)
    - Low: Category matches

    Args:
        design_id: Part design ID
        color_id: Color ID

    Returns:
        List of StorageSuggestionDTO, ordered by confidence
    """
    try:
        suggestions = service.get_all_suggestions(design_id, color_id)
        return [StorageSuggestionDTO(**s.to_dict()) for s in suggestions]
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


@router.get("/patterns/elements", response_model=list[ElementStoragePatternDTO])
def get_element_storage_patterns(
    service: StorageHierarchyService = Depends(get_storage_hierarchy_service),
):
    """
    Get all element-level storage patterns.

    Returns containers where specific elements (design_id + color_id) are stored.
    Shows which containers store elements exclusively (one element per container)
    vs. containers that store multiple elements.
    """
    patterns = service.get_element_storage_patterns()
    return [ElementStoragePatternDTO(**p) for p in patterns]


@router.get("/patterns/parts", response_model=list[PartStoragePatternDTO])
def get_part_storage_patterns(
    service: StorageHierarchyService = Depends(get_storage_hierarchy_service),
):
    """
    Get all part-level storage patterns.

    Returns containers where specific parts (design_id, any color) are stored.
    Shows which containers store parts by part type rather than by element.
    """
    patterns = service.get_part_storage_patterns()
    return [PartStoragePatternDTO(**p) for p in patterns]


@router.get("/patterns/categories", response_model=list[CategoryStoragePatternDTO])
def get_category_storage_patterns(
    service: StorageHierarchyService = Depends(get_storage_hierarchy_service),
):
    """
    Get all category-level storage patterns.

    Returns containers where parts from specific categories are stored.
    Shows which containers organize parts by category (e.g., all bricks together).
    """
    patterns = service.get_category_storage_patterns()
    return [CategoryStoragePatternDTO(**p) for p in patterns]


@router.get("/strategies", response_model=list[ElementStorageStrategyDTO])
def get_element_storage_strategies(
    service: StorageHierarchyService = Depends(get_storage_hierarchy_service),
):
    """
    Analyze how each element is stored based on container/drawer naming patterns.

    Categorizes storage strategies:
    - 'by_element': Container name contains part number AND color description
    - 'by_part': Container name contains part number but NO color description
    - 'by_category_size': Drawer is "Really Useful" AND container has size description (large/small)
    - 'by_category': Drawer is "Really Useful" AND container has NO size description
    - 'unknown': Doesn't match any pattern

    Returns a list of all elements with their inferred storage strategy.
    """
    strategies = service.get_element_storage_strategies()
    return [ElementStorageStrategyDTO(**s) for s in strategies]

