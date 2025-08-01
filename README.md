Lego Inventory

A simple SQLite-backed inventory management system for LEGO parts, using Rebrickable as the canonical source and importing inventory from Instabrick/BrickLink XML exports.

Features
	•	Data import from Instabrick XML
	•	Alias reconciliation between BrickLink/Instabrick IDs and Rebrickable part IDs
	•	Name filling via Rebrickable API and manual mappings
	•	Web UI (no external dependencies) to browse parts, locations, and sets
	•	CLI scripts for data migration, cleaning, and mapping generation

Repository Structure

lego_inventory/
├── data/
│   ├── lego_inventory.db       # SQLite database (WAL + SHM)
│   ├── instabrick_inventory.xml  # Sample Instabrick export
│   └── *.csv                   # Mapping CSV files
├── src/
│   ├── load_instabrick_inventory.py  # Load XML into DB
│   ├── clean_instabrick_inventory.py # Reconcile aliases & fill names
│   ├── import_part_mapping.py        # Bulk import alias→Rebrickable mappings
│   ├── generate_part_mapping.py      # Build mapping from owned sets via API
│   ├── import_name_mapping.py        # Fill manual name mappings
│   ├── server.py                     # Lightweight HTTP server for the UI
│   └── utils/
│       ├── rebrickable_api.py        # Rebrickable API client helpers
│       └── common_functions.py       # .env loader for API keys
└── README.md

Prerequisites
	•	Python 3.9+
	•	Dependencies (in src/utils/rebrickable_api.py): requests
	•	A Rebrickable API key and user token in a .env file:

REBRICKABLE_API_KEY=<your_api_key>
REBRICKABLE_USER_TOKEN=<your_user_token>

Setup
	1.	Clone the repo

git clone https://github.com/andyburdick72/lego_inventory.git
cd lego_inventory

	2.	Install dependencies

pip install requests

	3.	Initialize database schema (if needed):

python3 src/inventory_db.py  # or scripts call init_db()



Common Workflows

1. Load Instabrick XML

python3 src/load_instabrick_inventory.py path/to/instabrick_inventory.xml

2. Reconcile aliases & fill part names

python3 src/clean_instabrick_inventory.py [--mapping path/to/mapping.csv]

3. Import manual mappings

python3 src/import_part_mapping.py data/bricklink_to_rebrickable.csv
python3 src/import_name_mapping.py data/instabrick_stragglers.csv

4. Generate mapping from owned sets

python3 src/generate_part_mapping.py data/bricklink_to_rebrickable.csv

5. Run the web UI

python3 src/server.py
# Then browse http://localhost:8000 in your browser

Database Schema
	•	colors: Rebrickable color data
	•	color_aliases: BrickLink → Rebrickable color mapping
	•	parts: Canonical Rebrickable part IDs and names
	•	part_aliases: BrickLink/Instabrick → Rebrickable part mapping
	•	inventory: Quantities by part, color, status, and location (drawer, container, or set)

Roadmap / Ideas
	•	Column sorting & searching in the UI
	•	Export inventory to CSV
	•	Editable drawer/container & part locations
	•	Part-out a set & generate pick lists
	•	Bulk edit locations