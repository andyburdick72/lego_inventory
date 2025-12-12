"""FastAPI router for global search endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.di import get_search_service
from app.errors import ValidationError
from core.dtos import (
    SearchCategoryDTO,
    SearchContainerDTO,
    SearchDrawerDTO,
    SearchPartDTO,
    SearchResultsDTO,
    SearchSetDTO,
)
from core.services.search_service import SearchService

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=SearchResultsDTO)
def search(
    q: str = Query(..., description="Search query (minimum 2 characters)", min_length=2),
    limit: int = Query(10, description="Maximum results per entity type", ge=1, le=50),
    service: SearchService = Depends(get_search_service),
):
    """
    Global search across parts, sets, drawers, containers, and categories.

    Returns results grouped by entity type, with a maximum number of results per type.
    """
    try:
        results = service.search(query=q, limit_per_type=limit)

        # Deduplicate results by unique identifier before converting to DTOs
        # Parts: deduplicate by design_id
        seen_parts = set()
        unique_parts = []
        for p in results["parts"]:
            design_id = str(p.get("design_id", ""))
            if design_id and design_id not in seen_parts:
                seen_parts.add(design_id)
                unique_parts.append(p)

        # Sets: deduplicate by set_number
        seen_sets = set()
        unique_sets = []
        for s in results["sets"]:
            set_number = str(s.get("set_number", ""))
            if set_number and set_number not in seen_sets:
                seen_sets.add(set_number)
                unique_sets.append(s)

        # Convert to DTOs
        parts = [
            SearchPartDTO(
                design_id=str(p.get("design_id", "")),
                name=str(p.get("name", "")),
                part_url=p.get("part_url"),
                part_img_url=p.get("part_img_url"),
                part_category_id=p.get("part_category_id"),
                part_category_name=p.get("part_category_name"),
            )
            for p in unique_parts
        ]

        sets = [
            SearchSetDTO(
                set_number=str(s.get("set_number", "")),
                name=str(s.get("name", "")),
                year=s.get("year"),
                theme_id=s.get("theme_id"),
                theme_name=s.get("theme_name"),
                status=s.get("status"),
                image_url=s.get("image_url"),
                rebrickable_url=s.get("rebrickable_url"),
            )
            for s in unique_sets
        ]

        # Drawers: deduplicate by id
        seen_drawers = set()
        unique_drawers = []
        for d in results["drawers"]:
            drawer_id = int(d.get("id", 0))
            if drawer_id and drawer_id not in seen_drawers:
                seen_drawers.add(drawer_id)
                unique_drawers.append(d)

        # Containers: deduplicate by id
        seen_containers = set()
        unique_containers = []
        for c in results["containers"]:
            container_id = int(c.get("id", 0))
            if container_id and container_id not in seen_containers:
                seen_containers.add(container_id)
                unique_containers.append(c)

        # Categories: deduplicate by id
        seen_categories = set()
        unique_categories = []
        for cat in results["categories"]:
            category_id = int(cat.get("id", 0))
            if category_id and category_id not in seen_categories:
                seen_categories.add(category_id)
                unique_categories.append(cat)

        drawers = [
            SearchDrawerDTO(
                id=int(d.get("id", 0)),
                name=str(d.get("name", "")),
                description=d.get("description"),
            )
            for d in unique_drawers
        ]

        containers = [
            SearchContainerDTO(
                id=int(c.get("id", 0)),
                name=str(c.get("name", "")),
                description=c.get("description"),
                drawer_id=int(c.get("drawer_id", 0)),
                drawer_name=c.get("drawer_name"),
            )
            for c in unique_containers
        ]

        categories = [
            SearchCategoryDTO(
                id=int(cat.get("id", 0)),
                name=str(cat.get("name", "")),
            )
            for cat in unique_categories
        ]

        return SearchResultsDTO(
            parts=parts,
            sets=sets,
            drawers=drawers,
            containers=containers,
            categories=categories,
        )
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
