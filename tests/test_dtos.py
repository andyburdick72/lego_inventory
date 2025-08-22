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
        raise AssertionError(f"Unsupported DTO constructor for {cls}: {e}")


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
