#!/usr/bin/env python3
"""
Backend Testing for Smart POS Journal Entries Feature
Testing POST and GET /api/finance/journal-entries with Smart POS templates
"""

import requests
import json
from datetime import datetime

# Configuration
BACKEND_URL = "https://accounting-engine-6.preview.emergentagent.com/api"
WORKSHOP_ID = "finmodule-sync"

def test_smart_pos_journal_entries():
    """Test Smart POS journal entries with various templates"""
    
    print("=" * 80)
    print("SMART POS JOURNAL ENTRIES BACKEND TESTING")
    print("=" * 80)
    print()
    
    results = {
        "passed": 0,
        "failed": 0,
        "tests": []
    }
    
    # Test 1: POST instant_sale template (balanced entry)
    print("TEST 1: POST instant_sale template (balanced entry)")
    print("-" * 80)
    
    instant_sale_entry = {
        "date": "2026-05-11",
        "description": "بيع فوري [PARTY:أحمد العتيبي] [PARTY_TYPE:customer] [VEHICLE_REF:ABC-1234]",
        "transaction_type": "instant_sale",
        "source": "smart_pos",
        "lines": [
            {
                "account": "003",
                "account_name": "النقدية",
                "debit": 1500.00,
                "credit": 0.00
            },
            {
                "account": "026",
                "account_name": "إيرادات المبيعات",
                "debit": 0.00,
                "credit": 1500.00
            }
        ],
        "total": 1500.00
    }
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/finance/journal-entries",
            params={"workshop_id": WORKSHOP_ID},
            json=instant_sale_entry,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                instant_sale_id = data.get("id")
                print(f"✅ PASS: instant_sale entry created successfully")
                print(f"   Entry ID: {instant_sale_id}")
                print(f"   Message: {data.get('message')}")
                results["passed"] += 1
                results["tests"].append({
                    "name": "POST instant_sale (balanced)",
                    "status": "PASS",
                    "entry_id": instant_sale_id
                })
            else:
                print(f"❌ FAIL: API returned success=False")
                print(f"   Error: {data.get('error')}")
                results["failed"] += 1
                results["tests"].append({
                    "name": "POST instant_sale (balanced)",
                    "status": "FAIL",
                    "error": data.get('error')
                })
        else:
            print(f"❌ FAIL: HTTP {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            results["failed"] += 1
            results["tests"].append({
                "name": "POST instant_sale (balanced)",
                "status": "FAIL",
                "error": f"HTTP {response.status_code}"
            })
    except Exception as e:
        print(f"❌ FAIL: Exception - {str(e)}")
        results["failed"] += 1
        results["tests"].append({
            "name": "POST instant_sale (balanced)",
            "status": "FAIL",
            "error": str(e)
        })
    
    print()
    
    # Test 2: POST salary template (balanced entry)
    print("TEST 2: POST salary template (balanced entry)")
    print("-" * 80)
    
    salary_entry = {
        "date": "2026-05-11",
        "description": "صرف راتب [PARTY:محمد السالم] [PARTY_TYPE:employee]",
        "transaction_type": "salary",
        "source": "smart_pos",
        "lines": [
            {
                "account": "031",
                "account_name": "رواتب وأجور",
                "debit": 5000.00,
                "credit": 0.00
            },
            {
                "account": "003",
                "account_name": "النقدية",
                "debit": 0.00,
                "credit": 5000.00
            }
        ],
        "total": 5000.00
    }
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/finance/journal-entries",
            params={"workshop_id": WORKSHOP_ID},
            json=salary_entry,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                salary_id = data.get("id")
                print(f"✅ PASS: salary entry created successfully")
                print(f"   Entry ID: {salary_id}")
                results["passed"] += 1
                results["tests"].append({
                    "name": "POST salary (balanced)",
                    "status": "PASS",
                    "entry_id": salary_id
                })
            else:
                print(f"❌ FAIL: API returned success=False")
                results["failed"] += 1
                results["tests"].append({
                    "name": "POST salary (balanced)",
                    "status": "FAIL",
                    "error": data.get('error')
                })
        else:
            print(f"❌ FAIL: HTTP {response.status_code}")
            results["failed"] += 1
            results["tests"].append({
                "name": "POST salary (balanced)",
                "status": "FAIL",
                "error": f"HTTP {response.status_code}"
            })
    except Exception as e:
        print(f"❌ FAIL: Exception - {str(e)}")
        results["failed"] += 1
        results["tests"].append({
            "name": "POST salary (balanced)",
            "status": "FAIL",
            "error": str(e)
        })
    
    print()
    
    # Test 3: POST collect_customer template (balanced entry)
    print("TEST 3: POST collect_customer template (balanced entry)")
    print("-" * 80)
    
    collect_customer_entry = {
        "date": "2026-05-11",
        "description": "تحصيل من عميل [PARTY:فهد الدوسري] [PARTY_TYPE:customer]",
        "transaction_type": "collect_customer",
        "source": "smart_pos",
        "lines": [
            {
                "account": "003",
                "account_name": "النقدية",
                "debit": 2500.00,
                "credit": 0.00
            },
            {
                "account": "005",
                "account_name": "ذمم مدينة - عملاء",
                "debit": 0.00,
                "credit": 2500.00
            }
        ],
        "total": 2500.00
    }
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/finance/journal-entries",
            params={"workshop_id": WORKSHOP_ID},
            json=collect_customer_entry,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                collect_id = data.get("id")
                print(f"✅ PASS: collect_customer entry created successfully")
                print(f"   Entry ID: {collect_id}")
                results["passed"] += 1
                results["tests"].append({
                    "name": "POST collect_customer (balanced)",
                    "status": "PASS",
                    "entry_id": collect_id
                })
            else:
                print(f"❌ FAIL: API returned success=False")
                results["failed"] += 1
                results["tests"].append({
                    "name": "POST collect_customer (balanced)",
                    "status": "FAIL",
                    "error": data.get('error')
                })
        else:
            print(f"❌ FAIL: HTTP {response.status_code}")
            results["failed"] += 1
            results["tests"].append({
                "name": "POST collect_customer (balanced)",
                "status": "FAIL",
                "error": f"HTTP {response.status_code}"
            })
    except Exception as e:
        print(f"❌ FAIL: Exception - {str(e)}")
        results["failed"] += 1
        results["tests"].append({
            "name": "POST collect_customer (balanced)",
            "status": "FAIL",
            "error": str(e)
        })
    
    print()
    
    # Test 4: POST pay_supplier template (balanced entry)
    print("TEST 4: POST pay_supplier template (balanced entry)")
    print("-" * 80)
    
    pay_supplier_entry = {
        "date": "2026-05-11",
        "description": "سداد لمورد [PARTY:شركة قطع الغيار المتحدة] [PARTY_TYPE:supplier]",
        "transaction_type": "pay_supplier",
        "source": "smart_pos",
        "lines": [
            {
                "account": "211",
                "account_name": "ذمم دائنة - موردون",
                "debit": 3500.00,
                "credit": 0.00
            },
            {
                "account": "003",
                "account_name": "النقدية",
                "debit": 0.00,
                "credit": 3500.00
            }
        ],
        "total": 3500.00
    }
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/finance/journal-entries",
            params={"workshop_id": WORKSHOP_ID},
            json=pay_supplier_entry,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                pay_supplier_id = data.get("id")
                print(f"✅ PASS: pay_supplier entry created successfully")
                print(f"   Entry ID: {pay_supplier_id}")
                results["passed"] += 1
                results["tests"].append({
                    "name": "POST pay_supplier (balanced)",
                    "status": "PASS",
                    "entry_id": pay_supplier_id
                })
            else:
                print(f"❌ FAIL: API returned success=False")
                results["failed"] += 1
                results["tests"].append({
                    "name": "POST pay_supplier (balanced)",
                    "status": "FAIL",
                    "error": data.get('error')
                })
        else:
            print(f"❌ FAIL: HTTP {response.status_code}")
            results["failed"] += 1
            results["tests"].append({
                "name": "POST pay_supplier (balanced)",
                "status": "FAIL",
                "error": f"HTTP {response.status_code}"
            })
    except Exception as e:
        print(f"❌ FAIL: Exception - {str(e)}")
        results["failed"] += 1
        results["tests"].append({
            "name": "POST pay_supplier (balanced)",
            "status": "FAIL",
            "error": str(e)
        })
    
    print()
    
    # Test 5: POST unbalanced entry (should be rejected)
    print("TEST 5: POST unbalanced entry (should be REJECTED)")
    print("-" * 80)
    
    unbalanced_entry = {
        "date": "2026-05-11",
        "description": "قيد غير متوازن - اختبار الرفض",
        "transaction_type": "test",
        "source": "smart_pos",
        "lines": [
            {
                "account": "003",
                "account_name": "النقدية",
                "debit": 1000.00,
                "credit": 0.00
            },
            {
                "account": "026",
                "account_name": "إيرادات المبيعات",
                "debit": 0.00,
                "credit": 800.00  # Intentionally unbalanced
            }
        ],
        "total": 1000.00
    }
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/finance/journal-entries",
            params={"workshop_id": WORKSHOP_ID},
            json=unbalanced_entry,
            timeout=10
        )
        
        if response.status_code == 400:
            data = response.json()
            if "غير متوازن" in data.get("detail", ""):
                print(f"✅ PASS: Unbalanced entry correctly REJECTED")
                print(f"   Error message: {data.get('detail')}")
                results["passed"] += 1
                results["tests"].append({
                    "name": "POST unbalanced entry (rejection)",
                    "status": "PASS",
                    "note": "Correctly rejected unbalanced entry"
                })
            else:
                print(f"❌ FAIL: Rejected but wrong error message")
                print(f"   Detail: {data.get('detail')}")
                results["failed"] += 1
                results["tests"].append({
                    "name": "POST unbalanced entry (rejection)",
                    "status": "FAIL",
                    "error": "Wrong error message"
                })
        elif response.status_code == 200:
            print(f"❌ FAIL: Unbalanced entry was ACCEPTED (should be rejected)")
            results["failed"] += 1
            results["tests"].append({
                "name": "POST unbalanced entry (rejection)",
                "status": "FAIL",
                "error": "Unbalanced entry was accepted"
            })
        else:
            print(f"⚠️  UNEXPECTED: HTTP {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            results["failed"] += 1
            results["tests"].append({
                "name": "POST unbalanced entry (rejection)",
                "status": "FAIL",
                "error": f"Unexpected HTTP {response.status_code}"
            })
    except Exception as e:
        print(f"❌ FAIL: Exception - {str(e)}")
        results["failed"] += 1
        results["tests"].append({
            "name": "POST unbalanced entry (rejection)",
            "status": "FAIL",
            "error": str(e)
        })
    
    print()
    
    # Test 6: GET journal entries and verify Smart POS entries
    print("TEST 6: GET journal entries and verify Smart POS entries")
    print("-" * 80)
    
    try:
        response = requests.get(
            f"{BACKEND_URL}/finance/journal-entries",
            params={
                "workshop_id": WORKSHOP_ID,
                "limit": 100
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                entries = data.get("data", [])
                print(f"✅ PASS: GET journal entries successful")
                print(f"   Total entries retrieved: {len(entries)}")
                
                # Find Smart POS entries
                smart_pos_entries = [e for e in entries if e.get("source") == "smart_pos"]
                print(f"   Smart POS entries found: {len(smart_pos_entries)}")
                
                # Verify tokens in descriptions
                token_checks = {
                    "PARTY": 0,
                    "PARTY_TYPE": 0,
                    "VEHICLE_REF": 0
                }
                
                for entry in smart_pos_entries:
                    desc = entry.get("description", "")
                    if "[PARTY:" in desc:
                        token_checks["PARTY"] += 1
                    if "[PARTY_TYPE:" in desc:
                        token_checks["PARTY_TYPE"] += 1
                    if "[VEHICLE_REF:" in desc:
                        token_checks["VEHICLE_REF"] += 1
                    
                    # Verify balance
                    lines = entry.get("lines", [])
                    total_debit = sum(line.get("debit", 0) for line in lines)
                    total_credit = sum(line.get("credit", 0) for line in lines)
                    
                    if abs(total_debit - total_credit) > 0.01:
                        print(f"   ⚠️  Entry {entry.get('id')} is UNBALANCED: debit={total_debit}, credit={total_credit}")
                
                print(f"   Token usage:")
                print(f"     - [PARTY:...] tokens: {token_checks['PARTY']}")
                print(f"     - [PARTY_TYPE:...] tokens: {token_checks['PARTY_TYPE']}")
                print(f"     - [VEHICLE_REF:...] tokens: {token_checks['VEHICLE_REF']}")
                
                results["passed"] += 1
                results["tests"].append({
                    "name": "GET journal entries",
                    "status": "PASS",
                    "total_entries": len(entries),
                    "smart_pos_entries": len(smart_pos_entries),
                    "tokens": token_checks
                })
            else:
                print(f"❌ FAIL: API returned success=False")
                results["failed"] += 1
                results["tests"].append({
                    "name": "GET journal entries",
                    "status": "FAIL",
                    "error": data.get('error')
                })
        else:
            print(f"❌ FAIL: HTTP {response.status_code}")
            results["failed"] += 1
            results["tests"].append({
                "name": "GET journal entries",
                "status": "FAIL",
                "error": f"HTTP {response.status_code}"
            })
    except Exception as e:
        print(f"❌ FAIL: Exception - {str(e)}")
        results["failed"] += 1
        results["tests"].append({
            "name": "GET journal entries",
            "status": "FAIL",
            "error": str(e)
        })
    
    print()
    
    # Test 7: Verify debit/credit balance in all entries
    print("TEST 7: Verify debit/credit balance in all Smart POS entries")
    print("-" * 80)
    
    try:
        response = requests.get(
            f"{BACKEND_URL}/finance/journal-entries",
            params={
                "workshop_id": WORKSHOP_ID,
                "limit": 100
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            entries = data.get("data", [])
            smart_pos_entries = [e for e in entries if e.get("source") == "smart_pos"]
            
            all_balanced = True
            unbalanced_count = 0
            
            for entry in smart_pos_entries:
                lines = entry.get("lines", [])
                total_debit = sum(line.get("debit", 0) for line in lines)
                total_credit = sum(line.get("credit", 0) for line in lines)
                
                if abs(total_debit - total_credit) > 0.01:
                    all_balanced = False
                    unbalanced_count += 1
                    print(f"   ⚠️  UNBALANCED: Entry {entry.get('id')[:8]}...")
                    print(f"      Debit: {total_debit:.2f}, Credit: {total_credit:.2f}")
            
            if all_balanced:
                print(f"✅ PASS: All Smart POS entries are balanced")
                print(f"   Checked {len(smart_pos_entries)} entries")
                results["passed"] += 1
                results["tests"].append({
                    "name": "Verify debit/credit balance",
                    "status": "PASS",
                    "entries_checked": len(smart_pos_entries)
                })
            else:
                print(f"❌ FAIL: Found {unbalanced_count} unbalanced entries")
                results["failed"] += 1
                results["tests"].append({
                    "name": "Verify debit/credit balance",
                    "status": "FAIL",
                    "unbalanced_count": unbalanced_count
                })
        else:
            print(f"❌ FAIL: HTTP {response.status_code}")
            results["failed"] += 1
            results["tests"].append({
                "name": "Verify debit/credit balance",
                "status": "FAIL",
                "error": f"HTTP {response.status_code}"
            })
    except Exception as e:
        print(f"❌ FAIL: Exception - {str(e)}")
        results["failed"] += 1
        results["tests"].append({
            "name": "Verify debit/credit balance",
            "status": "FAIL",
            "error": str(e)
        })
    
    print()
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Total Tests: {results['passed'] + results['failed']}")
    print(f"✅ Passed: {results['passed']}")
    print(f"❌ Failed: {results['failed']}")
    print()
    
    if results['failed'] == 0:
        print("🎉 ALL TESTS PASSED - SMART POS BACKEND FULLY FUNCTIONAL")
    else:
        print("⚠️  SOME TESTS FAILED - SEE DETAILS ABOVE")
    
    print("=" * 80)
    
    return results

if __name__ == "__main__":
    test_smart_pos_journal_entries()
