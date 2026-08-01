#!/usr/bin/env python3
"""
اختبار شامل لنقاط نهاية الذمم المدينة (AR Endpoints) بعد الإصلاحات
Comprehensive AR Endpoints Testing After Fixes

Testing the fixes:
1. reset-all-data now separates try/except for each table to prevent journal_entries deletion from being blocked
2. ar_ledger now ignores any collections not linked to an existing credit invoice (requires reference_id to exist in operations within the same workshop/scope)
"""

import requests
import json
import os
import uuid
from datetime import datetime, timedelta

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

def print_api_call(method, url, params=None, data=None):
    """Print API call details"""
    print(f"📡 {method} {url}")
    if params:
        print(f"📤 المعاملات: {params}")
    if data:
        print(f"📤 البيانات: {json.dumps(data, indent=2, ensure_ascii=False)}")

def test_reset_all_data():
    """
    اختبار 1: إعادة تعيين جميع البيانات والتحقق من حذف القيود اليومية
    Test 1: Reset all data and verify journal entries deletion
    """
    print_test_header("اختبار إعادة تعيين جميع البيانات")
    
    try:
        # Step 1: Reset all data
        url = f"{BACKEND_URL}/finance/reset-all-data"
        params = {
            "workshop_id": WORKSHOP_ID,
            "confirm": "DELETE_ALL"
        }
        
        print_api_call("DELETE", url, params=params)
        
        response = requests.delete(url, params=params, timeout=60)
        print(f"📊 كود الاستجابة: {response.status_code}")
        
        if response.status_code != 200:
            print_result(False, f"فشل في إعادة تعيين البيانات: {response.status_code}")
            print(f"نص الاستجابة: {response.text}")
            return False
        
        reset_data = response.json()
        print_result(True, f"تم إعادة تعيين البيانات بنجاح")
        print(f"📊 تفاصيل الحذف: {json.dumps(reset_data, indent=2, ensure_ascii=False)}")
        
        # Step 2: Verify journal entries are deleted
        journal_url = f"{BACKEND_URL}/finance/journal-entries"
        journal_params = {
            "workshop_id": WORKSHOP_ID,
            "start_date": "2024-06-01",
            "end_date": "2024-06-30"
        }
        
        print_api_call("GET", journal_url, params=journal_params)
        
        journal_response = requests.get(journal_url, params=journal_params, timeout=30)
        print(f"📊 كود الاستجابة: {journal_response.status_code}")
        
        if journal_response.status_code != 200:
            print_result(False, f"فشل في جلب القيود اليومية: {journal_response.status_code}")
            return False
        
        journal_data = journal_response.json()
        entries = journal_data.get("data", [])
        
        if len(entries) == 0:
            print_result(True, f"تم حذف جميع القيود اليومية بنجاح: {len(entries)} قيد")
            return True
        else:
            print_result(False, f"لم يتم حذف جميع القيود اليومية: {len(entries)} قيد متبقي")
            return False
            
    except Exception as e:
        print_result(False, f"خطأ في اختبار إعادة التعيين: {str(e)}")
        return False

def create_june_2024_scenario():
    """
    إنشاء سيناريو يونيو 2024
    Create June 2024 scenario:
    - أحمد: 780 آجل + تحصيل 400 + تحصيل 200 (رصيد نهائي: 180)
    - محمد: 720 آجل + تحصيل 720 (رصيد نهائي: 0)
    - سارة: 330 نقد (رصيد نهائي: 0)
    """
    print_test_header("إنشاء سيناريو يونيو 2024")
    
    operations_created = []
    
    try:
        # أحمد - عملية آجل 780 ريال
        ahmed_credit_op = {
            "workshop_id": WORKSHOP_ID,
            "type": "sale",
            "partner_name": "أحمد محمد العميل",
            "items": [
                {
                    "name": "خدمة صيانة شاملة",
                    "quantity": 1,
                    "price": 780.0
                }
            ],
            "total": 780.0,
            "paymentMethod": "credit",
            "op_date": "2024-06-05"
        }
        
        print("🔸 إنشاء عملية أحمد الآجلة (780 ريال)")
        print_api_call("POST", f"{BACKEND_URL}/operations", data=ahmed_credit_op)
        
        response = requests.post(f"{BACKEND_URL}/operations", json=ahmed_credit_op, timeout=30)
        print(f"📊 كود الاستجابة: {response.status_code}")
        
        if response.status_code not in [200, 201]:
            print_result(False, f"فشل في إنشاء عملية أحمد: {response.status_code}")
            return []
        
        ahmed_op_data = response.json()
        ahmed_op_id = ahmed_op_data.get("id")
        operations_created.append(("أحمد - آجل", ahmed_op_id))
        print_result(True, f"تم إنشاء عملية أحمد: {ahmed_op_id}")
        
        # أحمد - تحصيل 400 ريال
        print("🔸 تحصيل من أحمد (400 ريال)")
        payment_1_url = f"{BACKEND_URL}/operations/{ahmed_op_id}/confirm-payment"
        payment_1_data = {
            "workshopId": WORKSHOP_ID,
            "amount": 400.0,
            "payment_date": "2024-06-15"
        }
        
        print_api_call("POST", payment_1_url, data=payment_1_data)
        
        payment_1_response = requests.post(payment_1_url, json=payment_1_data, timeout=30)
        print(f"📊 كود الاستجابة: {payment_1_response.status_code}")
        
        if payment_1_response.status_code not in [200, 201]:
            print_result(False, f"فشل في تحصيل الدفعة الأولى من أحمد: {payment_1_response.status_code}")
        else:
            payment_1_result = payment_1_response.json()
            print_result(True, f"تم تحصيل 400 ريال من أحمد. الرصيد المتبقي: {payment_1_result.get('remaining', 0)}")
        
        # أحمد - تحصيل 200 ريال
        print("🔸 تحصيل من أحمد (200 ريال)")
        payment_2_data = {
            "workshopId": WORKSHOP_ID,
            "amount": 200.0,
            "payment_date": "2024-06-25"
        }
        
        print_api_call("POST", payment_1_url, data=payment_2_data)
        
        payment_2_response = requests.post(payment_1_url, json=payment_2_data, timeout=30)
        print(f"📊 كود الاستجابة: {payment_2_response.status_code}")
        
        if payment_2_response.status_code not in [200, 201]:
            print_result(False, f"فشل في تحصيل الدفعة الثانية من أحمد: {payment_2_response.status_code}")
        else:
            payment_2_result = payment_2_response.json()
            print_result(True, f"تم تحصيل 200 ريال من أحمد. الرصيد المتبقي: {payment_2_result.get('remaining', 0)}")
        
        # محمد - عملية آجل 720 ريال
        mohammed_credit_op = {
            "workshop_id": WORKSHOP_ID,
            "type": "sale",
            "partner_name": "محمد أحمد العميل",
            "items": [
                {
                    "name": "إصلاح محرك",
                    "quantity": 1,
                    "price": 720.0
                }
            ],
            "total": 720.0,
            "paymentMethod": "credit",
            "op_date": "2024-06-10"
        }
        
        print("🔸 إنشاء عملية محمد الآجلة (720 ريال)")
        print_api_call("POST", f"{BACKEND_URL}/operations", data=mohammed_credit_op)
        
        response = requests.post(f"{BACKEND_URL}/operations", json=mohammed_credit_op, timeout=30)
        print(f"📊 كود الاستجابة: {response.status_code}")
        
        if response.status_code not in [200, 201]:
            print_result(False, f"فشل في إنشاء عملية محمد: {response.status_code}")
        else:
            mohammed_op_data = response.json()
            mohammed_op_id = mohammed_op_data.get("id")
            operations_created.append(("محمد - آجل", mohammed_op_id))
            print_result(True, f"تم إنشاء عملية محمد: {mohammed_op_id}")
            
            # محمد - تحصيل كامل 720 ريال
            print("🔸 تحصيل كامل من محمد (720 ريال)")
            mohammed_payment_url = f"{BACKEND_URL}/operations/{mohammed_op_id}/confirm-payment"
            mohammed_payment_data = {
                "workshopId": WORKSHOP_ID,
                "amount": 720.0,
                "payment_date": "2024-06-20"
            }
            
            print_api_call("POST", mohammed_payment_url, data=mohammed_payment_data)
            
            mohammed_payment_response = requests.post(mohammed_payment_url, json=mohammed_payment_data, timeout=30)
            print(f"📊 كود الاستجابة: {mohammed_payment_response.status_code}")
            
            if mohammed_payment_response.status_code not in [200, 201]:
                print_result(False, f"فشل في تحصيل من محمد: {mohammed_payment_response.status_code}")
            else:
                mohammed_payment_result = mohammed_payment_response.json()
                print_result(True, f"تم تحصيل 720 ريال من محمد. الرصيد المتبقي: {mohammed_payment_result.get('remaining', 0)}")
        
        # سارة - عملية نقد 330 ريال
        sara_cash_op = {
            "workshop_id": WORKSHOP_ID,
            "type": "sale",
            "partner_name": "سارة علي العميلة",
            "items": [
                {
                    "name": "تغيير زيت وفلاتر",
                    "quantity": 1,
                    "price": 330.0
                }
            ],
            "total": 330.0,
            "paymentMethod": "cash",
            "op_date": "2024-06-12"
        }
        
        print("🔸 إنشاء عملية سارة النقدية (330 ريال)")
        print_api_call("POST", f"{BACKEND_URL}/operations", data=sara_cash_op)
        
        response = requests.post(f"{BACKEND_URL}/operations", json=sara_cash_op, timeout=30)
        print(f"📊 كود الاستجابة: {response.status_code}")
        
        if response.status_code not in [200, 201]:
            print_result(False, f"فشل في إنشاء عملية سارة: {response.status_code}")
        else:
            sara_op_data = response.json()
            sara_op_id = sara_op_data.get("id")
            operations_created.append(("سارة - نقد", sara_op_id))
            print_result(True, f"تم إنشاء عملية سارة: {sara_op_id}")
        
        print_result(True, f"تم إنشاء سيناريو يونيو 2024 بنجاح: {len(operations_created)} عمليات")
        return operations_created
        
    except Exception as e:
        print_result(False, f"خطأ في إنشاء السيناريو: {str(e)}")
        return []

def test_ar_customers_endpoint():
    """
    اختبار 2: نقطة نهاية عملاء الذمم المدينة
    Test 2: AR Customers endpoint - should show total_ar=180 and one customer Ahmed with 180
    """
    print_test_header("اختبار نقطة نهاية عملاء الذمم المدينة")
    
    try:
        url = f"{BACKEND_URL}/finance/ar/customers"
        params = {
            "workshop_id": WORKSHOP_ID,
            "as_of": "2024-06-30"
        }
        
        print_api_call("GET", url, params=params)
        
        response = requests.get(url, params=params, timeout=30)
        print(f"📊 كود الاستجابة: {response.status_code}")
        
        if response.status_code != 200:
            print_result(False, f"فشل في جلب عملاء الذمم المدينة: {response.status_code}")
            print(f"نص الاستجابة: {response.text}")
            return False
        
        data = response.json()
        print(f"📄 البيانات المستلمة: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        if not data.get("success"):
            print_result(False, f"فشل في الاستعلام: {data.get('message', 'خطأ غير محدد')}")
            return False
        
        ar_data = data.get("data", {})
        total_ar = ar_data.get("total_ar", 0)
        customers = ar_data.get("customers", [])
        
        # التحقق من إجمالي الذمم المدينة = 180
        if total_ar == 180:
            print_result(True, f"إجمالي الذمم المدينة صحيح: {total_ar} ريال")
        else:
            print_result(False, f"إجمالي الذمم المدينة خطأ: متوقع 180، الفعلي {total_ar}")
            return False
        
        # التحقق من وجود عميل واحد فقط (أحمد) برصيد 180
        ahmed_customers = [c for c in customers if "أحمد" in c.get("customer_name", "")]
        
        if len(ahmed_customers) == 1:
            ahmed = ahmed_customers[0]
            ahmed_balance = ahmed.get("balance", 0)
            
            if ahmed_balance == 180:
                print_result(True, f"رصيد أحمد صحيح: {ahmed_balance} ريال")
                return True
            else:
                print_result(False, f"رصيد أحمد خطأ: متوقع 180، الفعلي {ahmed_balance}")
                return False
        else:
            print_result(False, f"عدد عملاء أحمد خطأ: متوقع 1، الفعلي {len(ahmed_customers)}")
            return False
            
    except Exception as e:
        print_result(False, f"خطأ في اختبار عملاء الذمم المدينة: {str(e)}")
        return False

def test_ar_ledger_endpoint():
    """
    اختبار 3: نقطة نهاية دفتر الذمم المدينة
    Test 3: AR Ledger endpoint - should show ending_balance=180 for June
    """
    print_test_header("اختبار نقطة نهاية دفتر الذمم المدينة")
    
    try:
        url = f"{BACKEND_URL}/finance/ar/ledger"
        params = {
            "workshop_id": WORKSHOP_ID,
            "start_date": "2024-06-01",
            "end_date": "2024-06-30"
        }
        
        print_api_call("GET", url, params=params)
        
        response = requests.get(url, params=params, timeout=30)
        print(f"📊 كود الاستجابة: {response.status_code}")
        
        if response.status_code != 200:
            print_result(False, f"فشل في جلب دفتر الذمم المدينة: {response.status_code}")
            print(f"نص الاستجابة: {response.text}")
            return False
        
        data = response.json()
        print(f"📄 البيانات المستلمة: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        if not data.get("success"):
            print_result(False, f"فشل في الاستعلام: {data.get('message', 'خطأ غير محدد')}")
            return False
        
        ledger_data = data.get("data", {})
        ending_balance = ledger_data.get("ending_balance", 0)
        
        if ending_balance == 180:
            print_result(True, f"الرصيد النهائي لدفتر الذمم المدينة صحيح: {ending_balance} ريال")
            return True
        else:
            print_result(False, f"الرصيد النهائي خطأ: متوقع 180، الفعلي {ending_balance}")
            return False
            
    except Exception as e:
        print_result(False, f"خطأ في اختبار دفتر الذمم المدينة: {str(e)}")
        return False

def test_ar_customer_statement():
    """
    اختبار 4: كشف حساب العميل (أحمد)
    Test 4: Customer Statement for Ahmed - should show ending_balance=180
    """
    print_test_header("اختبار كشف حساب العميل (أحمد)")
    
    try:
        url = f"{BACKEND_URL}/finance/ar/customer-statement"
        params = {
            "workshop_id": WORKSHOP_ID,
            "customer": "أحمد محمد العميل",
            "start_date": "2024-06-01",
            "end_date": "2024-06-30"
        }
        
        print_api_call("GET", url, params=params)
        
        response = requests.get(url, params=params, timeout=30)
        print(f"📊 كود الاستجابة: {response.status_code}")
        
        if response.status_code != 200:
            print_result(False, f"فشل في جلب كشف حساب أحمد: {response.status_code}")
            print(f"نص الاستجابة: {response.text}")
            return False
        
        data = response.json()
        print(f"📄 البيانات المستلمة: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        if not data.get("success"):
            print_result(False, f"فشل في الاستعلام: {data.get('message', 'خطأ غير محدد')}")
            return False
        
        statement_data = data.get("data", {})
        ending_balance = statement_data.get("ending_balance", 0)
        
        if ending_balance == 180:
            print_result(True, f"الرصيد النهائي لكشف حساب أحمد صحيح: {ending_balance} ريال")
            return True
        else:
            print_result(False, f"الرصيد النهائي خطأ: متوقع 180، الفعلي {ending_balance}")
            return False
            
    except Exception as e:
        print_result(False, f"خطأ في اختبار كشف حساب العميل: {str(e)}")
        return False

def test_ar_aging_endpoint():
    """
    اختبار 5: تقرير أعمار الذمم المدينة
    Test 5: AR Aging report - should show total_ar=180 and 0_30=180
    """
    print_test_header("اختبار تقرير أعمار الذمم المدينة")
    
    try:
        url = f"{BACKEND_URL}/finance/ar/aging"
        params = {
            "workshop_id": WORKSHOP_ID,
            "as_of": "2024-06-30"
        }
        
        print_api_call("GET", url, params=params)
        
        response = requests.get(url, params=params, timeout=30)
        print(f"📊 كود الاستجابة: {response.status_code}")
        
        if response.status_code != 200:
            print_result(False, f"فشل في جلب تقرير أعمار الذمم: {response.status_code}")
            print(f"نص الاستجابة: {response.text}")
            return False
        
        data = response.json()
        print(f"📄 البيانات المستلمة: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        if not data.get("success"):
            print_result(False, f"فشل في الاستعلام: {data.get('message', 'خطأ غير محدد')}")
            return False
        
        aging_data = data.get("data", {})
        total_ar = aging_data.get("total_ar", 0)
        aging_buckets = aging_data.get("aging_buckets", {})
        bucket_0_30 = aging_buckets.get("0_30", 0)
        
        # التحقق من إجمالي الذمم المدينة = 180
        if total_ar == 180:
            print_result(True, f"إجمالي الذمم المدينة في تقرير الأعمار صحيح: {total_ar} ريال")
        else:
            print_result(False, f"إجمالي الذمم المدينة خطأ: متوقع 180، الفعلي {total_ar}")
            return False
        
        # التحقق من فئة 0-30 يوم = 180
        if bucket_0_30 == 180:
            print_result(True, f"فئة 0-30 يوم صحيحة: {bucket_0_30} ريال")
            return True
        else:
            print_result(False, f"فئة 0-30 يوم خطأ: متوقع 180، الفعلي {bucket_0_30}")
            return False
            
    except Exception as e:
        print_result(False, f"خطأ في اختبار تقرير أعمار الذمم: {str(e)}")
        return False

def test_ar_turnover_endpoint():
    """
    اختبار 6: تقرير دوران الذمم المدينة
    Test 6: AR Turnover report - should show credit_sales_total=1500 and closing_receivables=180
    """
    print_test_header("اختبار تقرير دوران الذمم المدينة")
    
    try:
        url = f"{BACKEND_URL}/finance/ar/turnover"
        params = {
            "workshop_id": WORKSHOP_ID,
            "start_date": "2024-06-01",
            "end_date": "2024-06-30",
            "credit_sales_total": 1500.0
        }
        
        print_api_call("GET", url, params=params)
        
        response = requests.get(url, params=params, timeout=30)
        print(f"📊 كود الاستجابة: {response.status_code}")
        
        if response.status_code != 200:
            print_result(False, f"فشل في جلب تقرير دوران الذمم: {response.status_code}")
            print(f"نص الاستجابة: {response.text}")
            return False
        
        data = response.json()
        print(f"📄 البيانات المستلمة: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        if not data.get("success"):
            print_result(False, f"فشل في الاستعلام: {data.get('message', 'خطأ غير محدد')}")
            return False
        
        turnover_data = data.get("data", {})
        credit_sales_total = turnover_data.get("credit_sales_total", 0)
        closing_receivables = turnover_data.get("closing_receivables", 0)
        
        # التحقق من إجمالي المبيعات الآجلة = 1500 (780 + 720)
        if credit_sales_total == 1500:
            print_result(True, f"إجمالي المبيعات الآجلة صحيح: {credit_sales_total} ريال")
        else:
            print_result(False, f"إجمالي المبيعات الآجلة خطأ: متوقع 1500، الفعلي {credit_sales_total}")
            return False
        
        # التحقق من الذمم المدينة الختامية = 180
        if closing_receivables == 180:
            print_result(True, f"الذمم المدينة الختامية صحيحة: {closing_receivables} ريال")
            return True
        else:
            print_result(False, f"الذمم المدينة الختامية خطأ: متوقع 180، الفعلي {closing_receivables}")
            return False
            
    except Exception as e:
        print_result(False, f"خطأ في اختبار تقرير دوران الذمم: {str(e)}")
        return False

def run_ar_endpoints_tests():
    """تشغيل جميع اختبارات نقاط نهاية الذمم المدينة"""
    print("🚀 بدء اختبار نقاط نهاية الذمم المدينة (AR Endpoints)")
    print(f"🌐 رابط الخادم: {BACKEND_URL}")
    print(f"🏪 معرف الورشة: {WORKSHOP_ID}")
    print(f"⏰ وقت الاختبار: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = []
    
    # اختبار 1: إعادة تعيين جميع البيانات
    print_test_header("المرحلة 1: إعادة تعيين البيانات")
    reset_success = test_reset_all_data()
    results.append(("إعادة تعيين جميع البيانات", reset_success))
    
    if not reset_success:
        print("❌ فشل في إعادة تعيين البيانات. توقف الاختبار.")
        return False
    
    # إنشاء سيناريو يونيو 2024
    print_test_header("المرحلة 2: إنشاء سيناريو يونيو 2024")
    operations = create_june_2024_scenario()
    
    if not operations:
        print("❌ فشل في إنشاء السيناريو. توقف الاختبار.")
        return False
    
    # اختبار نقاط نهاية الذمم المدينة
    print_test_header("المرحلة 3: اختبار نقاط نهاية الذمم المدينة")
    
    # اختبار 2: عملاء الذمم المدينة
    results.append(("عملاء الذمم المدينة", test_ar_customers_endpoint()))
    
    # اختبار 3: دفتر الذمم المدينة
    results.append(("دفتر الذمم المدينة", test_ar_ledger_endpoint()))
    
    # اختبار 4: كشف حساب العميل
    results.append(("كشف حساب العميل", test_ar_customer_statement()))
    
    # اختبار 5: تقرير أعمار الذمم
    results.append(("تقرير أعمار الذمم المدينة", test_ar_aging_endpoint()))
    
    # اختبار 6: تقرير دوران الذمم
    results.append(("تقرير دوران الذمم المدينة", test_ar_turnover_endpoint()))
    
    # ملخص النتائج
    print_test_header("ملخص نتائج اختبار نقاط نهاية الذمم المدينة")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ نجح" if result else "❌ فشل"
        print(f"{status} {test_name}")
    
    print(f"\n📊 النتيجة النهائية: {passed}/{total} اختبارات نجحت")
    
    if passed == total:
        print("🎉 جميع اختبارات نقاط نهاية الذمم المدينة نجحت!")
        print("\n📋 ملخص النتائج المتوقعة:")
        print("   • إجمالي الذمم المدينة: 180 ريال")
        print("   • عميل واحد (أحمد) برصيد: 180 ريال")
        print("   • إجمالي المبيعات الآجلة: 1500 ريال")
        print("   • فئة 0-30 يوم: 180 ريال")
        return True
    else:
        print(f"⚠️ {total - passed} اختبارات فشلت")
        return False

if __name__ == "__main__":
    success = run_ar_endpoints_tests()
    exit(0 if success else 1)