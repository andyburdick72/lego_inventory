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
        Return only 'loose' inventory rows for a given design_id,
        matching the legacy shape used by inventory_db.loose_inventory_for_part.
        Columns: color_name, hex, color_id, quantity, drawer, container
        """
        return self._all(
            """
            SELECT c.name AS color_name, c.hex,
                i.color_id, i.quantity,
                i.drawer, i.container
            FROM inventory i
            JOIN colors c ON c.id = i.color_id
            WHERE i.design_id = ? AND i.status = 'loose'
            ORDER BY i.drawer, i.container, i.color_id
            """,
            [design_id],
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
