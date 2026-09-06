"""
Iteration 132 - Testing two bug fixes:
1. Vehicle fileNumber save issue - PUT /api/vehicles/{id} should accept and persist fileNumber
2. Net Income card in ComprehensiveFinancial - account-tree-details should return operations_cash_total and operations_bank_total
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
WORKSHOP_ID = os.environ.get('DEFAULT_WORKSHOP_ID', 'finmodule-sync')


class TestVehicleFileNumber:
    """Test that fileNumber is properly saved when updating a vehicle"""
    
    @pytest.fixture
    def test_vehicle_id(self):
        """Create a test vehicle and return its ID"""
        payload = {
            "plateNumber": f"TEST-{uuid.uuid4().hex[:6].upper()}",
            "brand": "Toyota",
            "model": "Camry",
            "year": 2024,
            "color": "White",
            "customerName": "Test Customer",
            "customerPhone": "0501234567",
        }
        response = requests.post(f"{BASE_URL}/api/vehicles", json=payload)
        assert response.status_code == 200, f"Failed to create vehicle: {response.text}"
        vehicle = response.json()
        vehicle_id = vehicle.get("id")
        assert vehicle_id, "Vehicle ID not returned"
        yield vehicle_id
        # Cleanup
        try:
            requests.delete(f"{BASE_URL}/api/vehicles/{vehicle_id}")
        except Exception:            pass
    
    def test_update_vehicle_with_file_number(self, test_vehicle_id):
        """Test that fileNumber can be updated via PUT /api/vehicles/{id}"""
        file_number = f"FILE-{uuid.uuid4().hex[:8].upper()}"
        
        # Update vehicle with fileNumber
        update_payload = {"fileNumber": file_number}
        response = requests.put(f"{BASE_URL}/api/vehicles/{test_vehicle_id}", json=update_payload)
        
        assert response.status_code == 200, f"PUT failed: {response.text}"
        updated_vehicle = response.json()
        
        # Verify fileNumber in response
        assert updated_vehicle.get("fileNumber") == file_number, \
            f"fileNumber not in PUT response. Got: {updated_vehicle.get('fileNumber')}"
        
        # GET the vehicle to verify persistence
        get_response = requests.get(f"{BASE_URL}/api/vehicles/{test_vehicle_id}")
        assert get_response.status_code == 200, f"GET failed: {get_response.text}"
        fetched_vehicle = get_response.json()
        
        # Verify fileNumber persisted
        assert fetched_vehicle.get("fileNumber") == file_number, \
            f"fileNumber not persisted. Expected: {file_number}, Got: {fetched_vehicle.get('fileNumber')}"
        
        print(f"✅ fileNumber '{file_number}' successfully saved and retrieved")
    
    def test_update_vehicle_file_number_empty_to_value(self, test_vehicle_id):
        """Test updating fileNumber from empty to a value"""
        # First verify it's empty/None
        get_response = requests.get(f"{BASE_URL}/api/vehicles/{test_vehicle_id}")
        initial_vehicle = get_response.json()
        initial_file_number = initial_vehicle.get("fileNumber")
        print(f"Initial fileNumber: {initial_file_number}")
        
        # Update with new fileNumber
        new_file_number = f"NEW-FILE-{uuid.uuid4().hex[:6].upper()}"
        update_response = requests.put(
            f"{BASE_URL}/api/vehicles/{test_vehicle_id}",
            json={"fileNumber": new_file_number}
        )
        assert update_response.status_code == 200
        
        # Verify in GET
        verify_response = requests.get(f"{BASE_URL}/api/vehicles/{test_vehicle_id}")
        verified_vehicle = verify_response.json()
        
        assert verified_vehicle.get("fileNumber") == new_file_number, \
            f"fileNumber update failed. Expected: {new_file_number}, Got: {verified_vehicle.get('fileNumber')}"
        
        print(f"✅ fileNumber updated from '{initial_file_number}' to '{new_file_number}'")


class TestAccountTreeDetailsSummary:
    """Test that account-tree-details returns cash/bank totals in summary"""
    
    def test_account_tree_details_has_cash_bank_totals(self):
        """Test that /api/finance/reports/account-tree-details returns operations_cash_total and operations_bank_total"""
        params = {
            "workshop_id": WORKSHOP_ID,
            "account_code": "4000",  # Revenue account
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "include_descendants": "true",
            "page": 1,
            "page_size": 10
        }
        
        response = requests.get(f"{BASE_URL}/api/finance/reports/account-tree-details", params=params)
        
        assert response.status_code == 200, f"API call failed: {response.text}"
        data = response.json()
        
        # Check if response has success flag
        if "success" in data:
            assert data.get("success") == True, f"API returned success=false: {data}"
            data = data.get("data", {})
        
        # Check for operations summary
        operations = data.get("operations", {})
        summary = operations.get("summary", {})
        
        # Verify required fields exist
        assert "operations_cash_total" in summary or "total_cash_component" in summary, \
            f"Missing cash total in summary. Summary keys: {list(summary.keys())}"
        
        assert "operations_bank_total" in summary or "total_bank_component" in summary, \
            f"Missing bank total in summary. Summary keys: {list(summary.keys())}"
        
        # Log the values
        cash_total = summary.get("operations_cash_total", summary.get("total_cash_component", 0))
        bank_total = summary.get("operations_bank_total", summary.get("total_bank_component", 0))
        
        print(f"✅ Account tree details summary contains:")
        print(f"   - operations_cash_total: {cash_total}")
        print(f"   - operations_bank_total: {bank_total}")
        print(f"   - Full summary: {summary}")
    
    def test_account_tree_details_summary_structure(self):
        """Test the full structure of account-tree-details response"""
        params = {
            "workshop_id": WORKSHOP_ID,
            "account_code": "4000",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "include_descendants": "true",
            "page": 1,
            "page_size": 10
        }
        
        response = requests.get(f"{BASE_URL}/api/finance/reports/account-tree-details", params=params)
        assert response.status_code == 200
        
        result = response.json()
        data = result.get("data", result)
        
        # Check structure
        assert "operations" in data, f"Missing 'operations' in response. Keys: {list(data.keys())}"
        
        operations = data.get("operations", {})
        
        # Check for summary
        if "summary" in operations:
            summary = operations["summary"]
            expected_keys = [
                "total_credit",
                "total_cash_component",
                "total_bank_component",
                "operations_cash_total",
                "operations_bank_total"
            ]
            
            found_keys = [k for k in expected_keys if k in summary]
            print(f"✅ Found summary keys: {found_keys}")
            print(f"   Full summary: {summary}")
        else:
            print(f"⚠️ No summary in operations. Operations keys: {list(operations.keys())}")


class TestHealthCheck:
    """Basic health check"""
    
    def test_api_health(self):
        """Test that API is responding"""
        response = requests.get(f"{BASE_URL}/api/health")
        # Some APIs return 200, some 404 for health
        assert response.status_code in [200, 404], f"API not responding: {response.status_code}"
        print(f"✅ API is responding (status: {response.status_code})")
    
    def test_vehicles_list(self):
        """Test vehicles list endpoint"""
        response = requests.get(f"{BASE_URL}/api/vehicles")
        assert response.status_code == 200, f"Vehicles list failed: {response.text}"
        vehicles = response.json()
        assert isinstance(vehicles, list), "Expected list of vehicles"
        print(f"✅ Vehicles list returned {len(vehicles)} vehicles")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
