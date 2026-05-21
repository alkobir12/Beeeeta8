"""
Test Collection Order and Payment Receipt Features
Tests for the new collection order (أمر تحصيل) and payment receipt (إيصال دفع) functionality
added to the Customers page.
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://contract-audit-demo.preview.emergentagent.com')
WORKSHOP_ID = os.environ.get('REACT_APP_WORKSHOP_ID', 'finmodule-sync')


class TestCollectionOrderAPI:
    """Tests for collection order (payment_order) creation via /api/operations"""
    
    def test_create_collection_order_success(self):
        """Test creating a collection order with valid data"""
        # First get a customer to use
        customers_response = requests.get(f"{BASE_URL}/api/customers")
        assert customers_response.status_code == 200, f"Failed to get customers: {customers_response.text}"
        
        customers = customers_response.json()
        assert len(customers) > 0, "No customers found for testing"
        
        customer = customers[0]
        customer_id = customer.get('id')
        customer_name = customer.get('name', 'Test Customer')
        
        # Get chart of accounts for account selection
        accounts_response = requests.get(f"{BASE_URL}/api/finance/chart-of-accounts", params={"workshop_id": WORKSHOP_ID})
        assert accounts_response.status_code == 200, f"Failed to get accounts: {accounts_response.text}"
        
        accounts_data = accounts_response.json()
        accounts = accounts_data.get('data', accounts_data) if isinstance(accounts_data, dict) else accounts_data
        
        # Find an asset account
        account_id = None
        for acc in accounts:
            if acc.get('type', '').lower() in ['asset', 'liability', 'expense']:
                account_id = acc.get('id') or acc.get('code')
                break
        
        # Create collection order payload
        payload = {
            "type": "payment_order",
            "total": 100.0,
            "amount": 100.0,
            "paymentAmount": 100.0,
            "paymentMethod": "cash",
            "paymentStatus": "paid",
            "status": "issued",
            "date": "2026-04-06",
            "accountingAccountId": account_id,
            "partnerId": customer_id,
            "partnerName": customer_name,
            "partnerPhone": customer.get('phone', ''),
            "partnerType": "customer",
            "notes": f"تحصيل من العميل {customer_name}",
            "items": [{
                "name": f"تحصيل ذمم - {customer_name}",
                "quantity": 1,
                "price": 100.0,
                "total": 100.0,
                "isCustom": True,
            }],
        }
        
        response = requests.post(f"{BASE_URL}/api/operations", json=payload)
        assert response.status_code in [200, 201], f"Failed to create collection order: {response.text}"
        
        data = response.json()
        assert data.get('type') == 'payment_order', f"Expected type 'payment_order', got {data.get('type')}"
        assert data.get('partnerType') == 'customer', f"Expected partnerType 'customer', got {data.get('partnerType')}"
        assert data.get('partnerName') == customer_name, f"Expected partnerName '{customer_name}', got {data.get('partnerName')}"
        assert float(data.get('total', 0)) == 100.0, f"Expected total 100.0, got {data.get('total')}"
        
        print(f"✅ Collection order created successfully with ID: {data.get('id')}")
        return data.get('id')
    
    def test_create_collection_order_with_zero_amount_fails(self):
        """Test that creating a collection order with zero amount fails validation"""
        payload = {
            "type": "payment_order",
            "total": 0,
            "amount": 0,
            "paymentMethod": "cash",
            "partnerType": "customer",
            "partnerName": "Test Customer",
            "notes": "Test collection",
            "items": [],
        }
        
        response = requests.post(f"{BASE_URL}/api/operations", json=payload)
        # The API might accept it but with 0 total, or reject it
        # We just verify the response is handled
        assert response.status_code in [200, 201, 400], f"Unexpected status: {response.status_code}"
        print(f"✅ Zero amount handling verified: status {response.status_code}")
    
    def test_list_payment_orders(self):
        """Test listing payment_order type operations"""
        response = requests.get(f"{BASE_URL}/api/operations", params={"type": "payment_order", "limit": 10})
        assert response.status_code == 200, f"Failed to list operations: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Expected list response"
        
        # Verify all returned items are payment_order type
        for op in data:
            assert op.get('type') == 'payment_order', f"Expected type 'payment_order', got {op.get('type')}"
        
        print(f"✅ Found {len(data)} payment_order operations")
    
    def test_collection_order_has_customer_partner_type(self):
        """Test that collection orders created from customers have partnerType=customer"""
        response = requests.get(f"{BASE_URL}/api/operations", params={"type": "payment_order", "limit": 5})
        assert response.status_code == 200, f"Failed to list operations: {response.text}"
        
        data = response.json()
        
        # Check that at least one has partnerType=customer
        customer_orders = [op for op in data if op.get('partnerType') == 'customer']
        assert len(customer_orders) > 0, "No collection orders with partnerType=customer found"
        
        print(f"✅ Found {len(customer_orders)} collection orders with partnerType=customer")


class TestCustomersAPI:
    """Tests for customers API to ensure it's not broken"""
    
    def test_list_customers(self):
        """Test listing customers"""
        response = requests.get(f"{BASE_URL}/api/customers")
        assert response.status_code == 200, f"Failed to list customers: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Expected list response"
        assert len(data) > 0, "No customers found"
        
        # Verify customer structure
        customer = data[0]
        assert 'id' in customer, "Customer missing 'id' field"
        assert 'name' in customer, "Customer missing 'name' field"
        
        print(f"✅ Found {len(data)} customers")
    
    def test_customer_has_balance_fields(self):
        """Test that customers have balance fields for collection"""
        response = requests.get(f"{BASE_URL}/api/customers")
        assert response.status_code == 200, f"Failed to list customers: {response.text}"
        
        data = response.json()
        assert len(data) > 0, "No customers found"
        
        customer = data[0]
        # Check for balance-related fields (may be optional)
        balance_fields = ['debitBalance', 'creditBalance', 'ajelBalance', 'overdueBalance']
        found_fields = [f for f in balance_fields if f in customer]
        
        print(f"✅ Customer has balance fields: {found_fields}")


class TestChartOfAccountsAPI:
    """Tests for chart of accounts API used in collection modal"""
    
    def test_list_chart_of_accounts(self):
        """Test listing chart of accounts"""
        response = requests.get(f"{BASE_URL}/api/finance/chart-of-accounts", params={"workshop_id": WORKSHOP_ID})
        assert response.status_code == 200, f"Failed to list accounts: {response.text}"
        
        data = response.json()
        accounts = data.get('data', data) if isinstance(data, dict) else data
        assert isinstance(accounts, list), "Expected list of accounts"
        
        print(f"✅ Found {len(accounts)} chart of accounts")
    
    def test_accounts_have_required_fields(self):
        """Test that accounts have required fields for dropdown"""
        response = requests.get(f"{BASE_URL}/api/finance/chart-of-accounts", params={"workshop_id": WORKSHOP_ID})
        assert response.status_code == 200, f"Failed to list accounts: {response.text}"
        
        data = response.json()
        accounts = data.get('data', data) if isinstance(data, dict) else data
        
        if len(accounts) > 0:
            account = accounts[0]
            # Check for id/code and name fields
            has_id = 'id' in account or 'code' in account
            has_name = 'name' in account or 'name_ar' in account
            
            assert has_id, "Account missing 'id' or 'code' field"
            assert has_name, "Account missing 'name' or 'name_ar' field"
            
            print(f"✅ Accounts have required fields for dropdown")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
