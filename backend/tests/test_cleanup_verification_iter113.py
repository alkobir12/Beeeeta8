"""
Iteration 113 - Test Data Cleanup Verification
Verifies that the test business account (فرع الاختبار/TEST) has been deleted
and all endpoints are clean of test/demo data.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://canonical-integrity.preview.emergentagent.com').rstrip('/')


class TestCleanupVerification:
    """Verify test data cleanup is complete"""

    def test_biz_accounts_no_test_data(self):
        """Verify /api/biz-accounts has no test accounts (TEST/اختبار)"""
        response = requests.get(f"{BASE_URL}/api/biz-accounts")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Expected list response"
        
        # Check for test data patterns
        test_patterns = ['test', 'اختبار', 'TEST', 'demo']
        test_items = []
        for account in data:
            name = str(account.get('name', '')).lower()
            code = str(account.get('code', ''))
            for pattern in test_patterns:
                if pattern.lower() in name or pattern in code:
                    test_items.append(account)
                    break
        
        assert len(test_items) == 0, f"Found {len(test_items)} test accounts: {test_items}"
        print(f"✓ biz-accounts: {len(data)} accounts, 0 test data")

    def test_deleted_account_not_present(self):
        """Verify the specific deleted account (eb4589a8-cfd1-4132-8665-871b4503a7de) is gone"""
        response = requests.get(f"{BASE_URL}/api/biz-accounts")
        assert response.status_code == 200
        
        data = response.json()
        deleted_id = "eb4589a8-cfd1-4132-8665-871b4503a7de"
        
        found = [a for a in data if a.get('id') == deleted_id]
        assert len(found) == 0, f"Deleted account still present: {found}"
        print(f"✓ Deleted account {deleted_id} confirmed removed")

    def test_customers_no_test_data(self):
        """Verify /api/customers has no test data"""
        response = requests.get(f"{BASE_URL}/api/customers")
        assert response.status_code == 200
        
        data = response.json()
        test_patterns = ['test', 'اختبار', 'demo']
        test_items = [c for c in data if any(p in str(c.get('name', '')).lower() for p in test_patterns)]
        
        assert len(test_items) == 0, f"Found {len(test_items)} test customers"
        print(f"✓ customers: {len(data)} items, 0 test data")

    def test_suppliers_no_test_data(self):
        """Verify /api/suppliers has no test data"""
        response = requests.get(f"{BASE_URL}/api/suppliers")
        assert response.status_code == 200
        
        data = response.json()
        test_patterns = ['test', 'اختبار', 'demo']
        test_items = [c for c in data if any(p in str(c.get('name', '')).lower() for p in test_patterns)]
        
        assert len(test_items) == 0, f"Found {len(test_items)} test suppliers"
        print(f"✓ suppliers: {len(data)} items, 0 test data")

    def test_parts_no_test_data(self):
        """Verify /api/parts has no test data"""
        response = requests.get(f"{BASE_URL}/api/parts")
        assert response.status_code == 200
        
        data = response.json()
        test_patterns = ['test', 'اختبار', 'demo']
        test_items = [c for c in data if any(p in str(c.get('name', '')).lower() for p in test_patterns)]
        
        assert len(test_items) == 0, f"Found {len(test_items)} test parts"
        print(f"✓ parts: {len(data)} items, 0 test data")

    def test_services_no_test_data(self):
        """Verify /api/services has no test data"""
        response = requests.get(f"{BASE_URL}/api/services")
        assert response.status_code == 200
        
        data = response.json()
        test_patterns = ['test', 'اختبار', 'demo']
        test_items = [c for c in data if any(p in str(c.get('name', '')).lower() for p in test_patterns)]
        
        assert len(test_items) == 0, f"Found {len(test_items)} test services"
        print(f"✓ services: {len(data)} items, 0 test data")

    def test_operations_no_test_data(self):
        """Verify /api/operations has no test data in notes"""
        response = requests.get(f"{BASE_URL}/api/operations?limit=500")
        assert response.status_code == 200
        
        data = response.json()
        test_patterns = ['test', 'اختبار', 'demo']
        test_items = [c for c in data if any(p in str(c.get('notes', '')).lower() for p in test_patterns)]
        
        assert len(test_items) == 0, f"Found {len(test_items)} test operations"
        print(f"✓ operations: {len(data)} items, 0 test data")

    def test_vehicles_no_test_data(self):
        """Verify /api/vehicles has no test data"""
        response = requests.get(f"{BASE_URL}/api/vehicles")
        assert response.status_code == 200
        
        data = response.json()
        test_patterns = ['test', 'اختبار', 'demo']
        test_items = [c for c in data if any(p in str(c.get('plateNumber', '')).lower() for p in test_patterns)]
        
        assert len(test_items) == 0, f"Found {len(test_items)} test vehicles"
        print(f"✓ vehicles: {len(data)} items, 0 test data")


class TestEndpointsHealth:
    """Verify all basic endpoints return 200"""

    def test_customers_endpoint(self):
        """GET /api/customers returns 200"""
        response = requests.get(f"{BASE_URL}/api/customers")
        assert response.status_code == 200

    def test_suppliers_endpoint(self):
        """GET /api/suppliers returns 200"""
        response = requests.get(f"{BASE_URL}/api/suppliers")
        assert response.status_code == 200

    def test_parts_endpoint(self):
        """GET /api/parts returns 200"""
        response = requests.get(f"{BASE_URL}/api/parts")
        assert response.status_code == 200

    def test_services_endpoint(self):
        """GET /api/services returns 200"""
        response = requests.get(f"{BASE_URL}/api/services")
        assert response.status_code == 200

    def test_biz_accounts_endpoint(self):
        """GET /api/biz-accounts returns 200"""
        response = requests.get(f"{BASE_URL}/api/biz-accounts")
        assert response.status_code == 200

    def test_operations_endpoint(self):
        """GET /api/operations returns 200"""
        response = requests.get(f"{BASE_URL}/api/operations")
        assert response.status_code == 200

    def test_vehicles_endpoint(self):
        """GET /api/vehicles returns 200"""
        response = requests.get(f"{BASE_URL}/api/vehicles")
        assert response.status_code == 200
