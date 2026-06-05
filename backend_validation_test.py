#!/usr/bin/env python3
"""
BACKEND VALIDATION TEST SUITE
Workshop Management System - Comprehensive Backend Endpoint Testing

Test Priorities:
1. CRITICAL ENDPOINTS (Previously showed 404 - verify current status)
2. SIDEBAR & SETTINGS
3. ANALYTICS DATA ENDPOINTS
4. PRINT FLOW VALIDATION
5. USER & AUTH (if implemented)
"""

import requests
import json
import os
from datetime import datetime

# Get backend URL from environment
BACKEND_URL = os.getenv('REACT_APP_BACKEND_URL', 'https://workshop-helper-7.preview.emergentagent.com')
API_BASE = f"{BACKEND_URL}/api"

print(f"🔍 Testing Backend API at: {API_BASE}")
print("=" * 80)

# Test Results Tracking
test_results = {
    "passed": [],
    "failed": [],
    "warnings": []
}

def test_endpoint(name, method, endpoint, expected_status=200, data=None, check_fn=None):
    """Generic test function for API endpoints"""
    url = f"{API_BASE}{endpoint}"
    try:
        if method == "GET":
            response = requests.get(url, timeout=10)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=10)
        elif method == "PUT":
            response = requests.put(url, json=data, timeout=10)
        elif method == "DELETE":
            response = requests.delete(url, timeout=10)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        # Check status code
        if response.status_code != expected_status:
            test_results["failed"].append({
                "name": name,
                "endpoint": endpoint,
                "expected": expected_status,
                "actual": response.status_code,
                "response": response.text[:200]
            })
            print(f"❌ {name}: Expected {expected_status}, got {response.status_code}")
            return False, response
        
        # Run custom check function if provided
        if check_fn:
            try:
                result = check_fn(response)
                if not result:
                    test_results["failed"].append({
                        "name": name,
                        "endpoint": endpoint,
                        "reason": "Custom check failed"
                    })
                    print(f"❌ {name}: Custom check failed")
                    return False, response
            except Exception as e:
                test_results["failed"].append({
                    "name": name,
                    "endpoint": endpoint,
                    "reason": f"Check function error: {str(e)}"
                })
                print(f"❌ {name}: Check function error - {str(e)}")
                return False, response
        
        test_results["passed"].append(name)
        print(f"✅ {name}")
        return True, response
        
    except requests.exceptions.Timeout:
        test_results["failed"].append({
            "name": name,
            "endpoint": endpoint,
            "reason": "Request timeout"
        })
        print(f"❌ {name}: Request timeout")
        return False, None
    except Exception as e:
        test_results["failed"].append({
            "name": name,
            "endpoint": endpoint,
            "reason": str(e)
        })
        print(f"❌ {name}: {str(e)}")
        return False, None

# ============================================================================
# SECTION 1: CRITICAL ENDPOINTS (Previously showed 404)
# ============================================================================
print("\n" + "=" * 80)
print("SECTION 1: CRITICAL ENDPOINTS (Previously showed 404)")
print("=" * 80)

# Test 1.1: GET /api/diagnosis-cases
def check_diagnosis_cases(response):
    data = response.json()
    if not isinstance(data, list):
        print(f"   ⚠️  Expected array, got {type(data)}")
        return False
    print(f"   ℹ️  Found {len(data)} diagnosis cases")
    return True

test_endpoint(
    "GET /api/diagnosis-cases",
    "GET",
    "/diagnosis-cases",
    check_fn=check_diagnosis_cases
)

# Test 1.2: GET /api/customer-receipts
def check_customer_receipts(response):
    data = response.json()
    if not isinstance(data, list):
        print(f"   ⚠️  Expected array, got {type(data)}")
        return False
    print(f"   ℹ️  Found {len(data)} customer receipts")
    return True

test_endpoint(
    "GET /api/customer-receipts",
    "GET",
    "/customer-receipts",
    check_fn=check_customer_receipts
)

# Test 1.3: GET /api/quotes
def check_quotes(response):
    data = response.json()
    if not isinstance(data, list):
        print(f"   ⚠️  Expected array, got {type(data)}")
        return False
    print(f"   ℹ️  Found {len(data)} quotes")
    return True

test_endpoint(
    "GET /api/quotes",
    "GET",
    "/quotes",
    check_fn=check_quotes
)

# Test 1.4: POST /api/seed/print-templates (idempotent)
def check_seed_templates(response):
    data = response.json()
    if "added" not in data:
        print(f"   ⚠️  Expected 'added' field in response")
        return False
    print(f"   ℹ️  Templates added: {data['added']}")
    return True

test_endpoint(
    "POST /api/seed/print-templates",
    "POST",
    "/seed/print-templates",
    check_fn=check_seed_templates
)

# Test 1.5: POST /api/print/resolve-template
def check_resolve_template(response):
    data = response.json()
    if "template" not in data:
        print(f"   ⚠️  Expected 'template' field in response")
        return False
    if data.get("type") != "invoice":
        print(f"   ⚠️  Expected type='invoice', got {data.get('type')}")
        return False
    print(f"   ℹ️  Template resolved: {data.get('template', {}).get('name', 'N/A')}")
    return True

test_endpoint(
    "POST /api/print/resolve-template (invoice)",
    "POST",
    "/print/resolve-template",
    data={"override_type": "invoice"},
    check_fn=check_resolve_template
)

# Test 1.6: POST /api/print/render with Arabic data
def check_render_html(response):
    data = response.json()
    if "html" not in data:
        print(f"   ⚠️  Expected 'html' field in response")
        return False
    html = data["html"]
    if "اختبار" not in html:
        print(f"   ⚠️  Arabic customer name 'اختبار' not found in HTML")
        return False
    if "123.45" not in html:
        print(f"   ⚠️  Total amount '123.45' not found in HTML")
        return False
    print(f"   ℹ️  HTML rendered successfully with Arabic content ({len(html)} chars)")
    return True

test_endpoint(
    "POST /api/print/render (Arabic data)",
    "POST",
    "/print/render",
    data={
        "override_type": "invoice",
        "data": {
            "CUSTOMER_NAME": "اختبار",
            "CUSTOMER_PHONE": "+966501234567",
            "VEHICLE_PLATE": "ABC-1234",
            "VEHICLE_MODEL": "تويوتا كامري",
            "VEHICLE_YEAR": "2020",
            "INVOICE_NO": "INV-TEST-001",
            "SUBTOTAL": "100.00",
            "TAX": "23.45",
            "TOTAL": "123.45",
            "items": [
                {"name": "تغيير زيت", "qty": 1, "price": 50.0, "total": 50.0},
                {"name": "فلتر هواء", "qty": 1, "price": 50.0, "total": 50.0}
            ]
        }
    },
    check_fn=check_render_html
)

# ============================================================================
# SECTION 2: SIDEBAR & SETTINGS
# ============================================================================
print("\n" + "=" * 80)
print("SECTION 2: SIDEBAR & SETTINGS")
print("=" * 80)

# Test 2.1: GET /api/settings - menuConfig structure
def check_settings_menu(response):
    data = response.json()
    if "menuConfig" not in data:
        print(f"   ⚠️  Expected 'menuConfig' field in response")
        return False
    
    menu_config = data["menuConfig"]
    if "items" not in menu_config:
        print(f"   ⚠️  Expected 'items' field in menuConfig")
        return False
    
    items = menu_config["items"]
    if not isinstance(items, list):
        print(f"   ⚠️  Expected items to be a list")
        return False
    
    if len(items) < 10:
        print(f"   ⚠️  Expected at least 10 menu items, got {len(items)}")
        return False
    
    # Check for Arabic labels
    arabic_found = False
    for item in items:
        if "label" in item and any(ord(c) > 1536 for c in item.get("label", "")):
            arabic_found = True
            break
    
    if not arabic_found:
        print(f"   ⚠️  No Arabic labels found in menu items")
        return False
    
    print(f"   ℹ️  Menu config has {len(items)} items with Arabic labels")
    return True

test_endpoint(
    "GET /api/settings (menuConfig validation)",
    "GET",
    "/settings",
    check_fn=check_settings_menu
)

# ============================================================================
# SECTION 3: ANALYTICS DATA ENDPOINTS
# ============================================================================
print("\n" + "=" * 80)
print("SECTION 3: ANALYTICS DATA ENDPOINTS")
print("=" * 80)

# Test 3.1: GET /api/vehicles (all)
def check_vehicles_all(response):
    data = response.json()
    if not isinstance(data, list):
        print(f"   ⚠️  Expected array, got {type(data)}")
        return False
    print(f"   ℹ️  Total vehicles: {len(data)}")
    return True

test_endpoint(
    "GET /api/vehicles (all)",
    "GET",
    "/vehicles",
    check_fn=check_vehicles_all
)

# Test 3.2: GET /api/vehicles?status=abandoned
def check_vehicles_abandoned(response):
    data = response.json()
    if not isinstance(data, list):
        print(f"   ⚠️  Expected array, got {type(data)}")
        return False
    print(f"   ℹ️  Abandoned vehicles: {len(data)}")
    return True

test_endpoint(
    "GET /api/vehicles?status=abandoned",
    "GET",
    "/vehicles?status=abandoned",
    check_fn=check_vehicles_abandoned
)

# Test 3.3: GET /api/vehicles?status=awaiting_parts
def check_vehicles_awaiting_parts(response):
    data = response.json()
    if not isinstance(data, list):
        print(f"   ⚠️  Expected array, got {type(data)}")
        return False
    print(f"   ℹ️  Awaiting parts: {len(data)}")
    return True

test_endpoint(
    "GET /api/vehicles?status=awaiting_parts",
    "GET",
    "/vehicles?status=awaiting_parts",
    check_fn=check_vehicles_awaiting_parts
)

# Test 3.4: GET /api/vehicles?status=awaiting_approval
def check_vehicles_awaiting_approval(response):
    data = response.json()
    if not isinstance(data, list):
        print(f"   ⚠️  Expected array, got {type(data)}")
        return False
    print(f"   ℹ️  Awaiting approval: {len(data)}")
    return True

test_endpoint(
    "GET /api/vehicles?status=awaiting_approval",
    "GET",
    "/vehicles?status=awaiting_approval",
    check_fn=check_vehicles_awaiting_approval
)

# ============================================================================
# SECTION 4: PRINT FLOW VALIDATION
# ============================================================================
print("\n" + "=" * 80)
print("SECTION 4: PRINT FLOW VALIDATION")
print("=" * 80)

# Test 4.1: Create test vehicle
print("\n📝 Creating test vehicle for print flow validation...")
vehicle_data = {
    "plateNumber": f"TEST-{datetime.now().strftime('%H%M%S')}",
    "brand": "تويوتا",
    "model": "كامري",
    "year": 2020,
    "color": "أبيض",
    "customerName": "عميل اختبار",
    "customerPhone": "+966501234567",
    "customerEmail": "test@example.com",
    "services": ["تغيير زيت", "فحص شامل"]
}

success, vehicle_response = test_endpoint(
    "POST /api/vehicles (test vehicle)",
    "POST",
    "/vehicles",
    expected_status=200,
    data=vehicle_data
)

if success and vehicle_response:
    vehicle = vehicle_response.json()
    vehicle_id = vehicle.get("id")
    print(f"   ℹ️  Test vehicle created: {vehicle_id}")
    
    # Test 4.2: Resolve template for diagnosis
    test_endpoint(
        "POST /api/print/resolve-template (diagnosis)",
        "POST",
        "/print/resolve-template",
        data={"override_type": "diagnosis"}
    )
    
    # Test 4.3: Resolve template for quote
    test_endpoint(
        "POST /api/print/resolve-template (quote)",
        "POST",
        "/print/resolve-template",
        data={"override_type": "quote"}
    )
    
    # Test 4.4: Resolve template for receipt
    test_endpoint(
        "POST /api/print/resolve-template (receipt)",
        "POST",
        "/print/resolve-template",
        data={"override_type": "receipt"}
    )
    
    # Test 4.5: Render diagnosis report
    test_endpoint(
        "POST /api/print/render (diagnosis)",
        "POST",
        "/print/render",
        data={
            "override_type": "diagnosis",
            "data": {
                "CUSTOMER_NAME": "عميل اختبار",
                "VEHICLE_PLATE": vehicle.get("plateNumber"),
                "VEHICLE_MODEL": "تويوتا كامري",
                "VEHICLE_YEAR": "2020",
                "DIAGNOSIS_DATE": datetime.now().strftime("%Y-%m-%d"),
                "items": [
                    {"name": "تغيير زيت", "qty": 1, "price": 150.0, "total": 150.0},
                    {"name": "فحص شامل", "qty": 1, "price": 200.0, "total": 200.0}
                ]
            }
        }
    )
    
    # Test 4.6: Render quote
    test_endpoint(
        "POST /api/print/render (quote)",
        "POST",
        "/print/render",
        data={
            "override_type": "quote",
            "data": {
                "CUSTOMER_NAME": "عميل اختبار",
                "VEHICLE_PLATE": vehicle.get("plateNumber"),
                "VEHICLE_MODEL": "تويوتا كامري",
                "VEHICLE_YEAR": "2020",
                "SUBTOTAL": "350.00",
                "DISCOUNT": "0.00",
                "TAX": "52.50",
                "TOTAL": "402.50",
                "items": [
                    {"name": "تغيير زيت", "qty": 1, "price": 150.0, "total": 150.0},
                    {"name": "فحص شامل", "qty": 1, "price": 200.0, "total": 200.0}
                ]
            }
        }
    )

# ============================================================================
# SECTION 5: USER & AUTH (if implemented)
# ============================================================================
print("\n" + "=" * 80)
print("SECTION 5: USER & AUTH (if implemented)")
print("=" * 80)

# Test 5.1: GET /api/users (check if endpoint exists)
def check_users_endpoint(response):
    # Accept both 200 (exists) and 404 (not implemented)
    return True

success, response = test_endpoint(
    "GET /api/users (check existence)",
    "GET",
    "/users",
    expected_status=200
)

if not success:
    print("   ℹ️  /api/users endpoint not implemented (expected)")
    test_results["warnings"].append("GET /api/users endpoint not implemented")

# Test 5.2: POST /api/auth/request-otp (WhatsApp OTP flow)
def check_otp_request(response):
    data = response.json()
    if "token" not in data:
        print(f"   ⚠️  Expected 'token' field in response")
        return False
    if "whatsappDeeplink" not in data:
        print(f"   ⚠️  Expected 'whatsappDeeplink' field in response")
        return False
    print(f"   ℹ️  OTP request successful, token: {data['token'][:20]}...")
    return True

test_endpoint(
    "POST /api/auth/request-otp",
    "POST",
    "/auth/request-otp",
    data={"phone": "+966501234567"},
    check_fn=check_otp_request
)

# ============================================================================
# FINAL SUMMARY
# ============================================================================
print("\n" + "=" * 80)
print("TEST SUMMARY")
print("=" * 80)

total_tests = len(test_results["passed"]) + len(test_results["failed"])
pass_rate = (len(test_results["passed"]) / total_tests * 100) if total_tests > 0 else 0

print(f"\n✅ Passed: {len(test_results['passed'])}/{total_tests} ({pass_rate:.1f}%)")
print(f"❌ Failed: {len(test_results['failed'])}/{total_tests}")
print(f"⚠️  Warnings: {len(test_results['warnings'])}")

if test_results["failed"]:
    print("\n" + "=" * 80)
    print("FAILED TESTS DETAILS")
    print("=" * 80)
    for failure in test_results["failed"]:
        print(f"\n❌ {failure['name']}")
        print(f"   Endpoint: {failure['endpoint']}")
        if "expected" in failure:
            print(f"   Expected: {failure['expected']}, Actual: {failure['actual']}")
        if "reason" in failure:
            print(f"   Reason: {failure['reason']}")
        if "response" in failure:
            print(f"   Response: {failure['response']}")

if test_results["warnings"]:
    print("\n" + "=" * 80)
    print("WARNINGS")
    print("=" * 80)
    for warning in test_results["warnings"]:
        print(f"⚠️  {warning}")

print("\n" + "=" * 80)
print("TEST EXECUTION COMPLETE")
print("=" * 80)

# Exit with appropriate code
exit(0 if len(test_results["failed"]) == 0 else 1)
