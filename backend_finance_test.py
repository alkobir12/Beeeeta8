#!/usr/bin/env python3
"""
Backend Finance API Testing Script

Testing the following financial reporting endpoints after recent accounting modifications:
1. GET /api/finance/reports/reconciliation?workshop_id=finmodule-sync&start_date=<last14days>&end_date=<today>
2. GET /api/finance/reports/income-statement for the same period
3. GET /api/finance/reports/balance-sheet?workshop_id=finmodule-sync&as_of_date=<today>
4. Check for no 500 errors in these flows
5. Verify that type=payment_order appears in reconciliation rows (even if difference is not zero)
"""

import requests
import json
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, List

class FinanceAPITester:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        self.workshop_id = "finmodule-sync"
        
        # Calculate date range (last 14 days)
        today = datetime.now()
        self.end_date = today.strftime("%Y-%m-%d")
        self.start_date = (today - timedelta(days=14)).strftime("%Y-%m-%d")
        
        print(f"📅 Test Period: {self.start_date} to {self.end_date}")
        print(f"🏪 Workshop ID: {self.workshop_id}")

    def test_reconciliation_report(self) -> Dict[str, Any]:
        """Test GET /api/finance/reports/reconciliation - should return success=true with summary and rows"""
        print("🔍 Testing: GET /api/finance/reports/reconciliation")
        
        try:
            params = {
                'workshop_id': self.workshop_id,
                'start_date': self.start_date,
                'end_date': self.end_date
            }
            
            response = self.session.get(
                f"{self.base_url}/api/finance/reports/reconciliation",
                params=params
            )
            
            result = {
                "endpoint": "/api/finance/reports/reconciliation",
                "status_code": response.status_code,
                "success": False,
                "issues": [],
                "payment_order_found": False
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
                
            # Check for success=true
            if not data.get("success"):
                result["issues"].append("Response success is not true")
                
            # Check for summary field
            if "data" not in data:
                result["issues"].append("Missing 'data' field in response")
            else:
                data_section = data["data"]
                
                if "summary" not in data_section:
                    result["issues"].append("Missing 'summary' field in data")
                else:
                    summary = data_section["summary"]
                    if "matched" not in summary:
                        result["issues"].append("Missing 'matched' field in summary")
                    if "total_absolute_difference" not in summary:
                        result["issues"].append("Missing 'total_absolute_difference' field in summary")
                
                # Check for rows field
                if "rows" not in data_section:
                    result["issues"].append("Missing 'rows' field in data")
                else:
                    rows = data_section["rows"]
                    if not isinstance(rows, list):
                        result["issues"].append("'rows' should be an array")
                    else:
                        # Check for payment_order type in rows
                        payment_order_types = [row for row in rows if row.get("type") == "payment_order"]
                        if payment_order_types:
                            result["payment_order_found"] = True
                            print(f"   ✅ Found payment_order entries: {len(payment_order_types)}")
                        else:
                            print(f"   ⚠️ No payment_order entries found in {len(rows)} rows")
                            
            if not result["issues"]:
                result["success"] = True
                print("✅ Reconciliation Report: PASSED - success=true with summary and rows")
                if result["payment_order_found"]:
                    print("   ✅ payment_order type found in reconciliation rows")
            else:
                print("❌ Reconciliation Report: FAILED")
                for issue in result["issues"]:
                    print(f"   - {issue}")
                    
            return result
            
        except requests.exceptions.RequestException as e:
            result = {
                "endpoint": "/api/finance/reports/reconciliation",
                "status_code": None,
                "success": False,
                "issues": [f"Request failed: {e}"],
                "payment_order_found": False
            }
            print("❌ Reconciliation Report: FAILED - Request error")
            print(f"   - {e}")
            return result

    def test_income_statement_report(self) -> Dict[str, Any]:
        """Test GET /api/finance/reports/income-statement - should have totals present"""
        print("🔍 Testing: GET /api/finance/reports/income-statement")
        
        try:
            params = {
                'workshop_id': self.workshop_id,
                'start_date': self.start_date,
                'end_date': self.end_date
            }
            
            response = self.session.get(
                f"{self.base_url}/api/finance/reports/income-statement",
                params=params
            )
            
            result = {
                "endpoint": "/api/finance/reports/income-statement",
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
                
            # Check for success=true
            if not data.get("success"):
                result["issues"].append("Response success is not true")
                
            # Check for data and totals
            if "data" not in data:
                result["issues"].append("Missing 'data' field in response")
            else:
                data_section = data["data"]
                
                if "totals" not in data_section:
                    result["issues"].append("Missing 'totals' field in data")
                else:
                    totals = data_section["totals"]
                    required_totals = ["revenue", "expenses", "net_income"]
                    
                    for field in required_totals:
                        if field not in totals:
                            result["issues"].append(f"Missing '{field}' in totals")
                        else:
                            try:
                                float(totals[field])
                            except (TypeError, ValueError):
                                result["issues"].append(f"totals.{field} is not numeric: {totals[field]}")
                                
            if not result["issues"]:
                result["success"] = True
                print("✅ Income Statement: PASSED - totals present with required fields")
                if "data" in data and "totals" in data["data"]:
                    totals = data["data"]["totals"]
                    print(f"   - Revenue: {totals.get('revenue', 0)}")
                    print(f"   - Expenses: {totals.get('expenses', 0)}")
                    print(f"   - Net Income: {totals.get('net_income', 0)}")
            else:
                print("❌ Income Statement: FAILED")
                for issue in result["issues"]:
                    print(f"   - {issue}")
                    
            return result
            
        except requests.exceptions.RequestException as e:
            result = {
                "endpoint": "/api/finance/reports/income-statement",
                "status_code": None,
                "success": False,
                "issues": [f"Request failed: {e}"]
            }
            print("❌ Income Statement: FAILED - Request error")
            print(f"   - {e}")
            return result

    def test_balance_sheet_report(self) -> Dict[str, Any]:
        """Test GET /api/finance/reports/balance-sheet - should return proper balance sheet structure"""
        print("🔍 Testing: GET /api/finance/reports/balance-sheet")
        
        try:
            params = {
                'workshop_id': self.workshop_id,
                'as_of_date': self.end_date
            }
            
            response = self.session.get(
                f"{self.base_url}/api/finance/reports/balance-sheet",
                params=params
            )
            
            result = {
                "endpoint": "/api/finance/reports/balance-sheet",
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
                
            # Check for success=true
            if not data.get("success"):
                result["issues"].append("Response success is not true")
                
            # Check for data structure
            if "data" not in data:
                result["issues"].append("Missing 'data' field in response")
            else:
                data_section = data["data"]
                
                # Check for totals
                if "totals" not in data_section:
                    result["issues"].append("Missing 'totals' field in data")
                else:
                    totals = data_section["totals"]
                    required_totals = ["assets", "liabilities", "equity", "liabilities_plus_equity"]
                    
                    for field in required_totals:
                        if field not in totals:
                            result["issues"].append(f"Missing '{field}' in totals")
                        else:
                            try:
                                float(totals[field])
                            except (TypeError, ValueError):
                                result["issues"].append(f"totals.{field} is not numeric: {totals[field]}")
                
                # Check for sections
                if "sections" not in data_section:
                    result["issues"].append("Missing 'sections' field in data")
                else:
                    sections = data_section["sections"]
                    required_sections = ["assets", "liabilities", "equity"]
                    
                    for section in required_sections:
                        if section not in sections:
                            result["issues"].append(f"Missing '{section}' section")
                        elif not isinstance(sections[section], list):
                            result["issues"].append(f"Section '{section}' should be an array")
                            
            if not result["issues"]:
                result["success"] = True
                print("✅ Balance Sheet: PASSED - proper structure with totals and sections")
                if "data" in data and "totals" in data["data"]:
                    totals = data["data"]["totals"]
                    print(f"   - Assets: {totals.get('assets', 0)}")
                    print(f"   - Liabilities: {totals.get('liabilities', 0)}")
                    print(f"   - Equity: {totals.get('equity', 0)}")
                    print(f"   - L+E: {totals.get('liabilities_plus_equity', 0)}")
            else:
                print("❌ Balance Sheet: FAILED")
                for issue in result["issues"]:
                    print(f"   - {issue}")
                    
            return result
            
        except requests.exceptions.RequestException as e:
            result = {
                "endpoint": "/api/finance/reports/balance-sheet",
                "status_code": None,
                "success": False,
                "issues": [f"Request failed: {e}"]
            }
            print("❌ Balance Sheet: FAILED - Request error")
            print(f"   - {e}")
            return result

    def test_no_500_errors(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Check that none of the APIs returned 500 errors"""
        print("🔍 Testing: No 500 errors in financial reports")
        
        result = {
            "test": "no_500_errors",
            "success": True,
            "issues": []
        }
        
        for test_result in results:
            if test_result.get("status_code") == 500:
                result["success"] = False
                result["issues"].append(f"{test_result['endpoint']}: returned 500 error")
                
        if result["success"]:
            print("✅ No 500 Errors: PASSED - All financial APIs returned non-500 status codes")
        else:
            print("❌ No 500 Errors: FAILED")
            for issue in result["issues"]:
                print(f"   - {issue}")
                
        return result

    def run_all_tests(self) -> Dict[str, Any]:
        """Run all financial report tests and return summary"""
        print(f"🚀 Starting Backend Finance API Tests")
        print(f"Base URL: {self.base_url}")
        print("=" * 60)
        
        results = []
        
        # Test 1: Reconciliation Report
        results.append(self.test_reconciliation_report())
        print()
        
        # Test 2: Income Statement Report
        results.append(self.test_income_statement_report())
        print()
        
        # Test 3: Balance Sheet Report
        results.append(self.test_balance_sheet_report())
        print()
        
        # Test 4: No 500 errors
        no_500_result = self.test_no_500_errors(results)
        results.append(no_500_result)
        print()
        
        # Summary
        print("=" * 60)
        print("📊 FINANCE API TEST SUMMARY")
        print("=" * 60)
        
        passed_count = sum(1 for r in results if r.get("success", False))
        total_count = len(results)
        
        for result in results:
            endpoint = result.get("endpoint", result.get("test", "Unknown"))
            status = "✅ PASS" if result.get("success", False) else "❌ FAIL"
            print(f"{status} {endpoint}")
            
        # Special note about payment_order
        reconciliation_result = next((r for r in results if r.get("endpoint") == "/api/finance/reports/reconciliation"), None)
        if reconciliation_result and reconciliation_result.get("payment_order_found"):
            print("   ✅ payment_order type found in reconciliation rows")
        elif reconciliation_result:
            print("   ⚠️ payment_order type not found in reconciliation rows")
            
        print(f"\nOverall: {passed_count}/{total_count} tests passed")
        
        overall_success = passed_count == total_count
        
        if overall_success:
            print("🎉 ALL FINANCE TESTS PASSED - Financial reporting APIs working correctly!")
        else:
            print("⚠️ SOME FINANCE TESTS FAILED - Check logs above for details")
            
        return {
            "overall_success": overall_success,
            "passed_count": passed_count,
            "total_count": total_count,
            "results": results
        }


def main():
    """Main function to run the finance tests"""
    # Use the base URL from frontend/.env
    BASE_URL = "https://vehicle-accounting-2.preview.emergentagent.com"
    
    if len(sys.argv) > 1:
        BASE_URL = sys.argv[1]
        
    print("Backend Finance APIs Testing")
    print("=" * 60)
    
    tester = FinanceAPITester(BASE_URL)
    summary = tester.run_all_tests()
    
    # Exit with appropriate code
    exit_code = 0 if summary["overall_success"] else 1
    sys.exit(exit_code)


if __name__ == "__main__":
    main()