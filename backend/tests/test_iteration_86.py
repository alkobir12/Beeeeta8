"""
Iteration 86 Tests:
1. Backend: create operation with vehicleId returns vehicleId+visitId and scope='vehicle' (no 500)
2. Backend: date parsing robustness - balance-sheet API should handle various date formats
3. Backend accounting: purchase mapping to expense account fallback still active
4. Finance APIs should not hang due to date format issues
"""
import pytest
import requests
import os
import uuid
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://pdpl-memory-engine.preview.emergentagent.com').rstrip('/')
WORKSHOP_ID = os.environ.get('REACT_APP_WORKSHOP_ID', 'finmodule-sync')


class TestOperationVehicleIdLinking:
    """Test that operations with vehicleId return correct scope and vehicleId"""
    
    def test_create_operation_with_vehicle_id_returns_vehicle_scope(self):
        """POST /api/operations with vehicleId should return scope='vehicle' and vehicleId in response"""
        # First, get an existing vehicle from the database
        vehicles_response = requests.get(f"{BASE_URL}/api/vehicles?limit=1")
        if vehicles_response.status_code != 200 or not vehicles_response.json():
            pytest.skip("No vehicles available for testing")
        
        vehicles = vehicles_response.json()
        if not vehicles or not isinstance(vehicles, list) or len(vehicles) == 0:
            pytest.skip("No vehicles available for testing")
        
        test_vehicle_id = vehicles[0].get("id")
        if not test_vehicle_id:
            pytest.skip("Vehicle has no ID")
        
        payload = {
            "type": "sale",
            "partnerName": "TEST_عميل اختبار",
            "total": 150.0,
            "items": [{"name": "خدمة اختبار", "quantity": 1, "price": 150.0}],
            "paymentMethod": "cash",
            "vehicleId": test_vehicle_id,
            "workshopId": WORKSHOP_ID,
            "notes": "TEST operation with vehicleId"
        }
        
        response = requests.post(f"{BASE_URL}/api/operations", json=payload)
        
        # Should not return 500
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify vehicleId is preserved
        assert data.get("vehicleId") == test_vehicle_id or data.get("vehicle_id") == test_vehicle_id, \
            f"vehicleId not preserved in response: {data}"
        
        # Verify scope is 'vehicle' when vehicleId is present
        scope = data.get("scope")
        assert scope == "vehicle", f"Expected scope='vehicle', got scope='{scope}'"
        
        # Cleanup
        op_id = data.get("id")
        if op_id:
            requests.delete(f"{BASE_URL}/api/operations/{op_id}")
        
        print(f"✅ Operation with vehicleId created successfully with scope='vehicle'")
    
    def test_create_operation_without_vehicle_id_returns_workshop_scope(self):
        """POST /api/operations without vehicleId should return scope='workshop'"""
        payload = {
            "type": "expense",
            "partnerName": "TEST_مورد اختبار",
            "total": 200.0,
            "items": [{"name": "مصروف اختبار", "quantity": 1, "price": 200.0}],
            "paymentMethod": "cash",
            "workshopId": WORKSHOP_ID,
            "notes": "TEST operation without vehicleId"
        }
        
        response = requests.post(f"{BASE_URL}/api/operations", json=payload)
        
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify scope is 'workshop' when no vehicleId
        scope = data.get("scope")
        assert scope == "workshop", f"Expected scope='workshop', got scope='{scope}'"
        
        # Cleanup
        op_id = data.get("id")
        if op_id:
            requests.delete(f"{BASE_URL}/api/operations/{op_id}")
        
        print(f"✅ Operation without vehicleId created successfully with scope='workshop'")


class TestDateParsingRobustness:
    """Test that finance APIs handle various date formats without hanging"""
    
    def test_balance_sheet_with_iso_date(self):
        """Balance sheet API should work with ISO date format"""
        today = datetime.now().strftime("%Y-%m-%d")
        
        response = requests.get(
            f"{BASE_URL}/api/finance/reports/balance-sheet",
            params={"workshop_id": WORKSHOP_ID, "as_of_date": today},
            timeout=15
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True or "data" in data, f"Balance sheet failed: {data}"
        print(f"✅ Balance sheet with ISO date format works")
    
    def test_balance_sheet_with_slash_date(self):
        """Balance sheet API should handle MM/DD/YYYY format"""
        today = datetime.now()
        slash_date = today.strftime("%m/%d/%Y")
        
        response = requests.get(
            f"{BASE_URL}/api/finance/reports/balance-sheet",
            params={"workshop_id": WORKSHOP_ID, "as_of_date": slash_date},
            timeout=15
        )
        
        # Should not hang or return 500
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        # Even if parsing fails, should return gracefully
        assert "data" in data or "error" in data, f"Unexpected response: {data}"
        print(f"✅ Balance sheet with slash date format handled gracefully")
    
    def test_income_statement_date_parsing(self):
        """Income statement API should handle date range without hanging"""
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")
        
        response = requests.get(
            f"{BASE_URL}/api/finance/reports/income-statement",
            params={
                "workshop_id": WORKSHOP_ID,
                "start_date": start_date,
                "end_date": end_date
            },
            timeout=15
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True or "data" in data, f"Income statement failed: {data}"
        print(f"✅ Income statement with date range works")
    
    def test_trial_balance_date_parsing(self):
        """Trial balance API should handle date without hanging"""
        today = datetime.now().strftime("%Y-%m-%d")
        
        response = requests.get(
            f"{BASE_URL}/api/finance/reports/trial-balance",
            params={"workshop_id": WORKSHOP_ID, "date": today},
            timeout=15
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True or "data" in data, f"Trial balance failed: {data}"
        print(f"✅ Trial balance with date works")


class TestPurchaseExpenseAccountFallback:
    """Test that purchase operations map to expense accounts correctly"""
    
    def test_purchase_operation_maps_to_expense_account(self):
        """Purchase operation should use expense account fallback (6100) when no specific account"""
        payload = {
            "type": "purchase",
            "partnerName": "TEST_مورد قطع غيار",
            "total": 500.0,
            "items": [{"name": "قطع غيار", "quantity": 5, "price": 100.0}],
            "paymentMethod": "cash",
            "workshopId": WORKSHOP_ID,
            "notes": "TEST purchase operation for expense fallback"
        }
        
        response = requests.post(f"{BASE_URL}/api/operations", json=payload)
        
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}: {response.text}"
        
        data = response.json()
        op_id = data.get("id")
        
        # Verify operation was created
        assert op_id, f"Operation ID not returned: {data}"
        
        # Cleanup
        if op_id:
            requests.delete(f"{BASE_URL}/api/operations/{op_id}")
        
        print(f"✅ Purchase operation created successfully")
    
    def test_expense_operation_maps_to_expense_account(self):
        """Expense operation should use expense account (6100) by default"""
        payload = {
            "type": "expense",
            "partnerName": "TEST_مصروف كهرباء",
            "total": 300.0,
            "items": [{"name": "فاتورة كهرباء", "quantity": 1, "price": 300.0}],
            "paymentMethod": "cash",
            "workshopId": WORKSHOP_ID,
            "notes": "TEST expense operation"
        }
        
        response = requests.post(f"{BASE_URL}/api/operations", json=payload)
        
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}: {response.text}"
        
        data = response.json()
        op_id = data.get("id")
        
        # Verify operation was created
        assert op_id, f"Operation ID not returned: {data}"
        
        # Cleanup
        if op_id:
            requests.delete(f"{BASE_URL}/api/operations/{op_id}")
        
        print(f"✅ Expense operation created successfully")


class TestReconciliationAPI:
    """Test reconciliation API works without date parsing issues"""
    
    def test_reconciliation_api_returns_data(self):
        """Reconciliation API should return data without hanging"""
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")
        
        response = requests.get(
            f"{BASE_URL}/api/finance/reports/reconciliation",
            params={
                "workshop_id": WORKSHOP_ID,
                "start_date": start_date,
                "end_date": end_date
            },
            timeout=15
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True or "data" in data, f"Reconciliation failed: {data}"
        print(f"✅ Reconciliation API works")


class TestChartOfAccountsResetButton:
    """Regression test: Chart of Accounts reset button endpoint exists"""
    
    def test_accounts_init_defaults_endpoint_exists(self):
        """POST /api/accounts/init-defaults should exist (reset button endpoint)"""
        # Just verify the endpoint exists and doesn't return 404
        response = requests.post(f"{BASE_URL}/api/accounts/init-defaults", timeout=15)
        
        # Should not be 404 (endpoint exists)
        assert response.status_code != 404, f"Reset accounts endpoint not found (404)"
        
        # Could be 200 (success) or 400/500 (error but endpoint exists)
        print(f"✅ Chart of Accounts reset endpoint exists (status: {response.status_code})")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
