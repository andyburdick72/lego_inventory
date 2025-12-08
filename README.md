# LEGO Inventory Management System

A SQLite-backed inventory management system for LEGO parts and sets.  
Uses [Rebrickable](https://rebrickable.com/api/) as the canonical source and supports importing inventory from Instabrick/BrickLink XML exports.

---

## **Features**
- **Data import from Instabrick XML** with BrickLink → Rebrickable ID conversion  
- **Alias reconciliation** between BrickLink/Instabrick IDs and Rebrickable part & color IDs  
- **Full CRUD** for drawers, containers, sets, and loose parts inventory
- **Loose parts inventory management**:
  - Update part quantities in drawers/containers
  - Move parts between locations (with quantity control)
  - Delete parts from inventory
  - View loose parts by location with card and table views
- **Merge / move inventory** between locations  
- **Set management**:
  - Track multiple copies of a set
  - Store Rebrickable metadata (image, theme, year, etc.)
  - Set statuses: **Built**, **In Box**, **Work in Progress**, **Teardown**, **Loose Parts**
- **Part-out** a set into loose inventory
- **Move parts** between sets and loose inventory
- **Location reconciliation** for Loose Parts sets (identifies missing/excess parts)
- **Inventory mismatch detection** (compares required vs available parts)
- **Put-away bin** functionality for organizing teardown sets
- **Multiple view modes**: Card and table views for parts and inventory
- **Hierarchical views** for loose parts and parts by set (collapsible, sortable, searchable)  
- **CSV export** for any table, preserving current filters and sorting  
- **Sanity checks** for inventory consistency (loose vs in-sets counts)  
- **Web UI** (Next.js frontend + FastAPI backend) to browse parts, locations, and sets  

---

## **Repository Structure**
```
lego_inventory/
├── data/
│   ├── lego_inventory.db                 # SQLite database
│   ├── instabrick_inventory.xml          # Sample Instabrick export
│   └── reports/                          # Generated CSV reports
├── frontend/                             # Next.js frontend application
│   ├── app/                              # Next.js App Router pages
│   ├── components/                       # React components
│   │   ├── ui/                           # shadcn/ui components
│   │   ├── loose-parts/                  # Loose parts dialogs
│   │   └── ...
│   └── lib/                              # Utilities and hooks
├── src/
│   ├── app/
│   │   ├── api/                          # FastAPI REST API
│   │   │   ├── main.py                   # FastAPI application
│   │   │   └── v1/                       # API v1 endpoints
│   │   ├── di.py                         # Dependency injection
│   │   └── errors.py                     # Error handling
│   ├── core/
│   │   ├── services/                     # Business logic services
│   │   ├── dtos.py                       # Data transfer objects
│   │   └── enums.py                      # Status and other enums
│   ├── infra/
│   │   └── db/
│   │       ├── inventory_db.py           # DB creation & execution helpers
│   │       └── repositories/             # Data access layer
│   ├── scripts/
│   │   ├── load_my_rebrickable_parts.py  # Load parts for all owned sets
│   │   ├── load_rebrickable_colors.py    # Load Rebrickable colors
│   │   ├── precheck_instabrick_inventory.py # Pre-check Instabrick XML for missing aliases
│   │   ├── fix_alias_typos.py            # Fix typos from precheck step
│   │   ├── load_instabrick_inventory.py  # Import Instabrick XML into DB
│   │   └── inventory_sanity_checks.py    # Validate loose vs set inventories
│   └── integrations/
│       └── rebrickable_api.py            # Rebrickable API client
├── tests/
│   ├── unit/                             # Unit tests
│   ├── infra/repositories/               # Repository tests
│   ├── contract/api/                     # API contract tests
│   └── smoke/                            # Smoke tests
├── requirements.txt
├── requirements-dev.txt                  # Dev dependencies (code quality, testing)
├── dev.sh                                # Development script (setup, test, run)
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
The `dev.sh` script is the preferred way to set up and run the project. It handles environment setup, dependency installation, testing, and starts both servers.

**Basic usage:**
```bash
./dev.sh
```
This will:
- Install/update dependencies
- Run all tests (unit, smoke, contract)
- Start the Next.js frontend on port 3001
- Start the FastAPI backend on port 8001

**With coverage reporting:**
```bash
./dev.sh cov
```
This runs all tests with coverage reporting and merges unit + contract test coverage, then starts both servers.

**Note:** `dev.sh` automatically kills any existing servers on ports 3001 and 8001 before starting new ones to ensure fresh code is loaded.

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
- **Manage inventory via web UI**:
  - Update part quantities in drawers/containers
  - Move parts between locations
  - Delete parts from inventory
  - View and reconcile location counts
- Add/edit drawers, containers, and sets via the web UI  
- Import updated Instabrick XML after inventory changes  
- Run sanity checks:
  ```bash
  python3 src/inventory_sanity_checks.py
  ```
- Part-out sets or move inventory  
- Export any table to CSV for reporting
- Use location reconciliation to identify missing/excess parts  

---

## **Web UI**

### FastAPI Backend + Next.js Frontend

Run:
```bash
./dev.sh
```

This will:
1. Install/update dependencies
2. Run all tests (unit, smoke, contract)
3. Start the Next.js frontend on port 3001
4. Start the FastAPI backend on port 8001

**Access:**
- **Frontend**: http://localhost:3001 (Next.js)
- **Backend API**: http://localhost:8001 (FastAPI)
- **API Docs**: http://localhost:8001/docs (Swagger UI)

**UI Highlights:**
- **Loose Parts** page: Browse all loose inventory with card/table views and CRUD operations
- **Location Counts** page: View inventory totals grouped by drawer/container
- **Part Counts** page: Aggregate part counts across all sets
- **Part Color Counts** page: Part counts grouped by part and color
- **Container Detail** pages: View parts in a specific container with management actions
- **Drawer Detail** pages: View containers and parts in a drawer
- **Location Reconciliation** page: Identify missing/excess parts for Loose Parts sets
- **Inventory Mismatches** page: Compare required vs available parts across sets
- **Set Detail** pages: View parts in a set with full metadata
- **Part Detail** pages: View all locations where a part appears
- Column sorting & searching (per table)  
- CSV export button for every table view
- Modern React-based UI with responsive design
- Action buttons for inventory management (update quantity, move, delete)  

---

## **API Endpoints**

The FastAPI backend provides RESTful endpoints for managing inventory. Full API documentation is available at http://localhost:8001/docs when the server is running.

### **Inventory Management**
- `GET /api/v1/inventory/loose` - List all loose inventory items
- `GET /api/v1/inventory/loose/{id}` - Get a single inventory item by ID
- `PATCH /api/v1/inventory/loose/{id}/quantity` - Update inventory quantity
- `PATCH /api/v1/inventory/loose/{id}/location` - Update inventory location (container)
- `DELETE /api/v1/inventory/loose/{id}` - Delete an inventory item
- `POST /api/v1/inventory/loose/{id}/move` - Move parts between locations
- `GET /api/v1/inventory/loose` - List all loose parts
- `GET /api/v1/inventory/part-counts` - Get part counts across all sets
- `GET /api/v1/inventory/part-color-counts` - Get part+color counts
- `GET /api/v1/inventory/location-counts` - Get inventory totals by location

### **Drawers & Containers**
- `GET /api/v1/drawers` - List all drawers
- `POST /api/v1/drawers/create` - Create a drawer
- `POST /api/v1/drawers/rename` - Update drawer
- `POST /api/v1/drawers/delete` - Soft delete drawer
- `GET /api/v1/containers?drawer_id={id}` - List containers for a drawer
- `POST /api/v1/containers/create` - Create a container
- `GET /api/v1/containers/{id}` - Get container details
- `GET /api/v1/containers/{id}/parts` - Get parts in a container
- `GET /api/v1/containers/put-away-bin` - Get put-away bin container
- `POST /api/v1/containers/put-away-bin` - Set put-away bin

### **Sets & Parts**
- `GET /api/v1/sets` - List all sets
- `GET /api/v1/sets/{set_number}` - Get set details
- `GET /api/v1/parts/{design_id}` - Get part details and locations
- `GET /api/v1/parts/{design_id}/inventory` - Get inventory for a part

### **Reconciliation & Mismatches**
- `GET /api/v1/location-reconciliation/items/loose-parts` - Get reconciliation items for Loose Parts sets
- `GET /api/v1/mismatches` - Get inventory mismatches summary
- `GET /api/v1/mismatches/sets/{set_number}` - Get mismatches for a specific set

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
  Or use `./dev.sh` which runs all tests automatically before starting servers.

- **Unit tests only**:
  ```bash
  pytest tests/unit/
  ```

- **Repository tests only**:
  ```bash
  pytest tests/infra/
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
- `tests/unit/` - Unit tests (fast, isolated) for services, adapters, utilities
- `tests/infra/repositories/` - Repository tests for database operations
- `tests/contract/api/` - Contract tests for API endpoints (requires running server)
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