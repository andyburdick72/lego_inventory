"""Additional tests for route builders to improve coverage."""
import pytest

from utils.routes import (
    container_url,
    drawer_url,
    part_url,
    rebrickable_part_color_url,
    rebrickable_part_url,
    rebrickable_set_url,
    set_url,
)


@pytest.mark.unit
def test_drawer_url_with_special_chars():
    """Test drawer_url with special characters."""
    assert drawer_url("drawer#1") == "/drawers/drawer%231"
    assert drawer_url("drawer&name") == "/drawers/drawer%26name"


@pytest.mark.unit
def test_container_url_with_special_chars():
    """Test container_url with special characters."""
    assert container_url("container#1") == "/containers/container%231"
    assert container_url("container&name") == "/containers/container%26name"


@pytest.mark.unit
def test_part_url_with_special_chars():
    """Test part_url with special characters."""
    assert part_url("part#1") == "/parts/part%231"
    assert part_url("part&name") == "/parts/part%26name"


@pytest.mark.unit
def test_set_url_with_special_chars():
    """Test set_url with special characters."""
    assert set_url("set#1") == "/sets/set%231"
    assert set_url("set&name") == "/sets/set%26name"


@pytest.mark.unit
def test_rebrickable_part_url_with_special_chars():
    """Test rebrickable_part_url with special characters."""
    assert rebrickable_part_url("part#1") == "https://rebrickable.com/parts/part%231/"
    assert rebrickable_part_url("part&name") == "https://rebrickable.com/parts/part%26name/"


@pytest.mark.unit
def test_rebrickable_part_color_url_empty_string():
    """Test rebrickable_part_color_url with empty string color_id."""
    assert rebrickable_part_color_url("3001", "") == "https://rebrickable.com/parts/3001/"


@pytest.mark.unit
def test_rebrickable_part_color_url_with_special_chars():
    """Test rebrickable_part_color_url with special characters."""
    result = rebrickable_part_color_url("part#1", "color#1")
    assert "part%231" in result
    assert "color%231" in result


@pytest.mark.unit
def test_rebrickable_set_url_with_special_chars():
    """Test rebrickable_set_url with special characters."""
    assert rebrickable_set_url("set#1") == "https://rebrickable.com/sets/set%231/"
    assert rebrickable_set_url("set&name") == "https://rebrickable.com/sets/set%26name/"

