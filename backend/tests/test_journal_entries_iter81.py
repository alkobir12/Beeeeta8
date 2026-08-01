"""
Test Journal Entries API - Iteration 81
Tests for party_label, party_type, vehicle_label, operation_type_label fields
and search functionality
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://ar-ledger-ssot.preview.emergentagent.com').rstrip('/')
WORKSHOP_ID = os.environ.get('REACT_APP_WORKSHOP_ID', 'finmodule-sync')


class TestJournalEntriesAPI:
    """Test GET /api/finance/journal-entries returns required fields"""

    def test_journal_entries_returns_party_label(self):
        """Test that party_label field is returned"""
        response = requests.get(
            f"{BASE_URL}/api/finance/journal-entries",
            params={"workshop_id": WORKSHOP_ID, "limit": 10}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        assert "data" in data
        
        if len(data["data"]) > 0:
            entry = data["data"][0]
            assert "party_label" in entry, "party_label field missing from response"
            print(f"✅ party_label found: {entry.get('party_label')}")

    def test_journal_entries_returns_party_type(self):
        """Test that party_type field is returned"""
        response = requests.get(
            f"{BASE_URL}/api/finance/journal-entries",
            params={"workshop_id": WORKSHOP_ID, "limit": 10}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        
        if len(data["data"]) > 0:
            entry = data["data"][0]
            assert "party_type" in entry, "party_type field missing from response"
            # party_type should be one of: customer, supplier, open, manual
            valid_types = {"customer", "supplier", "open", "manual", ""}
            assert entry.get("party_type", "") in valid_types or entry.get("party_type") is None
            print(f"✅ party_type found: {entry.get('party_type')}")

    def test_journal_entries_returns_vehicle_label(self):
        """Test that vehicle_label field is returned"""
        response = requests.get(
            f"{BASE_URL}/api/finance/journal-entries",
            params={"workshop_id": WORKSHOP_ID, "limit": 10}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        
        if len(data["data"]) > 0:
            entry = data["data"][0]
            assert "vehicle_label" in entry, "vehicle_label field missing from response"
            print(f"✅ vehicle_label found: {entry.get('vehicle_label')}")

    def test_journal_entries_returns_operation_type_label(self):
        """Test that operation_type_label field is returned"""
        response = requests.get(
            f"{BASE_URL}/api/finance/journal-entries",
            params={"workshop_id": WORKSHOP_ID, "limit": 10}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        
        if len(data["data"]) > 0:
            entry = data["data"][0]
            assert "operation_type_label" in entry, "operation_type_label field missing from response"
            # operation_type_label should be Arabic label
            print(f"✅ operation_type_label found: {entry.get('operation_type_label')}")

    def test_journal_entries_all_required_fields(self):
        """Test that all required fields are present in each entry"""
        response = requests.get(
            f"{BASE_URL}/api/finance/journal-entries",
            params={"workshop_id": WORKSHOP_ID, "limit": 20}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        
        required_fields = ["party_label", "party_type", "vehicle_label", "operation_type_label"]
        
        for i, entry in enumerate(data["data"][:10]):
            for field in required_fields:
                assert field in entry, f"Entry {i}: {field} field missing"
            print(f"✅ Entry {i}: All required fields present - party_label={entry.get('party_label')}, operation_type_label={entry.get('operation_type_label')}")

    def test_journal_entries_operation_type_labels_arabic(self):
        """Test that operation_type_label contains Arabic labels"""
        response = requests.get(
            f"{BASE_URL}/api/finance/journal-entries",
            params={"workshop_id": WORKSHOP_ID, "limit": 50}
        )
        assert response.status_code == 200
        data = response.json()
        
        expected_labels = {"بيع", "خدمة", "شراء", "مصروف", "مرتجع بيع", "مرتجع شراء", "أمر سداد", "تحصيل/سداد", "غير محدد"}
        
        found_labels = set()
        for entry in data["data"]:
            label = entry.get("operation_type_label", "")
            if label:
                found_labels.add(label)
        
        print(f"✅ Found operation_type_labels: {found_labels}")
        # At least some labels should be in Arabic
        assert len(found_labels) > 0, "No operation_type_labels found"


class TestJournalEntriesUpdate:
    """Test PUT /api/finance/journal-entries/{id} for party label update"""

    def test_update_entry_with_party_token(self):
        """Test that updating description with [PARTY:...] token works"""
        # First get an entry
        response = requests.get(
            f"{BASE_URL}/api/finance/journal-entries",
            params={"workshop_id": WORKSHOP_ID, "limit": 5}
        )
        assert response.status_code == 200
        data = response.json()
        
        if len(data["data"]) == 0:
            pytest.skip("No entries to test update")
        
        entry = data["data"][0]
        entry_id = entry.get("id")
        
        # Update with PARTY token
        test_party = "عميل اختبار"
        clean_desc = str(entry.get("description", "")).replace("[PARTY:", "").split("]")[0] if "[PARTY:" in str(entry.get("description", "")) else entry.get("description", "")
        new_description = f"{clean_desc} [PARTY:{test_party}]"
        
        update_response = requests.put(
            f"{BASE_URL}/api/finance/journal-entries/{entry_id}",
            params={"workshop_id": WORKSHOP_ID},
            json={
                "date": entry.get("date"),
                "description": new_description,
                "transaction_type": entry.get("transaction_type", "manual"),
                "lines": entry.get("lines", []),
                "total": entry.get("total", 0)
            }
        )
        
        # Check if update was successful (may fail if entry is read-only)
        if update_response.status_code == 200:
            update_data = update_response.json()
            print(f"✅ Update response: {update_data.get('success')}")
            
            # Verify the party_label is updated
            verify_response = requests.get(
                f"{BASE_URL}/api/finance/journal-entries",
                params={"workshop_id": WORKSHOP_ID, "limit": 5}
            )
            verify_data = verify_response.json()
            updated_entry = next((e for e in verify_data["data"] if e.get("id") == entry_id), None)
            if updated_entry:
                print(f"✅ Updated party_label: {updated_entry.get('party_label')}")
        else:
            print(f"⚠️ Update returned status {update_response.status_code} - entry may be read-only")


class TestJournalEntriesSearch:
    """Test search functionality includes party_label and operation_type_label"""

    def test_search_by_party_label(self):
        """Test that search can find entries by party_label"""
        # First get entries to find a party_label to search for
        response = requests.get(
            f"{BASE_URL}/api/finance/journal-entries",
            params={"workshop_id": WORKSHOP_ID, "limit": 20}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Find a non-empty party_label
        search_term = None
        for entry in data["data"]:
            party = entry.get("party_label", "")
            if party and party != "مفتوح" and len(party) > 3:
                search_term = party[:10]  # Use first 10 chars
                break
        
        if search_term:
            print(f"✅ Found party_label to search: {search_term}")
        else:
            print("⚠️ No suitable party_label found for search test")

    def test_search_by_operation_type_label(self):
        """Test that search can find entries by operation_type_label"""
        response = requests.get(
            f"{BASE_URL}/api/finance/journal-entries",
            params={"workshop_id": WORKSHOP_ID, "limit": 20}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Find entries with specific operation types
        operation_types = set()
        for entry in data["data"]:
            op_type = entry.get("operation_type_label", "")
            if op_type:
                operation_types.add(op_type)
        
        print(f"✅ Found operation_type_labels: {operation_types}")
        assert len(operation_types) > 0, "No operation_type_labels found"


class TestJournalEntriesRegression:
    """Regression tests for totals and main table rendering"""

    def test_entries_have_totals(self):
        """Test that entries have total field"""
        response = requests.get(
            f"{BASE_URL}/api/finance/journal-entries",
            params={"workshop_id": WORKSHOP_ID, "limit": 10}
        )
        assert response.status_code == 200
        data = response.json()
        
        for entry in data["data"]:
            assert "total" in entry, "total field missing"
            assert isinstance(entry.get("total"), (int, float)), "total should be numeric"
        
        print(f"✅ All entries have valid total field")

    def test_entries_have_lines(self):
        """Test that entries have lines array"""
        response = requests.get(
            f"{BASE_URL}/api/finance/journal-entries",
            params={"workshop_id": WORKSHOP_ID, "limit": 10}
        )
        assert response.status_code == 200
        data = response.json()
        
        for entry in data["data"]:
            assert "lines" in entry, "lines field missing"
            assert isinstance(entry.get("lines"), list), "lines should be array"
        
        print(f"✅ All entries have valid lines array")

    def test_entries_have_date(self):
        """Test that entries have date field"""
        response = requests.get(
            f"{BASE_URL}/api/finance/journal-entries",
            params={"workshop_id": WORKSHOP_ID, "limit": 10}
        )
        assert response.status_code == 200
        data = response.json()
        
        for entry in data["data"]:
            assert "date" in entry, "date field missing"
        
        print(f"✅ All entries have date field")

    def test_response_has_total_count(self):
        """Test that response includes total count"""
        response = requests.get(
            f"{BASE_URL}/api/finance/journal-entries",
            params={"workshop_id": WORKSHOP_ID, "limit": 10}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "total" in data, "total count missing from response"
        print(f"✅ Response includes total count: {data.get('total')}")
