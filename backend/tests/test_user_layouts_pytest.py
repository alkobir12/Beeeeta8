import pytest
import httpx
from fastapi.testclient import TestClient
import sys
import os

# Add the backend directory to the path to import the server
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import the FastAPI app
from server import app

# Use TestClient for local testing
client = TestClient(app)

# Also test against the live API
LIVE_BASE_URL = "https://vehicle-accounting-2.preview.emergentagent.com/api"

class TestUserLayoutsAPI:
    """Pytest test class for User Layouts API"""
    
    @pytest.fixture
    def test_user_id(self):
        return "pytest_user_123"
    
    @pytest.fixture
    def test_page(self):
        return "vehicleDetails"
    
    @pytest.fixture
    def test_blocks(self):
        return ["vehicle_info", "visits", "financial_summary", "guidance", "status_actions"]
    
    def test_get_initial_empty_layout_local(self, test_user_id, test_page):
        """Test GET endpoint returns empty blocks initially (local TestClient)"""
        response = client.get(f"/api/user-layouts/{test_user_id}/{test_page}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["userId"] == test_user_id
        assert data["page"] == test_page
        assert isinstance(data["blocks"], list)
    
    def test_put_layout_update_local(self, test_user_id, test_page, test_blocks):
        """Test PUT endpoint saves blocks (local TestClient)"""
        payload = {
            "page": test_page,
            "blocks": test_blocks
        }
        
        response = client.put(f"/api/user-layouts/{test_user_id}/{test_page}", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["userId"] == test_user_id
        assert data["page"] == test_page
        assert data["blocks"] == test_blocks
    
    def test_get_saved_layout_local(self, test_user_id, test_page, test_blocks):
        """Test GET endpoint returns saved blocks (local TestClient)"""
        # First save some blocks
        payload = {"page": test_page, "blocks": test_blocks}
        client.put(f"/api/user-layouts/{test_user_id}/{test_page}", json=payload)
        
        # Then retrieve them
        response = client.get(f"/api/user-layouts/{test_user_id}/{test_page}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["blocks"] == test_blocks
    
    def test_page_mismatch_error_local(self, test_user_id, test_page):
        """Test PUT with page mismatch returns 400 error (local TestClient)"""
        payload = {
            "page": "wrongPage",  # Different from URL
            "blocks": ["block1", "block2"]
        }
        
        response = client.put(f"/api/user-layouts/{test_user_id}/{test_page}", json=payload)
        
        assert response.status_code == 400
        assert "Page mismatch" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_live_api_endpoints(self, test_user_id, test_page, test_blocks):
        """Test against the live API endpoints"""
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            # Test GET initial empty
            response = await http_client.get(f"{LIVE_BASE_URL}/user-layouts/{test_user_id}/{test_page}")
            assert response.status_code == 200
            data = response.json()
            assert "blocks" in data
            
            # Test PUT update
            payload = {"page": test_page, "blocks": test_blocks}
            response = await http_client.put(
                f"{LIVE_BASE_URL}/user-layouts/{test_user_id}/{test_page}",
                json=payload
            )
            assert response.status_code == 200
            data = response.json()
            assert data["blocks"] == test_blocks
            
            # Test GET saved
            response = await http_client.get(f"{LIVE_BASE_URL}/user-layouts/{test_user_id}/{test_page}")
            assert response.status_code == 200
            data = response.json()
            assert data["blocks"] == test_blocks

if __name__ == "__main__":
    # Run pytest programmatically
    pytest.main([__file__, "-v"])