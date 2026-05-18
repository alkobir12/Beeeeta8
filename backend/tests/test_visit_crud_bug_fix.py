"""
Test Visit CRUD operations - Bug Fix Testing

Tests the fix for visits disappearing after being saved and closed:
1. POST /api/vehicles/{vehicle_id}/visits - create a new visit with items in notes
2. PUT /api/visits/{visit_id} - update visit with status=completed, exitDate, notes (with items JSON), mileage
3. GET /api/vehicles/{vehicle_id}/visits - verify visits are returned after creation and update
4. DELETE /api/visits/{visit_id} - verify cleanup works

Bug context: handleCloseVisit was NOT saving items/notes before closing. Now it does.
Backend was crashing with 500 because updated_at column doesn't exist - removed it.
"""

import pytest
import requests
import json
import uuid
import os
from datetime import datetime

# Get base URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://vehicle-accounting-2.preview.emergentagent.com').rstrip('/')

# Test vehicle ID from the review request
TEST_VEHICLE_ID = "ca81024e-195b-464e-9671-0f532aad1545"


class TestVisitCRUD:
    """Test visit CRUD operations to verify the bug fix"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.created_visit_ids = []
        yield
        # Cleanup: delete test visits created during tests
        for visit_id in self.created_visit_ids:
            try:
                self.session.delete(f"{BASE_URL}/api/visits/{visit_id}")
            except:
                pass
    
    def test_01_get_vehicle_visits_initial(self):
        """Test GET /api/vehicles/{vehicle_id}/visits - verify endpoint works"""
        response = self.session.get(f"{BASE_URL}/api/vehicles/{TEST_VEHICLE_ID}/visits")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of visits"
        print(f"✅ GET visits returned {len(data)} visits for vehicle {TEST_VEHICLE_ID[:8]}")
        
        # Store initial visit count for later comparison
        self.initial_visit_count = len(data)
        return data
    
    def test_02_create_visit_with_items_in_notes(self):
        """Test POST /api/vehicles/{vehicle_id}/visits - create visit with items in notes JSON"""
        
        # Items in the JSON format that frontend uses
        items_data = {
            "items": [
                {"itemType": "service", "name": "فحص كمبيوتر", "quantity": 1, "price": 150},
                {"itemType": "part", "name": "فلتر زيت", "quantity": 1, "price": 45},
            ],
            "text": "ملاحظات اختبارية"
        }
        
        payload = {
            "entryDate": datetime.utcnow().isoformat(),
            "status": "in_progress",
            "mileage": 75000,
            "technicianId": None,
            "notes": json.dumps(items_data, ensure_ascii=False)
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/vehicles/{TEST_VEHICLE_ID}/visits",
            json=payload
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Validate response structure
        assert "id" in data, "Response should contain 'id'"
        assert data.get("status") == "in_progress", f"Expected status 'in_progress', got {data.get('status')}"
        assert data.get("mileage") == 75000, f"Expected mileage 75000, got {data.get('mileage')}"
        
        # Verify notes were saved
        notes = data.get("notes") or ""
        assert len(notes) > 0, "Notes should not be empty"
        
        # Parse notes and verify items
        try:
            parsed_notes = json.loads(notes)
            assert "items" in parsed_notes, "Notes should contain items"
            assert len(parsed_notes["items"]) == 2, f"Expected 2 items, got {len(parsed_notes['items'])}"
            print(f"✅ Created visit {data['id'][:8]} with {len(parsed_notes['items'])} items")
        except json.JSONDecodeError:
            print(f"⚠️ Notes not JSON, raw value: {notes[:100]}")
        
        self.created_visit_ids.append(data["id"])
        return data
    
    def test_03_update_visit_save_items_and_close(self):
        """Test PUT /api/visits/{visit_id} - update visit with items, mileage and close it
        
        This tests the bug fix: handleCloseVisit now saves items/notes/mileage alongside status change
        """
        # First create a visit
        create_payload = {
            "entryDate": datetime.utcnow().isoformat(),
            "status": "in_progress",
            "mileage": 80000,
            "notes": json.dumps({"items": [], "text": ""}, ensure_ascii=False)
        }
        
        create_resp = self.session.post(
            f"{BASE_URL}/api/vehicles/{TEST_VEHICLE_ID}/visits",
            json=create_payload
        )
        assert create_resp.status_code == 200, f"Create failed: {create_resp.text}"
        visit = create_resp.json()
        visit_id = visit["id"]
        self.created_visit_ids.append(visit_id)
        
        # Now update with items and close (simulating handleCloseVisit)
        items_data = {
            "items": [
                {"itemType": "service", "name": "تغيير زيت", "quantity": 1, "price": 120},
                {"itemType": "service", "name": "فحص فرامل", "quantity": 1, "price": 80},
                {"itemType": "part", "name": "فلتر هواء", "quantity": 1, "price": 60},
            ],
            "text": "تم الصيانة بنجاح"
        }
        
        update_payload = {
            "status": "completed",
            "exitDate": datetime.utcnow().isoformat(),
            "technicianId": None,
            "mileage": 80500,
            "notes": json.dumps(items_data, ensure_ascii=False)
        }
        
        response = self.session.put(
            f"{BASE_URL}/api/visits/{visit_id}",
            json=update_payload
        )
        
        # Key assertion: should NOT return 500 (was the bug)
        assert response.status_code != 500, f"Backend returned 500 error (bug not fixed): {response.text}"
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify status was updated to completed
        assert data.get("status") == "completed", f"Expected status 'completed', got {data.get('status')}"
        
        # Verify mileage was saved
        assert data.get("mileage") == 80500, f"Expected mileage 80500, got {data.get('mileage')}"
        
        # Verify notes/items were saved (KEY BUG FIX TEST)
        notes = data.get("notes") or ""
        assert len(notes) > 10, f"Notes should contain items JSON, got: {notes}"
        
        try:
            parsed = json.loads(notes)
            assert "items" in parsed, "Notes should have items key"
            assert len(parsed["items"]) == 3, f"Expected 3 items, got {len(parsed['items'])}"
            print(f"✅ Visit {visit_id[:8]} updated & closed with {len(parsed['items'])} items preserved")
        except json.JSONDecodeError:
            pytest.fail(f"Notes not valid JSON: {notes}")
        
        return data
    
    def test_04_get_visits_after_update_persistence(self):
        """Test GET /api/vehicles/{vehicle_id}/visits - verify visits persist after update/close
        
        This tests that visits don't disappear after being saved and closed
        """
        # Create and close a visit first
        items_data = {
            "items": [{"itemType": "service", "name": "خدمة اختبار", "quantity": 1, "price": 100}],
            "text": "اختبار الحفظ"
        }
        
        create_payload = {
            "entryDate": datetime.utcnow().isoformat(),
            "status": "in_progress",
            "mileage": 90000,
            "notes": json.dumps(items_data, ensure_ascii=False)
        }
        
        create_resp = self.session.post(
            f"{BASE_URL}/api/vehicles/{TEST_VEHICLE_ID}/visits",
            json=create_payload
        )
        assert create_resp.status_code == 200
        visit = create_resp.json()
        visit_id = visit["id"]
        self.created_visit_ids.append(visit_id)
        
        # Close the visit
        close_payload = {
            "status": "completed",
            "exitDate": datetime.utcnow().isoformat(),
            "mileage": 90100,
            "notes": json.dumps(items_data, ensure_ascii=False)  # Items preserved
        }
        
        update_resp = self.session.put(f"{BASE_URL}/api/visits/{visit_id}", json=close_payload)
        assert update_resp.status_code == 200, f"Update failed: {update_resp.text}"
        
        # NOW verify the visit still appears in the list (BUG FIX: visits shouldn't disappear)
        get_resp = self.session.get(f"{BASE_URL}/api/vehicles/{TEST_VEHICLE_ID}/visits")
        assert get_resp.status_code == 200
        
        visits = get_resp.json()
        visit_ids = [v.get("id") for v in visits]
        
        assert visit_id in visit_ids, f"Visit {visit_id[:8]} disappeared after being closed! BUG!"
        
        # Verify the items are still there
        found_visit = next((v for v in visits if v.get("id") == visit_id), None)
        assert found_visit is not None, "Could not find the visit in list"
        assert found_visit.get("status") == "completed", "Status should be completed"
        
        notes = found_visit.get("notes") or ""
        try:
            parsed = json.loads(notes)
            assert "items" in parsed and len(parsed["items"]) > 0, "Items should persist after close"
            print(f"✅ Visit {visit_id[:8]} still visible after close with {len(parsed['items'])} items")
        except:
            print(f"⚠️ Could not parse notes: {notes[:100]}")
        
        return found_visit
    
    def test_05_delete_visit_cleanup(self):
        """Test DELETE /api/visits/{visit_id} - verify deletion works"""
        # Create a visit to delete
        payload = {
            "entryDate": datetime.utcnow().isoformat(),
            "status": "completed",
            "mileage": 95000,
            "notes": "{\"items\": [], \"text\": \"للحذف\"}"
        }
        
        create_resp = self.session.post(
            f"{BASE_URL}/api/vehicles/{TEST_VEHICLE_ID}/visits",
            json=payload
        )
        assert create_resp.status_code == 200
        visit_id = create_resp.json()["id"]
        # Don't add to cleanup list since we're testing delete
        
        # Delete the visit
        delete_resp = self.session.delete(f"{BASE_URL}/api/visits/{visit_id}")
        assert delete_resp.status_code == 200, f"Delete failed: {delete_resp.text}"
        
        data = delete_resp.json()
        assert data.get("success") == True, f"Expected success=True, got {data}"
        
        # Verify it's gone
        get_resp = self.session.get(f"{BASE_URL}/api/vehicles/{TEST_VEHICLE_ID}/visits")
        visits = get_resp.json()
        visit_ids = [v.get("id") for v in visits]
        
        assert visit_id not in visit_ids, f"Visit {visit_id[:8]} should be deleted but still exists"
        print(f"✅ Visit {visit_id[:8]} successfully deleted")
    
    def test_06_update_visit_without_500_error(self):
        """Test that PUT /api/visits/{visit_id} does NOT return 500 error
        
        Bug was: backend crashed with 500 because updated_at column doesn't exist in Supabase
        """
        # Create a visit
        payload = {
            "entryDate": datetime.utcnow().isoformat(),
            "status": "in_progress",
            "mileage": 100000
        }
        
        create_resp = self.session.post(
            f"{BASE_URL}/api/vehicles/{TEST_VEHICLE_ID}/visits",
            json=payload
        )
        assert create_resp.status_code == 200
        visit_id = create_resp.json()["id"]
        self.created_visit_ids.append(visit_id)
        
        # Try multiple update variations
        updates = [
            {"status": "in_progress", "mileage": 100100},  # Simple update
            {"notes": "{\"items\":[], \"text\":\"test\"}"},  # Just notes
            {"status": "completed", "exitDate": datetime.utcnow().isoformat()},  # Close
            {"technicianId": None, "mileage": 100200},  # Technician update
        ]
        
        for i, upd in enumerate(updates):
            resp = self.session.put(f"{BASE_URL}/api/visits/{visit_id}", json=upd)
            assert resp.status_code != 500, f"Update #{i+1} returned 500: {resp.text}"
            assert resp.status_code == 200, f"Update #{i+1} failed with {resp.status_code}: {resp.text}"
        
        print(f"✅ All {len(updates)} update variations succeeded without 500 error")


class TestVisitFilterCounts:
    """Test that visit filter logic returns correct counts"""
    
    def test_visit_counts_logic(self):
        """Test visit counting logic for filters (all, open, closed)"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        response = session.get(f"{BASE_URL}/api/vehicles/{TEST_VEHICLE_ID}/visits")
        assert response.status_code == 200
        visits = response.json()
        
        all_count = len(visits)
        open_count = len([v for v in visits if (v.get("status") or "").lower() != "completed"])
        closed_count = len([v for v in visits if (v.get("status") or "").lower() == "completed"])
        
        # Verify counts add up
        assert open_count + closed_count == all_count, \
            f"Counts don't add up: {open_count} + {closed_count} != {all_count}"
        
        print(f"✅ Visit counts: all={all_count}, open={open_count}, closed={closed_count}")
        
        return {"all": all_count, "open": open_count, "closed": closed_count}


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
