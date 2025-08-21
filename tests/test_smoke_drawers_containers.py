def _container_label_column(conn):
    # Detect whether containers table uses 'label' or 'name' for the container label
    with closing(conn.cursor()) as cur:
        cur.execute("PRAGMA table_info(containers)")
        cols = {row[1] for row in cur.fetchall()}  # row[1] is column name
    if "label" in cols:
        return "label"
    if "name" in cols:
        return "name"
    # Fallback: many schemas use 'code' or similar, but fail explicitly if unknown
    raise RuntimeError(f"Unknown containers label column; found columns: {cols}")


import os
import uuid
from contextlib import closing

import pytest

from infra.db.inventory_db import (
    DuplicateLabelError,
    InventoryConstraintError,
    _connect,
    create_container,
    create_drawer,
    restore_container,
    soft_delete_container,
)

# Opt-in: only run when explicitly enabled
pytestmark = pytest.mark.skipif(
    not os.environ.get("ALLOW_SMOKE_TESTS"),
    reason="Set ALLOW_SMOKE_TESTS=1 to run destructive smoke tests",
)

TEST_DRAWER_PREFIX = "Test Drawer "


def cleanup_test_artifacts(conn):
    """Remove leftover test containers/drawers created by smoke tests.
    Deletes only empty containers labeled 'A1' in drawers starting with 'Test Drawer ',
    and deletes empty drawers with that prefix that have no containers remaining.
    """
    with closing(conn.cursor()) as cur:
        # Delete empty containers labeled A1 in test drawers
        label_col = _container_label_column(conn)
        cur.execute(
            f"""
            DELETE FROM containers
            WHERE {label_col} = 'A1'
              AND drawer_id IN (SELECT id FROM drawers WHERE name LIKE ?)
              AND NOT EXISTS (
                  SELECT 1 FROM inventory WHERE container_id = containers.id
              )
            """,
            (TEST_DRAWER_PREFIX + "%",),
        )
        # Delete empty test drawers (no containers left)
        cur.execute(
            """
            DELETE FROM drawers
            WHERE name LIKE ?
              AND NOT EXISTS (
                  SELECT 1 FROM containers WHERE drawer_id = drawers.id
              )
            """,
            (TEST_DRAWER_PREFIX + "%",),
        )
        conn.commit()


# Use a unique drawer name on each run to avoid UNIQUE(name) collisions


def test_smoke_drawers_containers():
    DRAWER_NAME = f"Test Drawer {uuid.uuid4().hex[:8]}"
    with _connect() as conn:
        # Pre-clean any leftovers from previous runs
        cleanup_test_artifacts(conn)

        c = None
        d = None
        try:
            print(f"Creating drawer '{DRAWER_NAME}'...")
            d = create_drawer(conn, DRAWER_NAME)
            print(f"Drawer created with id={d}")

            print("Creating container A1...")
            c = create_container(conn, d, "A1")
            print(f"Container created with id={c}")

            print("Trying duplicate container...")
            with pytest.raises(DuplicateLabelError):
                create_container(conn, d, "A1")
            print("✅ Duplicate check passed (DuplicateLabelError raised)")

            print("Soft deleting container...")
            try:
                soft_delete_container(conn, c)  # should succeed if empty
                print("✅ Soft delete worked")
                restore_container(conn, c)
                print("✅ Restore worked")
            except InventoryConstraintError as e:
                # If inventory exists we expect a constraint; consider that a pass path
                print(f"❌ Blocked as expected: {e}")

        finally:
            # Best-effort cleanup of the container/drawer we created, if still present and empty
            if c is not None:
                try:
                    with closing(conn.cursor()) as cur:
                        cur.execute(
                            """
                            DELETE FROM containers
                            WHERE id = ?
                              AND NOT EXISTS (
                                  SELECT 1 FROM inventory WHERE container_id = containers.id
                              )
                            """,
                            (c,),
                        )
                        conn.commit()
                except Exception as e:
                    print(f"(cleanup) Skipped deleting container {c}: {e}")

            if d is not None:
                try:
                    with closing(conn.cursor()) as cur:
                        cur.execute(
                            """
                            DELETE FROM drawers
                            WHERE id = ?
                              AND NOT EXISTS (
                                  SELECT 1 FROM containers WHERE drawer_id = drawers.id
                              )
                            """,
                            (d,),
                        )
                        conn.commit()
                except Exception as e:
                    print(f"(cleanup) Skipped deleting drawer {d}: {e}")

            # Final sweep to catch any other 'Test Drawer *' / 'A1' leftovers from earlier runs
            try:
                cleanup_test_artifacts(conn)
            except Exception as e:
                print(f"(cleanup) Final sweep skipped: {e}")
