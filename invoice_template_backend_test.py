#!/usr/bin/env python3
"""
Invoice Template Studio A4 Designer Backend API Testing
Tests all invoice template endpoints after UX improvements
"""

import requests
import json
import sys
from datetime import datetime

# Backend URL from frontend/.env
BASE_URL = "https://accounting-ssot-fix.preview.emergentagent.com/api"

# Test results tracking
tests_passed = 0
tests_failed = 0
failed_tests = []

def print_test(name, status, details=""):
    """Print test result"""
    global tests_passed, tests_failed, failed_tests
    symbol = "✅" if status else "❌"
    print(f"{symbol} {name}")
    if details:
        print(f"   {details}")
    if status:
        tests_passed += 1
    else:
        tests_failed += 1
        failed_tests.append({"name": name, "details": details})
    print()

def test_list_templates():
    """Test GET /api/invoice-templates - List all templates"""
    try:
        response = requests.get(f"{BASE_URL}/invoice-templates", timeout=10)
        if response.status_code == 200:
            templates = response.json()
            print_test(
                "GET /api/invoice-templates",
                True,
                f"Status: {response.status_code}, Templates count: {len(templates)}"
            )
            return templates
        else:
            print_test(
                "GET /api/invoice-templates",
                False,
                f"Status: {response.status_code}, Response: {response.text[:200]}"
            )
            return []
    except Exception as e:
        print_test("GET /api/invoice-templates", False, f"Exception: {str(e)}")
        return []

def test_create_blank_template():
    """Test POST /api/invoice-templates/create-blank - Create blank template with A4 properties"""
    try:
        payload = {
            "name": "Test A4 Template",
            "rows": 12,
            "cols": 8
        }
        response = requests.post(
            f"{BASE_URL}/invoice-templates/create-blank",
            json=payload,
            timeout=10
        )
        if response.status_code in [200, 201]:
            template = response.json()
            # Verify A4 page properties
            has_page = "page" in template
            has_elements = "elements" in template
            has_schema = "schema" in template
            page_is_a4 = template.get("page", {}).get("size") == "A4"
            
            success = has_page and has_elements and has_schema and page_is_a4
            print_test(
                "POST /api/invoice-templates/create-blank",
                success,
                f"Status: {response.status_code}, Template ID: {template.get('id')}, "
                f"Page: {template.get('page')}, Elements: {len(template.get('elements', []))}"
            )
            return template if success else None
        else:
            print_test(
                "POST /api/invoice-templates/create-blank",
                False,
                f"Status: {response.status_code}, Response: {response.text[:200]}"
            )
            return None
    except Exception as e:
        print_test("POST /api/invoice-templates/create-blank", False, f"Exception: {str(e)}")
        return None

def test_auto_save(template_id):
    """Test POST /api/invoice-templates/{tid}/auto-save - Auto-save with elements array"""
    try:
        # Test with elements containing text, image, table, qr
        payload = {
            "elements": [
                {
                    "id": "text1",
                    "type": "text",
                    "x": 10,
                    "y": 10,
                    "w": 200,
                    "h": 30,
                    "content": "اسم العميل",
                    "binding": "CUSTOMER_NAME"
                },
                {
                    "id": "img1",
                    "type": "image",
                    "x": 500,
                    "y": 10,
                    "w": 100,
                    "h": 100,
                    "src": "logo.png"
                },
                {
                    "id": "table1",
                    "type": "table",
                    "x": 10,
                    "y": 150,
                    "w": 580,
                    "h": 200,
                    "binding": "ITEMS"
                },
                {
                    "id": "qr1",
                    "type": "qr",
                    "x": 500,
                    "y": 400,
                    "w": 80,
                    "h": 80,
                    "binding": "INVOICE_NUMBER"
                }
            ],
            "schema": [
                {"field": "CUSTOMER_NAME", "type": "text"},
                {"field": "ITEMS", "type": "table"},
                {"field": "INVOICE_NUMBER", "type": "text"}
            ],
            "page": {
                "size": "A4",
                "orientation": "portrait",
                "width": 595,
                "height": 842
            }
        }
        response = requests.post(
            f"{BASE_URL}/invoice-templates/{template_id}/auto-save",
            json=payload,
            timeout=10
        )
        if response.status_code == 200:
            result = response.json()
            template = result.get("template", {})
            elements_saved = len(template.get("elements", [])) == 4
            schema_saved = len(template.get("schema", [])) == 3
            page_saved = template.get("page", {}).get("size") == "A4"
            
            success = elements_saved and schema_saved and page_saved
            print_test(
                "POST /api/invoice-templates/{tid}/auto-save",
                success,
                f"Status: {response.status_code}, Elements: {len(template.get('elements', []))}, "
                f"Schema: {len(template.get('schema', []))}, Page: {template.get('page')}"
            )
            return success
        else:
            print_test(
                "POST /api/invoice-templates/{tid}/auto-save",
                False,
                f"Status: {response.status_code}, Response: {response.text[:200]}"
            )
            return False
    except Exception as e:
        print_test("POST /api/invoice-templates/{tid}/auto-save", False, f"Exception: {str(e)}")
        return False

def test_save_design(template_id):
    """Test POST /api/invoice-templates/{tid}/design - Save A4 design"""
    try:
        payload = {
            "elements": [
                {
                    "id": "text1",
                    "type": "text",
                    "x": 20,
                    "y": 20,
                    "w": 150,
                    "h": 25,
                    "content": "رقم الفاتورة"
                }
            ],
            "page": {
                "size": "A4",
                "orientation": "portrait"
            },
            "schema": [
                {"field": "INVOICE_NUMBER", "type": "text"}
            ]
        }
        response = requests.post(
            f"{BASE_URL}/invoice-templates/{template_id}/design",
            json=payload,
            timeout=10
        )
        if response.status_code == 200:
            template = response.json()
            success = (
                len(template.get("elements", [])) > 0 and
                template.get("page", {}).get("size") == "A4"
            )
            print_test(
                "POST /api/invoice-templates/{tid}/design",
                success,
                f"Status: {response.status_code}, Elements: {len(template.get('elements', []))}"
            )
            return success
        else:
            print_test(
                "POST /api/invoice-templates/{tid}/design",
                False,
                f"Status: {response.status_code}, Response: {response.text[:200]}"
            )
            return False
    except Exception as e:
        print_test("POST /api/invoice-templates/{tid}/design", False, f"Exception: {str(e)}")
        return False

def test_save_named_arabic(template_id):
    """Test POST /api/invoice-templates/{tid}/save-named - Create named copy with Arabic name"""
    try:
        payload = {
            "name": "فاتوره",
            "grid": [
                ["{{WORKSHOP_NAME}}", "", "", "{{CUSTOMER_NAME}}"],
                ["{{ITEMS}}", "", "", ""],
                ["البند", "الكمية", "السعر", "المجموع"]
            ],
            "mapping": {
                "CUSTOMER_NAME": "A1",
                "WORKSHOP_NAME": "A1"
            },
            "itemsConfig": {
                "anchor": "{{ITEMS}}",
                "columns": {
                    "description": "A",
                    "qty": "B",
                    "price": "C",
                    "total": "D"
                }
            },
            "elements": [],
            "schema": [],
            "page": {"size": "A4", "orientation": "portrait"}
        }
        response = requests.post(
            f"{BASE_URL}/invoice-templates/{template_id}/save-named",
            json=payload,
            timeout=10
        )
        if response.status_code in [200, 201]:
            template = response.json()
            name_preserved = template.get("name") == "فاتوره"
            has_id = "id" in template and template["id"] != template_id
            
            success = name_preserved and has_id
            print_test(
                "POST /api/invoice-templates/{tid}/save-named (Arabic)",
                success,
                f"Status: {response.status_code}, Name: {template.get('name')}, "
                f"New ID: {template.get('id')}"
            )
            return template if success else None
        else:
            print_test(
                "POST /api/invoice-templates/{tid}/save-named (Arabic)",
                False,
                f"Status: {response.status_code}, Response: {response.text[:200]}"
            )
            return None
    except Exception as e:
        print_test("POST /api/invoice-templates/{tid}/save-named (Arabic)", False, f"Exception: {str(e)}")
        return None

def test_save_json(template_id):
    """Test POST /api/invoice-templates/{tid}/save-json - Save grid/mapping/items"""
    try:
        payload = {
            "grid": [
                ["{{WORKSHOP_NAME}}", "", "{{DATE}}"],
                ["{{CUSTOMER_NAME}}", "", "{{INVOICE_NUMBER}}"],
                ["{{ITEMS}}", "", ""],
                ["البند", "الكمية", "السعر"]
            ],
            "mapping": {
                "WORKSHOP_NAME": "A1",
                "DATE": "C1",
                "CUSTOMER_NAME": "A2",
                "INVOICE_NUMBER": "C2"
            },
            "items": {
                "anchor": "{{ITEMS}}",
                "columns": {
                    "description": "A",
                    "qty": "B",
                    "price": "C"
                }
            }
        }
        response = requests.post(
            f"{BASE_URL}/invoice-templates/{template_id}/save-json",
            json=payload,
            timeout=10
        )
        if response.status_code == 200:
            result = response.json()
            success = result.get("status") == "ok"
            print_test(
                "POST /api/invoice-templates/{tid}/save-json",
                success,
                f"Status: {response.status_code}, Result: {result}"
            )
            return success
        else:
            print_test(
                "POST /api/invoice-templates/{tid}/save-json",
                False,
                f"Status: {response.status_code}, Response: {response.text[:200]}"
            )
            return False
    except Exception as e:
        print_test("POST /api/invoice-templates/{tid}/save-json", False, f"Exception: {str(e)}")
        return False

def test_soft_delete(template_id):
    """Test DELETE /api/invoice-templates/{tid} - Soft delete"""
    try:
        response = requests.delete(
            f"{BASE_URL}/invoice-templates/{template_id}",
            timeout=10
        )
        if response.status_code == 200:
            result = response.json()
            success = result.get("status") == "archived"
            print_test(
                "DELETE /api/invoice-templates/{tid} (soft delete)",
                success,
                f"Status: {response.status_code}, Result: {result}"
            )
            return success
        else:
            print_test(
                "DELETE /api/invoice-templates/{tid} (soft delete)",
                False,
                f"Status: {response.status_code}, Response: {response.text[:200]}"
            )
            return False
    except Exception as e:
        print_test("DELETE /api/invoice-templates/{tid} (soft delete)", False, f"Exception: {str(e)}")
        return False

def test_hard_delete(template_id):
    """Test DELETE /api/invoice-templates/{tid}/hard - Hard delete"""
    try:
        response = requests.delete(
            f"{BASE_URL}/invoice-templates/{template_id}/hard",
            timeout=10
        )
        if response.status_code == 200:
            result = response.json()
            success = result.get("status") in ["deleted", "ok"]
            print_test(
                "DELETE /api/invoice-templates/{tid}/hard",
                success,
                f"Status: {response.status_code}, Result: {result}"
            )
            return success
        else:
            print_test(
                "DELETE /api/invoice-templates/{tid}/hard",
                False,
                f"Status: {response.status_code}, Response: {response.text[:200]}"
            )
            return False
    except Exception as e:
        print_test("DELETE /api/invoice-templates/{tid}/hard", False, f"Exception: {str(e)}")
        return False

def test_cleanup_empty():
    """Test POST /api/invoice-templates/cleanup-empty - Clean empty templates"""
    try:
        response = requests.post(
            f"{BASE_URL}/invoice-templates/cleanup-empty",
            timeout=10
        )
        if response.status_code == 200:
            result = response.json()
            has_archived = "archived" in result
            has_deleted = "deleted" in result
            success = has_archived and has_deleted
            print_test(
                "POST /api/invoice-templates/cleanup-empty",
                success,
                f"Status: {response.status_code}, Archived: {result.get('archived')}, "
                f"Deleted: {result.get('deleted')}"
            )
            return success
        else:
            print_test(
                "POST /api/invoice-templates/cleanup-empty",
                False,
                f"Status: {response.status_code}, Response: {response.text[:200]}"
            )
            return False
    except Exception as e:
        print_test("POST /api/invoice-templates/cleanup-empty", False, f"Exception: {str(e)}")
        return False

def test_print_invoice_xlsx(template_id):
    """Test POST /api/print/invoice-xlsx - Generate Excel invoice"""
    try:
        payload = {
            "templateId": template_id,
            "data": {
                "WORKSHOP_NAME": "ورشة الأمل",
                "CUSTOMER_NAME": "أحمد محمد",
                "INVOICE_NUMBER": "INV-2025-001",
                "DATE": "2025-01-15",
                "TOTAL": "1500.00",
                "ITEMS": [
                    {
                        "description": "تغيير زيت",
                        "qty": "1",
                        "price": "150",
                        "total": "150"
                    },
                    {
                        "description": "فلتر هواء",
                        "qty": "2",
                        "price": "50",
                        "total": "100"
                    }
                ]
            }
        }
        response = requests.post(
            f"{BASE_URL}/print/invoice-xlsx",
            json=payload,
            timeout=15
        )
        if response.status_code == 200:
            # Check if response is Excel file
            content_type = response.headers.get("content-type", "")
            is_excel = "spreadsheet" in content_type or "xlsx" in content_type
            has_content = len(response.content) > 0
            
            success = is_excel and has_content
            print_test(
                "POST /api/print/invoice-xlsx",
                success,
                f"Status: {response.status_code}, Content-Type: {content_type}, "
                f"Size: {len(response.content)} bytes"
            )
            return success
        else:
            print_test(
                "POST /api/print/invoice-xlsx",
                False,
                f"Status: {response.status_code}, Response: {response.text[:200]}"
            )
            return False
    except Exception as e:
        print_test("POST /api/print/invoice-xlsx", False, f"Exception: {str(e)}")
        return False

def test_resize_handles_data(template_id):
    """Test that resize handles data (x,y,w,h) saves correctly"""
    try:
        payload = {
            "elements": [
                {
                    "id": "resizable1",
                    "type": "text",
                    "x": 100,
                    "y": 100,
                    "w": 200,
                    "h": 50,
                    "content": "Resizable Element"
                }
            ],
            "page": {"size": "A4", "orientation": "portrait"}
        }
        response = requests.post(
            f"{BASE_URL}/invoice-templates/{template_id}/design",
            json=payload,
            timeout=10
        )
        if response.status_code == 200:
            template = response.json()
            elements = template.get("elements", [])
            if elements:
                elem = elements[0]
                has_coords = all(k in elem for k in ["x", "y", "w", "h"])
                coords_match = (
                    elem.get("x") == 100 and
                    elem.get("y") == 100 and
                    elem.get("w") == 200 and
                    elem.get("h") == 50
                )
                success = has_coords and coords_match
                print_test(
                    "Resize handles data (x,y,w,h) saves correctly",
                    success,
                    f"Element coords: x={elem.get('x')}, y={elem.get('y')}, "
                    f"w={elem.get('w')}, h={elem.get('h')}"
                )
                return success
            else:
                print_test(
                    "Resize handles data (x,y,w,h) saves correctly",
                    False,
                    "No elements found in response"
                )
                return False
        else:
            print_test(
                "Resize handles data (x,y,w,h) saves correctly",
                False,
                f"Status: {response.status_code}"
            )
            return False
    except Exception as e:
        print_test("Resize handles data (x,y,w,h) saves correctly", False, f"Exception: {str(e)}")
        return False

def main():
    """Run all tests"""
    print("=" * 80)
    print("Invoice Template Studio A4 Designer Backend API Testing")
    print("=" * 80)
    print(f"Backend URL: {BASE_URL}")
    print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print()

    # Test 1: List templates
    print("TEST 1: List all templates")
    print("-" * 80)
    existing_templates = test_list_templates()

    # Test 2: Create blank template with A4 properties
    print("TEST 2: Create blank template with A4 page properties")
    print("-" * 80)
    new_template = test_create_blank_template()

    if new_template:
        template_id = new_template.get("id")
        
        # Test 3: Auto-save with elements array
        print("TEST 3: Auto-save with elements (text/image/table/qr)")
        print("-" * 80)
        test_auto_save(template_id)

        # Test 4: Save A4 design
        print("TEST 4: Save A4 design (elements/page/schema)")
        print("-" * 80)
        test_save_design(template_id)

        # Test 5: Resize handles data
        print("TEST 5: Verify resize handles data saves correctly")
        print("-" * 80)
        test_resize_handles_data(template_id)

        # Test 6: Save JSON (grid/mapping/items)
        print("TEST 6: Save grid/mapping/items")
        print("-" * 80)
        test_save_json(template_id)

        # Test 7: Save named copy with Arabic name
        print("TEST 7: Save named template with Arabic name 'فاتوره'")
        print("-" * 80)
        arabic_template = test_save_named_arabic(template_id)

        # Test 8: Print invoice Excel
        print("TEST 8: Generate Excel invoice")
        print("-" * 80)
        test_print_invoice_xlsx(template_id)

        # Test 9: Cleanup empty templates
        print("TEST 9: Cleanup empty templates")
        print("-" * 80)
        test_cleanup_empty()

        # Test 10: Soft delete
        print("TEST 10: Soft delete template")
        print("-" * 80)
        test_soft_delete(template_id)

        # Test 11: Hard delete (create another template first)
        print("TEST 11: Hard delete template")
        print("-" * 80)
        temp_template = test_create_blank_template()
        if temp_template:
            test_hard_delete(temp_template.get("id"))

    # Test missing endpoints
    print("TEST 12: Check for missing endpoints")
    print("-" * 80)
    print_test(
        "POST /api/invoice-templates/import",
        False,
        "Endpoint NOT IMPLEMENTED in backend"
    )
    print_test(
        "POST /api/invoice-templates/import-url",
        False,
        "Endpoint NOT IMPLEMENTED in backend"
    )

    # Summary
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    total_tests = tests_passed + tests_failed
    pass_rate = (tests_passed / total_tests * 100) if total_tests > 0 else 0
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {tests_passed} ✅")
    print(f"Failed: {tests_failed} ❌")
    print(f"Pass Rate: {pass_rate:.1f}%")
    print()

    if failed_tests:
        print("FAILED TESTS:")
        print("-" * 80)
        for i, test in enumerate(failed_tests, 1):
            print(f"{i}. {test['name']}")
            print(f"   {test['details']}")
            print()

    print("=" * 80)
    print(f"Test completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    # Exit with appropriate code
    sys.exit(0 if tests_failed == 0 else 1)

if __name__ == "__main__":
    main()
