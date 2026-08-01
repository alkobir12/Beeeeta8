#!/usr/bin/env python3
"""
Focused Backend Health Check for Operations CEO Embedded Section
Tests:
1. POST /api/ceo/ai-analysis-multi with sample accountIds and question
2. GET /api/operations/analytics/summary sanity check
"""

import requests
import json
import os
from datetime import datetime

# Get backend URL from environment
BACKEND_URL = os.getenv('REACT_APP_BACKEND_URL', 'https://ar-ledger-ssot.preview.emergentagent.com')
BASE_URL = f"{BACKEND_URL}/api"

print("=" * 80)
print("FOCUSED BACKEND HEALTH CHECK: Operations CEO Embedded Section")
print("=" * 80)
print(f"Backend URL: {BASE_URL}")
print(f"Test Time: {datetime.now().isoformat()}")
print("=" * 80)

test_results = []
total_tests = 0
passed_tests = 0

def test_endpoint(name, method, url, data=None, expected_status=200, check_fields=None):
    """Helper function to test an endpoint"""
    global total_tests, passed_tests
    total_tests += 1
    
    try:
        print(f"\n{'='*80}")
        print(f"TEST {total_tests}: {name}")
        print(f"{'='*80}")
        print(f"Method: {method}")
        print(f"URL: {url}")
        if data:
            print(f"Payload: {json.dumps(data, ensure_ascii=False, indent=2)}")
        
        if method == "GET":
            response = requests.get(url, timeout=30)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=30)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        print(f"Status Code: {response.status_code}")
        
        # Check status code
        if response.status_code != expected_status:
            print(f"❌ FAILED: Expected status {expected_status}, got {response.status_code}")
            if response.status_code >= 400:
                print(f"Error Response: {response.text[:500]}")
            test_results.append({
                "test": name,
                "status": "FAILED",
                "reason": f"Status code {response.status_code} != {expected_status}",
                "response": response.text[:500] if response.status_code >= 400 else None
            })
            return False
        
        # Parse JSON response
        try:
            response_data = response.json()
            print(f"Response Preview: {json.dumps(response_data, ensure_ascii=False, indent=2)[:1000]}")
        except Exception as e:
            print(f"❌ FAILED: Could not parse JSON response: {e}")
            print(f"Raw Response: {response.text[:500]}")
            test_results.append({
                "test": name,
                "status": "FAILED",
                "reason": f"JSON parse error: {e}",
                "response": response.text[:500]
            })
            return False
        
        # Check required fields
        if check_fields:
            missing_fields = []
            for field in check_fields:
                if '.' in field:
                    # Nested field check
                    parts = field.split('.')
                    current = response_data
                    for part in parts:
                        if isinstance(current, dict) and part in current:
                            current = current[part]
                        else:
                            missing_fields.append(field)
                            break
                else:
                    if field not in response_data:
                        missing_fields.append(field)
            
            if missing_fields:
                print(f"❌ FAILED: Missing required fields: {missing_fields}")
                test_results.append({
                    "test": name,
                    "status": "FAILED",
                    "reason": f"Missing fields: {missing_fields}",
                    "response": response_data
                })
                return False
        
        print(f"✅ PASSED")
        passed_tests += 1
        test_results.append({
            "test": name,
            "status": "PASSED",
            "response": response_data
        })
        return True
        
    except requests.exceptions.Timeout:
        print(f"❌ FAILED: Request timeout after 30 seconds")
        test_results.append({
            "test": name,
            "status": "FAILED",
            "reason": "Timeout after 30s"
        })
        return False
    except Exception as e:
        print(f"❌ FAILED: Exception: {e}")
        test_results.append({
            "test": name,
            "status": "FAILED",
            "reason": str(e)
        })
        return False

# ============================================================================
# TEST 1: GET /api/operations/analytics/summary - Sanity Check
# ============================================================================
print("\n" + "="*80)
print("SECTION 1: Operations Analytics Summary - Sanity Recheck")
print("="*80)

test_endpoint(
    name="GET /api/operations/analytics/summary",
    method="GET",
    url=f"{BASE_URL}/operations/analytics/summary",
    expected_status=200,
    check_fields=["today", "week", "month"]
)

# ============================================================================
# TEST 2: POST /api/ceo/ai-analysis-multi - With Sample Account IDs
# ============================================================================
print("\n" + "="*80)
print("SECTION 2: CEO AI Analysis Multi - With Sample Accounts")
print("="*80)

# First, get active accounts to use as sample
print("\nFetching active accounts for testing...")
try:
    accounts_response = requests.get(f"{BASE_URL}/biz-accounts", timeout=10)
    if accounts_response.status_code == 200:
        accounts = accounts_response.json()
        if isinstance(accounts, list) and len(accounts) > 0:
            # Use first 2-3 accounts as sample
            sample_account_ids = [acc.get('id') for acc in accounts[:3] if acc.get('id')]
            print(f"Found {len(accounts)} accounts, using {len(sample_account_ids)} for testing")
            print(f"Sample Account IDs: {sample_account_ids}")
        else:
            print("No accounts found, will let endpoint auto-pick active accounts")
            sample_account_ids = []
    else:
        print(f"Could not fetch accounts (status {accounts_response.status_code}), will let endpoint auto-pick")
        sample_account_ids = []
except Exception as e:
    print(f"Error fetching accounts: {e}, will let endpoint auto-pick")
    sample_account_ids = []

# Test with sample accounts and a question
test_payload = {
    "accountIds": sample_account_ids,  # Empty list will auto-pick active accounts
    "question": "ما هي أفضل الفروع أداءً من حيث الربحية؟",
    "days": 30
}

test_endpoint(
    name="POST /api/ceo/ai-analysis-multi with sample accounts",
    method="POST",
    url=f"{BASE_URL}/ceo/ai-analysis-multi",
    data=test_payload,
    expected_status=200,
    check_fields=["accounts", "totals"]
)

# Test with empty accountIds (auto-pick)
print("\n" + "-"*80)
print("Testing with empty accountIds (auto-pick active accounts)")
print("-"*80)

test_payload_auto = {
    "accountIds": [],
    "question": "كيف يمكن تحسين الربحية؟",
    "days": 30
}

test_endpoint(
    name="POST /api/ceo/ai-analysis-multi with auto-pick accounts",
    method="POST",
    url=f"{BASE_URL}/ceo/ai-analysis-multi",
    data=test_payload_auto,
    expected_status=200,
    check_fields=["accounts", "totals"]
)

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "="*80)
print("TEST SUMMARY")
print("="*80)
print(f"Total Tests: {total_tests}")
print(f"Passed: {passed_tests}")
print(f"Failed: {total_tests - passed_tests}")
print(f"Success Rate: {(passed_tests/total_tests*100):.1f}%")
print("="*80)

# Detailed results
print("\nDETAILED RESULTS:")
print("-"*80)
for i, result in enumerate(test_results, 1):
    status_icon = "✅" if result["status"] == "PASSED" else "❌"
    print(f"{i}. {status_icon} {result['test']}")
    if result["status"] == "FAILED":
        print(f"   Reason: {result.get('reason', 'Unknown')}")

print("\n" + "="*80)
print("FOCUSED BACKEND HEALTH CHECK COMPLETE")
print("="*80)

# Exit with appropriate code
exit(0 if passed_tests == total_tests else 1)
