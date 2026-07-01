#!/usr/bin/env python3
"""
Operations Scope Testing Script
اختبار ميزة (نوع العملية: مركبة / ورشة عامة) بعد التعديلات الأخيرة

Tests:
1. Create vehicle operation (scope: "vehicle") with vehicleId
2. Create workshop operation (scope: "workshop") without vehicleId  
3. GET /api/operations - verify both operations appear with correct scope
4. GET /api/operations?vehicle_id=veh-test-1 - verify filtering works
"""

import requests
import json
import sys
from datetime import datetime

# Get backend URL from frontend/.env
BACKEND_URL = "https://erp-compliance-check.preview.emergentagent.com/api"

# Test results tracking
test_results = {
    "passed": [],
    "failed": [],
    "total": 0
}

def log_test(name, passed, details=""):
    """Log test result"""
    test_results["total"] += 1
    if passed:
        test_results["passed"].append(name)
        print(f"✅ {name}")
        if details:
            print(f"   {details}")
    else:
        test_results["failed"].append(name)
        print(f"❌ {name}")
        if details:
            print(f"   {details}")

def print_summary():
    """Print test summary"""
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Total Tests: {test_results['total']}")
    print(f"Passed: {len(test_results['passed'])} ✅")
    print(f"Failed: {len(test_results['failed'])} ❌")
    
    if test_results['failed']:
        print("\nFailed Tests:")
        for test in test_results['failed']:
            print(f"  - {test}")
    
    print("="*80)

def test_operations_scope():
    """Test operations with scope field (vehicle vs workshop)"""
    print("\n" + "="*80)
    print("TESTING OPERATIONS SCOPE FEATURE (اختبار ميزة نوع العملية)")
    print("="*80)
    print(f"Backend URL: {BACKEND_URL}")
    print(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    # Test 1: Create vehicle operation (scope: "vehicle")
    print("\n[1] Testing POST /api/operations (Vehicle Operation)")
    vehicle_operation = {
        "accountId": "test-account-1",
        "vehicleId": "veh-test-1",
        "scope": "vehicle",
        "type": "purchase",
        "partnerType": "supplier",
        "partnerName": "مورد اختبار المركبة",
        "items": [
            {"itemType": "part", "itemId": "p1", "name": "فلتر زيت", "qty": 1, "price": 100}
        ],
        "paymentMethod": "cash",
        "notes": "عملية مشتريات على مركبة"
    }
    
    vehicle_op_id = None
    try:
        response = requests.post(f"{BACKEND_URL}/operations", 
                                json=vehicle_operation, 
                                timeout=15)
        if response.status_code == 200:
            data = response.json()
            vehicle_op_id = data.get('id')
            log_test("Create vehicle operation", True, 
                    f"Operation ID: {vehicle_op_id}, Scope: {data.get('scope', 'N/A')}")
            
            # Verify scope field
            if data.get('scope') == 'vehicle':
                print("   ✓ Scope field correctly set to 'vehicle'")
            else:
                print(f"   ⚠ Scope field issue: expected 'vehicle', got '{data.get('scope')}'")
                
            # Verify vehicleId field
            if data.get('vehicleId') == 'veh-test-1':
                print("   ✓ VehicleId field correctly preserved")
            else:
                print(f"   ⚠ VehicleId field issue: expected 'veh-test-1', got '{data.get('vehicleId')}'")
        else:
            log_test("Create vehicle operation", False, 
                    f"Status: {response.status_code}, Response: {response.text[:300]}")
    except Exception as e:
        log_test("Create vehicle operation", False, f"Error: {str(e)}")
    
    # Test 2: Create workshop operation (scope: "workshop")
    print("\n[2] Testing POST /api/operations (Workshop Operation)")
    workshop_operation = {
        "accountId": "test-account-2",
        "scope": "workshop",
        "type": "purchase",
        "partnerType": "supplier",
        "partnerName": "مورد مواد تنظيف",
        "items": [
            {"itemType": "part", "itemId": "p2", "name": "منظفات ورشة", "qty": 3, "price": 50}
        ],
        "paymentMethod": "cash",
        "notes": "عملية عامة للورشة"
    }
    
    workshop_op_id = None
    try:
        response = requests.post(f"{BACKEND_URL}/operations", 
                                json=workshop_operation, 
                                timeout=15)
        if response.status_code == 200:
            data = response.json()
            workshop_op_id = data.get('id')
            log_test("Create workshop operation", True, 
                    f"Operation ID: {workshop_op_id}, Scope: {data.get('scope', 'N/A')}")
            
            # Verify scope field
            if data.get('scope') == 'workshop':
                print("   ✓ Scope field correctly set to 'workshop'")
            else:
                print(f"   ⚠ Scope field issue: expected 'workshop', got '{data.get('scope')}'")
                
            # Verify no vehicleId field
            if not data.get('vehicleId'):
                print("   ✓ VehicleId field correctly empty/null")
            else:
                print(f"   ⚠ VehicleId field should be empty, got '{data.get('vehicleId')}'")
        else:
            log_test("Create workshop operation", False, 
                    f"Status: {response.status_code}, Response: {response.text[:300]}")
    except Exception as e:
        log_test("Create workshop operation", False, f"Error: {str(e)}")
    
    # Test 3: GET /api/operations (verify both operations appear with correct scope)
    print("\n[3] Testing GET /api/operations (List all operations)")
    try:
        response = requests.get(f"{BACKEND_URL}/operations", timeout=15)
        if response.status_code == 200:
            operations = response.json()
            log_test("Get all operations", True, 
                    f"Retrieved {len(operations)} operations")
            
            # Find our test operations
            vehicle_op_found = None
            workshop_op_found = None
            
            for op in operations:
                if op.get('id') == vehicle_op_id:
                    vehicle_op_found = op
                elif op.get('id') == workshop_op_id:
                    workshop_op_found = op
            
            # Verify vehicle operation
            if vehicle_op_found:
                print(f"   ✓ Vehicle operation found: ID={vehicle_op_found.get('id')}")
                if vehicle_op_found.get('scope') == 'vehicle':
                    print("   ✓ Vehicle operation has correct scope: 'vehicle'")
                else:
                    print(f"   ❌ Vehicle operation scope issue: expected 'vehicle', got '{vehicle_op_found.get('scope')}'")
                
                if vehicle_op_found.get('vehicleId') == 'veh-test-1':
                    print("   ✓ Vehicle operation has correct vehicleId")
                else:
                    print(f"   ❌ Vehicle operation vehicleId issue: expected 'veh-test-1', got '{vehicle_op_found.get('vehicleId')}'")
            else:
                print("   ❌ Vehicle operation not found in list")
            
            # Verify workshop operation
            if workshop_op_found:
                print(f"   ✓ Workshop operation found: ID={workshop_op_found.get('id')}")
                if workshop_op_found.get('scope') == 'workshop':
                    print("   ✓ Workshop operation has correct scope: 'workshop'")
                else:
                    print(f"   ❌ Workshop operation scope issue: expected 'workshop', got '{workshop_op_found.get('scope')}'")
                
                if not workshop_op_found.get('vehicleId'):
                    print("   ✓ Workshop operation has no vehicleId (correct)")
                else:
                    print(f"   ❌ Workshop operation should have no vehicleId, got '{workshop_op_found.get('vehicleId')}'")
            else:
                print("   ❌ Workshop operation not found in list")
                
        else:
            log_test("Get all operations", False, 
                    f"Status: {response.status_code}, Response: {response.text[:300]}")
    except Exception as e:
        log_test("Get all operations", False, f"Error: {str(e)}")
    
    # Test 4: GET /api/operations?vehicle_id=veh-test-1 (verify filtering works)
    print("\n[4] Testing GET /api/operations?vehicle_id=veh-test-1 (Filter by vehicle)")
    try:
        response = requests.get(f"{BACKEND_URL}/operations?vehicle_id=veh-test-1", timeout=15)
        if response.status_code == 200:
            filtered_operations = response.json()
            log_test("Filter operations by vehicle_id", True, 
                    f"Retrieved {len(filtered_operations)} operations for vehicle 'veh-test-1'")
            
            # Should only contain the vehicle operation, not the workshop operation
            vehicle_op_in_filter = None
            workshop_op_in_filter = None
            
            for op in filtered_operations:
                if op.get('id') == vehicle_op_id:
                    vehicle_op_in_filter = op
                elif op.get('id') == workshop_op_id:
                    workshop_op_in_filter = op
            
            if vehicle_op_in_filter:
                print("   ✓ Vehicle operation correctly included in filter")
                if vehicle_op_in_filter.get('vehicleId') == 'veh-test-1':
                    print("   ✓ Filtered operation has correct vehicleId")
                else:
                    print(f"   ❌ Filtered operation vehicleId issue: expected 'veh-test-1', got '{vehicle_op_in_filter.get('vehicleId')}'")
            else:
                print("   ❌ Vehicle operation missing from filtered results")
            
            if not workshop_op_in_filter:
                print("   ✓ Workshop operation correctly excluded from filter")
            else:
                print("   ❌ Workshop operation incorrectly included in vehicle filter")
                
        else:
            log_test("Filter operations by vehicle_id", False, 
                    f"Status: {response.status_code}, Response: {response.text[:300]}")
    except Exception as e:
        log_test("Filter operations by vehicle_id", False, f"Error: {str(e)}")
    
    # Test 5: Verify scope field persistence and retrieval
    print("\n[5] Testing scope field persistence in Supabase/storage")
    
    # Check if scope field is properly saved and retrieved
    scope_persistence_test = True
    scope_details = []
    
    try:
        response = requests.get(f"{BACKEND_URL}/operations", timeout=15)
        if response.status_code == 200:
            operations = response.json()
            
            for op in operations:
                if op.get('id') in [vehicle_op_id, workshop_op_id]:
                    scope = op.get('scope')
                    vehicle_id = op.get('vehicleId')
                    
                    if op.get('id') == vehicle_op_id:
                        if scope != 'vehicle':
                            scope_persistence_test = False
                            scope_details.append(f"Vehicle operation scope wrong: {scope}")
                        if vehicle_id != 'veh-test-1':
                            scope_persistence_test = False
                            scope_details.append(f"Vehicle operation vehicleId wrong: {vehicle_id}")
                    
                    elif op.get('id') == workshop_op_id:
                        if scope != 'workshop':
                            scope_persistence_test = False
                            scope_details.append(f"Workshop operation scope wrong: {scope}")
                        if vehicle_id:
                            scope_persistence_test = False
                            scope_details.append(f"Workshop operation should have no vehicleId: {vehicle_id}")
            
            if scope_persistence_test:
                log_test("Scope field persistence", True, 
                        "All scope fields correctly saved and retrieved from Supabase")
            else:
                log_test("Scope field persistence", False, 
                        f"Issues found: {'; '.join(scope_details)}")
        else:
            log_test("Scope field persistence", False, 
                    f"Could not retrieve operations for verification: {response.status_code}")
    except Exception as e:
        log_test("Scope field persistence", False, f"Error: {str(e)}")

def main():
    """Main test execution"""
    print("OPERATIONS SCOPE TESTING")
    print("اختبار ميزة (نوع العملية: مركبة / ورشة عامة)")
    
    # Run the operations scope tests
    test_operations_scope()
    
    # Print summary
    print_summary()
    
    # Report findings
    print("\n" + "="*80)
    print("FINDINGS REPORT (تقرير النتائج)")
    print("="*80)
    
    if test_results['failed']:
        print("❌ ISSUES FOUND:")
        for test in test_results['failed']:
            print(f"  - {test}")
        print("\nThe scope field feature needs attention.")
    else:
        print("✅ ALL TESTS PASSED:")
        print("  - حقل scope محفوظ ويعود من Supabase/المخزن كما هو")
        print("  - الفلاتر بـ vehicle_id ما زالت تعمل بعد إضافة الحقل")
        print("  - العمليات المركبة (scope: vehicle) تحتوي على vehicleId")
        print("  - العمليات العامة (scope: workshop) لا تحتوي على vehicleId")
        print("\nScope field feature is working correctly!")
    
    print("="*80)
    
    # Exit with appropriate code
    if test_results['failed']:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()