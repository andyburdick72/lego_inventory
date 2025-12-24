# tests/contract/test_write_endpoints.py
import os
import uuid

import httpx
import pytest

pytestmark = pytest.mark.contract

if os.getenv("APP_SAFE_MODE") == "true":
    pytest.skip("Legacy write endpoints are disabled in set-centric safe mode.", allow_module_level=True)

BASE = os.getenv("APP_BASE_URL", "http://localhost:8001")


@pytest.fixture(scope="module")
def client():
    # Increased timeout for write operations that may hit database locks
    with httpx.Client(base_url=BASE, timeout=30.0) as c:
        yield c


# ------------------------- Drawers -------------------------


def test_drawers_create_rename_move_delete_and_restore(client):
    base = f"A1-{uuid.uuid4().hex[:6]}"
    # Create new drawer
    r = client.post("/api/v1/drawers/create", json={"name": base, "description": "Wall-1"})
    assert r.status_code in (200, 201)
    did = r.json().get("id")
    assert isinstance(did, int)

    # Duplicate by name should 409 while active
    dup = client.post("/api/v1/drawers/create", json={"name": base})
    assert dup.status_code == 409

    # Rename
    rn = client.post("/api/v1/drawers/rename", json={"id": did, "new_name": base + "-renamed"})
    assert rn.status_code == 200

    # Move (sort index)
    mv = client.post("/api/v1/drawers/move", json={"id": did, "new_sort_index": 10})
    assert mv.status_code == 200

    # Delete (soft)
    dl = client.post("/api/v1/drawers/delete", json={"id": did})
    assert dl.status_code == 200

    # Re-create with same name should RESTORE (not 409)
    r2 = client.post("/api/v1/drawers/create", json={"name": base})
    assert r2.status_code in (200, 201)
    did2 = r2.json().get("id")
    assert isinstance(did2, int)

    # Cleanup: delete restored drawer
    client.post("/api/v1/drawers/delete", json={"id": did2})


# ------------------------- Containers -------------------------


def test_containers_create_dup_move_rename_delete_and_reuse_cell(client):
    b1 = f"B1-{uuid.uuid4().hex[:6]}"
    b2 = f"B2-{uuid.uuid4().hex[:6]}"
    # Setup: two drawers
    d1 = client.post("/api/v1/drawers/create", json={"name": b1})
    assert d1.status_code in (200, 201)
    drawer1 = d1.json().get("id")

    d2 = client.post("/api/v1/drawers/create", json={"name": b2})
    assert d2.status_code in (200, 201)
    drawer2 = d2.json().get("id")

    cname1 = f"C1-{uuid.uuid4().hex[:6]}"
    cname3 = f"C3-{uuid.uuid4().hex[:6]}"
    # Create container in drawer1 at 0,0
    c1 = client.post(
        "/api/v1/containers/create",
        json={"drawer_id": drawer1, "name": cname1, "row_index": 0, "col_index": 0},
    )
    assert c1.status_code in (200, 201)
    cid = c1.json().get("id")

    # Duplicate name within same drawer should 409
    cdup = client.post("/api/v1/containers/create", json={"drawer_id": drawer1, "name": cname1})
    assert cdup.status_code == 409

    # Move to drawer2
    mv = client.post("/api/v1/containers/move", json={"id": cid, "new_drawer_id": drawer2})
    assert mv.status_code == 200

    # Rename
    rn = client.post("/api/v1/containers/rename", json={"id": cid, "new_name": "C2"})
    assert rn.status_code == 200

    # Delete (soft)
    dl = client.post("/api/v1/containers/delete", json={"id": cid})
    assert dl.status_code == 200

    # Reuse the same cell (0,0) in drawer1 should be allowed now
    c2 = client.post(
        "/api/v1/containers/create",
        json={"drawer_id": drawer1, "name": cname3, "row_index": 0, "col_index": 0},
    )
    assert c2.status_code in (200, 201)

    # Cleanup: delete created container and drawers
    c2_id = c2.json().get("id")
    if isinstance(c2_id, int):
        client.post("/api/v1/containers/delete", json={"id": c2_id})
    client.post("/api/v1/drawers/delete", json={"id": drawer1})
    client.post("/api/v1/drawers/delete", json={"id": drawer2})
