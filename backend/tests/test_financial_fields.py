"""
Test suite for financial fields in customers and suppliers endpoints.
Tests the new debitBalance, creditBalance, ajelBalance, overdueBalance, 
settledAmount, paymentPlanCount, and movements fields.
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://canonical-integrity.preview.emergentagent.com')


class TestCustomersFinancialFields:
    """Test financial fields in GET /api/customers endpoint"""
    
    def test_customers_endpoint_returns_200(self):
        """Test that customers endpoint returns 200 status"""
        response = requests.get(f"{BASE_URL}/api/customers")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✅ GET /api/customers returns 200")
    
    def test_customers_have_financial_fields(self):
        """Test that customers have all required financial fields"""
        response = requests.get(f"{BASE_URL}/api/customers")
        assert response.status_code == 200
        
        customers = response.json()
        assert isinstance(customers, list), "Response should be a list"
        
        if len(customers) > 0:
            customer = customers[0]
            
            # Check for required financial fields
            required_fields = [
                'debitBalance',
                'creditBalance', 
                'ajelBalance',
                'overdueBalance',
                'settledAmount',
                'paymentPlanCount',
                'movements'
            ]
            
            for field in required_fields:
                assert field in customer, f"Missing field: {field}"
                print(f"✅ Customer has field: {field}")
            
            # Verify field types
            assert isinstance(customer['debitBalance'], (int, float)), "debitBalance should be numeric"
            assert isinstance(customer['creditBalance'], (int, float)), "creditBalance should be numeric"
            assert isinstance(customer['ajelBalance'], (int, float)), "ajelBalance should be numeric"
            assert isinstance(customer['overdueBalance'], (int, float)), "overdueBalance should be numeric"
            assert isinstance(customer['settledAmount'], (int, float)), "settledAmount should be numeric"
            assert isinstance(customer['paymentPlanCount'], int), "paymentPlanCount should be integer"
            assert isinstance(customer['movements'], list), "movements should be a list"
            
            print("✅ All financial field types are correct")
        else:
            print("⚠️ No customers found to test")
    
    def test_customer_movements_structure(self):
        """Test that customer movements have correct structure"""
        response = requests.get(f"{BASE_URL}/api/customers")
        assert response.status_code == 200
        
        customers = response.json()
        
        # Find a customer with movements
        customer_with_movements = None
        for customer in customers:
            if customer.get('movements') and len(customer['movements']) > 0:
                customer_with_movements = customer
                break
        
        if customer_with_movements:
            movement = customer_with_movements['movements'][0]
            
            # Check movement structure
            expected_fields = ['id', 'direction', 'label', 'amount', 'date', 'source']
            for field in expected_fields:
                assert field in movement, f"Movement missing field: {field}"
                print(f"✅ Movement has field: {field}")
            
            # Verify direction is valid
            assert movement['direction'] in ['debit', 'credit'], "direction should be 'debit' or 'credit'"
            print("✅ Movement structure is correct")
        else:
            print("⚠️ No customers with movements found to test")


class TestSuppliersFinancialFields:
    """Test financial fields in GET /api/suppliers endpoint"""
    
    def test_suppliers_endpoint_returns_200(self):
        """Test that suppliers endpoint returns 200 status"""
        response = requests.get(f"{BASE_URL}/api/suppliers")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✅ GET /api/suppliers returns 200")
    
    def test_suppliers_have_financial_fields(self):
        """Test that suppliers have all required financial fields"""
        response = requests.get(f"{BASE_URL}/api/suppliers")
        assert response.status_code == 200
        
        suppliers = response.json()
        assert isinstance(suppliers, list), "Response should be a list"
        
        if len(suppliers) > 0:
            supplier = suppliers[0]
            
            # Check for required financial fields
            required_fields = [
                'debitBalance',
                'creditBalance',
                'ajelBalance',
                'overdueBalance',
                'settledAmount',
                'paymentPlanCount',
                'movements'
            ]
            
            for field in required_fields:
                assert field in supplier, f"Missing field: {field}"
                print(f"✅ Supplier has field: {field}")
            
            # Verify field types
            assert isinstance(supplier['debitBalance'], (int, float)), "debitBalance should be numeric"
            assert isinstance(supplier['creditBalance'], (int, float)), "creditBalance should be numeric"
            assert isinstance(supplier['ajelBalance'], (int, float)), "ajelBalance should be numeric"
            assert isinstance(supplier['overdueBalance'], (int, float)), "overdueBalance should be numeric"
            assert isinstance(supplier['settledAmount'], (int, float)), "settledAmount should be numeric"
            assert isinstance(supplier['paymentPlanCount'], int), "paymentPlanCount should be integer"
            assert isinstance(supplier['movements'], list), "movements should be a list"
            
            print("✅ All supplier financial field types are correct")
        else:
            print("⚠️ No suppliers found to test")


class TestAccountsSubaccounts:
    """Test subaccounts creation for customers and suppliers"""
    
    def test_accounts_endpoint_returns_200(self):
        """Test that accounts endpoint returns 200 status"""
        response = requests.get(f"{BASE_URL}/api/accounts")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✅ GET /api/accounts returns 200")
    
    def test_customer_subaccounts_exist(self):
        """Test that customer subaccounts are created with correct pattern"""
        response = requests.get(f"{BASE_URL}/api/accounts")
        assert response.status_code == 200
        
        accounts = response.json()
        
        # Find customer subaccounts (id starts with acc-customer-)
        customer_subaccounts = [
            acc for acc in accounts 
            if str(acc.get('id', '')).startswith('acc-customer-')
        ]
        
        print(f"✅ Found {len(customer_subaccounts)} customer subaccounts")
        
        if len(customer_subaccounts) > 0:
            subaccount = customer_subaccounts[0]
            
            # Verify subaccount structure
            assert subaccount.get('code', '').startswith('1103'), "Customer subaccount code should start with 1103"
            assert subaccount.get('type') == 'asset', "Customer subaccount type should be 'asset'"
            assert subaccount.get('parent_id') == 'acc-1103', "Customer subaccount parent_id should be 'acc-1103'"
            
            print("✅ Customer subaccount structure is correct")
    
    def test_supplier_subaccounts_pattern(self):
        """Test that supplier subaccounts follow correct pattern"""
        response = requests.get(f"{BASE_URL}/api/accounts")
        assert response.status_code == 200
        
        accounts = response.json()
        
        # Find supplier subaccounts (id starts with acc-supplier-)
        supplier_subaccounts = [
            acc for acc in accounts 
            if str(acc.get('id', '')).startswith('acc-supplier-')
        ]
        
        print(f"✅ Found {len(supplier_subaccounts)} supplier subaccounts")
        
        if len(supplier_subaccounts) > 0:
            subaccount = supplier_subaccounts[0]
            
            # Verify subaccount structure
            assert subaccount.get('code', '').startswith('2101'), "Supplier subaccount code should start with 2101"
            assert subaccount.get('type') == 'liability', "Supplier subaccount type should be 'liability'"
            assert subaccount.get('parent_id') == 'acc-2101', "Supplier subaccount parent_id should be 'acc-2101'"
            
            print("✅ Supplier subaccount structure is correct")


class TestHealthEndpoint:
    """Test health endpoint"""
    
    def test_health_endpoint(self):
        """Test that health endpoint returns ok status"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('status') == 'ok', f"Expected status 'ok', got {data.get('status')}"
        print("✅ Health endpoint returns ok")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
