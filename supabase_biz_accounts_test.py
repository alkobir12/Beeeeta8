#!/usr/bin/env python3
"""
Supabase Mode Test for Biz-Accounts Endpoints
Testing if Supabase integration works when DB_PROVIDER=supabase

This will test:
1. Temporarily switch to supabase mode
2. Test GET /api/biz-accounts returns data from business_accounts table
3. Test POST /api/biz-accounts creates new row in Supabase
4. Switch back to memory mode
"""

import asyncio
import aiohttp
import json
import os
from datetime import datetime
from typing import Dict, Any, List

# Get backend URL from environment
BACKEND_URL = os.getenv('REACT_APP_BACKEND_URL', 'https://stamp-approval-flow.preview.emergentagent.com')
API_BASE = f"{BACKEND_URL}/api"

class SupabaseBizAccountsTester:
    def __init__(self):
        self.session = None
        self.test_results = []
        self.original_db_provider = None
        
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
    
    def read_env_file(self, file_path: str) -> dict:
        """Read .env file and return as dict"""
        env_vars = {}
        try:
            with open(file_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        env_vars[key] = value
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
        return env_vars
    
    def write_env_file(self, file_path: str, env_vars: dict):
        """Write env vars to .env file"""
        try:
            with open(file_path, 'w') as f:
                for key, value in env_vars.items():
                    f.write(f"{key}={value}\n")
        except Exception as e:
            print(f"Error writing {file_path}: {e}")
    
    async def check_supabase_credentials(self):
        """Check if Supabase credentials are configured"""
        print("\n🔍 Checking Supabase credentials...")
        
        env_file = '/app/backend/.env'
        env_vars = self.read_env_file(env_file)
        
        supabase_url = env_vars.get('SUPABASE_URL', '')
        supabase_key = env_vars.get('SUPABASE_SERVICE_ROLE_KEY', '')
        
        if supabase_url and supabase_key:
            self.log_test("Supabase credentials configured", True,
                         f"URL: {supabase_url[:50]}..., Key: {supabase_key[:20]}...")
            return True
        else:
            self.log_test("Supabase credentials configured", False,
                         f"Missing URL: {not supabase_url}, Missing Key: {not supabase_key}")
            return False
    
    async def switch_to_supabase_mode(self):
        """Temporarily switch to Supabase mode"""
        print("\n🔄 Switching to Supabase mode...")
        
        env_file = '/app/backend/.env'
        env_vars = self.read_env_file(env_file)
        
        # Store original value
        self.original_db_provider = env_vars.get('DB_PROVIDER', 'memory')
        
        # Switch to supabase
        env_vars['DB_PROVIDER'] = 'supabase'
        self.write_env_file(env_file, env_vars)
        
        # Restart backend to pick up new env
        import subprocess
        try:
            result = subprocess.run(['sudo', 'supervisorctl', 'restart', 'backend'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                self.log_test("Switch to Supabase mode", True, "Backend restarted successfully")
                # Wait for backend to start
                await asyncio.sleep(3)
                return True
            else:
                self.log_test("Switch to Supabase mode", False, f"Restart failed: {result.stderr}")
                return False
        except Exception as e:
            self.log_test("Switch to Supabase mode", False, f"Restart error: {e}")
            return False
    
    async def switch_back_to_memory_mode(self):
        """Switch back to original mode"""
        print("\n🔄 Switching back to memory mode...")
        
        if self.original_db_provider is None:
            return
        
        env_file = '/app/backend/.env'
        env_vars = self.read_env_file(env_file)
        env_vars['DB_PROVIDER'] = self.original_db_provider
        self.write_env_file(env_file, env_vars)
        
        # Restart backend
        import subprocess
        try:
            result = subprocess.run(['sudo', 'supervisorctl', 'restart', 'backend'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                print("✅ Backend switched back to memory mode")
                await asyncio.sleep(3)
            else:
                print(f"⚠️ Failed to switch back: {result.stderr}")
        except Exception as e:
            print(f"⚠️ Error switching back: {e}")
    
    async def test_supabase_biz_accounts_get(self):
        """Test GET /api/biz-accounts in Supabase mode"""
        print("\n🏢 Testing GET /api/biz-accounts in Supabase mode...")
        
        success, response, status = await self.make_request('GET', '/biz-accounts')
        
        if success and isinstance(response, list):
            self.log_test("GET /api/biz-accounts (Supabase mode)", True,
                         f"Returned {len(response)} accounts from Supabase business_accounts table")
        elif status == 500:
            error_msg = str(response).lower()
            if 'supabase' in error_msg or 'postgres' in error_msg:
                self.log_test("GET /api/biz-accounts (Supabase mode)", False,
                             "Supabase connection error", response)
            else:
                self.log_test("GET /api/biz-accounts (Supabase mode)", False,
                             f"500 error: {response}")
        else:
            self.log_test("GET /api/biz-accounts (Supabase mode)", False,
                         f"Unexpected response - Status: {status}", response)
    
    async def test_supabase_biz_accounts_post(self):
        """Test POST /api/biz-accounts in Supabase mode"""
        print("\n🏢 Testing POST /api/biz-accounts in Supabase mode...")
        
        # Arabic payload
        arabic_payload = {
            "name": "فرع سوبابيس تجريبي",
            "code": "SUPA", 
            "currency": "SAR"
        }
        
        success, response, status = await self.make_request('POST', '/biz-accounts', arabic_payload)
        
        if success and isinstance(response, dict) and 'id' in response:
            arabic_preserved = response.get('name') == "فرع سوبابيس تجريبي"
            self.log_test("POST /api/biz-accounts (Supabase mode)", True,
                         f"Created account in Supabase, Arabic preserved: {arabic_preserved}")
        elif status == 500:
            error_msg = str(response).lower()
            if 'supabase' in error_msg or 'postgres' in error_msg:
                self.log_test("POST /api/biz-accounts (Supabase mode)", False,
                             "Supabase connection/auth error", response)
            else:
                self.log_test("POST /api/biz-accounts (Supabase mode)", False,
                             f"500 error: {response}")
        else:
            self.log_test("POST /api/biz-accounts (Supabase mode)", False,
                         f"Unexpected response - Status: {status}", response)
    
    async def test_supabase_status_endpoint(self):
        """Test Supabase status endpoint"""
        print("\n🔍 Testing Supabase status endpoint...")
        
        success, response, status = await self.make_request('GET', '/supabase/status')
        
        if success and isinstance(response, dict):
            connected = response.get('connected', False)
            mode = response.get('mode', 'unknown')
            self.log_test("GET /api/supabase/status", True,
                         f"Connected: {connected}, Mode: {mode}")
        else:
            self.log_test("GET /api/supabase/status", False,
                         f"Status: {status}", response)
    
    async def run_all_tests(self):
        """Run all Supabase biz-accounts tests"""
        print(f"🚀 Starting Supabase Biz-Accounts Tests")
        print(f"Backend URL: {API_BASE}")
        print("=" * 70)
        
        # Check if Supabase is configured
        if not await self.check_supabase_credentials():
            print("❌ Supabase credentials not configured, skipping Supabase tests")
            return 0, 1, 1
        
        # Test Supabase status first
        await self.test_supabase_status_endpoint()
        
        # Switch to Supabase mode
        if not await self.switch_to_supabase_mode():
            print("❌ Could not switch to Supabase mode, skipping tests")
            return 0, 1, 1
        
        try:
            # Test Supabase endpoints
            await self.test_supabase_biz_accounts_get()
            await self.test_supabase_biz_accounts_post()
            
        finally:
            # Always switch back to memory mode
            await self.switch_back_to_memory_mode()
        
        # Summary
        print("\n" + "=" * 70)
        print("📊 SUPABASE BIZ-ACCOUNTS TEST SUMMARY")
        print("=" * 70)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['success'])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests*100):.1f}%")
        
        if failed_tests > 0:
            print(f"\n❌ DETAILED FAILURES:")
            for result in self.test_results:
                if not result['success']:
                    print(f"   • {result['test']}: {result['details']}")
        
        return passed_tests, failed_tests, total_tests

async def main():
    """Main test execution"""
    async with SupabaseBizAccountsTester() as tester:
        passed, failed, total = await tester.run_all_tests()
        
        # Exit with appropriate code
        if failed == 0:
            print(f"\n🎉 All Supabase tests passed!")
            return 0
        else:
            print(f"\n⚠️  {failed} test(s) failed")
            return 1

if __name__ == "__main__":
    import sys
    exit_code = asyncio.run(main())
    sys.exit(exit_code)