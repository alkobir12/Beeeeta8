"""
Test Journal Entries CRUD APIs
Tests for:
- POST /api/finance/journal-entries - Create manual journal entry
- GET /api/finance/journal-entries/{id} - Get single entry
- PUT /api/finance/journal-entries/{id} - Update manual entry
- DELETE /api/finance/journal-entries/{id} - Delete manual entry
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL", "https://workshop-operator.preview.emergentagent.com"
).rstrip("/")
WORKSHOP_ID = "finmodule-sync"


class TestJournalEntriesCRUD:
    """Journal Entries CRUD API tests"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test data"""
        self.test_entry_id = None
        yield
        # Cleanup: Delete test entry if created
        if self.test_entry_id:
            try:
                requests.delete(
                    f"{BASE_URL}/api/finance/journal-entries/{self.test_entry_id}",
                    params={"workshop_id": WORKSHOP_ID},
                )
            except:
                pass

    def test_create_journal_entry(self):
        """Test POST /api/finance/journal-entries - Create new manual entry"""
        payload = {
            "date": "2026-01-25",
            "description": f"TEST_قيد اختبار {uuid.uuid4().hex[:8]}",
            "lines": [
                {
                    "account": "101",
                    "account_name": "النقدية",
                    "debit": 1500,
                    "credit": 0,
                },
                {
                    "account": "522",
                    "account_name": "مصاريف إيجار",
                    "debit": 0,
                    "credit": 1500,
                },
            ],
            "total": 1500,
        }

        response = requests.post(
            f"{BASE_URL}/api/finance/journal-entries",
            params={"workshop_id": WORKSHOP_ID},
            json=payload,
        )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        data = response.json()
        assert data.get("success") == True, "Response should have success=True"
        assert "id" in data, "Response should have id"
        assert (
            data.get("message") == "تم إنشاء القيد المحاسبي بنجاح"
        ), "Should return success message"

        self.test_entry_id = data["id"]
        print(f"✅ Created journal entry with ID: {self.test_entry_id}")

        # Verify data was persisted by GET
        get_response = requests.get(
            f"{BASE_URL}/api/finance/journal-entries/{self.test_entry_id}",
            params={"workshop_id": WORKSHOP_ID},
        )
        assert get_response.status_code == 200
        get_data = get_response.json()
        assert get_data.get("success") == True
        assert get_data["data"]["description"] == payload["description"]
        assert get_data["data"]["total"] == payload["total"]
        print("✅ Verified entry persisted correctly")

    def test_get_single_journal_entry(self):
        """Test GET /api/finance/journal-entries/{id} - Get single entry"""
        # First create an entry
        payload = {
            "date": "2026-01-25",
            "description": f"TEST_قيد للقراءة {uuid.uuid4().hex[:8]}",
            "lines": [
                {
                    "account": "101",
                    "account_name": "النقدية",
                    "debit": 500,
                    "credit": 0,
                },
                {
                    "account": "411",
                    "account_name": "إيرادات خدمات الصيانة",
                    "debit": 0,
                    "credit": 500,
                },
            ],
            "total": 500,
        }

        create_response = requests.post(
            f"{BASE_URL}/api/finance/journal-entries",
            params={"workshop_id": WORKSHOP_ID},
            json=payload,
        )
        assert create_response.status_code == 200
        entry_id = create_response.json()["id"]
        self.test_entry_id = entry_id

        # Test GET single entry
        response = requests.get(
            f"{BASE_URL}/api/finance/journal-entries/{entry_id}",
            params={"workshop_id": WORKSHOP_ID},
        )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        data = response.json()
        assert data.get("success") == True, "Response should have success=True"
        assert "data" in data, "Response should have data"

        entry = data["data"]
        assert entry["id"] == entry_id, "Entry ID should match"
        assert (
            entry["description"] == payload["description"]
        ), "Description should match"
        assert entry["total"] == payload["total"], "Total should match"
        assert entry["source"] == "manual", "Source should be manual"
        assert len(entry["lines"]) == 2, "Should have 2 lines"

        print(f"✅ GET single entry works - ID: {entry_id}")

    def test_get_nonexistent_entry(self):
        """Test GET /api/finance/journal-entries/{id} - Non-existent entry"""
        fake_id = str(uuid.uuid4())

        response = requests.get(
            f"{BASE_URL}/api/finance/journal-entries/{fake_id}",
            params={"workshop_id": WORKSHOP_ID},
        )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        data = response.json()
        assert data.get("success") == False, "Response should have success=False"
        assert "error" in data or "message" in data, "Should have error message"

        print("✅ GET non-existent entry returns proper error")

    def test_update_journal_entry(self):
        """Test PUT /api/finance/journal-entries/{id} - Update manual entry"""
        # First create an entry
        payload = {
            "date": "2026-01-25",
            "description": f"TEST_قيد للتعديل {uuid.uuid4().hex[:8]}",
            "lines": [
                {
                    "account": "101",
                    "account_name": "النقدية",
                    "debit": 1000,
                    "credit": 0,
                },
                {
                    "account": "522",
                    "account_name": "مصاريف إيجار",
                    "debit": 0,
                    "credit": 1000,
                },
            ],
            "total": 1000,
        }

        create_response = requests.post(
            f"{BASE_URL}/api/finance/journal-entries",
            params={"workshop_id": WORKSHOP_ID},
            json=payload,
        )
        assert create_response.status_code == 200
        entry_id = create_response.json()["id"]
        self.test_entry_id = entry_id

        # Test PUT update
        update_payload = {
            "date": "2026-01-26",
            "description": "TEST_قيد معدل",
            "lines": [
                {
                    "account": "101",
                    "account_name": "النقدية",
                    "debit": 2000,
                    "credit": 0,
                },
                {
                    "account": "522",
                    "account_name": "مصاريف إيجار",
                    "debit": 0,
                    "credit": 2000,
                },
            ],
            "total": 2000,
        }

        response = requests.put(
            f"{BASE_URL}/api/finance/journal-entries/{entry_id}",
            params={"workshop_id": WORKSHOP_ID},
            json=update_payload,
        )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        data = response.json()
        assert data.get("success") == True, "Response should have success=True"
        assert (
            data.get("message") == "تم تحديث القيد المحاسبي بنجاح"
        ), "Should return success message"

        # Verify update was persisted
        get_response = requests.get(
            f"{BASE_URL}/api/finance/journal-entries/{entry_id}",
            params={"workshop_id": WORKSHOP_ID},
        )
        get_data = get_response.json()
        assert get_data["data"]["description"] == update_payload["description"]
        assert get_data["data"]["total"] == update_payload["total"]

        print(f"✅ PUT update entry works - ID: {entry_id}")

    def test_update_nonexistent_entry(self):
        """Test PUT /api/finance/journal-entries/{id} - Non-existent entry"""
        fake_id = str(uuid.uuid4())

        update_payload = {
            "date": "2026-01-26",
            "description": "TEST_قيد غير موجود",
            "lines": [],
            "total": 0,
        }

        response = requests.put(
            f"{BASE_URL}/api/finance/journal-entries/{fake_id}",
            params={"workshop_id": WORKSHOP_ID},
            json=update_payload,
        )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        data = response.json()
        assert data.get("success") == False, "Response should have success=False"

        print("✅ PUT non-existent entry returns proper error")

    def test_delete_journal_entry(self):
        """Test DELETE /api/finance/journal-entries/{id} - Delete manual entry"""
        # First create an entry
        payload = {
            "date": "2026-01-25",
            "description": f"TEST_قيد للحذف {uuid.uuid4().hex[:8]}",
            "lines": [
                {
                    "account": "101",
                    "account_name": "النقدية",
                    "debit": 750,
                    "credit": 0,
                },
                {
                    "account": "411",
                    "account_name": "إيرادات خدمات الصيانة",
                    "debit": 0,
                    "credit": 750,
                },
            ],
            "total": 750,
        }

        create_response = requests.post(
            f"{BASE_URL}/api/finance/journal-entries",
            params={"workshop_id": WORKSHOP_ID},
            json=payload,
        )
        assert create_response.status_code == 200
        entry_id = create_response.json()["id"]

        # Test DELETE
        response = requests.delete(
            f"{BASE_URL}/api/finance/journal-entries/{entry_id}",
            params={"workshop_id": WORKSHOP_ID},
        )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        data = response.json()
        assert data.get("success") == True, "Response should have success=True"
        assert (
            data.get("message") == "تم حذف القيد المحاسبي بنجاح"
        ), "Should return success message"

        # Verify deletion - GET should return error
        get_response = requests.get(
            f"{BASE_URL}/api/finance/journal-entries/{entry_id}",
            params={"workshop_id": WORKSHOP_ID},
        )
        get_data = get_response.json()
        assert get_data.get("success") == False, "Entry should not exist after deletion"

        print(f"✅ DELETE entry works - ID: {entry_id}")

        # Clear test_entry_id since we already deleted
        self.test_entry_id = None

    def test_delete_nonexistent_entry(self):
        """Test DELETE /api/finance/journal-entries/{id} - Non-existent entry"""
        fake_id = str(uuid.uuid4())

        response = requests.delete(
            f"{BASE_URL}/api/finance/journal-entries/{fake_id}",
            params={"workshop_id": WORKSHOP_ID},
        )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        data = response.json()
        assert data.get("success") == False, "Response should have success=False"

        print("✅ DELETE non-existent entry returns proper error")

    def test_list_journal_entries(self):
        """Test GET /api/finance/journal-entries - List all entries"""
        response = requests.get(
            f"{BASE_URL}/api/finance/journal-entries",
            params={"workshop_id": WORKSHOP_ID, "limit": 10},
        )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        data = response.json()
        assert data.get("success") == True, "Response should have success=True"
        assert "data" in data, "Response should have data"
        assert isinstance(data["data"], list), "Data should be a list"

        # Check that manual entries have source="manual"
        manual_entries = [e for e in data["data"] if e.get("source") == "manual"]
        operation_entries = [e for e in data["data"] if e.get("source") == "operation"]

        print(
            f"✅ List entries works - Total: {len(data['data'])}, Manual: {len(manual_entries)}, Operations: {len(operation_entries)}"
        )


class TestJournalEntryValidation:
    """Journal Entry validation tests"""

    def test_create_entry_with_balanced_lines(self):
        """Test that balanced entries are accepted"""
        payload = {
            "date": "2026-01-25",
            "description": f"TEST_قيد متوازن {uuid.uuid4().hex[:8]}",
            "lines": [
                {
                    "account": "101",
                    "account_name": "النقدية",
                    "debit": 1000,
                    "credit": 0,
                },
                {
                    "account": "522",
                    "account_name": "مصاريف إيجار",
                    "debit": 0,
                    "credit": 1000,
                },
            ],
            "total": 1000,
        }

        response = requests.post(
            f"{BASE_URL}/api/finance/journal-entries",
            params={"workshop_id": WORKSHOP_ID},
            json=payload,
        )

        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True

        # Cleanup
        if data.get("id"):
            requests.delete(
                f"{BASE_URL}/api/finance/journal-entries/{data['id']}",
                params={"workshop_id": WORKSHOP_ID},
            )

        print("✅ Balanced entry accepted")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
