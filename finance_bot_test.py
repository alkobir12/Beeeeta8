#!/usr/bin/env python3
"""
اختبار مشكلة أبوفهد - Finance Bot Testing
Testing Abu Fahad's issue when sending messages to the finance bot
"""

import requests
import json
import os
from datetime import datetime

# Configuration from frontend/.env
BACKEND_URL = "https://contract-audit-demo.preview.emergentagent.com/api"
WORKSHOP_ID = "finmodule-sync"
CONVERSATION_ID = "e2e-session-1"

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

def test_finance_bot_health():
    """
    اختبار 1: فحص صحة Finance Bot
    Test 1: Finance Bot Health Check
    """
    print_test_header("اختبار صحة Finance Bot")
    
    try:
        url = f"{BACKEND_URL}/finance-bot/health"
        
        print(f"📡 استدعاء: GET {url}")
        
        response = requests.get(url, timeout=30)
        print(f"📊 كود الاستجابة: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"📄 الاستجابة: {json.dumps(data, indent=2, ensure_ascii=False)}")
            
            # Check required fields
            status = data.get("status")
            has_key = data.get("has_key")
            
            if status == "ok" and has_key is True:
                print_result(True, f"Finance Bot صحي: status={status}, has_key={has_key}")
                return True
            else:
                print_result(False, f"Finance Bot غير صحي: status={status}, has_key={has_key}")
                return False
        else:
            print_result(False, f"فشل في فحص الصحة: كود {response.status_code}")
            print(f"نص الاستجابة: {response.text}")
            return False
            
    except Exception as e:
        print_result(False, f"خطأ في فحص الصحة: {str(e)}")
        return False

def test_finance_bot_chat_arabic():
    """
    اختبار 2: إرسال رسالة عربية قصيرة
    Test 2: Send short Arabic message
    """
    print_test_header("اختبار إرسال رسالة عربية قصيرة")
    
    try:
        url = f"{BACKEND_URL}/finance-bot/chat"
        
        payload = {
            "message": "ما هو الوضع المالي للورشة؟",
            "workshop_id": WORKSHOP_ID,
            "conversation_id": CONVERSATION_ID
        }
        
        print(f"📡 استدعاء: POST {url}")
        print(f"📤 البيانات المرسلة: {json.dumps(payload, indent=2, ensure_ascii=False)}")
        
        response = requests.post(url, json=payload, timeout=60)
        print(f"📊 كود الاستجابة: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"📄 الاستجابة: {json.dumps(data, indent=2, ensure_ascii=False)}")
            
            # Check required fields
            response_text = data.get("response", "")
            provider = data.get("provider", "")
            
            if response_text and len(response_text.strip()) > 0:
                if provider == "openai-gpt-5.1":
                    print_result(True, f"رد صحيح: النص غير فارغ، المزود={provider}")
                    print(f"📝 نص الرد: {response_text[:200]}...")
                    return True
                else:
                    print_result(False, f"مزود خاطئ: متوقع openai-gpt-5.1، وجد {provider}")
                    return False
            else:
                print_result(False, "الرد فارغ أو غير موجود")
                return False
        else:
            print_result(False, f"فشل في إرسال الرسالة: كود {response.status_code}")
            print(f"نص الاستجابة: {response.text}")
            return False
            
    except Exception as e:
        print_result(False, f"خطأ في إرسال الرسالة: {str(e)}")
        return False

def test_finance_bot_follow_up():
    """
    اختبار 3: إرسال رسالة متابعة بنفس conversation_id
    Test 3: Send follow-up message with same conversation_id
    """
    print_test_header("اختبار رسالة المتابعة")
    
    try:
        url = f"{BACKEND_URL}/finance-bot/chat"
        
        payload = {
            "message": "هل يمكنك إعطائي تفاصيل أكثر عن الإيرادات؟",
            "workshop_id": WORKSHOP_ID,
            "conversation_id": CONVERSATION_ID  # Same conversation ID
        }
        
        print(f"📡 استدعاء: POST {url}")
        print(f"📤 البيانات المرسلة: {json.dumps(payload, indent=2, ensure_ascii=False)}")
        
        response = requests.post(url, json=payload, timeout=60)
        print(f"📊 كود الاستجابة: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"📄 الاستجابة: {json.dumps(data, indent=2, ensure_ascii=False)}")
            
            # Check that server didn't crash and endpoint works repeatedly
            response_text = data.get("response", "")
            
            if response_text and len(response_text.strip()) > 0:
                print_result(True, "السيرفر لم ينهار والـ endpoint يعمل بشكل متكرر")
                print(f"📝 نص الرد: {response_text[:200]}...")
                return True
            else:
                print_result(False, "الرد فارغ في رسالة المتابعة")
                return False
        else:
            print_result(False, f"فشل في رسالة المتابعة: كود {response.status_code}")
            print(f"نص الاستجابة: {response.text}")
            return False
            
    except Exception as e:
        print_result(False, f"خطأ في رسالة المتابعة: {str(e)}")
        return False

def test_finance_bot_with_account_code():
    """
    اختبار 4: إرسال رسالة مع account_code=411
    Test 4: Send message with account_code=411
    """
    print_test_header("اختبار رسالة مع رمز الحساب 411")
    
    try:
        url = f"{BACKEND_URL}/finance-bot/chat"
        
        payload = {
            "message": "أريد تحليل حساب الإيرادات",
            "workshop_id": WORKSHOP_ID,
            "conversation_id": f"{CONVERSATION_ID}-account",
            "account_code": "411"
        }
        
        print(f"📡 استدعاء: POST {url}")
        print(f"📤 البيانات المرسلة: {json.dumps(payload, indent=2, ensure_ascii=False)}")
        
        response = requests.post(url, json=payload, timeout=60)
        print(f"📊 كود الاستجابة: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"📄 الاستجابة: {json.dumps(data, indent=2, ensure_ascii=False)}")
            
            # Check that response contains response field
            response_text = data.get("response", "")
            
            if response_text and len(response_text.strip()) > 0:
                print_result(True, f"رد صحيح مع account_code=411")
                print(f"📝 نص الرد: {response_text[:200]}...")
                return True
            else:
                print_result(False, "الرد فارغ مع account_code=411")
                return False
        else:
            print_result(False, f"فشل مع account_code=411: كود {response.status_code}")
            print(f"نص الاستجابة: {response.text}")
            return False
            
    except Exception as e:
        print_result(False, f"خطأ مع account_code=411: {str(e)}")
        return False

def run_finance_bot_tests():
    """تشغيل جميع اختبارات Finance Bot"""
    print("🚀 بدء اختبار مشكلة أبوفهد - Finance Bot")
    print(f"🌐 رابط الخادم: {BACKEND_URL}")
    print(f"🏪 معرف الورشة: {WORKSHOP_ID}")
    print(f"💬 معرف المحادثة: {CONVERSATION_ID}")
    print(f"⏰ وقت الاختبار: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = []
    
    # اختبار 1: فحص صحة Finance Bot
    results.append(("فحص صحة Finance Bot", test_finance_bot_health()))
    
    # اختبار 2: إرسال رسالة عربية قصيرة
    results.append(("إرسال رسالة عربية قصيرة", test_finance_bot_chat_arabic()))
    
    # اختبار 3: رسالة متابعة بنفس conversation_id
    results.append(("رسالة متابعة بنفس conversation_id", test_finance_bot_follow_up()))
    
    # اختبار 4: رسالة مع account_code=411
    results.append(("رسالة مع account_code=411", test_finance_bot_with_account_code()))
    
    # ملخص النتائج
    print_test_header("ملخص نتائج اختبار Finance Bot")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ نجح" if result else "❌ فشل"
        print(f"{status} {test_name}")
    
    print(f"\n📊 النتيجة النهائية: {passed}/{total} اختبارات نجحت")
    
    if passed == total:
        print("🎉 جميع اختبارات Finance Bot نجحت!")
        return True
    else:
        print(f"⚠️ {total - passed} اختبارات فشلت")
        return False

if __name__ == "__main__":
    success = run_finance_bot_tests()
    exit(0 if success else 1)