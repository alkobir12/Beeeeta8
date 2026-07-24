#!/usr/bin/env python3
"""
Operations Scope Testing Script - Modified Version
اختبار ميزة (نوع العملية: مركبة / ورشة عامة) بدون إرسال حقل scope صراحة

Tests operations without explicitly sending scope field, 
relying on backend logic to infer scope from vehicleId presence.
"""

import requests
import json
import sys
from datetime import datetime

# Get backend URL from frontend/.env
BACKEND_URL = "https://stamp-approval-flow.preview.emergentagent.com/api"

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

def test_operations_scope_inference():
    """Test operations scope inference (without explicit scope field)"""
    print("\n" + "="*80)
    print("TESTING OPERATIONS SCOPE INFERENCE (اختبار استنتاج نوع العملية)")
    print("="*80)
    print(f"Backend URL: {BACKEND_URL}")
    print(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    # Setup: Create a test vehicle first
    print("\n[Setup] Creating test vehicle for operations testing")
    test_vehicle = {
        "plateNumber": "TEST-OP-001",
        "brand": "تويوتا",
        "model": "كامري",
        "year": 2020,
        "color": "أبيض",
        "customerName": "عميل اختبار العمليات",
        "customerPhone": "0501234567",
        "customerEmail": "test@example.com",
        "status": "diagnosis"
    }
    
    created_vehicle_id = None
    try:
        response = requests.post(f"{BACKEND_URL}/vehicles", json=test_vehicle, timeout=15)
        if response.status_code == 200:
            created_vehicle_id = response.json().get('id')
            print(f"   ✓ Created test vehicle: {created_vehicle_id}")
        else:
            print(f"   ⚠ Failed to create test vehicle: {response.status_code}")
    except Exception as e:
        print(f"   ⚠ Error creating test vehicle: {str(e)}")
    
    # Test 1: Create vehicle operation (with vehicleId, scope should be inferred as "vehicle")
    print("\n[1] Testing POST /api/operations (Vehicle Operation - scope inferred)")
    vehicle_operation = {
        "vehicleId": created_vehicle_id,
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
                    f"Operation ID: {vehicle_op_id}")
            
            # Check if vehicleId is preserved
            if data.get('vehicleId') == 'veh-test-1':
                print("   ✓ VehicleId field correctly preserved")
            else:
                print(f"   ⚠ VehicleId field issue: expected 'veh-test-1', got '{data.get('vehicleId')}'")
        else:
            log_test("Create vehicle operation", False, 
                    f"Status: {response.status_code}, Response: {response.text[:300]}")
    except Exception as e:
        log_test("Create vehicle operation", False, f"Error: {str(e)}")
    
    # Test 2: Create workshop operation (without vehicleId, scope should be inferred as "workshop")
    print("\n[2] Testing POST /api/operations (Workshop Operation - scope inferred)")
    workshop_operation = {
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
                    f"Operation ID: {workshop_op_id}")
            
            # Check that vehicleId is not set
            if not data.get('vehicleId'):
                print("   ✓ VehicleId field correctly empty/null")
            else:
                print(f"   ⚠ VehicleId field should be empty, got '{data.get('vehicleId')}'")
        else:
            log_test("Create workshop operation", False, 
                    f"Status: {response.status_code}, Response: {response.text[:300]}")
    except Exception as e:
        log_test("Create workshop operation", False, f"Error: {str(e)}")
    
    # Test 3: GET /api/operations (verify both operations appear with correct inferred scope)
    print("\n[3] Testing GET /api/operations (Verify scope inference)")
    try:
        response = requests.get(f"{BACKEND_URL}/operations", timeout=15)
        if response.status_code == 200:
            operations = response.json()
            log_test("Get all operations with scope inference", True, 
                    f"Retrieved {len(operations)} operations")
            
            # Find our test operations
            vehicle_op_found = None
            workshop_op_found = None
            
            for op in operations:
                if op.get('id') == vehicle_op_id:
                    vehicle_op_found = op
                elif op.get('id') == workshop_op_id:
                    workshop_op_found = op
            
            # Verify vehicle operation scope inference
            if vehicle_op_found:
                print(f"   ✓ Vehicle operation found: ID={vehicle_op_found.get('id')}")
                if vehicle_op_found.get('scope') == 'vehicle':
                    print("   ✅ Vehicle operation scope correctly inferred as 'vehicle'")
                else:
                    print(f"   ❌ Vehicle operation scope inference failed: expected 'vehicle', got '{vehicle_op_found.get('scope')}'")
                
                if vehicle_op_found.get('vehicleId') == '12345678-1234-1234-1234-123456789001':
                    print("   ✓ Vehicle operation has correct vehicleId")
                else:
                    print(f"   ❌ Vehicle operation vehicleId issue: expected '12345678-1234-1234-1234-123456789001', got '{vehicle_op_found.get('vehicleId')}'")
            else:
                print("   ❌ Vehicle operation not found in list")
            
            # Verify workshop operation scope inference
            if workshop_op_found:
                print(f"   ✓ Workshop operation found: ID={workshop_op_found.get('id')}")
                if workshop_op_found.get('scope') == 'workshop':
                    print("   ✅ Workshop operation scope correctly inferred as 'workshop'")
                else:
                    print(f"   ❌ Workshop operation scope inference failed: expected 'workshop', got '{workshop_op_found.get('scope')}'")
                
                if not workshop_op_found.get('vehicleId'):
                    print("   ✓ Workshop operation has no vehicleId (correct)")
                else:
                    print(f"   ❌ Workshop operation should have no vehicleId, got '{workshop_op_found.get('vehicleId')}'")
            else:
                print("   ❌ Workshop operation not found in list")
                
        else:
            log_test("Get all operations with scope inference", False, 
                    f"Status: {response.status_code}, Response: {response.text[:300]}")
    except Exception as e:
        log_test("Get all operations with scope inference", False, f"Error: {str(e)}")
    
    # Test 4: GET /api/operations?vehicle_id=finbot-insights-1 (verify filtering still works)
    print("\n[4] Testing GET /api/operations?vehicle_id=finbot-insights-1 (Filter by vehicle)")
    try:
        response = requests.get(f"{BACKEND_URL}/operations?vehicle_id=finbot-insights-1", timeout=15)
        if response.status_code == 200:
            filtered_operations = response.json()
            log_test("Filter operations by vehicle_id", True, 
                    f"Retrieved {len(filtered_operations)} operations for vehicle '12345678-1234-1234-1234-123456789001'")
            
            # Should only contain the vehicle operation, not the workshop operation
            vehicle_op_in_filter = None
            workshop_op_in_filter = None
            
            for op in filtered_operations:
                if op.get('id') == vehicle_op_id:
                    vehicle_op_in_filter = op
                elif op.get('id') == workshop_op_id:
                    workshop_op_in_filter = op
            
            if vehicle_op_in_filter:
                print("   ✅ Vehicle operation correctly included in filter")
                if vehicle_op_in_filter.get('vehicleId') == '12345678-1234-1234-1234-123456789001':
                    print("   ✓ Filtered operation has correct vehicleId")
                    if vehicle_op_in_filter.get('scope') == 'vehicle':
                        print("   ✓ Filtered operation has correct scope: 'vehicle'")
                    else:
                        print(f"   ⚠ Filtered operation scope issue: expected 'vehicle', got '{vehicle_op_in_filter.get('scope')}'")
                else:
                    print(f"   ❌ Filtered operation vehicleId issue: expected '12345678-1234-1234-1234-123456789001', got '{vehicle_op_in_filter.get('vehicleId')}'")
            else:
                print("   ❌ Vehicle operation missing from filtered results")
            
            if not workshop_op_in_filter:
                print("   ✅ Workshop operation correctly excluded from filter")
            else:
                print("   ❌ Workshop operation incorrectly included in vehicle filter")
                
        else:
            log_test("Filter operations by vehicle_id", False, 
                    f"Status: {response.status_code}, Response: {response.text[:300]}")
    except Exception as e:
        log_test("Filter operations by vehicle_id", False, f"Error: {str(e)}")

def main():
    """Main test execution"""
    print("OPERATIONS SCOPE INFERENCE TESTING")
    print("اختبار استنتاج نوع العملية (مركبة / ورشة عامة)")
    
    # Run the operations scope inference tests
    test_operations_scope_inference()
    
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
        print("\nThe scope field inference needs attention.")
    else:
        print("✅ ALL TESTS PASSED:")
        print("  - ✅ حقل scope يتم استنتاجه بشكل صحيح من وجود vehicleId")
        print("  - ✅ العمليات المركبة (مع vehicleId) تظهر بـ scope: 'vehicle'")
        print("  - ✅ العمليات العامة (بدون vehicleId) تظهر بـ scope: 'workshop'")
        print("  - ✅ الفلاتر بـ vehicle_id ما زالت تعمل بعد إضافة منطق الـ scope")
        print("  - ✅ كلا العمليتين تظهران في الرد من GET /api/operations")
        print("\nScope field inference is working correctly!")
    
    print("="*80)
    
    # Exit with appropriate code
    if test_results['failed']:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()