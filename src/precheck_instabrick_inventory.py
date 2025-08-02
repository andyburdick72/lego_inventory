"""
Precheck inventory XML for missing part and color aliases and allow interactive resolution.

Usage:
    python3 src/precheck_instabrick_inventory.py data/instabrick_inventory.xml
"""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import inventory_db as db
from utils.rebrickable_api import bulk_parts_by_bricklink, get_json

from inventory_db import resolve_part, resolve_color

def precheck_xml(xml_path: Path) -> None:
    print(f"Prechecking XML from: {xml_path}")
    tree = ET.parse(xml_path)
    items = tree.findall(".//ITEM")
    print(f"→ Found {len(items)} inventory records.")

    unknown_parts: set[str] = set()
    unknown_colors: set[int] = set()

    for item in items:
        alias = item.findtext("ITEMID").strip()
        bl_color = int(item.findtext("COLOR"))

        if not resolve_part(alias):
            unknown_parts.add(alias)
        if not resolve_color(bl_color):
            unknown_colors.add(bl_color)

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
            user_input = input(f"❓ Could not resolve {alias}. Enter Rebrickable design ID (or blank to skip): ").strip()
            if user_input:
                db.insert_part(user_input, "Unknown part")
                db.add_part_alias(alias, user_input)
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

    print("\n✅ Precheck complete. You may now safely run load_instabrick_inventory.py.")

def main() -> None:
    path = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else Path(__file__).resolve().parents[1] / "data" / "instabrick_inventory.xml"
    )
    if not path.exists():
        print(f"File not found: {path}")
        sys.exit(1)
    precheck_xml(path)

if __name__ == "__main__":
    main()