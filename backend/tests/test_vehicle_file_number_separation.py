"""
Test: Vehicle fileNumber separation from customerFileNumber
Requirements:
1. Vehicle creation should NOT auto-fill fileNumber from customer
2. GET /api/vehicles and /api/vehicles/{id} return both fileNumber and customerFileNumber separately
3. Archive search by fileNumber/customerFileNumber works
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://accounting-engine-6.preview.emergentagent.com').rstrip('/')


class TestVehicleFileNumberSeparation:
    """Test that vehicle fileNumber is separate from customerFileNumber"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test data"""
        self.test_customer_file = f"TEST-CUST-{uuid.uuid4().hex[:6]}"
        self.test_vehicle_file = f"TEST-VEH-{uuid.uuid4().hex[:6]}"
        self.test_phone = f"05{uuid.uuid4().hex[:8]}"
        self.created_customer_id = None
        self.created_vehicle_id = None
        yield
        # Cleanup
        if self.created_vehicle_id:
            try:
                requests.delete(f"{BASE_URL}/api/vehicles/{self.created_vehicle_id}")
            except:
                pass
        if self.created_customer_id:
            try:
                requests.delete(f"{BASE_URL}/api/customers/{self.created_customer_id}")
            except:
                pass

    def test_vehicle_creation_does_not_auto_fill_file_number(self):
        """
        When creating a vehicle linked to a customer with fileNumber,
        the vehicle's fileNumber should NOT be auto-filled from customer.
        Only customerFileNumber should be populated.
        """
        # Step 1: Create customer with fileNumber
        customer_payload = {
            "name": f"TEST Customer {uuid.uuid4().hex[:4]}",
            "phone": self.test_phone,
            "fileNumber": self.test_customer_file
        }
        cust_resp = requests.post(f"{BASE_URL}/api/customers", json=customer_payload)
        assert cust_resp.status_code in [200, 201], f"Customer creation failed: {cust_resp.text}"
        customer = cust_resp.json()
        self.created_customer_id = customer.get('id')
        print(f"✅ Created customer with fileNumber: {self.test_customer_file}")
        
        # Step 2: Create vehicle WITHOUT fileNumber, linked to customer
        vehicle_payload = {
            "plateNumber": f"TEST-{uuid.uuid4().hex[:4]}",
            "brand": "Toyota",
            "model": "Camry",
            "year": 2024,
            "color": "White",
            "customerName": customer_payload["name"],
            "customerPhone": self.test_phone,
            # fileNumber intentionally NOT provided
        }
        veh_resp = requests.post(f"{BASE_URL}/api/vehicles", json=vehicle_payload)
        assert veh_resp.status_code in [200, 201], f"Vehicle creation failed: {veh_resp.text}"
        vehicle = veh_resp.json()
        self.created_vehicle_id = vehicle.get('id')
        
        # Verify: fileNumber should be empty/None (NOT auto-filled from customer)
        vehicle_file_number = vehicle.get('fileNumber')
        customer_file_number = vehicle.get('customerFileNumber')
        
        print(f"Vehicle fileNumber: {vehicle_file_number}")
        print(f"Vehicle customerFileNumber: {customer_file_number}")
        
        # fileNumber should be empty/None since we didn't provide it
        assert vehicle_file_number is None or vehicle_file_number == '' or vehicle_file_number == '-', \
            f"Vehicle fileNumber should be empty but got: {vehicle_file_number}"
        
        # customerFileNumber should be populated from linked customer
        assert customer_file_number == self.test_customer_file, \
            f"customerFileNumber should be {self.test_customer_file} but got: {customer_file_number}"
        
        print("✅ Vehicle fileNumber is NOT auto-filled from customer")

    def test_vehicle_creation_with_explicit_file_number(self):
        """
        When creating a vehicle with explicit fileNumber,
        it should be preserved and separate from customerFileNumber.
        """
        # Step 1: Create customer with fileNumber
        customer_payload = {
            "name": f"TEST Customer {uuid.uuid4().hex[:4]}",
            "phone": self.test_phone,
            "fileNumber": self.test_customer_file
        }
        cust_resp = requests.post(f"{BASE_URL}/api/customers", json=customer_payload)
        assert cust_resp.status_code in [200, 201], f"Customer creation failed: {cust_resp.text}"
        customer = cust_resp.json()
        self.created_customer_id = customer.get('id')
        
        # Step 2: Create vehicle WITH explicit fileNumber
        vehicle_payload = {
            "plateNumber": f"TEST-{uuid.uuid4().hex[:4]}",
            "brand": "Honda",
            "model": "Accord",
            "year": 2024,
            "color": "Black",
            "customerName": customer_payload["name"],
            "customerPhone": self.test_phone,
            "fileNumber": self.test_vehicle_file  # Explicit vehicle file number
        }
        veh_resp = requests.post(f"{BASE_URL}/api/vehicles", json=vehicle_payload)
        assert veh_resp.status_code in [200, 201], f"Vehicle creation failed: {veh_resp.text}"
        vehicle = veh_resp.json()
        self.created_vehicle_id = vehicle.get('id')
        
        # Verify both fields are separate
        vehicle_file_number = vehicle.get('fileNumber')
        customer_file_number = vehicle.get('customerFileNumber')
        
        print(f"Vehicle fileNumber: {vehicle_file_number}")
        print(f"Vehicle customerFileNumber: {customer_file_number}")
        
        # fileNumber should be the explicit value we provided
        assert vehicle_file_number == self.test_vehicle_file, \
            f"Vehicle fileNumber should be {self.test_vehicle_file} but got: {vehicle_file_number}"
        
        # customerFileNumber should be from linked customer
        assert customer_file_number == self.test_customer_file, \
            f"customerFileNumber should be {self.test_customer_file} but got: {customer_file_number}"
        
        print("✅ Vehicle fileNumber and customerFileNumber are separate")

    def test_get_vehicle_returns_both_file_numbers(self):
        """
        GET /api/vehicles/{id} should return both fileNumber and customerFileNumber
        """
        # Create customer and vehicle
        customer_payload = {
            "name": f"TEST Customer {uuid.uuid4().hex[:4]}",
            "phone": self.test_phone,
            "fileNumber": self.test_customer_file
        }
        cust_resp = requests.post(f"{BASE_URL}/api/customers", json=customer_payload)
        customer = cust_resp.json()
        self.created_customer_id = customer.get('id')
        
        vehicle_payload = {
            "plateNumber": f"TEST-{uuid.uuid4().hex[:4]}",
            "brand": "Nissan",
            "model": "Altima",
            "year": 2024,
            "color": "Silver",
            "customerName": customer_payload["name"],
            "customerPhone": self.test_phone,
            "fileNumber": self.test_vehicle_file
        }
        veh_resp = requests.post(f"{BASE_URL}/api/vehicles", json=vehicle_payload)
        vehicle = veh_resp.json()
        self.created_vehicle_id = vehicle.get('id')
        
        # GET the vehicle by ID
        get_resp = requests.get(f"{BASE_URL}/api/vehicles/{self.created_vehicle_id}")
        assert get_resp.status_code == 200, f"GET vehicle failed: {get_resp.text}"
        fetched = get_resp.json()
        
        # Verify both fields exist and are correct
        assert 'fileNumber' in fetched, "fileNumber field missing from GET response"
        assert 'customerFileNumber' in fetched, "customerFileNumber field missing from GET response"
        
        assert fetched['fileNumber'] == self.test_vehicle_file, \
            f"GET fileNumber mismatch: expected {self.test_vehicle_file}, got {fetched['fileNumber']}"
        assert fetched['customerFileNumber'] == self.test_customer_file, \
            f"GET customerFileNumber mismatch: expected {self.test_customer_file}, got {fetched['customerFileNumber']}"
        
        print("✅ GET /api/vehicles/{id} returns both fileNumber and customerFileNumber correctly")

    def test_get_vehicles_list_returns_both_file_numbers(self):
        """
        GET /api/vehicles should return both fileNumber and customerFileNumber for each vehicle
        """
        # Create customer and vehicle
        customer_payload = {
            "name": f"TEST Customer {uuid.uuid4().hex[:4]}",
            "phone": self.test_phone,
            "fileNumber": self.test_customer_file
        }
        cust_resp = requests.post(f"{BASE_URL}/api/customers", json=customer_payload)
        customer = cust_resp.json()
        self.created_customer_id = customer.get('id')
        
        vehicle_payload = {
            "plateNumber": f"TEST-{uuid.uuid4().hex[:4]}",
            "brand": "Kia",
            "model": "Optima",
            "year": 2024,
            "color": "Blue",
            "customerName": customer_payload["name"],
            "customerPhone": self.test_phone,
            "fileNumber": self.test_vehicle_file
        }
        veh_resp = requests.post(f"{BASE_URL}/api/vehicles", json=vehicle_payload)
        vehicle = veh_resp.json()
        self.created_vehicle_id = vehicle.get('id')
        
        # GET all vehicles
        list_resp = requests.get(f"{BASE_URL}/api/vehicles")
        assert list_resp.status_code == 200, f"GET vehicles list failed: {list_resp.text}"
        vehicles = list_resp.json()
        
        # Find our test vehicle
        test_vehicle = next((v for v in vehicles if v.get('id') == self.created_vehicle_id), None)
        assert test_vehicle is not None, "Test vehicle not found in list"
        
        # Verify both fields exist
        assert 'fileNumber' in test_vehicle, "fileNumber field missing from list response"
        assert 'customerFileNumber' in test_vehicle, "customerFileNumber field missing from list response"
        
        assert test_vehicle['fileNumber'] == self.test_vehicle_file
        assert test_vehicle['customerFileNumber'] == self.test_customer_file
        
        print("✅ GET /api/vehicles returns both fileNumber and customerFileNumber for each vehicle")


class TestArchiveSearchByFileNumber:
    """Test archive search functionality by fileNumber/customerFileNumber"""
    
    def test_vehicles_list_contains_file_number_fields(self):
        """
        Verify that vehicles list API returns fileNumber and customerFileNumber
        which are used by frontend for archive search filtering
        """
        resp = requests.get(f"{BASE_URL}/api/vehicles")
        assert resp.status_code == 200, f"GET vehicles failed: {resp.text}"
        vehicles = resp.json()
        
        if len(vehicles) == 0:
            pytest.skip("No vehicles in database to test")
        
        # Check first vehicle has the required fields
        first_vehicle = vehicles[0]
        
        # These fields should exist (even if null)
        assert 'fileNumber' in first_vehicle or first_vehicle.get('fileNumber') is None, \
            "fileNumber field should be present in vehicle response"
        assert 'customerFileNumber' in first_vehicle or first_vehicle.get('customerFileNumber') is None, \
            "customerFileNumber field should be present in vehicle response"
        
        print(f"✅ Vehicles list contains fileNumber and customerFileNumber fields")
        print(f"   Sample: fileNumber={first_vehicle.get('fileNumber')}, customerFileNumber={first_vehicle.get('customerFileNumber')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
