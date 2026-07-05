#!/usr/bin/env python3
"""
Invoice Template Regression Test Suite
Focused testing for new/updated invoice template endpoints and related flows
"""

import asyncio
import aiohttp
import json
import sys
from datetime import datetime
from typing import Dict, Any, List

# Backend URL from environment
BACKEND_URL = "https://pdpl-memory-engine.preview.emergentagent.com/api"

class InvoiceTemplateRegressionTest:
    def __init__(self):
        self.session = None
        self.results = []
        self.template_id = None
        
    async def setup(self):
        """Initialize HTTP session"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={'Content-Type': 'application/json'}
        )
        
    async def cleanup(self):
        """Close HTTP session"""
        if self.session:
            await self.session.close()
            
    def log_result(self, test_name: str, success: bool, details: str = "", response_data: Any = None):
        """Log test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        self.results.append({
            'test': test_name,
            'success': success,
            'details': details,
            'response_data': response_data
        })
        print(f"{status}: {test_name}")
        if details:
            print(f"   Details: {details}")
        if not success and response_data:
            print(f"   Response: {response_data}")
        print()
        
    async def make_request(self, method: str, endpoint: str, data: Dict = None) -> tuple:
        """Make HTTP request and return (success, response_data, status_code)"""
        try:
            url = f"{BACKEND_URL}{endpoint}"
            
            if method.upper() == 'GET':
                async with self.session.get(url) as response:
                    response_data = await response.json()
                    return response.status < 400, response_data, response.status
            elif method.upper() == 'POST':
                async with self.session.post(url, json=data) as response:
                    response_data = await response.json()
                    return response.status < 400, response_data, response.status
            elif method.upper() == 'PUT':
                async with self.session.put(url, json=data) as response:
                    response_data = await response.json()
                    return response.status < 400, response_data, response.status
            elif method.upper() == 'DELETE':
                async with self.session.delete(url) as response:
                    response_data = await response.json()
                    return response.status < 400, response_data, response.status
                    
        except Exception as e:
            return False, str(e), 500
            
    def validate_no_id_leakage(self, data: Any) -> bool:
        """Check that response doesn't contain _id fields"""
        if isinstance(data, dict):
            if '_id' in data:
                return False
            return all(self.validate_no_id_leakage(v) for v in data.values())
        elif isinstance(data, list):
            return all(self.validate_no_id_leakage(item) for item in data)
        return True
        
    def validate_iso_dates(self, data: Any) -> bool:
        """Check that date fields are in ISO format"""
        if isinstance(data, dict):
            for key, value in data.items():
                if key.endswith('At') or key.endswith('Date'):
                    if isinstance(value, str):
                        try:
                            datetime.fromisoformat(value.replace('Z', '+00:00'))
                        except:
                            return False
            return all(self.validate_iso_dates(v) for v in data.values())
        elif isinstance(data, list):
            return all(self.validate_iso_dates(item) for item in data)
        return True

    async def test_1_create_blank_template(self):
        """Test 1: POST /api/invoice-templates/create-blank -> expect template with preview, page size A4"""
        success, response_data, status = await self.make_request('POST', '/invoice-templates/create-blank', {
            'name': 'Test Template',
            'rows': 12,
            'cols': 8
        })
        
        if success and response_data:
            # Store template ID for subsequent tests
            self.template_id = response_data.get('id')
            
            # Validate response structure
            has_preview = 'preview' in response_data
            has_page_a4 = response_data.get('page', {}).get('size') == 'A4'
            no_id_leak = self.validate_no_id_leakage(response_data)
            
            if has_preview and has_page_a4 and no_id_leak and self.template_id:
                self.log_result("Create Blank Template", True, 
                              f"Template created with ID: {self.template_id}, page size: A4, preview: {len(response_data.get('preview', []))} rows")
            else:
                self.log_result("Create Blank Template", False, 
                              f"Missing required fields - preview: {has_preview}, A4: {has_page_a4}, no _id: {no_id_leak}")
        else:
            self.log_result("Create Blank Template", False, f"Request failed with status {status}", response_data)

    async def test_2_save_json_template(self):
        """Test 2: POST /api/invoice-templates/{tid}/save-json with grid+mapping+items -> expect ok and template updated"""
        if not self.template_id:
            self.log_result("Save JSON Template", False, "No template ID from previous test")
            return
            
        test_data = {
            'grid': [
                ['{{WORKSHOP_NAME}}', '', '', '{{CUSTOMER_NAME}}'],
                ['{{ITEMS}}', '', '', ''],
                ['المادة', 'الكمية', 'السعر', 'المجموع'],
                ['', '', '', '']
            ],
            'mapping': {
                'WORKSHOP_NAME': 'A1',
                'CUSTOMER_NAME': 'D1',
                'ITEMS': 'A2'
            },
            'items': {
                'anchor': '{{ITEMS}}',
                'columns': {
                    'description': 'A',
                    'qty': 'B', 
                    'price': 'C',
                    'total': 'D'
                }
            }
        }
        
        success, response_data, status = await self.make_request('POST', f'/invoice-templates/{self.template_id}/save-json', test_data)
        
        if success and response_data:
            status_ok = response_data.get('status') == 'ok'
            no_id_leak = self.validate_no_id_leakage(response_data)
            
            if status_ok and no_id_leak:
                self.log_result("Save JSON Template", True, "Template saved successfully with grid, mapping, and items config")
            else:
                self.log_result("Save JSON Template", False, f"Status not ok or _id leak - status: {response_data.get('status')}, no _id: {no_id_leak}")
        else:
            self.log_result("Save JSON Template", False, f"Request failed with status {status}", response_data)

    async def test_3_auto_save_template(self):
        """Test 3: POST /api/invoice-templates/{tid}/auto-save with grid/mapping/itemsConfig/elements/schema/page -> expect status ok and template echoed"""
        if not self.template_id:
            self.log_result("Auto Save Template", False, "No template ID from previous test")
            return
            
        test_data = {
            'grid': [
                ['{{WORKSHOP_NAME}}', '', '', '{{CUSTOMER_NAME}}'],
                ['{{ITEMS}}', '', '', ''],
                ['المادة', 'الكمية', 'السعر', 'المجموع']
            ],
            'mapping': {
                'WORKSHOP_NAME': 'A1',
                'CUSTOMER_NAME': 'D1'
            },
            'itemsConfig': {
                'anchor': '{{ITEMS}}',
                'columns': {'description': 'A', 'qty': 'B', 'price': 'C', 'total': 'D'}
            },
            'elements': [
                {'type': 'text', 'content': 'فاتورة', 'position': {'x': 100, 'y': 50}}
            ],
            'schema': [
                {'field': 'WORKSHOP_NAME', 'type': 'text', 'required': True}
            ],
            'page': {'size': 'A4', 'orientation': 'portrait'}
        }
        
        success, response_data, status = await self.make_request('POST', f'/invoice-templates/{self.template_id}/auto-save', test_data)
        
        if success and response_data:
            status_ok = response_data.get('status') == 'ok'
            has_template = 'template' in response_data
            no_id_leak = self.validate_no_id_leakage(response_data)
            
            if status_ok and has_template and no_id_leak:
                self.log_result("Auto Save Template", True, "Template auto-saved successfully with all components")
            else:
                self.log_result("Auto Save Template", False, f"Missing required response - status ok: {status_ok}, has template: {has_template}, no _id: {no_id_leak}")
        else:
            self.log_result("Auto Save Template", False, f"Request failed with status {status}", response_data)

    async def test_4_save_named_template(self):
        """Test 4: POST /api/invoice-templates/{tid}/save-named with name='فاتوره' -> expect new template listed"""
        if not self.template_id:
            self.log_result("Save Named Template", False, "No template ID from previous test")
            return
            
        test_data = {
            'name': 'فاتوره',
            'grid': [
                ['{{WORKSHOP_NAME}}', '', '', '{{CUSTOMER_NAME}}'],
                ['{{ITEMS}}', '', '', '']
            ],
            'mapping': {'WORKSHOP_NAME': 'A1', 'CUSTOMER_NAME': 'D1'},
            'itemsConfig': {'anchor': '{{ITEMS}}', 'columns': {'description': 'A', 'qty': 'B'}}
        }
        
        success, response_data, status = await self.make_request('POST', f'/invoice-templates/{self.template_id}/save-named', test_data)
        
        if success and response_data:
            has_name = response_data.get('name') == 'فاتوره'
            has_id = 'id' in response_data
            no_id_leak = self.validate_no_id_leakage(response_data)
            
            if has_name and has_id and no_id_leak:
                # Verify it appears in template list
                list_success, list_data, _ = await self.make_request('GET', '/invoice-templates')
                if list_success:
                    named_template_found = any(t.get('name') == 'فاتوره' for t in list_data)
                    if named_template_found:
                        self.log_result("Save Named Template", True, f"Named template 'فاتوره' created and listed successfully")
                    else:
                        self.log_result("Save Named Template", False, "Named template created but not found in list")
                else:
                    self.log_result("Save Named Template", False, "Template created but failed to verify in list")
            else:
                self.log_result("Save Named Template", False, f"Invalid response - name: {has_name}, id: {has_id}, no _id: {no_id_leak}")
        else:
            self.log_result("Save Named Template", False, f"Request failed with status {status}", response_data)

    async def test_5_make_default_template(self):
        """Test 5: POST /api/invoice-templates/{tid}/make-default -> expect isDefault true"""
        if not self.template_id:
            self.log_result("Make Default Template", False, "No template ID from previous test")
            return
            
        success, response_data, status = await self.make_request('POST', f'/invoice-templates/{self.template_id}/make-default')
        
        if success and response_data:
            is_default = response_data.get('isDefault') is True
            no_id_leak = self.validate_no_id_leakage(response_data)
            
            if is_default and no_id_leak:
                self.log_result("Make Default Template", True, "Template successfully set as default")
            else:
                self.log_result("Make Default Template", False, f"isDefault not true or _id leak - isDefault: {response_data.get('isDefault')}, no _id: {no_id_leak}")
        else:
            self.log_result("Make Default Template", False, f"Request failed with status {status}", response_data)

    async def test_6_cleanup_empty_templates(self):
        """Test 6: POST /api/invoice-templates/cleanup-empty (purge=false) -> expect archived>=0"""
        success, response_data, status = await self.make_request('POST', '/invoice-templates/cleanup-empty?purge=false')
        
        if success and response_data:
            has_archived = 'archived' in response_data
            archived_count = response_data.get('archived', -1)
            no_id_leak = self.validate_no_id_leakage(response_data)
            
            if has_archived and archived_count >= 0 and no_id_leak:
                self.log_result("Cleanup Empty Templates", True, f"Cleanup completed - archived: {archived_count} templates")
            else:
                self.log_result("Cleanup Empty Templates", False, f"Invalid response - has archived: {has_archived}, count: {archived_count}, no _id: {no_id_leak}")
        else:
            self.log_result("Cleanup Empty Templates", False, f"Request failed with status {status}", response_data)

    async def test_7_list_templates_hide_archived(self):
        """Test 7: GET /api/invoice-templates -> ensure archived ones hidden"""
        success, response_data, status = await self.make_request('GET', '/invoice-templates')
        
        if success and isinstance(response_data, list):
            archived_found = any(t.get('archived') is True for t in response_data)
            no_id_leak = self.validate_no_id_leakage(response_data)
            
            if not archived_found and no_id_leak:
                self.log_result("List Templates Hide Archived", True, f"Template list returned {len(response_data)} templates, no archived ones visible")
            else:
                self.log_result("List Templates Hide Archived", False, f"Archived templates found or _id leak - archived found: {archived_found}, no _id: {no_id_leak}")
        else:
            self.log_result("List Templates Hide Archived", False, f"Request failed with status {status}", response_data)

    async def test_8_soft_delete_template(self):
        """Test 8: DELETE /api/invoice-templates/{tid} (soft) -> status archived"""
        if not self.template_id:
            self.log_result("Soft Delete Template", False, "No template ID from previous test")
            return
            
        success, response_data, status = await self.make_request('DELETE', f'/invoice-templates/{self.template_id}')
        
        if success and response_data:
            status_archived = response_data.get('status') == 'archived'
            no_id_leak = self.validate_no_id_leakage(response_data)
            
            if status_archived and no_id_leak:
                self.log_result("Soft Delete Template", True, "Template successfully soft deleted (archived)")
            else:
                self.log_result("Soft Delete Template", False, f"Status not archived or _id leak - status: {response_data.get('status')}, no _id: {no_id_leak}")
        else:
            self.log_result("Soft Delete Template", False, f"Request failed with status {status}", response_data)

    async def test_9_hard_delete_template(self):
        """Test 9: DELETE /api/invoice-templates/{tid}/hard -> if not default -> status deleted; if default -> 400"""
        # Create a new non-default template for hard delete test
        create_success, create_data, _ = await self.make_request('POST', '/invoice-templates/create-blank', {'name': 'Test Delete Template'})
        
        if not create_success or not create_data:
            self.log_result("Hard Delete Template", False, "Failed to create test template for deletion")
            return
            
        test_template_id = create_data.get('id')
        
        # Test hard delete on non-default template
        success, response_data, status = await self.make_request('DELETE', f'/invoice-templates/{test_template_id}/hard')
        
        if success and response_data:
            status_deleted = response_data.get('status') == 'deleted'
            no_id_leak = self.validate_no_id_leakage(response_data)
            
            if status_deleted and no_id_leak:
                self.log_result("Hard Delete Template (Non-Default)", True, "Non-default template successfully hard deleted")
            else:
                self.log_result("Hard Delete Template (Non-Default)", False, f"Status not deleted or _id leak - status: {response_data.get('status')}, no _id: {no_id_leak}")
        else:
            self.log_result("Hard Delete Template (Non-Default)", False, f"Request failed with status {status}", response_data)
            
        # Test hard delete on default template (should fail with 400)
        if self.template_id:
            # First make it default again
            await self.make_request('POST', f'/invoice-templates/{self.template_id}/make-default')
            
            success, response_data, status = await self.make_request('DELETE', f'/invoice-templates/{self.template_id}/hard')
            
            if status == 400:
                self.log_result("Hard Delete Template (Default)", True, "Default template correctly rejected for hard deletion (400 error)")
            else:
                self.log_result("Hard Delete Template (Default)", False, f"Expected 400 error for default template deletion, got {status}")

    async def test_sanity_biz_accounts(self):
        """Sanity Check: GET /api/biz-accounts"""
        success, response_data, status = await self.make_request('GET', '/biz-accounts')
        
        if success and isinstance(response_data, list):
            no_id_leak = self.validate_no_id_leakage(response_data)
            iso_dates = self.validate_iso_dates(response_data)
            
            if no_id_leak and iso_dates:
                self.log_result("Sanity Check - Biz Accounts", True, f"Business accounts endpoint working - {len(response_data)} accounts")
            else:
                self.log_result("Sanity Check - Biz Accounts", False, f"Validation failed - no _id: {no_id_leak}, ISO dates: {iso_dates}")
        else:
            self.log_result("Sanity Check - Biz Accounts", False, f"Request failed with status {status}", response_data)

    async def test_sanity_ceo_accounts(self):
        """Sanity Check: GET /api/ceo/accounts"""
        success, response_data, status = await self.make_request('GET', '/ceo/accounts')
        
        if success:
            no_id_leak = self.validate_no_id_leakage(response_data)
            iso_dates = self.validate_iso_dates(response_data)
            
            if no_id_leak and iso_dates:
                self.log_result("Sanity Check - CEO Accounts", True, "CEO accounts endpoint working")
            else:
                self.log_result("Sanity Check - CEO Accounts", False, f"Validation failed - no _id: {no_id_leak}, ISO dates: {iso_dates}")
        else:
            self.log_result("Sanity Check - CEO Accounts", False, f"Request failed with status {status}", response_data)

    async def test_sanity_ai_kb_search(self):
        """Sanity Check: GET /api/ai/kb/local-search?query=test"""
        success, response_data, status = await self.make_request('GET', '/ai/kb/local-search?query=test')
        
        if success:
            no_id_leak = self.validate_no_id_leakage(response_data)
            iso_dates = self.validate_iso_dates(response_data)
            
            if no_id_leak and iso_dates:
                self.log_result("Sanity Check - AI KB Search", True, "AI knowledge base search endpoint working")
            else:
                self.log_result("Sanity Check - AI KB Search", False, f"Validation failed - no _id: {no_id_leak}, ISO dates: {iso_dates}")
        else:
            self.log_result("Sanity Check - AI KB Search", False, f"Request failed with status {status}", response_data)

    async def run_all_tests(self):
        """Run all invoice template regression tests"""
        print("🧪 Starting Invoice Template Regression Test Suite")
        print("=" * 60)
        
        await self.setup()
        
        try:
            # Core invoice template endpoint tests
            await self.test_1_create_blank_template()
            await self.test_2_save_json_template()
            await self.test_3_auto_save_template()
            await self.test_4_save_named_template()
            await self.test_5_make_default_template()
            await self.test_6_cleanup_empty_templates()
            await self.test_7_list_templates_hide_archived()
            await self.test_8_soft_delete_template()
            await self.test_9_hard_delete_template()
            
            # Sanity checks
            await self.test_sanity_biz_accounts()
            await self.test_sanity_ceo_accounts()
            await self.test_sanity_ai_kb_search()
            
        finally:
            await self.cleanup()
            
        # Print summary
        print("=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        
        passed = sum(1 for r in self.results if r['success'])
        total = len(self.results)
        pass_rate = (passed / total * 100) if total > 0 else 0
        
        print(f"Total Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {total - passed}")
        print(f"Pass Rate: {pass_rate:.1f}%")
        print()
        
        # Show failed tests
        failed_tests = [r for r in self.results if not r['success']]
        if failed_tests:
            print("❌ FAILED TESTS:")
            for test in failed_tests:
                print(f"  • {test['test']}: {test['details']}")
        else:
            print("✅ ALL TESTS PASSED!")
            
        return pass_rate >= 80  # Consider 80%+ pass rate as success

async def main():
    """Main test runner"""
    tester = InvoiceTemplateRegressionTest()
    success = await tester.run_all_tests()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())