#!/usr/bin/env python3
"""
اختبار ميزة التوقيع الإلكتروني وربط الموافقة بالفاتورة وملف المركبة
Electronic Signature Feature and Approval Linking Test

Tests:
1. Backend - /api/approvals endpoints
2. Backend - Document generator with approval_info
3. Frontend - Basic integration checks
"""

import requests
import json
import uuid
import time
from datetime import datetime
from typing import Dict, Any, Optional

# Configuration
BACKEND_URL = "https://workshop-operator.preview.emergentagent.com/api"

class ApprovalSystemTester:
    def __init__(self):
        self.session = requests.Session()
        self.test_data = {}
        self.results = []
        
    def log_result(self, test_name: str, success: bool, details: str = "", data: Any = None):
        """Log test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        result = {
            "test": test_name,
            "status": status,
            "success": success,
            "details": details,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        self.results.append(result)
        print(f"{status} - {test_name}")
        if details:
            print(f"    {details}")
        if not success and data:
            print(f"    Data: {data}")
        print()

    def test_create_vehicle_and_approval(self) -> bool:
        """Test 1: Create vehicle and approval request"""
        try:
            # Create a test vehicle first
            vehicle_data = {
                "brand": "تويوتا",
                "model": "برادو",
                "year": 2020,
                "plateNumber": "ABC-1234",
                "color": "أبيض",
                "customerName": "أحمد محمد",
                "customerPhone": "0501234567",
                "customerEmail": "ahmed@test.com",
                "notes": "فحص دوري وصيانة",
                "services": []
            }
            
            response = self.session.post(f"{BACKEND_URL}/vehicles", json=vehicle_data)
            if response.status_code != 200:
                self.log_result("Create Vehicle", False, f"Failed to create vehicle: {response.status_code}", response.text)
                return False
                
            vehicle = response.json()
            self.test_data['vehicle_id'] = vehicle['id']
            self.test_data['customer_id'] = vehicle['customerId']
            
            self.log_result("Create Vehicle", True, f"Vehicle created with ID: {vehicle['id']}")
            
            # Create approval request
            approval_data = {
                "vehicleId": self.test_data['vehicle_id'],
                "customerId": self.test_data['customer_id'],
                "title": "موافقة على أعمال الصيانة",
                "amount": 1500.0,
                "serviceItems": [
                    {"description": "تغيير زيت المحرك", "price": 200},
                    {"description": "فحص الفرامل", "price": 150},
                    {"description": "تنظيف المحرك", "price": 100}
                ],
                "serviceItemsText": "تغيير زيت المحرك، فحص الفرامل، تنظيف المحرك",
                "expiryDays": 7
            }
            
            response = self.session.post(f"{BACKEND_URL}/approvals", json=approval_data)
            if response.status_code != 200:
                self.log_result("Create Approval Request", False, f"Failed to create approval: {response.status_code}", response.text)
                return False
                
            approval = response.json()
            self.test_data['approval_token'] = approval['token']
            
            self.log_result("Create Approval Request", True, f"Approval created with token: {approval['token']}")
            return True
            
        except Exception as e:
            self.log_result("Create Vehicle and Approval", False, f"Exception: {str(e)}")
            return False

    def test_public_approval_response(self) -> bool:
        """Test 2: Submit public approval response"""
        try:
            token = self.test_data.get('approval_token')
            if not token:
                self.log_result("Public Approval Response", False, "No approval token available")
                return False
            
            # Submit approval response as form data
            response_data = {
                "status": "approved",
                "name": "أحمد محمد العميل",
                "phone": "0501234567",
                "notes": "موافق على جميع الأعمال المطلوبة"
            }
            
            response = self.session.post(
                f"{BACKEND_URL}/approvals/public/{token}/respond",
                data=response_data,
                headers={
                    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15',
                    'X-Forwarded-For': '192.168.1.100',
                    'Content-Type': 'application/x-www-form-urlencoded'
                }
            )
            
            if response.status_code != 200:
                self.log_result("Public Approval Response", False, f"Failed to submit response: {response.status_code}", response.text)
                return False
                
            result = response.json()
            self.test_data['approval_response'] = result
            
            self.log_result("Public Approval Response", True, f"Response submitted successfully, status: {result.get('status')}")
            return True
            
        except Exception as e:
            self.log_result("Public Approval Response", False, f"Exception: {str(e)}")
            return False

    def test_get_approvals_with_response_data(self) -> bool:
        """Test 3: Verify GET /api/approvals returns response data"""
        try:
            vehicle_id = self.test_data.get('vehicle_id')
            if not vehicle_id:
                self.log_result("Get Approvals", False, "No vehicle ID available")
                return False
            
            # Wait a moment for data to be saved
            time.sleep(2)
            
            response = self.session.get(f"{BACKEND_URL}/approvals?vehicle_id={vehicle_id}")
            if response.status_code != 200:
                self.log_result("Get Approvals", False, f"Failed to get approvals: {response.status_code}", response.text)
                return False
                
            approvals = response.json()
            if not approvals or len(approvals) == 0:
                self.log_result("Get Approvals", False, "No approvals found")
                return False
                
            approval = approvals[0]
            
            # Check required fields
            checks = []
            
            # Status should be 'approved'
            if approval.get('status') == 'approved':
                checks.append("✅ status = 'approved'")
            else:
                checks.append(f"❌ status = '{approval.get('status')}' (expected 'approved')")
            
            # responderName should not be empty
            responder_name = approval.get('responderName')
            if responder_name and responder_name.strip():
                checks.append(f"✅ responderName = '{responder_name}'")
            else:
                checks.append(f"❌ responderName is empty or missing")
            
            # responderPhone should not be empty
            responder_phone = approval.get('responderPhone')
            if responder_phone and responder_phone.strip():
                checks.append(f"✅ responderPhone = '{responder_phone}'")
            else:
                checks.append(f"❌ responderPhone is empty or missing")
            
            # respondedAt should not be empty
            responded_at = approval.get('respondedAt')
            if responded_at and responded_at.strip():
                checks.append(f"✅ respondedAt = '{responded_at}'")
            else:
                checks.append(f"❌ respondedAt is empty or missing")
            
            # serviceItemsText should contain ip= and ua=
            service_items_text = approval.get('serviceItemsText', '')
            if 'ip=' in service_items_text and 'ua=' in service_items_text:
                checks.append(f"✅ serviceItemsText contains ip= and ua=")
            else:
                checks.append(f"❌ serviceItemsText missing ip= or ua=: '{service_items_text}'")
            
            all_passed = all('✅' in check for check in checks)
            details = "\n    ".join(checks)
            
            self.log_result("Get Approvals - Field Verification", all_passed, details, approval)
            return all_passed
            
        except Exception as e:
            self.log_result("Get Approvals", False, f"Exception: {str(e)}")
            return False

    def test_document_generator_with_approval(self) -> bool:
        """Test 4: Document generator with approval_info"""
        try:
            # Prepare document generation data with approval_info
            doc_data = {
                "doc_type": "invoice",
                "workshop": {
                    "name": "ورشة الخليج للسيارات",
                    "name_en": "Gulf Auto Workshop",
                    "address": "الرياض، المملكة العربية السعودية",
                    "phone": "0112345678",
                    "email": "info@gulfauto.com",
                    "tax_number": "123456789"
                },
                "customer": {
                    "name": "أحمد محمد العميل",
                    "company": "",
                    "address": "الرياض",
                    "phone": "0501234567",
                    "email": "ahmed@test.com"
                },
                "vehicle": {
                    "brand": "تويوتا",
                    "model": "برادو",
                    "year": "2020",
                    "plateNumber": "ABC-1234",
                    "vin": "JT123456789",
                    "color": "أبيض",
                    "mileage": "50000"
                },
                "items": [
                    {
                        "description": "تغيير زيت المحرك",
                        "quantity": 1,
                        "unit_price": 200,
                        "discount": 0
                    }
                ],
                "settings": {
                    "theme": "أزرق",
                    "style": "حديث",
                    "tax_rate": 15,
                    "approval_info": {
                        "token": self.test_data.get('approval_token', 'APR-TEST123'),
                        "status": "approved",
                        "responderName": "أحمد محمد العميل",
                        "responderPhone": "0501234567",
                        "respondedAt": datetime.now().isoformat(),
                        "clientIp": "192.168.1.100"
                    }
                }
            }
            
            response = self.session.post(f"{BACKEND_URL}/documents/generate", json=doc_data)
            if response.status_code != 200:
                self.log_result("Document Generator", False, f"Failed to generate document: {response.status_code}", response.text)
                return False
                
            result = response.json()
            html_content = result.get('html', '')
            
            if not html_content:
                self.log_result("Document Generator", False, "No HTML content returned")
                return False
            
            # Check for approval section content
            checks = []
            
            # Check for "موافقة العميل" section
            if "موافقة العميل" in html_content:
                checks.append("✅ Contains 'موافقة العميل' section")
            else:
                checks.append("❌ Missing 'موافقة العميل' section")
            
            # Check for approval text with name
            if "تمت الموافقة إلكترونياً من" in html_content and "أحمد محمد العميل" in html_content:
                checks.append("✅ Contains approval text with customer name")
            else:
                checks.append("❌ Missing approval text with customer name")
            
            # Check for approval time
            if "وقت الموافقة" in html_content:
                checks.append("✅ Contains approval time text")
            else:
                checks.append("❌ Missing approval time text")
            
            # Check for IP address
            if "عنوان الجهاز (IP)" in html_content and "192.168.1.100" in html_content:
                checks.append("✅ Contains IP address information")
            else:
                checks.append("❌ Missing IP address information")
            
            # Check for QR code image
            if 'data:image/png;base64,' in html_content and '<img src="data:image/png;base64,' in html_content:
                checks.append("✅ Contains QR code image")
            else:
                checks.append("❌ Missing QR code image")
            
            all_passed = all('✅' in check for check in checks)
            details = "\n    ".join(checks)
            
            self.log_result("Document Generator - Approval Content", all_passed, details)
            
            # Save HTML for inspection if needed
            self.test_data['generated_html'] = html_content
            
            # Print a sample of the HTML to debug
            print(f"DEBUG: Generated HTML sample (first 2000 chars):")
            print(html_content[:2000])
            print("...")
            
            # Find and print the approval section
            if "موافقة العميل" in html_content:
                start_idx = html_content.find("موافقة العميل")
                approval_section = html_content[start_idx-200:start_idx+800]
                print(f"DEBUG: Approval section:")
                print(approval_section)
            
            print(f"DEBUG: HTML contains 'موافقة العميل': {'موافقة العميل' in html_content}")
            print(f"DEBUG: HTML contains 'تمت الموافقة إلكترونياً من': {'تمت الموافقة إلكترونياً من' in html_content}")
            
            return all_passed
            
        except Exception as e:
            self.log_result("Document Generator", False, f"Exception: {str(e)}")
            return False

    def test_frontend_integration_safety(self) -> bool:
        """Test 5: Frontend integration safety checks"""
        try:
            # This is a logical test - we can't directly test React components
            # but we can verify the backend endpoints work as expected for frontend calls
            
            # Test 1: DocumentPrint.jsx scenario - sending settings with approval_token (without approval_info)
            doc_data_with_token = {
                "doc_type": "invoice",
                "workshop": {"name": "Test Workshop"},
                "customer": {"name": "Test Customer"},
                "vehicle": {"brand": "Test"},
                "items": [{"description": "Test", "quantity": 1, "unit_price": 100}],
                "settings": {
                    "approval_token": self.test_data.get('approval_token', 'TEST-TOKEN')
                }
            }
            
            response = self.session.post(f"{BACKEND_URL}/documents/generate", json=doc_data_with_token)
            if response.status_code == 200:
                self.log_result("Frontend Integration - DocumentPrint", True, "Document generation with approval_token works")
            else:
                self.log_result("Frontend Integration - DocumentPrint", False, f"Document generation failed: {response.status_code}")
                return False
            
            # Test 2: VehicleDetails.jsx scenario - GET approvals with empty or missing fields
            vehicle_id = self.test_data.get('vehicle_id')
            if vehicle_id:
                response = self.session.get(f"{BACKEND_URL}/approvals?vehicle_id={vehicle_id}")
                if response.status_code == 200:
                    approvals = response.json()
                    # This should not cause errors even if serviceItemsText is missing
                    self.log_result("Frontend Integration - VehicleDetails", True, f"Approvals endpoint returns {len(approvals)} items without errors")
                else:
                    self.log_result("Frontend Integration - VehicleDetails", False, f"Approvals endpoint failed: {response.status_code}")
                    return False
            
            return True
            
        except Exception as e:
            self.log_result("Frontend Integration Safety", False, f"Exception: {str(e)}")
            return False

    def run_all_tests(self):
        """Run all tests in sequence"""
        print("🚀 Starting Electronic Signature and Approval System Tests")
        print("=" * 60)
        print()
        
        tests = [
            ("Create Vehicle and Approval Request", self.test_create_vehicle_and_approval),
            ("Submit Public Approval Response", self.test_public_approval_response),
            ("Verify Approval Response Data", self.test_get_approvals_with_response_data),
            ("Document Generator with Approval Info", self.test_document_generator_with_approval),
            ("Frontend Integration Safety", self.test_frontend_integration_safety)
        ]
        
        passed = 0
        total = len(tests)
        
        for test_name, test_func in tests:
            print(f"Running: {test_name}")
            print("-" * 40)
            if test_func():
                passed += 1
            print()
        
        print("=" * 60)
        print(f"📊 TEST SUMMARY: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 ALL TESTS PASSED! Electronic signature system is working correctly.")
        else:
            print("⚠️  Some tests failed. Check the details above.")
            
        print()
        print("📋 DETAILED RESULTS:")
        for result in self.results:
            print(f"  {result['status']} {result['test']}")
            if result['details']:
                for line in result['details'].split('\n'):
                    if line.strip():
                        print(f"    {line.strip()}")
        
        return passed == total

def main():
    """Main test execution"""
    tester = ApprovalSystemTester()
    success = tester.run_all_tests()
    
    if success:
        print("\n✅ Electronic signature and approval system is fully functional!")
    else:
        print("\n❌ Electronic signature system has issues that need to be addressed.")
    
    return success

if __name__ == "__main__":
    main()