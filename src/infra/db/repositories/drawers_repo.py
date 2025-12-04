from __future__ import annotations

from .base import BaseRepo


# Local duplicate error to avoid circular import during module import.
# Server maps DB constraint violations separately; this signals duplicates when
# calling the repository directly.
class DuplicateLabelError(Exception):
    pass


class DrawersRepo(BaseRepo):
    def get_drawer(self, drawer_id: int) -> dict | None:
        return self._one(
            """
            SELECT d.id, d.name, d.description
            FROM drawers d
            WHERE d.id = ?
            """,
            [drawer_id],
        )

    def list_drawers(self) -> list[dict]:
        return self._all(
            """
            SELECT d.id, d.name, d.description
            FROM drawers d
            ORDER BY d.name COLLATE NOCASE
            """
        )

    def list_containers(self, drawer_id: int) -> list[dict]:
        return self._all(
            """
            SELECT c.id,
                   c.drawer_id,
                   c.name AS label,
                   CASE WHEN c.deleted_at IS NULL THEN 0 ELSE 1 END AS deleted
            FROM containers c
            WHERE c.drawer_id = ?
            ORDER BY c.name COLLATE NOCASE
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

    # ----------------------------
    # Write operations: Drawers
    # ----------------------------
    def create_drawer(
        self, *, name: str, description: str | None = None, rows: int | None = None, cols: int | None = None
    ) -> int:
        # Check for active drawer with same name
        active_dup = self._one(
            """
            SELECT 1
            FROM drawers
            WHERE name = ? COLLATE NOCASE
            AND deleted_at IS NULL
            """,
            [name],
        )
        if active_dup:
            raise DuplicateLabelError(f"Drawer '{name}' already exists")

        # Check for soft-deleted drawer with same name - restore it instead of creating new
        soft_deleted = self._one(
            """
            SELECT id
            FROM drawers
            WHERE name = ? COLLATE NOCASE
            AND deleted_at IS NOT NULL
            """,
            [name],
        )
        if soft_deleted:
            drawer_id = soft_deleted["id"] if isinstance(soft_deleted, dict) else soft_deleted[0]
            # Restore the soft-deleted drawer with new values
            self._one(
                """
                UPDATE drawers
                SET deleted_at = NULL,
                    description = ?,
                    rows = ?,
                    cols = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                [description, rows, cols, drawer_id],
            )
            return int(drawer_id)

        # No existing drawer (active or deleted) - create new one
        row = self._one(
            """
            INSERT INTO drawers (name, description, rows, cols)
            VALUES (?, ?, ?, ?)
            RETURNING id
            """,
            [name, description, rows, cols],
        )
        if row is None:
            raise RuntimeError("Failed to create drawer: no ID returned")
        return int(row["id"] if isinstance(row, dict) else row[0])

    def rename_drawer(self, *, drawer_id: int, new_name: str) -> None:
        dup = self._one(
            """
            SELECT 1
            FROM drawers
            WHERE name = ? COLLATE NOCASE
            AND deleted_at IS NULL
            """,
            [new_name],
        )
        if dup:
            raise DuplicateLabelError(f"Drawer '{new_name}' already exists")

        self._one(
            """
            UPDATE drawers
            SET name = ?
            WHERE id = ?
            """,
            [new_name, drawer_id],
        )

    def update_drawer(
        self,
        *,
        drawer_id: int,
        new_name: str,
        description: Optional[str] = None,
        rows: Optional[int] = None,
        cols: Optional[int] = None,
    ) -> None:
        """Update drawer name, description, rows, and cols."""
        dup = self._one(
            """
            SELECT 1
            FROM drawers
            WHERE name = ? COLLATE NOCASE
            AND deleted_at IS NULL
            AND id != ?
            """,
            [new_name, drawer_id],
        )
        if dup:
            raise DuplicateLabelError(f"Drawer '{new_name}' already exists")

        self._one(
            """
            UPDATE drawers
            SET name = ?, description = ?, rows = ?, cols = ?
            WHERE id = ?
            """,
            [new_name, description, rows, cols, drawer_id],
        )

    def move_drawer(self, *, drawer_id: int, new_sort_index: int | None) -> None:
        self._one(
            """
            UPDATE drawers
            SET sort_index = ?
            WHERE id = ?
            """,
            [new_sort_index, drawer_id],
        )

    def delete_drawer(self, *, drawer_id: int) -> None:
        self._one(
            """
            UPDATE drawers
            SET deleted_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            [drawer_id],
        )

    # ----------------------------
    # Write operations: Containers
    # ----------------------------
    def create_container(
        self,
        *,
        drawer_id: int,
        name: str,
        description: str | None = None,
        row_index: int | None = None,
        col_index: int | None = None,
        sort_index: int | None = None,
    ) -> int:
        dup = self._one(
            """
            SELECT 1
            FROM containers
            WHERE drawer_id = ?
            AND name = ? COLLATE NOCASE
            AND deleted_at IS NULL
            """,
            [drawer_id, name],
        )
        if dup:
            raise DuplicateLabelError(f"Container '{name}' already exists in this drawer")

        row = self._one(
            """
            INSERT INTO containers (drawer_id, name, description, row_index, col_index, sort_index)
            VALUES (?, ?, ?, ?, ?, ?)
            RETURNING id
            """,
            [drawer_id, name, description, row_index, col_index, sort_index],
        )
        if row is None:
            raise RuntimeError("Failed to create container: no ID returned")
        return int(row["id"] if isinstance(row, dict) else row[0])

    def rename_container(self, *, container_id: int, new_name: str) -> None:
        row = self._one(
            """
            SELECT drawer_id
            FROM containers
            WHERE id = ?
            """,
            [container_id],
        )
        if not row:
            return
        drawer_id = row["drawer_id"] if isinstance(row, dict) else row[0]

        dup = self._one(
            """
            SELECT 1
            FROM containers
            WHERE drawer_id = ?
            AND name = ? COLLATE NOCASE
            AND deleted_at IS NULL
            """,
            [drawer_id, new_name],
        )
        if dup:
            raise DuplicateLabelError(f"Container '{new_name}' already exists in this drawer")

        self._one(
            """
            UPDATE containers
            SET name = ?
            WHERE id = ?
            """,
            [new_name, container_id],
        )

    def move_container(
        self,
        *,
        container_id: int,
        new_drawer_id: int | None = None,
        row_index: int | None = None,
        col_index: int | None = None,
        sort_index: int | None = None,
    ) -> None:
        fields = []
        params: list[object] = []
        if new_drawer_id is not None:
            fields.append("drawer_id = ?")
            params.append(new_drawer_id)
        if row_index is not None:
            fields.append("row_index = ?")
            params.append(row_index)
        if col_index is not None:
            fields.append("col_index = ?")
            params.append(col_index)
        if sort_index is not None:
            fields.append("sort_index = ?")
            params.append(sort_index)
        if not fields:
            return
        params.append(container_id)

        self._one(
            f"""
            UPDATE containers
            SET {', '.join(fields)}
            WHERE id = ?
            """,
            params,
        )

    def delete_container(self, *, container_id: int) -> None:
        self._one(
            """
            UPDATE containers
            SET deleted_at = CURRENT_TIMESTAMP,
                row_index  = NULL,
                col_index  = NULL,
                sort_index = NULL
            WHERE id = ?
            """,
            [container_id],
        )
