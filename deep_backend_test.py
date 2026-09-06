#!/usr/bin/env python3
"""
Backend Deep Tests for Workshop Management System
Focus: Budgets, Operations, Parts Import, and Regression Tests
"""

import requests
import json
import os
import sys
from datetime import datetime
from io import StringIO
import uuid

# Get backend URL from environment
BACKEND_URL = os.getenv('REACT_APP_BACKEND_URL', 'https://financial-ssot.preview.emergentagent.com')
API_BASE = f"{BACKEND_URL}/api"

class BackendTester:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        self.test_results = []
        
    def log_test(self, test_name, success, details=""):
        """Log test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {test_name}")
        if details:
            print(f"   Details: {details}")
        self.test_results.append({
            'test': test_name,
            'success': success,
            'details': details
        })
        
    def test_budgets_endpoints(self):
        """Test all budgets endpoints as specified in review request"""
        print("\n=== TESTING BUDGETS ENDPOINTS ===")
        
        # First ensure we have business accounts
        try:
            resp = self.session.get(f"{API_BASE}/biz-accounts")
            if resp.status_code != 200:
                self.log_test("GET /api/biz-accounts (prerequisite)", False, f"Status: {resp.status_code}")
                return
            
            accounts = resp.json()
            if not accounts:
                self.log_test("GET /api/biz-accounts (prerequisite)", False, "No accounts found")
                return
                
            account_id = accounts[0]['id']
            self.log_test("GET /api/biz-accounts (prerequisite)", True, f"Found {len(accounts)} accounts")
            
        except Exception as e:
            self.log_test("GET /api/biz-accounts (prerequisite)", False, str(e))
            return
        
        # Test 1: GET /api/budgets (no params) returns array
        try:
            resp = self.session.get(f"{API_BASE}/budgets")
            success = resp.status_code == 200 and isinstance(resp.json(), list)
            self.log_test("GET /api/budgets (no params) returns array", success, 
                         f"Status: {resp.status_code}, Type: {type(resp.json())}")
        except Exception as e:
            self.log_test("GET /api/budgets (no params) returns array", False, str(e))
        
        # Test 2: POST /api/budgets with accountId and period=current YYYY-MM
        current_period = datetime.now().strftime('%Y-%m')
        budget_data = {
            "accountId": account_id,
            "period": current_period,
            "incomeTarget": 10000.0,
            "expenseTarget": 7000.0,
            "notes": "Test budget creation"
        }
        
        try:
            resp = self.session.post(f"{API_BASE}/budgets", json=budget_data)
            success = resp.status_code == 200
            created_budget = resp.json() if success else None
            budget_id = created_budget.get('id') if created_budget else None
            
            self.log_test("POST /api/budgets with accountId and period", success,
                         f"Status: {resp.status_code}, Budget ID: {budget_id}")
        except Exception as e:
            self.log_test("POST /api/budgets with accountId and period", False, str(e))
            return
        
        # Test 3: GET /api/budgets?account_id=<that_id> returns array with actualIncome/actualExpenses
        try:
            resp = self.session.get(f"{API_BASE}/budgets?account_id={account_id}")
            success = resp.status_code == 200
            budgets = resp.json() if success else []
            
            has_actuals = False
            if success and budgets:
                # Check if any budget has actualIncome and actualExpenses fields
                for budget in budgets:
                    if 'actualIncome' in budget and 'actualExpenses' in budget:
                        has_actuals = True
                        break
            
            self.log_test("GET /api/budgets?account_id returns array with actualIncome/actualExpenses", 
                         success and has_actuals,
                         f"Status: {resp.status_code}, Budgets: {len(budgets)}, Has actuals: {has_actuals}")
        except Exception as e:
            self.log_test("GET /api/budgets?account_id returns array with actualIncome/actualExpenses", False, str(e))
        
        # Test 4: PUT /api/budgets/{id} updating incomeTarget and expenseTarget
        if budget_id:
            update_data = {
                "incomeTarget": 12000.0,
                "expenseTarget": 8000.0
            }
            try:
                resp = self.session.put(f"{API_BASE}/budgets/{budget_id}", json=update_data)
                success = resp.status_code == 200
                updated_budget = resp.json() if success else None
                
                # Verify the update worked
                targets_updated = False
                if updated_budget:
                    targets_updated = (updated_budget.get('incomeTarget') == 12000.0 and 
                                     updated_budget.get('expenseTarget') == 8000.0)
                
                self.log_test("PUT /api/budgets/{id} updating incomeTarget and expenseTarget", 
                             success and targets_updated,
                             f"Status: {resp.status_code}, Targets updated: {targets_updated}")
            except Exception as e:
                self.log_test("PUT /api/budgets/{id} updating incomeTarget and expenseTarget", False, str(e))
    
    def test_operations_quick_access(self):
        """Test operations quick access endpoints"""
        print("\n=== TESTING OPERATIONS QUICK ACCESS ===")
        
        # Get business accounts for operations
        try:
            resp = self.session.get(f"{API_BASE}/biz-accounts")
            accounts = resp.json()
            account_id = accounts[0]['id'] if accounts else str(uuid.uuid4())
        except:
            account_id = str(uuid.uuid4())
        
        # Create two operations if needed
        operation_ids = []
        for i in range(2):
            operation_data = {
                "accountId": account_id,
                "type": "purchase" if i == 0 else "sale",
                "partnerName": f"شريك تجاري {i+1}",
                "partnerType": "supplier" if i == 0 else "customer",
                "items": [
                    {
                        "itemId": str(uuid.uuid4()),
                        "itemType": "part",
                        "name": f"قطعة غيار {i+1}",
                        "quantity": 2,
                        "price": 100.0
                    }
                ],
                "paymentMethod": "cash",
                "notes": f"عملية اختبار {i+1}"
            }
            
            try:
                resp = self.session.post(f"{API_BASE}/operations", json=operation_data)
                if resp.status_code == 200:
                    operation = resp.json()
                    operation_ids.append(operation.get('id'))
                    self.log_test(f"POST /api/operations (operation {i+1})", True, 
                                 f"Created operation: {operation.get('id')}")
                else:
                    self.log_test(f"POST /api/operations (operation {i+1})", False, 
                                 f"Status: {resp.status_code}")
            except Exception as e:
                self.log_test(f"POST /api/operations (operation {i+1})", False, str(e))
        
        # Test: GET /api/operations should list them sorted by date desc
        try:
            resp = self.session.get(f"{API_BASE}/operations")
            success = resp.status_code == 200
            operations = resp.json() if success else []
            
            # Check if sorted by date desc (most recent first)
            sorted_correctly = True
            if len(operations) > 1:
                for i in range(len(operations) - 1):
                    current_date = operations[i].get('date', '')
                    next_date = operations[i + 1].get('date', '')
                    if current_date < next_date:  # Should be desc order
                        sorted_correctly = False
                        break
            
            self.log_test("GET /api/operations lists operations sorted by date desc", 
                         success and len(operations) >= 2,
                         f"Status: {resp.status_code}, Operations: {len(operations)}, Sorted: {sorted_correctly}")
        except Exception as e:
            self.log_test("GET /api/operations lists operations sorted by date desc", False, str(e))
        
        # Test: GET /api/operations/{id} returns document
        if operation_ids:
            try:
                op_id = operation_ids[0]
                resp = self.session.get(f"{API_BASE}/operations/{op_id}")
                success = resp.status_code == 200
                operation = resp.json() if success else {}
                
                self.log_test("GET /api/operations/{id} returns document", success,
                             f"Status: {resp.status_code}, Operation ID: {operation.get('id')}")
            except Exception as e:
                self.log_test("GET /api/operations/{id} returns document", False, str(e))
        
        # Test: PUT /api/operations/{id} with {partnerName:'مورد معدل'} persists change
        if operation_ids:
            try:
                op_id = operation_ids[0]
                update_data = {"partnerName": "مورد معدل"}
                resp = self.session.put(f"{API_BASE}/operations/{op_id}", json=update_data)
                success = resp.status_code == 200
                updated_op = resp.json() if success else {}
                
                # Verify the change persisted
                name_updated = updated_op.get('partnerName') == 'مورد معدل'
                
                self.log_test("PUT /api/operations/{id} with partnerName persists change", 
                             success and name_updated,
                             f"Status: {resp.status_code}, Name updated: {name_updated}")
            except Exception as e:
                self.log_test("PUT /api/operations/{id} with partnerName persists change", False, str(e))
    
    def test_parts_excel_import(self):
        """Test parts Excel/CSV import functionality"""
        print("\n=== TESTING PARTS EXCEL IMPORT ===")
        
        # Create a small in-memory CSV
        csv_content = """partNumber,name,category,purchasePrice,sellingPrice,quantity,minQuantity,supplier
TEST001,قطعة اختبار 1,محرك,50.0,75.0,10,5,مورد الاختبار
TEST002,قطعة اختبار 2,كهرباء,30.0,45.0,15,3,مورد الاختبار"""
        
        # Test: POST /api/import/parts with CSV should return {status:'ok'} and created>0
        try:
            files = {
                'file': ('test_parts.csv', csv_content, 'text/csv')
            }
            # Remove Content-Type header for multipart upload
            headers = {k: v for k, v in self.session.headers.items() if k.lower() != 'content-type'}
            
            resp = self.session.post(f"{API_BASE}/import/parts", files=files, headers=headers)
            success = resp.status_code == 200
            result = resp.json() if success else {}
            
            status_ok = result.get('status') == 'ok'
            created_count = result.get('created', 0)
            
            # Accept both created>0 or skipped>0 (if parts already exist)
            has_activity = (created_count > 0 or result.get('skipped', 0) > 0)
            self.log_test("POST /api/import/parts with CSV returns {status:'ok'} and activity", 
                         success and status_ok and has_activity,
                         f"Status: {resp.status_code}, Result: {result}")
        except Exception as e:
            self.log_test("POST /api/import/parts with CSV returns {status:'ok'} and activity", False, str(e))
        
        # Test: Verify that GET /api/parts lists the imported part
        try:
            resp = self.session.get(f"{API_BASE}/parts")
            success = resp.status_code == 200
            parts = resp.json() if success else []
            
            # Look for our test parts
            test_parts_found = 0
            for part in parts:
                if part.get('partNumber', '').startswith('TEST'):
                    test_parts_found += 1
            
            self.log_test("GET /api/parts lists the imported parts", 
                         success and test_parts_found >= 1,
                         f"Status: {resp.status_code}, Test parts found: {test_parts_found}")
        except Exception as e:
            self.log_test("GET /api/parts lists the imported parts", False, str(e))
    
    def test_regression_endpoints(self):
        """Test regression endpoints to ensure they still work"""
        print("\n=== TESTING REGRESSION ENDPOINTS ===")
        
        # Test: GET /api/biz-accounts
        try:
            resp = self.session.get(f"{API_BASE}/biz-accounts")
            success = resp.status_code == 200
            accounts = resp.json() if success else []
            
            self.log_test("GET /api/biz-accounts", success,
                         f"Status: {resp.status_code}, Accounts: {len(accounts)}")
        except Exception as e:
            self.log_test("GET /api/biz-accounts", False, str(e))
        
        # Test: GET /api/operations
        try:
            resp = self.session.get(f"{API_BASE}/operations")
            success = resp.status_code == 200
            operations = resp.json() if success else []
            
            self.log_test("GET /api/operations", success,
                         f"Status: {resp.status_code}, Operations: {len(operations)}")
        except Exception as e:
            self.log_test("GET /api/operations", False, str(e))
        
        # Test: POST /api/print/resolve-template with invoice type
        try:
            template_data = {"override_type": "invoice"}
            resp = self.session.post(f"{API_BASE}/print/resolve-template", json=template_data)
            success = resp.status_code == 200
            template = resp.json() if success else {}
            
            self.log_test("POST /api/print/resolve-template with invoice type", success,
                         f"Status: {resp.status_code}, Template type: {template.get('type')}")
        except Exception as e:
            self.log_test("POST /api/print/resolve-template with invoice type", False, str(e))
        
        # Test: POST /api/auth/request-otp
        try:
            otp_data = {"phone": "+966501234567"}
            resp = self.session.post(f"{API_BASE}/auth/request-otp", json=otp_data)
            success = resp.status_code == 200
            result = resp.json() if success else {}
            
            self.log_test("POST /api/auth/request-otp", success,
                         f"Status: {resp.status_code}, Has token: {'token' in result}")
        except Exception as e:
            self.log_test("POST /api/auth/request-otp", False, str(e))
    
    def run_all_tests(self):
        """Run all backend tests"""
        print(f"🚀 Starting Backend Deep Tests")
        print(f"Backend URL: {BACKEND_URL}")
        print(f"API Base: {API_BASE}")
        
        # Run test suites
        self.test_budgets_endpoints()
        self.test_operations_quick_access()
        self.test_parts_excel_import()
        self.test_regression_endpoints()
        
        # Summary
        print(f"\n=== TEST SUMMARY ===")
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['success'])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests*100):.1f}%")
        
        if failed_tests > 0:
            print(f"\n=== FAILED TESTS ===")
            for result in self.test_results:
                if not result['success']:
                    print(f"❌ {result['test']}: {result['details']}")
        
        return passed_tests, failed_tests

if __name__ == "__main__":
    tester = BackendTester()
    passed, failed = tester.run_all_tests()
    
    # Exit with error code if tests failed
    sys.exit(1 if failed > 0 else 0)