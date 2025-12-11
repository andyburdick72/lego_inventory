# Test Database Isolation

## Overview

Tests are **completely isolated** from your production inventory database. This document explains how the isolation works and why your inventory is safe.

## How It Works

### 1. Test Database Creation
- When `./dev.sh` runs contract tests, it creates a **temporary test database** using `mktemp`
- The test database is stored in the repo root with a name like `.test_contract_XXXXXX.db`
- This is a **completely separate file** from your production database

### 2. Test Server Isolation
- The test server runs in a **separate background process** (via `&` in bash)
- The test server process has `APP_DB_PATH` environment variable set to the test database
- The test server **only** uses the test database - it cannot access your production database

### 3. Test Execution
- All contract tests run against the test server
- Tests can create, modify, and delete data in the test database
- **Your production database is never touched**

### 4. Cleanup
- After tests complete, the test server process is **killed**
- The temporary test database file is **deleted** (`rm -f`)
- The `APP_DB_PATH` environment variable is **unset**

### 5. Dev Server Startup
- The dev server starts in a **new process** (via `exec python -m uvicorn`)
- Since `APP_DB_PATH` is unset, it uses the **default database** (`data/lego_inventory.db`)
- The dev server **cannot** access the test database because:
  - The test database file has been deleted
  - The test server process has been killed
  - `APP_DB_PATH` is unset

## Safety Checks

The `dev.sh` script includes multiple safety checks:

1. **Verification that `APP_DB_PATH` is unset** before starting dev server
2. **Verification that test database file is deleted** before starting dev server
3. **Explicit logging** showing which database the dev server will use

## Process Isolation

- **Test server**: Runs in background process with `APP_DB_PATH` set to test database
- **Dev server**: Runs in new process with `APP_DB_PATH` unset (uses default database)
- **Python module caching**: Each process has its own Python interpreter, so `@lru_cache` on `get_settings()` is per-process

## Your Inventory is Safe

✅ Tests run against a temporary database that is deleted after tests  
✅ Test server runs in a separate process that is killed before dev server starts  
✅ Dev server uses the default production database  
✅ Multiple safety checks verify isolation  
✅ Test database file is explicitly removed before dev server starts  

## Verification

When you run `./dev.sh`, you'll see:
```
🔒 SAFETY CHECK: Verifying database isolation...
   - Test database: .test_contract_XXXXXX.db (should be removed)
   - Production database: /path/to/data/lego_inventory.db
   - APP_DB_PATH: <unset - will use default>
   ✅ Dev server will use production database
```

This confirms that:
- The test database has been removed
- The dev server will use your production database
- No test data can leak into your inventory
