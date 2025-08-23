from __future__ import annotations

from .base import BaseRepo


class PartsRepo(BaseRepo):
    def fetch_part_name(self, design_id: str) -> str | None:
        row = self._one(
            """
            SELECT name FROM parts WHERE design_id = ?
            """,
            [design_id],
        )
        if not row:
            return None
        # row may be sqlite3.Row or dict
        return row["name"] if row["name"] is not None else None

    def get_part(self, design_id: str) -> dict | None:
        return self._one(
            """
            SELECT design_id, name, part_url, part_img_url
            FROM parts
            WHERE design_id = ?
            """,
            [design_id],
        )

    def unknown_parts(self) -> list[dict]:
        return self._all(
            """
            SELECT design_id
            FROM parts
            WHERE name = 'Unknown part'
            ORDER BY design_id
            """
        )

    def resolve_part_alias(self, alias: str) -> dict | None:
        return self._one(
            """
            SELECT design_id
            FROM part_aliases
            WHERE alias = ?
            """,
            [alias],
        )
