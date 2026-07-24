#!/usr/bin/env python3
"""
Test Accrual Posting Scenarios with New Chart-of-Accounts Codes
Testing the updated accounting posting logic to use new chart-of-accounts codes and accrual basis.

Test scope:
1) Create CASH purchase operation with accountId=acc-1201 (equipment asset) total=5000, paymentMethod=cash, type=purchase, workshopId=finmodule-sync. Verify a journal entry exists with source=operation, reference_id=op_id, lines: debit account 1201, credit cash (1101) for 5000.
2) Create CASH purchase operation with accountId=acc-6100 (operating expense) total=1200 paymentMethod=cash. Verify JE: Dr 6100, Cr 1101.
3) Create BANK salary operation as purchase with accountId=acc-6101 total=3000 paymentMethod=transfer. Verify JE: Dr 6101, Cr 1102.
4) Create owner draw as purchase with accountId=acc-3102 total=2000 paymentMethod=cash. Verify JE: Dr 3102, Cr 1101 AND that income statement does NOT treat equity accounts as expenses (net income should not change because of this entry).
5) Create CREDIT sale operation total=1500 paymentMethod=credit type=sale. Verify JE created immediately (accrual): Dr 1103, Cr 4100.
6) Confirm payment for the credit sale via POST /api/operations/{op_id}/confirm-payment with amount=1500 and date. Verify journal entry source=operation_payment: Dr 1101 or 1102 based on payment_method, Cr 1103.

Also verify cash-flow report uses 1101+1102 by creating a date range covering tests and checking /api/finance/reports/cash-flow has non-zero operating cash.

Ensure cleanup: delete created operations and linked journal entries (cascade delete by reference_id) after assertions.
"""

import pytest
import requests
import json
import os
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Configuration
BACKEND_URL = os.getenv("REACT_APP_BACKEND_URL", "https://stamp-approval-flow.preview.emergentagent.com") + "/api"
WORKSHOP_ID = "finmodule-sync"

class TestAccrualPostingScenarios:
    """Test class for accrual posting scenarios with new COA codes"""
    
    def setup_method(self):
        """Setup for each test method"""
        self.created_operations = []
        self.created_journal_entries = []
        self.test_date = datetime.now().strftime("%Y-%m-%d")
        
    def teardown_method(self):
        """Cleanup after each test method"""
        # Delete created operations (should cascade delete journal entries)
        for op_id in self.created_operations:
            try:
                response = requests.delete(f"{BACKEND_URL}/operations/{op_id}")
                print(f"Deleted operation {op_id}: {response.status_code}")
            except Exception as e:
                print(f"Failed to delete operation {op_id}: {e}")
        
        # Delete any remaining journal entries
        for entry_id in self.created_journal_entries:
            try:
                response = requests.delete(
                    f"{BACKEND_URL}/finance/journal-entries/{entry_id}",
                    params={"workshop_id": WORKSHOP_ID}
                )
                print(f"Deleted journal entry {entry_id}: {response.status_code}")
            except Exception as e:
                print(f"Failed to delete journal entry {entry_id}: {e}")
    
    def create_operation(self, operation_data: Dict[str, Any]) -> Dict[str, Any]:
        """Helper to create an operation and track it for cleanup"""
        response = requests.post(f"{BACKEND_URL}/operations", json=operation_data, timeout=30)
        assert response.status_code in [200, 201], f"Failed to create operation: {response.status_code} - {response.text}"
        
        op_data = response.json()
        op_id = op_data.get("id")
        assert op_id, "Operation ID not returned"
        
        self.created_operations.append(op_id)
        return op_data
    
    def get_journal_entries_for_operation(self, op_id: str) -> List[Dict[str, Any]]:
        """Get journal entries linked to an operation"""
        response = requests.get(
            f"{BACKEND_URL}/finance/journal-entries",
            params={"workshop_id": WORKSHOP_ID, "limit": 100},
            timeout=30
        )
        assert response.status_code == 200, f"Failed to get journal entries: {response.status_code}"
        
        data = response.json()
        entries = data.get("data", [])
        
        # Filter entries for this operation
        operation_entries = [
            entry for entry in entries 
            if entry.get("reference_id") == op_id or 
               (entry.get("source") == "operation" and entry.get("reference_id") == op_id)
        ]
        
        return operation_entries
    
    def verify_journal_entry_lines(self, entry: Dict[str, Any], expected_lines: List[Dict[str, Any]]):
        """Verify journal entry has expected debit/credit lines"""
        actual_lines = entry.get("lines", [])
        assert len(actual_lines) == len(expected_lines), f"Expected {len(expected_lines)} lines, got {len(actual_lines)}"
        
        # Sort both by account code for comparison
        actual_sorted = sorted(actual_lines, key=lambda x: x.get("account", ""))
        expected_sorted = sorted(expected_lines, key=lambda x: x.get("account", ""))
        
        for actual, expected in zip(actual_sorted, expected_sorted):
            assert actual.get("account") == expected.get("account"), f"Account mismatch: {actual.get('account')} != {expected.get('account')}"
            assert abs(float(actual.get("debit", 0)) - float(expected.get("debit", 0))) < 0.01, f"Debit mismatch for account {expected.get('account')}"
            assert abs(float(actual.get("credit", 0)) - float(expected.get("credit", 0))) < 0.01, f"Credit mismatch for account {expected.get('account')}"
    
    def test_cash_equipment_purchase(self):
        """Test 1: CASH purchase operation with accountingAccountId=acc-1201 (equipment asset) total=5000 - should post directly to 1201"""
        print("\n🧪 Test 1: Cash Equipment Purchase (direct posting to 1201 via accountingAccountId)")
        
        operation_data = {
            "type": "purchase",
            "accountingAccountId": "acc-1201",  # Equipment asset account
            "workshopId": WORKSHOP_ID,
            "partnerType": "supplier",
            "partnerName": "معدات الورشة المحدودة",
            "items": [
                {
                    "itemType": "equipment",
                    "name": "رافعة هيدروليكية",
                    "quantity": 1,
                    "price": 5000.0
                }
            ],
            "total": 5000.0,
            "paymentMethod": "cash",
            "notes": "شراء معدات نقداً",
            "date": self.test_date
        }
        
        # Create operation
        op_data = self.create_operation(operation_data)
        op_id = op_data["id"]
        
        # Verify journal entry was created with selected account (1201)
        entries = self.get_journal_entries_for_operation(op_id)
        assert len(entries) >= 1, "No journal entry created for cash purchase"
        
        entry = entries[0]
        assert entry.get("source") == "operation", f"Expected source=operation, got {entry.get('source')}"
        assert entry.get("reference_id") == op_id, "Journal entry not linked to operation"
        assert abs(float(entry.get("total", 0)) - 5000.0) < 0.01, "Journal entry total mismatch"
        
        # Verify lines: Dr 1201 (Equipment), Cr 1101 (Cash)
        # The system should now use the selected debit account (1201) instead of defaulting to 6100
        expected_lines = [
            {"account": "1201", "debit": 5000.0, "credit": 0.0},
            {"account": "1101", "debit": 0.0, "credit": 5000.0}
        ]
        self.verify_journal_entry_lines(entry, expected_lines)
        
        print("✅ Cash equipment purchase journal entry verified (direct posting to 1201)")
    
    def test_operations_post_accepts_accounting_account_id(self):
        """Test: Operations POST accepts accountingAccountId and posting uses it"""
        print("\n🧪 Test: Operations POST accepts accountingAccountId parameter")
        
        operation_data = {
            "type": "purchase",
            "accountingAccountId": "acc-6101",  # Using accountingAccountId instead of accountId
            "workshopId": WORKSHOP_ID,
            "partnerType": "employee",
            "partnerName": "رواتب الموظفين - اختبار accountingAccountId",
            "items": [
                {
                    "itemType": "salary",
                    "name": "راتب شهر يناير",
                    "quantity": 1,
                    "price": 2500.0
                }
            ],
            "total": 2500.0,
            "paymentMethod": "cash",
            "notes": "اختبار accountingAccountId parameter",
            "date": self.test_date
        }
        
        # Create operation
        op_data = self.create_operation(operation_data)
        op_id = op_data["id"]
        
        # Verify journal entry was created with selected account from accountingAccountId
        entries = self.get_journal_entries_for_operation(op_id)
        assert len(entries) >= 1, "No journal entry created for operation with accountingAccountId"
        
        entry = entries[0]
        assert entry.get("source") == "operation", f"Expected source=operation, got {entry.get('source')}"
        assert entry.get("reference_id") == op_id, "Journal entry not linked to operation"
        assert abs(float(entry.get("total", 0)) - 2500.0) < 0.01, "Journal entry total mismatch"
        
        # Verify lines: Dr 6101 (from accountingAccountId), Cr 1101 (Cash)
        expected_lines = [
            {"account": "6101", "debit": 2500.0, "credit": 0.0},
            {"account": "1101", "debit": 0.0, "credit": 2500.0}
        ]
        self.verify_journal_entry_lines(entry, expected_lines)
        
        print("✅ Operations POST accepts accountingAccountId and uses it for posting")
    
    def test_cash_operating_expense(self):
        """Test 2: CASH purchase operation (operating expense) total=1200 - should default to 6100"""
        print("\n🧪 Test 2: Cash Operating Expense (defaults to 6100)")
        
        operation_data = {
            "type": "purchase",
            # Note: Without accountId, system defaults to 6100 for purchases (operating expense)
            "workshopId": WORKSHOP_ID,
            "partnerType": "supplier",
            "partnerName": "مواد التنظيف والصيانة",
            "items": [
                {
                    "itemType": "supplies",
                    "name": "مواد تنظيف ومستلزمات",
                    "quantity": 1,
                    "price": 1200.0
                }
            ],
            "total": 1200.0,
            "paymentMethod": "cash",
            "notes": "مصروفات تشغيلية نقداً",
            "date": self.test_date
        }
        
        # Create operation
        op_data = self.create_operation(operation_data)
        op_id = op_data["id"]
        
        # Verify journal entry was created
        entries = self.get_journal_entries_for_operation(op_id)
        assert len(entries) >= 1, "No journal entry created for cash operating expense"
        
        entry = entries[0]
        assert entry.get("source") == "operation", f"Expected source=operation, got {entry.get('source')}"
        assert entry.get("reference_id") == op_id, "Journal entry not linked to operation"
        assert abs(float(entry.get("total", 0)) - 1200.0) < 0.01, "Journal entry total mismatch"
        
        # Verify lines: Dr 6100 (Operating Expense), Cr 1101 (Cash)
        expected_lines = [
            {"account": "6100", "debit": 1200.0, "credit": 0.0},
            {"account": "1101", "debit": 0.0, "credit": 1200.0}
        ]
        self.verify_journal_entry_lines(entry, expected_lines)
        
        print("✅ Cash operating expense journal entry verified")
    
    def test_bank_salary_expense(self):
        """Test 3: BANK salary operation with accountingAccountId=acc-6101 total=3000 paymentMethod=transfer - should post directly to 6101"""
        print("\n🧪 Test 3: Bank Salary Expense (direct posting to 6101 via accountingAccountId)")
        
        operation_data = {
            "type": "purchase",
            "accountingAccountId": "acc-6101",  # Salary expense account
            "workshopId": WORKSHOP_ID,
            "partnerType": "employee",
            "partnerName": "رواتب الموظفين",
            "items": [
                {
                    "itemType": "salary",
                    "name": "راتب شهر ديسمبر",
                    "quantity": 1,
                    "price": 3000.0
                }
            ],
            "total": 3000.0,
            "paymentMethod": "transfer",  # Bank transfer
            "notes": "رواتب عبر التحويل البنكي",
            "date": self.test_date
        }
        
        # Create operation
        op_data = self.create_operation(operation_data)
        op_id = op_data["id"]
        
        # Verify journal entry was created with selected account (6101)
        entries = self.get_journal_entries_for_operation(op_id)
        assert len(entries) >= 1, "No journal entry created for bank purchase"
        
        entry = entries[0]
        assert entry.get("source") == "operation", f"Expected source=operation, got {entry.get('source')}"
        assert entry.get("reference_id") == op_id, "Journal entry not linked to operation"
        assert abs(float(entry.get("total", 0)) - 3000.0) < 0.01, "Journal entry total mismatch"
        
        # Verify lines: Dr 6101 (Salary Expense), Cr 1102 (Bank)
        # The system should now use the selected debit account (6101) instead of defaulting to 6100
        expected_lines = [
            {"account": "6101", "debit": 3000.0, "credit": 0.0},
            {"account": "1102", "debit": 0.0, "credit": 3000.0}
        ]
        self.verify_journal_entry_lines(entry, expected_lines)
        
        print("✅ Bank salary expense journal entry verified (direct posting to 6101)")
    
    def test_owner_draw_cash(self):
        """Test 4: Owner draw with accountingAccountId=acc-3102 total=2000 paymentMethod=cash - should post directly to 3102"""
        print("\n🧪 Test 4: Owner Draw Cash (direct posting to 3102 via accountingAccountId)")
        
        operation_data = {
            "type": "purchase",
            "accountingAccountId": "acc-3102",  # Owner draw account
            "workshopId": WORKSHOP_ID,
            "partnerType": "owner",
            "partnerName": "مسحوبات المالك",
            "items": [
                {
                    "itemType": "draw",
                    "name": "مسحوبات شخصية",
                    "quantity": 1,
                    "price": 2000.0
                }
            ],
            "total": 2000.0,
            "paymentMethod": "cash",
            "notes": "مسحوبات المالك نقداً",
            "date": self.test_date
        }
        
        # Create operation
        op_data = self.create_operation(operation_data)
        op_id = op_data["id"]
        
        # Verify journal entry was created with selected account (3102)
        entries = self.get_journal_entries_for_operation(op_id)
        assert len(entries) >= 1, "No journal entry created for owner draw"
        
        entry = entries[0]
        assert entry.get("source") == "operation", f"Expected source=operation, got {entry.get('source')}"
        assert entry.get("reference_id") == op_id, "Journal entry not linked to operation"
        assert abs(float(entry.get("total", 0)) - 2000.0) < 0.01, "Journal entry total mismatch"
        
        # Verify lines: Dr 3102 (Owner Draw), Cr 1101 (Cash)
        # The system should now use the selected debit account (3102) instead of defaulting to 6100
        expected_lines = [
            {"account": "3102", "debit": 2000.0, "credit": 0.0},
            {"account": "1101", "debit": 0.0, "credit": 2000.0}
        ]
        self.verify_journal_entry_lines(entry, expected_lines)
        
        # Verify income statement does NOT treat equity accounts as expenses
        # Get income statement for the test period
        start_date = self.test_date
        end_date = self.test_date
        
        response = requests.get(
            f"{BACKEND_URL}/finance/reports/income-statement",
            params={
                "workshop_id": WORKSHOP_ID,
                "start_date": start_date,
                "end_date": end_date
            },
            timeout=30
        )
        assert response.status_code == 200, f"Failed to get income statement: {response.status_code}"
        
        income_data = response.json()
        assert income_data.get("success"), "Income statement request failed"
        
        # Owner draw (3102) should NOT appear in expenses
        expense_accounts = income_data.get("data", {}).get("details", {}).get("expenses_by_account", {})
        assert "3102" not in expense_accounts, "Owner draw (3102) incorrectly treated as expense in income statement"
        
        print("✅ Owner draw journal entry verified (direct posting to 3102) and confirmed not in income statement expenses")
    
    def test_credit_sale_accrual(self):
        """Test 5: CREDIT sale operation total=1500 paymentMethod=credit type=sale"""
        print("\n🧪 Test 5: Credit Sale Accrual (immediate JE)")
        
        operation_data = {
            "type": "sale",
            "workshopId": WORKSHOP_ID,
            "partnerType": "customer",
            "partnerName": "عميل آجل تجريبي",
            "items": [
                {
                    "itemType": "service",
                    "name": "خدمة صيانة شاملة",
                    "quantity": 1,
                    "price": 1500.0
                }
            ],
            "total": 1500.0,
            "paymentMethod": "credit",  # Credit sale
            "notes": "بيع آجل - اختبار الاستحقاق",
            "date": self.test_date
        }
        
        # Create operation
        op_data = self.create_operation(operation_data)
        op_id = op_data["id"]
        
        # Verify journal entry was created immediately (accrual basis)
        entries = self.get_journal_entries_for_operation(op_id)
        assert len(entries) >= 1, "No journal entry created for credit sale (accrual basis)"
        
        entry = entries[0]
        assert entry.get("source") == "operation", f"Expected source=operation, got {entry.get('source')}"
        assert entry.get("reference_id") == op_id, "Journal entry not linked to operation"
        assert abs(float(entry.get("total", 0)) - 1500.0) < 0.01, "Journal entry total mismatch"
        
        # Verify lines: Dr 1103 (AR), Cr 4100 (Revenue)
        expected_lines = [
            {"account": "1103", "debit": 1500.0, "credit": 0.0},
            {"account": "4100", "debit": 0.0, "credit": 1500.0}
        ]
        self.verify_journal_entry_lines(entry, expected_lines)
        
        print("✅ Credit sale accrual journal entry verified")
        
        # Store operation ID for payment confirmation test
        self.credit_sale_op_id = op_id
    
    def test_credit_sale_payment_confirmation(self):
        """Test 6: Confirm payment for credit sale via POST /api/operations/{op_id}/confirm-payment"""
        print("\n🧪 Test 6: Credit Sale Payment Confirmation")
        
        # First create a credit sale
        self.test_credit_sale_accrual()
        op_id = self.credit_sale_op_id
        
        # Confirm payment
        payment_data = {
            "workshopId": WORKSHOP_ID,
            "amount": 1500.0,
            "date": self.test_date
        }
        
        response = requests.post(
            f"{BACKEND_URL}/operations/{op_id}/confirm-payment",
            json=payment_data,
            timeout=30
        )
        assert response.status_code == 200, f"Failed to confirm payment: {response.status_code} - {response.text}"
        
        payment_result = response.json()
        assert payment_result.get("success"), "Payment confirmation failed"
        
        # Verify payment journal entry was created
        response = requests.get(
            f"{BACKEND_URL}/finance/journal-entries",
            params={"workshop_id": WORKSHOP_ID, "limit": 100},
            timeout=30
        )
        assert response.status_code == 200, "Failed to get journal entries"
        
        data = response.json()
        entries = data.get("data", [])
        
        # Find payment entry
        payment_entries = [
            entry for entry in entries 
            if entry.get("source") == "operation_payment" and entry.get("reference_id") == op_id
        ]
        assert len(payment_entries) >= 1, "No payment journal entry created"
        
        payment_entry = payment_entries[0]
        assert abs(float(payment_entry.get("total", 0)) - 1500.0) < 0.01, "Payment entry total mismatch"
        
        # Verify lines: Dr 1101 (Cash), Cr 1103 (AR)
        expected_lines = [
            {"account": "1101", "debit": 1500.0, "credit": 0.0},
            {"account": "1103", "debit": 0.0, "credit": 1500.0}
        ]
        self.verify_journal_entry_lines(payment_entry, expected_lines)
        
        print("✅ Credit sale payment confirmation journal entry verified")
    
    def test_cash_flow_report_integration(self):
        """Test cash-flow report uses 1101+1102 and shows non-zero operating cash"""
        print("\n🧪 Test 7: Cash Flow Report Integration")
        
        # Create some cash transactions first
        self.test_cash_equipment_purchase()
        self.test_cash_operating_expense() 
        self.test_bank_salary_expense()
        
        # Get cash flow report
        start_date = self.test_date
        end_date = self.test_date
        
        response = requests.get(
            f"{BACKEND_URL}/finance/reports/cash-flow",
            params={
                "workshop_id": WORKSHOP_ID,
                "start_date": start_date,
                "end_date": end_date
            },
            timeout=30
        )
        assert response.status_code == 200, f"Failed to get cash flow report: {response.status_code}"
        
        cash_flow_data = response.json()
        assert cash_flow_data.get("success"), "Cash flow report request failed"
        
        # Verify operating activities show non-zero cash flows
        operating = cash_flow_data.get("data", {}).get("operating_activities", {})
        
        # Should have cash outflows from our test transactions
        cash_to_suppliers = abs(float(operating.get("cash_to_suppliers", 0)))
        cash_for_salaries = abs(float(operating.get("cash_for_salaries", 0)))
        
        # We created cash purchases (1200) + equipment (5000) + salary via bank (3000)
        # Equipment should be in investing, salary in operating, supplies in operating
        assert cash_to_suppliers > 0 or cash_for_salaries > 0, "Cash flow report shows no operating cash movements"
        
        print(f"✅ Cash flow report verified - Suppliers: {cash_to_suppliers}, Salaries: {cash_for_salaries}")
    
    def test_full_accrual_posting_scenario(self):
        """Run all accrual posting scenarios in sequence"""
        print("\n🚀 Running Full Accrual Posting Scenarios Test Suite")
        print(f"🌐 Backend URL: {BACKEND_URL}")
        print(f"🏪 Workshop ID: {WORKSHOP_ID}")
        print(f"📅 Test Date: {self.test_date}")
        
        # Run all individual tests
        self.test_cash_equipment_purchase()
        self.test_operations_post_accepts_accounting_account_id()
        self.test_cash_operating_expense()
        self.test_bank_salary_expense()
        self.test_owner_draw_cash()
        self.test_credit_sale_payment_confirmation()  # This includes credit sale test
        self.test_cash_flow_report_integration()
        
        print("\n🎉 All accrual posting scenarios completed successfully!")


def run_accrual_posting_tests():
    """Run the accrual posting tests"""
    test_instance = TestAccrualPostingScenarios()
    
    try:
        test_instance.setup_method()
        test_instance.test_full_accrual_posting_scenario()
        print("\n✅ All tests passed!")
        return True
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        return False
    finally:
        test_instance.teardown_method()


if __name__ == "__main__":
    success = run_accrual_posting_tests()
    exit(0 if success else 1)