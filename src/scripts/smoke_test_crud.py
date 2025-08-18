import uuid

from infra.db.inventory_db import (
    DuplicateLabelError,
    InventoryConstraintError,
    _connect,
    create_container,
    create_drawer,
    restore_container,
    soft_delete_container,
)

# Use a unique drawer name on each run to avoid UNIQUE(name) collisions
DRAWER_NAME = f"Test Drawer {uuid.uuid4().hex[:8]}"

with _connect() as conn:
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
