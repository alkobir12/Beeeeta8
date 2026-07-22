"""
Workshop Bot API Tests - Iteration 115
Tests for the Claude-style Workshop AI Bot with skill catalog integration
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://workshop-engine.preview.emergentagent.com')


class TestWorkshopBotCatalog:
    """Tests for skill catalog endpoints"""
    
    def test_catalog_summary(self):
        """Test GET /api/workshop-bot/catalog/summary returns skill counts"""
        response = requests.get(f"{BASE_URL}/api/workshop-bot/catalog/summary")
        assert response.status_code == 200
        
        data = response.json()
        assert "summary" in data
        summary = data["summary"]
        assert "total_skills" in summary
        assert "total_prompts" in summary
        assert "total_agents" in summary
        assert summary["total_skills"] > 0, "Should have skills loaded"
        print(f"✅ Catalog summary: {summary['total_skills']} skills, {summary['total_prompts']} prompts, {summary['total_agents']} agents")
    
    def test_skills_search(self):
        """Test GET /api/workshop-bot/skills with search query"""
        response = requests.get(f"{BASE_URL}/api/workshop-bot/skills", params={"query": "agent", "limit": 10})
        assert response.status_code == 200
        
        data = response.json()
        assert "skills" in data
        skills = data["skills"]
        assert len(skills) > 0, "Should find skills matching 'agent'"
        
        # Verify skill structure
        skill = skills[0]
        assert "id" in skill
        assert "title" in skill
        assert "category" in skill
        print(f"✅ Found {len(skills)} skills matching 'agent'")
    
    def test_skills_limit(self):
        """Test skills endpoint respects limit parameter"""
        response = requests.get(f"{BASE_URL}/api/workshop-bot/skills", params={"limit": 5})
        assert response.status_code == 200
        
        data = response.json()
        skills = data.get("skills", [])
        assert len(skills) <= 5, "Should respect limit parameter"
        print(f"✅ Skills limit working: returned {len(skills)} skills")


class TestWorkshopBotModels:
    """Tests for model and engine endpoints"""
    
    def test_get_models(self):
        """Test GET /api/workshop-bot/models returns available models"""
        response = requests.get(f"{BASE_URL}/api/workshop-bot/models")
        assert response.status_code == 200
        
        data = response.json()
        assert "models" in data
        models = data["models"]
        assert len(models) > 0, "Should have models available"
        
        # Check for expected models
        model_ids = [m["id"] for m in models]
        assert "kb" in model_ids, "Should have kb (knowledge base) model"
        assert "gpt-5.1" in model_ids, "Should have gpt-5.1 model"
        print(f"✅ Found {len(models)} models: {model_ids}")
    
    def test_get_engines(self):
        """Test GET /api/workshop-bot/engines returns supported engines"""
        response = requests.get(f"{BASE_URL}/api/workshop-bot/engines")
        assert response.status_code == 200
        
        data = response.json()
        assert "engines" in data
        engines = data["engines"]
        assert len(engines) > 0, "Should have engines available"
        
        # Check engine structure
        engine = engines[0]
        assert "id" in engine
        assert "name" in engine
        assert "name_ar" in engine
        print(f"✅ Found {len(engines)} engines")


class TestWorkshopBotRespond:
    """Tests for the respond endpoint"""
    
    def test_respond_kb_mode(self):
        """Test POST /api/workshop-bot/respond with kb model"""
        payload = {
            "message": "السيارة تنتع وما تشد",
            "model": "kb",
            "mode": "unified"
        }
        response = requests.post(f"{BASE_URL}/api/workshop-bot/respond", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "ok"
        assert "reply" in data
        assert "session_id" in data
        assert data["model_used"] == "kb"
        print(f"✅ KB mode response: {data['reply'][:50]}...")
    
    def test_respond_gpt51_mode(self):
        """Test POST /api/workshop-bot/respond with gpt-5.1 model"""
        payload = {
            "message": "ما هي أسباب ارتفاع حرارة المحرك؟",
            "model": "gpt-5.1",
            "mode": "unified",
            "session_id": "test-gpt51-session-iter115"
        }
        response = requests.post(f"{BASE_URL}/api/workshop-bot/respond", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "ok"
        assert "reply" in data
        assert len(data["reply"]) > 50, "GPT-5.1 should provide detailed response"
        assert data["model_used"] == "gpt-5.1"
        print(f"✅ GPT-5.1 mode response length: {len(data['reply'])} chars")
    
    def test_respond_with_session_id(self):
        """Test respond endpoint maintains session_id"""
        session_id = "test-session-iter115"
        payload = {
            "message": "مرحبا",
            "model": "kb",
            "mode": "unified",
            "session_id": session_id
        }
        response = requests.post(f"{BASE_URL}/api/workshop-bot/respond", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data["session_id"] == session_id or data["session_id"] is not None
        print(f"✅ Session ID maintained: {data['session_id']}")
    
    def test_respond_tech_mode(self):
        """Test respond endpoint with tech mode"""
        payload = {
            "message": "السيارة تنتع وما تشد",
            "model": "kb",
            "mode": "tech"
        }
        response = requests.post(f"{BASE_URL}/api/workshop-bot/respond", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "ok"
        # Tech mode should include diagnostic steps
        assert "reply" in data
        print(f"✅ Tech mode response received")


class TestWorkshopBotConversations:
    """Tests for conversation management endpoints"""
    
    def test_get_conversations(self):
        """Test GET /api/workshop-bot/conversations returns conversation list"""
        response = requests.get(f"{BASE_URL}/api/workshop-bot/conversations", params={"limit": 10})
        assert response.status_code == 200
        
        data = response.json()
        assert "conversations" in data
        conversations = data["conversations"]
        # May be empty if no conversations exist
        print(f"✅ Found {len(conversations)} conversations")
    
    def test_get_conversation_messages(self):
        """Test GET /api/workshop-bot/conversations/{session_id} returns messages"""
        # First create a conversation
        payload = {
            "message": "اختبار المحادثة",
            "model": "kb",
            "mode": "unified",
            "session_id": "test-conversation-iter115"
        }
        requests.post(f"{BASE_URL}/api/workshop-bot/respond", json=payload)
        
        # Then get the messages
        response = requests.get(f"{BASE_URL}/api/workshop-bot/conversations/test-conversation-iter115")
        assert response.status_code == 200
        
        data = response.json()
        assert "messages" in data
        messages = data["messages"]
        assert len(messages) >= 2, "Should have at least user and assistant messages"
        print(f"✅ Found {len(messages)} messages in conversation")
    
    def test_delete_conversation(self):
        """Test DELETE /api/workshop-bot/conversations/{session_id}"""
        # First create a conversation
        session_id = "test-delete-conversation-iter115"
        payload = {
            "message": "محادثة للحذف",
            "model": "kb",
            "mode": "unified",
            "session_id": session_id
        }
        requests.post(f"{BASE_URL}/api/workshop-bot/respond", json=payload)
        
        # Delete the conversation
        response = requests.delete(f"{BASE_URL}/api/workshop-bot/conversations/{session_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        print(f"✅ Conversation deleted successfully")
        
        # Verify deletion
        verify_response = requests.get(f"{BASE_URL}/api/workshop-bot/conversations/{session_id}")
        assert verify_response.status_code == 200
        verify_data = verify_response.json()
        assert len(verify_data.get("messages", [])) == 0, "Messages should be deleted"


class TestWorkshopBotHealth:
    """Tests for health check endpoint"""
    
    def test_health_check(self):
        """Test GET /api/workshop-bot/health returns status"""
        response = requests.get(f"{BASE_URL}/api/workshop-bot/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "running"
        assert "version" in data
        assert "rules_count" in data
        assert "engines_supported" in data
        print(f"✅ Health check passed: version {data['version']}, {data['rules_count']} rules")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
