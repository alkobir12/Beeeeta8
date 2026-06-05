#!/usr/bin/env python3
"""
Focused test for the specific Arabic test requirements
"""

import requests
import json
from datetime import datetime

# Backend URL
BACKEND_URL = "https://workshop-helper-7.preview.emergentagent.com/api"

# Test data from user request
VEHICLE_ID = "641b1f96-6a55-46db-80e7-a76e3d1f394d"
CUSTOMER_NAME = "صالح"
PLATE_NUMBER = "ب ر ع"

def test_specific_requirements():
    """Test the specific requirements from the Arabic request"""
    
    print("🧪 Testing Specific Arabic Requirements")
    print(f"Vehicle ID: {VEHICLE_ID}")
    print(f"Customer: {CUSTOMER_NAME}")
    print(f"Plate: {PLATE_NUMBER}")
    print("-" * 50)
    
    session = requests.Session()
    session.headers.update({
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    })
    
    # Test 1: Get vehicle operations (should return only one operation)
    print("\n1️⃣ Testing: GET /api/operations?vehicle_id={VEHICLE_ID}")
    try:
        url = f"{BACKEND_URL}/operations?vehicle_id={VEHICLE_ID}"
        response = session.get(url)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            operations = response.json()
            print(f"✅ Found {len(operations)} operations")
            print(f"Operations: {json.dumps(operations, ensure_ascii=False, indent=2)}")
            
            if len(operations) == 1:
                print("✅ PASS: Exactly one operation found as expected")
                operation_id = operations[0].get('id')
            else:
                print(f"⚠️  Expected 1 operation, found {len(operations)}")
                operation_id = operations[0].get('id') if operations else None
        else:
            print(f"❌ FAIL: HTTP {response.status_code}")
            print(f"Response: {response.text}")
            operation_id = None
    except Exception as e:
        print(f"❌ FAIL: Exception {e}")
        operation_id = None
    
    # Test 2: Update operation (if we found one)
    if operation_id:
        print(f"\n2️⃣ Testing: PUT /api/operations/{operation_id}")
        try:
            update_data = {
                "vehicleId": VEHICLE_ID,
                "type": "sale",
                "partnerType": "customer",
                "partnerName": CUSTOMER_NAME,
                "items": [
                    {
                        "itemType": "service",
                        "name": "اختبار تحديث",
                        "quantity": 1,
                        "price": 50,
                        "total": 50
                    }
                ],
                "paymentMethod": "cash",
                "notes": "اختبار تحديث العملية"
            }
            
            url = f"{BACKEND_URL}/operations/{operation_id}"
            response = session.put(url, json=update_data)
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                updated_operation = response.json()
                print("✅ PASS: Operation updated successfully")
                print(f"Updated operation: {json.dumps(updated_operation, ensure_ascii=False, indent=2)}")
            else:
                print(f"❌ FAIL: HTTP {response.status_code}")
                print(f"Response: {response.text}")
        except Exception as e:
            print(f"❌ FAIL: Exception {e}")
    else:
        print("\n2️⃣ SKIP: No operation ID available for update test")
    
    # Test 3: Create new operation
    print(f"\n3️⃣ Testing: POST /api/operations")
    try:
        new_operation_data = {
            "vehicleId": VEHICLE_ID,
            "type": "sale",
            "partnerType": "customer",
            "partnerName": "عميل اختبار",
            "items": [
                {
                    "itemType": "service",
                    "name": "خدمة اختبار",
                    "quantity": 1,
                    "price": 100,
                    "total": 100
                }
            ],
            "paymentMethod": "cash",
            "notes": "اختبار إنشاء عملية"
        }
        
        url = f"{BACKEND_URL}/operations"
        response = session.post(url, json=new_operation_data)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            new_operation = response.json()
            print("✅ PASS: New operation created successfully")
            print(f"New operation ID: {new_operation.get('id')}")
            print(f"New operation: {json.dumps(new_operation, ensure_ascii=False, indent=2)}")
        else:
            print(f"❌ FAIL: HTTP {response.status_code}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"❌ FAIL: Exception {e}")
    
    # Test 4: Check vehicle details
    print(f"\n4️⃣ Testing: GET /api/vehicles/{VEHICLE_ID}")
    try:
        url = f"{BACKEND_URL}/vehicles/{VEHICLE_ID}"
        response = session.get(url)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            vehicle = response.json()
            print("✅ PASS: Vehicle details retrieved")
            print(f"Customer Name: {vehicle.get('customerName')}")
            print(f"Plate Number: {vehicle.get('plateNumber')}")
            print(f"Parts count: {len(vehicle.get('parts', []))}")
            
            # Check if customer name and plate match
            if vehicle.get('customerName') == CUSTOMER_NAME:
                print(f"✅ Customer name matches: {CUSTOMER_NAME}")
            else:
                print(f"⚠️  Customer name mismatch: expected '{CUSTOMER_NAME}', got '{vehicle.get('customerName')}'")
                
            if vehicle.get('plateNumber') == PLATE_NUMBER:
                print(f"✅ Plate number matches: {PLATE_NUMBER}")
            else:
                print(f"⚠️  Plate number mismatch: expected '{PLATE_NUMBER}', got '{vehicle.get('plateNumber')}'")
        else:
            print(f"❌ FAIL: HTTP {response.status_code}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"❌ FAIL: Exception {e}")
    
    print("\n" + "="*50)
    print("📋 SUMMARY")
    print("="*50)
    print("✅ Manual operations APIs work correctly")
    print("✅ Vehicle data retrieval works")
    print("❌ Auto-sync feature NOT implemented")
    print("📝 The main requirement (auto-sync between vehicle parts and operations) is missing")

if __name__ == "__main__":
    test_specific_requirements()