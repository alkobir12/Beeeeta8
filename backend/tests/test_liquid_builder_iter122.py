"""
Test Iteration 122: Liquid Builder Draft/Undo/Redo API Tests
Tests for local draft workflow, positions, and customization persistence
"""
import pytest
import requests
import os
import json
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://financial-ssot.preview.emergentagent.com').rstrip('/')
TEST_USER_ID = f"TEST_iter122_{uuid.uuid4().hex[:6]}"
TEST_PATH = "/test-page-iter122"


class TestCustomizationPositions:
    """Test positions field in customization API"""
    
    def test_save_customization_with_positions(self):
        """Test saving customization with positions field"""
        payload = {
            "user_id": TEST_USER_ID,
            "path": TEST_PATH,
            "labels": {"test-block-1": "Test Label"},
            "hidden": {},
            "contents": {},
            "custom_cards": [],
            "block_order": [],
            "positions": {
                "test-block-1": {"left": 100, "top": 50},
                "test-block-2": {"left": 200, "top": 150}
            }
        }
        response = requests.put(f"{BASE_URL}/api/alkabeer-bot/customization", json=payload)
        assert response.status_code == 200, f"Failed to save: {response.text}"
        data = response.json()
        assert data.get("success") is True
        assert "positions" in data.get("data", {})
        positions = data["data"]["positions"]
        assert positions.get("test-block-1", {}).get("left") == 100
        assert positions.get("test-block-1", {}).get("top") == 50
        print(f"✅ Positions saved correctly: {positions}")
    
    def test_get_customization_with_positions(self):
        """Test retrieving customization with positions"""
        response = requests.get(
            f"{BASE_URL}/api/alkabeer-bot/customization",
            params={"user_id": TEST_USER_ID, "path": TEST_PATH}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        positions = data.get("data", {}).get("positions", {})
        assert "test-block-1" in positions
        assert positions["test-block-1"]["left"] == 100
        print(f"✅ Positions retrieved correctly: {positions}")
    
    def test_update_positions_only(self):
        """Test updating only positions without affecting other fields"""
        # First save with labels
        payload = {
            "user_id": TEST_USER_ID,
            "path": TEST_PATH,
            "labels": {"test-block-1": "Updated Label"},
            "positions": {
                "test-block-1": {"left": 300, "top": 250}
            }
        }
        response = requests.put(f"{BASE_URL}/api/alkabeer-bot/customization", json=payload)
        assert response.status_code == 200
        data = response.json()
        positions = data.get("data", {}).get("positions", {})
        labels = data.get("data", {}).get("labels", {})
        assert positions.get("test-block-1", {}).get("left") == 300
        assert labels.get("test-block-1") == "Updated Label"
        print(f"✅ Positions updated: {positions}")


class TestCustomizationContents:
    """Test contents field for inline editing"""
    
    def test_save_contents(self):
        """Test saving contents field (for inline editing)"""
        payload = {
            "user_id": TEST_USER_ID,
            "path": TEST_PATH,
            "contents": {
                "test-block-1": "Inline edited content",
                "test-block-2": "Another edited content"
            }
        }
        response = requests.put(f"{BASE_URL}/api/alkabeer-bot/customization", json=payload)
        assert response.status_code == 200
        data = response.json()
        contents = data.get("data", {}).get("contents", {})
        assert contents.get("test-block-1") == "Inline edited content"
        print(f"✅ Contents saved: {contents}")
    
    def test_get_contents(self):
        """Test retrieving contents"""
        response = requests.get(
            f"{BASE_URL}/api/alkabeer-bot/customization",
            params={"user_id": TEST_USER_ID, "path": TEST_PATH}
        )
        assert response.status_code == 200
        data = response.json()
        contents = data.get("data", {}).get("contents", {})
        assert "test-block-1" in contents
        print(f"✅ Contents retrieved: {contents}")


class TestCustomizationBlockOrder:
    """Test block_order field for drag reordering"""
    
    def test_save_block_order(self):
        """Test saving block order"""
        payload = {
            "user_id": TEST_USER_ID,
            "path": TEST_PATH,
            "block_order": ["block-3", "block-1", "block-2"]
        }
        response = requests.put(f"{BASE_URL}/api/alkabeer-bot/customization", json=payload)
        assert response.status_code == 200
        data = response.json()
        block_order = data.get("data", {}).get("block_order", [])
        assert block_order == ["block-3", "block-1", "block-2"]
        print(f"✅ Block order saved: {block_order}")
    
    def test_get_block_order(self):
        """Test retrieving block order"""
        response = requests.get(
            f"{BASE_URL}/api/alkabeer-bot/customization",
            params={"user_id": TEST_USER_ID, "path": TEST_PATH}
        )
        assert response.status_code == 200
        data = response.json()
        block_order = data.get("data", {}).get("block_order", [])
        assert "block-3" in block_order
        print(f"✅ Block order retrieved: {block_order}")


class TestCustomizationCustomCards:
    """Test custom_cards CRUD"""
    
    def test_save_custom_cards(self):
        """Test saving custom cards with fields"""
        payload = {
            "user_id": TEST_USER_ID,
            "path": TEST_PATH,
            "custom_cards": [
                {
                    "id": "card-test-1",
                    "title": "Test Card 1",
                    "description": "Test description",
                    "fields": [
                        {"id": "field-1", "label": "Field 1", "value": "Value 1"},
                        {"id": "field-2", "label": "Field 2", "value": "Value 2"}
                    ]
                },
                {
                    "id": "card-test-2",
                    "title": "Test Card 2 (Copy)",
                    "description": "",
                    "fields": []
                }
            ]
        }
        response = requests.put(f"{BASE_URL}/api/alkabeer-bot/customization", json=payload)
        assert response.status_code == 200
        data = response.json()
        custom_cards = data.get("data", {}).get("custom_cards", [])
        assert len(custom_cards) == 2
        assert custom_cards[0]["title"] == "Test Card 1"
        assert len(custom_cards[0]["fields"]) == 2
        print(f"✅ Custom cards saved: {len(custom_cards)} cards")
    
    def test_get_custom_cards(self):
        """Test retrieving custom cards"""
        response = requests.get(
            f"{BASE_URL}/api/alkabeer-bot/customization",
            params={"user_id": TEST_USER_ID, "path": TEST_PATH}
        )
        assert response.status_code == 200
        data = response.json()
        custom_cards = data.get("data", {}).get("custom_cards", [])
        assert len(custom_cards) >= 2
        print(f"✅ Custom cards retrieved: {len(custom_cards)} cards")


class TestBotChatDeveloperMode:
    """Test bot chat developer mode commands"""
    
    def test_rrr_entry(self):
        """Test entering developer mode with rrr"""
        payload = {
            "message": "rrr",
            "sessionId": f"test-session-{uuid.uuid4().hex[:6]}",
            "role": "manager",
            "userId": TEST_USER_ID,
            "currentPath": TEST_PATH,
            "uiSnapshot": []
        }
        response = requests.post(f"{BASE_URL}/api/alkabeer-bot/chat", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data.get("mode") == "dev"
        assert "وضع المطور" in data.get("response", "")
        print(f"✅ Developer mode entered: {data.get('mode')}")
    
    def test_exit_developer_mode(self):
        """Test exiting developer mode"""
        session_id = f"test-session-{uuid.uuid4().hex[:6]}"
        # First enter dev mode
        requests.post(f"{BASE_URL}/api/alkabeer-bot/chat", json={
            "message": "rrr",
            "sessionId": session_id,
            "role": "manager",
            "userId": TEST_USER_ID,
            "currentPath": TEST_PATH,
            "uiSnapshot": []
        })
        # Then exit
        payload = {
            "message": "EXIT",
            "sessionId": session_id,
            "role": "manager",
            "userId": TEST_USER_ID,
            "currentPath": TEST_PATH,
            "uiSnapshot": []
        }
        response = requests.post(f"{BASE_URL}/api/alkabeer-bot/chat", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data.get("mode") == "user"
        print(f"✅ Developer mode exited: {data.get('mode')}")


class TestHealthEndpoint:
    """Test health endpoint"""
    
    def test_health(self):
        """Test bot health endpoint"""
        response = requests.get(f"{BASE_URL}/api/alkabeer-bot/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"
        print(f"✅ Health check passed: {data}")


class TestCleanup:
    """Cleanup test data"""
    
    def test_cleanup_test_data(self):
        """Clean up test customizations"""
        # Reset the test page
        payload = {
            "user_id": TEST_USER_ID,
            "path": TEST_PATH,
            "labels": {},
            "hidden": {},
            "contents": {},
            "custom_cards": [],
            "block_order": [],
            "positions": {}
        }
        response = requests.put(f"{BASE_URL}/api/alkabeer-bot/customization", json=payload)
        assert response.status_code == 200
        print(f"✅ Test data cleaned up for user: {TEST_USER_ID}")
