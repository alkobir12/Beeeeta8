#!/usr/bin/env python3
"""
اختبار مركز للتحقق من مشكلة حساب الذمم المدينة
Focused test to check AR calculation issue
"""

import requests
import json

BACKEND_URL = "https://contract-audit-demo.preview.emergentagent.com/api"
WORKSHOP_ID = "finmodule-sync"

def test_ar_calculation_issue():
    """اختبار مشكلة حساب الذمم المدينة"""
    
    print("🚀 بدء اختبار مشكلة حساب الذمم المدينة")
    
    # Step 1: Reset data
    print("\n1️⃣ تصفير البيانات...")
    reset_url = f"{BACKEND_URL}/finance/reset-all-data"
    reset_params = {"workshop_id": WORKSHOP_ID, "confirm": "DELETE_ALL"}
    reset_response = requests.delete(reset_url, params=reset_params, timeout=30)
    print(f"   تصفير البيانات: {reset_response.status_code}")
    
    # Step 2: Create credit operation
    print("\n2️⃣ إنشاء عملية آجلة...")
    operation_data = {
        "workshopId": WORKSHOP_ID,
        "type": "sale",
        "paymentMethod": "credit",
        "partnerName": "أحمد العميل التجريبي",
        "partnerType": "customer",
        "opDate": "2024-06-01",
        "items": [{"itemType": "service", "name": "خدمة صيانة", "quantity": 1, "price": 100.0}],
        "total": 100.0,
        "notes": "عملية بيع آجل للاختبار"
    }
    
    operation_url = f"{BACKEND_URL}/operations"
    operation_response = requests.post(operation_url, json=operation_data, timeout=30)
    print(f"   إنشاء العملية: {operation_response.status_code}")
    
    if operation_response.status_code == 200:
        operation_id = operation_response.json().get("id")
        print(f"   معرف العملية: {operation_id}")
        
        # Step 3: Check AR after operation creation
        print("\n3️⃣ فحص الذمم بعد إنشاء العملية...")
        check_ar_state("بعد إنشاء العملية")
        
        # Step 4: Confirm first payment
        print("\n4️⃣ تأكيد السداد الأول (40 ريال)...")
        payment_data = {
            "workshopId": WORKSHOP_ID,
            "amount": 40.0,
            "payment_date": "2024-06-15",
            "notes": "سداد جزئي 40 ريال"
        }
        
        payment_url = f"{BACKEND_URL}/operations/{operation_id}/confirm-payment"
        payment_response = requests.post(payment_url, json=payment_data, timeout=30)
        print(f"   تأكيد السداد الأول: {payment_response.status_code}")
        
        if payment_response.status_code == 200:
            payment_result = payment_response.json()
            print(f"   نتيجة السداد: {payment_result}")
            
            # Check AR after first payment
            print("\n5️⃣ فحص الذمم بعد السداد الأول...")
            check_ar_state("بعد السداد الأول")
            
            # Step 6: Confirm second payment
            print("\n6️⃣ تأكيد السداد الثاني (60 ريال)...")
            payment_data["amount"] = 60.0
            payment_data["notes"] = "سداد متبقي 60 ريال"
            
            payment_response2 = requests.post(payment_url, json=payment_data, timeout=30)
            print(f"   تأكيد السداد الثاني: {payment_response2.status_code}")
            
            if payment_response2.status_code == 200:
                payment_result2 = payment_response2.json()
                print(f"   نتيجة السداد: {payment_result2}")
                
                # Check AR after second payment
                print("\n7️⃣ فحص الذمم بعد السداد الثاني...")
                check_ar_state("بعد السداد الثاني")

def check_ar_state(stage):
    """فحص حالة الذمم المدينة"""
    print(f"   📊 حالة الذمم {stage}:")
    
    # Check journal entries
    journal_url = f"{BACKEND_URL}/finance/journal-entries"
    journal_params = {"workshop_id": WORKSHOP_ID}
    journal_response = requests.get(journal_url, params=journal_params, timeout=30)
    
    if journal_response.status_code == 200:
        journal_data = journal_response.json()
        entries = journal_data.get("data", [])
        print(f"      📋 عدد القيود: {len(entries)}")
        
        ar_balance = 0
        for entry in entries:
            lines = entry.get("lines", [])
            for line in lines:
                if line.get("account") == "113":
                    debit = line.get("debit", 0)
                    credit = line.get("credit", 0)
                    ar_balance += debit - credit
        
        print(f"      💰 رصيد الذمم من القيود: {ar_balance}")
    
    # Check AR ledger
    ar_url = f"{BACKEND_URL}/finance/ar/ledger"
    ar_params = {
        "workshop_id": WORKSHOP_ID,
        "start_date": "2024-06-01",
        "end_date": "2024-06-30"
    }
    ar_response = requests.get(ar_url, params=ar_params, timeout=30)
    
    if ar_response.status_code == 200:
        ar_data = ar_response.json()
        ending_balance = ar_data.get("data", {}).get("ending_balance", 0)
        rows = ar_data.get("data", {}).get("rows", [])
        print(f"      📊 رصيد دفتر الذمم: {ending_balance}")
        print(f"      📄 عدد حركات دفتر الذمم: {len(rows)}")
        
        for row in rows:
            print(f"         {row.get('date')[:10]}: {row.get('type')} - مدين={row.get('debit', 0)}, دائن={row.get('credit', 0)}")

if __name__ == "__main__":
    test_ar_calculation_issue()