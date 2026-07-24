"""
test_operations_validation_iter171.py
Tests for Operations validation rules:
- sale/sale_return requires vehicle or customer
- purchase/purchase_return requires supplier
- payment_order + originalType=receipt_voucher requires vehicle
- payment_order + originalType=settlement requires partner (customer/supplier)
- PAYMENT_METHOD_OPTIONS does NOT contain 'wallet' (محفظة)
- OPERATION_TYPE_OPTIONS includes receipt_voucher, settlement, sale_return
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://stamp-approval-flow.preview.emergentagent.com"


class TestOperationsValidation:
    """Test backend validation rules for operations"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test data"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.test_prefix = f"TEST_{uuid.uuid4().hex[:6]}"

    # ─────────────────────────────────────────────────────────────────────────
    # Test 1: Sale without vehicle/customer => 400
    # ─────────────────────────────────────────────────────────────────────────
    def test_sale_without_vehicle_or_customer_returns_400(self):
        """Sale operation without vehicle or customer should return 400"""
        payload = {
            "type": "sale",
            "accountingAccountId": "026",
            "items": [{"name": "Test Item", "quantity": 1, "price": 100}],
            "paymentMethod": "cash",
            # No vehicleId, no partnerId, no partnerName
        }
        response = self.session.post(f"{BASE_URL}/api/operations", json=payload)
        
        # Should return 400 with validation error
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        data = response.json()
        assert "detail" in data
        # Check Arabic error message
        assert "مركبة" in data["detail"] or "عميل" in data["detail"] or "vehicle" in data["detail"].lower() or "customer" in data["detail"].lower()
        print(f"✓ Sale without vehicle/customer correctly rejected: {data['detail']}")

    # ─────────────────────────────────────────────────────────────────────────
    # Test 2: Sale return without vehicle/customer => 400
    # ─────────────────────────────────────────────────────────────────────────
    def test_sale_return_without_vehicle_or_customer_returns_400(self):
        """Sale return operation without vehicle or customer should return 400"""
        payload = {
            "type": "sale_return",
            "accountingAccountId": "026",
            "items": [{"name": "Test Return Item", "quantity": 1, "price": 50}],
            "paymentMethod": "cash",
            # No vehicleId, no partnerId, no partnerName
        }
        response = self.session.post(f"{BASE_URL}/api/operations", json=payload)
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        data = response.json()
        assert "detail" in data
        print(f"✓ Sale return without vehicle/customer correctly rejected: {data['detail']}")

    # ─────────────────────────────────────────────────────────────────────────
    # Test 3: Purchase without supplier => 400
    # ─────────────────────────────────────────────────────────────────────────
    def test_purchase_without_supplier_returns_400(self):
        """Purchase operation without supplier should return 400"""
        payload = {
            "type": "purchase",
            "accountingAccountId": "036",
            "items": [{"name": "Test Purchase", "quantity": 1, "price": 200}],
            "paymentMethod": "cash",
            # No partnerId, no partnerName
        }
        response = self.session.post(f"{BASE_URL}/api/operations", json=payload)
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        data = response.json()
        assert "detail" in data
        assert "مورد" in data["detail"] or "supplier" in data["detail"].lower()
        print(f"✓ Purchase without supplier correctly rejected: {data['detail']}")

    # ─────────────────────────────────────────────────────────────────────────
    # Test 4: Purchase return without supplier => 400
    # ─────────────────────────────────────────────────────────────────────────
    def test_purchase_return_without_supplier_returns_400(self):
        """Purchase return operation without supplier should return 400"""
        payload = {
            "type": "purchase_return",
            "accountingAccountId": "036",
            "items": [{"name": "Test Purchase Return", "quantity": 1, "price": 100}],
            "paymentMethod": "cash",
            # No partnerId, no partnerName
        }
        response = self.session.post(f"{BASE_URL}/api/operations", json=payload)
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        data = response.json()
        assert "detail" in data
        print(f"✓ Purchase return without supplier correctly rejected: {data['detail']}")

    # ─────────────────────────────────────────────────────────────────────────
    # Test 5: payment_order + originalType=receipt_voucher without vehicle => 400
    # ─────────────────────────────────────────────────────────────────────────
    def test_receipt_voucher_without_vehicle_returns_400(self):
        """Receipt voucher (سند قبض) without vehicle should return 400"""
        payload = {
            "type": "payment_order",
            "originalType": "receipt_voucher",
            "accountingAccountId": "005",
            "paymentAmount": 500,
            "paymentMethod": "cash",
            "partnerType": "customer",
            "partnerName": "Test Customer",
            # No vehicleId
        }
        response = self.session.post(f"{BASE_URL}/api/operations", json=payload)
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        data = response.json()
        assert "detail" in data
        assert "مركبة" in data["detail"] or "vehicle" in data["detail"].lower() or "سند" in data["detail"]
        print(f"✓ Receipt voucher without vehicle correctly rejected: {data['detail']}")

    # ─────────────────────────────────────────────────────────────────────────
    # Test 6: payment_order + originalType=settlement without partner => 400
    # ─────────────────────────────────────────────────────────────────────────
    def test_settlement_without_partner_returns_400(self):
        """Settlement (تسوية) without partner should return 400"""
        payload = {
            "type": "payment_order",
            "originalType": "settlement",
            "accountingAccountId": "005",
            "paymentAmount": 300,
            "paymentMethod": "cash",
            # No partnerId, no partnerName, no partnerType
        }
        response = self.session.post(f"{BASE_URL}/api/operations", json=payload)
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        data = response.json()
        assert "detail" in data
        assert "عميل" in data["detail"] or "مورد" in data["detail"] or "partner" in data["detail"].lower() or "تسوية" in data["detail"]
        print(f"✓ Settlement without partner correctly rejected: {data['detail']}")

    # ─────────────────────────────────────────────────────────────────────────
    # Test 7: settlement with invalid partnerType => 400
    # ─────────────────────────────────────────────────────────────────────────
    def test_settlement_with_invalid_partner_type_returns_400(self):
        """Settlement with invalid partnerType should return 400"""
        payload = {
            "type": "payment_order",
            "originalType": "settlement",
            "accountingAccountId": "005",
            "paymentAmount": 300,
            "paymentMethod": "cash",
            "partnerType": "invalid_type",  # Invalid type
            "partnerName": "Test Partner",
        }
        response = self.session.post(f"{BASE_URL}/api/operations", json=payload)
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        data = response.json()
        assert "detail" in data
        print(f"✓ Settlement with invalid partnerType correctly rejected: {data['detail']}")

    # ─────────────────────────────────────────────────────────────────────────
    # Test 8: Valid sale with customer should succeed
    # ─────────────────────────────────────────────────────────────────────────
    def test_valid_sale_with_customer_succeeds(self):
        """Valid sale operation with customer should succeed"""
        payload = {
            "type": "sale",
            "accountingAccountId": "026",
            "items": [{"name": f"{self.test_prefix}_Item", "quantity": 1, "price": 100}],
            "paymentMethod": "cash",
            "partnerType": "customer",
            "partnerName": f"{self.test_prefix}_Customer",
        }
        response = self.session.post(f"{BASE_URL}/api/operations", json=payload)
        
        # Should succeed (200 or 201)
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}: {response.text}"
        data = response.json()
        assert "id" in data or (isinstance(data, dict) and data.get("success"))
        print(f"✓ Valid sale with customer succeeded")

    # ─────────────────────────────────────────────────────────────────────────
    # Test 9: Valid purchase with supplier should succeed
    # ─────────────────────────────────────────────────────────────────────────
    def test_valid_purchase_with_supplier_succeeds(self):
        """Valid purchase operation with supplier should succeed"""
        payload = {
            "type": "purchase",
            "accountingAccountId": "036",
            "items": [{"name": f"{self.test_prefix}_Purchase", "quantity": 1, "price": 200}],
            "paymentMethod": "cash",
            "partnerType": "supplier",
            "partnerName": f"{self.test_prefix}_Supplier",
        }
        response = self.session.post(f"{BASE_URL}/api/operations", json=payload)
        
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}: {response.text}"
        print(f"✓ Valid purchase with supplier succeeded")

    # ─────────────────────────────────────────────────────────────────────────
    # Test 10: Valid settlement with customer should succeed
    # ─────────────────────────────────────────────────────────────────────────
    def test_valid_settlement_with_customer_succeeds(self):
        """Valid settlement with customer should succeed"""
        payload = {
            "type": "payment_order",
            "originalType": "settlement",
            "accountingAccountId": "005",
            "paymentAmount": 300,
            "paymentMethod": "cash",
            "partnerType": "customer",
            "partnerName": f"{self.test_prefix}_SettlementCustomer",
        }
        response = self.session.post(f"{BASE_URL}/api/operations", json=payload)
        
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}: {response.text}"
        print(f"✓ Valid settlement with customer succeeded")

    # ─────────────────────────────────────────────────────────────────────────
    # Test 11: Valid settlement with supplier should succeed
    # ─────────────────────────────────────────────────────────────────────────
    def test_valid_settlement_with_supplier_succeeds(self):
        """Valid settlement with supplier should succeed"""
        payload = {
            "type": "payment_order",
            "originalType": "settlement",
            "accountingAccountId": "2101",
            "paymentAmount": 400,
            "paymentMethod": "cash",
            "partnerType": "supplier",
            "partnerName": f"{self.test_prefix}_SettlementSupplier",
        }
        response = self.session.post(f"{BASE_URL}/api/operations", json=payload)
        
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}: {response.text}"
        print(f"✓ Valid settlement with supplier succeeded")


class TestOperationsAPIHealth:
    """Test basic API health and endpoints"""

    def test_operations_list_endpoint(self):
        """Test that operations list endpoint is accessible"""
        response = requests.get(f"{BASE_URL}/api/operations", timeout=10)
        assert response.status_code == 200, f"Operations list failed: {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "Expected list response"
        print(f"✓ Operations list endpoint working, returned {len(data)} operations")

    def test_accounts_endpoint(self):
        """Test that accounts endpoint is accessible"""
        response = requests.get(f"{BASE_URL}/api/accounts", timeout=10)
        assert response.status_code == 200, f"Accounts endpoint failed: {response.status_code}"
        print(f"✓ Accounts endpoint working")

    def test_smart_accounting_accounts_endpoint(self):
        """Test smart accounting accounts endpoint"""
        response = requests.get(f"{BASE_URL}/api/smart-accounting/accounts?operation_type=sale&field_key=debit", timeout=10)
        assert response.status_code == 200, f"Smart accounting endpoint failed: {response.status_code}"
        data = response.json()
        assert data.get("success") == True
        print(f"✓ Smart accounting accounts endpoint working")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
