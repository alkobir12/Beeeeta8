"""
Test for intermittent zeros issue in financial dashboard.
Tests backend APIs for income-statement and balance-sheet stability.
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://accounting-ssot-fix.preview.emergentagent.com').rstrip('/')
WORKSHOP_ID = "finmodule-sync"


class TestFinanceAPIStability:
    """Test financial APIs for stability and consistency"""
    
    def test_income_statement_consistency(self):
        """Test income-statement API returns consistent data across multiple calls"""
        results = []
        
        for i in range(5):
            response = requests.get(
                f"{BASE_URL}/api/finance/reports/income-statement",
                params={
                    "workshop_id": WORKSHOP_ID,
                    "start_date": "2000-01-01",
                    "end_date": "2026-01-15"
                }
            )
            
            assert response.status_code == 200, f"Call {i+1}: Expected 200, got {response.status_code}"
            
            data = response.json()
            assert data.get("success") == True, f"Call {i+1}: API returned success=false"
            
            # Extract key values
            totals = data.get("data", {}).get("totals", {})
            sales_summary = data.get("data", {}).get("sales_summary", {})
            
            result = {
                "revenue": totals.get("revenue", 0),
                "expenses": totals.get("expenses", 0),
                "net_income": totals.get("net_income", 0),
                "operations_cash_total": sales_summary.get("operations_cash_total", 0),
                "operations_bank_total": sales_summary.get("operations_bank_total", 0),
                "operations_credit_total": sales_summary.get("operations_credit_total", 0),
            }
            results.append(result)
            
            print(f"Call {i+1}: net_income={result['net_income']}, cash={result['operations_cash_total']}, bank={result['operations_bank_total']}")
            
            time.sleep(0.5)  # Small delay between calls
        
        # Check consistency
        first_result = results[0]
        for i, result in enumerate(results[1:], 2):
            assert result == first_result, f"Call {i} differs from call 1: {result} != {first_result}"
        
        print("✅ All 5 calls returned consistent data")
    
    def test_balance_sheet_consistency(self):
        """Test balance-sheet API returns consistent data across multiple calls"""
        results = []
        
        for i in range(5):
            response = requests.get(
                f"{BASE_URL}/api/finance/reports/balance-sheet",
                params={
                    "workshop_id": WORKSHOP_ID,
                    "as_of_date": "2026-01-15"
                }
            )
            
            assert response.status_code == 200, f"Call {i+1}: Expected 200, got {response.status_code}"
            
            data = response.json()
            assert data.get("success") == True, f"Call {i+1}: API returned success=false"
            
            # Extract key values
            totals = data.get("data", {}).get("totals", {})
            
            result = {
                "assets": totals.get("assets", 0),
                "liabilities": totals.get("liabilities", 0),
                "equity": totals.get("equity", 0),
            }
            results.append(result)
            
            print(f"Call {i+1}: assets={result['assets']}, liabilities={result['liabilities']}, equity={result['equity']}")
            
            time.sleep(0.5)  # Small delay between calls
        
        # Check consistency
        first_result = results[0]
        for i, result in enumerate(results[1:], 2):
            assert result == first_result, f"Call {i} differs from call 1: {result} != {first_result}"
        
        print("✅ All 5 calls returned consistent data")
    
    def test_sales_summary_in_income_statement(self):
        """Test that sales_summary is always present in income-statement response"""
        response = requests.get(
            f"{BASE_URL}/api/finance/reports/income-statement",
            params={
                "workshop_id": WORKSHOP_ID,
                "start_date": "2000-01-01",
                "end_date": "2026-01-15"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        
        # Check sales_summary structure
        sales_summary = data.get("data", {}).get("sales_summary", {})
        
        required_fields = [
            "operations_total",
            "operations_count",
            "operations_cash_total",
            "operations_bank_total",
            "operations_credit_total"
        ]
        
        for field in required_fields:
            assert field in sales_summary, f"Missing field: {field}"
            print(f"  {field}: {sales_summary[field]}")
        
        print("✅ sales_summary structure is correct")
    
    def test_rapid_refresh_stability(self):
        """Test rapid consecutive API calls (simulating user clicking refresh multiple times)"""
        results = []
        
        # Rapid fire 10 requests
        for i in range(10):
            response = requests.get(
                f"{BASE_URL}/api/finance/reports/income-statement",
                params={
                    "workshop_id": WORKSHOP_ID,
                    "start_date": "2000-01-01",
                    "end_date": "2026-01-15"
                }
            )
            
            assert response.status_code == 200, f"Call {i+1}: Expected 200, got {response.status_code}"
            
            data = response.json()
            net_income = data.get("data", {}).get("totals", {}).get("net_income", 0)
            results.append(net_income)
            
            # No delay - rapid fire
        
        # Check all results are the same
        unique_values = set(results)
        assert len(unique_values) == 1, f"Inconsistent results: {unique_values}"
        
        print(f"✅ All 10 rapid calls returned consistent net_income: {results[0]}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
