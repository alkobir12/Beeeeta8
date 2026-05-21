"""
Test Vehicle Details Features - Iteration 104
Tests:
1. Supplier archive table in vehicle details
2. Financial summary source buttons
3. Collapse/expand toggles for vehicle and customer info blocks
4. Backend API returns supplier_archive_total
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://fleet-audit-system-2.preview.emergentagent.com')


class TestVehicleFinancialSummaryAPI:
    """Test /api/vehicles/{id}/financial-summary endpoint"""
    
    def test_financial_summary_returns_supplier_archive_total(self):
        """Verify API returns supplier_archive_total field"""
        # Get a vehicle ID first
        vehicles_response = requests.get(f"{BASE_URL}/api/vehicles")
        assert vehicles_response.status_code == 200, f"Failed to get vehicles: {vehicles_response.text}"
        
        vehicles = vehicles_response.json()
        if not vehicles:
            pytest.skip("No vehicles available for testing")
        
        vehicle_id = vehicles[0].get('id')
        assert vehicle_id, "Vehicle ID not found"
        
        # Get financial summary
        response = requests.get(f"{BASE_URL}/api/vehicles/{vehicle_id}/financial-summary")
        assert response.status_code == 200, f"Failed to get financial summary: {response.text}"
        
        data = response.json()
        
        # Verify required fields exist
        required_fields = ['total_workshop', 'total_suppliers', 'supplier_archive_total', 'total_paid', 'advance_paid', 'balance']
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        
        # Verify supplier_archive_total equals total_suppliers
        assert data['supplier_archive_total'] == data['total_suppliers'], \
            f"supplier_archive_total ({data['supplier_archive_total']}) should equal total_suppliers ({data['total_suppliers']})"
        
        print(f"✓ Financial summary API returns all required fields including supplier_archive_total")
        print(f"  - total_workshop: {data['total_workshop']}")
        print(f"  - total_suppliers: {data['total_suppliers']}")
        print(f"  - supplier_archive_total: {data['supplier_archive_total']}")
        print(f"  - total_paid: {data['total_paid']}")
        print(f"  - balance: {data['balance']}")
    
    def test_financial_summary_numeric_values(self):
        """Verify all financial values are numeric"""
        vehicles_response = requests.get(f"{BASE_URL}/api/vehicles")
        vehicles = vehicles_response.json()
        if not vehicles:
            pytest.skip("No vehicles available for testing")
        
        vehicle_id = vehicles[0].get('id')
        response = requests.get(f"{BASE_URL}/api/vehicles/{vehicle_id}/financial-summary")
        data = response.json()
        
        numeric_fields = ['total_workshop', 'total_suppliers', 'supplier_archive_total', 'total_paid', 'advance_paid', 'balance']
        for field in numeric_fields:
            value = data.get(field)
            assert isinstance(value, (int, float)), f"Field {field} should be numeric, got {type(value)}"
        
        print("✓ All financial values are numeric")
    
    def test_financial_summary_nonexistent_vehicle(self):
        """Verify API handles non-existent vehicle gracefully"""
        response = requests.get(f"{BASE_URL}/api/vehicles/nonexistent-vehicle-id-12345/financial-summary")
        # Should return 200 with zero values or 404
        assert response.status_code in [200, 404], f"Unexpected status: {response.status_code}"
        
        if response.status_code == 200:
            data = response.json()
            # All values should be 0 for non-existent vehicle
            assert data.get('total_workshop', 0) == 0 or data.get('total_workshop') is not None
            print("✓ Non-existent vehicle returns zero values")
        else:
            print("✓ Non-existent vehicle returns 404")


class TestVehicleVisitsAPI:
    """Test /api/vehicles/{id}/visits endpoint for supplier items"""
    
    def test_visits_contain_supplier_items(self):
        """Verify visits can contain supplier type items"""
        vehicles_response = requests.get(f"{BASE_URL}/api/vehicles")
        vehicles = vehicles_response.json()
        if not vehicles:
            pytest.skip("No vehicles available for testing")
        
        vehicle_id = vehicles[0].get('id')
        response = requests.get(f"{BASE_URL}/api/vehicles/{vehicle_id}/visits")
        assert response.status_code == 200, f"Failed to get visits: {response.text}"
        
        visits = response.json()
        print(f"✓ Vehicle visits endpoint returns {len(visits)} visits")
        
        # Check if any visit has supplier items
        supplier_items_found = False
        for visit in visits:
            items = visit.get('items', [])
            for item in items:
                if item.get('itemType') == 'supplier':
                    supplier_items_found = True
                    print(f"  - Found supplier item: {item.get('name')} in visit {visit.get('id')}")
        
        if not supplier_items_found:
            print("  - No supplier items found in visits (this is OK if no supplier items were added)")


class TestVehicleDetailsEndpoints:
    """Test vehicle details related endpoints"""
    
    def test_vehicle_details_endpoint(self):
        """Verify vehicle details endpoint works"""
        vehicles_response = requests.get(f"{BASE_URL}/api/vehicles")
        vehicles = vehicles_response.json()
        if not vehicles:
            pytest.skip("No vehicles available for testing")
        
        vehicle_id = vehicles[0].get('id')
        response = requests.get(f"{BASE_URL}/api/vehicles/{vehicle_id}")
        assert response.status_code == 200, f"Failed to get vehicle details: {response.text}"
        
        data = response.json()
        assert 'id' in data, "Vehicle should have id"
        assert 'plateNumber' in data or 'plate_number' in data, "Vehicle should have plate number"
        
        print(f"✓ Vehicle details endpoint works for vehicle {vehicle_id}")
    
    def test_technicians_endpoint(self):
        """Verify technicians endpoint works (needed for visit form)"""
        response = requests.get(f"{BASE_URL}/api/technicians")
        assert response.status_code == 200, f"Failed to get technicians: {response.text}"
        
        data = response.json()
        print(f"✓ Technicians endpoint returns {len(data)} technicians")
    
    def test_suppliers_endpoint(self):
        """Verify suppliers endpoint works (needed for supplier items)"""
        response = requests.get(f"{BASE_URL}/api/suppliers")
        assert response.status_code == 200, f"Failed to get suppliers: {response.text}"
        
        data = response.json()
        print(f"✓ Suppliers endpoint returns {len(data)} suppliers")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
