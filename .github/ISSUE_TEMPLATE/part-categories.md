---
name: Add Rebrickable Part Categories
about: Add part category support from Rebrickable API
title: 'Add Rebrickable Part Categories'
labels: 'type:feature, area:backend, area:frontend'
assignees: ''
projects: '1'
---

## Description

Add support for displaying part categories (e.g., "Brick", "Plate", "Tile", "SNOT") from the Rebrickable API. Part categories are a property of the part itself, not the set-part relationship.

## Current Status

- ✅ Database schema: `part_categories` table exists, `parts.part_category_id` column exists
- ✅ Backend: Repository queries support categories, API DTOs have fields (commented out)
- ✅ Frontend: UI components ready (commented out)
- ❌ Data population: Scripts exist but are too slow/inefficient
- ❌ Display: Categories not shown in UI (intentionally disabled)

## Technical Details

### Database Schema
- `part_categories` table: `id` (INTEGER PRIMARY KEY), `name` (TEXT)
- `parts` table: `part_category_id` (INTEGER, FOREIGN KEY to `part_categories.id`)

### API Endpoints
- Individual part endpoint: `/api/v1/parts/{design_id}` - should return `part_category_id` and `part_category_name`
- Part Detail page should display category in header section

### Challenges
1. **API Performance**: The Rebrickable set parts endpoint (`/sets/{set_num}/parts/`) does NOT return `part_category_id`
2. **Fetching Strategy**: Need to fetch from individual part endpoint (`/parts/{design_id}/`), which requires ~2700 API calls
3. **Rate Limiting**: Sequential fetching is very slow (~1 part/sec = 45+ minutes)
4. **Data Population**: Need efficient batch/parallel processing

## Acceptance Criteria

- [ ] Part categories are populated in the database for all parts in `set_parts`
- [ ] Category names are stored in `part_categories` table
- [ ] Part Detail page displays category in header (below part ID)
- [ ] Category is searchable/filterable (if applicable)
- [ ] Loading script completes in reasonable time (< 10 minutes for ~2700 parts)

## Implementation Notes

### Scripts Created (Need Optimization)
- `src/scripts/load_all_part_categories.py` - Fetches categories for all parts (currently too slow)
- `src/scripts/verify_part_categories.py` - Verification script

### Potential Solutions
1. **Parallel Processing**: Use ThreadPoolExecutor with 5-10 workers (already attempted)
2. **Batch API Calls**: Check if Rebrickable supports bulk part queries
3. **Incremental Loading**: Load categories gradually as parts are accessed
4. **Background Job**: Run category loading as a background task
5. **Alternative Source**: Check if category data is available elsewhere (BrickLink, etc.)

## Related Files

- `src/infra/db/inventory_db.py` - Database schema
- `src/infra/db/repositories/parts_repo.py` - Repository with category support
- `src/app/api/v1/parts.py` - API endpoint (category fields commented out)
- `frontend/app/parts/[designId]/page.tsx` - Part Detail page (category display commented out)
- `src/scripts/load_all_part_categories.py` - Category loading script
- `src/scripts/verify_part_categories.py` - Verification script

## Priority

**P3** - Nice to have, not blocking core functionality. Can be added later when we have time to optimize the data loading process.

