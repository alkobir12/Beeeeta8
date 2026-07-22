"""
MoltBot Editor API Tests - Iteration 133
Tests for:
- Draft save/history/comments/publish APIs
- Customization persistence
- End-to-end publish reflection
"""
import pytest
import requests
import os
import uuid
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://workshop-engine.preview.emergentagent.com"

TEST_USER_ID = "manager"
TEST_PATH_OPERATIONS = "/operations"
TEST_PATH_DASHBOARD = "/"


class TestMoltBotEditorHealth:
    """Health check for MoltBot Editor APIs"""
    
    def test_alkabeer_bot_health(self):
        """Test /api/alkabeer-bot/health endpoint"""
        response = requests.get(f"{BASE_URL}/api/alkabeer-bot/health", timeout=10)
        assert response.status_code == 200, f"Health check failed: {response.text}"
        data = response.json()
        assert data.get("status") == "ok"
        print(f"✓ Health check passed: {data}")


class TestMoltBotEditorDraft:
    """Draft save and retrieval tests"""
    
    def test_get_editor_draft(self):
        """Test GET /api/alkabeer-bot/editor/draft"""
        params = {"user_id": TEST_USER_ID, "path": TEST_PATH_OPERATIONS}
        response = requests.get(f"{BASE_URL}/api/alkabeer-bot/editor/draft", params=params, timeout=10)
        assert response.status_code == 200, f"Get draft failed: {response.text}"
        data = response.json()
        assert data.get("success") is True
        assert "data" in data
        draft_data = data["data"]
        assert "config" in draft_data
        assert "version" in draft_data
        assert "status" in draft_data
        print(f"✓ Get draft passed - version: {draft_data.get('version')}, status: {draft_data.get('status')}")
    
    def test_save_editor_draft(self):
        """Test POST /api/alkabeer-bot/editor/draft/save"""
        test_label = f"test-label-{uuid.uuid4().hex[:8]}"
        payload = {
            "user_id": TEST_USER_ID,
            "path": TEST_PATH_OPERATIONS,
            "config": {
                "labels": {"operations-active-tab-title": test_label},
                "hidden": {},
                "contents": {},
                "custom_cards": [],
                "block_order": [],
                "positions": {},
                "styles": {},
                "assets": {},
                "page_manifest": {}
            },
            "note": "test_save_draft",
            "status": "draft"
        }
        response = requests.post(f"{BASE_URL}/api/alkabeer-bot/editor/draft/save", json=payload, timeout=10)
        assert response.status_code == 200, f"Save draft failed: {response.text}"
        data = response.json()
        assert data.get("success") is True
        assert "data" in data
        saved = data["data"]
        assert saved.get("version") >= 1
        assert saved.get("status") == "draft"
        print(f"✓ Save draft passed - version: {saved.get('version')}, note: {saved.get('note')}")
        return test_label
    
    def test_draft_persistence(self):
        """Test that saved draft is retrievable"""
        # Save a draft
        test_label = f"persistence-test-{uuid.uuid4().hex[:8]}"
        save_payload = {
            "user_id": TEST_USER_ID,
            "path": TEST_PATH_OPERATIONS,
            "config": {
                "labels": {"operations-active-tab-title": test_label},
                "hidden": {},
                "contents": {},
                "custom_cards": [],
                "block_order": [],
                "positions": {},
                "styles": {},
                "assets": {},
                "page_manifest": {}
            },
            "note": "persistence_test",
            "status": "draft"
        }
        save_response = requests.post(f"{BASE_URL}/api/alkabeer-bot/editor/draft/save", json=save_payload, timeout=10)
        assert save_response.status_code == 200
        saved_version = save_response.json()["data"]["version"]
        
        # Retrieve the draft
        params = {"user_id": TEST_USER_ID, "path": TEST_PATH_OPERATIONS}
        get_response = requests.get(f"{BASE_URL}/api/alkabeer-bot/editor/draft", params=params, timeout=10)
        assert get_response.status_code == 200
        retrieved = get_response.json()["data"]
        assert retrieved.get("version") == saved_version
        assert retrieved.get("config", {}).get("labels", {}).get("operations-active-tab-title") == test_label
        print(f"✓ Draft persistence verified - label: {test_label}")


class TestMoltBotEditorHistory:
    """History API tests"""
    
    def test_get_editor_history(self):
        """Test GET /api/alkabeer-bot/editor/history"""
        params = {"user_id": TEST_USER_ID, "path": TEST_PATH_OPERATIONS, "limit": 10}
        response = requests.get(f"{BASE_URL}/api/alkabeer-bot/editor/history", params=params, timeout=10)
        assert response.status_code == 200, f"Get history failed: {response.text}"
        data = response.json()
        assert data.get("success") is True
        assert "data" in data
        history = data["data"]
        assert isinstance(history, list)
        print(f"✓ Get history passed - {len(history)} entries found")
        if history:
            latest = history[0]
            print(f"  Latest: version={latest.get('version')}, status={latest.get('status')}, note={latest.get('note')}")


class TestMoltBotEditorComments:
    """Comments API tests"""
    
    def test_get_editor_comments(self):
        """Test GET /api/alkabeer-bot/editor/comments"""
        params = {"path": TEST_PATH_OPERATIONS, "limit": 20}
        response = requests.get(f"{BASE_URL}/api/alkabeer-bot/editor/comments", params=params, timeout=10)
        assert response.status_code == 200, f"Get comments failed: {response.text}"
        data = response.json()
        assert data.get("success") is True
        assert "data" in data
        comments = data["data"]
        assert isinstance(comments, list)
        print(f"✓ Get comments passed - {len(comments)} comments found")
    
    def test_add_editor_comment(self):
        """Test POST /api/alkabeer-bot/editor/comments"""
        test_message = f"Test comment {uuid.uuid4().hex[:8]}"
        payload = {
            "user_id": TEST_USER_ID,
            "path": TEST_PATH_OPERATIONS,
            "block_id": "operations-active-tab-title",
            "message": test_message,
            "author_name": "Test User"
        }
        response = requests.post(f"{BASE_URL}/api/alkabeer-bot/editor/comments", json=payload, timeout=10)
        assert response.status_code == 200, f"Add comment failed: {response.text}"
        data = response.json()
        assert data.get("success") is True
        comment = data["data"]
        assert comment.get("message") == test_message
        assert comment.get("id") is not None
        print(f"✓ Add comment passed - id: {comment.get('id')}")
        return comment.get("id")
    
    def test_update_editor_comment(self):
        """Test PUT /api/alkabeer-bot/editor/comments/{comment_id}"""
        # First add a comment
        add_payload = {
            "user_id": TEST_USER_ID,
            "path": TEST_PATH_OPERATIONS,
            "block_id": "test-block",
            "message": "Comment to update",
            "author_name": "Test User"
        }
        add_response = requests.post(f"{BASE_URL}/api/alkabeer-bot/editor/comments", json=add_payload, timeout=10)
        assert add_response.status_code == 200
        comment_id = add_response.json()["data"]["id"]
        
        # Update the comment
        update_payload = {"resolved": True}
        update_response = requests.put(f"{BASE_URL}/api/alkabeer-bot/editor/comments/{comment_id}", json=update_payload, timeout=10)
        assert update_response.status_code == 200, f"Update comment failed: {update_response.text}"
        data = update_response.json()
        assert data.get("success") is True
        assert data["data"].get("resolved") is True
        print(f"✓ Update comment passed - resolved: True")
    
    def test_delete_editor_comment(self):
        """Test DELETE /api/alkabeer-bot/editor/comments/{comment_id}"""
        # First add a comment
        add_payload = {
            "user_id": TEST_USER_ID,
            "path": TEST_PATH_OPERATIONS,
            "block_id": "test-block",
            "message": "Comment to delete",
            "author_name": "Test User"
        }
        add_response = requests.post(f"{BASE_URL}/api/alkabeer-bot/editor/comments", json=add_payload, timeout=10)
        assert add_response.status_code == 200
        comment_id = add_response.json()["data"]["id"]
        
        # Delete the comment
        delete_response = requests.delete(f"{BASE_URL}/api/alkabeer-bot/editor/comments/{comment_id}", timeout=10)
        assert delete_response.status_code == 200, f"Delete comment failed: {delete_response.text}"
        data = delete_response.json()
        assert data.get("success") is True
        print(f"✓ Delete comment passed")


class TestMoltBotEditorPublish:
    """Publish API tests - critical for end-to-end reflection"""
    
    def test_publish_editor_draft(self):
        """Test POST /api/alkabeer-bot/editor/publish"""
        test_label = f"published-label-{uuid.uuid4().hex[:8]}"
        payload = {
            "user_id": TEST_USER_ID,
            "path": TEST_PATH_OPERATIONS,
            "config": {
                "labels": {"operations-active-tab-title": test_label},
                "hidden": {},
                "contents": {},
                "custom_cards": [],
                "block_order": [],
                "positions": {},
                "styles": {},
                "assets": {},
                "page_manifest": {}
            },
            "note": "test_publish",
            "status": "published"
        }
        response = requests.post(f"{BASE_URL}/api/alkabeer-bot/editor/publish", json=payload, timeout=10)
        assert response.status_code == 200, f"Publish failed: {response.text}"
        data = response.json()
        assert data.get("success") is True
        published = data["data"]
        assert published.get("status") == "published"
        print(f"✓ Publish passed - version: {published.get('version')}")
        return test_label
    
    def test_publish_reflects_in_customization(self):
        """Test that published changes reflect in customization API"""
        # Publish a change
        test_label = f"reflect-test-{uuid.uuid4().hex[:8]}"
        publish_payload = {
            "user_id": TEST_USER_ID,
            "path": TEST_PATH_OPERATIONS,
            "config": {
                "labels": {"operations-active-tab-title": test_label},
                "hidden": {},
                "contents": {},
                "custom_cards": [],
                "block_order": [],
                "positions": {},
                "styles": {},
                "assets": {},
                "page_manifest": {}
            },
            "note": "reflection_test",
            "status": "published"
        }
        publish_response = requests.post(f"{BASE_URL}/api/alkabeer-bot/editor/publish", json=publish_payload, timeout=10)
        assert publish_response.status_code == 200
        
        # Check customization API
        params = {"user_id": TEST_USER_ID, "path": TEST_PATH_OPERATIONS}
        custom_response = requests.get(f"{BASE_URL}/api/alkabeer-bot/customization", params=params, timeout=10)
        assert custom_response.status_code == 200
        custom_data = custom_response.json()["data"]
        assert custom_data.get("labels", {}).get("operations-active-tab-title") == test_label
        print(f"✓ Publish reflection verified - label in customization: {test_label}")


class TestMoltBotCustomization:
    """Customization API tests"""
    
    def test_get_customization(self):
        """Test GET /api/alkabeer-bot/customization"""
        params = {"user_id": TEST_USER_ID, "path": TEST_PATH_DASHBOARD}
        response = requests.get(f"{BASE_URL}/api/alkabeer-bot/customization", params=params, timeout=10)
        assert response.status_code == 200, f"Get customization failed: {response.text}"
        data = response.json()
        assert data.get("success") is True
        assert "data" in data
        custom = data["data"]
        assert "labels" in custom
        assert "hidden" in custom
        assert "contents" in custom
        print(f"✓ Get customization passed")
    
    def test_save_customization(self):
        """Test PUT /api/alkabeer-bot/customization"""
        test_label = f"custom-label-{uuid.uuid4().hex[:8]}"
        payload = {
            "user_id": TEST_USER_ID,
            "path": TEST_PATH_DASHBOARD,
            "labels": {"dashboard-card-title": test_label},
            "hidden": {},
            "contents": {},
            "custom_cards": [],
            "block_order": [],
            "positions": {},
            "styles": {},
            "assets": {},
            "page_manifest": {}
        }
        response = requests.put(f"{BASE_URL}/api/alkabeer-bot/customization", json=payload, timeout=10)
        assert response.status_code == 200, f"Save customization failed: {response.text}"
        data = response.json()
        assert data.get("success") is True
        saved = data["data"]
        assert saved.get("labels", {}).get("dashboard-card-title") == test_label
        print(f"✓ Save customization passed - label: {test_label}")


class TestMoltBotEndToEndPublishReflection:
    """End-to-end publish reflection tests"""
    
    def test_operations_page_publish_reflection(self):
        """Test publishing to operations page and verifying reflection"""
        # Generate unique test value
        test_value = f"E2E-OPS-{uuid.uuid4().hex[:6]}"
        
        # Publish to operations page
        publish_payload = {
            "user_id": TEST_USER_ID,
            "path": TEST_PATH_OPERATIONS,
            "config": {
                "labels": {"operations-active-tab-title": test_value},
                "hidden": {},
                "contents": {"operations-active-tab-title": test_value},
                "custom_cards": [],
                "block_order": [],
                "positions": {},
                "styles": {},
                "assets": {},
                "page_manifest": {}
            },
            "note": "e2e_operations_test",
            "status": "published"
        }
        publish_response = requests.post(f"{BASE_URL}/api/alkabeer-bot/editor/publish", json=publish_payload, timeout=10)
        assert publish_response.status_code == 200, f"Publish failed: {publish_response.text}"
        
        # Verify in customization
        params = {"user_id": TEST_USER_ID, "path": TEST_PATH_OPERATIONS}
        custom_response = requests.get(f"{BASE_URL}/api/alkabeer-bot/customization", params=params, timeout=10)
        assert custom_response.status_code == 200
        custom_data = custom_response.json()["data"]
        
        assert custom_data.get("labels", {}).get("operations-active-tab-title") == test_value, \
            f"Label not reflected: expected {test_value}, got {custom_data.get('labels', {}).get('operations-active-tab-title')}"
        assert custom_data.get("contents", {}).get("operations-active-tab-title") == test_value, \
            f"Content not reflected: expected {test_value}, got {custom_data.get('contents', {}).get('operations-active-tab-title')}"
        
        print(f"✓ Operations page E2E publish reflection verified - value: {test_value}")
    
    def test_dashboard_page_publish_reflection(self):
        """Test publishing to dashboard page and verifying reflection"""
        # Generate unique test value
        test_value = f"E2E-DASH-{uuid.uuid4().hex[:6]}"
        
        # Publish to dashboard page
        publish_payload = {
            "user_id": TEST_USER_ID,
            "path": TEST_PATH_DASHBOARD,
            "config": {
                "labels": {"dashboard-card-title": test_value},
                "hidden": {},
                "contents": {"dashboard-card-title": test_value},
                "custom_cards": [],
                "block_order": [],
                "positions": {},
                "styles": {},
                "assets": {},
                "page_manifest": {}
            },
            "note": "e2e_dashboard_test",
            "status": "published"
        }
        publish_response = requests.post(f"{BASE_URL}/api/alkabeer-bot/editor/publish", json=publish_payload, timeout=10)
        assert publish_response.status_code == 200, f"Publish failed: {publish_response.text}"
        
        # Verify in customization
        params = {"user_id": TEST_USER_ID, "path": TEST_PATH_DASHBOARD}
        custom_response = requests.get(f"{BASE_URL}/api/alkabeer-bot/customization", params=params, timeout=10)
        assert custom_response.status_code == 200
        custom_data = custom_response.json()["data"]
        
        assert custom_data.get("labels", {}).get("dashboard-card-title") == test_value, \
            f"Label not reflected: expected {test_value}, got {custom_data.get('labels', {}).get('dashboard-card-title')}"
        
        print(f"✓ Dashboard page E2E publish reflection verified - value: {test_value}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
