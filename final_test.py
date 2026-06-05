#!/usr/bin/env python3
"""
اختبار نهائي مع business account صحيح
Final test with valid business account
"""

import requests
import json

API_URL = "https://garage-erp-arabic.preview.emergentagent.com"

def test_with_valid_business_account():
    """اختبار مع business account صحيح"""
    print("🔧 اختبار مع business account صحيح")
    
    # استخدام business account موجود
    valid_account_id = "40b024d7-260d-4b45-94fb-20c1c594c76f"  # الفرع الرئيسي
    
    payload = {
        "type": "purchase",
        "partnerType": "supplier",
        "partnerName": "اختبار مع business account صحيح",
        "accountId": valid_account_id,
        "items": [
            {
                "itemType": "part",
                "itemId": "t-valid-account",
                "name": "قطعة مع business account",
                "quantity": 2,  # استخدام quantity
                "price": 85
            }
        ],
        "paymentMethod": "cash",
        "notes": "test with valid business account"
    }
    
    print(f"accountId: {valid_account_id} (الفرع الرئيسي)")
    
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
            print("✅ نجح الاختبار مع business account صحيح!")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return True
        else:
            print("❌ فشل مع business account صحيح")
            print(response.text)
            return False
            
    except Exception as e:
        print(f"خطأ: {e}")
        return False

def test_frontend_like_payload():
    """اختبار مع payload مشابه للواجهة مع business account صحيح"""
    print("\n🔧 اختبار مع payload مشابه للواجهة")
    
    valid_account_id = "40b024d7-260d-4b45-94fb-20c1c594c76f"
    
    # payload مشابه لما ترسله الواجهة
    payload = {
        "accountId": valid_account_id,
        "vehicleId": "",  # فارغ
        "visitId": "",   # فارغ
        "scope": "workshop",
        "type": "purchase",
        "partnerType": "supplier",
        "partnerName": "مورد قطع غيار",
        "items": [
            {
                "itemType": "part",
                "itemId": "part-123",
                "name": "فلتر زيت",
                "quantity": 3,
                "price": 45
            },
            {
                "itemType": "service",
                "itemId": "service-456", 
                "name": "تغيير زيت",
                "quantity": 1,
                "price": 120
            }
        ],
        "paymentMethod": "cash",
        "notes": "عملية شراء من الواجهة",
        "paymentReceipt": None
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
            print("✅ نجح الاختبار مع payload مشابه للواجهة!")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return True
        else:
            print("❌ فشل مع payload مشابه للواجهة")
            print(response.text)
            return False
            
    except Exception as e:
        print(f"خطأ: {e}")
        return False

if __name__ == "__main__":
    success1 = test_with_valid_business_account()
    success2 = test_frontend_like_payload()
    
    print(f"\n📊 النتائج النهائية:")
    print(f"اختبار business account صحيح: {'✅ نجح' if success1 else '❌ فشل'}")
    print(f"اختبار payload مشابه للواجهة: {'✅ نجح' if success2 else '❌ فشل'}")
    
    if success1 and success2:
        print("\n🎉 جميع الاختبارات نجحت! المشكلة كانت في accountId غير صحيح")
    else:
        print("\n⚠️ ما زالت هناك مشاكل تحتاج حل")