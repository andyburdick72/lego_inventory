## Summary
Add support for displaying part categories (e.g., "Brick", "Plate", "Tile", "SNOT") from the Rebrickable API on the Part Detail page.

## Context / Links
- Database schema already supports categories (`part_categories` table, `parts.part_category_id` column)
- Backend code is ready but commented out (API DTOs, repository queries)
- Frontend code is ready but commented out (Part Detail page display)
- Challenge: Rebrickable set parts endpoint doesn't return `part_category_id`, requiring individual part API calls (~2700 calls = 45+ minutes)
- Scripts created: `load_all_part_categories.py` (needs optimization), `verify_part_categories.py`

## Acceptance criteria (required)
- [x] Tests updated/added (N/A - data loading script)
- [x] No regressions in smoke tests (`./dev.sh`)
- [ ] Linked to milestone (phase)

## Additional checklist
- [ ] Optimize category loading script (parallel processing, batch API calls, or incremental loading)
- [ ] Populate `part_categories` table with category names
- [ ] Populate `parts.part_category_id` for all parts in `set_parts`
- [ ] Uncomment category fields in `PartDTO` and API endpoint
- [ ] Uncomment category display in Part Detail page header
- [ ] Verify categories display correctly in UI
- [ ] Add category to search/filter if applicable

## Implementation Notes
- The Rebrickable `/sets/{set_num}/parts/` endpoint does NOT include `part_category_id`
- Must fetch from `/parts/{design_id}/` endpoint individually
- Current script processes ~1 part/sec (too slow for 2700+ parts)
- Potential solutions: parallel processing, batch API, incremental loading, or background job

## Related Files
- `src/infra/db/inventory_db.py` - Database schema
- `src/infra/db/repositories/parts_repo.py` - Repository queries
- `src/app/api/v1/parts.py` - API endpoint (fields commented out)
- `frontend/app/parts/[designId]/page.tsx` - Part Detail page (display commented out)
- `src/scripts/load_all_part_categories.py` - Loading script (needs optimization)
- `src/scripts/verify_part_categories.py` - Verification script

