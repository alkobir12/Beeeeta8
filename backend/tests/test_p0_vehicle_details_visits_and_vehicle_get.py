#!/usr/bin/env python3
"""
P0 Vehicle Details, Visits, and Vehicle GET API Testing
اختبار APIs المركبات والزيارات - الأولوية صفر

Tests:
1. GET /api/vehicles returns 200 JSON
2. GET /api/vehicles/{valid_id} returns 200 with valid ID: f3422cc1-dd9c-4e69-8205-0aa50b3795a1
3. GET /api/vehicles/{nonexistent_id} returns 404 (not 500) with random UUID: 11111111-1111-1111-1111-111111111111
4. POST /api/vehicles/{valid_id}/visits works and returns 200 with ISO dates (no datetime objects)
5. GET /api/vehicles/{valid_id}/visits returns 200
"""

import pytest
import requests
import json
import os
from datetime import datetime

# Configuration
# Use REACT_APP_BACKEND_URL (from frontend/.env) when available; fallback to the preview URL.
_DEFAULT_BACKEND_BASE = "https://accounting-ssot-fix.preview.emergentagent.com"
try:
    _env_path = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", ".env")
    _backend = None
    if os.path.exists(_env_path):
        with open(_env_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    _backend = line.split("=", 1)[1].strip()
                    break
    BACKEND_URL = f"{(_backend or _DEFAULT_BACKEND_BASE).rstrip('/')}/api"
except Exception:
    BACKEND_URL = f"{_DEFAULT_BACKEND_BASE}/api"

VALID_VEHICLE_ID = "f3422cc1-dd9c-4e69-8205-0aa50b3795a1"
NONEXISTENT_VEHICLE_ID = "11111111-1111-1111-1111-111111111111"

class TestVehicleDetailsVisitsAPI:
    """Test class for Vehicle Details and Visits API endpoints"""
    
    def test_1_get_vehicles_returns_200_json(self):
        """
        Test 1: تأكد أن GET /api/vehicles يرجع 200 JSON
        """
        print("\n🧪 Test 1: GET /api/vehicles returns 200 JSON")
        
        url = f"{BACKEND_URL}/vehicles"
        print(f"📡 Request: GET {url}")
        
        response = requests.get(url, timeout=30)
        print(f"📊 Status Code: {response.status_code}")
        
        # Should return 200
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Should return JSON
        try:
            data = response.json()
            assert isinstance(data, list), "Response should be a JSON list"
            print(f"✅ Success: Got {len(data)} vehicles in JSON format")
        except json.JSONDecodeError:
            pytest.fail("Response is not valid JSON")
    
    def test_2_get_vehicle_valid_id_returns_200(self):
        """
        Test 2: تأكد أن GET /api/vehicles/{valid_id} يرجع 200
        استخدم valid id: f3422cc1-dd9c-4e69-8205-0aa50b3795a1
        """
        print(f"\n🧪 Test 2: GET /api/vehicles/{VALID_VEHICLE_ID} returns 200")
        
        url = f"{BACKEND_URL}/vehicles/{VALID_VEHICLE_ID}"
        print(f"📡 Request: GET {url}")
        
        response = requests.get(url, timeout=30)
        print(f"📊 Status Code: {response.status_code}")
        
        # Should return 200 for valid vehicle ID
        assert response.status_code == 200, f"Expected 200 for valid vehicle ID, got {response.status_code}"
        
        # Should return JSON with vehicle data
        try:
            data = response.json()
            assert isinstance(data, dict), "Response should be a JSON object"
            assert "id" in data, "Response should contain vehicle ID"
            assert data["id"] == VALID_VEHICLE_ID, "Response should contain the correct vehicle ID"
            print(f"✅ Success: Got vehicle data for ID {VALID_VEHICLE_ID}")
        except json.JSONDecodeError:
            pytest.fail("Response is not valid JSON")
    
    def test_3_get_vehicle_nonexistent_id_returns_404_not_500(self):
        """
        Test 3: تأكد أن GET /api/vehicles/{nonexistent_id} لا يعطي 500
        استخدم id عشوائي UUID مثل 11111111-1111-1111-1111-111111111111
        المتوقع: 404 Vehicle not found
        """
        print(f"\n🧪 Test 3: GET /api/vehicles/{NONEXISTENT_VEHICLE_ID} returns 404 (not 500)")
        
        url = f"{BACKEND_URL}/vehicles/{NONEXISTENT_VEHICLE_ID}"
        print(f"📡 Request: GET {url}")
        
        response = requests.get(url, timeout=30)
        print(f"📊 Status Code: {response.status_code}")
        
        # Should return 404, NOT 500
        assert response.status_code == 404, f"Expected 404 for nonexistent vehicle, got {response.status_code}"
        
        # Should return JSON with error message
        try:
            data = response.json()
            assert isinstance(data, dict), "Response should be a JSON object"
            detail = data.get("detail", "").lower()
            assert "not found" in detail or "غير موجود" in detail, f"Expected 'not found' message, got: {detail}"
            print(f"✅ Success: Got 404 with proper error message: {data.get('detail')}")
        except json.JSONDecodeError:
            pytest.fail("Response is not valid JSON")
    
    def test_4_post_vehicle_visits_returns_200_with_iso_dates(self):
        """
        Test 4: تأكد أن POST /api/vehicles/{valid_id}/visits يعمل ويرجع 200 
        مع تواريخ ISO بدون datetime object (أرسل notes JSON نصي + status)
        """
        print(f"\n🧪 Test 4: POST /api/vehicles/{VALID_VEHICLE_ID}/visits returns 200 with ISO dates")
        
        url = f"{BACKEND_URL}/vehicles/{VALID_VEHICLE_ID}/visits"
        print(f"📡 Request: POST {url}")
        
        # Create visit data with notes as JSON string and status
        visit_data = {
            "notes": json.dumps({
                "items": [
                    {
                        "itemType": "service",
                        "name": "خدمة اختبار",
                        "quantity": 1,
                        "price": 150
                    }
                ]
            }),
            "status": "in_progress",
            "mileage": 50000,
            "description": "زيارة اختبار للمركبة"
        }
        
        print(f"📤 Data: {json.dumps(visit_data, indent=2, ensure_ascii=False)}")
        
        response = requests.post(url, json=visit_data, timeout=30)
        print(f"📊 Status Code: {response.status_code}")
        
        # Should return 200 or 201
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}"
        
        # Should return JSON with visit data
        try:
            data = response.json()
            assert isinstance(data, dict), "Response should be a JSON object"
            
            # Check for ISO date format (no datetime objects)
            response_str = json.dumps(data)
            assert "datetime.datetime" not in response_str, "Response should not contain datetime objects"
            
            # Check for proper date fields
            if "created_at" in data:
                created_at = data["created_at"]
                # Should be ISO format string
                assert isinstance(created_at, str), "created_at should be string in ISO format"
                # Try to parse as ISO date
                datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            
            print("✅ Success: Created visit with proper ISO dates")
            
            # Store visit ID for next test
            self.created_visit_id = data.get("id")
            
        except json.JSONDecodeError:
            pytest.fail("Response is not valid JSON")
        except ValueError as e:
            pytest.fail(f"Date parsing failed: {e}")
    
    def test_5_get_vehicle_visits_returns_200(self):
        """
        Test 5: تأكد أن GET /api/vehicles/{valid_id}/visits يرجع 200
        """
        print(f"\n🧪 Test 5: GET /api/vehicles/{VALID_VEHICLE_ID}/visits returns 200")
        
        url = f"{BACKEND_URL}/vehicles/{VALID_VEHICLE_ID}/visits"
        print(f"📡 Request: GET {url}")
        
        response = requests.get(url, timeout=30)
        print(f"📊 Status Code: {response.status_code}")
        
        # Should return 200
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Should return JSON with visits list
        try:
            data = response.json()
            assert isinstance(data, list), "Response should be a JSON list"
            print(f"✅ Success: Got {len(data)} visits for vehicle {VALID_VEHICLE_ID}")
            
            # Check that visits have proper structure
            for visit in data:
                assert isinstance(visit, dict), "Each visit should be a JSON object"
                assert "id" in visit, "Each visit should have an ID"
                
                # Check date fields are in ISO format
                for date_field in ["created_at", "updated_at"]:
                    if date_field in visit and visit[date_field]:
                        assert isinstance(visit[date_field], str), f"{date_field} should be string"
                        # Try to parse as ISO date
                        datetime.fromisoformat(visit[date_field].replace('Z', '+00:00'))
            
        except json.JSONDecodeError:
            pytest.fail("Response is not valid JSON")
        except ValueError as e:
            pytest.fail(f"Date parsing failed: {e}")

def run_tests():
    """Run all tests and return results"""
    print("🚀 Starting P0 Vehicle Details, Visits, and Vehicle GET API Tests")
    print(f"🌐 Backend URL: {BACKEND_URL}")
    print(f"🚗 Valid Vehicle ID: {VALID_VEHICLE_ID}")
    print(f"❌ Nonexistent Vehicle ID: {NONEXISTENT_VEHICLE_ID}")
    print(f"⏰ Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    test_instance = TestVehicleDetailsVisitsAPI()
    results = []
    
    # Test 1: GET /api/vehicles
    try:
        test_instance.test_1_get_vehicles_returns_200_json()
        results.append(("GET /api/vehicles returns 200 JSON", True))
    except Exception as e:
        print(f"❌ Test 1 failed: {e}")
        results.append(("GET /api/vehicles returns 200 JSON", False))
    
    # Test 2: GET /api/vehicles/{valid_id}
    try:
        test_instance.test_2_get_vehicle_valid_id_returns_200()
        results.append(("GET /api/vehicles/{valid_id} returns 200", True))
    except Exception as e:
        print(f"❌ Test 2 failed: {e}")
        results.append(("GET /api/vehicles/{valid_id} returns 200", False))
    
    # Test 3: GET /api/vehicles/{nonexistent_id}
    try:
        test_instance.test_3_get_vehicle_nonexistent_id_returns_404_not_500()
        results.append(("GET /api/vehicles/{nonexistent_id} returns 404", True))
    except Exception as e:
        print(f"❌ Test 3 failed: {e}")
        results.append(("GET /api/vehicles/{nonexistent_id} returns 404", False))
    
    # Test 4: POST /api/vehicles/{valid_id}/visits
    try:
        test_instance.test_4_post_vehicle_visits_returns_200_with_iso_dates()
        results.append(("POST /api/vehicles/{valid_id}/visits with ISO dates", True))
    except Exception as e:
        print(f"❌ Test 4 failed: {e}")
        results.append(("POST /api/vehicles/{valid_id}/visits with ISO dates", False))
    
    # Test 5: GET /api/vehicles/{valid_id}/visits
    try:
        test_instance.test_5_get_vehicle_visits_returns_200()
        results.append(("GET /api/vehicles/{valid_id}/visits returns 200", True))
    except Exception as e:
        print(f"❌ Test 5 failed: {e}")
        results.append(("GET /api/vehicles/{valid_id}/visits returns 200", False))
    
    # Summary
    print("\n" + "="*60)
    print("📊 TEST RESULTS SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\n📈 Final Result: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All P0 Vehicle API tests passed!")
        return True
    else:
        print(f"⚠️ {total - passed} tests failed")
        return False

if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)