import pytest

from src.core.enums import Status


def test_iterability_and_uniqueness():
    members = list(Status)
    values = [m.value for m in members]
    assert len(values) == len(set(values))  # unique values
    # Ensure all five statuses are present
    assert {Status.BUILT, Status.IN_BOX, Status.WIP, Status.LOOSE, Status.TEARDOWN} <= set(members)


@pytest.mark.parametrize(
    "value,expected",
    [
        # Already an enum
        (Status.BUILT, Status.BUILT),
        # Match by exact value
        ("built", Status.BUILT),
        ("in_box", Status.IN_BOX),
        ("wip", Status.WIP),
        ("loose_parts", Status.LOOSE),
        ("teardown", Status.TEARDOWN),
        # Match by normalized name
        ("BUILT", Status.BUILT),
        ("In_Box", Status.IN_BOX),
        ("WIP", Status.WIP),
        ("loose", Status.LOOSE),  # legacy synonym
        ("teardown", Status.TEARDOWN),
        # Match by legacy phrases
        ("work in progress", Status.WIP),
        ("in box", Status.IN_BOX),
    ],
)
def test_from_any_valid(value, expected):
    assert Status.from_any(value) is expected


@pytest.mark.parametrize("bad", ["", "not_a_status", None, 123, {}, []])
def test_from_any_invalid_raises(bad):
    with pytest.raises((ValueError, TypeError)):
        Status.from_any(bad)


def test_labels_are_human_friendly():
    assert Status.BUILT.label == "Built"
    assert Status.IN_BOX.label == "In Box"
    assert Status.WIP.label == "Work in Progress"
    assert Status.LOOSE.label == "Loose"
    assert Status.TEARDOWN.label == "Teardown"


@pytest.mark.unit
def test_roundtrip_from_value_for_all_members():
    # For each enum member, its .value should round-trip via from_any
    for member in Status:
        assert Status.from_any(member.value) is member


@pytest.mark.parametrize(
    "value,expected",
    [
        (" in box ", Status.IN_BOX),
        ("  WORK IN PROGRESS ", Status.WIP),
        ("  loose  ", Status.LOOSE),
    ],
)
@pytest.mark.unit
def test_from_any_trims_and_is_case_insensitive_for_legacy_values(value, expected):
    assert Status.from_any(value) is expected


@pytest.mark.unit
def test_value_constants_are_stable():
    # Guard against accidental value renames which break persistence/interop
    assert Status.BUILT.value == "built"
    assert Status.IN_BOX.value == "in_box"
    assert Status.WIP.value == "wip"
    assert Status.LOOSE.value == "loose_parts"
    assert Status.TEARDOWN.value == "teardown"


def test_status_from_any_rejects_non_str_non_enum_bytes():
    with pytest.raises((ValueError, TypeError)):
        Status.from_any(b"in_box")


def test_status_from_any_accepts_enum_instance_roundtrip():
    # Passing an enum instance should return it unchanged
    assert Status.from_any(Status.WIP) is Status.WIP


def test_status_labels_for_all_members():
    labels = {s: s.label for s in Status}
    assert labels[Status.BUILT] == "Built"
    assert labels[Status.IN_BOX] == "In Box"
    assert labels[Status.WIP] == "Work in Progress"
    assert labels[Status.LOOSE] == "Loose"
    assert labels[Status.TEARDOWN] == "Teardown"
