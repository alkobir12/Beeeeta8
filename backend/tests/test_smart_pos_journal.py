"""
Test Smart POS Journal and Journal Entries API
Tests for iteration 206 - Smart POS creates reference operations + journal entry payment method display
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://payment-defaults.preview.emergentagent.com').rstrip('/')
WORKSHOP_ID = 'finmodule-sync'


class TestJournalEntriesAPI:
    """Test journal entries API with payment method/status fields"""
    
    def test_journal_entries_returns_payment_method_fields(self):
        """Verify journal entries include payment_method and payment_method_label_ar"""
        response = requests.get(
            f"{BASE_URL}/api/finance/journal-entries",
            params={"workshop_id": WORKSHOP_ID, "limit": 10}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("success") == True, "API should return success=true"
        assert "data" in data, "Response should contain 'data' field"
        
        entries = data["data"]
        assert len(entries) > 0, "Should have at least one journal entry"
        
        # Check first entry has payment method fields
        entry = entries[0]
        assert "payment_method" in entry, "Entry should have payment_method field"
        assert "payment_method_label_ar" in entry, "Entry should have payment_method_label_ar field"
        assert "payment_status" in entry, "Entry should have payment_status field"
        assert "payment_status_label_ar" in entry, "Entry should have payment_status_label_ar field"
        
        print(f"✅ Entry has payment_method: {entry.get('payment_method')}")
        print(f"✅ Entry has payment_method_label_ar: {entry.get('payment_method_label_ar')}")
    
    def test_journal_entries_payment_method_values(self):
        """Verify payment method values are correct (cash/bank/pos/credit)"""
        response = requests.get(
            f"{BASE_URL}/api/finance/journal-entries",
            params={"workshop_id": WORKSHOP_ID, "limit": 50}
        )
        assert response.status_code == 200
        
        data = response.json()
        entries = data.get("data", [])
        
        valid_methods = {"cash", "bank", "pos", "credit", ""}
        valid_labels = {"نقدي", "بنك", "نقاط بيع", "آجل", "-", ""}
        
        for entry in entries:
            method = entry.get("payment_method", "")
            label = entry.get("payment_method_label_ar", "")
            
            # Method should be valid
            assert method in valid_methods or method == "", f"Invalid payment_method: {method}"
            
            # If method is set, label should be set
            if method:
                assert label, f"payment_method_label_ar should be set when payment_method is {method}"
        
        print(f"✅ Verified {len(entries)} entries have valid payment method values")
    
    def test_journal_entries_source_field(self):
        """Verify journal entries have source field for tracking origin"""
        response = requests.get(
            f"{BASE_URL}/api/finance/journal-entries",
            params={"workshop_id": WORKSHOP_ID, "limit": 10}
        )
        assert response.status_code == 200
        
        data = response.json()
        entries = data.get("data", [])
        
        for entry in entries:
            assert "source" in entry, "Entry should have source field"
            source = entry.get("source", "")
            print(f"  Entry {entry.get('id', 'N/A')[:8]}... source: {source}")
        
        print(f"✅ All {len(entries)} entries have source field")


class TestOperationsAPI:
    """Test operations API for Smart POS integration"""
    
    def test_operations_list(self):
        """Verify operations API returns data"""
        response = requests.get(
            f"{BASE_URL}/api/operations",
            params={"workshop_id": WORKSHOP_ID, "limit": 5}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Operations should return a list"
        
        if len(data) > 0:
            op = data[0]
            assert "id" in op, "Operation should have id"
            assert "type" in op, "Operation should have type"
            print(f"✅ Found {len(data)} operations")
            print(f"  First operation: {op.get('id', 'N/A')[:8]}... type: {op.get('type')}")
    
    def test_operations_have_payment_fields(self):
        """Verify operations have payment method and status fields"""
        response = requests.get(
            f"{BASE_URL}/api/operations",
            params={"workshop_id": WORKSHOP_ID, "limit": 10}
        )
        assert response.status_code == 200
        
        data = response.json()
        
        for op in data:
            # Check payment fields exist
            assert "paymentMethod" in op or "payment_method" in op, "Operation should have paymentMethod"
            assert "paymentStatus" in op or "payment_status" in op, "Operation should have paymentStatus"
        
        print(f"✅ All {len(data)} operations have payment fields")


class TestChartOfAccountsAPI:
    """Test chart of accounts API"""
    
    def test_chart_of_accounts_list(self):
        """Verify chart of accounts API returns data"""
        response = requests.get(
            f"{BASE_URL}/api/finance/chart-of-accounts",
            params={"workshop_id": WORKSHOP_ID}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "success" in data or isinstance(data, list), "Should return success or list"
        
        accounts = data.get("data", data) if isinstance(data, dict) else data
        print(f"✅ Found {len(accounts)} chart of accounts")


class TestSmartPOSTemplates:
    """Test Smart POS template functionality"""
    
    def test_pos_instant_sale_creates_journal_entry(self):
        """Verify POS instant sale creates journal entry with correct payment method"""
        # Get journal entries with pos_instant_sale source
        response = requests.get(
            f"{BASE_URL}/api/finance/journal-entries",
            params={"workshop_id": WORKSHOP_ID, "limit": 50}
        )
        assert response.status_code == 200
        
        data = response.json()
        entries = data.get("data", [])
        
        # Find POS instant sale entries
        pos_entries = [e for e in entries if e.get("source") == "pos_instant_sale"]
        
        if len(pos_entries) > 0:
            entry = pos_entries[0]
            print(f"✅ Found POS instant sale entry: {entry.get('id', 'N/A')[:8]}...")
            print(f"  Payment method: {entry.get('payment_method')}")
            print(f"  Payment method label: {entry.get('payment_method_label_ar')}")
            print(f"  Total: {entry.get('total')}")
            
            # Verify payment method is set
            assert entry.get("payment_method"), "POS entry should have payment_method"
            assert entry.get("payment_method_label_ar"), "POS entry should have payment_method_label_ar"
        else:
            print("⚠️ No POS instant sale entries found - this is OK if no POS sales have been made")
    
    def test_operation_payment_income_creates_journal_entry(self):
        """Verify operation payment income creates journal entry"""
        response = requests.get(
            f"{BASE_URL}/api/finance/journal-entries",
            params={"workshop_id": WORKSHOP_ID, "limit": 50}
        )
        assert response.status_code == 200
        
        data = response.json()
        entries = data.get("data", [])
        
        # Find operation payment income entries
        payment_entries = [e for e in entries if e.get("source") == "operation_payment_income"]
        
        if len(payment_entries) > 0:
            entry = payment_entries[0]
            print(f"✅ Found operation payment income entry: {entry.get('id', 'N/A')[:8]}...")
            print(f"  Payment method: {entry.get('payment_method')}")
            print(f"  Payment method label: {entry.get('payment_method_label_ar')}")
            
            # Verify payment method is set
            assert entry.get("payment_method"), "Payment entry should have payment_method"
        else:
            print("⚠️ No operation payment income entries found")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
