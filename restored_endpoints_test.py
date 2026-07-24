#!/usr/bin/env python3
"""
Focused test for restored backend endpoints as requested in review.
Testing: diagnosis-cases, customer-receipts, quotes, seed/print-templates, print/resolve-template, print/render
"""

import requests
import json
import sys
from datetime import datetime

# Backend URL from frontend/.env
BASE_URL = "https://stamp-approval-flow.preview.emergentagent.com/api"

def test_endpoint(method, endpoint, data=None, expected_status=200, description=""):
    """Test a single endpoint and return results"""
    url = f"{BASE_URL}{endpoint}"
    
    try:
        print(f"\n🔍 Testing {method} {endpoint}")
        print(f"   Description: {description}")
        print(f"   URL: {url}")
        
        if method == "GET":
            response = requests.get(url, timeout=30)
        elif method == "POST":
            headers = {"Content-Type": "application/json"}
            response = requests.post(url, json=data, headers=headers, timeout=30)
        else:
            print(f"❌ Unsupported method: {method}")
            return False
            
        print(f"   Status: {response.status_code}")
        
        if response.status_code == expected_status:
            try:
                json_response = response.json()
                print(f"   ✅ SUCCESS: Got expected {expected_status} status")
                
                # Additional validation based on endpoint
                if endpoint == "/diagnosis-cases" and isinstance(json_response, list):
                    print(f"   📊 Response: Array with {len(json_response)} items")
                elif endpoint == "/customer-receipts" and isinstance(json_response, list):
                    print(f"   📊 Response: Array with {len(json_response)} items")
                elif endpoint == "/quotes" and isinstance(json_response, list):
                    print(f"   📊 Response: Array with {len(json_response)} items")
                elif endpoint == "/seed/print-templates":
                    if "added" in json_response:
                        print(f"   📊 Response: {json_response}")
                    else:
                        print(f"   ⚠️  Response missing 'added' field: {json_response}")
                elif endpoint == "/print/resolve-template":
                    if "template" in json_response or "type" in json_response:
                        print(f"   📊 Response contains template object")
                    else:
                        print(f"   ⚠️  Response missing template object: {json_response}")
                elif endpoint == "/print/render":
                    if isinstance(json_response, dict) and ("html" in json_response or len(str(json_response)) > 100):
                        print(f"   📊 Response contains HTML content ({len(str(json_response))} chars)")
                    else:
                        print(f"   ⚠️  Response doesn't look like HTML: {str(json_response)[:200]}...")
                else:
                    print(f"   📊 Response: {str(json_response)[:200]}...")
                    
                return True
                
            except json.JSONDecodeError:
                print(f"   ⚠️  Non-JSON response: {response.text[:200]}...")
                return response.status_code == expected_status
        else:
            print(f"   ❌ FAILED: Expected {expected_status}, got {response.status_code}")
            try:
                error_response = response.json()
                print(f"   Error: {error_response}")
            except:
                print(f"   Error text: {response.text[:200]}...")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ REQUEST ERROR: {e}")
        return False
    except Exception as e:
        print(f"   ❌ UNEXPECTED ERROR: {e}")
        return False

def main():
    """Run all restored endpoint tests"""
    print("🚀 TESTING RESTORED BACKEND ENDPOINTS")
    print("=" * 60)
    
    results = []
    
    # Test 1: GET /api/diagnosis-cases (expect 200 array)
    success = test_endpoint(
        "GET", 
        "/diagnosis-cases",
        description="Get diagnosis cases array"
    )
    results.append(("GET /api/diagnosis-cases", success))
    
    # Test 2: GET /api/customer-receipts (expect 200 array)  
    success = test_endpoint(
        "GET",
        "/customer-receipts", 
        description="Get customer receipts array"
    )
    results.append(("GET /api/customer-receipts", success))
    
    # Test 3: GET /api/quotes (expect 200 array)
    success = test_endpoint(
        "GET",
        "/quotes",
        description="Get quotes array"
    )
    results.append(("GET /api/quotes", success))
    
    # Test 4: POST /api/seed/print-templates (expect {added:[...] or []})
    success = test_endpoint(
        "POST",
        "/seed/print-templates",
        data={},
        description="Seed print templates"
    )
    results.append(("POST /api/seed/print-templates", success))
    
    # Test 5: POST /api/print/resolve-template with {override_type:'invoice'} (expect 200 with template object)
    success = test_endpoint(
        "POST",
        "/print/resolve-template",
        data={"override_type": "invoice"},
        description="Resolve invoice template"
    )
    results.append(("POST /api/print/resolve-template", success))
    
    # Test 6: POST /api/print/render with Arabic data (expect 200 with html)
    render_data = {
        "override_type": "invoice",
        "data": {
            "CUSTOMER_NAME": "اختبار",
            "ITEMS_ROWS": [
                {"name": "خدمة الصيانة", "quantity": 1, "price": 100.0, "total": 100.0},
                {"name": "قطعة غيار", "quantity": 2, "price": 50.0, "total": 100.0}
            ],
            "TOTAL": 200.0,
            "DATE": datetime.now().strftime("%Y-%m-%d")
        }
    }
    success = test_endpoint(
        "POST",
        "/print/render",
        data=render_data,
        description="Render invoice with Arabic data"
    )
    results.append(("POST /api/print/render", success))
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if success:
            passed += 1
    
    print(f"\n🎯 OVERALL: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("🎉 ALL RESTORED ENDPOINTS WORKING CORRECTLY!")
        return True
    else:
        print("⚠️  SOME ENDPOINTS HAVE ISSUES - SEE DETAILS ABOVE")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)