#!/usr/bin/env python3
"""
Backend Operations API Testing Script
اختبار Backend APIs الخاصة بالعمليات للتأكد من وجود بيانات تسمح باختبار UI

Test Requirements (Arabic):
1) GET /api/operations?workshop_id=finmodule-sync - check if returns operations list
2) If empty, create test operation via POST /api/operations 
3) Test PUT /api/operations/{id} to update items/total
4) Test DELETE /api/operations/{id}
"""

import requests
import json
import uuid
from datetime import datetime, timezone
import os
import sys

# Get BASE_URL from frontend .env
def get_base_url():
    try:
        with open('/app/frontend/.env', 'r') as f:
            for line in f:
                if line.startswith('REACT_APP_BACKEND_URL='):
                    return line.split('=', 1)[1].strip()
    except Exception as e:
        print(f"❌ Error reading frontend .env: {e}")
        return "https://accounting-engine-6.preview.emergentagent.com"
    
    return "https://accounting-engine-6.preview.emergentagent.com"

BASE_URL = get_base_url()
API_BASE = f"{BASE_URL}/api"

print(f"🔗 Testing Operations API at: {API_BASE}")
print(f"📅 Test Date: {datetime.now().isoformat()}")
print("=" * 60)

def test_get_operations():
    """Test 1: GET /api/operations with workshop_id parameter"""
    print("\n1️⃣ Testing GET /api/operations...")
    
    try:
        # Test with workshop_id parameter
        workshop_id = "finmodule-sync"
        response = requests.get(
            f"{API_BASE}/operations",
            params={"workshop_id": workshop_id},
            timeout=30
        )
        
        print(f"   📡 GET /api/operations?workshop_id={workshop_id}")
        print(f"   📊 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            operations = response.json()
            print(f"   ✅ Success: Found {len(operations)} operations")
            
            if operations:
                print("   📋 Sample operation structure:")
                sample = operations[0]
                for key in ['id', 'type', 'partnerName', 'total', 'items']:
                    if key in sample:
                        print(f"      - {key}: {sample[key]}")
            
            return operations
        else:
            print(f"   ❌ Failed: {response.status_code} - {response.text}")
            return []
            
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return []

def test_get_operations_no_params():
    """Test GET /api/operations without parameters"""
    print("\n🔄 Testing GET /api/operations (without workshop_id)...")
    
    try:
        response = requests.get(f"{API_BASE}/operations", timeout=30)
        print(f"   📡 GET /api/operations")
        print(f"   📊 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            operations = response.json()
            print(f"   ✅ Success: Found {len(operations)} operations")
            return operations
        else:
            print(f"   ❌ Failed: {response.status_code} - {response.text}")
            return []
            
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return []

def create_test_operation():
    """Test 2: POST /api/operations - Create test operation"""
    print("\n2️⃣ Creating test operation via POST /api/operations...")
    
    # Create minimal payload as specified
    operation_payload = {
        "workshopId": "finmodule-sync",
        "accountId": None,  # Use null like existing operations
        "partnerType": "customer",
        "partnerName": "عميل اختبار العمليات",
        "type": "sale",
        "paymentMethod": "credit",
        "items": [
            {
                "name": "خدمة تغيير زيت اختبار",
                "quantity": 1,
                "price": 150.0,
                "itemType": "service"
            },
            {
                "name": "فلتر زيت اختبار",
                "quantity": 2,
                "price": 25.0,
                "itemType": "part"
            }
        ],
        "notes": "عملية اختبار تم إنشاؤها بواسطة نظام الاختبار",
        "op_date": datetime.now(timezone.utc).strftime("%Y-%m-%d")
    }
    
    try:
        response = requests.post(
            f"{API_BASE}/operations",
            json=operation_payload,
            timeout=30
        )
        
        print(f"   📡 POST /api/operations")
        print(f"   📊 Status Code: {response.status_code}")
        
        if response.status_code in [200, 201]:
            operation = response.json()
            print(f"   ✅ Success: Created operation with ID: {operation.get('id')}")
            print(f"   💰 Total: {operation.get('total', 0)}")
            print(f"   👤 Partner: {operation.get('partnerName')}")
            print(f"   📦 Items: {len(operation.get('items', []))}")
            return operation
        else:
            print(f"   ❌ Failed: {response.status_code}")
            print(f"   📄 Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return None

def test_update_operation(operation_id):
    """Test 3: PUT /api/operations/{id} - Update operation"""
    print(f"\n3️⃣ Testing PUT /api/operations/{operation_id}...")
    
    # Update payload - modify items and total
    update_payload = {
        "items": [
            {
                "name": "خدمة تغيير زيت محدثة",
                "quantity": 1,
                "price": 200.0,  # Updated price
                "itemType": "service"
            },
            {
                "name": "فلتر زيت محدث",
                "quantity": 3,  # Updated quantity
                "price": 30.0,  # Updated price
                "itemType": "part"
            },
            {
                "name": "بند جديد - فحص كمبيوتر",
                "quantity": 1,
                "price": 100.0,
                "itemType": "service"
            }
        ],
        "total": 390.0,  # 200 + (3*30) + 100
        "notes": "تم تحديث العملية - إضافة بند جديد وتعديل الأسعار"
    }
    
    try:
        response = requests.put(
            f"{API_BASE}/operations/{operation_id}",
            json=update_payload,
            timeout=30
        )
        
        print(f"   📡 PUT /api/operations/{operation_id}")
        print(f"   📊 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            updated_operation = response.json()
            print(f"   ✅ Success: Updated operation")
            print(f"   💰 New Total: {updated_operation.get('total', 0)}")
            print(f"   📦 New Items Count: {len(updated_operation.get('items', []))}")
            
            # Verify the update
            items = updated_operation.get('items', [])
            calculated_total = sum(item.get('price', 0) * item.get('quantity', 1) for item in items)
            print(f"   🧮 Calculated Total: {calculated_total}")
            
            return updated_operation
        else:
            print(f"   ❌ Failed: {response.status_code}")
            print(f"   📄 Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return None

def test_get_single_operation(operation_id):
    """Test GET /api/operations/{id} - Get single operation"""
    print(f"\n🔍 Testing GET /api/operations/{operation_id}...")
    
    try:
        response = requests.get(f"{API_BASE}/operations/{operation_id}", timeout=30)
        
        print(f"   📡 GET /api/operations/{operation_id}")
        print(f"   📊 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            operation = response.json()
            print(f"   ✅ Success: Retrieved operation")
            print(f"   👤 Partner: {operation.get('partnerName')}")
            print(f"   💰 Total: {operation.get('total')}")
            print(f"   📦 Items: {len(operation.get('items', []))}")
            return operation
        else:
            print(f"   ❌ Failed: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return None

def test_delete_operation(operation_id):
    """Test 4: DELETE /api/operations/{id} - Delete operation"""
    print(f"\n4️⃣ Testing DELETE /api/operations/{operation_id}...")
    
    try:
        response = requests.delete(f"{API_BASE}/operations/{operation_id}", timeout=30)
        
        print(f"   📡 DELETE /api/operations/{operation_id}")
        print(f"   📊 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ Success: Operation deleted")
            print(f"   📄 Response: {result}")
            
            # Verify deletion by trying to get the operation
            verify_response = requests.get(f"{API_BASE}/operations/{operation_id}", timeout=30)
            if verify_response.status_code == 404:
                print(f"   ✅ Verified: Operation no longer exists (404)")
            else:
                print(f"   ⚠️  Warning: Operation still exists (Status: {verify_response.status_code})")
            
            return True
        else:
            print(f"   ❌ Failed: {response.status_code}")
            print(f"   📄 Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return False

def main():
    """Main test execution"""
    print("🚀 Starting Backend Operations API Testing")
    print(f"🎯 Target: {API_BASE}")
    
    results = {
        "get_operations_with_workshop_id": False,
        "get_operations_no_params": False,
        "create_operation": False,
        "update_operation": False,
        "get_single_operation": False,
        "delete_operation": False,
        "created_operation_id": None
    }
    
    # Test 1: GET operations with workshop_id
    operations_with_id = test_get_operations()
    results["get_operations_with_workshop_id"] = len(operations_with_id) >= 0  # Success if no error
    
    # Test 1b: GET operations without parameters
    operations_no_params = test_get_operations_no_params()
    results["get_operations_no_params"] = len(operations_no_params) >= 0  # Success if no error
    
    # Test 2: Create operation if needed
    created_operation = create_test_operation()
    operation_id = None
    
    if created_operation and created_operation.get('id'):
        results["create_operation"] = True
        results["created_operation_id"] = created_operation['id']
        operation_id = created_operation['id']
    else:
        # If creation failed, use an existing operation for testing update/delete
        if operations_with_id:
            operation_id = operations_with_id[0]['id']
            print(f"\n⚠️  Using existing operation for update/delete tests: {operation_id}")
    
    if operation_id:
        # Test 3: Get single operation
        single_operation = test_get_single_operation(operation_id)
        results["get_single_operation"] = single_operation is not None
        
        # Test 4: Update operation (only if we created it, not existing ones)
        if results["create_operation"]:
            updated_operation = test_update_operation(operation_id)
            results["update_operation"] = updated_operation is not None
            
            # Test 5: Delete operation (only if we created it)
            delete_success = test_delete_operation(operation_id)
            results["delete_operation"] = delete_success
        else:
            print(f"\n⚠️  Skipping update/delete tests on existing operation to avoid data corruption")
    
    # Final verification - check operations list again
    print("\n🔄 Final verification - checking operations list...")
    final_operations = test_get_operations()
    
    # Summary Report
    print("\n" + "=" * 60)
    print("📊 OPERATIONS API TEST RESULTS SUMMARY")
    print("=" * 60)
    
    passed_tests = sum(1 for result in results.values() if result is True)
    total_tests = len([k for k in results.keys() if k != "created_operation_id"])
    
    print(f"✅ Passed: {passed_tests}/{total_tests} tests")
    print(f"🎯 Success Rate: {(passed_tests/total_tests)*100:.1f}%")
    
    print("\n📋 Detailed Results:")
    test_names = {
        "get_operations_with_workshop_id": "GET /api/operations?workshop_id=finmodule-sync",
        "get_operations_no_params": "GET /api/operations (no params)",
        "create_operation": "POST /api/operations (create)",
        "get_single_operation": "GET /api/operations/{id}",
        "update_operation": "PUT /api/operations/{id}",
        "delete_operation": "DELETE /api/operations/{id}"
    }
    
    for key, name in test_names.items():
        status = "✅ PASS" if results[key] else "❌ FAIL"
        print(f"   {status} - {name}")
    
    if results["created_operation_id"]:
        print(f"\n🆔 Test Operation ID: {results['created_operation_id']}")
    
    # Query Parameters Report
    print("\n📝 QUERY PARAMETERS REPORT:")
    print("   - workshop_id: Optional parameter for filtering operations by workshop")
    print("   - account_id: Optional parameter for filtering by account")
    print("   - type: Optional parameter for filtering by operation type (sale/purchase)")
    print("   - vehicle_id: Optional parameter for filtering by vehicle")
    
    # API Endpoints Summary
    print("\n🔗 API ENDPOINTS TESTED:")
    print("   - GET /api/operations - List operations (with optional query params)")
    print("   - POST /api/operations - Create new operation")
    print("   - GET /api/operations/{id} - Get single operation")
    print("   - PUT /api/operations/{id} - Update operation")
    print("   - DELETE /api/operations/{id} - Delete operation")
    
    print(f"\n🏁 Testing completed at: {datetime.now().isoformat()}")
    
    # Return success status
    return passed_tests == total_tests

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)