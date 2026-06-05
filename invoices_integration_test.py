#!/usr/bin/env python3
"""
اختبار شامل لنظام الفواتير التلقائية
Comprehensive Invoices Integration Testing
"""

import requests
import json
import sys
import os
from datetime import datetime

# Backend URL
API_URL = os.getenv("REACT_APP_BACKEND_URL", "https://garage-erp-arabic.preview.emergentagent.com")
BACKEND_URL = f"{API_URL}/api"

# Test results tracking
test_results = {
    "passed": [],
    "failed": [],
    "total": 0,
    "details": []
}

def log_test(name, passed, details=""):
    """Log test result"""
    test_results["total"] += 1
    result = {
        "name": name,
        "passed": passed,
        "details": details,
        "timestamp": datetime.now().isoformat()
    }
    test_results["details"].append(result)
    
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
    print("ملخص الاختبار - TEST SUMMARY")
    print("="*80)
    print(f"إجمالي الاختبارات - Total Tests: {test_results['total']}")
    print(f"نجح - Passed: {len(test_results['passed'])} ✅")
    print(f"فشل - Failed: {len(test_results['failed'])} ❌")
    
    if test_results['failed']:
        print("\nالاختبارات الفاشلة - Failed Tests:")
        for test in test_results['failed']:
            print(f"  - {test}")
    
    print("="*80)

# ============================================================================
# TEST 1: INVOICES API ENDPOINTS
# ============================================================================

def test_invoices_api():
    """Test Invoices API endpoints"""
    print("\n" + "="*80)
    print("اختبار 1: Invoices API Endpoints")
    print("="*80)
    
    # Test 1.1: GET /api/invoices
    print("\n[1.1] Testing GET /api/invoices")
    try:
        response = requests.get(f"{BACKEND_URL}/invoices", timeout=10)
        if response.status_code == 200:
            invoices = response.json()
            log_test("GET /api/invoices", True, 
                    f"Status: 200, Retrieved {len(invoices)} invoices")
        else:
            log_test("GET /api/invoices", False, 
                    f"Status: {response.status_code}, Response: {response.text[:200]}")
    except Exception as e:
        log_test("GET /api/invoices", False, f"Error: {str(e)}")
    
    # Test 1.2: POST /api/invoices (Create new invoice)
    print("\n[1.2] Testing POST /api/invoices")
    test_invoice_data = {
        "vehicleId": "test-vehicle-1",
        "customerId": "test-customer-1",
        "customerName": "أحمد محمد",
        "plateNumber": "ABC-1234",
        "items": [
            {"name": "تغيير زيت", "quantity": 1, "price": 150, "total": 150},
            {"name": "فلتر زيت", "quantity": 1, "price": 50, "total": 50}
        ],
        "subtotal": 200,
        "tax": 30,
        "total": 230,
        "status": "pending"
    }
    
    created_invoice_id = None
    try:
        response = requests.post(f"{BACKEND_URL}/invoices", 
                                json=test_invoice_data, 
                                timeout=10)
        if response.status_code == 200:
            data = response.json()
            created_invoice_id = data.get('id')
            log_test("POST /api/invoices", True, 
                    f"Status: 200, Created invoice ID: {created_invoice_id}")
        else:
            log_test("POST /api/invoices", False, 
                    f"Status: {response.status_code}, Response: {response.text[:300]}")
    except Exception as e:
        log_test("POST /api/invoices", False, f"Error: {str(e)}")
    
    # Test 1.3: GET /api/invoices?vehicleId=xxx
    print("\n[1.3] Testing GET /api/invoices?vehicleId=test-vehicle-1")
    try:
        response = requests.get(f"{BACKEND_URL}/invoices?vehicleId=test-vehicle-1", timeout=10)
        if response.status_code == 200:
            invoices = response.json()
            found = any(inv.get('vehicle_id') == 'test-vehicle-1' for inv in invoices)
            if found:
                log_test("GET /api/invoices?vehicleId", True, 
                        f"Status: 200, Found {len(invoices)} invoice(s) for vehicle")
            else:
                log_test("GET /api/invoices?vehicleId", False, 
                        f"Status: 200, but no invoices found for test-vehicle-1")
        else:
            log_test("GET /api/invoices?vehicleId", False, 
                    f"Status: {response.status_code}, Response: {response.text[:200]}")
    except Exception as e:
        log_test("GET /api/invoices?vehicleId", False, f"Error: {str(e)}")
    
    # Test 1.4: PUT /api/invoices/:id (Update invoice)
    if created_invoice_id:
        print(f"\n[1.4] Testing PUT /api/invoices/{created_invoice_id}")
        update_data = {
            "items": [
                {"name": "تغيير زيت", "quantity": 1, "price": 150, "total": 150},
                {"name": "فلتر زيت", "quantity": 2, "price": 50, "total": 100},
                {"name": "فلتر هواء", "quantity": 1, "price": 80, "total": 80}
            ],
            "subtotal": 330,
            "tax": 49.5,
            "total": 379.5,
            "status": "pending"
        }
        
        try:
            response = requests.put(f"{BACKEND_URL}/invoices/{created_invoice_id}", 
                                   json=update_data, 
                                   timeout=10)
            if response.status_code == 200:
                log_test("PUT /api/invoices/:id", True, 
                        f"Status: 200, Updated invoice successfully")
            else:
                log_test("PUT /api/invoices/:id", False, 
                        f"Status: {response.status_code}, Response: {response.text[:200]}")
        except Exception as e:
            log_test("PUT /api/invoices/:id", False, f"Error: {str(e)}")
    else:
        log_test("PUT /api/invoices/:id", False, "Skipped - no invoice created")
    
    # Test 1.5: GET /api/invoices/:id (Get single invoice)
    if created_invoice_id:
        print(f"\n[1.5] Testing GET /api/invoices/{created_invoice_id}")
        try:
            response = requests.get(f"{BACKEND_URL}/invoices/{created_invoice_id}", timeout=10)
            if response.status_code == 200:
                invoice = response.json()
                log_test("GET /api/invoices/:id", True, 
                        f"Status: 200, Retrieved invoice with {len(invoice.get('items', []))} items")
            else:
                log_test("GET /api/invoices/:id", False, 
                        f"Status: {response.status_code}, Response: {response.text[:200]}")
        except Exception as e:
            log_test("GET /api/invoices/:id", False, f"Error: {str(e)}")
    else:
        log_test("GET /api/invoices/:id", False, "Skipped - no invoice created")
    
    return created_invoice_id

# ============================================================================
# TEST 2: SUPABASE TABLE STRUCTURE
# ============================================================================

def test_supabase_table():
    """Test Supabase invoices table structure"""
    print("\n" + "="*80)
    print("اختبار 2: Supabase Table Structure")
    print("="*80)
    
    print("\n[2.1] Checking Supabase invoices table")
    try:
        # Try to get invoices to verify table exists
        response = requests.get(f"{BACKEND_URL}/invoices", timeout=10)
        if response.status_code == 200:
            invoices = response.json()
            
            # Check if we have any invoices to verify structure
            if invoices and len(invoices) > 0:
                sample_invoice = invoices[0]
                required_columns = [
                    'id', 'vehicle_id', 'customer_name', 'plate_number', 
                    'items', 'subtotal', 'tax', 'total', 'status', 'created_at'
                ]
                
                missing_columns = [col for col in required_columns if col not in sample_invoice]
                
                if not missing_columns:
                    log_test("Supabase table structure", True, 
                            f"All required columns present: {', '.join(required_columns)}")
                else:
                    log_test("Supabase table structure", False, 
                            f"Missing columns: {', '.join(missing_columns)}")
                
                # Display sample invoice structure
                print(f"\n   Sample invoice structure:")
                for key in sample_invoice.keys():
                    value = sample_invoice[key]
                    if isinstance(value, list):
                        print(f"   - {key}: [{len(value)} items]")
                    elif isinstance(value, dict):
                        print(f"   - {key}: {{dict}}")
                    else:
                        print(f"   - {key}: {type(value).__name__}")
            else:
                log_test("Supabase table structure", True, 
                        "Table exists but empty - cannot verify column structure")
        else:
            log_test("Supabase table structure", False, 
                    f"Failed to access table: Status {response.status_code}")
    except Exception as e:
        log_test("Supabase table structure", False, f"Error: {str(e)}")

# ============================================================================
# TEST 3: FRONTEND CODE VERIFICATION
# ============================================================================

def test_frontend_code():
    """Verify frontend code has createOrUpdateInvoice function"""
    print("\n" + "="*80)
    print("اختبار 3: Frontend Code Verification")
    print("="*80)
    
    print("\n[3.1] Checking VehicleDetails.jsx for createOrUpdateInvoice()")
    try:
        with open('/app/frontend/src/pages/VehicleDetails.jsx', 'r', encoding='utf-8') as f:
            content = f.read()
            
            # Check if createOrUpdateInvoice function exists
            if 'createOrUpdateInvoice' in content:
                log_test("createOrUpdateInvoice function exists", True, 
                        "Function found in VehicleDetails.jsx")
                
                # Check if it's being called
                if 'await createOrUpdateInvoice' in content:
                    log_test("createOrUpdateInvoice is called", True, 
                            "Function is being invoked in the code")
                else:
                    log_test("createOrUpdateInvoice is called", False, 
                            "Function exists but not being called")
                
                # Check if it uses /invoices endpoint
                if '/invoices' in content:
                    log_test("Uses /invoices endpoint", True, 
                            "Code uses correct API endpoint")
                else:
                    log_test("Uses /invoices endpoint", False, 
                            "Code may be using wrong endpoint")
            else:
                log_test("createOrUpdateInvoice function exists", False, 
                        "Function not found in VehicleDetails.jsx")
    except Exception as e:
        log_test("Frontend code verification", False, f"Error: {str(e)}")
    
    print("\n[3.2] Checking api.js for invoices endpoints")
    try:
        with open('/app/frontend/src/services/api.js', 'r', encoding='utf-8') as f:
            content = f.read()
            
            # Check if api.js has invoices endpoints
            if 'invoices' in content.lower():
                log_test("api.js has invoices endpoints", True, 
                        "Invoices endpoints found in api.js")
                
                # Check if it's using /invoices (not /v1/accounting/invoices)
                if '/v1/accounting/invoices' in content:
                    log_test("api.js uses correct endpoint", False, 
                            "Still using old /v1/accounting/invoices endpoint")
                elif '/invoices' in content:
                    log_test("api.js uses correct endpoint", True, 
                            "Using correct /invoices endpoint")
            else:
                log_test("api.js has invoices endpoints", False, 
                        "No invoices endpoints found in api.js")
    except FileNotFoundError:
        log_test("api.js verification", False, "api.js file not found")
    except Exception as e:
        log_test("api.js verification", False, f"Error: {str(e)}")

# ============================================================================
# TEST 4: INTEGRATION TEST
# ============================================================================

def test_integration():
    """Test full integration: Create vehicle -> Add items -> Verify invoice"""
    print("\n" + "="*80)
    print("اختبار 4: Integration Test (Vehicle -> Items -> Invoice)")
    print("="*80)
    
    # Step 1: Create a test vehicle
    print("\n[4.1] Creating test vehicle")
    vehicle_data = {
        "plateNumber": "TEST-999",
        "brand": "تويوتا",
        "model": "كامري",
        "year": 2023,
        "color": "أبيض",
        "customerName": "عميل اختبار الفواتير",
        "customerPhone": "0501234567",
        "customerEmail": "test@example.com",
        "status": "diagnosis"
    }
    
    vehicle_id = None
    try:
        response = requests.post(f"{BACKEND_URL}/vehicles", json=vehicle_data, timeout=10)
        if response.status_code == 200:
            vehicle = response.json()
            vehicle_id = vehicle.get('id')
            log_test("Create test vehicle", True, f"Vehicle ID: {vehicle_id}")
        else:
            log_test("Create test vehicle", False, 
                    f"Status: {response.status_code}, Response: {response.text[:200]}")
            return
    except Exception as e:
        log_test("Create test vehicle", False, f"Error: {str(e)}")
        return
    
    # Step 2: Simulate adding items (create invoice)
    print("\n[4.2] Creating invoice for vehicle")
    invoice_data = {
        "vehicleId": vehicle_id,
        "customerId": "test-customer-integration",
        "customerName": "عميل اختبار الفواتير",
        "plateNumber": "TEST-999",
        "items": [
            {"name": "تغيير زيت", "quantity": 1, "price": 150, "total": 150},
            {"name": "فحص كمبيوتر", "quantity": 1, "price": 200, "total": 200}
        ],
        "subtotal": 350,
        "tax": 52.5,
        "total": 402.5,
        "status": "pending"
    }
    
    invoice_id = None
    try:
        response = requests.post(f"{BACKEND_URL}/invoices", json=invoice_data, timeout=10)
        if response.status_code == 200:
            result = response.json()
            invoice_id = result.get('id')
            log_test("Create invoice for vehicle", True, f"Invoice ID: {invoice_id}")
        else:
            log_test("Create invoice for vehicle", False, 
                    f"Status: {response.status_code}, Response: {response.text[:200]}")
    except Exception as e:
        log_test("Create invoice for vehicle", False, f"Error: {str(e)}")
    
    # Step 3: Verify invoice is linked to vehicle
    print("\n[4.3] Verifying invoice is linked to vehicle")
    try:
        response = requests.get(f"{BACKEND_URL}/invoices?vehicleId={vehicle_id}", timeout=10)
        if response.status_code == 200:
            invoices = response.json()
            linked_invoice = next((inv for inv in invoices if inv.get('vehicle_id') == vehicle_id), None)
            
            if linked_invoice:
                log_test("Invoice linked to vehicle", True, 
                        f"Found invoice {linked_invoice.get('id')} linked to vehicle {vehicle_id}")
                
                # Verify invoice data
                items = linked_invoice.get('items', [])
                if len(items) == 2:
                    log_test("Invoice has correct items", True, 
                            f"Invoice has {len(items)} items as expected")
                else:
                    log_test("Invoice has correct items", False, 
                            f"Expected 2 items, found {len(items)}")
            else:
                log_test("Invoice linked to vehicle", False, 
                        f"No invoice found for vehicle {vehicle_id}")
        else:
            log_test("Invoice linked to vehicle", False, 
                    f"Status: {response.status_code}")
    except Exception as e:
        log_test("Invoice linked to vehicle", False, f"Error: {str(e)}")
    
    # Step 4: Update invoice (simulate adding more items)
    if invoice_id:
        print("\n[4.4] Updating invoice (adding more items)")
        update_data = {
            "items": [
                {"name": "تغيير زيت", "quantity": 1, "price": 150, "total": 150},
                {"name": "فحص كمبيوتر", "quantity": 1, "price": 200, "total": 200},
                {"name": "فلتر هواء", "quantity": 1, "price": 80, "total": 80}
            ],
            "subtotal": 430,
            "tax": 64.5,
            "total": 494.5,
            "status": "pending"
        }
        
        try:
            response = requests.put(f"{BACKEND_URL}/invoices/{invoice_id}", 
                                   json=update_data, 
                                   timeout=10)
            if response.status_code == 200:
                log_test("Update invoice with new items", True, 
                        "Invoice updated successfully")
                
                # Verify update
                response = requests.get(f"{BACKEND_URL}/invoices/{invoice_id}", timeout=10)
                if response.status_code == 200:
                    updated_invoice = response.json()
                    items = updated_invoice.get('items', [])
                    if len(items) == 3:
                        log_test("Invoice update verified", True, 
                                f"Invoice now has {len(items)} items")
                    else:
                        log_test("Invoice update verified", False, 
                                f"Expected 3 items, found {len(items)}")
            else:
                log_test("Update invoice with new items", False, 
                        f"Status: {response.status_code}")
        except Exception as e:
            log_test("Update invoice with new items", False, f"Error: {str(e)}")
    
    # Cleanup
    print("\n[Cleanup] Deleting test data")
    if vehicle_id:
        try:
            requests.delete(f"{BACKEND_URL}/vehicles/{vehicle_id}", timeout=10)
            print(f"   ✓ Deleted test vehicle {vehicle_id}")
        except Exception as e:
            print(f"   ⚠ Failed to delete vehicle: {str(e)}")

# ============================================================================
# TEST 5: ERROR SCENARIOS
# ============================================================================

def test_error_scenarios():
    """Test error handling"""
    print("\n" + "="*80)
    print("اختبار 5: Error Scenarios")
    print("="*80)
    
    # Test 5.1: Get non-existent invoice
    print("\n[5.1] Testing GET /api/invoices/non-existent-id")
    try:
        response = requests.get(f"{BACKEND_URL}/invoices/non-existent-id-12345", timeout=10)
        if response.status_code == 404:
            log_test("Get non-existent invoice returns 404", True, 
                    "Correctly returns 404 for non-existent invoice")
        else:
            log_test("Get non-existent invoice returns 404", False, 
                    f"Expected 404, got {response.status_code}")
    except Exception as e:
        log_test("Get non-existent invoice returns 404", False, f"Error: {str(e)}")
    
    # Test 5.2: Create invoice with missing required fields
    print("\n[5.2] Testing POST /api/invoices with missing fields")
    invalid_data = {
        "vehicleId": "test-vehicle",
        # Missing customerName, plateNumber, items, etc.
    }
    
    try:
        response = requests.post(f"{BACKEND_URL}/invoices", json=invalid_data, timeout=10)
        # Should either succeed with defaults or return error
        if response.status_code in [200, 400, 422]:
            log_test("Handle missing fields", True, 
                    f"Status: {response.status_code} (handled appropriately)")
        else:
            log_test("Handle missing fields", False, 
                    f"Unexpected status: {response.status_code}")
    except Exception as e:
        log_test("Handle missing fields", False, f"Error: {str(e)}")

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main test execution"""
    print("\n" + "="*80)
    print("اختبار شامل لنظام الفواتير التلقائية")
    print("COMPREHENSIVE INVOICES INTEGRATION TESTING")
    print("="*80)
    print(f"Backend URL: {BACKEND_URL}")
    print(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    # Run all tests
    test_invoices_api()
    test_supabase_table()
    test_frontend_code()
    test_integration()
    test_error_scenarios()
    
    # Print summary
    print_summary()
    
    # Save detailed results to file
    try:
        with open('/app/invoices_test_results.json', 'w', encoding='utf-8') as f:
            json.dump(test_results, f, ensure_ascii=False, indent=2)
        print(f"\n📄 Detailed results saved to: /app/invoices_test_results.json")
    except Exception as e:
        print(f"\n⚠ Failed to save results: {str(e)}")
    
    # Exit with appropriate code
    if test_results['failed']:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()
