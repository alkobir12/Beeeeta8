#!/usr/bin/env python3
"""
AutoProfit Pro Backend API Testing Script
اختبار سريع للواجهات الخلفية المرتبطة بنظام AutoProfit Pro
"""

import requests
import json
import sys
from datetime import datetime

# Get backend URL from environment
BACKEND_URL = "https://contract-audit-demo.preview.emergentagent.com/api"

# Test results tracking
test_results = {
    "passed": [],
    "failed": [],
    "total": 0,
    "details": []
}

def log_test(name, passed, details="", response_data=None):
    """Log test result with detailed information"""
    test_results["total"] += 1
    result_info = {
        "name": name,
        "passed": passed,
        "details": details,
        "response_data": response_data
    }
    test_results["details"].append(result_info)
    
    if passed:
        test_results["passed"].append(name)
        print(f"✅ {name}")
        if details:
            print(f"   {details}")
    else:
        test_results["failed"].append(name)
        print(f"❌ {name}")
        if details:
            print(f"   {details}")

def print_summary():
    """Print comprehensive test summary"""
    print("\n" + "="*80)
    print("ملخص اختبار AutoProfit Pro - TEST SUMMARY")
    print("="*80)
    print(f"إجمالي الاختبارات - Total Tests: {test_results['total']}")
    print(f"نجح - Passed: {len(test_results['passed'])} ✅")
    print(f"فشل - Failed: {len(test_results['failed'])} ❌")
    
    if test_results['failed']:
        print("\nالاختبارات الفاشلة - Failed Tests:")
        for test in test_results['failed']:
            print(f"  - {test}")
    
    print("\n" + "="*80)
    print("تفاصيل الاستجابات - Response Details:")
    print("="*80)
    
    for result in test_results["details"]:
        status = "✅ نجح" if result["passed"] else "❌ فشل"
        print(f"\n{status} - {result['name']}")
        if result["details"]:
            print(f"   التفاصيل: {result['details']}")
        if result["response_data"]:
            print(f"   بيانات الاستجابة: {json.dumps(result['response_data'], indent=2, ensure_ascii=False)[:500]}...")
    
    print("="*80)

def test_financial_ratios():
    """Test GET /api/analytics-advanced/financial-ratios"""
    print("\n[1] اختبار النسب المالية - Testing Financial Ratios")
    try:
        response = requests.get(f"{BACKEND_URL}/analytics-advanced/financial-ratios", timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            
            # Check required fields for frontend
            required_fields = ['ratios']
            if 'ratios' in data:
                ratios = data['ratios']
                ratio_fields = ['current_ratio', 'quick_ratio', 'gross_margin', 'net_margin', 'inventory_turnover', 'debt_ratio']
                missing_fields = [field for field in ratio_fields if field not in ratios]
                
                if not missing_fields:
                    log_test("Financial Ratios API", True, 
                            f"Status: 200 OK, All required fields present", data)
                else:
                    log_test("Financial Ratios API", False, 
                            f"Status: 200 OK but missing fields: {missing_fields}", data)
            else:
                log_test("Financial Ratios API", False, 
                        f"Status: 200 OK but missing 'ratios' field", data)
        else:
            log_test("Financial Ratios API", False, 
                    f"Status: {response.status_code}, Response: {response.text[:300]}")
    except Exception as e:
        log_test("Financial Ratios API", False, f"Exception: {str(e)}")

def test_profit_loss():
    """Test GET /api/analytics-advanced/profit-loss"""
    print("\n[2] اختبار الأرباح والخسائر - Testing Profit & Loss")
    try:
        response = requests.get(f"{BACKEND_URL}/analytics-advanced/profit-loss", timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            
            # Check required fields for frontend
            required_fields = ['revenue', 'cost_of_goods_sold', 'gross_profit', 'operating_expenses', 'net_profit']
            missing_fields = [field for field in required_fields if field not in data]
            
            # Check revenue subfields
            if 'revenue' in data:
                revenue_fields = ['services', 'parts', 'total']
                revenue_missing = [field for field in revenue_fields if field not in data['revenue']]
                if revenue_missing:
                    missing_fields.extend([f"revenue.{field}" for field in revenue_missing])
            
            # Check operating_expenses subfields
            if 'operating_expenses' in data:
                if 'total' not in data['operating_expenses']:
                    missing_fields.append('operating_expenses.total')
            
            if not missing_fields:
                log_test("Profit & Loss API", True, 
                        f"Status: 200 OK, All required fields present", data)
            else:
                log_test("Profit & Loss API", False, 
                        f"Status: 200 OK but missing fields: {missing_fields}", data)
        else:
            log_test("Profit & Loss API", False, 
                    f"Status: {response.status_code}, Response: {response.text[:300]}")
    except Exception as e:
        log_test("Profit & Loss API", False, f"Exception: {str(e)}")

def test_top_performers():
    """Test GET /api/analytics-advanced/top-performers"""
    print("\n[3] اختبار أفضل الأداء - Testing Top Performers")
    try:
        response = requests.get(f"{BACKEND_URL}/analytics-advanced/top-performers", timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            
            # Check required fields for frontend
            required_fields = ['top_services', 'top_parts']
            missing_fields = [field for field in required_fields if field not in data]
            
            # Check if arrays contain required subfields
            if 'top_services' in data and isinstance(data['top_services'], list) and data['top_services']:
                service_fields = ['name', 'count', 'revenue']
                for service in data['top_services'][:1]:  # Check first item
                    service_missing = [field for field in service_fields if field not in service]
                    if service_missing:
                        missing_fields.extend([f"top_services[].{field}" for field in service_missing])
            
            if 'top_parts' in data and isinstance(data['top_parts'], list) and data['top_parts']:
                part_fields = ['name', 'quantity', 'revenue']  # Note: uses 'quantity' not 'count'
                for part in data['top_parts'][:1]:  # Check first item
                    part_missing = [field for field in part_fields if field not in part]
                    if part_missing:
                        missing_fields.extend([f"top_parts[].{field}" for field in part_missing])
            
            if not missing_fields:
                log_test("Top Performers API", True, 
                        f"Status: 200 OK, All required fields present", data)
            else:
                log_test("Top Performers API", False, 
                        f"Status: 200 OK but missing fields: {missing_fields}", data)
        else:
            log_test("Top Performers API", False, 
                    f"Status: {response.status_code}, Response: {response.text[:300]}")
    except Exception as e:
        log_test("Top Performers API", False, f"Exception: {str(e)}")

def test_balance_sheet_summary():
    """Test GET /api/accounts-chart/balance-sheet/summary"""
    print("\n[4] اختبار ملخص الميزانية - Testing Balance Sheet Summary")
    try:
        response = requests.get(f"{BACKEND_URL}/accounts-chart/balance-sheet/summary", timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            
            # Check required fields for frontend
            required_fields = ['assets', 'liabilities', 'net_income', 'revenue']
            missing_fields = [field for field in required_fields if field not in data]
            
            if not missing_fields:
                log_test("Balance Sheet Summary API", True, 
                        f"Status: 200 OK, All required fields present", data)
            else:
                log_test("Balance Sheet Summary API", False, 
                        f"Status: 200 OK but missing fields: {missing_fields}", data)
        else:
            log_test("Balance Sheet Summary API", False, 
                    f"Status: {response.status_code}, Response: {response.text[:300]}")
    except Exception as e:
        log_test("Balance Sheet Summary API", False, f"Exception: {str(e)}")

def test_ai_recommendations():
    """Test GET /api/ai-recommendations"""
    print("\n[5] اختبار توصيات الذكاء الاصطناعي - Testing AI Recommendations")
    try:
        response = requests.get(f"{BACKEND_URL}/ai-recommendations", timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            
            # Check required fields for frontend
            if 'recommendations' in data and isinstance(data['recommendations'], list):
                if data['recommendations']:  # If there are recommendations
                    recommendation_fields = ['id', 'title', 'description', 'priority', 'type', 'current_value', 'recommended_value', 'expected_impact']
                    missing_fields = []
                    for rec in data['recommendations'][:1]:  # Check first recommendation
                        rec_missing = [field for field in recommendation_fields if field not in rec]
                        if rec_missing:
                            missing_fields.extend([f"recommendations[].{field}" for field in rec_missing])
                    
                    if not missing_fields:
                        log_test("AI Recommendations API", True, 
                                f"Status: 200 OK, All required fields present, Count: {len(data['recommendations'])}", data)
                    else:
                        log_test("AI Recommendations API", False, 
                                f"Status: 200 OK but missing fields: {missing_fields}", data)
                else:
                    log_test("AI Recommendations API", True, 
                            f"Status: 200 OK, Empty recommendations array (valid)", data)
            else:
                log_test("AI Recommendations API", False, 
                        f"Status: 200 OK but missing 'recommendations' array", data)
        else:
            log_test("AI Recommendations API", False, 
                    f"Status: {response.status_code}, Response: {response.text[:300]}")
    except Exception as e:
        log_test("AI Recommendations API", False, f"Exception: {str(e)}")

def test_ai_recommendations_stats():
    """Test GET /api/ai-recommendations/stats"""
    print("\n[6] اختبار إحصائيات توصيات الذكاء الاصطناعي - Testing AI Recommendations Stats")
    try:
        response = requests.get(f"{BACKEND_URL}/ai-recommendations/stats", timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            
            # Check required fields for frontend
            required_fields = ['by_priority', 'implemented_value']
            missing_fields = [field for field in required_fields if field not in data]
            
            # Check by_priority subfields
            if 'by_priority' in data:
                priority_fields = ['high', 'medium', 'low']
                priority_missing = [field for field in priority_fields if field not in data['by_priority']]
                if priority_missing:
                    missing_fields.extend([f"by_priority.{field}" for field in priority_missing])
            
            if not missing_fields:
                log_test("AI Recommendations Stats API", True, 
                        f"Status: 200 OK, All required fields present", data)
            else:
                log_test("AI Recommendations Stats API", False, 
                        f"Status: 200 OK but missing fields: {missing_fields}", data)
        else:
            log_test("AI Recommendations Stats API", False, 
                    f"Status: {response.status_code}, Response: {response.text[:300]}")
    except Exception as e:
        log_test("AI Recommendations Stats API", False, f"Exception: {str(e)}")

def check_backend_logs():
    """Check backend logs for any errors during testing"""
    print("\n[7] فحص سجلات الباكند - Checking Backend Logs")
    try:
        # Try to get recent backend logs
        import subprocess
        result = subprocess.run(['tail', '-n', '50', '/var/log/supervisor/backend.err.log'], 
                              capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            logs = result.stdout
            if logs.strip():
                # Look for recent errors
                error_lines = [line for line in logs.split('\n') if 'ERROR' in line or 'Exception' in line]
                if error_lines:
                    log_test("Backend Logs Check", False, 
                            f"Found {len(error_lines)} error lines in recent logs")
                    print("   Recent errors:")
                    for error in error_lines[-3:]:  # Show last 3 errors
                        print(f"   {error}")
                else:
                    log_test("Backend Logs Check", True, 
                            "No recent errors found in backend logs")
            else:
                log_test("Backend Logs Check", True, 
                        "Backend logs are empty (no errors)")
        else:
            log_test("Backend Logs Check", False, 
                    f"Could not read backend logs: {result.stderr}")
    except Exception as e:
        log_test("Backend Logs Check", False, f"Exception checking logs: {str(e)}")

def main():
    """Main test execution"""
    print("\n" + "="*80)
    print("اختبار AutoProfit Pro - AUTOPROFIT PRO BACKEND TESTING")
    print("="*80)
    print(f"Backend URL: {BACKEND_URL}")
    print(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    print("\nاختبار نقاط النهاية المالية الرئيسية (GET فقط حالياً)")
    print("Testing main financial endpoints (GET only currently):")
    print("- GET /api/analytics-advanced/financial-ratios")
    print("- GET /api/analytics-advanced/profit-loss") 
    print("- GET /api/analytics-advanced/top-performers")
    print("- GET /api/accounts-chart/balance-sheet/summary")
    print("- GET /api/ai-recommendations")
    print("- GET /api/ai-recommendations/stats")
    
    # Run all tests
    test_financial_ratios()
    test_profit_loss()
    test_top_performers()
    test_balance_sheet_summary()
    test_ai_recommendations()
    test_ai_recommendations_stats()
    check_backend_logs()
    
    # Print comprehensive summary
    print_summary()
    
    # Exit with appropriate code
    if test_results['failed']:
        print(f"\n❌ {len(test_results['failed'])} اختبار فشل - tests failed")
        sys.exit(1)
    else:
        print(f"\n✅ جميع الاختبارات نجحت - All {len(test_results['passed'])} tests passed")
        sys.exit(0)

if __name__ == "__main__":
    main()