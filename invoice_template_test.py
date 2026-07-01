#!/usr/bin/env python3
"""
Backend smoke test for new invoice template APIs
Testing the 4 specific endpoints requested in the review.
"""

import requests
import json
import sys
import time
from datetime import datetime

# Use the production backend URL from frontend .env
BASE_URL = "https://erp-compliance-check.preview.emergentagent.com/api"

def log_test(test_name, status, details=""):
    """Log test results with timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    status_icon = "✅" if status == "PASS" else "❌"
    print(f"[{timestamp}] {status_icon} {test_name}")
    if details:
        print(f"    {details}")

def test_invoice_template_import():
    """Test 1: POST /api/invoice-templates/import-url with Excel URL"""
    print("\n=== TEST 1: Invoice Template Import from URL ===")
    
    url = f"{BASE_URL}/invoice-templates/import-url"
    excel_url = "https://customer-assets.emergentagent.com/job_autoworkshopai/artifacts/l3knvrsj_%D9%86%D9%85%D9%88%D8%B0%D8%AC%20%D8%A7.xlsx"
    
    payload = {"url": excel_url}
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            
            # Check required fields
            required_fields = ['id', 'format', 'fields', 'preview']
            missing_fields = [field for field in required_fields if field not in data]
            
            if missing_fields:
                log_test("Invoice Template Import", "FAIL", f"Missing fields: {missing_fields}")
                return None
            
            if data.get('format') != 'xlsx':
                log_test("Invoice Template Import", "FAIL", f"Expected format 'xlsx', got '{data.get('format')}'")
                return None
            
            log_test("Invoice Template Import", "PASS", 
                    f"ID: {data['id']}, Format: {data['format']}, Fields: {len(data.get('fields', []))}, Preview rows: {len(data.get('preview', []))}")
            return data['id']
        else:
            log_test("Invoice Template Import", "FAIL", f"Status: {response.status_code}, Response: {response.text}")
            return None
            
    except Exception as e:
        log_test("Invoice Template Import", "FAIL", f"Exception: {str(e)}")
        return None

def test_list_templates(expected_template_id=None):
    """Test 2: GET /api/invoice-templates should include imported template"""
    print("\n=== TEST 2: List Invoice Templates ===")
    
    url = f"{BASE_URL}/invoice-templates"
    
    try:
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            templates = response.json()
            
            if not isinstance(templates, list):
                log_test("List Templates", "FAIL", f"Expected list, got {type(templates)}")
                return False
            
            if expected_template_id:
                template_ids = [t.get('id') for t in templates]
                if expected_template_id in template_ids:
                    log_test("List Templates", "PASS", f"Found imported template {expected_template_id} in list of {len(templates)} templates")
                else:
                    log_test("List Templates", "FAIL", f"Imported template {expected_template_id} not found in list")
                    return False
            else:
                log_test("List Templates", "PASS", f"Retrieved {len(templates)} templates")
            
            return True
        else:
            log_test("List Templates", "FAIL", f"Status: {response.status_code}, Response: {response.text}")
            return False
            
    except Exception as e:
        log_test("List Templates", "FAIL", f"Exception: {str(e)}")
        return False

def test_make_default_template(template_id):
    """Test 3: POST /api/invoice-templates/{id}/make-default then GET to verify isDefault true"""
    print("\n=== TEST 3: Make Template Default ===")
    
    if not template_id:
        log_test("Make Default Template", "FAIL", "No template ID provided")
        return False
    
    # Step 3a: Make template default
    url = f"{BASE_URL}/invoice-templates/{template_id}/make-default"
    
    try:
        response = requests.post(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('isDefault') == True:
                log_test("Make Default Template - POST", "PASS", f"Template {template_id} set as default")
            else:
                log_test("Make Default Template - POST", "FAIL", f"isDefault not set to true: {data.get('isDefault')}")
                return False
        else:
            log_test("Make Default Template - POST", "FAIL", f"Status: {response.status_code}, Response: {response.text}")
            return False
            
    except Exception as e:
        log_test("Make Default Template - POST", "FAIL", f"Exception: {str(e)}")
        return False
    
    # Step 3b: Verify by getting the template
    url = f"{BASE_URL}/invoice-templates"
    
    try:
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            templates = response.json()
            target_template = next((t for t in templates if t.get('id') == template_id), None)
            
            if target_template and target_template.get('isDefault') == True:
                log_test("Make Default Template - GET Verify", "PASS", f"Template {template_id} confirmed as default")
                return True
            else:
                log_test("Make Default Template - GET Verify", "FAIL", f"Template not found or isDefault not true")
                return False
        else:
            log_test("Make Default Template - GET Verify", "FAIL", f"Status: {response.status_code}")
            return False
            
    except Exception as e:
        log_test("Make Default Template - GET Verify", "FAIL", f"Exception: {str(e)}")
        return False

def test_print_invoice_xlsx(template_id):
    """Test 4: POST /api/print/invoice-xlsx with templateId and sample data"""
    print("\n=== TEST 4: Print Invoice XLSX ===")
    
    if not template_id:
        log_test("Print Invoice XLSX", "FAIL", "No template ID provided")
        return False
    
    url = f"{BASE_URL}/print/invoice-xlsx"
    
    # Sample invoice data
    sample_data = {
        "templateId": template_id,
        "invoiceNumber": "INV-TEST-001",
        "customerName": "عميل تجريبي",
        "customerPhone": "+966501234567",
        "vehiclePlate": "ABC-123",
        "vehicleBrand": "تويوتا",
        "vehicleModel": "كامري",
        "items": [
            {
                "name": "تغيير زيت المحرك",
                "quantity": 1,
                "price": 150.0,
                "total": 150.0
            },
            {
                "name": "فلتر هواء",
                "quantity": 1,
                "price": 80.0,
                "total": 80.0
            }
        ],
        "subtotal": 230.0,
        "tax": 34.5,
        "total": 264.5,
        "date": datetime.now().isoformat()
    }
    
    try:
        response = requests.post(url, json=sample_data, timeout=30)
        
        if response.status_code == 200:
            content_type = response.headers.get('content-type', '').lower()
            
            # Check if content-type is xlsx
            if 'xlsx' in content_type or 'spreadsheet' in content_type or 'excel' in content_type:
                log_test("Print Invoice XLSX", "PASS", 
                        f"Status: 200, Content-Type: {content_type}, Content-Length: {len(response.content)} bytes")
                return True
            else:
                log_test("Print Invoice XLSX", "FAIL", 
                        f"Expected XLSX content-type, got: {content_type}")
                return False
        else:
            log_test("Print Invoice XLSX", "FAIL", f"Status: {response.status_code}, Response: {response.text}")
            return False
            
    except Exception as e:
        log_test("Print Invoice XLSX", "FAIL", f"Exception: {str(e)}")
        return False

def main():
    """Run all invoice template API tests"""
    print("🧪 BACKEND SMOKE TEST: Invoice Template APIs")
    print("=" * 60)
    
    start_time = time.time()
    
    # Test 1: Import template from URL
    template_id = test_invoice_template_import()
    
    # Test 2: List templates (verify import)
    list_success = test_list_templates(template_id)
    
    # Test 3: Make template default
    default_success = False
    if template_id:
        default_success = test_make_default_template(template_id)
    
    # Test 4: Print invoice XLSX
    print_success = False
    if template_id:
        print_success = test_print_invoice_xlsx(template_id)
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    
    tests = [
        ("Import Template from URL", template_id is not None),
        ("List Templates", list_success),
        ("Make Template Default", default_success),
        ("Print Invoice XLSX", print_success)
    ]
    
    passed = sum(1 for _, success in tests if success)
    total = len(tests)
    
    for test_name, success in tests:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\n🎯 RESULT: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if template_id:
        print(f"📋 Imported Template ID: {template_id}")
    
    elapsed = time.time() - start_time
    print(f"⏱️  Total time: {elapsed:.2f}s")
    
    # Exit with appropriate code
    sys.exit(0 if passed == total else 1)

if __name__ == "__main__":
    main()