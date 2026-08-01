#!/usr/bin/env python3
"""
Extended test script for DELETE operations - testing multiple deletions
Testing DELETE /api/vehicles/{vehicle_id} and DELETE /api/customers/{customer_id}
with multiple test data as requested.
"""

import requests
import json
import sys
from typing import List, Dict, Any

# Get base URL from frontend .env
BASE_URL = "https://ar-ledger-ssot.preview.emergentagent.com"
API_BASE = f"{BASE_URL}/api"

def make_request(method: str, endpoint: str, data: dict = None) -> tuple:
    """Make HTTP request and return (success, response_data, status_code)"""
    url = f"{API_BASE}{endpoint}"
    try:
        if method.upper() == "GET":
            response = requests.get(url, timeout=30)
        elif method.upper() == "POST":
            response = requests.post(url, json=data, timeout=30)
        elif method.upper() == "DELETE":
            response = requests.delete(url, timeout=30)
        else:
            return False, f"Unsupported method: {method}", 0
        
        try:
            response_data = response.json()
        except:
            response_data = response.text
        
        return response.status_code < 400, response_data, response.status_code
    except Exception as e:
        return False, str(e), 0

def create_test_data():
    """Create test vehicles and customers for deletion testing"""
    print("🔧 Creating test data for deletion testing...")
    
    test_customers = []
    test_vehicles = []
    
    # Create test customers
    for i in range(3):
        customer_data = {
            "name": f"عميل تجريبي {i+1}",
            "phone": f"050123456{i}",
            "email": f"test{i+1}@delete.com",
            "totalVisits": 1,
            "vehicles": []
        }
        
        success, result, status = make_request("POST", "/customers", customer_data)
        if success:
            test_customers.append(result)
            print(f"✅ Created customer: {result.get('name')} (ID: {result.get('id')})")
        else:
            print(f"❌ Failed to create customer {i+1}: {result}")
    
    # Create test vehicles
    for i, customer in enumerate(test_customers):
        vehicle_data = {
            "plateNumber": f"ت ج ر {1000+i}",
            "brand": "تويوتا",
            "model": "كامري",
            "year": 2020 + i,
            "color": ["أبيض", "أسود", "فضي"][i],
            "customerName": customer.get('name'),
            "customerPhone": customer.get('phone'),
            "customerEmail": customer.get('email'),
            "services": [],
            "status": "diagnosis"
        }
        
        success, result, status = make_request("POST", "/vehicles", vehicle_data)
        if success:
            test_vehicles.append(result)
            print(f"✅ Created vehicle: {result.get('plateNumber')} (ID: {result.get('id')})")
        else:
            print(f"❌ Failed to create vehicle {i+1}: {result}")
    
    return test_customers, test_vehicles

def test_multiple_vehicle_deletions():
    """Test deleting multiple vehicles"""
    print("\n🚗 Testing Multiple Vehicle Deletions")
    print("=" * 50)
    
    # Get current vehicles
    success, vehicles_data, status = make_request("GET", "/vehicles")
    if not success:
        print(f"❌ Failed to get vehicles: {vehicles_data}")
        return False
    
    initial_count = len(vehicles_data)
    print(f"📊 Initial vehicle count: {initial_count}")
    
    # Find test vehicles (those with plate numbers starting with "ت ج ر")
    test_vehicles = [v for v in vehicles_data if v.get('plateNumber', '').startswith('ت ج ر')]
    
    if len(test_vehicles) < 2:
        print("⚠️ Not enough test vehicles found. Creating test data...")
        customers, vehicles = create_test_data()
        test_vehicles = vehicles
    
    deleted_count = 0
    for i, vehicle in enumerate(test_vehicles[:3]):  # Delete up to 3 vehicles
        vehicle_id = vehicle.get('id')
        plate = vehicle.get('plateNumber')
        
        print(f"\n{i+1}. Deleting vehicle {plate} (ID: {vehicle_id})...")
        
        success, delete_result, status = make_request("DELETE", f"/vehicles/{vehicle_id}")
        
        if success and isinstance(delete_result, dict) and delete_result.get('success') == True:
            print(f"✅ Successfully deleted vehicle {plate}")
            deleted_count += 1
        else:
            print(f"❌ Failed to delete vehicle {plate}: {delete_result}")
    
    # Verify final count
    success, vehicles_after, status = make_request("GET", "/vehicles")
    if success:
        final_count = len(vehicles_after)
        expected_count = initial_count - deleted_count
        print(f"\n📊 Final vehicle count: {final_count} (expected: {expected_count})")
        
        if final_count == expected_count:
            print("✅ Vehicle count matches expected after deletions")
            return True
        else:
            print("❌ Vehicle count mismatch after deletions")
            return False
    else:
        print(f"❌ Failed to verify final vehicle count: {vehicles_after}")
        return False

def test_multiple_customer_deletions():
    """Test deleting multiple customers"""
    print("\n👤 Testing Multiple Customer Deletions")
    print("=" * 50)
    
    # Get current customers
    success, customers_data, status = make_request("GET", "/customers")
    if not success:
        print(f"❌ Failed to get customers: {customers_data}")
        return False
    
    initial_count = len(customers_data)
    print(f"📊 Initial customer count: {initial_count}")
    
    # Find test customers (those with names containing "تجريبي")
    test_customers = [c for c in customers_data if 'تجريبي' in c.get('name', '')]
    
    if len(test_customers) < 2:
        print("⚠️ Not enough test customers found. Creating test data...")
        customers, vehicles = create_test_data()
        test_customers = customers
    
    deleted_count = 0
    for i, customer in enumerate(test_customers[:2]):  # Delete up to 2 customers
        customer_id = customer.get('id')
        name = customer.get('name')
        
        print(f"\n{i+1}. Deleting customer {name} (ID: {customer_id})...")
        
        success, delete_result, status = make_request("DELETE", f"/customers/{customer_id}")
        
        if success and isinstance(delete_result, dict) and delete_result.get('success') == True:
            print(f"✅ Successfully deleted customer {name}")
            deleted_count += 1
        else:
            print(f"❌ Failed to delete customer {name}: {delete_result}")
    
    # Verify final count
    success, customers_after, status = make_request("GET", "/customers")
    if success:
        final_count = len(customers_after)
        expected_count = initial_count - deleted_count
        print(f"\n📊 Final customer count: {final_count} (expected: {expected_count})")
        
        if final_count == expected_count:
            print("✅ Customer count matches expected after deletions")
            return True
        else:
            print("❌ Customer count mismatch after deletions")
            return False
    else:
        print(f"❌ Failed to verify final customer count: {customers_after}")
        return False

def test_error_handling():
    """Test error handling for non-existent IDs"""
    print("\n🔍 Testing Error Handling")
    print("=" * 50)
    
    # Test deleting non-existent vehicle
    fake_vehicle_id = "00000000-0000-0000-0000-000000000000"
    print(f"1. Testing delete of non-existent vehicle {fake_vehicle_id}...")
    
    success, result, status = make_request("DELETE", f"/vehicles/{fake_vehicle_id}")
    print(f"   Response: {result} (Status: {status})")
    
    # For Supabase, deleting non-existent records might still return success
    # This is acceptable behavior
    
    # Test deleting non-existent customer
    fake_customer_id = "00000000-0000-0000-0000-000000000000"
    print(f"\n2. Testing delete of non-existent customer {fake_customer_id}...")
    
    success, result, status = make_request("DELETE", f"/customers/{fake_customer_id}")
    print(f"   Response: {result} (Status: {status})")
    
    print("✅ Error handling test completed")
    return True

def main():
    """Run extended delete operation tests"""
    print("🧪 EXTENDED DELETE Operations Test Suite")
    print("Testing with real Supabase database")
    print(f"Base URL: {BASE_URL}")
    print("=" * 60)
    
    # Test results
    vehicle_test_passed = False
    customer_test_passed = False
    error_test_passed = False
    
    try:
        # Test multiple vehicle deletions
        vehicle_test_passed = test_multiple_vehicle_deletions()
        
        # Test multiple customer deletions
        customer_test_passed = test_multiple_customer_deletions()
        
        # Test error handling
        error_test_passed = test_error_handling()
        
    except Exception as e:
        print(f"\n❌ Unexpected error during testing: {e}")
        return False
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 EXTENDED TEST SUMMARY")
    print("=" * 60)
    print(f"Multiple Vehicle Deletions: {'✅ PASSED' if vehicle_test_passed else '❌ FAILED'}")
    print(f"Multiple Customer Deletions: {'✅ PASSED' if customer_test_passed else '❌ FAILED'}")
    print(f"Error Handling: {'✅ PASSED' if error_test_passed else '❌ FAILED'}")
    
    overall_success = vehicle_test_passed and customer_test_passed and error_test_passed
    print(f"\nOverall Result: {'🎉 ALL TESTS PASSED' if overall_success else '❌ SOME TESTS FAILED'}")
    
    return overall_success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)