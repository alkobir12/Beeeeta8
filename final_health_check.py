#!/usr/bin/env python3
"""
Final Comprehensive Health Check - فحص صحي شامل نهائي
Testing all critical systems as requested:
1. References (المراجع)
2. Knowledge (المعرفة)
3. Operations (العمليات)
4. Basics (الأساسيات)
5. Print (الطباعة)
"""

import requests
import json
import time
from datetime import datetime
from typing import Dict, Any, List, Tuple

# Backend URL from environment
BACKEND_URL = "https://pdpl-memory-engine.preview.emergentagent.com/api"

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

class TestResults:
    def __init__(self):
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0
        self.working_endpoints = []
        self.failed_endpoints = []
        self.test_details = []
    
    def add_result(self, endpoint: str, method: str, status: str, details: str = "", response_time: float = 0):
        self.total_tests += 1
        full_endpoint = f"{method} {endpoint}"
        
        if status == "PASS":
            self.passed_tests += 1
            self.working_endpoints.append(full_endpoint)
        else:
            self.failed_tests += 1
            self.failed_endpoints.append(f"{full_endpoint} - {details}")
        
        self.test_details.append({
            "endpoint": full_endpoint,
            "status": status,
            "details": details,
            "response_time": response_time
        })
    
    def get_success_rate(self) -> float:
        if self.total_tests == 0:
            return 0.0
        return (self.passed_tests / self.total_tests) * 100
    
    def print_summary(self):
        print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*80}")
        print(f"FINAL HEALTH CHECK SUMMARY - ملخص الفحص الصحي النهائي")
        print(f"{'='*80}{Colors.RESET}\n")
        
        success_rate = self.get_success_rate()
        color = Colors.GREEN if success_rate >= 90 else Colors.YELLOW if success_rate >= 70 else Colors.RED
        
        print(f"{Colors.BOLD}Overall Success Rate (نسبة النجاح الإجمالية):{Colors.RESET} {color}{success_rate:.1f}%{Colors.RESET}")
        print(f"{Colors.BOLD}Total Tests:{Colors.RESET} {self.total_tests}")
        print(f"{Colors.GREEN}Passed:{Colors.RESET} {self.passed_tests}")
        print(f"{Colors.RED}Failed:{Colors.RESET} {self.failed_tests}")
        print()
        
        print(f"{Colors.BOLD}{Colors.GREEN}Working Endpoints (الـ endpoints العاملة):{Colors.RESET}")
        if self.working_endpoints:
            for endpoint in self.working_endpoints:
                print(f"  ✅ {endpoint}")
        else:
            print(f"  {Colors.RED}None{Colors.RESET}")
        print()
        
        if self.failed_endpoints:
            print(f"{Colors.BOLD}{Colors.RED}Failed Endpoints (المشاكل):{Colors.RESET}")
            for endpoint in self.failed_endpoints:
                print(f"  ❌ {endpoint}")
            print()
        
        # Deployment readiness
        print(f"{Colors.BOLD}Deployment Readiness (تقييم الجاهزية للنشر):{Colors.RESET}")
        if success_rate >= 90:
            print(f"  {Colors.GREEN}{Colors.BOLD}✅ READY FOR DEPLOYMENT{Colors.RESET}")
        elif success_rate >= 70:
            print(f"  {Colors.YELLOW}{Colors.BOLD}⚠️  READY WITH MINOR ISSUES{Colors.RESET}")
        else:
            print(f"  {Colors.RED}{Colors.BOLD}❌ NOT READY - CRITICAL ISSUES{Colors.RESET}")
        print()

def log_section(title: str):
    """Log section header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*80}")
    print(f"{title}")
    print(f"{'='*80}{Colors.RESET}\n")

def log_test(test_name: str, status: str, details: str = "", response_time: float = 0):
    """Log test results with colors"""
    color = Colors.GREEN if status == "PASS" else Colors.RED if status == "FAIL" else Colors.YELLOW
    symbol = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
    print(f"{color}{symbol} [{status}]{Colors.RESET} {test_name}")
    if details:
        print(f"  {details}")
    if response_time > 0:
        print(f"  ⏱️  Response Time: {response_time:.3f}s")
    print()

def test_references(results: TestResults):
    """Test 1: References System (المراجع)"""
    log_section("TEST 1: References System (المراجع)")
    
    # Test 1.1: GET /api/references/electrical
    try:
        start_time = time.time()
        response = requests.get(f"{BACKEND_URL}/references/electrical", timeout=15)
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            # Handle both direct array and wrapped response
            refs = data if isinstance(data, list) else data.get('references', [])
            if refs and isinstance(refs, list):
                log_test("GET /api/references/electrical", "PASS", 
                        f"Retrieved {len(refs)} electrical references", response_time)
                results.add_result("/api/references/electrical", "GET", "PASS", 
                                 f"{len(refs)} references", response_time)
            else:
                log_test("GET /api/references/electrical", "FAIL", 
                        f"No references found in response", response_time)
                results.add_result("/api/references/electrical", "GET", "FAIL", 
                                 "No references found", response_time)
        else:
            log_test("GET /api/references/electrical", "FAIL", 
                    f"Status: {response.status_code}", response_time)
            results.add_result("/api/references/electrical", "GET", "FAIL", 
                             f"Status {response.status_code}", response_time)
    except Exception as e:
        log_test("GET /api/references/electrical", "FAIL", f"Error: {str(e)}")
        results.add_result("/api/references/electrical", "GET", "FAIL", str(e))
    
    # Test 1.2: POST /api/references/electrical/smart-search
    try:
        start_time = time.time()
        payload = {"query": "جهد البطارية"}
        response = requests.post(f"{BACKEND_URL}/references/electrical/smart-search", 
                                json=payload, timeout=15)
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            log_test("POST /api/references/electrical/smart-search", "PASS", 
                    f"Search for 'جهد البطارية' successful", response_time)
            results.add_result("/api/references/electrical/smart-search", "POST", "PASS", 
                             "Search working", response_time)
        else:
            log_test("POST /api/references/electrical/smart-search", "FAIL", 
                    f"Status: {response.status_code}", response_time)
            results.add_result("/api/references/electrical/smart-search", "POST", "FAIL", 
                             f"Status {response.status_code}", response_time)
    except Exception as e:
        log_test("POST /api/references/electrical/smart-search", "FAIL", f"Error: {str(e)}")
        results.add_result("/api/references/electrical/smart-search", "POST", "FAIL", str(e))
    
    # Test 1.3: GET /api/references/dtc?code=P0087
    try:
        start_time = time.time()
        response = requests.get(f"{BACKEND_URL}/references/dtc", 
                               params={"code": "P0087"}, timeout=15)
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            log_test("GET /api/references/dtc?code=P0087", "PASS", 
                    f"DTC lookup successful", response_time)
            results.add_result("/api/references/dtc", "GET", "PASS", 
                             "DTC lookup working", response_time)
        else:
            log_test("GET /api/references/dtc?code=P0087", "FAIL", 
                    f"Status: {response.status_code}", response_time)
            results.add_result("/api/references/dtc", "GET", "FAIL", 
                             f"Status {response.status_code}", response_time)
    except Exception as e:
        log_test("GET /api/references/dtc?code=P0087", "FAIL", f"Error: {str(e)}")
        results.add_result("/api/references/dtc", "GET", "FAIL", str(e))

def test_knowledge(results: TestResults):
    """Test 2: Knowledge System (المعرفة)"""
    log_section("TEST 2: Knowledge System (المعرفة)")
    
    # Test 2.1: GET /api/ai/kb/docs
    try:
        start_time = time.time()
        response = requests.get(f"{BACKEND_URL}/ai/kb/docs", timeout=15)
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            # Handle both direct array and wrapped response
            docs = data if isinstance(data, list) else data.get('docs', [])
            if docs and isinstance(docs, list):
                log_test("GET /api/ai/kb/docs", "PASS", 
                        f"Retrieved {len(docs)} knowledge documents", response_time)
                results.add_result("/api/ai/kb/docs", "GET", "PASS", 
                                 f"{len(docs)} documents", response_time)
            else:
                log_test("GET /api/ai/kb/docs", "FAIL", 
                        f"No documents found in response", response_time)
                results.add_result("/api/ai/kb/docs", "GET", "FAIL", 
                                 "No documents found", response_time)
        else:
            log_test("GET /api/ai/kb/docs", "FAIL", 
                    f"Status: {response.status_code}", response_time)
            results.add_result("/api/ai/kb/docs", "GET", "FAIL", 
                             f"Status {response.status_code}", response_time)
    except Exception as e:
        log_test("GET /api/ai/kb/docs", "FAIL", f"Error: {str(e)}")
        results.add_result("/api/ai/kb/docs", "GET", "FAIL", str(e))
    
    # Test 2.2: POST /api/ai/kb/smart-search
    try:
        start_time = time.time()
        payload = {"query": "محرك"}
        response = requests.post(f"{BACKEND_URL}/ai/kb/smart-search", 
                                json=payload, timeout=15)
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            log_test("POST /api/ai/kb/smart-search", "PASS", 
                    f"Search for 'محرك' successful", response_time)
            results.add_result("/api/ai/kb/smart-search", "POST", "PASS", 
                             "Search working", response_time)
        else:
            log_test("POST /api/ai/kb/smart-search", "FAIL", 
                    f"Status: {response.status_code}", response_time)
            results.add_result("/api/ai/kb/smart-search", "POST", "FAIL", 
                             f"Status {response.status_code}", response_time)
    except Exception as e:
        log_test("POST /api/ai/kb/smart-search", "FAIL", f"Error: {str(e)}")
        results.add_result("/api/ai/kb/smart-search", "POST", "FAIL", str(e))

def test_operations(results: TestResults):
    """Test 3: Operations System (العمليات)"""
    log_section("TEST 3: Operations System (العمليات)")
    
    # Test 3.1: GET /api/operations/analytics/summary
    try:
        start_time = time.time()
        response = requests.get(f"{BACKEND_URL}/operations/analytics/summary", timeout=15)
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            log_test("GET /api/operations/analytics/summary", "PASS", 
                    f"Analytics summary retrieved successfully", response_time)
            results.add_result("/api/operations/analytics/summary", "GET", "PASS", 
                             "Analytics working", response_time)
        else:
            log_test("GET /api/operations/analytics/summary", "FAIL", 
                    f"Status: {response.status_code}", response_time)
            results.add_result("/api/operations/analytics/summary", "GET", "FAIL", 
                             f"Status {response.status_code}", response_time)
    except Exception as e:
        log_test("GET /api/operations/analytics/summary", "FAIL", f"Error: {str(e)}")
        results.add_result("/api/operations/analytics/summary", "GET", "FAIL", str(e))

def test_basics(results: TestResults):
    """Test 4: Basic Systems (الأساسيات)"""
    log_section("TEST 4: Basic Systems (الأساسيات)")
    
    # Test 4.1: GET /api/profile
    try:
        start_time = time.time()
        response = requests.get(f"{BACKEND_URL}/profile", timeout=10)
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            log_test("GET /api/profile", "PASS", 
                    f"Profile data retrieved", response_time)
            results.add_result("/api/profile", "GET", "PASS", 
                             "Profile working", response_time)
        else:
            log_test("GET /api/profile", "FAIL", 
                    f"Status: {response.status_code}", response_time)
            results.add_result("/api/profile", "GET", "FAIL", 
                             f"Status {response.status_code}", response_time)
    except Exception as e:
        log_test("GET /api/profile", "FAIL", f"Error: {str(e)}")
        results.add_result("/api/profile", "GET", "FAIL", str(e))
    
    # Test 4.2: GET /api/vehicles
    try:
        start_time = time.time()
        response = requests.get(f"{BACKEND_URL}/vehicles", timeout=10)
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                log_test("GET /api/vehicles", "PASS", 
                        f"Retrieved {len(data)} vehicles", response_time)
                results.add_result("/api/vehicles", "GET", "PASS", 
                                 f"{len(data)} vehicles", response_time)
            else:
                log_test("GET /api/vehicles", "FAIL", 
                        f"Expected list, got {type(data)}", response_time)
                results.add_result("/api/vehicles", "GET", "FAIL", 
                                 "Invalid response format", response_time)
        else:
            log_test("GET /api/vehicles", "FAIL", 
                    f"Status: {response.status_code}", response_time)
            results.add_result("/api/vehicles", "GET", "FAIL", 
                             f"Status {response.status_code}", response_time)
    except Exception as e:
        log_test("GET /api/vehicles", "FAIL", f"Error: {str(e)}")
        results.add_result("/api/vehicles", "GET", "FAIL", str(e))
    
    # Test 4.3: GET /api/settings
    try:
        start_time = time.time()
        response = requests.get(f"{BACKEND_URL}/settings", timeout=10)
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            log_test("GET /api/settings", "PASS", 
                    f"Settings retrieved successfully", response_time)
            results.add_result("/api/settings", "GET", "PASS", 
                             "Settings working", response_time)
        else:
            log_test("GET /api/settings", "FAIL", 
                    f"Status: {response.status_code}", response_time)
            results.add_result("/api/settings", "GET", "FAIL", 
                             f"Status {response.status_code}", response_time)
    except Exception as e:
        log_test("GET /api/settings", "FAIL", f"Error: {str(e)}")
        results.add_result("/api/settings", "GET", "FAIL", str(e))

def test_print(results: TestResults):
    """Test 5: Print System (الطباعة)"""
    log_section("TEST 5: Print System (الطباعة)")
    
    # Test 5.1: POST /api/print/render
    try:
        start_time = time.time()
        payload = {
            "template_type": "invoice",
            "data": {
                "WORKSHOP_NAME": "ورشة الاختبار",
                "CUSTOMER_NAME": "عميل تجريبي",
                "INVOICE_NUMBER": "INV-TEST-001",
                "DATE": datetime.now().strftime("%Y-%m-%d"),
                "TOTAL": "1500.00",
                "ITEMS_ROWS": "<tr><td>خدمة تجريبية</td><td>1</td><td>1500.00</td></tr>"
            }
        }
        response = requests.post(f"{BACKEND_URL}/print/render", 
                                json=payload, timeout=15)
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            html_content = response.text
            if len(html_content) > 100 and "html" in html_content.lower():
                log_test("POST /api/print/render", "PASS", 
                        f"HTML rendered successfully ({len(html_content)} chars)", response_time)
                results.add_result("/api/print/render", "POST", "PASS", 
                                 "Print rendering working", response_time)
            else:
                log_test("POST /api/print/render", "FAIL", 
                        f"Invalid HTML response", response_time)
                results.add_result("/api/print/render", "POST", "FAIL", 
                                 "Invalid HTML", response_time)
        else:
            log_test("POST /api/print/render", "FAIL", 
                    f"Status: {response.status_code}", response_time)
            results.add_result("/api/print/render", "POST", "FAIL", 
                             f"Status {response.status_code}", response_time)
    except Exception as e:
        log_test("POST /api/print/render", "FAIL", f"Error: {str(e)}")
        results.add_result("/api/print/render", "POST", "FAIL", str(e))

def main():
    """Run all health checks"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*80}")
    print(f"FINAL COMPREHENSIVE HEALTH CHECK")
    print(f"فحص صحي شامل نهائي")
    print(f"{'='*80}{Colors.RESET}\n")
    print(f"Backend URL: {BACKEND_URL}")
    print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    results = TestResults()
    
    # Run all test sections
    test_references(results)
    test_knowledge(results)
    test_operations(results)
    test_basics(results)
    test_print(results)
    
    # Print final summary
    results.print_summary()
    
    return results.get_success_rate() >= 90

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
