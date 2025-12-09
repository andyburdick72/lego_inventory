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
            SELECT p.design_id, p.name, p.part_url, p.part_img_url,
                   p.part_category_id, p.ignore_in_inventory,
                   pc.name AS part_category_name
            FROM parts p
            LEFT JOIN part_categories pc ON pc.id = p.part_category_id
            WHERE p.design_id = ?
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

    def get_part_aliases(self, design_id: str) -> list[dict]:
        """Get all aliases for a part."""
        return self._all(
            """
            SELECT alias
            FROM part_aliases
            WHERE design_id = ?
            ORDER BY alias
            """,
            [design_id],
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

    def update_part(self, design_id: str, **fields) -> None:
        """Update part fields."""
        if not fields:
            return
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values())
        values.append(design_id)
        self.conn.execute(
            f"UPDATE parts SET {set_clause} WHERE design_id = ?",
            values,
        )
        self.conn.commit()
