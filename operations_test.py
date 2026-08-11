#!/usr/bin/env python3
"""
اختبار شامل لمسار POST /api/operations
Testing comprehensive POST /api/operations endpoint

الهدف:
1) معرفة لماذا بعض طلبات POST /api/operations ترجع 500/520 من الواجهة بينما طلبات curl البسيطة تنجح
2) التأكد من تطابق شكل البيانات (schema) بين الباك إند والواجهة
3) إنتاج Log اختبارات واضح يبيّن كل تجربة وما كانت نتيجتها
"""

import requests
import json
import os
from datetime import datetime

# قراءة URL الباك إند من ملف البيئة
def get_backend_url():
    try:
        with open('/app/frontend/.env', 'r') as f:
            for line in f:
                if line.startswith('REACT_APP_BACKEND_URL='):
                    return line.split('=', 1)[1].strip()
    except:
        pass
    return "https://canonical-integrity.preview.emergentagent.com"

API_URL = get_backend_url()
print(f"🔗 Backend URL: {API_URL}")

def test_get_operations():
    """استرجاع مثال من العمليات الحالية"""
    print("\n" + "="*60)
    print("📋 1) استرجاع العمليات الحالية (GET /api/operations)")
    print("="*60)
    
    try:
        response = requests.get(f"{API_URL}/api/operations", timeout=30)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            operations = response.json()
            print(f"عدد العمليات الموجودة: {len(operations)}")
            
            if operations:
                first_op = operations[0]
                print("\n📄 شكل أول عملية موجودة:")
                print(json.dumps(first_op, indent=2, ensure_ascii=False))
                
                print("\n🔑 المفاتيح الموجودة في العملية:")
                for key in first_op.keys():
                    print(f"  - {key}: {type(first_op[key]).__name__}")
                
                return first_op
            else:
                print("⚠️ لا توجد عمليات في قاعدة البيانات")
                return None
        else:
            print(f"❌ خطأ في استرجاع العمليات: {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ خطأ في الاتصال: {str(e)}")
        return None

def test_post_operation(test_name, payload):
    """اختبار POST /api/operations مع payload محدد"""
    print(f"\n📤 اختبار: {test_name}")
    print("-" * 50)
    
    print("📋 البيانات المرسلة:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    
    try:
        response = requests.post(
            f"{API_URL}/api/operations", 
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        print(f"\n📊 النتيجة:")
        print(f"Status Code: {response.status_code}")
        
        try:
            response_data = response.json()
            print("Response JSON:")
            print(json.dumps(response_data, indent=2, ensure_ascii=False))
            
            # البحث عن رسائل الخطأ
            if response.status_code >= 400:
                error_fields = ['error', 'detail', 'message', 'errors']
                for field in error_fields:
                    if field in response_data:
                        print(f"🚨 رسالة الخطأ ({field}): {response_data[field]}")
                        
        except json.JSONDecodeError:
            print("Response Text (not JSON):")
            print(response.text[:500])
            
        return {
            'status_code': response.status_code,
            'success': response.status_code < 400,
            'response': response.text[:500] if response.status_code >= 400 else response.json()
        }
        
    except Exception as e:
        print(f"❌ خطأ في الطلب: {str(e)}")
        return {
            'status_code': 0,
            'success': False,
            'response': str(e)
        }

def run_operation_tests():
    """تشغيل جميع اختبارات العمليات"""
    print("🚀 بدء اختبار مسار POST /api/operations")
    print("=" * 80)
    
    # 1) استرجاع العمليات الحالية
    existing_operation = test_get_operations()
    
    # 2) اختبار أربعة أنواع من الطلبات
    test_results = []
    
    # (A) أبسط نموذج يعمل (baseline)
    payload_a = {
        "type": "purchase",
        "partnerType": "supplier",
        "partnerName": "اختبار بسيط",
        "items": [
            {
                "itemType": "part",
                "itemId": "t1",
                "name": "قطعة",
                "qty": 1,
                "price": 100
            }
        ],
        "paymentMethod": "cash",
        "notes": "baseline"
    }
    
    result_a = test_post_operation("(A) أبسط نموذج يعمل (baseline)", payload_a)
    test_results.append(("A - Baseline", result_a))
    
    # (B) نموذج قريب من الواجهة (باستخدام quantity بدلاً من qty)
    payload_b = {
        "type": "purchase",
        "partnerType": "supplier",
        "partnerName": "اختبار quantity",
        "accountId": "113",
        "vehicleId": "veh-test-1",
        "items": [
            {
                "itemType": "part",
                "itemId": "t2",
                "name": "زيت",
                "quantity": 2,  # استخدام quantity بدلاً من qty
                "price": 50
            }
        ],
        "paymentMethod": "cash",
        "notes": "from operations form style"
    }
    
    result_b = test_post_operation("(B) نموذج قريب من الواجهة (quantity)", payload_b)
    test_results.append(("B - Frontend Style", result_b))
    
    # (C) نموذج فيه scope و visitId كما يرسله الـ form
    payload_c = {
        "type": "purchase",
        "partnerType": "supplier",
        "partnerName": "اختبار scope",
        "accountId": "113",
        "vehicleId": "veh-test-2",
        "visitId": "visit-test-1",
        "scope": "vehicle",
        "items": [
            {
                "itemType": "part",
                "itemId": "t3",
                "name": "فلتر هواء",
                "quantity": 1,
                "price": 80
            }
        ],
        "paymentMethod": "cash",
        "notes": "with scope & visitId"
    }
    
    result_c = test_post_operation("(C) نموذج مع scope و visitId", payload_c)
    test_results.append(("C - With Scope & VisitId", result_c))
    
    # (D) نموذج بدون items (Edge case)
    payload_d = {
        "type": "purchase",
        "partnerType": "supplier",
        "partnerName": "بدون عناصر",
        "items": [],
        "paymentMethod": "cash",
        "notes": "no items"
    }
    
    result_d = test_post_operation("(D) نموذج بدون عناصر (Edge case)", payload_d)
    test_results.append(("D - No Items", result_d))
    
    return test_results, existing_operation

def analyze_frontend_backend_schema():
    """مقارنة شكل البيانات بين الواجهة والباك إند"""
    print("\n" + "="*60)
    print("🔍 3) مقارنة شكل البيانات بين الواجهة والباك إند")
    print("="*60)
    
    print("\n📋 شكل البيانات المتوقع من الواجهة (Operations.jsx):")
    frontend_schema = {
        "accountId": "string",
        "vehicleId": "string", 
        "visitId": "string",
        "scope": "string ('vehicle' | 'workshop')",
        "type": "string ('purchase' | 'sale')",
        "partnerType": "string ('supplier' | 'customer')",
        "partnerName": "string",
        "items": [
            {
                "itemType": "string ('part' | 'service')",
                "itemId": "string",
                "name": "string",
                "quantity": "number",  # الواجهة تستخدم quantity
                "price": "number"
            }
        ],
        "paymentMethod": "string ('cash' | 'credit')",
        "notes": "string",
        "paymentReceipt": "file | null"
    }
    
    for key, value_type in frontend_schema.items():
        print(f"  - {key}: {value_type}")
    
    print("\n📋 شكل البيانات المتوقع من الباك إند (supabase_service.operations_create):")
    backend_schema = {
        "type": "string",
        "accountId": "string (-> account_id)",
        "vehicleId": "string (-> vehicle_id)", 
        "partnerType": "string (-> partner_type)",
        "partnerName": "string (-> partner_name)",
        "items": [
            {
                "itemType": "string",
                "itemId": "string", 
                "name": "string",
                "qty": "number",  # الباك إند يتوقع qty
                "price": "number"
            }
        ],
        "paymentMethod": "string (-> payment_method)",
        "notes": "string"
    }
    
    for key, value_type in backend_schema.items():
        print(f"  - {key}: {value_type}")
    
    print("\n⚠️ الاختلافات المحتملة:")
    differences = [
        "1. الواجهة ترسل 'quantity' بينما الباك إند يتوقع 'qty' في العناصر",
        "2. الواجهة ترسل 'visitId' و 'scope' و 'paymentReceipt' التي قد لا يدعمها الباك إند",
        "3. الباك إند يحول camelCase إلى snake_case (accountId -> account_id)",
        "4. الواجهة قد ترسل حقول إضافية غير مدعومة"
    ]
    
    for diff in differences:
        print(f"  {diff}")

def generate_final_report(test_results, existing_operation):
    """إنتاج التقرير النهائي"""
    print("\n" + "="*80)
    print("📊 4) التقرير النهائي - نتائج اختبار POST /api/operations")
    print("="*80)
    
    print("\n📋 جدول نتائج الاختبارات:")
    print("-" * 80)
    print(f"{'اختبار':<25} {'Status Code':<12} {'نجح/فشل':<10} {'ملاحظات'}")
    print("-" * 80)
    
    for test_name, result in test_results:
        status = "✅ نجح" if result['success'] else "❌ فشل"
        notes = ""
        
        if not result['success']:
            if isinstance(result['response'], dict):
                # البحث عن رسالة خطأ
                error_msg = (result['response'].get('detail') or 
                           result['response'].get('error') or 
                           result['response'].get('message') or 
                           str(result['response'])[:50])
                notes = f"خطأ: {error_msg}"
            else:
                notes = f"خطأ: {str(result['response'])[:50]}"
        
        print(f"{test_name:<25} {result['status_code']:<12} {status:<10} {notes}")
    
    print("-" * 80)
    
    # خلاصة المقارنة
    print("\n🔍 خلاصة المقارنة بين الواجهة والباك إند:")
    
    if existing_operation:
        print(f"\n📄 شكل العملية في قاعدة البيانات:")
        db_keys = list(existing_operation.keys())
        print(f"المفاتيح: {', '.join(db_keys)}")
        
        if 'items' in existing_operation and existing_operation['items']:
            item_keys = list(existing_operation['items'][0].keys()) if existing_operation['items'] else []
            print(f"مفاتيح العناصر: {', '.join(item_keys)}")
    
    print(f"\n📋 شكل form الواجهة:")
    frontend_keys = ['accountId', 'vehicleId', 'visitId', 'scope', 'type', 'partnerType', 'partnerName', 'items', 'paymentMethod', 'notes', 'paymentReceipt']
    print(f"المفاتيح: {', '.join(frontend_keys)}")
    
    print(f"\n📋 مفاتيح العناصر في الواجهة:")
    item_keys = ['itemType', 'itemId', 'name', 'quantity', 'price']
    print(f"المفاتيح: {', '.join(item_keys)}")
    
    # توصيات الإصلاح
    print(f"\n💡 توصيات الإصلاح:")
    
    failed_tests = [result for _, result in test_results if not result['success']]
    
    if failed_tests:
        print("1. إصلاح الأخطاء التالية في الباك إند:")
        for i, (test_name, result) in enumerate(test_results):
            if not result['success']:
                print(f"   - {test_name}: {result.get('response', 'خطأ غير محدد')}")
    
    print("2. توحيد أسماء الحقول:")
    print("   - تحويل 'quantity' إلى 'qty' في الواجهة أو دعم كلاهما في الباك إند")
    print("   - التعامل مع الحقول الإضافية (visitId, scope, paymentReceipt) في الباك إند")
    
    print("3. تحسين معالجة الأخطاء:")
    print("   - إرجاع رسائل خطأ واضحة عند فشل العملية")
    print("   - التحقق من صحة البيانات قبل المعالجة")
    
    success_count = sum(1 for _, result in test_results if result['success'])
    total_count = len(test_results)
    
    print(f"\n📈 الخلاصة العامة:")
    print(f"نجح {success_count} من {total_count} اختبارات ({success_count/total_count*100:.1f}%)")
    
    if success_count == total_count:
        print("✅ جميع الاختبارات نجحت - النظام يعمل بشكل صحيح")
    elif success_count > 0:
        print("⚠️ بعض الاختبارات فشلت - يحتاج إصلاحات جزئية")
    else:
        print("❌ جميع الاختبارات فشلت - يحتاج مراجعة شاملة")

def main():
    """الدالة الرئيسية"""
    print("🔧 اختبار شامل لمسار POST /api/operations")
    print(f"⏰ وقت الاختبار: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🌐 Backend URL: {API_URL}")
    
    try:
        # تشغيل الاختبارات
        test_results, existing_operation = run_operation_tests()
        
        # تحليل الاختلافات
        analyze_frontend_backend_schema()
        
        # إنتاج التقرير النهائي
        generate_final_report(test_results, existing_operation)
        
        print(f"\n✅ انتهى الاختبار بنجاح")
        
    except Exception as e:
        print(f"\n❌ خطأ عام في الاختبار: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()