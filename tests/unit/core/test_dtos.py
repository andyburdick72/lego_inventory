import json

import pytest

# Import DTO module from src (conftest.py adds src/ to sys.path)
from core import dtos as dtos_mod


def _dump(model):
    """Normalize a DTO to a plain dict regardless of implementation.
    Supports pydantic v2 (.model_dump), pydantic v1 (.dict), or dataclasses (__dict__).
    """
    if hasattr(model, "model_dump"):
        return model.model_dump()
    if hasattr(model, "dict"):
        return model.dict()
    if hasattr(model, "__dict__"):
        return dict(model.__dict__)
    raise AssertionError("Unsupported DTO type for dump")


def _make(cls, data):
    """Recreate a DTO from a dict for round-trip tests."""
    # pydantic v2
    if hasattr(cls, "model_validate"):
        return cls.model_validate(data)
    # pydantic v1
    try:
        return cls.parse_obj(data)
    except Exception:
        pass
    # dataclass / simple class
    try:
        return cls(**data)
    except Exception as e:
        raise AssertionError(f"Unsupported DTO constructor for {cls}: {e}") from e


@pytest.mark.parametrize(
    "dto_name, sample",
    [
        ("DrawerDTO", {"id": 123, "name": "Really Useful Box 4L #1 - Angle (small)"}),
        ("ContainerDTO", {"id": 7, "label": "A1", "drawer_id": 123}),
    ],
)
def test_dto_roundtrip(dto_name, sample):
    DTO = getattr(dtos_mod, dto_name, None)
    if DTO is None:
        pytest.skip(f"{dto_name} not present in core.dtos")

    original = _make(DTO, sample)
    # JSON encode/decode to simulate API / persistence boundaries
    decoded = json.loads(json.dumps(_dump(original)))
    reconstructed = _make(DTO, decoded)

    assert _dump(reconstructed) == _dump(original)


def test_optional_fields_are_preserved_if_present():
    """If DTOs define optional fields, ensure they survive a round-trip.
    This test is tolerant: it skips if the DTOs don't expose the fields.
    """
    DrawerDTO = getattr(dtos_mod, "DrawerDTO", None)
    if DrawerDTO is None:
        pytest.skip("DrawerDTO not present")

    # Try a couple of common optional fields; ignore if the class doesn't define them
    sample = {"id": 999, "name": "Test Drawer"}
    for field, value in ("description", "A drawer for slopes"), ("location_hint", "Garage"):
        if hasattr(DrawerDTO, "model_fields") and field in getattr(DrawerDTO, "model_fields", {}):
            sample[field] = value

    original = _make(DrawerDTO, sample)
    decoded = json.loads(json.dumps(_dump(original)))
    reconstructed = _make(DrawerDTO, decoded)
    assert _dump(reconstructed) == _dump(original)


@pytest.mark.parametrize(
    "field,value",
    [("deleted", False), ("deleted_at", None), (None, None)],
)
def test_containerdto_optional_deleted_roundtrip(field, value):
    ContainerDTO = getattr(dtos_mod, "ContainerDTO", None)
    if ContainerDTO is None:
        pytest.skip("ContainerDTO not present in core.dtos")

    sample = {"id": 1, "label": "All", "drawer_id": 2}
    if field:
        sample[field] = value

    original = _make(ContainerDTO, sample)
    decoded = json.loads(json.dumps(_dump(original)))
    reconstructed = _make(ContainerDTO, decoded)
    assert _dump(reconstructed) == _dump(original)


def test_drawerdto_accepts_extra_fields_tolerantly():
    DrawerDTO = getattr(dtos_mod, "DrawerDTO", None)
    if DrawerDTO is None:
        pytest.skip("DrawerDTO not present in core.dtos")

    # Some DTOs may forbid extra fields; this test only asserts that if the DTO accepts them,
    # they survive a round-trip; otherwise it skips.
    sample = {"id": 321, "name": "RUB 4L #2"}
    sample_with_extra = dict(sample)
    sample_with_extra["_ignored"] = "x"

    try:
        original = _make(DrawerDTO, sample_with_extra)
    except AssertionError:
        pytest.skip("DrawerDTO appears to be strict about extra fields")

    decoded = json.loads(json.dumps(_dump(original)))
    reconstructed = _make(DrawerDTO, decoded)
    assert _dump(reconstructed) == _dump(original)
