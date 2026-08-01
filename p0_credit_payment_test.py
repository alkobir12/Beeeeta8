#!/usr/bin/env python3
"""
P0 Credit Payment Logic Testing Script
اختبار منطق P0 الجديد على باك-إند (مزود Supabase)

Test Sequence:
1. POST /api/operations بعملية بيع paymentMethod=credit وتاريخ محدد 2024-06-01
2. GET /api/finance/journal-entries - تحقق أنه لا يوجد أي قيد reference_id=op_id مباشرة بعد الإنشاء
3. POST /api/operations/{op_id}/confirm-payment بمبلغ 40 وتاريخ 2024-06-15
4. POST /api/operations/{op_id}/confirm-payment بمبلغ 60 وتاريخ 2024-06-15
5. GET journal-entries - تحقق أنه يوجد قيود source=operation_payment وreference_id=op_id وعددها 2
6. DELETE /api/operations/{op_id} - تحقق أن قيود journal_entries المرتبطة حُذفت
7. اختبر DELETE /api/finance/journal-entries/{entry_id} على قيد موجود
"""

import requests
import json
import time
from datetime import datetime

# Configuration
BASE_URL = "https://ar-ledger-ssot.preview.emergentagent.com/api"
WORKSHOP_ID = "finmodule-sync"

class P0CreditPaymentTester:
    def __init__(self):
        self.base_url = BASE_URL
        self.workshop_id = WORKSHOP_ID
        self.session = requests.Session()
        self.test_results = []
        self.operation_id = None
        self.payment_entry_ids = []
        
    def log_result(self, test_name, status, details, response_data=None):
        """Log test result with timestamp"""
        result = {
            "test": test_name,
            "status": status,
            "details": details,
            "timestamp": datetime.now().isoformat(),
            "response_data": response_data
        }
        self.test_results.append(result)
        
        status_icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        print(f"{status_icon} {test_name}: {details}")
        
        if response_data and isinstance(response_data, dict):
            if response_data.get('success') is False:
                print(f"   Error: {response_data.get('message', 'Unknown error')}")
    
    def make_request(self, method, endpoint, data=None, params=None):
        """Make HTTP request with error handling"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method.upper() == "GET":
                response = self.session.get(url, params=params, timeout=30)
            elif method.upper() == "POST":
                response = self.session.post(url, json=data, params=params, timeout=30)
            elif method.upper() == "DELETE":
                response = self.session.delete(url, params=params, timeout=30)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            print(f"🔗 {method} {url}")
            if params:
                print(f"   Params: {params}")
            if data:
                print(f"   Data: {json.dumps(data, indent=2, ensure_ascii=False)}")
            print(f"   Status: {response.status_code}")
            
            # Try to parse JSON response
            try:
                response_data = response.json()
                print(f"   Response: {json.dumps(response_data, indent=2, ensure_ascii=False)[:500]}...")
            except:
                response_data = {"raw_response": response.text[:500]}
                print(f"   Raw Response: {response.text[:200]}...")
            
            return response.status_code, response_data
            
        except requests.exceptions.RequestException as e:
            error_data = {"error": str(e)}
            print(f"❌ Request failed: {e}")
            return 0, error_data
    
    def test_1_create_credit_operation(self):
        """Test 1: إنشاء عملية بيع بالآجل"""
        print("\n" + "="*60)
        print("TEST 1: إنشاء عملية بيع بالآجل (Credit Sale Operation)")
        print("="*60)
        
        operation_data = {
            "workshop_id": self.workshop_id,
            "type": "sale",
            "partner_name": "عميل اختبار P0",
            "items": [
                {
                    "name": "خدمة صيانة اختبار",
                    "quantity": 1,
                    "price": 100.0
                }
            ],
            "total": 100.0,
            "paymentMethod": "credit",  # Use camelCase as expected by Supabase service
            "op_date": "2024-06-01"
        }
        
        status_code, response_data = self.make_request("POST", "/operations", operation_data)
        
        if status_code == 200:
            # Check if response has direct ID or nested in data
            self.operation_id = response_data.get("id") or response_data.get("data", {}).get("id")
            
            if self.operation_id:
                # Check if payment method was set correctly to credit
                payment_method = response_data.get("paymentMethod", "")
                if payment_method == "credit":
                    self.log_result(
                        "Create Credit Operation", 
                        "PASS", 
                        f"Operation created successfully with ID: {self.operation_id}, payment method: {payment_method}",
                        response_data
                    )
                    return True
                else:
                    self.log_result(
                        "Create Credit Operation", 
                        "WARN", 
                        f"Operation created with ID: {self.operation_id}, but payment method is '{payment_method}' instead of 'credit'",
                        response_data
                    )
                    # Continue with test even if payment method is different
                    return True
            else:
                self.log_result(
                    "Create Credit Operation", 
                    "FAIL", 
                    "Operation created but no ID returned",
                    response_data
                )
                return False
        else:
            self.log_result(
                "Create Credit Operation", 
                "FAIL", 
                f"Failed to create operation. Status: {status_code}",
                response_data
            )
            return False
    
    def test_2_verify_no_initial_journal_entry(self):
        """Test 2: التحقق من عدم وجود قيد محاسبي فوري"""
        print("\n" + "="*60)
        print("TEST 2: التحقق من عدم وجود قيد محاسبي فوري")
        print("="*60)
        
        if not self.operation_id:
            self.log_result(
                "Verify No Initial Journal Entry", 
                "SKIP", 
                "No operation ID available from previous test"
            )
            return False
        
        params = {"workshop_id": self.workshop_id}
        status_code, response_data = self.make_request("GET", "/finance/journal-entries", params=params)
        
        if status_code == 200 and response_data.get("success"):
            entries = response_data.get("data", [])
            
            # Check for entries with our operation ID as reference_id
            operation_entries = [
                entry for entry in entries 
                if entry.get("reference_id") == self.operation_id
            ]
            
            if len(operation_entries) == 0:
                self.log_result(
                    "Verify No Initial Journal Entry", 
                    "PASS", 
                    f"✅ Correct: No journal entries found for operation {self.operation_id} (credit operations should not create immediate entries)",
                    {"total_entries": len(entries), "operation_entries": len(operation_entries)}
                )
                return True
            else:
                self.log_result(
                    "Verify No Initial Journal Entry", 
                    "FAIL", 
                    f"❌ Found {len(operation_entries)} journal entries for operation {self.operation_id} - should be 0 for credit operations",
                    {"operation_entries": operation_entries}
                )
                return False
        else:
            self.log_result(
                "Verify No Initial Journal Entry", 
                "FAIL", 
                f"Failed to retrieve journal entries. Status: {status_code}",
                response_data
            )
            return False
    
    def test_3_confirm_payment_40(self):
        """Test 3: تأكيد دفعة جزئية 40 ريال"""
        print("\n" + "="*60)
        print("TEST 3: تأكيد دفعة جزئية 40 ريال")
        print("="*60)
        
        if not self.operation_id:
            self.log_result(
                "Confirm Payment 40", 
                "SKIP", 
                "No operation ID available"
            )
            return False
        
        payment_data = {
            "amount": 40.0,
            "payment_date": "2024-06-15",
            "workshop_id": self.workshop_id
        }
        
        endpoint = f"/operations/{self.operation_id}/confirm-payment"
        status_code, response_data = self.make_request("POST", endpoint, payment_data)
        
        if status_code == 200 and response_data.get("success"):
            self.log_result(
                "Confirm Payment 40", 
                "PASS", 
                "First payment confirmation (40 SAR) successful",
                response_data
            )
            return True
        else:
            self.log_result(
                "Confirm Payment 40", 
                "FAIL", 
                f"Failed to confirm first payment. Status: {status_code}",
                response_data
            )
            return False
    
    def test_4_confirm_payment_60(self):
        """Test 4: تأكيد دفعة جزئية 60 ريال"""
        print("\n" + "="*60)
        print("TEST 4: تأكيد دفعة جزئية 60 ريال")
        print("="*60)
        
        if not self.operation_id:
            self.log_result(
                "Confirm Payment 60", 
                "SKIP", 
                "No operation ID available"
            )
            return False
        
        payment_data = {
            "amount": 60.0,
            "payment_date": "2024-06-15",
            "workshop_id": self.workshop_id
        }
        
        endpoint = f"/operations/{self.operation_id}/confirm-payment"
        status_code, response_data = self.make_request("POST", endpoint, payment_data)
        
        if status_code == 200 and response_data.get("success"):
            self.log_result(
                "Confirm Payment 60", 
                "PASS", 
                "Second payment confirmation (60 SAR) successful",
                response_data
            )
            return True
        else:
            self.log_result(
                "Confirm Payment 60", 
                "FAIL", 
                f"Failed to confirm second payment. Status: {status_code}",
                response_data
            )
            return False
    
    def test_5_verify_payment_journal_entries(self):
        """Test 5: التحقق من وجود قيود الدفع"""
        print("\n" + "="*60)
        print("TEST 5: التحقق من وجود قيود الدفع")
        print("="*60)
        
        if not self.operation_id:
            self.log_result(
                "Verify Payment Journal Entries", 
                "SKIP", 
                "No operation ID available"
            )
            return False
        
        params = {"workshop_id": self.workshop_id}
        status_code, response_data = self.make_request("GET", "/finance/journal-entries", params=params)
        
        if status_code == 200 and response_data.get("success"):
            entries = response_data.get("data", [])
            
            # Find payment entries for our operation
            payment_entries = [
                entry for entry in entries 
                if (entry.get("reference_id") == self.operation_id and 
                    entry.get("source") == "operation_payment")
            ]
            
            if len(payment_entries) == 2:
                # Verify amounts
                amounts = []
                for entry in payment_entries:
                    # Look for debit amounts in the journal lines
                    lines = entry.get("lines", [])
                    for line in lines:
                        if line.get("debit", 0) > 0:
                            amounts.append(line.get("debit"))
                
                expected_amounts = [40.0, 60.0]
                amounts.sort()
                expected_amounts.sort()
                
                if amounts == expected_amounts:
                    self.payment_entry_ids = [entry.get("id") for entry in payment_entries]
                    self.log_result(
                        "Verify Payment Journal Entries", 
                        "PASS", 
                        f"✅ Found 2 payment journal entries with correct amounts: {amounts}",
                        {
                            "payment_entries_count": len(payment_entries),
                            "amounts_found": amounts,
                            "entry_ids": self.payment_entry_ids
                        }
                    )
                    return True
                else:
                    self.log_result(
                        "Verify Payment Journal Entries", 
                        "FAIL", 
                        f"❌ Found 2 entries but amounts don't match. Expected: {expected_amounts}, Found: {amounts}",
                        {"payment_entries": payment_entries}
                    )
                    return False
            else:
                self.log_result(
                    "Verify Payment Journal Entries", 
                    "FAIL", 
                    f"❌ Expected 2 payment journal entries, found {len(payment_entries)}",
                    {"payment_entries": payment_entries}
                )
                return False
        else:
            self.log_result(
                "Verify Payment Journal Entries", 
                "FAIL", 
                f"Failed to retrieve journal entries. Status: {status_code}",
                response_data
            )
            return False
    
    def test_6_delete_operation_cascade(self):
        """Test 6: حذف العملية والتحقق من الحذف المتسلسل"""
        print("\n" + "="*60)
        print("TEST 6: حذف العملية والتحقق من الحذف المتسلسل")
        print("="*60)
        
        if not self.operation_id:
            self.log_result(
                "Delete Operation Cascade", 
                "SKIP", 
                "No operation ID available"
            )
            return False
        
        # First, delete the operation
        endpoint = f"/operations/{self.operation_id}"
        status_code, response_data = self.make_request("DELETE", endpoint)
        
        if status_code == 200 and response_data.get("success"):
            print("   ✅ Operation deleted successfully")
            
            # Wait a moment for cascade deletion
            time.sleep(2)
            
            # Now check if journal entries are also deleted
            params = {"workshop_id": self.workshop_id}
            status_code, response_data = self.make_request("GET", "/finance/journal-entries", params=params)
            
            if status_code == 200 and response_data.get("success"):
                entries = response_data.get("data", [])
                
                # Check if any entries still reference our deleted operation
                remaining_entries = [
                    entry for entry in entries 
                    if entry.get("reference_id") == self.operation_id
                ]
                
                if len(remaining_entries) == 0:
                    self.log_result(
                        "Delete Operation Cascade", 
                        "PASS", 
                        "✅ Operation and all related journal entries deleted successfully (cascade delete working)",
                        {"remaining_entries": len(remaining_entries)}
                    )
                    return True
                else:
                    self.log_result(
                        "Delete Operation Cascade", 
                        "FAIL", 
                        f"❌ Operation deleted but {len(remaining_entries)} journal entries still reference it",
                        {"remaining_entries": remaining_entries}
                    )
                    return False
            else:
                self.log_result(
                    "Delete Operation Cascade", 
                    "FAIL", 
                    "Operation deleted but failed to verify journal entries deletion",
                    response_data
                )
                return False
        else:
            self.log_result(
                "Delete Operation Cascade", 
                "FAIL", 
                f"Failed to delete operation. Status: {status_code}",
                response_data
            )
            return False
    
    def test_7_delete_journal_entry(self):
        """Test 7: اختبار حذف قيد محاسبي مباشر"""
        print("\n" + "="*60)
        print("TEST 7: اختبار حذف قيد محاسبي مباشر")
        print("="*60)
        
        # First, get any existing journal entry to test deletion
        params = {"workshop_id": self.workshop_id}
        status_code, response_data = self.make_request("GET", "/finance/journal-entries", params=params)
        
        if status_code == 200 and response_data.get("success"):
            entries = response_data.get("data", [])
            
            if len(entries) > 0:
                # Pick the first entry for deletion test
                test_entry = entries[0]
                entry_id = test_entry.get("id")
                
                if entry_id:
                    # Test deletion
                    endpoint = f"/finance/journal-entries/{entry_id}"
                    params = {"workshop_id": self.workshop_id}
                    status_code, response_data = self.make_request("DELETE", endpoint, params=params)
                    
                    if status_code == 200:
                        self.log_result(
                            "Delete Journal Entry", 
                            "PASS", 
                            f"✅ Journal entry {entry_id} deleted successfully",
                            response_data
                        )
                        return True
                    else:
                        self.log_result(
                            "Delete Journal Entry", 
                            "FAIL", 
                            f"❌ Failed to delete journal entry {entry_id}. Status: {status_code}",
                            response_data
                        )
                        return False
                else:
                    self.log_result(
                        "Delete Journal Entry", 
                        "SKIP", 
                        "No entry ID found in available journal entries"
                    )
                    return False
            else:
                self.log_result(
                    "Delete Journal Entry", 
                    "SKIP", 
                    "No journal entries available for deletion test"
                )
                return False
        else:
            self.log_result(
                "Delete Journal Entry", 
                "FAIL", 
                f"Failed to retrieve journal entries for deletion test. Status: {status_code}",
                response_data
            )
            return False
    
    def run_all_tests(self):
        """Run all P0 credit payment tests"""
        print("🚀 Starting P0 Credit Payment Logic Tests")
        print(f"📍 Backend URL: {self.base_url}")
        print(f"🏪 Workshop ID: {self.workshop_id}")
        print(f"⏰ Test Started: {datetime.now().isoformat()}")
        
        tests = [
            self.test_1_create_credit_operation,
            self.test_2_verify_no_initial_journal_entry,
            self.test_3_confirm_payment_40,
            self.test_4_confirm_payment_60,
            self.test_5_verify_payment_journal_entries,
            self.test_6_delete_operation_cascade,
            self.test_7_delete_journal_entry
        ]
        
        passed = 0
        failed = 0
        skipped = 0
        
        for test in tests:
            try:
                result = test()
                if result is True:
                    passed += 1
                elif result is False:
                    failed += 1
                else:
                    skipped += 1
            except Exception as e:
                print(f"❌ Test {test.__name__} crashed: {e}")
                failed += 1
        
        # Print summary
        print("\n" + "="*80)
        print("📊 P0 CREDIT PAYMENT LOGIC TEST SUMMARY")
        print("="*80)
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"⚠️ Skipped: {skipped}")
        print(f"📈 Success Rate: {(passed/(passed+failed)*100):.1f}%" if (passed+failed) > 0 else "N/A")
        print(f"⏰ Test Completed: {datetime.now().isoformat()}")
        
        # Print detailed results
        print("\n📋 DETAILED RESULTS:")
        for i, result in enumerate(self.test_results, 1):
            status_icon = "✅" if result["status"] == "PASS" else "❌" if result["status"] == "FAIL" else "⚠️"
            print(f"{i}. {status_icon} {result['test']}: {result['details']}")
        
        return passed, failed, skipped

def main():
    """Main test execution"""
    tester = P0CreditPaymentTester()
    passed, failed, skipped = tester.run_all_tests()
    
    # Exit with appropriate code
    if failed > 0:
        exit(1)
    else:
        exit(0)

if __name__ == "__main__":
    main()