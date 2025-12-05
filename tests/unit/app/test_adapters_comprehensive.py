"""Additional tests for adapters to improve coverage."""
import pytest

from app.adapters import (
    row_to_container,
    row_to_container_summary,
    row_to_drawer,
    row_to_drawer_summary,
    row_to_inventory_item,
    row_to_set,
    rows_to,
)


@pytest.mark.unit
def test_row_to_drawer_with_container_count():
    """Test row_to_drawer with container_count."""
    row = {"id": 1, "name": "Drawer A", "deleted": 0, "container_count": 5}
    dto = row_to_drawer(row)
    assert dto.id == 1
    assert dto.name == "Drawer A"
    assert dto.container_count == 5


@pytest.mark.unit
def test_row_to_drawer_with_none_container_count():
    """Test row_to_drawer with None container_count."""
    row = {"id": 1, "name": "Drawer A", "deleted": 0, "container_count": None}
    dto = row_to_drawer(row)
    assert dto.container_count is None


@pytest.mark.unit
def test_row_to_container_with_drawer_name():
    """Test row_to_container with drawer_name."""
    row = {
        "id": 1,
        "label": "Container A",
        "drawer_id": 5,
        "drawer_name": "Drawer 5",
        "deleted": 0,
        "parts_count": 10,
    }
    dto = row_to_container(row)
    assert dto.id == 1
    assert dto.label == "Container A"
    assert dto.drawer_id == 5
    assert dto.drawer_name == "Drawer 5"
    assert dto.parts_count == 10


@pytest.mark.unit
def test_row_to_set_with_all_fields():
    """Test row_to_set with all optional fields."""
    row = {
        "set_number": "12345-1",
        "name": "Test Set",
        "year": 2024,
        "theme": "Test Theme",
        "status": "built",
        "total_parts": 100,
        "image_url": "https://example.com/image.jpg",
        "rebrickable_url": "https://rebrickable.com/sets/12345-1/",
    }
    dto = row_to_set(row)
    assert dto.set_number == "12345-1"
    assert dto.name == "Test Set"
    assert dto.year == 2024
    assert dto.theme == "Test Theme"
    assert dto.total_parts == 100
    assert dto.image_url == "https://example.com/image.jpg"
    assert dto.rebrickable_url == "https://rebrickable.com/sets/12345-1/"


@pytest.mark.unit
def test_row_to_inventory_item_with_set_info():
    """Test row_to_inventory_item with set information."""
    row = {
        "part_id": "3001",
        "color_id": 1,
        "color_name": "White",
        "color_hex": "#FFFFFF",
        "quantity": 5,
        "status": "loose",
        "set_number": "12345-1",
        "set_name": "Test Set",
        "part_name": "Brick 2 x 4",
        "image_url": "https://example.com/3001.jpg",
        "rebrickable_url": "https://rebrickable.com/parts/3001/",
    }
    dto = row_to_inventory_item(row)
    assert dto.part_id == "3001"
    assert dto.color_id == 1
    assert dto.quantity == 5
    assert dto.set_number == "12345-1"
    assert dto.set_name == "Test Set"
    assert dto.part_name == "Brick 2 x 4"


@pytest.mark.unit
def test_row_to_inventory_item_color_hex_with_hash():
    """Test row_to_inventory_item strips # from color_hex."""
    row = {
        "part_id": "3001",
        "color_id": 1,
        "color_hex": "#FF0000",
        "quantity": 1,
        "status": "loose",
    }
    dto = row_to_inventory_item(row)
    assert dto.color_hex == "FF0000"


@pytest.mark.unit
def test_row_to_inventory_item_color_hex_without_hash():
    """Test row_to_inventory_item with color_hex without #."""
    row = {
        "part_id": "3001",
        "color_id": 1,
        "color_hex": "FF0000",
        "quantity": 1,
        "status": "loose",
    }
    dto = row_to_inventory_item(row)
    assert dto.color_hex == "FF0000"


@pytest.mark.unit
def test_row_to_drawer_summary_with_all_fields():
    """Test row_to_drawer_summary with all fields."""
    row = {
        "id": 1,
        "name": "Drawer A",
        "description": "Test drawer",
        "kind": "standard",
        "cols": 4,
        "rows": 3,
        "sort_index": 10,
        "container_count": 5,
        "part_count": 100,
    }
    dto = row_to_drawer_summary(row)
    assert dto.id == 1
    assert dto.name == "Drawer A"
    assert dto.description == "Test drawer"
    assert dto.kind == "standard"
    assert dto.cols == 4
    assert dto.rows == 3
    assert dto.sort_index == 10
    assert dto.container_count == 5
    assert dto.part_count == 100


@pytest.mark.unit
def test_row_to_container_summary_with_all_fields():
    """Test row_to_container_summary with all fields."""
    row = {
        "id": 1,
        "name": "Container A",
        "description": "Test container",
        "row_index": 0,
        "col_index": 1,
        "sort_index": 5,
        "part_count": 50,
        "unique_parts": 25,
    }
    dto = row_to_container_summary(row)
    assert dto.id == 1
    assert dto.name == "Container A"
    assert dto.description == "Test container"
    assert dto.row_index == 0
    assert dto.col_index == 1
    assert dto.sort_index == 5
    assert dto.part_count == 50
    assert dto.unique_parts == 25


@pytest.mark.unit
def test_rows_to_with_single_row():
    """Test rows_to with single row."""
    def to_id(row):
        return row["id"]
    
    rows = [{"id": 42}]
    result = rows_to(to_id, rows)
    assert result == [42]


@pytest.mark.unit
def test_rows_to_with_multiple_rows():
    """Test rows_to with multiple rows."""
    def to_name(row):
        return row["name"]
    
    rows = [{"name": "A"}, {"name": "B"}, {"name": "C"}]
    result = rows_to(to_name, rows)
    assert result == ["A", "B", "C"]

