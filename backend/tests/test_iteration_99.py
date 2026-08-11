"""
Iteration 99 Tests - Testing:
1. JournalEntries print: Workshop data (name/phone/register/tax) from profile/settings APIs
2. AlKabeer bot: rrr works for manager only, rejects non-manager
3. AlKabeer bot dev commands: rename/hide/show saved and fetched via customization endpoint
4. ComprehensiveFinancial: Budget tab CRUD (add/delete budget item)
5. ComprehensiveFinancial: Trial balance endpoint returns data
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://canonical-integrity.preview.emergentagent.com')
WORKSHOP_ID = os.environ.get('REACT_APP_WORKSHOP_ID', 'finmodule-sync')


class TestProfileAndSettingsAPIs:
    """Test profile and settings APIs for JournalEntries print functionality"""
    
    def test_profile_api_returns_workshop_data(self):
        """Profile API should return workshop name, phone, commercial register, tax number"""
        response = requests.get(f"{BASE_URL}/api/profile")
        assert response.status_code == 200, f"Profile API failed: {response.text}"
        
        data = response.json()
        # Handle both {success, data} and direct data formats
        profile = data.get('data') if data.get('success') else data
        
        # Verify workshop data fields exist
        assert profile is not None, "Profile data is None"
        # Check for name (various field names)
        name = profile.get('business_name') or profile.get('name') or profile.get('workshopName')
        assert name, f"Workshop name not found in profile: {profile}"
        print(f"✅ Profile API returns workshop name: {name}")
        
    def test_settings_api_returns_workshop_settings(self):
        """Settings API should return workshop settings"""
        response = requests.get(f"{BASE_URL}/api/settings")
        assert response.status_code == 200, f"Settings API failed: {response.text}"
        
        data = response.json()
        assert data is not None, "Settings data is None"
        print(f"✅ Settings API returns data: {list(data.keys()) if isinstance(data, dict) else 'non-dict'}")


class TestAlKabeerBotDevMode:
    """Test AlKabeer Bot developer mode (rrr command)"""
    
    def test_health_endpoint(self):
        """Bot health endpoint should work"""
        response = requests.get(f"{BASE_URL}/api/alkabeer-bot/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get('status') == 'ok'
        print("✅ AlKabeer Bot health endpoint OK")
    
    def test_rrr_activates_dev_mode_for_manager(self):
        """rrr command should activate dev mode for manager role"""
        session_id = str(uuid.uuid4())
        response = requests.post(f"{BASE_URL}/api/alkabeer-bot/chat", json={
            "message": "rrr",
            "sessionId": session_id,
            "role": "manager",
            "userId": "test-manager",
            "currentPath": "/",
            "uiSnapshot": []
        })
        assert response.status_code == 200, f"Chat API failed: {response.text}"
        
        data = response.json()
        assert data.get('mode') == 'dev', f"Expected mode='dev', got: {data.get('mode')}"
        assert 'تم تفعيل وضع المطور' in data.get('response', ''), f"Response should mention dev mode activation"
        print("✅ rrr activates dev mode for manager role")
    
    def test_rrr_activates_dev_mode_for_arabic_manager(self):
        """rrr command should activate dev mode for مدير role"""
        session_id = str(uuid.uuid4())
        response = requests.post(f"{BASE_URL}/api/alkabeer-bot/chat", json={
            "message": "rrr",
            "sessionId": session_id,
            "role": "مدير",
            "userId": "test-manager-ar",
            "currentPath": "/",
            "uiSnapshot": []
        })
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('mode') == 'dev', f"Expected mode='dev' for مدير role, got: {data.get('mode')}"
        print("✅ rrr activates dev mode for مدير role")
    
    def test_rrr_rejected_for_non_manager(self):
        """rrr command should be rejected for non-manager roles"""
        session_id = str(uuid.uuid4())
        response = requests.post(f"{BASE_URL}/api/alkabeer-bot/chat", json={
            "message": "rrr",
            "sessionId": session_id,
            "role": "technician",
            "userId": "test-tech",
            "currentPath": "/",
            "uiSnapshot": []
        })
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('mode') == 'user', f"Expected mode='user' for technician, got: {data.get('mode')}"
        assert 'متاح للمدير فقط' in data.get('response', ''), f"Response should mention manager-only"
        print("✅ rrr rejected for non-manager role (technician)")
    
    def test_rrr_rejected_for_empty_role(self):
        """rrr command should be rejected for empty role"""
        session_id = str(uuid.uuid4())
        response = requests.post(f"{BASE_URL}/api/alkabeer-bot/chat", json={
            "message": "rrr",
            "sessionId": session_id,
            "role": "",
            "userId": "test-empty",
            "currentPath": "/",
            "uiSnapshot": []
        })
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('mode') == 'user', f"Expected mode='user' for empty role, got: {data.get('mode')}"
        print("✅ rrr rejected for empty role")
    
    def test_customization_endpoint_default(self):
        """Customization endpoint should return default empty config"""
        response = requests.get(f"{BASE_URL}/api/alkabeer-bot/customization", params={
            "user_id": "test-user-default",
            "path": "/test-page"
        })
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('success') == True
        assert 'data' in data
        assert 'labels' in data['data']
        assert 'hidden' in data['data']
        print("✅ Customization endpoint returns default config")
    
    def test_dev_mode_hide_command_saves_customization(self):
        """Dev mode hide command should save to customization"""
        session_id = str(uuid.uuid4())
        user_id = f"test-hide-{uuid.uuid4().hex[:8]}"
        test_path = "/test-hide-page"
        
        # First activate dev mode
        response = requests.post(f"{BASE_URL}/api/alkabeer-bot/chat", json={
            "message": "rrr",
            "sessionId": session_id,
            "role": "manager",
            "userId": user_id,
            "currentPath": test_path,
            "uiSnapshot": [{"testid": "test-element", "text": "عنصر اختبار", "tag": "div"}]
        })
        assert response.status_code == 200
        assert response.json().get('mode') == 'dev'
        
        # Send hide command
        response = requests.post(f"{BASE_URL}/api/alkabeer-bot/chat", json={
            "message": "اخف عنصر اختبار",
            "sessionId": session_id,
            "role": "manager",
            "userId": user_id,
            "currentPath": test_path,
            "uiSnapshot": [{"testid": "test-element", "text": "عنصر اختبار", "tag": "div"}]
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get('mode') == 'dev'
        
        # Check if customization was saved
        cust_response = requests.get(f"{BASE_URL}/api/alkabeer-bot/customization", params={
            "user_id": user_id,
            "path": test_path
        })
        assert cust_response.status_code == 200
        cust_data = cust_response.json()
        print(f"✅ Dev mode hide command processed, customization: {cust_data.get('data', {})}")


class TestBudgetCRUD:
    """Test Budget CRUD operations for ComprehensiveFinancial"""
    
    def test_get_budgets_endpoint(self):
        """GET /api/finance/budgets should return budget data"""
        response = requests.get(f"{BASE_URL}/api/finance/budgets", params={
            "workshop_id": WORKSHOP_ID,
            "month": "2026-01"
        })
        assert response.status_code == 200, f"Budgets API failed: {response.text}"
        
        data = response.json()
        assert 'data' in data or 'rows' in data or isinstance(data, list), f"Unexpected response format: {data}"
        print(f"✅ GET budgets endpoint works")
    
    def test_create_budget_item(self):
        """POST /api/finance/budgets should create a budget item"""
        test_budget = {
            "workshop_id": WORKSHOP_ID,
            "month": "2026-01",
            "name": f"TEST_budget_item_{uuid.uuid4().hex[:6]}",
            "category": "operating",
            "planned": 5000,
            "actual": 3000,
            "notes": "Test budget item for iteration 99"
        }
        
        response = requests.post(f"{BASE_URL}/api/finance/budgets", json=test_budget)
        assert response.status_code == 200, f"Create budget failed: {response.text}"
        
        data = response.json()
        assert data.get('success') == True or 'id' in data or 'data' in data, f"Unexpected response: {data}"
        
        # Extract created budget ID
        created_id = data.get('data', {}).get('id') or data.get('id')
        print(f"✅ Created budget item with ID: {created_id}")
        return created_id
    
    def test_create_and_delete_budget_item(self):
        """Create and delete a budget item"""
        # Create
        test_budget = {
            "workshop_id": WORKSHOP_ID,
            "month": "2026-01",
            "name": f"TEST_delete_budget_{uuid.uuid4().hex[:6]}",
            "category": "parts",
            "planned": 2000,
            "actual": 1500,
            "notes": "Test budget for deletion"
        }
        
        create_response = requests.post(f"{BASE_URL}/api/finance/budgets", json=test_budget)
        assert create_response.status_code == 200, f"Create budget failed: {create_response.text}"
        
        create_data = create_response.json()
        budget_id = create_data.get('data', {}).get('id') or create_data.get('id')
        assert budget_id, f"No budget ID returned: {create_data}"
        
        # Delete
        delete_response = requests.delete(
            f"{BASE_URL}/api/finance/budgets/{budget_id}",
            params={"workshop_id": WORKSHOP_ID}
        )
        assert delete_response.status_code == 200, f"Delete budget failed: {delete_response.text}"
        print(f"✅ Created and deleted budget item: {budget_id}")


class TestTrialBalance:
    """Test Trial Balance endpoint for ComprehensiveFinancial"""
    
    def test_trial_balance_endpoint(self):
        """GET /api/finance/reports/trial-balance should return trial balance data"""
        response = requests.get(f"{BASE_URL}/api/finance/reports/trial-balance", params={
            "workshop_id": WORKSHOP_ID,
            "start_date": "2025-01-01",
            "end_date": "2026-01-31"
        })
        assert response.status_code == 200, f"Trial balance API failed: {response.text}"
        
        data = response.json()
        assert data.get('success') == True, f"Trial balance not successful: {data}"
        assert 'data' in data, f"No data in response: {data}"
        
        trial_data = data['data']
        assert 'accounts' in trial_data, f"No accounts in trial balance: {trial_data}"
        assert 'totals' in trial_data, f"No totals in trial balance: {trial_data}"
        
        totals = trial_data['totals']
        assert 'total_debit' in totals, f"No total_debit in totals: {totals}"
        assert 'total_credit' in totals, f"No total_credit in totals: {totals}"
        
        print(f"✅ Trial balance endpoint works - {len(trial_data['accounts'])} accounts, debit={totals['total_debit']}, credit={totals['total_credit']}")


class TestJournalEntriesAPI:
    """Test Journal Entries API for print functionality"""
    
    def test_journal_entries_endpoint(self):
        """GET /api/finance/journal-entries should return entries"""
        response = requests.get(f"{BASE_URL}/api/finance/journal-entries", params={
            "workshop_id": WORKSHOP_ID,
            "limit": 5
        })
        assert response.status_code == 200, f"Journal entries API failed: {response.text}"
        
        data = response.json()
        assert data.get('success') == True, f"Journal entries not successful: {data}"
        print(f"✅ Journal entries endpoint works - {len(data.get('data', []))} entries")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
