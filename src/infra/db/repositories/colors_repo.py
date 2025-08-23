from __future__ import annotations

from .base import BaseRepo


class ColorsRepo(BaseRepo):
    def resolve_color_alias(self, bl_id: int) -> int | None:
        row = self._one(
            """
            SELECT color_id
            FROM color_aliases
            WHERE alias_id = ?
            """,
            [bl_id],
        )
        if not row:
            return None
        # sqlite3.Row or dict
        return row["color_id"]

    # Optional helpers (handy later / tests)
    def get_color(self, color_id: int) -> dict | None:
        return self._one(
            """
            SELECT id, name, hex, r, g, b
            FROM colors
            WHERE id = ?
            """,
            [color_id],
        )

    def list_colors(self) -> list[dict]:
        return self._all(
            """
            SELECT id, name, hex, r, g, b
            FROM colors
            ORDER BY id
            """
        )
