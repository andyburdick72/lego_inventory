import pytest

from core import enums as enums_mod


def _label_of(member):
    """Return the human-friendly label of a Status enum member.
    Supports either `.label` (attr or method) or `.to_label()`.
    Fallbacks to the member name if no label API exists yet.
    """
    if hasattr(member, "label"):
        val = member.label
        return val() if callable(val) else val
    if hasattr(member, "to_label"):
        val = member.to_label
        return val() if callable(val) else val
    return member.name


def _parser(Status):
    """Return a parser function if available (Status.parse or Status.from_str)."""
    return getattr(Status, "parse", None) or getattr(Status, "from_str", None)


def test_status_has_expected_members():
    Status = enums_mod.Status
    # Core statuses we expect; allow variants for "loose" and do not require "unsorted"
    names = {m.name.lower() for m in Status}
    required = {"built", "in_box", "wip", "teardown"}
    assert required.issubset(names), f"Missing required statuses from {names}"
    assert any(
        v in names for v in {"loose", "loose_parts", "loose_inventory"}
    ), f"Expected a 'loose' variant among {{'loose','loose_parts','loose_inventory'}}, got {names}"


def test_status_labels_are_human_friendly():
    Status = enums_mod.Status
    mapping = {
        "wip": "Work in Progress",
        "in_box": "In Box",
        "built": "Built",
        "loose": "Loose",
        "loose_parts": "Loose",
        "teardown": "Teardown",
        # "unsorted": "Unsorted",  # optional in some schemas
    }
    for m in Status:
        key = m.name.lower()
        if key in mapping:
            assert _label_of(m) == mapping[key]


@pytest.mark.parametrize(
    "raw,expected_name",
    [
        ("built", "BUILT"),
        ("Built", "BUILT"),
        ("WORK IN PROGRESS", "WIP"),  # label → enum parsing supported by many impls
        ("in_box", "IN_BOX"),
    ],
)
def test_status_parse_from_strings(raw, expected_name):
    Status = enums_mod.Status
    parser = _parser(Status)
    if parser is None:
        pytest.xfail("Status.parse/from_str not implemented yet")
    val = parser(raw)
    assert val.name == expected_name
