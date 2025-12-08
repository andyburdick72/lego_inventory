"""Contract tests for inventory CRUD endpoints."""
import os

import httpx
import pytest

pytestmark = pytest.mark.contract

API_BASE = os.getenv("API_BASE_URL") or os.getenv("API_BASE") or ""
SKIP_REASON = "API_BASE_URL or API_BASE not set"


def _skip_if_no_api():
    if not API_BASE:
        pytest.skip(SKIP_REASON)


def _client():
    if not API_BASE:
        pytest.skip(SKIP_REASON)
    return httpx.Client(base_url=API_BASE, timeout=10.0)


def test_get_inventory_item_by_id():
    """Test GET /inventory/loose/{id} endpoint."""
    _skip_if_no_api()
    with _client() as c:
        # First, get a list of loose inventory items
        list_resp = c.get("/inventory/loose")
        assert list_resp.status_code == 200
        items = list_resp.json()
        
        if not items:
            pytest.skip("No loose inventory items available for testing")
        
        # Get the first item's ID
        first_item = items[0]
        assert "id" in first_item
        inventory_id = first_item["id"]
        
        # Test getting the item by ID
        get_resp = c.get(f"/inventory/loose/{inventory_id}")
        assert get_resp.status_code == 200
        data = get_resp.json()
        
        # Verify response structure
        assert "id" in data
        assert data["id"] == inventory_id
        assert "part_id" in data
        assert "color_id" in data
        assert "quantity" in data
        assert "status" in data
        
        # Test 404 for non-existent ID
        not_found_resp = c.get("/inventory/loose/99999999")
        assert not_found_resp.status_code == 404


def test_update_inventory_quantity():
    """Test PATCH /inventory/loose/{id}/quantity endpoint."""
    _skip_if_no_api()
    with _client() as c:
        # Get an existing inventory item
        list_resp = c.get("/inventory/loose")
        assert list_resp.status_code == 200
        items = list_resp.json()
        
        if not items:
            pytest.skip("No loose inventory items available for testing")
        
        first_item = items[0]
        inventory_id = first_item["id"]
        original_quantity = first_item["quantity"]
        
        # Test updating quantity
        new_quantity = original_quantity + 10
        update_resp = c.patch(
            f"/inventory/loose/{inventory_id}/quantity",
            json={"quantity": new_quantity}
        )
        assert update_resp.status_code == 200
        update_data = update_resp.json()
        assert update_data["id"] == inventory_id
        
        # Verify the update
        get_resp = c.get(f"/inventory/loose/{inventory_id}")
        assert get_resp.status_code == 200
        updated_item = get_resp.json()
        assert updated_item["quantity"] == new_quantity
        
        # Restore original quantity
        restore_resp = c.patch(
            f"/inventory/loose/{inventory_id}/quantity",
            json={"quantity": original_quantity}
        )
        assert restore_resp.status_code == 200
        
        # Test setting quantity to 0 (should delete)
        zero_resp = c.patch(
            f"/inventory/loose/{inventory_id}/quantity",
            json={"quantity": 0}
        )
        assert zero_resp.status_code == 200
        
        # Verify item is deleted
        deleted_resp = c.get(f"/inventory/loose/{inventory_id}")
        assert deleted_resp.status_code == 404
        
        # Test validation errors (need a new item since we deleted the first one)
        if len(items) > 1:
            second_item = items[1]
            second_id = second_item["id"]
            invalid_resp = c.patch(
                f"/inventory/loose/{second_id}/quantity",
                json={"quantity": -1}
            )
            assert invalid_resp.status_code == 422
        
        # Test 404 for non-existent ID
        not_found_resp = c.patch(
            "/inventory/loose/99999999/quantity",
            json={"quantity": 5}
        )
        assert not_found_resp.status_code == 404


def test_update_inventory_location():
    """Test PATCH /inventory/loose/{id}/location endpoint."""
    _skip_if_no_api()
    with _client() as c:
        # Get an existing inventory item
        list_resp = c.get("/inventory/loose")
        assert list_resp.status_code == 200
        items = list_resp.json()
        
        if not items:
            pytest.skip("No loose inventory items available for testing")
        
        first_item = items[0]
        inventory_id = first_item["id"]
        original_container_id = first_item.get("container_id")
        
        # Get a container to move to (or None to remove location)
        containers_resp = c.get("/drawers")
        assert containers_resp.status_code == 200
        drawers = containers_resp.json()
        
        if drawers:
            drawer_id = drawers[0]["id"]
            containers_list_resp = c.get(f"/containers?drawer_id={drawer_id}")
            if containers_list_resp.status_code == 200:
                containers = containers_list_resp.json()
                if containers:
                    new_container_id = containers[0]["id"]
                    
                    # Test updating location
                    update_resp = c.patch(
                        f"/inventory/loose/{inventory_id}/location",
                        json={"container_id": new_container_id}
                    )
                    assert update_resp.status_code == 200
                    
                    # Verify the update
                    get_resp = c.get(f"/inventory/loose/{inventory_id}")
                    assert get_resp.status_code == 200
                    updated_item = get_resp.json()
                    assert updated_item["container_id"] == new_container_id
                    
                    # Restore original location
                    restore_resp = c.patch(
                        f"/inventory/loose/{inventory_id}/location",
                        json={"container_id": original_container_id}
                    )
                    assert restore_resp.status_code == 200
        
        # Test removing location (setting to None)
        remove_resp = c.patch(
            f"/inventory/loose/{inventory_id}/location",
            json={"container_id": None}
        )
        assert remove_resp.status_code == 200
        
        # Verify location removed
        get_resp = c.get(f"/inventory/loose/{inventory_id}")
        assert get_resp.status_code == 200
        updated_item = get_resp.json()
        assert updated_item.get("container_id") is None
        
        # Restore original location
        if original_container_id is not None:
            restore_resp = c.patch(
                f"/inventory/loose/{inventory_id}/location",
                json={"container_id": original_container_id}
            )
            assert restore_resp.status_code == 200
        
        # Test 404 for non-existent ID
        not_found_resp = c.patch(
            "/inventory/loose/99999999/location",
            json={"container_id": None}
        )
        assert not_found_resp.status_code == 404


def test_delete_inventory_item():
    """Test DELETE /inventory/loose/{id} endpoint."""
    _skip_if_no_api()
    with _client() as c:
        # Get an existing inventory item
        list_resp = c.get("/inventory/loose")
        assert list_resp.status_code == 200
        items = list_resp.json()
        
        if not items:
            pytest.skip("No loose inventory items available for testing")
        
        # Use the last item to avoid affecting other tests
        item_to_delete = items[-1]
        inventory_id = item_to_delete["id"]
        part_id = item_to_delete["part_id"]
        color_id = item_to_delete["color_id"]
        quantity = item_to_delete["quantity"]
        container_id = item_to_delete.get("container_id")
        
        # Test deletion
        delete_resp = c.delete(f"/inventory/loose/{inventory_id}")
        assert delete_resp.status_code == 200
        delete_data = delete_resp.json()
        assert delete_data["id"] == inventory_id
        
        # Verify item is deleted
        get_resp = c.get(f"/inventory/loose/{inventory_id}")
        assert get_resp.status_code == 404
        
        # Test 404 for non-existent ID
        not_found_resp = c.delete("/inventory/loose/99999999")
        assert not_found_resp.status_code == 404
        
        # Note: We don't restore the deleted item as it's a destructive operation
        # In a real scenario, you might want to recreate it for test isolation


def test_move_inventory():
    """Test POST /inventory/loose/{id}/move endpoint."""
    _skip_if_no_api()
    with _client() as c:
        # Get an existing inventory item with quantity > 1
        list_resp = c.get("/inventory/loose")
        assert list_resp.status_code == 200
        items = list_resp.json()
        
        if not items:
            pytest.skip("No loose inventory items available for testing")
        
        # Find an item with quantity > 1
        source_item = None
        for item in items:
            if item["quantity"] > 1:
                source_item = item
                break
        
        if not source_item:
            pytest.skip("No inventory items with quantity > 1 available for move testing")
        
        inventory_id = source_item["id"]
        original_quantity = source_item["quantity"]
        original_container_id = source_item.get("container_id")
        move_quantity = 1
        
        # Get a different container to move to
        containers_resp = c.get("/drawers")
        assert containers_resp.status_code == 200
        drawers = containers_resp.json()
        
        target_container_id = None
        if drawers:
            drawer_id = drawers[0]["id"]
            containers_list_resp = c.get(f"/containers?drawer_id={drawer_id}")
            if containers_list_resp.status_code == 200:
                containers = containers_list_resp.json()
                # Find a different container or use None
                for container in containers:
                    if container["id"] != original_container_id:
                        target_container_id = container["id"]
                        break
        
        # Test moving inventory
        move_resp = c.post(
            f"/inventory/loose/{inventory_id}/move",
            json={
                "to_container_id": target_container_id,
                "quantity": move_quantity
            }
        )
        assert move_resp.status_code == 200
        move_data = move_resp.json()
        assert move_data["from_id"] == inventory_id
        assert move_data["quantity"] == move_quantity
        assert move_data["to_container_id"] == target_container_id
        
        # Verify source quantity decreased
        get_source_resp = c.get(f"/inventory/loose/{inventory_id}")
        if get_source_resp.status_code == 200:
            # Item still exists with reduced quantity
            source_updated = get_source_resp.json()
            assert source_updated["quantity"] == original_quantity - move_quantity
        elif get_source_resp.status_code == 404:
            # Item was deleted (quantity became 0 after move)
            # This happens when we move all the quantity
            assert original_quantity == move_quantity
        else:
            # Unexpected status code
            assert False, f"Unexpected status code: {get_source_resp.status_code}"
        
        # Test validation errors
        # Test moving more than available (need a new item since we may have modified the first)
        if original_quantity > move_quantity and get_source_resp.status_code == 200:
            remaining_qty = source_updated["quantity"]
            if remaining_qty > 0:
                invalid_resp = c.post(
                    f"/inventory/loose/{inventory_id}/move",
                    json={
                        "to_container_id": target_container_id,
                        "quantity": remaining_qty + 100  # More than available
                    }
                )
                assert invalid_resp.status_code == 422
        
        # Test invalid quantity (need a new item)
        if len(items) > 1:
            second_item = items[1]
            if second_item["quantity"] > 0:
                invalid_qty_resp = c.post(
                    f"/inventory/loose/{second_item['id']}/move",
                    json={
                        "to_container_id": target_container_id,
                        "quantity": 0
                    }
                )
                assert invalid_qty_resp.status_code == 422
        
        # Test 404 for non-existent ID
        not_found_resp = c.post(
            "/inventory/loose/99999999/move",
            json={"to_container_id": None, "quantity": 1}
        )
        assert not_found_resp.status_code == 404

