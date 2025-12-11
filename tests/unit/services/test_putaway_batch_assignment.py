"""Unit tests for putaway batch assignment logic using FastAPI TestClient."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)


def test_batch_assign_empty_assignments():
    """Test batch assign with empty assignments list."""
    response = client.post("/api/v1/putaway/batch-assign", json={"assignments": []})
    assert response.status_code == 422  # Validation error


def test_batch_assign_invalid_format():
    """Test batch assign with invalid request format."""
    response = client.post("/api/v1/putaway/batch-assign", json={})
    assert response.status_code == 422  # Missing assignments field


def test_batch_assign_invalid_container():
    """Test batch assign with invalid container ID."""
    response = client.post(
        "/api/v1/putaway/batch-assign",
        json={
            "assignments": [
                {
                    "design_id": "3001",
                    "color_id": 1,
                    "quantity": 1,
                    "container_id": 999999,  # Invalid container ID
                }
            ]
        },
    )
    # Should return 200 with errors in response
    assert response.status_code == 200
    data = response.json()
    assert "total_requested" in data
    assert "total_assigned" in data
    assert "total_skipped" in data
    assert "assignments" in data
    assert "errors" in data
    assert isinstance(data["errors"], list)
    assert data["total_assigned"] == 0


def test_batch_assign_skip():
    """Test batch assign with skipped assignments (container_id = null)."""
    response = client.post(
        "/api/v1/putaway/batch-assign",
        json={
            "assignments": [
                {
                    "design_id": "3001",
                    "color_id": 1,
                    "quantity": 1,
                    "container_id": None,
                }
            ]
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_requested"] == 1
    assert data["total_skipped"] == 1
    assert data["total_assigned"] == 0
    assert len(data["assignments"]) == 1
    assert data["assignments"][0]["success"] is True
    assert (
        "skip" in data["assignments"][0]["message"].lower()
        or data["assignments"][0]["container_id"] is None
    )


def test_batch_assign_invalid_quantity():
    """Test batch assign with invalid quantity (0 or negative)."""
    # First get a valid container
    drawers_resp = client.get("/api/v1/drawers")
    if drawers_resp.status_code != 200 or not drawers_resp.json():
        pytest.skip("No drawers available for testing")

    drawer_id = drawers_resp.json()[0]["id"]
    containers_resp = client.get(f"/api/v1/containers?drawer_id={drawer_id}")

    if containers_resp.status_code != 200 or not containers_resp.json():
        pytest.skip("No containers available for testing")

    container_id = containers_resp.json()[0]["id"]

    response = client.post(
        "/api/v1/putaway/batch-assign",
        json={
            "assignments": [
                {
                    "design_id": "3001",
                    "color_id": 1,
                    "quantity": 0,  # Invalid quantity
                    "container_id": container_id,
                }
            ]
        },
    )
    # Should return 200 with errors
    assert response.status_code == 200
    data = response.json()
    assert len(data["errors"]) > 0 or data["total_assigned"] == 0


def test_batch_assign_invalid_fields():
    """Test batch assign with missing required fields."""
    response = client.post(
        "/api/v1/putaway/batch-assign",
        json={
            "assignments": [
                {
                    "design_id": "",  # Empty design_id
                    "color_id": 1,
                    "quantity": 1,
                    "container_id": 1,
                }
            ]
        },
    )
    assert response.status_code == 200  # Non-blocking validation
    data = response.json()
    assert data["total_assigned"] == 0
    assert len(data["errors"]) > 0
