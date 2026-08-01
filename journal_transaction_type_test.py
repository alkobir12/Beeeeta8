#!/usr/bin/env python3
"""
Journal Entries Transaction Type Testing Script
Testing transaction_type field in journal_entries table after Supabase schema update
"""

import requests
import json
import sys
from datetime import datetime

# Get backend URL from environment
BACKEND_URL = "https://ar-ledger-ssot.preview.emergentagent.com/api"
WORKSHOP_ID = "finmodule-sync"

# Test results tracking
test_results = {
    "passed": [],
    "failed": [],
    "total": 0
}

def log_test(name, passed, details=""):
    """Log test result"""
    test_results["total"] += 1
    if passed:
        test_results["passed"].append(name)
        print(f"✅ {name}")
        if details:
            print(f"   {details}")
    else:
        test_results["failed"].append(name)
        print(f"❌ {name}")
        if details:
            print(f"   {details}")

def print_summary():
    """Print test summary"""
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Total Tests: {test_results['total']}")
    print(f"Passed: {len(test_results['passed'])} ✅")
    print(f"Failed: {len(test_results['failed'])} ❌")
    
    if test_results['failed']:
        print("\nFailed Tests:")
        for test in test_results['failed']:
            print(f"  - {test}")
    
    print("="*80)

def test_journal_entries_transaction_type():
    """Test journal entries transaction_type field functionality"""
    print("\n" + "="*80)
    print("TESTING JOURNAL ENTRIES TRANSACTION_TYPE FIELD")
    print("اختبار حقل transaction_type في جدول journal_entries")
    print("="*80)
    
    created_entry_id = None
    
    # Test 1: Create manual journal entry with transaction_type: "purchase"
    print("\n[1] Testing POST /api/finance/journal-entries (Create with transaction_type: purchase)")
    
    journal_entry_data = {
        "date": "2026-01-25",
        "description": "اختبار قيد شراء يدوي بعد إضافة العمود",
        "transaction_type": "purchase",
        "lines": [
            {
                "account": "514",
                "account_name": "مصروفات قطع غيار",
                "debit": 500,
                "credit": 0
            },
            {
                "account": "101",
                "account_name": "النقدية",
                "debit": 0,
                "credit": 500
            }
        ],
        "total": 500
    }
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/finance/journal-entries?workshop_id={WORKSHOP_ID}",
            json=journal_entry_data,
            timeout=15
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                created_entry_id = data.get('id')
                log_test("Create journal entry with transaction_type: purchase", True,
                        f"Entry ID: {created_entry_id}")
            else:
                log_test("Create journal entry with transaction_type: purchase", False,
                        f"Success=False: {data.get('message', 'No message')}")
        else:
            log_test("Create journal entry with transaction_type: purchase", False,
                    f"Status: {response.status_code}, Response: {response.text[:300]}")
    except Exception as e:
        log_test("Create journal entry with transaction_type: purchase", False, f"Error: {str(e)}")
    
    # Test 2: Retrieve journal entries and verify the new entry
    print("\n[2] Testing GET /api/finance/journal-entries (Verify new entry)")
    
    try:
        response = requests.get(
            f"{BACKEND_URL}/finance/journal-entries?workshop_id={WORKSHOP_ID}&limit=10",
            timeout=15
        )
        
        if response.status_code == 200:
            response_data = response.json()
            entries = response_data.get('data', [])  # Use 'data' instead of 'entries'
            
            # Find our created entry
            found_entry = None
            if created_entry_id:
                for entry in entries:
                    if entry.get('id') == created_entry_id:
                        found_entry = entry
                        break
            
            if found_entry:
                transaction_type = found_entry.get('transaction_type')
                source = found_entry.get('source')
                
                if transaction_type == "purchase" and source == "manual":
                    log_test("Verify entry transaction_type and source", True,
                            f"transaction_type: {transaction_type}, source: {source}")
                else:
                    log_test("Verify entry transaction_type and source", False,
                            f"Expected transaction_type=purchase, source=manual. Got transaction_type={transaction_type}, source={source}")
            else:
                log_test("Verify entry transaction_type and source", False,
                        f"Entry with ID {created_entry_id} not found in retrieved entries")
        else:
            log_test("Verify entry transaction_type and source", False,
                    f"Status: {response.status_code}, Response: {response.text[:300]}")
    except Exception as e:
        log_test("Verify entry transaction_type and source", False, f"Error: {str(e)}")
    
    # Test 3: Update the journal entry to change transaction_type to "sale"
    if created_entry_id:
        print("\n[3] Testing PUT /api/finance/journal-entries/{id} (Update transaction_type to sale)")
        
        update_data = {
            "date": "2026-01-26",
            "description": "تعديل نوع الحركة إلى بيع",
            "transaction_type": "sale",
            "lines": [
                {
                    "account": "411",
                    "account_name": "إيرادات خدمات الصيانة",
                    "debit": 0,
                    "credit": 800
                },
                {
                    "account": "113",
                    "account_name": "ذمم مدينة عملاء",
                    "debit": 800,
                    "credit": 0
                }
            ],
            "total": 800
        }
        
        try:
            response = requests.put(
                f"{BACKEND_URL}/finance/journal-entries/{created_entry_id}?workshop_id={WORKSHOP_ID}",
                json=update_data,
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    log_test("Update journal entry transaction_type to sale", True,
                            f"Updated entry ID: {created_entry_id}")
                else:
                    log_test("Update journal entry transaction_type to sale", False,
                            f"Success=False: {data.get('message', 'No message')}")
            else:
                log_test("Update journal entry transaction_type to sale", False,
                        f"Status: {response.status_code}, Response: {response.text[:300]}")
        except Exception as e:
            log_test("Update journal entry transaction_type to sale", False, f"Error: {str(e)}")
    else:
        log_test("Update journal entry transaction_type to sale", False, "Skipped - no entry created")
    
    # Test 4: Retrieve entries again and verify the update
    if created_entry_id:
        print("\n[4] Testing GET /api/finance/journal-entries (Verify updated transaction_type)")
        
        try:
            response = requests.get(
                f"{BACKEND_URL}/finance/journal-entries?workshop_id={WORKSHOP_ID}&limit=10",
                timeout=15
            )
            
            if response.status_code == 200:
                response_data = response.json()
                entries = response_data.get('data', [])  # Use 'data' instead of 'entries'
                
                # Find our updated entry
                found_entry = None
                for entry in entries:
                    if entry.get('id') == created_entry_id:
                        found_entry = entry
                        break
                
                if found_entry:
                    transaction_type = found_entry.get('transaction_type')
                    
                    if transaction_type == "sale":
                        log_test("Verify updated transaction_type is sale", True,
                                f"transaction_type successfully updated to: {transaction_type}")
                    else:
                        log_test("Verify updated transaction_type is sale", False,
                                f"Expected transaction_type=sale. Got transaction_type={transaction_type}")
                else:
                    log_test("Verify updated transaction_type is sale", False,
                            f"Entry with ID {created_entry_id} not found in retrieved entries")
            else:
                log_test("Verify updated transaction_type is sale", False,
                        f"Status: {response.status_code}, Response: {response.text[:300]}")
        except Exception as e:
            log_test("Verify updated transaction_type is sale", False, f"Error: {str(e)}")
    else:
        log_test("Verify updated transaction_type is sale", False, "Skipped - no entry created")

def main():
    """Main test execution"""
    print("\n" + "="*80)
    print("JOURNAL ENTRIES TRANSACTION_TYPE FIELD TESTING")
    print("اختبار حقل transaction_type في جدول journal_entries")
    print("="*80)
    print(f"Backend URL: {BACKEND_URL}")
    print(f"Workshop ID: {WORKSHOP_ID}")
    print(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    # Run the test
    test_journal_entries_transaction_type()
    
    # Print summary
    print_summary()
    
    # Generate final report
    print("\n" + "="*80)
    print("FINAL REPORT - تقرير نهائي")
    print("="*80)
    
    if len(test_results['failed']) == 0:
        print("✅ جميع الاختبارات نجحت - All tests passed!")
        print("✅ حقل transaction_type يعمل بشكل صحيح:")
        print("   - يتم حفظه عند إنشاء قيد جديد")
        print("   - يتم قراءته عند استرجاع القيود")
        print("   - يتم تحديثه بنجاح")
        print("✅ The transaction_type field works correctly:")
        print("   - Saves properly when creating new entries")
        print("   - Reads properly when retrieving entries")
        print("   - Updates successfully")
    else:
        print("❌ بعض الاختبارات فشلت - Some tests failed")
        print("❌ حقل transaction_type قد يحتاج إلى مراجعة")
        print("❌ The transaction_type field may need review")
    
    print("="*80)
    
    # Exit with appropriate code
    if test_results['failed']:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()