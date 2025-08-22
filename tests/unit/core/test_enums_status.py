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
