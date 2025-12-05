"""Comprehensive tests for Status enum to improve coverage."""
import pytest

from core.enums import Status


@pytest.mark.unit
def test_from_any_with_bytes_raises():
    """Test that bytes raise TypeError/ValueError."""
    with pytest.raises((ValueError, TypeError)):
        Status.from_any(b"built")


@pytest.mark.unit
def test_from_any_with_none_raises():
    """Test that None raises ValueError."""
    with pytest.raises(ValueError):
        Status.from_any(None)


@pytest.mark.unit
def test_from_any_with_int_raises():
    """Test that int raises ValueError."""
    with pytest.raises(ValueError):
        Status.from_any(123)


@pytest.mark.unit
def test_from_any_with_dict_raises():
    """Test that dict raises ValueError."""
    with pytest.raises(ValueError):
        Status.from_any({"status": "built"})


@pytest.mark.unit
def test_from_any_with_list_raises():
    """Test that list raises ValueError."""
    with pytest.raises(ValueError):
        Status.from_any(["built"])


@pytest.mark.unit
def test_from_any_with_empty_string_raises():
    """Test that empty string raises ValueError."""
    with pytest.raises(ValueError):
        Status.from_any("")


@pytest.mark.unit
def test_from_any_with_invalid_string_raises():
    """Test that invalid string raises ValueError."""
    with pytest.raises(ValueError):
        Status.from_any("not_a_status")


@pytest.mark.unit
def test_from_any_with_whitespace_only_raises():
    """Test that whitespace-only string raises ValueError."""
    with pytest.raises(ValueError):
        Status.from_any("   ")


@pytest.mark.unit
def test_label_for_all_statuses():
    """Test that all statuses have labels."""
    assert Status.BUILT.label == "Built"
    assert Status.IN_BOX.label == "In Box"
    assert Status.WIP.label == "Work in Progress"
    assert Status.LOOSE.label == "Loose"
    assert Status.TEARDOWN.label == "Teardown"


@pytest.mark.unit
def test_from_any_case_insensitive_member_names():
    """Test that member names are case-insensitive."""
    assert Status.from_any("BUILT") == Status.BUILT
    assert Status.from_any("built") == Status.BUILT
    assert Status.from_any("Built") == Status.BUILT
    assert Status.from_any("WIP") == Status.WIP
    assert Status.from_any("wip") == Status.WIP


@pytest.mark.unit
def test_from_any_legacy_loose_synonym():
    """Test that 'loose' maps to LOOSE enum."""
    assert Status.from_any("loose") == Status.LOOSE
    assert Status.from_any("loose_parts") == Status.LOOSE


@pytest.mark.unit
def test_from_any_legacy_work_in_progress():
    """Test legacy 'work in progress' mapping."""
    assert Status.from_any("work in progress") == Status.WIP
    assert Status.from_any("WORK IN PROGRESS") == Status.WIP
    assert Status.from_any("  work in progress  ") == Status.WIP


@pytest.mark.unit
def test_from_any_legacy_in_box():
    """Test legacy 'in box' mapping."""
    assert Status.from_any("in box") == Status.IN_BOX
    assert Status.from_any("IN BOX") == Status.IN_BOX
    assert Status.from_any("  in box  ") == Status.IN_BOX

