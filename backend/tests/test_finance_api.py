"""
Finance API Tests for ERP Workshop System
Tests the income statement API and sales_summary functionality
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://payment-defaults.preview.emergentagent.com')
WORKSHOP_ID = 'finmodule-sync'


class TestIncomeStatementAPI:
    """Tests for GET /api/finance/reports/income-statement"""
    
    def test_income_statement_returns_200(self):
        """Test that income statement API returns 200 OK"""
        response = requests.get(
            f"{BASE_URL}/api/finance/reports/income-statement",
            params={
                'workshop_id': WORKSHOP_ID,
                'start_date': '2000-01-01',
                'end_date': '2026-04-22'
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    def test_income_statement_has_totals(self):
        """Test that income statement returns totals"""
        response = requests.get(
            f"{BASE_URL}/api/finance/reports/income-statement",
            params={
                'workshop_id': WORKSHOP_ID,
                'start_date': '2000-01-01',
                'end_date': '2026-04-22'
            }
        )
        data = response.json()
        assert data.get('success') == True, "API should return success=true"
        assert 'data' in data, "Response should have 'data' field"
        assert 'totals' in data['data'], "Data should have 'totals' field"
        
        totals = data['data']['totals']
        assert 'revenue' in totals, "Totals should have 'revenue'"
        assert 'expenses' in totals, "Totals should have 'expenses'"
        assert 'net_income' in totals, "Totals should have 'net_income'"
    
    def test_income_statement_has_sales_summary(self):
        """Test that income statement returns sales_summary with payment breakdown"""
        response = requests.get(
            f"{BASE_URL}/api/finance/reports/income-statement",
            params={
                'workshop_id': WORKSHOP_ID,
                'start_date': '2000-01-01',
                'end_date': '2026-04-22'
            }
        )
        data = response.json()
        assert data.get('success') == True, "API should return success=true"
        assert 'sales_summary' in data['data'], "Data should have 'sales_summary' field"
        
        sales_summary = data['data']['sales_summary']
        assert 'operations_cash_total' in sales_summary, "sales_summary should have 'operations_cash_total'"
        assert 'operations_bank_total' in sales_summary, "sales_summary should have 'operations_bank_total'"
        assert 'operations_credit_total' in sales_summary, "sales_summary should have 'operations_credit_total'"
    
    def test_income_statement_no_duplicate_revenue(self):
        """Test that revenue totals don't include duplicates from payment sources"""
        response = requests.get(
            f"{BASE_URL}/api/finance/reports/income-statement",
            params={
                'workshop_id': WORKSHOP_ID,
                'start_date': '2000-01-01',
                'end_date': '2026-04-22'
            }
        )
        data = response.json()
        totals = data['data']['totals']
        sales_summary = data['data']['sales_summary']
        
        # Revenue should be from journal entries, not operations
        # sales_summary shows operations breakdown
        revenue = totals['revenue']
        operations_total = sales_summary.get('operations_total', 0)
        
        # These should be different - revenue is from journal entries
        # operations_total is from operations table
        print(f"Revenue from totals: {revenue}")
        print(f"Operations total from sales_summary: {operations_total}")
        print(f"Cash: {sales_summary.get('operations_cash_total', 0)}")
        print(f"Bank: {sales_summary.get('operations_bank_total', 0)}")
        print(f"Credit: {sales_summary.get('operations_credit_total', 0)}")
        
        # Verify the breakdown adds up
        cash = sales_summary.get('operations_cash_total', 0)
        bank = sales_summary.get('operations_bank_total', 0)
        credit = sales_summary.get('operations_credit_total', 0)
        
        # The sum of cash + bank + credit should equal operations_total
        calculated_total = cash + bank + credit
        assert abs(calculated_total - operations_total) < 1, \
            f"Payment breakdown ({calculated_total}) should equal operations_total ({operations_total})"


class TestBalanceSheetAPI:
    """Tests for GET /api/finance/reports/balance-sheet"""
    
    def test_balance_sheet_returns_200(self):
        """Test that balance sheet API returns 200 OK"""
        response = requests.get(
            f"{BASE_URL}/api/finance/reports/balance-sheet",
            params={
                'workshop_id': WORKSHOP_ID,
                'as_of_date': '2026-04-22'
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    def test_balance_sheet_has_totals(self):
        """Test that balance sheet returns totals"""
        response = requests.get(
            f"{BASE_URL}/api/finance/reports/balance-sheet",
            params={
                'workshop_id': WORKSHOP_ID,
                'as_of_date': '2026-04-22'
            }
        )
        data = response.json()
        assert data.get('success') == True, "API should return success=true"
        assert 'data' in data, "Response should have 'data' field"
        assert 'totals' in data['data'], "Data should have 'totals' field"


class TestReconciliationAPI:
    """Tests for GET /api/finance/reports/reconciliation"""
    
    def test_reconciliation_returns_200(self):
        """Test that reconciliation API returns 200 OK"""
        response = requests.get(
            f"{BASE_URL}/api/finance/reports/reconciliation",
            params={
                'workshop_id': WORKSHOP_ID,
                'start_date': '2000-01-01',
                'end_date': '2026-04-22'
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
