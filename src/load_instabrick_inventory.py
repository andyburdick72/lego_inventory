"""
Load inventory data from an Instabrick XML export into lego_inventory.db
using only preloaded Rebrickable parts and colors.

Each BrickLink ITEMID and COLOR is mapped to its Rebrickable equivalent
via the part_aliases and color_aliases tables. No Rebrickable API access
is used in this script.

Usage:

    python3 src/load_instabrick_inventory.py data/instabrick_inventory.xml
"""
from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import inventory_db as db
from inventory_db import resolve_part, resolve_color
from utils.rebrickable_api import bulk_parts_by_bricklink, get_json

# --------------------------------------------------------------------------- status map and parser

STATUS_MAP = {
    "In Box": "in_box",
    "Built": "built",
    "Teardown": "teardown",
    "Work in Progress": "wip",
    "WIP": "wip",
}

RE_REMARK = re.compile(r"^\[IB\](.*)\[IB\]$")


def parse_remarks(raw: str) -> Tuple[str, Optional[str], Optional[str], Optional[str]]:
    """Return (status, drawer, container, set_number) parsed from REMARKS."""
    if not raw:
        return "loose", None, None, None
    m = RE_REMARK.match(raw.strip())
    text = m.group(1) if m else raw.strip()
    if text.startswith("("):
        close = text.find(")")
        status_text = text[1:close]
        status = STATUS_MAP.get(status_text, status_text)
        parts = text[close + 1 :].lstrip("|").split("|", 1)
        set_no = parts[0].strip() if parts else None
        return status, None, None, set_no
    drawer, container = None, None
    if "|" in text:
        drawer, container = (s.strip() for s in text.split("|", 1))
    else:
        drawer = text.strip()
    return "loose", drawer or None, container or None, None


# --------------------------------------------------------------------------- main loader

def load_xml(xml_path: Path) -> None:
    print(f"Loading XML from: {xml_path}")
    tree = ET.parse(xml_path)
    items = tree.findall(".//ITEM")
    print(f"→ Found {len(items)} inventory records.")

    unknown_parts: set[str] = set()
    unknown_colors: set[int] = set()
    prepared = []

    for item in items:
        alias = item.findtext("ITEMID").strip()
        bl_color = int(item.findtext("COLOR"))
        qty = int(item.findtext("QTY"))

        design_ids = resolve_part(alias)
        if isinstance(design_ids, str):
            design_ids = [design_ids]
        color_id = resolve_color(bl_color)

        if not design_ids:
            unknown_parts.add(alias)
            continue
        if not color_id:
            unknown_colors.add(bl_color)
            continue

        remarks = item.findtext("REMARKS", "")
        status, drawer, container, set_no = parse_remarks(remarks)

        for design_id in design_ids:
            prepared.append(
                (design_id, color_id, qty, status, drawer, container, set_no)
            )

    # Try to resolve missing part aliases via API or prompt user
    for alias in sorted(unknown_parts):
        matching_items = [it for it in items if it.findtext("ITEMID").strip() == alias]
        example = matching_items[0] if matching_items else None
        print(f"\n🔍 Missing part alias: {alias}")
        if example is not None:
            print("Example from XML:")
            for tag in ("ITEMID", "ITEMNAME", "COLOR", "QTY", "REMARKS"):
                print(f"  {tag}: {example.findtext(tag)}")

        result = bulk_parts_by_bricklink([alias])
        if alias in result:
            design_id, name = result[alias]
            print(f"✔️ Found in Rebrickable: {design_id} – {name}")
            db.insert_part(design_id, name)
            db.add_part_alias(alias, design_id)
        else:
            user_input = input(f"❓ Could not resolve {alias}. Enter one or more Rebrickable design IDs (comma- or semicolon-separated, or blank to skip): ").strip()
            if user_input:
                design_ids = [pid.strip() for pid in re.split(r"[;,]", user_input) if pid.strip()]
                for pid in design_ids:
                    try:
                        name = db.fetch_part_name(pid)
                        if not name:
                            data = get_json(f"/parts/{pid}/")
                            name = data["name"]
                            db.insert_part(pid, name)
                        db.add_part_alias(alias, pid)
                    except Exception as e:
                        print(f"❌ Error fetching or inserting part {pid}: {e}")
            else:
                print(f"⚠️ Skipping alias: {alias}")

    # Try to resolve missing colors via API or prompt user
    for bl_color in sorted(unknown_colors):
        print(f"\n🎨 Missing color alias: BrickLink color {bl_color}")
        try:
            data = get_json("/colors/", params={"bricklink_id__in": bl_color})
            if data["results"]:
                color = data["results"][0]
                rb_id = int(color["id"])
                name = color["name"]
                hex_code = color["rgb"].lstrip("#").upper()
                db.insert_color(rb_id, name, hex_code)
                db.add_color_alias(bl_color, rb_id)
                print(f"✔️ Found and added color: BL {bl_color} → RB {rb_id} ({name})")
            else:
                raise ValueError("No match found")
        except Exception:
            user_input = input(f"❓ Enter Rebrickable color ID for BrickLink color {bl_color} (or blank to skip): ").strip()
            if user_input.isdigit():
                db.add_color_alias(bl_color, int(user_input))
            else:
                print(f"⚠️ Skipping color: {bl_color}")

    for idx, rec in enumerate(prepared, start=1):
        db.insert_inventory(*rec)
        if idx % 100 == 0:
            print(f"  … {idx}/{len(prepared)} inserted")

    print(f"✅ Import complete: {len(prepared)} inventory records inserted.")


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