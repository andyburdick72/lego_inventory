# pyright: reportMissingImports=false
import re
from typing import cast

import pytest
from bs4 import BeautifulSoup
from bs4.element import Tag

pytestmark = pytest.mark.ui


def _soup(resp):
    return BeautifulSoup(resp.data, "html.parser")


def _href_of(a: Tag) -> str:
    h = a.get("href")
    if isinstance(h, list):
        return h[0] if h else ""
    return cast(str, h or "")


def test_main_loose_parts_has_drawer_and_container_links(client):
    resp = client.get("/")
    assert resp.status_code == 200
    soup = _soup(resp)

    # Look for at least one drawer/container anchor anywhere in the main table
    drawer_a = soup.select_one("a[href^='/drawers/']")
    container_a = soup.select_one("a[href^='/containers/']")

    assert drawer_a is not None, "Expected at least one drawer link in main Loose Parts table"
    assert container_a is not None, "Expected at least one container link in main Loose Parts table"

    assert re.match(r"^/drawers/[^\s]+$", _href_of(drawer_a)) is not None
    assert re.match(r"^/containers/[^\s]+$", _href_of(container_a)) is not None


@pytest.mark.parametrize("design_id", ["3023"])  # use a stable part from fixtures
def test_part_page_loose_tab_has_drawer_and_container_links(client, design_id):
    resp = client.get(f"/parts/{design_id}")
    assert resp.status_code == 200
    soup = _soup(resp)

    # Target links inside the Loose Parts tab/table if present
    # (Fall back to any table on the page to avoid brittleness across templates.)
    drawer_a = soup.select_one("#loose-parts a[href^='/drawers/'], a[href^='/drawers/']")
    container_a = soup.select_one("#loose-parts a[href^='/containers/'], a[href^='/containers/']")

    assert drawer_a is not None, "Expected at least one drawer link in Loose Parts tab"
    assert container_a is not None, "Expected at least one container link in Loose Parts tab"

    assert re.match(r"^/drawers/[^\s]+$", _href_of(drawer_a)) is not None
    assert re.match(r"^/containers/[^\s]+$", _href_of(container_a)) is not None


@pytest.mark.parametrize("design_id", ["3023"])  # use a stable part from fixtures
def test_part_page_in_sets_tab_split_and_linked(client, design_id):
    resp = client.get(f"/parts/{design_id}")
    assert resp.status_code == 200
    soup = _soup(resp)

    # Headers should be: Set | Name | Color | Qty
    header_cells = [th.get_text(strip=True) for th in soup.select("#in-sets table thead th")]
    # Some templates inject extra columns; only assert the first four in order
    assert header_cells[:4] == [
        "Set",
        "Name",
        "Color",
        "Qty",
    ], f"Unexpected headers: {header_cells}"

    # First body row: column 0 should contain a link to /sets/<id>, column 1 is name (plain)
    first_row = soup.select_one("#in-sets table tbody tr")
    assert first_row is not None, "Expected at least one row in In Sets table"
    cells = first_row.select("td")
    assert len(cells) >= 4, f"Expected at least 4 columns, saw {len(cells)}"

    set_id_a = cells[0].select_one("a[href^='/sets/']")
    assert set_id_a is not None, "Set ID column should contain a hyperlink to /sets/<set_num>"
    assert re.match(r"^/sets/[^\s/]+/?$", _href_of(set_id_a)) is not None

    # Name cell should have readable text (may also contain whitespace/spans etc.)
    assert cells[1].get_text(strip=True) != "", "Set Name column should contain text"
