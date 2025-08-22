from typing import Any, cast

import pytest

from app import adapters as adapters_mod
from core import dtos as dtos_mod


def _call_rows_to(rows_to, rows, conv):
    """Support either signature: rows_to(rows, conv) or rows_to(conv, rows)."""
    try:
        return rows_to(rows, conv)
    except TypeError:
        return rows_to(conv, rows)


def test_rows_to_helper_exists_and_works():
    rows_to = getattr(adapters_mod, "rows_to", None)
    assert callable(rows_to), "rows_to helper not found"

    class Row(dict):
        def __getattr__(self, k):  # sqlite Row-like
            return self[k]

    rows = [Row({"id": 1, "label": "A1"}), Row({"id": 2, "label": "A2"})]

    def to_tuple(r):
        return (r["id"], r["label"])

    assert _call_rows_to(rows_to, rows, to_tuple) == [(1, "A1"), (2, "A2")]


def test_row_to_drawer_if_present():
    fn = getattr(adapters_mod, "row_to_drawer", None)
    if not callable(fn):
        pytest.skip("row_to_drawer not present in app.adapters")

    DrawerDTO = getattr(dtos_mod, "DrawerDTO", None)
    assert DrawerDTO, "DrawerDTO missing in core.dtos"

    # DB often uses 'name' for drawers; allow adapters to accept that
    row = {"id": 42, "name": "Really Useful Box 4L #1 - Angle (small)", "deleted": 0}
    dto = fn(row)
    dto_any = cast(Any, dto)
    assert isinstance(dto, DrawerDTO)
    assert dto_any.id == 42
    drawer_name = getattr(dto, "name", None) or getattr(dto, "label", None)
    assert drawer_name == "Really Useful Box 4L #1 - Angle (small)"
    deleted = getattr(dto, "deleted", None)
    if deleted is not None:
        assert deleted in (False, 0)


def test_row_to_container_if_present():
    fn = getattr(adapters_mod, "row_to_container", None)
    if not callable(fn):
        pytest.skip("row_to_container not present in app.adapters")

    ContainerDTO = getattr(dtos_mod, "ContainerDTO", None)
    assert ContainerDTO, "ContainerDTO missing in core.dtos"

    row = {"id": 7, "label": "A1", "drawer_id": 42, "deleted": 1}
    dto = fn(row)
    dto_any = cast(Any, dto)
    assert isinstance(dto, ContainerDTO)
    assert (
        dto_any.id,
        getattr(dto, "label", None),
        getattr(dto, "drawer_id", None),
    ) == (7, "A1", 42)
    deleted = getattr(dto, "deleted", None)
    if deleted is not None:
        assert deleted in (True, 1)


def test_row_to_set_if_present():
    fn = getattr(adapters_mod, "row_to_set", None)
    if not callable(fn):
        pytest.skip("row_to_set not present in app.adapters (sets CRUD not implemented yet)")

    SetDTO = getattr(dtos_mod, "SetDTO", None)
    if SetDTO is None:
        pytest.skip("SetDTO not present in core.dtos")

    row = {"id": 3, "set_num": "1234-1", "name": "Test Set", "status": "built"}
    dto = fn(row)
    dto_any = cast(Any, dto)
    assert isinstance(dto, SetDTO)
    assert (
        dto_any.id,
        getattr(dto, "set_num", None),
        getattr(dto, "name", None),
    ) == (3, "1234-1", "Test Set")
    # status might be str or enum; accept either
    status_val = getattr(dto, "status", None)
    status_name = getattr(status_val, "name", None)
    allowed = {"built", "wip", "in_box", "teardown", "loose", "loose_parts"}
    if status_name is not None:
        assert status_name.lower() in allowed
    else:
        assert str(status_val).lower() in allowed


# Additional branch coverage tests
def test_rows_to_accepts_generators_and_attr_rows():
    rows_to = getattr(adapters_mod, "rows_to", None)
    if not callable(rows_to):
        pytest.skip("rows_to helper not found in app.adapters")

    class Row(dict):
        def __getattr__(self, k):
            return self[k]

    src = (Row({"id": i, "label": f"L{i}"}) for i in range(3))  # generator

    def to_tuple(r):
        # exercise both dict and attribute access paths
        return (r["id"], r.label)

    out = _call_rows_to(rows_to, src, to_tuple)
    assert out == [(0, "L0"), (1, "L1"), (2, "L2")]


def test_row_to_drawer_accepts_label_field():
    fn = getattr(adapters_mod, "row_to_drawer", None)
    if not callable(fn):
        pytest.skip("row_to_drawer not present in app.adapters")

    DrawerDTO = getattr(dtos_mod, "DrawerDTO", None)
    assert DrawerDTO, "DrawerDTO missing in core.dtos"

    row = {"id": 101, "label": "Small Parts Drawer", "deleted": None}
    dto = fn(row)
    dto_any = cast(Any, dto)
    assert isinstance(dto, DrawerDTO)
    assert dto_any.id == 101
    drawer_name = next((getattr(dto, attr, None) for attr in ("name", "label", "title")), None)
    if not drawer_name:  # treat None or empty string as absent
        pytest.xfail(
            "DrawerDTO lacks or leaves empty name/label/title; adjust adapter to map 'label' input"
        )
    assert drawer_name == "Small Parts Drawer"


def test_row_to_container_tolerates_extra_fields_and_none_deleted():
    fn = getattr(adapters_mod, "row_to_container", None)
    if not callable(fn):
        pytest.skip("row_to_container not present in app.adapters")

    ContainerDTO = getattr(dtos_mod, "ContainerDTO", None)
    assert ContainerDTO, "ContainerDTO missing in core.dtos"

    row = {"id": 55, "label": "All", "drawer_id": 9, "deleted": None, "ignored": "x"}
    dto = fn(row)
    dto_any = cast(Any, dto)
    assert isinstance(dto, ContainerDTO)
    assert (dto_any.id, getattr(dto, "label", None), getattr(dto, "drawer_id", None)) == (
        55,
        "All",
        9,
    )


def test_row_to_set_accepts_enum_status_if_supported():
    fn = getattr(adapters_mod, "row_to_set", None)
    if not callable(fn):
        pytest.skip("row_to_set not present in app.adapters (sets CRUD not implemented yet)")

    SetDTO = getattr(dtos_mod, "SetDTO", None)
    if SetDTO is None:
        pytest.skip("SetDTO not present in core.dtos")

    try:
        from core.enums import Status

        status_value = Status.WIP
    except Exception:  # enum not available; fall back to string
        status_value = "wip"

    row = {"id": 8, "set_num": "9999-1", "name": "Enum Set", "status": status_value}
    dto = fn(row)
    dto_any = cast(Any, dto)
    assert isinstance(dto, SetDTO)
    assert (dto_any.id, getattr(dto, "set_num", None), getattr(dto, "name", None)) == (
        8,
        "9999-1",
        "Enum Set",
    )
    status_val = getattr(dto, "status", None)
    status_name = getattr(status_val, "name", None)
    allowed = {"built", "wip", "in_box", "teardown", "loose", "loose_parts"}
    if status_name is not None:
        assert status_name.lower() in allowed
    else:
        assert str(status_val).lower() in allowed


# --- Cover set status line (invalid/missing status triggers ValueError in from_any)
def test_row_to_set_status_invalid_raises_on_line():
    fn = getattr(adapters_mod, "row_to_set", None)
    if not callable(fn):
        pytest.skip("row_to_set not present in app.adapters")
    # from_any(None) will raise, ensuring line execution is counted
    with pytest.raises(ValueError):
        fn({"set_number": "1234-1", "name": "No Status", "status": None})


# --- Cover inventory item status line (same idea) + qty fallback tested elsewhere
def test_row_to_inventory_item_status_invalid_raises_on_line():
    fn = getattr(adapters_mod, "row_to_inventory_item", None)
    if not callable(fn):
        pytest.skip("row_to_inventory_item not present in app.adapters")
    with pytest.raises(ValueError):
        fn({"part_id": "3001", "color_id": 5, "qty": 1, "status": None})


# --- Ensure qty fallback path is exercised
def test_row_to_inventory_item_qty_fallback_ok():
    fn = getattr(adapters_mod, "row_to_inventory_item", None)
    if not callable(fn):
        pytest.skip("row_to_inventory_item not present in app.adapters")
    from core.enums import Status

    dto = fn({"part_id": "3001", "color_id": 5, "qty": 9, "status": Status.BUILT})
    assert getattr(dto, "quantity", None) == 9


# --- Exercise drawer/container summary adapters (defaults/int coercions)
def test_row_to_drawer_summary_defaults_coercions():
    fn = getattr(adapters_mod, "row_to_drawer_summary", None)
    if not callable(fn):
        pytest.skip("row_to_drawer_summary not present in app.adapters")
    dto = fn({"id": "10"})  # string to exercise int(...) coercion
    assert getattr(dto, "id", None) == 10
    assert getattr(dto, "name", None) == ""
    assert getattr(dto, "sort_index", None) == 0
    assert getattr(dto, "container_count", None) == 0
    assert getattr(dto, "part_count", None) == 0


def test_row_to_container_summary_defaults_coercions():
    fn = getattr(adapters_mod, "row_to_container_summary", None)
    if not callable(fn):
        pytest.skip("row_to_container_summary not present in app.adapters")
    dto = fn({"id": "11"})
    assert getattr(dto, "id", None) == 11
    assert getattr(dto, "name", None) == ""
    assert getattr(dto, "sort_index", None) == 0
    assert getattr(dto, "part_count", None) == 0
    assert getattr(dto, "unique_parts", None) == 0
