from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

from .base import BaseRepo


class InventoryRepo(BaseRepo):
    def iter_loose_parts(self, filters: Mapping[str, Any] | None = None) -> Iterable[dict]:
        """
        Stream loose-part rows honoring simple filters.
        Returned shape:
          design_id, part_name, color_id, color_name, hex, quantity,
          drawer_name, container_name, container_id
        Supported filters (all optional):
          - design_id: str
          - color_id: int
          - drawer_id: int
          - container_id: int
          - search: str (matches part name or design_id)
          - include_deleted: bool
        """
        filters = dict(filters or {})
        clauses: list[str] = ["i.status = 'loose'"]
        params: list[Any] = []

        if v := filters.get("design_id"):
            clauses.append("i.design_id = ?")
            params.append(v)
        if (v := filters.get("color_id")) is not None:
            clauses.append("i.color_id = ?")
            params.append(v)
        if (v := filters.get("container_id")) is not None:
            clauses.append("i.container_id = ?")
            params.append(v)
        if (v := filters.get("drawer_id")) is not None:
            clauses.append("c.drawer_id = ?")
            params.append(v)
        if q := filters.get("search"):
            clauses.append("(p.name LIKE ? OR p.design_id LIKE ?)")
            like = f"%{q}%"
            params.extend([like, like])

        include_deleted = bool(filters.get("include_deleted"))
        if not include_deleted:
            clauses.append("c.deleted_at IS NULL")
            clauses.append("d.deleted_at IS NULL")

        where = " AND ".join(clauses) if clauses else "1=1"

        sql = f"""
        SELECT
            i.design_id,
            p.name AS part_name,
            i.color_id,
            col.name AS color_name,
            col.hex AS hex,
            i.quantity,
            d.name  AS drawer_name,
            c.name  AS container_name,
            i.container_id
        FROM inventory i
        JOIN parts   p   ON p.design_id = i.design_id
        JOIN colors  col ON col.id       = i.color_id
        LEFT JOIN containers c ON c.id = i.container_id
        LEFT JOIN drawers    d ON d.id = c.drawer_id
        WHERE {where}
        ORDER BY p.name COLLATE NOCASE, i.design_id, i.color_id
        """
        return self._iter(sql, params)

    def storage_location_counts(self, filters: Mapping[str, Any] | None = None) -> list[dict]:
        """
        Aggregate loose inventory by drawer/container.
        Returns: drawer_name, container_name, total_quantity, unique_parts
        Supported filters:
          - drawer_id: int
          - search: str (matches part name or design_id)
          - include_deleted: bool
        """
        filters = dict(filters or {})
        clauses: list[str] = ["i.status = 'loose'"]
        params: list[Any] = []

        if (v := filters.get("drawer_id")) is not None:
            clauses.append("c.drawer_id = ?")
            params.append(v)
        if q := filters.get("search"):
            clauses.append(
                "EXISTS (SELECT 1 FROM parts p2 WHERE p2.design_id = i.design_id AND (p2.name LIKE ? OR p2.design_id LIKE ?))"
            )
            like = f"%{q}%"
            params.extend([like, like])

        include_deleted = bool(filters.get("include_deleted"))
        if not include_deleted:
            clauses.append("c.deleted_at IS NULL")
            clauses.append("d.deleted_at IS NULL")

        where = " AND ".join(clauses) if clauses else "1=1"

        sql = f"""
        SELECT
            d.name AS drawer_name,
            c.name AS container_name,
            SUM(i.quantity) AS total_quantity,
            COUNT(DISTINCT i.design_id || ':' || i.color_id) AS unique_parts
        FROM inventory i
        LEFT JOIN containers c ON c.id = i.container_id
        LEFT JOIN drawers    d ON d.id = c.drawer_id
        WHERE {where}
        GROUP BY d.name, c.name
        ORDER BY d.name COLLATE NOCASE, c.name COLLATE NOCASE
        """
        return self._all(sql, params)

    def inventory_by_part(self, design_id: str) -> list[dict]:
        """
        Return all inventory rows for a given design_id with color info,
        matching the legacy shape used by inventory_db.inventory_by_part.
        Columns: color_name, hex, color_id, quantity, status, drawer, container, set_number
        """
        return self._all(
            """
            SELECT c.name AS color_name,
                c.hex,
                i.color_id,
                i.quantity,
                i.status,
                i.drawer,
                i.container,
                i.set_number
            FROM inventory i
            JOIN colors c ON c.id = i.color_id
            WHERE i.design_id = ?
            ORDER BY i.status, i.drawer, i.container, i.color_id
            """,
            [design_id],
        )

    def loose_inventory_for_part(self, design_id: str) -> list[dict]:
        """
        Return only 'loose' inventory rows for a given design_id.
        Returns: part_id, color_id, color_name, color_hex, quantity, status,
                 drawer_id, drawer_name, container_id, container_label,
                 part_name, image_url, rebrickable_url
        """
        return self._all(
            """
            SELECT 
                i.design_id AS part_id,
                i.color_id,
                col.name AS color_name,
                col.hex AS color_hex,
                i.quantity,
                i.status,
                d.id AS drawer_id,
                d.name AS drawer_name,
                c.id AS container_id,
                c.name AS container_label,
                p.name AS part_name,
                p.part_img_url AS image_url,
                p.part_url AS rebrickable_url
            FROM inventory i
            JOIN colors col ON col.id = i.color_id
            LEFT JOIN parts p ON p.design_id = i.design_id
            LEFT JOIN containers c ON c.id = i.container_id
            LEFT JOIN drawers d ON d.id = c.drawer_id
            WHERE i.design_id = ? AND i.status = 'loose'
            ORDER BY d.name, c.name, i.color_id
            """,
            [design_id],
        )

    def loose_inventory_for_part_color(self, design_id: str, color_id: int) -> list[dict]:
        """
        Return only 'loose' inventory rows for a specific part+color combination.
        Returns: drawer_id, drawer_name, container_id, container_name, quantity
        """
        return self._all(
            """
            SELECT 
                d.id AS drawer_id,
                d.name AS drawer_name,
                c.id AS container_id,
                c.name AS container_name,
                i.quantity
            FROM inventory i
            LEFT JOIN containers c ON c.id = i.container_id
            LEFT JOIN drawers d ON d.id = c.drawer_id
            WHERE i.design_id = ? AND i.color_id = ? AND i.status = 'loose'
                AND (c.deleted_at IS NULL OR c.id IS NULL)
                AND (d.deleted_at IS NULL OR d.id IS NULL)
            ORDER BY d.name, c.name
            """,
            [design_id, color_id],
        )

    def get_putaway_bin_parts(self, search: str | None = None) -> list[dict]:
        """
        Return all parts currently in the putaway bin, with part and color details.
        Optionally filters by search_query matching part name or design_id.
        Excludes parts flagged with ignore_in_inventory.
        
        Returns: inventory_id, design_id, part_name, color_id, color_name, hex,
                 quantity, drawer_id, drawer_name, container_id, container_name,
                 part_url, part_img_url
        """
        # First, get the putaway bin container_id
        putaway_bin = self._one(
            """
            SELECT c.id AS container_id
            FROM containers c
            JOIN drawers d ON d.id = c.drawer_id
            WHERE c.is_put_away_bin = 1 
              AND c.deleted_at IS NULL 
              AND d.deleted_at IS NULL
            LIMIT 1
            """,
            [],
        )
        
        if not putaway_bin:
            return []
        
        container_id = putaway_bin.get("container_id")
        
        clauses = ["i.status = 'loose'", "i.container_id = ?", "COALESCE(p.ignore_in_inventory, 0) = 0"]
        params: list[Any] = [container_id]
        
        if search:
            clauses.append("(p.name LIKE ? OR p.design_id LIKE ?)")
            like = f"%{search}%"
            params.extend([like, like])
        
        where = " AND ".join(clauses)
        
        sql = f"""
            SELECT 
                i.id AS inventory_id,
                i.design_id,
                p.name AS part_name,
                i.color_id,
                col.name AS color_name,
                col.hex,
                i.quantity,
                d.id AS drawer_id,
                d.name AS drawer_name,
                c.id AS container_id,
                c.name AS container_name,
                p.part_url,
                p.part_img_url
            FROM inventory i
            JOIN parts p ON p.design_id = i.design_id
            JOIN colors col ON col.id = i.color_id
            LEFT JOIN containers c ON c.id = i.container_id
            LEFT JOIN drawers d ON d.id = c.drawer_id
            WHERE {where}
            ORDER BY p.name COLLATE NOCASE, i.design_id, i.color_id
        """
        return self._all(sql, params)

    def locations_rows_new(self) -> list[dict]:
        """
        Rows for the 'new path': inventory linked to containers/drawers (container_id not null).
        Columns: drawer, container, design_id, name, color_name, hex, qty
        """
        return self._all(
            """
            SELECT d.name AS drawer, c.name AS container,
                p.design_id, p.name,
                col.name AS color_name, col.hex,
                SUM(i.quantity) AS qty
            FROM inventory i
            JOIN containers c ON c.id = i.container_id
            JOIN drawers    d ON d.id = c.drawer_id
            JOIN parts      p ON p.design_id = i.design_id
            JOIN colors     col ON col.id = i.color_id
            WHERE i.status = 'loose' AND i.container_id IS NOT NULL
            AND c.deleted_at IS NULL AND d.deleted_at IS NULL
            GROUP BY d.name, c.name, p.design_id, i.color_id
            """,
            [],
        )

    def locations_rows_legacy(self) -> list[dict]:
        """
        Rows for the 'legacy path': inventory without container_id, using text columns.
        Columns: drawer, container, design_id, name, color_name, hex, qty
        """
        return self._all(
            """
            SELECT i.drawer AS drawer, i.container AS container,
                p.design_id, p.name,
                col.name AS color_name, col.hex,
                SUM(i.quantity) AS qty
            FROM inventory i
            JOIN parts  p  ON p.design_id = i.design_id
            JOIN colors col ON col.id     = i.color_id
            WHERE i.status = 'loose' AND i.container_id IS NULL
            GROUP BY i.drawer, i.container, p.design_id, i.color_id
            """,
            [],
        )

    def parts_with_totals(self) -> list[dict]:
        """
        Parts with total loose quantities (LEFT JOIN to include zero totals).
        Columns: design_id, name, total_quantity
        """
        return self._all(
            """
            SELECT p.design_id, p.name,
                SUM(i.quantity) AS total_quantity
            FROM parts p
            LEFT JOIN inventory i ON i.design_id = p.design_id
            GROUP BY p.design_id
            ORDER BY p.design_id
            """,
            [],
        )

    def search_parts(self, query: str) -> list[dict]:
        """
        Search parts by design_id or name (LIKE %query%) and include total quantities.
        Columns: design_id, name, total_quantity
        """
        pattern = f"%{query}%"
        return self._all(
            """
            SELECT p.design_id, p.name,
                SUM(i.quantity) AS total_quantity
            FROM parts p
            LEFT JOIN inventory i ON i.design_id = p.design_id
            WHERE p.design_id LIKE ? OR p.name LIKE ?
            GROUP BY p.design_id
            ORDER BY p.design_id
            """,
            [pattern, pattern],
        )

    def loose_total(self) -> int:
        """Return the total loose quantity (COALESCE SUM)."""
        row = self._one("SELECT COALESCE(SUM(quantity),0) AS q FROM inventory WHERE status='loose'")
        return int(row["q"]) if row and row["q"] is not None else 0

    def get_loose_inventory_totals(self) -> list[dict]:
        """
        Return loose inventory totals grouped by design_id and color_id.
        Columns: design_id, color_id, quantity
        Note: Part/color names are not included here - they're added in the service layer
        """
        return self._all(
            """
            SELECT design_id, color_id, SUM(quantity) AS quantity
            FROM inventory
            WHERE status = 'loose'
            GROUP BY design_id, color_id
            ORDER BY design_id, color_id
            """,
            [],
        )

    def get_part_color_info(self, design_id: str, color_id: int) -> dict | None:
        """
        Get part and color information for a design_id and color_id.
        Returns: part_name, color_name, color_hex, part_url, part_img_url
        """
        # Query parts and colors separately and combine
        part_row = self._one(
            """
            SELECT name, part_url, part_img_url
            FROM parts
            WHERE design_id = ?
            """,
            [design_id],
        )
        color_row = self._one(
            """
            SELECT name, hex
            FROM colors
            WHERE id = ?
            """,
            [color_id],
        )

        if not part_row or not color_row:
            return None

        return {
            "part_name": part_row.get("name"),
            "color_name": color_row.get("name"),
            "color_hex": color_row.get("hex"),
            "part_url": part_row.get("part_url"),
            "part_img_url": part_row.get("part_img_url"),
        }

    def update_loose_inventory_quantity(
        self, design_id: str, color_id: int, new_quantity: int
    ) -> None:
        """
        Update the total loose inventory quantity for a part+color.

        This consolidates all inventory records for this part+color:
        - If new_quantity is 0, deletes all records
        - If new_quantity > 0:
          - If no records exist, creates one with container_id=NULL
          - If records exist, updates the first one and deletes the rest
        """
        # Get all current inventory records for this part+color
        current_records = self._all(
            """
            SELECT id, container_id, quantity
            FROM inventory
            WHERE design_id = ? AND color_id = ? AND status = 'loose'
            ORDER BY id
            """,
            [design_id, color_id],
        )

        if new_quantity == 0:
            # Delete all records
            self.conn.execute(
                """
                DELETE FROM inventory
                WHERE design_id = ? AND color_id = ? AND status = 'loose'
                """,
                [design_id, color_id],
            )
        elif current_records:
            # Update first record, delete rest
            first_id = current_records[0]["id"]
            self.conn.execute(
                """
                UPDATE inventory
                SET quantity = ?
                WHERE id = ?
                """,
                [new_quantity, first_id],
            )
            # Delete remaining records
            if len(current_records) > 1:
                other_ids = [r["id"] for r in current_records[1:]]
                placeholders = ",".join(["?"] * len(other_ids))
                self.conn.execute(
                    f"""
                    DELETE FROM inventory
                    WHERE id IN ({placeholders})
                    """,
                    other_ids,
                )
        else:
            # No records exist, create one
            self.conn.execute(
                """
                INSERT INTO inventory (design_id, color_id, quantity, status)
                VALUES (?, ?, ?, 'loose')
                """,
                [design_id, color_id, new_quantity],
            )

        self.conn.commit()

    def get_inventory_by_location(
        self, design_id: str, color_id: int, drawer_id: int | None, container_id: int | None
    ) -> list[dict]:
        """
        Get inventory for a part+color at a specific location.
        Returns: list of dicts with quantity, drawer_id, container_id, drawer_name, container_name
        """
        clauses = [
            "i.design_id = ?",
            "i.color_id = ?",
            "i.status = 'loose'",
        ]
        params = [design_id, color_id]

        if drawer_id is not None:
            clauses.append("c.drawer_id = ?")
            params.append(drawer_id)
        else:
            clauses.append("c.drawer_id IS NULL")

        if container_id is not None:
            clauses.append("i.container_id = ?")
            params.append(container_id)
        else:
            clauses.append("i.container_id IS NULL")

        where = " AND ".join(clauses)

        return self._all(
            f"""
            SELECT 
                i.quantity,
                d.id AS drawer_id,
                d.name AS drawer_name,
                c.id AS container_id,
                c.name AS container_name
            FROM inventory i
            LEFT JOIN containers c ON c.id = i.container_id
            LEFT JOIN drawers d ON d.id = c.drawer_id
            WHERE {where}
            """,
            params,
        )

    def get_inventory_totals_by_location(self, design_id: str, color_id: int) -> list[dict]:
        """
        Get inventory totals for a part+color grouped by location.
        Returns: list of dicts with drawer_id, container_id, drawer_name, container_name, quantity
        """
        return self._all(
            """
            SELECT 
                d.id AS drawer_id,
                d.name AS drawer_name,
                c.id AS container_id,
                c.name AS container_name,
                SUM(i.quantity) AS quantity
            FROM inventory i
            LEFT JOIN containers c ON c.id = i.container_id
            LEFT JOIN drawers d ON d.id = c.drawer_id
            WHERE i.design_id = ? AND i.color_id = ? AND i.status = 'loose'
            GROUP BY d.id, c.id, d.name, c.name
            ORDER BY d.id, c.id
            """,
            [design_id, color_id],
        )

    def set_inventory_quantity_at_location(
        self,
        design_id: str,
        color_id: int,
        quantity: int,
        drawer_id: int | None,
        container_id: int | None,
    ) -> None:
        """
        Set inventory quantity at a specific location for a part+color.

        This will:
        - Delete/update only inventory records at the SPECIFIC location (matching container_id)
        - Leave inventory at other locations untouched
        - Create a new inventory record at the specified location (if quantity > 0)
        - If drawer_id/container_id are None, updates records without location (container_id IS NULL)

        This allows a part+color to have inventory in multiple locations simultaneously
        (e.g., some in put-away bin for teardown sets, some in other locations for loose parts).
        """
        # Delete existing inventory at this SPECIFIC location only
        if container_id is not None:
            # Specific container location
            self.conn.execute(
                """
                DELETE FROM inventory
                WHERE design_id = ? AND color_id = ? AND status = 'loose' AND container_id = ?
                """,
                [design_id, color_id, container_id],
            )
        else:
            # No specific location (container_id IS NULL)
            self.conn.execute(
                """
                DELETE FROM inventory
                WHERE design_id = ? AND color_id = ? AND status = 'loose' AND container_id IS NULL
                """,
                [design_id, color_id],
            )

        # If quantity > 0, create new record at specified location
        if quantity > 0:
            if container_id is not None:
                # Specific container location
                self.conn.execute(
                    """
                    INSERT INTO inventory (design_id, color_id, quantity, status, container_id)
                    VALUES (?, ?, ?, 'loose', ?)
                    """,
                    [design_id, color_id, quantity, container_id],
                )
            else:
                # No specific location (loose parts that can be anywhere)
                self.conn.execute(
                    """
                    INSERT INTO inventory (design_id, color_id, quantity, status)
                    VALUES (?, ?, ?, 'loose')
                    """,
                    [design_id, color_id, quantity],
                )

        self.conn.commit()

    def get_inventory_by_id(self, inventory_id: int) -> dict | None:
        """
        Get a single inventory item by id.
        Returns: dict with all inventory fields plus joined part/color/container/drawer info
        """
        return self._one(
            """
            SELECT 
                i.id,
                i.design_id AS part_id,
                i.color_id,
                col.name AS color_name,
                col.hex AS color_hex,
                i.quantity,
                i.status,
                d.id AS drawer_id,
                d.name AS drawer_name,
                c.id AS container_id,
                c.name AS container_label,
                p.name AS part_name,
                p.part_img_url AS image_url,
                p.part_url AS rebrickable_url
            FROM inventory i
            JOIN parts p ON p.design_id = i.design_id
            JOIN colors col ON col.id = i.color_id
            LEFT JOIN containers c ON c.id = i.container_id
            LEFT JOIN drawers d ON d.id = c.drawer_id
            WHERE i.id = ?
            """,
            [inventory_id],
        )

    def update_inventory_quantity(self, inventory_id: int, quantity: int) -> None:
        """
        Update the quantity of a specific inventory item.
        Raises error if inventory_id doesn't exist.
        """
        if quantity < 0:
            raise ValueError("Quantity cannot be negative")

        # Check if inventory exists
        existing = self._one(
            "SELECT id, quantity FROM inventory WHERE id = ?",
            [inventory_id],
        )
        if not existing:
            raise ValueError(f"Inventory item {inventory_id} not found")

        if quantity == 0:
            # Delete the inventory item
            self.conn.execute("DELETE FROM inventory WHERE id = ?", [inventory_id])
        else:
            # Update quantity
            self.conn.execute(
                "UPDATE inventory SET quantity = ? WHERE id = ?",
                [quantity, inventory_id],
            )

        self.conn.commit()

    def update_inventory_location(self, inventory_id: int, container_id: int | None) -> None:
        """
        Update the location (container_id) of a specific inventory item.
        Raises error if inventory_id doesn't exist.
        """
        # Check if inventory exists
        existing = self._one(
            "SELECT id FROM inventory WHERE id = ?",
            [inventory_id],
        )
        if not existing:
            raise ValueError(f"Inventory item {inventory_id} not found")

        # Update container_id
        self.conn.execute(
            "UPDATE inventory SET container_id = ? WHERE id = ?",
            [container_id, inventory_id],
        )

        self.conn.commit()

    def delete_inventory(self, inventory_id: int) -> None:
        """
        Delete a specific inventory item.
        Raises error if inventory_id doesn't exist.
        """
        # Check if inventory exists
        existing = self._one(
            "SELECT id FROM inventory WHERE id = ?",
            [inventory_id],
        )
        if not existing:
            raise ValueError(f"Inventory item {inventory_id} not found")

        self.conn.execute("DELETE FROM inventory WHERE id = ?", [inventory_id])
        self.conn.commit()

    def move_inventory(
        self,
        from_inventory_id: int,
        to_container_id: int | None,
        quantity: int,
    ) -> None:
        """
        Move a quantity of parts from one inventory item to another location.

        This will:
        1. Check if the source inventory has enough quantity
        2. Reduce the source inventory by the quantity
        3. Find or create inventory at the destination location
        4. Increase the destination inventory by the quantity

        If the source inventory quantity becomes 0, it will be deleted.
        """
        if quantity <= 0:
            raise ValueError("Quantity must be positive")

        # Get source inventory
        source = self._one(
            """
            SELECT id, design_id, color_id, quantity, container_id
            FROM inventory
            WHERE id = ?
            """,
            [from_inventory_id],
        )
        if not source:
            raise ValueError(f"Source inventory item {from_inventory_id} not found")

        if source["quantity"] < quantity:
            raise ValueError(
                f"Insufficient quantity. Available: {source['quantity']}, requested: {quantity}"
            )

        design_id = source["design_id"]
        color_id = source["color_id"]
        new_source_quantity = source["quantity"] - quantity

        # Check if destination inventory exists
        if to_container_id is not None:
            dest = self._one(
                """
                SELECT id, quantity
                FROM inventory
                WHERE design_id = ? AND color_id = ? AND status = 'loose' AND container_id = ?
                """,
                [design_id, color_id, to_container_id],
            )
        else:
            dest = self._one(
                """
                SELECT id, quantity
                FROM inventory
                WHERE design_id = ? AND color_id = ? AND status = 'loose' AND container_id IS NULL
                """,
                [design_id, color_id],
            )

        # Update source inventory
        if new_source_quantity == 0:
            self.conn.execute("DELETE FROM inventory WHERE id = ?", [from_inventory_id])
        else:
            self.conn.execute(
                "UPDATE inventory SET quantity = ? WHERE id = ?",
                [new_source_quantity, from_inventory_id],
            )

        # Update or create destination inventory
        if dest:
            new_dest_quantity = dest["quantity"] + quantity
            self.conn.execute(
                "UPDATE inventory SET quantity = ? WHERE id = ?",
                [new_dest_quantity, dest["id"]],
            )
        else:
            # Create new inventory at destination
            if to_container_id is not None:
                self.conn.execute(
                    """
                    INSERT INTO inventory (design_id, color_id, quantity, status, container_id)
                    VALUES (?, ?, ?, 'loose', ?)
                    """,
                    [design_id, color_id, quantity, to_container_id],
                )
            else:
                self.conn.execute(
                    """
                    INSERT INTO inventory (design_id, color_id, quantity, status)
                    VALUES (?, ?, ?, 'loose')
                    """,
                    [design_id, color_id, quantity],
                )

        self.conn.commit()

    def elements_in_multiple_locations(self) -> list[dict]:
        """
        Find elements (part + color) that exist in multiple non-put-away-bin locations.

        Returns a list of dicts with:
        - design_id, part_name, color_id, color_name, color_hex
        - part_url, part_img_url
        - location_count (number of distinct locations, excluding put-away bin)
        - total_quantity (sum across all non-put-away locations)
        - locations (list of location dicts with drawer_id, drawer_name, container_id, container_name, quantity)
        """
        # First, get the put-away bin container_id if it exists
        put_away_bin = self._one(
            """
            SELECT c.id AS container_id
            FROM containers c
            JOIN drawers d ON d.id = c.drawer_id
            WHERE c.is_put_away_bin = 1 
              AND c.deleted_at IS NULL 
              AND d.deleted_at IS NULL
            LIMIT 1
            """,
            [],
        )
        put_away_container_id = put_away_bin.get("container_id") if put_away_bin else None

        # Build the query to find elements in multiple locations
        # We'll use a CTE to:
        # 1. Group by design_id + color_id and count distinct locations (excluding put-away)
        # 2. Filter to only those with >1 location
        # 3. Join back to get all location details

        if put_away_container_id is not None:
            # Exclude put-away bin
            location_filter = "AND (i.container_id IS NULL OR i.container_id != ?)"
            params = [put_away_container_id]
        else:
            # No put-away bin configured, include all locations
            location_filter = ""
            params = []

        sql = f"""
        WITH element_locations AS (
            SELECT 
                i.design_id,
                i.color_id,
                d.id AS drawer_id,
                d.name AS drawer_name,
                c.id AS container_id,
                c.name AS container_name,
                SUM(i.quantity) AS quantity
            FROM inventory i
            LEFT JOIN containers c ON c.id = i.container_id
            LEFT JOIN drawers d ON d.id = c.drawer_id
            WHERE i.status = 'loose'
              AND (c.deleted_at IS NULL OR c.id IS NULL)
              AND (d.deleted_at IS NULL OR d.id IS NULL)
              {location_filter}
            GROUP BY i.design_id, i.color_id, d.id, c.id, d.name, c.name
        ),
        element_counts AS (
            SELECT 
                design_id,
                color_id,
                COUNT(DISTINCT drawer_id || ':' || COALESCE(container_id, 'NULL')) AS location_count,
                SUM(quantity) AS total_quantity
            FROM element_locations
            GROUP BY design_id, color_id
            HAVING location_count > 1
        )
        SELECT 
            ec.design_id,
            p.name AS part_name,
            ec.color_id,
            col.name AS color_name,
            col.hex AS color_hex,
            p.part_url,
            p.part_img_url,
            ec.location_count,
            ec.total_quantity
        FROM element_counts ec
        JOIN parts p ON p.design_id = ec.design_id
        JOIN colors col ON col.id = ec.color_id
        ORDER BY ec.location_count DESC, p.name COLLATE NOCASE, ec.color_id
        """

        elements = self._all(sql, params)

        # For each element, get all its locations
        result = []
        for elem in elements:
            design_id = elem["design_id"]
            color_id = elem["color_id"]

            # Get all locations for this element (excluding put-away)
            # Include the first inventory ID for each location for move operations
            if put_away_container_id is not None:
                locations = self._all(
                    """
                    SELECT 
                        d.id AS drawer_id,
                        d.name AS drawer_name,
                        c.id AS container_id,
                        c.name AS container_name,
                        SUM(i.quantity) AS quantity,
                        MIN(i.id) AS inventory_id
                    FROM inventory i
                    LEFT JOIN containers c ON c.id = i.container_id
                    LEFT JOIN drawers d ON d.id = c.drawer_id
                    WHERE i.design_id = ? 
                      AND i.color_id = ?
                      AND i.status = 'loose'
                      AND (i.container_id IS NULL OR i.container_id != ?)
                      AND (c.deleted_at IS NULL OR c.id IS NULL)
                      AND (d.deleted_at IS NULL OR d.id IS NULL)
                    GROUP BY d.id, c.id, d.name, c.name
                    ORDER BY d.name COLLATE NOCASE, c.name COLLATE NOCASE
                    """,
                    [design_id, color_id, put_away_container_id],
                )
            else:
                locations = self._all(
                    """
                    SELECT 
                        d.id AS drawer_id,
                        d.name AS drawer_name,
                        c.id AS container_id,
                        c.name AS container_name,
                        SUM(i.quantity) AS quantity,
                        MIN(i.id) AS inventory_id
                    FROM inventory i
                    LEFT JOIN containers c ON c.id = i.container_id
                    LEFT JOIN drawers d ON d.id = c.drawer_id
                    WHERE i.design_id = ? 
                      AND i.color_id = ?
                      AND i.status = 'loose'
                      AND (c.deleted_at IS NULL OR c.id IS NULL)
                      AND (d.deleted_at IS NULL OR d.id IS NULL)
                    GROUP BY d.id, c.id, d.name, c.name
                    ORDER BY d.name COLLATE NOCASE, c.name COLLATE NOCASE
                    """,
                    [design_id, color_id],
                )

            result.append(
                {
                    **elem,
                    "locations": locations,
                }
            )

        return result

    def analyze_element_storage_patterns(self) -> list[dict]:
        """
        Analyze storage patterns at the element level (design_id + color_id).

        Returns containers where specific elements are stored, with statistics:
        - container_id, drawer_id, drawer_name, container_name
        - element_count (number of distinct elements stored there)
        - total_quantity (sum of all quantities)
        - is_exclusive (True if container only stores this one element)
        """
        return self._all(
            """
            SELECT 
                c.id AS container_id,
                d.id AS drawer_id,
                d.name AS drawer_name,
                c.name AS container_name,
                COUNT(DISTINCT i.design_id || ':' || i.color_id) AS element_count,
                SUM(i.quantity) AS total_quantity,
                CASE 
                    WHEN COUNT(DISTINCT i.design_id || ':' || i.color_id) = 1 THEN 1
                    ELSE 0
                END AS is_exclusive
            FROM inventory i
            JOIN containers c ON c.id = i.container_id
            JOIN drawers d ON d.id = c.drawer_id
            WHERE i.status = 'loose'
              AND i.container_id IS NOT NULL
              AND c.deleted_at IS NULL
              AND d.deleted_at IS NULL
              AND c.is_put_away_bin = 0
            GROUP BY c.id, d.id, d.name, c.name
            ORDER BY is_exclusive DESC, element_count ASC, d.name, c.name
            """,
            [],
        )

    def analyze_part_storage_patterns(self) -> list[dict]:
        """
        Analyze storage patterns at the part level (design_id only, any color).

        Returns containers where specific parts (any color) are stored:
        - container_id, drawer_id, drawer_name, container_name
        - design_id, part_name
        - color_count (number of distinct colors for this part in this container)
        - total_quantity
        """
        return self._all(
            """
            SELECT 
                c.id AS container_id,
                d.id AS drawer_id,
                d.name AS drawer_name,
                c.name AS container_name,
                i.design_id,
                p.name AS part_name,
                COUNT(DISTINCT i.color_id) AS color_count,
                SUM(i.quantity) AS total_quantity
            FROM inventory i
            JOIN containers c ON c.id = i.container_id
            JOIN drawers d ON d.id = c.drawer_id
            JOIN parts p ON p.design_id = i.design_id
            WHERE i.status = 'loose'
              AND i.container_id IS NOT NULL
              AND c.deleted_at IS NULL
              AND d.deleted_at IS NULL
              AND c.is_put_away_bin = 0
            GROUP BY c.id, d.id, d.name, c.name, i.design_id, p.name
            ORDER BY d.name, c.name, p.name
            """,
            [],
        )

    def analyze_category_storage_patterns(self) -> list[dict]:
        """
        Analyze storage patterns at the category level (part_category_id).

        Returns containers where parts from specific categories are stored:
        - container_id, drawer_id, drawer_name, container_name
        - part_category_id, part_category_name
        - part_count (number of distinct parts in this category in this container)
        - element_count (number of distinct elements)
        - total_quantity
        """
        return self._all(
            """
            SELECT 
                c.id AS container_id,
                d.id AS drawer_id,
                d.name AS drawer_name,
                c.name AS container_name,
                p.part_category_id,
                pc.name AS part_category_name,
                COUNT(DISTINCT i.design_id) AS part_count,
                COUNT(DISTINCT i.design_id || ':' || i.color_id) AS element_count,
                SUM(i.quantity) AS total_quantity
            FROM inventory i
            JOIN containers c ON c.id = i.container_id
            JOIN drawers d ON d.id = c.drawer_id
            JOIN parts p ON p.design_id = i.design_id
            LEFT JOIN part_categories pc ON pc.id = p.part_category_id
            WHERE i.status = 'loose'
              AND i.container_id IS NOT NULL
              AND c.deleted_at IS NULL
              AND d.deleted_at IS NULL
              AND c.is_put_away_bin = 0
              AND p.part_category_id IS NOT NULL
            GROUP BY c.id, d.id, d.name, c.name, p.part_category_id, pc.name
            ORDER BY d.name, c.name, pc.name
            """,
            [],
        )

    def find_element_location(self, design_id: str, color_id: int) -> list[dict]:
        """
        Find all locations where a specific element (design_id + color_id) is stored.
        Excludes put-away bin.

        Returns: list of dicts with container_id, drawer_id, drawer_name, container_name, color_name, quantity
        """
        # Get put-away bin container_id
        put_away_bin = self._one(
            """
            SELECT c.id AS container_id
            FROM containers c
            JOIN drawers d ON d.id = c.drawer_id
            WHERE c.is_put_away_bin = 1 
              AND c.deleted_at IS NULL 
              AND d.deleted_at IS NULL
            LIMIT 1
            """,
            [],
        )
        put_away_container_id = put_away_bin.get("container_id") if put_away_bin else None

        if put_away_container_id is not None:
            return self._all(
                """
                SELECT 
                    c.id AS container_id,
                    d.id AS drawer_id,
                    d.name AS drawer_name,
                    c.name AS container_name,
                    col.name AS color_name,
                    SUM(i.quantity) AS quantity
                FROM inventory i
                JOIN colors col ON col.id = i.color_id
                LEFT JOIN containers c ON c.id = i.container_id
                LEFT JOIN drawers d ON d.id = c.drawer_id
                WHERE i.design_id = ? 
                  AND i.color_id = ?
                  AND i.status = 'loose'
                  AND (i.container_id IS NULL OR i.container_id != ?)
                  AND (c.deleted_at IS NULL OR c.id IS NULL)
                  AND (d.deleted_at IS NULL OR d.id IS NULL)
                GROUP BY c.id, d.id, d.name, c.name, col.name
                ORDER BY quantity DESC, d.name, c.name
                """,
                [design_id, color_id, put_away_container_id],
            )
        else:
            return self._all(
                """
                SELECT 
                    c.id AS container_id,
                    d.id AS drawer_id,
                    d.name AS drawer_name,
                    c.name AS container_name,
                    col.name AS color_name,
                    SUM(i.quantity) AS quantity
                FROM inventory i
                JOIN colors col ON col.id = i.color_id
                LEFT JOIN containers c ON c.id = i.container_id
                LEFT JOIN drawers d ON d.id = c.drawer_id
                WHERE i.design_id = ? 
                  AND i.color_id = ?
                  AND i.status = 'loose'
                  AND (c.deleted_at IS NULL OR c.id IS NULL)
                  AND (d.deleted_at IS NULL OR d.id IS NULL)
                GROUP BY c.id, d.id, d.name, c.name, col.name
                ORDER BY quantity DESC, d.name, c.name
                """,
                [design_id, color_id],
            )

    def find_part_location(self, design_id: str) -> list[dict]:
        """
        Find all locations where a specific part (any color) is stored.
        Excludes put-away bin.

        Returns: list of dicts with container_id, drawer_id, drawer_name, container_name,
                 color_count, total_quantity
        """
        # Get put-away bin container_id
        put_away_bin = self._one(
            """
            SELECT c.id AS container_id
            FROM containers c
            JOIN drawers d ON d.id = c.drawer_id
            WHERE c.is_put_away_bin = 1 
              AND c.deleted_at IS NULL 
              AND d.deleted_at IS NULL
            LIMIT 1
            """,
            [],
        )
        put_away_container_id = put_away_bin.get("container_id") if put_away_bin else None

        if put_away_container_id is not None:
            return self._all(
                """
                SELECT 
                    c.id AS container_id,
                    d.id AS drawer_id,
                    d.name AS drawer_name,
                    c.name AS container_name,
                    COUNT(DISTINCT i.color_id) AS color_count,
                    SUM(i.quantity) AS total_quantity
                FROM inventory i
                LEFT JOIN containers c ON c.id = i.container_id
                LEFT JOIN drawers d ON d.id = c.drawer_id
                WHERE i.design_id = ? 
                  AND i.status = 'loose'
                  AND (i.container_id IS NULL OR i.container_id != ?)
                  AND (c.deleted_at IS NULL OR c.id IS NULL)
                  AND (d.deleted_at IS NULL OR d.id IS NULL)
                GROUP BY c.id, d.id, d.name, c.name
                ORDER BY total_quantity DESC, d.name, c.name
                """,
                [design_id, put_away_container_id],
            )
        else:
            return self._all(
                """
                SELECT 
                    c.id AS container_id,
                    d.id AS drawer_id,
                    d.name AS drawer_name,
                    c.name AS container_name,
                    COUNT(DISTINCT i.color_id) AS color_count,
                    SUM(i.quantity) AS total_quantity
                FROM inventory i
                LEFT JOIN containers c ON c.id = i.container_id
                LEFT JOIN drawers d ON d.id = c.drawer_id
                WHERE i.design_id = ? 
                  AND i.status = 'loose'
                  AND (c.deleted_at IS NULL OR c.id IS NULL)
                  AND (d.deleted_at IS NULL OR d.id IS NULL)
                GROUP BY c.id, d.id, d.name, c.name
                ORDER BY total_quantity DESC, d.name, c.name
                """,
                [design_id],
            )

    def find_category_location(self, part_category_id: int) -> list[dict]:
        """
        Find all locations where parts from a specific category are stored.
        Excludes put-away bin.

        Returns: list of dicts with container_id, drawer_id, drawer_name, container_name,
                 part_count, element_count, total_quantity
        """
        # Get put-away bin container_id
        put_away_bin = self._one(
            """
            SELECT c.id AS container_id
            FROM containers c
            JOIN drawers d ON d.id = c.drawer_id
            WHERE c.is_put_away_bin = 1 
              AND c.deleted_at IS NULL 
              AND d.deleted_at IS NULL
            LIMIT 1
            """,
            [],
        )
        put_away_container_id = put_away_bin.get("container_id") if put_away_bin else None

        if put_away_container_id is not None:
            return self._all(
                """
                SELECT 
                    c.id AS container_id,
                    d.id AS drawer_id,
                    d.name AS drawer_name,
                    c.name AS container_name,
                    COUNT(DISTINCT i.design_id) AS part_count,
                    COUNT(DISTINCT i.design_id || ':' || i.color_id) AS element_count,
                    SUM(i.quantity) AS total_quantity
                FROM inventory i
                JOIN parts p ON p.design_id = i.design_id
                LEFT JOIN containers c ON c.id = i.container_id
                LEFT JOIN drawers d ON d.id = c.drawer_id
                WHERE p.part_category_id = ?
                  AND i.status = 'loose'
                  AND (i.container_id IS NULL OR i.container_id != ?)
                  AND (c.deleted_at IS NULL OR c.id IS NULL)
                  AND (d.deleted_at IS NULL OR d.id IS NULL)
                GROUP BY c.id, d.id, d.name, c.name
                ORDER BY total_quantity DESC, d.name, c.name
                """,
                [part_category_id, put_away_container_id],
            )
        else:
            return self._all(
                """
                SELECT 
                    c.id AS container_id,
                    d.id AS drawer_id,
                    d.name AS drawer_name,
                    c.name AS container_name,
                    COUNT(DISTINCT i.design_id) AS part_count,
                    COUNT(DISTINCT i.design_id || ':' || i.color_id) AS element_count,
                    SUM(i.quantity) AS total_quantity
                FROM inventory i
                JOIN parts p ON p.design_id = i.design_id
                LEFT JOIN containers c ON c.id = i.container_id
                LEFT JOIN drawers d ON d.id = c.drawer_id
                WHERE p.part_category_id = ?
                  AND i.status = 'loose'
                  AND (c.deleted_at IS NULL OR c.id IS NULL)
                  AND (d.deleted_at IS NULL OR d.id IS NULL)
                GROUP BY c.id, d.id, d.name, c.name
                ORDER BY total_quantity DESC, d.name, c.name
                """,
                [part_category_id],
            )

    def analyze_element_storage_strategies(self) -> list[dict]:
        """
        Analyze how each element (design_id + color_id) is stored based on container/drawer naming patterns.
        
        Categorizes storage strategies:
        - 'by_element': Container name contains part number AND color description
        - 'by_part': Container name contains part number but NO color description
        - 'by_category_size': Drawer is "Really Useful" AND container has size description (large/small)
        - 'by_category': Drawer is "Really Useful" AND container has NO size description
        - 'unknown': Doesn't match any pattern
        
        Returns: list of dicts with design_id, color_id, part_name, color_name, storage_strategy,
                 drawer_name, container_name, quantity, and evidence (why it was categorized this way)
        """
        # Get all unique elements (design_id + color_id) with their primary location
        # For elements in multiple locations, we'll use the location with the highest quantity
        # This includes ALL loose elements, not just those in containers
        elements = self._all(
            """
            WITH all_elements AS (
                -- Get all unique loose elements, excluding parts marked to ignore in inventory
                SELECT DISTINCT
                    i.design_id,
                    i.color_id
                FROM inventory i
                JOIN parts p ON p.design_id = i.design_id
                WHERE i.status = 'loose'
                  AND COALESCE(p.ignore_in_inventory, 0) = 0
            ),
            element_locations AS (
                SELECT 
                    i.design_id,
                    i.color_id,
                    p.name AS part_name,
                    p.part_img_url,
                    p.part_category_id,
                    pc.name AS part_category_name,
                    col.name AS color_name,
                    col.hex AS color_hex,
                    d.id AS drawer_id,
                    d.name AS drawer_name,
                    c.id AS container_id,
                    c.name AS container_name,
                    c.is_put_away_bin,
                    SUM(i.quantity) AS quantity,
                    ROW_NUMBER() OVER (
                        PARTITION BY i.design_id, i.color_id 
                        ORDER BY 
                            CASE WHEN c.is_put_away_bin = 1 THEN 1 ELSE 0 END,  -- Put-away bin last
                            CASE WHEN c.deleted_at IS NOT NULL OR d.deleted_at IS NOT NULL THEN 1 ELSE 0 END,  -- Deleted last
                            CASE WHEN i.container_id IS NULL THEN 1 ELSE 0 END,  -- Unassigned last
                            SUM(i.quantity) DESC,  -- Highest quantity first
                            d.name, c.name
                    ) AS rn
                FROM inventory i
                JOIN parts p ON p.design_id = i.design_id
                JOIN colors col ON col.id = i.color_id
                LEFT JOIN part_categories pc ON pc.id = p.part_category_id
                LEFT JOIN containers c ON c.id = i.container_id
                LEFT JOIN drawers d ON d.id = c.drawer_id
                WHERE i.status = 'loose'
                  AND COALESCE(p.ignore_in_inventory, 0) = 0
                GROUP BY i.design_id, i.color_id, d.id, d.name, c.id, c.name, p.name, p.part_img_url, p.part_category_id, pc.name, col.name, col.hex, c.is_put_away_bin, c.deleted_at, d.deleted_at, i.container_id
            ),
            putaway_only_check AS (
                -- Check if element is ONLY in putaway bin (no other locations)
                SELECT 
                    i.design_id,
                    i.color_id,
                    CASE WHEN COUNT(CASE WHEN c.is_put_away_bin = 0 OR c.is_put_away_bin IS NULL THEN 1 END) = 0 
                         AND COUNT(CASE WHEN c.is_put_away_bin = 1 THEN 1 END) > 0
                         THEN 1 ELSE 0 END AS is_only_in_putaway
                FROM inventory i
                JOIN parts p ON p.design_id = i.design_id
                LEFT JOIN containers c ON c.id = i.container_id
                WHERE i.status = 'loose'
                  AND COALESCE(p.ignore_in_inventory, 0) = 0
                GROUP BY i.design_id, i.color_id
            ),
            putaway_locations AS (
                -- Get putaway bin location for elements that are only in putaway bin
                SELECT 
                    i.design_id,
                    i.color_id,
                    d.id AS drawer_id,
                    d.name AS drawer_name,
                    c.id AS container_id,
                    c.name AS container_name,
                    SUM(i.quantity) AS quantity
                FROM inventory i
                JOIN parts p ON p.design_id = i.design_id
                JOIN containers c ON c.id = i.container_id
                LEFT JOIN drawers d ON d.id = c.drawer_id
                WHERE i.status = 'loose'
                  AND c.is_put_away_bin = 1
                  AND COALESCE(p.ignore_in_inventory, 0) = 0
                GROUP BY i.design_id, i.color_id, d.id, d.name, c.id, c.name
            )
            SELECT 
                ae.design_id,
                ae.color_id,
                COALESCE(el.part_name, p.name) AS part_name,
                COALESCE(el.part_img_url, p.part_img_url) AS part_img_url,
                COALESCE(el.part_category_id, p.part_category_id) AS part_category_id,
                COALESCE(el.part_category_name, pc.name) AS part_category_name,
                COALESCE(el.color_name, col.name) AS color_name,
                COALESCE(el.color_hex, col.hex) AS color_hex,
                COALESCE(el.drawer_id, pl.drawer_id) AS drawer_id,
                COALESCE(el.drawer_name, pl.drawer_name) AS drawer_name,
                COALESCE(el.container_id, pl.container_id) AS container_id,
                COALESCE(el.container_name, pl.container_name) AS container_name,
                COALESCE(el.quantity, pl.quantity, 0) AS quantity,
                COALESCE(poc.is_only_in_putaway, 0) AS is_only_in_putaway
            FROM all_elements ae
            JOIN parts p ON p.design_id = ae.design_id
            JOIN colors col ON col.id = ae.color_id
            LEFT JOIN part_categories pc ON pc.id = p.part_category_id
            LEFT JOIN element_locations el ON el.design_id = ae.design_id 
                AND el.color_id = ae.color_id 
                AND el.rn = 1
                AND (el.is_put_away_bin = 0 OR el.is_put_away_bin IS NULL)  -- Exclude putaway bin from strategy determination
            LEFT JOIN putaway_only_check poc ON poc.design_id = ae.design_id 
                AND poc.color_id = ae.color_id
            LEFT JOIN putaway_locations pl ON pl.design_id = ae.design_id 
                AND pl.color_id = ae.color_id
            ORDER BY ae.design_id, ae.color_id
            """,
            [],
        )
        
        # Common color descriptions to look for in container names
        color_keywords = [
            'white', 'black', 'red', 'blue', 'green', 'yellow', 'orange', 'purple', 'pink',
            'brown', 'tan', 'gray', 'grey', 'trans', 'clear', 'bright', 'dark', 'light',
            'sand', 'lime', 'olive', 'dark', 'medium', 'light', 'transparent'
        ]
        
        # Size keywords - check for both standalone and in parentheses
        size_keywords = ['large', 'small', 'big', 'tiny']
        size_in_parens = ['(large)', '(small)', '(big)', '(tiny)']
        
        # Get all part aliases for matching
        # This includes both BrickLink/Instabrick aliases AND alternate Rebrickable part IDs
        all_aliases = self._all(
            """
            SELECT alias, design_id
            FROM part_aliases
            """,
            [],
        )
        # Build a map: design_id -> list of aliases (including itself)
        # Also build reverse map: alias -> list of design_ids that use it
        alias_map: dict[str, list[str]] = {}
        alias_to_design_ids: dict[str, list[str]] = {}  # Reverse map
        for alias_row in all_aliases:
            design_id = alias_row['design_id']
            alias = alias_row['alias']
            if design_id not in alias_map:
                alias_map[design_id] = [design_id]  # Include the design_id itself
            alias_map[design_id].append(alias.lower())
            # Build reverse map
            alias_lower = alias.lower()
            if alias_lower not in alias_to_design_ids:
                alias_to_design_ids[alias_lower] = []
            if design_id not in alias_to_design_ids[alias_lower]:
                alias_to_design_ids[alias_lower].append(design_id)
        
        # Build a map of valid design_ids (for checking if container part is a valid part)
        valid_design_ids = self._all(
            """
            SELECT design_id FROM parts
            """,
            [],
        )
        valid_design_id_set = {row['design_id'].lower() for row in valid_design_ids}
        
        def normalize_part_id(part_id: str) -> str:
            """Normalize part ID by removing trailing letters (e.g., '2412a' -> '2412')."""
            # Remove trailing letters
            return re.sub(r'[a-z]+$', '', part_id.lower(), flags=re.IGNORECASE)
        
        def extract_part_numbers_from_container(container_name: str) -> list[str]:
            """Extract potential part numbers from container name.
            
            Looks for:
            - Numbers in parentheses: (2431) -> 2431, (3003 Bright) -> 3003
            - Standalone numbers/part IDs as word boundaries
            """
            container_lower = container_name.lower()
            part_numbers = []
            
            # Extract numbers in parentheses: (2431) or (2431a) or (3003 Bright)
            # First try exact match: (2431)
            paren_matches = re.findall(r'\(([a-z0-9]+)\)', container_lower)
            part_numbers.extend(paren_matches)
            
            # Also extract first alphanumeric sequence from parentheses: (3003 Bright) -> 3003
            # This handles cases where there's text after the part number in parentheses
            paren_with_text = re.findall(r'\(([a-z0-9]+)\s+', container_lower)
            for match in paren_with_text:
                if match not in part_numbers:
                    part_numbers.append(match)
            
            # Extract standalone part-like sequences (alphanumeric, 2+ chars) as word boundaries
            word_boundary_matches = re.findall(r'\b([a-z0-9]{3,})\b', container_lower)
            for match in word_boundary_matches:
                # Filter out common words
                if match not in ['row', 'bin', 'col', 'the', 'and', 'or', 'for', 'with', 'bright', 'dark', 'light']:
                    part_numbers.append(match)
            
            return part_numbers
        
        def matches_part_number(container_name: str, design_id: str) -> bool:
            """Check if container name contains the part number or any variation/alias."""
            container_lower = container_name.lower()
            design_id_lower = design_id.lower()
            
            # Direct match - part ID in container name
            if design_id_lower in container_lower:
                return True
            
            # Extract potential part numbers from container name (e.g., from parentheses)
            container_part_numbers = extract_part_numbers_from_container(container_name)
            
            # Check if any extracted part number matches the design ID or is a prefix
            for container_part in container_part_numbers:
                container_part_lower = container_part.lower()
                
                # Exact match
                if container_part_lower == design_id_lower:
                    return True
                
                # Prefix match - container part is a prefix of part ID (e.g., "2431" matches "2431pr0077")
                if design_id_lower.startswith(container_part_lower):
                    # Make sure it's a meaningful match (at least 2 chars)
                    if len(container_part_lower) >= 2:
                        return True
            
                # Reverse prefix match - part ID (normalized) is a prefix of container part
                normalized_design_id = normalize_part_id(design_id)
                if normalized_design_id and container_part_lower.startswith(normalized_design_id):
                    if len(normalized_design_id) >= 2:
                        return True
            
            # Normalized match (e.g., "2412a" matches "2412")
            normalized_design_id = normalize_part_id(design_id)
            if normalized_design_id:
                # Check if normalized ID appears in container name as word boundary
                pattern = r'\b' + re.escape(normalized_design_id) + r'\b'
                if re.search(pattern, container_lower):
                    return True
                
                # Check extracted part numbers
                for container_part in container_part_numbers:
                    if normalized_design_id == container_part.lower():
                        return True
            
            # Check aliases - also check reverse (container part might be an alias of design_id)
            # First, check if any extracted container part number is an alias of the design_id
            for container_part in container_part_numbers:
                container_part_lower = container_part.lower()
                # Check if this container part is an alias of the design_id
                if design_id in alias_map:
                    for alias in alias_map[design_id]:
                        if alias.lower() == container_part_lower:
                            return True
                        # Also check normalized versions
                        normalized_alias = normalize_part_id(alias)
                        if normalized_alias == container_part_lower:
                            return True
                # Also check if container part is a prefix of any alias
                if design_id in alias_map:
                    for alias in alias_map[design_id]:
                        alias_lower = alias.lower()
                        if alias_lower.startswith(container_part_lower):
                            if len(container_part_lower) >= 2:
                                return True
                
                # Also check reverse: if container_part is an alias, check if design_id uses that alias
                # This handles cases where container has "3003" and element is "6223", and 3003 is an alias of 6223
                if container_part_lower in alias_to_design_ids:
                    # Container part is an alias - check if element's design_id is one of the design_ids that use this alias
                    for mapped_design_id in alias_to_design_ids[container_part_lower]:
                        if mapped_design_id.lower() == design_id_lower:
                            return True
                        # Check normalized
                        normalized_container = normalize_part_id(container_part)
                        normalized_element = normalize_part_id(design_id)
                        if normalized_container and normalized_element and normalized_container == normalized_element:
                            return True
                
                # Also check if container_part itself is a design_id that has design_id as an alias
                # This handles: container has design_id "3003", element is "6223", and 6223 is an alias of 3003
                if container_part_lower in alias_map:
                    for alias_of_container in alias_map[container_part_lower]:
                        if alias_of_container.lower() == design_id_lower:
                            return True
                
                # Check if container_part is a valid design_id that shares BrickLink ID with element's design_id
                # This handles cases where both parts share the same BrickLink ID (e.g., 3003 and 6223 both have BrickLink ID "3003")
                # Since we can't store multiple mappings for the same alias, we use a heuristic:
                # If container_part is a valid design_id AND it's stored as an alias mapping to itself (e.g., "3003" -> "3003"),
                # this indicates it's a BrickLink ID. We then check if the element's design_id might also share this alias
                # by checking if the container_part's design_id has the container_part as an alias (self-reference).
                # This is a heuristic that works for common cases where BrickLink IDs are numeric and match design_ids.
                if container_part_lower in valid_design_id_set:
                    # Container part is a valid design_id (e.g., "3003")
                    # Check if the container_part itself is stored as an alias (e.g., "3003" -> "3003")
                    if container_part_lower in alias_to_design_ids:
                        # Container part number is stored as an alias - check if it maps to itself
                        mapped_design_ids = alias_to_design_ids[container_part_lower]
                        if container_part_lower in [d.lower() for d in mapped_design_ids]:
                            # Container part has itself as an alias (e.g., 3003 -> 3003)
                            # This indicates it's a BrickLink ID. Since both 3003 and 6223 share BrickLink ID "3003"
                            # but we can only store one mapping, we need to check if element 6223 should also match.
                            # We can't verify this from the DB alone, but we can use a heuristic:
                            # If the container_part is a valid design_id with self-referential alias (BrickLink ID pattern),
                            # and the element is a different design_id, check if they might share this alias by
                            # checking if the element's design_id has any aliases that are also valid design_ids
                            # that have the same self-referential pattern. But that's complex.
                            # Simpler: if container_part is numeric (common BrickLink ID pattern) and is a valid design_id
                            # with self-referential alias, and element is different, allow match as a heuristic.
                            # This is a reasonable assumption for common BrickLink IDs.
                            if container_part_lower != design_id_lower:
                                # They're different parts - check if container_part looks like a BrickLink ID (numeric, 3-4 digits)
                                if container_part_lower.isdigit() and 3 <= len(container_part_lower) <= 4:
                                    # Heuristic: allow match for shared BrickLink IDs
                                    # This handles the case where both 3003 and 6223 share BrickLink ID "3003"
                                    return True
            
            # Check aliases - design_id aliases in container
            if design_id in alias_map:
                for alias in alias_map[design_id]:
                    alias_lower = alias.lower()
                    # Direct match
                    if alias_lower in container_lower:
                        return True
                    # Check against extracted part numbers
                    for container_part in container_part_numbers:
                        if alias_lower == container_part.lower():
                            return True
                        # Prefix match
                        if alias_lower.startswith(container_part.lower()):
                            if len(container_part) >= 2:
                                return True
                    # Normalized alias match
                    normalized_alias = normalize_part_id(alias)
                    if normalized_alias:
                        pattern = r'\b' + re.escape(normalized_alias) + r'\b'
                        if re.search(pattern, container_lower):
                            return True
                        for container_part in container_part_numbers:
                            if normalized_alias == container_part.lower():
                                return True
            
            return False
        
        result = []
        for elem in elements:
            design_id = elem['design_id']
            is_only_in_putaway = elem.get('is_only_in_putaway', 0) == 1
            
            # If element is only in putaway bin, use putaway location for display
            # (we already have it from the putaway_locations CTE via COALESCE)
            container_name = (elem['container_name'] or '').lower()
            drawer_name = (elem['drawer_name'] or '').lower()
            
            # Check if element is unassigned (no container) or only in putaway bin
            if not elem['container_name']:
                if is_only_in_putaway:
                    storage_strategy = 'in_putaway_bin'
                    evidence = ['Element is only in the putaway bin (temporary storage)']
                else:
                    storage_strategy = 'unassigned'
                    evidence = ['Element is not assigned to any container']
            else:
                # Check if drawer is "Really Useful" - only check drawer name
                is_really_useful = 'really useful' in drawer_name
                
                # Check if container name contains part number (design_id or alias/variation)
                has_part_number = matches_part_number(container_name, design_id)
                
                # Check if container name contains color description
                has_color = any(keyword in container_name for keyword in color_keywords)
                
                # Check if container name contains size description
                # Check both standalone keywords and in parentheses, in both container and drawer names
                # Also check for category descriptions in parentheses that might indicate size (e.g., "Curved 1x1 Other")
                has_size = (
                    any(keyword in container_name for keyword in size_keywords) or
                    any(keyword in container_name for keyword in size_in_parens) or
                    any(keyword in drawer_name for keyword in size_keywords) or
                    any(keyword in drawer_name for keyword in size_in_parens) or
                    # Check for category descriptions in parentheses (e.g., "(Curved 1x1 Other)")
                    bool(re.search(r'\([^)]*(?:1x1|2x2|3x3|4x4|small|large|tiny|big)[^)]*\)', container_name, re.IGNORECASE))
                )
                
                # Check if container has category description in parentheses (e.g., "(Curved 1x1 Other)")
                # This indicates category-based storage even if not in Really Useful drawer
                has_category_description = bool(
                    re.search(r'\([^)]*(?:curved|clip|brick|tile|plate|slope|hinge|bracket|technic|other)[^)]*\)', 
                             container_name, re.IGNORECASE)
                )
                
                # Determine storage strategy
                storage_strategy = 'unknown'
                evidence = []
                
                if is_really_useful:
                    if has_size:
                        storage_strategy = 'by_category_size'
                        evidence.append(f"Drawer is 'Really Useful' and container has size description")
                    else:
                        storage_strategy = 'by_category'
                        evidence.append(f"Drawer is 'Really Useful' and container has no size description")
                elif has_category_description:
                    # Container has category description in parentheses - treat as category-based
                    if has_size:
                        storage_strategy = 'by_category_size'
                        evidence.append(f"Container has category description with size indicator in parentheses")
                    else:
                        storage_strategy = 'by_category'
                        evidence.append(f"Container has category description in parentheses")
                elif has_part_number:
                    if has_color:
                        storage_strategy = 'by_element'
                        evidence.append(f"Container name contains part number '{design_id}' and color description")
                    else:
                        storage_strategy = 'by_part'
                        evidence.append(f"Container name contains part number '{design_id}' but no color description")
                else:
                    storage_strategy = 'unknown'
                    evidence.append(f"Container name doesn't contain part number and drawer is not 'Really Useful'")
            
            result.append({
                'design_id': design_id,
                'color_id': elem['color_id'],
                'part_name': elem['part_name'],
                'part_img_url': elem.get('part_img_url'),
                'part_category_id': elem.get('part_category_id'),
                'part_category_name': elem.get('part_category_name'),
                'color_name': elem['color_name'],
                'color_hex': elem.get('color_hex'),
                'storage_strategy': storage_strategy,
                'drawer_id': elem.get('drawer_id'),
                'drawer_name': elem['drawer_name'] or None,
                'container_id': elem.get('container_id'),
                'container_name': elem['container_name'] or None,
                'quantity': elem['quantity'],
                'evidence': '; '.join(evidence),
            })
        
        return result
