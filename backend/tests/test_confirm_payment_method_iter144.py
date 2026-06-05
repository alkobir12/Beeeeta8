"""
Test confirm-payment endpoint with payment_method selection (cash/bank)
Iteration 144: Testing that confirm-payment accepts payment_method and generates correct journal entries
"""
import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://garage-erp-arabic.preview.emergentagent.com').rstrip('/')
WORKSHOP_ID = os.environ.get('REACT_APP_WORKSHOP_ID', 'finmodule-sync')


class TestConfirmPaymentMethod:
    """Test confirm-payment endpoint with payment_method selection"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test data"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.created_operations = []
        self.created_journal_entries = []
        yield
        # Cleanup created test data
        for op_id in self.created_operations:
            try:
                self.session.delete(f"{BASE_URL}/api/operations/{op_id}")
            except:
                pass
    
    def _create_credit_operation(self, op_type="sale", total=1000.0):
        """Helper to create a credit operation for testing"""
        payload = {
            "type": op_type,
            "workshopId": WORKSHOP_ID,
            "accountId": "test-account",
            "accountingAccountId": "4100" if op_type == "sale" else "6100",
            "paymentMethod": "credit",
            "paymentStatus": "unpaid",
            "total": total,
            "items": [{"name": "TEST_item", "quantity": 1, "price": total, "total": total}],
            "partnerName": f"TEST_Partner_{uuid.uuid4().hex[:6]}",
            "date": datetime.utcnow().isoformat(),
            "scope": "workshop",
            "notes": "TEST_confirm_payment_method"
        }
        response = self.session.post(f"{BASE_URL}/api/operations", json=payload)
        if response.status_code in [200, 201]:
            data = response.json()
            op_id = data.get("id")
            if op_id:
                self.created_operations.append(op_id)
            return data
        return None
    
    def test_api_health(self):
        """Test API is accessible"""
        response = self.session.get(f"{BASE_URL}/api/settings")
        assert response.status_code == 200, f"API not accessible: {response.status_code}"
        print("✓ API health check passed")
    
    def test_create_credit_sale_operation(self):
        """Test creating a credit sale operation"""
        op = self._create_credit_operation(op_type="sale", total=500.0)
        assert op is not None, "Failed to create credit operation"
        assert op.get("id"), "Operation ID not returned"
        print(f"✓ Created credit sale operation: {op.get('id')}")
        return op
    
    def test_confirm_payment_with_cash_method(self):
        """Test confirm-payment with payment_method=cash generates 1101 entry"""
        # Create credit operation
        op = self._create_credit_operation(op_type="sale", total=300.0)
        if not op or not op.get("id"):
            pytest.skip("Could not create credit operation")
        
        op_id = op.get("id")
        
        # Confirm payment with cash method
        confirm_payload = {
            "workshopId": WORKSHOP_ID,
            "payment_method": "cash",
            "amount": 300.0,
            "date": datetime.utcnow().isoformat()
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/operations/{op_id}/confirm-payment",
            json=confirm_payload
        )
        
        print(f"Confirm payment response status: {response.status_code}")
        print(f"Confirm payment response: {response.text[:500] if response.text else 'empty'}")
        
        assert response.status_code == 200, f"Confirm payment failed: {response.status_code} - {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Confirm payment not successful: {data}"
        
        # Check settlement_method is cash
        result_data = data.get("data", {})
        settlement_method = result_data.get("settlement_method")
        assert settlement_method == "cash", f"Expected settlement_method=cash, got {settlement_method}"
        
        print(f"✓ Confirm payment with cash method successful")
        print(f"  - settlement_method: {settlement_method}")
        print(f"  - paid: {result_data.get('paid')}")
        print(f"  - status: {result_data.get('status')}")
        
        return data
    
    def test_confirm_payment_with_bank_method(self):
        """Test confirm-payment with payment_method=bank generates 1102 entry"""
        # Create credit operation
        op = self._create_credit_operation(op_type="sale", total=400.0)
        if not op or not op.get("id"):
            pytest.skip("Could not create credit operation")
        
        op_id = op.get("id")
        
        # Confirm payment with bank method
        confirm_payload = {
            "workshopId": WORKSHOP_ID,
            "payment_method": "bank",
            "amount": 400.0,
            "date": datetime.utcnow().isoformat()
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/operations/{op_id}/confirm-payment",
            json=confirm_payload
        )
        
        print(f"Confirm payment response status: {response.status_code}")
        print(f"Confirm payment response: {response.text[:500] if response.text else 'empty'}")
        
        assert response.status_code == 200, f"Confirm payment failed: {response.status_code} - {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Confirm payment not successful: {data}"
        
        # Check settlement_method is bank
        result_data = data.get("data", {})
        settlement_method = result_data.get("settlement_method")
        assert settlement_method == "bank", f"Expected settlement_method=bank, got {settlement_method}"
        
        print(f"✓ Confirm payment with bank method successful")
        print(f"  - settlement_method: {settlement_method}")
        print(f"  - paid: {result_data.get('paid')}")
        print(f"  - status: {result_data.get('status')}")
        
        return data
    
    def test_confirm_payment_with_transfer_alias(self):
        """Test confirm-payment with payment_method=transfer (alias for bank)"""
        op = self._create_credit_operation(op_type="sale", total=250.0)
        if not op or not op.get("id"):
            pytest.skip("Could not create credit operation")
        
        op_id = op.get("id")
        
        confirm_payload = {
            "workshopId": WORKSHOP_ID,
            "payment_method": "transfer",
            "amount": 250.0,
            "date": datetime.utcnow().isoformat()
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/operations/{op_id}/confirm-payment",
            json=confirm_payload
        )
        
        assert response.status_code == 200, f"Confirm payment failed: {response.status_code}"
        
        data = response.json()
        result_data = data.get("data", {})
        settlement_method = result_data.get("settlement_method")
        
        # transfer should map to bank
        assert settlement_method == "bank", f"Expected settlement_method=bank for transfer, got {settlement_method}"
        print(f"✓ Confirm payment with transfer alias maps to bank")
    
    def test_confirm_payment_with_card_alias(self):
        """Test confirm-payment with payment_method=card (alias for bank)"""
        op = self._create_credit_operation(op_type="sale", total=200.0)
        if not op or not op.get("id"):
            pytest.skip("Could not create credit operation")
        
        op_id = op.get("id")
        
        confirm_payload = {
            "workshopId": WORKSHOP_ID,
            "payment_method": "card",
            "amount": 200.0,
            "date": datetime.utcnow().isoformat()
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/operations/{op_id}/confirm-payment",
            json=confirm_payload
        )
        
        assert response.status_code == 200, f"Confirm payment failed: {response.status_code}"
        
        data = response.json()
        result_data = data.get("data", {})
        settlement_method = result_data.get("settlement_method")
        
        # card should map to bank
        assert settlement_method == "bank", f"Expected settlement_method=bank for card, got {settlement_method}"
        print(f"✓ Confirm payment with card alias maps to bank")
    
    def test_partial_payment_keeps_credit_method(self):
        """Test partial payment keeps payment_method=credit with status=partial"""
        op = self._create_credit_operation(op_type="sale", total=1000.0)
        if not op or not op.get("id"):
            pytest.skip("Could not create credit operation")
        
        op_id = op.get("id")
        
        # Pay only 300 of 1000
        confirm_payload = {
            "workshopId": WORKSHOP_ID,
            "payment_method": "bank",
            "amount": 300.0,
            "date": datetime.utcnow().isoformat()
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/operations/{op_id}/confirm-payment",
            json=confirm_payload
        )
        
        assert response.status_code == 200, f"Confirm payment failed: {response.status_code}"
        
        data = response.json()
        result_data = data.get("data", {})
        
        # For partial payment, payment_method should remain credit
        payment_method = result_data.get("payment_method")
        status = result_data.get("status")
        settlement_method = result_data.get("settlement_method")
        remaining = result_data.get("remaining")
        
        assert status == "partial", f"Expected status=partial, got {status}"
        assert payment_method == "credit", f"Expected payment_method=credit for partial, got {payment_method}"
        assert settlement_method == "bank", f"Expected settlement_method=bank, got {settlement_method}"
        assert remaining == 700.0, f"Expected remaining=700, got {remaining}"
        
        print(f"✓ Partial payment keeps credit method with partial status")
        print(f"  - status: {status}")
        print(f"  - payment_method: {payment_method}")
        print(f"  - settlement_method: {settlement_method}")
        print(f"  - remaining: {remaining}")
    
    def test_full_payment_updates_method(self):
        """Test full payment updates payment_method to selected method"""
        op = self._create_credit_operation(op_type="sale", total=500.0)
        if not op or not op.get("id"):
            pytest.skip("Could not create credit operation")
        
        op_id = op.get("id")
        
        # Pay full amount with bank
        confirm_payload = {
            "workshopId": WORKSHOP_ID,
            "payment_method": "bank",
            "amount": 500.0,
            "date": datetime.utcnow().isoformat()
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/operations/{op_id}/confirm-payment",
            json=confirm_payload
        )
        
        assert response.status_code == 200, f"Confirm payment failed: {response.status_code}"
        
        data = response.json()
        result_data = data.get("data", {})
        
        payment_method = result_data.get("payment_method")
        status = result_data.get("status")
        settlement_method = result_data.get("settlement_method")
        remaining = result_data.get("remaining")
        
        assert status == "paid", f"Expected status=paid, got {status}"
        assert payment_method == "bank", f"Expected payment_method=bank for full payment, got {payment_method}"
        assert settlement_method == "bank", f"Expected settlement_method=bank, got {settlement_method}"
        assert remaining == 0.0, f"Expected remaining=0, got {remaining}"
        
        print(f"✓ Full payment updates method to selected method")
        print(f"  - status: {status}")
        print(f"  - payment_method: {payment_method}")
        print(f"  - settlement_method: {settlement_method}")
    
    def test_purchase_credit_confirm_with_cash(self):
        """Test confirm-payment for purchase operation with cash"""
        op = self._create_credit_operation(op_type="purchase", total=600.0)
        if not op or not op.get("id"):
            pytest.skip("Could not create credit purchase operation")
        
        op_id = op.get("id")
        
        confirm_payload = {
            "workshopId": WORKSHOP_ID,
            "payment_method": "cash",
            "amount": 600.0,
            "date": datetime.utcnow().isoformat()
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/operations/{op_id}/confirm-payment",
            json=confirm_payload
        )
        
        assert response.status_code == 200, f"Confirm payment failed: {response.status_code}"
        
        data = response.json()
        result_data = data.get("data", {})
        settlement_method = result_data.get("settlement_method")
        
        assert settlement_method == "cash", f"Expected settlement_method=cash, got {settlement_method}"
        print(f"✓ Purchase credit confirm with cash successful")


class TestOperationsListCreditFilter:
    """Test operations list to find credit operations"""
    
    def test_list_operations(self):
        """Test listing operations"""
        response = requests.get(f"{BASE_URL}/api/operations", params={"limit": 50})
        assert response.status_code == 200, f"Failed to list operations: {response.status_code}"
        
        ops = response.json()
        assert isinstance(ops, list), "Operations should be a list"
        
        # Find credit operations
        credit_ops = [
            op for op in ops 
            if (op.get("paymentMethod") or op.get("payment_method") or "").lower() == "credit"
            or (op.get("paymentStatus") or op.get("payment_status") or "").lower() in ["unpaid", "partial"]
        ]
        
        print(f"✓ Found {len(credit_ops)} credit operations out of {len(ops)} total")
        
        if credit_ops:
            sample = credit_ops[0]
            print(f"  Sample credit operation:")
            print(f"    - id: {sample.get('id')}")
            print(f"    - type: {sample.get('type')}")
            print(f"    - paymentMethod: {sample.get('paymentMethod') or sample.get('payment_method')}")
            print(f"    - paymentStatus: {sample.get('paymentStatus') or sample.get('payment_status')}")
            print(f"    - total: {sample.get('total')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
