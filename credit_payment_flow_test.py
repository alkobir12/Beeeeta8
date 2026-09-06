#!/usr/bin/env python3
"""
اختبار تدفق تأكيد السداد للآجل + الحذف الذري
Credit Payment Confirmation Flow + Atomic Deletion Testing

البيئة:
- استخدم API base من frontend/.env (REACT_APP_BACKEND_URL) وأضف /api
- DB provider المتوقع: supabase (لا تغيّر إعدادات البيئة)

المطلوب:
1) استدعِ DELETE /api/finance/reset-all-data لتصفير البيانات
2) أنشئ عملية بيع credit عبر POST /api/operations مع workshopId=finmodule-sync و paymentMethod=credit و total/items
3) أكد سداد جزئي عبر POST /api/operations/{op_id}/confirm-payment بمبلغ جزئي
4) أكد سداد باقي المبلغ
5) تحقق من تقارير AR
6) اختبر DELETE /api/operations/{op_id} بعد وجود دفعات
"""

import requests
import json
import os
import uuid
from datetime import datetime, timedelta

# Configuration from frontend/.env
BACKEND_URL = "https://financial-ssot.preview.emergentagent.com/api"
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

def step_1_reset_all_data():
    """
    الخطوة 1: تصفير جميع البيانات
    """
    print_test_header("الخطوة 1: تصفير جميع البيانات")
    
    try:
        url = f"{BACKEND_URL}/finance/reset-all-data"
        params = {"workshop_id": WORKSHOP_ID, "confirm": "DELETE_ALL"}
        
        print_api_call("DELETE", url, params=params)
        
        response = requests.delete(url, params=params, timeout=30)
        print(f"📊 كود الاستجابة: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print_result(True, "تم تصفير البيانات بنجاح")
            print(f"📄 الاستجابة: {json.dumps(data, ensure_ascii=False, indent=2)}")
            return True
        else:
            print_result(False, f"فشل في تصفير البيانات: {response.status_code}")
            print(f"📄 نص الاستجابة: {response.text}")
            return False
            
    except Exception as e:
        print_result(False, f"خطأ في تصفير البيانات: {str(e)}")
        return False

def step_2_create_credit_operation():
    """
    الخطوة 2: إنشاء عملية بيع آجل
    """
    print_test_header("الخطوة 2: إنشاء عملية بيع آجل")
    
    try:
        operation_data = {
            "workshopId": WORKSHOP_ID,
            "type": "sale",
            "paymentMethod": "credit",
            "partnerName": "أحمد العميل التجريبي",
            "partnerType": "customer",
            "opDate": "2024-06-01",
            "items": [
                {
                    "itemType": "service",
                    "name": "خدمة صيانة شاملة",
                    "quantity": 1,
                    "price": 100.0
                }
            ],
            "total": 100.0,
            "notes": "عملية بيع آجل للاختبار"
        }
        
        url = f"{BACKEND_URL}/operations"
        print_api_call("POST", url, data=operation_data)
        
        response = requests.post(url, json=operation_data, timeout=30)
        print(f"📊 كود الاستجابة: {response.status_code}")
        
        if response.status_code in [200, 201]:
            data = response.json()
            operation_id = data.get("id")
            print_result(True, f"تم إنشاء العملية الآجلة بنجاح: {operation_id}")
            print(f"📄 تفاصيل العملية: {json.dumps(data, ensure_ascii=False, indent=2)}")
            
            # Verify payment method is credit
            if data.get("paymentMethod") == "credit":
                print_result(True, "طريقة الدفع محفوظة كـ 'credit' بشكل صحيح")
            else:
                print_result(False, f"طريقة الدفع غير صحيحة: {data.get('paymentMethod')}")
                
            return operation_id
        else:
            print_result(False, f"فشل في إنشاء العملية: {response.status_code}")
            print(f"📄 نص الاستجابة: {response.text}")
            return None
            
    except Exception as e:
        print_result(False, f"خطأ في إنشاء العملية: {str(e)}")
        return None

def step_3_verify_no_initial_journal_entry(operation_id):
    """
    الخطوة 3: التحقق من عدم وجود قيد محاسبي فوري (قاعدة P0)
    """
    print_test_header("الخطوة 3: التحقق من عدم وجود قيد محاسبي فوري")
    
    try:
        url = f"{BACKEND_URL}/finance/journal-entries"
        params = {"workshop_id": WORKSHOP_ID}
        
        print_api_call("GET", url, params=params)
        
        response = requests.get(url, params=params, timeout=30)
        print(f"📊 كود الاستجابة: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            entries = data.get("data", [])
            
            # Look for entries related to our operation
            operation_entries = [
                entry for entry in entries 
                if entry.get("reference_id") == operation_id
            ]
            
            if len(operation_entries) == 0:
                print_result(True, "لا يوجد قيد محاسبي فوري للعملية الآجلة (سلوك P0 صحيح)")
                return True
            else:
                print_result(False, f"وُجد {len(operation_entries)} قيد محاسبي للعملية (خطأ في قاعدة P0)")
                return False
        else:
            print_result(False, f"فشل في جلب القيود المحاسبية: {response.status_code}")
            return False
            
    except Exception as e:
        print_result(False, f"خطأ في التحقق من القيود: {str(e)}")
        return False

def step_4_confirm_partial_payment(operation_id, amount, payment_date):
    """
    الخطوة 4: تأكيد سداد جزئي
    """
    print_test_header(f"الخطوة 4: تأكيد سداد جزئي - {amount} ريال")
    
    try:
        payment_data = {
            "workshopId": WORKSHOP_ID,
            "amount": amount,
            "payment_date": payment_date,
            "notes": f"سداد جزئي {amount} ريال"
        }
        
        url = f"{BACKEND_URL}/operations/{operation_id}/confirm-payment"
        print_api_call("POST", url, data=payment_data)
        
        response = requests.post(url, json=payment_data, timeout=30)
        print(f"📊 كود الاستجابة: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print_result(True, "تم تأكيد السداد الجزئي بنجاح")
            print(f"📄 تفاصيل السداد: {json.dumps(data, ensure_ascii=False, indent=2)}")
            
            # Check response contains paid and remaining
            payment_data = data.get("data", {})
            if "paid" in payment_data and "remaining" in payment_data:
                paid = payment_data.get("paid")
                remaining = payment_data.get("remaining")
                print_result(True, f"المدفوع: {paid} ريال، المتبقي: {remaining} ريال")
                return True
            else:
                print_result(False, "الاستجابة لا تحتوي على 'paid' و 'remaining'")
                return False
        else:
            print_result(False, f"فشل في تأكيد السداد: {response.status_code}")
            print(f"📄 نص الاستجابة: {response.text}")
            return False
            
    except Exception as e:
        print_result(False, f"خطأ في تأكيد السداد: {str(e)}")
        return False

def step_5_verify_payment_journal_entries(operation_id, expected_count):
    """
    الخطوة 5: التحقق من إنشاء قيود السداد
    """
    print_test_header(f"الخطوة 5: التحقق من قيود السداد (متوقع: {expected_count})")
    
    try:
        url = f"{BACKEND_URL}/finance/journal-entries"
        params = {"workshop_id": WORKSHOP_ID}
        
        print_api_call("GET", url, params=params)
        
        response = requests.get(url, params=params, timeout=30)
        print(f"📊 كود الاستجابة: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            entries = data.get("data", [])
            
            # Look for payment entries related to our operation
            payment_entries = [
                entry for entry in entries 
                if (entry.get("reference_id") == operation_id and 
                    entry.get("source") == "operation_payment")
            ]
            
            print(f"📊 عدد قيود السداد الموجودة: {len(payment_entries)}")
            
            if len(payment_entries) == expected_count:
                print_result(True, f"تم إنشاء {expected_count} قيد سداد بشكل صحيح")
                
                # Verify account codes and amounts
                for i, entry in enumerate(payment_entries):
                    print(f"📋 قيد السداد {i+1}:")
                    print(f"   المصدر: {entry.get('source')}")
                    print(f"   المرجع: {entry.get('reference_id')}")
                    print(f"   الوصف: {entry.get('description')}")
                    
                    lines = entry.get("lines", [])
                    for line in lines:
                        account = line.get("account")
                        account_name = line.get("account_name")
                        debit = line.get("debit", 0)
                        credit = line.get("credit", 0)
                        print(f"   {account} ({account_name}): مدين={debit}, دائن={credit}")
                
                return True
            else:
                print_result(False, f"عدد قيود السداد غير صحيح: متوقع {expected_count}, موجود {len(payment_entries)}")
                return False
        else:
            print_result(False, f"فشل في جلب القيود المحاسبية: {response.status_code}")
            return False
            
    except Exception as e:
        print_result(False, f"خطأ في التحقق من قيود السداد: {str(e)}")
        return False

def step_6_check_ar_reports():
    """
    الخطوة 6: التحقق من تقارير الذمم المدينة (AR)
    """
    print_test_header("الخطوة 6: التحقق من تقارير الذمم المدينة")
    
    try:
        # Check AR Customers report
        customers_url = f"{BACKEND_URL}/finance/ar/customers"
        customers_params = {
            "workshop_id": WORKSHOP_ID,
            "as_of": "2024-06-30"
        }
        
        print_api_call("GET", customers_url, params=customers_params)
        
        customers_response = requests.get(customers_url, params=customers_params, timeout=30)
        print(f"📊 كود استجابة تقرير العملاء: {customers_response.status_code}")
        
        if customers_response.status_code == 200:
            customers_data = customers_response.json()
            print_result(True, "تم جلب تقرير عملاء الذمم المدينة بنجاح")
            print(f"📄 تقرير العملاء: {json.dumps(customers_data, ensure_ascii=False, indent=2)}")
        else:
            print_result(False, f"فشل في جلب تقرير العملاء: {customers_response.status_code}")
        
        # Check AR Ledger report
        ledger_url = f"{BACKEND_URL}/finance/ar/ledger"
        ledger_params = {
            "workshop_id": WORKSHOP_ID,
            "start_date": "2024-06-01",
            "end_date": "2024-06-30"
        }
        
        print_api_call("GET", ledger_url, params=ledger_params)
        
        ledger_response = requests.get(ledger_url, params=ledger_params, timeout=30)
        print(f"📊 كود استجابة دفتر الذمم: {ledger_response.status_code}")
        
        if ledger_response.status_code == 200:
            ledger_data = ledger_response.json()
            print_result(True, "تم جلب دفتر الذمم المدينة بنجاح")
            print(f"📄 دفتر الذمم: {json.dumps(ledger_data, ensure_ascii=False, indent=2)}")
            
            # Check if AR decreased after payments
            ending_balance = ledger_data.get("data", {}).get("ending_balance", 0)
            if ending_balance == 0:
                print_result(True, "الذمم المدينة انخفضت إلى صفر بعد السداد الكامل")
                return True
            else:
                print_result(False, f"الذمم المدينة لم تنخفض بشكل صحيح: الرصيد النهائي = {ending_balance}")
                return False
        else:
            print_result(False, f"فشل في جلب دفتر الذمم: {ledger_response.status_code}")
            return False
            
    except Exception as e:
        print_result(False, f"خطأ في التحقق من تقارير الذمم: {str(e)}")
        return False

def step_7_test_atomic_deletion(operation_id):
    """
    الخطوة 7: اختبار الحذف الذري للعملية والقيود المرتبطة
    """
    print_test_header("الخطوة 7: اختبار الحذف الذري")
    
    try:
        # First, verify journal entries exist
        journal_url = f"{BACKEND_URL}/finance/journal-entries"
        journal_params = {"workshop_id": WORKSHOP_ID}
        
        print("🔍 التحقق من وجود القيود قبل الحذف...")
        journal_response = requests.get(journal_url, params=journal_params, timeout=30)
        
        if journal_response.status_code == 200:
            journal_data = journal_response.json()
            entries_before = journal_data.get("data", [])
            operation_entries_before = [
                entry for entry in entries_before 
                if entry.get("reference_id") == operation_id
            ]
            print(f"📊 عدد القيود المرتبطة بالعملية قبل الحذف: {len(operation_entries_before)}")
        else:
            print_result(False, "فشل في جلب القيود قبل الحذف")
            return False
        
        # Delete the operation
        delete_url = f"{BACKEND_URL}/operations/{operation_id}"
        print_api_call("DELETE", delete_url)
        
        delete_response = requests.delete(delete_url, timeout=30)
        print(f"📊 كود استجابة حذف العملية: {delete_response.status_code}")
        
        if delete_response.status_code == 200:
            print_result(True, "تم حذف العملية بنجاح")
            
            # Verify operation is deleted
            get_operation_response = requests.get(f"{BACKEND_URL}/operations/{operation_id}", timeout=30)
            if get_operation_response.status_code == 404:
                print_result(True, "تأكيد: العملية محذوفة من قاعدة البيانات")
            else:
                print_result(False, f"العملية ما زالت موجودة: {get_operation_response.status_code}")
            
            # Verify related journal entries are deleted (cascade deletion)
            journal_response_after = requests.get(journal_url, params=journal_params, timeout=30)
            
            if journal_response_after.status_code == 200:
                journal_data_after = journal_response_after.json()
                entries_after = journal_data_after.get("data", [])
                operation_entries_after = [
                    entry for entry in entries_after 
                    if entry.get("reference_id") == operation_id
                ]
                
                print(f"📊 عدد القيود المرتبطة بالعملية بعد الحذف: {len(operation_entries_after)}")
                
                if len(operation_entries_after) == 0:
                    print_result(True, "تأكيد: جميع القيود المرتبطة حُذفت (حذف ذري ناجح)")
                    return True
                else:
                    print_result(False, f"فشل الحذف الذري: {len(operation_entries_after)} قيد ما زال موجوداً")
                    return False
            else:
                print_result(False, "فشل في التحقق من القيود بعد الحذف")
                return False
        else:
            print_result(False, f"فشل في حذف العملية: {delete_response.status_code}")
            print(f"📄 نص الاستجابة: {delete_response.text}")
            return False
            
    except Exception as e:
        print_result(False, f"خطأ في اختبار الحذف الذري: {str(e)}")
        return False

def run_credit_payment_flow_test():
    """تشغيل اختبار تدفق السداد الآجل الكامل"""
    print("🚀 بدء اختبار تدفق تأكيد السداد للآجل + الحذف الذري")
    print(f"🌐 رابط الخادم: {BACKEND_URL}")
    print(f"🏪 معرف الورشة: {WORKSHOP_ID}")
    print(f"⏰ وقت الاختبار: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = []
    operation_id = None
    
    # الخطوة 1: تصفير البيانات
    step1_result = step_1_reset_all_data()
    results.append(("تصفير البيانات", step1_result))
    
    if step1_result:
        # الخطوة 2: إنشاء عملية آجلة
        operation_id = step_2_create_credit_operation()
        step2_result = operation_id is not None
        results.append(("إنشاء عملية آجلة", step2_result))
        
        if step2_result:
            # الخطوة 3: التحقق من عدم وجود قيد فوري
            step3_result = step_3_verify_no_initial_journal_entry(operation_id)
            results.append(("عدم وجود قيد فوري (P0)", step3_result))
            
            # الخطوة 4أ: تأكيد سداد جزئي (40 ريال)
            step4a_result = step_4_confirm_partial_payment(operation_id, 40.0, "2024-06-15")
            results.append(("تأكيد سداد جزئي (40 ريال)", step4a_result))
            
            if step4a_result:
                # التحقق من قيد السداد الأول
                step5a_result = step_5_verify_payment_journal_entries(operation_id, 1)
                results.append(("قيد السداد الأول", step5a_result))
                
                # الخطوة 4ب: تأكيد السداد المتبقي (60 ريال)
                step4b_result = step_4_confirm_partial_payment(operation_id, 60.0, "2024-06-15")
                results.append(("تأكيد السداد المتبقي (60 ريال)", step4b_result))
                
                if step4b_result:
                    # التحقق من قيود السداد (2 قيود)
                    step5b_result = step_5_verify_payment_journal_entries(operation_id, 2)
                    results.append(("قيود السداد الكاملة", step5b_result))
                    
                    # الخطوة 6: التحقق من تقارير AR
                    step6_result = step_6_check_ar_reports()
                    results.append(("تقارير الذمم المدينة", step6_result))
                    
                    # الخطوة 7: اختبار الحذف الذري
                    step7_result = step_7_test_atomic_deletion(operation_id)
                    results.append(("الحذف الذري", step7_result))
    
    # ملخص النتائج
    print_test_header("ملخص نتائج اختبار تدفق السداد الآجل")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ نجح" if result else "❌ فشل"
        print(f"{status} {test_name}")
    
    print(f"\n📊 النتيجة النهائية: {passed}/{total} اختبارات نجحت")
    
    if passed == total:
        print("🎉 جميع اختبارات تدفق السداد الآجل نجحت!")
        return True
    else:
        print(f"⚠️ {total - passed} اختبارات فشلت")
        return False

if __name__ == "__main__":
    success = run_credit_payment_flow_test()
    exit(0 if success else 1)