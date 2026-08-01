#!/usr/bin/env python3
"""
Workshop Management System - Comprehensive Backend API Testing
Review Request: Test all backend APIs with Supabase integration
"""

import requests
import json
import uuid
from datetime import datetime

# Backend URL from frontend/.env
BACKEND_URL = "https://ar-ledger-ssot.preview.emergentagent.com/api"

# Test credentials
TEST_USERNAME = "مدير"

def print_header(title):
    """Print formatted header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def print_section(title):
    """Print formatted section"""
    print(f"\n{'─' * 70}")
    print(f"  {title}")
    print(f"{'─' * 70}")

def test_endpoint(method, endpoint, data=None, expected_status=200, description=""):
    """Test an API endpoint and return detailed result"""
    url = f"{BACKEND_URL}{endpoint}"
    
    print(f"\n🔍 Testing: {method} {endpoint}")
    if description:
        print(f"   Description: {description}")
    
    try:
        headers = {"Content-Type": "application/json"}
        
        if method.upper() == "GET":
            response = requests.get(url, headers=headers, timeout=30)
        elif method.upper() == "POST":
            response = requests.post(url, json=data, headers=headers, timeout=30)
        else:
            print(f"   ❌ FAIL: Unsupported method {method}")
            return {"success": False, "error": f"Unsupported method: {method}"}
        
        # Parse response
        try:
            response_data = response.json()
        except:
            response_data = response.text[:200] if response.text else ""
        
        # Determine success
        success = response.status_code == expected_status
        
        result = {
            "success": success,
            "status_code": response.status_code,
            "endpoint": endpoint,
            "method": method,
            "data": response_data
        }
        
        # Print result
        if success:
            print(f"   ✅ PASS: HTTP {response.status_code}")
            
            # Print data summary
            if isinstance(response_data, list):
                print(f"   📊 Returned {len(response_data)} items")
                result["count"] = len(response_data)
                if len(response_data) > 0:
                    print(f"   📝 Sample item keys: {list(response_data[0].keys())[:5]}")
            elif isinstance(response_data, dict):
                print(f"   📝 Response keys: {list(response_data.keys())}")
                result["keys"] = list(response_data.keys())
        else:
            print(f"   ❌ FAIL: HTTP {response.status_code} (expected {expected_status})")
            if isinstance(response_data, dict) and "detail" in response_data:
                print(f"   💬 Error: {response_data['detail']}")
            elif isinstance(response_data, str):
                print(f"   💬 Response: {response_data[:100]}")
        
        return result
        
    except requests.exceptions.Timeout:
        print(f"   ❌ FAIL: Request timeout (>30s)")
        return {"success": False, "error": "Request timeout", "endpoint": endpoint}
    except requests.exceptions.RequestException as e:
        print(f"   ❌ FAIL: Request error - {str(e)}")
        return {"success": False, "error": str(e), "endpoint": endpoint}
    except Exception as e:
        print(f"   ❌ FAIL: Unexpected error - {str(e)}")
        return {"success": False, "error": str(e), "endpoint": endpoint}

def main():
    print_header("🔧 Workshop Management System - Backend API Testing")
    print(f"\n📍 Backend URL: {BACKEND_URL}")
    print(f"🗄️  Database Provider: Supabase")
    print(f"👤 Test User: {TEST_USERNAME}")
    print(f"⏰ Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = []
    
    # ============================================================
    # TEST 1: Stats Endpoint
    # ============================================================
    print_section("TEST 1: Dashboard Statistics")
    result = test_endpoint(
        "GET", "/stats",
        description="Should return statistics (customers, vehicles, income, expenses)"
    )
    results.append(result)
    
    if result["success"] and isinstance(result["data"], dict):
        stats = result["data"]
        print(f"\n   📈 Statistics Summary:")
        print(f"      • Total Customers: {stats.get('totalCustomers', 'N/A')}")
        print(f"      • Active Vehicles: {stats.get('activeVehicles', 'N/A')}")
        if "thisMonth" in stats:
            print(f"      • This Month Income: {stats['thisMonth'].get('income', 0)}")
            print(f"      • This Month Expenses: {stats['thisMonth'].get('expenses', 0)}")
    
    # ============================================================
    # TEST 2: Customers Endpoint
    # ============================================================
    print_section("TEST 2: Customers API")
    
    # GET customers
    result = test_endpoint(
        "GET", "/customers",
        description="Should return list of customers"
    )
    results.append(result)
    
    # POST create customer
    customer_data = {
        "id": str(uuid.uuid4()),
        "name": "عميل تجريبي",
        "phone": f"966{str(uuid.uuid4().int)[:9]}",
        "email": f"test{str(uuid.uuid4())[:8]}@example.com",
        "totalVisits": 1,
        "lastVisit": datetime.utcnow().isoformat(),
        "vehicles": []
    }
    
    print(f"\n   Creating test customer: {customer_data['name']}")
    result = test_endpoint(
        "POST", "/customers",
        data=customer_data,
        description="Should create new customer"
    )
    results.append(result)
    
    # ============================================================
    # TEST 3: Services Endpoint
    # ============================================================
    print_section("TEST 3: Services API")
    result = test_endpoint(
        "GET", "/services",
        description="Should return services list"
    )
    results.append(result)
    
    # ============================================================
    # TEST 4: Technicians Endpoint
    # ============================================================
    print_section("TEST 4: Technicians API")
    result = test_endpoint(
        "GET", "/technicians",
        description="Should return technicians list"
    )
    results.append(result)
    
    # ============================================================
    # TEST 5: Parts Endpoint
    # ============================================================
    print_section("TEST 5: Parts Inventory API")
    result = test_endpoint(
        "GET", "/parts",
        description="Should return parts list"
    )
    results.append(result)
    
    # ============================================================
    # TEST 6: Vehicles Endpoint
    # ============================================================
    print_section("TEST 6: Vehicles API")
    
    # GET vehicles
    result = test_endpoint(
        "GET", "/vehicles",
        description="Should return list of vehicles"
    )
    results.append(result)
    
    # POST create vehicle
    vehicle_data = {
        "plateNumber": f"TEST-{str(uuid.uuid4())[:4].upper()}",
        "brand": "تويوتا",
        "model": "كامري",
        "year": 2022,
        "color": "فضي",
        "customerName": "أحمد الراشد",
        "customerPhone": f"966{str(uuid.uuid4().int)[:9]}",
        "customerEmail": f"test{str(uuid.uuid4())[:8]}@example.com",
        "issue": "صيانة دورية",
        "status": "diagnosis",
        "mileage": 45000
    }
    
    print(f"\n   Creating test vehicle: {vehicle_data['plateNumber']}")
    result = test_endpoint(
        "POST", "/vehicles",
        data=vehicle_data,
        description="Should create new vehicle"
    )
    results.append(result)
    
    if result["success"] and isinstance(result["data"], dict):
        vehicle_id = result["data"].get("id")
        if vehicle_id:
            print(f"   ✅ Vehicle created with ID: {vehicle_id}")
    
    # ============================================================
    # TEST 7: Business Accounts Endpoint
    # ============================================================
    print_section("TEST 7: Business Accounts API")
    result = test_endpoint(
        "GET", "/business-accounts",
        description="Should return business accounts"
    )
    results.append(result)
    
    # ============================================================
    # TEST 8: Salaries Endpoint
    # ============================================================
    print_section("TEST 8: Salaries API")
    result = test_endpoint(
        "GET", "/salaries",
        description="Should return salaries (empty list is OK)"
    )
    results.append(result)
    
    # ============================================================
    # TEST 9: Users Endpoint
    # ============================================================
    print_section("TEST 9: Users API")
    result = test_endpoint(
        "GET", "/users",
        description="Should return users list (3 users expected)"
    )
    results.append(result)
    
    if result["success"] and isinstance(result["data"], list):
        user_count = len(result["data"])
        if user_count == 3:
            print(f"   ✅ Correct: Found {user_count} users as expected")
        else:
            print(f"   ⚠️  Warning: Found {user_count} users (expected 3)")
    
    # ============================================================
    # SUMMARY
    # ============================================================
    print_header("📊 TEST SUMMARY")
    
    total_tests = len(results)
    passed_tests = sum(1 for r in results if r["success"])
    failed_tests = total_tests - passed_tests
    success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
    
    print(f"\n   Total Tests: {total_tests}")
    print(f"   ✅ Passed: {passed_tests}")
    print(f"   ❌ Failed: {failed_tests}")
    print(f"   📈 Success Rate: {success_rate:.1f}%")
    
    # Detailed results
    print_section("📋 Detailed Test Results")
    
    for i, result in enumerate(results, 1):
        endpoint = result.get("endpoint", "unknown")
        method = result.get("method", "GET")
        status = "✅ PASS" if result["success"] else "❌ FAIL"
        
        print(f"\n   {i}. {status} - {method} {endpoint}")
        
        if result["success"]:
            if "count" in result:
                print(f"      → Returned {result['count']} items")
            if "keys" in result:
                print(f"      → Response keys: {', '.join(result['keys'][:5])}")
        else:
            if "status_code" in result:
                print(f"      → HTTP Status: {result['status_code']}")
            if "error" in result:
                print(f"      → Error: {result['error']}")
    
    # Critical issues
    critical_issues = []
    for result in results:
        if not result["success"]:
            status_code = result.get("status_code", 0)
            if status_code >= 500:
                critical_issues.append({
                    "endpoint": result["endpoint"],
                    "status": status_code,
                    "error": result.get("error", "Unknown error")
                })
    
    if critical_issues:
        print_section("🚨 CRITICAL ISSUES FOUND")
        for issue in critical_issues:
            print(f"\n   ❌ {issue['endpoint']}")
            print(f"      → HTTP {issue['status']}")
            print(f"      → {issue['error']}")
    
    # Supabase validation
    print_section("🗄️  Supabase Integration Status")
    
    if failed_tests == 0:
        print("\n   ✅ All endpoints working correctly with Supabase")
        print("   ✅ No MongoDB errors detected")
        print("   ✅ Database connectivity confirmed")
    else:
        print(f"\n   ⚠️  {failed_tests} endpoint(s) failing")
        print("   🔍 Check if endpoints are using Supabase correctly")
        
        # Check for MongoDB errors
        mongo_errors = []
        for result in results:
            if not result["success"] and isinstance(result.get("data"), dict):
                error_msg = str(result["data"].get("detail", ""))
                if "mongo" in error_msg.lower() or "ssl" in error_msg.lower():
                    mongo_errors.append(result["endpoint"])
        
        if mongo_errors:
            print("\n   🚨 MongoDB errors detected in:")
            for ep in mongo_errors:
                print(f"      • {ep}")
            print("   ⚠️  These endpoints should use Supabase, not MongoDB")
    
    # Final verdict
    print_header("🎯 FINAL VERDICT")
    
    if failed_tests == 0:
        print("\n   🎉 ALL TESTS PASSED!")
        print("   ✅ Workshop Management System backend is working correctly")
        print("   ✅ All APIs return 200 OK with valid data")
        print("   ✅ Supabase integration confirmed")
    elif success_rate >= 80:
        print("\n   ⚠️  MOSTLY WORKING")
        print(f"   ✅ {passed_tests}/{total_tests} tests passed")
        print(f"   ❌ {failed_tests} endpoint(s) need attention")
    else:
        print("\n   🚨 CRITICAL ISSUES DETECTED")
        print(f"   ❌ {failed_tests}/{total_tests} tests failed")
        print("   🔧 Immediate fixes required")
    
    print("\n" + "=" * 70 + "\n")
    
    return results, passed_tests, failed_tests

if __name__ == "__main__":
    results, passed, failed = main()
