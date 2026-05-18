#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
اختبار Backend للفاتورة بعد التعديلات
Backend Testing for Invoice After Modifications

Test Objective (Arabic):
اختبر Backend على preview domain (REACT_APP_BACKEND_URL) للفاتورة بعد التعديلات:

1) POST /api/documents/generate payload لفاتورة invoice مع workshop يحتوي commercialRegister + address + phone + document_number + date.
   - تحقق أن HTML يحتوي: 'بيانات الورشة' و 'السجل التجاري' و 'رقم الجوال' و 'عنوان الورشة' و 'رقم المستند'.
   - تحقق أنه لا يحتوي كلمات: 'ضريبة' أو 'رقم الضريبة' أو 'الرقم الضريبي' أو 'tax_' أو 'VAT'.

2) POST /api/documents/generate لنوع quote/diagnosis أيضا وتأكد أنه لا يعرض ضريبة.

ارجع لي نتائج pass/fail + لقطات مقتطفات من HTML حول بلوك الورشة + أي كلمات محظورة إن ظهرت.
"""

import requests
import json
import sys
from datetime import datetime
import re

# Backend URL from frontend .env
BACKEND_URL = "https://vehicle-accounting-2.preview.emergentagent.com/api"

class InvoiceBackendTester:
    def __init__(self):
        self.backend_url = BACKEND_URL
        self.results = []
        self.test_count = 0
        self.passed_count = 0
        
    def log_result(self, test_name, status, details, html_snippet="", forbidden_words=[]):
        """Log test result"""
        self.test_count += 1
        if status == "PASS":
            self.passed_count += 1
            
        result = {
            "test": test_name,
            "status": status,
            "details": details,
            "html_snippet": html_snippet,
            "forbidden_words": forbidden_words
        }
        self.results.append(result)
        
        # Print immediate result
        status_icon = "✅" if status == "PASS" else "❌"
        print(f"{status_icon} {test_name}: {status}")
        if details:
            print(f"   Details: {details}")
        if html_snippet:
            print(f"   HTML Snippet: {html_snippet[:200]}...")
        if forbidden_words:
            print(f"   ⚠️ Forbidden words found: {forbidden_words}")
        print()

    def extract_workshop_block(self, html_content):
        """Extract workshop details block from HTML"""
        # Look for the workshop section
        patterns = [
            r'<h3[^>]*>بيانات الورشة</h3>.*?</div>',
            r'بيانات الورشة.*?(?=<h3|</div>|</section>)',
            r'<div[^>]*workshop[^>]*>.*?</div>',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html_content, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(0)
        
        # If no specific block found, look for lines containing workshop info
        lines = html_content.split('\n')
        workshop_lines = []
        in_workshop_section = False
        
        for line in lines:
            if 'بيانات الورشة' in line:
                in_workshop_section = True
                workshop_lines.append(line)
            elif in_workshop_section:
                if any(term in line for term in ['السجل التجاري', 'رقم الجوال', 'عنوان الورشة', 'رقم المستند']):
                    workshop_lines.append(line)
                elif line.strip() and not any(term in line for term in ['السجل التجاري', 'رقم الجوال', 'عنوان الورشة']):
                    break
        
        return '\n'.join(workshop_lines) if workshop_lines else ""

    def check_required_fields(self, html_content):
        """Check if HTML contains required workshop fields"""
        required_fields = [
            'بيانات الورشة',
            'السجل التجاري', 
            'رقم الجوال',
            'عنوان الورشة',
            'رقم المستند'
        ]
        
        found_fields = []
        missing_fields = []
        
        for field in required_fields:
            if field in html_content:
                found_fields.append(field)
            else:
                missing_fields.append(field)
                
        return found_fields, missing_fields

    def check_forbidden_words(self, html_content):
        """Check for forbidden tax-related words (excluding base64 images)"""
        forbidden_words = [
            'ضريبة',
            'رقم الضريبة', 
            'الرقم الضريبي',
            'tax_',
            'VAT'
        ]
        
        found_forbidden = []
        
        # Split content into lines and exclude base64 image data
        lines = html_content.split('\n')
        text_content = []
        
        for line in lines:
            # Skip lines containing base64 image data
            if 'base64' not in line.lower():
                text_content.append(line)
        
        # Join back the non-base64 content
        clean_content = '\n'.join(text_content)
        
        for word in forbidden_words:
            if word in clean_content:
                found_forbidden.append(word)
                
        return found_forbidden

    def test_invoice_generation(self):
        """Test invoice generation with workshop details"""
        print("🧪 Testing Invoice Generation...")
        
        payload = {
            "doc_type": "invoice",
            "workshop": {
                "name": "ورشة عبدالله الكبير للصيانة",
                "name_en": "Abdullah Alkabeer Maintenance Workshop", 
                "address": "الرياض، حي الملز، شارع الأمير سلطان",
                "phone": "0553280100",
                "email": "info@alkabeer-workshop.sa",
                "website": "www.alkabeer-workshop.sa",
                "commercial_register": "1010123456",
                "commercialRegister": "1010123456"
            },
            "customer": {
                "name": "أحمد محمد العميل",
                "customerName": "أحمد محمد العميل",
                "phone": "0551234567",
                "customerPhone": "0551234567",
                "address": "الرياض، حي النرجس"
            },
            "vehicle": {
                "brand": "تويوتا",
                "model": "كامري",
                "year": "2022",
                "plateNumber": "أ ب ج 1234",
                "color": "أبيض",
                "mileage": "85000"
            },
            "items": [
                {
                    "description": "تغيير زيت المحرك",
                    "name": "تغيير زيت المحرك", 
                    "quantity": 1,
                    "qty": 1,
                    "unit_price": 150,
                    "price": 150
                },
                {
                    "description": "فلتر زيت أصلي",
                    "name": "فلتر زيت أصلي",
                    "quantity": 1, 
                    "qty": 1,
                    "unit_price": 45,
                    "price": 45
                },
                {
                    "description": "فحص شامل للمحرك",
                    "name": "فحص شامل للمحرك",
                    "quantity": 1,
                    "qty": 1, 
                    "unit_price": 200,
                    "price": 200
                }
            ],
            "settings": {
                "theme": "أزرق",
                "style": "حديث",
                "tax_rate": 0,
                "document_number": f"INV-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "validity_days": 30,
                "terms": [
                    "الأسعار بالريال السعودي",
                    "يرجى التحقق من البنود قبل مغادرة الورشة", 
                    "ضمان الإصلاح حسب نوع الخدمة",
                    "لا يتم استرداد المبلغ بعد الخروج"
                ]
            }
        }
        
        try:
            response = requests.post(
                f"{self.backend_url}/documents/generate",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code != 200:
                self.log_result(
                    "Invoice Generation API Call",
                    "FAIL", 
                    f"HTTP {response.status_code}: {response.text[:200]}"
                )
                return None
                
            data = response.json()
            
            if not data.get("success"):
                self.log_result(
                    "Invoice Generation Success",
                    "FAIL",
                    f"API returned success=false: {data}"
                )
                return None
                
            html_content = data.get("html", "")
            
            if not html_content:
                self.log_result(
                    "Invoice HTML Content",
                    "FAIL", 
                    "No HTML content returned"
                )
                return None
                
            self.log_result(
                "Invoice Generation API Call",
                "PASS",
                f"Successfully generated invoice {data.get('document_number', 'N/A')}"
            )
            
            return html_content
            
        except requests.exceptions.RequestException as e:
            self.log_result(
                "Invoice Generation API Call",
                "FAIL",
                f"Request failed: {str(e)}"
            )
            return None
        except Exception as e:
            self.log_result(
                "Invoice Generation API Call", 
                "FAIL",
                f"Unexpected error: {str(e)}"
            )
            return None

    def test_quote_generation(self):
        """Test quote generation (should not show tax)"""
        print("🧪 Testing Quote Generation...")
        
        payload = {
            "doc_type": "quote",
            "workshop": {
                "name": "ورشة عبدالله الكبير للصيانة",
                "address": "الرياض، حي الملز، شارع الأمير سلطان",
                "phone": "0553280100", 
                "commercial_register": "1010123456"
            },
            "customer": {
                "name": "سعد أحمد العميل",
                "phone": "0559876543"
            },
            "vehicle": {
                "brand": "هوندا",
                "model": "أكورد", 
                "year": "2021",
                "plateNumber": "د هـ و 5678"
            },
            "items": [
                {
                    "description": "إصلاح نظام التكييف",
                    "quantity": 1,
                    "unit_price": 350
                },
                {
                    "description": "تنظيف فلاتر الهواء",
                    "quantity": 2,
                    "unit_price": 75
                }
            ],
            "settings": {
                "theme": "أخضر",
                "tax_rate": 0
            }
        }
        
        try:
            response = requests.post(
                f"{self.backend_url}/documents/generate",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code != 200:
                self.log_result(
                    "Quote Generation API Call",
                    "FAIL",
                    f"HTTP {response.status_code}: {response.text[:200]}"
                )
                return None
                
            data = response.json()
            html_content = data.get("html", "")
            
            self.log_result(
                "Quote Generation API Call", 
                "PASS",
                f"Successfully generated quote {data.get('document_number', 'N/A')}"
            )
            
            return html_content
            
        except Exception as e:
            self.log_result(
                "Quote Generation API Call",
                "FAIL", 
                f"Error: {str(e)}"
            )
            return None

    def test_diagnosis_generation(self):
        """Test diagnosis generation (should not show tax)"""
        print("🧪 Testing Diagnosis Generation...")
        
        payload = {
            "doc_type": "diagnosis",
            "workshop": {
                "name": "ورشة عبدالله الكبير للصيانة",
                "address": "الرياض، حي الملز، شارع الأمير سلطان", 
                "phone": "0553280100",
                "commercial_register": "1010123456"
            },
            "customer": {
                "name": "فهد سالم العميل",
                "phone": "0557654321"
            },
            "vehicle": {
                "brand": "نيسان",
                "model": "التيما",
                "year": "2020", 
                "plateNumber": "ز ح ط 9012"
            },
            "items": [
                {
                    "description": "فحص نظام الفرامل",
                    "quantity": 1,
                    "unit_price": 120
                },
                {
                    "description": "فحص نظام التعليق",
                    "quantity": 1,
                    "unit_price": 100
                }
            ],
            "settings": {
                "theme": "بنفسجي",
                "tax_rate": 0
            }
        }
        
        try:
            response = requests.post(
                f"{self.backend_url}/documents/generate",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code != 200:
                self.log_result(
                    "Diagnosis Generation API Call",
                    "FAIL",
                    f"HTTP {response.status_code}: {response.text[:200]}"
                )
                return None
                
            data = response.json()
            html_content = data.get("html", "")
            
            self.log_result(
                "Diagnosis Generation API Call",
                "PASS", 
                f"Successfully generated diagnosis {data.get('document_number', 'N/A')}"
            )
            
            return html_content
            
        except Exception as e:
            self.log_result(
                "Diagnosis Generation API Call",
                "FAIL",
                f"Error: {str(e)}"
            )
            return None

    def analyze_html_content(self, html_content, doc_type):
        """Analyze HTML content for required and forbidden elements"""
        print(f"🔍 Analyzing {doc_type.upper()} HTML Content...")
        
        # Check required fields
        found_fields, missing_fields = self.check_required_fields(html_content)
        
        if missing_fields:
            self.log_result(
                f"{doc_type.title()} Required Fields Check",
                "FAIL",
                f"Missing fields: {missing_fields}. Found: {found_fields}"
            )
        else:
            self.log_result(
                f"{doc_type.title()} Required Fields Check", 
                "PASS",
                f"All required fields found: {found_fields}"
            )
        
        # Check forbidden words
        forbidden_words = self.check_forbidden_words(html_content)
        
        if forbidden_words:
            self.log_result(
                f"{doc_type.title()} Forbidden Words Check",
                "FAIL",
                f"Found forbidden tax-related words: {forbidden_words}",
                forbidden_words=forbidden_words
            )
        else:
            self.log_result(
                f"{doc_type.title()} Forbidden Words Check",
                "PASS", 
                "No forbidden tax-related words found"
            )
        
        # Extract workshop block
        workshop_block = self.extract_workshop_block(html_content)
        
        if workshop_block:
            self.log_result(
                f"{doc_type.title()} Workshop Block Extraction",
                "PASS",
                "Workshop block found and extracted",
                html_snippet=workshop_block
            )
        else:
            self.log_result(
                f"{doc_type.title()} Workshop Block Extraction", 
                "FAIL",
                "Could not extract workshop block from HTML"
            )
        
        return {
            "found_fields": found_fields,
            "missing_fields": missing_fields,
            "forbidden_words": forbidden_words,
            "workshop_block": workshop_block
        }

    def run_all_tests(self):
        """Run all backend tests"""
        print("🚀 Starting Backend Invoice Testing...")
        print(f"Backend URL: {self.backend_url}")
        print("=" * 60)
        
        # Test 1: Invoice Generation
        invoice_html = self.test_invoice_generation()
        if invoice_html:
            self.analyze_html_content(invoice_html, "invoice")
        
        print("-" * 40)
        
        # Test 2: Quote Generation  
        quote_html = self.test_quote_generation()
        if quote_html:
            self.analyze_html_content(quote_html, "quote")
        
        print("-" * 40)
        
        # Test 3: Diagnosis Generation
        diagnosis_html = self.test_diagnosis_generation()
        if diagnosis_html:
            self.analyze_html_content(diagnosis_html, "diagnosis")
        
        print("=" * 60)
        self.print_summary()

    def print_summary(self):
        """Print test summary"""
        print("📊 TEST SUMMARY")
        print("=" * 60)
        
        print(f"Total Tests: {self.test_count}")
        print(f"Passed: {self.passed_count}")
        print(f"Failed: {self.test_count - self.passed_count}")
        print(f"Success Rate: {(self.passed_count/self.test_count*100):.1f}%" if self.test_count > 0 else "0%")
        
        print("\n📋 DETAILED RESULTS:")
        print("-" * 60)
        
        for result in self.results:
            status_icon = "✅" if result["status"] == "PASS" else "❌"
            print(f"{status_icon} {result['test']}: {result['status']}")
            
            if result["details"]:
                print(f"   📝 {result['details']}")
                
            if result["html_snippet"]:
                print(f"   🔍 HTML Snippet:")
                # Show first few lines of HTML snippet
                lines = result["html_snippet"].split('\n')[:3]
                for line in lines:
                    if line.strip():
                        print(f"      {line.strip()[:100]}...")
                        
            if result["forbidden_words"]:
                print(f"   ⚠️ Forbidden Words: {result['forbidden_words']}")
                
            print()
        
        # Overall result
        if self.passed_count == self.test_count:
            print("🎉 ALL TESTS PASSED! Invoice backend is working correctly.")
        else:
            failed_count = self.test_count - self.passed_count
            print(f"⚠️ {failed_count} TEST(S) FAILED. Please review the issues above.")
        
        print("=" * 60)

def main():
    """Main test execution"""
    tester = InvoiceBackendTester()
    
    try:
        tester.run_all_tests()
    except KeyboardInterrupt:
        print("\n⏹️ Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error during testing: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()