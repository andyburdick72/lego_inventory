from inventory_db import (
    DuplicateLabelError,
    InventoryConstraintError,
    _connect,
    create_container,
    create_drawer,
    restore_container,
    soft_delete_container,
)

with _connect() as conn:
    print("Creating drawer...")
    d = create_drawer(conn, "Test Drawer")
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
