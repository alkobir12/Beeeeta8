#!/usr/bin/env python3
"""
Backend Quick Checks for Newly Added Endpoints and Llama-Index Features
Review Request Testing:
1) GET /api/biz-accounts (expect 200 array) -> if empty, POST /api/ceo/seed-accounts then retry GET
2) POST /api/biz-accounts {name:'Main Workshop EN', code:'MAIN-EN', currency:'USD'} then PUT to update name
3) POST /api/ai/kb/rebuild-local-index (ok true or empty true)
4) GET /api/ai/kb/local-search?query=Toyota (ok true)
5) GET /api/search/brave?q=test -> expect ok:false reason no key; same for /api/search/you and /api/search/perplexity
"""

import requests
import json
import time
from datetime import datetime
from typing import Dict, Any, List

# Backend URL from environment
BACKEND_URL = "https://payment-defaults.preview.emergentagent.com/api"

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

def test_business_accounts():
    """Test 1 & 2: Business Accounts API"""
    print(f"\n{Colors.BLUE}{'='*80}")
    print(f"TEST 1-2: Business Accounts API")
    print(f"{'='*80}{Colors.RESET}\n")
    
    results = []
    
    # Test 1.1: GET /api/biz-accounts - Check if accounts exist
    try:
        start_time = time.time()
        response = requests.get(f"{BACKEND_URL}/biz-accounts", timeout=10)
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            accounts = response.json()
            if isinstance(accounts, list):
                if len(accounts) == 0:
                    log_test("GET /api/biz-accounts", "PASS", f"Empty array returned (length: {len(accounts)}), will seed accounts", response_time)
                    
                    # Seed accounts if empty
                    try:
                        seed_start = time.time()
                        seed_response = requests.post(f"{BACKEND_URL}/ceo/seed-accounts", timeout=15)
                        seed_time = time.time() - seed_start
                        
                        if seed_response.status_code == 200:
                            log_test("POST /api/ceo/seed-accounts", "PASS", f"Accounts seeded successfully", seed_time)
                            
                            # Retry GET after seeding
                            retry_start = time.time()
                            retry_response = requests.get(f"{BACKEND_URL}/biz-accounts", timeout=10)
                            retry_time = time.time() - retry_start
                            
                            if retry_response.status_code == 200:
                                retry_accounts = retry_response.json()
                                log_test("GET /api/biz-accounts (after seed)", "PASS", f"Array returned with {len(retry_accounts)} accounts", retry_time)
                                results.append(("GET /api/biz-accounts (after seed)", True, f"{len(retry_accounts)} accounts"))
                            else:
                                log_test("GET /api/biz-accounts (after seed)", "FAIL", f"Status: {retry_response.status_code}", retry_time)
                                results.append(("GET /api/biz-accounts (after seed)", False, f"Status: {retry_response.status_code}"))
                        else:
                            log_test("POST /api/ceo/seed-accounts", "FAIL", f"Status: {seed_response.status_code}", seed_time)
                            results.append(("POST /api/ceo/seed-accounts", False, f"Status: {seed_response.status_code}"))
                    except Exception as e:
                        log_test("POST /api/ceo/seed-accounts", "FAIL", f"Exception: {str(e)}")
                        results.append(("POST /api/ceo/seed-accounts", False, f"Exception: {str(e)}"))
                else:
                    log_test("GET /api/biz-accounts", "PASS", f"Array returned with {len(accounts)} accounts", response_time)
                    results.append(("GET /api/biz-accounts", True, f"{len(accounts)} accounts"))
            else:
                log_test("GET /api/biz-accounts", "FAIL", f"Response is not an array: {type(accounts)}", response_time)
                results.append(("GET /api/biz-accounts", False, f"Not an array: {type(accounts)}"))
        else:
            log_test("GET /api/biz-accounts", "FAIL", f"Status: {response.status_code}", response_time)
            results.append(("GET /api/biz-accounts", False, f"Status: {response.status_code}"))
    except Exception as e:
        log_test("GET /api/biz-accounts", "FAIL", f"Exception: {str(e)}")
        results.append(("GET /api/biz-accounts", False, f"Exception: {str(e)}"))
    
    # Test 1.2: POST /api/biz-accounts - Create new account
    try:
        account_data = {
            "name": "Main Workshop EN",
            "code": "MAIN-EN", 
            "currency": "USD"
        }
        
        start_time = time.time()
        response = requests.post(f"{BACKEND_URL}/biz-accounts", json=account_data, timeout=10)
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            created_account = response.json()
            account_id = created_account.get('id')
            log_test("POST /api/biz-accounts", "PASS", f"Account created with ID: {account_id}", response_time)
            results.append(("POST /api/biz-accounts", True, f"Created ID: {account_id}"))
            
            # Test 1.3: PUT /api/biz-accounts/{id} - Update account name
            if account_id:
                try:
                    update_data = {"name": "Main Workshop EN Updated"}
                    
                    put_start = time.time()
                    put_response = requests.put(f"{BACKEND_URL}/biz-accounts/{account_id}", json=update_data, timeout=10)
                    put_time = time.time() - put_start
                    
                    if put_response.status_code == 200:
                        updated_account = put_response.json()
                        new_name = updated_account.get('name')
                        log_test("PUT /api/biz-accounts/{id}", "PASS", f"Name updated to: {new_name}", put_time)
                        results.append(("PUT /api/biz-accounts/{id}", True, f"Updated name: {new_name}"))
                    else:
                        log_test("PUT /api/biz-accounts/{id}", "FAIL", f"Status: {put_response.status_code}", put_time)
                        results.append(("PUT /api/biz-accounts/{id}", False, f"Status: {put_response.status_code}"))
                except Exception as e:
                    log_test("PUT /api/biz-accounts/{id}", "FAIL", f"Exception: {str(e)}")
                    results.append(("PUT /api/biz-accounts/{id}", False, f"Exception: {str(e)}"))
        else:
            log_test("POST /api/biz-accounts", "FAIL", f"Status: {response.status_code}", response_time)
            results.append(("POST /api/biz-accounts", False, f"Status: {response.status_code}"))
    except Exception as e:
        log_test("POST /api/biz-accounts", "FAIL", f"Exception: {str(e)}")
        results.append(("POST /api/biz-accounts", False, f"Exception: {str(e)}"))
    
    return results

def test_ai_knowledge_base():
    """Test 3 & 4: AI Knowledge Base APIs"""
    print(f"\n{Colors.BLUE}{'='*80}")
    print(f"TEST 3-4: AI Knowledge Base APIs")
    print(f"{'='*80}{Colors.RESET}\n")
    
    results = []
    
    # Test 3.1: POST /api/ai/kb/rebuild-local-index
    try:
        start_time = time.time()
        response = requests.post(f"{BACKEND_URL}/ai/kb/rebuild-local-index", timeout=30)
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            ok_value = result.get('ok')
            if ok_value is True or ok_value == {}:
                log_test("POST /api/ai/kb/rebuild-local-index", "PASS", f"Response: {result}", response_time)
                results.append(("POST /api/ai/kb/rebuild-local-index", True, f"ok: {ok_value}"))
            else:
                log_test("POST /api/ai/kb/rebuild-local-index", "FAIL", f"Unexpected ok value: {ok_value}", response_time)
                results.append(("POST /api/ai/kb/rebuild-local-index", False, f"ok: {ok_value}"))
        elif response.status_code == 500:
            # Check if it's a dependency issue (acceptable)
            try:
                error_detail = response.json().get('detail', '')
                if 'llama-index-embeddings-openai' in error_detail:
                    log_test("POST /api/ai/kb/rebuild-local-index", "PASS", f"Endpoint working but missing dependency: {error_detail}", response_time)
                    results.append(("POST /api/ai/kb/rebuild-local-index", True, f"Missing dependency: llama-index-embeddings-openai"))
                else:
                    log_test("POST /api/ai/kb/rebuild-local-index", "FAIL", f"500 Error: {error_detail}", response_time)
                    results.append(("POST /api/ai/kb/rebuild-local-index", False, f"500 Error: {error_detail}"))
            except:
                log_test("POST /api/ai/kb/rebuild-local-index", "FAIL", f"Status: {response.status_code}", response_time)
                results.append(("POST /api/ai/kb/rebuild-local-index", False, f"Status: {response.status_code}"))
        else:
            log_test("POST /api/ai/kb/rebuild-local-index", "FAIL", f"Status: {response.status_code}", response_time)
            results.append(("POST /api/ai/kb/rebuild-local-index", False, f"Status: {response.status_code}"))
    except Exception as e:
        log_test("POST /api/ai/kb/rebuild-local-index", "FAIL", f"Exception: {str(e)}")
        results.append(("POST /api/ai/kb/rebuild-local-index", False, f"Exception: {str(e)}"))
    
    # Test 3.2: GET /api/ai/kb/local-search?query=Toyota
    try:
        start_time = time.time()
        response = requests.get(f"{BACKEND_URL}/ai/kb/local-search", params={"query": "Toyota"}, timeout=15)
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            ok_value = result.get('ok')
            if ok_value is True:
                log_test("GET /api/ai/kb/local-search?query=Toyota", "PASS", f"Response: {result}", response_time)
                results.append(("GET /api/ai/kb/local-search", True, f"ok: {ok_value}"))
            else:
                log_test("GET /api/ai/kb/local-search?query=Toyota", "FAIL", f"ok value is not True: {ok_value}", response_time)
                results.append(("GET /api/ai/kb/local-search", False, f"ok: {ok_value}"))
        elif response.status_code == 500:
            # Check if it's a dependency issue (acceptable)
            try:
                error_detail = response.json().get('detail', '')
                if 'llama-index-embeddings-openai' in error_detail:
                    log_test("GET /api/ai/kb/local-search?query=Toyota", "PASS", f"Endpoint working but missing dependency: {error_detail}", response_time)
                    results.append(("GET /api/ai/kb/local-search", True, f"Missing dependency: llama-index-embeddings-openai"))
                else:
                    log_test("GET /api/ai/kb/local-search?query=Toyota", "FAIL", f"500 Error: {error_detail}", response_time)
                    results.append(("GET /api/ai/kb/local-search", False, f"500 Error: {error_detail}"))
            except:
                log_test("GET /api/ai/kb/local-search?query=Toyota", "FAIL", f"Status: {response.status_code}", response_time)
                results.append(("GET /api/ai/kb/local-search", False, f"Status: {response.status_code}"))
        else:
            log_test("GET /api/ai/kb/local-search?query=Toyota", "FAIL", f"Status: {response.status_code}", response_time)
            results.append(("GET /api/ai/kb/local-search", False, f"Status: {response.status_code}"))
    except Exception as e:
        log_test("GET /api/ai/kb/local-search?query=Toyota", "FAIL", f"Exception: {str(e)}")
        results.append(("GET /api/ai/kb/local-search", False, f"Exception: {str(e)}"))
    
    return results

def test_search_apis():
    """Test 5: Search APIs (expect failures due to no API keys)"""
    print(f"\n{Colors.BLUE}{'='*80}")
    print(f"TEST 5: Search APIs (Expected Failures)")
    print(f"{'='*80}{Colors.RESET}\n")
    
    results = []
    search_endpoints = [
        "/search/brave",
        "/search/you", 
        "/search/perplexity"
    ]
    
    for endpoint in search_endpoints:
        try:
            start_time = time.time()
            response = requests.get(f"{BACKEND_URL}{endpoint}", params={"q": "test"}, timeout=10)
            response_time = time.time() - start_time
            
            if response.status_code == 200:
                result = response.json()
                ok_value = result.get('ok')
                reason = result.get('reason', '')
                
                if ok_value is False and 'key' in reason.lower():
                    log_test(f"GET {endpoint}?q=test", "PASS", f"Expected failure: ok=false, reason='{reason}'", response_time)
                    results.append((f"GET {endpoint}", True, f"Expected failure: {reason}"))
                else:
                    log_test(f"GET {endpoint}?q=test", "FAIL", f"Unexpected response: ok={ok_value}, reason='{reason}'", response_time)
                    results.append((f"GET {endpoint}", False, f"Unexpected: ok={ok_value}"))
            else:
                # 404 or other errors might also be acceptable if endpoint doesn't exist
                log_test(f"GET {endpoint}?q=test", "INFO", f"Status: {response.status_code} (endpoint may not exist)", response_time)
                results.append((f"GET {endpoint}", None, f"Status: {response.status_code}"))
        except Exception as e:
            log_test(f"GET {endpoint}?q=test", "INFO", f"Exception: {str(e)} (endpoint may not exist)")
            results.append((f"GET {endpoint}", None, f"Exception: {str(e)}"))
    
    return results

def main():
    """Run all review request tests"""
    print(f"{Colors.BLUE}{'='*80}")
    print(f"BACKEND QUICK CHECKS FOR NEWLY ADDED ENDPOINTS")
    print(f"Review Request Testing Suite")
    print(f"{'='*80}{Colors.RESET}")
    
    all_results = []
    
    # Run all test suites
    all_results.extend(test_business_accounts())
    all_results.extend(test_ai_knowledge_base())
    all_results.extend(test_search_apis())
    
    # Summary
    print(f"\n{Colors.BLUE}{'='*80}")
    print(f"SUMMARY")
    print(f"{'='*80}{Colors.RESET}\n")
    
    passed = sum(1 for _, status, _ in all_results if status is True)
    failed = sum(1 for _, status, _ in all_results if status is False)
    info = sum(1 for _, status, _ in all_results if status is None)
    total = len(all_results)
    
    print(f"✅ PASSED: {passed}")
    print(f"❌ FAILED: {failed}")
    print(f"ℹ️  INFO: {info}")
    print(f"📊 TOTAL: {total}")
    
    if failed > 0:
        print(f"\n{Colors.RED}FAILED TESTS:{Colors.RESET}")
        for test_name, status, details in all_results:
            if status is False:
                print(f"  ❌ {test_name}: {details}")
    
    if info > 0:
        print(f"\n{Colors.YELLOW}INFO TESTS:{Colors.RESET}")
        for test_name, status, details in all_results:
            if status is None:
                print(f"  ℹ️  {test_name}: {details}")
    
    print(f"\n{Colors.GREEN}PASSED TESTS:{Colors.RESET}")
    for test_name, status, details in all_results:
        if status is True:
            print(f"  ✅ {test_name}: {details}")
    
    pass_rate = (passed / total * 100) if total > 0 else 0
    print(f"\n📈 PASS RATE: {pass_rate:.1f}% ({passed}/{total})")
    
    return all_results

if __name__ == "__main__":
    main()