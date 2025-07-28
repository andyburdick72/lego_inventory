"""Load inventory data from an Instabrick XML export into the SQLite database.

This script parses the XML format produced by Instabrick and inserts
each item into the ``lego_inventory`` database. It uses the helper
functions defined in ``inventory_db.py`` to insert parts and
inventory records. If a part already exists, the existing record is
reused rather than creating a duplicate. Colour codes are stored as
their numeric identifiers if no mapping is available. Status values
found in the XML are mapped to the canonical statuses used in the
database (``in_box``, ``built``, ``teardown``, ``loose``). Any
unrecognised status will be converted to a lower‑case, underscore
version of the raw text. Locations extracted from remarks without
explicit status are stored in the ``bin`` field.

Usage:

    python3 -m lego_inventory.load_instabrick_xml path/to/instabrick_inventory.xml

The script will create the database if it does not exist and insert
records accordingly.
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

from . import inventory_db as db

DEFAULT_XML = Path(__file__).resolve().parents[1] / "data" / "instabrick_inventory.xml"
xml_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_XML

STATUS_MAP = {
    "In Box": "in_box",
    "Built": "built",
    "Teardown": "teardown",
    "Work in Progress": "work_in_progress",
    "WIP": "work_in_progress",
}


def parse_remarks(remarks: str) -> tuple[Optional[str], str]:
    """Parse the remarks string into a tuple of (location, status).

    The Instabrick remarks are wrapped in ``[IB]... [IB]`` markers. If
    the content starts with a parenthesised status (e.g. ``(Built)``),
    that status is extracted and returned; the location is left as
    ``None``. Otherwise the text before the first ``|`` is treated as
    the location and the status is assumed to be ``loose``. If no
    recognised pattern is found, both values are ``None``.
    """
    if not remarks:
        return None, "loose"
    # Remove surrounding [IB] markers
    text = remarks
    if text.startswith("[IB]"):
        text = text[4:]
    if text.endswith("[IB]"):
        text = text[:-4]
    text = text.strip()
    if not text:
        return None, "loose"
    # Status enclosed in parentheses at start
    if text.startswith("("):
        end = text.find(")")
        if end != -1:
            status_text = text[1:end]
            status_key = STATUS_MAP.get(status_text, status_text.lower().replace(" ", "_"))
            return None, status_key
    # Otherwise treat text before first | as location
    parts = text.split("|", 1)
    location = parts[0].strip() if parts[0].strip() else None
    return location, "loose"


def load_xml(path: str) -> None:
    tree = ET.parse(path)
    root = tree.getroot()
    db.init_db()
    inserted_parts = 0
    inserted_records = 0
    for item_el in root.findall("ITEM"):
        item_id = (item_el.findtext("ITEMID") or "").strip()
        if not item_id:
            continue
        # Insert part (use item_id as both part number and name if name unknown)
        part_id = db.insert_part(item_id, item_id)
        inserted_parts += 1
        # Colour code
        colour = (item_el.findtext("COLOR") or "").strip() or "unknown"
        # Quantity
        qty_text = (item_el.findtext("QTY") or "0").strip()
        try:
            quantity = int(qty_text)
        except ValueError:
            quantity = 0
        # Remarks for status and location
        remarks = (item_el.findtext("REMARKS") or "").strip()
        location, status = parse_remarks(remarks)
        # Insert inventory record
        db.insert_inventory(
            part_id=part_id,
            colour=colour,
            quantity=quantity,
            status=status,
            container=None,
            drawer=None,
            bin_name=location,
        )
        inserted_records += 1
    print(f"Inserted {inserted_records} inventory records for {inserted_parts} parts.")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python3 -m lego_inventory.load_instabrick_xml <xml_file>")
        sys.exit(1)
    xml_path = sys.argv[1]
    load_xml(xml_path)


if __name__ == "__main__":
    main()