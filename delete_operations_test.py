#!/usr/bin/env python3
"""
Test script for DELETE operations on vehicles and customers
Testing DELETE /api/vehicles/{vehicle_id} and DELETE /api/customers/{customer_id}
Using real Supabase database as requested.
"""

import requests
import json
import sys
from typing import List, Dict, Any

# Get base URL from frontend .env
BASE_URL = "https://finance-overhaul-7.preview.emergentagent.com"
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

def test_vehicle_delete():
    """Test DELETE /api/vehicles/{vehicle_id}"""
    print("🚗 Testing Vehicle Delete Operation")
    print("=" * 50)
    
    # Step 1: Get existing vehicles
    print("1. Getting existing vehicles...")
    success, vehicles_data, status = make_request("GET", "/vehicles")
    
    if not success:
        print(f"❌ Failed to get vehicles: {vehicles_data} (Status: {status})")
        return False
    
    if not vehicles_data or len(vehicles_data) == 0:
        print("⚠️  No vehicles found in database. Creating a test vehicle first...")
        
        # Create a test vehicle
        test_vehicle = {
            "plateNumber": "ت س ت 1234",
            "brand": "تويوتا",
            "model": "كامري",
            "year": 2020,
            "color": "أبيض",
            "customerName": "عميل تجريبي للحذف",
            "customerPhone": "0501234567",
            "customerEmail": "test@delete.com",
            "services": [],
            "status": "diagnosis"
        }
        
        success, create_result, status = make_request("POST", "/vehicles", test_vehicle)
        if not success:
            print(f"❌ Failed to create test vehicle: {create_result} (Status: {status})")
            return False
        
        print(f"✅ Created test vehicle with ID: {create_result.get('id')}")
        vehicle_id = create_result.get('id')
    else:
        # Use first vehicle from the list
        vehicle_id = vehicles_data[0].get('id')
        print(f"✅ Found {len(vehicles_data)} vehicles. Using vehicle ID: {vehicle_id}")
    
    if not vehicle_id:
        print("❌ No valid vehicle ID found")
        return False
    
    # Step 2: Delete the vehicle
    print(f"\n2. Deleting vehicle {vehicle_id}...")
    success, delete_result, status = make_request("DELETE", f"/vehicles/{vehicle_id}")
    
    if not success:
        print(f"❌ DELETE request failed: {delete_result} (Status: {status})")
        return False
    
    print(f"✅ DELETE response: {delete_result}")
    
    # Step 3: Verify response contains {"success": true}
    if isinstance(delete_result, dict) and delete_result.get('success') == True:
        print("✅ Response contains {'success': true}")
    else:
        print(f"❌ Expected {{'success': true}}, got: {delete_result}")
        return False
    
    # Step 4: Verify vehicle is no longer in the list
    print(f"\n3. Verifying vehicle {vehicle_id} is deleted...")
    success, vehicles_after, status = make_request("GET", "/vehicles")
    
    if not success:
        print(f"❌ Failed to get vehicles after delete: {vehicles_after} (Status: {status})")
        return False
    
    # Check if deleted vehicle is still in the list
    deleted_vehicle_found = any(v.get('id') == vehicle_id for v in vehicles_after)
    
    if deleted_vehicle_found:
        print(f"❌ Vehicle {vehicle_id} still found in vehicles list after deletion")
        return False
    else:
        print(f"✅ Vehicle {vehicle_id} successfully removed from vehicles list")
    
    print("🎉 Vehicle delete test PASSED")
    return True

def test_customer_delete():
    """Test DELETE /api/customers/{customer_id}"""
    print("\n👤 Testing Customer Delete Operation")
    print("=" * 50)
    
    # Step 1: Get existing customers
    print("1. Getting existing customers...")
    success, customers_data, status = make_request("GET", "/customers")
    
    if not success:
        print(f"❌ Failed to get customers: {customers_data} (Status: {status})")
        return False
    
    if not customers_data or len(customers_data) == 0:
        print("⚠️  No customers found in database. Creating a test customer first...")
        
        # Create a test customer
        test_customer = {
            "name": "عميل تجريبي للحذف",
            "phone": "0509876543",
            "email": "customer@delete.com",
            "totalVisits": 1,
            "vehicles": []
        }
        
        success, create_result, status = make_request("POST", "/customers", test_customer)
        if not success:
            print(f"❌ Failed to create test customer: {create_result} (Status: {status})")
            return False
        
        print(f"✅ Created test customer with ID: {create_result.get('id')}")
        customer_id = create_result.get('id')
    else:
        # Use first customer from the list
        customer_id = customers_data[0].get('id')
        print(f"✅ Found {len(customers_data)} customers. Using customer ID: {customer_id}")
    
    if not customer_id:
        print("❌ No valid customer ID found")
        return False
    
    # Step 2: Check for related vehicles before deletion
    print(f"\n2. Checking for vehicles related to customer {customer_id}...")
    success, vehicles_data, status = make_request("GET", "/vehicles")
    
    if success:
        related_vehicles = [v for v in vehicles_data if v.get('customerId') == customer_id]
        print(f"✅ Found {len(related_vehicles)} vehicles related to this customer")
        if related_vehicles:
            print(f"   Related vehicle IDs: {[v.get('id') for v in related_vehicles]}")
    else:
        print(f"⚠️  Could not check related vehicles: {vehicles_data}")
        related_vehicles = []
    
    # Step 3: Delete the customer
    print(f"\n3. Deleting customer {customer_id}...")
    success, delete_result, status = make_request("DELETE", f"/customers/{customer_id}")
    
    if not success:
        print(f"❌ DELETE request failed: {delete_result} (Status: {status})")
        return False
    
    print(f"✅ DELETE response: {delete_result}")
    
    # Step 4: Verify response contains {"success": true}
    if isinstance(delete_result, dict) and delete_result.get('success') == True:
        print("✅ Response contains {'success': true}")
    else:
        print(f"❌ Expected {{'success': true}}, got: {delete_result}")
        return False
    
    # Step 5: Verify customer is no longer in the list
    print(f"\n4. Verifying customer {customer_id} is deleted...")
    success, customers_after, status = make_request("GET", "/customers")
    
    if not success:
        print(f"❌ Failed to get customers after delete: {customers_after} (Status: {status})")
        return False
    
    # Check if deleted customer is still in the list
    deleted_customer_found = any(c.get('id') == customer_id for c in customers_after)
    
    if deleted_customer_found:
        print(f"❌ Customer {customer_id} still found in customers list after deletion")
        return False
    else:
        print(f"✅ Customer {customer_id} successfully removed from customers list")
    
    # Step 6: Verify related vehicles are handled properly
    if related_vehicles:
        print(f"\n5. Verifying related vehicles are handled...")
        success, vehicles_after, status = make_request("GET", "/vehicles")
        
        if success:
            remaining_related = [v for v in vehicles_after if v.get('customerId') == customer_id]
            if remaining_related:
                print(f"⚠️  Found {len(remaining_related)} vehicles still linked to deleted customer")
                print(f"   Vehicle IDs: {[v.get('id') for v in remaining_related]}")
                # This might be acceptable depending on implementation
            else:
                print("✅ No vehicles remain linked to deleted customer")
        else:
            print(f"⚠️  Could not verify related vehicles after deletion: {vehicles_after}")
    
    print("🎉 Customer delete test PASSED")
    return True

def main():
    """Run all delete operation tests"""
    print("🧪 DELETE Operations Test Suite")
    print("Testing with real Supabase database")
    print(f"Base URL: {BASE_URL}")
    print("=" * 60)
    
    # Test results
    vehicle_test_passed = False
    customer_test_passed = False
    
    try:
        # Test vehicle delete
        vehicle_test_passed = test_vehicle_delete()
        
        # Test customer delete
        customer_test_passed = test_customer_delete()
        
    except Exception as e:
        print(f"\n❌ Unexpected error during testing: {e}")
        return False
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    print(f"Vehicle Delete Test: {'✅ PASSED' if vehicle_test_passed else '❌ FAILED'}")
    print(f"Customer Delete Test: {'✅ PASSED' if customer_test_passed else '❌ FAILED'}")
    
    overall_success = vehicle_test_passed and customer_test_passed
    print(f"\nOverall Result: {'🎉 ALL TESTS PASSED' if overall_success else '❌ SOME TESTS FAILED'}")
    
    return overall_success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)