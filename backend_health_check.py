#!/usr/bin/env python3
"""
Backend Health Check for Operations CEO Embedded Section
Testing: /api/ceo/ai-analysis-multi and /api/operations/analytics/summary
"""

import requests
import json
import sys
from datetime import datetime

# Get backend URL from environment
BACKEND_URL = "https://erp-compliance-check.preview.emergentagent.com/api"

def test_operations_analytics_summary():
    """Test GET /api/operations/analytics/summary endpoint"""
    print("\n" + "="*80)
    print("TEST 1: GET /api/operations/analytics/summary")
    print("="*80)
    
    try:
        url = f"{BACKEND_URL}/operations/analytics/summary"
        print(f"URL: {url}")
        
        response = requests.get(url, timeout=30)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ SUCCESS: Endpoint is reachable and working")
            print(f"Response keys: {list(data.keys())}")
            
            # Check for expected structure
            if 'today' in data:
                print(f"  - Today data: {data['today']}")
            if 'week' in data:
                print(f"  - Week data: {data['week']}")
            if 'month' in data:
                print(f"  - Month data: {data['month']}")
            
            return True, "Endpoint working correctly"
        else:
            print(f"❌ FAILED: Status {response.status_code}")
            print(f"Response: {response.text[:500]}")
            return False, f"Status {response.status_code}"
            
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return False, str(e)


def test_ceo_ai_analysis_multi():
    """Test POST /api/ceo/ai-analysis-multi endpoint"""
    print("\n" + "="*80)
    print("TEST 2: POST /api/ceo/ai-analysis-multi")
    print("="*80)
    
    try:
        url = f"{BACKEND_URL}/ceo/ai-analysis-multi"
        print(f"URL: {url}")
        
        # Test payload with sample account IDs
        payload = {
            "accountIds": ["test-account-1", "test-account-2"],
            "question": "حلل لي الربحية الشهرية"
        }
        print(f"Payload: {json.dumps(payload, ensure_ascii=False)}")
        
        response = requests.post(url, json=payload, timeout=30)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ SUCCESS: Endpoint is reachable and working")
            print(f"Response keys: {list(data.keys())}")
            
            # Check for expected structure
            if 'totals' in data:
                print(f"  - Totals: {data['totals']}")
            if 'ai' in data:
                print(f"  - AI response present: {bool(data['ai'])}")
            
            return True, "Endpoint working correctly"
        elif response.status_code == 404:
            print(f"❌ FAILED: Endpoint NOT FOUND (404)")
            print(f"This endpoint does not exist in the backend")
            return False, "Endpoint not implemented"
        else:
            print(f"❌ FAILED: Status {response.status_code}")
            print(f"Response: {response.text[:500]}")
            return False, f"Status {response.status_code}"
            
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return False, str(e)


def main():
    print("\n" + "="*80)
    print("BACKEND HEALTH CHECK - Operations CEO Embedded Section")
    print(f"Time: {datetime.now().isoformat()}")
    print("="*80)
    
    results = []
    
    # Test 1: Operations Analytics Summary
    success1, msg1 = test_operations_analytics_summary()
    results.append(("GET /api/operations/analytics/summary", success1, msg1))
    
    # Test 2: CEO AI Analysis Multi
    success2, msg2 = test_ceo_ai_analysis_multi()
    results.append(("POST /api/ceo/ai-analysis-multi", success2, msg2))
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    for endpoint, success, msg in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {endpoint}")
        print(f"       {msg}")
    
    # Exit code
    all_passed = all(r[1] for r in results)
    if all_passed:
        print("\n✅ ALL TESTS PASSED")
        sys.exit(0)
    else:
        print("\n❌ SOME TESTS FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
