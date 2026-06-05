#!/usr/bin/env python3
"""
Backend Readiness Health Ping Test
Testing the specific endpoints requested in the review:
1) GET /api/settings => 200 + JSON
2) GET /api/operations/analytics/summary => 200 + JSON  
3) GET /api/approvals/stream => should establish SSE (just confirm 200 and text/event-stream)
4) POST /api/ceo/ai-analysis-multi with {} or minimal payload => 200 + accounts/totals, ai null if no key
5) GET /api/customers => 200 + array
6) GET /api/customers/{someId}/approvals => if any exists, 200; otherwise 200 empty array
"""

import requests
import json
import time
from datetime import datetime
from typing import Dict, Any, List

# Backend URL from environment
BACKEND_URL = "https://workshop-helper-7.preview.emergentagent.com/api"

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

def log_test(test_name: str, status: str, details: str = "", response_time: float = 0):
    """Log test results with colors"""
    color = Colors.GREEN if status == "PASS" else Colors.RED if status == "FAIL" else Colors.YELLOW
    print(f"{color}[{status}]{Colors.RESET} {test_name}")
    if details:
        print(f"  {details}")
    if response_time > 0:
        print(f"  ⏱️  Response Time: {response_time:.3f}s")
    print()

def test_backend_readiness():
    """Test Backend Readiness Health Ping Endpoints"""
    print(f"\n{Colors.BLUE}{'='*80}")
    print(f"BACKEND READINESS HEALTH PING TEST")
    print(f"فحص جاهزية الخلفية - اختبار صحي")
    print(f"{'='*80}{Colors.RESET}\n")
    
    results = []
    
    # Test 1: GET /api/settings => 200 + JSON
    try:
        start_time = time.time()
        response = requests.get(f"{BACKEND_URL}/settings", timeout=10)
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            try:
                data = response.json()
                log_test(
                    "1) GET /api/settings",
                    "PASS",
                    f"✅ Status: 200, JSON response with keys: {list(data.keys())[:5]}...",
                    response_time
                )
                results.append(("GET /api/settings", True, response_time))
            except json.JSONDecodeError:
                log_test(
                    "1) GET /api/settings",
                    "FAIL",
                    f"❌ Status: 200 but invalid JSON response"
                )
                results.append(("GET /api/settings", False, 0))
        else:
            log_test(
                "1) GET /api/settings",
                "FAIL",
                f"❌ Status: {response.status_code}, Response: {response.text[:200]}"
            )
            results.append(("GET /api/settings", False, 0))
    except Exception as e:
        log_test("1) GET /api/settings", "FAIL", f"❌ Exception: {str(e)}")
        results.append(("GET /api/settings", False, 0))
    
    # Test 2: GET /api/operations/analytics/summary => 200 + JSON
    try:
        start_time = time.time()
        response = requests.get(f"{BACKEND_URL}/operations/analytics/summary", timeout=10)
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            try:
                data = response.json()
                log_test(
                    "2) GET /api/operations/analytics/summary",
                    "PASS",
                    f"✅ Status: 200, JSON response with keys: {list(data.keys())[:5]}...",
                    response_time
                )
                results.append(("GET /api/operations/analytics/summary", True, response_time))
            except json.JSONDecodeError:
                log_test(
                    "2) GET /api/operations/analytics/summary",
                    "FAIL",
                    f"❌ Status: 200 but invalid JSON response"
                )
                results.append(("GET /api/operations/analytics/summary", False, 0))
        else:
            log_test(
                "2) GET /api/operations/analytics/summary",
                "FAIL",
                f"❌ Status: {response.status_code}, Response: {response.text[:200]}"
            )
            results.append(("GET /api/operations/analytics/summary", False, 0))
    except Exception as e:
        log_test("2) GET /api/operations/analytics/summary", "FAIL", f"❌ Exception: {str(e)}")
        results.append(("GET /api/operations/analytics/summary", False, 0))
    
    # Test 3: GET /api/approvals/stream => should establish SSE (just confirm 200 and text/event-stream)
    try:
        start_time = time.time()
        response = requests.get(f"{BACKEND_URL}/approvals/stream", timeout=10, stream=True)
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            content_type = response.headers.get('content-type', '').lower()
            if 'text/event-stream' in content_type:
                log_test(
                    "3) GET /api/approvals/stream",
                    "PASS",
                    f"✅ Status: 200, Content-Type: {content_type} (SSE established)",
                    response_time
                )
                results.append(("GET /api/approvals/stream", True, response_time))
            else:
                log_test(
                    "3) GET /api/approvals/stream",
                    "FAIL",
                    f"❌ Status: 200 but Content-Type is not text/event-stream: {content_type}"
                )
                results.append(("GET /api/approvals/stream", False, 0))
        else:
            log_test(
                "3) GET /api/approvals/stream",
                "FAIL",
                f"❌ Status: {response.status_code}, Response: {response.text[:200]}"
            )
            results.append(("GET /api/approvals/stream", False, 0))
    except Exception as e:
        log_test("3) GET /api/approvals/stream", "FAIL", f"❌ Exception: {str(e)}")
        results.append(("GET /api/approvals/stream", False, 0))
    
    # Test 4: POST /api/ceo/ai-analysis-multi with {} or minimal payload => 200 + accounts/totals, ai null if no key
    try:
        payload = {}  # Minimal payload as requested
        
        start_time = time.time()
        response = requests.post(
            f"{BACKEND_URL}/ceo/ai-analysis-multi",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=15
        )
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            try:
                data = response.json()
                has_accounts = 'accounts' in data
                has_totals = 'totals' in data
                ai_field = data.get('ai')  # Can be null if no key
                
                if has_accounts and has_totals:
                    log_test(
                        "4) POST /api/ceo/ai-analysis-multi",
                        "PASS",
                        f"✅ Status: 200, Has accounts: {has_accounts}, Has totals: {has_totals}, AI field: {ai_field is not None}",
                        response_time
                    )
                    results.append(("POST /api/ceo/ai-analysis-multi", True, response_time))
                else:
                    log_test(
                        "4) POST /api/ceo/ai-analysis-multi",
                        "FAIL",
                        f"❌ Missing required fields - accounts: {has_accounts}, totals: {has_totals}"
                    )
                    results.append(("POST /api/ceo/ai-analysis-multi", False, 0))
            except json.JSONDecodeError:
                log_test(
                    "4) POST /api/ceo/ai-analysis-multi",
                    "FAIL",
                    f"❌ Status: 200 but invalid JSON response"
                )
                results.append(("POST /api/ceo/ai-analysis-multi", False, 0))
        else:
            log_test(
                "4) POST /api/ceo/ai-analysis-multi",
                "FAIL",
                f"❌ Status: {response.status_code}, Response: {response.text[:200]}"
            )
            results.append(("POST /api/ceo/ai-analysis-multi", False, 0))
    except Exception as e:
        log_test("4) POST /api/ceo/ai-analysis-multi", "FAIL", f"❌ Exception: {str(e)}")
        results.append(("POST /api/ceo/ai-analysis-multi", False, 0))
    
    # Test 5: GET /api/customers => 200 + array
    try:
        start_time = time.time()
        response = requests.get(f"{BACKEND_URL}/customers", timeout=10)
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            try:
                data = response.json()
                if isinstance(data, list):
                    log_test(
                        "5) GET /api/customers",
                        "PASS",
                        f"✅ Status: 200, Array response with {len(data)} customers",
                        response_time
                    )
                    results.append(("GET /api/customers", True, response_time))
                    # Store customer ID for next test
                    customer_id = data[0].get('id') if data else None
                else:
                    log_test(
                        "5) GET /api/customers",
                        "FAIL",
                        f"❌ Status: 200 but response is not an array: {type(data)}"
                    )
                    results.append(("GET /api/customers", False, 0))
                    customer_id = None
            except json.JSONDecodeError:
                log_test(
                    "5) GET /api/customers",
                    "FAIL",
                    f"❌ Status: 200 but invalid JSON response"
                )
                results.append(("GET /api/customers", False, 0))
                customer_id = None
        else:
            log_test(
                "5) GET /api/customers",
                "FAIL",
                f"❌ Status: {response.status_code}, Response: {response.text[:200]}"
            )
            results.append(("GET /api/customers", False, 0))
            customer_id = None
    except Exception as e:
        log_test("5) GET /api/customers", "FAIL", f"❌ Exception: {str(e)}")
        results.append(("GET /api/customers", False, 0))
        customer_id = None
    
    # Test 6: GET /api/customers/{someId}/approvals => if any exists, 200; otherwise 200 empty array
    if customer_id:
        try:
            start_time = time.time()
            response = requests.get(f"{BACKEND_URL}/customers/{customer_id}/approvals", timeout=10)
            response_time = time.time() - start_time
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    if isinstance(data, list):
                        log_test(
                            "6) GET /api/customers/{id}/approvals",
                            "PASS",
                            f"✅ Status: 200, Array response with {len(data)} approvals for customer {customer_id}",
                            response_time
                        )
                        results.append(("GET /api/customers/{id}/approvals", True, response_time))
                    else:
                        log_test(
                            "6) GET /api/customers/{id}/approvals",
                            "FAIL",
                            f"❌ Status: 200 but response is not an array: {type(data)}"
                        )
                        results.append(("GET /api/customers/{id}/approvals", False, 0))
                except json.JSONDecodeError:
                    log_test(
                        "6) GET /api/customers/{id}/approvals",
                        "FAIL",
                        f"❌ Status: 200 but invalid JSON response"
                    )
                    results.append(("GET /api/customers/{id}/approvals", False, 0))
            else:
                log_test(
                    "6) GET /api/customers/{id}/approvals",
                    "FAIL",
                    f"❌ Status: {response.status_code}, Response: {response.text[:200]}"
                )
                results.append(("GET /api/customers/{id}/approvals", False, 0))
        except Exception as e:
            log_test("6) GET /api/customers/{id}/approvals", "FAIL", f"❌ Exception: {str(e)}")
            results.append(("GET /api/customers/{id}/approvals", False, 0))
    else:
        log_test(
            "6) GET /api/customers/{id}/approvals",
            "SKIP",
            "⚠️ Skipped - No customer ID available from previous test"
        )
        results.append(("GET /api/customers/{id}/approvals", False, 0))
    
    return results

def print_summary(all_results: List[tuple]):
    """Print comprehensive test summary"""
    print(f"\n{Colors.BLUE}{'='*80}")
    print(f"BACKEND READINESS TEST SUMMARY")
    print(f"ملخص اختبار جاهزية الخلفية")
    print(f"{'='*80}{Colors.RESET}\n")
    
    total_tests = len(all_results)
    passed_tests = sum(1 for _, passed, _ in all_results if passed)
    failed_tests = total_tests - passed_tests
    
    # Calculate average response time
    response_times = [rt for _, passed, rt in all_results if passed and rt > 0]
    avg_response_time = sum(response_times) / len(response_times) if response_times else 0
    
    print(f"Total Tests: {total_tests}")
    print(f"{Colors.GREEN}Passed: {passed_tests}{Colors.RESET}")
    print(f"{Colors.RED}Failed: {failed_tests}{Colors.RESET}")
    print(f"Success Rate: {(passed_tests/total_tests*100):.1f}%")
    print(f"Average Response Time: {avg_response_time:.3f}s\n")
    
    # Detailed results
    print("Detailed Results:")
    print("-" * 80)
    for test_name, passed, response_time in all_results:
        status = f"{Colors.GREEN}✅ PASS{Colors.RESET}" if passed else f"{Colors.RED}❌ FAIL{Colors.RESET}"
        time_str = f"({response_time:.3f}s)" if response_time > 0 else ""
        print(f"{status} {test_name} {time_str}")
    
    print("\n" + "="*80)
    
    # Final verdict
    if failed_tests == 0:
        print(f"{Colors.GREEN}🎉 ALL BACKEND READINESS TESTS PASSED!{Colors.RESET}")
        print(f"{Colors.GREEN}✅ Backend is ready for production use.{Colors.RESET}")
    else:
        print(f"{Colors.RED}⚠️  {failed_tests} TEST(S) FAILED.{Colors.RESET}")
        print(f"{Colors.RED}❌ Backend readiness issues detected - review failures above.{Colors.RESET}")
    print("="*80 + "\n")

def main():
    """Main test execution"""
    print(f"\n{Colors.BLUE}{'='*80}")
    print(f"BACKEND READINESS HEALTH PING TEST")
    print(f"اختبار فحص جاهزية الخلفية الصحي")
    print(f"{'='*80}{Colors.RESET}\n")
    print(f"Backend URL: {BACKEND_URL}")
    print(f"Test Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Run backend readiness tests
    results = test_backend_readiness()
    
    # Print summary
    print_summary(results)

if __name__ == "__main__":
    main()