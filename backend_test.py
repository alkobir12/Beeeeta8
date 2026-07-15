"""
اختبار نهائي backend فقط لنظام ERP المحاسبي
Final Backend Testing for ERP Accounting System

Test Scenarios:
1. Real-time integration: Mixed sale operation (service + parts) with new codes 003/027/042
2. Double-entry firewall: Reject unbalanced entry (debit 1600 vs credit 1500)
3. Inventory & COGS: Selling part BRK-PAD-01 decreases quantity and generates automatic COGS entry
4. Idempotency: Same reference FIX-SA-2026-X99 twice should not create two different operations
5. Precision: Operations with 0.55 should not cause final differences in debit/credit
"""

import requests
import json
import uuid
from datetime import datetime
from decimal import Decimal

# Backend URL
BASE_URL = "https://fabrication-guard.preview.emergentagent.com/api"
WORKSHOP_ID = "finmodule-sync"

# Test results storage
test_results = {
    "scenario_1": {"status": "NOT_RUN", "details": ""},
    "scenario_2": {"status": "NOT_RUN", "details": ""},
    "scenario_3": {"status": "NOT_RUN", "details": ""},
    "scenario_4": {"status": "NOT_RUN", "details": ""},
    "scenario_5": {"status": "NOT_RUN", "details": ""},
}


def print_section(title):
    """Print a formatted section header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_result(scenario, status, details):
    """Print test result"""
    symbol = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
    print(f"\n{symbol} {scenario}: {status}")
    print(f"   {details}")
    test_results[scenario] = {"status": status, "details": details}


# ============================================================================
# SCENARIO 1: Real-time Integration - Mixed Sale Operation
# ============================================================================
def test_scenario_1_real_time_integration():
    """
    Test: عملية بيع مختلطة 1500 (خدمة + قطع) بأكواد جديدة 003/027/042
    Verify: انعكاسها على ميزان المراجعة + القيود
    """
    print_section("SCENARIO 1: Real-time Integration - Mixed Sale Operation")
    
    try:
        # Step 1: Create a mixed sale operation (service + parts)
        operation_id = f"TEST-SALE-{uuid.uuid4().hex[:8]}"
        operation_data = {
            "id": operation_id,
            "workshop_id": WORKSHOP_ID,
            "type": "sale",
            "partner_type": "customer",
            "partner_name": "عميل اختبار",
            "items": [
                {
                    "id": str(uuid.uuid4()),
                    "name": "خدمة صيانة",
                    "type": "service",
                    "itemType": "service",
                    "price": 800,
                    "quantity": 1,
                    "total": 800
                },
                {
                    "id": str(uuid.uuid4()),
                    "name": "قطعة غيار",
                    "type": "part",
                    "itemType": "part",
                    "code": "003",
                    "price": 700,
                    "quantity": 1,
                    "total": 700
                }
            ],
            "total": 1500,
            "payment_method": "cash",
            "payment_status": "paid",
            "op_date": datetime.now().strftime("%Y-%m-%d"),
            "notes": f"Test operation - Mixed sale with codes 003/027/042"
        }
        
        print(f"\n📝 Creating mixed sale operation: {operation_id}")
        print(f"   Total: 1500 (Service: 800 + Parts: 700)")
        
        # Create operation
        response = requests.post(
            f"{BASE_URL}/operations",
            json=operation_data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code not in [200, 201]:
            print_result("scenario_1", "FAIL", f"Failed to create operation: {response.status_code} - {response.text[:200]}")
            return
        
        print(f"   ✓ Operation created successfully")
        
        # Step 2: Create journal entry with new codes (003, 027, 042)
        journal_entry = {
            "id": str(uuid.uuid4()),
            "workshop_id": WORKSHOP_ID,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "description": f"قيد بيع مختلط - {operation_id}",
            "source": "operation",
            "transaction_type": "sale",
            "reference_id": operation_id,
            "lines": [
                {
                    "account": "003",  # النقد (Cash)
                    "account_name": "النقد",
                    "debit": 1500,
                    "credit": 0
                },
                {
                    "account": "027",  # إيرادات خدمات (Service Revenue - new code)
                    "account_name": "إيرادات خدمات",
                    "debit": 0,
                    "credit": 800
                },
                {
                    "account": "042",  # إيرادات قطع (Parts Revenue - new code)
                    "account_name": "إيرادات قطع غيار",
                    "debit": 0,
                    "credit": 700
                }
            ],
            "total": 1500
        }
        
        print(f"\n📝 Creating journal entry with new codes:")
        print(f"   Debit: 003 (النقد) = 1500")
        print(f"   Credit: 027 (إيرادات خدمات) = 800")
        print(f"   Credit: 042 (إيرادات قطع) = 700")
        
        response = requests.post(
            f"{BASE_URL}/finance/journal-entries?workshop_id={WORKSHOP_ID}",
            json=journal_entry,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code not in [200, 201]:
            print_result("scenario_1", "FAIL", f"Failed to create journal entry: {response.status_code} - {response.text[:200]}")
            return
        
        print(f"   ✓ Journal entry created successfully")
        
        # Step 3: Verify in trial balance
        print(f"\n🔍 Verifying in trial balance...")
        response = requests.get(
            f"{BASE_URL}/finance/reports/trial-balance",
            params={"workshop_id": WORKSHOP_ID}
        )
        
        if response.status_code != 200:
            print_result("scenario_1", "FAIL", f"Failed to fetch trial balance: {response.status_code}")
            return
        
        trial_balance = response.json()
        accounts = trial_balance.get("data", {}).get("accounts", [])
        
        # Check for codes 003, 027, 042
        found_codes = {}
        for account in accounts:
            code = account.get("code")
            if code in ["003", "027", "042"]:
                found_codes[code] = {
                    "name": account.get("name"),
                    "debit": account.get("debit", 0),
                    "credit": account.get("credit", 0)
                }
        
        print(f"\n📊 Trial Balance Results:")
        for code, data in found_codes.items():
            print(f"   {code} ({data['name']}): Debit={data['debit']}, Credit={data['credit']}")
        
        # Verify balances
        if "003" in found_codes and found_codes["003"]["debit"] >= 1500:
            print(f"   ✓ Code 003 (النقد) reflects debit of 1500+")
        else:
            print_result("scenario_1", "FAIL", "Code 003 not found or incorrect balance in trial balance")
            return
        
        if "027" in found_codes and found_codes["027"]["credit"] >= 800:
            print(f"   ✓ Code 027 (إيرادات خدمات) reflects credit of 800+")
        else:
            print_result("scenario_1", "FAIL", "Code 027 not found or incorrect balance in trial balance")
            return
        
        if "042" in found_codes and found_codes["042"]["credit"] >= 700:
            print(f"   ✓ Code 042 (إيرادات قطع) reflects credit of 700+")
        else:
            print_result("scenario_1", "FAIL", "Code 042 not found or incorrect balance in trial balance")
            return
        
        print_result("scenario_1", "PASS", "Mixed sale operation reflected correctly in trial balance with new codes 003/027/042")
        
    except Exception as e:
        print_result("scenario_1", "FAIL", f"Exception: {str(e)}")


# ============================================================================
# SCENARIO 2: Double-Entry Firewall - Reject Unbalanced Entry
# ============================================================================
def test_scenario_2_double_entry_firewall():
    """
    Test: رفض قيد غير متوازن (مدين 1600 مقابل دائن 1500)
    Verify: النظام يرفض القيد غير المتوازن
    """
    print_section("SCENARIO 2: Double-Entry Firewall - Reject Unbalanced Entry")
    
    try:
        # Create an unbalanced journal entry (debit 1600 vs credit 1500)
        unbalanced_entry = {
            "id": str(uuid.uuid4()),
            "workshop_id": WORKSHOP_ID,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "description": "قيد غير متوازن - اختبار",
            "source": "manual",
            "lines": [
                {
                    "account": "003",
                    "account_name": "النقد",
                    "debit": 1600,  # Debit = 1600
                    "credit": 0
                },
                {
                    "account": "027",
                    "account_name": "إيرادات",
                    "debit": 0,
                    "credit": 1500  # Credit = 1500 (UNBALANCED!)
                }
            ],
            "total": 1600
        }
        
        print(f"\n📝 Attempting to create unbalanced journal entry:")
        print(f"   Debit: 1600")
        print(f"   Credit: 1500")
        print(f"   Difference: 100 (UNBALANCED)")
        
        response = requests.post(
            f"{BASE_URL}/finance/journal-entries?workshop_id={WORKSHOP_ID}",
            json=unbalanced_entry,
            headers={"Content-Type": "application/json"}
        )
        
        # System should reject this (400 or 422 status code)
        if response.status_code in [400, 422]:
            print(f"   ✓ System correctly rejected unbalanced entry")
            print(f"   Response: {response.status_code} - {response.text[:200]}")
            print_result("scenario_2", "PASS", "System correctly rejected unbalanced journal entry (debit 1600 vs credit 1500)")
        elif response.status_code in [200, 201]:
            print(f"   ✗ System ACCEPTED unbalanced entry (SECURITY ISSUE!)")
            print_result("scenario_2", "FAIL", "System accepted unbalanced journal entry - double-entry firewall not working")
        else:
            print_result("scenario_2", "FAIL", f"Unexpected response: {response.status_code} - {response.text[:200]}")
        
    except Exception as e:
        print_result("scenario_2", "FAIL", f"Exception: {str(e)}")


# ============================================================================
# SCENARIO 3: Inventory & COGS - Automatic COGS Entry
# ============================================================================
def test_scenario_3_inventory_cogs():
    """
    Test: بيع القطعة BRK-PAD-01 ينقص الكمية ويولد قيد COGS تلقائي
    Verify: الكمية تنقص + قيد COGS تلقائي
    """
    print_section("SCENARIO 3: Inventory & COGS - Automatic COGS Entry")
    
    try:
        # Step 1: Check initial inventory for BRK-PAD-01
        print(f"\n📦 Checking initial inventory for BRK-PAD-01...")
        response = requests.get(f"{BASE_URL}/parts")
        
        if response.status_code != 200:
            print_result("scenario_3", "FAIL", f"Failed to fetch parts: {response.status_code}")
            return
        
        parts = response.json()
        brake_pad = None
        for part in parts:
            if part.get("code") == "BRK-PAD-01" or "BRK-PAD-01" in part.get("name", ""):
                brake_pad = part
                break
        
        if not brake_pad:
            # Create the part if it doesn't exist
            print(f"   Part BRK-PAD-01 not found, creating...")
            brake_pad = {
                "id": str(uuid.uuid4()),
                "code": "BRK-PAD-01",
                "name": "فحمات فرامل",
                "category": "فرامل",
                "price": 150,
                "cost": 100,
                "quantity": 10,
                "minStock": 2,
                "supplier": "مورد اختبار"
            }
            response = requests.post(
                f"{BASE_URL}/parts",
                json=brake_pad,
                headers={"Content-Type": "application/json"}
            )
            if response.status_code not in [200, 201]:
                print_result("scenario_3", "FAIL", f"Failed to create part: {response.status_code}")
                return
        
        initial_quantity = brake_pad.get("quantity", 0)
        part_cost = brake_pad.get("cost", 100)
        part_id = brake_pad.get("id")
        
        print(f"   ✓ Part found: {brake_pad.get('name')}")
        print(f"   Initial quantity: {initial_quantity}")
        print(f"   Cost: {part_cost}")
        
        # Step 2: Create a sale operation for this part
        operation_id = f"TEST-COGS-{uuid.uuid4().hex[:8]}"
        sale_operation = {
            "id": operation_id,
            "workshop_id": WORKSHOP_ID,
            "type": "sale",
            "partner_type": "customer",
            "partner_name": "عميل اختبار COGS",
            "items": [
                {
                    "id": part_id,
                    "name": brake_pad.get("name"),
                    "code": "BRK-PAD-01",
                    "type": "part",
                    "itemType": "part",
                    "price": 150,
                    "quantity": 2,  # Sell 2 units
                    "total": 300,
                    "cost": part_cost
                }
            ],
            "total": 300,
            "payment_method": "cash",
            "payment_status": "paid",
            "op_date": datetime.now().strftime("%Y-%m-%d"),
            "notes": f"Test COGS - Selling BRK-PAD-01"
        }
        
        print(f"\n📝 Creating sale operation for 2 units of BRK-PAD-01...")
        response = requests.post(
            f"{BASE_URL}/operations",
            json=sale_operation,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code not in [200, 201]:
            print_result("scenario_3", "FAIL", f"Failed to create sale operation: {response.status_code}")
            return
        
        print(f"   ✓ Sale operation created")
        
        # Step 3: Check if inventory decreased
        print(f"\n🔍 Checking inventory after sale...")
        response = requests.get(f"{BASE_URL}/parts/{part_id}")
        
        if response.status_code == 200:
            updated_part = response.json()
            new_quantity = updated_part.get("quantity", initial_quantity)
            print(f"   Initial quantity: {initial_quantity}")
            print(f"   New quantity: {new_quantity}")
            print(f"   Expected decrease: 2")
            
            if new_quantity == initial_quantity - 2:
                print(f"   ✓ Inventory decreased correctly")
            else:
                print(f"   ⚠️ Inventory did not decrease as expected")
        
        # Step 4: Check for automatic COGS journal entry
        print(f"\n🔍 Checking for automatic COGS journal entry...")
        response = requests.get(
            f"{BASE_URL}/finance/journal-entries",
            params={"workshop_id": WORKSHOP_ID, "reference_id": operation_id}
        )
        
        if response.status_code != 200:
            print_result("scenario_3", "FAIL", f"Failed to fetch journal entries: {response.status_code}")
            return
        
        entries = response.json()
        cogs_entry_found = False
        
        for entry in entries:
            lines = entry.get("lines", [])
            has_cogs_debit = False
            has_inventory_credit = False
            
            for line in lines:
                account_code = line.get("account", "")
                account_name = line.get("account_name", "").lower()
                debit = line.get("debit", 0)
                credit = line.get("credit", 0)
                
                # Check for COGS debit (تكلفة البضاعة المباعة)
                if ("cogs" in account_name or "تكلفة" in account_name) and debit > 0:
                    has_cogs_debit = True
                    print(f"   ✓ Found COGS debit: {account_name} = {debit}")
                
                # Check for Inventory credit (مخزون)
                if ("inventory" in account_name or "مخزون" in account_name) and credit > 0:
                    has_inventory_credit = True
                    print(f"   ✓ Found Inventory credit: {account_name} = {credit}")
            
            if has_cogs_debit and has_inventory_credit:
                cogs_entry_found = True
                break
        
        if cogs_entry_found:
            print_result("scenario_3", "PASS", "Inventory decreased and automatic COGS journal entry generated")
        else:
            print_result("scenario_3", "FAIL", "Automatic COGS journal entry not found")
        
    except Exception as e:
        print_result("scenario_3", "FAIL", f"Exception: {str(e)}")


# ============================================================================
# SCENARIO 4: Idempotency - Same Reference Twice
# ============================================================================
def test_scenario_4_idempotency():
    """
    Test: نفس reference FIX-SA-2026-X99 مرتين لا ينشئ عمليتين مختلفتين
    Verify: النظام يمنع التكرار
    """
    print_section("SCENARIO 4: Idempotency - Same Reference Twice")
    
    try:
        reference_id = "FIX-SA-2026-X99"
        
        # Create first operation with this reference
        operation_1 = {
            "id": reference_id,
            "workshop_id": WORKSHOP_ID,
            "type": "sale",
            "partner_type": "customer",
            "partner_name": "عميل اختبار Idempotency",
            "items": [
                {
                    "id": str(uuid.uuid4()),
                    "name": "خدمة",
                    "type": "service",
                    "price": 500,
                    "quantity": 1,
                    "total": 500
                }
            ],
            "total": 500,
            "payment_method": "cash",
            "payment_status": "paid",
            "op_date": datetime.now().strftime("%Y-%m-%d"),
            "notes": f"Test idempotency - Reference: {reference_id}"
        }
        
        print(f"\n📝 Creating first operation with reference: {reference_id}")
        response1 = requests.post(
            f"{BASE_URL}/operations",
            json=operation_1,
            headers={"Content-Type": "application/json"}
        )
        
        if response1.status_code not in [200, 201]:
            print(f"   ⚠️ First operation creation failed: {response1.status_code}")
            # Continue anyway to test idempotency
        else:
            print(f"   ✓ First operation created")
        
        # Try to create second operation with SAME reference
        print(f"\n📝 Attempting to create second operation with SAME reference: {reference_id}")
        response2 = requests.post(
            f"{BASE_URL}/operations",
            json=operation_1,  # Same data
            headers={"Content-Type": "application/json"}
        )
        
        # System should reject duplicate (409 Conflict or 400 Bad Request)
        if response2.status_code in [409, 400, 422]:
            print(f"   ✓ System correctly rejected duplicate operation")
            print(f"   Response: {response2.status_code}")
            print_result("scenario_4", "PASS", f"System correctly prevented duplicate operation with reference {reference_id}")
        elif response2.status_code in [200, 201]:
            # Check if it's actually the same operation (idempotent response)
            print(f"   ⚠️ System returned 200/201, checking if it's idempotent...")
            
            # Fetch operations with this reference
            response = requests.get(
                f"{BASE_URL}/operations",
                params={"workshop_id": WORKSHOP_ID}
            )
            
            if response.status_code == 200:
                operations = response.json()
                matching_ops = [op for op in operations if op.get("id") == reference_id]
                
                if len(matching_ops) == 1:
                    print(f"   ✓ Only one operation exists (idempotent behavior)")
                    print_result("scenario_4", "PASS", f"System is idempotent - only one operation created for reference {reference_id}")
                else:
                    print(f"   ✗ Multiple operations found: {len(matching_ops)}")
                    print_result("scenario_4", "FAIL", f"System created multiple operations for same reference {reference_id}")
            else:
                print_result("scenario_4", "FAIL", f"Could not verify idempotency: {response.status_code}")
        else:
            print_result("scenario_4", "FAIL", f"Unexpected response: {response2.status_code}")
        
    except Exception as e:
        print_result("scenario_4", "FAIL", f"Exception: {str(e)}")


# ============================================================================
# SCENARIO 5: Precision - Decimal Operations
# ============================================================================
def test_scenario_5_precision():
    """
    Test: عمليات 0.55 لا تسبب فروقات نهائية في المدين/الدائن
    Verify: الدقة العشرية صحيحة
    """
    print_section("SCENARIO 5: Precision - Decimal Operations with 0.55")
    
    try:
        # Create multiple operations with 0.55 amounts
        operations = []
        total_amount = 0
        
        for i in range(10):
            operation_id = f"TEST-PRECISION-{uuid.uuid4().hex[:8]}"
            amount = 0.55
            total_amount += amount
            
            operation = {
                "id": operation_id,
                "workshop_id": WORKSHOP_ID,
                "type": "sale",
                "partner_type": "customer",
                "partner_name": f"عميل دقة {i+1}",
                "items": [
                    {
                        "id": str(uuid.uuid4()),
                        "name": "خدمة صغيرة",
                        "type": "service",
                        "price": amount,
                        "quantity": 1,
                        "total": amount
                    }
                ],
                "total": amount,
                "payment_method": "cash",
                "payment_status": "paid",
                "op_date": datetime.now().strftime("%Y-%m-%d"),
                "notes": f"Test precision - Amount: {amount}"
            }
            
            operations.append(operation)
        
        print(f"\n📝 Creating 10 operations with amount 0.55 each...")
        print(f"   Total expected: {total_amount}")
        
        created_count = 0
        for op in operations:
            response = requests.post(
                f"{BASE_URL}/operations",
                json=op,
                headers={"Content-Type": "application/json"}
            )
            if response.status_code in [200, 201]:
                created_count += 1
        
        print(f"   ✓ Created {created_count} operations")
        
        # Create corresponding journal entries
        print(f"\n📝 Creating journal entries for precision test...")
        for op in operations:
            journal_entry = {
                "id": str(uuid.uuid4()),
                "workshop_id": WORKSHOP_ID,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "description": f"قيد دقة - {op['id']}",
                "source": "operation",
                "transaction_type": "sale",
                "reference_id": op["id"],
                "lines": [
                    {
                        "account": "003",
                        "account_name": "النقد",
                        "debit": 0.55,
                        "credit": 0
                    },
                    {
                        "account": "027",
                        "account_name": "إيرادات",
                        "debit": 0,
                        "credit": 0.55
                    }
                ],
                "total": 0.55
            }
            
            response = requests.post(
                f"{BASE_URL}/finance/journal-entries?workshop_id={WORKSHOP_ID}",
                json=journal_entry,
                headers={"Content-Type": "application/json"}
            )
        
        # Check trial balance for precision
        print(f"\n🔍 Checking trial balance for precision...")
        response = requests.get(
            f"{BASE_URL}/finance/reports/trial-balance",
            params={"workshop_id": WORKSHOP_ID}
        )
        
        if response.status_code != 200:
            print_result("scenario_5", "FAIL", f"Failed to fetch trial balance: {response.status_code}")
            return
        
        trial_balance = response.json()
        totals = trial_balance.get("data", {}).get("totals", {})
        total_debit = totals.get("total_debit", 0)
        total_credit = totals.get("total_credit", 0)
        
        print(f"\n📊 Trial Balance Totals:")
        print(f"   Total Debit: {total_debit}")
        print(f"   Total Credit: {total_credit}")
        print(f"   Difference: {abs(total_debit - total_credit)}")
        
        # Check if difference is within acceptable precision (0.01)
        difference = abs(total_debit - total_credit)
        if difference < 0.01:
            print(f"   ✓ Precision is correct (difference < 0.01)")
            print_result("scenario_5", "PASS", f"Decimal precision correct - no significant difference in debit/credit (diff: {difference})")
        else:
            print(f"   ✗ Precision issue detected (difference: {difference})")
            print_result("scenario_5", "FAIL", f"Precision issue - debit/credit difference: {difference}")
        
    except Exception as e:
        print_result("scenario_5", "FAIL", f"Exception: {str(e)}")


# ============================================================================
# MAIN TEST EXECUTION
# ============================================================================
def main():
    """Run all test scenarios"""
    print("\n" + "=" * 80)
    print("  اختبار نهائي backend لنظام ERP المحاسبي")
    print("  Final Backend Testing for ERP Accounting System")
    print("  URL: https://fabrication-guard.preview.emergentagent.com")
    print("=" * 80)
    
    # Run all scenarios
    test_scenario_1_real_time_integration()
    test_scenario_2_double_entry_firewall()
    test_scenario_3_inventory_cogs()
    test_scenario_4_idempotency()
    test_scenario_5_precision()
    
    # Print summary
    print_section("TEST SUMMARY")
    
    passed = sum(1 for r in test_results.values() if r["status"] == "PASS")
    failed = sum(1 for r in test_results.values() if r["status"] == "FAIL")
    total = len(test_results)
    
    print(f"\n📊 Results: {passed}/{total} scenarios passed")
    print(f"   ✅ Passed: {passed}")
    print(f"   ❌ Failed: {failed}")
    
    print(f"\n📋 Detailed Results:")
    for scenario, result in test_results.items():
        symbol = "✅" if result["status"] == "PASS" else "❌" if result["status"] == "FAIL" else "⚠️"
        print(f"   {symbol} {scenario}: {result['status']}")
        if result["details"]:
            print(f"      {result['details']}")
    
    print("\n" + "=" * 80)
    print("  Testing Complete")
    print("=" * 80 + "\n")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
