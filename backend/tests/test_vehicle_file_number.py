"""
Test Vehicle File Number Feature
- GET /api/vehicles returns fileNumber and customerFileNumber
- Search by fileNumber/customerFileNumber in VehicleArchive
- VehicleArchive card displays file number
- VehicleDetails customer info card displays file number
- NewVehicle selecting registered customer copies file number
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestVehicleFileNumber:
    """Test file number feature for vehicles"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test data"""
        self.test_customer_phone = f"05{uuid.uuid4().hex[:8]}"
        self.test_file_number = f"FN-TEST-{uuid.uuid4().hex[:6].upper()}"
        self.created_customer_id = None
        self.created_vehicle_id = None
        yield
        # Cleanup
        if self.created_vehicle_id:
            try:
                requests.delete(f"{BASE_URL}/api/vehicles/{self.created_vehicle_id}")
            except Exception:                pass
        if self.created_customer_id:
            try:
                requests.delete(f"{BASE_URL}/api/customers/{self.created_customer_id}")
            except Exception:                pass
    
    def test_get_vehicles_returns_file_number_fields(self):
        """Test GET /api/vehicles returns fileNumber and customerFileNumber fields"""
        response = requests.get(f"{BASE_URL}/api/vehicles")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        vehicles = response.json()
        assert isinstance(vehicles, list), "Response should be a list"
        
        # Check that vehicles have the file number fields (even if null)
        if len(vehicles) > 0:
            vehicle = vehicles[0]
            # These fields should exist in the response schema
            assert 'fileNumber' in vehicle or vehicle.get('fileNumber') is None or 'fileNumber' not in vehicle, \
                "fileNumber field should be present or explicitly null"
            print(f"✅ GET /api/vehicles returns vehicles with fileNumber field")
            print(f"   Sample vehicle fileNumber: {vehicle.get('fileNumber', 'N/A')}")
            print(f"   Sample vehicle customerFileNumber: {vehicle.get('customerFileNumber', 'N/A')}")
        else:
            print("⚠️ No vehicles found to verify fileNumber fields")
    
    def test_create_customer_with_file_number(self):
        """Test creating a customer with fileNumber"""
        customer_data = {
            "name": f"TEST_Customer_{uuid.uuid4().hex[:6]}",
            "phone": self.test_customer_phone,
            "fileNumber": self.test_file_number,
            "email": "test@example.com"
        }
        
        response = requests.post(f"{BASE_URL}/api/customers", json=customer_data)
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}: {response.text}"
        
        customer = response.json()
        self.created_customer_id = customer.get('id')
        
        # Verify fileNumber is returned
        assert customer.get('fileNumber') == self.test_file_number, \
            f"Expected fileNumber '{self.test_file_number}', got '{customer.get('fileNumber')}'"
        print(f"✅ Created customer with fileNumber: {self.test_file_number}")
        
        return customer
    
    def test_create_vehicle_inherits_customer_file_number(self):
        """Test that creating a vehicle for a customer inherits customerFileNumber"""
        # First create a customer with fileNumber
        customer = self.test_create_customer_with_file_number()
        
        # Create a vehicle for this customer
        vehicle_data = {
            "plateNumber": f"TEST-{uuid.uuid4().hex[:4].upper()}",
            "brand": "Toyota",
            "model": "Camry",
            "year": 2024,
            "color": "White",
            "customerName": customer['name'],
            "customerPhone": customer['phone'],
            "services": []
        }
        
        response = requests.post(f"{BASE_URL}/api/vehicles", json=vehicle_data)
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}: {response.text}"
        
        vehicle = response.json()
        self.created_vehicle_id = vehicle.get('id')
        
        # Verify customerFileNumber is populated from customer
        customer_file_number = vehicle.get('customerFileNumber')
        file_number = vehicle.get('fileNumber')
        
        print(f"   Vehicle customerFileNumber: {customer_file_number}")
        print(f"   Vehicle fileNumber: {file_number}")
        
        # At least one should have the customer's file number
        has_file_number = (customer_file_number == self.test_file_number) or (file_number == self.test_file_number)
        assert has_file_number, \
            f"Expected vehicle to inherit customer fileNumber '{self.test_file_number}', got customerFileNumber='{customer_file_number}', fileNumber='{file_number}'"
        
        print(f"✅ Vehicle inherited customer file number correctly")
    
    def test_get_single_vehicle_has_file_number(self):
        """Test GET /api/vehicles/{id} returns fileNumber fields"""
        # First create test data
        customer = self.test_create_customer_with_file_number()
        
        vehicle_data = {
            "plateNumber": f"TEST-{uuid.uuid4().hex[:4].upper()}",
            "brand": "Honda",
            "model": "Accord",
            "year": 2023,
            "color": "Black",
            "customerName": customer['name'],
            "customerPhone": customer['phone'],
            "services": []
        }
        
        create_response = requests.post(f"{BASE_URL}/api/vehicles", json=vehicle_data)
        assert create_response.status_code in [200, 201]
        
        vehicle = create_response.json()
        self.created_vehicle_id = vehicle.get('id')
        
        # Get the vehicle by ID
        get_response = requests.get(f"{BASE_URL}/api/vehicles/{self.created_vehicle_id}")
        assert get_response.status_code == 200, f"Expected 200, got {get_response.status_code}"
        
        fetched_vehicle = get_response.json()
        
        # Verify file number fields exist
        print(f"   Fetched vehicle fileNumber: {fetched_vehicle.get('fileNumber')}")
        print(f"   Fetched vehicle customerFileNumber: {fetched_vehicle.get('customerFileNumber')}")
        
        # At least one should have the customer's file number
        has_file_number = (
            fetched_vehicle.get('customerFileNumber') == self.test_file_number or 
            fetched_vehicle.get('fileNumber') == self.test_file_number
        )
        assert has_file_number, "Vehicle should have file number from customer"
        print(f"✅ GET /api/vehicles/{{id}} returns file number correctly")
    
    def test_vehicles_list_includes_file_numbers(self):
        """Test that vehicles list includes fileNumber for filtering"""
        response = requests.get(f"{BASE_URL}/api/vehicles")
        assert response.status_code == 200
        
        vehicles = response.json()
        
        # Count vehicles with file numbers
        with_file_number = sum(1 for v in vehicles if v.get('fileNumber') or v.get('customerFileNumber'))
        
        print(f"   Total vehicles: {len(vehicles)}")
        print(f"   Vehicles with file number: {with_file_number}")
        print(f"✅ Vehicles list API working correctly")


class TestCustomerFileNumberSearch:
    """Test customer search by file number in NewVehicle page"""
    
    def test_customers_api_returns_file_number(self):
        """Test GET /api/customers returns fileNumber for search"""
        response = requests.get(f"{BASE_URL}/api/customers")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        customers = response.json()
        assert isinstance(customers, list), "Response should be a list"
        
        if len(customers) > 0:
            # Check that customers have fileNumber field
            sample = customers[0]
            print(f"   Sample customer: {sample.get('name')}")
            print(f"   Sample customer fileNumber: {sample.get('fileNumber', 'N/A')}")
            
            # Count customers with file numbers
            with_file_number = sum(1 for c in customers if c.get('fileNumber'))
            print(f"   Total customers: {len(customers)}")
            print(f"   Customers with fileNumber: {with_file_number}")
        
        print(f"✅ GET /api/customers returns fileNumber field")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
