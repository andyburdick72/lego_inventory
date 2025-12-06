from __future__ import annotations

import sqlite3

# Allow running this file directly (python src/scripts/load_my_rebrickable_sets.py)
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Final

_ROOT = Path(__file__).resolve().parents[1]  # repo root containing the 'src' package
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.settings import get_settings  # noqa: E402
from core.enums import Status  # noqa: E402
from integrations.rebrickable_api import get_json  # noqa: E402
from scripts.load_my_rebrickable_parts import fetch_owned_sets  # noqa: E402

# Centralized settings (cached)
SETTINGS = get_settings()
API_KEY: Final[str] | None = SETTINGS.rebrickable_api_key
USER_TOKEN: Final[str] | None = SETTINGS.rebrickable_user_token
if not API_KEY or not USER_TOKEN:
    raise RuntimeError(
        "Missing APP_REBRICKABLE_API_KEY or APP_REBRICKABLE_USER_TOKEN in data/.env or environment"
    )


def load_my_rebrickable_sets_noninteractive(default_status: str = "in_box", update_themes: bool = False):
    """
    Non-interactive version that uses a default status for all new sets.
    Returns a summary string of what was done.
    
    Args:
        default_status: Status to use for new sets
        update_themes: If True, update theme information for all sets (even existing ones)
    """
    if USER_TOKEN is None:
        raise ValueError("USER_TOKEN cannot be None")
    
    from core.enums import Status
    
    # Validate default status
    try:
        status_enum = Status.from_any(default_status)
        chosen_status_value = status_enum.value
    except ValueError:
        raise ValueError(f"Invalid default_status: {default_status}")
    
    set_nums = fetch_owned_sets(USER_TOKEN)
    owned_counts = Counter(set_nums)
    summary_lines = []

    with sqlite3.connect(str(SETTINGS.db_path)) as conn:
        c = conn.cursor()

        for set_num, owned_count in owned_counts.items():
            c.execute("SELECT COUNT(*) FROM sets WHERE set_num = ?", (set_num,))
            db_count = c.fetchone()[0]
            
            # Always fetch theme data if update_themes is True
            should_fetch_theme = update_themes or db_count < owned_count
            
            if db_count >= owned_count and not update_themes:
                if db_count > owned_count:
                    print(
                        f"⚠️ DB has {db_count} copies of {set_num} but Rebrickable shows {owned_count}. Skipping inserts; please reconcile."
                    )
                else:
                    print(
                        f"Skipping {set_num}: DB already has {db_count} copies (matches Rebrickable)."
                    )
                if should_fetch_theme:
                    # Still update theme even if skipping inserts
                    url = f"https://rebrickable.com/api/v3/lego/sets/{set_num}/"
                    set_data = get_json(url, params={"key": API_KEY})
                    theme_id = set_data.get("theme_id")
                    
                    # Fetch theme name from themes endpoint if we have theme_id
                    theme_name = None
                    if theme_id is not None:
                        try:
                            theme_url = f"https://rebrickable.com/api/v3/lego/themes/{theme_id}/"
                            theme_data = get_json(theme_url, params={"key": API_KEY})
                            theme_name = theme_data.get("name")
                        except Exception:
                            # If theme fetch fails, continue without theme name
                            pass
                    
                    if theme_id is not None and theme_name:
                        c.execute(
                            """
                            INSERT OR REPLACE INTO themes (id, name)
                            VALUES (?, ?)
                            """,
                            (theme_id, theme_name),
                        )
                        c.execute(
                            """
                            UPDATE sets SET theme_id = ? WHERE set_num = ?
                            """,
                            (theme_id, set_num),
                        )
                        print(f"  Updated theme for {set_num}: {theme_name}")
                continue

            url = f"https://rebrickable.com/api/v3/lego/sets/{set_num}/"
            set_data = get_json(url, params={"key": API_KEY})

            name = set_data["name"]
            year = set_data["year"]
            theme_id = set_data.get("theme_id")
            image_url = set_data["set_img_url"]
            rebrickable_url = set_data["set_url"]
            
            # Fetch theme name from themes endpoint if we have theme_id
            theme_name = None
            if theme_id is not None:
                try:
                    theme_url = f"https://rebrickable.com/api/v3/lego/themes/{theme_id}/"
                    theme_data = get_json(theme_url, params={"key": API_KEY})
                    theme_name = theme_data.get("name")
                except Exception:
                    # If theme fetch fails, continue without theme name
                    pass
            
            # Store theme if present
            if theme_id is not None and theme_name:
                c.execute(
                    """
                    INSERT OR REPLACE INTO themes (id, name)
                    VALUES (?, ?)
                    """,
                    (theme_id, theme_name),
                )

            to_insert = owned_count - db_count

            # Use the provided default status (non-interactive mode)
            skip_set = False

            # --- Insert the delta rows using the chosen status ---
            for _ in range(to_insert):
                c.execute(
                    """
                    INSERT INTO sets (set_num, name, year, theme_id, image_url, rebrickable_url, status, added_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        set_num,
                        name,
                        year,
                        theme_id,
                        image_url,
                        rebrickable_url,
                        chosen_status_value,
                        datetime.now().isoformat(),
                    ),
                )

            msg = f"✅ Added {to_insert} row(s) for set {set_num}: {name} (owned={owned_count}, was={db_count}); status='{chosen_status_value}'"
            print(msg)
            summary_lines.append(msg)
    
    return "\n".join(summary_lines) if summary_lines else "No new sets to import."


def load_my_rebrickable_sets():
    if USER_TOKEN is None:
        raise ValueError("USER_TOKEN cannot be None")
    set_nums = fetch_owned_sets(USER_TOKEN)
    owned_counts = Counter(set_nums)

    with sqlite3.connect(str(SETTINGS.db_path)) as conn:
        c = conn.cursor()

        for set_num, owned_count in owned_counts.items():
            c.execute("SELECT COUNT(*) FROM sets WHERE set_num = ?", (set_num,))
            db_count = c.fetchone()[0]
            
            # Always fetch set data to get theme information
            url = f"https://rebrickable.com/api/v3/lego/sets/{set_num}/"
            set_data = get_json(url, params={"key": API_KEY})

            name = set_data["name"]
            year = set_data["year"]
            theme_id = set_data.get("theme_id")
            image_url = set_data["set_img_url"]
            rebrickable_url = set_data["set_url"]
            
            # Fetch theme name from themes endpoint if we have theme_id
            theme_name = None
            if theme_id is not None:
                try:
                    theme_url = f"https://rebrickable.com/api/v3/lego/themes/{theme_id}/"
                    theme_data = get_json(theme_url, params={"key": API_KEY})
                    theme_name = theme_data.get("name")
                except Exception:
                    # If theme fetch fails, continue without theme name
                    pass
            
            # Store theme if present (always update themes)
            if theme_id is not None and theme_name:
                c.execute(
                    """
                    INSERT OR REPLACE INTO themes (id, name)
                    VALUES (?, ?)
                    """,
                    (theme_id, theme_name),
                )
                # Update theme_id for all existing sets with this set_num
                c.execute(
                    """
                    UPDATE sets SET theme_id = ? WHERE set_num = ?
                    """,
                    (theme_id, set_num),
                )
            
            if db_count >= owned_count:
                if db_count > owned_count:
                    print(
                        f"⚠️ DB has {db_count} copies of {set_num} but Rebrickable shows {owned_count}. Skipping inserts; please reconcile."
                    )
                else:
                    print(
                        f"Skipping {set_num}: DB already has {db_count} copies (matches Rebrickable). Theme updated."
                    )
                continue

            to_insert = owned_count - db_count

            # --- Choose status interactively for this set ---
            # Build a numbered menu from Status enum
            status_options = list(Status)
            # Try to find a sensible default (unsorted), fallback to first option
            default_idx = next(
                (
                    i
                    for i, s in enumerate(status_options)
                    if getattr(s, "value", str(s)).lower() == "unsorted"
                ),
                0,
            )

            print(
                f"\nSet {set_num}: {name} — need to add {to_insert} row(s). Choose a status for the new row(s), or skip importing this set:"
            )
            print("  [0] ** Skip this set (do not insert) **")
            for i, s in enumerate(status_options, start=1):
                label = getattr(s, "label", None)  # if your enum exposes a human label
                display = label if isinstance(label, str) else getattr(s, "value", str(s))
                default_marker = " (default)" if (i - 1) == default_idx else ""
                print(f"  [{i}] {display}{default_marker}")

            skip_set = False
            chosen_status_value: str
            while True:
                raw = input(
                    f"Enter choice 0-{len(status_options)} (0=skip, Enter defaults to {default_idx+1}): "
                ).strip()
                if raw == "":
                    chosen = status_options[default_idx]
                    chosen_status_value = getattr(chosen, "value", str(chosen))
                    break
                # allow typed commands for skipping
                if raw.lower() in {"0", "s", "skip"}:
                    skip_set = True
                    break
                if raw.isdigit():
                    n = int(raw)
                    if 1 <= n <= len(status_options):
                        chosen = status_options[n - 1]
                        chosen_status_value = getattr(chosen, "value", str(chosen))
                        break
                print("Invalid selection. Please try again.")

            if skip_set:
                print(f"⏭️ Skipping {set_num}: user chose not to import.")
                continue

            # --- Insert the delta rows using the chosen status ---
            for _ in range(to_insert):
                c.execute(
                    """
                    INSERT INTO sets (set_num, name, year, theme_id, image_url, rebrickable_url, status, added_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        set_num,
                        name,
                        year,
                        theme_id,
                        image_url,
                        rebrickable_url,
                        chosen_status_value,
                        datetime.now().isoformat(),
                    ),
                )

            print(
                f"✅ Added {to_insert} row(s) for set {set_num}: {name} (owned={owned_count}, was={db_count}); status='{chosen_status_value}'"
            )


if __name__ == "__main__":
    load_my_rebrickable_sets()
