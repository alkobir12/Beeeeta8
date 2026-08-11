#!/usr/bin/env python3
"""
Backend API Testing Script for Arabic Requirements

Testing the following features:
1. POST /api/operations works without 500 error with accountingAccountId=5000
2. Verify Rakan entries separation via GET /api/finance/journal-entries (include_rakan parameter)
3. User authentication and permissions system
4. Finance APIs for receivables data
"""

import requests
import json
import sys
from typing import Dict, Any
from datetime import datetime

class ArabicRequirementsAPITester:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        self.workshop_id = "finmodule-sync"  # From backend/.env

    def test_operations_with_rakan_account(self) -> Dict[str, Any]:
        """Test POST /api/operations with accountingAccountId=5000 (Rakan account)"""
        print("🔍 Testing: POST /api/operations with accountingAccountId=5000")
        
        try:
            # Test data for Rakan parts operation
            operation_data = {
                "type": "purchase",
                "partnerName": "مورد قطع راكان",
                "total": 1500.0,
                "accountingAccountId": "5000",
                "paymentMethod": "cash",
                "date": datetime.now().isoformat(),
                "notes": "شراء قطع غيار راكان",
                "scope": "rakan_parts",
                "businessUnit": "rakan_parts"
            }
            
            response = self.session.post(
                f"{self.base_url}/api/operations", 
                json=operation_data
            )
            
            result = {
                "endpoint": "POST /api/operations",
                "test": "rakan_account_5000",
                "status_code": response.status_code,
                "success": False,
                "issues": []
            }
            
            # Check that we don't get a 500 error
            if response.status_code == 500:
                result["issues"].append("Got 500 error when creating operation with accountingAccountId=5000")
                try:
                    error_data = response.json()
                    result["error_details"] = error_data
                except:
                    result["error_details"] = response.text
                return result
            
            # Accept 200, 201, or other success codes
            if response.status_code not in [200, 201]:
                result["issues"].append(f"Unexpected status code {response.status_code}, expected 200/201")
                try:
                    error_data = response.json()
                    result["error_details"] = error_data
                except:
                    result["error_details"] = response.text
                return result
                
            try:
                data = response.json()
                result["data"] = data
                result["operation_id"] = data.get("id") if isinstance(data, dict) else None
            except json.JSONDecodeError as e:
                result["issues"].append(f"Invalid JSON response: {e}")
                return result
                
            result["success"] = True
            print("✅ Operations API with Rakan Account: PASSED - No 500 error")
            print(f"   - Status: {response.status_code}")
            if result.get("operation_id"):
                print(f"   - Operation ID: {result['operation_id']}")
                
            return result
            
        except requests.exceptions.RequestException as e:
            result = {
                "endpoint": "POST /api/operations",
                "test": "rakan_account_5000",
                "status_code": None,
                "success": False,
                "issues": [f"Request failed: {e}"]
            }
            print("❌ Operations API with Rakan Account: FAILED - Request error")
            print(f"   - {e}")
            return result

    def test_journal_entries_rakan_separation(self) -> Dict[str, Any]:
        """Test GET /api/finance/journal-entries with include_rakan parameter"""
        print("🔍 Testing: GET /api/finance/journal-entries (Rakan separation)")
        
        results = {
            "endpoint": "GET /api/finance/journal-entries",
            "test": "rakan_separation",
            "success": False,
            "issues": [],
            "tests": {}
        }
        
        try:
            # Test 1: include_rakan=false (should not show Rakan entries)
            print("   Testing include_rakan=false...")
            response_false = self.session.get(
                f"{self.base_url}/api/finance/journal-entries",
                params={
                    "workshop_id": self.workshop_id,
                    "include_rakan": "false",
                    "limit": 50
                }
            )
            
            results["tests"]["include_rakan_false"] = {
                "status_code": response_false.status_code,
                "success": False,
                "issues": []
            }
            
            if response_false.status_code != 200:
                results["tests"]["include_rakan_false"]["issues"].append(
                    f"Status code {response_false.status_code}, expected 200"
                )
            else:
                try:
                    data_false = response_false.json()
                    results["tests"]["include_rakan_false"]["data"] = data_false
                    results["tests"]["include_rakan_false"]["success"] = True
                    print(f"     ✅ include_rakan=false: {len(data_false.get('data', []))} entries")
                except json.JSONDecodeError as e:
                    results["tests"]["include_rakan_false"]["issues"].append(f"Invalid JSON: {e}")
            
            # Test 2: include_rakan=true (should show Rakan entries)
            print("   Testing include_rakan=true...")
            response_true = self.session.get(
                f"{self.base_url}/api/finance/journal-entries",
                params={
                    "workshop_id": self.workshop_id,
                    "include_rakan": "true",
                    "limit": 50
                }
            )
            
            results["tests"]["include_rakan_true"] = {
                "status_code": response_true.status_code,
                "success": False,
                "issues": []
            }
            
            if response_true.status_code != 200:
                results["tests"]["include_rakan_true"]["issues"].append(
                    f"Status code {response_true.status_code}, expected 200"
                )
            else:
                try:
                    data_true = response_true.json()
                    results["tests"]["include_rakan_true"]["data"] = data_true
                    results["tests"]["include_rakan_true"]["success"] = True
                    print(f"     ✅ include_rakan=true: {len(data_true.get('data', []))} entries")
                except json.JSONDecodeError as e:
                    results["tests"]["include_rakan_true"]["issues"].append(f"Invalid JSON: {e}")
            
            # Check if both tests passed
            both_passed = (
                results["tests"]["include_rakan_false"]["success"] and 
                results["tests"]["include_rakan_true"]["success"]
            )
            
            if both_passed:
                # Compare entry counts (true should >= false, indicating Rakan entries exist)
                count_false = len(results["tests"]["include_rakan_false"]["data"].get("data", []))
                count_true = len(results["tests"]["include_rakan_true"]["data"].get("data", []))
                
                if count_true >= count_false:
                    results["success"] = True
                    print("✅ Journal Entries Rakan Separation: PASSED")
                    print(f"   - Without Rakan: {count_false} entries")
                    print(f"   - With Rakan: {count_true} entries")
                else:
                    results["issues"].append(
                        f"Expected include_rakan=true ({count_true}) >= include_rakan=false ({count_false})"
                    )
            else:
                results["issues"].append("One or both API calls failed")
                
        except requests.exceptions.RequestException as e:
            results["issues"].append(f"Request failed: {e}")
            
        if not results["success"]:
            print("❌ Journal Entries Rakan Separation: FAILED")
            for issue in results["issues"]:
                print(f"   - {issue}")
                
        return results

    def test_users_api(self) -> Dict[str, Any]:
        """Test GET /api/users for permissions system"""
        print("🔍 Testing: GET /api/users (permissions system)")
        
        try:
            response = self.session.get(f"{self.base_url}/api/users")
            
            result = {
                "endpoint": "GET /api/users",
                "test": "permissions_system",
                "status_code": response.status_code,
                "success": False,
                "issues": []
            }
            
            if response.status_code != 200:
                result["issues"].append(f"Status code {response.status_code}, expected 200")
                return result
                
            try:
                data = response.json()
                result["data"] = data
            except json.JSONDecodeError as e:
                result["issues"].append(f"Invalid JSON response: {e}")
                return result
            
            # Check if users have role and permissions structure
            if isinstance(data, list) and len(data) > 0:
                # Check for manager user
                manager_user = None
                for user in data:
                    if user.get("name") == "مدير" or user.get("role") == "manager":
                        manager_user = user
                        break
                
                if manager_user:
                    result["manager_found"] = True
                    print(f"   ✅ Found manager user: {manager_user.get('name', 'N/A')}")
                else:
                    result["manager_found"] = False
                    print("   ⚠️ No manager user found")
                
                # Check permissions structure
                sample_user = data[0]
                if "permissions" in sample_user or "role" in sample_user:
                    result["permissions_structure"] = True
                    print("   ✅ Users have permissions/role structure")
                else:
                    result["permissions_structure"] = False
                    result["issues"].append("Users missing permissions/role structure")
            else:
                result["issues"].append("No users found or invalid data structure")
                
            if not result["issues"]:
                result["success"] = True
                print("✅ Users API: PASSED - Permissions system available")
            else:
                print("❌ Users API: FAILED")
                for issue in result["issues"]:
                    print(f"   - {issue}")
                    
            return result
            
        except requests.exceptions.RequestException as e:
            result = {
                "endpoint": "GET /api/users",
                "test": "permissions_system",
                "status_code": None,
                "success": False,
                "issues": [f"Request failed: {e}"]
            }
            print("❌ Users API: FAILED - Request error")
            print(f"   - {e}")
            return result

    def test_finance_ar_customers(self) -> Dict[str, Any]:
        """Test GET /api/finance/ar/customers for receivables data"""
        print("🔍 Testing: GET /api/finance/ar/customers (receivables)")
        
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            response = self.session.get(
                f"{self.base_url}/api/finance/ar/customers",
                params={
                    "workshop_id": self.workshop_id,
                    "as_of": today,
                    "include_today": "true"
                }
            )
            
            result = {
                "endpoint": "GET /api/finance/ar/customers",
                "test": "receivables_data",
                "status_code": response.status_code,
                "success": False,
                "issues": []
            }
            
            if response.status_code != 200:
                result["issues"].append(f"Status code {response.status_code}, expected 200")
                return result
                
            try:
                data = response.json()
                result["data"] = data
            except json.JSONDecodeError as e:
                result["issues"].append(f"Invalid JSON response: {e}")
                return result
            
            # Check for required structure
            if "success" in data and data["success"]:
                ar_data = data.get("data", {})
                if "total_ar" in ar_data and "customers" in ar_data:
                    result["success"] = True
                    total_ar = ar_data["total_ar"]
                    customers_count = len(ar_data["customers"])
                    print("✅ Finance AR Customers: PASSED")
                    print(f"   - Total AR: {total_ar}")
                    print(f"   - Customers with balances: {customers_count}")
                else:
                    result["issues"].append("Missing total_ar or customers in response data")
            else:
                result["issues"].append("API returned success=false or missing success field")
                
            if not result["success"]:
                print("❌ Finance AR Customers: FAILED")
                for issue in result["issues"]:
                    print(f"   - {issue}")
                    
            return result
            
        except requests.exceptions.RequestException as e:
            result = {
                "endpoint": "GET /api/finance/ar/customers",
                "test": "receivables_data",
                "status_code": None,
                "success": False,
                "issues": [f"Request failed: {e}"]
            }
            print("❌ Finance AR Customers: FAILED - Request error")
            print(f"   - {e}")
            return result

    def run_all_tests(self) -> Dict[str, Any]:
        """Run all tests and return summary"""
        print(f"🚀 Starting Arabic Requirements Backend API Tests")
        print(f"Base URL: {self.base_url}")
        print(f"Workshop ID: {self.workshop_id}")
        print("=" * 70)
        
        results = []
        
        # Test 1: Operations with Rakan account (5000)
        results.append(self.test_operations_with_rakan_account())
        print()
        
        # Test 2: Journal entries Rakan separation
        results.append(self.test_journal_entries_rakan_separation())
        print()
        
        # Test 3: Users API (permissions system)
        results.append(self.test_users_api())
        print()
        
        # Test 4: Finance AR customers (receivables data)
        results.append(self.test_finance_ar_customers())
        print()
        
        # Summary
        print("=" * 70)
        print("📊 TEST SUMMARY")
        print("=" * 70)
        
        passed_count = sum(1 for r in results if r.get("success", False))
        total_count = len(results)
        
        for result in results:
            test_name = result.get("test", result.get("endpoint", "Unknown"))
            status = "✅ PASS" if result.get("success", False) else "❌ FAIL"
            print(f"{status} {test_name}")
            
        print(f"\nOverall: {passed_count}/{total_count} tests passed")
        
        overall_success = passed_count == total_count
        
        if overall_success:
            print("🎉 ALL BACKEND TESTS PASSED!")
        else:
            print("⚠️ SOME BACKEND TESTS FAILED - Check logs above for details")
            
        return {
            "overall_success": overall_success,
            "passed_count": passed_count,
            "total_count": total_count,
            "results": results
        }


def main():
    """Main function to run the tests"""
    # Use the base URL from frontend/.env
    BASE_URL = "https://finance-overhaul-7.preview.emergentagent.com"
    
    if len(sys.argv) > 1:
        BASE_URL = sys.argv[1]
        
    print("Arabic Requirements Backend API Testing")
    print("=" * 70)
    
    tester = ArabicRequirementsAPITester(BASE_URL)
    summary = tester.run_all_tests()
    
    # Exit with appropriate code
    exit_code = 0 if summary["overall_success"] else 1
    sys.exit(exit_code)


if __name__ == "__main__":
    main()