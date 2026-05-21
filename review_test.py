#!/usr/bin/env python3
"""
Specific test for the review request:
1) Import template A: POST /api/invoice-templates/import-url with https://customer-assets.emergentagent.com/job_autoworkshopai/artifacts/4gfupvnp_%D9%86%D9%85%D9%88%D8%B0%D8%AC%20%D8%A7.xlsx
2) Import template B: POST /api/invoice-templates/import-url with https://customer-assets.emergentagent.com/job_autoworkshopai/artifacts/fa15iq7h_%D9%81%D8%A7%D8%AA%D9%88%D8%B1%D8%A9%20%D9%86%D9%85%D9%88%D8%B0%D8%AC.xlsx
3) Get list and ensure both present
4) Make template B default
5) Call POST /api/print/invoice-xlsx with templateId of B and sample data with ITEMS to ensure XLSX returned
"""

import requests
import json
import sys
from datetime import datetime

BASE_URL = "https://fleet-audit-system-2.preview.emergentagent.com/api"

def test_review_requirements():
    print("🧪 REVIEW REQUEST TEST: Invoice Template Import and Generation")
    print("=" * 70)
    
    results = []
    template_a_id = None
    template_b_id = None
    
    # Test 1: Import Template A
    print("\n1️⃣ Testing Template A Import...")
    url_a = "https://customer-assets.emergentagent.com/job_autoworkshopai/artifacts/4gfupvnp_%D9%86%D9%85%D9%88%D8%B0%D8%AC%20%D8%A7.xlsx"
    
    try:
        response = requests.post(
            f"{BASE_URL}/invoice-templates/import-url",
            json={"url": url_a},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            template_a_id = data.get('id')
            print(f"✅ Template A imported successfully")
            print(f"   ID: {template_a_id}")
            print(f"   Name: {data.get('name')}")
            print(f"   Format: {data.get('format')}")
            print(f"   Preview rows: {len(data.get('preview', []))}")
            results.append(("Import Template A", True))
        else:
            print(f"❌ Template A import failed: {response.status_code}")
            print(f"   Response: {response.text}")
            results.append(("Import Template A", False))
    except Exception as e:
        print(f"❌ Template A import error: {e}")
        results.append(("Import Template A", False))
    
    # Test 2: Import Template B
    print("\n2️⃣ Testing Template B Import...")
    url_b = "https://customer-assets.emergentagent.com/job_autoworkshopai/artifacts/fa15iq7h_%D9%81%D8%A7%D8%AA%D9%88%D8%B1%D8%A9%20%D9%86%D9%85%D9%88%D8%B0%D8%AC.xlsx"
    
    try:
        response = requests.post(
            f"{BASE_URL}/invoice-templates/import-url",
            json={"url": url_b},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            template_b_id = data.get('id')
            print(f"✅ Template B imported successfully")
            print(f"   ID: {template_b_id}")
            print(f"   Name: {data.get('name')}")
            print(f"   Format: {data.get('format')}")
            print(f"   Preview rows: {len(data.get('preview', []))}")
            results.append(("Import Template B", True))
        else:
            print(f"❌ Template B import failed: {response.status_code}")
            print(f"   Response: {response.text}")
            results.append(("Import Template B", False))
    except Exception as e:
        print(f"❌ Template B import error: {e}")
        results.append(("Import Template B", False))
    
    # Test 3: Get list and ensure both present
    print("\n3️⃣ Testing Template List...")
    try:
        response = requests.get(f"{BASE_URL}/invoice-templates", timeout=10)
        
        if response.status_code == 200:
            templates = response.json()
            print(f"✅ Templates list retrieved successfully")
            print(f"   Total templates: {len(templates)}")
            
            template_a_found = False
            template_b_found = False
            
            for template in templates:
                if template.get('id') == template_a_id:
                    template_a_found = True
                    print(f"   ✓ Template A found: {template.get('name')}")
                if template.get('id') == template_b_id:
                    template_b_found = True
                    print(f"   ✓ Template B found: {template.get('name')}")
            
            if template_a_found and template_b_found:
                print("✅ Both templates are present in the list")
                results.append(("List Templates", True))
            else:
                print(f"❌ Missing templates - A: {template_a_found}, B: {template_b_found}")
                results.append(("List Templates", False))
        else:
            print(f"❌ Template list failed: {response.status_code}")
            results.append(("List Templates", False))
    except Exception as e:
        print(f"❌ Template list error: {e}")
        results.append(("List Templates", False))
    
    # Test 4: Make template B default
    print("\n4️⃣ Testing Make Template B Default...")
    if template_b_id:
        try:
            response = requests.post(
                f"{BASE_URL}/invoice-templates/{template_b_id}/make-default",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('isDefault') == True:
                    print(f"✅ Template B set as default successfully")
                    print(f"   Template ID: {data.get('id')}")
                    print(f"   Is Default: {data.get('isDefault')}")
                    results.append(("Make Template B Default", True))
                else:
                    print(f"❌ Template B not marked as default")
                    results.append(("Make Template B Default", False))
            else:
                print(f"❌ Make default failed: {response.status_code}")
                print(f"   Response: {response.text}")
                results.append(("Make Template B Default", False))
        except Exception as e:
            print(f"❌ Make default error: {e}")
            results.append(("Make Template B Default", False))
    else:
        print("❌ Template B ID not available")
        results.append(("Make Template B Default", False))
    
    # Test 5: Generate Invoice XLSX with Template B
    print("\n5️⃣ Testing Invoice XLSX Generation...")
    if template_b_id:
        sample_data = {
            "templateId": template_b_id,
            "data": {
                "CUSTOMER_NAME": "أحمد محمد الراشد",
                "INVOICE_NUMBER": "INV-20250108-001",
                "DATE": datetime.now().strftime("%Y-%m-%d"),
                "WORKSHOP_NAME": "ورشة الاختبار الشاملة",
                "WORKSHOP_PHONE": "+966501234567",
                "TOTAL": "1500.00",
                "SUBTOTAL": "1300.00",
                "TAX": "200.00",
                "ITEMS": [
                    {
                        "name": "تغيير زيت المحرك",
                        "quantity": 1,
                        "price": 150.00,
                        "total": 150.00
                    },
                    {
                        "name": "فلتر الهواء",
                        "quantity": 1,
                        "price": 80.00,
                        "total": 80.00
                    },
                    {
                        "name": "فحص شامل للمحرك",
                        "quantity": 1,
                        "price": 500.00,
                        "total": 500.00
                    }
                ]
            }
        }
        
        try:
            response = requests.post(
                f"{BASE_URL}/print/invoice-xlsx",
                json=sample_data,
                timeout=30
            )
            
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '')
                content_length = len(response.content)
                
                print(f"✅ Invoice XLSX generated successfully")
                print(f"   Content Type: {content_type}")
                print(f"   Content Length: {content_length} bytes")
                print(f"   Template ID used: {template_b_id}")
                
                # Verify it's actually an XLSX file
                if 'spreadsheet' in content_type or content_length > 1000:
                    print("✅ Response appears to be a valid XLSX file")
                    results.append(("Generate Invoice XLSX", True))
                else:
                    print("⚠️  Response may not be a valid XLSX file")
                    results.append(("Generate Invoice XLSX", False))
            else:
                print(f"❌ Invoice XLSX generation failed: {response.status_code}")
                print(f"   Response: {response.text}")
                results.append(("Generate Invoice XLSX", False))
        except Exception as e:
            print(f"❌ Invoice XLSX generation error: {e}")
            results.append(("Generate Invoice XLSX", False))
    else:
        print("❌ Template B ID not available")
        results.append(("Generate Invoice XLSX", False))
    
    # Print final summary
    print("\n" + "=" * 70)
    print("📊 FINAL TEST RESULTS")
    print("=" * 70)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
        if result:
            passed += 1
    
    print(f"\n📈 Overall Result: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED - Invoice template functionality is working correctly!")
        return True
    else:
        print("⚠️  SOME TESTS FAILED - Please check the failed tests above")
        return False

if __name__ == "__main__":
    success = test_review_requirements()
    sys.exit(0 if success else 1)