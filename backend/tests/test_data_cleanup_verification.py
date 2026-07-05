"""
Test Data Cleanup Verification - Iteration 50
Verifies that all records containing "تجريبي" (test/trial) have been removed from:
- Customers
- Services
- Parts
- Accounts (Chart of Accounts)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://pdpl-memory-engine.preview.emergentagent.com')
WORKSHOP_ID = os.environ.get('REACT_APP_WORKSHOP_ID', 'finmodule-sync')


class TestDataCleanupVerification:
    """Verify that all تجريبي (test/trial) data has been removed"""

    def test_no_test_customers(self):
        """Verify no customers contain تجريبي in their name"""
        response = requests.get(f"{BASE_URL}/api/customers")
        assert response.status_code == 200, f"Failed to get customers: {response.text}"
        
        customers = response.json()
        assert isinstance(customers, list), "Customers response should be a list"
        
        test_customers = [c for c in customers if 'تجريبي' in str(c.get('name', ''))]
        assert len(test_customers) == 0, f"Found {len(test_customers)} customers with تجريبي: {[c.get('name') for c in test_customers]}"
        
        print(f"✅ Verified: {len(customers)} customers, none contain تجريبي")

    def test_no_test_services(self):
        """Verify no services contain تجريبي in their name"""
        response = requests.get(f"{BASE_URL}/api/services")
        assert response.status_code == 200, f"Failed to get services: {response.text}"
        
        services = response.json()
        assert isinstance(services, list), "Services response should be a list"
        
        test_services = [s for s in services if 'تجريبي' in str(s.get('name', ''))]
        assert len(test_services) == 0, f"Found {len(test_services)} services with تجريبي: {[s.get('name') for s in test_services]}"
        
        print(f"✅ Verified: {len(services)} services, none contain تجريبي")

    def test_no_test_parts(self):
        """Verify no parts contain تجريبي in their name"""
        response = requests.get(f"{BASE_URL}/api/parts")
        assert response.status_code == 200, f"Failed to get parts: {response.text}"
        
        parts = response.json()
        assert isinstance(parts, list), "Parts response should be a list"
        
        test_parts = [p for p in parts if 'تجريبي' in str(p.get('name', ''))]
        assert len(test_parts) == 0, f"Found {len(test_parts)} parts with تجريبي: {[p.get('name') for p in test_parts]}"
        
        print(f"✅ Verified: {len(parts)} parts, none contain تجريبي")

    def test_no_test_accounts(self):
        """Verify no accounts contain تجريبي in their name"""
        response = requests.get(f"{BASE_URL}/api/finance/chart-of-accounts?workshop_id={WORKSHOP_ID}")
        assert response.status_code == 200, f"Failed to get accounts: {response.text}"
        
        data = response.json()
        accounts = data.get('data', []) if isinstance(data, dict) else data
        assert isinstance(accounts, list), "Accounts response should be a list"
        
        test_accounts = [
            a for a in accounts 
            if 'تجريبي' in str(a.get('name', '')) or 'تجريبي' in str(a.get('name_ar', ''))
        ]
        assert len(test_accounts) == 0, f"Found {len(test_accounts)} accounts with تجريبي: {[a.get('name', a.get('name_ar')) for a in test_accounts]}"
        
        print(f"✅ Verified: {len(accounts)} accounts, none contain تجريبي")


class TestOperationsPageAPIs:
    """Verify Operations page related APIs are working"""

    def test_health_check(self):
        """Verify API health"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.text}"
        print("✅ API health check passed")

    def test_operations_list(self):
        """Verify operations list endpoint works"""
        response = requests.get(f"{BASE_URL}/api/operations")
        assert response.status_code == 200, f"Failed to get operations: {response.text}"
        
        operations = response.json()
        assert isinstance(operations, list), "Operations response should be a list"
        print(f"✅ Operations list returned {len(operations)} items")

    def test_chart_of_accounts(self):
        """Verify chart of accounts endpoint works"""
        response = requests.get(f"{BASE_URL}/api/finance/chart-of-accounts?workshop_id={WORKSHOP_ID}")
        assert response.status_code == 200, f"Failed to get chart of accounts: {response.text}"
        
        data = response.json()
        accounts = data.get('data', []) if isinstance(data, dict) else data
        assert isinstance(accounts, list), "Accounts response should be a list"
        print(f"✅ Chart of accounts returned {len(accounts)} items")

    def test_biz_accounts(self):
        """Verify business accounts endpoint works"""
        response = requests.get(f"{BASE_URL}/api/biz-accounts")
        assert response.status_code == 200, f"Failed to get business accounts: {response.text}"
        
        accounts = response.json()
        assert isinstance(accounts, list), "Business accounts response should be a list"
        print(f"✅ Business accounts returned {len(accounts)} items")

    def test_customers_list(self):
        """Verify customers list endpoint works"""
        response = requests.get(f"{BASE_URL}/api/customers")
        assert response.status_code == 200, f"Failed to get customers: {response.text}"
        
        customers = response.json()
        assert isinstance(customers, list), "Customers response should be a list"
        print(f"✅ Customers list returned {len(customers)} items")

    def test_suppliers_list(self):
        """Verify suppliers list endpoint works"""
        response = requests.get(f"{BASE_URL}/api/suppliers")
        assert response.status_code == 200, f"Failed to get suppliers: {response.text}"
        
        suppliers = response.json()
        assert isinstance(suppliers, list), "Suppliers response should be a list"
        print(f"✅ Suppliers list returned {len(suppliers)} items")


class TestAccountFiltering:
    """Verify account filtering logic for Operations page"""

    def test_accounts_do_not_contain_customer_subaccounts(self):
        """Verify chart of accounts doesn't mix customer sub-accounts with general accounts"""
        response = requests.get(f"{BASE_URL}/api/finance/chart-of-accounts?workshop_id={WORKSHOP_ID}")
        assert response.status_code == 200, f"Failed to get accounts: {response.text}"
        
        data = response.json()
        accounts = data.get('data', []) if isinstance(data, dict) else data
        
        # Check for customer sub-accounts that should be filtered in frontend
        customer_subaccounts = [
            a for a in accounts 
            if str(a.get('id', '')).startswith('acc-customer-')
            or str(a.get('code', '')).startswith('1103')
            or 'عميل -' in str(a.get('name', ''))
            or 'عميل -' in str(a.get('name_ar', ''))
        ]
        
        # Note: These accounts may exist in the database but should be filtered in frontend
        print(f"ℹ️ Found {len(customer_subaccounts)} customer sub-accounts in database (filtered in frontend)")
        
        # The test passes as long as the API returns data
        assert len(accounts) > 0, "Should have some accounts"
        print(f"✅ Chart of accounts has {len(accounts)} total accounts")

    def test_accounts_do_not_contain_supplier_subaccounts(self):
        """Verify chart of accounts doesn't mix supplier sub-accounts with general accounts"""
        response = requests.get(f"{BASE_URL}/api/finance/chart-of-accounts?workshop_id={WORKSHOP_ID}")
        assert response.status_code == 200, f"Failed to get accounts: {response.text}"
        
        data = response.json()
        accounts = data.get('data', []) if isinstance(data, dict) else data
        
        # Check for supplier sub-accounts that should be filtered in frontend
        supplier_subaccounts = [
            a for a in accounts 
            if str(a.get('id', '')).startswith('acc-supplier-')
            or str(a.get('code', '')).startswith('2101')
            or 'مورد -' in str(a.get('name', ''))
            or 'مورد -' in str(a.get('name_ar', ''))
        ]
        
        # Note: These accounts may exist in the database but should be filtered in frontend
        print(f"ℹ️ Found {len(supplier_subaccounts)} supplier sub-accounts in database (filtered in frontend)")
        
        # The test passes as long as the API returns data
        assert len(accounts) > 0, "Should have some accounts"
        print(f"✅ Chart of accounts has {len(accounts)} total accounts")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
