"""
Load inventory data from an **Instabrick** XML export into lego_inventory.db
using the v2 canonical Rebrickable schema.

* Translates BrickLink / Instabrick ITEMID → Rebrickable design_id via
  utils.rebrickable_api.bulk_parts_by_bricklink (batched to avoid 429s).
* Translates BrickLink colour ids → Rebrickable colour ids via the
  ``color_aliases`` table (populated by load_rebrickable_colors.py).
* Parses remarks to extract status, drawer, container, set_number.

Run::

    python src/load_instabrick_xml.py  data/instabrick_inventory.xml
"""
from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import inventory_db as db
from utils.rebrickable_api import bulk_parts_by_bricklink
from utils.rebrickable_api import get_json
from inventory_db import resolve_part, add_part_alias, insert_part, resolve_color

# --------------------------------------------------------------------------- status map
STATUS_MAP = {
    "In Box": "in_box",
    "Built": "built",
    "Teardown": "teardown",
    "Work in Progress": "wip",
    "WIP": "wip",
}

# --------------------------------------------------------------------------- remarks parser
RE_REMARK = re.compile(r"^\[IB\](.*)\[IB\]$")


def parse_remarks(raw: str) -> Tuple[str, Optional[str], Optional[str], Optional[str]]:
    """
    Return (status, drawer, container, set_number).

    * Loose parts:  [IB]Drawer|Container[IB]
    * Built/WIP/etc: [IB](Built)|10787-1 Gabby's Dollhouse[IB]
    """
    if not raw:
        return "loose", None, None, None

    m = RE_REMARK.match(raw.strip())
    text = m.group(1) if m else raw.strip()

    # Leading (Status)
    if text.startswith("("):
        close = text.find(")")
        status_text = text[1:close]
        status = STATUS_MAP.get(status_text, status_text.lower().replace(" ", "_"))
        # remainder contains set number
        parts = text[close + 1 :].lstrip("|").split("|", 1)
        set_no = parts[0].strip() if parts else None
        return status, None, None, set_no

    # Otherwise loose
    drawer, container = None, None
    if "|" in text:
        drawer, container = (s.strip() for s in text.split("|", 1))
    else:
        drawer = text.strip()
    return "loose", drawer or None, container or None, None


# --------------------------------------------------------------------------- loader
MAX_BATCH = 50  # keep well under API limit to reduce 429s


def _batch_translate_parts(alias_ids: List[str]) -> Dict[str, Tuple[str, str]]:
    """Return alias → (design_id, name) mapping, inserting into DB as needed."""
    mapping: Dict[str, Tuple[str, str]] = {}
    unresolved: List[str] = []

    for aid in alias_ids:
        did = resolve_part(aid)
        if did:
            mapping[aid] = (did, None)  # name not needed
        else:
            unresolved.append(aid)

    for i in range(0, len(unresolved), MAX_BATCH):
        chunk = unresolved[i : i + MAX_BATCH]
        remote = bulk_parts_by_bricklink(chunk)
        for alias, (design_id, name) in remote.items():
            insert_part(design_id, name)
            add_part_alias(alias, design_id)
            mapping[alias] = (design_id, name)
    # Any aliases still not in mapping could not be resolved via the API
    still_missing = [a for a in unresolved if a not in mapping]
    if still_missing:
        print("Warning: BrickLink/Instabrick part IDs not found in Rebrickable:", still_missing)
    return mapping


def load_xml(xml_path: Path) -> None:
    print(f"Loading {xml_path} …")
    tree = ET.parse(xml_path)
    items = tree.findall(".//ITEM")
    total_items = len(items)
    print(f"Found {total_items} inventory records in XML. Beginning import …")

    # Collect all unique ITEMID and COLOR IDs first
    alias_ids = [it.findtext("ITEMID").strip() for it in items]

    # Map ITEMID → ITEMNAME so we can create placeholder parts for aliases
    alias_to_name = {
        it.findtext("ITEMID").strip(): it.findtext("ITEMNAME", "").strip()
        for it in items
    }

    color_aliases = {int(it.findtext("COLOR")) for it in items}

    part_map = _batch_translate_parts(alias_ids)

    missing_colors = []
    color_map: Dict[int, int] = {}
    for aid in color_aliases:
        cid = resolve_color(aid)
        if cid:
            color_map[aid] = cid
        else:
            missing_colors.append(aid)

    if missing_colors:
        print("Resolving", len(missing_colors), "missing BrickLink color IDs via Rebrickable …")
        for bl_id in missing_colors:
            data = get_json(
                "/colors/",
                params={"bricklink_id__in": bl_id},
            )
            if data["results"]:
                c = data["results"][0]
                rb_id = int(c["id"])
                name = c["name"]
                hex_code = c["rgb"].lstrip("#").upper()
                # Insert color + alias
                db.insert_color(rb_id, name, hex_code)
                db.add_color_alias(bl_id, rb_id)
                color_map[bl_id] = rb_id
                print(f"  • BL {bl_id} → RB {rb_id} ({name})")
            else:
                print(f"  • Warning: BrickLink color {bl_id} not found in Rebrickable")
                # Leave unresolved; will trigger error below

        # After attempting fallback, abort if any still unresolved
        unresolved = [bl for bl in missing_colors if bl not in color_map]
        if unresolved:
            print("Error: still missing color aliases for:", unresolved)
            sys.exit(1)

    inserted = 0
    for it in items:
        alias = it.findtext("ITEMID").strip()

        # If the alias is still unresolved, create a local placeholder part
        if alias not in part_map:
            placeholder_name = alias_to_name.get(alias, "Unknown part")
            insert_part(alias, placeholder_name or "Unknown part")
            add_part_alias(alias, alias)
            part_map[alias] = (alias, placeholder_name)
            print(f"  • Added local part record for BL-only alias {alias} – '{placeholder_name}'")

        design_id, _ = part_map[alias]
        color_id = color_map[int(it.findtext("COLOR"))]
        quantity = int(it.findtext("QTY"))

        status, drawer, container, set_no = parse_remarks(it.findtext("REMARKS", ""))

        db.insert_inventory(
            design_id=design_id,
            color_id=color_id,
            quantity=quantity,
            status=status,
            drawer=drawer,
            container=container,
            set_number=set_no,
        )
        inserted += 1
        if inserted % 100 == 0:
            print(f"  … {inserted}/{total_items} processed")

    print(f"Import complete: {inserted}/{total_items} records inserted.")


def main() -> None:
    path = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else Path(__file__).resolve().parents[1] / "data" / "instabrick_inventory.xml"
    )
    if not path.exists():
        print(f"File not found: {path}")
        sys.exit(1)
    load_xml(path)


if __name__ == "__main__":
    main()