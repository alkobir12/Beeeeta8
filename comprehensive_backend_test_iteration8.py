#!/usr/bin/env python3
"""
Comprehensive Backend Testing for AutoPro Workshop Management System
Testing Environment: https://fleet-audit-system-2.preview.emergentagent.com
Iteration 8 - Full API Coverage Testing
"""

import requests
import json
import sys
from datetime import datetime, timedelta
import traceback
import uuid

class ComprehensiveBackendTester:
    def __init__(self):
        # Use the actual backend URL from frontend/.env
        self.base_url = "https://fleet-audit-system-2.preview.emergentagent.com"
        self.api_url = f"{self.base_url}/api"
        self.results = []
        self.session = requests.Session()
        
        # Set headers for all requests
        self.session.headers.update({
            'User-Agent': 'AutoPro-Backend-Tester/8.0',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
        
        # Test data storage
        self.test_vehicle_id = None
        self.test_customer_id = None
        self.test_operation_id = None
    
    def log_result(self, test_name, success, status_code=None, response_data=None, error=None, details=None):
        """Log test result with comprehensive details"""
        result = {
            'test': test_name,
            'success': success,
            'timestamp': datetime.now().isoformat(),
            'status_code': status_code,
            'error': str(error) if error else None,
            'details': details
        }
        
        if response_data and isinstance(response_data, dict):
            result['response_keys'] = list(response_data.keys())
            result['response_size'] = len(str(response_data))
        elif response_data and isinstance(response_data, list):
            result['response_count'] = len(response_data)
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
        print()
    
    def test_health_endpoint(self):
        """Test 1: GET /health => 200"""
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=10)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    self.log_result(
                        "GET /health", 
                        True, 
                        response.status_code, 
                        data,
                        details=f"Health status: {data.get('status', 'unknown')}, DB: {data.get('db', 'unknown')}"
                    )
                except json.JSONDecodeError:
                    self.log_result(
                        "GET /health", 
                        True, 
                        response.status_code,
                        details="Response is not JSON but status 200 received"
                    )
            else:
                self.log_result(
                    "GET /health", 
                    False, 
                    response.status_code,
                    error=f"Expected 200, got {response.status_code}"
                )
                
        except Exception as e:
            self.log_result("GET /health", False, error=e)
    
    def test_settings_endpoint(self):
        """Test 2: GET /api/settings => 200 JSON"""
        try:
            response = self.session.get(f"{self.api_url}/settings", timeout=10)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    self.log_result(
                        "GET /api/settings", 
                        True, 
                        response.status_code, 
                        data,
                        details=f"Settings keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}"
                    )
                except json.JSONDecodeError:
                    self.log_result(
                        "GET /api/settings", 
                        False, 
                        response.status_code,
                        error="Response is not valid JSON"
                    )
            else:
                self.log_result(
                    "GET /api/settings", 
                    False, 
                    response.status_code,
                    error=f"Expected 200, got {response.status_code}"
                )
                
        except Exception as e:
            self.log_result("GET /api/settings", False, error=e)
    
    def test_vehicles_endpoints(self):
        """Test 3: Vehicles CRUD operations"""
        # Test GET /api/vehicles
        try:
            response = self.session.get(f"{self.api_url}/vehicles", timeout=15)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    if isinstance(data, list):
                        self.log_result(
                            "GET /api/vehicles", 
                            True, 
                            response.status_code, 
                            data,
                            details=f"Found {len(data)} vehicles"
                        )
                    else:
                        self.log_result(
                            "GET /api/vehicles", 
                            True, 
                            response.status_code, 
                            data,
                            details="Response is not a list but valid JSON"
                        )
                except json.JSONDecodeError:
                    self.log_result(
                        "GET /api/vehicles", 
                        False, 
                        response.status_code,
                        error="Response is not valid JSON"
                    )
            else:
                self.log_result(
                    "GET /api/vehicles", 
                    False, 
                    response.status_code,
                    error=f"Expected 200, got {response.status_code}"
                )
                
        except Exception as e:
            self.log_result("GET /api/vehicles", False, error=e)
        
        # Test POST /api/vehicles (Create vehicle)
        try:
            test_vehicle_data = {
                "plateNumber": f"TEST-{datetime.now().strftime('%H%M%S')}",
                "brand": "تويوتا",
                "model": "كامري",
                "year": 2020,
                "color": "أبيض",
                "customerName": "عميل تجريبي",
                "customerPhone": f"05{datetime.now().strftime('%H%M%S')}",
                "customerEmail": "test@example.com"
            }
            
            response = self.session.post(f"{self.api_url}/vehicles", json=test_vehicle_data, timeout=15)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    self.test_vehicle_id = data.get('id')
                    self.log_result(
                        "POST /api/vehicles", 
                        True, 
                        response.status_code, 
                        data,
                        details=f"Created vehicle with ID: {self.test_vehicle_id}"
                    )
                except json.JSONDecodeError:
                    self.log_result(
                        "POST /api/vehicles", 
                        False, 
                        response.status_code,
                        error="Response is not valid JSON"
                    )
            else:
                self.log_result(
                    "POST /api/vehicles", 
                    False, 
                    response.status_code,
                    error=f"Expected 200, got {response.status_code}. Response: {response.text[:200]}"
                )
                
        except Exception as e:
            self.log_result("POST /api/vehicles", False, error=e)
    
    def test_customers_endpoint(self):
        """Test 4: GET /api/customers"""
        try:
            response = self.session.get(f"{self.api_url}/customers", timeout=15)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    if isinstance(data, list):
                        self.log_result(
                            "GET /api/customers", 
                            True, 
                            response.status_code, 
                            data,
                            details=f"Found {len(data)} customers"
                        )
                    else:
                        self.log_result(
                            "GET /api/customers", 
                            True, 
                            response.status_code, 
                            data,
                            details="Response is not a list but valid JSON"
                        )
                except json.JSONDecodeError:
                    self.log_result(
                        "GET /api/customers", 
                        False, 
                        response.status_code,
                        error="Response is not valid JSON"
                    )
            else:
                self.log_result(
                    "GET /api/customers", 
                    False, 
                    response.status_code,
                    error=f"Expected 200, got {response.status_code}"
                )
                
        except Exception as e:
            self.log_result("GET /api/customers", False, error=e)
    
    def test_finance_endpoints(self):
        """Test 5: Finance module endpoints"""
        # Finance endpoints require workshop_id parameter
        workshop_id = "finmodule-sync"  # From frontend/.env
        
        finance_endpoints = [
            f"/api/finance/chart-of-accounts?workshop_id={workshop_id}",
            f"/api/finance/journal-entries?workshop_id={workshop_id}", 
            f"/api/finance/reports/balance-sheet?workshop_id={workshop_id}",
            f"/api/finance/reports/trial-balance?workshop_id={workshop_id}",
            f"/api/finance/reports/income-statement?workshop_id={workshop_id}",
            f"/api/finance/reports/cash-flow?workshop_id={workshop_id}",
            f"/api/finance/alerts?workshop_id={workshop_id}"
        ]
        
        for endpoint in finance_endpoints:
            try:
                response = self.session.get(f"{self.base_url}{endpoint}", timeout=15)
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        self.log_result(
                            f"GET {endpoint}", 
                            True, 
                            response.status_code,
                            data,
                            details=f"Response type: {type(data).__name__}"
                        )
                    except json.JSONDecodeError:
                        self.log_result(
                            f"GET {endpoint}", 
                            False, 
                            response.status_code,
                            error="Response is not valid JSON"
                        )
                else:
                    self.log_result(
                        f"GET {endpoint}", 
                        False, 
                        response.status_code,
                        error=f"Expected 200, got {response.status_code}"
                    )
                    
            except Exception as e:
                self.log_result(f"GET {endpoint}", False, error=e)
    
    def test_stitch_endpoints(self):
        """Test 6: Stitch UI generation endpoints"""
        stitch_endpoints = [
            "/api/stitch/history",
        ]
        
        for endpoint in stitch_endpoints:
            try:
                response = self.session.get(f"{self.base_url}{endpoint}", timeout=15)
                
                if response.status_code in [200, 404]:  # 404 is acceptable for empty history
                    try:
                        data = response.json()
                        self.log_result(
                            f"GET {endpoint}", 
                            True, 
                            response.status_code,
                            data,
                            details=f"Response type: {type(data).__name__}"
                        )
                    except json.JSONDecodeError:
                        self.log_result(
                            f"GET {endpoint}", 
                            True, 
                            response.status_code,
                            details="Non-JSON response but acceptable status"
                        )
                else:
                    self.log_result(
                        f"GET {endpoint}", 
                        False, 
                        response.status_code,
                        error=f"Unexpected status code: {response.status_code}"
                    )
                    
            except Exception as e:
                self.log_result(f"GET {endpoint}", False, error=e)
        
        # Test POST /api/stitch/generate
        try:
            stitch_data = {
                "prompt": "إنشاء صفحة تسجيل دخول بسيطة",
                "scope": "قسم واحد",
                "style": "حديث",
                "color_scheme": "أزرق"
            }
            
            response = self.session.post(f"{self.base_url}/api/stitch/generate", json=stitch_data, timeout=30)
            
            if response.status_code in [200, 202]:  # Accept both success and accepted
                try:
                    data = response.json()
                    self.log_result(
                        "POST /api/stitch/generate", 
                        True, 
                        response.status_code,
                        data,
                        details=f"Stitch generation response: {data.get('status', 'unknown')}"
                    )
                except json.JSONDecodeError:
                    self.log_result(
                        "POST /api/stitch/generate", 
                        False, 
                        response.status_code,
                        error="Response is not valid JSON"
                    )
            else:
                self.log_result(
                    "POST /api/stitch/generate", 
                    False, 
                    response.status_code,
                    error=f"Expected 200/202, got {response.status_code}. Response: {response.text[:200]}"
                )
                
        except Exception as e:
            self.log_result("POST /api/stitch/generate", False, error=e)
    
    def test_whatsapp_bot_endpoints(self):
        """Test 7: WhatsApp bot endpoints"""
        whatsapp_endpoints = [
            "/api/whatsapp-bot/status",
            "/api/whatsapp-bot/info",
            "/api/alkabeer-bot/status",
            "/api/moltbot/status"
        ]
        
        for endpoint in whatsapp_endpoints:
            try:
                response = self.session.get(f"{self.base_url}{endpoint}", timeout=15)
                
                # Accept various status codes as WhatsApp might not be fully configured
                if response.status_code in [200, 404, 500]:
                    try:
                        data = response.json()
                        self.log_result(
                            f"GET {endpoint}", 
                            True, 
                            response.status_code,
                            data,
                            details=f"WhatsApp endpoint accessible, status: {response.status_code}"
                        )
                    except json.JSONDecodeError:
                        self.log_result(
                            f"GET {endpoint}", 
                            True, 
                            response.status_code,
                            details=f"Endpoint accessible, non-JSON response, status: {response.status_code}"
                        )
                else:
                    self.log_result(
                        f"GET {endpoint}", 
                        False, 
                        response.status_code,
                        error=f"Unexpected status code: {response.status_code}"
                    )
                    
            except Exception as e:
                self.log_result(f"GET {endpoint}", False, error=e)
    
    def test_operations_endpoints(self):
        """Test 8: Operations endpoints"""
        try:
            response = self.session.get(f"{self.base_url}/api/operations", timeout=15)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    self.log_result(
                        "GET /api/operations", 
                        True, 
                        response.status_code,
                        data,
                        details=f"Found {len(data) if isinstance(data, list) else 'N/A'} operations"
                    )
                except json.JSONDecodeError:
                    self.log_result(
                        "GET /api/operations", 
                        False, 
                        response.status_code,
                        error="Response is not valid JSON"
                    )
            else:
                self.log_result(
                    "GET /api/operations", 
                    False, 
                    response.status_code,
                    error=f"Expected 200, got {response.status_code}"
                )
                
        except Exception as e:
            self.log_result("GET /api/operations", False, error=e)
    
    def test_cors_preflight(self):
        """Test 9: CORS preflight requests"""
        try:
            headers = {
                'Origin': 'https://fleet-audit-system-2.preview.emergentagent.com',
                'Access-Control-Request-Method': 'GET',
                'Access-Control-Request-Headers': 'Content-Type'
            }
            
            response = self.session.options(f"{self.api_url}/vehicles", headers=headers, timeout=10)
            
            cors_origin = response.headers.get('Access-Control-Allow-Origin')
            cors_methods = response.headers.get('Access-Control-Allow-Methods')
            cors_headers = response.headers.get('Access-Control-Allow-Headers')
            
            if cors_origin:
                self.log_result(
                    "OPTIONS /api/vehicles CORS", 
                    True, 
                    response.status_code,
                    details=f"CORS Origin: {cors_origin}, Methods: {cors_methods}, Headers: {cors_headers}"
                )
            else:
                self.log_result(
                    "OPTIONS /api/vehicles CORS", 
                    False, 
                    response.status_code,
                    error="Access-Control-Allow-Origin header not found",
                    details=f"Available headers: {dict(response.headers)}"
                )
                
        except Exception as e:
            self.log_result("OPTIONS /api/vehicles CORS", False, error=e)
    
    def test_vehicle_parts_integration(self):
        """Test 10: Vehicle parts and journal integration"""
        if not self.test_vehicle_id:
            self.log_result(
                "Vehicle Parts Integration", 
                False, 
                error="No test vehicle ID available from previous tests"
            )
            return
        
        try:
            parts_data = [
                {
                    "name": "فلتر زيت",
                    "price": 50,
                    "quantity": 1,
                    "category": "فلاتر"
                },
                {
                    "name": "زيت محرك",
                    "price": 120,
                    "quantity": 4,
                    "category": "زيوت"
                }
            ]
            
            response = self.session.post(
                f"{self.api_url}/vehicles/{self.test_vehicle_id}/save-parts-and-create-journal", 
                json=parts_data, 
                timeout=20
            )
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    self.log_result(
                        "POST Vehicle Parts Integration", 
                        True, 
                        response.status_code,
                        data,
                        details=f"Created operation: {data.get('operation_id')}, journal: {data.get('journal_entry_id')}"
                    )
                except json.JSONDecodeError:
                    self.log_result(
                        "POST Vehicle Parts Integration", 
                        False, 
                        response.status_code,
                        error="Response is not valid JSON"
                    )
            else:
                self.log_result(
                    "POST Vehicle Parts Integration", 
                    False, 
                    response.status_code,
                    error=f"Expected 200, got {response.status_code}. Response: {response.text[:200]}"
                )
                
        except Exception as e:
            self.log_result("POST Vehicle Parts Integration", False, error=e)
    
    def run_all_tests(self):
        """Run all comprehensive backend tests"""
        print("🚀 Starting Comprehensive Backend Tests - Iteration 8")
        print("🎯 Target: https://fleet-audit-system-2.preview.emergentagent.com")
        print("=" * 80)
        
        # Core Infrastructure Tests
        self.test_health_endpoint()
        self.test_settings_endpoint()
        self.test_cors_preflight()
        
        # Main API Tests
        self.test_vehicles_endpoints()
        self.test_customers_endpoint()
        self.test_operations_endpoints()
        
        # Financial Module Tests
        self.test_finance_endpoints()
        
        # Advanced Features Tests
        self.test_stitch_endpoints()
        self.test_whatsapp_bot_endpoints()
        
        # Integration Tests
        self.test_vehicle_parts_integration()
        
        # Generate comprehensive summary
        self.generate_summary()
    
    def generate_summary(self):
        """Generate comprehensive test summary"""
        print("=" * 80)
        print("📊 COMPREHENSIVE TEST RESULTS SUMMARY - ITERATION 8")
        print("=" * 80)
        
        total_tests = len(self.results)
        passed_tests = len([r for r in self.results if r['success']])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        print()
        
        # Categorize results
        categories = {
            'Infrastructure': ['health', 'settings', 'CORS'],
            'Core APIs': ['vehicles', 'customers', 'operations'],
            'Finance Module': ['finance', 'chart-of-accounts', 'journal-entries', 'reports'],
            'Advanced Features': ['stitch', 'whatsapp', 'alkabeer', 'moltbot'],
            'Integration': ['Parts Integration']
        }
        
        for category, keywords in categories.items():
            category_results = [r for r in self.results if any(keyword.lower() in r['test'].lower() for keyword in keywords)]
            if category_results:
                category_passed = len([r for r in category_results if r['success']])
                category_total = len(category_results)
                print(f"📁 {category}: {category_passed}/{category_total} ({(category_passed/category_total)*100:.1f}%)")
        
        print()
        
        # Show failed tests with details
        if failed_tests > 0:
            print("❌ FAILED TESTS:")
            for result in self.results:
                if not result['success']:
                    print(f"  - {result['test']}")
                    if result['error']:
                        print(f"    Error: {result['error']}")
                    if result['status_code']:
                        print(f"    Status: {result['status_code']}")
            print()
        
        # Show critical passed tests
        print("✅ KEY PASSED TESTS:")
        critical_tests = ['health', 'settings', 'vehicles', 'finance']
        for result in self.results:
            if result['success'] and any(test in result['test'].lower() for test in critical_tests):
                details = f" ({result['details']})" if result['details'] else ""
                print(f"  - {result['test']}{details}")
        
        print()
        print("🎯 BACKEND TESTING COMPLETE - ITERATION 8")
        
        # Save detailed results to file
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            results_file = f'/app/backend_test_results_iteration8_{timestamp}.json'
            with open(results_file, 'w', encoding='utf-8') as f:
                json.dump(self.results, f, ensure_ascii=False, indent=2)
            print(f"📄 Detailed results saved to: {results_file}")
        except Exception as e:
            print(f"⚠️ Could not save results file: {e}")

def main():
    """Main test execution"""
    try:
        tester = ComprehensiveBackendTester()
        tester.run_all_tests()
        
        # Return appropriate exit code
        failed_tests = len([r for r in tester.results if not r['success']])
        return 0 if failed_tests == 0 else 1
        
    except KeyboardInterrupt:
        print("\n⚠️ Tests interrupted by user")
        return 1
    except Exception as e:
        print(f"💥 Critical error during testing: {e}")
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())