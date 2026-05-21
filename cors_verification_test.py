#!/usr/bin/env python3
"""
CORS Restriction Verification Test
Testing CORS changes to ensure API behavior is not broken
"""

import requests
import json
from datetime import datetime

# Configuration from frontend/.env
BACKEND_URL = "https://fleet-audit-system-2.preview.emergentagent.com/api"
WORKSHOP_ID = "finmodule-sync"

# CORS Origins to test
CORS_ORIGINS = [
    "https://fixsa.online",
    "https://www.fixsa.online"
]

def print_test_header(test_name):
    """Print formatted test header"""
    print(f"\n{'='*60}")
    print(f"🧪 {test_name}")
    print(f"{'='*60}")

def print_result(success, message, details=None):
    """Print test result with formatting"""
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"{status}: {message}")
    if details:
        print(f"Details: {details}")

def test_health_endpoint():
    """
    Test 1: GET /health returns 200 (using stats endpoint as health check)
    """
    print_test_header("Health Check Test (via Stats Endpoint)")
    
    try:
        # Use stats endpoint as health check since it's simple and reliable
        stats_url = f"{BACKEND_URL}/stats"
        print(f"📡 Request: GET {stats_url}")
        
        response = requests.get(stats_url, timeout=10)
        print(f"📊 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"📄 Response keys: {list(data.keys())}")
            print_result(True, "Backend health check (stats) returns 200 OK")
            return True
        else:
            print_result(False, f"Backend health check failed with status {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print_result(False, f"Backend health check error: {str(e)}")
        return False

def test_customers_endpoint():
    """
    Test 2: OPTIONS/GET /api/customers returns expected response
    """
    print_test_header("Customers Endpoint Test")
    
    try:
        customers_url = f"{BACKEND_URL}/customers"
        
        # Test OPTIONS request first
        print(f"📡 Request: OPTIONS {customers_url}")
        options_response = requests.options(customers_url, timeout=10)
        print(f"📊 OPTIONS Status Code: {options_response.status_code}")
        
        # Test GET request
        print(f"📡 Request: GET {customers_url}")
        get_response = requests.get(customers_url, timeout=10)
        print(f"📊 GET Status Code: {get_response.status_code}")
        
        if get_response.status_code == 200:
            customers = get_response.json()
            print(f"📄 Customers count: {len(customers)}")
            print_result(True, f"Customers endpoint returns 200 OK with {len(customers)} customers")
            return True
        else:
            print_result(False, f"Customers endpoint failed with status {get_response.status_code}")
            print(f"Response: {get_response.text}")
            return False
            
    except Exception as e:
        print_result(False, f"Customers endpoint error: {str(e)}")
        return False

def test_cors_headers():
    """
    Test 3: Check CORS headers for allowed origins
    """
    print_test_header("CORS Headers Test")
    
    all_passed = True
    
    for origin in CORS_ORIGINS:
        try:
            print(f"\n🧪 Testing Origin: {origin}")
            
            customers_url = f"{BACKEND_URL}/customers"
            headers = {
                'Origin': origin,
                'Access-Control-Request-Method': 'GET',
                'Access-Control-Request-Headers': 'Content-Type'
            }
            
            # Test preflight OPTIONS request
            print(f"📡 Request: OPTIONS {customers_url}")
            print(f"📤 Headers: {json.dumps(headers, indent=2)}")
            
            response = requests.options(customers_url, headers=headers, timeout=10)
            print(f"📊 Status Code: {response.status_code}")
            
            # Check CORS headers in response
            cors_headers = {}
            for header_name in response.headers:
                if header_name.lower().startswith('access-control'):
                    cors_headers[header_name] = response.headers[header_name]
            
            print(f"📄 CORS Headers: {json.dumps(cors_headers, indent=2)}")
            
            # Check for Access-Control-Allow-Origin
            allow_origin = response.headers.get('Access-Control-Allow-Origin', '')
            
            if allow_origin == origin or allow_origin == '*':
                print_result(True, f"CORS headers correct for origin {origin}")
            else:
                print_result(False, f"CORS headers incorrect for origin {origin}. Got: {allow_origin}")
                all_passed = False
                
        except Exception as e:
            print_result(False, f"CORS test error for {origin}: {str(e)}")
            all_passed = False
    
    return all_passed

def test_api_functionality():
    """
    Test 4: Verify core API functionality still works
    """
    print_test_header("API Functionality Test")
    
    try:
        # Test multiple endpoints to ensure CORS changes didn't break functionality
        endpoints = [
            ("Vehicles", f"{BACKEND_URL}/vehicles"),
            ("Services", f"{BACKEND_URL}/services"),
            ("Stats", f"{BACKEND_URL}/stats")
        ]
        
        all_passed = True
        
        for name, url in endpoints:
            try:
                print(f"\n🧪 Testing {name}")
                print(f"📡 Request: GET {url}")
                
                response = requests.get(url, timeout=10)
                print(f"📊 Status Code: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list):
                        print(f"📄 Response: {len(data)} items")
                    else:
                        print(f"📄 Response: {type(data).__name__}")
                    print_result(True, f"{name} endpoint working correctly")
                else:
                    print_result(False, f"{name} endpoint failed with status {response.status_code}")
                    all_passed = False
                    
            except Exception as e:
                print_result(False, f"{name} endpoint error: {str(e)}")
                all_passed = False
        
        return all_passed
        
    except Exception as e:
        print_result(False, f"API functionality test error: {str(e)}")
        return False

def run_cors_verification():
    """Run all CORS verification tests"""
    print("🚀 Starting CORS Restriction Verification")
    print(f"🌐 Backend URL: {BACKEND_URL}")
    print(f"🏪 Workshop ID: {WORKSHOP_ID}")
    print(f"⏰ Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = []
    
    # Test 1: Health endpoint (using stats)
    results.append(("Backend Health Check", test_health_endpoint()))
    
    # Test 2: Customers endpoint
    results.append(("Customers Endpoint", test_customers_endpoint()))
    
    # Test 3: CORS headers
    results.append(("CORS Headers", test_cors_headers()))
    
    # Test 4: API functionality
    results.append(("API Functionality", test_api_functionality()))
    
    # Summary
    print_test_header("CORS Verification Test Results")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\n📊 Final Result: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All CORS verification tests passed!")
        print("✅ CORS restriction changes did not break API behavior")
        return True
    else:
        print(f"⚠️ {total - passed} tests failed")
        print("❌ CORS restriction changes may have broken some functionality")
        return False

if __name__ == "__main__":
    success = run_cors_verification()
    exit(0 if success else 1)