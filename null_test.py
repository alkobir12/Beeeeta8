#!/usr/bin/env python3
"""
اختبار مع null بدلاً من string فارغ
Test with null instead of empty string
"""

import requests
import json

API_URL = "https://workshop-helper-7.preview.emergentagent.com"

def test_with_null_values():
    """اختبار مع null بدلاً من string فارغ"""
    print("🔧 اختبار مع null بدلاً من string فارغ")
    
    valid_account_id = "40b024d7-260d-4b45-94fb-20c1c594c76f"
    
    payload = {
        "accountId": valid_account_id,
        "vehicleId": None,  # null بدلاً من ""
        "visitId": None,    # null بدلاً من ""
        "scope": "workshop",
        "type": "purchase",
        "partnerType": "supplier",
        "partnerName": "مورد قطع غيار - null test",
        "items": [
            {
                "itemType": "part",
                "itemId": "part-null-test",
                "name": "فلتر زيت - null test",
                "quantity": 2,
                "price": 55
            }
        ],
        "paymentMethod": "cash",
        "notes": "اختبار مع null values",
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
            print("✅ نجح الاختبار مع null values!")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return True
        else:
            print("❌ فشل مع null values")
            print(response.text)
            return False
            
    except Exception as e:
        print(f"خطأ: {e}")
        return False

def test_without_optional_fields():
    """اختبار بدون الحقول الاختيارية"""
    print("\n🔧 اختبار بدون الحقول الاختيارية")
    
    valid_account_id = "40b024d7-260d-4b45-94fb-20c1c594c76f"
    
    # payload مبسط بدون الحقول الاختيارية
    payload = {
        "accountId": valid_account_id,
        "type": "purchase",
        "partnerType": "supplier",
        "partnerName": "مورد مبسط",
        "items": [
            {
                "itemType": "part",
                "itemId": "part-simple",
                "name": "قطعة مبسطة",
                "quantity": 1,
                "price": 100
            }
        ],
        "paymentMethod": "cash",
        "notes": "اختبار مبسط"
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
            print("✅ نجح الاختبار المبسط!")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return True
        else:
            print("❌ فشل الاختبار المبسط")
            print(response.text)
            return False
            
    except Exception as e:
        print(f"خطأ: {e}")
        return False

if __name__ == "__main__":
    success1 = test_with_null_values()
    success2 = test_without_optional_fields()
    
    print(f"\n📊 النتائج:")
    print(f"اختبار مع null values: {'✅ نجح' if success1 else '❌ فشل'}")
    print(f"اختبار مبسط: {'✅ نجح' if success2 else '❌ فشل'}")