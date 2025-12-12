from __future__ import annotations

from .base import BaseRepo


class SearchRepo(BaseRepo):
    """Repository for global search across all entities."""

    def search_parts(self, query: str, limit: int = 10) -> list[dict]:
        """Search parts by design_id, name, or category name."""
        like = f"%{query}%"
        return self._all(
            """
            SELECT DISTINCT
                p.design_id,
                p.name,
                p.part_url,
                p.part_img_url,
                p.part_category_id,
                pc.name AS part_category_name
            FROM parts p
            LEFT JOIN part_categories pc ON pc.id = p.part_category_id
            WHERE p.design_id LIKE ? 
               OR p.name LIKE ? 
               OR pc.name LIKE ?
            ORDER BY 
                CASE 
                    WHEN p.design_id = ? THEN 1
                    WHEN p.design_id LIKE ? THEN 2
                    WHEN p.name LIKE ? THEN 3
                    ELSE 4
                END,
                p.name COLLATE NOCASE
            LIMIT ?
            """,
            [like, like, like, query, f"{query}%", like, limit],
        )

    def search_sets(self, query: str, limit: int = 10) -> list[dict]:
        """Search sets by set_number, name, or theme name."""
        like = f"%{query}%"
        return self._all(
            """
            SELECT DISTINCT
                s.set_num AS set_number,
                s.name,
                s.year,
                s.theme_id,
                t.name AS theme_name,
                s.status,
                s.image_url,
                s.rebrickable_url
            FROM sets s
            LEFT JOIN themes t ON t.id = s.theme_id
            WHERE s.set_num LIKE ?
               OR s.name LIKE ?
               OR t.name LIKE ?
            ORDER BY 
                CASE 
                    WHEN s.set_num = ? THEN 1
                    WHEN s.set_num LIKE ? THEN 2
                    WHEN s.name LIKE ? THEN 3
                    ELSE 4
                END,
                s.year DESC, s.set_num
            LIMIT ?
            """,
            [like, like, like, query, f"{query}%", like, limit],
        )

    def search_drawers(self, query: str, limit: int = 10) -> list[dict]:
        """Search drawers by name."""
        like = f"%{query}%"
        return self._all(
            """
            SELECT 
                d.id,
                d.name,
                d.description
            FROM drawers d
            WHERE d.name LIKE ?
              AND d.deleted_at IS NULL
              AND (d.kind IS NULL OR d.kind NOT IN ('rub_box_legacy','rub_box_nested_error'))
            ORDER BY 
                CASE 
                    WHEN d.name = ? THEN 1
                    WHEN d.name LIKE ? THEN 2
                    ELSE 3
                END,
                d.name COLLATE NOCASE
            LIMIT ?
            """,
            [like, query, like, limit],
        )

    def search_containers(self, query: str, limit: int = 10) -> list[dict]:
        """Search containers by name or drawer name."""
        like = f"%{query}%"
        return self._all(
            """
            SELECT DISTINCT
                c.id,
                c.name,
                c.description,
                c.drawer_id,
                d.name AS drawer_name
            FROM containers c
            JOIN drawers d ON d.id = c.drawer_id AND d.deleted_at IS NULL
            WHERE (c.name LIKE ? OR d.name LIKE ?)
              AND c.deleted_at IS NULL
            ORDER BY 
                CASE 
                    WHEN c.name = ? THEN 1
                    WHEN c.name LIKE ? THEN 2
                    WHEN d.name LIKE ? THEN 3
                    ELSE 4
                END,
                d.name COLLATE NOCASE, c.name COLLATE NOCASE
            LIMIT ?
            """,
            [like, like, query, like, like, limit],
        )

    def search_categories(self, query: str, limit: int = 10) -> list[dict]:
        """Search part categories by name."""
        like = f"%{query}%"
        return self._all(
            """
            SELECT 
                pc.id,
                pc.name
            FROM part_categories pc
            WHERE pc.name LIKE ?
            ORDER BY 
                CASE 
                    WHEN pc.name = ? THEN 1
                    WHEN pc.name LIKE ? THEN 2
                    ELSE 3
                END,
                pc.name COLLATE NOCASE
            LIMIT ?
            """,
            [like, query, like, limit],
        )
