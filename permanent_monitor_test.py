#!/usr/bin/env python3
"""
اختبار ميزة "المراقب الدائم" الجديدة
Testing the new "Permanent Monitor" feature

Test Requirements (Arabic):
1) GET /api/finance/alerts?workshop_id=finmodule-sync
   - تأكد يرجع success=true
   - وتأكد alerts ليست فارغة (على الأقل ar_open أو ap_open لو كانت موجودة في الميزان)

2) تأكد أن /api/finance/reports/trial-balance لا يزال يعمل ويعيد codes تشمل 101/113/211/411/514

3) اختبار أن endpoint لا يستغرق وقت طويل (target < 5s)
"""

import requests
import time
import json
from datetime import datetime

# Configuration
BACKEND_URL = "https://garage-erp-arabic.preview.emergentagent.com/api"
WORKSHOP_ID = "finmodule-sync"

def test_permanent_monitor():
    """اختبار شامل لميزة المراقب الدائم"""
    
    print("🔍 بدء اختبار ميزة المراقب الدائم (Permanent Monitor)")
    print("=" * 60)
    
    results = {
        "alerts_api": {"status": "❌", "details": ""},
        "trial_balance_api": {"status": "❌", "details": ""},
        "performance": {"status": "❌", "details": ""},
        "overall": {"status": "❌", "summary": ""}
    }
    
    # Test 1: Finance Alerts API
    print("\n📊 Test 1: اختبار GET /api/finance/alerts")
    try:
        start_time = time.time()
        
        response = requests.get(
            f"{BACKEND_URL}/finance/alerts",
            params={"workshop_id": WORKSHOP_ID},
            timeout=10
        )
        
        alerts_duration = time.time() - start_time
        
        print(f"   Status Code: {response.status_code}")
        print(f"   Response Time: {alerts_duration:.2f}s")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   Response Structure: {json.dumps(data, ensure_ascii=False, indent=2)[:500]}...")
            
            # Check success=true
            success = data.get("success", False)
            print(f"   ✅ success = {success}")
            
            if success:
                alerts_data = data.get("data", {})
                alerts = alerts_data.get("alerts", [])
                
                print(f"   📋 عدد التنبيهات: {len(alerts)}")
                
                # Check for ar_open or ap_open alerts
                ar_open_found = any(alert.get("id") == "ar_open" for alert in alerts)
                ap_open_found = any(alert.get("id") == "ap_open" for alert in alerts)
                
                print(f"   🔍 ar_open alert found: {ar_open_found}")
                print(f"   🔍 ap_open alert found: {ap_open_found}")
                
                # Display all alerts
                for i, alert in enumerate(alerts, 1):
                    alert_id = alert.get("id", "unknown")
                    severity = alert.get("severity", "unknown")
                    title = alert.get("title", "No title")
                    message = alert.get("message", "No message")
                    print(f"   Alert {i}: [{severity}] {alert_id} - {title}")
                    print(f"            {message}")
                
                if len(alerts) > 0 or ar_open_found or ap_open_found:
                    results["alerts_api"]["status"] = "✅"
                    results["alerts_api"]["details"] = f"API working, {len(alerts)} alerts found"
                else:
                    results["alerts_api"]["status"] = "⚠️"
                    results["alerts_api"]["details"] = "API working but no alerts found (may be normal if no issues)"
            else:
                results["alerts_api"]["status"] = "❌"
                results["alerts_api"]["details"] = f"success=false in response"
        else:
            results["alerts_api"]["status"] = "❌"
            results["alerts_api"]["details"] = f"HTTP {response.status_code}: {response.text[:200]}"
            
    except Exception as e:
        results["alerts_api"]["status"] = "❌"
        results["alerts_api"]["details"] = f"Exception: {str(e)}"
        print(f"   ❌ Error: {e}")
    
    # Test 2: Trial Balance API (verify it still works)
    print("\n⚖️ Test 2: اختبار GET /api/finance/reports/trial-balance")
    try:
        start_time = time.time()
        
        response = requests.get(
            f"{BACKEND_URL}/finance/reports/trial-balance",
            params={"workshop_id": WORKSHOP_ID},
            timeout=10
        )
        
        tb_duration = time.time() - start_time
        
        print(f"   Status Code: {response.status_code}")
        print(f"   Response Time: {tb_duration:.2f}s")
        
        if response.status_code == 200:
            data = response.json()
            success = data.get("success", False)
            print(f"   ✅ success = {success}")
            
            if success:
                tb_data = data.get("data", {})
                accounts = tb_data.get("accounts", [])
                
                print(f"   📊 عدد الحسابات: {len(accounts)}")
                
                # Check for required account codes
                required_codes = ["101", "113", "211", "411", "514"]
                found_codes = []
                
                for account in accounts:
                    code = account.get("code", "")
                    name = account.get("name", "")
                    debit = account.get("debit", 0)
                    credit = account.get("credit", 0)
                    
                    if code in required_codes:
                        found_codes.append(code)
                        print(f"   ✅ Account {code} ({name}): Debit={debit}, Credit={credit}")
                
                missing_codes = [code for code in required_codes if code not in found_codes]
                
                if len(missing_codes) == 0:
                    results["trial_balance_api"]["status"] = "✅"
                    results["trial_balance_api"]["details"] = f"All required codes found: {found_codes}"
                else:
                    results["trial_balance_api"]["status"] = "⚠️"
                    results["trial_balance_api"]["details"] = f"Found: {found_codes}, Missing: {missing_codes}"
                    
                # Show totals
                totals = tb_data.get("totals", {})
                total_debit = totals.get("total_debit", 0)
                total_credit = totals.get("total_credit", 0)
                print(f"   💰 Total Debit: {total_debit}, Total Credit: {total_credit}")
                
            else:
                results["trial_balance_api"]["status"] = "❌"
                results["trial_balance_api"]["details"] = "success=false in response"
        else:
            results["trial_balance_api"]["status"] = "❌"
            results["trial_balance_api"]["details"] = f"HTTP {response.status_code}: {response.text[:200]}"
            
    except Exception as e:
        results["trial_balance_api"]["status"] = "❌"
        results["trial_balance_api"]["details"] = f"Exception: {str(e)}"
        print(f"   ❌ Error: {e}")
    
    # Test 3: Performance Check (< 5s target)
    print("\n⏱️ Test 3: اختبار الأداء (Performance)")
    try:
        max_duration = max(alerts_duration if 'alerts_duration' in locals() else 0, 
                          tb_duration if 'tb_duration' in locals() else 0)
        
        print(f"   Alerts API Duration: {alerts_duration if 'alerts_duration' in locals() else 'N/A'}s")
        print(f"   Trial Balance Duration: {tb_duration if 'tb_duration' in locals() else 'N/A'}s")
        print(f"   Max Duration: {max_duration:.2f}s")
        print(f"   Target: < 5.0s")
        
        if max_duration < 5.0:
            results["performance"]["status"] = "✅"
            results["performance"]["details"] = f"Performance good: {max_duration:.2f}s < 5.0s"
        elif max_duration < 10.0:
            results["performance"]["status"] = "⚠️"
            results["performance"]["details"] = f"Performance acceptable: {max_duration:.2f}s (target: <5s)"
        else:
            results["performance"]["status"] = "❌"
            results["performance"]["details"] = f"Performance poor: {max_duration:.2f}s > 10s"
            
    except Exception as e:
        results["performance"]["status"] = "❌"
        results["performance"]["details"] = f"Exception: {str(e)}"
        print(f"   ❌ Error: {e}")
    
    # Overall Assessment
    print("\n📋 ملخص النتائج (Results Summary)")
    print("=" * 60)
    
    # Count test results (excluding 'overall' key)
    test_results_only = {k: v for k, v in results.items() if k != "overall"}
    passed_tests = sum(1 for test in test_results_only.values() if test["status"] == "✅")
    warning_tests = sum(1 for test in test_results_only.values() if test["status"] == "⚠️")
    failed_tests = sum(1 for test in test_results_only.values() if test["status"] == "❌")
    
    for test_name, result in test_results_only.items():
        print(f"{result['status']} {test_name}: {result['details']}")
    
    print(f"\nTest Statistics: ✅ {passed_tests}, ⚠️ {warning_tests}, ❌ {failed_tests}")
    
    # Determine overall status
    total_tests = len(test_results_only)
    if failed_tests == 0 and warning_tests == 0:
        results["overall"]["status"] = "✅"
        results["overall"]["summary"] = "جميع الاختبارات نجحت - المراقب الدائم يعمل بشكل مثالي"
    elif failed_tests == 0:
        results["overall"]["status"] = "⚠️"
        results["overall"]["summary"] = f"الاختبارات نجحت مع تحذيرات ({warning_tests} warnings)"
    else:
        results["overall"]["status"] = "❌"
        results["overall"]["summary"] = f"فشل في {failed_tests} اختبار من أصل {total_tests}"
    
    print(f"\n🎯 النتيجة النهائية: {results['overall']['status']} {results['overall']['summary']}")
    
    return results

if __name__ == "__main__":
    test_results = test_permanent_monitor()
    
    # Exit with appropriate code
    if test_results["overall"]["status"] == "✅":
        exit(0)
    elif test_results["overall"]["status"] == "⚠️":
        exit(1)  # Warnings
    else:
        exit(2)  # Failures