#!/usr/bin/env python3
"""
اختبار إصلاح مشكلة عدم ظهور عمليات/عملاء الذمم عند as_of=اليوم
Testing fix for AR operations/customers not appearing when as_of=today

خلفية: كان عندنا issue بسبب مقارنة التاريخ في Supabase: op_date مخزن كـ timestamp مع timezone، 
بينما as_of كان YYYY-MM-DD فقط، فـ lte كان يستبعد عمليات نفس اليوم (بعد منتصف الليل). 
تم إصلاحه بتحويل end_date إلى end-of-day: YYYY-MM-DDT23:59:59Z.

Background: We had an issue due to date comparison in Supabase: op_date stored as timestamp with timezone,
while as_of was YYYY-MM-DD only, so lte was excluding same-day operations (after midnight).
Fixed by converting end_date to end-of-day: YYYY-MM-DDT23:59:59Z.
"""

import requests
import json
import uuid
from datetime import datetime, timezone
import time

# Configuration
BACKEND_URL = "https://ar-ledger-ssot.preview.emergentagent.com/api"
WORKSHOP_ID = "finmodule-sync"

def print_test_header(test_name):
    """Print formatted test header"""
    print(f"\n{'='*80}")
    print(f"🧪 {test_name}")
    print(f"{'='*80}")

def print_result(success, message, details=None):
    """Print test result with formatting"""
    status = "✅ نجح" if success else "❌ فشل"
    print(f"{status}: {message}")
    if details:
        print(f"التفاصيل: {details}")

def print_api_call(method, url, data=None, params=None):
    """Print API call details"""
    print(f"📡 {method} {url}")
    if params:
        print(f"📤 المعاملات: {json.dumps(params, ensure_ascii=False, indent=2)}")
    if data:
        print(f"📤 البيانات: {json.dumps(data, ensure_ascii=False, indent=2)}")

def reset_data():
    """Reset all financial data to start fresh"""
    print_test_header("تصفير البيانات المالية")
    
    try:
        url = f"{BACKEND_URL}/finance/reset-all-data"
        params = {
            "workshop_id": WORKSHOP_ID,
            "confirm": "DELETE_ALL"
        }
        
        print_api_call("DELETE", url, params=params)
        response = requests.delete(url, params=params, timeout=30)
        print(f"📊 كود الاستجابة: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print_result(True, f"تم تصفير البيانات بنجاح: {data.get('message', '')}")
            return True
        else:
            print_result(False, f"فشل في تصفير البيانات: {response.status_code}")
            print(f"نص الاستجابة: {response.text}")
            return False
            
    except Exception as e:
        print_result(False, f"خطأ في تصفير البيانات: {str(e)}")
        return False

def create_credit_operation(partner_name, amount):
    """Create a credit operation for today"""
    try:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        operation_data = {
            "workshopId": WORKSHOP_ID,
            "type": "sale",
            "partnerType": "customer", 
            "partnerName": partner_name,
            "paymentMethod": "credit",
            "opDate": today,
            "items": [
                {
                    "itemType": "service",
                    "name": f"خدمة صيانة لـ {partner_name}",
                    "quantity": 1,
                    "price": float(amount)
                }
            ],
            "total": float(amount),
            "notes": f"عملية اختبار آجلة - {partner_name}"
        }
        
        url = f"{BACKEND_URL}/operations"
        print_api_call("POST", url, data=operation_data)
        
        response = requests.post(url, json=operation_data, timeout=30)
        print(f"📊 كود الاستجابة: {response.status_code}")
        
        if response.status_code in [200, 201]:
            data = response.json()
            operation_id = data.get("id")
            print_result(True, f"تم إنشاء العملية الآجلة: {operation_id}")
            print(f"  👤 العميل: {partner_name}")
            print(f"  💰 المبلغ: {amount} ريال")
            print(f"  📅 التاريخ: {today}")
            return operation_id
        else:
            print_result(False, f"فشل في إنشاء العملية: {response.status_code}")
            print(f"نص الاستجابة: {response.text}")
            return None
            
    except Exception as e:
        print_result(False, f"خطأ في إنشاء العملية: {str(e)}")
        return None

def test_ar_customers_today():
    """Test AR customers report with as_of=today"""
    print_test_header("اختبار تقرير عملاء الذمم المدينة - اليوم")
    
    try:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        url = f"{BACKEND_URL}/finance/ar/customers"
        params = {
            "workshop_id": WORKSHOP_ID,
            "as_of": today
        }
        
        print_api_call("GET", url, params=params)
        response = requests.get(url, params=params, timeout=30)
        print(f"📊 كود الاستجابة: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get("success"):
                customers = data.get("data", {}).get("customers", [])
                total_ar = data.get("data", {}).get("total_ar", 0)
                
                print_result(True, f"تم جلب تقرير العملاء بنجاح")
                print(f"  📊 إجمالي الذمم المدينة: {total_ar} ريال")
                print(f"  👥 عدد العملاء: {len(customers)}")
                
                # Check if total AR is >= 300 (100 + 200)
                if total_ar >= 300:
                    print_result(True, f"إجمالي الذمم المدينة صحيح: {total_ar} >= 300")
                else:
                    print_result(False, f"إجمالي الذمم المدينة غير صحيح: {total_ar} < 300")
                    return False
                
                # Display customer details
                for customer in customers:
                    name = customer.get("customer", "بدون اسم")
                    balance = customer.get("balance", 0)
                    print(f"  👤 {name}: {balance} ريال")
                
                # Check if customers appear (not empty)
                if len(customers) > 0:
                    print_result(True, f"العملاء ظاهرون في التقرير: {len(customers)} عميل")
                    return True
                else:
                    print_result(False, "لا يوجد عملاء في التقرير رغم وجود عمليات اليوم")
                    return False
            else:
                print_result(False, f"فشل في جلب التقرير: {data.get('message', 'خطأ غير محدد')}")
                return False
        else:
            print_result(False, f"فشل في استدعاء التقرير: {response.status_code}")
            print(f"نص الاستجابة: {response.text}")
            return False
            
    except Exception as e:
        print_result(False, f"خطأ في اختبار تقرير العملاء: {str(e)}")
        return False

def test_ar_ledger_today():
    """Test AR ledger report for today's period"""
    print_test_header("اختبار دفتر الذمم المدينة - فترة اليوم")
    
    try:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        url = f"{BACKEND_URL}/finance/ar/ledger"
        params = {
            "workshop_id": WORKSHOP_ID,
            "start_date": today,
            "end_date": today
        }
        
        print_api_call("GET", url, params=params)
        response = requests.get(url, params=params, timeout=30)
        print(f"📊 كود الاستجابة: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get("success"):
                rows = data.get("data", {}).get("rows", [])
                ending_balance = data.get("data", {}).get("ending_balance", 0)
                
                print_result(True, f"تم جلب دفتر الذمم بنجاح")
                print(f"  📊 الرصيد النهائي: {ending_balance} ريال")
                print(f"  📄 عدد القيود: {len(rows)}")
                
                # Check for invoice_credit_sale entries
                credit_sale_entries = [e for e in rows if e.get("type") == "invoice_credit_sale"]
                
                if len(credit_sale_entries) >= 2:
                    print_result(True, f"يحتوي على قيود البيع الآجل: {len(credit_sale_entries)} قيد")
                    
                    # Display entry details
                    for entry in credit_sale_entries:
                        date = entry.get("date", "")
                        debit = entry.get("debit", 0)
                        customer = entry.get("customer", "بدون اسم")
                        print(f"  📝 {date}: {customer} - {debit} ريال")
                    
                    return True
                else:
                    print_result(False, f"لا يحتوي على قيود البيع الآجل الكافية: {len(credit_sale_entries)} < 2")
                    return False
            else:
                print_result(False, f"فشل في جلب دفتر الذمم: {data.get('message', 'خطأ غير محدد')}")
                return False
        else:
            print_result(False, f"فشل في استدعاء دفتر الذمم: {response.status_code}")
            print(f"نص الاستجابة: {response.text}")
            return False
            
    except Exception as e:
        print_result(False, f"خطأ في اختبار دفتر الذمم: {str(e)}")
        return False

def test_include_today_false():
    """Test include_today=false parameter if it exists"""
    print_test_header("اختبار معامل include_today=false")
    
    try:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        url = f"{BACKEND_URL}/finance/ar/customers"
        params = {
            "workshop_id": WORKSHOP_ID,
            "as_of": today,
            "include_today": "false"
        }
        
        print_api_call("GET", url, params=params)
        response = requests.get(url, params=params, timeout=30)
        print(f"📊 كود الاستجابة: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get("success"):
                customers = data.get("data", {}).get("customers", [])
                total_ar = data.get("data", {}).get("total_ar", 0)
                
                print_result(True, f"تم جلب التقرير مع include_today=false")
                print(f"  📊 إجمالي الذمم المدينة: {total_ar} ريال")
                print(f"  👥 عدد العملاء: {len(customers)}")
                
                # With include_today=false, we expect lower or zero AR
                if total_ar < 300:
                    print_result(True, f"معامل include_today=false يعمل: {total_ar} < 300")
                    return True
                else:
                    print_result(False, f"معامل include_today=false لا يعمل: {total_ar} >= 300")
                    return False
            else:
                print_result(False, f"فشل في جلب التقرير: {data.get('message', 'خطأ غير محدد')}")
                return False
        else:
            # If the parameter doesn't exist, that's okay
            print_result(True, f"معامل include_today غير مدعوم (مقبول): {response.status_code}")
            return True
            
    except Exception as e:
        print_result(False, f"خطأ في اختبار include_today: {str(e)}")
        return False

def run_ar_date_fix_test():
    """Run the complete AR date fix test"""
    print("🚀 بدء اختبار إصلاح مشكلة تاريخ الذمم المدينة")
    print(f"🌐 رابط الخادم: {BACKEND_URL}")
    print(f"🏪 معرف الورشة: {WORKSHOP_ID}")
    print(f"⏰ وقت الاختبار: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📅 تاريخ اليوم: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}")
    
    results = []
    
    # Step 1: Reset data
    print_test_header("الخطوة 1: تصفير البيانات")
    reset_success = reset_data()
    results.append(("تصفير البيانات", reset_success))
    
    if not reset_success:
        print("❌ فشل في تصفير البيانات - توقف الاختبار")
        return False
    
    # Step 2: Create two credit operations today
    print_test_header("الخطوة 2: إنشاء عمليتين آجلتين اليوم")
    
    operation1_id = create_credit_operation("أحمد العميل الأول", 100)
    results.append(("إنشاء العملية الأولى (100 ريال)", operation1_id is not None))
    
    if operation1_id:
        time.sleep(1)  # Small delay between operations
        
    operation2_id = create_credit_operation("محمد العميل الثاني", 200)
    results.append(("إنشاء العملية الثانية (200 ريال)", operation2_id is not None))
    
    if not operation1_id or not operation2_id:
        print("❌ فشل في إنشاء العمليات - توقف الاختبار")
        return False
    
    # Small delay to ensure data is processed
    time.sleep(2)
    
    # Step 3: Test AR customers with as_of=today
    print_test_header("الخطوة 3: اختبار تقرير عملاء الذمم مع as_of=اليوم")
    ar_customers_success = test_ar_customers_today()
    results.append(("تقرير عملاء الذمم (as_of=اليوم)", ar_customers_success))
    
    # Step 4: Test AR ledger for today's period
    print_test_header("الخطوة 4: اختبار دفتر الذمم لفترة اليوم")
    ar_ledger_success = test_ar_ledger_today()
    results.append(("دفتر الذمم (فترة اليوم)", ar_ledger_success))
    
    # Step 5: Test include_today=false (optional)
    print_test_header("الخطوة 5: اختبار معامل include_today=false")
    include_today_success = test_include_today_false()
    results.append(("معامل include_today=false", include_today_success))
    
    # Summary
    print_test_header("ملخص نتائج اختبار إصلاح تاريخ الذمم المدينة")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ نجح" if result else "❌ فشل"
        print(f"{status} {test_name}")
    
    print(f"\n📊 النتيجة النهائية: {passed}/{total} اختبارات نجحت")
    
    # Final assessment
    critical_tests = [
        ("إنشاء العملية الأولى (100 ريال)", operation1_id is not None),
        ("إنشاء العملية الثانية (200 ريال)", operation2_id is not None),
        ("تقرير عملاء الذمم (as_of=اليوم)", ar_customers_success),
        ("دفتر الذمم (فترة اليوم)", ar_ledger_success)
    ]
    
    critical_passed = sum(1 for _, result in critical_tests if result)
    critical_total = len(critical_tests)
    
    if critical_passed == critical_total:
        print("🎉 جميع الاختبارات الأساسية نجحت!")
        print("✅ إصلاح مشكلة تاريخ الذمم المدينة يعمل بشكل صحيح")
        print("✅ العمليات الآجلة تظهر في تقارير الذمم عند as_of=اليوم")
        return True
    else:
        print(f"⚠️ {critical_total - critical_passed} اختبارات أساسية فشلت")
        print("❌ مشكلة تاريخ الذمم المدينة لم تُحل بالكامل")
        return False

if __name__ == "__main__":
    success = run_ar_date_fix_test()
    exit(0 if success else 1)