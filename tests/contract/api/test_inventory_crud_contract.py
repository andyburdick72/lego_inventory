"""Contract tests for inventory CRUD endpoints."""
import os

import httpx
import pytest

pytestmark = pytest.mark.contract

if os.getenv("APP_SAFE_MODE") == "true":
    pytest.skip("Inventory CRUD endpoints are disabled in set-centric safe mode.", allow_module_level=True)

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
        
        # Check location reconciliation to avoid items that are required
        reconciliation_resp = c.get("/location-reconciliation/items/loose-parts")
        required_items = set()
        if reconciliation_resp.status_code == 200:
            recon_items = reconciliation_resp.json()
            for item in recon_items:
                required_items.add((item["design_id"], item["color_id"]))
        
        # Find an item that is NOT required for location reconciliation
        test_item = None
        for item in items:
            if (item["part_id"], item["color_id"]) not in required_items:
                test_item = item
                break
        
        if not test_item:
            pytest.skip(
                "No inventory items available for quantity update testing that won't affect location reconciliation. "
                "All items are required by sets."
            )
        
        inventory_id = test_item["id"]
        original_quantity = test_item["quantity"]
        
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
        
        # Test validation errors (use a different item to avoid deleting our test item)
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
        
        # Note: We skip the "set quantity to 0" test to avoid deleting inventory items
        # that would need to be restored. If you need to test deletion, create a
        # dedicated test item that can be safely deleted.


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
        
        # Check location reconciliation to avoid items that are required
        reconciliation_resp = c.get("/location-reconciliation/items/loose-parts")
        required_items = set()
        if reconciliation_resp.status_code == 200:
            recon_items = reconciliation_resp.json()
            for item in recon_items:
                required_items.add((item["design_id"], item["color_id"]))
        
        # Find an item that is NOT required for location reconciliation
        test_item = None
        for item in items:
            if (item["part_id"], item["color_id"]) not in required_items:
                test_item = item
                break
        
        if not test_item:
            pytest.skip(
                "No inventory items available for location update testing that won't affect location reconciliation. "
                "All items are required by sets."
            )
        
        inventory_id = test_item["id"]
        original_container_id = test_item.get("container_id")
        
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
    """
    Test DELETE /inventory/loose/{id} endpoint.
    
    Note: This test is intentionally destructive and does NOT restore the deleted item,
    as there is no API endpoint to create inventory items. To avoid affecting location
    reconciliation, we skip items that are required by sets (which would show up in
    location reconciliation).
    """
    _skip_if_no_api()
    with _client() as c:
        # Get an existing inventory item
        list_resp = c.get("/inventory/loose")
        assert list_resp.status_code == 200
        items = list_resp.json()
        
        if not items:
            pytest.skip("No loose inventory items available for testing")
        
        # Check location reconciliation to find items that are required
        # We'll avoid deleting those to prevent integrity test failures
        reconciliation_resp = c.get("/location-reconciliation/items/loose-parts")
        required_items = set()
        if reconciliation_resp.status_code == 200:
            recon_items = reconciliation_resp.json()
            for item in recon_items:
                required_items.add((item["design_id"], item["color_id"]))
        
        # Find an item that is NOT required for location reconciliation
        item_to_delete = None
        for item in reversed(items):  # Start from the end
            if (item["part_id"], item["color_id"]) not in required_items:
                item_to_delete = item
                break
        
        if not item_to_delete:
            pytest.skip(
                "No inventory items available for deletion testing that won't affect location reconciliation. "
                "All items are required by sets."
            )
        
        inventory_id = item_to_delete["id"]
        part_id = item_to_delete["part_id"]
        color_id = item_to_delete["color_id"]
        
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
        
        # Note: We cannot restore the deleted item as there is no API endpoint to create inventory items.
        # However, we've selected an item that is NOT required for location reconciliation,
        # so it should not cause the integrity test to fail.


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
        
        # Check location reconciliation to avoid items that are required
        reconciliation_resp = c.get("/location-reconciliation/items/loose-parts")
        required_items = set()
        if reconciliation_resp.status_code == 200:
            recon_items = reconciliation_resp.json()
            for item in recon_items:
                required_items.add((item["design_id"], item["color_id"]))
        
        # Find an item with quantity > 1 that is NOT required for location reconciliation
        source_item = None
        for item in items:
            if item["quantity"] > 1 and (item["part_id"], item["color_id"]) not in required_items:
                source_item = item
                break
        
        if not source_item:
            pytest.skip(
                "No inventory items with quantity > 1 available for move testing that won't affect location reconciliation. "
                "All items are required by sets or have quantity <= 1."
            )
        
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
        
        # Store the created inventory ID for cleanup
        created_inventory_id = move_data.get("to_id")
        
        # Verify source quantity decreased
        get_source_resp = c.get(f"/inventory/loose/{inventory_id}")
        source_updated = None
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
        
        # TEARDOWN: Restore original state by moving the inventory back
        # We need to restore the moved quantity back to the original location
        part_id = source_item["part_id"]
        color_id = source_item["color_id"]
        
        # Get all inventory for this part+color to find the one at target location
        part_inventory_resp = c.get(f"/parts/{part_id}/loose")
        if part_inventory_resp.status_code == 200:
            part_items = part_inventory_resp.json()
            # Find the item at the target location (or None if target_container_id is None)
            target_item = None
            for item in part_items:
                if (item["color_id"] == color_id and 
                    item.get("container_id") == target_container_id):
                    target_item = item
                    break
            
            if target_item:
                target_inventory_id = target_item["id"]
                target_quantity = target_item["quantity"]
                
                # Move back exactly the quantity we moved (or all of it if less)
                quantity_to_move_back = min(move_quantity, target_quantity)
                
                if quantity_to_move_back > 0:
                    restore_move_resp = c.post(
                        f"/inventory/loose/{target_inventory_id}/move",
                        json={
                            "to_container_id": original_container_id,
                            "quantity": quantity_to_move_back
                        }
                    )
                    # If restore succeeds, verify source is restored
                    if restore_move_resp.status_code == 200:
                        # Check if source item exists and is restored
                        final_source_resp = c.get(f"/inventory/loose/{inventory_id}")
                        if final_source_resp.status_code == 200:
                            final_source = final_source_resp.json()
                            # Verify location is correct
                            assert final_source.get("container_id") == original_container_id
                        else:
                            # Source was deleted, check if we can find it at original location
                            # and verify quantity is restored
                            part_items_after = c.get(f"/parts/{part_id}/loose").json()
                            found_at_original = None
                            for item in part_items_after:
                                if (item["color_id"] == color_id and 
                                    item.get("container_id") == original_container_id):
                                    found_at_original = item
                                    break
                            # If we found it, the restore worked
                            # If not, the original item might have been deleted and we can't restore it
                        
                        # Clean up: if target item still exists and was created by our test, delete it
                        final_target_resp = c.get(f"/inventory/loose/{target_inventory_id}")
                        if final_target_resp.status_code == 200:
                            final_target = final_target_resp.json()
                            # If quantity is 0, delete it
                            if final_target["quantity"] == 0:
                                c.delete(f"/inventory/loose/{target_inventory_id}")
                            # If quantity matches what we moved and it's a small amount, 
                            # it was likely created by our test - delete it
                            elif (final_target["quantity"] == target_quantity - quantity_to_move_back and
                                  target_quantity == move_quantity and
                                  move_quantity <= 10):  # Only delete if it's a small test quantity
                                c.delete(f"/inventory/loose/{target_inventory_id}")


def test_inventory_integrity_after_all_tests():
    """
    Verify that all inventory CRUD tests have properly cleaned up after themselves.
    
    This test should run after all other inventory CRUD tests to ensure:
    1. Location Reconciliation has 0 items needing reconciliation
    2. Multiple Locations has 0 elements in multiple locations
    
    If this test fails, it means one of the previous tests left inventory in an incorrect state.
    
    This test is optional and can be skipped by setting SKIP_INTEGRITY_CHECK=1.
    Enable it when you want to verify test cleanup: SKIP_INTEGRITY_CHECK=0 pytest ...
    """
    _skip_if_no_api()
    
    # Skip this test unless explicitly enabled
    skip_integrity = os.getenv("SKIP_INTEGRITY_CHECK", "1")
    if skip_integrity.lower() in ("1", "true", "yes"):
        pytest.skip(
            "Inventory integrity check is disabled by default. "
            "Set SKIP_INTEGRITY_CHECK=0 to enable it."
        )
    
    with _client() as c:
        # Check Location Reconciliation - Loose Parts
        loose_parts_resp = c.get("/location-reconciliation/items/loose-parts")
        assert loose_parts_resp.status_code == 200
        loose_parts_items = loose_parts_resp.json()
        assert isinstance(loose_parts_items, list)
        assert len(loose_parts_items) == 0, (
            f"Location Reconciliation (Loose Parts) has {len(loose_parts_items)} items needing reconciliation. "
            f"This indicates inventory was not properly restored after tests. "
            f"Items: {loose_parts_items[:5] if len(loose_parts_items) > 0 else []}"
        )
        
        # Check Location Reconciliation - Teardown
        teardown_resp = c.get("/location-reconciliation/items/teardown")
        assert teardown_resp.status_code == 200
        teardown_items = teardown_resp.json()
        assert isinstance(teardown_items, list)
        assert len(teardown_items) == 0, (
            f"Location Reconciliation (Teardown) has {len(teardown_items)} items needing reconciliation. "
            f"This indicates inventory was not properly restored after tests. "
            f"Items: {teardown_items[:5] if len(teardown_items) > 0 else []}"
        )
        
        # Check Multiple Locations
        multiple_locations_resp = c.get("/inventory/multiple-locations")
        assert multiple_locations_resp.status_code == 200
        multiple_locations_elements = multiple_locations_resp.json()
        assert isinstance(multiple_locations_elements, list)
        assert len(multiple_locations_elements) == 0, (
            f"Multiple Locations has {len(multiple_locations_elements)} elements in multiple locations. "
            f"This indicates inventory was not properly restored after tests. "
            f"Elements: {[{'design_id': e.get('design_id'), 'color_id': e.get('color_id'), 'locations': len(e.get('locations', []))} for e in multiple_locations_elements[:5]] if len(multiple_locations_elements) > 0 else []}"
        )

