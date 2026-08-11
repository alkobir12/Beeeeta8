"""
Iteration 203 - Live Vehicle Data Enrichment in Operations
Tests that GET /api/operations and GET /api/operations/{id} return live vehicle/customer data
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://canonical-integrity.preview.emergentagent.com')


class TestOperationsLiveVehicleEnrichment:
    """Test that operations reflect live vehicle/customer data"""

    def test_operations_list_returns_vehicle_enrichment_fields(self):
        """GET /api/operations should include customerName, customerPhone, vehiclePlate, vehicleBrand, vehicleModel"""
        response = requests.get(f"{BASE_URL}/api/operations", params={"limit": 10})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        
        # Find an operation with a vehicleId
        vehicle_ops = [op for op in data if op.get('vehicleId')]
        assert len(vehicle_ops) > 0, "Should have at least one operation with vehicleId"
        
        op = vehicle_ops[0]
        # Check enrichment fields exist
        assert 'customerName' in op, "Operation should have customerName field"
        assert 'customerPhone' in op, "Operation should have customerPhone field"
        assert 'vehiclePlate' in op, "Operation should have vehiclePlate field"
        assert 'vehicleBrand' in op, "Operation should have vehicleBrand field"
        assert 'vehicleModel' in op, "Operation should have vehicleModel field"
        
        print(f"✓ Operation {op.get('id')} has enrichment fields:")
        print(f"  customerName: {op.get('customerName')}")
        print(f"  customerPhone: {op.get('customerPhone')}")
        print(f"  vehiclePlate: {op.get('vehiclePlate')}")
        print(f"  vehicleBrand: {op.get('vehicleBrand')}")
        print(f"  vehicleModel: {op.get('vehicleModel')}")

    def test_operations_get_by_id_returns_vehicle_enrichment(self):
        """GET /api/operations/{id} should include live vehicle data"""
        # First get an operation with vehicleId
        list_response = requests.get(f"{BASE_URL}/api/operations", params={"limit": 20})
        assert list_response.status_code == 200
        
        ops = list_response.json()
        vehicle_ops = [op for op in ops if op.get('vehicleId')]
        assert len(vehicle_ops) > 0, "Need at least one operation with vehicleId"
        
        op_id = vehicle_ops[0]['id']
        vehicle_id = vehicle_ops[0]['vehicleId']
        
        # Get the specific operation
        op_response = requests.get(f"{BASE_URL}/api/operations/{op_id}")
        assert op_response.status_code == 200, f"Expected 200, got {op_response.status_code}"
        
        op = op_response.json()
        assert op.get('customerName') is not None or op.get('customerName') == '', "customerName should be present"
        assert op.get('vehiclePlate') is not None or op.get('vehiclePlate') == '', "vehiclePlate should be present"
        
        print(f"✓ Operation {op_id} single-get enrichment verified")

    def test_operation_enrichment_matches_vehicle_data(self):
        """Operation's enriched data should match the actual vehicle record"""
        # Get operations with vehicleId
        list_response = requests.get(f"{BASE_URL}/api/operations", params={"limit": 20})
        assert list_response.status_code == 200
        
        ops = list_response.json()
        vehicle_ops = [op for op in ops if op.get('vehicleId') and op.get('customerName')]
        
        if not vehicle_ops:
            pytest.skip("No operations with vehicleId and customerName found")
        
        op = vehicle_ops[0]
        vehicle_id = op['vehicleId']
        
        # Get the vehicle directly
        vehicle_response = requests.get(f"{BASE_URL}/api/vehicles/{vehicle_id}")
        assert vehicle_response.status_code == 200, f"Vehicle {vehicle_id} should exist"
        
        vehicle = vehicle_response.json()
        
        # Compare enriched data with vehicle data
        assert op.get('customerName') == vehicle.get('customerName'), \
            f"customerName mismatch: op={op.get('customerName')}, vehicle={vehicle.get('customerName')}"
        assert op.get('customerPhone') == vehicle.get('customerPhone'), \
            f"customerPhone mismatch: op={op.get('customerPhone')}, vehicle={vehicle.get('customerPhone')}"
        assert op.get('vehiclePlate') == vehicle.get('plateNumber'), \
            f"vehiclePlate mismatch: op={op.get('vehiclePlate')}, vehicle={vehicle.get('plateNumber')}"
        assert op.get('vehicleBrand') == vehicle.get('brand'), \
            f"vehicleBrand mismatch: op={op.get('vehicleBrand')}, vehicle={vehicle.get('brand')}"
        assert op.get('vehicleModel') == vehicle.get('model'), \
            f"vehicleModel mismatch: op={op.get('vehicleModel')}, vehicle={vehicle.get('model')}"
        
        print(f"✓ Operation {op['id']} enrichment matches vehicle {vehicle_id}")
        print(f"  Customer: {op.get('customerName')}")
        print(f"  Phone: {op.get('customerPhone')}")
        print(f"  Plate: {op.get('vehiclePlate')}")
        print(f"  Brand/Model: {op.get('vehicleBrand')} {op.get('vehicleModel')}")


class TestVehicleDetailsLinkedJournalEntries:
    """Test that Vehicle Details page data is still accessible"""

    def test_vehicle_details_endpoint_works(self):
        """GET /api/vehicles/{id} should return vehicle data"""
        # Get a vehicle ID from operations
        ops_response = requests.get(f"{BASE_URL}/api/operations", params={"limit": 5})
        assert ops_response.status_code == 200
        
        ops = ops_response.json()
        vehicle_ops = [op for op in ops if op.get('vehicleId')]
        
        if not vehicle_ops:
            pytest.skip("No operations with vehicleId found")
        
        vehicle_id = vehicle_ops[0]['vehicleId']
        
        # Get vehicle details
        response = requests.get(f"{BASE_URL}/api/vehicles/{vehicle_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        vehicle = response.json()
        assert 'id' in vehicle
        assert 'plateNumber' in vehicle or 'plate_number' in vehicle
        
        print(f"✓ Vehicle {vehicle_id} details accessible")

    def test_journal_entries_endpoint_works(self):
        """GET /api/finance/journal-entries should work"""
        response = requests.get(f"{BASE_URL}/api/finance/journal-entries", params={"limit": 5, "workshop_id": "finmodule-sync"})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Could be list or dict with 'data' key
        entries = data if isinstance(data, list) else data.get('data', data.get('entries', []))
        
        print(f"✓ Journal entries endpoint works, returned {len(entries) if isinstance(entries, list) else 'data'}")


class TestOperationsPageDoesNotBreak:
    """Test that operations list endpoint returns valid data structure"""

    def test_operations_list_structure(self):
        """Operations list should have expected structure"""
        response = requests.get(f"{BASE_URL}/api/operations", params={"limit": 10})
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        
        if data:
            op = data[0]
            # Check required fields
            required_fields = ['id', 'type', 'total']
            for field in required_fields:
                assert field in op, f"Missing required field: {field}"
            
            # Check enrichment fields are present (even if empty)
            enrichment_fields = ['customerName', 'customerPhone', 'vehiclePlate', 'vehicleBrand', 'vehicleModel']
            for field in enrichment_fields:
                assert field in op, f"Missing enrichment field: {field}"
        
        print(f"✓ Operations list structure valid, {len(data)} operations returned")

    def test_operations_with_vehicle_filter(self):
        """Operations filtered by vehicle_id should work"""
        # First get a vehicle ID
        ops_response = requests.get(f"{BASE_URL}/api/operations", params={"limit": 10})
        assert ops_response.status_code == 200
        
        ops = ops_response.json()
        vehicle_ops = [op for op in ops if op.get('vehicleId')]
        
        if not vehicle_ops:
            pytest.skip("No operations with vehicleId found")
        
        vehicle_id = vehicle_ops[0]['vehicleId']
        
        # Filter by vehicle_id
        filtered_response = requests.get(f"{BASE_URL}/api/operations", params={"vehicle_id": vehicle_id})
        assert filtered_response.status_code == 200
        
        filtered_ops = filtered_response.json()
        # All returned operations should have this vehicle_id
        for op in filtered_ops:
            assert op.get('vehicleId') == vehicle_id, f"Operation {op.get('id')} has wrong vehicleId"
        
        print(f"✓ Vehicle filter works, {len(filtered_ops)} operations for vehicle {vehicle_id}")
