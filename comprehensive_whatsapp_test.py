#!/usr/bin/env python3
"""
Comprehensive Backend Testing - Workshop Management System
Testing all 5 sections as per review request:
1. WhatsApp APIs
2. Approvals System
3. Document Management
4. Settings & Menu
5. Analytics
"""

import requests
import json
from datetime import datetime

# Backend URL from frontend/.env
BASE_URL = "https://fabrication-guard.preview.emergentagent.com/api"

# Test results tracking
test_results = {
    "passed": [],
    "failed": [],
    "warnings": []
}

def log_test(section, test_name, passed, details=""):
    """Log test result"""
    result = f"[{section}] {test_name}"
    if passed:
        test_results["passed"].append(result)
        print(f"✅ {result}")
    else:
        test_results["failed"].append(result)
        print(f"❌ {result}")
    if details:
        print(f"   {details}")

def check_no_id_fields(data, path=""):
    """Recursively check for _id fields in response"""
    if isinstance(data, dict):
        if '_id' in data:
            return False, f"Found _id at {path}"
        for key, value in data.items():
            result, msg = check_no_id_fields(value, f"{path}.{key}")
            if not result:
                return result, msg
    elif isinstance(data, list):
        for i, item in enumerate(data):
            result, msg = check_no_id_fields(item, f"{path}[{i}]")
            if not result:
                return result, msg
    return True, ""

def check_iso_dates(data):
    """Check if dates are in ISO format"""
    date_fields = ['createdAt', 'updatedAt', 'expiresAt', 'respondedAt', 'date', 'entryDate', 'lastVisit']
    issues = []
    
    def check_dict(d, path=""):
        for key, value in d.items():
            if key in date_fields and value is not None:
                if isinstance(value, str):
                    try:
                        datetime.fromisoformat(value.replace('Z', '+00:00'))
                    except:
                        issues.append(f"{path}.{key}: {value}")
                elif isinstance(value, dict):
                    check_dict(value, f"{path}.{key}")
            elif isinstance(value, dict):
                check_dict(value, f"{path}.{key}")
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        check_dict(item, f"{path}.{key}[{i}]")
    
    if isinstance(data, dict):
        check_dict(data)
    elif isinstance(data, list):
        for i, item in enumerate(data):
            if isinstance(item, dict):
                check_dict(item, f"[{i}]")
    
    return len(issues) == 0, issues

print("=" * 80)
print("COMPREHENSIVE BACKEND TESTING - Workshop Management System")
print("=" * 80)
print()

# ============================================================================
# SECTION 1: WHATSAPP APIs (NEW)
# ============================================================================
print("\n" + "=" * 80)
print("SECTION 1: WHATSAPP APIs")
print("=" * 80)

# Test 1.1: GET /api/whatsapp/status
print("\n[Test 1.1] GET /api/whatsapp/status")
try:
    response = requests.get(f"{BASE_URL}/whatsapp/status", timeout=10)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        # Verify expected fields
        has_initialized = 'initialized' in data
        has_delivery = 'delivery_method' in data
        
        if has_initialized and data['initialized'] and has_delivery:
            log_test("WhatsApp", "GET /api/whatsapp/status", True, 
                    f"initialized={data['initialized']}, delivery_method={data['delivery_method']}")
        else:
            log_test("WhatsApp", "GET /api/whatsapp/status", False, 
                    f"Missing expected fields or not initialized")
    else:
        log_test("WhatsApp", "GET /api/whatsapp/status", False, 
                f"Expected 200, got {response.status_code}")
except Exception as e:
    log_test("WhatsApp", "GET /api/whatsapp/status", False, str(e))

# Test 1.2: POST /api/whatsapp/send-document
print("\n[Test 1.2] POST /api/whatsapp/send-document")
try:
    payload = {
        "phone": "0501234567",
        "customerName": "أحمد",
        "documentType": "invoice",
        "vehiclePlate": "ABC-123",
        "trackingLink": "https://test.com"
    }
    response = requests.post(f"{BASE_URL}/whatsapp/send-document", 
                            json=payload, timeout=10)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        # Check for success field
        if data.get('success'):
            log_test("WhatsApp", "POST /api/whatsapp/send-document", True,
                    f"Document sent successfully, delivery_method={data.get('delivery_method')}")
        else:
            log_test("WhatsApp", "POST /api/whatsapp/send-document", False,
                    "success=False in response")
    else:
        log_test("WhatsApp", "POST /api/whatsapp/send-document", False,
                f"Expected 200, got {response.status_code}: {response.text}")
except Exception as e:
    log_test("WhatsApp", "POST /api/whatsapp/send-document", False, str(e))

# Test 1.3: GET /api/whatsapp/messages
print("\n[Test 1.3] GET /api/whatsapp/messages")
try:
    response = requests.get(f"{BASE_URL}/whatsapp/messages", timeout=10)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)[:500]}...")
        
        # Verify structure
        if 'messages' in data and 'count' in data:
            log_test("WhatsApp", "GET /api/whatsapp/messages", True,
                    f"Retrieved {data['count']} messages")
        else:
            log_test("WhatsApp", "GET /api/whatsapp/messages", False,
                    "Missing 'messages' or 'count' field")
    else:
        log_test("WhatsApp", "GET /api/whatsapp/messages", False,
                f"Expected 200, got {response.status_code}")
except Exception as e:
    log_test("WhatsApp", "GET /api/whatsapp/messages", False, str(e))

# Test 1.4: POST /api/whatsapp/send-approval
print("\n[Test 1.4] POST /api/whatsapp/send-approval")
try:
    payload = {
        "phone": "0501234567",
        "customerName": "أحمد",
        "title": "طلب اعتماد",
        "amount": 500,
        "approvalLink": "https://test.com/approval/ABC"
    }
    response = requests.post(f"{BASE_URL}/whatsapp/send-approval",
                            json=payload, timeout=10)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        if data.get('success'):
            log_test("WhatsApp", "POST /api/whatsapp/send-approval", True,
                    f"Approval sent successfully")
        else:
            log_test("WhatsApp", "POST /api/whatsapp/send-approval", False,
                    "success=False in response")
    else:
        log_test("WhatsApp", "POST /api/whatsapp/send-approval", False,
                f"Expected 200, got {response.status_code}: {response.text}")
except Exception as e:
    log_test("WhatsApp", "POST /api/whatsapp/send-approval", False, str(e))

# ============================================================================
# SECTION 2: APPROVALS SYSTEM
# ============================================================================
print("\n" + "=" * 80)
print("SECTION 2: APPROVALS SYSTEM")
print("=" * 80)

# Test 2.1: POST /api/approvals
print("\n[Test 2.1] POST /api/approvals")
approval_token = None
try:
    payload = {
        "vehicleId": "test-vehicle-001",
        "customerId": "test-customer-001",
        "title": "طلب اعتماد اختبار",
        "amount": 500
    }
    response = requests.post(f"{BASE_URL}/approvals", json=payload, timeout=10)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        # Check for token and expiresAt
        if 'token' in data and 'expiresAt' in data:
            approval_token = data['token']
            
            # Verify no _id fields
            no_id, msg = check_no_id_fields(data)
            if not no_id:
                test_results["warnings"].append(f"[Approvals] POST /api/approvals: {msg}")
            
            # Verify ISO date
            iso_ok, issues = check_iso_dates(data)
            if not iso_ok:
                test_results["warnings"].append(f"[Approvals] POST /api/approvals: Date format issues: {issues}")
            
            log_test("Approvals", "POST /api/approvals", True,
                    f"Created approval with token={approval_token}")
        else:
            log_test("Approvals", "POST /api/approvals", False,
                    "Missing token or expiresAt field")
    else:
        log_test("Approvals", "POST /api/approvals", False,
                f"Expected 200, got {response.status_code}")
except Exception as e:
    log_test("Approvals", "POST /api/approvals", False, str(e))

# Test 2.2: GET /api/approvals
print("\n[Test 2.2] GET /api/approvals")
try:
    response = requests.get(f"{BASE_URL}/approvals", timeout=10)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Response: Retrieved {len(data)} approvals")
        
        if isinstance(data, list):
            # Check first item if exists
            if len(data) > 0:
                no_id, msg = check_no_id_fields(data)
                if not no_id:
                    test_results["warnings"].append(f"[Approvals] GET /api/approvals: {msg}")
                
                iso_ok, issues = check_iso_dates(data)
                if not iso_ok:
                    test_results["warnings"].append(f"[Approvals] GET /api/approvals: Date issues: {issues}")
            
            log_test("Approvals", "GET /api/approvals", True,
                    f"Retrieved {len(data)} approvals")
        else:
            log_test("Approvals", "GET /api/approvals", False,
                    "Expected array response")
    else:
        log_test("Approvals", "GET /api/approvals", False,
                f"Expected 200, got {response.status_code}")
except Exception as e:
    log_test("Approvals", "GET /api/approvals", False, str(e))

# Test 2.3: GET /api/approvals/public/{token}
if approval_token:
    print(f"\n[Test 2.3] GET /api/approvals/public/{approval_token}")
    try:
        response = requests.get(f"{BASE_URL}/approvals/public/{approval_token}", timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
            
            no_id, msg = check_no_id_fields(data)
            if not no_id:
                test_results["warnings"].append(f"[Approvals] GET public token: {msg}")
            
            log_test("Approvals", "GET /api/approvals/public/{token}", True,
                    "Public access working")
        else:
            log_test("Approvals", "GET /api/approvals/public/{token}", False,
                    f"Expected 200, got {response.status_code}")
    except Exception as e:
        log_test("Approvals", "GET /api/approvals/public/{token}", False, str(e))

# Test 2.4: POST /api/notifications/prepare
print("\n[Test 2.4] POST /api/notifications/prepare")
try:
    payload = {
        "type": "approval",
        "phone": "0501234567",
        "link": "https://test.com"
    }
    response = requests.post(f"{BASE_URL}/notifications/prepare",
                            json=payload, timeout=10)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        # Check phone normalization
        if 'phone' in data:
            normalized_phone = data['phone']
            # Should be 966501234567 (not +966966...)
            if normalized_phone.startswith('966') and not normalized_phone.startswith('966966'):
                log_test("Approvals", "POST /api/notifications/prepare", True,
                        f"Phone normalized correctly: {normalized_phone}")
            else:
                log_test("Approvals", "POST /api/notifications/prepare", False,
                        f"Phone normalization issue: {normalized_phone}")
        else:
            log_test("Approvals", "POST /api/notifications/prepare", False,
                    "Missing phone field in response")
    else:
        log_test("Approvals", "POST /api/notifications/prepare", False,
                f"Expected 200, got {response.status_code}")
except Exception as e:
    log_test("Approvals", "POST /api/notifications/prepare", False, str(e))

# ============================================================================
# SECTION 3: DOCUMENT MANAGEMENT
# ============================================================================
print("\n" + "=" * 80)
print("SECTION 3: DOCUMENT MANAGEMENT")
print("=" * 80)

# Test 3.1: GET /api/diagnosis-cases
print("\n[Test 3.1] GET /api/diagnosis-cases")
try:
    response = requests.get(f"{BASE_URL}/diagnosis-cases", timeout=10)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Response: Retrieved {len(data)} diagnosis cases")
        
        if isinstance(data, list):
            no_id, msg = check_no_id_fields(data)
            if not no_id:
                test_results["warnings"].append(f"[Documents] GET diagnosis-cases: {msg}")
            
            log_test("Documents", "GET /api/diagnosis-cases", True,
                    f"Retrieved {len(data)} cases")
        else:
            log_test("Documents", "GET /api/diagnosis-cases", False,
                    "Expected array response")
    else:
        log_test("Documents", "GET /api/diagnosis-cases", False,
                f"Expected 200, got {response.status_code}")
except Exception as e:
    log_test("Documents", "GET /api/diagnosis-cases", False, str(e))

# Test 3.2: GET /api/invoices
print("\n[Test 3.2] GET /api/invoices")
try:
    response = requests.get(f"{BASE_URL}/invoices", timeout=10)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Response: Retrieved {len(data)} invoices")
        
        if isinstance(data, list):
            no_id, msg = check_no_id_fields(data)
            if not no_id:
                test_results["warnings"].append(f"[Documents] GET invoices: {msg}")
            
            log_test("Documents", "GET /api/invoices", True,
                    f"Retrieved {len(data)} invoices")
        else:
            log_test("Documents", "GET /api/invoices", False,
                    "Expected array response")
    else:
        log_test("Documents", "GET /api/invoices", False,
                f"Expected 200, got {response.status_code}")
except Exception as e:
    log_test("Documents", "GET /api/invoices", False, str(e))

# Test 3.3: GET /api/quotes
print("\n[Test 3.3] GET /api/quotes")
try:
    response = requests.get(f"{BASE_URL}/quotes", timeout=10)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Response: Retrieved {len(data)} quotes")
        
        if isinstance(data, list):
            no_id, msg = check_no_id_fields(data)
            if not no_id:
                test_results["warnings"].append(f"[Documents] GET quotes: {msg}")
            
            log_test("Documents", "GET /api/quotes", True,
                    f"Retrieved {len(data)} quotes")
        else:
            log_test("Documents", "GET /api/quotes", False,
                    "Expected array response")
    else:
        log_test("Documents", "GET /api/quotes", False,
                f"Expected 200, got {response.status_code}")
except Exception as e:
    log_test("Documents", "GET /api/quotes", False, str(e))

# Test 3.4: GET /api/customer-receipts
print("\n[Test 3.4] GET /api/customer-receipts")
try:
    response = requests.get(f"{BASE_URL}/customer-receipts", timeout=10)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Response: Retrieved {len(data)} customer receipts")
        
        if isinstance(data, list):
            no_id, msg = check_no_id_fields(data)
            if not no_id:
                test_results["warnings"].append(f"[Documents] GET customer-receipts: {msg}")
            
            log_test("Documents", "GET /api/customer-receipts", True,
                    f"Retrieved {len(data)} receipts")
        else:
            log_test("Documents", "GET /api/customer-receipts", False,
                    "Expected array response")
    else:
        log_test("Documents", "GET /api/customer-receipts", False,
                f"Expected 200, got {response.status_code}")
except Exception as e:
    log_test("Documents", "GET /api/customer-receipts", False, str(e))

# Test 3.5: POST /api/print/render with Arabic data
print("\n[Test 3.5] POST /api/print/render with Arabic data")
try:
    payload = {
        "CUSTOMER_NAME": "أحمد الراشد",
        "VEHICLE_PLATE": "ABC-123",
        "TOTAL": 1500.50,
        "ITEMS_ROWS": "<tr><td>خدمة صيانة</td><td>500</td></tr>"
    }
    response = requests.post(f"{BASE_URL}/print/render",
                            json=payload, timeout=10)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        html = response.text
        print(f"Response length: {len(html)} chars")
        
        # Check if Arabic content is preserved
        if "أحمد الراشد" in html and "1500.50" in html:
            log_test("Documents", "POST /api/print/render", True,
                    "Arabic content preserved in HTML")
        else:
            log_test("Documents", "POST /api/print/render", False,
                    "Arabic content not found in HTML")
    else:
        log_test("Documents", "POST /api/print/render", False,
                f"Expected 200, got {response.status_code}")
except Exception as e:
    log_test("Documents", "POST /api/print/render", False, str(e))

# Test 3.6: POST /api/print/resolve-template
print("\n[Test 3.6] POST /api/print/resolve-template")
try:
    payload = {"override_type": "invoice"}
    response = requests.post(f"{BASE_URL}/print/resolve-template",
                            json=payload, timeout=10)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)[:300]}...")
        
        if 'template' in data or 'content' in data:
            log_test("Documents", "POST /api/print/resolve-template", True,
                    "Template resolved successfully")
        else:
            log_test("Documents", "POST /api/print/resolve-template", False,
                    "Missing template/content in response")
    else:
        log_test("Documents", "POST /api/print/resolve-template", False,
                f"Expected 200, got {response.status_code}")
except Exception as e:
    log_test("Documents", "POST /api/print/resolve-template", False, str(e))

# ============================================================================
# SECTION 4: SETTINGS & MENU
# ============================================================================
print("\n" + "=" * 80)
print("SECTION 4: SETTINGS & MENU")
print("=" * 80)

# Test 4.1: GET /api/settings - verify menuConfig
print("\n[Test 4.1] GET /api/settings - verify menuConfig")
try:
    response = requests.get(f"{BASE_URL}/settings", timeout=10)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Response keys: {list(data.keys())}")
        
        # Check for menuConfig
        if 'menuConfig' in data:
            menu_config = data['menuConfig']
            items = menu_config.get('items', [])
            print(f"Menu items count: {len(items)}")
            
            # Look for CEO group with Knowledge inside
            ceo_group_found = False
            knowledge_found = False
            
            for item in items:
                if item.get('group') and 'ceo' in item.get('path', '').lower():
                    ceo_group_found = True
                    print(f"Found CEO group: {item.get('label')}")
                    
                    # Check children
                    children = item.get('children', [])
                    for child in children:
                        if 'knowledge' in child.get('path', '').lower():
                            knowledge_found = True
                            print(f"Found Knowledge in CEO group: {child.get('label')}")
            
            if ceo_group_found and knowledge_found:
                log_test("Settings", "GET /api/settings - menuConfig", True,
                        "CEO group with Knowledge found")
            else:
                log_test("Settings", "GET /api/settings - menuConfig", False,
                        f"CEO group found: {ceo_group_found}, Knowledge found: {knowledge_found}")
        else:
            log_test("Settings", "GET /api/settings - menuConfig", False,
                    "menuConfig not found in settings")
    else:
        log_test("Settings", "GET /api/settings - menuConfig", False,
                f"Expected 200, got {response.status_code}")
except Exception as e:
    log_test("Settings", "GET /api/settings - menuConfig", False, str(e))

# ============================================================================
# SECTION 5: ANALYTICS
# ============================================================================
print("\n" + "=" * 80)
print("SECTION 5: ANALYTICS")
print("=" * 80)

# Test 5.1: GET /api/vehicles - count total
print("\n[Test 5.1] GET /api/vehicles - count total")
try:
    response = requests.get(f"{BASE_URL}/vehicles", timeout=10)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        total_count = len(data)
        print(f"Total vehicles: {total_count}")
        
        # Check for paymentMethod field in vehicles
        has_payment_method = False
        if total_count > 0 and isinstance(data, list):
            # Check if any vehicle has paymentMethod
            for vehicle in data[:5]:  # Check first 5
                if 'paymentMethod' in vehicle:
                    has_payment_method = True
                    break
        
        log_test("Analytics", "GET /api/vehicles - total count", True,
                f"Total: {total_count}, paymentMethod field present: {has_payment_method}")
    else:
        log_test("Analytics", "GET /api/vehicles - total count", False,
                f"Expected 200, got {response.status_code}")
except Exception as e:
    log_test("Analytics", "GET /api/vehicles - total count", False, str(e))

# Test 5.2: GET /api/vehicles?status=awaiting_parts
print("\n[Test 5.2] GET /api/vehicles?status=awaiting_parts")
try:
    response = requests.get(f"{BASE_URL}/vehicles?status=awaiting_parts", timeout=10)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        count = len(data)
        print(f"Vehicles awaiting parts: {count}")
        
        log_test("Analytics", "GET /api/vehicles?status=awaiting_parts", True,
                f"Count: {count}")
    else:
        log_test("Analytics", "GET /api/vehicles?status=awaiting_parts", False,
                f"Expected 200, got {response.status_code}")
except Exception as e:
    log_test("Analytics", "GET /api/vehicles?status=awaiting_parts", False, str(e))

# Test 5.3: GET /api/vehicles?status=awaiting_approval
print("\n[Test 5.3] GET /api/vehicles?status=awaiting_approval")
try:
    response = requests.get(f"{BASE_URL}/vehicles?status=awaiting_approval", timeout=10)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        count = len(data)
        print(f"Vehicles awaiting approval: {count}")
        
        log_test("Analytics", "GET /api/vehicles?status=awaiting_approval", True,
                f"Count: {count}")
    else:
        log_test("Analytics", "GET /api/vehicles?status=awaiting_approval", False,
                f"Expected 200, got {response.status_code}")
except Exception as e:
    log_test("Analytics", "GET /api/vehicles?status=awaiting_approval", False, str(e))

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 80)
print("TEST SUMMARY")
print("=" * 80)

print(f"\n✅ PASSED: {len(test_results['passed'])}")
for test in test_results['passed']:
    print(f"   {test}")

if test_results['failed']:
    print(f"\n❌ FAILED: {len(test_results['failed'])}")
    for test in test_results['failed']:
        print(f"   {test}")

if test_results['warnings']:
    print(f"\n⚠️  WARNINGS: {len(test_results['warnings'])}")
    for warning in test_results['warnings']:
        print(f"   {warning}")

total_tests = len(test_results['passed']) + len(test_results['failed'])
pass_rate = (len(test_results['passed']) / total_tests * 100) if total_tests > 0 else 0

print(f"\n{'=' * 80}")
print(f"OVERALL: {len(test_results['passed'])}/{total_tests} tests passed ({pass_rate:.1f}%)")
print(f"{'=' * 80}")
