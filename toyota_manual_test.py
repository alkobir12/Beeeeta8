#!/usr/bin/env python3
"""
Toyota Manual Backend API Testing
Testing specific Toyota Manual endpoints as requested in review:
1. GET /api/toyota-manual/search with single-character queries
2. GET /api/toyota-manual/content/by-file with specific files
3. Regression testing of existing endpoints
"""

import requests
import json
import time
from datetime import datetime

# Backend URL from frontend/.env
BACKEND_URL = "https://finance-overhaul-7.preview.emergentagent.com/api"

def test_endpoint(method, endpoint, params=None, data=None, expected_status=200, timeout=30):
    """Test an API endpoint and return result"""
    url = f"{BACKEND_URL}{endpoint}"
    
    try:
        if method.upper() == "GET":
            response = requests.get(url, params=params, timeout=timeout)
        elif method.upper() == "POST":
            response = requests.post(url, json=data, timeout=timeout)
        else:
            return {"success": False, "error": f"Unsupported method: {method}"}
        
        result = {
            "success": response.status_code == expected_status,
            "status_code": response.status_code,
            "endpoint": endpoint,
            "method": method,
            "params": params
        }
        
        # Try to parse JSON response
        try:
            result["data"] = response.json()
            result["data_type"] = type(result["data"]).__name__
            if isinstance(result["data"], list):
                result["count"] = len(result["data"])
            elif isinstance(result["data"], dict):
                result["keys"] = list(result["data"].keys())
        except:
            result["data"] = response.text[:500] if response.text else ""
            result["data_type"] = "text"
        
        return result
        
    except requests.exceptions.Timeout:
        return {"success": False, "error": "Request timeout", "endpoint": endpoint}
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": str(e), "endpoint": endpoint}

def main():
    print("🔍 Toyota Manual Backend API Testing")
    print("=" * 60)
    print(f"Backend URL: {BACKEND_URL}")
    print(f"Testing Toyota Manual endpoints as requested in review")
    print()
    
    results = []
    passed = 0
    failed = 0
    
    # Test 1: Single-character search queries
    print("📋 Test 1: Single-character search queries (should no longer reject length<2)")
    print("-" * 70)
    
    single_char_queries = [
        ('a', 'English single character'),
        ('ب', 'Arabic single character'),
        ('e', 'Another English character'),
        ('م', 'Another Arabic character')
    ]
    
    for query, description in single_char_queries:
        print(f"Testing search with '{query}' ({description})...", end=" ")
        result = test_endpoint("GET", "/toyota-manual/search", params={"q": query})
        results.append(result)
        
        if result["success"]:
            status = "✅ PASS"
            passed += 1
            if "data" in result and isinstance(result["data"], dict):
                if "results" in result["data"]:
                    count = len(result["data"]["results"])
                    status += f" ({count} results)"
                elif "count" in result["data"]:
                    status += f" ({result['data']['count']} results)"
        else:
            status = "❌ FAIL"
            failed += 1
            if "status_code" in result:
                status += f" - HTTP {result['status_code']}"
                if result["status_code"] == 400:
                    status += " (Still rejecting short queries?)"
        
        print(status)
    
    print()
    
    # Test 2: Content by file endpoint
    print("📋 Test 2: GET /api/toyota-manual/content/by-file with specific files")
    print("-" * 70)
    
    # First, let's get some actual file paths from the content endpoint
    print("Getting available files from /toyota-manual/content...", end=" ")
    content_result = test_endpoint("GET", "/toyota-manual/content", params={"limit": 10})
    
    test_files = []
    if content_result["success"] and "data" in content_result:
        content_data = content_result["data"]
        if isinstance(content_data, dict) and "documents" in content_data:
            # Extract file paths from the first few documents
            for doc in content_data["documents"][:3]:
                if isinstance(doc, dict) and "file" in doc:
                    test_files.append(doc["file"])
        elif isinstance(content_data, list):
            # If it's a list of documents
            for doc in content_data[:3]:
                if isinstance(doc, dict) and "file" in doc:
                    test_files.append(doc["file"])
    
    # Add the specific file mentioned in the review request
    test_files.insert(0, "repair2/html/contents/local_rm000003a7j001x.html")
    
    # Remove duplicates while preserving order
    test_files = list(dict.fromkeys(test_files))
    
    print(f"Found {len(test_files)} files to test")
    
    for file_path in test_files[:4]:  # Test up to 4 files
        print(f"Testing content/by-file with '{file_path}'...", end=" ")
        result = test_endpoint("GET", "/toyota-manual/content/by-file", params={"file": file_path})
        results.append(result)
        
        if result["success"]:
            status = "✅ PASS"
            passed += 1
            if "data" in result and isinstance(result["data"], dict):
                # Check for expected fields
                expected_fields = ["title", "content", "images", "procedures"]
                found_fields = []
                for field in expected_fields:
                    if field in result["data"]:
                        found_fields.append(field)
                
                if found_fields:
                    status += f" (has: {', '.join(found_fields)})"
                else:
                    status += " (basic response)"
        else:
            status = "❌ FAIL"
            failed += 1
            if "status_code" in result:
                status += f" - HTTP {result['status_code']}"
        
        print(status)
    
    print()
    
    # Test 3: Regression testing of existing endpoints
    print("📋 Test 3: Regression testing of existing Toyota Manual endpoints")
    print("-" * 70)
    
    regression_endpoints = [
        ("/toyota-manual/stats", "Statistics endpoint"),
        ("/toyota-manual/sections", "Sections endpoint"),
        ("/toyota-manual/content", "Content endpoint")
    ]
    
    for endpoint, description in regression_endpoints:
        print(f"Testing {description}...", end=" ")
        result = test_endpoint("GET", endpoint)
        results.append(result)
        
        if result["success"]:
            status = "✅ PASS"
            passed += 1
            if "data" in result and isinstance(result["data"], dict):
                if endpoint == "/toyota-manual/stats":
                    # Check for expected stats fields
                    stats_fields = ["sections", "documents", "images"]
                    found_stats = [f for f in stats_fields if f in result["data"]]
                    if found_stats:
                        stats_str = ', '.join(f'{f}={result["data"][f]}' for f in found_stats)
                        status += f" ({stats_str})"
                elif endpoint == "/toyota-manual/sections":
                    if "count" in result["data"]:
                        status += f" ({result['data']['count']} sections)"
                    elif isinstance(result["data"], list):
                        status += f" ({len(result['data'])} sections)"
                elif endpoint == "/toyota-manual/content":
                    if "count" in result["data"]:
                        status += f" ({result['data']['count']} documents)"
                    elif "documents" in result["data"]:
                        status += f" ({len(result['data']['documents'])} documents)"
        else:
            status = "❌ FAIL"
            failed += 1
            if "status_code" in result:
                status += f" - HTTP {result['status_code']}"
        
        print(status)
    
    print()
    print("📊 Test Summary:")
    print("=" * 60)
    print(f"Total Tests: {len(results)}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"Success Rate: {(passed/len(results)*100):.1f}%")
    
    print()
    print("🔍 Detailed Results:")
    print("-" * 60)
    
    # Group results by test category
    test_categories = [
        ("Single-character search", 0, 4),
        ("Content by file", 4, 4 + len(test_files[:4])),
        ("Regression tests", 4 + len(test_files[:4]), len(results))
    ]
    
    for category, start_idx, end_idx in test_categories:
        print(f"\n{category}:")
        for i in range(start_idx, min(end_idx, len(results))):
            result = results[i]
            endpoint = result.get("endpoint", "unknown")
            method = result.get("method", "GET")
            params = result.get("params", {})
            
            if result["success"]:
                print(f"  ✅ {method} {endpoint}")
                if params:
                    print(f"     Params: {params}")
                if "data" in result and isinstance(result["data"], dict):
                    if "count" in result["data"]:
                        print(f"     → {result['data']['count']} items")
                    elif "keys" in result:
                        print(f"     → Keys: {', '.join(result['keys'][:5])}{'...' if len(result['keys']) > 5 else ''}")
            else:
                print(f"  ❌ {method} {endpoint}")
                if params:
                    print(f"     Params: {params}")
                if "status_code" in result:
                    print(f"     → HTTP {result['status_code']}")
                if "error" in result:
                    print(f"     → Error: {result['error']}")
    
    print()
    
    # Performance analysis
    print("⚡ Performance Analysis:")
    print("-" * 30)
    
    # Check for any 4xx/5xx errors
    client_errors = [r for r in results if r.get("status_code", 0) >= 400 and r.get("status_code", 0) < 500]
    server_errors = [r for r in results if r.get("status_code", 0) >= 500]
    
    if client_errors:
        print("🔴 4xx Client Errors:")
        for result in client_errors:
            print(f"   • {result['endpoint']} - HTTP {result['status_code']}")
    
    if server_errors:
        print("🔴 5xx Server Errors:")
        for result in server_errors:
            print(f"   • {result['endpoint']} - HTTP {result['status_code']}")
    
    if not client_errors and not server_errors:
        print("✅ No 4xx/5xx errors detected")
    
    print()
    
    # Final assessment
    if failed == 0:
        print("🎉 ALL TESTS PASSED!")
        print("✅ Single-character search queries working")
        print("✅ Content by file endpoint working")
        print("✅ No regressions in existing endpoints")
    elif passed >= len(results) * 0.8:  # 80% pass rate
        print("⚠️  MOSTLY WORKING - Minor issues detected")
        if any(r.get("status_code") == 400 for r in results if "/search" in r.get("endpoint", "")):
            print("❌ Single-character search may still be rejecting short queries")
    else:
        print("🚨 CRITICAL ISSUES - Multiple endpoints failing")
    
    return passed, failed, results

if __name__ == "__main__":
    main()