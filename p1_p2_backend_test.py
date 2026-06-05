#!/usr/bin/env python3
"""
اختبار التغييرات الجديدة P1 و P2
Testing P1 (finance-bot safe analysis) and P2 (transaction_type) changes
"""

import requests
import json
import os
from datetime import datetime
import uuid

# Configuration
BACKEND_URL = "https://workshop-helper-7.preview.emergentagent.com/api"
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

def test_p1_finance_bot_safe_analysis():
    """
    P1: اختبار تحليل البوت المالي الآمن
    POST /api/finance-bot/chat مع financial_data
    يجب أن يحتوي الرد على "ملاحظات سريعة (تحليل قواعدي):"
    """
    print_test_header("P1: اختبار تحليل البوت المالي الآمن")
    
    try:
        url = f"{BACKEND_URL}/finance-bot/chat"
        print(f"📡 استدعاء: POST {url}")
        
        # إعداد البيانات المالية للاختبار (بيانات تؤدي إلى تحليل قواعدي)
        payload = {
            "message": "حلل الوضع المالي للورشة",
            "workshop_id": WORKSHOP_ID,
            "financial_data": {
                "revenue": 10000,
                "expenses": 9500,  # هامش ربح منخفض لتفعيل التحليل القواعدي
                "assets": 50000,
                "liabilities": 30000,  # نسبة التزامات عالية لتفعيل التحليل
                "cash_flow": 500,
                "profit_margin": 5  # هامش ربح منخفض
            }
        }
        
        print(f"📤 البيانات المرسلة:")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        
        response = requests.post(url, json=payload, timeout=60)
        print(f"📊 كود الاستجابة: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"📄 البيانات المستلمة:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            
            # التحقق من وجود conversation_id
            conversation_id = data.get("conversation_id")
            if conversation_id:
                print_result(True, f"conversation_id موجود: {conversation_id}")
            else:
                print_result(False, "conversation_id غير موجود في الاستجابة")
                return False
            
            # التحقق من وجود النص المطلوب في الاستجابة
            response_text = data.get("response", "")
            required_text = "ملاحظات سريعة (تحليل قواعدي):"
            
            if required_text in response_text:
                print_result(True, f"النص المطلوب موجود: '{required_text}'")
                print(f"📝 جزء من الاستجابة: {response_text[:500]}...")
                return True
            else:
                print_result(False, f"النص المطلوب غير موجود: '{required_text}'")
                print(f"📝 الاستجابة الكاملة: {response_text}")
                return False
                
        else:
            print_result(False, f"فشل الطلب - كود الخطأ: {response.status_code}")
            print(f"📄 رسالة الخطأ: {response.text}")
            return False
            
    except Exception as e:
        print_result(False, f"خطأ في الاختبار: {str(e)}")
        return False

def test_p2_transaction_type_creation():
    """
    P2: اختبار إنشاء قيد محاسبي مع transaction_type
    POST /api/finance/journal-entries?workshop_id=finmodule-sync مع transaction_type='expense'
    """
    print_test_header("P2: اختبار إنشاء قيد محاسبي مع transaction_type")
    
    try:
        url = f"{BACKEND_URL}/finance/journal-entries"
        params = {"workshop_id": WORKSHOP_ID}
        print(f"📡 استدعاء: POST {url}?workshop_id={WORKSHOP_ID}")
        
        # إعداد بيانات القيد المحاسبي
        entry_id = str(uuid.uuid4())
        payload = {
            "id": entry_id,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "description": "اختبار قيد مصروفات P2",
            "transaction_type": "expense",
            "lines": [
                {
                    "account": "521",
                    "account_name": "مصاريف رواتب",
                    "debit": 5000,
                    "credit": 0
                },
                {
                    "account": "101",
                    "account_name": "النقدية",
                    "debit": 0,
                    "credit": 5000
                }
            ],
            "total": 5000
        }
        
        print(f"📤 البيانات المرسلة:")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        
        response = requests.post(url, json=payload, params=params, timeout=30)
        print(f"📊 كود الاستجابة: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"📄 البيانات المستلمة:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            
            # التحقق من وجود transaction_type في الاستجابة
            if "data" in data and len(data["data"]) > 0:
                entry_data = data["data"][0]
                returned_transaction_type = entry_data.get("transaction_type")
                
                if returned_transaction_type == "expense":
                    print_result(True, f"transaction_type صحيح: {returned_transaction_type}")
                else:
                    print_result(False, f"transaction_type غير صحيح. المتوقع: expense, الفعلي: {returned_transaction_type}")
                    return False
                
                # التحقق من عدم وجود note fallback في الرسالة
                message = data.get("message", "")
                if "note fallback" not in message.lower():
                    print_result(True, "الرسالة لا تحتوي على note fallback")
                else:
                    print_result(False, f"الرسالة تحتوي على note fallback: {message}")
                    return False
                
                return entry_id  # إرجاع ID للاختبار التالي
            else:
                print_result(False, "لا توجد بيانات في الاستجابة")
                return False
                
        else:
            print_result(False, f"فشل الطلب - كود الخطأ: {response.status_code}")
            print(f"📄 رسالة الخطأ: {response.text}")
            return False
            
    except Exception as e:
        print_result(False, f"خطأ في الاختبار: {str(e)}")
        return False

def test_p2_transaction_type_retrieval():
    """
    P2: اختبار استرجاع القيود المحاسبية والتأكد من وجود transaction_type
    GET /api/finance/journal-entries?workshop_id=finmodule-sync
    """
    print_test_header("P2: اختبار استرجاع القيود المحاسبية مع transaction_type")
    
    try:
        url = f"{BACKEND_URL}/finance/journal-entries"
        params = {"workshop_id": WORKSHOP_ID}
        print(f"📡 استدعاء: GET {url}?workshop_id={WORKSHOP_ID}")
        
        response = requests.get(url, params=params, timeout=30)
        print(f"📊 كود الاستجابة: {response.status_code}")
        
        if response.status_code == 200:
            response_data = response.json()
            
            # Handle both formats: direct array or {"success": true, "data": [...]}
            if isinstance(response_data, dict) and "data" in response_data:
                data = response_data["data"]
            else:
                data = response_data
                
            print(f"📄 عدد القيود المستلمة: {len(data) if isinstance(data, list) else 'غير محدد'}")
            
            # البحث عن القيد الذي أنشأناه في الاختبار السابق
            found_test_entry = False
            for entry in data:
                if entry.get("description") == "اختبار قيد مصروفات P2":
                    found_test_entry = True
                    transaction_type = entry.get("transaction_type")
                    
                    if transaction_type:
                        print_result(True, f"القيد المضاف موجود مع transaction_type: {transaction_type}")
                        
                        if transaction_type == "expense":
                            print_result(True, "transaction_type صحيح (expense)")
                            return True
                        else:
                            print_result(False, f"transaction_type غير صحيح. المتوقع: expense, الفعلي: {transaction_type}")
                            return False
                    else:
                        print_result(False, "القيد المضاف موجود لكن transaction_type غير موجود")
                        return False
            
            if not found_test_entry:
                print_result(False, "القيد المضاف في الاختبار السابق غير موجود")
                # عرض أول 3 قيود للمراجعة
                print("📋 أول 3 قيود موجودة:")
                for i, entry in enumerate(data[:3]):
                    print(f"  {i+1}. {entry.get('description', 'بدون وصف')} - transaction_type: {entry.get('transaction_type', 'غير موجود')}")
                return False
            
        else:
            print_result(False, f"فشل الطلب - كود الخطأ: {response.status_code}")
            print(f"📄 رسالة الخطأ: {response.text}")
            return False
            
    except Exception as e:
        print_result(False, f"خطأ في الاختبار: {str(e)}")
        return False

def main():
    """تشغيل جميع اختبارات P1 و P2"""
    print("🚀 بدء اختبارات P1 و P2")
    print(f"🔗 Backend URL: {BACKEND_URL}")
    print(f"🏪 Workshop ID: {WORKSHOP_ID}")
    
    results = []
    
    # اختبار P1: تحليل البوت المالي الآمن
    print("\n" + "="*70)
    print("📋 اختبارات P1: finance-bot safe analysis")
    print("="*70)
    
    p1_result = test_p1_finance_bot_safe_analysis()
    results.append(("P1: تحليل البوت المالي الآمن", p1_result))
    
    # اختبار P2: transaction_type
    print("\n" + "="*70)
    print("📋 اختبارات P2: transaction_type")
    print("="*70)
    
    p2_creation_result = test_p2_transaction_type_creation()
    results.append(("P2: إنشاء قيد مع transaction_type", bool(p2_creation_result)))
    
    if p2_creation_result:
        p2_retrieval_result = test_p2_transaction_type_retrieval()
        results.append(("P2: استرجاع قيد مع transaction_type", p2_retrieval_result))
    else:
        results.append(("P2: استرجاع قيد مع transaction_type", False))
    
    # ملخص النتائج
    print("\n" + "="*70)
    print("📊 ملخص نتائج اختبارات P1 و P2")
    print("="*70)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ نجح" if result else "❌ فشل"
        print(f"{status}: {test_name}")
        if result:
            passed += 1
    
    print(f"\n📈 النتيجة النهائية: {passed}/{total} اختبارات نجحت")
    
    if passed == total:
        print("🎉 جميع اختبارات P1 و P2 نجحت!")
        return True
    else:
        print("⚠️ بعض اختبارات P1 و P2 فشلت - يرجى مراجعة التفاصيل أعلاه")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)