#!/usr/bin/env python3
"""
اختبار إضافي لحل مشكلة accountId UUID
Additional test to fix accountId UUID issue
"""

import requests
import json
import uuid

API_URL = "https://finance-overhaul-7.preview.emergentagent.com"

def test_with_proper_uuid():
    """اختبار مع UUID صحيح للـ accountId"""
    print("🔧 اختبار مع UUID صحيح للـ accountId")
    
    # إنشاء UUID صحيح
    proper_account_id = str(uuid.uuid4())
    proper_vehicle_id = str(uuid.uuid4())
    
    payload = {
        "type": "purchase",
        "partnerType": "supplier", 
        "partnerName": "اختبار UUID صحيح",
        "accountId": proper_account_id,
        "vehicleId": proper_vehicle_id,
        "items": [
            {
                "itemType": "part",
                "itemId": "t-uuid-test",
                "name": "قطعة اختبار UUID",
                "quantity": 1,  # استخدام quantity
                "price": 75
            }
        ],
        "paymentMethod": "cash",
        "notes": "test with proper UUID"
    }
    
    print(f"accountId: {proper_account_id}")
    print(f"vehicleId: {proper_vehicle_id}")
    
    try:
        response = requests.post(
            f"{API_URL}/api/operations",
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ نجح الاختبار مع UUID صحيح!")
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print("❌ فشل حتى مع UUID صحيح")
            print(response.text)
            
    except Exception as e:
        print(f"خطأ: {e}")

def test_with_null_account_id():
    """اختبار مع accountId فارغ"""
    print("\n🔧 اختبار مع accountId فارغ")
    
    payload = {
        "type": "purchase",
        "partnerType": "supplier",
        "partnerName": "اختبار بدون accountId",
        "items": [
            {
                "itemType": "part", 
                "itemId": "t-null-test",
                "name": "قطعة بدون account",
                "quantity": 1,
                "price": 60
            }
        ],
        "paymentMethod": "cash",
        "notes": "test without accountId"
    }
    
    try:
        response = requests.post(
            f"{API_URL}/api/operations",
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ نجح الاختبار بدون accountId!")
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print("❌ فشل بدون accountId")
            print(response.text)
            
    except Exception as e:
        print(f"خطأ: {e}")

def test_quantity_vs_qty():
    """اختبار الفرق بين quantity و qty"""
    print("\n🔧 اختبار الفرق بين quantity و qty")
    
    # اختبار مع qty (يجب أن ينجح)
    payload_qty = {
        "type": "purchase",
        "partnerType": "supplier",
        "partnerName": "اختبار qty",
        "items": [
            {
                "itemType": "part",
                "itemId": "t-qty-test", 
                "name": "قطعة مع qty",
                "qty": 2,  # استخدام qty
                "price": 40
            }
        ],
        "paymentMethod": "cash",
        "notes": "test with qty field"
    }
    
    print("📋 اختبار مع qty:")
    try:
        response = requests.post(
            f"{API_URL}/api/operations",
            json=payload_qty,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            print("✅ نجح مع qty")
        else:
            print("❌ فشل مع qty")
            print(response.text[:200])
    except Exception as e:
        print(f"خطأ: {e}")
    
    # اختبار مع quantity (قد يفشل)
    payload_quantity = {
        "type": "purchase", 
        "partnerType": "supplier",
        "partnerName": "اختبار quantity",
        "items": [
            {
                "itemType": "part",
                "itemId": "t-quantity-test",
                "name": "قطعة مع quantity", 
                "quantity": 2,  # استخدام quantity
                "price": 40
            }
        ],
        "paymentMethod": "cash",
        "notes": "test with quantity field"
    }
    
    print("\n📋 اختبار مع quantity:")
    try:
        response = requests.post(
            f"{API_URL}/api/operations",
            json=payload_quantity,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            print("✅ نجح مع quantity")
        else:
            print("❌ فشل مع quantity")
            print(response.text[:200])
    except Exception as e:
        print(f"خطأ: {e}")

if __name__ == "__main__":
    test_with_proper_uuid()
    test_with_null_account_id()
    test_quantity_vs_qty()