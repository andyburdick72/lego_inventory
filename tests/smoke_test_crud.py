import uuid
from contextlib import closing

from infra.db.inventory_db import (
    DuplicateLabelError,
    InventoryConstraintError,
    _connect,
    create_container,
    create_drawer,
    restore_container,
    soft_delete_container,
)

TEST_DRAWER_PREFIX = "Test Drawer "


def cleanup_test_artifacts(conn):
    """Remove leftover test containers/drawers created by smoke tests.
    Deletes only empty containers named 'A1' in drawers starting with 'Test Drawer ',
    and deletes empty drawers with that prefix that have no containers remaining.
    """
    with closing(conn.cursor()) as cur:
        # Delete empty containers named A1 in test drawers
        cur.execute(
            """
            DELETE FROM containers
            WHERE name = 'A1'
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
        try:
            create_container(conn, d, "A1")
        except DuplicateLabelError:
            print("✅ Duplicate check passed (DuplicateLabelError raised)")

        print("Soft deleting container...")
        try:
            soft_delete_container(conn, c)  # should succeed if empty
            print("✅ Soft delete worked")
            restore_container(conn, c)
            print("✅ Restore worked")
        except InventoryConstraintError as e:
            print(f"❌ Blocked as expected: {e}")

    finally:
        # Best-effort cleanup of the container/drawer we created, if still present and empty
        if c is not None:
            try:
                with closing(conn.cursor()) as cur:
                    # Delete the specific container if empty
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
                    # Delete the drawer if it has no remaining containers
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
