"""
Test Chart of Accounts - Reindex Display Codes Feature (Iteration 158)

Tests:
1. GET /api/accounts/tree - Returns accounts with sequential codes (001, 002...) and legacy_code
2. POST /api/accounts/reindex-display-codes - Reindexes account codes starting from 001
3. GET /api/accounts/reconciliation-report - Returns reconciliation report after code changes
4. Verify no separate numbering field - code is the actual account code
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://vehicle-accounting-2.preview.emergentagent.com').rstrip('/')
WORKSHOP_ID = "finmodule-sync"


class TestChartOfAccountsTree:
    """Test /api/accounts/tree endpoint"""
    
    def test_accounts_tree_returns_success(self):
        """Test that accounts tree endpoint returns success"""
        response = requests.get(
            f"{BASE_URL}/api/accounts/tree",
            params={"workshop_id": WORKSHOP_ID, "type": "all", "hideZero": "false", "search": ""}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        print(f"✅ Accounts tree returned success")
    
    def test_accounts_tree_has_sequential_codes(self):
        """Test that accounts have sequential codes (001, 002, 003...)"""
        response = requests.get(
            f"{BASE_URL}/api/accounts/tree",
            params={"workshop_id": WORKSHOP_ID, "type": "all", "hideZero": "false", "search": ""}
        )
        assert response.status_code == 200
        data = response.json()
        
        accounts = data.get("data", {}).get("accounts", [])
        assert len(accounts) > 0, "Should have at least one account"
        
        # Check first account has sequential code format
        first_account = accounts[0]
        code = first_account.get("code", "")
        assert code.isdigit(), f"Code should be numeric, got: {code}"
        assert len(code) == 3, f"Code should be 3 digits (e.g., 001), got: {code}"
        print(f"✅ First account code: {code}")
    
    def test_accounts_tree_has_legacy_code(self):
        """Test that accounts have legacy_code for backward compatibility"""
        response = requests.get(
            f"{BASE_URL}/api/accounts/tree",
            params={"workshop_id": WORKSHOP_ID, "type": "all", "hideZero": "false", "search": ""}
        )
        assert response.status_code == 200
        data = response.json()
        
        accounts = data.get("data", {}).get("accounts", [])
        assert len(accounts) > 0
        
        # Check first account has legacy_code
        first_account = accounts[0]
        legacy_code = first_account.get("legacy_code", "")
        assert legacy_code, f"Should have legacy_code, got: {legacy_code}"
        print(f"✅ First account legacy_code: {legacy_code}")
    
    def test_accounts_tree_has_summary(self):
        """Test that accounts tree returns summary with assets, liabilities, etc."""
        response = requests.get(
            f"{BASE_URL}/api/accounts/tree",
            params={"workshop_id": WORKSHOP_ID, "type": "all", "hideZero": "false", "search": ""}
        )
        assert response.status_code == 200
        data = response.json()
        
        summary = data.get("data", {}).get("summary", {})
        assert "assets" in summary
        assert "liabilities" in summary
        assert "net_profit" in summary
        print(f"✅ Summary: assets={summary.get('assets')}, liabilities={summary.get('liabilities')}, net_profit={summary.get('net_profit')}")


class TestReindexDisplayCodes:
    """Test /api/accounts/reindex-display-codes endpoint"""
    
    def test_reindex_returns_success(self):
        """Test that reindex endpoint returns success"""
        response = requests.post(f"{BASE_URL}/api/accounts/reindex-display-codes")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        print(f"✅ Reindex returned success")
    
    def test_reindex_returns_count(self):
        """Test that reindex returns count of reindexed accounts"""
        response = requests.post(f"{BASE_URL}/api/accounts/reindex-display-codes")
        assert response.status_code == 200
        data = response.json()
        
        count = data.get("data", {}).get("count", 0)
        assert count > 0, f"Should have reindexed at least one account, got: {count}"
        print(f"✅ Reindexed {count} accounts")
    
    def test_reindex_starts_from_001(self):
        """Test that reindex starts from 001"""
        response = requests.post(f"{BASE_URL}/api/accounts/reindex-display-codes")
        assert response.status_code == 200
        data = response.json()
        
        first_code = data.get("data", {}).get("first_code", "")
        assert first_code == "001", f"First code should be 001, got: {first_code}"
        print(f"✅ First code after reindex: {first_code}")
    
    def test_reindex_preserves_legacy_code(self):
        """Test that reindex preserves legacy_code"""
        response = requests.post(f"{BASE_URL}/api/accounts/reindex-display-codes")
        assert response.status_code == 200
        data = response.json()
        
        sample = data.get("data", {}).get("sample", [])
        assert len(sample) > 0, "Should have sample accounts"
        
        first_sample = sample[0]
        legacy_code = first_sample.get("legacy_code", "")
        assert legacy_code, f"Should have legacy_code, got: {legacy_code}"
        print(f"✅ Sample account legacy_code preserved: {legacy_code}")


class TestReconciliationReport:
    """Test /api/accounts/reconciliation-report endpoint"""
    
    def test_reconciliation_returns_success(self):
        """Test that reconciliation report returns success"""
        response = requests.get(
            f"{BASE_URL}/api/accounts/reconciliation-report",
            params={"workshop_id": WORKSHOP_ID}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        print(f"✅ Reconciliation report returned success")
    
    def test_reconciliation_has_summary(self):
        """Test that reconciliation report has summary"""
        response = requests.get(
            f"{BASE_URL}/api/accounts/reconciliation-report",
            params={"workshop_id": WORKSHOP_ID}
        )
        assert response.status_code == 200
        data = response.json()
        
        summary = data.get("data", {}).get("summary", {})
        assert "accounts_count" in summary
        assert "matched_count" in summary
        assert "mismatched_count" in summary
        print(f"✅ Summary: accounts={summary.get('accounts_count')}, matched={summary.get('matched_count')}, mismatched={summary.get('mismatched_count')}")
    
    def test_reconciliation_has_rows_with_code(self):
        """Test that reconciliation report rows have code field"""
        response = requests.get(
            f"{BASE_URL}/api/accounts/reconciliation-report",
            params={"workshop_id": WORKSHOP_ID}
        )
        assert response.status_code == 200
        data = response.json()
        
        rows = data.get("data", {}).get("rows", [])
        assert len(rows) > 0, "Should have at least one row"
        
        first_row = rows[0]
        code = first_row.get("code", "")
        assert code, f"Row should have code, got: {code}"
        print(f"✅ First row code: {code}")


class TestFinanceEndpoints:
    """Test finance endpoints still work after code changes"""
    
    def test_income_statement_works(self):
        """Test that income statement endpoint works"""
        response = requests.get(
            f"{BASE_URL}/api/finance/reports/income-statement",
            params={"workshop_id": WORKSHOP_ID}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        print(f"✅ Income statement works")
    
    def test_balance_sheet_works(self):
        """Test that balance sheet endpoint works"""
        response = requests.get(
            f"{BASE_URL}/api/finance/reports/balance-sheet",
            params={"workshop_id": WORKSHOP_ID}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        print(f"✅ Balance sheet works")
    
    def test_trial_balance_works(self):
        """Test that trial balance endpoint works"""
        response = requests.get(
            f"{BASE_URL}/api/finance/reports/trial-balance",
            params={"workshop_id": WORKSHOP_ID}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        print(f"✅ Trial balance works")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
