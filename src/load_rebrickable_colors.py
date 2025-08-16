"""Load Rebrickable colours (plus BrickLink aliases) into lego_inventory.db.

This script relies on shared utilities:
* ``utils.common_functions.load_rebrickable_environment`` loads the
  API key from your ``.env`` file (ignored by Git).  It sets the
  ``REBRICKABLE_API_KEY`` environment variable for this process.
* ``utils.rebrickable_api.paginate`` handles paginated API calls and
  reuses the same API key.

Usage:

    python3 src/load_rebrickable_colors.py

(Ensure your ``.env`` has ``REBRICKABLE_API_KEY``.)
"""

from __future__ import annotations

import inventory_db as db
from utils.common_functions import load_rebrickable_environment
from utils.rebrickable_api import paginate


def _rgb_split(hex_code: str) -> tuple[int, int, int]:
    hex_code = hex_code.lstrip("#")
    return tuple(int(hex_code[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore


def main() -> None:
    # Load env vars; exits with error if missing.
    load_rebrickable_environment()

    db.init_db()

    colors_rows: list[tuple[int, str, str, int, int, int]] = []
    alias_rows: list[tuple[int, int]] = []  # (bricklink_id, color_id)

    for c in paginate("/colors/", params={"page_size": 1000}):
        cid = int(c["id"])
        name = c["name"]
        hex_code = c["rgb"].upper()
        r, g, b = _rgb_split(hex_code)
        colors_rows.append((cid, name, hex_code, r, g, b))

        bl_ids = c["external_ids"].get("BrickLink", {}).get("ext_ids", [])
        alias_rows += [(int(bl), cid) for bl in bl_ids if bl is not None]

    with db._connect() as conn:  # pylint: disable=protected-access
        conn.executemany(
            "INSERT OR IGNORE INTO colors(id,name,hex,r,g,b) VALUES (?,?,?,?,?,?)",
            colors_rows,
        )
        conn.executemany(
            "INSERT OR IGNORE INTO color_aliases(alias_id,color_id) VALUES (?,?)",
            alias_rows,
        )
        conn.commit()

    print(f"Inserted/updated {len(colors_rows)} colors and {len(alias_rows)} aliases.")


if __name__ == "__main__":
    main()
