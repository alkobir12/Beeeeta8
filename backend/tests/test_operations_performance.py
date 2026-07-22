"""
Operations Performance Tests - Iteration 51
Tests for operations loading speed after warm cache optimization
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://workshop-engine.preview.emergentagent.com').rstrip('/')


class TestOperationsPerformance:
    """Test operations API performance after cache optimization"""
    
    def test_health_check(self):
        """Verify API is healthy"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"
        print("✅ Health check passed")
    
    def test_operations_list_with_limit_200(self):
        """Test GET /api/operations?limit=200 response time"""
        # First request (cold)
        start_time = time.time()
        response = requests.get(f"{BASE_URL}/api/operations?limit=200")
        cold_time = time.time() - start_time
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✅ Operations list returned {len(data)} items")
        print(f"⏱️ Cold request time: {cold_time:.3f}s")
        
        # Second request (warm)
        start_time = time.time()
        response = requests.get(f"{BASE_URL}/api/operations?limit=200")
        warm_time = time.time() - start_time
        
        assert response.status_code == 200
        print(f"⏱️ Warm request time: {warm_time:.3f}s")
        
        # Performance assertion - should be under 2 seconds
        assert warm_time < 2.0, f"Operations API too slow: {warm_time:.3f}s"
        print("✅ Performance within acceptable range (<2s)")
    
    def test_operations_list_response_structure(self):
        """Verify operations response has correct structure"""
        response = requests.get(f"{BASE_URL}/api/operations?limit=10")
        assert response.status_code == 200
        data = response.json()
        
        if len(data) > 0:
            op = data[0]
            # Check required fields exist
            assert "id" in op, "Missing 'id' field"
            assert "type" in op, "Missing 'type' field"
            print(f"✅ Operation structure valid: id={op.get('id')[:8]}...")
            
            # Check optional fields
            optional_fields = ["accountId", "vehicleId", "partnerName", "items", "total", "paymentMethod"]
            present_fields = [f for f in optional_fields if f in op]
            print(f"📊 Optional fields present: {present_fields}")
    
    def test_operations_list_sorting(self):
        """Verify operations are sorted by created_at desc"""
        response = requests.get(f"{BASE_URL}/api/operations?limit=50")
        assert response.status_code == 200
        data = response.json()
        
        if len(data) >= 2:
            # Check that operations are sorted by date (newest first)
            dates = []
            for op in data[:10]:  # Check first 10
                date_str = op.get("createdAt") or op.get("date") or ""
                if date_str:
                    dates.append(date_str)
            
            if len(dates) >= 2:
                # Verify descending order
                sorted_dates = sorted(dates, reverse=True)
                assert dates == sorted_dates, "Operations not sorted by date descending"
                print("✅ Operations sorted correctly (newest first)")
            else:
                print("⚠️ Not enough dates to verify sorting")
        else:
            print("⚠️ Not enough operations to verify sorting")
    
    def test_operations_limit_parameter(self):
        """Verify limit parameter works correctly"""
        # Test with limit=5
        response = requests.get(f"{BASE_URL}/api/operations?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 5, f"Expected max 5 operations, got {len(data)}"
        print(f"✅ Limit=5 returned {len(data)} operations")
        
        # Test with limit=200
        response = requests.get(f"{BASE_URL}/api/operations?limit=200")
        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 200, f"Expected max 200 operations, got {len(data)}"
        print(f"✅ Limit=200 returned {len(data)} operations")
    
    def test_multiple_requests_performance(self):
        """Test performance consistency across multiple requests"""
        times = []
        for i in range(3):
            start_time = time.time()
            response = requests.get(f"{BASE_URL}/api/operations?limit=200")
            elapsed = time.time() - start_time
            times.append(elapsed)
            assert response.status_code == 200
        
        avg_time = sum(times) / len(times)
        max_time = max(times)
        min_time = min(times)
        
        print(f"⏱️ Request times: {[f'{t:.3f}s' for t in times]}")
        print(f"⏱️ Average: {avg_time:.3f}s, Min: {min_time:.3f}s, Max: {max_time:.3f}s")
        
        # All requests should be under 2 seconds
        assert max_time < 2.0, f"Max request time too high: {max_time:.3f}s"
        print("✅ All requests within acceptable range")


class TestOperationsPageDependencies:
    """Test other endpoints that Operations page depends on"""
    
    def test_chart_of_accounts(self):
        """Test chart of accounts endpoint"""
        response = requests.get(f"{BASE_URL}/api/accounts")
        assert response.status_code == 200
        data = response.json()
        print(f"✅ Chart of accounts: {len(data)} accounts")
    
    def test_biz_accounts(self):
        """Test business accounts endpoint"""
        response = requests.get(f"{BASE_URL}/api/biz-accounts")
        assert response.status_code == 200
        data = response.json()
        print(f"✅ Business accounts: {len(data)} accounts")
    
    def test_customers(self):
        """Test customers endpoint"""
        response = requests.get(f"{BASE_URL}/api/customers")
        assert response.status_code == 200
        data = response.json()
        print(f"✅ Customers: {len(data)} customers")
    
    def test_suppliers(self):
        """Test suppliers endpoint"""
        response = requests.get(f"{BASE_URL}/api/suppliers")
        assert response.status_code == 200
        data = response.json()
        print(f"✅ Suppliers: {len(data)} suppliers")
    
    def test_vehicles(self):
        """Test vehicles endpoint"""
        response = requests.get(f"{BASE_URL}/api/vehicles")
        assert response.status_code == 200
        data = response.json()
        print(f"✅ Vehicles: {len(data)} vehicles")
    
    def test_parts(self):
        """Test parts endpoint"""
        response = requests.get(f"{BASE_URL}/api/parts")
        assert response.status_code == 200
        data = response.json()
        print(f"✅ Parts: {len(data)} parts")
    
    def test_services(self):
        """Test services endpoint"""
        response = requests.get(f"{BASE_URL}/api/services")
        assert response.status_code == 200
        data = response.json()
        print(f"✅ Services: {len(data)} services")
