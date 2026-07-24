# Move local data to another machine

This package contains the gitignored local state for **Ervin-Burdick's Bricks** (`lego_inventory`). The git repo can already exist on the destination machine; you only need to unpack this archive into it.

**Created:** 2026-07-24  
**Source DB integrity:** `PRAGMA integrity_check` → `ok` (WAL checkpointed before packaging)

## What’s in the zip

| Path in archive | Destination |
|---|---|
| `data/lego_inventory.db` | `data/lego_inventory.db` (required) |
| `data/.env` | `data/.env` (required — credentials + safe mode) |
| `data/reports/` | `data/reports/` (optional) |
| `data/instabrick_inventory.xml` | `data/instabrick_inventory.xml` (optional) |
| `data/backups/` | `data/backups/` (optional historical snapshots) |
| `MIGRATE_SETUP.md` | (this file — keep or discard) |

Excluded on purpose: `*.db-wal` / `*.db-shm`, `*.broken`, empty legacy `inventory.db`, `.DS_Store`.

> **Security:** The zip includes `data/.env` with Rebrickable credentials. Transfer privately (AirDrop, USB, `scp`). Do not commit the zip or `.env` to git. Delete the zip after a successful restore.

## Prerequisites on the other machine

- Repo already cloned (any recent `main` / your working branch)
- Python 3.9+ and Node.js 18+ (same as usual for this project)
- Stop any local server that might recreate an empty DB

## Restore steps

From the **repo root** on the destination machine:

```bash
cd /path/to/lego_inventory

# Optional: keep any existing empty data/ out of the way
if [ -d data ]; then mv data "data.bak.$(date +%Y%m%d%H%M%S)"; fi

# Unpack (creates ./data/...)
unzip -o /path/to/lego_inventory_local_data_20260724.zip

# Verify
sqlite3 data/lego_inventory.db "PRAGMA integrity_check;"
# expect: ok

ls -la data/lego_inventory.db data/.env
```

Confirm paths in `.env` (already portable relative paths):

- `APP_DB_PATH=./data/lego_inventory.db`
- `APP_REPORTS_DIR=./data/reports`
- `APP_SAFE_MODE=true` (matches the source machine)

## Start the app

```bash
./dev.sh
```

- Frontend: http://localhost:3001  
- Backend / API docs: http://localhost:8001/docs  

`./dev.sh` installs deps, runs tests against a **temporary** DB, then starts servers against `data/lego_inventory.db` (with `APP_DB_PATH` unset for the live server).

If you prefer a quicker bring-up after deps already exist:

```bash
source .venv/bin/activate
PYTHONPATH=src python -m app.settings   # should show db_path under this repo's data/
# then start via ./dev.sh or your usual uvicorn + next commands
```

## Smoke-check that the right DB loaded

1. Open the sets list — counts/names should match the source machine.
2. Spot-check one set you know well (status, image, part counts).
3. If you use Rebrickable sync/scripts, confirm credentials still work.

Quick DB row sanity (optional):

```bash
sqlite3 data/lego_inventory.db ".tables"
```

## If something looks wrong

| Symptom | Fix |
|---|---|
| Empty / fresh schema | You unpacked outside the repo, or `APP_DB_PATH` points elsewhere — fix `.env` and restart |
| Integrity check fails | Re-copy the zip; do not use a partial transfer |
| Rebrickable API errors | Confirm `data/.env` was unpacked; keys must be present (see README for `APP_REBRICKABLE_*` naming if you regenerate `.env`) |
| Location/drawer UI missing | Expected while `APP_SAFE_MODE=true` |

## After a successful migrate

1. Keep the source machine’s `data/` (or this zip) until you’ve used the destination for a few days.
2. Delete the zip from Downloads / USB once you’re confident.
3. Prefer treating **one** machine as the writer going forward to avoid divergent DBs (SQLite is a single-file DB, not a sync service).
