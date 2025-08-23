from __future__ import annotations

from .base import BaseRepo


class DrawersRepo(BaseRepo):
    def get_drawer(self, drawer_id: int) -> dict | None:
        return self._one(
            """
            SELECT d.id, d.name, d.note
            FROM drawers d
            WHERE d.id = ?
            """,
            [drawer_id],
        )

    def list_drawers(self) -> list[dict]:
        return self._all(
            """
            SELECT d.id, d.name, d.note
            FROM drawers d
            ORDER BY d.name COLLATE NOCASE
            """
        )

    def list_containers(self, drawer_id: int) -> list[dict]:
        return self._all(
            """
            SELECT c.id, c.drawer_id, c.label, c.deleted
            FROM containers c
            WHERE c.drawer_id = ?
            ORDER BY c.label COLLATE NOCASE
            """,
            [drawer_id],
        )

    def list_drawers_with_counts(self) -> list[dict]:
        return self._all(
            """
            SELECT d.id,
                d.name,
                d.description,
                d.kind,
                d.cols,
                d.rows,
                d.sort_index,
                COUNT(DISTINCT c.id) AS container_count,
                COALESCE(SUM(i.quantity), 0) AS part_count
            FROM drawers d
            LEFT JOIN containers c ON c.drawer_id = d.id AND c.deleted_at IS NULL
            LEFT JOIN inventory  i ON i.container_id = c.id AND i.status='loose'
            WHERE (d.kind IS NULL OR d.kind NOT IN ('rub_box_legacy','rub_box_nested_error'))
            AND d.deleted_at IS NULL
            GROUP BY d.id
            ORDER BY d.sort_index, d.name
            """
        )

    def get_drawer_active(self, drawer_id: int) -> dict | None:
        return self._one(
            """
            SELECT *
            FROM drawers
            WHERE id = ? AND deleted_at IS NULL
            """,
            [drawer_id],
        )

    def list_containers_with_counts(self, drawer_id: int) -> list[dict]:
        return self._all(
            """
            SELECT c.id,
                c.name,
                c.description,
                c.row_index,
                c.col_index,
                c.sort_index,
                COALESCE(SUM(i.quantity), 0) AS part_count,
                COUNT(DISTINCT i.design_id || ':' || i.color_id) AS unique_parts
            FROM containers c
            JOIN drawers d ON d.id = c.drawer_id AND d.deleted_at IS NULL
            LEFT JOIN inventory i ON i.container_id = c.id AND i.status='loose'
            WHERE c.drawer_id = ? AND c.deleted_at IS NULL
            GROUP BY c.id
            ORDER BY c.row_index, c.col_index, c.sort_index, c.name
            """,
            [drawer_id],
        )

    def get_container_with_drawer(self, container_id: int) -> dict | None:
        return self._one(
            """
            SELECT c.*,
                   d.name AS drawer_name,
                   d.id   AS drawer_id
            FROM containers c
            JOIN drawers d ON d.id = c.drawer_id AND d.deleted_at IS NULL
            WHERE c.id = ? AND c.deleted_at IS NULL
            """,
            [container_id],
        )

    def iter_parts_in_container(self, container_id: int):
        return self._iter(
            """
            SELECT i.part_id,
                   p.name  AS part_name,
                   i.color_id,
                   i.quantity,
                   i.status,
                   i.location
            FROM inventory i
            JOIN parts p ON p.id = i.part_id
            WHERE i.container_id = ? AND i.status='loose'
            ORDER BY p.name COLLATE NOCASE, i.color_id
            """,
            [container_id],
        )

    def list_aggregated_parts_in_container(self, container_id: int) -> list[dict]:
        return self._all(
            """
            SELECT p.design_id,
                p.name AS part_name,
                col.id   AS color_id,
                col.name AS color_name,
                col.hex,
                SUM(i.quantity) AS qty
            FROM inventory i
            JOIN parts  p   ON p.design_id = i.design_id
            JOIN colors col ON col.id      = i.color_id
            WHERE i.container_id = ? AND i.status='loose'
            AND EXISTS (SELECT 1 FROM containers c2 WHERE c2.id = i.container_id AND c2.deleted_at IS NULL)
            GROUP BY p.design_id, col.id
            ORDER BY p.design_id, col.id
            """,
            [container_id],
        )
