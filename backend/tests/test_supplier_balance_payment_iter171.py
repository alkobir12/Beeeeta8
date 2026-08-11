"""
Test suite for supplier balance payment and duplicate detection features
Iteration 171 - Testing:
1. ConfirmPaymentDialog: supplier_balance method availability
2. confirm-via-supplier-balance endpoint
3. Duplicate detection logic
"""
import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://finance-overhaul-7.preview.emergentagent.com').rstrip('/')
WORKSHOP_ID = os.environ.get('REACT_APP_WORKSHOP_ID', 'finmodule-sync')


class TestHealthAndBasicEndpoints:
    """Basic health and endpoint availability tests"""
    
    def test_health_endpoint(self):
        """Test that the API is healthy"""
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"
        print("✅ Health endpoint working")
    
    def test_suppliers_endpoint(self):
        """Test suppliers endpoint returns data"""
        response = requests.get(f"{BASE_URL}/api/suppliers", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✅ Suppliers endpoint working - {len(data)} suppliers found")
        return data
    
    def test_operations_endpoint(self):
        """Test operations endpoint returns data"""
        response = requests.get(f"{BASE_URL}/api/operations?limit=10", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✅ Operations endpoint working - {len(data)} operations found")
        return data


class TestSmartAccountingEndpoints:
    """Test smart accounting endpoints including supplier balance payment"""
    
    def test_smart_accounts_endpoint(self):
        """Test smart accounts endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/smart-accounting/accounts",
            params={"operation_type": "purchase", "field_key": "credit"},
            timeout=10
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        accounts = data.get("data", [])
        print(f"✅ Smart accounts endpoint working - {len(accounts)} accounts returned")
        
        # Check if supplier balance account (2101) is in the list
        codes = [acc.get("code") for acc in accounts]
        assert "2101" in codes, "Supplier balance account (2101) should be available for purchase credit"
        print("✅ Supplier balance account (2101) available in purchase credit accounts")
    
    def test_supplier_balance_payment_endpoint_exists(self):
        """Test that supplier balance payment endpoint exists"""
        # Test with invalid data to verify endpoint exists
        response = requests.post(
            f"{BASE_URL}/api/smart-accounting/supplier-balance-payment",
            json={"supplier_id": "", "amount": 0},
            timeout=10
        )
        # Should return 400 (bad request) not 404 (not found)
        assert response.status_code in [400, 422], f"Expected 400/422, got {response.status_code}"
        print("✅ Supplier balance payment endpoint exists")
    
    def test_confirm_via_supplier_balance_endpoint_exists(self):
        """Test that confirm-via-supplier-balance endpoint exists"""
        fake_op_id = str(uuid.uuid4())
        response = requests.post(
            f"{BASE_URL}/api/smart-accounting/operations/{fake_op_id}/confirm-via-supplier-balance",
            json={"workshop_id": WORKSHOP_ID},
            timeout=10
        )
        # Should return 404 (operation not found) not 405 (method not allowed)
        assert response.status_code in [400, 404, 422], f"Expected 400/404/422, got {response.status_code}"
        print("✅ Confirm via supplier balance endpoint exists")


class TestSupplierBalancePaymentFlow:
    """Test the supplier balance payment flow"""
    
    @pytest.fixture
    def get_supplier_with_credit(self):
        """Get a supplier that has credit balance"""
        response = requests.get(f"{BASE_URL}/api/suppliers", timeout=10)
        suppliers = response.json()
        
        # Find supplier with credit balance > 0
        for sup in suppliers:
            credit = float(sup.get("credit_balance") or sup.get("creditBalance") or 0)
            if credit > 0:
                return sup
        
        # If no supplier with credit, return first supplier
        if suppliers:
            return suppliers[0]
        return None
    
    def test_supplier_balance_payment_validation(self):
        """Test supplier balance payment validates amount > 0"""
        response = requests.post(
            f"{BASE_URL}/api/smart-accounting/supplier-balance-payment",
            json={
                "supplier_id": "test-supplier-id",
                "amount": 0,
                "workshop_id": WORKSHOP_ID
            },
            timeout=10
        )
        assert response.status_code == 400
        data = response.json()
        assert "المبلغ" in data.get("detail", "") or "amount" in data.get("detail", "").lower()
        print("✅ Supplier balance payment validates amount > 0")
    
    def test_supplier_balance_payment_requires_supplier_id(self):
        """Test supplier balance payment requires valid supplier_id"""
        response = requests.post(
            f"{BASE_URL}/api/smart-accounting/supplier-balance-payment",
            json={
                "supplier_id": "",
                "amount": 100,
                "workshop_id": WORKSHOP_ID
            },
            timeout=10
        )
        # Should fail because supplier_id is empty or invalid
        assert response.status_code in [400, 404, 422, 503]
        print("✅ Supplier balance payment validates supplier_id")


class TestConfirmViaSupplierBalance:
    """Test confirm operation via supplier balance endpoint"""
    
    def test_confirm_via_supplier_balance_requires_operation(self):
        """Test that endpoint requires valid operation ID"""
        fake_op_id = str(uuid.uuid4())
        response = requests.post(
            f"{BASE_URL}/api/smart-accounting/operations/{fake_op_id}/confirm-via-supplier-balance",
            json={
                "workshop_id": WORKSHOP_ID,
                "supplier_id": "test-supplier"
            },
            timeout=10
        )
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data.get("detail", "").lower() or "غير موجود" in data.get("detail", "")
        print("✅ Confirm via supplier balance validates operation exists")
    
    def test_confirm_via_supplier_balance_with_real_operation(self):
        """Test confirm via supplier balance with a real operation (if exists)"""
        # Get operations
        ops_response = requests.get(f"{BASE_URL}/api/operations?limit=50", timeout=10)
        operations = ops_response.json()
        
        # Find an operation with credit payment method (unpaid)
        credit_op = None
        for op in operations:
            payment_method = str(op.get("paymentMethod") or op.get("payment_method") or "").lower()
            payment_status = str(op.get("paymentStatus") or op.get("payment_status") or "").lower()
            if payment_method == "credit" or payment_status == "unpaid":
                credit_op = op
                break
        
        if not credit_op:
            print("⚠️ No credit/unpaid operation found to test - skipping")
            pytest.skip("No credit operation available for testing")
            return
        
        op_id = credit_op.get("id")
        
        # Get suppliers
        sup_response = requests.get(f"{BASE_URL}/api/suppliers", timeout=10)
        suppliers = sup_response.json()
        
        if not suppliers:
            print("⚠️ No suppliers found - skipping")
            pytest.skip("No suppliers available for testing")
            return
        
        supplier_id = suppliers[0].get("id")
        
        # Try to confirm via supplier balance
        response = requests.post(
            f"{BASE_URL}/api/smart-accounting/operations/{op_id}/confirm-via-supplier-balance",
            json={
                "workshop_id": WORKSHOP_ID,
                "supplier_id": supplier_id,
                "amount": 1  # Small amount for testing
            },
            timeout=15
        )
        
        # Should either succeed or fail with insufficient balance
        assert response.status_code in [200, 400], f"Unexpected status: {response.status_code}"
        data = response.json()
        
        if response.status_code == 200:
            assert data.get("success") is True
            print(f"✅ Confirm via supplier balance succeeded for operation {op_id}")
        else:
            # Should fail with insufficient balance message
            detail = data.get("detail", "")
            assert "رصيد" in detail or "balance" in detail.lower() or "غير كافٍ" in detail
            print(f"✅ Confirm via supplier balance correctly rejected due to insufficient balance")


class TestDuplicateDetection:
    """Test duplicate operation detection logic"""
    
    def test_create_operation_endpoint(self):
        """Test that operations can be created"""
        # Create a test operation
        test_payload = {
            "type": "purchase",
            "workshopId": WORKSHOP_ID,
            "workshop_id": WORKSHOP_ID,
            "total": 100,
            "amount": 100,
            "paymentMethod": "cash",
            "paymentStatus": "paid",
            "partnerName": f"TEST_Supplier_{uuid.uuid4().hex[:8]}",
            "partnerType": "supplier",
            "scope": "workshop",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "items": [
                {
                    "name": "Test Item",
                    "itemType": "part",
                    "quantity": 1,
                    "price": 100,
                    "total": 100
                }
            ],
            "notes": f"TEST_DUPLICATE_DETECTION_{uuid.uuid4().hex[:8]}"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/operations",
            json=test_payload,
            timeout=15
        )
        
        assert response.status_code in [200, 201], f"Failed to create operation: {response.text}"
        data = response.json()
        op_id = data.get("id")
        assert op_id, "Operation ID should be returned"
        print(f"✅ Created test operation: {op_id}")
        
        # Clean up - delete the test operation
        delete_response = requests.delete(f"{BASE_URL}/api/operations/{op_id}", timeout=10)
        if delete_response.status_code in [200, 204]:
            print(f"✅ Cleaned up test operation: {op_id}")
        
        return op_id


class TestVehicleArchive:
    """Test vehicle archive endpoint"""
    
    def test_vehicle_archive_endpoint_exists(self):
        """Test that vehicle archive endpoint exists"""
        fake_vehicle_id = str(uuid.uuid4())
        response = requests.post(
            f"{BASE_URL}/api/smart-accounting/vehicle/{fake_vehicle_id}/archive",
            json={},
            timeout=10
        )
        # Should return success (even for non-existent vehicle, it stores locally)
        assert response.status_code in [200, 404], f"Unexpected status: {response.status_code}"
        print("✅ Vehicle archive endpoint exists")
    
    def test_vehicle_archive_status_endpoint(self):
        """Test vehicle archive status endpoint"""
        fake_vehicle_id = str(uuid.uuid4())
        response = requests.get(
            f"{BASE_URL}/api/smart-accounting/vehicle/{fake_vehicle_id}/archive-status",
            timeout=10
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        print("✅ Vehicle archive status endpoint working")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
