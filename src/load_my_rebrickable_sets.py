from __future__ import annotations

import os
import sqlite3
from datetime import datetime

from dotenv import load_dotenv

from load_my_rebrickable_parts import fetch_owned_sets
from utils.rebrickable_api import get_json

DB_PATH = "data/lego_inventory.db"

# Load credentials from .env
load_dotenv("data/.env")
API_KEY = os.getenv("REBRICKABLE_API_KEY")
USER_TOKEN = os.getenv("REBRICKABLE_USER_TOKEN")


def load_my_rebrickable_sets():
    set_nums = fetch_owned_sets(USER_TOKEN)

    with sqlite3.connect(DB_PATH) as conn:
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
