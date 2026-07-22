#!/usr/bin/env python3
"""
i18n and Backend Regression Testing
Focus Areas:
1. New i18n endpoints: GET/POST /api/i18n/resources with persistence verification
2. Services API structure validation
3. Operations dependencies: biz-accounts, operations, analytics
4. No regressions on existing endpoints: settings, vehicles, parts, approvals
"""

import requests
import json
import time
from datetime import datetime
from typing import Dict, Any, List

# Backend URL from environment
BACKEND_URL = "https://workshop-engine.preview.emergentagent.com/api"

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

def test_i18n_endpoints():
    """Test 1: New i18n endpoints with persistence verification"""
    print(f"\n{Colors.BLUE}{'='*80}")
    print(f"TEST 1: i18n Resources API (موارد الترجمة)")
    print(f"{'='*80}{Colors.RESET}\n")
    
    results = []
    
    # Test 1.1: GET /api/i18n/resources (without lang param) - Get all languages
    try:
        start_time = time.time()
        response = requests.get(f"{BACKEND_URL}/i18n/resources", timeout=10)
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            log_test(
                "GET /api/i18n/resources - جلب جميع اللغات",
                "PASS",
                f"Status: {response.status_code}, Languages found: {list(data.keys()) if isinstance(data, dict) else 'List format'}",
                response_time
            )
            results.append(("GET /api/i18n/resources (all)", True, response_time))
        else:
            log_test(
                "GET /api/i18n/resources - جلب جميع اللغات",
                "FAIL",
                f"Status: {response.status_code}, Response: {response.text[:200]}"
            )
            results.append(("GET /api/i18n/resources (all)", False, 0))
    except Exception as e:
        log_test("GET /api/i18n/resources (all)", "FAIL", f"Exception: {str(e)}")
        results.append(("GET /api/i18n/resources (all)", False, 0))
    
    # Test 1.2: POST /api/i18n/resources - Save English resources
    try:
        test_data = {
            "lang": "en",
            "resources": {
                "common": {
                    "ok": "OK",
                    "cancel": "Cancel",
                    "save": "Save"
                },
                "dashboard": {
                    "title": "Dashboard",
                    "vehicles": "Vehicles"
                }
            }
        }
        
        start_time = time.time()
        response = requests.post(
            f"{BACKEND_URL}/i18n/resources",
            json=test_data,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            log_test(
                "POST /api/i18n/resources - حفظ موارد الإنجليزية",
                "PASS",
                f"Status: {response.status_code}, Response: {data}",
                response_time
            )
            results.append(("POST /api/i18n/resources (en)", True, response_time))
        else:
            log_test(
                "POST /api/i18n/resources - حفظ موارد الإنجليزية",
                "FAIL",
                f"Status: {response.status_code}, Response: {response.text[:200]}"
            )
            results.append(("POST /api/i18n/resources (en)", False, 0))
    except Exception as e:
        log_test("POST /api/i18n/resources (en)", "FAIL", f"Exception: {str(e)}")
        results.append(("POST /api/i18n/resources (en)", False, 0))
    
    # Test 1.3: GET /api/i18n/resources?lang=en - Verify persistence
    try:
        time.sleep(0.5)  # Small delay to ensure data is persisted
        start_time = time.time()
        response = requests.get(f"{BACKEND_URL}/i18n/resources?lang=en", timeout=10)
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            # Verify the data was actually saved
            saved_correctly = (
                data.get("lang") == "en" and
                isinstance(data.get("resources"), dict) and
                data.get("resources", {}).get("common", {}).get("ok") == "OK"
            )
            
            if saved_correctly:
                log_test(
                    "GET /api/i18n/resources?lang=en - التحقق من الحفظ",
                    "PASS",
                    f"✅ Data persisted correctly: lang={data.get('lang')}, common.ok={data.get('resources', {}).get('common', {}).get('ok')}",
                    response_time
                )
                results.append(("GET /api/i18n/resources (en verify)", True, response_time))
            else:
                log_test(
                    "GET /api/i18n/resources?lang=en - التحقق من الحفظ",
                    "FAIL",
                    f"❌ Data NOT persisted correctly. Response: {data}"
                )
                results.append(("GET /api/i18n/resources (en verify)", False, 0))
        else:
            log_test(
                "GET /api/i18n/resources?lang=en - التحقق من الحفظ",
                "FAIL",
                f"Status: {response.status_code}"
            )
            results.append(("GET /api/i18n/resources (en verify)", False, 0))
    except Exception as e:
        log_test("GET /api/i18n/resources (en verify)", "FAIL", f"Exception: {str(e)}")
        results.append(("GET /api/i18n/resources (en verify)", False, 0))
    
    # Test 1.4: POST /api/i18n/resources - Save Arabic resources
    try:
        test_data_ar = {
            "lang": "ar",
            "resources": {
                "common": {
                    "ok": "موافق",
                    "cancel": "إلغاء",
                    "save": "حفظ"
                },
                "dashboard": {
                    "title": "لوحة التحكم",
                    "vehicles": "المركبات"
                }
            }
        }
        
        start_time = time.time()
        response = requests.post(
            f"{BACKEND_URL}/i18n/resources",
            json=test_data_ar,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            log_test(
                "POST /api/i18n/resources - حفظ موارد العربية",
                "PASS",
                f"Status: {response.status_code}, Response: {data}",
                response_time
            )
            results.append(("POST /api/i18n/resources (ar)", True, response_time))
        else:
            log_test(
                "POST /api/i18n/resources - حفظ موارد العربية",
                "FAIL",
                f"Status: {response.status_code}, Response: {response.text[:200]}"
            )
            results.append(("POST /api/i18n/resources (ar)", False, 0))
    except Exception as e:
        log_test("POST /api/i18n/resources (ar)", "FAIL", f"Exception: {str(e)}")
        results.append(("POST /api/i18n/resources (ar)", False, 0))
    
    return results

def test_services_api_structure():
    """Test 2: Services API structure validation"""
    print(f"\n{Colors.BLUE}{'='*80}")
    print(f"TEST 2: Services API Structure (هيكل API الخدمات)")
    print(f"{'='*80}{Colors.RESET}\n")
    
    results = []
    
    # Test 2.1: GET /api/services - Verify structure and required fields
    try:
        start_time = time.time()
        response = requests.get(f"{BACKEND_URL}/services", timeout=10)
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            services = response.json()
            
            # Verify it's a list
            if not isinstance(services, list):
                log_test(
                    "GET /api/services - التحقق من الهيكل",
                    "FAIL",
                    f"❌ Expected list, got: {type(services)}"
                )
                results.append(("GET /api/services structure", False, 0))
                return results
            
            # Check if we have services
            if len(services) == 0:
                log_test(
                    "GET /api/services - التحقق من الهيكل",
                    "WARN",
                    f"⚠️  No services found in database"
                )
                results.append(("GET /api/services structure", True, response_time))
                return results
            
            # Verify required fields in first service
            first_service = services[0]
            required_fields = ["id", "name", "category", "price", "duration"]
            missing_fields = [field for field in required_fields if field not in first_service]
            
            if not missing_fields:
                log_test(
                    "GET /api/services - التحقق من الهيكل",
                    "PASS",
                    f"✅ Structure correct: {len(services)} services, Required fields present: {required_fields}",
                    response_time
                )
                results.append(("GET /api/services structure", True, response_time))
            else:
                log_test(
                    "GET /api/services - التحقق من الهيكل",
                    "FAIL",
                    f"❌ Missing required fields: {missing_fields}. Available fields: {list(first_service.keys())}"
                )
                results.append(("GET /api/services structure", False, 0))
        else:
            log_test(
                "GET /api/services - التحقق من الهيكل",
                "FAIL",
                f"Status: {response.status_code}, Response: {response.text[:200]}"
            )
            results.append(("GET /api/services structure", False, 0))
    except Exception as e:
        log_test("GET /api/services structure", "FAIL", f"Exception: {str(e)}")
        results.append(("GET /api/services structure", False, 0))
    
    return results

def test_operations_dependencies():
    """Test 3: Operations related dependencies"""
    print(f"\n{Colors.BLUE}{'='*80}")
    print(f"TEST 3: Operations Dependencies (تبعيات العمليات)")
    print(f"{'='*80}{Colors.RESET}\n")
    
    results = []
    
    # Test 3.1: GET /api/biz-accounts
    try:
        start_time = time.time()
        response = requests.get(f"{BACKEND_URL}/biz-accounts", timeout=10)
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            log_test(
                "GET /api/biz-accounts - حسابات الأعمال",
                "PASS",
                f"Status: {response.status_code}, Accounts found: {len(data) if isinstance(data, list) else 'Object format'}",
                response_time
            )
            results.append(("GET /api/biz-accounts", True, response_time))
        else:
            log_test(
                "GET /api/biz-accounts - حسابات الأعمال",
                "FAIL",
                f"Status: {response.status_code}, Response: {response.text[:200]}"
            )
            results.append(("GET /api/biz-accounts", False, 0))
    except Exception as e:
        log_test("GET /api/biz-accounts", "FAIL", f"Exception: {str(e)}")
        results.append(("GET /api/biz-accounts", False, 0))
    
    # Test 3.2: GET /api/operations
    try:
        start_time = time.time()
        response = requests.get(f"{BACKEND_URL}/operations", timeout=10)
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            log_test(
                "GET /api/operations - العمليات",
                "PASS",
                f"Status: {response.status_code}, Operations found: {len(data) if isinstance(data, list) else 'Object format'}",
                response_time
            )
            results.append(("GET /api/operations", True, response_time))
        else:
            log_test(
                "GET /api/operations - العمليات",
                "FAIL",
                f"Status: {response.status_code}, Response: {response.text[:200]}"
            )
            results.append(("GET /api/operations", False, 0))
    except Exception as e:
        log_test("GET /api/operations", "FAIL", f"Exception: {str(e)}")
        results.append(("GET /api/operations", False, 0))
    
    # Test 3.3: GET /api/operations/analytics/summary
    try:
        start_time = time.time()
        response = requests.get(f"{BACKEND_URL}/operations/analytics/summary", timeout=10)
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            log_test(
                "GET /api/operations/analytics/summary - ملخص التحليلات",
                "PASS",
                f"Status: {response.status_code}, Summary data: {str(data)[:100]}...",
                response_time
            )
            results.append(("GET /api/operations/analytics/summary", True, response_time))
        else:
            log_test(
                "GET /api/operations/analytics/summary - ملخص التحليلات",
                "FAIL",
                f"Status: {response.status_code}, Response: {response.text[:200]}"
            )
            results.append(("GET /api/operations/analytics/summary", False, 0))
    except Exception as e:
        log_test("GET /api/operations/analytics/summary", "FAIL", f"Exception: {str(e)}")
        results.append(("GET /api/operations/analytics/summary", False, 0))
    
    return results

def test_existing_endpoints_regression():
    """Test 4: No regressions on existing endpoints"""
    print(f"\n{Colors.BLUE}{'='*80}")
    print(f"TEST 4: Existing Endpoints Regression (اختبار عدم التراجع)")
    print(f"{'='*80}{Colors.RESET}\n")
    
    results = []
    
    # Test 4.1: GET /api/settings
    try:
        start_time = time.time()
        response = requests.get(f"{BACKEND_URL}/settings", timeout=10)
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            log_test(
                "GET /api/settings - الإعدادات",
                "PASS",
                f"Status: {response.status_code}, Settings keys: {list(data.keys()) if isinstance(data, dict) else 'List format'}",
                response_time
            )
            results.append(("GET /api/settings", True, response_time))
        else:
            log_test(
                "GET /api/settings - الإعدادات",
                "FAIL",
                f"Status: {response.status_code}, Response: {response.text[:200]}"
            )
            results.append(("GET /api/settings", False, 0))
    except Exception as e:
        log_test("GET /api/settings", "FAIL", f"Exception: {str(e)}")
        results.append(("GET /api/settings", False, 0))
    
    # Test 4.2: GET /api/vehicles
    try:
        start_time = time.time()
        response = requests.get(f"{BACKEND_URL}/vehicles", timeout=10)
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            log_test(
                "GET /api/vehicles - المركبات",
                "PASS",
                f"Status: {response.status_code}, Vehicles count: {len(data) if isinstance(data, list) else 'Object format'}",
                response_time
            )
            results.append(("GET /api/vehicles", True, response_time))
        else:
            log_test(
                "GET /api/vehicles - المركبات",
                "FAIL",
                f"Status: {response.status_code}, Response: {response.text[:200]}"
            )
            results.append(("GET /api/vehicles", False, 0))
    except Exception as e:
        log_test("GET /api/vehicles", "FAIL", f"Exception: {str(e)}")
        results.append(("GET /api/vehicles", False, 0))
    
    # Test 4.3: GET /api/parts
    try:
        start_time = time.time()
        response = requests.get(f"{BACKEND_URL}/parts", timeout=10)
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            log_test(
                "GET /api/parts - القطع",
                "PASS",
                f"Status: {response.status_code}, Parts count: {len(data) if isinstance(data, list) else 'Object format'}",
                response_time
            )
            results.append(("GET /api/parts", True, response_time))
        else:
            log_test(
                "GET /api/parts - القطع",
                "FAIL",
                f"Status: {response.status_code}, Response: {response.text[:200]}"
            )
            results.append(("GET /api/parts", False, 0))
    except Exception as e:
        log_test("GET /api/parts", "FAIL", f"Exception: {str(e)}")
        results.append(("GET /api/parts", False, 0))
    
    # Test 4.4: GET /api/approvals
    try:
        start_time = time.time()
        response = requests.get(f"{BACKEND_URL}/approvals", timeout=10)
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            log_test(
                "GET /api/approvals - الموافقات",
                "PASS",
                f"Status: {response.status_code}, Approvals count: {len(data) if isinstance(data, list) else 'Object format'}",
                response_time
            )
            results.append(("GET /api/approvals", True, response_time))
        else:
            log_test(
                "GET /api/approvals - الموافقات",
                "FAIL",
                f"Status: {response.status_code}, Response: {response.text[:200]}"
            )
            results.append(("GET /api/approvals", False, 0))
    except Exception as e:
        log_test("GET /api/approvals", "FAIL", f"Exception: {str(e)}")
        results.append(("GET /api/approvals", False, 0))
    
    return results

def print_summary(all_results: List[tuple]):
    """Print comprehensive test summary"""
    print(f"\n{Colors.BLUE}{'='*80}")
    print(f"i18n REGRESSION TEST SUMMARY (ملخص اختبار التراجع)")
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
        print(f"{Colors.GREEN}🎉 ALL REGRESSION TESTS PASSED! No regressions detected.{Colors.RESET}")
    else:
        print(f"{Colors.RED}⚠️  {failed_tests} TEST(S) FAILED. Regressions detected - please review.{Colors.RESET}")
    print("="*80 + "\n")

def main():
    """Main test execution"""
    print(f"\n{Colors.BLUE}{'='*80}")
    print(f"i18n AND BACKEND REGRESSION TESTING")
    print(f"اختبار التراجع للترجمة والخلفية")
    print(f"{'='*80}{Colors.RESET}\n")
    print(f"Backend URL: {BACKEND_URL}")
    print(f"Test Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    all_results = []
    
    # Run all tests in order
    all_results.extend(test_i18n_endpoints())
    all_results.extend(test_services_api_structure())
    all_results.extend(test_operations_dependencies())
    all_results.extend(test_existing_endpoints_regression())
    
    # Print summary
    print_summary(all_results)

if __name__ == "__main__":
    main()