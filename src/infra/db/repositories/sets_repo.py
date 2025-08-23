from __future__ import annotations

from collections.abc import Iterable

from .base import BaseRepo


class SetsRepo(BaseRepo):
    def get_set(self, set_id: int) -> dict | None:
        return self._one(
            """
            SELECT s.id,
                   s.set_number,
                   s.name,
                   s.status,
                   s.theme_id,
                   s.year
            FROM sets s
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
                sp.part_id,
                p.name AS part_name,
                sp.color_id,
                c.name AS color_name,
                c.hex  AS hex,
                sp.quantity,
                sp.is_spare
            FROM set_parts sp
            JOIN parts  p ON p.id = sp.part_id
            JOIN colors c ON c.id = sp.color_id
            WHERE sp.set_id = ?
            ORDER BY p.name COLLATE NOCASE, sp.color_id
            """,
            [set_id],
        )

    def get_set_by_num(self, set_num: str) -> dict | None:
        return self._one(
            """
            SELECT set_num, name, year, theme, image_url, rebrickable_url, status, added_at
            FROM sets
            WHERE set_num = ?
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
                p.part_img_url
            FROM set_parts sp
            JOIN parts  p ON p.design_id = sp.design_id
            JOIN colors c ON c.id        = sp.color_id
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
        Columns: set_num, set_name, year, color_id, color_name, hex, quantity
        """
        return self._all(
            """
            SELECT s.set_num,
                   s.name        AS set_name,
                   s.year        AS year,
                   c.id          AS color_id,
                   c.name        AS color_name,
                   c.hex         AS hex,
                   sp.quantity   AS quantity
            FROM set_parts sp
            JOIN sets  s ON s.set_num = sp.set_num
            JOIN colors c ON c.id     = sp.color_id
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
