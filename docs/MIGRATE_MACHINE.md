# Move the app to another machine

Until **bricks.ervinburdick.com** (Render + Supabase) is live, this project is a **local dual-process app** with a gitignored SQLite DB. Moving machines means copying **gitignored local state** — not just cloning the repo.

Prefer **one writer machine** at a time. SQLite is a single-file DB, not a sync service.

## What moves vs what you recreate

| Item | Action |
|---|---|
| Git repo (`main`) | Clone / pull on the destination |
| `data/lego_inventory.db` | **Copy** (required) |
| `data/.env` | **Copy** (required — Rebrickable creds + `APP_SAFE_MODE`) |
| `data/reports/`, `data/backups/`, Instabrick XML | Copy if you care about them |
| `.venv/` | **Do not copy** — recreate on the destination |
| `frontend/node_modules/` | **Do not copy** — `npm install` on the destination |

`data/` is gitignored on purpose. Never commit `.env`, the DB, or a migrate zip.

## Prerequisites (destination)

- Git access to `andyburdick72/lego_inventory` (HTTPS or SSH)
- **Python 3.10+** (3.13 recommended; matches tooling / pinned deps)
- **Node.js 18+** and npm
- `sqlite3` CLI (for integrity checks)
- Stop any local server that might create an empty DB under `data/`

If you use SSH host aliases for multiple GitHub accounts (e.g. `github.com-andyburdick72`), clone with that host — a stale alias like `github-personal` will fail DNS.

## 1. Source machine — package local data

From the **repo root**, with servers stopped (or at least no writers):

```bash
# Checkpoint WAL into the main DB file
sqlite3 data/lego_inventory.db "PRAGMA wal_checkpoint(TRUNCATE); PRAGMA integrity_check;"
# expect: ok

STAMP=$(date +%Y%m%d)
OUT="$HOME/Desktop/lego_inventory_local_data_${STAMP}.zip"
REPO_ROOT="$(pwd)"

zip -r "$OUT" \
  data/lego_inventory.db \
  data/.env \
  data/reports \
  data/instabrick_inventory.xml \
  data/backups \
  -x "*.DS_Store" "*/*.db-wal" "*/*.db-shm" "*/*.broken"

# Optional: self-describing zip — copy this guide to the archive root as MIGRATE_SETUP.md
(
  cd "$(mktemp -d)"
  cp "$REPO_ROOT/docs/MIGRATE_MACHINE.md" MIGRATE_SETUP.md
  zip -j "$OUT" MIGRATE_SETUP.md
)

ls -lh "$OUT"
```

Transfer the zip privately (AirDrop, USB, `scp`). Do not push it to GitHub.

After clone, prefer **`docs/MIGRATE_MACHINE.md`** in-repo. A zip-root `MIGRATE_SETUP.md` is only for someone who opened the archive first — it is **not** a permanent file in the repo root.

## 2. Destination machine — clone and restore

```bash
# Prefer SSH with your personal-account host alias if configured
git clone git@github.com-andyburdick72:andyburdick72/lego_inventory.git
# or: git clone https://github.com/andyburdick72/lego_inventory.git

cd lego_inventory

# Recreate venv at THIS path (never reuse a copied .venv — activate embeds absolute paths)
python3.13 -m venv .venv   # or: python3 -m venv .venv  (must be 3.10+)
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt -r requirements-dev.txt

# Frontend deps (dev.sh does not run npm install)
cd frontend && npm install && cd ..

# Restore local data
if [ -d data ]; then mv data "data.bak.$(date +%Y%m%d%H%M%S)"; fi
unzip -o /path/to/lego_inventory_local_data_YYYYMMDD.zip

sqlite3 data/lego_inventory.db "PRAGMA integrity_check;"
# expect: ok
ls -la data/lego_inventory.db data/.env
```

Confirm `data/.env` still has portable relative paths:

- `APP_DB_PATH=./data/lego_inventory.db`
- `APP_REPORTS_DIR=./data/reports`
- `APP_SAFE_MODE=…` (match the source machine if you want the same UI gating)

## 3. Start the app

Canonical bring-up (installs Python deps, runs tests against a **temporary** DB, then starts both servers against production `data/lego_inventory.db`):

```bash
source .venv/bin/activate
./dev.sh
```

- Frontend: http://localhost:3001  
- Backend / API docs: http://localhost:8001/docs  

**Both processes are required.** If only Next.js is running, the UI loads but every data fetch fails (“Error loading count / sets”).

### Faster daily start (after deps exist)

```bash
# terminal 1 — API
source .venv/bin/activate
export PYTHONPATH=src
unset APP_DB_PATH
python -m uvicorn app.api.main:app --host 0.0.0.0 --port 8001 --reload

# terminal 2 — UI
cd frontend && npm run dev
```

## 4. Smoke-check

1. Sets list count/names match the source machine.
2. Spot-check one known set (status, image, part counts).
3. Header total part count loads (not “Error loading count”).
4. Optional: `sqlite3 data/lego_inventory.db "SELECT COUNT(*) FROM sets;"`

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Could not resolve hostname github-…` | Remote URL uses an SSH alias missing from `~/.ssh/config`. Use a configured `Host` (e.g. `github.com-andyburdick72`) or HTTPS. |
| `python: command not found` with `(.venv)` active | Venv was created on another path/machine. Delete `.venv` and recreate with `python3 -m venv .venv`. |
| Frontend “may have failed to start” / blank deps | Run `cd frontend && npm install`, then `npm run dev`. |
| UI up, “Error loading sets/count” | Backend not on `:8001`. Start uvicorn / `./dev.sh`. |
| Empty / fresh schema | Unpacked outside repo root, or `APP_DB_PATH` wrong — fix `.env` and restart. |
| Integrity check fails | Re-copy the zip; don’t use a partial transfer. |
| Rebrickable API errors | Confirm `data/.env` was restored with `APP_REBRICKABLE_*` keys. |
| Location/drawer UI missing | Expected while `APP_SAFE_MODE=true`. |

## After a successful migrate

1. Keep the source `data/` (or zip) for a few days.
2. Delete the zip from Downloads / USB once confident.
3. Treat **one** machine as the writer going forward.

When hosted deploy ships, prefer the cloud DB as source of truth and treat this guide as a fallback for offline/dev snapshots only.
