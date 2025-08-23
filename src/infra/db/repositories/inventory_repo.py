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
