from enum import Enum


class Status(Enum):
    BUILT = "built"
    IN_BOX = "in_box"
    WIP = "wip"
    LOOSE = "loose_parts"
    TEARDOWN = "teardown"

    @classmethod
    def from_any(cls, value):
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            legacy_map = {
                "work in progress": cls.WIP,
                "loose": cls.LOOSE,
                "loose_parts": cls.LOOSE,
                "in box": cls.IN_BOX,
            }
            if normalized in legacy_map:
                return legacy_map[normalized]
            for member in cls:
                if member.value == normalized or member.name.lower() == normalized:
                    return member
        raise ValueError(f"Cannot parse {value!r} into {cls.__name__}")

    @property
    def label(self):
        return _STATUS_LABELS.get(self, self.name.title())


_STATUS_LABELS = {
    Status.BUILT: "Built",
    Status.IN_BOX: "In Box",
    Status.WIP: "Work in Progress",
    Status.LOOSE: "Loose",
    Status.TEARDOWN: "Teardown",
}
