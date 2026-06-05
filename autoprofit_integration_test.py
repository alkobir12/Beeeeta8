#!/usr/bin/env python3
"""
AutoProfit Pro Financial Integration Testing
اختبار ربط العمليات بالنظام المالي AutoProfit Pro

Test Objective (Arabic):
اختبار ربط العمليات بالنظام المالي AutoProfit Pro بعد التعديلات الأخيرة:
1) اختبار إنشاء عملية جديدة عبر API
2) بعد إنشاء العملية مباشرةً، استدعاء endpoints المالية
3) تحقق من تغيّر قيم الإيرادات والأصول والدخل الصافي والنسب المالية
4) سجّل snapshot قبل وبعد للقيم الرئيسية
"""

import requests
import json
import sys
from datetime import datetime

# Backend URL from environment
BACKEND_URL = "https://garage-erp-arabic.preview.emergentagent.com/api"

# Test results tracking
test_results = {
    "passed": [],
    "failed": [],
    "total": 0,
    "snapshots": {}
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
    print("AUTOPROFIT PRO INTEGRATION TEST SUMMARY")
    print("="*80)
    print(f"Total Tests: {test_results['total']}")
    print(f"Passed: {len(test_results['passed'])} ✅")
    print(f"Failed: {len(test_results['failed'])} ❌")
    
    if test_results['failed']:
        print("\nFailed Tests:")
        for test in test_results['failed']:
            print(f"  - {test}")
    
    print("="*80)

def capture_financial_snapshot(label):
    """Capture financial data snapshot"""
    print(f"\n📊 Capturing financial snapshot: {label}")
    snapshot = {
        "timestamp": datetime.now().isoformat(),
        "balance_sheet": None,
        "financial_ratios": None,
        "profit_loss": None
    }
    
    # Get Balance Sheet Summary
    try:
        response = requests.get(f"{BACKEND_URL}/accounts-chart/balance-sheet/summary", timeout=10)
        if response.status_code == 200:
            snapshot["balance_sheet"] = response.json()
            print(f"   ✓ Balance Sheet: Assets={snapshot['balance_sheet'].get('assets')}, Revenue={snapshot['balance_sheet'].get('revenue')}")
        else:
            print(f"   ❌ Balance Sheet failed: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Balance Sheet error: {str(e)}")
    
    # Get Financial Ratios
    try:
        response = requests.get(f"{BACKEND_URL}/analytics-advanced/financial-ratios", timeout=10)
        if response.status_code == 200:
            snapshot["financial_ratios"] = response.json()
            ratios = snapshot["financial_ratios"].get("ratios", {})
            print(f"   ✓ Financial Ratios: Current={ratios.get('current_ratio')}, Net Margin={ratios.get('net_margin')}")
        else:
            print(f"   ❌ Financial Ratios failed: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Financial Ratios error: {str(e)}")
    
    # Get Profit & Loss
    try:
        response = requests.get(f"{BACKEND_URL}/analytics-advanced/profit-loss", timeout=10)
        if response.status_code == 200:
            snapshot["profit_loss"] = response.json()
            print(f"   ✓ Profit & Loss: Revenue={snapshot['profit_loss'].get('revenue', {}).get('total')}, Net Profit={snapshot['profit_loss'].get('net_profit')}")
        else:
            print(f"   ❌ Profit & Loss failed: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Profit & Loss error: {str(e)}")
    
    test_results["snapshots"][label] = snapshot
    return snapshot

def compare_snapshots(before, after):
    """Compare financial snapshots and report changes"""
    print("\n📈 FINANCIAL CHANGES ANALYSIS:")
    print("="*60)
    
    changes_detected = False
    
    # Compare Balance Sheet
    if before["balance_sheet"] and after["balance_sheet"]:
        before_bs = before["balance_sheet"]
        after_bs = after["balance_sheet"]
        
        print("Balance Sheet Changes:")
        for key in ["assets", "liabilities", "revenue", "net_income"]:
            before_val = before_bs.get(key, 0)
            after_val = after_bs.get(key, 0)
            change = after_val - before_val
            if change != 0:
                changes_detected = True
                print(f"  • {key}: {before_val} → {after_val} (Change: {change:+.2f})")
            else:
                print(f"  • {key}: {before_val} (No change)")
    
    # Compare Profit & Loss
    if before["profit_loss"] and after["profit_loss"]:
        before_pl = before["profit_loss"]
        after_pl = after["profit_loss"]
        
        print("\nProfit & Loss Changes:")
        # Revenue changes
        before_revenue = before_pl.get("revenue", {}).get("total", 0)
        after_revenue = after_pl.get("revenue", {}).get("total", 0)
        revenue_change = after_revenue - before_revenue
        if revenue_change != 0:
            changes_detected = True
            print(f"  • Total Revenue: {before_revenue} → {after_revenue} (Change: {revenue_change:+.2f})")
        else:
            print(f"  • Total Revenue: {before_revenue} (No change)")
        
        # Net profit changes
        before_profit = before_pl.get("net_profit", 0)
        after_profit = after_pl.get("net_profit", 0)
        profit_change = after_profit - before_profit
        if profit_change != 0:
            changes_detected = True
            print(f"  • Net Profit: {before_profit} → {after_profit} (Change: {profit_change:+.2f})")
        else:
            print(f"  • Net Profit: {before_profit} (No change)")
    
    # Compare Financial Ratios
    if before["financial_ratios"] and after["financial_ratios"]:
        before_ratios = before["financial_ratios"].get("ratios", {})
        after_ratios = after["financial_ratios"].get("ratios", {})
        
        print("\nFinancial Ratios Changes:")
        for key in ["current_ratio", "quick_ratio", "gross_margin", "net_margin"]:
            before_val = before_ratios.get(key, 0)
            after_val = after_ratios.get(key, 0)
            change = after_val - before_val
            if abs(change) > 0.001:  # Small threshold for float comparison
                changes_detected = True
                print(f"  • {key}: {before_val} → {after_val} (Change: {change:+.4f})")
            else:
                print(f"  • {key}: {before_val} (No change)")
    
    print("="*60)
    
    if changes_detected:
        print("✅ FINANCIAL INTEGRATION WORKING: Changes detected after operation creation")
        return True
    else:
        print("⚠️  NO FINANCIAL CHANGES: Operation may not be integrated with financial system")
        return False

def test_autoprofit_integration():
    """Test AutoProfit Pro financial integration"""
    print("\n" + "="*80)
    print("TESTING AUTOPROFIT PRO FINANCIAL INTEGRATION")
    print("اختبار ربط العمليات بالنظام المالي AutoProfit Pro")
    print("="*80)
    
    # Step 1: Capture initial financial state
    before_snapshot = capture_financial_snapshot("BEFORE_OPERATION")
    
    # Step 2: Create a new operation
    print("\n[1] Testing POST /api/operations (Create new operation)")
    operation_payload = {
        "accountId": None,  # Let the system handle account assignment
        "vehicleId": None,
        "type": "sale",
        "partnerType": "customer",
        "partnerName": "عميل اختبار",
        "items": [
            {
                "itemType": "service",
                "name": "تغيير زيت",
                "quantity": 1,
                "price": 200
            },
            {
                "itemType": "part",
                "name": "فلتر زيت",
                "quantity": 1,
                "price": 50
            }
        ],
        "paymentMethod": "cash",
        "paymentStatus": "paid",
        "notes": "عملية اختبارية للربط المالي"
    }
    
    operation_created = False
    operation_id = None
    
    try:
        print(f"   Payload: {json.dumps(operation_payload, ensure_ascii=False, indent=2)}")
        response = requests.post(f"{BACKEND_URL}/operations", 
                               json=operation_payload, 
                               timeout=15)
        
        if response.status_code in [200, 201]:
            data = response.json()
            operation_id = data.get('id')
            total = data.get('total', 0)
            subtotal = data.get('subtotal', 0)
            
            log_test("Create operation", True, 
                    f"Operation ID: {operation_id}, Total: {total}, Subtotal: {subtotal}")
            operation_created = True
            
        else:
            log_test("Create operation", False, 
                    f"Status: {response.status_code}, Response: {response.text[:300]}")
            
    except Exception as e:
        log_test("Create operation", False, f"Error: {str(e)}")
    
    if not operation_created:
        print("\n❌ Cannot continue testing - operation creation failed")
        return
    
    # Step 3: Wait a moment for financial processing
    print("\n⏳ Waiting 2 seconds for financial processing...")
    import time
    time.sleep(2)
    
    # Step 4: Capture financial state after operation
    after_snapshot = capture_financial_snapshot("AFTER_OPERATION")
    
    # Step 5: Test individual financial endpoints
    print("\n[2] Testing GET /api/accounts-chart/balance-sheet/summary")
    try:
        response = requests.get(f"{BACKEND_URL}/accounts-chart/balance-sheet/summary", timeout=10)
        if response.status_code == 200:
            data = response.json()
            required_fields = ["assets", "liabilities", "revenue", "net_income"]
            missing_fields = [f for f in required_fields if f not in data]
            
            if not missing_fields:
                log_test("Balance Sheet Summary", True, 
                        f"Assets: {data.get('assets')}, Revenue: {data.get('revenue')}, Net Income: {data.get('net_income')}")
            else:
                log_test("Balance Sheet Summary", False, 
                        f"Missing fields: {missing_fields}")
        else:
            log_test("Balance Sheet Summary", False, 
                    f"Status: {response.status_code}, Response: {response.text[:200]}")
    except Exception as e:
        log_test("Balance Sheet Summary", False, f"Error: {str(e)}")
    
    print("\n[3] Testing GET /api/analytics-advanced/financial-ratios")
    try:
        response = requests.get(f"{BACKEND_URL}/analytics-advanced/financial-ratios", timeout=10)
        if response.status_code == 200:
            data = response.json()
            ratios = data.get("ratios", {})
            required_ratios = ["current_ratio", "quick_ratio", "gross_margin", "net_margin"]
            missing_ratios = [r for r in required_ratios if r not in ratios]
            
            if not missing_ratios:
                log_test("Financial Ratios", True, 
                        f"Current Ratio: {ratios.get('current_ratio')}, Net Margin: {ratios.get('net_margin')}")
            else:
                log_test("Financial Ratios", False, 
                        f"Missing ratios: {missing_ratios}")
        else:
            log_test("Financial Ratios", False, 
                    f"Status: {response.status_code}, Response: {response.text[:200]}")
    except Exception as e:
        log_test("Financial Ratios", False, f"Error: {str(e)}")
    
    print("\n[4] Testing GET /api/analytics-advanced/profit-loss")
    try:
        response = requests.get(f"{BACKEND_URL}/analytics-advanced/profit-loss", timeout=10)
        if response.status_code == 200:
            data = response.json()
            required_fields = ["revenue", "cost_of_goods_sold", "gross_profit", "net_profit"]
            missing_fields = [f for f in required_fields if f not in data]
            
            if not missing_fields:
                revenue_total = data.get("revenue", {}).get("total", 0)
                log_test("Profit & Loss", True, 
                        f"Revenue Total: {revenue_total}, Net Profit: {data.get('net_profit')}")
            else:
                log_test("Profit & Loss", False, 
                        f"Missing fields: {missing_fields}")
        else:
            log_test("Profit & Loss", False, 
                    f"Status: {response.status_code}, Response: {response.text[:200]}")
    except Exception as e:
        log_test("Profit & Loss", False, f"Error: {str(e)}")
    
    # Step 6: Compare snapshots and analyze changes
    integration_working = compare_snapshots(before_snapshot, after_snapshot)
    
    if integration_working:
        log_test("Financial Integration", True, "Operation successfully integrated with financial system")
    else:
        log_test("Financial Integration", False, "No financial changes detected - integration may not be working")
    
    # Step 7: Record payload and results for report
    test_results["operation_payload"] = operation_payload
    test_results["operation_id"] = operation_id
    test_results["integration_working"] = integration_working

def main():
    """Main test execution"""
    print("\n" + "="*80)
    print("AUTOPROFIT PRO FINANCIAL INTEGRATION TEST")
    print("اختبار ربط العمليات بالنظام المالي AutoProfit Pro")
    print("="*80)
    print(f"Backend URL: {BACKEND_URL}")
    print(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    # Run the integration test
    test_autoprofit_integration()
    
    # Print detailed results
    print_summary()
    
    # Print detailed report in Arabic
    print("\n" + "="*80)
    print("تقرير مفصل للاختبار (DETAILED TEST REPORT)")
    print("="*80)
    
    if "operation_payload" in test_results:
        print("\n1) الـ payload المرسل لعملية البيع:")
        print(json.dumps(test_results["operation_payload"], ensure_ascii=False, indent=2))
    
    if "snapshots" in test_results:
        snapshots = test_results["snapshots"]
        if "BEFORE_OPERATION" in snapshots and "AFTER_OPERATION" in snapshots:
            before = snapshots["BEFORE_OPERATION"]
            after = snapshots["AFTER_OPERATION"]
            
            print("\n2) Snapshot قبل وبعد للقيم الرئيسية:")
            
            if before["balance_sheet"] and after["balance_sheet"]:
                print("\nBalance Sheet:")
                for key in ["assets", "liabilities", "revenue", "net_income"]:
                    before_val = before["balance_sheet"].get(key, 0)
                    after_val = after["balance_sheet"].get(key, 0)
                    print(f"  {key}: {before_val} → {after_val}")
            
            if before["profit_loss"] and after["profit_loss"]:
                print("\nProfit & Loss:")
                before_revenue = before["profit_loss"].get("revenue", {}).get("total", 0)
                after_revenue = after["profit_loss"].get("revenue", {}).get("total", 0)
                before_profit = before["profit_loss"].get("net_profit", 0)
                after_profit = after["profit_loss"].get("net_profit", 0)
                print(f"  revenue.total: {before_revenue} → {after_revenue}")
                print(f"  net_profit: {before_profit} → {after_profit}")
    
    print("\n3) أي أخطاء ظهرت في الاستجابات أو status codes:")
    if test_results["failed"]:
        for failed_test in test_results["failed"]:
            print(f"  - {failed_test}")
    else:
        print("  لا توجد أخطاء - جميع الاختبارات نجحت ✅")
    
    print("\n4) خلاصة الربط المالي:")
    if test_results.get("integration_working", False):
        print("  ✅ الربط بين /api/operations و /api/accounts-chart/* و /api/analytics-advanced/* يعمل بشكل صحيح")
        print("  ✅ تم رصد تغييرات في القيم المالية بعد إنشاء العملية")
    else:
        print("  ❌ لم يتم رصد تغييرات مالية بعد إنشاء العملية")
        print("  ⚠️  قد تحتاج إلى مراجعة ربط العمليات بالنظام المالي")
    
    print("="*80)
    
    # Exit with appropriate code
    if test_results['failed']:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()