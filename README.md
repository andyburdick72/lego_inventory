Lego Inventory

A simple SQLite-backed inventory management system for LEGO parts, using Rebrickable as the canonical source and importing inventory from Instabrick/BrickLink XML exports.

Features
* Data import from Instabrick XML
* Alias reconciliation between BrickLink/Instabrick IDs and Rebrickable part IDs
* Name filling via Rebrickable API and manual mappings
* Web UI (no external dependencies) to browse parts, locations, and sets
* CLI scripts for data migration, cleaning, and mapping generation

Repository Structure

lego_inventory/
├── data/
│   ├── lego_inventory.db             # SQLite database (WAL + SHM)
│   ├── instabrick_inventory.xml      # Sample Instabrick export
│   └── *.csv                         # Mapping CSV files
├── src/
│   ├── inventory_db.py               # Create and execute against DB
│   ├── load_my_rebrickable_parts.py  # Load all the parts for my Rebrickable sets into DB
│   ├── load_rebrickable_colors.py    # Load Rebrickable colors into DB
│   ├── load_instabrick_inventory.py  # Load Instabrick inventory from XML file into DB and convert to Rebrickable IDs
│   ├── server.py                     # Lightweight HTTP server for the UI
│   └── utils/
│       ├── rebrickable_api.py        # Rebrickable API client helpers
│       └── common_functions.py       # .env loader for API keys
└── README.md

Prerequisites

* Python 3.9+
* Dependencies (in src/utils/rebrickable_api.py): requests
* A Rebrickable API key and user token in a .env file

REBRICKABLE_API_KEY=<your_api_key>
REBRICKABLE_USER_TOKEN=<your_user_token>
REBRICKABLE_USERNAME=<your_username>
REBRICKABLE_PASSWORD=<your_password>

Setup

1.	Clone the repo

git clone https://github.com/andyburdick72/lego_inventory.git
cd lego_inventory

2.	Install dependencies

pip install requests

3.	Initialize database schema (if needed):

python3 src/inventory_db.py 
# or scripts call init_db()

Common Workflows

1. Create DB schema

python3 src/create_inventory_db.py

2. Load Rebrickable parts and colors

python3 src/load_my_rebrickable_parts.py
python3 src/load_rebrickable_colors.py

3. Load Instabrick XML

python3 src/load_instabrick_inventory.py data/instabrick_inventory.xml

4. Run the web UI

python3 src/server.py

5. Visit http://localhost:8000 in your browser

Database Schema

* colors: Rebrickable color data
* color_aliases: BrickLink → Rebrickable color mapping
* parts: Canonical Rebrickable part IDs and names
* part_aliases: BrickLink/Instabrick → Rebrickable part mapping
* inventory: Quantities by part, color, status, and location (drawer, container, or set)

Roadmap / Ideas

* Column sorting & searching in the UI
* Export inventory to CSV
* Editable drawer / container & part locations
* Part-out a set
* Generate pick lists
* Bulk edit locations