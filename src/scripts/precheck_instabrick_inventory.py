"""
Precheck inventory XML for missing part and color aliases and allow interactive resolution.

Usage:
    python3 src/precheck_instabrick_inventory.py data/instabrick_inventory.xml
"""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from core.services.rebrickable_api import bulk_parts_by_bricklink, get_json
from infra.db import inventory_db as db
from infra.db.inventory_db import resolve_color, resolve_part


def _text(el: ET.Element, tag: str) -> str:
    """Return trimmed text for a tag, or empty string if missing (helps type checkers)."""
    val = el.findtext(tag)
    return val.strip() if isinstance(val, str) else ""


def precheck_xml(xml_path: Path) -> None:
    print(f"Prechecking XML from: {xml_path}")
    tree = ET.parse(xml_path)
    items = tree.findall(".//ITEM")
    print(f"→ Found {len(items)} inventory records.")

    unknown_parts: set[str] = set()
    unknown_colors: set[int] = set()

    for item in items:
        alias = _text(item, "ITEMID")
        color_s = _text(item, "COLOR")
        bl_color = int(color_s) if color_s else 0

        if not resolve_part(alias):
            unknown_parts.add(alias)
        if not resolve_color(bl_color):
            unknown_colors.add(bl_color)

    # Try to resolve missing part aliases via API or prompt user
    total_parts = len(unknown_parts)
    for idx, alias in enumerate(sorted(unknown_parts), 1):
        matching_items = [it for it in items if _text(it, "ITEMID") == alias]
        example = matching_items[0] if matching_items else None
        # Check if the alias itself is a valid Rebrickable part ID
        try:
            part_data = get_json(f"/parts/{alias}/")
            name = part_data.get("name", "Unknown part")
            confirm = (
                input(f"❓ Use '{alias}' as Rebrickable ID? Found: {name} [y/n]: ").strip().lower()
            )
            if confirm == "y":
                db.insert_part(alias, name)
                db.add_part_alias(alias, alias)
                print(f"✔️ Added part: {alias} – {name}")
                progress = (idx / total_parts) * 100
                print(f"🧭 Progress: {idx}/{total_parts} ({progress:.1f}%)")
                continue
        except Exception:
            pass  # silently continue if not valid

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
            user_input = input(
                f"❓ Could not resolve {alias}. Enter Rebrickable design ID(s), comma- or semicolon-separated (or blank to skip): "
            ).strip()
            if user_input:
                part_ids = [
                    pid.strip() for pid in user_input.replace(";", ",").split(",") if pid.strip()
                ]
                for pid in part_ids:
                    try:
                        part_data = get_json(f"/parts/{pid}/")
                        name = part_data.get("name", "Unknown part")
                        db.insert_part(pid, name)
                        db.add_part_alias(alias, pid)
                        print(f"✔️ Added part: {pid} – {name}")
                    except Exception as e:
                        print(f"❌ Error retrieving part {pid} from Rebrickable: {e}")
            else:
                print(f"⚠️ Skipping alias: {alias}")

        progress = (idx / total_parts) * 100
        print(f"🧭 Progress: {idx}/{total_parts} ({progress:.1f}%)")

    # Try to resolve missing colors via API or prompt user
    for bl_color in sorted(unknown_colors):
        print(f"\n🎨 Missing color alias: BrickLink color {bl_color}")
        try:
            data = get_json("/colors/", params={"bricklink_id__in": str(bl_color)})
            if data["results"]:
                color = data["results"][0]
                rb_id = int(color["id"])
                name = color["name"]
                hex_code = str(color.get("rgb") or "").lstrip("#").upper()
                if rb_id != -1:
                    db.insert_color(rb_id, name, hex_code)
                    db.add_color_alias(bl_color, rb_id)
                    print(f"✔️ Found and added color: BL {bl_color} → RB {rb_id} ({name})")
                else:
                    raise ValueError(
                        f"Rebrickable returned invalid ID (-1) for BL color {bl_color}"
                    )
            else:
                raise ValueError(f"No match found for BrickLink color {bl_color}")
        except Exception:
            user_input = input(
                f"❓ Enter Rebrickable color ID for BrickLink color {bl_color} (or blank to skip): "
            ).strip()
            if user_input.isdigit():
                try:
                    data = get_json(f"/colors/{user_input}/")
                    name = data.get("name", "Unknown color")
                    hex_code = data.get("rgb", "").lstrip("#").upper()
                    db.insert_color(int(user_input), name, hex_code)
                    db.add_color_alias(bl_color, int(user_input))
                    print(f"✔️ Added color: BL {bl_color} → RB {user_input} ({name})")
                except Exception as e:
                    print(f"❌ Error retrieving color info from Rebrickable: {e}")
                    print(f"⚠️ Skipping color: {bl_color}")
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
