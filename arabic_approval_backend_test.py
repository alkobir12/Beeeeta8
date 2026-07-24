#!/usr/bin/env python3
"""
Arabic Approval Backend Testing
Testing specific requirements from Arabic review request:

1) POST /api/documents/generate (invoice) مع settings تحتوي approval_token/approval_info/approval_vehicle_id
2) تأكد أن HTML لا يحتوي 'موافقة العميل' ولا 'QR' ولا 'barcode' ولا 'token'
3) تأكد أن صناديق بيانات العميل/الورشة أصغر (تحقق من وجود padding الجديد 0.6rem 0.7rem و font-size 0.7rem إن أمكن في HTML)

Backend URL: https://stamp-approval-flow.preview.emergentagent.com/api
"""

import requests
import json
import sys
import re
from datetime import datetime
import traceback

class ArabicApprovalBackendTester:
    def __init__(self):
        self.base_url = "https://stamp-approval-flow.preview.emergentagent.com"
        self.api_url = f"{self.base_url}/api"
        self.results = []
        self.session = requests.Session()
        
        # Set headers for all requests
        self.session.headers.update({
            'User-Agent': 'Arabic-Approval-Tester/1.0',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
    
    def log_result(self, test_name, success, status_code=None, response_data=None, error=None, details=None, html_snippet=None):
        """Log test result with HTML snippet support"""
        result = {
            'test': test_name,
            'success': success,
            'timestamp': datetime.now().isoformat(),
            'status_code': status_code,
            'error': str(error) if error else None,
            'details': details,
            'html_snippet': html_snippet
        }
        
        if response_data and isinstance(response_data, dict):
            result['response_keys'] = list(response_data.keys())
            result['response_size'] = len(str(response_data))
        
        self.results.append(result)
        
        # Print immediate feedback
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if status_code:
            print(f"    Status: {status_code}")
        if error:
            print(f"    Error: {error}")
        if details:
            print(f"    Details: {details}")
        if html_snippet:
            print(f"    HTML Snippet: {html_snippet[:200]}...")
        print()
    
    def test_invoice_generation_with_approval_settings(self):
        """Test 1: POST /api/documents/generate (invoice) with approval settings"""
        try:
            # Prepare invoice generation payload with approval settings
            payload = {
                "doc_type": "invoice",
                "customer": {
                    "name": "أحمد محمد العميل",
                    "phone": "0551234567",
                    "email": "ahmed@example.com"
                },
                "vehicle": {
                    "plateNumber": "ت س ت 1234",
                    "brand": "تويوتا",
                    "model": "كامري",
                    "year": 2024
                },
                "workshop": {
                    "name": "ورشة الاختبار",
                    "commercialRegister": "1010123456",
                    "phone": "0553280100",
                    "address": "الرياض، المملكة العربية السعودية"
                },
                "items": [
                    {
                        "name": "خدمة صيانة شاملة",
                        "description": "خدمة صيانة شاملة",
                        "quantity": 1,
                        "price": 500,
                        "unit_price": 500
                    },
                    {
                        "name": "قطعة غيار أصلية",
                        "description": "قطعة غيار أصلية",
                        "quantity": 2,
                        "price": 150,
                        "unit_price": 150
                    }
                ],
                "settings": {
                    "approval_token": "APV-TEST-2026-001",
                    "approval_info": {
                        "token": "APV-TEST-2026-001",
                        "status": "approved",
                        "responderName": "أحمد محمد العميل",
                        "responderPhone": "0551234567",
                        "respondedAt": "2026-02-08T10:30:00Z",
                        "clientIp": "192.168.1.100",
                        "userAgent": "Mozilla/5.0 Test Browser"
                    },
                    "approval_vehicle_id": "f3422cc1-dd9c-4e69-8205-0aa50b3795a1",
                    "document_number": "INV-TEST-20260208",
                    "date": "2026-02-08"
                }
            }
            
            response = self.session.post(
                f"{self.api_url}/documents/generate", 
                json=payload, 
                timeout=30
            )
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    
                    if data.get('success') and 'html' in data:
                        html_content = data['html']
                        
                        # Extract a sample of the HTML for logging
                        html_sample = html_content[:500] if len(html_content) > 500 else html_content
                        
                        self.log_result(
                            "POST /api/documents/generate (invoice with approval settings)", 
                            True, 
                            response.status_code, 
                            data,
                            details=f"Invoice generated successfully with approval settings. HTML length: {len(html_content)} chars",
                            html_snippet=html_sample
                        )
                        
                        # Store HTML for further analysis
                        self.generated_html = html_content
                        return True
                        
                    else:
                        self.log_result(
                            "POST /api/documents/generate (invoice with approval settings)", 
                            False, 
                            response.status_code,
                            data,
                            error="Response missing 'success' or 'html' field"
                        )
                        return False
                        
                except json.JSONDecodeError:
                    self.log_result(
                        "POST /api/documents/generate (invoice with approval settings)", 
                        False, 
                        response.status_code,
                        error="Response is not valid JSON"
                    )
                    return False
            else:
                self.log_result(
                    "POST /api/documents/generate (invoice with approval settings)", 
                    False, 
                    response.status_code,
                    error=f"Expected 200, got {response.status_code}. Response: {response.text[:200]}"
                )
                return False
                
        except Exception as e:
            self.log_result(
                "POST /api/documents/generate (invoice with approval settings)", 
                False, 
                error=e
            )
            return False
    
    def test_html_forbidden_content(self):
        """Test 2: Verify HTML doesn't contain forbidden words"""
        if not hasattr(self, 'generated_html'):
            self.log_result(
                "HTML Forbidden Content Check", 
                False,
                error="No HTML available for testing (previous test failed)"
            )
            return False
        
        html = self.generated_html
        forbidden_words = ['موافقة العميل', 'QR', 'barcode', 'token']
        found_forbidden = []
        
        for word in forbidden_words:
            # Case-insensitive search for English words, exact match for Arabic
            if word in ['QR', 'barcode', 'token']:
                pattern = re.compile(re.escape(word), re.IGNORECASE)
            else:
                pattern = re.compile(re.escape(word))
            
            matches = pattern.findall(html)
            if matches:
                found_forbidden.append({
                    'word': word,
                    'count': len(matches),
                    'matches': matches[:3]  # First 3 matches for reference
                })
        
        if found_forbidden:
            error_details = "; ".join([f"'{item['word']}' found {item['count']} times" for item in found_forbidden])
            
            # Extract context around first forbidden word for snippet
            first_forbidden = found_forbidden[0]
            word_pos = html.find(first_forbidden['matches'][0])
            context_start = max(0, word_pos - 100)
            context_end = min(len(html), word_pos + 100)
            context_snippet = html[context_start:context_end]
            
            self.log_result(
                "HTML Forbidden Content Check", 
                False,
                error=f"Found forbidden content: {error_details}",
                details=f"Total forbidden words found: {len(found_forbidden)}",
                html_snippet=context_snippet
            )
            return False
        else:
            # Show a sample of the HTML to confirm it was checked
            html_sample = html[:300] if len(html) > 300 else html
            
            self.log_result(
                "HTML Forbidden Content Check", 
                True,
                details=f"No forbidden words found. Checked: {', '.join(forbidden_words)}. HTML length: {len(html)} chars",
                html_snippet=html_sample
            )
            return True
    
    def test_html_styling_improvements(self):
        """Test 3: Check for smaller customer/workshop data boxes with new styling"""
        if not hasattr(self, 'generated_html'):
            self.log_result(
                "HTML Styling Improvements Check", 
                False,
                error="No HTML available for testing (previous test failed)"
            )
            return False
        
        html = self.generated_html
        styling_checks = {
            'padding_0_6_0_7': False,
            'font_size_0_7': False,
            'customer_workshop_boxes': False
        }
        
        found_snippets = []
        
        # Check for new padding: 0.6rem 0.7rem
        padding_patterns = [
            r'padding:\s*0\.6rem\s+0\.7rem',
            r'padding:\s*0\.6rem\s*0\.7rem',
            r'padding-top:\s*0\.6rem.*padding-left:\s*0\.7rem',
            r'padding-bottom:\s*0\.6rem.*padding-right:\s*0\.7rem'
        ]
        
        for pattern in padding_patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            if matches:
                styling_checks['padding_0_6_0_7'] = True
                found_snippets.append(f"Padding found: {matches[0]}")
                break
        
        # Check for font-size: 0.7rem
        font_size_patterns = [
            r'font-size:\s*0\.7rem',
            r'font-size:\s*\.7rem'
        ]
        
        for pattern in font_size_patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            if matches:
                styling_checks['font_size_0_7'] = True
                found_snippets.append(f"Font-size found: {matches[0]}")
                break
        
        # Check for customer/workshop data sections
        customer_workshop_patterns = [
            r'بيانات\s*العميل',
            r'بيانات\s*الورشة',
            r'customer.*data',
            r'workshop.*data'
        ]
        
        for pattern in customer_workshop_patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            if matches:
                styling_checks['customer_workshop_boxes'] = True
                found_snippets.append(f"Customer/Workshop section found: {matches[0]}")
                break
        
        # Determine overall success
        improvements_found = sum(styling_checks.values())
        total_checks = len(styling_checks)
        
        if improvements_found >= 2:  # At least 2 out of 3 improvements found
            self.log_result(
                "HTML Styling Improvements Check", 
                True,
                details=f"Found {improvements_found}/{total_checks} styling improvements: {found_snippets}",
                html_snippet="; ".join(found_snippets)
            )
            return True
        else:
            # Extract a sample around styling areas for analysis
            style_pos = html.find('<style>')
            if style_pos != -1:
                style_end = html.find('</style>', style_pos)
                if style_end != -1:
                    style_content = html[style_pos:style_end + 8]
                    style_sample = style_content[:500] if len(style_content) > 500 else style_content
                else:
                    style_sample = html[style_pos:style_pos + 500]
            else:
                style_sample = "No <style> section found"
            
            self.log_result(
                "HTML Styling Improvements Check", 
                False,
                error=f"Only found {improvements_found}/{total_checks} expected styling improvements",
                details=f"Missing improvements: {[k for k, v in styling_checks.items() if not v]}",
                html_snippet=style_sample
            )
            return False
    
    def run_all_tests(self):
        """Run all Arabic approval tests"""
        print("🚀 Starting Arabic Approval Backend Tests")
        print("=" * 60)
        print(f"Backend URL: {self.api_url}")
        print("=" * 60)
        
        # Test 1: Invoice generation with approval settings
        test1_success = self.test_invoice_generation_with_approval_settings()
        
        # Test 2: HTML forbidden content check
        test2_success = self.test_html_forbidden_content()
        
        # Test 3: HTML styling improvements check
        test3_success = self.test_html_styling_improvements()
        
        # Generate summary
        self.generate_summary()
        
        return test1_success and test2_success and test3_success
    
    def generate_summary(self):
        """Generate test summary with HTML snippets"""
        print("=" * 60)
        print("📊 ARABIC APPROVAL TEST RESULTS")
        print("=" * 60)
        
        total_tests = len(self.results)
        passed_tests = len([r for r in self.results if r['success']])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        print()
        
        # Show detailed results
        for result in self.results:
            status = "✅ PASS" if result['success'] else "❌ FAIL"
            print(f"{status} {result['test']}")
            
            if result['details']:
                print(f"    Details: {result['details']}")
            
            if result['error']:
                print(f"    Error: {result['error']}")
            
            if result['html_snippet']:
                print(f"    HTML Snippet: {result['html_snippet'][:150]}...")
            
            print()
        
        print("🎯 ARABIC APPROVAL TESTING COMPLETE")
        
        # Save detailed results to file
        try:
            with open('/app/arabic_approval_test_results.json', 'w', encoding='utf-8') as f:
                json.dump(self.results, f, ensure_ascii=False, indent=2)
            print("📄 Detailed results saved to: /app/arabic_approval_test_results.json")
        except Exception as e:
            print(f"⚠️ Could not save results file: {e}")

def main():
    """Main test execution"""
    try:
        tester = ArabicApprovalBackendTester()
        success = tester.run_all_tests()
        
        # Return appropriate exit code
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n⚠️ Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"💥 Critical error during testing: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()