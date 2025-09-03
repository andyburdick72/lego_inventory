from collections.abc import Mapping

import app.di as di

# ---- Fakes that let us exercise adapter branches without touching sqlite ----


class _FakeDrawersImplCounts:
    """Exposes list_drawers_with_counts to hit that branch in _DrawersRepoAdapter.list."""

    def __init__(self):
        self.calls = []

    def list_drawers_with_counts(self):
        self.calls.append("list_with_counts")
        # include container_count / part_count to cover normalization logic
        return [
            {"id": 1, "name": "A1", "container_count": 2, "part_count": 3},
            {"id": 2, "name": "A2", "container_count": None, "part_count": 0},
        ]


class _FakeDrawersImplDeleteUndelete:
    """Only exposes delete/undelete so soft_delete/restore fallbacks are used."""

    def __init__(self):
        self.deleted = []
        self.restored = []

    def delete_drawer(self, drawer_id: int):
        self.deleted.append(drawer_id)

    def undelete_drawer(self, drawer_id: int):
        self.restored.append(drawer_id)


class _FakeContainersImpl:
    """Containers adapter target with list/create and delete/undelete fallbacks."""

    def __init__(self):
        self.deleted = []
        self.restored = []

    def list_containers_with_counts(self, drawer_id: int):
        return [{"id": 10, "drawer_id": drawer_id, "name": "C1"}]

    def create_container(self, *args, **kwargs):
        return {"id": 11, "drawer_id": kwargs.get("drawer_id"), "name": kwargs.get("name")}

    def delete_container(self, container_id: int):
        self.deleted.append(container_id)

    def undelete_container(self, container_id: int):
        self.restored.append(container_id)


class _FakeInventoryImpl:
    def __init__(self):
        self.called = False

    def storage_location_counts(self, *, filters=None):  # matches concrete name
        self.called = True
        return [{"kind": "drawer", "count": 1}]

    def loose_inventory_for_part(self, design_id: str):
        return [{"design_id": design_id, "qty": 5}]


def test_drawers_list_with_counts_normalizes_keys():
    adapter = di._DrawersRepoAdapter(_FakeDrawersImplCounts())  # type: ignore[attr-defined]
    rows = list(adapter.list())
    assert isinstance(rows, list)
    # Ensure normalization added 'containers' and 'parts' keys
    assert rows[0]["containers"] == 2
    assert rows[0]["parts"] == 3
    # None container_count becomes 0
    assert rows[1]["containers"] == 0


def test_drawers_soft_delete_and_restore_fallbacks():
    impl = _FakeDrawersImplDeleteUndelete()
    adapter = di._DrawersRepoAdapter(impl)  # type: ignore[attr-defined]
    adapter.soft_delete(7)
    adapter.restore(7)
    assert impl.deleted == [7]
    assert impl.restored == [7]


def test_containers_list_requires_drawer_id_and_create_and_delete_restore():
    impl = _FakeContainersImpl()
    adapter = di._ContainersRepoAdapter(impl)  # type: ignore[attr-defined]

    # list without drawer_id returns []
    assert adapter.list(filters=None) == []
    assert adapter.list(filters={}) == []

    # list with drawer_id hits the impl
    rows = adapter.list(filters={"drawer_id": 9})
    assert rows and rows[0]["drawer_id"] == 9

    # create returns Mapping with id
    created = adapter.create(label="C1", drawer_id=9)
    assert isinstance(created, Mapping)
    assert created["id"] == 11 and created["drawer_id"] == 9

    # soft_delete/restore use fallbacks
    adapter.soft_delete(55)
    adapter.restore(55)
    assert impl.deleted == [55]
    assert impl.restored == [55]


def test_inventory_adapter_methods_call_impl():
    inv = _FakeInventoryImpl()
    adapter = di._InventoryRepoAdapter(inv)  # type: ignore[attr-defined]
    # counts_by_storage_location delegates to impl
    rows = adapter.counts_by_storage_location()
    assert inv.called is True
    assert rows == [{"kind": "drawer", "count": 1}]
    # loose_inventory_for_part delegates to impl
    parts = adapter.loose_inventory_for_part("3001")
    assert parts and parts[0]["design_id"] == "3001"
