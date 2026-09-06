"""
Performance P0 Tests - Operations and Dashboard Speed Improvements
Tests for:
1. GET /api/operations - faster response with correct data
2. POST /api/vehicles/dashboard/summaries - batch endpoint for service type
3. Dashboard N+1 fix verification
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://financial-ssot.preview.emergentagent.com').rstrip('/')


class TestOperationsPerformance:
    """Test operations endpoint performance improvements"""

    def test_operations_returns_data_not_empty(self):
        """GET /api/operations should return actual data, not empty array"""
        response = requests.get(f"{BASE_URL}/api/operations", params={"limit": 50})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        # Should have some operations in the system
        assert len(data) > 0, "Operations list should not be empty"
        
        # Verify structure of first operation
        if data:
            op = data[0]
            assert "id" in op, "Operation should have id"
            assert "type" in op, "Operation should have type"

    def test_operations_response_time_under_3_seconds(self):
        """GET /api/operations should respond in under 3 seconds"""
        start_time = time.time()
        response = requests.get(f"{BASE_URL}/api/operations", params={"limit": 100})
        elapsed = time.time() - start_time
        
        assert response.status_code == 200
        assert elapsed < 3.0, f"Response took {elapsed:.2f}s, expected < 3s"
        print(f"✅ Operations endpoint responded in {elapsed:.2f}s")

    def test_operations_with_limit_parameter(self):
        """GET /api/operations should respect limit parameter"""
        response = requests.get(f"{BASE_URL}/api/operations", params={"limit": 10})
        assert response.status_code == 200
        
        data = response.json()
        assert len(data) <= 10, f"Expected max 10 items, got {len(data)}"

    def test_operations_sorted_by_date_desc(self):
        """Operations should be sorted by date descending (newest first)"""
        response = requests.get(f"{BASE_URL}/api/operations", params={"limit": 20})
        assert response.status_code == 200
        
        data = response.json()
        if len(data) >= 2:
            # Check that dates are in descending order
            dates = []
            for op in data:
                date_str = op.get("date") or op.get("createdAt") or ""
                if date_str:
                    dates.append(date_str)
            
            if len(dates) >= 2:
                # Verify descending order
                for i in range(len(dates) - 1):
                    assert dates[i] >= dates[i+1], f"Operations not sorted: {dates[i]} should be >= {dates[i+1]}"


class TestDashboardSummariesEndpoint:
    """Test the new batch endpoint for vehicle dashboard summaries"""

    def test_dashboard_summaries_endpoint_exists(self):
        """POST /api/vehicles/dashboard/summaries should exist"""
        response = requests.post(
            f"{BASE_URL}/api/vehicles/dashboard/summaries",
            json={"vehicle_ids": []}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "summaries" in data, "Response should have summaries key"

    def test_dashboard_summaries_returns_service_type(self):
        """Dashboard summaries should return serviceType for each vehicle"""
        # First get some real vehicle IDs
        vehicles_response = requests.get(f"{BASE_URL}/api/vehicles")
        assert vehicles_response.status_code == 200
        
        vehicles = vehicles_response.json()
        if not vehicles:
            pytest.skip("No vehicles in system to test")
        
        # Get first 3 vehicle IDs
        vehicle_ids = [v["id"] for v in vehicles[:3] if v.get("id")]
        
        response = requests.post(
            f"{BASE_URL}/api/vehicles/dashboard/summaries",
            json={"vehicle_ids": vehicle_ids}
        )
        assert response.status_code == 200
        
        data = response.json()
        summaries = data.get("summaries", [])
        
        # Verify each summary has required fields
        for summary in summaries:
            assert "vehicleId" in summary, "Summary should have vehicleId"
            assert "serviceType" in summary, "Summary should have serviceType"
            assert "visitsCount" in summary, "Summary should have visitsCount"
            assert "estimatedTotal" in summary, "Summary should have estimatedTotal"

    def test_dashboard_summaries_batch_performance(self):
        """Batch endpoint should be faster than N individual calls"""
        # Get vehicle IDs
        vehicles_response = requests.get(f"{BASE_URL}/api/vehicles")
        vehicles = vehicles_response.json()
        
        if len(vehicles) < 5:
            pytest.skip("Need at least 5 vehicles to test batch performance")
        
        vehicle_ids = [v["id"] for v in vehicles[:10] if v.get("id")]
        
        # Time the batch call
        start_time = time.time()
        response = requests.post(
            f"{BASE_URL}/api/vehicles/dashboard/summaries",
            json={"vehicle_ids": vehicle_ids}
        )
        batch_time = time.time() - start_time
        
        assert response.status_code == 200
        print(f"✅ Batch endpoint for {len(vehicle_ids)} vehicles took {batch_time:.2f}s")
        
        # Should be reasonably fast (under 2 seconds for 10 vehicles)
        assert batch_time < 2.0, f"Batch took {batch_time:.2f}s, expected < 2s"

    def test_dashboard_summaries_empty_ids(self):
        """Empty vehicle_ids should return empty summaries"""
        response = requests.post(
            f"{BASE_URL}/api/vehicles/dashboard/summaries",
            json={"vehicle_ids": []}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("summaries") == [], "Empty input should return empty summaries"


class TestVehiclesEndpoint:
    """Test vehicles endpoint for dashboard"""

    def test_vehicles_list_performance(self):
        """GET /api/vehicles should respond quickly"""
        start_time = time.time()
        response = requests.get(f"{BASE_URL}/api/vehicles")
        elapsed = time.time() - start_time
        
        assert response.status_code == 200
        assert elapsed < 2.0, f"Vehicles endpoint took {elapsed:.2f}s, expected < 2s"
        print(f"✅ Vehicles endpoint responded in {elapsed:.2f}s")

    def test_vehicles_have_required_fields(self):
        """Vehicles should have fields needed for dashboard"""
        response = requests.get(f"{BASE_URL}/api/vehicles")
        assert response.status_code == 200
        
        vehicles = response.json()
        if not vehicles:
            pytest.skip("No vehicles to test")
        
        vehicle = vehicles[0]
        required_fields = ["id", "plateNumber", "status", "customerName"]
        for field in required_fields:
            assert field in vehicle, f"Vehicle missing required field: {field}"


class TestNoN1Queries:
    """Verify N+1 query pattern is eliminated"""

    def test_dashboard_does_not_call_individual_visits(self):
        """
        The dashboard should use batch endpoint instead of calling
        /api/vehicles/{id}/visits for each vehicle.
        
        This test verifies the batch endpoint works correctly.
        """
        # Get vehicles
        vehicles_response = requests.get(f"{BASE_URL}/api/vehicles")
        vehicles = vehicles_response.json()
        
        if len(vehicles) < 3:
            pytest.skip("Need at least 3 vehicles")
        
        vehicle_ids = [v["id"] for v in vehicles[:5]]
        
        # The batch endpoint should work
        batch_response = requests.post(
            f"{BASE_URL}/api/vehicles/dashboard/summaries",
            json={"vehicle_ids": vehicle_ids}
        )
        assert batch_response.status_code == 200
        
        summaries = batch_response.json().get("summaries", [])
        
        # Should return summaries for all requested vehicles
        returned_ids = {s["vehicleId"] for s in summaries}
        for vid in vehicle_ids:
            assert vid in returned_ids, f"Missing summary for vehicle {vid}"
        
        print(f"✅ Batch endpoint returned summaries for {len(summaries)} vehicles")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
