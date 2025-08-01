#!/usr/bin/env python3
"""
import_name_mapping.py

Usage:
    python3 src/import_name_mapping.py path/to/your_name_mapping.csv
"""
import sys
import csv
from pathlib import Path

from inventory_db import resolve_part, insert_part
from utils.common_functions import load_rebrickable_environment

def main():
    if len(sys.argv) != 2:
        print("Usage: python import_name_mapping.py path/to/name_mapping.csv")
        sys.exit(1)

    mapping_csv = Path(sys.argv[1])
    if not mapping_csv.is_file():
        print(f"ERROR: file not found: {mapping_csv}")
        sys.exit(1)

    # ensure REBRICKABLE_USER_TOKEN etc are loaded (not strictly needed here,
    # but keeps env loading consistent)
    load_rebrickable_environment()

    updated = 0
    with mapping_csv.open(newline="", encoding="utf-8") as fp:
        reader = csv.reader(fp)
        for row in reader:
            alias, name = row[0].strip(), row[1].strip()
            if not alias or not name:
                continue

            # figure out the canonical design_id
            design_id = resolve_part(alias) or alias

            # insert_part will only overwrite if name was 'Unknown part'
            insert_part(design_id, name)
            updated += 1

    print(f"Updated names for {updated} parts.")


if __name__ == "__main__":
    main()