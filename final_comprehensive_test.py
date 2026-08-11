#!/usr/bin/env python3
"""
Comprehensive Backend Testing for Workshop Management System
Testing: Enhanced Approval System, Chart of Accounts, Branches, Operations
"""

import requests
import json
import sys
from datetime import datetime
import uuid

# Configuration
BASE_URL = "https://canonical-integrity.preview.emergentagent.com/api"
USERNAME = "مدير"

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*80}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text.center(80)}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*80}{Colors.RESET}\n")

def print_test(name, passed, details=""):
    status = f"{Colors.GREEN}✅ PASS{Colors.RESET}" if passed else f"{Colors.RED}❌ FAIL{Colors.RESET}"
    print(f"{status} - {name}")
    if details:
        print(f"    {Colors.YELLOW}{details}{Colors.RESET}")

def print_section(text):
    print(f"\n{Colors.BOLD}{text}{Colors.RESET}")
    print(f"{'-'*80}")

# Test Results Storage
test_results = {
    'total': 0,
    'passed': 0,
    'failed': 0,
    'tests': []
}

def record_test(name, passed, details="", response=None):
    test_results['total'] += 1
    if passed:
        test_results['passed'] += 1
    else:
        test_results['failed'] += 1
    
    test_results['tests'].append({
        'name': name,
        'passed': passed,
        'details': details,
        'response': response
    })
    print_test(name, passed, details)

# ============================================================================
# 1. ENHANCED APPROVAL SYSTEM TESTS
# ============================================================================

def test_enhanced_approval_system():
    print_header("1. ENHANCED APPROVAL SYSTEM")
    
    # First, get a vehicle to use for testing
    print_section("Setup: Getting test vehicle")
    try:
        resp = requests.get(f"{BASE_URL}/vehicles", timeout=10)
        vehicles = resp.json()
        if not vehicles:
            print(f"{Colors.YELLOW}⚠️  No vehicles found. Creating test vehicle...{Colors.RESET}")
            # Create a test vehicle
            vehicle_data = {
                "customerName": "عميل الاختبار",
                "customerPhone": "0501234567",
                "plateNumber": "ABC-1234",
                "make": "تويوتا",
                "model": "كامري",
                "year": 2020,
                "mileage": 50000,
                "status": "diagnosis"
            }
            resp = requests.post(f"{BASE_URL}/vehicles", json=vehicle_data, timeout=10)
            vehicle = resp.json()
            vehicle_id = vehicle['id']
            customer_id = vehicle.get('customerId')
            print(f"{Colors.GREEN}✓ Created test vehicle: {vehicle_id}{Colors.RESET}")
        else:
            vehicle = vehicles[0]
            vehicle_id = vehicle['id']
            customer_id = vehicle.get('customerId')
            print(f"{Colors.GREEN}✓ Using existing vehicle: {vehicle_id}{Colors.RESET}")
    except Exception as e:
        print(f"{Colors.RED}✗ Failed to get/create vehicle: {e}{Colors.RESET}")
        vehicle_id = None
        customer_id = None
    
    # Test 1: POST /api/approvals with custom expiryDays and images
    print_section("Test 1: Create approval with custom expiry (14 days) and images")
    try:
        approval_data = {
            "vehicleId": vehicle_id,
            "customerId": customer_id,
            "title": "طلب اعتماد إصلاح شامل",
            "amount": 2500.00,
            "expiryDays": 14,
            "serviceItems": [
                {"name": "تغيير زيت المحرك", "price": 150.00},
                {"name": "فحص الفرامل", "price": 200.00},
                {"name": "تبديل فلتر الهواء", "price": 100.00}
            ],
            "serviceItemsText": "تغيير زيت المحرك\nفحص الفرامل\nتبديل فلتر الهواء",
            "images": [
                "https://example.com/image1.jpg",
                "https://example.com/image2.jpg"
            ]
        }
        
        resp = requests.post(f"{BASE_URL}/approvals", json=approval_data, timeout=10)
        
        if resp.status_code == 200:
            result = resp.json()
            token = result.get('token')
            has_images = 'images' in result and len(result.get('images', [])) > 0
            has_expiry = 'expiresAt' in result
            
            if has_images and has_expiry:
                record_test(
                    "POST /api/approvals with expiryDays=14 and images",
                    True,
                    f"Token: {token}, Images: {len(result.get('images', []))}, ExpiresAt: {result.get('expiresAt')}"
                )
                
                # Test 2: GET /api/approvals/public/{token}
                print_section("Test 2: Get public approval by token")
                try:
                    resp_public = requests.get(f"{BASE_URL}/approvals/public/{token}", timeout=10)
                    if resp_public.status_code == 200:
                        public_data = resp_public.json()
                        has_images_public = 'images' in public_data and len(public_data.get('images', [])) > 0
                        record_test(
                            "GET /api/approvals/public/{token}",
                            True,
                            f"Retrieved approval with {len(public_data.get('images', []))} images"
                        )
                    else:
                        record_test(
                            "GET /api/approvals/public/{token}",
                            False,
                            f"Status: {resp_public.status_code}, Error: {resp_public.text[:200]}"
                        )
                except Exception as e:
                    record_test("GET /api/approvals/public/{token}", False, str(e))
            else:
                record_test(
                    "POST /api/approvals with expiryDays=14 and images",
                    False,
                    f"Missing fields - Images: {has_images}, ExpiresAt: {has_expiry}. Response: {json.dumps(result)[:200]}"
                )
        else:
            error_detail = resp.text[:500]
            record_test(
                "POST /api/approvals with expiryDays=14 and images",
                False,
                f"Status: {resp.status_code}, Error: {error_detail}"
            )
    except Exception as e:
        record_test("POST /api/approvals with expiryDays=14 and images", False, str(e))
    
    # Test 3: GET /api/approvals (list all)
    print_section("Test 3: List all approvals")
    try:
        resp = requests.get(f"{BASE_URL}/approvals", timeout=10)
        if resp.status_code == 200:
            approvals = resp.json()
            record_test(
                "GET /api/approvals",
                True,
                f"Retrieved {len(approvals)} approvals"
            )
        else:
            record_test("GET /api/approvals", False, f"Status: {resp.status_code}")
    except Exception as e:
        record_test("GET /api/approvals", False, str(e))

# ============================================================================
# 2. CHART OF ACCOUNTS TESTS
# ============================================================================

def test_chart_of_accounts():
    print_header("2. CHART OF ACCOUNTS (شجرة الحسابات)")
    
    # Test 1: GET /api/accounts (should return 45 accounts)
    print_section("Test 1: Get all accounts (expecting 45 default accounts)")
    try:
        resp = requests.get(f"{BASE_URL}/accounts", timeout=10)
        
        if resp.status_code == 200:
            accounts = resp.json()
            account_count = len(accounts)
            
            if account_count == 0:
                # Try to initialize default accounts
                print(f"{Colors.YELLOW}⚠️  No accounts found. Attempting to initialize...{Colors.RESET}")
                try:
                    init_resp = requests.post(f"{BASE_URL}/admin/init-database", timeout=15)
                    if init_resp.status_code == 200:
                        init_result = init_resp.json()
                        print(f"{Colors.GREEN}✓ Database initialization result: {json.dumps(init_result, indent=2)}{Colors.RESET}")
                        
                        # Try getting accounts again
                        resp = requests.get(f"{BASE_URL}/accounts", timeout=10)
                        if resp.status_code == 200:
                            accounts = resp.json()
                            account_count = len(accounts)
                except Exception as init_error:
                    print(f"{Colors.RED}✗ Failed to initialize database: {init_error}{Colors.RESET}")
            
            if account_count >= 40:  # Allow some flexibility
                record_test(
                    "GET /api/accounts",
                    True,
                    f"Retrieved {account_count} accounts (expected ~45)"
                )
            elif account_count > 0:
                record_test(
                    "GET /api/accounts",
                    False,
                    f"Retrieved {account_count} accounts, expected 45. Database may not be fully initialized."
                )
            else:
                record_test(
                    "GET /api/accounts",
                    False,
                    "No accounts found. Database table may not exist or is empty."
                )
        else:
            error_detail = resp.text[:500]
            record_test(
                "GET /api/accounts",
                False,
                f"Status: {resp.status_code}, Error: {error_detail}"
            )
    except Exception as e:
        record_test("GET /api/accounts", False, str(e))
    
    # Test 2: POST /api/accounts (create new account)
    print_section("Test 2: Create new account")
    try:
        new_account = {
            "code": "6200",
            "name": "مصروفات تسويقية",
            "nameEn": "Marketing Expenses",
            "type": "expense",
            "parentId": "acc-6000",
            "isSystem": False
        }
        
        resp = requests.post(f"{BASE_URL}/accounts", json=new_account, timeout=10)
        
        if resp.status_code == 200:
            result = resp.json()
            account_id = result.get('id')
            record_test(
                "POST /api/accounts",
                True,
                f"Created account: {result.get('name')} (ID: {account_id})"
            )
            
            # Test 3: PUT /api/accounts/{id} (update account)
            print_section("Test 3: Update account")
            try:
                update_data = {
                    "name": "مصروفات تسويق وإعلان",
                    "nameEn": "Marketing & Advertising Expenses"
                }
                
                resp_update = requests.put(f"{BASE_URL}/accounts/{account_id}", json=update_data, timeout=10)
                
                if resp_update.status_code == 200:
                    updated = resp_update.json()
                    record_test(
                        "PUT /api/accounts/{id}",
                        True,
                        f"Updated account name to: {updated.get('name')}"
                    )
                else:
                    record_test(
                        "PUT /api/accounts/{id}",
                        False,
                        f"Status: {resp_update.status_code}, Error: {resp_update.text[:200]}"
                    )
            except Exception as e:
                record_test("PUT /api/accounts/{id}", False, str(e))
            
            # Test 4: DELETE /api/accounts/{id} (delete non-system account)
            print_section("Test 4: Delete non-system account")
            try:
                resp_delete = requests.delete(f"{BASE_URL}/accounts/{account_id}", timeout=10)
                
                if resp_delete.status_code == 200:
                    record_test(
                        "DELETE /api/accounts/{id} (non-system)",
                        True,
                        "Successfully deleted non-system account"
                    )
                else:
                    record_test(
                        "DELETE /api/accounts/{id} (non-system)",
                        False,
                        f"Status: {resp_delete.status_code}"
                    )
            except Exception as e:
                record_test("DELETE /api/accounts/{id} (non-system)", False, str(e))
        else:
            record_test(
                "POST /api/accounts",
                False,
                f"Status: {resp.status_code}, Error: {resp.text[:200]}"
            )
    except Exception as e:
        record_test("POST /api/accounts", False, str(e))
    
    # Test 5: DELETE system account (should fail)
    print_section("Test 5: Attempt to delete system account (should fail)")
    try:
        # Try to delete a system account (e.g., acc-1000 - Assets)
        resp = requests.delete(f"{BASE_URL}/accounts/acc-1000", timeout=10)
        
        if resp.status_code == 400 or resp.status_code == 403:
            record_test(
                "DELETE /api/accounts/{id} (system account)",
                True,
                "Correctly prevented deletion of system account"
            )
        elif resp.status_code == 404:
            record_test(
                "DELETE /api/accounts/{id} (system account)",
                False,
                "System account not found - database may not be initialized"
            )
        elif resp.status_code == 200:
            record_test(
                "DELETE /api/accounts/{id} (system account)",
                False,
                "CRITICAL: System account was deleted! Protection not working."
            )
        else:
            record_test(
                "DELETE /api/accounts/{id} (system account)",
                False,
                f"Unexpected status: {resp.status_code}"
            )
    except Exception as e:
        record_test("DELETE /api/accounts/{id} (system account)", False, str(e))
    
    # Test 6: Verify tree structure
    print_section("Test 6: Verify account tree structure")
    try:
        resp = requests.get(f"{BASE_URL}/accounts", timeout=10)
        if resp.status_code == 200:
            accounts = resp.json()
            
            # Check for parent-child relationships
            parent_accounts = [a for a in accounts if a.get('parent_id') is None or a.get('parentId') is None]
            child_accounts = [a for a in accounts if a.get('parent_id') or a.get('parentId')]
            
            has_structure = len(parent_accounts) > 0 and len(child_accounts) > 0
            
            record_test(
                "Verify account tree structure",
                has_structure,
                f"Parents: {len(parent_accounts)}, Children: {len(child_accounts)}"
            )
        else:
            record_test("Verify account tree structure", False, "Could not retrieve accounts")
    except Exception as e:
        record_test("Verify account tree structure", False, str(e))

# ============================================================================
# 3. BRANCHES (BUSINESS ACCOUNTS) TESTS
# ============================================================================

def test_branches():
    print_header("3. BRANCHES (الفروع)")
    
    # Test 1: GET /api/biz-accounts
    print_section("Test 1: Get all branches")
    try:
        resp = requests.get(f"{BASE_URL}/biz-accounts", timeout=10)
        
        if resp.status_code == 200:
            branches = resp.json()
            record_test(
                "GET /api/biz-accounts",
                True,
                f"Retrieved {len(branches)} branches"
            )
            
            # Display existing branches
            if branches:
                print(f"\n{Colors.BLUE}Existing branches:{Colors.RESET}")
                for branch in branches[:5]:  # Show first 5
                    print(f"  - {branch.get('name')} (Code: {branch.get('code')})")
        else:
            record_test("GET /api/biz-accounts", False, f"Status: {resp.status_code}")
    except Exception as e:
        record_test("GET /api/biz-accounts", False, str(e))
    
    # Test 2: POST /api/biz-accounts
    print_section("Test 2: Create new branch")
    try:
        new_branch = {
            "name": "فرع الاختبار",
            "code": "TEST",
            "currency": "SAR"
        }
        
        resp = requests.post(f"{BASE_URL}/biz-accounts", json=new_branch, timeout=10)
        
        if resp.status_code == 200:
            result = resp.json()
            branch_id = result.get('id')
            record_test(
                "POST /api/biz-accounts",
                True,
                f"Created branch: {result.get('name')} (ID: {branch_id})"
            )
            
            # Test 3: PUT /api/biz-accounts/{id}
            print_section("Test 3: Update branch")
            try:
                update_data = {
                    "name": "فرع الاختبار المحدث",
                    "currency": "USD"
                }
                
                resp_update = requests.put(f"{BASE_URL}/biz-accounts/{branch_id}", json=update_data, timeout=10)
                
                if resp_update.status_code == 200:
                    updated = resp_update.json()
                    record_test(
                        "PUT /api/biz-accounts/{id}",
                        True,
                        f"Updated branch: {updated.get('name')}"
                    )
                else:
                    record_test(
                        "PUT /api/biz-accounts/{id}",
                        False,
                        f"Status: {resp_update.status_code}, Error: {resp_update.text[:200]}"
                    )
            except Exception as e:
                record_test("PUT /api/biz-accounts/{id}", False, str(e))
        else:
            record_test(
                "POST /api/biz-accounts",
                False,
                f"Status: {resp.status_code}, Error: {resp.text[:200]}"
            )
    except Exception as e:
        record_test("POST /api/biz-accounts", False, str(e))

# ============================================================================
# 4. OPERATIONS WITH ACCOUNT LINKING TESTS
# ============================================================================

def test_operations_with_accounts():
    print_header("4. OPERATIONS LINKED TO ACCOUNTS")
    
    # First, get an account ID to use
    print_section("Setup: Getting account for testing")
    account_id = None
    try:
        resp = requests.get(f"{BASE_URL}/accounts", timeout=10)
        if resp.status_code == 200:
            accounts = resp.json()
            if accounts:
                # Find a revenue account
                revenue_accounts = [a for a in accounts if a.get('type') == 'revenue']
                if revenue_accounts:
                    account_id = revenue_accounts[0].get('id')
                    print(f"{Colors.GREEN}✓ Using account: {revenue_accounts[0].get('name')} (ID: {account_id}){Colors.RESET}")
                else:
                    account_id = accounts[0].get('id')
                    print(f"{Colors.YELLOW}⚠️  Using first available account: {accounts[0].get('name')}{Colors.RESET}")
    except Exception as e:
        print(f"{Colors.RED}✗ Failed to get account: {e}{Colors.RESET}")
    
    # Get a vehicle for testing
    vehicle_id = None
    try:
        resp = requests.get(f"{BASE_URL}/vehicles", timeout=10)
        if resp.status_code == 200:
            vehicles = resp.json()
            if vehicles:
                vehicle_id = vehicles[0]['id']
                print(f"{Colors.GREEN}✓ Using vehicle: {vehicle_id}{Colors.RESET}")
    except Exception as e:
        print(f"{Colors.RED}✗ Failed to get vehicle: {e}{Colors.RESET}")
    
    # Test 1: POST /api/operations with accountId
    print_section("Test 1: Create operation with accountId")
    try:
        operation_data = {
            "type": "service",
            "accountId": account_id,
            "vehicleId": vehicle_id,
            "partnerType": "customer",
            "partnerName": "عميل الاختبار",
            "items": [
                {
                    "name": "تغيير زيت",
                    "quantity": 1,
                    "price": 150.00,
                    "itemType": "service"
                },
                {
                    "name": "فلتر زيت",
                    "quantity": 1,
                    "price": 50.00,
                    "itemType": "part"
                }
            ],
            "paymentMethod": "cash",
            "notes": "عملية اختبار"
        }
        
        resp = requests.post(f"{BASE_URL}/operations", json=operation_data, timeout=10)
        
        if resp.status_code == 200:
            result = resp.json()
            operation_id = result.get('id')
            linked_account = result.get('accountId')
            
            if linked_account == account_id:
                record_test(
                    "POST /api/operations with accountId",
                    True,
                    f"Created operation (ID: {operation_id}) linked to account: {account_id}"
                )
                
                # Test 2: GET /api/operations and verify linking
                print_section("Test 2: Verify operation is linked to account")
                try:
                    resp_ops = requests.get(f"{BASE_URL}/operations", timeout=10)
                    
                    if resp_ops.status_code == 200:
                        operations = resp_ops.json()
                        found_operation = None
                        for op in operations:
                            if op.get('id') == operation_id:
                                found_operation = op
                                break
                        
                        if found_operation and found_operation.get('accountId') == account_id:
                            record_test(
                                "GET /api/operations - verify account linking",
                                True,
                                f"Operation correctly linked to account {account_id}"
                            )
                        else:
                            record_test(
                                "GET /api/operations - verify account linking",
                                False,
                                "Operation not found or not linked to account"
                            )
                    else:
                        record_test(
                            "GET /api/operations - verify account linking",
                            False,
                            f"Status: {resp_ops.status_code}"
                        )
                except Exception as e:
                    record_test("GET /api/operations - verify account linking", False, str(e))
            else:
                record_test(
                    "POST /api/operations with accountId",
                    False,
                    f"Account linking failed. Expected: {account_id}, Got: {linked_account}"
                )
        else:
            record_test(
                "POST /api/operations with accountId",
                False,
                f"Status: {resp.status_code}, Error: {resp.text[:200]}"
            )
    except Exception as e:
        record_test("POST /api/operations with accountId", False, str(e))
    
    # Test 3: GET /api/operations (list all)
    print_section("Test 3: List all operations")
    try:
        resp = requests.get(f"{BASE_URL}/operations", timeout=10)
        
        if resp.status_code == 200:
            operations = resp.json()
            record_test(
                "GET /api/operations",
                True,
                f"Retrieved {len(operations)} operations"
            )
        else:
            record_test("GET /api/operations", False, f"Status: {resp.status_code}")
    except Exception as e:
        record_test("GET /api/operations", False, str(e))

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def print_summary():
    print_header("TEST SUMMARY")
    
    total = test_results['total']
    passed = test_results['passed']
    failed = test_results['failed']
    pass_rate = (passed / total * 100) if total > 0 else 0
    
    print(f"{Colors.BOLD}Total Tests: {total}{Colors.RESET}")
    print(f"{Colors.GREEN}Passed: {passed}{Colors.RESET}")
    print(f"{Colors.RED}Failed: {failed}{Colors.RESET}")
    print(f"{Colors.BOLD}Pass Rate: {pass_rate:.1f}%{Colors.RESET}\n")
    
    if failed > 0:
        print(f"{Colors.RED}{Colors.BOLD}FAILED TESTS:{Colors.RESET}")
        for test in test_results['tests']:
            if not test['passed']:
                print(f"  ❌ {test['name']}")
                if test['details']:
                    print(f"     {test['details']}")
        print()
    
    # Categorize issues
    critical_issues = []
    for test in test_results['tests']:
        if not test['passed']:
            if 'schema cache' in test['details'].lower() or 'table' in test['details'].lower():
                critical_issues.append(f"Database schema issue: {test['name']}")
            elif 'column' in test['details'].lower():
                critical_issues.append(f"Missing column: {test['name']}")
    
    if critical_issues:
        print(f"{Colors.RED}{Colors.BOLD}CRITICAL ISSUES FOUND:{Colors.RESET}")
        for issue in critical_issues:
            print(f"  🔴 {issue}")
        print()

def main():
    print_header("COMPREHENSIVE BACKEND TESTING")
    print(f"Backend URL: {BASE_URL}")
    print(f"Test User: {USERNAME}")
    print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    try:
        # Run all test suites
        test_enhanced_approval_system()
        test_chart_of_accounts()
        test_branches()
        test_operations_with_accounts()
        
        # Print summary
        print_summary()
        
        # Exit with appropriate code
        sys.exit(0 if test_results['failed'] == 0 else 1)
        
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Testing interrupted by user{Colors.RESET}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}Fatal error during testing: {e}{Colors.RESET}")
        sys.exit(1)

if __name__ == "__main__":
    main()
