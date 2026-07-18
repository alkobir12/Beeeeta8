"""
Test Finance Dashboard APIs - Iteration 111
Tests for:
- /api/finance/reports/ar-customers endpoint (alias)
- /api/finance/reports/income-statement endpoint
- /api/finance/reports/balance-sheet endpoint
- Data parsing and response structure
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://payment-defaults.preview.emergentagent.com')
WORKSHOP_ID = "finmodule-sync"


class TestFinanceDashboardAPIs:
    """Finance Dashboard API tests"""

    def test_ar_customers_endpoint_alias(self):
        """Test /api/finance/reports/ar-customers endpoint (alias)"""
        response = requests.get(
            f"{BASE_URL}/api/finance/reports/ar-customers",
            params={"workshop_id": WORKSHOP_ID, "as_of": "2026-04-11"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("success") == True, "Expected success=true"
        assert "data" in data, "Expected 'data' key in response"
        assert "customers" in data["data"], "Expected 'customers' in data"
        assert "total_ar" in data["data"], "Expected 'total_ar' in data"
        
        # Verify total_ar is a number
        total_ar = data["data"]["total_ar"]
        assert isinstance(total_ar, (int, float)), f"Expected total_ar to be a number, got {type(total_ar)}"
        print(f"AR Customers endpoint works - total_ar: {total_ar}")

    def test_ar_customers_original_endpoint(self):
        """Test /api/finance/ar/customers endpoint (original)"""
        response = requests.get(
            f"{BASE_URL}/api/finance/ar/customers",
            params={"workshop_id": WORKSHOP_ID, "as_of": "2026-04-11"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("success") == True, "Expected success=true"
        print(f"AR Customers original endpoint works")

    def test_income_statement_endpoint(self):
        """Test /api/finance/reports/income-statement endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/finance/reports/income-statement",
            params={
                "workshop_id": WORKSHOP_ID,
                "start_date": "2026-03-28",
                "end_date": "2026-04-11"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("success") == True, "Expected success=true"
        assert "data" in data, "Expected 'data' key in response"
        assert "totals" in data["data"], "Expected 'totals' in data"
        
        totals = data["data"]["totals"]
        assert "revenue" in totals, "Expected 'revenue' in totals"
        assert "expenses" in totals, "Expected 'expenses' in totals"
        assert "net_income" in totals, "Expected 'net_income' in totals"
        
        # Verify net_income is calculated correctly
        net_income = totals["net_income"]
        expected_net = totals["revenue"] - totals["expenses"]
        assert abs(net_income - expected_net) < 0.01, f"Net income mismatch: {net_income} vs {expected_net}"
        print(f"Income Statement endpoint works - net_income: {net_income}")

    def test_balance_sheet_endpoint(self):
        """Test /api/finance/reports/balance-sheet endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/finance/reports/balance-sheet",
            params={"workshop_id": WORKSHOP_ID, "as_of_date": "2026-04-11"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("success") == True, "Expected success=true"
        assert "data" in data, "Expected 'data' key in response"
        assert "totals" in data["data"], "Expected 'totals' in data"
        
        totals = data["data"]["totals"]
        assert "assets" in totals, "Expected 'assets' in totals"
        assert "liabilities" in totals, "Expected 'liabilities' in totals"
        assert "equity" in totals, "Expected 'equity' in totals"
        print(f"Balance Sheet endpoint works - assets: {totals['assets']}")

    def test_response_structure_for_frontend_parsing(self):
        """Test that response structure matches frontend expectations"""
        # Frontend expects: { success: true, data: { ... } }
        # And uses unwrapApiData which checks response.data.data
        
        response = requests.get(
            f"{BASE_URL}/api/finance/reports/income-statement",
            params={
                "workshop_id": WORKSHOP_ID,
                "start_date": "2026-03-28",
                "end_date": "2026-04-11"
            }
        )
        
        data = response.json()
        
        # Verify structure
        assert "success" in data, "Missing 'success' key"
        assert "data" in data, "Missing 'data' key"
        
        # The frontend's unwrapApiData function expects:
        # - response.data.data (axios wraps in data, then API has data)
        # So the API response should have: { success: true, data: { totals: {...} } }
        inner_data = data["data"]
        assert isinstance(inner_data, dict), "data should be a dict"
        assert "totals" in inner_data, "data should contain 'totals'"
        
        print("Response structure matches frontend expectations")

    def test_net_income_not_zero_with_data(self):
        """Test that net income is not incorrectly zero when there's actual data"""
        response = requests.get(
            f"{BASE_URL}/api/finance/reports/income-statement",
            params={
                "workshop_id": WORKSHOP_ID,
                "start_date": "2025-01-01",  # Wider date range
                "end_date": "2026-04-15"
            }
        )
        
        data = response.json()
        assert data.get("success") == True
        
        totals = data["data"]["totals"]
        revenue = totals["revenue"]
        expenses = totals["expenses"]
        net_income = totals["net_income"]
        
        # If there's revenue or expenses, net_income should not be zero
        if revenue > 0 or expenses > 0:
            # Net income should be revenue - expenses
            expected = revenue - expenses
            assert abs(net_income - expected) < 0.01, f"Net income should be {expected}, got {net_income}"
            print(f"Net income correctly calculated: {net_income} (revenue: {revenue}, expenses: {expenses})")
        else:
            print("No revenue or expenses in the period - net income is correctly 0")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
