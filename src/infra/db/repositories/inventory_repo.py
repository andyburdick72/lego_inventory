from __future__ import annotations

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

    def get_inventory_totals_by_location(
        self, design_id: str, color_id: int
    ) -> list[dict]:
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

    def update_inventory_location(
        self, inventory_id: int, container_id: int | None
    ) -> None:
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
            
            result.append({
                **elem,
                "locations": locations,
            })
        
        return result
