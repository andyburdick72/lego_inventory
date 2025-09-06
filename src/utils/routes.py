# src/utils/routes.py
from urllib.parse import quote


def drawer_url(drawer_id: int | str) -> str:
    """
    Build a canonical URL for a drawer details page.
    """
    return f"/drawers/{quote(str(drawer_id))}"


def container_url(container_id: int | str) -> str:
    """
    Build a canonical URL for a container details page.
    """
    return f"/containers/{quote(str(container_id))}"


# Additional URL builder functions
def part_url(design_id: int | str) -> str:
    """Canonical local URL for a part detail page."""
    return f"/parts/{quote(str(design_id))}"


def set_url(set_num: int | str) -> str:
    """Canonical local URL for a set detail page."""
    return f"/sets/{quote(str(set_num))}"


def rebrickable_part_url(design_id: int | str) -> str:
    """External URL to Rebrickable part page."""
    return f"https://rebrickable.com/parts/{quote(str(design_id))}/"


def rebrickable_part_color_url(design_id: int | str, color_id: int | str | None) -> str:
    """External URL to Rebrickable part+color page (falls back to part URL)."""
    if color_id is None or str(color_id) == "":
        return rebrickable_part_url(design_id)
    return f"https://rebrickable.com/parts/{quote(str(design_id))}/{quote(str(color_id))}/"


def rebrickable_set_url(set_num: int | str) -> str:
    """External URL to Rebrickable set page."""
    return f"https://rebrickable.com/sets/{quote(str(set_num))}/"
