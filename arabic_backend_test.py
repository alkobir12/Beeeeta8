#!/usr/bin/env python3
"""
اختبار التغييرات الجديدة للباك-إند - Arabic Backend Changes Testing
Testing specific backend changes as requested in Arabic:
1. /api/finance-bot/chat - fast_only analysis
2. /api/operations - credit payment method
3. /api/finance/journal-entries - transaction_type field
"""

import requests
import json
import time
from datetime import datetime

# Configuration
BACKEND_URL = "https://accounting-ssot-fix.preview.emergentagent.com/api"
WORKSHOP_ID = "finmodule-sync"

def print_test_header(test_name):
    """Print formatted test header"""
    print(f"\n{'='*70}")
    print(f"🧪 {test_name}")
    print(f"{'='*70}")

def print_result(success, message, details=None):
    """Print test result with formatting"""
    status = "✅ نجح" if success else "❌ فشل"
    print(f"{status}: {message}")
    if details:
        print(f"التفاصيل: {details}")

def test_finance_bot_fast_analysis():
    """
    اختبار 1: /api/finance-bot/chat - تحليل سريع (fast_only)
    POST برسالة قصيرة "تنبيه سريع" مع financial_data
    تحقق أن الاستجابة ترجع بسرعة وتحتوي "ملاحظات سريعة (تحليل قواعدي)"
    """
    print_test_header("اختبار التحليل السريع للبوت المالي - Finance Bot Fast Analysis")
    
    try:
        url = f"{BACKEND_URL}/finance-bot/chat"
        print(f"📡 استدعاء: POST {url}")
        
        # بيانات الاختبار مع financial_data لتفعيل التحليل السريع
        test_data = {
            "message": "تنبيه سريع",
            "workshop_id": WORKSHOP_ID,
            "financial_data": {
                "revenue": 10000,
                "expenses": 9500,
                "assets": 50000,
                "liabilities": 30000,
                "cash_flow": 500,
                "profit_margin": 5.0,
                "debt_ratio": 60.0
            }
        }
        
        print(f"📤 البيانات المرسلة:")
        print(json.dumps(test_data, indent=2, ensure_ascii=False))
        
        # قياس وقت الاستجابة
        start_time = time.time()
        response = requests.post(url, json=test_data, timeout=60)
        response_time = time.time() - start_time
        
        print(f"📊 كود الاستجابة: {response.status_code}")
        print(f"⏱️ وقت الاستجابة: {response_time:.2f} ثانية")
        
        if response.status_code == 200:
            data = response.json()
            print(f"📄 البيانات المستلمة:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            
            # التحقق من وجود الاستجابة والـ conversation_id
            if "response" in data and "conversation_id" in data:
                response_text = data["response"]
                
                # التحقق من وجود "ملاحظات سريعة (تحليل قواعدي)" في الاستجابة
                if "ملاحظات سريعة (تحليل قواعدي)" in response_text:
                    print_result(True, "التحليل السريع يعمل بشكل صحيح")
                    print(f"🔍 تم العثور على قسم التحليل القواعدي في الاستجابة")
                    print(f"🆔 معرف المحادثة: {data['conversation_id']}")
                    return True
                else:
                    print_result(False, "لم يتم العثور على قسم التحليل القواعدي في الاستجابة")
                    print(f"📝 نص الاستجابة: {response_text[:500]}...")
                    return False
            else:
                print_result(False, "هيكل الاستجابة غير صحيح - مفقود response أو conversation_id")
                return False
        else:
            print_result(False, f"فشل في الاستدعاء - كود الخطأ: {response.status_code}")
            print(f"📄 رسالة الخطأ: {response.text}")
            return False
            
    except Exception as e:
        print_result(False, f"خطأ في الاختبار: {str(e)}")
        return False

def test_operations_credit_payment():
    """
    اختبار 2: /api/operations - طريقة الدفع الآجل
    POST عملية sale أو purchase مع paymentMethod='credit'
    تأكد أن العملية تُحفظ وترجع paymentMethod=credit
    """
    print_test_header("اختبار عمليات الدفع الآجل - Operations Credit Payment")
    
    try:
        url = f"{BACKEND_URL}/operations"
        print(f"📡 استدعاء: POST {url}")
        
        # بيانات عملية بيع بالآجل
        test_data = {
            "workshop_id": WORKSHOP_ID,
            "type": "sale",
            "partner_type": "customer",
            "partner_name": "عميل اختبار الآجل",
            "items": [
                {
                    "item_type": "service",
                    "item_id": "srv_001",
                    "name": "خدمة صيانة آجلة",
                    "qty": 1,
                    "price": 500.0
                }
            ],
            "total": 500.0,
            "paymentMethod": "credit",
            "op_date": datetime.now().strftime("%Y-%m-%d"),
            "notes": "عملية اختبار للدفع الآجل"
        }
        
        print(f"📤 البيانات المرسلة:")
        print(json.dumps(test_data, indent=2, ensure_ascii=False))
        
        response = requests.post(url, json=test_data, timeout=30)
        print(f"📊 كود الاستجابة: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"📄 البيانات المستلمة:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            
            # التحقق من حفظ paymentMethod=credit
            # الاستجابة ترجع العملية مباشرة بدون success wrapper
            if "id" in data and "paymentMethod" in data:
                if data.get("paymentMethod") == "credit":
                    print_result(True, "تم حفظ العملية بطريقة الدفع الآجل بنجاح")
                    print(f"🆔 معرف العملية: {data.get('id')}")
                    return data.get('id')
                else:
                    print_result(False, f"طريقة الدفع غير صحيحة: {data.get('paymentMethod')}")
                    return False
            else:
                print_result(False, "هيكل الاستجابة غير صحيح - مفقود id أو paymentMethod")
                return False
        else:
            print_result(False, f"فشل في الاستدعاء - كود الخطأ: {response.status_code}")
            print(f"📄 رسالة الخطأ: {response.text}")
            return False
            
    except Exception as e:
        print_result(False, f"خطأ في الاختبار: {str(e)}")
        return False

def test_journal_entries_transaction_type():
    """
    اختبار 3: /api/finance/journal-entries - حقل transaction_type
    POST قيد transaction_type='sale' أو 'purchase'
    تأكد أن transaction_type يُخزن ويُرجع بشكل صحيح
    """
    print_test_header("اختبار حقل نوع المعاملة في القيود - Journal Entries Transaction Type")
    
    try:
        url = f"{BACKEND_URL}/finance/journal-entries"
        print(f"📡 استدعاء: POST {url}")
        
        # بيانات قيد محاسبي مع transaction_type
        test_data = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "description": "اختبار قيد بيع مع نوع المعاملة",
            "transaction_type": "sale",
            "lines": [
                {
                    "account": "101",
                    "account_name": "النقدية",
                    "debit": 1000.0,
                    "credit": 0.0
                },
                {
                    "account": "411",
                    "account_name": "إيرادات المبيعات",
                    "debit": 0.0,
                    "credit": 1000.0
                }
            ],
            "total": 1000.0
        }
        
        print(f"📤 البيانات المرسلة:")
        print(json.dumps(test_data, indent=2, ensure_ascii=False))
        
        # إرسال workshop_id كـ query parameter
        params = {"workshop_id": WORKSHOP_ID}
        response = requests.post(url, json=test_data, params=params, timeout=30)
        print(f"📊 كود الاستجابة: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"📄 البيانات المستلمة:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            
            # التحقق من حفظ transaction_type
            if "success" in data and data["success"]:
                if "data" in data and isinstance(data["data"], list) and len(data["data"]) > 0:
                    entry = data["data"][0]
                    if entry.get("transaction_type") == "sale":
                        print_result(True, "تم حفظ القيد مع نوع المعاملة بنجاح")
                        print(f"🆔 معرف القيد: {entry.get('id')}")
                        
                        # اختبار إضافي: استرجاع القيود للتأكد من الحفظ
                        return test_retrieve_journal_entry_with_transaction_type(entry.get('id'))
                    else:
                        print_result(False, f"نوع المعاملة غير صحيح: {entry.get('transaction_type')}")
                        return False
                else:
                    print_result(False, "هيكل الاستجابة غير صحيح - مفقود data أو فارغ")
                    return False
            else:
                print_result(False, "فشل في إنشاء القيد")
                return False
        else:
            print_result(False, f"فشل في الاستدعاء - كود الخطأ: {response.status_code}")
            print(f"📄 رسالة الخطأ: {response.text}")
            return False
            
    except Exception as e:
        print_result(False, f"خطأ في الاختبار: {str(e)}")
        return False

def test_retrieve_journal_entry_with_transaction_type(entry_id):
    """
    اختبار إضافي: استرجاع القيد للتأكد من حفظ transaction_type
    """
    print(f"\n🔍 اختبار إضافي: استرجاع القيد {entry_id}")
    
    try:
        url = f"{BACKEND_URL}/finance/journal-entries"
        print(f"📡 استدعاء: GET {url}")
        
        params = {"workshop_id": WORKSHOP_ID}
        response = requests.get(url, params=params, timeout=30)
        print(f"📊 كود الاستجابة: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            if "success" in data and data["success"] and "data" in data:
                entries = data["data"]
                
                # البحث عن القيد المُنشأ
                for entry in entries:
                    if entry.get("id") == entry_id:
                        if entry.get("transaction_type") == "sale":
                            print_result(True, "تم العثور على القيد مع نوع المعاملة المحفوظ")
                            return True
                        else:
                            print_result(False, f"نوع المعاملة مفقود أو غير صحيح: {entry.get('transaction_type')}")
                            return False
                
                print_result(False, f"لم يتم العثور على القيد {entry_id}")
                return False
            else:
                print_result(False, "فشل في استرجاع القيود")
                return False
        else:
            print_result(False, f"فشل في استرجاع القيود - كود الخطأ: {response.status_code}")
            return False
            
    except Exception as e:
        print_result(False, f"خطأ في اختبار الاسترجاع: {str(e)}")
        return False

def main():
    """تشغيل جميع الاختبارات"""
    print("🚀 بدء اختبار التغييرات الجديدة للباك-إند")
    print(f"🌐 رابط الباك-إند: {BACKEND_URL}")
    print(f"🏪 معرف الورشة: {WORKSHOP_ID}")
    print(f"📅 وقت الاختبار: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = []
    
    # اختبار 1: التحليل السريع للبوت المالي
    results.append(("اختبار التحليل السريع للبوت المالي", test_finance_bot_fast_analysis()))
    
    # اختبار 2: عمليات الدفع الآجل
    results.append(("اختبار عمليات الدفع الآجل", test_operations_credit_payment()))
    
    # اختبار 3: حقل نوع المعاملة في القيود
    results.append(("اختبار حقل نوع المعاملة", test_journal_entries_transaction_type()))
    
    # ملخص النتائج
    print(f"\n{'='*70}")
    print("📊 ملخص نتائج الاختبار")
    print(f"{'='*70}")
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ نجح" if result else "❌ فشل"
        print(f"{status}: {test_name}")
        if result:
            passed += 1
    
    print(f"\n📈 النتيجة النهائية: {passed}/{total} اختبارات نجحت")
    
    if passed == total:
        print("🎉 جميع الاختبارات نجحت! التغييرات الجديدة تعمل بشكل صحيح.")
    else:
        print("⚠️ بعض الاختبارات فشلت. يرجى مراجعة التفاصيل أعلاه.")
    
    return passed == total

if __name__ == "__main__":
    main()