"""Populate the SQLite database with sample LEGO inventory data.

This script uses the ``inventory_db`` module to insert a handful of
parts and inventory records. It is intended for testing the web
interface. Running the script multiple times will create duplicate
entries, so it's best to delete the ``lego_inventory.db`` file before
repopulating. To run:

    python3 -m lego_inventory.sample_data
"""

import inventory_db as db

def main() -> None:
    db.init_db()
    # Insert parts
    pid1 = db.insert_part("3001", "Brick 2 x 4")
    pid2 = db.insert_part("3002", "Brick 2 x 3")
    pid3 = db.insert_part("3003", "Brick 2 x 2")
    pid4 = db.insert_part("3062", "Round Brick 1 x 1")

    # Insert inventory records
    db.insert_inventory(pid1, "red", 50, "loose", container="A", drawer="1")
    db.insert_inventory(pid1, "blue", 20, "loose", container="A", drawer="2")
    db.insert_inventory(pid2, "green", 15, "teardown")
    db.insert_inventory(pid2, "yellow", 30, "in_box")
    db.insert_inventory(pid3, "black", 100, "built")
    db.insert_inventory(pid4, "white", 10, "work_in_progress")
    db.insert_inventory(pid4, "gray", 25, "loose", bin_name="General")
    print("Sample data inserted.")


if __name__ == "__main__":
    main()