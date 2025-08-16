from inventory_db import add_part_alias, insert_part
from utils.rebrickable_api import get_json

# --- List of manual alias corrections ---
manual_alias_fixes = {
    "60592c02": ["60601"],
    "dis126": ["92456c01pr0326", "64408", "61547", "92198pr0402"],
    "frnd474": ["69969pr0014", "92198pr0271"],
    "frnd547": ["92198pr0321", "92456c01pr0450", "24184"],
}


def safe_add_alias(bl_id: str, rb_id: str):
    try:
        part_data = get_json(f"/parts/{rb_id}/")
        name = part_data.get("name", "Unknown part")
        insert_part(rb_id, name)
        add_part_alias(bl_id, rb_id)
        print(f"✔️ Mapped {bl_id} → {rb_id} ({name})")
    except Exception as e:
        print(f"❌ Failed to map {bl_id} → {rb_id}: {e}")


def main():
    for alias, rb_ids in manual_alias_fixes.items():
        for rb_id in rb_ids:
            safe_add_alias(alias, rb_id)


if __name__ == "__main__":
    main()
