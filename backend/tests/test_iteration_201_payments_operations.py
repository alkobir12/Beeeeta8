"""
Iteration 201 - Payments ↔ Operations Integration Tests
Tests:
1. GET /api/operations returns paymentMethod/paymentStatus/totalPaid/balance from linked visit
2. GET /api/operations/{id} returns same payment fields
3. Journal entries with source=visit_receipt_voucher exist with proper tags
4. Operations page can read operations without breaking
"""

import pytest
import requests
import os
import json

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://workshop-operator.preview.emergentagent.com')
WORKSHOP_ID = os.environ.get('REACT_APP_WORKSHOP_ID', 'finmodule-sync')

# Known visit ID from main agent context
KNOWN_VISIT_ID = "ef0a3030-d377-4a96-ba7f-acf302cf3ad4"


class TestOperationsPaymentIntegration:
    """Test operations API returns payment data from linked visits"""

    def test_operations_list_returns_payment_fields(self):
        """GET /api/operations should return paymentMethod, paymentStatus, totalPaid, balance"""
        response = requests.get(f"{BASE_URL}/api/operations", params={"limit": 10})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Expected list response"
        
        if len(data) > 0:
            op = data[0]
            # Check that payment fields exist (may be null for some operations)
            assert "paymentMethod" in op, "Missing paymentMethod field"
            assert "paymentStatus" in op, "Missing paymentStatus field"
            assert "totalPaid" in op, "Missing totalPaid field"
            assert "balance" in op, "Missing balance field"
            print(f"✅ Operations list returns payment fields: paymentMethod={op.get('paymentMethod')}, paymentStatus={op.get('paymentStatus')}, totalPaid={op.get('totalPaid')}, balance={op.get('balance')}")

    def test_known_visit_operation_has_correct_payment_data(self):
        """GET /api/operations/{id} for known visit should return correct payment data"""
        response = requests.get(f"{BASE_URL}/api/operations/{KNOWN_VISIT_ID}")
        
        if response.status_code == 404:
            pytest.skip(f"Known visit operation {KNOWN_VISIT_ID} not found - may have been cleaned up")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        op = response.json()
        
        # Verify payment fields from visit
        assert op.get("paymentMethod") == "cash", f"Expected paymentMethod='cash', got {op.get('paymentMethod')}"
        assert op.get("paymentStatus") == "paid_full", f"Expected paymentStatus='paid_full', got {op.get('paymentStatus')}"
        assert op.get("totalPaid") == 3000.0, f"Expected totalPaid=3000.0, got {op.get('totalPaid')}"
        assert op.get("balance") == 0.0, f"Expected balance=0.0, got {op.get('balance')}"
        
        print(f"✅ Known visit operation has correct payment data: paymentMethod={op.get('paymentMethod')}, paymentStatus={op.get('paymentStatus')}, totalPaid={op.get('totalPaid')}, balance={op.get('balance')}")

    def test_operation_get_returns_visit_linked_fields(self):
        """GET /api/operations/{id} should return visitId and vehicleId"""
        response = requests.get(f"{BASE_URL}/api/operations/{KNOWN_VISIT_ID}")
        
        if response.status_code == 404:
            pytest.skip(f"Known visit operation {KNOWN_VISIT_ID} not found")
        
        assert response.status_code == 200
        op = response.json()
        
        # Verify visit linkage
        assert op.get("visitId") == KNOWN_VISIT_ID, f"Expected visitId={KNOWN_VISIT_ID}, got {op.get('visitId')}"
        assert op.get("vehicleId"), "Expected vehicleId to be set"
        assert op.get("scope") == "vehicle", f"Expected scope='vehicle', got {op.get('scope')}"
        
        print(f"✅ Operation has visit linkage: visitId={op.get('visitId')}, vehicleId={op.get('vehicleId')}, scope={op.get('scope')}")


class TestJournalEntriesVisitReceipt:
    """Test journal entries with source=visit_receipt_voucher"""

    def test_journal_entries_with_visit_receipt_source_exist(self):
        """Journal entries with source=visit_receipt_voucher should exist"""
        response = requests.get(
            f"{BASE_URL}/api/finance/journal-entries",
            params={"workshop_id": WORKSHOP_ID, "limit": 100}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        entries = data.get("data", data) if isinstance(data, dict) else data
        
        assert isinstance(entries, list), "Expected list of entries"
        
        visit_receipts = [e for e in entries if e.get("source") == "visit_receipt_voucher"]
        
        print(f"Total journal entries: {len(entries)}")
        print(f"Visit receipt voucher entries: {len(visit_receipts)}")
        
        # At least one visit receipt voucher should exist
        assert len(visit_receipts) >= 1, "Expected at least one journal entry with source=visit_receipt_voucher"
        
        print(f"✅ Found {len(visit_receipts)} journal entries with source=visit_receipt_voucher")

    def test_visit_receipt_journal_entry_has_required_tags(self):
        """Journal entry with source=visit_receipt_voucher should have PARTY/VEHICLE tags"""
        response = requests.get(
            f"{BASE_URL}/api/finance/journal-entries",
            params={"workshop_id": WORKSHOP_ID, "limit": 100}
        )
        assert response.status_code == 200
        
        data = response.json()
        entries = data.get("data", data) if isinstance(data, dict) else data
        
        visit_receipts = [e for e in entries if e.get("source") == "visit_receipt_voucher"]
        
        if not visit_receipts:
            pytest.skip("No visit receipt voucher entries found")
        
        entry = visit_receipts[0]
        description = entry.get("description", "")
        
        # Check for required tags
        has_party = "[PARTY:" in description
        has_party_type = "[PARTY_TYPE:" in description
        has_visit = "[VISIT:" in description
        
        print(f"Entry description: {description[:200]}...")
        print(f"Has PARTY tag: {has_party}")
        print(f"Has PARTY_TYPE tag: {has_party_type}")
        print(f"Has VISIT tag: {has_visit}")
        
        assert has_party, "Expected [PARTY:...] tag in description"
        assert has_party_type, "Expected [PARTY_TYPE:...] tag in description"
        assert has_visit, "Expected [VISIT:...] tag in description"
        
        print(f"✅ Journal entry has required tags: PARTY={has_party}, PARTY_TYPE={has_party_type}, VISIT={has_visit}")

    def test_visit_receipt_journal_entry_has_reference_id(self):
        """Journal entry with source=visit_receipt_voucher should have reference_id pointing to visit"""
        response = requests.get(
            f"{BASE_URL}/api/finance/journal-entries",
            params={"workshop_id": WORKSHOP_ID, "limit": 100}
        )
        assert response.status_code == 200
        
        data = response.json()
        entries = data.get("data", data) if isinstance(data, dict) else data
        
        visit_receipts = [e for e in entries if e.get("source") == "visit_receipt_voucher"]
        
        if not visit_receipts:
            pytest.skip("No visit receipt voucher entries found")
        
        entry = visit_receipts[0]
        reference_id = entry.get("reference_id")
        
        assert reference_id, "Expected reference_id to be set"
        
        # Verify reference_id is a valid UUID format
        import re
        uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        assert re.match(uuid_pattern, reference_id, re.IGNORECASE), f"Expected reference_id to be UUID, got {reference_id}"
        
        print(f"✅ Journal entry has reference_id: {reference_id}")


class TestOperationsPageIntegration:
    """Test that Operations page can read operations without breaking"""

    def test_operations_list_endpoint_works(self):
        """GET /api/operations should work without errors"""
        response = requests.get(f"{BASE_URL}/api/operations", params={"limit": 50})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Expected list response"
        
        print(f"✅ Operations list endpoint works, returned {len(data)} operations")

    def test_operations_with_vehicle_filter(self):
        """GET /api/operations with vehicle_id filter should work"""
        # First get an operation to find a vehicle_id
        response = requests.get(f"{BASE_URL}/api/operations", params={"limit": 5})
        assert response.status_code == 200
        
        data = response.json()
        if not data:
            pytest.skip("No operations found")
        
        # Find an operation with vehicleId
        vehicle_ops = [op for op in data if op.get("vehicleId")]
        if not vehicle_ops:
            pytest.skip("No operations with vehicleId found")
        
        vehicle_id = vehicle_ops[0].get("vehicleId")
        
        # Test filter
        response = requests.get(f"{BASE_URL}/api/operations", params={"vehicle_id": vehicle_id, "limit": 10})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        filtered_data = response.json()
        assert isinstance(filtered_data, list), "Expected list response"
        
        # All returned operations should have the same vehicleId
        for op in filtered_data:
            assert op.get("vehicleId") == vehicle_id, f"Expected vehicleId={vehicle_id}, got {op.get('vehicleId')}"
        
        print(f"✅ Operations filter by vehicle_id works, returned {len(filtered_data)} operations for vehicle {vehicle_id}")

    def test_operations_integrity_check_endpoint(self):
        """POST /api/operations/integrity/check should work"""
        # Get some operation IDs first
        response = requests.get(f"{BASE_URL}/api/operations", params={"limit": 5})
        assert response.status_code == 200
        
        data = response.json()
        if not data:
            pytest.skip("No operations found")
        
        op_ids = [op.get("id") for op in data if op.get("id")][:3]
        
        # Test integrity check
        response = requests.post(
            f"{BASE_URL}/api/operations/integrity/check",
            json={"op_ids": op_ids, "workshop_id": WORKSHOP_ID}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        result = response.json()
        print(f"✅ Operations integrity check works: {result.get('data', {}).get('summary', {})}")


class TestOperationsPaymentSummary:
    """Test operations return correct payment summary from visits"""

    def test_operations_list_includes_workshop_total(self):
        """Operations should include workshopTotal field"""
        response = requests.get(f"{BASE_URL}/api/operations", params={"limit": 10})
        assert response.status_code == 200
        
        data = response.json()
        if not data:
            pytest.skip("No operations found")
        
        op = data[0]
        assert "workshopTotal" in op, "Missing workshopTotal field"
        print(f"✅ Operations include workshopTotal: {op.get('workshopTotal')}")

    def test_operations_list_includes_supplier_archive_total(self):
        """Operations should include supplierArchiveTotal field"""
        response = requests.get(f"{BASE_URL}/api/operations", params={"limit": 10})
        assert response.status_code == 200
        
        data = response.json()
        if not data:
            pytest.skip("No operations found")
        
        op = data[0]
        assert "supplierArchiveTotal" in op, "Missing supplierArchiveTotal field"
        print(f"✅ Operations include supplierArchiveTotal: {op.get('supplierArchiveTotal')}")

    def test_operations_list_includes_advance_paid(self):
        """Operations should include advancePaid field"""
        response = requests.get(f"{BASE_URL}/api/operations", params={"limit": 10})
        assert response.status_code == 200
        
        data = response.json()
        if not data:
            pytest.skip("No operations found")
        
        op = data[0]
        assert "advancePaid" in op, "Missing advancePaid field"
        print(f"✅ Operations include advancePaid: {op.get('advancePaid')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
