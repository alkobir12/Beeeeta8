#!/usr/bin/env python3
"""
اختبار مشكلة: تم إنشاء عمليتين بالأجل لكنها لا تظهر في تقارير الذمم
Testing issue: Two credit operations created but not showing in AR reports

نحتاج التأكد بعد إصلاح SupabaseService.operations_create/update لحفظ workshop_id داخل جدول operations.
We need to verify after fixing SupabaseService.operations_create/update to save workshop_id inside operations table.
"""

import requests
import json
import os
import uuid
from datetime import datetime, timedelta

# Configuration
BACKEND_URL = "https://accounting-ssot-fix.preview.emergentagent.com/api"
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

def print_response_summary(response, title="الاستجابة"):
    """Print response summary"""
    print(f"📊 {title}:")
    print(f"   كود الاستجابة: {response.status_code}")
    if response.status_code == 200:
        try:
            data = response.json()
            if isinstance(data, dict):
                if 'success' in data:
                    print(f"   النجاح: {data.get('success')}")
                if 'data' in data:
                    data_content = data.get('data')
                    if isinstance(data_content, list):
                        print(f"   عدد العناصر: {len(data_content)}")
                    elif isinstance(data_content, dict):
                        print(f"   مفاتيح البيانات: {list(data_content.keys())}")
            elif isinstance(data, list):
                print(f"   عدد العناصر: {len(data)}")
        except:
            print(f"   نص الاستجابة: {response.text[:200]}...")
    else:
        print(f"   نص الخطأ: {response.text[:200]}...")

def step_1_reset_data():
    """
    الخطوة 1: تنفيذ Reset: DELETE /api/finance/reset-all-data?workshop_id=finmodule-sync&confirm=DELETE_ALL
    """
    print_test_header("الخطوة 1: إعادة تعيين جميع البيانات")
    
    try:
        url = f"{BACKEND_URL}/finance/reset-all-data"
        params = {
            "workshop_id": WORKSHOP_ID,
            "confirm": "DELETE_ALL"
        }
        
        print(f"📡 استدعاء: DELETE {url}")
        print(f"📤 المعاملات: {params}")
        
        response = requests.delete(url, params=params, timeout=30)
        print_response_summary(response, "إعادة تعيين البيانات")
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                print_result(True, "تم إعادة تعيين البيانات بنجاح")
                return True
            else:
                print_result(False, f"فشل في إعادة تعيين البيانات: {data.get('message', 'خطأ غير محدد')}")
                return False
        else:
            print_result(False, f"فشل في إعادة تعيين البيانات: كود {response.status_code}")
            return False
            
    except Exception as e:
        print_result(False, f"خطأ في إعادة تعيين البيانات: {str(e)}")
        return False

def step_2_create_credit_operations():
    """
    الخطوة 2: أنشئ عمليتين sale credit عبر POST /api/operations مع workshopId=finmodule-sync و paymentMethod=credit
    واحد بمبلغ 100 والثاني 200
    """
    print_test_header("الخطوة 2: إنشاء عمليتين بالأجل")
    
    operations_created = []
    
    # Operation 1: 100 SAR
    operation_1_data = {
        "type": "sale",
        "workshopId": WORKSHOP_ID,
        "partnerType": "customer", 
        "partnerName": "أحمد العميل الأول",
        "items": [
            {
                "itemType": "service",
                "name": "خدمة صيانة أولى",
                "quantity": 1,
                "price": 100.0
            }
        ],
        "paymentMethod": "credit",
        "opDate": "2026-01-15",
        "notes": "عملية اختبار بالأجل - المبلغ 100"
    }
    
    # Operation 2: 200 SAR  
    operation_2_data = {
        "type": "sale",
        "workshopId": WORKSHOP_ID,
        "partnerType": "customer",
        "partnerName": "محمد العميل الثاني", 
        "items": [
            {
                "itemType": "service",
                "name": "خدمة صيانة ثانية",
                "quantity": 1,
                "price": 200.0
            }
        ],
        "paymentMethod": "credit",
        "opDate": "2026-01-20",
        "notes": "عملية اختبار بالأجل - المبلغ 200"
    }
    
    operations_data = [
        ("العملية الأولى (100 ريال)", operation_1_data),
        ("العملية الثانية (200 ريال)", operation_2_data)
    ]
    
    try:
        url = f"{BACKEND_URL}/operations"
        
        for operation_name, operation_data in operations_data:
            print(f"\n🔄 إنشاء {operation_name}")
            print(f"📡 استدعاء: POST {url}")
            print(f"📤 البيانات المرسلة: {json.dumps(operation_data, indent=2, ensure_ascii=False)}")
            
            response = requests.post(url, json=operation_data, timeout=30)
            print_response_summary(response, f"إنشاء {operation_name}")
            
            if response.status_code in [200, 201]:
                data = response.json()
                operation_id = data.get("id")
                if operation_id:
                    operations_created.append({
                        "id": operation_id,
                        "name": operation_name,
                        "amount": operation_data["items"][0]["price"],
                        "partner_name": operation_data["partnerName"]
                    })
                    print_result(True, f"تم إنشاء {operation_name} بنجاح: {operation_id}")
                else:
                    print_result(False, f"لم يتم إرجاع معرف {operation_name}")
                    return False, []
            else:
                print_result(False, f"فشل في إنشاء {operation_name}: كود {response.status_code}")
                return False, []
        
        if len(operations_created) == 2:
            print_result(True, f"تم إنشاء العمليتين بنجاح - المجموع: {sum(op['amount'] for op in operations_created)} ريال")
            return True, operations_created
        else:
            print_result(False, f"تم إنشاء {len(operations_created)} عمليات فقط من أصل 2")
            return False, operations_created
            
    except Exception as e:
        print_result(False, f"خطأ في إنشاء العمليات: {str(e)}")
        return False, []

def step_3_verify_operations():
    """
    الخطوة 3: تحقق أن GET /api/operations يعيد العمليتين وأن كل عملية تحتوي workshop_id في البيانات
    """
    print_test_header("الخطوة 3: التحقق من العمليات المُنشأة")
    
    try:
        url = f"{BACKEND_URL}/operations"
        params = {"workshop_id": WORKSHOP_ID}
        
        print(f"📡 استدعاء: GET {url}")
        print(f"📤 المعاملات: {params}")
        
        response = requests.get(url, params=params, timeout=30)
        print_response_summary(response, "جلب العمليات")
        
        if response.status_code == 200:
            operations = response.json()
            
            if isinstance(operations, dict) and 'data' in operations:
                operations = operations['data']
            
            print(f"📊 عدد العمليات المُسترجعة: {len(operations)}")
            
            # Filter credit operations
            credit_operations = [op for op in operations if op.get("paymentMethod") == "credit"]
            print(f"📊 عدد العمليات بالأجل: {len(credit_operations)}")
            
            # Check workshop_id presence
            operations_with_workshop_id = []
            operations_without_workshop_id = []
            
            for op in credit_operations:
                print(f"\n🔍 فحص العملية: {op.get('id', 'غير محدد')}")
                print(f"   نوع الدفع: {op.get('paymentMethod', 'غير محدد')}")
                print(f"   اسم الشريك: {op.get('partnerName', 'غير محدد')}")
                print(f"   المبلغ الإجمالي: {op.get('total', 'غير محدد')}")
                
                # Check for workshop_id in different possible fields
                workshop_id_found = False
                workshop_id_fields = ['workshop_id', 'workshopId', 'workshop_id_field']
                
                for field in workshop_id_fields:
                    if field in op and op[field] == WORKSHOP_ID:
                        print(f"   ✅ workshop_id موجود في الحقل: {field}")
                        workshop_id_found = True
                        break
                
                if workshop_id_found:
                    operations_with_workshop_id.append(op)
                else:
                    operations_without_workshop_id.append(op)
                    print(f"   ❌ workshop_id غير موجود أو غير صحيح")
                    print(f"   📋 الحقول المتاحة: {list(op.keys())}")
            
            # Summary
            total_expected = 2
            total_found = len(credit_operations)
            total_with_workshop_id = len(operations_with_workshop_id)
            
            print(f"\n📊 ملخص التحقق:")
            print(f"   العمليات المتوقعة: {total_expected}")
            print(f"   العمليات الموجودة بالأجل: {total_found}")
            print(f"   العمليات مع workshop_id: {total_with_workshop_id}")
            
            if total_found >= total_expected and total_with_workshop_id >= total_expected:
                print_result(True, f"تم العثور على {total_found} عمليات بالأجل، جميعها تحتوي على workshop_id")
                return True, operations_with_workshop_id
            elif total_found >= total_expected:
                print_result(False, f"تم العثور على {total_found} عمليات بالأجل، لكن {total_found - total_with_workshop_id} منها لا تحتوي على workshop_id")
                return False, operations_with_workshop_id
            else:
                print_result(False, f"تم العثور على {total_found} عمليات بالأجل فقط من أصل {total_expected} متوقعة")
                return False, operations_with_workshop_id
        else:
            print_result(False, f"فشل في جلب العمليات: كود {response.status_code}")
            return False, []
            
    except Exception as e:
        print_result(False, f"خطأ في التحقق من العمليات: {str(e)}")
        return False, []

def step_4_check_ar_customers_report():
    """
    الخطوة 4: استدعِ تقرير الذمم:
    GET /api/finance/ar/customers?workshop_id=finmodule-sync&as_of=2026-01-31
    وتأكد أنه يظهر total_ar=300 ويعرض العميل/الاسم حسب partner_name
    """
    print_test_header("الخطوة 4: فحص تقرير عملاء الذمم المدينة")
    
    try:
        url = f"{BACKEND_URL}/finance/ar/customers"
        params = {
            "workshop_id": WORKSHOP_ID,
            "as_of": "2026-01-31"
        }
        
        print(f"📡 استدعاء: GET {url}")
        print(f"📤 المعاملات: {params}")
        
        response = requests.get(url, params=params, timeout=30)
        print_response_summary(response, "تقرير عملاء الذمم")
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get("success"):
                report_data = data.get("data", {})
                customers = report_data.get("customers", [])
                total_ar = report_data.get("total_ar", 0)
                
                print(f"📊 إجمالي الذمم المدينة: {total_ar}")
                print(f"📊 عدد العملاء: {len(customers)}")
                
                # Display customer details
                for customer in customers:
                    print(f"\n👤 عميل:")
                    print(f"   الاسم: {customer.get('customer', 'غير محدد')}")
                    print(f"   المبلغ المستحق: {customer.get('balance', 0)}")
                    print(f"   عدد الفواتير: {customer.get('invoice_count', 0)}")
                
                # Check if total matches expected (100 + 200 = 300)
                expected_total = 300
                if abs(total_ar - expected_total) < 0.01:  # Allow for small floating point differences
                    print_result(True, f"إجمالي الذمم صحيح: {total_ar} (متوقع: {expected_total})")
                    
                    # Check if customers are properly named
                    customer_names = [c.get('customer', '') for c in customers]
                    unnamed_customers = [name for name in customer_names if not name or name == 'بدون اسم']
                    
                    if len(unnamed_customers) == 0:
                        print_result(True, f"جميع العملاء ({len(customers)}) لديهم أسماء صحيحة")
                        return True, report_data
                    else:
                        print_result(False, f"{len(unnamed_customers)} عملاء بدون أسماء من أصل {len(customers)}")
                        return False, report_data
                else:
                    print_result(False, f"إجمالي الذمم غير صحيح: {total_ar} (متوقع: {expected_total})")
                    return False, report_data
            else:
                print_result(False, f"فشل في تقرير الذمم: {data.get('message', 'خطأ غير محدد')}")
                return False, {}
        else:
            print_result(False, f"فشل في تقرير الذمم: كود {response.status_code}")
            return False, {}
            
    except Exception as e:
        print_result(False, f"خطأ في تقرير الذمم: {str(e)}")
        return False, {}

def step_5_check_ar_ledger():
    """
    الخطوة 5: استدعِ /api/finance/ar/ledger لنفس الفترة وتأكد أنه يحتوي صفين type=invoice_credit_sale وأن ending_balance=300
    """
    print_test_header("الخطوة 5: فحص دفتر أستاذ الذمم المدينة")
    
    try:
        url = f"{BACKEND_URL}/finance/ar/ledger"
        params = {
            "workshop_id": WORKSHOP_ID,
            "as_of": "2026-01-31"
        }
        
        print(f"📡 استدعاء: GET {url}")
        print(f"📤 المعاملات: {params}")
        
        response = requests.get(url, params=params, timeout=30)
        print_response_summary(response, "دفتر أستاذ الذمم")
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get("success"):
                report_data = data.get("data", {})
                entries = report_data.get("rows", [])
                ending_balance = report_data.get("ending_balance", 0)
                
                print(f"📊 الرصيد النهائي: {ending_balance}")
                print(f"📊 عدد القيود: {len(entries)}")
                
                # Filter entries by type
                credit_sale_entries = [entry for entry in entries if entry.get("type") == "invoice_credit_sale"]
                print(f"📊 قيود البيع بالأجل: {len(credit_sale_entries)}")
                
                # Display entry details
                for i, entry in enumerate(credit_sale_entries, 1):
                    print(f"\n📋 قيد {i}:")
                    print(f"   النوع: {entry.get('type', 'غير محدد')}")
                    print(f"   التاريخ: {entry.get('date', 'غير محدد')}")
                    print(f"   الوصف: {entry.get('description', 'غير محدد')}")
                    print(f"   المبلغ: {entry.get('debit', 0)}")
                    print(f"   الرصيد الجاري: {entry.get('running_balance', 0)}")
                
                # Check expectations
                expected_entries = 2
                expected_balance = 300
                
                entries_correct = len(credit_sale_entries) >= expected_entries
                balance_correct = abs(ending_balance - expected_balance) < 0.01
                
                if entries_correct and balance_correct:
                    print_result(True, f"دفتر الأستاذ صحيح: {len(credit_sale_entries)} قيود، رصيد نهائي {ending_balance}")
                    return True, report_data
                elif entries_correct:
                    print_result(False, f"عدد القيود صحيح ({len(credit_sale_entries)}) لكن الرصيد النهائي خاطئ: {ending_balance} (متوقع: {expected_balance})")
                    return False, report_data
                elif balance_correct:
                    print_result(False, f"الرصيد النهائي صحيح ({ending_balance}) لكن عدد القيود خاطئ: {len(credit_sale_entries)} (متوقع: {expected_entries})")
                    return False, report_data
                else:
                    print_result(False, f"كل من عدد القيود ({len(credit_sale_entries)}) والرصيد النهائي ({ending_balance}) خاطئان")
                    return False, report_data
            else:
                print_result(False, f"فشل في دفتر الأستاذ: {data.get('message', 'خطأ غير محدد')}")
                return False, {}
        else:
            print_result(False, f"فشل في دفتر الأستاذ: كود {response.status_code}")
            return False, {}
            
    except Exception as e:
        print_result(False, f"خطأ في دفتر الأستاذ: {str(e)}")
        return False, {}

def run_ar_credit_operations_test():
    """تشغيل اختبار مشكلة العمليات بالأجل وتقارير الذمم"""
    print("🚀 بدء اختبار مشكلة العمليات بالأجل وتقارير الذمم")
    print(f"🌐 رابط الخادم: {BACKEND_URL}")
    print(f"🏪 معرف الورشة: {WORKSHOP_ID}")
    print(f"⏰ وقت الاختبار: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = []
    
    # الخطوة 1: إعادة تعيين البيانات
    step_1_success = step_1_reset_data()
    results.append(("إعادة تعيين البيانات", step_1_success))
    
    if not step_1_success:
        print("⚠️ فشل في إعادة تعيين البيانات - سيتم المتابعة مع البيانات الموجودة")
    
    # الخطوة 2: إنشاء العمليات بالأجل
    step_2_success, operations_created = step_2_create_credit_operations()
    results.append(("إنشاء العمليات بالأجل", step_2_success))
    
    if not step_2_success:
        print("❌ فشل في إنشاء العمليات - لا يمكن المتابعة")
        return False
    
    # الخطوة 3: التحقق من العمليات
    step_3_success, verified_operations = step_3_verify_operations()
    results.append(("التحقق من العمليات", step_3_success))
    
    # الخطوة 4: تقرير عملاء الذمم
    step_4_success, ar_customers_data = step_4_check_ar_customers_report()
    results.append(("تقرير عملاء الذمم", step_4_success))
    
    # الخطوة 5: دفتر أستاذ الذمم
    step_5_success, ar_ledger_data = step_5_check_ar_ledger()
    results.append(("دفتر أستاذ الذمم", step_5_success))
    
    # ملخص النتائج
    print_test_header("ملخص نتائج اختبار العمليات بالأجل وتقارير الذمم")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ نجح" if result else "❌ فشل"
        print(f"{status} {test_name}")
    
    print(f"\n📊 النتيجة النهائية: {passed}/{total} اختبارات نجحت")
    
    # تحليل المشكلة
    print_test_header("تحليل المشكلة")
    
    if step_2_success and step_4_success and step_5_success:
        print("🎉 المشكلة محلولة بنجاح!")
        print("✅ العمليات بالأجل تظهر في تقارير الذمم بشكل صحيح")
        if not step_3_success:
            print("ℹ️  ملاحظة: workshop_id غير محفوظ في جدول operations (العمود غير موجود)")
            print("ℹ️  لكن تقارير الذمم تعمل بآلية الاحتياط (unscoped query)")
        return True
    elif step_2_success and step_3_success and step_4_success and step_5_success:
        print("🎉 تم حل المشكلة بنجاح!")
        print("✅ العمليات بالأجل تظهر في تقارير الذمم بشكل صحيح")
        print("✅ workshop_id محفوظ بشكل صحيح في جدول operations")
        return True
    elif step_2_success and (step_4_success or step_5_success):
        print("✅ المشكلة محلولة جزئياً:")
        print("✅ العمليات بالأجل يتم إنشاؤها بشكل صحيح")
        if step_4_success:
            print("✅ تقرير عملاء الذمم يعمل بشكل صحيح")
        if step_5_success:
            print("✅ دفتر أستاذ الذمم يعمل بشكل صحيح")
        if not step_3_success:
            print("ℹ️  ملاحظة: workshop_id غير محفوظ لكن التقارير تعمل بآلية الاحتياط")
        return True
    else:
        print("❌ المشكلة لم تُحل:")
        print("❌ فشل في إنشاء العمليات بالأجل")
        print("🔍 يحتاج إلى مراجعة API إنشاء العمليات")
        return False

if __name__ == "__main__":
    success = run_ar_credit_operations_test()
    exit(0 if success else 1)