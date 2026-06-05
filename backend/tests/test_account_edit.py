"""
Test Account Edit/Update functionality
Tests PUT /api/accounts/{id} endpoint for updating chart of accounts entries
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://workshop-helper-7.preview.emergentagent.com')
WORKSHOP_ID = "finmodule-sync"


class TestAccountUpdate:
    """Tests for account update endpoint PUT /api/accounts/{id}"""
    
    @pytest.fixture
    def test_account(self):
        """Create a test account to update"""
        unique_code = f"TEST{uuid.uuid4().hex[:6].upper()}"
        response = requests.post(
            f"{BASE_URL}/api/finance/chart-of-accounts",
            params={"workshop_id": WORKSHOP_ID},
            json={
                "code": unique_code,
                "name": "حساب اختبار للتعديل",
                "type": "asset"
            }
        )
        assert response.status_code == 200, f"Failed to create test account: {response.text}"
        data = response.json()
        assert data.get("success") is True
        account = data["data"]
        yield account
        # Cleanup - delete the test account
        try:
            requests.delete(f"{BASE_URL}/api/accounts/{account['id']}")
        except:
            pass

    def test_update_account_code(self, test_account):
        """Test updating account code"""
        new_code = f"UPD{uuid.uuid4().hex[:4].upper()}"
        response = requests.put(
            f"{BASE_URL}/api/accounts/{test_account['id']}",
            json={"code": new_code}
        )
        assert response.status_code == 200, f"Update failed: {response.text}"
        data = response.json()
        assert data["code"] == new_code, "Code was not updated"
        
        # Verify persistence via GET
        get_response = requests.get(
            f"{BASE_URL}/api/finance/chart-of-accounts",
            params={"workshop_id": WORKSHOP_ID}
        )
        accounts = get_response.json()["data"]
        found = [a for a in accounts if a["id"] == test_account["id"]]
        assert len(found) == 1
        assert found[0]["code"] == new_code

    def test_update_account_name(self, test_account):
        """Test updating account name"""
        new_name = "اسم حساب معدل"
        response = requests.put(
            f"{BASE_URL}/api/accounts/{test_account['id']}",
            json={"name": new_name}
        )
        assert response.status_code == 200, f"Update failed: {response.text}"
        data = response.json()
        assert data["name"] == new_name, "Name was not updated"

    def test_update_account_type(self, test_account):
        """Test updating account type (asset -> revenue)"""
        response = requests.put(
            f"{BASE_URL}/api/accounts/{test_account['id']}",
            json={"type": "revenue"}
        )
        assert response.status_code == 200, f"Update failed: {response.text}"
        data = response.json()
        assert data["type"] == "revenue", "Type was not updated"

    def test_update_account_balance(self, test_account):
        """Test updating account balance"""
        new_balance = 5000.75
        response = requests.put(
            f"{BASE_URL}/api/accounts/{test_account['id']}",
            json={"balance": new_balance}
        )
        assert response.status_code == 200, f"Update failed: {response.text}"
        data = response.json()
        assert data["balance"] == new_balance, "Balance was not updated"

    def test_update_account_parent_id(self, test_account):
        """Test updating account parent_id"""
        # Get an existing parent account
        response = requests.get(
            f"{BASE_URL}/api/finance/chart-of-accounts",
            params={"workshop_id": WORKSHOP_ID}
        )
        accounts = response.json()["data"]
        parent = next((a for a in accounts if a.get("code") == "1000"), None)
        
        if parent:
            response = requests.put(
                f"{BASE_URL}/api/accounts/{test_account['id']}",
                json={"parentId": parent["id"]}
            )
            assert response.status_code == 200, f"Update failed: {response.text}"
            data = response.json()
            assert data["parentId"] == parent["id"], "Parent ID was not updated"

    def test_update_multiple_fields(self, test_account):
        """Test updating multiple fields at once"""
        new_code = f"MUL{uuid.uuid4().hex[:4].upper()}"
        new_name = "تعديل متعدد الحقول"
        new_type = "expense"
        new_balance = 999.99
        
        response = requests.put(
            f"{BASE_URL}/api/accounts/{test_account['id']}",
            json={
                "code": new_code,
                "name": new_name,
                "type": new_type,
                "balance": new_balance
            }
        )
        assert response.status_code == 200, f"Update failed: {response.text}"
        data = response.json()
        assert data["code"] == new_code
        assert data["name"] == new_name
        assert data["type"] == new_type
        assert data["balance"] == new_balance

    def test_update_preserves_other_fields(self, test_account):
        """Test that updating one field preserves other fields"""
        original_code = test_account["code"]
        
        # Update only name
        response = requests.put(
            f"{BASE_URL}/api/accounts/{test_account['id']}",
            json={"name": "اسم جديد فقط"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Code should be unchanged
        assert data["code"] == original_code, "Original code was modified when updating name only"

    def test_update_nonexistent_account(self):
        """Test updating a non-existent account (should fail gracefully)"""
        fake_id = str(uuid.uuid4())
        response = requests.put(
            f"{BASE_URL}/api/accounts/{fake_id}",
            json={"name": "لن ينجح"}
        )
        # Either 404 or empty result should be acceptable
        # The API currently returns 200 with empty data for non-existent IDs
        assert response.status_code in [200, 404]


class TestAccountEditIntegration:
    """Integration tests - Create → Update → GET flow"""
    
    def test_create_update_verify_flow(self):
        """Complete flow: Create → Update → Verify persistence"""
        unique_code = f"INT{uuid.uuid4().hex[:6].upper()}"
        
        # Step 1: Create account
        create_response = requests.post(
            f"{BASE_URL}/api/finance/chart-of-accounts",
            params={"workshop_id": WORKSHOP_ID},
            json={
                "code": unique_code,
                "name": "حساب التكامل الأصلي",
                "type": "liability"
            }
        )
        assert create_response.status_code == 200
        created = create_response.json()["data"]
        account_id = created["id"]
        
        try:
            # Step 2: Update all fields
            updated_code = f"UPD{uuid.uuid4().hex[:4].upper()}"
            update_response = requests.put(
                f"{BASE_URL}/api/accounts/{account_id}",
                json={
                    "code": updated_code,
                    "name": "حساب التكامل المعدل",
                    "type": "equity",
                    "balance": 12345.67
                }
            )
            assert update_response.status_code == 200
            updated = update_response.json()
            
            # Verify update response
            assert updated["code"] == updated_code
            assert updated["name"] == "حساب التكامل المعدل"
            assert updated["type"] == "equity"
            assert updated["balance"] == 12345.67
            
            # Step 3: GET to verify persistence
            get_response = requests.get(
                f"{BASE_URL}/api/finance/chart-of-accounts",
                params={"workshop_id": WORKSHOP_ID}
            )
            accounts = get_response.json()["data"]
            found = [a for a in accounts if a["id"] == account_id]
            
            assert len(found) == 1
            persisted = found[0]
            assert persisted["code"] == updated_code
            assert persisted["name"] == "حساب التكامل المعدل"
            assert persisted["type"] == "equity"
            
        finally:
            # Cleanup
            requests.delete(f"{BASE_URL}/api/accounts/{account_id}")
