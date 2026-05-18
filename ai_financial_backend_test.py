#!/usr/bin/env python3
"""
اختبار تكامل الباك-إند للصفحة الجديدة /ai-financial
Testing backend integration for the new /ai-financial page

المطلوب (استخدم REACT_APP_BACKEND_URL):
1) GET /api/finance/reports/trial-balance?workshop_id=finmodule-sync وتأكد يرجع success=true و data.accounts array.
2) GET /api/finance/reports/income-statement مع workshop_id + start_date + end_date وتأكد يرجع totals.
3) GET /api/finance/reports/balance-sheet?workshop_id=finmodule-sync وتأكد يرجع totals.assets/liabilities/equity.
4) GET /api/finance/chart-of-accounts?workshop_id=finmodule-sync وتأكد يرجع success=true و data list.
5) POST /api/finance-bot/chat برسالة قصيرة وتأكد يرجع response + conversation_id.
6) POST /api/finance/audit-system?workshop_id=finmodule-sync وتأكد يرجع success.

اذكر أي فشل، latency عالية، أو اختلاف في بنية الاستجابة.
"""

import requests
import json
import os
import time
from datetime import datetime, timedelta

# Configuration from frontend/.env
BACKEND_URL = "https://vehicle-accounting-2.preview.emergentagent.com/api"
WORKSHOP_ID = "finmodule-sync"

def print_test_header(test_name):
    """Print formatted test header"""
    print(f"\n{'='*70}")
    print(f"🧪 {test_name}")
    print(f"{'='*70}")

def print_result(success, message, details=None, latency=None):
    """Print test result with formatting"""
    status = "✅ نجح" if success else "❌ فشل"
    latency_info = f" ({latency:.2f}s)" if latency else ""
    print(f"{status}: {message}{latency_info}")
    if details:
        print(f"التفاصيل: {details}")

def measure_latency(func):
    """Decorator to measure API call latency"""
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        latency = end_time - start_time
        return result, latency
    return wrapper

@measure_latency
def test_trial_balance():
    """
    اختبار 1: GET /api/finance/reports/trial-balance?workshop_id=finmodule-sync
    تأكد يرجع success=true و data.accounts array
    """
    print_test_header("اختبار ميزان المراجعة - Trial Balance")
    
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
            
            # التحقق من البنية المطلوبة
            success = data.get("success")
            accounts = data.get("data", {}).get("accounts", [])
            
            if success is True:
                print_result(True, f"✓ success = {success}")
            else:
                print_result(False, f"✗ success = {success} (متوقع: true)")
                return False
            
            if isinstance(accounts, list) and len(accounts) > 0:
                print_result(True, f"✓ data.accounts array موجود ({len(accounts)} حساب)")
                
                # فحص بنية الحسابات
                sample_account = accounts[0]
                required_fields = ["code", "name", "debit", "credit"]
                missing_fields = [field for field in required_fields if field not in sample_account]
                
                if not missing_fields:
                    print_result(True, f"✓ بنية الحساب صحيحة: {list(sample_account.keys())}")
                    
                    # عرض عينة من البيانات
                    for i, account in enumerate(accounts[:3]):
                        print(f"   حساب {i+1}: {account.get('code')} - {account.get('name')} (مدين: {account.get('debit')}, دائن: {account.get('credit')})")
                    
                    return True
                else:
                    print_result(False, f"✗ حقول مفقودة في بنية الحساب: {missing_fields}")
                    return False
            else:
                print_result(False, f"✗ data.accounts غير موجود أو فارغ (النوع: {type(accounts)}, العدد: {len(accounts) if isinstance(accounts, list) else 'N/A'})")
                return False
        else:
            print_result(False, f"كود استجابة غير متوقع: {response.status_code}")
            print(f"نص الاستجابة: {response.text}")
            return False
            
    except Exception as e:
        print_result(False, f"خطأ في الاتصال: {str(e)}")
        return False

@measure_latency
def test_income_statement():
    """
    اختبار 2: GET /api/finance/reports/income-statement مع workshop_id + start_date + end_date
    تأكد يرجع totals
    """
    print_test_header("اختبار قائمة الدخل - Income Statement")
    
    try:
        url = f"{BACKEND_URL}/finance/reports/income-statement"
        
        # استخدام تواريخ حديثة
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        
        params = {
            "workshop_id": WORKSHOP_ID,
            "start_date": start_date,
            "end_date": end_date
        }
        
        print(f"📡 استدعاء: GET {url}")
        print(f"📤 المعاملات: {params}")
        
        response = requests.get(url, params=params, timeout=30)
        print(f"📊 كود الاستجابة: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"📄 البيانات المستلمة: {json.dumps(data, indent=2, ensure_ascii=False)}")
            
            # التحقق من وجود totals
            totals = data.get("data", {}).get("totals", {})
            
            if totals:
                required_totals = ["revenue", "expenses", "net_income"]
                missing_totals = [field for field in required_totals if field not in totals]
                
                if not missing_totals:
                    print_result(True, f"✓ totals موجود مع جميع الحقول المطلوبة")
                    print(f"   الإيرادات: {totals.get('revenue', 0)}")
                    print(f"   المصروفات: {totals.get('expenses', 0)}")
                    print(f"   صافي الدخل: {totals.get('net_income', 0)}")
                    return True
                else:
                    print_result(False, f"✗ حقول مفقودة في totals: {missing_totals}")
                    return False
            else:
                print_result(False, f"✗ totals غير موجود في data")
                return False
        else:
            print_result(False, f"كود استجابة غير متوقع: {response.status_code}")
            print(f"نص الاستجابة: {response.text}")
            return False
            
    except Exception as e:
        print_result(False, f"خطأ في الاتصال: {str(e)}")
        return False

@measure_latency
def test_balance_sheet():
    """
    اختبار 3: GET /api/finance/reports/balance-sheet?workshop_id=finmodule-sync
    تأكد يرجع totals.assets/liabilities/equity
    """
    print_test_header("اختبار الميزانية العمومية - Balance Sheet")
    
    try:
        url = f"{BACKEND_URL}/finance/reports/balance-sheet"
        params = {"workshop_id": WORKSHOP_ID}
        
        print(f"📡 استدعاء: GET {url}")
        print(f"📤 المعاملات: {params}")
        
        response = requests.get(url, params=params, timeout=30)
        print(f"📊 كود الاستجابة: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"📄 البيانات المستلمة: {json.dumps(data, indent=2, ensure_ascii=False)}")
            
            # التحقق من وجود totals مع الحقول المطلوبة
            totals = data.get("data", {}).get("totals", {})
            
            if totals:
                required_fields = ["assets", "liabilities", "equity"]
                missing_fields = [field for field in required_fields if field not in totals]
                
                if not missing_fields:
                    print_result(True, f"✓ totals.assets/liabilities/equity موجودة")
                    print(f"   الأصول: {totals.get('assets', 0)}")
                    print(f"   الالتزامات: {totals.get('liabilities', 0)}")
                    print(f"   حقوق الملكية: {totals.get('equity', 0)}")
                    
                    # التحقق من توازن الميزانية
                    assets = float(totals.get('assets', 0))
                    liabilities = float(totals.get('liabilities', 0))
                    equity = float(totals.get('equity', 0))
                    
                    if abs(assets - (liabilities + equity)) < 0.01:
                        print_result(True, f"✓ الميزانية متوازنة (الأصول = الالتزامات + حقوق الملكية)")
                    else:
                        print_result(True, f"⚠️ الميزانية غير متوازنة (فرق: {assets - (liabilities + equity):.2f})")
                    
                    return True
                else:
                    print_result(False, f"✗ حقول مفقودة في totals: {missing_fields}")
                    return False
            else:
                print_result(False, f"✗ totals غير موجود في data")
                return False
        else:
            print_result(False, f"كود استجابة غير متوقع: {response.status_code}")
            print(f"نص الاستجابة: {response.text}")
            return False
            
    except Exception as e:
        print_result(False, f"خطأ في الاتصال: {str(e)}")
        return False

@measure_latency
def test_chart_of_accounts():
    """
    اختبار 4: GET /api/finance/chart-of-accounts?workshop_id=finmodule-sync
    تأكد يرجع success=true و data list
    """
    print_test_header("اختبار دليل الحسابات - Chart of Accounts")
    
    try:
        url = f"{BACKEND_URL}/finance/chart-of-accounts"
        params = {"workshop_id": WORKSHOP_ID}
        
        print(f"📡 استدعاء: GET {url}")
        print(f"📤 المعاملات: {params}")
        
        response = requests.get(url, params=params, timeout=30)
        print(f"📊 كود الاستجابة: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"📄 البيانات المستلمة: {json.dumps(data, indent=2, ensure_ascii=False)}")
            
            # التحقق من البنية المطلوبة
            success = data.get("success")
            accounts_data = data.get("data")
            
            if success is True:
                print_result(True, f"✓ success = {success}")
            else:
                print_result(False, f"✗ success = {success} (متوقع: true)")
                return False
            
            if isinstance(accounts_data, list) and len(accounts_data) > 0:
                print_result(True, f"✓ data list موجود ({len(accounts_data)} حساب)")
                
                # فحص بنية الحسابات
                sample_account = accounts_data[0]
                expected_fields = ["code", "name"]
                
                has_required_fields = all(field in sample_account for field in expected_fields)
                
                if has_required_fields:
                    print_result(True, f"✓ بنية الحساب صحيحة: {list(sample_account.keys())}")
                    
                    # عرض عينة من البيانات
                    for i, account in enumerate(accounts_data[:5]):
                        print(f"   حساب {i+1}: {account.get('code')} - {account.get('name', account.get('name_ar', 'بدون اسم'))}")
                    
                    return True
                else:
                    print_result(False, f"✗ حقول مفقودة في بنية الحساب: {expected_fields}")
                    return False
            else:
                print_result(False, f"✗ data غير موجود أو فارغ أو ليس list (النوع: {type(accounts_data)}, العدد: {len(accounts_data) if isinstance(accounts_data, list) else 'N/A'})")
                return False
        else:
            print_result(False, f"كود استجابة غير متوقع: {response.status_code}")
            print(f"نص الاستجابة: {response.text}")
            return False
            
    except Exception as e:
        print_result(False, f"خطأ في الاتصال: {str(e)}")
        return False

@measure_latency
def test_finance_bot_chat():
    """
    اختبار 5: POST /api/finance-bot/chat برسالة قصيرة
    تأكد يرجع response + conversation_id
    """
    print_test_header("اختبار بوت أبوفهد المالي - Finance Bot Chat")
    
    try:
        url = f"{BACKEND_URL}/finance-bot/chat"
        payload = {
            "message": "ما هو الوضع المالي العام؟",
            "workshop_id": WORKSHOP_ID
        }
        
        print(f"📡 استدعاء: POST {url}")
        print(f"📤 البيانات المرسلة: {json.dumps(payload, indent=2, ensure_ascii=False)}")
        
        response = requests.post(url, json=payload, timeout=60)
        print(f"📊 كود الاستجابة: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"📄 البيانات المستلمة: {json.dumps(data, indent=2, ensure_ascii=False)}")
            
            # التحقق من وجود الحقول المطلوبة
            response_text = data.get("response")
            conversation_id = data.get("conversation_id")
            
            if response_text and isinstance(response_text, str) and len(response_text) > 10:
                print_result(True, f"✓ response موجود ({len(response_text)} حرف)")
                print(f"   عينة من الرد: {response_text[:150]}...")
            else:
                print_result(False, f"✗ response غير موجود أو فارغ أو قصير (النوع: {type(response_text)}, الطول: {len(response_text) if response_text else 0})")
                return False
            
            if conversation_id and isinstance(conversation_id, str):
                print_result(True, f"✓ conversation_id موجود: {conversation_id}")
            else:
                print_result(False, f"✗ conversation_id غير موجود أو غير صحيح (النوع: {type(conversation_id)}, القيمة: {conversation_id})")
                return False
            
            return True
        else:
            print_result(False, f"كود استجابة غير متوقع: {response.status_code}")
            print(f"نص الاستجابة: {response.text}")
            return False
            
    except Exception as e:
        print_result(False, f"خطأ في الاتصال: {str(e)}")
        return False

@measure_latency
def test_audit_system():
    """
    اختبار 6: POST /api/finance/audit-system?workshop_id=finmodule-sync
    تأكد يرجع success
    """
    print_test_header("اختبار نظام التدقيق المالي - Audit System")
    
    try:
        url = f"{BACKEND_URL}/finance/audit-system"
        params = {"workshop_id": WORKSHOP_ID}
        
        print(f"📡 استدعاء: POST {url}")
        print(f"📤 المعاملات: {params}")
        
        response = requests.post(url, params=params, timeout=45)
        print(f"📊 كود الاستجابة: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"📄 البيانات المستلمة: {json.dumps(data, indent=2, ensure_ascii=False)}")
            
            # التحقق من وجود success
            success = data.get("success")
            
            if success is True:
                print_result(True, f"✓ success = {success}")
                
                # فحص البيانات الإضافية إن وجدت
                if "health_score" in data:
                    print(f"   نقاط الصحة المالية: {data.get('health_score')}")
                
                if "findings" in data:
                    findings = data.get("findings", [])
                    print(f"   عدد النتائج: {len(findings)}")
                
                return True
            else:
                print_result(False, f"✗ success = {success} (متوقع: true)")
                return False
        else:
            print_result(False, f"كود استجابة غير متوقع: {response.status_code}")
            print(f"نص الاستجابة: {response.text}")
            return False
            
    except Exception as e:
        print_result(False, f"خطأ في الاتصال: {str(e)}")
        return False

def run_ai_financial_backend_tests():
    """تشغيل جميع اختبارات تكامل الباك إند للصفحة المالية الذكية"""
    print("🚀 بدء اختبار تكامل الباك-إند للصفحة الجديدة /ai-financial")
    print(f"🌐 رابط الخادم: {BACKEND_URL}")
    print(f"🏪 معرف الورشة: {WORKSHOP_ID}")
    print(f"⏰ وقت الاختبار: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = []
    latencies = []
    
    # تشغيل جميع الاختبارات
    tests = [
        ("ميزان المراجعة", test_trial_balance),
        ("قائمة الدخل", test_income_statement),
        ("الميزانية العمومية", test_balance_sheet),
        ("دليل الحسابات", test_chart_of_accounts),
        ("بوت أبوفهد المالي", test_finance_bot_chat),
        ("نظام التدقيق المالي", test_audit_system)
    ]
    
    for test_name, test_func in tests:
        try:
            result, latency = test_func()
            results.append((test_name, result))
            latencies.append((test_name, latency))
            
            # تحذير من البطء العالي
            if latency > 10:
                print_result(False, f"⚠️ latency عالية للاختبار '{test_name}': {latency:.2f}s")
            elif latency > 5:
                print_result(True, f"⚠️ latency متوسطة للاختبار '{test_name}': {latency:.2f}s")
                
        except Exception as e:
            print_result(False, f"خطأ في تشغيل اختبار '{test_name}': {str(e)}")
            results.append((test_name, False))
            latencies.append((test_name, 0))
    
    # ملخص النتائج
    print_test_header("ملخص نتائج اختبار تكامل الباك إند")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ نجح" if result else "❌ فشل"
        # العثور على latency المقابل
        test_latency = next((lat for name, lat in latencies if name == test_name), 0)
        latency_info = f" ({test_latency:.2f}s)" if test_latency > 0 else ""
        print(f"{status} {test_name}{latency_info}")
    
    # تحليل الأداء
    print(f"\n📊 النتيجة النهائية: {passed}/{total} اختبارات نجحت")
    
    if latencies:
        avg_latency = sum(lat for _, lat in latencies) / len(latencies)
        max_latency = max(lat for _, lat in latencies)
        print(f"⏱️ متوسط زمن الاستجابة: {avg_latency:.2f}s")
        print(f"⏱️ أعلى زمن استجابة: {max_latency:.2f}s")
        
        # تحذيرات الأداء
        slow_tests = [(name, lat) for name, lat in latencies if lat > 10]
        if slow_tests:
            print(f"🐌 اختبارات بطيئة (>10s):")
            for name, lat in slow_tests:
                print(f"   - {name}: {lat:.2f}s")
    
    if passed == total:
        print("🎉 جميع اختبارات تكامل الباك إند نجحت!")
        return True
    else:
        print(f"⚠️ {total - passed} اختبارات فشلت")
        return False

if __name__ == "__main__":
    success = run_ai_financial_backend_tests()
    exit(0 if success else 1)