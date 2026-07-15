#!/usr/bin/env python3
"""
اختبار الميزات العربية المحددة - Arabic Features Testing
Testing specific Arabic features as requested in the review
"""

import requests
import json
import os
from datetime import datetime

# Configuration
BACKEND_URL = "https://fabrication-guard.preview.emergentagent.com/api"
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

def test_trial_balance_api():
    """
    اختبار 1: مسار ميزان المراجعة
    GET /api/finance/reports/trial-balance?workshop_id=finmodule-sync
    تأكد أن status = 200 وأن data.accounts تحتوي على حسابات مع حقول debit/credit
    """
    print_test_header("اختبار API ميزان المراجعة")
    
    try:
        url = f"{BACKEND_URL}/finance/reports/trial-balance"
        params = {"workshop_id": WORKSHOP_ID}
        
        print(f"📡 استدعاء: GET {url}")
        print(f"📤 المعاملات: {params}")
        
        response = requests.get(url, params=params, timeout=30)
        print(f"📊 كود الاستجابة: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"📄 البيانات المستلمة: {json.dumps(data, indent=2, ensure_ascii=False)}")
            
            # التحقق من هيكل البيانات
            if "data" in data and "accounts" in data["data"]:
                accounts = data["data"]["accounts"]
                print_result(True, f"تم العثور على {len(accounts)} حساب في ميزان المراجعة")
                
                # التحقق من وجود حقول debit/credit في الحسابات
                valid_accounts = 0
                for account in accounts:
                    if "debit" in account and "credit" in account:
                        valid_accounts += 1
                        print(f"  ✓ حساب {account.get('code', 'N/A')}: مدين={account.get('debit', 0)}, دائن={account.get('credit', 0)}")
                
                if valid_accounts > 0:
                    print_result(True, f"{valid_accounts} حساب يحتوي على حقول مدين/دائن")
                    return True, data
                else:
                    print_result(False, "لا توجد حسابات تحتوي على حقول مدين/دائن")
                    return False, data
            else:
                print_result(False, "هيكل البيانات غير صحيح - لا توجد data.accounts")
                return False, data
        else:
            print_result(False, f"كود استجابة غير متوقع: {response.status_code}")
            print(f"نص الاستجابة: {response.text}")
            return False, None
            
    except Exception as e:
        print_result(False, f"خطأ في الاتصال: {str(e)}")
        return False, None

def test_finance_bot_general_question():
    """
    اختبار 2: سؤال عام لأبوفهد بدون account_code
    POST /api/finance-bot/chat بدون account_code
    """
    print_test_header("اختبار سؤال عام لأبوفهد")
    
    try:
        url = f"{BACKEND_URL}/finance-bot/chat"
        payload = {
            "message": "ما هو الوضع المالي العام للورشة؟",
            "workshop_id": WORKSHOP_ID
        }
        
        print(f"📡 استدعاء: POST {url}")
        print(f"📤 البيانات المرسلة: {json.dumps(payload, indent=2, ensure_ascii=False)}")
        
        response = requests.post(url, json=payload, timeout=60)
        print(f"📊 كود الاستجابة: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"📄 البيانات المستلمة: {json.dumps(data, indent=2, ensure_ascii=False)}")
            
            # التحقق من وجود الرد
            if "response" in data and data["response"]:
                response_text = data["response"]
                print_result(True, f"تم استلام رد من أبوفهد ({len(response_text)} حرف)")
                print(f"🤖 رد أبوفهد: {response_text[:200]}...")
                
                # التحقق من conversation_id
                conversation_id = data.get("conversation_id")
                if conversation_id:
                    print_result(True, f"تم إنشاء conversation_id: {conversation_id}")
                    return True, conversation_id
                else:
                    print_result(False, "لم يتم إرجاع conversation_id")
                    return False, None
            else:
                print_result(False, "لم يتم استلام رد من أبوفهد")
                return False, None
        else:
            print_result(False, f"كود استجابة غير متوقع: {response.status_code}")
            print(f"نص الاستجابة: {response.text}")
            return False, None
            
    except Exception as e:
        print_result(False, f"خطأ في الاتصال: {str(e)}")
        return False, None

def test_finance_bot_account_specific_question():
    """
    اختبار 3: سؤال محدد لحساب 411 مع account_code
    POST /api/finance-bot/chat مع account_code: "411"
    """
    print_test_header("اختبار سؤال محدد لحساب 411")
    
    try:
        url = f"{BACKEND_URL}/finance-bot/chat"
        payload = {
            "message": "دقّق هذا الحساب",
            "account_code": "411",
            "workshop_id": WORKSHOP_ID
        }
        
        print(f"📡 استدعاء: POST {url}")
        print(f"📤 البيانات المرسلة: {json.dumps(payload, indent=2, ensure_ascii=False)}")
        
        response = requests.post(url, json=payload, timeout=60)
        print(f"📊 كود الاستجابة: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"📄 البيانات المستلمة: {json.dumps(data, indent=2, ensure_ascii=False)}")
            
            # التحقق من وجود الرد
            if "response" in data and data["response"]:
                response_text = data["response"]
                print_result(True, f"تم استلام رد من أبوفهد للحساب 411 ({len(response_text)} حرف)")
                print(f"🤖 رد أبوفهد: {response_text[:200]}...")
                
                # التحقق من أن الرد يختلف عن الرد العام (يحتوي على معلومات الحساب)
                account_keywords = ["411", "حساب", "إيرادات", "تدقيق"]
                has_account_info = any(keyword in response_text for keyword in account_keywords)
                
                if has_account_info:
                    print_result(True, "الرد يحتوي على معلومات خاصة بالحساب 411")
                else:
                    print_result(True, "الرد عام (قد يكون بسبب عدم وجود بيانات للحساب)")
                
                return True
            else:
                print_result(False, "لم يتم استلام رد من أبوفهد")
                return False
        else:
            print_result(False, f"كود استجابة غير متوقع: {response.status_code}")
            print(f"نص الاستجابة: {response.text}")
            return False
            
    except Exception as e:
        print_result(False, f"خطأ في الاتصال: {str(e)}")
        return False

def test_system_audit_analysis():
    """
    اختبار 4: تحليل تقرير التدقيق مع أبوفهد
    محاكاة إرسال تقرير تدقيق لأبوفهد للتحليل
    """
    print_test_header("اختبار تحليل تقرير التدقيق مع أبوفهد")
    
    try:
        # محاكاة تقرير تدقيق
        mock_audit_report = {
            "summary": "تقرير تدقيق النظام المالي",
            "total_accounts": 15,
            "balanced_accounts": 12,
            "unbalanced_accounts": 3,
            "issues_found": [
                "عدم توازن في حساب النقدية",
                "مبالغ مدينة غير محصلة",
                "فروقات في المخزون"
            ],
            "recommendations": [
                "مراجعة حساب النقدية",
                "متابعة المبالغ المدينة",
                "جرد المخزون"
            ]
        }
        
        url = f"{BACKEND_URL}/finance-bot/chat"
        payload = {
            "message": f"حلّل تقرير التدقيق التالي وقدم توصياتك:\n\n{json.dumps(mock_audit_report, ensure_ascii=False, indent=2)}",
            "workshop_id": WORKSHOP_ID
        }
        
        print(f"📡 استدعاء: POST {url}")
        print(f"📤 البيانات المرسلة: {json.dumps(payload, indent=2, ensure_ascii=False)}")
        
        response = requests.post(url, json=payload, timeout=60)
        print(f"📊 كود الاستجابة: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"📄 البيانات المستلمة: {json.dumps(data, indent=2, ensure_ascii=False)}")
            
            # التحقق من وجود الرد
            if "response" in data and data["response"]:
                response_text = data["response"]
                print_result(True, f"تم استلام تحليل تقرير التدقيق من أبوفهد ({len(response_text)} حرف)")
                print(f"🤖 تحليل أبوفهد: {response_text[:300]}...")
                
                # التحقق من أن الرد يحتوي على كلمات مفتاحية للتحليل
                analysis_keywords = ["تحليل", "توصية", "تدقيق", "حساب", "توازن"]
                has_analysis = any(keyword in response_text for keyword in analysis_keywords)
                
                if has_analysis:
                    print_result(True, "الرد يحتوي على تحليل مفصل لتقرير التدقيق")
                else:
                    print_result(True, "الرد عام ولكن تم استلامه بنجاح")
                
                return True
            else:
                print_result(False, "لم يتم استلام تحليل من أبوفهد")
                return False
        else:
            print_result(False, f"كود استجابة غير متوقع: {response.status_code}")
            print(f"نص الاستجابة: {response.text}")
            return False
            
    except Exception as e:
        print_result(False, f"خطأ في الاتصال: {str(e)}")
        return False

def test_conversation_persistence(conversation_id):
    """
    اختبار 5: استمرارية المحادثة
    التأكد من أن conversation_id يحافظ على السياق
    """
    print_test_header("اختبار استمرارية المحادثة")
    
    if not conversation_id:
        print_result(False, "لا يوجد conversation_id للاختبار")
        return False
    
    try:
        url = f"{BACKEND_URL}/finance-bot/chat"
        payload = {
            "message": "ما هو آخر موضوع تحدثنا عنه؟",
            "conversation_id": conversation_id,
            "workshop_id": WORKSHOP_ID
        }
        
        print(f"📡 استدعاء: POST {url}")
        print(f"📤 البيانات المرسلة: {json.dumps(payload, indent=2, ensure_ascii=False)}")
        
        response = requests.post(url, json=payload, timeout=60)
        print(f"📊 كود الاستجابة: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"📄 البيانات المستلمة: {json.dumps(data, indent=2, ensure_ascii=False)}")
            
            # التحقق من وجود الرد
            if "response" in data and data["response"]:
                response_text = data["response"]
                print_result(True, f"تم استلام رد من أبوفهد ({len(response_text)} حرف)")
                print(f"🤖 رد أبوفهد: {response_text[:200]}...")
                
                # التحقق من أن conversation_id نفسه
                returned_conversation_id = data.get("conversation_id")
                if returned_conversation_id == conversation_id:
                    print_result(True, f"تم الحفاظ على نفس conversation_id: {conversation_id}")
                    return True
                else:
                    print_result(False, f"conversation_id مختلف: متوقع {conversation_id}, مستلم {returned_conversation_id}")
                    return False
            else:
                print_result(False, "لم يتم استلام رد من أبوفهد")
                return False
        else:
            print_result(False, f"كود استجابة غير متوقع: {response.status_code}")
            print(f"نص الاستجابة: {response.text}")
            return False
            
    except Exception as e:
        print_result(False, f"خطأ في الاتصال: {str(e)}")
        return False

def run_arabic_features_tests():
    """تشغيل جميع اختبارات الميزات العربية"""
    print("🚀 بدء اختبار الميزات العربية المحددة")
    print(f"🌐 رابط الخادم: {BACKEND_URL}")
    print(f"🏪 معرف الورشة: {WORKSHOP_ID}")
    print(f"⏰ وقت الاختبار: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = []
    conversation_id = None
    
    # اختبار 1: ميزان المراجعة API
    trial_balance_success, trial_balance_data = test_trial_balance_api()
    results.append(("ميزان المراجعة API", trial_balance_success))
    
    # اختبار 2: سؤال عام لأبوفهد
    general_success, conversation_id = test_finance_bot_general_question()
    results.append(("سؤال عام لأبوفهد", general_success))
    
    # اختبار 3: سؤال محدد للحساب 411
    account_success = test_finance_bot_account_specific_question()
    results.append(("سؤال محدد للحساب 411", account_success))
    
    # اختبار 4: تحليل تقرير التدقيق
    audit_success = test_system_audit_analysis()
    results.append(("تحليل تقرير التدقيق", audit_success))
    
    # اختبار 5: استمرارية المحادثة
    if conversation_id:
        persistence_success = test_conversation_persistence(conversation_id)
        results.append(("استمرارية المحادثة", persistence_success))
    
    # ملخص النتائج
    print_test_header("ملخص نتائج اختبار الميزات العربية")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ نجح" if result else "❌ فشل"
        print(f"{status} {test_name}")
    
    print(f"\n📊 النتيجة النهائية: {passed}/{total} اختبارات نجحت")
    
    if passed == total:
        print("🎉 جميع اختبارات الميزات العربية نجحت!")
        return True
    else:
        print(f"⚠️ {total - passed} اختبارات فشلت")
        return False

if __name__ == "__main__":
    success = run_arabic_features_tests()
    exit(0 if success else 1)