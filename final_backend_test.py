#!/usr/bin/env python3
"""
اختبار شامل للنظام المالي - Comprehensive Backend Testing
Testing all backend APIs including Abu Fahad finance bot and P0 credit payment logic
"""

import requests
import json
import os
import uuid
from datetime import datetime, timedelta

# Configuration
BACKEND_URL = "https://pdpl-memory-engine.preview.emergentagent.com/api"
WORKSHOP_ID = "finmodule-sync"

def print_test_header(test_name):
    """Print formatted test header"""
    print(f"\n{'='*60}")
    print(f"🧪 {test_name}")
    print(f"{'='*60}")

def print_result(success, message, details=None):
    """Print test result with formatting"""
    status = "✅ نجح" if success else "❌ فشل"
    print(f"{status}: {message}")
    if details:
        print(f"التفاصيل: {details}")

def test_abu_fahad_finance_bot():
    """
    اختبار بوت أبوفهد المالي
    """
    print_test_header("اختبار بوت أبوفهد المالي")
    
    try:
        # Test 1: General financial question
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
            response_text = data.get("response", "")
            conversation_id = data.get("conversation_id", "")
            
            if response_text and conversation_id:
                print_result(True, f"أبوفهد يعمل بنجاح - طول الرد: {len(response_text)} حرف")
                print(f"معرف المحادثة: {conversation_id}")
                
                # Test 2: Account-specific analysis
                payload2 = {
                    "message": "حلل حساب النقدية",
                    "workshop_id": WORKSHOP_ID,
                    "account_code": "101"
                }
                
                response2 = requests.post(url, json=payload2, timeout=60)
                if response2.status_code == 200:
                    data2 = response2.json()
                    response_text2 = data2.get("response", "")
                    if response_text2:
                        print_result(True, f"تحليل الحساب المحدد يعمل - طول الرد: {len(response_text2)} حرف")
                        return True
                    else:
                        print_result(False, "تحليل الحساب المحدد فشل - رد فارغ")
                        return False
                else:
                    print_result(False, f"تحليل الحساب المحدد فشل: {response2.status_code}")
                    return False
            else:
                print_result(False, "أبوفهد فشل - رد أو معرف محادثة مفقود")
                return False
        else:
            print_result(False, f"أبوفهد فشل: {response.status_code}")
            print(f"نص الاستجابة: {response.text}")
            return False
            
    except Exception as e:
        print_result(False, f"خطأ في اختبار أبوفهد: {str(e)}")
        return False

def test_p0_credit_payment_logic():
    """
    اختبار منطق P0 للدفع الآجل
    """
    print_test_header("اختبار منطق P0 للدفع الآجل")
    
    try:
        # Step 1: Create credit operation
        operation_data = {
            "type": "sale",
            "workshop_id": WORKSHOP_ID,
            "partner_name": "عميل اختبار P0",
            "items": [
                {
                    "name": "خدمة صيانة اختبار P0",
                    "quantity": 1,
                    "price": 100.0
                }
            ],
            "paymentMethod": "credit",  # Important: credit payment
            "op_date": "2024-06-01",
            "notes": "اختبار منطق P0 للدفع الآجل"
        }
        
        url = f"{BACKEND_URL}/operations"
        print(f"📡 إنشاء عملية آجلة: POST {url}")
        
        response = requests.post(url, json=operation_data, timeout=30)
        print(f"📊 كود الاستجابة: {response.status_code}")
        
        if response.status_code in [200, 201]:
            data = response.json()
            operation_id = data.get("id")
            print_result(True, f"تم إنشاء العملية الآجلة: {operation_id}")
            
            # Step 2: Check no immediate journal entry (P0 rule)
            journal_url = f"{BACKEND_URL}/finance/journal-entries"
            journal_params = {"workshop_id": WORKSHOP_ID}
            journal_response = requests.get(journal_url, params=journal_params, timeout=30)
            
            if journal_response.status_code == 200:
                journal_data = journal_response.json()
                entries = journal_data.get("data", [])
                
                # Look for immediate entry with our operation ID
                immediate_entries = [e for e in entries if e.get("reference_id") == operation_id]
                
                if not immediate_entries:
                    print_result(True, "P0 صحيح: لا يوجد قيد فوري للعملية الآجلة")
                    
                    # Step 3: Test payment confirmation
                    payment_url = f"{BACKEND_URL}/operations/{operation_id}/confirm-payment"
                    payment_data = {
                        "amount": 40.0,
                        "payment_date": "2024-06-15",
                        "workshopId": WORKSHOP_ID
                    }
                    
                    payment_response = requests.post(payment_url, json=payment_data, timeout=30)
                    if payment_response.status_code == 200:
                        payment_result = payment_response.json()
                        
                        # Handle different response formats
                        if "data" in payment_result:
                            payment_data_resp = payment_result["data"]
                            paid = payment_data_resp.get("paid", 0)
                            remaining = payment_data_resp.get("remaining", 0)
                        else:
                            paid = payment_result.get("paid", 0)
                            remaining = payment_result.get("remaining", 0)
                        
                        if paid == 40.0 and remaining >= 0:
                            print_result(True, f"تأكيد الدفعة الأولى نجح: دُفع {paid}, متبقي {remaining}")
                            
                            # Check journal entry created for payment
                            journal_response2 = requests.get(journal_url, params=journal_params, timeout=30)
                            if journal_response2.status_code == 200:
                                journal_data2 = journal_response2.json()
                                entries2 = journal_data2.get("data", [])
                                
                                payment_entries = [e for e in entries2 if e.get("reference_id") == operation_id and e.get("source") == "operation_payment"]
                                
                                if payment_entries:
                                    print_result(True, f"تم إنشاء قيد الدفعة: {len(payment_entries)} قيد")
                                    return True
                                else:
                                    print_result(False, "لم يتم إنشاء قيد للدفعة")
                                    return False
                            else:
                                print_result(False, f"فشل في جلب القيود بعد الدفعة: {journal_response2.status_code}")
                                return False
                        else:
                            print_result(False, f"مبالغ الدفعة غير صحيحة: دُفع {paid}, متبقي {remaining} (متوقع: دُفع 40.0)")
                            return False
                    else:
                        print_result(False, f"فشل في تأكيد الدفعة: {payment_response.status_code}")
                        return False
                else:
                    print_result(False, f"P0 خطأ: وُجد قيد فوري للعملية الآجلة ({len(immediate_entries)} قيد)")
                    return False
            else:
                print_result(False, f"فشل في جلب القيود: {journal_response.status_code}")
                return False
        else:
            print_result(False, f"فشل في إنشاء العملية الآجلة: {response.status_code}")
            print(f"نص الاستجابة: {response.text}")
            return False
            
    except Exception as e:
        print_result(False, f"خطأ في اختبار P0: {str(e)}")
        return False

def test_chart_of_accounts():
    """
    اختبار دليل الحسابات
    """
    print_test_header("اختبار دليل الحسابات")
    
    try:
        url = f"{BACKEND_URL}/finance/chart-of-accounts"
        params = {"workshop_id": WORKSHOP_ID}
        
        print(f"📡 استدعاء: GET {url}")
        
        response = requests.get(url, params=params, timeout=30)
        print(f"📊 كود الاستجابة: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get("success"):
                accounts = data.get("data", [])
                print_result(True, f"دليل الحسابات يعمل: {len(accounts)} حساب")
                
                # Check for essential accounts
                account_codes = [acc.get("code") for acc in accounts]
                essential_codes = ["101", "113", "211", "411"]
                
                missing_codes = [code for code in essential_codes if code not in account_codes]
                
                if not missing_codes:
                    print_result(True, "جميع الحسابات الأساسية موجودة")
                    return True
                else:
                    print_result(False, f"حسابات أساسية مفقودة: {missing_codes}")
                    return False
            else:
                print_result(False, f"دليل الحسابات فشل: {data.get('message', 'خطأ غير محدد')}")
                return False
        else:
            print_result(False, f"دليل الحسابات فشل: كود {response.status_code}")
            return False
            
    except Exception as e:
        print_result(False, f"خطأ في اختبار دليل الحسابات: {str(e)}")
        return False

def test_audit_system():
    """
    اختبار نظام التدقيق المالي
    """
    print_test_header("اختبار نظام التدقيق المالي")
    
    try:
        url = f"{BACKEND_URL}/finance/audit-system"
        params = {"workshop_id": WORKSHOP_ID}
        
        print(f"📡 استدعاء: POST {url}")
        
        response = requests.post(url, params=params, timeout=30)
        print(f"📊 كود الاستجابة: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get("success"):
                audit_data = data.get("data", {})
                health_score = audit_data.get("health_score", 0)
                total_issues = audit_data.get("total_issues", 0)
                
                print_result(True, f"نظام التدقيق يعمل - نقاط الصحة: {health_score}/100")
                print(f"عدد المشاكل: {total_issues}")
                
                # Check audit categories
                categories = ["balance_sheet_check", "trial_balance_check", "cash_flow_check"]
                for category in categories:
                    if category in audit_data:
                        cat_data = audit_data[category]
                        status = cat_data.get("status", "unknown")
                        print(f"  {category}: {status}")
                
                return True
            else:
                print_result(False, f"نظام التدقيق فشل: {data.get('message', 'خطأ غير محدد')}")
                return False
        else:
            print_result(False, f"نظام التدقيق فشل: كود {response.status_code}")
            return False
            
    except Exception as e:
        print_result(False, f"خطأ في اختبار نظام التدقيق: {str(e)}")
        return False

def test_journal_entries_transaction_type():
    """
    اختبار حقل transaction_type في القيود اليومية
    """
    print_test_header("اختبار حقل transaction_type في القيود اليومية")
    
    try:
        # Create journal entry with transaction_type
        entry_data = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "description": "اختبار transaction_type",
            "transaction_type": "expense",
            "lines": [
                {
                    "account": "521",
                    "account_name": "مصاريف رواتب",
                    "debit": 1000,
                    "credit": 0
                },
                {
                    "account": "101",
                    "account_name": "النقدية",
                    "debit": 0,
                    "credit": 1000
                }
            ],
            "total": 1000
        }
        
        url = f"{BACKEND_URL}/finance/journal-entries"
        params = {"workshop_id": WORKSHOP_ID}
        print(f"📡 إنشاء قيد مع transaction_type: POST {url}")
        
        response = requests.post(url, json=entry_data, params=params, timeout=30)
        print(f"📊 كود الاستجابة: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get("success"):
                created_entries = data.get("data", [])
                if created_entries and len(created_entries) > 0:
                    entry = created_entries[0]
                    transaction_type = entry.get("transaction_type")
                    
                    if transaction_type == "expense":
                        print_result(True, f"تم إنشاء قيد مع transaction_type: {transaction_type}")
                        
                        # Verify by retrieving entries
                        get_response = requests.get(url, params={"workshop_id": WORKSHOP_ID}, timeout=30)
                        if get_response.status_code == 200:
                            get_data = get_response.json()
                            entries = get_data.get("data", [])
                            
                            # Find our entry
                            our_entry = None
                            for e in entries:
                                if e.get("description") == "اختبار transaction_type":
                                    our_entry = e
                                    break
                            
                            if our_entry and our_entry.get("transaction_type") == "expense":
                                print_result(True, "تم التحقق من حفظ transaction_type بنجاح")
                                return True
                            else:
                                print_result(False, "transaction_type لم يُحفظ بشكل صحيح")
                                return False
                        else:
                            print_result(False, f"فشل في جلب القيود للتحقق: {get_response.status_code}")
                            return False
                    else:
                        print_result(False, f"transaction_type غير صحيح: {transaction_type}")
                        return False
                else:
                    print_result(False, "لم يتم إرجاع بيانات القيد المُنشأ")
                    return False
            else:
                print_result(False, f"فشل في إنشاء القيد: {data.get('message', 'خطأ غير محدد')}")
                return False
        else:
            print_result(False, f"فشل في إنشاء القيد: {response.status_code}")
            print(f"نص الاستجابة: {response.text}")
            return False
            
    except Exception as e:
        print_result(False, f"خطأ في اختبار transaction_type: {str(e)}")
        return False

def run_comprehensive_tests():
    """تشغيل جميع الاختبارات الشاملة"""
    print("🚀 بدء الاختبار الشامل للنظام المالي")
    print(f"🌐 رابط الخادم: {BACKEND_URL}")
    print(f"🏪 معرف الورشة: {WORKSHOP_ID}")
    print(f"⏰ وقت الاختبار: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = []
    
    # اختبار 1: بوت أبوفهد المالي
    results.append(("بوت أبوفهد المالي", test_abu_fahad_finance_bot()))
    
    # اختبار 2: منطق P0 للدفع الآجل
    results.append(("منطق P0 للدفع الآجل", test_p0_credit_payment_logic()))
    
    # اختبار 3: دليل الحسابات
    results.append(("دليل الحسابات", test_chart_of_accounts()))
    
    # اختبار 4: نظام التدقيق المالي
    results.append(("نظام التدقيق المالي", test_audit_system()))
    
    # اختبار 5: حقل transaction_type
    results.append(("حقل transaction_type", test_journal_entries_transaction_type()))
    
    # ملخص النتائج
    print_test_header("ملخص نتائج الاختبار الشامل")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ نجح" if result else "❌ فشل"
        print(f"{status} {test_name}")
    
    print(f"\n📊 النتيجة النهائية: {passed}/{total} اختبارات نجحت")
    
    if passed == total:
        print("🎉 جميع الاختبارات الشاملة نجحت!")
        return True
    else:
        print(f"⚠️ {total - passed} اختبارات فشلت")
        return False

if __name__ == "__main__":
    success = run_comprehensive_tests()
    exit(0 if success else 1)