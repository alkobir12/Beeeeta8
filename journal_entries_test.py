#!/usr/bin/env python3
"""
Journal Entries Transaction Type Testing Script
Tests: Manual journal entries with transaction_type field support in Supabase
"""

import requests
import json
import sys
from datetime import datetime
import uuid

# Get backend URL from environment
BACKEND_URL = "https://canonical-integrity.preview.emergentagent.com/api"
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
    print("JOURNAL ENTRIES TRANSACTION_TYPE TEST SUMMARY")
    print("="*80)
    print(f"Total Tests: {test_results['total']}")
    print(f"Passed: {len(test_results['passed'])} ✅")
    print(f"Failed: {len(test_results['failed'])} ❌")
    
    if test_results['failed']:
        print("\nFailed Tests:")
        for test in test_results['failed']:
            print(f"  - {test}")
    
    success_rate = len(test_results['passed']) / test_results['total'] * 100 if test_results['total'] > 0 else 0
    print(f"\nSuccess Rate: {success_rate:.1f}%")

def test_create_manual_journal_entry():
    """Test 1: Create manual journal entry with transaction_type"""
    print("\n🧪 Test 1: Creating manual journal entry with transaction_type='purchase'")
    
    # Prepare test data
    journal_entry_data = {
        "date": "2026-01-25",
        "description": "اختبار قيد شراء يدوي",
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
        url = f"{BACKEND_URL}/finance/journal-entries?workshop_id={WORKSHOP_ID}"
        print(f"POST {url}")
        print(f"Body: {json.dumps(journal_entry_data, ensure_ascii=False, indent=2)}")
        
        response = requests.post(url, json=journal_entry_data)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response: {json.dumps(data, ensure_ascii=False, indent=2)}")
            
            if data.get("success"):
                entry_id = data.get("id")
                if entry_id:
                    log_test("Create manual journal entry", True, f"Created entry with ID: {entry_id}")
                    return entry_id
                else:
                    log_test("Create manual journal entry", False, "No ID returned in response")
                    return None
            else:
                log_test("Create manual journal entry", False, f"Success=false: {data.get('message', 'Unknown error')}")
                return None
        else:
            error_text = response.text
            log_test("Create manual journal entry", False, f"HTTP {response.status_code}: {error_text}")
            return None
            
    except Exception as e:
        log_test("Create manual journal entry", False, f"Exception: {str(e)}")
        return None

def test_retrieve_journal_entries(created_entry_id=None):
    """Test 2: Retrieve journal entries and verify transaction_type field"""
    print("\n🧪 Test 2: Retrieving journal entries and checking transaction_type field")
    
    try:
        url = f"{BACKEND_URL}/finance/journal-entries?workshop_id={WORKSHOP_ID}&limit=10"
        print(f"GET {url}")
        
        response = requests.get(url)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response: {json.dumps(data, ensure_ascii=False, indent=2)}")
            
            if data.get("success"):
                entries = data.get("data", [])
                print(f"Found {len(entries)} journal entries")
                
                # Look for our created entry
                created_entry_found = False
                transaction_type_found = False
                source_manual_found = False
                
                for entry in entries:
                    print(f"\nEntry ID: {entry.get('id')}")
                    print(f"Description: {entry.get('description')}")
                    print(f"Transaction Type: {entry.get('transaction_type')}")
                    print(f"Source: {entry.get('source')}")
                    
                    # Check if this is our created entry
                    if created_entry_id and entry.get('id') == created_entry_id:
                        created_entry_found = True
                        print("✓ Found our created entry")
                        
                        # Check transaction_type field
                        if entry.get('transaction_type') == 'purchase':
                            transaction_type_found = True
                            print("✓ transaction_type field exists and has correct value 'purchase'")
                        else:
                            print(f"✗ transaction_type field missing or incorrect: {entry.get('transaction_type')}")
                        
                        # Check source field
                        if entry.get('source') == 'manual':
                            source_manual_found = True
                            print("✓ source field exists and has correct value 'manual'")
                        else:
                            print(f"✗ source field missing or incorrect: {entry.get('source')}")
                
                # Log test results
                if created_entry_id:
                    log_test("Find created journal entry", created_entry_found, 
                           f"Entry ID {created_entry_id} {'found' if created_entry_found else 'not found'}")
                    log_test("Verify transaction_type field", transaction_type_found,
                           f"transaction_type = 'purchase' {'found' if transaction_type_found else 'not found'}")
                    log_test("Verify source field", source_manual_found,
                           f"source = 'manual' {'found' if source_manual_found else 'not found'}")
                else:
                    # Just check if any entries have transaction_type field
                    has_transaction_type = any(entry.get('transaction_type') is not None for entry in entries)
                    log_test("Journal entries have transaction_type field", has_transaction_type,
                           f"Found {len([e for e in entries if e.get('transaction_type')])} entries with transaction_type")
                
                return entries
            else:
                log_test("Retrieve journal entries", False, f"Success=false: {data.get('message', 'Unknown error')}")
                return []
        else:
            error_text = response.text
            log_test("Retrieve journal entries", False, f"HTTP {response.status_code}: {error_text}")
            return []
            
    except Exception as e:
        log_test("Retrieve journal entries", False, f"Exception: {str(e)}")
        return []

def test_update_journal_entry(entry_id):
    """Test 3: Update journal entry transaction_type"""
    print(f"\n🧪 Test 3: Updating journal entry {entry_id} transaction_type to 'sale'")
    
    if not entry_id:
        log_test("Update journal entry", False, "No entry ID provided")
        return False
    
    try:
        url = f"{BACKEND_URL}/finance/journal-entries/{entry_id}?workshop_id={WORKSHOP_ID}"
        update_data = {
            "transaction_type": "sale"
        }
        
        print(f"PUT {url}")
        print(f"Body: {json.dumps(update_data, ensure_ascii=False, indent=2)}")
        
        response = requests.put(url, json=update_data)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response: {json.dumps(data, ensure_ascii=False, indent=2)}")
            
            if data.get("success"):
                log_test("Update journal entry transaction_type", True, "Successfully updated to 'sale'")
                return True
            else:
                log_test("Update journal entry transaction_type", False, f"Success=false: {data.get('message', 'Unknown error')}")
                return False
        else:
            error_text = response.text
            log_test("Update journal entry transaction_type", False, f"HTTP {response.status_code}: {error_text}")
            return False
            
    except Exception as e:
        log_test("Update journal entry transaction_type", False, f"Exception: {str(e)}")
        return False

def test_verify_updated_entry(entry_id):
    """Test 4: Verify updated transaction_type"""
    print(f"\n🧪 Test 4: Verifying updated transaction_type for entry {entry_id}")
    
    if not entry_id:
        log_test("Verify updated transaction_type", False, "No entry ID provided")
        return False
    
    try:
        url = f"{BACKEND_URL}/finance/journal-entries?workshop_id={WORKSHOP_ID}&limit=10"
        print(f"GET {url}")
        
        response = requests.get(url)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get("success"):
                entries = data.get("data", [])
                
                # Find our updated entry
                for entry in entries:
                    if entry.get('id') == entry_id:
                        transaction_type = entry.get('transaction_type')
                        print(f"Found entry {entry_id}")
                        print(f"Current transaction_type: {transaction_type}")
                        
                        if transaction_type == 'sale':
                            log_test("Verify updated transaction_type", True, "transaction_type successfully updated to 'sale'")
                            return True
                        else:
                            log_test("Verify updated transaction_type", False, f"transaction_type is '{transaction_type}', expected 'sale'")
                            return False
                
                log_test("Verify updated transaction_type", False, f"Entry {entry_id} not found")
                return False
            else:
                log_test("Verify updated transaction_type", False, f"Success=false: {data.get('message', 'Unknown error')}")
                return False
        else:
            error_text = response.text
            log_test("Verify updated transaction_type", False, f"HTTP {response.status_code}: {error_text}")
            return False
            
    except Exception as e:
        log_test("Verify updated transaction_type", False, f"Exception: {str(e)}")
        return False

def main():
    """Main test execution"""
    print("🚀 Starting Journal Entries Transaction Type Tests")
    print(f"Backend URL: {BACKEND_URL}")
    print(f"Workshop ID: {WORKSHOP_ID}")
    print("="*80)
    
    # Test 1: Create manual journal entry with transaction_type
    created_entry_id = test_create_manual_journal_entry()
    
    # Test 2: Retrieve and verify transaction_type field
    entries = test_retrieve_journal_entries(created_entry_id)
    
    # Test 3 & 4: Update and verify (optional tests)
    if created_entry_id:
        print("\n📝 Running optional update tests...")
        update_success = test_update_journal_entry(created_entry_id)
        if update_success:
            test_verify_updated_entry(created_entry_id)
    else:
        print("\n⚠️ Skipping update tests - no entry ID available")
    
    # Print final summary
    print_summary()
    
    # Return exit code based on results
    if test_results['failed']:
        print(f"\n❌ Some tests failed. Check the issues above.")
        return 1
    else:
        print(f"\n✅ All tests passed! Journal entries transaction_type functionality is working correctly.")
        return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)