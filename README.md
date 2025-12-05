# LEGO Inventory Management System

A SQLite-backed inventory management system for LEGO parts and sets.  
Uses [Rebrickable](https://rebrickable.com/api/) as the canonical source and supports importing inventory from Instabrick/BrickLink XML exports.

---

## **Features**
- **Data import from Instabrick XML** with BrickLink → Rebrickable ID conversion  
- **Alias reconciliation** between BrickLink/Instabrick IDs and Rebrickable part & color IDs  
- **Full CRUD** for drawers, containers, and sets  
- **Merge / move inventory** between locations  
- **Set management**:
  - Track multiple copies of a set
  - Store Rebrickable metadata (image, theme, year, etc.)
  - Set statuses: **Built**, **In Box**, **Work in Progress**, **Teardown**, **Loose Parts**
- **Part-out** a set into loose inventory
- **Move parts** between sets and loose inventory
- **Hierarchical views** for loose parts and parts by set (collapsible, sortable, searchable)  
- **CSV export** for any table, preserving current filters and sorting  
- **Sanity checks** for inventory consistency (loose vs in-sets counts)  
- **Web UI** (no external dependencies) to browse parts, locations, and sets  

---

## **Repository Structure**
```
lego_inventory/
├── data/
│   ├── lego_inventory.db                 # SQLite database
│   ├── instabrick_inventory.xml          # Sample Instabrick export
├── src/
│   ├── app/
│   │   ├── server.py                     # [DEPRECATED] Legacy HTTP server (use FastAPI + Next.js)
│   │   ├── api/                          # FastAPI REST API
│   │   │   └── main.py                   # FastAPI application
│   │   ├── static/
│   │   │   └── styles.css                # CSS for web UI
│   │   └── templates/
│   │       ├── *.html                    # HTML templates for web UI
│   ├── infra/
│   │   └── db/
│   │       └── inventory_db.py           # DB creation & execution helpers
│   ├── scripts/
│   │   ├── load_my_rebrickable_parts.py  # Load parts for all owned sets
│   │   ├── load_rebrickable_colors.py    # Load Rebrickable colors
│   │   ├── precheck_instabrick_inventory.py # Pre-check Instabrick XML for missing aliases
│   │   ├── fix_alias_typos.py            # Fix typos from precheck step
│   │   ├── load_instabrick_inventory.py  # Import Instabrick XML into DB
│   │   └── inventory_sanity_checks.py    # Validate loose vs set inventories
│   └── utils/
│       ├── rebrickable_api.py            # API client helpers
│       ├── rebrickable_generate_user_token.py
│       └── common_functions.py           # .env loader for API keys
├── requirements.txt
├── requirements-dev.txt                  # Dev dependencies (code quality, testing)
└── README.md
```

---

## **Prerequisites**
- **Python 3.9+**
- Dependencies: `requests`  
- Rebrickable API credentials in `.env`:
```env
REBRICKABLE_API_KEY=<your_api_key>
REBRICKABLE_USER_TOKEN=<your_user_token>
REBRICKABLE_USERNAME=<your_username>
REBRICKABLE_PASSWORD=<your_password>
```

---

## **Setup**

### 1. Clone the repo
```bash
git clone https://github.com/andyburdick72/lego_inventory.git
cd lego_inventory
```

### 2. Install dependencies
```bash
pip install requests
```

### 3. Using `dev.sh` for setup and running
The `dev.sh` script is the preferred way to set up and run the project. It handles environment setup, dependency installation, testing, and starts the server.

**Basic usage:**
```bash
./dev.sh
```
This will:
- Install/update dependencies
- Run unit tests with coverage
- Run contract tests (starts FastAPI server automatically)
- Start the FastAPI server on port 8001

**With coverage reporting:**
```bash
./dev.sh cov
```
This runs all tests with coverage reporting and merges unit + contract test coverage.

**Note:** `dev.sh` automatically kills any existing server on port 8001 before starting a new one to ensure fresh code is loaded.

### macOS Launcher (optional)

For convenience, you can generate a macOS app bundle that starts the LEGO server
in a Terminal window with one click.

From the repo root:
```bash
./scripts/mac/create_lego_app.sh
```

This will create **Start LEGO Server.app** in your `~/Applications/` folder
(using `lego.png` in the repo root as its icon). Drag it to your Dock for quick access.

If the Dock icon does not update after regeneration, run:
```bash
killall Dock
```

### 4. Initialize database schema (manual alternative)
```bash
python3 src/inventory_db.py
```

---

## **Workflows**

### **Initial Setup**
1. **Create DB schema**
   ```bash
   python3 src/inventory_db.py
   ```
2. **Load Rebrickable parts & colors**
   ```bash
   python3 src/load_my_rebrickable_parts.py
   python3 src/load_rebrickable_colors.py
   ```
3. **Pre-check Instabrick XML** for missing aliases (optional but recommended)
   ```bash
   python3 src/precheck_instabrick_inventory.py data/instabrick_inventory.xml
   python3 src/fix_alias_typos.py  # if needed
   ```
4. **Load Instabrick XML**
   ```bash
   python3 src/load_instabrick_inventory.py data/instabrick_inventory.xml
   ```

### **Ongoing Maintenance**
- Add/edit drawers, containers, and sets via the web UI  
- Import updated Instabrick XML after inventory changes  
- Run sanity checks:
  ```bash
  python3 src/inventory_sanity_checks.py
  ```
- Part-out sets or move inventory  
- Export any table to CSV for reporting  

---

## **Web UI**

### FastAPI Backend + Next.js Frontend (Recommended)

Run:
```bash
./dev.sh
```

This will:
1. Install/update dependencies
2. Run unit tests with coverage
3. Run contract tests (automatically starts FastAPI server)
4. Start the FastAPI server on port 8001

**Note:** The Next.js frontend must be started separately:
```bash
cd frontend
npm run dev
```

**Access:**
- **Frontend**: http://localhost:3000 (Next.js)
- **API**: http://localhost:8001 (FastAPI)
- **API Docs**: http://localhost:8001/docs (Swagger UI)

**UI Highlights:**
- **Loose Parts by Location** and **Parts by Set**: collapsible hierarchical views  
- Column sorting & searching (per table)  
- CSV export button for every table view
- Modern React-based UI with responsive design

### Legacy Python Server (Deprecated)

The old Python server (`src/app/server.py`) is deprecated. To run it:
```bash
SERVER_TYPE=legacy ./dev.sh
```
Visit: http://localhost:8000

**Note:** The legacy server is maintained for reference only. All new development uses FastAPI + Next.js.  

---

## **Database Schema Overview**
- **colors** — Rebrickable colors  
- **color_aliases** — BrickLink → Rebrickable color mapping  
- **parts** — Canonical Rebrickable part IDs and names  
- **part_aliases** — BrickLink/Instabrick → Rebrickable part mapping  
- **sets** — One row per owned set copy, with status & metadata  
- **set_parts** — Mapping of parts to sets  
- **inventory** — Quantities by part, color, status, and location (drawer, container, or set)  

---

## **Command Reference**
| Script | Purpose |
|--------|---------|
| `inventory_db.py` | Create/initialize DB schema |
| `load_my_rebrickable_parts.py` | Load parts for all owned sets |
| `load_rebrickable_colors.py` | Load Rebrickable color data |
| `precheck_instabrick_inventory.py` | Detect/fix missing aliases before import |
| `fix_alias_typos.py` | Correct typos from precheck step |
| `load_instabrick_inventory.py` | Import Instabrick XML into DB |
| `inventory_sanity_checks.py` | Compare loose vs set inventories |
| `server.py` | [DEPRECATED] Run legacy web UI (use FastAPI + Next.js) |

---

## **Developer Guide**

Developers should generally use `./dev.sh` to start the server and manage dependencies. The instructions below describe manual setup and code quality tools for those who prefer or need to use them.

This section describes recommended practices for local development and code quality.

### 1. Set up a virtual environment
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies
- **Production dependencies:**
  ```bash
  pip install -r requirements.txt
  ```
- **Development dependencies (code quality, testing):**
  ```bash
  pip install -r requirements-dev.txt
  ```

### 3. Code quality tools
- **Run Ruff (lint/fix):**
  ```bash
  ruff check src --fix
  ```
- **Format with Black:**
  ```bash
  black src
  ```
- **Type-check with mypy:**
  ```bash
  mypy src
  ```

### 4. Run tests

- **All tests** (unit + contract):
  ```bash
  pytest
  ```
  Or use `./dev.sh` which runs all tests automatically.

- **Unit tests only**:
  ```bash
  pytest tests/unit/
  ```

- **Contract tests** (API endpoints, requires FastAPI server running):
  ```bash
  export API_BASE_URL=http://localhost:8001/api/v1
  pytest -m contract
  ```
  
  **Note:** The `./dev.sh` script automatically starts the FastAPI server for contract tests, so you don't need to start it manually.

- **All tests with coverage**:
  ```bash
  pytest --cov=src --cov-report=term-missing
  ```

### 5. Test coverage
Coverage is enabled by default via `pytest.ini`. The project includes:
- **Unit tests**: Fast, isolated tests for core functionality (adapters, errors, settings, enums, routes)
- **Comprehensive unit tests**: Additional coverage tests for edge cases and branch coverage
- **Contract tests**: Integration tests that verify API endpoints work correctly

Run tests with:
```bash
pytest
```

This will:
- Run all tests
- Enforce a minimum coverage threshold (currently 70%)
- Print missing lines (skipping fully covered files)
- Generate XML and HTML coverage reports

Open `coverage_html_report/index.html` in a browser to view the detailed coverage report.

**Test Structure:**
- `tests/unit/` - Unit tests (fast, isolated)
- `tests/contract/api/` - Contract tests for API endpoints
- `tests/smoke/` - Quick sanity checks

---

## Roadmap Management (GitHub Issues + Project)

This repo tracks the roadmap in GitHub Issues and a Project board (user project: **LEGO Inventory Management System Roadmap**). Issues include checklists, labels, and—when appropriate—a **Copilot** prompt and a **Recommended branch name**.

### Labels
- `type:*` → feature | refactor | test | bug | exploration  
- `area:*` → backend | frontend | scripts  
- `priority:*` → P1 | P2 | P3  
- `size:*` → S | M | L  
- `copilot` → multi-file or cross-cutting work where Copilot Pro will help

### Milestones & Project
- 13 milestones mirror the roadmap phases (e.g., *Refactor: write endpoints*, *Part-Out Wizard*).  
- A GitHub Actions workflow auto-adds any new issue to the Project using the repo variable **`LEGO_PROJECT_ID`**.

### Scripts (one-time setup / regeneration)
From repo root:

```bash
# seed labels & milestones
./scripts/seed_labels.sh
./scripts/seed_milestones.sh

# create (or find) the Project and set repo var LEGO_PROJECT_ID
./scripts/create_project_and_set_var.sh

# scaffold issue/PR templates and the add-to-project workflow, then push
./scripts/scaffold_github_files.sh
git push

# batch create the 13 roadmap issues (with Copilot prompts + branch suggestions)
./scripts/create_roadmap_issues_with_copilot.sh
```

### Working an issue
1. Open the issue and copy **🔀 Recommended branch** (e.g. `feature/route-write-endpoints`).
2. Create the branch and reference the issue number in commits:
   ```bash
   git checkout -b feature/route-write-endpoints
   git commit -m "Implement create_drawer endpoint (#1)"
   ```
3. Use the **💡 Copilot Prompt** in the issue body with Copilot Chat (VS Code) for multi-file changes.
4. Move the card on the Project board using the **Status** field (Backlog → In Progress → Done). Closing the issue auto-moves it to **Done**.

> Note: The Project board title and node id are managed by scripts; the node id is stored in the repo variable `LEGO_PROJECT_ID`.