#!/usr/bin/env python3
"""
اختبار نقاط النهاية الجديدة للذمم المدينة (AR Endpoints)
Testing new Accounts Receivable (AR) endpoints derived from operations + journal_entries

Test Scenario: June 2024
- يوم 1: عملية بيع إجمالي 780 paymentMethod=credit للعميل أحمد العتيبي بتاريخ 2024-06-01
  ثم confirm-payment مبلغ 400 بتاريخ 2024-06-01، ثم confirm-payment مبلغ 200 بتاريخ 2024-06-15
- يوم 5: عملية بيع إجمالي 720 paymentMethod=credit للعميل محمد القحطاني بتاريخ 2024-06-05
  ثم confirm-payment مبلغ 720 بتاريخ 2024-06-20
- يوم 10: عملية بيع إجمالي 330 paymentMethod=cash للعميلة سارة الشمري بتاريخ 2024-06-10 (لا تؤثر على الذمم)

Expected Results as of 2024-06-30:
- Total AR = 180 SAR (أحمد العتيبي only)
- AR aging: total_ar=180, 0_30=180
- AR ledger ending_balance=180
- Customer statement أحمد العتيبي ending_balance=180
- AR turnover closing_receivables=180
"""

import requests
import json
from datetime import datetime
import time

# Configuration
BASE_URL = "https://vehicle-accounting-2.preview.emergentagent.com/api"
WORKSHOP_ID = "finmodule-sync"

class AREndpointsTest:
    def __init__(self):
        self.base_url = BASE_URL
        self.workshop_id = WORKSHOP_ID
        self.session = requests.Session()
        self.test_results = []
        
    def log_result(self, test_name, status, details):
        """Log test result"""
        result = {
            "test": test_name,
            "status": status,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        self.test_results.append(result)
        status_icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        print(f"{status_icon} {test_name}: {details}")
        
    def make_request(self, method, endpoint, data=None, params=None):
        """Make HTTP request with error handling"""
        url = f"{self.base_url}{endpoint}"
        try:
            if method.upper() == "GET":
                response = self.session.get(url, params=params)
            elif method.upper() == "POST":
                response = self.session.post(url, json=data, params=params)
            elif method.upper() == "DELETE":
                response = self.session.delete(url, params=params)
            else:
                raise ValueError(f"Unsupported method: {method}")
                
            print(f"🔗 {method} {url}")
            if params:
                print(f"   Params: {params}")
            if data:
                print(f"   Data: {json.dumps(data, ensure_ascii=False, indent=2)}")
            print(f"   Status: {response.status_code}")
            
            return response
        except Exception as e:
            print(f"❌ Request failed: {e}")
            return None
            
    def reset_all_data(self):
        """Step 1: Reset all financial data"""
        print("\n" + "="*60)
        print("🔄 STEP 1: RESET ALL DATA")
        print("="*60)
        
        params = {
            "workshop_id": self.workshop_id,
            "confirm": "DELETE_ALL"
        }
        
        response = self.make_request("DELETE", "/finance/reset-all-data", params=params)
        
        if response and response.status_code == 200:
            self.log_result("Reset All Data", "PASS", "Successfully reset all financial data")
            return True
        else:
            error_msg = f"Failed to reset data. Status: {response.status_code if response else 'No response'}"
            if response:
                try:
                    error_detail = response.json()
                    error_msg += f", Detail: {error_detail}"
                except:
                    error_msg += f", Text: {response.text[:200]}"
            self.log_result("Reset All Data", "FAIL", error_msg)
            return False
            
    def create_sale_operation(self, customer_name, total_amount, payment_method, op_date):
        """Create a sale operation"""
        operation_data = {
            "workshop_id": self.workshop_id,
            "type": "sale",
            "partner_name": customer_name,
            "items": [
                {
                    "name": f"خدمة صيانة لـ {customer_name}",
                    "quantity": 1,
                    "price": total_amount
                }
            ],
            "total": total_amount,
            "paymentMethod": payment_method,
            "op_date": op_date
        }
        
        response = self.make_request("POST", "/operations", operation_data)
        
        if response and response.status_code == 200:
            try:
                result = response.json()
                operation_id = result.get("id")
                if operation_id:
                    self.log_result(f"Create Sale - {customer_name}", "PASS", 
                                  f"Operation created with ID: {operation_id}")
                    return operation_id
                else:
                    self.log_result(f"Create Sale - {customer_name}", "FAIL", 
                                  "No operation ID in response")
                    return None
            except Exception as e:
                self.log_result(f"Create Sale - {customer_name}", "FAIL", 
                              f"Failed to parse response: {e}")
                return None
        else:
            error_msg = f"Failed to create operation. Status: {response.status_code if response else 'No response'}"
            if response:
                try:
                    error_detail = response.json()
                    error_msg += f", Detail: {error_detail}"
                except:
                    error_msg += f", Text: {response.text[:200]}"
            self.log_result(f"Create Sale - {customer_name}", "FAIL", error_msg)
            return None
            
    def confirm_payment(self, operation_id, amount, payment_date):
        """Confirm payment for an operation"""
        payment_data = {
            "amount": amount,
            "payment_date": payment_date,
            "workshopId": self.workshop_id
        }
        
        response = self.make_request("POST", f"/operations/{operation_id}/confirm-payment", payment_data)
        
        if response and response.status_code == 200:
            try:
                result = response.json()
                self.log_result(f"Confirm Payment - {amount} SAR", "PASS", 
                              f"Payment confirmed: {result}")
                return True
            except Exception as e:
                self.log_result(f"Confirm Payment - {amount} SAR", "FAIL", 
                              f"Failed to parse response: {e}")
                return False
        else:
            error_msg = f"Failed to confirm payment. Status: {response.status_code if response else 'No response'}"
            if response:
                try:
                    error_detail = response.json()
                    error_msg += f", Detail: {error_detail}"
                except:
                    error_msg += f", Text: {response.text[:200]}"
            self.log_result(f"Confirm Payment - {amount} SAR", "FAIL", error_msg)
            return False
            
    def execute_june_scenario(self):
        """Execute the June 2024 scenario"""
        print("\n" + "="*60)
        print("📅 STEP 2: EXECUTE JUNE 2024 SCENARIO")
        print("="*60)
        
        # Day 1: أحمد العتيبي - 780 SAR credit sale
        print("\n--- Day 1 (2024-06-01): أحمد العتيبي ---")
        ahmed_op_id = self.create_sale_operation("أحمد العتيبي", 780, "credit", "2024-06-01")
        
        if ahmed_op_id:
            # Confirm payment 400 SAR on 2024-06-01
            self.confirm_payment(ahmed_op_id, 400, "2024-06-01")
            # Confirm payment 200 SAR on 2024-06-15
            self.confirm_payment(ahmed_op_id, 200, "2024-06-15")
            
        # Day 5: محمد القحطاني - 720 SAR credit sale
        print("\n--- Day 5 (2024-06-05): محمد القحطاني ---")
        mohammed_op_id = self.create_sale_operation("محمد القحطاني", 720, "credit", "2024-06-05")
        
        if mohammed_op_id:
            # Confirm payment 720 SAR on 2024-06-20
            self.confirm_payment(mohammed_op_id, 720, "2024-06-20")
            
        # Day 10: سارة الشمري - 330 SAR cash sale (doesn't affect AR)
        print("\n--- Day 10 (2024-06-10): سارة الشمري (Cash Sale) ---")
        self.create_sale_operation("سارة الشمري", 330, "cash", "2024-06-10")
        
        print("\n✅ June 2024 scenario execution completed")
        
    def test_ar_customers(self):
        """Test GET /api/finance/ar/customers"""
        print("\n" + "="*60)
        print("👥 STEP 3: TEST AR CUSTOMERS ENDPOINT")
        print("="*60)
        
        params = {
            "workshop_id": self.workshop_id,
            "as_of": "2024-06-30"
        }
        
        response = self.make_request("GET", "/finance/ar/customers", params=params)
        
        if response and response.status_code == 200:
            try:
                result = response.json()
                print(f"📊 AR Customers Response: {json.dumps(result, ensure_ascii=False, indent=2)}")
                
                # Verify total_ar = 180
                data = result.get("data", {})
                total_ar = data.get("total_ar", 0)
                customers = data.get("customers", [])
                
                if total_ar == 180:
                    self.log_result("AR Customers - Total AR", "PASS", f"Total AR = {total_ar} SAR (Expected: 180)")
                else:
                    self.log_result("AR Customers - Total AR", "FAIL", f"Total AR = {total_ar} SAR (Expected: 180)")
                
                # Verify only أحمد العتيبي with balance 180
                ahmed_found = False
                for customer in customers:
                    customer_name = customer.get("customer", customer.get("customer_name", ""))
                    if customer_name == "أحمد العتيبي":
                        ahmed_found = True
                        balance = customer.get("balance", 0)
                        if balance == 180:
                            self.log_result("AR Customers - أحمد العتيبي Balance", "PASS", 
                                          f"أحمد العتيبي balance = {balance} SAR (Expected: 180)")
                        else:
                            self.log_result("AR Customers - أحمد العتيبي Balance", "FAIL", 
                                          f"أحمد العتيبي balance = {balance} SAR (Expected: 180)")
                        break
                
                if not ahmed_found:
                    self.log_result("AR Customers - أحمد العتيبي Found", "FAIL", 
                                  "أحمد العتيبي not found in AR customers")
                else:
                    self.log_result("AR Customers - أحمد العتيبي Found", "PASS", 
                                  "أحمد العتيبي found in AR customers")
                
                # Verify only one customer with outstanding balance
                customers_with_balance = [c for c in customers if c.get("balance", 0) > 0]
                if len(customers_with_balance) == 1:
                    self.log_result("AR Customers - Count", "PASS", 
                                  f"Only 1 customer with outstanding balance (Expected: 1)")
                else:
                    self.log_result("AR Customers - Count", "FAIL", 
                                  f"{len(customers_with_balance)} customers with outstanding balance (Expected: 1)")
                
            except Exception as e:
                self.log_result("AR Customers - Parse Response", "FAIL", f"Failed to parse response: {e}")
        else:
            error_msg = f"Failed to get AR customers. Status: {response.status_code if response else 'No response'}"
            if response:
                try:
                    error_detail = response.json()
                    error_msg += f", Detail: {error_detail}"
                except:
                    error_msg += f", Text: {response.text[:200]}"
            self.log_result("AR Customers", "FAIL", error_msg)
            
    def test_ar_aging(self):
        """Test GET /api/finance/ar/aging"""
        print("\n" + "="*60)
        print("📈 STEP 4: TEST AR AGING ENDPOINT")
        print("="*60)
        
        params = {
            "workshop_id": self.workshop_id,
            "as_of": "2024-06-30"
        }
        
        response = self.make_request("GET", "/finance/ar/aging", params=params)
        
        if response and response.status_code == 200:
            try:
                result = response.json()
                print(f"📊 AR Aging Response: {json.dumps(result, ensure_ascii=False, indent=2)}")
                
                # Verify total_ar = 180
                data = result.get("data", {})
                total_ar = data.get("total_ar", 0)
                buckets = data.get("buckets", {})
                
                if total_ar == 180:
                    self.log_result("AR Aging - Total AR", "PASS", f"Total AR = {total_ar} SAR (Expected: 180)")
                else:
                    self.log_result("AR Aging - Total AR", "FAIL", f"Total AR = {total_ar} SAR (Expected: 180)")
                
                # Verify 0_30 = 180 (current period)
                aging_0_30 = buckets.get("0_30", 0)
                if aging_0_30 == 180:
                    self.log_result("AR Aging - 0-30 Days", "PASS", f"0-30 days = {aging_0_30} SAR (Expected: 180)")
                else:
                    self.log_result("AR Aging - 0-30 Days", "FAIL", f"0-30 days = {aging_0_30} SAR (Expected: 180)")
                
                # Verify other aging buckets are 0
                aging_31_60 = buckets.get("31_60", 0)
                aging_61_90 = buckets.get("61_90", 0)
                aging_over_90 = buckets.get("90_plus", 0)
                
                if aging_31_60 == 0 and aging_61_90 == 0 and aging_over_90 == 0:
                    self.log_result("AR Aging - Other Buckets", "PASS", 
                                  "All other aging buckets are 0 (Expected)")
                else:
                    self.log_result("AR Aging - Other Buckets", "FAIL", 
                                  f"31-60: {aging_31_60}, 61-90: {aging_61_90}, >90: {aging_over_90} (Expected: all 0)")
                
            except Exception as e:
                self.log_result("AR Aging - Parse Response", "FAIL", f"Failed to parse response: {e}")
        else:
            error_msg = f"Failed to get AR aging. Status: {response.status_code if response else 'No response'}"
            if response:
                try:
                    error_detail = response.json()
                    error_msg += f", Detail: {error_detail}"
                except:
                    error_msg += f", Text: {response.text[:200]}"
            self.log_result("AR Aging", "FAIL", error_msg)
            
    def test_ar_ledger(self):
        """Test GET /api/finance/ar/ledger"""
        print("\n" + "="*60)
        print("📋 STEP 5: TEST AR LEDGER ENDPOINT")
        print("="*60)
        
        params = {
            "workshop_id": self.workshop_id,
            "start_date": "2024-06-01",
            "end_date": "2024-06-30"
        }
        
        response = self.make_request("GET", "/finance/ar/ledger", params=params)
        
        if response and response.status_code == 200:
            try:
                result = response.json()
                print(f"📊 AR Ledger Response: {json.dumps(result, ensure_ascii=False, indent=2)}")
                
                # Verify ending_balance = 180
                data = result.get("data", {})
                ending_balance = data.get("ending_balance", 0)
                if ending_balance == 180:
                    self.log_result("AR Ledger - Ending Balance", "PASS", 
                                  f"Ending balance = {ending_balance} SAR (Expected: 180)")
                else:
                    self.log_result("AR Ledger - Ending Balance", "FAIL", 
                                  f"Ending balance = {ending_balance} SAR (Expected: 180)")
                
                # Verify transactions exist
                transactions = data.get("rows", [])
                if len(transactions) > 0:
                    self.log_result("AR Ledger - Transactions", "PASS", 
                                  f"Found {len(transactions)} transactions")
                else:
                    self.log_result("AR Ledger - Transactions", "FAIL", 
                                  "No transactions found in AR ledger")
                
            except Exception as e:
                self.log_result("AR Ledger - Parse Response", "FAIL", f"Failed to parse response: {e}")
        else:
            error_msg = f"Failed to get AR ledger. Status: {response.status_code if response else 'No response'}"
            if response:
                try:
                    error_detail = response.json()
                    error_msg += f", Detail: {error_detail}"
                except:
                    error_msg += f", Text: {response.text[:200]}"
            self.log_result("AR Ledger", "FAIL", error_msg)
            
    def test_customer_statement(self):
        """Test GET /api/finance/ar/customer-statement"""
        print("\n" + "="*60)
        print("📄 STEP 6: TEST CUSTOMER STATEMENT ENDPOINT")
        print("="*60)
        
        params = {
            "workshop_id": self.workshop_id,
            "customer": "أحمد العتيبي",
            "start_date": "2024-06-01",
            "end_date": "2024-06-30"
        }
        
        response = self.make_request("GET", "/finance/ar/customer-statement", params=params)
        
        if response and response.status_code == 200:
            try:
                result = response.json()
                print(f"📊 Customer Statement Response: {json.dumps(result, ensure_ascii=False, indent=2)}")
                
                # Verify ending_balance = 180
                data = result.get("data", {})
                ending_balance = data.get("ending_balance", 0)
                if ending_balance == 180:
                    self.log_result("Customer Statement - Ending Balance", "PASS", 
                                  f"أحمد العتيبي ending balance = {ending_balance} SAR (Expected: 180)")
                else:
                    self.log_result("Customer Statement - Ending Balance", "FAIL", 
                                  f"أحمد العتيبي ending balance = {ending_balance} SAR (Expected: 180)")
                
                # Verify customer name
                customer_name = data.get("customer", "")
                if customer_name == "أحمد العتيبي":
                    self.log_result("Customer Statement - Customer Name", "PASS", 
                                  f"Customer name = {customer_name} (Expected: أحمد العتيبي)")
                else:
                    self.log_result("Customer Statement - Customer Name", "FAIL", 
                                  f"Customer name = {customer_name} (Expected: أحمد العتيبي)")
                
                # Verify transactions exist
                transactions = data.get("rows", [])
                if len(transactions) > 0:
                    self.log_result("Customer Statement - Transactions", "PASS", 
                                  f"Found {len(transactions)} transactions for أحمد العتيبي")
                else:
                    self.log_result("Customer Statement - Transactions", "FAIL", 
                                  "No transactions found for أحمد العتيبي")
                
            except Exception as e:
                self.log_result("Customer Statement - Parse Response", "FAIL", f"Failed to parse response: {e}")
        else:
            error_msg = f"Failed to get customer statement. Status: {response.status_code if response else 'No response'}"
            if response:
                try:
                    error_detail = response.json()
                    error_msg += f", Detail: {error_detail}"
                except:
                    error_msg += f", Text: {response.text[:200]}"
            self.log_result("Customer Statement", "FAIL", error_msg)
            
    def test_ar_turnover(self):
        """Test GET /api/finance/ar/turnover"""
        print("\n" + "="*60)
        print("🔄 STEP 7: TEST AR TURNOVER ENDPOINT")
        print("="*60)
        
        params = {
            "workshop_id": self.workshop_id,
            "start_date": "2024-06-01",
            "end_date": "2024-06-30",
            "credit_sales_total": 1500  # Total credit sales (780 + 720)
        }
        
        response = self.make_request("GET", "/finance/ar/turnover", params=params)
        
        if response and response.status_code == 200:
            try:
                result = response.json()
                print(f"📊 AR Turnover Response: {json.dumps(result, ensure_ascii=False, indent=2)}")
                
                # Verify closing_receivables = 180
                data = result.get("data", {})
                closing_receivables = data.get("closing_receivables", 0)
                if closing_receivables == 180:
                    self.log_result("AR Turnover - Closing Receivables", "PASS", 
                                  f"Closing receivables = {closing_receivables} SAR (Expected: 180)")
                else:
                    self.log_result("AR Turnover - Closing Receivables", "FAIL", 
                                  f"Closing receivables = {closing_receivables} SAR (Expected: 180)")
                
                # Verify turnover ratio exists
                turnover_ratio = data.get("turnover")
                if turnover_ratio is not None:
                    self.log_result("AR Turnover - Turnover Ratio", "PASS", 
                                  f"Turnover ratio = {turnover_ratio}")
                else:
                    self.log_result("AR Turnover - Turnover Ratio", "FAIL", 
                                  "Turnover ratio not found in response")
                
                # Verify days_sales_outstanding exists
                dso = data.get("days_sales_outstanding")
                if dso is not None:
                    self.log_result("AR Turnover - DSO", "PASS", 
                                  f"Days Sales Outstanding = {dso} days")
                else:
                    self.log_result("AR Turnover - DSO", "FAIL", 
                                  "Days Sales Outstanding not found in response")
                
            except Exception as e:
                self.log_result("AR Turnover - Parse Response", "FAIL", f"Failed to parse response: {e}")
        else:
            error_msg = f"Failed to get AR turnover. Status: {response.status_code if response else 'No response'}"
            if response:
                try:
                    error_detail = response.json()
                    error_msg += f", Detail: {error_detail}"
                except:
                    error_msg += f", Text: {response.text[:200]}"
            self.log_result("AR Turnover", "FAIL", error_msg)
            
    def run_all_tests(self):
        """Run all AR endpoint tests"""
        print("🚀 Starting AR Endpoints Testing")
        print(f"📍 Base URL: {self.base_url}")
        print(f"🏢 Workshop ID: {self.workshop_id}")
        print(f"⏰ Test Started: {datetime.now().isoformat()}")
        
        # Step 1: Reset all data
        if not self.reset_all_data():
            print("❌ Failed to reset data. Stopping tests.")
            return
            
        # Wait a moment for reset to complete
        time.sleep(2)
        
        # Step 2: Execute June scenario
        self.execute_june_scenario()
        
        # Wait a moment for operations to be processed
        time.sleep(3)
        
        # Step 3-7: Test all AR endpoints
        self.test_ar_customers()
        self.test_ar_aging()
        self.test_ar_ledger()
        self.test_customer_statement()
        self.test_ar_turnover()
        
        # Print summary
        self.print_summary()
        
    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*60)
        print("📊 TEST SUMMARY")
        print("="*60)
        
        passed = len([r for r in self.test_results if r["status"] == "PASS"])
        failed = len([r for r in self.test_results if r["status"] == "FAIL"])
        warnings = len([r for r in self.test_results if r["status"] == "WARN"])
        total = len(self.test_results)
        
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"⚠️  Warnings: {warnings}")
        print(f"📊 Total: {total}")
        
        if failed > 0:
            print("\n❌ FAILED TESTS:")
            for result in self.test_results:
                if result["status"] == "FAIL":
                    print(f"   • {result['test']}: {result['details']}")
        
        if failed == 0:
            print("\n🎉 ALL TESTS PASSED! AR endpoints are working correctly.")
        else:
            print(f"\n⚠️  {failed} tests failed. Please review the issues above.")
        
        print(f"\n⏰ Test Completed: {datetime.now().isoformat()}")

if __name__ == "__main__":
    tester = AREndpointsTest()
    tester.run_all_tests()