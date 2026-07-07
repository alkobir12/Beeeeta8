#!/usr/bin/env python3
"""
Endpoint Verification Test for Workshop Management System
Tests the specific endpoints requested in the review:

GET endpoints that should return data or empty lists without 500 errors:
1. GET /api/operations
2. GET /api/vehicles
3. GET /api/customers
4. GET /api/invoices
5. GET /api/transactions
6. GET /api/technicians
7. GET /api/services
8. GET /api/biz-accounts
9. GET /api/operations/analytics/summary
10. GET /api/operations/pending

POST endpoint:
11. POST /api/vehicles with valid data
"""

import asyncio
import aiohttp
import json
import os
from datetime import datetime
from typing import Dict, Any, List

# Get backend URL from environment
BACKEND_URL = os.getenv('REACT_APP_BACKEND_URL', 'https://accounting-engine-6.preview.emergentagent.com')
API_BASE = f"{BACKEND_URL}/api"

class EndpointVerificationTester:
    def __init__(self):
        self.session = None
        self.test_results = []
        self.created_vehicle_id = None
        
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
    
    async def test_get_endpoints(self):
        """Test all GET endpoints that should return data or empty lists without 500 errors"""
        print("\n🔍 Testing GET Endpoints...")
        
        endpoints_to_test = [
            ('/operations', 'GET /api/operations'),
            ('/vehicles', 'GET /api/vehicles'),
            ('/customers', 'GET /api/customers'),
            ('/invoices', 'GET /api/invoices'),
            ('/transactions', 'GET /api/transactions'),
            ('/technicians', 'GET /api/technicians'),
            ('/services', 'GET /api/services'),
            ('/biz-accounts', 'GET /api/biz-accounts'),
            ('/operations/analytics/summary', 'GET /api/operations/analytics/summary'),
            ('/operations/pending', 'GET /api/operations/pending')
        ]
        
        for endpoint, test_name in endpoints_to_test:
            success, response, status = await self.make_request('GET', endpoint)
            
            if status == 500:
                self.log_test(test_name, False, f"500 Internal Server Error", response)
            elif status == 404:
                self.log_test(test_name, False, f"404 Not Found - endpoint not implemented", response)
            elif success:
                # Check if response is valid (list or dict with expected structure)
                if isinstance(response, list):
                    self.log_test(test_name, True, f"Returned list with {len(response)} items")
                elif isinstance(response, dict):
                    # For analytics endpoints, check for expected keys
                    if 'analytics' in endpoint or 'pending' in endpoint:
                        if 'count' in response or 'total' in response or 'items' in response:
                            self.log_test(test_name, True, f"Returned valid analytics/pending data structure")
                        else:
                            self.log_test(test_name, True, f"Returned dict response: {list(response.keys())}")
                    else:
                        self.log_test(test_name, True, f"Returned dict response: {list(response.keys())}")
                else:
                    self.log_test(test_name, True, f"Returned response type: {type(response)}")
            else:
                self.log_test(test_name, False, f"Status: {status}", response)
    
    async def test_vehicle_creation(self):
        """Test POST /api/vehicles with valid data"""
        print("\n🚗 Testing Vehicle Creation...")
        
        # Test data with Arabic content
        vehicle_data = {
            "plateNumber": "ABC-1234",
            "brand": "تويوتا",
            "model": "كامري",
            "year": 2020,
            "color": "أبيض",
            "customerName": "أحمد محمد",
            "customerPhone": "966501234567",
            "customerEmail": "ahmed@example.com",
            "issue": "فحص دوري",
            "status": "diagnosis",
            "mileage": 50000
        }
        
        success, response, status = await self.make_request('POST', '/vehicles', vehicle_data)
        
        if success and isinstance(response, dict) and 'id' in response:
            self.created_vehicle_id = response['id']
            self.log_test("POST /api/vehicles", True, 
                         f"Created vehicle with ID: {self.created_vehicle_id}, Plate: {response.get('plateNumber')}")
            
            # Verify the created vehicle appears in GET /api/vehicles
            success, vehicles_list, status = await self.make_request('GET', '/vehicles')
            if success and isinstance(vehicles_list, list):
                created_vehicle = next((v for v in vehicles_list if v.get('id') == self.created_vehicle_id), None)
                if created_vehicle:
                    self.log_test("Verify created vehicle in list", True,
                                 f"Found created vehicle in GET /api/vehicles")
                else:
                    self.log_test("Verify created vehicle in list", False,
                                 "Created vehicle not found in vehicles list")
            else:
                self.log_test("Verify created vehicle in list", False,
                             f"Could not fetch vehicles list: {status}")
        else:
            self.log_test("POST /api/vehicles", False, f"Status: {status}", response)
    
    async def test_data_integrity(self):
        """Test data integrity - no _id leakage and proper JSON serialization"""
        print("\n🔍 Testing Data Integrity...")
        
        endpoints_to_check = [
            '/vehicles',
            '/customers',
            '/services',
            '/technicians',
            '/biz-accounts'
        ]
        
        for endpoint in endpoints_to_check:
            success, response, status = await self.make_request('GET', endpoint)
            if success and isinstance(response, list):
                has_id_leak = False
                has_serialization_issues = False
                
                for item in response[:3]:  # Check first 3 items
                    if isinstance(item, dict):
                        # Check for _id leakage
                        if '_id' in item:
                            has_id_leak = True
                        
                        # Check for proper date serialization (should be ISO strings, not objects)
                        for key, value in item.items():
                            if key.endswith('Date') or key.endswith('At'):
                                if value and not isinstance(value, str):
                                    has_serialization_issues = True
                
                if has_id_leak:
                    self.log_test(f"No _id leakage in {endpoint}", False, "Found _id field in response")
                else:
                    self.log_test(f"No _id leakage in {endpoint}", True, "No _id fields found")
                
                if has_serialization_issues:
                    self.log_test(f"Proper date serialization in {endpoint}", False, "Found non-string date fields")
                else:
                    self.log_test(f"Proper date serialization in {endpoint}", True, "All date fields properly serialized")
            else:
                self.log_test(f"Data integrity check for {endpoint}", False, f"Could not test - endpoint failed: {status}")
    
    async def run_all_tests(self):
        """Run all endpoint verification tests"""
        print(f"🚀 Starting Endpoint Verification Tests")
        print(f"Backend URL: {API_BASE}")
        print(f"DB Provider: memory (as per .env)")
        print("=" * 60)
        
        # Run all test suites
        await self.test_get_endpoints()
        await self.test_vehicle_creation()
        await self.test_data_integrity()
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['success'])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests*100):.1f}%")
        
        if failed_tests > 0:
            print(f"\n❌ FAILED TESTS:")
            for result in self.test_results:
                if not result['success']:
                    print(f"   • {result['test']}: {result['details']}")
        
        # Specific analysis for the review request
        print(f"\n📋 REVIEW REQUEST ANALYSIS:")
        print("=" * 40)
        
        # Check the 10 GET endpoints
        get_endpoints = [
            'GET /api/operations',
            'GET /api/vehicles', 
            'GET /api/customers',
            'GET /api/invoices',
            'GET /api/transactions',
            'GET /api/technicians',
            'GET /api/services',
            'GET /api/biz-accounts',
            'GET /api/operations/analytics/summary',
            'GET /api/operations/pending'
        ]
        
        get_passed = sum(1 for result in self.test_results 
                        if result['test'] in get_endpoints and result['success'])
        
        print(f"GET Endpoints (10 total): {get_passed}/10 passed")
        
        # Check vehicle creation
        vehicle_creation_passed = any(result['test'] == 'POST /api/vehicles' and result['success'] 
                                    for result in self.test_results)
        print(f"Vehicle Creation: {'✅ PASSED' if vehicle_creation_passed else '❌ FAILED'}")
        
        return passed_tests, failed_tests, total_tests

async def main():
    """Main test execution"""
    async with EndpointVerificationTester() as tester:
        passed, failed, total = await tester.run_all_tests()
        
        # Exit with appropriate code
        if failed == 0:
            print(f"\n🎉 All endpoint verification tests passed!")
            return 0
        else:
            print(f"\n⚠️  {failed} test(s) failed")
            return 1

if __name__ == "__main__":
    import sys
    exit_code = asyncio.run(main())
    sys.exit(exit_code)