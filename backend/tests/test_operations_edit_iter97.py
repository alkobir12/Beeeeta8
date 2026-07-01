"""
Test operations edit functionality - Iteration 97
Tests:
1. PUT /api/operations/{id} returns 404 for non-existent operation ID
2. PUT /api/operations/{id} successfully updates existing operation
3. GET /api/operations/{id} returns updated data after PUT
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://erp-compliance-check.preview.emergentagent.com').rstrip('/')


class TestOperationsEdit:
    """Test operations edit/update functionality"""

    def test_put_operation_returns_404_for_nonexistent_id(self):
        """PUT /api/operations/{id} should return 404 for non-existent operation ID"""
        # Use a valid UUID format but non-existent ID
        nonexistent_id = "00000000-0000-0000-0000-000000000000"
        
        response = requests.put(
            f"{BASE_URL}/api/operations/{nonexistent_id}",
            json={"type": "purchase", "total": 100},
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        # Should return 404 Not Found
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        
        # Check response contains "not found" message
        data = response.json()
        assert "not found" in str(data.get("detail", "")).lower(), f"Expected 'not found' in response: {data}"
        print(f"✅ PUT /api/operations/{nonexistent_id} correctly returns 404")

    def test_put_operation_returns_error_for_invalid_uuid(self):
        """PUT /api/operations/{id} should return error for invalid UUID format"""
        invalid_id = "not-a-valid-uuid"
        
        response = requests.put(
            f"{BASE_URL}/api/operations/{invalid_id}",
            json={"type": "purchase", "total": 100},
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        # Should return 500 or 400 for invalid UUID
        assert response.status_code in [400, 500, 422], f"Expected 400/500/422, got {response.status_code}: {response.text}"
        print(f"✅ PUT /api/operations/{invalid_id} correctly returns error for invalid UUID")

    def test_create_and_update_operation(self):
        """Create an operation, update it, and verify the update"""
        # First, create a new operation
        create_payload = {
            "type": "purchase",
            "partnerName": "TEST_Supplier_Edit_Test",
            "partnerType": "supplier",
            "items": [
                {"name": "TEST_Item_Original", "quantity": 1, "price": 100, "total": 100}
            ],
            "paymentMethod": "cash",
            "paymentStatus": "paid",
            "notes": "TEST_Original_Notes",
            "date": "2026-04-08"
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/operations",
            json=create_payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        assert create_response.status_code in [200, 201], f"Failed to create operation: {create_response.text}"
        created_op = create_response.json()
        op_id = created_op.get("id")
        assert op_id, f"Created operation has no ID: {created_op}"
        print(f"✅ Created operation with ID: {op_id}")
        
        # Now update the operation
        update_payload = {
            "partnerName": "TEST_Supplier_Updated",
            "items": [
                {"name": "TEST_Item_Updated", "quantity": 2, "price": 150, "total": 300}
            ],
            "notes": "TEST_Updated_Notes"
        }
        
        update_response = requests.put(
            f"{BASE_URL}/api/operations/{op_id}",
            json=update_payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        assert update_response.status_code == 200, f"Failed to update operation: {update_response.text}"
        updated_op = update_response.json()
        print(f"✅ Updated operation: {updated_op.get('id')}")
        
        # Verify the update by fetching the operation
        get_response = requests.get(
            f"{BASE_URL}/api/operations/{op_id}",
            timeout=30
        )
        
        assert get_response.status_code == 200, f"Failed to get operation: {get_response.text}"
        fetched_op = get_response.json()
        
        # Verify updated fields
        assert fetched_op.get("partnerName") == "TEST_Supplier_Updated", f"partnerName not updated: {fetched_op}"
        assert fetched_op.get("notes") == "TEST_Updated_Notes", f"notes not updated: {fetched_op}"
        print(f"✅ Verified operation update - partnerName: {fetched_op.get('partnerName')}, notes: {fetched_op.get('notes')}")
        
        # Cleanup - delete the test operation
        delete_response = requests.delete(
            f"{BASE_URL}/api/operations/{op_id}",
            timeout=30
        )
        assert delete_response.status_code in [200, 204], f"Failed to delete operation: {delete_response.text}"
        print(f"✅ Cleaned up test operation: {op_id}")

    def test_update_operation_items(self):
        """Test updating operation items specifically"""
        # Create operation with initial items
        create_payload = {
            "type": "sale",
            "partnerName": "TEST_Customer_Items_Test",
            "partnerType": "customer",
            "items": [
                {"name": "TEST_Item_1", "quantity": 1, "price": 50, "total": 50},
                {"name": "TEST_Item_2", "quantity": 2, "price": 25, "total": 50}
            ],
            "paymentMethod": "cash",
            "paymentStatus": "paid",
            "date": "2026-04-08"
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/operations",
            json=create_payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        assert create_response.status_code in [200, 201], f"Failed to create operation: {create_response.text}"
        created_op = create_response.json()
        op_id = created_op.get("id")
        print(f"✅ Created operation with ID: {op_id}")
        
        # Update with new items
        update_payload = {
            "items": [
                {"name": "TEST_Item_Updated_1", "quantity": 3, "price": 100, "total": 300},
                {"name": "TEST_Item_Updated_2", "quantity": 1, "price": 200, "total": 200},
                {"name": "TEST_Item_New", "quantity": 5, "price": 10, "total": 50}
            ],
            "subtotal": 550,
            "total": 550
        }
        
        update_response = requests.put(
            f"{BASE_URL}/api/operations/{op_id}",
            json=update_payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        assert update_response.status_code == 200, f"Failed to update operation: {update_response.text}"
        print(f"✅ Updated operation items")
        
        # Verify the update
        get_response = requests.get(
            f"{BASE_URL}/api/operations/{op_id}",
            timeout=30
        )
        
        assert get_response.status_code == 200, f"Failed to get operation: {get_response.text}"
        fetched_op = get_response.json()
        
        # Verify items count
        items = fetched_op.get("items", [])
        assert len(items) == 3, f"Expected 3 items, got {len(items)}: {items}"
        print(f"✅ Verified items count: {len(items)}")
        
        # Cleanup
        delete_response = requests.delete(
            f"{BASE_URL}/api/operations/{op_id}",
            timeout=30
        )
        assert delete_response.status_code in [200, 204], f"Failed to delete operation: {delete_response.text}"
        print(f"✅ Cleaned up test operation: {op_id}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
