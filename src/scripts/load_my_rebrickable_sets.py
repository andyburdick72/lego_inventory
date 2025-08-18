from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Final

from app.settings import get_settings
from core.services.rebrickable_api import get_json
from scripts.load_my_rebrickable_parts import fetch_owned_sets

# Centralized settings (cached)
SETTINGS = get_settings()
API_KEY: Final[str] | None = SETTINGS.rebrickable_api_key
USER_TOKEN: Final[str] | None = SETTINGS.rebrickable_user_token
if not API_KEY or not USER_TOKEN:
    raise RuntimeError(
        "Missing APP_REBRICKABLE_API_KEY or APP_REBRICKABLE_USER_TOKEN in data/.env or environment"
    )


def load_my_rebrickable_sets():
    if USER_TOKEN is None:
        raise ValueError("USER_TOKEN cannot be None")
    set_nums = fetch_owned_sets(USER_TOKEN)

    with sqlite3.connect(str(SETTINGS.db_path)) as conn:
        c = conn.cursor()

        for set_num in set_nums:
            url = f"https://rebrickable.com/api/v3/lego/sets/{set_num}/"
            set_data = get_json(url, params={"key": API_KEY})

            name = set_data["name"]
            year = set_data["year"]
            theme = set_data["theme_id"]
            image_url = set_data["set_img_url"]
            rebrickable_url = set_data["set_url"]
            status = "unsorted"

            c.execute(
                "SELECT COUNT(*) FROM sets WHERE set_num = ? AND status = ?", (set_num, status)
            )
            if c.fetchone()[0] > 0:
                print(f"Skipping existing set {set_num} [{status}]")
                continue

            c.execute(
                """
                INSERT INTO sets (set_num, name, year, theme, image_url, rebrickable_url, status, added_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    set_num,
                    name,
                    year,
                    theme,
                    image_url,
                    rebrickable_url,
                    status,
                    datetime.now().isoformat(),
                ),
            )

            print(f"✅ Added set {set_num}: {name}")


if __name__ == "__main__":
    load_my_rebrickable_sets()
