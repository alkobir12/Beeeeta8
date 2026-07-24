#!/usr/bin/env python3
"""
Arabic Review Request Backend Testing - Sync Visits Issue
اختبر في preview domain (REACT_APP_BACKEND_URL) مشكلة sync visits:

1) POST /api/vehicles/{vehicle_id}/visits مع notes تحتوي items.
2) تحقق أن العملية المالية تنخلق بدون خطأ uuid.
3) GET /api/visits/{visit_id}/operations يرجع array non-empty.

رجع تقرير pass/fail.
"""

import requests
import json
import sys
import uuid
from datetime import datetime
import traceback

class SyncVisitsBackendTester:
    def __init__(self):
        # Use the preview domain from frontend/.env
        self.base_url = "https://stamp-approval-flow.preview.emergentagent.com"
        self.api_url = f"{self.base_url}/api"
        self.results = []
        self.session = requests.Session()
        
        # Set headers for all requests
        self.session.headers.update({
            'User-Agent': 'SyncVisits-Tester/1.0',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
        
        # Test vehicle ID - using a known vehicle from previous tests
        self.test_vehicle_id = "f3422cc1-dd9c-4e69-8205-0aa50b3795a1"
        self.created_visit_id = None
    
    def log_result(self, test_name, success, status_code=None, response_data=None, error=None, details=None):
        """Log test result"""
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
    
    def test_1_post_vehicle_visits_with_items(self):
        """Test 1: POST /api/vehicles/{vehicle_id}/visits مع notes تحتوي items"""
        try:
            url = f"{self.api_url}/vehicles/{self.test_vehicle_id}/visits"
            
            # Create visit payload with items in notes
            visit_payload = {
                "status": "in_progress",
                "mileage": 75000,
                "notes": {
                    "items": [
                        {
                            "itemType": "service",
                            "name": "خدمة صيانة تجريبية",
                            "quantity": 1,
                            "price": 150
                        },
                        {
                            "itemType": "part", 
                            "name": "فلتر زيت",
                            "quantity": 2,
                            "price": 45
                        }
                    ]
                }
            }
            
            print(f"🧪 Test 1: POST {url}")
            print(f"📝 Payload: {json.dumps(visit_payload, ensure_ascii=False, indent=2)}")
            
            response = self.session.post(url, json=visit_payload, timeout=15)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    visit_id = data.get('id')
                    
                    if visit_id:
                        self.created_visit_id = visit_id
                        self.log_result(
                            "POST /api/vehicles/{vehicle_id}/visits with items",
                            True,
                            response.status_code,
                            data,
                            details=f"Visit created successfully with ID: {visit_id}"
                        )
                    else:
                        self.log_result(
                            "POST /api/vehicles/{vehicle_id}/visits with items",
                            False,
                            response.status_code,
                            data,
                            error="Visit ID not returned in response"
                        )
                        
                except json.JSONDecodeError:
                    self.log_result(
                        "POST /api/vehicles/{vehicle_id}/visits with items",
                        False,
                        response.status_code,
                        error="Response is not valid JSON"
                    )
            else:
                try:
                    error_data = response.json()
                    self.log_result(
                        "POST /api/vehicles/{vehicle_id}/visits with items",
                        False,
                        response.status_code,
                        error=f"HTTP {response.status_code}: {error_data.get('detail', 'Unknown error')}"
                    )
                except:
                    self.log_result(
                        "POST /api/vehicles/{vehicle_id}/visits with items",
                        False,
                        response.status_code,
                        error=f"HTTP {response.status_code}: {response.text[:200]}"
                    )
                    
        except Exception as e:
            self.log_result(
                "POST /api/vehicles/{vehicle_id}/visits with items",
                False,
                error=e
            )
    
    def test_2_verify_financial_operation_created(self):
        """Test 2: تحقق أن العملية المالية تنخلق بدون خطأ uuid"""
        if not self.created_visit_id:
            self.log_result(
                "Verify financial operation created without UUID error",
                False,
                error="No visit ID available from previous test"
            )
            return
        
        try:
            # Wait a moment for sync to complete
            import time
            time.sleep(2)
            
            url = f"{self.api_url}/visits/{self.created_visit_id}/operations"
            
            print(f"🧪 Test 2: GET {url}")
            
            response = self.session.get(url, timeout=15)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    
                    if isinstance(data, list):
                        if len(data) > 0:
                            # Check if operations contain valid UUIDs and no UUID errors
                            operation = data[0]
                            operation_id = operation.get('id')
                            
                            # Verify UUID format
                            try:
                                uuid.UUID(operation_id)
                                uuid_valid = True
                            except (ValueError, TypeError):
                                uuid_valid = False
                            
                            if uuid_valid:
                                self.log_result(
                                    "Verify financial operation created without UUID error",
                                    True,
                                    response.status_code,
                                    data,
                                    details=f"Operation created with valid UUID: {operation_id}, Total operations: {len(data)}"
                                )
                            else:
                                self.log_result(
                                    "Verify financial operation created without UUID error",
                                    False,
                                    response.status_code,
                                    data,
                                    error=f"Operation has invalid UUID: {operation_id}"
                                )
                        else:
                            self.log_result(
                                "Verify financial operation created without UUID error",
                                False,
                                response.status_code,
                                data,
                                error="No operations found for the visit"
                            )
                    else:
                        self.log_result(
                            "Verify financial operation created without UUID error",
                            False,
                            response.status_code,
                            data,
                            error="Response is not an array"
                        )
                        
                except json.JSONDecodeError:
                    self.log_result(
                        "Verify financial operation created without UUID error",
                        False,
                        response.status_code,
                        error="Response is not valid JSON"
                    )
            else:
                try:
                    error_data = response.json()
                    self.log_result(
                        "Verify financial operation created without UUID error",
                        False,
                        response.status_code,
                        error=f"HTTP {response.status_code}: {error_data.get('detail', 'Unknown error')}"
                    )
                except:
                    self.log_result(
                        "Verify financial operation created without UUID error",
                        False,
                        response.status_code,
                        error=f"HTTP {response.status_code}: {response.text[:200]}"
                    )
                    
        except Exception as e:
            self.log_result(
                "Verify financial operation created without UUID error",
                False,
                error=e
            )
    
    def test_3_get_visit_operations_non_empty(self):
        """Test 3: GET /api/visits/{visit_id}/operations يرجع array non-empty"""
        if not self.created_visit_id:
            self.log_result(
                "GET /api/visits/{visit_id}/operations returns non-empty array",
                False,
                error="No visit ID available from previous test"
            )
            return
        
        try:
            url = f"{self.api_url}/visits/{self.created_visit_id}/operations"
            
            print(f"🧪 Test 3: GET {url}")
            
            response = self.session.get(url, timeout=15)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    
                    if isinstance(data, list) and len(data) > 0:
                        # Verify operation structure
                        operation = data[0]
                        required_fields = ['id', 'type', 'total', 'visit_id']
                        missing_fields = [field for field in required_fields if field not in operation]
                        
                        if not missing_fields:
                            self.log_result(
                                "GET /api/visits/{visit_id}/operations returns non-empty array",
                                True,
                                response.status_code,
                                data,
                                details=f"Found {len(data)} operations with valid structure. First operation total: {operation.get('total', 0)}"
                            )
                        else:
                            self.log_result(
                                "GET /api/visits/{visit_id}/operations returns non-empty array",
                                False,
                                response.status_code,
                                data,
                                error=f"Operation missing required fields: {missing_fields}"
                            )
                    elif isinstance(data, list) and len(data) == 0:
                        self.log_result(
                            "GET /api/visits/{visit_id}/operations returns non-empty array",
                            False,
                            response.status_code,
                            data,
                            error="Operations array is empty"
                        )
                    else:
                        self.log_result(
                            "GET /api/visits/{visit_id}/operations returns non-empty array",
                            False,
                            response.status_code,
                            data,
                            error="Response is not an array"
                        )
                        
                except json.JSONDecodeError:
                    self.log_result(
                        "GET /api/visits/{visit_id}/operations returns non-empty array",
                        False,
                        response.status_code,
                        error="Response is not valid JSON"
                    )
            else:
                try:
                    error_data = response.json()
                    self.log_result(
                        "GET /api/visits/{visit_id}/operations returns non-empty array",
                        False,
                        response.status_code,
                        error=f"HTTP {response.status_code}: {error_data.get('detail', 'Unknown error')}"
                    )
                except:
                    self.log_result(
                        "GET /api/visits/{visit_id}/operations returns non-empty array",
                        False,
                        response.status_code,
                        error=f"HTTP {response.status_code}: {response.text[:200]}"
                    )
                    
        except Exception as e:
            self.log_result(
                "GET /api/visits/{visit_id}/operations returns non-empty array",
                False,
                error=e
            )
    
    def run_all_tests(self):
        """Run all sync visits tests"""
        print("🚀 Starting Sync Visits Backend Tests")
        print("=" * 60)
        print(f"🎯 Target: {self.base_url}")
        print(f"🚗 Test Vehicle ID: {self.test_vehicle_id}")
        print("=" * 60)
        
        # Test 1: Create visit with items
        self.test_1_post_vehicle_visits_with_items()
        
        # Test 2: Verify financial operation created without UUID error
        self.test_2_verify_financial_operation_created()
        
        # Test 3: Verify operations endpoint returns non-empty array
        self.test_3_get_visit_operations_non_empty()
        
        # Generate summary
        self.generate_summary()
    
    def generate_summary(self):
        """Generate test summary"""
        print("=" * 60)
        print("📊 SYNC VISITS TEST RESULTS SUMMARY")
        print("=" * 60)
        
        total_tests = len(self.results)
        passed_tests = len([r for r in self.results if r['success']])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        print()
        
        # Show results in Arabic format
        print("📋 تقرير النتائج (Pass/Fail Report):")
        print("-" * 40)
        
        for result in self.results:
            status_ar = "نجح ✅" if result['success'] else "فشل ❌"
            test_name_ar = result['test']
            if "POST" in test_name_ar and "visits" in test_name_ar:
                test_name_ar = "إنشاء زيارة مع البنود"
            elif "financial operation" in test_name_ar:
                test_name_ar = "إنشاء العملية المالية بدون خطأ UUID"
            elif "operations returns non-empty" in test_name_ar:
                test_name_ar = "استرجاع العمليات المالية (غير فارغ)"
            
            print(f"{status_ar} {test_name_ar}")
            if result['details']:
                print(f"    التفاصيل: {result['details']}")
            if result['error']:
                print(f"    الخطأ: {result['error']}")
        
        print()
        
        # Overall result
        if failed_tests == 0:
            print("🎉 النتيجة النهائية: جميع الاختبارات نجحت - مشكلة sync visits محلولة")
            print("🎉 FINAL RESULT: ALL TESTS PASSED - Sync visits issue resolved")
        else:
            print("⚠️ النتيجة النهائية: يوجد مشاكل في sync visits تحتاج إصلاح")
            print("⚠️ FINAL RESULT: Sync visits issues found - needs fixing")
        
        print()
        
        # Show created visit ID for reference
        if self.created_visit_id:
            print(f"🆔 Visit ID Created: {self.created_visit_id}")
        
        # Save detailed results to file
        try:
            with open('/app/sync_visits_test_results.json', 'w', encoding='utf-8') as f:
                json.dump(self.results, f, ensure_ascii=False, indent=2)
            print("📄 Detailed results saved to: /app/sync_visits_test_results.json")
        except Exception as e:
            print(f"⚠️ Could not save results file: {e}")

def main():
    """Main test execution"""
    try:
        tester = SyncVisitsBackendTester()
        tester.run_all_tests()
        
        # Return appropriate exit code
        failed_tests = len([r for r in tester.results if not r['success']])
        sys.exit(1 if failed_tests > 0 else 0)
        
    except KeyboardInterrupt:
        print("\n⚠️ Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"💥 Critical error during testing: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()