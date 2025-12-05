# Test Migration Plan

## Overview
This document outlines the plan for updating existing tests to work with the new FastAPI/Next.js architecture, replacing references to the old Python server (`server.py`).

## ✅ Migration Status: COMPLETED

**Date Completed:** 2024

**Summary of Changes:**
- ✅ Updated `dev.sh` to start FastAPI server on port 8001 for contract tests
- ✅ Updated all existing contract tests to use `/api/v1` endpoints
- ✅ Created 4 new test files for new API endpoints (inventory, parts, sets, scripts)
- ✅ Added FastAPI TestClient fixture to `conftest.py`
- ✅ Removed obsolete UI tests (`test_hyperlink_columns.py`)
- ✅ Removed obsolete export tests (`test_export.py`)
- ✅ Updated `pytest.ini` with updated markers
- ✅ Added health check and root endpoint tests

## Current Test Structure

### Test Categories

1. **Unit Tests** (✅ No changes needed)
   - `tests/unit/` - Test individual components in isolation
   - These don't reference the server and should continue working

2. **Contract Tests** (⚠️ Need URL updates)
   - `tests/contract/api/` - Test API endpoints via HTTP
   - Currently reference `http://localhost:8000` (old server)
   - Need to update to FastAPI endpoints (`http://localhost:8001/api/v1`)

3. **UI Tests** (❌ Need complete rewrite)
   - `tests/ui/test_hyperlink_columns.py` - Test HTML rendering
   - Uses BeautifulSoup to parse HTML responses
   - References old server HTML routes (`/`, `/parts/{id}`)
   - **These tests are obsolete** - Next.js renders client-side, not server-side HTML

4. **Export Tests** (❌ Need rewrite)
   - `tests/contract/api/test_export.py` - Test CSV export endpoint
   - References `/export` endpoint from old server
   - **This endpoint doesn't exist in FastAPI** - CSV export is now client-side via DataTable

5. **Smoke Tests** (✅ No changes needed)
   - `tests/smoke/` - Test database operations directly
   - Don't reference the server, should continue working

## Detailed Migration Plan

### Phase 1: Contract Tests (API Endpoints)

**Files to Update:**
- `tests/contract/api/test_api_edges.py`
- `tests/contract/api/test_write_endpoints.py`
- `tests/contract/api/test_drawers_contract.py`
- `tests/contract/api/test_containers_contract.py`
- `tests/contract/api/test_errors_normalized.py`

**Changes Required:**

1. **Update Base URLs:**
   - Old: `http://localhost:8000` or `http://localhost:8000/api`
   - New: `http://localhost:8001/api/v1` (FastAPI default port)

2. **Update Endpoint Paths:**
   - Old: `/api/drawers` → New: `/api/v1/drawers`
   - Old: `/api/drawers/create` → New: `/api/v1/drawers/create`
   - Old: `/api/containers` → New: `/api/v1/containers`
   - Old: `/api/containers/create` → New: `/api/v1/containers/create`
   - Similar updates for all other endpoints

3. **Update Environment Variables:**
   - `tests/conftest.py` - Update default URL in help text
   - `tests/contract/api/test_write_endpoints.py` - Update `APP_BASE_URL` default

4. **Response Format Changes:**
   - FastAPI returns Pydantic models, which may have slightly different field names
   - Verify response shapes match expected DTOs
   - Update assertions if field names changed (e.g., `label` vs `name`)

**Action Items:**
- [ ] Update all base URLs to use FastAPI port (8001) and `/api/v1` prefix
- [ ] Update all endpoint paths to include `/v1`
- [ ] Verify response formats match FastAPI DTOs
- [ ] Update any field name assertions (e.g., `name` vs `label`)
- [ ] Test with running FastAPI server

### Phase 2: Export Tests (Remove/Replace)

**File:** `tests/contract/api/test_export.py`

**Status:** ❌ **This test file should be removed or significantly rewritten**

**Reason:** 
- The old server had a `/export` endpoint that generated CSV server-side
- The new Next.js frontend uses client-side CSV export via the DataTable component
- There is no server-side export endpoint in FastAPI

**Options:**
1. **Remove the test file** (recommended) - Export is now a frontend feature
2. **Create a new API endpoint** - If server-side export is needed, add `/api/v1/export` endpoint
3. **Add frontend E2E tests** - Test CSV export using Playwright/Cypress

**Action Items:**
- [ ] Decide: Remove test or add export endpoint
- [ ] If removing: Delete `test_export.py`
- [ ] If keeping: Add FastAPI export endpoint and update tests
- [ ] Document decision in test README

### Phase 3: UI Tests (Remove/Replace)

**File:** `tests/ui/test_hyperlink_columns.py`

**Status:** ❌ **This test file should be removed or converted to E2E tests**

**Reason:**
- Tests HTML rendering from server-side templates
- Next.js renders client-side, so server doesn't return HTML
- These tests check for specific HTML structure that no longer exists

**Options:**
1. **Remove the test file** (recommended) - UI is now client-side
2. **Convert to E2E tests** - Use Playwright/Cypress to test rendered Next.js pages
3. **Add component tests** - Test React components directly with React Testing Library

**Action Items:**
- [ ] Decide: Remove test or convert to E2E
- [ ] If removing: Delete `test_hyperlink_columns.py`
- [ ] If converting: Set up Playwright/Cypress and rewrite tests
- [ ] Document decision in test README

### Phase 4: Update Test Configuration

**Files:**
- `tests/conftest.py`
- `pytest.ini`

**Changes:**
1. Update default API base URL in `conftest.py`
2. Add marker for E2E tests if adding Playwright/Cypress
3. Update documentation/comments about test setup

**Action Items:**
- [ ] Update `conftest.py` default URL references
- [ ] Add E2E test markers if needed
- [ ] Update test documentation

### Phase 5: Add FastAPI Test Client (Optional but Recommended)

**New File:** `tests/conftest.py` (add FastAPI test client)

**Purpose:** Allow running contract tests against FastAPI TestClient instead of requiring a running server

**Implementation:**
```python
from fastapi.testclient import TestClient
from app.api.main import app

@pytest.fixture
def fastapi_client():
    """FastAPI test client for unit/contract tests."""
    return TestClient(app)
```

**Action Items:**
- [ ] Add FastAPI TestClient fixture to `conftest.py`
- [ ] Create separate contract tests that use TestClient
- [ ] Keep existing contract tests for integration testing against running server

## Test Execution Strategy

### Running Updated Tests

1. **Unit Tests** (unchanged):
   ```bash
   pytest tests/unit/
   ```

2. **Contract Tests** (updated):
   ```bash
   # With running FastAPI server
   API_BASE_URL=http://localhost:8001/api/v1 pytest tests/contract/api/
   
   # Or with TestClient (if implemented)
   pytest tests/contract/api/
   ```

3. **Smoke Tests** (unchanged):
   ```bash
   ALLOW_SMOKE_TESTS=1 pytest tests/smoke/
   ```

4. **E2E Tests** (if added):
   ```bash
   # With running Next.js dev server
   pytest tests/e2e/
   ```

## Migration Checklist

### Immediate Actions (Before Feature Development)
- [ ] Review and update contract test base URLs
- [ ] Update contract test endpoint paths
- [ ] Remove or document obsolete UI tests
- [ ] Remove or rewrite export tests
- [ ] Verify all contract tests pass against FastAPI

### Future Enhancements
- [ ] Add FastAPI TestClient for faster test execution
- [ ] Set up E2E testing framework (Playwright/Cypress)
- [ ] Add frontend component tests (React Testing Library)
- [ ] Add API integration tests for new features

## Notes

- **Backward Compatibility**: The old Python server (`server.py`) still exists but is deprecated
- **Test Coverage**: Unit and smoke tests should maintain current coverage
- **Contract Tests**: These are integration tests that verify API contracts - important to keep updated
- **UI Tests**: Server-side HTML rendering tests are no longer applicable

## New API Endpoints Requiring Tests

### Inventory Endpoints (NEW - No existing tests)

**File to Create:** `tests/contract/api/test_inventory_contract.py`

**Endpoints to Test:**
1. `GET /api/v1/inventory/total-count`
   - Returns total part count across all sets
   - Test: Valid response with count field
   - Test: Returns 0 when no sets exist

2. `GET /api/v1/inventory/loose`
   - Returns all loose inventory items
   - Test: Returns list of inventory items
   - Test: Empty list when no loose parts
   - Test: Response includes all required fields (part_id, color_id, quantity, drawer_name, container_label, etc.)

3. `GET /api/v1/inventory/part-counts`
   - Returns part counts grouped by design_id
   - Test: Returns list sorted by quantity descending
   - Test: Includes part_name, part_url, part_img_url
   - Test: Aggregates quantities correctly across sets
   - Test: Handles parts with missing metadata gracefully

4. `GET /api/v1/inventory/part-color-counts`
   - Returns part+color counts grouped by design_id and color_id
   - Test: Returns list sorted by quantity descending
   - Test: Includes color information (color_id, color_name, hex)
   - Test: Aggregates quantities correctly
   - Test: Handles missing color data gracefully

5. `GET /api/v1/inventory/location-counts`
   - Returns inventory totals by storage location
   - Test: Returns list sorted by quantity descending
   - Test: Combines drawer and container names correctly
   - Test: Handles locations with only drawer or only container
   - Test: Returns drawer_id and container_id for linking

**Test Structure:**
```python
def test_inventory_total_count(client):
    """Test total part count endpoint."""
    r = client.get("/api/v1/inventory/total-count")
    assert r.status_code == 200
    data = r.json()
    assert "total_count" in data
    assert isinstance(data["total_count"], int)
    assert data["total_count"] >= 0

def test_inventory_loose_parts(client):
    """Test loose inventory listing."""
    r = client.get("/api/v1/inventory/loose")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    if data:
        item = data[0]
        assert "part_id" in item
        assert "color_id" in item
        assert "quantity" in item
        assert "status" in item
        assert item["status"] == "loose"

# Similar tests for other endpoints...
```

### Parts Endpoints (NEW - No existing tests)

**File to Create:** `tests/contract/api/test_parts_contract.py`

**Endpoints to Test:**
1. `GET /api/v1/parts/{design_id}`
   - Returns part metadata
   - Test: Returns 200 with part data for valid design_id
   - Test: Returns 404 for invalid design_id
   - Test: Includes design_id, name, part_url, part_img_url

2. `GET /api/v1/parts/{design_id}/loose`
   - Returns loose inventory for a specific part
   - Test: Returns list of inventory items for part
   - Test: Returns empty list if part has no loose inventory
   - Test: Returns 404 for invalid design_id
   - Test: All items have matching design_id
   - Test: Includes drawer/container information

3. `GET /api/v1/parts/{design_id}/sets`
   - Returns sets containing a specific part
   - Test: Returns list of sets with the part
   - Test: Returns empty list if part not in any sets
   - Test: Returns 404 for invalid design_id
   - Test: Includes set_number, set_name, color_id, quantity

**Test Structure:**
```python
def test_get_part_by_id(client):
    """Test getting part by design_id."""
    r = client.get("/api/v1/parts/3001")
    assert r.status_code == 200
    data = r.json()
    assert data["design_id"] == "3001"
    assert "name" in data

def test_get_part_404(client):
    """Test 404 for invalid part."""
    r = client.get("/api/v1/parts/invalid-part-id")
    assert r.status_code == 404

def test_get_part_loose_inventory(client):
    """Test getting loose inventory for a part."""
    r = client.get("/api/v1/parts/3001/loose")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    # Verify all items are for the correct part
    for item in data:
        assert item["part_id"] == "3001"
        assert item["status"] == "loose"
```

### Sets Endpoints (NEW - No existing tests)

**File to Create:** `tests/contract/api/test_sets_contract.py`

**Endpoints to Test:**
1. `GET /api/v1/sets/count`
   - Returns total set count
   - Test: Returns count field
   - Test: Returns 0 when no sets exist

2. `GET /api/v1/sets`
   - Returns list of all sets
   - Test: Returns list of sets
   - Test: Includes all required fields (set_number, name, status, total_parts, etc.)
   - Test: Sorted by added_at DESC
   - Test: Empty list when no sets exist

3. `GET /api/v1/sets/{set_number}`
   - Returns specific set details
   - Test: Returns 200 with set data for valid set_number
   - Test: Returns 404 for invalid set_number
   - Test: Includes all metadata fields

4. `GET /api/v1/sets/{set_number}/parts`
   - Returns parts in a set
   - Test: Returns list of parts for set
   - Test: Returns empty list if set has no parts
   - Test: Returns 404 for invalid set_number
   - Test: Includes part details (design_id, name, color, quantity)

5. `PATCH /api/v1/sets/{set_number}/status`
   - Updates set status
   - Test: Updates status successfully
   - Test: Returns 404 for invalid set_number
   - Test: Returns 422 for invalid status value
   - Test: Validates status enum values

**Test Structure:**
```python
def test_list_sets(client):
    """Test listing all sets."""
    r = client.get("/api/v1/sets")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    if data:
        set_item = data[0]
        assert "set_number" in set_item
        assert "name" in set_item
        assert "status" in set_item

def test_update_set_status(client):
    """Test updating set status."""
    # First get a valid set
    sets = client.get("/api/v1/sets").json()
    if not sets:
        pytest.skip("No sets available for testing")
    
    set_num = sets[0]["set_number"]
    r = client.patch(
        f"/api/v1/sets/{set_num}/status",
        json={"status": "built"}
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "built"
```

### Scripts Endpoints (NEW - No existing tests)

**File to Create:** `tests/contract/api/test_scripts_contract.py`

**Endpoints to Test:**
1. `POST /api/v1/scripts/sync-rebrickable-parts`
   - Syncs parts from Rebrickable
   - Test: Accepts request and returns success message
   - Test: Handles all_sets parameter
   - Test: Returns appropriate error for invalid requests
   - **Note:** These are long-running operations, may need async/mocking

2. `POST /api/v1/scripts/sync-rebrickable-sets`
   - Syncs sets from Rebrickable
   - Test: Accepts request and returns success message
   - Test: Handles default_status parameter
   - Test: Returns appropriate error for invalid requests
   - **Note:** These are long-running operations, may need async/mocking

**Test Structure:**
```python
def test_sync_parts_basic(client):
    """Test sync parts endpoint accepts request."""
    r = client.post(
        "/api/v1/scripts/sync-rebrickable-parts",
        json={"all_sets": False}
    )
    # May return 200 immediately or 202 Accepted for async
    assert r.status_code in (200, 202)
    # Verify response structure
    data = r.json()
    assert "message" in data or "success" in data

# Note: Full integration tests may require mocking Rebrickable API
```

### Health Check Endpoints (NEW - Simple tests)

**Add to:** `tests/contract/api/test_api_edges.py` or new file

**Endpoints to Test:**
1. `GET /`
   - Health check
   - Test: Returns 200 with API info

2. `GET /health`
   - Health check
   - Test: Returns 200 with status ok

## Additional Recommended Tests

### Error Handling Tests

**File to Create/Update:** `tests/contract/api/test_errors_comprehensive.py`

**Test Cases:**
- Invalid JSON in request body
- Missing required fields
- Invalid field types
- Out of range values
- SQL injection attempts (sanitization)
- XSS attempts (if applicable)
- Rate limiting (if implemented)
- Authentication/authorization (if added)

### Edge Case Tests

**Add to existing contract test files:**

1. **Empty Database Tests:**
   - All endpoints handle empty database gracefully
   - No 500 errors on empty results
   - Proper empty list/object responses

2. **Large Dataset Tests:**
   - Performance with many records
   - Pagination (if implemented)
   - Memory usage

3. **Data Integrity Tests:**
   - Foreign key constraints
   - Unique constraints
   - Soft delete behavior
   - Cascade deletes

### Integration Tests

**File to Create:** `tests/integration/test_full_workflows.py`

**Test Scenarios:**
1. **Create Drawer → Create Container → Add Inventory → View Counts**
   - Full workflow from creation to viewing

2. **Create Set → Sync Parts → View Set Parts → Update Status**
   - Full set management workflow

3. **Part Detail → View Loose → View In Sets → Navigate to Set**
   - Full navigation workflow

### Performance Tests (Optional)

**File to Create:** `tests/performance/test_api_performance.py`

**Test Cases:**
- Response time for large datasets
- Concurrent request handling
- Database query optimization
- Memory usage under load

## Updated Test File Structure

```
tests/
├── contract/
│   └── api/
│       ├── test_api_edges.py (UPDATE)
│       ├── test_containers_contract.py (UPDATE)
│       ├── test_drawers_contract.py (UPDATE)
│       ├── test_errors_normalized.py (UPDATE)
│       ├── test_write_endpoints.py (UPDATE)
│       ├── test_export.py (REMOVE or REWRITE)
│       ├── test_inventory_contract.py (NEW)
│       ├── test_parts_contract.py (NEW)
│       ├── test_sets_contract.py (NEW)
│       ├── test_scripts_contract.py (NEW)
│       └── test_errors_comprehensive.py (NEW)
├── integration/
│   └── test_full_workflows.py (NEW)
├── performance/ (OPTIONAL)
│   └── test_api_performance.py (NEW)
└── ui/
    └── test_hyperlink_columns.py (REMOVE or CONVERT to E2E)
```

## Updated Migration Checklist

### Phase 1: Update Existing Contract Tests
- [ ] Update base URLs to FastAPI (`localhost:8001/api/v1`)
- [ ] Update endpoint paths with `/v1` prefix
- [ ] Verify response formats match FastAPI DTOs
- [ ] Update field name assertions if needed

### Phase 2: Remove Obsolete Tests
- [ ] Remove `test_export.py` (or rewrite if export endpoint added)
- [ ] Remove `test_hyperlink_columns.py` (or convert to E2E)

### Phase 3: Add New Contract Tests
- [ ] Create `test_inventory_contract.py` (5 endpoints)
- [ ] Create `test_parts_contract.py` (3 endpoints)
- [ ] Create `test_sets_contract.py` (5 endpoints)
- [ ] Create `test_scripts_contract.py` (2 endpoints)
- [ ] Add health check tests to `test_api_edges.py`

### Phase 4: Add Error Handling Tests
- [ ] Create `test_errors_comprehensive.py`
- [ ] Test invalid inputs, missing fields, type errors
- [ ] Test edge cases (empty DB, large datasets)

### Phase 5: Add Integration Tests (Optional)
- [ ] Create `test_full_workflows.py`
- [ ] Test complete user workflows end-to-end

### Phase 6: Add Performance Tests (Optional)
- [ ] Create `test_api_performance.py`
- [ ] Test response times and concurrent requests

## Questions to Resolve

1. Do we need server-side CSV export? (Currently only client-side)
2. Should we add E2E tests for Next.js pages?
3. Should we add React component tests?
4. Do we want to keep the old server running for comparison during migration?
5. **NEW:** Should scripts endpoints be tested with mocked Rebrickable API or real API calls?
6. **NEW:** Do we need performance/load testing, or is current coverage sufficient?
7. **NEW:** Should we add integration tests for full workflows, or rely on unit + contract tests?

