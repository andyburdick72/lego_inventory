# lego_inventory — Ervin-Burdick's Bricks

Personal LEGO inventory management system. Flask/FastAPI backend + Next.js frontend.

## GitHub

This repo belongs to the **andyburdick72** account. Use the github-personal MCP connector and `gh` as `andyburdick72` (never `andy-cleverlawn` here).

### Roadmap board
- **Project #1**: [LEGO Inventory Management System Roadmap](https://github.com/users/andyburdick72/projects/1)
- **Status**: To Do / In Progress / Done
- **Priority** / **Size**: project fields (`P1|P2|P3`, `S|M|L`) — **not** labels
- Default assignee: `andyburdick72`

### Labels (existing only — do not invent new ones)
- `type:*` — feature | bug | refactor | test | exploration
- `area:*` — backend | frontend | scripts
- `copilot` — multi-file / AI-assisted work

### Milestones
- Epic-style only (multiple related issues). Current: *Deploy: bricks.ervinburdick.com*.
- Do **not** create one-issue “phase” milestones; track single issues with project Status/Priority/Size.

### Creating issues
Prefer `/create-issue` or `scripts/gh_create_issue.sh`. Always: add to Project #1, set Status/Priority/Size, assign Andy. Need `gh` scopes `repo` + `project` (or `read:project`) on the personal account.

## Project Context

Personal side project. Solo developer (Andy). Not a business product — built for managing a personal LEGO collection. Low stakes, experimental.

## Stack

**Backend** (`src/`)
- Python 3.13, FastAPI + uvicorn (API server on port 8001)
- SQLAlchemy 2.0, Pydantic v2, pydantic-settings
- SQLite database at `data/lego_inventory.db`
- Config loaded via `app/settings.py` → `get_settings()` (cached); env prefix `APP_`; `.env` at `data/.env`

**Frontend** (`frontend/`)
- Next.js (port 3001), React Query, Radix UI, Tailwind

## Source Layout

```
src/
  app/        # FastAPI app: routes, DI, settings, error handling
    api/v1/   # Route handlers (drawers, sets, parts, inventory, putaway, …)
  core/       # Domain DTOs, enums, service interfaces
  infra/      # DB layer (SQLAlchemy), repository implementations
  integrations/ # Rebrickable API client
  scripts/    # One-off data scripts
  utils/      # Shared helpers
tests/
  unit/       # Fast, isolated
  infra/      # DB/repository tests
  contract/   # HTTP-level tests against a live test server (marked `contract`)
  smoke/      # Smoke tests
```

## Running Locally

```bash
./dev.sh        # runs unit + infra + smoke + contract tests, then starts both servers
./dev.sh cov    # same but with coverage merge
```

The script activates `.venv`, installs deps, spins up a temporary test DB for contract tests, then starts FastAPI (port 8001) and Next.js (port 3001).

**Env vars of note:**
- `APP_SAFE_MODE=true` — enables set-centric safe mode (hides location-dependent UI/endpoints)
- `APP_DB_PATH` — override DB path (used by dev.sh for test isolation)

## Testing

```bash
# Unit + infra tests only (fast, no server needed)
ALLOW_SMOKE_TESTS=1 pytest -q --no-cov tests/unit/ tests/infra/

# Contract tests (requires server running on port 8001)
pytest -m contract

# Full suite with coverage
./dev.sh cov
```

- Line-length: 100 (`pyproject.toml`)
- Linting: ruff (select E, F, I, UP, B); formatting: black
- Type checking: mypy (strict-ish; `ignore_missing_imports = true`)
- Coverage threshold: 70%

## Key Conventions

- `get_settings()` is a cached singleton — call `get_settings.cache_clear()` in tests that override `APP_DB_PATH`
- Route handlers live in `src/app/api/v1/`; add new resources there
- DTOs/enums belong in `src/core/`; DB models and repos in `src/infra/`
- Contract tests hit a real (ephemeral) SQLite DB — do not mock the DB layer
- `APP_SAFE_MODE` gates features both server-side and in the Next.js frontend via `NEXT_PUBLIC_APP_SAFE_MODE`
