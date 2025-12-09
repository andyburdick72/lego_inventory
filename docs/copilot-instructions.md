# AI Coding Agent Instructions for LEGO Inventory Management System

## Overview
This project is a SQLite-backed inventory management system for LEGO parts and sets. It integrates with the Rebrickable API and supports importing inventory from Instabrick/BrickLink XML exports. The system includes a web-based UI for managing inventory and provides various scripts for data import, validation, and maintenance.

## Architecture
- **Data Layer**: Located in `src/infra/db/`, this layer handles database schema creation and execution.
- **Business Logic**: Encapsulated in `src/core/` and `src/app/`, including services, DTOs, and enums.
- **Backend API**: FastAPI REST API in `src/app/api/` (port 8001) - ✅ **ACTIVE**
- **Frontend**: Next.js application in `frontend/` (port 3000) - ✅ **ACTIVE**
- **Legacy UI**: Deprecated HTML templates in `src/app/templates/` served via `src/app/server.py` (port 8000)
- **Scripts**: Found in `src/scripts/`, these handle data import, alias reconciliation, and inventory validation.
- **Utilities**: Common helper functions and API clients are in `src/utils/`.

### Key Data Flows
1. **Data Import**: Scripts in `src/scripts/` load data from external sources (e.g., Instabrick XML, Rebrickable API) into the SQLite database.
2. **Web UI**: 
   - **Modern**: Next.js frontend (port 3000) calls FastAPI backend (port 8001) - ✅ **ACTIVE**
   - **Legacy**: Deprecated HTML templates served via `src/app/server.py` (port 8000)
3. **Inventory Validation**: Scripts like `inventory_sanity_checks.py` ensure consistency between loose parts and set inventories.

## Developer Workflows
### Setup
- Use `dev.sh` for streamlined setup and running:
  ```bash
  ./dev.sh
  ```
  This installs dependencies, initializes the database, and starts the web server.

### Code Quality
- **Linting**: Run Ruff to check and fix linting issues:
  ```bash
  ruff check src --fix
  ```
- **Formatting**: Use Black to format code:
  ```bash
  black src
  ```
- **Type Checking**: Use mypy for static type analysis:
  ```bash
  mypy src
  ```

### Testing
- **Run all tests**:
  ```bash
  pytest
  ```
- **Contract Tests** (requires FastAPI server running):
  ```bash
  API_BASE_URL=http://localhost:8001/api/v1 pytest -m contract
  ```
  Note: `./dev.sh` automatically starts FastAPI for contract tests.
- **Coverage**: Generate coverage reports:
  ```bash
  pytest --cov=src --cov-report=term-missing
  ```

### Database Initialization
- Create the database schema manually (if not using `dev.sh`):
  ```bash
  python3 src/inventory_db.py
  ```

## Project-Specific Conventions
- **Database Schema**: The schema is defined in `src/infra/db/inventory_db.py`. Key tables include:
  - `colors`: Rebrickable colors
  - `parts`: Canonical Rebrickable part IDs (includes `part_category_id` for category-based storage)
  - `part_categories`: Rebrickable part category names
  - `inventory`: Tracks quantities by part, color, and location
- **Scripts**: Each script in `src/scripts/` has a specific purpose (e.g., `load_instabrick_inventory.py` for importing XML data).
- **Web UI**: Templates in `src/app/templates/` follow a consistent structure for displaying inventory data.

## Integration Points
- **Rebrickable API**: Used for fetching part and color data. API credentials are stored in a `.env` file.
- **Instabrick XML**: Imported via `load_instabrick_inventory.py`.

## Examples
### Adding a New Script
1. Place the script in `src/scripts/`.
2. Follow the pattern in existing scripts (e.g., `load_instabrick_inventory.py`):
   - Use `argparse` for CLI arguments.
   - Interact with the database via `src/infra/db/inventory_db.py`.

### Adding a New Web UI Feature
1. Create an HTML template in `src/app/templates/`.
2. Add a route in `src/app/server.py`.
3. Use the database helpers in `src/infra/db/` to fetch data.

---

This guide is designed to help AI coding agents quickly understand and contribute to the LEGO Inventory Management System. If any sections are unclear or incomplete, please provide feedback for improvement.
