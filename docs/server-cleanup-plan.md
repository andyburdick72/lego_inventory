# Old Python Server Cleanup Plan

## Current Status

The old Python server (`src/app/server.py`) is **deprecated** but still present. All functionality has been migrated to:
- **FastAPI** server on port 8001 (`src/app/api/main.py`)
- **Next.js** frontend on port 3000

## References to Old Server

### Still Active References

1. **`dev.sh`** - Has option to run legacy server (line 170)
   - ✅ Can be updated to remove legacy option or keep as fallback

2. **`scripts/mac/create_lego_app.sh`** - Creates macOS app that runs `server.py` (line 93)
   - ⚠️ Needs update to run FastAPI instead

3. **`src/scripts/snapshot_contracts.py`** - References `localhost:8000` (line 7)
   - ⚠️ Needs update to use FastAPI port 8001

4. **`src/app/settings.py`** - Default port 8000 (line 38)
   - ✅ Safe to keep (just a default, FastAPI uses 8001)

5. **Documentation files:**
   - `README.md` - References port 8000 and server.py
   - `docs/quick-start-modernization.md` - References old server
   - `docs/modernization-plan.md` - References old server
   - `docs/copilot-instructions.md` - References old server
   - `docs/teardown-feature-example.md` - References server.py

6. **Configuration files:**
   - `pyproject.toml` - Includes server.py in coverage (line 40, 58)
   - `mypy.ini` - Has config for server.py (line 18)

### Old Server Files (Can be removed)

1. **`src/app/server.py`** - The entire old server (2,421 lines)
2. **`src/app/templates/`** - HTML templates (19 files)
3. **`src/app/static/`** - CSS and JavaScript (7 files)

## Cleanup Options

### Option 1: Mark as Deprecated (Recommended First Step)
- Add deprecation notice to `server.py`
- Update all documentation to note deprecation
- Update scripts to use FastAPI
- Keep files for reference but mark as unused

### Option 2: Remove Entirely (After Option 1)
- Delete `server.py`, `templates/`, and `static/` directories
- Update all references in docs/scripts
- Remove from coverage/config files
- Clean commit history if desired

### Option 3: Archive to Separate Branch
- Create `legacy-server` branch
- Move old server files there
- Keep main branch clean

## Recommended Cleanup Steps

### Phase 1: Update References (Safe - No Deletion)
1. ✅ Update `dev.sh` - Already defaults to FastAPI
2. ⚠️ Update `scripts/mac/create_lego_app.sh` - Change to FastAPI
3. ⚠️ Update `src/scripts/snapshot_contracts.py` - Change port to 8001
4. ⚠️ Update `README.md` - Document FastAPI/Next.js instead
5. ⚠️ Update all `docs/*.md` files - Remove/update old server references
6. ⚠️ Add deprecation notice to `server.py` top

### Phase 2: Remove Files (After Verification)
1. Delete `src/app/server.py`
2. Delete `src/app/templates/` directory
3. Delete `src/app/static/` directory
4. Update `pyproject.toml` - Remove server.py from coverage
5. Update `mypy.ini` - Remove server.py config
6. Update `requirements.txt` - Remove Jinja2 if not used elsewhere

## Files to Update

### High Priority (Active Usage)
- [ ] `scripts/mac/create_lego_app.sh` - Update to FastAPI
- [ ] `src/scripts/snapshot_contracts.py` - Update port
- [ ] `README.md` - Update documentation

### Medium Priority (Documentation)
- [ ] `docs/quick-start-modernization.md`
- [ ] `docs/modernization-plan.md`
- [ ] `docs/copilot-instructions.md`
- [ ] `docs/teardown-feature-example.md`

### Low Priority (Configuration)
- [ ] `pyproject.toml` - Remove from coverage
- [ ] `mypy.ini` - Remove config
- [ ] `requirements.txt` - Check if Jinja2 still needed

## Verification Checklist

Before removing files, verify:
- [ ] All tests pass with FastAPI
- [ ] Next.js frontend works completely
- [ ] No scripts depend on old server
- [ ] Documentation updated
- [ ] macOS app script updated
- [ ] All references updated

