#!/usr/bin/env python3
"""
Focused Backend Test for Biz-Accounts Endpoints
Testing the new branch routes after Supabase integration as requested in Arabic review:

1. GET /api/biz-accounts in memory mode - should return [] without 500
2. POST /api/biz-accounts with Arabic payload in memory mode - should return mock object without Mongo connection
3. POST /api/biz-accounts/cleanup in memory mode - should return {kept: [], dropped: [], created: []} without 500
4. Focus: Did SSL/Mongo errors disappear for biz-accounts requests in memory mode?
"""

import asyncio
import aiohttp
import json
import os
from datetime import datetime
from typing import Dict, Any, List

# Get backend URL from environment
BACKEND_URL = os.getenv('REACT_APP_BACKEND_URL', 'https://financial-ssot.preview.emergentagent.com')
API_BASE = f"{BACKEND_URL}/api"

class BizAccountsTester:
    def __init__(self):
        self.session = None
        self.test_results = []
        self.created_account_id = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def log_test(self, test_name: str, success: bool, details: str = "", response_data: Any = None):
        """Log test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {test_name}")
        if details:
            print(f"   Details: {details}")
        if response_data and isinstance(response_data, dict):
            if 'error' in response_data or 'detail' in response_data:
                print(f"   Error: {response_data}")
        
        self.test_results.append({
            'test': test_name,
            'success': success,
            'details': details,
            'response': response_data
        })
    
    async def make_request(self, method: str, endpoint: str, data: Dict = None, params: Dict = None) -> tuple:
        """Make HTTP request and return (success, response_data, status_code)"""
        url = f"{API_BASE}{endpoint}"
        try:
            kwargs = {}
            if data:
                kwargs['json'] = data
            if params:
                kwargs['params'] = params
                
            async with self.session.request(method, url, **kwargs) as response:
                try:
                    response_data = await response.json()
                except:
                    response_data = await response.text()
                
                return response.status < 400, response_data, response.status
        except Exception as e:
            return False, {"error": str(e)}, 0
    
    async def test_get_biz_accounts_memory_mode(self):
        """Test GET /api/biz-accounts in memory mode - should return [] without 500"""
        print("\n🏢 Testing GET /api/biz-accounts in memory mode...")
        
        success, response, status = await self.make_request('GET', '/biz-accounts')
        
        if status == 500:
            self.log_test("GET /api/biz-accounts (no 500 error)", False, 
                         f"Returned 500 error - SSL/Mongo connection issue still exists", response)
        elif success and isinstance(response, list):
            self.log_test("GET /api/biz-accounts (no 500 error)", True,
                         f"Returned list with {len(response)} accounts - no SSL/Mongo errors")
        elif status == 404:
            self.log_test("GET /api/biz-accounts (no 500 error)", False,
                         "Endpoint not found (404) - implementation missing", response)
        else:
            self.log_test("GET /api/biz-accounts (no 500 error)", False,
                         f"Unexpected response - Status: {status}", response)
    
    async def test_post_biz_accounts_memory_mode(self):
        """Test POST /api/biz-accounts with Arabic payload in memory mode"""
        print("\n🏢 Testing POST /api/biz-accounts with Arabic data in memory mode...")
        
        # Arabic payload as specified in review request
        arabic_payload = {
            "name": "فرع تجريبي",
            "code": "TEST", 
            "currency": "SAR"
        }
        
        success, response, status = await self.make_request('POST', '/biz-accounts', arabic_payload)
        
        if status == 500:
            # Check if it's SSL/Mongo error
            error_msg = str(response).lower()
            if 'ssl' in error_msg or 'mongo' in error_msg or 'tlsv1_alert' in error_msg:
                self.log_test("POST /api/biz-accounts (no SSL/Mongo errors)", False,
                             "SSL/Mongo connection error still exists in memory mode", response)
            else:
                self.log_test("POST /api/biz-accounts (no SSL/Mongo errors)", False,
                             f"500 error but not SSL/Mongo related", response)
        elif success and isinstance(response, dict) and 'id' in response:
            self.created_account_id = response.get('id')
            # Verify Arabic content preserved
            arabic_preserved = response.get('name') == "فرع تجريبي"
            self.log_test("POST /api/biz-accounts (no SSL/Mongo errors)", True,
                         f"Created account ID: {self.created_account_id}, Arabic preserved: {arabic_preserved}")
        elif status == 404:
            self.log_test("POST /api/biz-accounts (no SSL/Mongo errors)", False,
                         "Endpoint not found (404) - implementation missing", response)
        else:
            self.log_test("POST /api/biz-accounts (no SSL/Mongo errors)", False,
                         f"Unexpected response - Status: {status}", response)
    
    async def test_post_biz_accounts_cleanup_memory_mode(self):
        """Test POST /api/biz-accounts/cleanup in memory mode"""
        print("\n🏢 Testing POST /api/biz-accounts/cleanup in memory mode...")
        
        success, response, status = await self.make_request('POST', '/biz-accounts/cleanup')
        
        if status == 500:
            # Check if it's SSL/Mongo error
            error_msg = str(response).lower()
            if 'ssl' in error_msg or 'mongo' in error_msg or 'tlsv1_alert' in error_msg:
                self.log_test("POST /api/biz-accounts/cleanup (no SSL/Mongo errors)", False,
                             "SSL/Mongo connection error still exists in memory mode", response)
            else:
                self.log_test("POST /api/biz-accounts/cleanup (no SSL/Mongo errors)", False,
                             f"500 error but not SSL/Mongo related", response)
        elif success and isinstance(response, dict):
            # Check for expected structure in memory mode
            has_expected_structure = 'status' in response and response.get('status') == 'ok'
            if has_expected_structure:
                final_accounts = response.get('final', [])
                self.log_test("POST /api/biz-accounts/cleanup (no SSL/Mongo errors)", True,
                             f"Cleanup successful, final accounts: {len(final_accounts)}")
            else:
                self.log_test("POST /api/biz-accounts/cleanup (no SSL/Mongo errors)", True,
                             f"No 500 error, response structure: {list(response.keys())}")
        elif status == 404:
            self.log_test("POST /api/biz-accounts/cleanup (no SSL/Mongo errors)", False,
                         "Endpoint not found (404) - implementation missing", response)
        else:
            self.log_test("POST /api/biz-accounts/cleanup (no SSL/Mongo errors)", False,
                         f"Unexpected response - Status: {status}", response)
    
    async def test_check_db_provider_mode(self):
        """Verify we're running in memory mode as expected"""
        print("\n🔍 Checking DB_PROVIDER mode...")
        
        # Try to get a simple endpoint to check if we're in memory mode
        success, response, status = await self.make_request('GET', '/services')
        
        if success:
            # In memory mode, services should return a small seeded list
            if isinstance(response, list) and len(response) <= 10:
                self.log_test("DB_PROVIDER=memory mode confirmed", True,
                             f"Services returned {len(response)} items (typical for memory mode)")
            else:
                self.log_test("DB_PROVIDER=memory mode confirmed", False,
                             f"Services returned {len(response) if isinstance(response, list) else 'non-list'} - might not be memory mode")
        else:
            self.log_test("DB_PROVIDER=memory mode confirmed", False,
                         f"Could not verify mode - services endpoint failed: {status}")
    
    async def test_no_mongo_ssl_errors_in_logs(self):
        """Test that endpoints don't generate SSL/Mongo errors in memory mode"""
        print("\n🔍 Testing multiple endpoints for SSL/Mongo error absence...")
        
        endpoints_to_test = [
            '/biz-accounts',
            '/services', 
            '/parts',
            '/operations'
        ]
        
        ssl_mongo_errors_found = 0
        
        for endpoint in endpoints_to_test:
            success, response, status = await self.make_request('GET', endpoint)
            
            if status == 500:
                error_msg = str(response).lower()
                if any(keyword in error_msg for keyword in ['ssl', 'mongo', 'tlsv1_alert', 'handshake']):
                    ssl_mongo_errors_found += 1
                    print(f"   ❌ {endpoint}: SSL/Mongo error detected")
                else:
                    print(f"   ⚠️  {endpoint}: 500 error but not SSL/Mongo related")
            else:
                print(f"   ✅ {endpoint}: No SSL/Mongo errors (status: {status})")
        
        self.log_test("No SSL/Mongo errors across endpoints", ssl_mongo_errors_found == 0,
                     f"Found SSL/Mongo errors in {ssl_mongo_errors_found} endpoints" if ssl_mongo_errors_found > 0 else "No SSL/Mongo errors detected")
    
    async def run_all_tests(self):
        """Run all biz-accounts focused tests"""
        print(f"🚀 Starting Biz-Accounts Focused Tests (Memory Mode)")
        print(f"Backend URL: {API_BASE}")
        print("=" * 70)
        
        # Check DB provider mode first
        await self.test_check_db_provider_mode()
        
        # Test the specific endpoints mentioned in review
        await self.test_get_biz_accounts_memory_mode()
        await self.test_post_biz_accounts_memory_mode()
        await self.test_post_biz_accounts_cleanup_memory_mode()
        
        # Check for SSL/Mongo errors across multiple endpoints
        await self.test_no_mongo_ssl_errors_in_logs()
        
        # Summary
        print("\n" + "=" * 70)
        print("📊 BIZ-ACCOUNTS TEST SUMMARY")
        print("=" * 70)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['success'])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests*100):.1f}%")
        
        # Key findings for the review request
        print(f"\n🎯 KEY FINDINGS FOR REVIEW REQUEST:")
        print("=" * 70)
        
        ssl_mongo_issues = []
        endpoints_working = []
        
        for result in self.test_results:
            if 'SSL/Mongo' in result['test']:
                if result['success']:
                    endpoints_working.append(result['test'])
                else:
                    ssl_mongo_issues.append(result['test'])
        
        if not ssl_mongo_issues:
            print("✅ SUCCESS: No SSL/Mongo errors found in biz-accounts endpoints in memory mode")
            print("✅ SUCCESS: All endpoints respond without 500 errors")
        else:
            print("❌ ISSUE: SSL/Mongo errors still present in:")
            for issue in ssl_mongo_issues:
                print(f"   • {issue}")
        
        if failed_tests > 0:
            print(f"\n❌ DETAILED FAILURES:")
            for result in self.test_results:
                if not result['success']:
                    print(f"   • {result['test']}: {result['details']}")
        
        return passed_tests, failed_tests, total_tests

async def main():
    """Main test execution"""
    async with BizAccountsTester() as tester:
        passed, failed, total = await tester.run_all_tests()
        
        # Exit with appropriate code
        if failed == 0:
            print(f"\n🎉 All biz-accounts tests passed!")
            return 0
        else:
            print(f"\n⚠️  {failed} test(s) failed")
            return 1

if __name__ == "__main__":
    import sys
    exit_code = asyncio.run(main())
    sys.exit(exit_code)