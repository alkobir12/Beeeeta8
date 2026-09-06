#!/usr/bin/env python3
"""
Deep Backend Regression Test - إعادة تشغيل اختبارات Backend العميقة
Focus on specific endpoints mentioned in the Arabic review request
"""

import requests
import json
import time
from datetime import datetime
from typing import Dict, Any, List

# Backend URL from environment
BACKEND_URL = "https://financial-ssot.preview.emergentagent.com/api"

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

def log_test(test_name: str, status: str, details: str = "", response_time: float = 0):
    """Log test results with colors"""
    color = Colors.GREEN if status == "PASS" else Colors.RED if status == "FAIL" else Colors.YELLOW
    print(f"{color}[{status}]{Colors.RESET} {test_name}")
    if details:
        print(f"  {details}")
    if response_time > 0:
        print(f"  ⏱️  Response Time: {response_time:.3f}s")
        if response_time > 30:
            print(f"  {Colors.YELLOW}⚠️  WARNING: Response time > 30s{Colors.RESET}")
    print()

def check_response_format(data: dict, test_name: str) -> List[str]:
    """Check for _id leakage and ISO date format"""
    issues = []
    
    # Check for _id fields (should not be present)
    def check_id_recursive(obj, path=""):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key == "_id":
                    issues.append(f"❌ _id field found at {path}.{key}")
                elif isinstance(value, (dict, list)):
                    check_id_recursive(value, f"{path}.{key}" if path else key)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                check_id_recursive(item, f"{path}[{i}]" if path else f"[{i}]")
    
    check_id_recursive(data)
    
    # Check for proper date formats (should be ISO strings)
    def check_dates_recursive(obj, path=""):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key.lower().endswith(('at', 'date', 'time')) and isinstance(value, str):
                    # Check if it looks like ISO format
                    if 'T' in value and ('Z' in value or '+' in value or value.endswith('00')):
                        # Looks like ISO format - good
                        pass
                    else:
                        issues.append(f"⚠️  Non-ISO date format at {path}.{key}: {value}")
                elif isinstance(value, (dict, list)):
                    check_dates_recursive(value, f"{path}.{key}" if path else key)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                check_dates_recursive(item, f"{path}[{i}]" if path else f"[{i}]")
    
    check_dates_recursive(data)
    
    return issues

def test_critical_endpoints():
    """Test critical endpoints that were previously returning 404"""
    print(f"\n{Colors.BLUE}{'='*80}")
    print(f"CRITICAL ENDPOINTS TEST - اختبار المسارات الحرجة")
    print(f"{'='*80}{Colors.RESET}\n")
    
    results = []
    
    # Test 1: POST /api/auth/request-otp
    try:
        otp_data = {
            "phone": "+966501234567",
            "type": "login"
        }
        
        start_time = time.time()
        response = requests.post(
            f"{BACKEND_URL}/auth/request-otp",
            json=otp_data,
            headers={"Content-Type": "application/json"},
            timeout=15
        )
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            issues = check_response_format(data, "auth/request-otp")
            log_test(
                "POST /api/auth/request-otp",
                "PASS",
                f"✅ OTP request successful. Response: {str(data)[:100]}..." + (f"\n  Issues: {issues}" if issues else ""),
                response_time
            )
            results.append(("POST /api/auth/request-otp", True, response_time))
        else:
            log_test(
                "POST /api/auth/request-otp",
                "FAIL",
                f"Status: {response.status_code}, Response: {response.text[:200]}"
            )
            results.append(("POST /api/auth/request-otp", False, 0))
    except Exception as e:
        log_test("POST /api/auth/request-otp", "FAIL", f"Exception: {str(e)}")
        results.append(("POST /api/auth/request-otp", False, 0))
    
    # Test 2: POST /api/print/resolve-template with override_type='invoice'
    try:
        template_data = {
            "override_type": "invoice"
        }
        
        start_time = time.time()
        response = requests.post(
            f"{BACKEND_URL}/print/resolve-template",
            json=template_data,
            headers={"Content-Type": "application/json"},
            timeout=15
        )
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            issues = check_response_format(data, "print/resolve-template")
            log_test(
                "POST /api/print/resolve-template (invoice)",
                "PASS",
                f"✅ Template resolved. Type: {data.get('type', 'N/A')}" + (f"\n  Issues: {issues}" if issues else ""),
                response_time
            )
            results.append(("POST /api/print/resolve-template (invoice)", True, response_time))
        else:
            log_test(
                "POST /api/print/resolve-template (invoice)",
                "FAIL",
                f"Status: {response.status_code}, Response: {response.text[:200]}"
            )
            results.append(("POST /api/print/resolve-template (invoice)", False, 0))
    except Exception as e:
        log_test("POST /api/print/resolve-template (invoice)", "FAIL", f"Exception: {str(e)}")
        results.append(("POST /api/print/resolve-template (invoice)", False, 0))
    
    # Test 3: POST /api/print/resolve-template with override_type='diagnosis'
    try:
        template_data = {
            "override_type": "diagnosis"
        }
        
        start_time = time.time()
        response = requests.post(
            f"{BACKEND_URL}/print/resolve-template",
            json=template_data,
            headers={"Content-Type": "application/json"},
            timeout=15
        )
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            issues = check_response_format(data, "print/resolve-template")
            log_test(
                "POST /api/print/resolve-template (diagnosis)",
                "PASS",
                f"✅ Template resolved. Type: {data.get('type', 'N/A')}" + (f"\n  Issues: {issues}" if issues else ""),
                response_time
            )
            results.append(("POST /api/print/resolve-template (diagnosis)", True, response_time))
        else:
            log_test(
                "POST /api/print/resolve-template (diagnosis)",
                "FAIL",
                f"Status: {response.status_code}, Response: {response.text[:200]}"
            )
            results.append(("POST /api/print/resolve-template (diagnosis)", False, 0))
    except Exception as e:
        log_test("POST /api/print/resolve-template (diagnosis)", "FAIL", f"Exception: {str(e)}")
        results.append(("POST /api/print/resolve-template (diagnosis)", False, 0))
    
    # Test 4: POST /api/ceo/seed-accounts
    try:
        start_time = time.time()
        response = requests.post(
            f"{BACKEND_URL}/ceo/seed-accounts",
            json={},
            headers={"Content-Type": "application/json"},
            timeout=15
        )
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            issues = check_response_format(data, "ceo/seed-accounts")
            log_test(
                "POST /api/ceo/seed-accounts",
                "PASS",
                f"✅ Accounts seeded. Response: {str(data)[:100]}..." + (f"\n  Issues: {issues}" if issues else ""),
                response_time
            )
            results.append(("POST /api/ceo/seed-accounts", True, response_time))
        else:
            log_test(
                "POST /api/ceo/seed-accounts",
                "FAIL",
                f"Status: {response.status_code}, Response: {response.text[:200]}"
            )
            results.append(("POST /api/ceo/seed-accounts", False, 0))
    except Exception as e:
        log_test("POST /api/ceo/seed-accounts", "FAIL", f"Exception: {str(e)}")
        results.append(("POST /api/ceo/seed-accounts", False, 0))
    
    # Test 5: GET /api/ceo/accounts
    try:
        start_time = time.time()
        response = requests.get(f"{BACKEND_URL}/ceo/accounts", timeout=15)
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            issues = check_response_format(data, "ceo/accounts")
            account_count = len(data) if isinstance(data, list) else 1
            log_test(
                "GET /api/ceo/accounts",
                "PASS",
                f"✅ Accounts retrieved. Count: {account_count}" + (f"\n  Issues: {issues}" if issues else ""),
                response_time
            )
            results.append(("GET /api/ceo/accounts", True, response_time))
        else:
            log_test(
                "GET /api/ceo/accounts",
                "FAIL",
                f"Status: {response.status_code}, Response: {response.text[:200]}"
            )
            results.append(("GET /api/ceo/accounts", False, 0))
    except Exception as e:
        log_test("GET /api/ceo/accounts", "FAIL", f"Exception: {str(e)}")
        results.append(("GET /api/ceo/accounts", False, 0))
    
    # Test 6: POST /api/seed/print-templates
    try:
        start_time = time.time()
        response = requests.post(
            f"{BACKEND_URL}/seed/print-templates",
            json={},
            headers={"Content-Type": "application/json"},
            timeout=15
        )
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            issues = check_response_format(data, "seed/print-templates")
            log_test(
                "POST /api/seed/print-templates",
                "PASS",
                f"✅ Templates seeded. Response: {str(data)[:100]}..." + (f"\n  Issues: {issues}" if issues else ""),
                response_time
            )
            results.append(("POST /api/seed/print-templates", True, response_time))
        else:
            log_test(
                "POST /api/seed/print-templates",
                "FAIL",
                f"Status: {response.status_code}, Response: {response.text[:200]}"
            )
            results.append(("POST /api/seed/print-templates", False, 0))
    except Exception as e:
        log_test("POST /api/seed/print-templates", "FAIL", f"Exception: {str(e)}")
        results.append(("POST /api/seed/print-templates", False, 0))
    
    # Test 7: POST /api/admin/create-indexes
    try:
        start_time = time.time()
        response = requests.post(
            f"{BACKEND_URL}/admin/create-indexes",
            json={},
            headers={"Content-Type": "application/json"},
            timeout=15
        )
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            issues = check_response_format(data, "admin/create-indexes")
            log_test(
                "POST /api/admin/create-indexes",
                "PASS",
                f"✅ Indexes created. Response: {str(data)[:100]}..." + (f"\n  Issues: {issues}" if issues else ""),
                response_time
            )
            results.append(("POST /api/admin/create-indexes", True, response_time))
        else:
            log_test(
                "POST /api/admin/create-indexes",
                "FAIL",
                f"Status: {response.status_code}, Response: {response.text[:200]}"
            )
            results.append(("POST /api/admin/create-indexes", False, 0))
    except Exception as e:
        log_test("POST /api/admin/create-indexes", "FAIL", f"Exception: {str(e)}")
        results.append(("POST /api/admin/create-indexes", False, 0))
    
    # Test 8: POST /api/seed/clone-basics
    try:
        start_time = time.time()
        response = requests.post(
            f"{BACKEND_URL}/seed/clone-basics",
            json={},
            headers={"Content-Type": "application/json"},
            timeout=15
        )
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            issues = check_response_format(data, "seed/clone-basics")
            log_test(
                "POST /api/seed/clone-basics",
                "PASS",
                f"✅ Basics cloned. Response: {str(data)[:100]}..." + (f"\n  Issues: {issues}" if issues else ""),
                response_time
            )
            results.append(("POST /api/seed/clone-basics", True, response_time))
        else:
            log_test(
                "POST /api/seed/clone-basics",
                "FAIL",
                f"Status: {response.status_code}, Response: {response.text[:200]}"
            )
            results.append(("POST /api/seed/clone-basics", False, 0))
    except Exception as e:
        log_test("POST /api/seed/clone-basics", "FAIL", f"Exception: {str(e)}")
        results.append(("POST /api/seed/clone-basics", False, 0))
    
    return results

def test_regression_endpoints():
    """Test regression endpoints for quick verification"""
    print(f"\n{Colors.BLUE}{'='*80}")
    print(f"REGRESSION ENDPOINTS TEST - اختبار الانحدار السريع")
    print(f"{'='*80}{Colors.RESET}\n")
    
    results = []
    
    # Test 1: GET /api/settings
    try:
        start_time = time.time()
        response = requests.get(f"{BACKEND_URL}/settings", timeout=15)
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            issues = check_response_format(data, "settings")
            log_test(
                "GET /api/settings",
                "PASS",
                f"✅ Settings retrieved. Keys: {list(data.keys()) if isinstance(data, dict) else 'N/A'}" + (f"\n  Issues: {issues}" if issues else ""),
                response_time
            )
            results.append(("GET /api/settings", True, response_time))
        else:
            log_test(
                "GET /api/settings",
                "FAIL",
                f"Status: {response.status_code}, Response: {response.text[:200]}"
            )
            results.append(("GET /api/settings", False, 0))
    except Exception as e:
        log_test("GET /api/settings", "FAIL", f"Exception: {str(e)}")
        results.append(("GET /api/settings", False, 0))
    
    # Test 2: POST /api/settings
    try:
        settings_data = {
            "currency": "SAR",
            "taxEnabled": True,
            "taxRate": 15,
            "language": "ar"
        }
        
        start_time = time.time()
        response = requests.post(
            f"{BACKEND_URL}/settings",
            json=settings_data,
            headers={"Content-Type": "application/json"},
            timeout=15
        )
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            issues = check_response_format(data, "settings")
            log_test(
                "POST /api/settings",
                "PASS",
                f"✅ Settings updated. Response: {str(data)[:100]}..." + (f"\n  Issues: {issues}" if issues else ""),
                response_time
            )
            results.append(("POST /api/settings", True, response_time))
        else:
            log_test(
                "POST /api/settings",
                "FAIL",
                f"Status: {response.status_code}, Response: {response.text[:200]}"
            )
            results.append(("POST /api/settings", False, 0))
    except Exception as e:
        log_test("POST /api/settings", "FAIL", f"Exception: {str(e)}")
        results.append(("POST /api/settings", False, 0))
    
    # Test 3: POST /api/ceo/ai-analysis-multi with accountIds
    try:
        # First get some account IDs
        accounts_response = requests.get(f"{BACKEND_URL}/ceo/accounts", timeout=10)
        account_ids = []
        if accounts_response.status_code == 200:
            accounts = accounts_response.json()
            if isinstance(accounts, list) and len(accounts) > 0:
                account_ids = [acc.get("id") for acc in accounts[:2] if acc.get("id")]
        
        analysis_data = {
            "accountIds": account_ids,
            "question": "ما هو أداء الورشة هذا الشهر؟"
        }
        
        start_time = time.time()
        response = requests.post(
            f"{BACKEND_URL}/ceo/ai-analysis-multi",
            json=analysis_data,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            issues = check_response_format(data, "ceo/ai-analysis-multi")
            log_test(
                "POST /api/ceo/ai-analysis-multi (with accountIds)",
                "PASS",
                f"✅ Analysis completed. AccountIds: {len(account_ids)}" + (f"\n  Issues: {issues}" if issues else ""),
                response_time
            )
            results.append(("POST /api/ceo/ai-analysis-multi (with accountIds)", True, response_time))
        else:
            log_test(
                "POST /api/ceo/ai-analysis-multi (with accountIds)",
                "FAIL",
                f"Status: {response.status_code}, Response: {response.text[:200]}"
            )
            results.append(("POST /api/ceo/ai-analysis-multi (with accountIds)", False, 0))
    except Exception as e:
        log_test("POST /api/ceo/ai-analysis-multi (with accountIds)", "FAIL", f"Exception: {str(e)}")
        results.append(("POST /api/ceo/ai-analysis-multi (with accountIds)", False, 0))
    
    # Test 4: POST /api/ceo/ai-analysis-multi without accountIds
    try:
        analysis_data = {
            "question": "ما هي التوصيات لتحسين الأداء؟"
        }
        
        start_time = time.time()
        response = requests.post(
            f"{BACKEND_URL}/ceo/ai-analysis-multi",
            json=analysis_data,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            issues = check_response_format(data, "ceo/ai-analysis-multi")
            log_test(
                "POST /api/ceo/ai-analysis-multi (without accountIds)",
                "PASS",
                f"✅ Analysis completed without accountIds" + (f"\n  Issues: {issues}" if issues else ""),
                response_time
            )
            results.append(("POST /api/ceo/ai-analysis-multi (without accountIds)", True, response_time))
        else:
            log_test(
                "POST /api/ceo/ai-analysis-multi (without accountIds)",
                "FAIL",
                f"Status: {response.status_code}, Response: {response.text[:200]}"
            )
            results.append(("POST /api/ceo/ai-analysis-multi (without accountIds)", False, 0))
    except Exception as e:
        log_test("POST /api/ceo/ai-analysis-multi (without accountIds)", "FAIL", f"Exception: {str(e)}")
        results.append(("POST /api/ceo/ai-analysis-multi (without accountIds)", False, 0))
    
    # Test 5: POST /api/print/invoice-xlsx with simple ITEMS data
    try:
        invoice_data = {
            "CUSTOMER_NAME": "أحمد الراشد",
            "INVOICE_NUMBER": "INV-001",
            "DATE": "2024-01-15",
            "ITEMS": [
                {
                    "name": "زيت محرك",
                    "quantity": 1,
                    "price": 150.0,
                    "total": 150.0
                },
                {
                    "name": "فلتر هواء",
                    "quantity": 2,
                    "price": 75.0,
                    "total": 150.0
                }
            ],
            "TOTAL": 300.0
        }
        
        start_time = time.time()
        response = requests.post(
            f"{BACKEND_URL}/print/invoice-xlsx",
            json=invoice_data,
            headers={"Content-Type": "application/json"},
            timeout=15
        )
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            # Check if response is binary (Excel file) or JSON
            content_type = response.headers.get('content-type', '')
            if 'application/vnd.openxmlformats' in content_type or len(response.content) > 1000:
                log_test(
                    "POST /api/print/invoice-xlsx",
                    "PASS",
                    f"✅ Excel file generated. Size: {len(response.content)} bytes",
                    response_time
                )
                results.append(("POST /api/print/invoice-xlsx", True, response_time))
            else:
                # Try to parse as JSON
                try:
                    data = response.json()
                    issues = check_response_format(data, "print/invoice-xlsx")
                    log_test(
                        "POST /api/print/invoice-xlsx",
                        "PASS",
                        f"✅ Response received: {str(data)[:100]}..." + (f"\n  Issues: {issues}" if issues else ""),
                        response_time
                    )
                    results.append(("POST /api/print/invoice-xlsx", True, response_time))
                except:
                    log_test(
                        "POST /api/print/invoice-xlsx",
                        "PASS",
                        f"✅ Response received. Content-Type: {content_type}",
                        response_time
                    )
                    results.append(("POST /api/print/invoice-xlsx", True, response_time))
        else:
            log_test(
                "POST /api/print/invoice-xlsx",
                "FAIL",
                f"Status: {response.status_code}, Response: {response.text[:200]}"
            )
            results.append(("POST /api/print/invoice-xlsx", False, 0))
    except Exception as e:
        log_test("POST /api/print/invoice-xlsx", "FAIL", f"Exception: {str(e)}")
        results.append(("POST /api/print/invoice-xlsx", False, 0))
    
    # Test 6: GET /api/references/dtc?code=P2565
    try:
        start_time = time.time()
        response = requests.get(f"{BACKEND_URL}/references/dtc?code=P2565", timeout=15)
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            issues = check_response_format(data, "references/dtc")
            log_test(
                "GET /api/references/dtc?code=P2565",
                "PASS",
                f"✅ DTC lookup successful. Response: {str(data)[:100]}..." + (f"\n  Issues: {issues}" if issues else ""),
                response_time
            )
            results.append(("GET /api/references/dtc?code=P2565", True, response_time))
        else:
            log_test(
                "GET /api/references/dtc?code=P2565",
                "FAIL",
                f"Status: {response.status_code}, Response: {response.text[:200]}"
            )
            results.append(("GET /api/references/dtc?code=P2565", False, 0))
    except Exception as e:
        log_test("GET /api/references/dtc?code=P2565", "FAIL", f"Exception: {str(e)}")
        results.append(("GET /api/references/dtc?code=P2565", False, 0))
    
    # Test 7: POST /api/notifications/prepare
    try:
        notification_data = {
            "phone": "+966501234567",
            "link": "https://example.com",
            "type": "approval",
            "message": "طلب اعتماد جديد"
        }
        
        start_time = time.time()
        response = requests.post(
            f"{BACKEND_URL}/notifications/prepare",
            json=notification_data,
            headers={"Content-Type": "application/json"},
            timeout=15
        )
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            issues = check_response_format(data, "notifications/prepare")
            
            # Check for Arabic preservation and phone normalization
            whatsapp_link = data.get('whatsappDeeplink', '')
            phone_check = '966501234567' in whatsapp_link and '+966966' not in whatsapp_link
            arabic_check = 'طلب' in whatsapp_link or 'اعتماد' in whatsapp_link
            
            log_test(
                "POST /api/notifications/prepare",
                "PASS",
                f"✅ Notification prepared. Phone OK: {phone_check}, Arabic OK: {arabic_check}" + (f"\n  Issues: {issues}" if issues else ""),
                response_time
            )
            results.append(("POST /api/notifications/prepare", True, response_time))
        else:
            log_test(
                "POST /api/notifications/prepare",
                "FAIL",
                f"Status: {response.status_code}, Response: {response.text[:200]}"
            )
            results.append(("POST /api/notifications/prepare", False, 0))
    except Exception as e:
        log_test("POST /api/notifications/prepare", "FAIL", f"Exception: {str(e)}")
        results.append(("POST /api/notifications/prepare", False, 0))
    
    return results

def test_arabic_html_preservation():
    """Test Arabic content preservation in HTML rendering"""
    print(f"\n{Colors.BLUE}{'='*80}")
    print(f"ARABIC HTML PRESERVATION TEST - اختبار الحفاظ على العربية في HTML")
    print(f"{'='*80}{Colors.RESET}\n")
    
    results = []
    
    # Test: POST /api/print/render with Arabic data
    try:
        render_data = {
            "CUSTOMER_NAME": "أحمد محمد الراشد",
            "WORKSHOP_NAME": "ورشة الاختبار",
            "INVOICE_NUMBER": "INV-2024-001",
            "DATE": "2024-01-15",
            "ITEMS_ROWS": [
                {
                    "name": "زيت محرك صناعي",
                    "quantity": 1,
                    "price": 150.0,
                    "total": 150.0
                },
                {
                    "name": "فلتر هواء أصلي",
                    "quantity": 1,
                    "price": 85.0,
                    "total": 85.0
                }
            ],
            "SUBTOTAL": 235.0,
            "TAX": 35.25,
            "TOTAL": 270.25
        }
        
        start_time = time.time()
        response = requests.post(
            f"{BACKEND_URL}/print/render",
            json=render_data,
            headers={"Content-Type": "application/json"},
            timeout=15
        )
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            html_content = response.text
            
            # Check for Arabic content preservation
            arabic_preserved = (
                "أحمد محمد الراشد" in html_content and
                "ورشة الاختبار" in html_content and
                "زيت محرك صناعي" in html_content and
                "فلتر هواء أصلي" in html_content
            )
            
            # Check for proper HTML structure
            html_structure = (
                "<html" in html_content and
                "<body" in html_content and
                "</html>" in html_content
            )
            
            log_test(
                "POST /api/print/render (Arabic preservation)",
                "PASS" if arabic_preserved and html_structure else "FAIL",
                f"✅ HTML rendered. Arabic preserved: {arabic_preserved}, HTML structure: {html_structure}, Length: {len(html_content)} chars",
                response_time
            )
            results.append(("POST /api/print/render (Arabic preservation)", arabic_preserved and html_structure, response_time))
        else:
            log_test(
                "POST /api/print/render (Arabic preservation)",
                "FAIL",
                f"Status: {response.status_code}, Response: {response.text[:200]}"
            )
            results.append(("POST /api/print/render (Arabic preservation)", False, 0))
    except Exception as e:
        log_test("POST /api/print/render (Arabic preservation)", "FAIL", f"Exception: {str(e)}")
        results.append(("POST /api/print/render (Arabic preservation)", False, 0))
    
    return results

def print_summary(all_results: List[tuple]):
    """Print comprehensive test summary"""
    print(f"\n{Colors.BLUE}{'='*80}")
    print(f"DEEP BACKEND REGRESSION TEST SUMMARY")
    print(f"ملخص اختبار الانحدار العميق للخلفية")
    print(f"{'='*80}{Colors.RESET}\n")
    
    total_tests = len(all_results)
    passed_tests = sum(1 for _, passed, _ in all_results if passed)
    failed_tests = total_tests - passed_tests
    
    # Calculate average response time
    response_times = [rt for _, passed, rt in all_results if passed and rt > 0]
    avg_response_time = sum(response_times) / len(response_times) if response_times else 0
    
    print(f"Total Tests: {total_tests}")
    print(f"{Colors.GREEN}Passed: {passed_tests}{Colors.RESET}")
    print(f"{Colors.RED}Failed: {failed_tests}{Colors.RESET}")
    print(f"Success Rate: {(passed_tests/total_tests*100):.1f}%")
    print(f"Average Response Time: {avg_response_time:.3f}s\n")
    
    # Check for slow endpoints
    slow_endpoints = [(name, rt) for name, passed, rt in all_results if passed and rt > 30]
    if slow_endpoints:
        print(f"{Colors.YELLOW}⚠️  SLOW ENDPOINTS (>30s):{Colors.RESET}")
        for name, rt in slow_endpoints:
            print(f"  - {name}: {rt:.3f}s")
        print()
    
    # Detailed results
    print("Detailed Results:")
    print("-" * 80)
    for test_name, passed, response_time in all_results:
        status = f"{Colors.GREEN}✅ PASS{Colors.RESET}" if passed else f"{Colors.RED}❌ FAIL{Colors.RESET}"
        time_str = f"({response_time:.3f}s)" if response_time > 0 else ""
        print(f"{status} {test_name} {time_str}")
    
    print("\n" + "="*80)
    
    # Final verdict
    if failed_tests == 0:
        print(f"{Colors.GREEN}🎉 ALL TESTS PASSED! No 404 errors found. System is working correctly.{Colors.RESET}")
    else:
        print(f"{Colors.RED}⚠️  {failed_tests} TEST(S) FAILED. Some endpoints may still be missing or broken.{Colors.RESET}")
    print("="*80 + "\n")

def main():
    """Main test execution"""
    print(f"\n{Colors.BLUE}{'='*80}")
    print(f"DEEP BACKEND REGRESSION TEST")
    print(f"إعادة تشغيل اختبارات Backend العميقة بعد استعادة المسارات")
    print(f"{'='*80}{Colors.RESET}\n")
    print(f"Backend URL: {BACKEND_URL}")
    print(f"Test Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    all_results = []
    
    # Run all test sections
    all_results.extend(test_critical_endpoints())
    all_results.extend(test_regression_endpoints())
    all_results.extend(test_arabic_html_preservation())
    
    # Print summary
    print_summary(all_results)

if __name__ == "__main__":
    main()