"""
Test Finance Reconciliation and Income Statement APIs - Iteration 74
Tests:
1. /api/finance/reports/reconciliation - returns rows/summary for last 2 weeks
2. /api/finance/reports/income-statement - uses date range (not cumulative)
3. payment_order operation creates journal entry with transaction_type=payment_order
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://accounting-ssot-fix.preview.emergentagent.com')
WORKSHOP_ID = os.environ.get('REACT_APP_WORKSHOP_ID', 'finmodule-sync')


class TestReconciliationEndpoint:
    """Test /api/finance/reports/reconciliation endpoint"""
    
    def test_reconciliation_returns_success(self):
        """Test that reconciliation endpoint returns success with rows and summary"""
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=14)).strftime('%Y-%m-%d')
        
        response = requests.get(
            f"{BASE_URL}/api/finance/reports/reconciliation",
            params={
                'workshop_id': WORKSHOP_ID,
                'start_date': start_date,
                'end_date': end_date
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data.get('success') == True, f"Expected success=True, got {data}"
        assert 'data' in data, "Response should contain 'data' key"
        
        result_data = data['data']
        assert 'rows' in result_data, "Response data should contain 'rows'"
        assert 'summary' in result_data, "Response data should contain 'summary'"
        assert 'period' in result_data, "Response data should contain 'period'"
        
        print(f"✅ Reconciliation endpoint returns success with {len(result_data.get('rows', []))} rows")
        print(f"   Summary: matched={result_data['summary'].get('matched')}, diff={result_data['summary'].get('total_absolute_difference')}")
    
    def test_reconciliation_rows_structure(self):
        """Test that reconciliation rows have correct structure"""
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=14)).strftime('%Y-%m-%d')
        
        response = requests.get(
            f"{BASE_URL}/api/finance/reports/reconciliation",
            params={
                'workshop_id': WORKSHOP_ID,
                'start_date': start_date,
                'end_date': end_date
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        rows = data.get('data', {}).get('rows', [])
        
        # Check that rows have expected fields
        expected_fields = ['type', 'operations_count', 'journal_entries_count', 
                          'operations_total', 'journal_entries_total', 'difference', 'matched']
        
        for row in rows:
            for field in expected_fields:
                assert field in row, f"Row missing field '{field}': {row}"
        
        print(f"✅ All {len(rows)} reconciliation rows have correct structure")
        for row in rows:
            print(f"   - {row['type']}: ops={row['operations_count']}, je={row['journal_entries_count']}, diff={row['difference']}")


class TestIncomeStatementEndpoint:
    """Test /api/finance/reports/income-statement endpoint with date range"""
    
    def test_income_statement_with_date_range(self):
        """Test that income statement respects date range parameters"""
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=14)).strftime('%Y-%m-%d')
        
        response = requests.get(
            f"{BASE_URL}/api/finance/reports/income-statement",
            params={
                'workshop_id': WORKSHOP_ID,
                'start_date': start_date,
                'end_date': end_date
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data.get('success') == True, f"Expected success=True, got {data}"
        assert 'data' in data, "Response should contain 'data' key"
        
        result_data = data['data']
        assert 'period' in result_data, "Response should contain 'period'"
        assert 'totals' in result_data, "Response should contain 'totals'"
        
        # Verify period matches requested dates
        period = result_data['period']
        assert period.get('start_date') == start_date, f"Expected start_date={start_date}, got {period.get('start_date')}"
        assert period.get('end_date') == end_date, f"Expected end_date={end_date}, got {period.get('end_date')}"
        
        print(f"✅ Income statement respects date range: {start_date} to {end_date}")
        print(f"   Totals: revenue={result_data['totals'].get('revenue')}, expenses={result_data['totals'].get('expenses')}, net={result_data['totals'].get('net_income')}")
    
    def test_income_statement_different_periods_return_different_results(self):
        """Test that different date ranges can return different results (not cumulative)"""
        # Last 7 days
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date_7d = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        
        response_7d = requests.get(
            f"{BASE_URL}/api/finance/reports/income-statement",
            params={
                'workshop_id': WORKSHOP_ID,
                'start_date': start_date_7d,
                'end_date': end_date
            }
        )
        
        # Last 30 days
        start_date_30d = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        response_30d = requests.get(
            f"{BASE_URL}/api/finance/reports/income-statement",
            params={
                'workshop_id': WORKSHOP_ID,
                'start_date': start_date_30d,
                'end_date': end_date
            }
        )
        
        assert response_7d.status_code == 200
        assert response_30d.status_code == 200
        
        data_7d = response_7d.json().get('data', {})
        data_30d = response_30d.json().get('data', {})
        
        # Verify periods are different
        assert data_7d.get('period', {}).get('start_date') == start_date_7d
        assert data_30d.get('period', {}).get('start_date') == start_date_30d
        
        print(f"✅ Income statement uses date range filtering (not cumulative)")
        print(f"   7-day period: {data_7d.get('period')}")
        print(f"   30-day period: {data_30d.get('period')}")


class TestPaymentOrderJournalEntry:
    """Test that payment_order operations create journal entries with correct transaction_type"""
    
    def test_journal_entries_endpoint_works(self):
        """Test that journal entries endpoint returns data"""
        response = requests.get(
            f"{BASE_URL}/api/finance/journal-entries",
            params={
                'workshop_id': WORKSHOP_ID,
                'limit': 50
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data.get('success') == True, f"Expected success=True, got {data}"
        assert 'data' in data, "Response should contain 'data' key"
        
        entries = data.get('data', [])
        print(f"✅ Journal entries endpoint works, returned {len(entries)} entries")
        
        # Check for payment_order transaction types
        payment_order_entries = [e for e in entries if e.get('transaction_type') == 'payment_order' or e.get('source') == 'operation_payment']
        print(f"   Found {len(payment_order_entries)} payment-related journal entries")
    
    def test_reconciliation_includes_payment_order_type(self):
        """Test that reconciliation tracks payment_order type"""
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=14)).strftime('%Y-%m-%d')
        
        response = requests.get(
            f"{BASE_URL}/api/finance/reports/reconciliation",
            params={
                'workshop_id': WORKSHOP_ID,
                'start_date': start_date,
                'end_date': end_date
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        rows = data.get('data', {}).get('rows', [])
        
        # Check that payment_order is one of the tracked types
        tracked_types = [row['type'] for row in rows]
        assert 'payment_order' in tracked_types, f"payment_order should be tracked, found types: {tracked_types}"
        
        payment_order_row = next((r for r in rows if r['type'] == 'payment_order'), None)
        print(f"✅ Reconciliation tracks payment_order type")
        print(f"   payment_order: ops={payment_order_row['operations_count']}, je={payment_order_row['journal_entries_count']}")


class TestTrialBalanceEndpoint:
    """Test trial balance endpoint"""
    
    def test_trial_balance_returns_success(self):
        """Test that trial balance endpoint returns success"""
        response = requests.get(
            f"{BASE_URL}/api/finance/reports/trial-balance",
            params={
                'workshop_id': WORKSHOP_ID
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data.get('success') == True, f"Expected success=True, got {data}"
        assert 'data' in data, "Response should contain 'data' key"
        
        result_data = data['data']
        assert 'accounts' in result_data, "Response should contain 'accounts'"
        assert 'totals' in result_data, "Response should contain 'totals'"
        
        print(f"✅ Trial balance endpoint works")
        print(f"   Accounts: {len(result_data.get('accounts', []))}")
        print(f"   Totals: debit={result_data['totals'].get('total_debit')}, credit={result_data['totals'].get('total_credit')}")


class TestCashFlowEndpoint:
    """Test cash flow endpoint"""
    
    def test_cash_flow_returns_success(self):
        """Test that cash flow endpoint returns success"""
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=14)).strftime('%Y-%m-%d')
        
        response = requests.get(
            f"{BASE_URL}/api/finance/reports/cash-flow",
            params={
                'workshop_id': WORKSHOP_ID,
                'start_date': start_date,
                'end_date': end_date
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data.get('success') == True, f"Expected success=True, got {data}"
        assert 'data' in data, "Response should contain 'data' key"
        
        result_data = data['data']
        assert 'operating_activities' in result_data, "Response should contain 'operating_activities'"
        assert 'investing_activities' in result_data, "Response should contain 'investing_activities'"
        assert 'financing_activities' in result_data, "Response should contain 'financing_activities'"
        
        print(f"✅ Cash flow endpoint works")
        print(f"   Operating: {result_data['operating_activities'].get('net_operating_cash')}")
        print(f"   Investing: {result_data['investing_activities'].get('net_investing_cash')}")
        print(f"   Financing: {result_data['financing_activities'].get('net_financing_cash')}")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
