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
from infra.db.inventory_db import _connect  # noqa: E402
from integrations.rebrickable_api import get_json  # noqa: E402
from scripts.load_my_rebrickable_parts import (  # noqa: E402
    fetch_owned_sets,
    gather_and_insert_parts,
)

# Centralized settings (cached)
SETTINGS = get_settings()
API_KEY: Final[str] | None = SETTINGS.rebrickable_api_key
USER_TOKEN: Final[str] | None = SETTINGS.rebrickable_user_token
if not API_KEY or not USER_TOKEN:
    raise RuntimeError(
        "Missing APP_REBRICKABLE_API_KEY or APP_REBRICKABLE_USER_TOKEN in data/.env or environment"
    )


def discover_new_sets(update_themes: bool = False) -> list[dict]:
    """
    Discover new sets from Rebrickable without inserting them.
    Returns a list of dicts with set information and quantity needed.
    
    Args:
        update_themes: If True, update theme information for existing sets
    
    Returns:
        List of dicts with keys: set_num, name, year, theme_id, theme_name, 
        image_url, rebrickable_url, quantity_needed, existing_count
    """
    if USER_TOKEN is None:
        raise ValueError("USER_TOKEN cannot be None")
    
    set_nums = fetch_owned_sets(USER_TOKEN)
    owned_counts = Counter(set_nums)
    new_sets_list: list[dict] = []
    
    # Use the same connection settings as the API (WAL mode, proper timeouts)
    conn = sqlite3.connect(
        str(SETTINGS.db_path), timeout=30.0, isolation_level=None, check_same_thread=False
    )
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    try:
        c = conn.cursor()
        
        for set_num, owned_count in owned_counts.items():
            c.execute("SELECT COUNT(*) FROM sets WHERE set_num = ?", (set_num,))
            db_count = c.fetchone()[0]
            
            # Always fetch theme data if update_themes is True
            should_fetch_theme = update_themes or db_count < owned_count
            
            if db_count >= owned_count and not update_themes:
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
            
            if to_insert > 0:
                new_sets_list.append({
                    "set_num": set_num,
                    "name": name,
                    "year": year,
                    "theme_id": theme_id,
                    "theme_name": theme_name,
                    "image_url": image_url,
                    "rebrickable_url": rebrickable_url,
                    "quantity_needed": to_insert,
                    "existing_count": db_count,
                })
        
        conn.commit()
    finally:
        conn.close()
    
    return new_sets_list


def apply_set_status_assignments(status_assignments: list[dict], auto_load_parts: bool = True) -> str:
    """
    Apply status assignments to new sets and insert them into the database.
    
    Args:
        status_assignments: List of dicts with keys: set_num, status, quantity
            - set_num: The set number
            - status: Status to assign (can be a single status for all copies, or a list)
            - quantity: Number of copies to insert (defaults to quantity_needed from discovery)
        auto_load_parts: If True, automatically load parts for newly inserted sets
    
    Returns:
        Summary string of what was done
    """
    if USER_TOKEN is None:
        raise ValueError("USER_TOKEN cannot be None")
    
    from core.enums import Status
    
    summary_lines = []
    new_sets: list[str] = []  # Track sets that were newly inserted
    
    # Use the same connection settings as the API (WAL mode, proper timeouts)
    conn = sqlite3.connect(
        str(SETTINGS.db_path), timeout=30.0, isolation_level=None, check_same_thread=False
    )
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    try:
        c = conn.cursor()
        
        # Fetch all set data we need
        set_nums = fetch_owned_sets(USER_TOKEN)
        owned_counts = Counter(set_nums)
        set_data_cache: dict[str, dict] = {}
        
        for assignment in status_assignments:
            set_num = assignment["set_num"]
            status = assignment.get("status", "in_box")
            quantity = assignment.get("quantity", assignment.get("quantity_needed", 1))
            
            # Validate status
            try:
                status_enum = Status.from_any(status)
                status_value = status_enum.value
            except ValueError:
                summary_lines.append(f"⚠️ Invalid status '{status}' for {set_num}, skipping")
                continue
            
            # Get set data (cache it)
            if set_num not in set_data_cache:
                url = f"https://rebrickable.com/api/v3/lego/sets/{set_num}/"
                set_data = get_json(url, params={"key": API_KEY})
                
                theme_id = set_data.get("theme_id")
                theme_name = None
                if theme_id is not None:
                    try:
                        theme_url = f"https://rebrickable.com/api/v3/lego/themes/{theme_id}/"
                        theme_data = get_json(theme_url, params={"key": API_KEY})
                        theme_name = theme_data.get("name")
                    except Exception:
                        pass
                
                set_data_cache[set_num] = {
                    "name": set_data["name"],
                    "year": set_data["year"],
                    "theme_id": theme_id,
                    "theme_name": theme_name,
                    "image_url": set_data["set_img_url"],
                    "rebrickable_url": set_data["set_url"],
                }
            
            data = set_data_cache[set_num]
            
            # Store theme if present
            if data["theme_id"] is not None and data["theme_name"]:
                c.execute(
                    """
                    INSERT OR REPLACE INTO themes (id, name)
                    VALUES (?, ?)
                    """,
                    (data["theme_id"], data["theme_name"]),
                )
            
            # Insert the sets
            for _ in range(quantity):
                c.execute(
                    """
                    INSERT INTO sets (set_num, name, year, theme_id, image_url, rebrickable_url, status, added_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        set_num,
                        data["name"],
                        data["year"],
                        data["theme_id"],
                        data["image_url"],
                        data["rebrickable_url"],
                        status_value,
                        datetime.now().isoformat(),
                    ),
                )
            
            msg = f"✅ Added {quantity} row(s) for set {set_num}: {data['name']}; status='{status_value}'"
            summary_lines.append(msg)
            
            # Track this set as newly inserted
            if set_num not in new_sets:
                new_sets.append(set_num)
        
        conn.commit()
    finally:
        conn.close()
    
    # Automatically load parts for newly discovered sets
    if auto_load_parts and new_sets:
        print(f"\n📦 Found {len(new_sets)} new set(s). Loading parts...")
        try:
            with _connect() as conn:
                gather_and_insert_parts(
                    new_sets,
                    conn,
                    insert_only_set_parts=False,  # Insert new parts too
                    include_spares=True,  # Include spare parts
                    include_minifig_parts=True,  # Include minifig parts
                    skip_refresh=False,  # Refresh existing set_parts
                )
            summary_lines.append(f"\n✅ Automatically loaded parts for {len(new_sets)} new set(s)")
        except Exception as e:
            error_msg = f"\n⚠️ Warning: Failed to automatically load parts for new sets: {e}"
            print(error_msg)
            summary_lines.append(error_msg)
    
    return "\n".join(summary_lines) if summary_lines else "No sets were inserted."


def load_my_rebrickable_sets_noninteractive(
    default_status: str = "in_box", update_themes: bool = False, auto_load_parts: bool = True
):
    """
    Non-interactive version that uses a default status for all new sets.
    Returns a summary string of what was done.

    Args:
        default_status: Status to use for new sets
        update_themes: If True, update theme information for all sets (even existing ones)
        auto_load_parts: If True, automatically load parts for newly discovered sets
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
    new_sets: list[str] = []  # Track sets that were newly inserted

    # Use the same connection settings as the API (WAL mode, proper timeouts)
    conn = sqlite3.connect(
        str(SETTINGS.db_path), timeout=30.0, isolation_level=None, check_same_thread=False
    )
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    try:
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

            # Track this set as newly inserted
            if set_num not in new_sets:
                new_sets.append(set_num)

        conn.commit()
    finally:
        conn.close()

    # Automatically load parts for newly discovered sets
    if auto_load_parts and new_sets:
        print(f"\n📦 Found {len(new_sets)} new set(s). Loading parts...")
        try:
            with _connect() as conn:
                gather_and_insert_parts(
                    new_sets,
                    conn,
                    insert_only_set_parts=False,  # Insert new parts too
                    include_spares=True,  # Include spare parts
                    include_minifig_parts=True,  # Include minifig parts
                    skip_refresh=False,  # Refresh existing set_parts
                )
            summary_lines.append(f"\n✅ Automatically loaded parts for {len(new_sets)} new set(s)")
        except Exception as e:
            error_msg = f"\n⚠️ Warning: Failed to automatically load parts for new sets: {e}"
            print(error_msg)
            summary_lines.append(error_msg)

    return "\n".join(summary_lines) if summary_lines else "No new sets to import."


def load_my_rebrickable_sets(auto_load_parts: bool = True):
    """
    Interactive version that prompts for status for each new set.

    Args:
        auto_load_parts: If True, automatically load parts for newly discovered sets
    """
    if USER_TOKEN is None:
        raise ValueError("USER_TOKEN cannot be None")
    set_nums = fetch_owned_sets(USER_TOKEN)
    owned_counts = Counter(set_nums)
    new_sets: list[str] = []  # Track sets that were newly inserted

    # Use the same connection settings as the API (WAL mode, proper timeouts)
    conn = sqlite3.connect(
        str(SETTINGS.db_path), timeout=30.0, isolation_level=None, check_same_thread=False
    )
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    try:
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

            # Track this set as newly inserted
            if set_num not in new_sets:
                new_sets.append(set_num)

        conn.commit()
    finally:
        conn.close()

    # Automatically load parts for newly discovered sets
    if auto_load_parts and new_sets:
        print(f"\n📦 Found {len(new_sets)} new set(s). Loading parts...")
        try:
            with _connect() as conn:
                gather_and_insert_parts(
                    new_sets,
                    conn,
                    insert_only_set_parts=False,  # Insert new parts too
                    include_spares=True,  # Include spare parts
                    include_minifig_parts=True,  # Include minifig parts
                    skip_refresh=False,  # Refresh existing set_parts
                )
            print(f"\n✅ Automatically loaded parts for {len(new_sets)} new set(s)")
        except Exception as e:
            print(f"\n⚠️ Warning: Failed to automatically load parts for new sets: {e}")
            import traceback

            print(traceback.format_exc())


if __name__ == "__main__":
    load_my_rebrickable_sets()
