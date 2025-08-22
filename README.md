<file name=0 path=/Users/andyburdick/Code/GitHub/andyburdick72/lego_inventory/README.md># LEGO Inventory Management System

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
│   │   ├── server.py                     # Lightweight HTTP server for UI
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
The `dev.sh` script is the preferred way to set up and run the project. It handles environment setup, dependency installation, and starts the server with a single command.

To use `dev.sh`:
```bash
./dev.sh
```
This will install dependencies, initialize the database if needed, and start the web UI server.

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
Run:
```bash
./dev.sh
```
Visit:  
```
http://localhost:8000
```

**UI Highlights:**
- **Loose Parts by Location** and **Parts by Set**: collapsible hierarchical views  
- Column sorting & searching (per table)  
- CSV export button for every table view  

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
| `server.py` | Run the web UI |

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

- **Unit tests** (default):
  ```bash
  pytest
  ```

- **Contract tests** (API endpoints, requires server running):
  ```bash
  export API_BASE_URL=http://localhost:8000/api
  pytest -m contract
  ```

- **All tests with coverage**:
  ```bash
  pytest --cov=src --cov-report=term-missing
  ```

### 5. Test coverage
To measure test coverage, first ensure development dependencies are installed:
```bash
pip install -r requirements-dev.txt
```
Then run pytest with coverage reporting:
```bash
pytest --cov=src --cov-report=term-missing
```
This command runs tests and displays coverage details in the terminal.

For an HTML coverage report, run:
```bash
pytest --cov=src --cov-report=html
```
The report will be generated in the `htmlcov` directory. Open `htmlcov/index.html` in a browser to view a detailed coverage report.