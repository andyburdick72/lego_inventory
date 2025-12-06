from __future__ import annotations

from collections.abc import Iterable

from .base import BaseRepo


class SetsRepo(BaseRepo):
    def get_set(self, set_id: int) -> dict | None:
        return self._one(
            """
            SELECT s.id,
                   s.set_num,
                   s.name,
                   s.status,
                   s.theme_id,
                   s.year,
                   s.image_url,
                   s.rebrickable_url,
                   s.added_at,
                   t.name AS theme_name
            FROM sets s
            LEFT JOIN themes t ON t.id = s.theme_id
            WHERE s.id = ?
            """,
            [set_id],
        )

    def iter_parts_by_set(self, set_id: int) -> Iterable[dict]:
        """
        Yield all parts belonging to a set.
        Returned shape matches current parts-by-set usage.
        """
        return self._iter(
            """
            SELECT
                p.design_id,
                p.name AS part_name,
                sp.color_id,
                c.name AS color_name,
                c.hex  AS hex,
                sp.quantity
            FROM sets s
            JOIN set_parts sp ON sp.set_num = s.set_num
            JOIN parts  p     ON p.design_id = sp.design_id
            JOIN colors c     ON c.id        = sp.color_id
            WHERE s.id = ?
            ORDER BY p.name COLLATE NOCASE, sp.color_id
            """,
            [set_id],
        )

    def get_set_by_num(self, set_num: str) -> dict | None:
        return self._one(
            """
            SELECT s.set_num, s.name, s.year, s.theme_id, s.image_url, s.rebrickable_url, s.status, s.added_at,
                   t.name AS theme_name
            FROM sets s
            LEFT JOIN themes t ON t.id = s.theme_id
            WHERE s.set_num = ?
            """,
            [set_num],
        )

    def list_parts_for_set(self, set_num: str) -> list[dict]:
        return self._all(
            """
            SELECT sp.design_id,
                p.name,
                sp.color_id,
                c.name AS color_name,
                c.hex  AS hex,
                sp.quantity,
                p.part_url,
                p.part_img_url,
                p.part_category_id,
                pc.name AS part_category_name
            FROM set_parts sp
            JOIN parts  p ON p.design_id = sp.design_id
            JOIN colors c ON c.id        = sp.color_id
            LEFT JOIN part_categories pc ON pc.id = p.part_category_id
            WHERE sp.set_num = ?
            ORDER BY sp.design_id, sp.color_id
            """,
            [set_num],
        )

    def get_set_parts_basic(self, set_num: str) -> list[dict]:
        """
        Return parts for a set without URL metadata.
        Columns: set_num, design_id, name, color_id, color_name, hex, quantity
        """
        return self._all(
            """
            SELECT sp.set_num AS set_num,
                   sp.design_id,
                   p.name,
                   sp.color_id,
                   c.name AS color_name,
                   c.hex  AS hex,
                   sp.quantity
            FROM set_parts sp
            JOIN parts  p ON p.design_id = sp.design_id
            JOIN colors c ON c.id        = sp.color_id
            WHERE sp.set_num = ?
            ORDER BY sp.design_id, sp.color_id
            """,
            [set_num],
        )

    def sets_for_part(self, design_id: str) -> list[dict]:
        """
        Return sets that contain a given design_id.
        Columns: set_num, name, year, status, quantity
        """
        return self._all(
            """
            SELECT s.set_num,
                   s.name,
                   s.year,
                   s.status,
                   SUM(sp.quantity) AS quantity
            FROM set_parts sp
            JOIN sets s ON s.set_num = sp.set_num
            WHERE sp.design_id = ?
            GROUP BY s.set_num, s.name, s.year, s.status
            ORDER BY s.year DESC, s.set_num
            """,
            [design_id],
        )

    def sets_for_part_with_colors(self, design_id: str) -> list[dict]:
        """
        Return sets that contain a given design_id with per-color detail.
        Columns: set_num, set_name, year, status, color_id, color_name, hex, quantity, part_category_id, part_category_name
        """
        return self._all(
            """
            SELECT s.set_num,
                   s.name        AS set_name,
                   s.year        AS year,
                   s.status      AS status,
                   c.id          AS color_id,
                   c.name        AS color_name,
                   c.hex         AS hex,
                   sp.quantity   AS quantity,
                   p.part_category_id,
                   pc.name       AS part_category_name
            FROM set_parts sp
            JOIN sets  s ON s.set_num = sp.set_num
            JOIN colors c ON c.id     = sp.color_id
            JOIN parts p ON p.design_id = sp.design_id
            LEFT JOIN part_categories pc ON pc.id = p.part_category_id
            WHERE sp.design_id = ?
            ORDER BY s.year, s.set_num, c.id
            """,
            [design_id],
        )

    def set_total_for_statuses(self, statuses: list[str]) -> int:
        """
        Return total quantity of parts across sets whose status is in the given list.
        """
        if not statuses:
            return 0
        placeholders = ",".join(["?"] * len(statuses))
        row = self._one(
            f"""
            SELECT COALESCE(SUM(sp.quantity), 0) AS q
            FROM set_parts sp
            JOIN sets s ON s.set_num = sp.set_num
            WHERE s.status IN ({placeholders})
            """,
            statuses,
        )
        return int(row["q"]) if row and row["q"] is not None else 0

    def update_set_by_num(self, set_num: str, **fields) -> None:
        """
        Update a set by set_num with the provided fields.
        """
        if not fields:
            return
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values())
        values.append(set_num)
        self.conn.execute(
            f"UPDATE sets SET {set_clause} WHERE set_num = ?",
            values,
        )
        self.conn.commit()

    def list_sets_with_statuses(self, statuses: list[str]) -> list[dict]:
        """
        Return sets with status in the given list.
        Columns: set_num, name, year, theme, status, image_url, rebrickable_url
        """
        if not statuses:
            return []
        placeholders = ",".join(["?"] * len(statuses))
        return self._all(
            f"""
            SELECT set_num, name, year, theme, status, image_url, rebrickable_url
            FROM sets
            WHERE status IN ({placeholders})
            ORDER BY year DESC, set_num
            """,
            statuses,
        )
