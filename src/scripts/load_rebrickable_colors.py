"""Load Rebrickable colours (plus BrickLink aliases) into the configured sqlite database (see app.settings).

Configuration:
* Credentials are resolved centrally via `app.settings` (pydantic-settings).
  Ensure `APP_REBRICKABLE_API_KEY` is set in `data/.env` (or the environment).
* HTTP pagination is handled by `core.services.rebrickable_api.paginate`.

Usage:

    PYTHONPATH=src python3 -m scripts.load_rebrickable_colors
"""

from __future__ import annotations

from app.settings import get_settings
from core.services.rebrickable_api import paginate
from infra.db import inventory_db as db


def _rgb_split(hex_code: str) -> tuple[int, int, int]:
    hex_code = hex_code.lstrip("#")
    return tuple(int(hex_code[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore


def main() -> None:
    get_settings()

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
