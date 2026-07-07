#!/usr/bin/env python3
"""
اختبار نظام الفواتير المعتمد على الملفات
Testing File-Based Invoice System
"""

import requests
import json
import sys
from datetime import datetime

# Backend URL from environment
BACKEND_URL = "https://accounting-engine-6.preview.emergentagent.com/api"

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
    print("ملخص نتائج الاختبار - TEST SUMMARY")
    print("="*80)
    print(f"إجمالي الاختبارات - Total Tests: {test_results['total']}")
    print(f"نجح - Passed: {len(test_results['passed'])} ✅")
    print(f"فشل - Failed: {len(test_results['failed'])} ❌")
    
    if test_results['failed']:
        print("\nالاختبارات الفاشلة - Failed Tests:")
        for test in test_results['failed']:
            print(f"  - {test}")
    
    print("="*80)

def test_invoice_system():
    """اختبار نظام الفواتير المعتمد على الملفات"""
    print("\n" + "="*80)
    print("اختبار نظام الفواتير المعتمد على الملفات")
    print("TESTING FILE-BASED INVOICE SYSTEM")
    print("="*80)
    
    # Test 1: GET /api/invoices - التأكد أن الـ endpoint يعمل ويعيد مصفوفة JSON
    print("\n[1] اختبار GET /api/invoices - التأكد من عمل الـ endpoint وإرجاع مصفوفة JSON")
    print("[1] Testing GET /api/invoices - Ensure endpoint works and returns JSON array")
    
    try:
        response = requests.get(f"{BACKEND_URL}/invoices", timeout=10)
        print(f"   Status Code: {response.status_code}")
        print(f"   Response Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                if isinstance(data, list):
                    log_test("GET /api/invoices returns JSON array", True, 
                            f"Status: {response.status_code}, Array length: {len(data)}")
                    print(f"   Response: {json.dumps(data, ensure_ascii=False, indent=2)[:500]}...")
                else:
                    log_test("GET /api/invoices returns JSON array", False, 
                            f"Status: {response.status_code}, Response is not an array: {type(data)}")
            except json.JSONDecodeError as e:
                log_test("GET /api/invoices returns JSON array", False, 
                        f"Status: {response.status_code}, Invalid JSON: {str(e)}")
        else:
            log_test("GET /api/invoices returns JSON array", False, 
                    f"Status: {response.status_code}, Response: {response.text[:200]}")
    except Exception as e:
        log_test("GET /api/invoices returns JSON array", False, f"Error: {str(e)}")
    
    # Test 2: POST /api/invoices - إنشاء فاتورة تجريبية
    print("\n[2] اختبار POST /api/invoices - إنشاء فاتورة تجريبية")
    print("[2] Testing POST /api/invoices - Create test invoice")
    
    test_invoice = {
        "vehicleId": "test-vehicle-123",
        "customerId": "test-customer-123", 
        "customerName": "عميل تجريبي",
        "plateNumber": "ت ج ر 1234",
        "items": [
            {"name": "خدمة تجريبية", "quantity": 1, "price": 100, "total": 100}
        ],
        "subtotal": 100,
        "tax": 15,
        "total": 115,
        "status": "pending"
    }
    
    created_invoice_id = None
    try:
        response = requests.post(f"{BACKEND_URL}/invoices", json=test_invoice, timeout=10)
        print(f"   Status Code: {response.status_code}")
        print(f"   Response Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"   Response: {json.dumps(data, ensure_ascii=False, indent=2)}")
                
                if data.get('success') == True and 'id' in data:
                    created_invoice_id = data['id']
                    log_test("POST /api/invoices creates invoice", True, 
                            f"Status: {response.status_code}, Success: {data.get('success')}, ID: {created_invoice_id}")
                else:
                    log_test("POST /api/invoices creates invoice", False, 
                            f"Status: {response.status_code}, Missing success=true or id field")
            except json.JSONDecodeError as e:
                log_test("POST /api/invoices creates invoice", False, 
                        f"Status: {response.status_code}, Invalid JSON: {str(e)}")
        else:
            log_test("POST /api/invoices creates invoice", False, 
                    f"Status: {response.status_code}, Response: {response.text[:200]}")
    except Exception as e:
        log_test("POST /api/invoices creates invoice", False, f"Error: {str(e)}")
    
    # Test 3: GET /api/invoices?vehicleId=test-vehicle-123 - التأكد أن الفاتورة الجديدة تظهر
    print("\n[3] اختبار GET /api/invoices?vehicleId=test-vehicle-123 - التأكد من ظهور الفاتورة الجديدة")
    print("[3] Testing GET /api/invoices?vehicleId=test-vehicle-123 - Ensure new invoice appears")
    
    try:
        response = requests.get(f"{BACKEND_URL}/invoices?vehicleId=test-vehicle-123", timeout=10)
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"   Response: {json.dumps(data, ensure_ascii=False, indent=2)}")
                
                if isinstance(data, list):
                    # البحث عن الفاتورة المنشأة
                    found_invoice = None
                    for invoice in data:
                        if invoice.get('vehicleId') == 'test-vehicle-123' or invoice.get('vehicle_id') == 'test-vehicle-123':
                            found_invoice = invoice
                            break
                    
                    if found_invoice:
                        log_test("GET /api/invoices?vehicleId shows new invoice", True, 
                                f"Status: {response.status_code}, Found invoice with ID: {found_invoice.get('id')}")
                        
                        # التحقق من البيانات
                        if (found_invoice.get('customerName') == 'عميل تجريبي' and 
                            found_invoice.get('plateNumber') == 'ت ج ر 1234' and
                            found_invoice.get('total') == 115):
                            print("   ✓ بيانات الفاتورة صحيحة - Invoice data is correct")
                        else:
                            print("   ⚠ بيانات الفاتورة غير مطابقة - Invoice data mismatch")
                    else:
                        log_test("GET /api/invoices?vehicleId shows new invoice", False, 
                                f"Status: {response.status_code}, Invoice not found in filtered results")
                else:
                    log_test("GET /api/invoices?vehicleId shows new invoice", False, 
                            f"Status: {response.status_code}, Response is not an array")
            except json.JSONDecodeError as e:
                log_test("GET /api/invoices?vehicleId shows new invoice", False, 
                        f"Status: {response.status_code}, Invalid JSON: {str(e)}")
        else:
            log_test("GET /api/invoices?vehicleId shows new invoice", False, 
                    f"Status: {response.status_code}, Response: {response.text[:200]}")
    except Exception as e:
        log_test("GET /api/invoices?vehicleId shows new invoice", False, f"Error: {str(e)}")
    
    # Test 4: PUT /api/invoices/{id} - تحديث حالة الفاتورة
    if created_invoice_id:
        print(f"\n[4] اختبار PUT /api/invoices/{created_invoice_id} - تحديث حالة الفاتورة إلى 'issued'")
        print(f"[4] Testing PUT /api/invoices/{created_invoice_id} - Update invoice status to 'issued'")
        
        update_data = {"status": "issued"}
        
        try:
            response = requests.put(f"{BACKEND_URL}/invoices/{created_invoice_id}", 
                                   json=update_data, timeout=10)
            print(f"   Status Code: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"   Response: {json.dumps(data, ensure_ascii=False, indent=2)}")
                    
                    if data.get('success') == True:
                        log_test("PUT /api/invoices/{id} updates status", True, 
                                f"Status: {response.status_code}, Success: {data.get('success')}")
                        
                        # التحقق من تحديث الحالة في البيانات المرجعة
                        if data.get('data', {}).get('status') == 'issued':
                            print("   ✓ تم تحديث الحالة بنجاح - Status updated successfully")
                        else:
                            print("   ⚠ الحالة لم تتحدث في الاستجابة - Status not updated in response")
                    else:
                        log_test("PUT /api/invoices/{id} updates status", False, 
                                f"Status: {response.status_code}, Success field missing or false")
                except json.JSONDecodeError as e:
                    log_test("PUT /api/invoices/{id} updates status", False, 
                            f"Status: {response.status_code}, Invalid JSON: {str(e)}")
            else:
                log_test("PUT /api/invoices/{id} updates status", False, 
                        f"Status: {response.status_code}, Response: {response.text[:200]}")
        except Exception as e:
            log_test("PUT /api/invoices/{id} updates status", False, f"Error: {str(e)}")
    else:
        log_test("PUT /api/invoices/{id} updates status", False, "Skipped - no invoice ID available")
    
    # Test 5: GET /api/invoices/{id} - التحقق من تحديث الحالة
    if created_invoice_id:
        print(f"\n[5] اختبار GET /api/invoices/{created_invoice_id} - التحقق من تحديث الحالة")
        print(f"[5] Testing GET /api/invoices/{created_invoice_id} - Verify status update")
        
        try:
            response = requests.get(f"{BACKEND_URL}/invoices/{created_invoice_id}", timeout=10)
            print(f"   Status Code: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"   Response: {json.dumps(data, ensure_ascii=False, indent=2)}")
                    
                    if data.get('status') == 'issued':
                        log_test("GET /api/invoices/{id} shows updated status", True, 
                                f"Status: {response.status_code}, Invoice status: {data.get('status')}")
                    else:
                        log_test("GET /api/invoices/{id} shows updated status", False, 
                                f"Status: {response.status_code}, Expected 'issued', got: {data.get('status')}")
                except json.JSONDecodeError as e:
                    log_test("GET /api/invoices/{id} shows updated status", False, 
                            f"Status: {response.status_code}, Invalid JSON: {str(e)}")
            else:
                log_test("GET /api/invoices/{id} shows updated status", False, 
                        f"Status: {response.status_code}, Response: {response.text[:200]}")
        except Exception as e:
            log_test("GET /api/invoices/{id} shows updated status", False, f"Error: {str(e)}")
    else:
        log_test("GET /api/invoices/{id} shows updated status", False, "Skipped - no invoice ID available")
    
    # Test 6: التحقق من التخزين في ملفات JSON
    print("\n[6] اختبار التخزين في ملفات JSON - Testing JSON file storage")
    
    # نحاول الحصول على جميع الفواتير مرة أخرى للتأكد من الثبات
    try:
        response = requests.get(f"{BACKEND_URL}/invoices", timeout=10)
        if response.status_code == 200:
            data = response.json()
            
            # البحث عن الفاتورة المنشأة
            found_invoice = None
            for invoice in data:
                if invoice.get('id') == created_invoice_id:
                    found_invoice = invoice
                    break
            
            if found_invoice and found_invoice.get('status') == 'issued':
                log_test("JSON file storage persistence", True, 
                        f"Invoice persisted with updated status: {found_invoice.get('status')}")
            elif found_invoice:
                log_test("JSON file storage persistence", False, 
                        f"Invoice found but status not persisted: {found_invoice.get('status')}")
            else:
                log_test("JSON file storage persistence", False, 
                        "Invoice not found in persistence check")
        else:
            log_test("JSON file storage persistence", False, 
                    f"Failed to retrieve invoices for persistence check: {response.status_code}")
    except Exception as e:
        log_test("JSON file storage persistence", False, f"Error checking persistence: {str(e)}")

def main():
    """Main test execution"""
    print("\n" + "="*80)
    print("اختبار نظام الفواتير المعتمد على الملفات")
    print("FILE-BASED INVOICE SYSTEM TESTING")
    print("="*80)
    print(f"Backend URL: {BACKEND_URL}")
    print(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    # Run invoice system tests
    test_invoice_system()
    
    # Print summary
    print_summary()
    
    # Exit with appropriate code
    if test_results['failed']:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()