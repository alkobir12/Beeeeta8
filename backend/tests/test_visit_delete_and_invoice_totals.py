#!/usr/bin/env python3
"""
Pytest test file for Arabic Review Request
اختبار pytest للمراجعة العربية

Tests:
1) Invoice document generation - no subtotal, single total only
3) Delete closed visit functionality

Created under /app/backend/tests/ as requested
"""

import pytest
import requests
import json
import uuid
from datetime import datetime

# Backend URL from frontend .env
BACKEND_URL = "https://vehicle-accounting-2.preview.emergentagent.com/api"
VEHICLE_ID = "f3422cc1-dd9c-4e69-8205-0aa50b3795a1"

class TestVisitDeleteAndInvoiceTotals:
    """Test class for visit deletion and invoice totals validation"""
    
    def test_invoice_document_no_subtotal_single_total(self):
        """
        Test 1: تأكد أن توليد المستند /api/documents/generate لفاتورة invoice 
        لا يحتوي 'المجموع الفرعي' ويحتوي فقط 'المجموع الكلي' مرة واحدة
        """
        url = f"{BACKEND_URL}/documents/generate"
        
        payload = {
            "doc_type": "invoice",
            "workshop": {
                "name": "ورشة الاختبار",
                "phone": "0553280100",
                "address": "الرياض، المملكة العربية السعودية",
                "commercial_register": "1010123456"
            },
            "customer": {
                "name": "عميل الاختبار",
                "phone": "0551234567"
            },
            "vehicle": {
                "brand": "تويوتا",
                "model": "كامري",
                "year": "2023",
                "plateNumber": "أ ب ج 1234"
            },
            "items": [
                {
                    "description": "تغيير زيت المحرك",
                    "quantity": 1,
                    "unit_price": 150
                },
                {
                    "description": "فلتر الزيت",
                    "quantity": 1,
                    "unit_price": 50
                }
            ],
            "settings": {
                "theme": "أزرق",
                "style": "حديث",
                "document_number": f"INV-TEST-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            }
        }
        
        response = requests.post(url, json=payload, timeout=30)
        
        # Assert successful response
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=true, got: {data}"
        
        html_content = data.get("html", "")
        assert html_content, "Expected HTML content in response"
        
        # Check for forbidden subtotal text
        forbidden_subtotal = "المجموع الفرعي"
        subtotal_count = html_content.count(forbidden_subtotal)
        
        # Check for required total text
        required_total = "المجموع الكلي"
        total_count = html_content.count(required_total)
        
        # Assertions
        assert subtotal_count == 0, f"Found {subtotal_count} occurrences of subtotal '{forbidden_subtotal}', expected 0"
        assert total_count == 1, f"Found {total_count} occurrences of total '{required_total}', expected exactly 1"
        
        print(f"✅ Invoice generated: {data.get('document_number')}")
        print(f"✅ No subtotal found, exactly one total found")
    
    def test_delete_closed_visit_functionality(self):
        """
        Test 3: اختبر حذف زيارة مغلقة
        - احصل على vehicle visits لسيارة f3422cc1-dd9c-4e69-8205-0aa50b3795a1
        - اختر زيارة status != in_progress
        - نفّذ DELETE /api/visits/{visit_id}
        - تأكد يرجع success true ثم GET visits لا يحتوي نفس visit
        """
        # Get vehicle visits
        visits_url = f"{BACKEND_URL}/vehicles/{VEHICLE_ID}/visits"
        
        visits_response = requests.get(visits_url, timeout=30)
        assert visits_response.status_code == 200, f"Cannot get vehicle visits: HTTP {visits_response.status_code}"
        
        visits_data = visits_response.json()
        visits = visits_data if isinstance(visits_data, list) else visits_data.get("visits", [])
        
        # Find a visit with status != in_progress
        closed_visit = None
        for visit in visits:
            status = visit.get("status", "").lower()
            if status != "in_progress":
                closed_visit = visit
                break
        
        if not closed_visit:
            # Create a test visit with completed status
            create_visit_payload = {
                "status": "completed",
                "notes": json.dumps({"items": [{"name": "Test service", "price": 100}]}),
                "mileage": 50000,
                "entry_date": datetime.now().isoformat()
            }
            
            create_response = requests.post(visits_url, json=create_visit_payload, timeout=30)
            assert create_response.status_code == 200, f"Cannot create test visit: {create_response.text}"
            
            closed_visit = create_response.json()
            print(f"✅ Created test visit: {closed_visit.get('id')}")
        
        visit_id = closed_visit.get("id")
        visit_status = closed_visit.get("status")
        
        assert visit_id, "Visit ID is required"
        assert visit_status != "in_progress", f"Expected non-in_progress status, got: {visit_status}"
        
        print(f"🎯 Testing deletion of visit: {visit_id} (status: {visit_status})")
        
        # Delete the visit
        delete_url = f"{BACKEND_URL}/visits/{visit_id}"
        delete_response = requests.delete(delete_url, timeout=30)
        
        assert delete_response.status_code == 200, f"Delete failed: HTTP {delete_response.status_code}: {delete_response.text}"
        
        delete_data = delete_response.json()
        success = delete_data.get("success", False)
        
        assert success == True, f"Expected success=true, got: {delete_data}"
        
        # Verify visit is no longer in the list
        verify_response = requests.get(visits_url, timeout=30)
        assert verify_response.status_code == 200, f"Cannot verify deletion: HTTP {verify_response.status_code}"
        
        verify_data = verify_response.json()
        verify_visits = verify_data if isinstance(verify_data, list) else verify_data.get("visits", [])
        
        # Check if deleted visit is still in the list
        deleted_visit_found = any(v.get("id") == visit_id for v in verify_visits)
        
        assert not deleted_visit_found, f"Deleted visit {visit_id} still found in visits list"
        
        print(f"✅ Visit {visit_id} successfully deleted and verified")

if __name__ == "__main__":
    pytest.main([__file__, "-v"])