"""Lightweight API smoke tests to improve coverage.

These tests use a temporary SQLite DB (via APP_DB_PATH) and exercise a handful of endpoints.
They are intentionally shallow: the goal is to ensure endpoints don't crash and basic flows work.
"""

from __future__ import annotations

from datetime import datetime, timezone
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.settings import get_settings


@pytest.fixture()
def client(tmp_path, monkeypatch) -> TestClient:
    db_path = tmp_path / "api_smoke.db"
    monkeypatch.setenv("APP_DB_PATH", str(db_path))
    monkeypatch.setenv("APP_SAFE_MODE", "false")
    get_settings.cache_clear()

    # Ensure schema exists for the temporary DB.
    from infra.db.inventory_db import init_db

    init_db()

    with TestClient(app) as c:
        yield c


def _seed_minimal_set(db_path: str, set_num: str, status: str, added_at: str) -> int:
    """Insert a minimal set copy row and return its id."""
    with sqlite3.connect(db_path, check_same_thread=False) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute("INSERT OR IGNORE INTO colors(id, name, hex) VALUES (1, 'Black', '#000000')")
        conn.execute("INSERT OR IGNORE INTO themes(id, name) VALUES (1, 'Test Theme')")
        conn.execute(
            """
            INSERT OR IGNORE INTO parts(design_id, name, part_url, part_img_url, part_category_id, ignore_in_inventory)
            VALUES ('3001', 'Brick 2 x 4', NULL, NULL, NULL, 0)
            """
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO set_parts(set_num, design_id, color_id, quantity)
            VALUES (?, '3001', 1, 10)
            """,
            (set_num,),
        )
        cur = conn.execute(
            """
            INSERT INTO sets (set_num, name, year, theme_id, image_url, rebrickable_url, status, added_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (set_num, "Test Set", 2024, 1, None, None, status, added_at),
        )
        conn.commit()
        return int(cur.lastrowid)


def test_sets_copies_and_per_copy_status_update(client, tmp_path):
    """Ensure set copies can be listed and updated independently by id."""
    db_path = str(tmp_path / "api_smoke.db")
    now = datetime.now(tz=timezone.utc).isoformat()

    id1 = _seed_minimal_set(db_path, "TEST-1", "wip", now)
    id2 = _seed_minimal_set(db_path, "TEST-1", "in_box", now)
    assert id1 != id2

    # Copies list (new endpoint)
    r = client.get("/api/v1/sets/copies")
    assert r.status_code == 200
    copies = r.json()
    assert any(c["id"] == id1 for c in copies)
    assert any(c["id"] == id2 for c in copies)

    # Aggregate list should still work
    r2 = client.get("/api/v1/sets")
    assert r2.status_code == 200
    assert any(s["set_number"] == "TEST-1" for s in r2.json())

    # Per-set copies list
    r3 = client.get("/api/v1/sets/TEST-1/copies")
    assert r3.status_code == 200
    assert len(r3.json()) >= 2

    # Old update endpoint should refuse ambiguous updates
    r4 = client.patch("/api/v1/sets/TEST-1/status", json={"status": "built"})
    assert r4.status_code == 409

    # Update a single copy by id
    r5 = client.patch(f"/api/v1/sets/copies/{id1}/status", json={"status": "built"})
    assert r5.status_code == 200
    assert r5.json()["status"] == "built"


def test_drawers_containers_inventory_and_search_smoke(client):
    """Hit a few core endpoints to ensure basic routing works without crashing."""
    # Create a drawer
    r = client.post("/api/v1/drawers/create", json={"name": "Drawer-Smoke", "description": "Test"})
    assert r.status_code in (200, 201)
    drawer_id = r.json()["id"]

    # Create a container
    r2 = client.post(
        "/api/v1/containers/create",
        json={"drawer_id": drawer_id, "name": "Bin-1", "row_index": 0, "col_index": 0},
    )
    assert r2.status_code in (200, 201)

    # List drawers/containers
    assert client.get("/api/v1/drawers").status_code == 200
    assert client.get(f"/api/v1/containers?drawer_id={drawer_id}").status_code == 200

    # Inventory + search endpoints (should return 200 even if empty)
    assert client.get("/api/v1/inventory/loose").status_code == 200
    assert client.get("/api/v1/search?q=Drawer").status_code == 200


def test_more_endpoints_for_coverage(client, tmp_path):
    """Exercise additional endpoints to raise coverage (still shallow assertions)."""
    # Create drawer + container via API
    r = client.post("/api/v1/drawers/create", json={"name": "Drawer-Cov", "description": "Test"})
    assert r.status_code in (200, 201)
    drawer_id = r.json()["id"]

    r2 = client.post(
        "/api/v1/containers/create",
        json={"drawer_id": drawer_id, "name": "Box-Cov", "row_index": 0, "col_index": 0},
    )
    assert r2.status_code in (200, 201)
    container_id = r2.json()["id"]

    # Drawer detail + rename + move
    assert client.get(f"/api/v1/drawers/{drawer_id}").status_code == 200
    assert (
        client.post("/api/v1/drawers/rename", json={"id": drawer_id, "new_name": "Drawer-Cov-2"}).status_code
        == 200
    )
    assert (
        client.post("/api/v1/drawers/move", json={"id": drawer_id, "new_sort_index": 5}).status_code
        == 200
    )

    # Container endpoints: detail, rename, update, move (noop), parts
    assert client.get(f"/api/v1/containers/{container_id}").status_code == 200
    assert (
        client.post(
            "/api/v1/containers/rename", json={"id": container_id, "new_name": "Box-Cov-2"}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v1/containers/update",
            json={"id": container_id, "description": "Updated", "row_index": 0, "col_index": 0},
        ).status_code
        == 200
    )
    assert client.post("/api/v1/containers/move", json={"id": container_id, "new_drawer_id": drawer_id}).status_code == 200
    assert client.get(f"/api/v1/containers/{container_id}/parts").status_code == 200

    # Mark container as put-away-bin and fetch it
    assert client.post("/api/v1/containers/put-away-bin", json={"container_id": container_id}).status_code == 200
    assert client.get("/api/v1/containers/put-away-bin").status_code == 200

    # Seed minimal parts + inventory + set for inventory/parts/mismatch endpoints
    db_path = str(tmp_path / "api_smoke.db")
    with sqlite3.connect(db_path, check_same_thread=False) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute("INSERT OR IGNORE INTO colors(id, name, hex) VALUES (1, 'Black', '#000000')")
        conn.execute("INSERT OR IGNORE INTO parts(design_id, name, part_url, part_img_url, ignore_in_inventory) VALUES ('3001', 'Brick 2 x 4', NULL, NULL, 0)")
        conn.execute("INSERT OR IGNORE INTO part_aliases(alias, design_id) VALUES ('3001b', '3001')")
        conn.execute(
            "INSERT INTO inventory(design_id, color_id, quantity, status, container_id) VALUES ('3001', 1, 5, 'loose', ?)",
            (container_id,),
        )
        conn.execute(
            "INSERT INTO sets(set_num, name, year, theme_id, status, added_at) VALUES ('COV-1', 'Cov Set', 2024, NULL, 'loose_parts', ?)",
            (datetime.now(tz=timezone.utc).isoformat(),),
        )
        conn.execute(
            "INSERT OR REPLACE INTO set_parts(set_num, design_id, color_id, quantity) VALUES ('COV-1', '3001', 1, 10)"
        )
        conn.commit()

    # Inventory aggregate endpoints
    assert client.get("/api/v1/inventory/total-count").status_code == 200
    assert client.get("/api/v1/inventory/part-counts").status_code == 200
    assert client.get("/api/v1/inventory/part-color-counts").status_code == 200
    assert client.get("/api/v1/inventory/part-category-counts").status_code == 200

    # Parts endpoints
    assert client.get("/api/v1/parts/3001").status_code == 200
    assert client.get("/api/v1/parts/3001/loose").status_code == 200
    assert client.get("/api/v1/parts/3001/sets").status_code == 200
    assert client.get("/api/v1/parts/3001/aliases").status_code == 200
    assert client.patch("/api/v1/parts/3001", json={"ignore_in_inventory": 1}).status_code == 200

    # Mismatch + storage hierarchy endpoints
    assert client.get("/api/v1/mismatches/summary").status_code == 200
    assert client.get("/api/v1/mismatches").status_code == 200
    assert client.get("/api/v1/mismatches/part-color").status_code == 200
    assert client.get("/api/v1/storage-hierarchy/strategies").status_code == 200


