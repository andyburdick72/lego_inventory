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
