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
