# tests/infra/repositories/test_totals.py
from infra.db.repositories.inventory_repo import InventoryRepo
from infra.db.repositories.sets_repo import SetsRepo


def test_totals_include_sets(conn_rw):
    inv = InventoryRepo(conn_rw)
    sets = SetsRepo(conn_rw)
    # seed in your conftest already has set_parts rows totaling > 0
    assert inv.loose_total() >= 0
    assert sets.set_total_for_statuses(["built", "wip", "in_box", "teardown"]) > 0
