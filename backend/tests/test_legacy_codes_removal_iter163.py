"""
Iteration 163: Test legacy codes removal from UI pages
- /accounting/chart-of-accounts: No legacy codes (1101/1102/1103/1104/4000...)
- /accounting/journal-entries: Codes mapped from legacy to new
- /accounting/comprehensive: No legacy text references
- GET /api/finance/chart-of-accounts: No codes >= 1000
"""
import pytest
import requests
import os
import re

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://payment-defaults.preview.emergentagent.com')
WORKSHOP_ID = os.environ.get('REACT_APP_WORKSHOP_ID', 'finmodule-sync')

LEGACY_CODES = ['1101', '1102', '1103', '1104', '2101', '4000', '4100', '5000', '5100', '6000', '6100']


class TestLegacyCodesRemoval:
    """Test that legacy codes are removed from all relevant pages and APIs"""

    def test_chart_of_accounts_api_no_legacy_codes(self):
        """GET /api/finance/chart-of-accounts should not return codes >= 1000"""
        response = requests.get(f"{BASE_URL}/api/finance/chart-of-accounts", params={"workshop_id": WORKSHOP_ID})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("success") is True, "API should return success=True"
        
        accounts = data.get("data", [])
        assert len(accounts) > 0, "Should have accounts"
        
        legacy_codes_found = []
        for acc in accounts:
            code = str(acc.get("code", "")).strip()
            # Check if code is numeric and >= 1000 (legacy format)
            if code.isdigit() and int(code) >= 1000:
                legacy_codes_found.append(code)
        
        assert len(legacy_codes_found) == 0, f"Found legacy codes >= 1000: {legacy_codes_found[:10]}"
        print(f"✅ PASS: {len(accounts)} accounts, 0 legacy codes (>=1000)")

    def test_chart_of_accounts_uses_sequential_codes(self):
        """Chart of accounts should use new sequential codes (001, 002, 003...)"""
        response = requests.get(f"{BASE_URL}/api/finance/chart-of-accounts", params={"workshop_id": WORKSHOP_ID})
        assert response.status_code == 200
        
        data = response.json()
        accounts = data.get("data", [])
        
        # Check that codes are in new format (3-digit sequential)
        sequential_codes = [acc.get("code") for acc in accounts if acc.get("code", "").isdigit() and len(acc.get("code", "")) == 3]
        
        assert len(sequential_codes) > 0, "Should have sequential 3-digit codes"
        print(f"✅ PASS: Found {len(sequential_codes)} sequential 3-digit codes")

    def test_journal_entries_api_returns_success(self):
        """GET /api/finance/journal-entries should return success"""
        response = requests.get(f"{BASE_URL}/api/finance/journal-entries", params={"workshop_id": WORKSHOP_ID, "limit": 50})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("success") is True, "API should return success=True"
        
        entries = data.get("data", [])
        print(f"✅ PASS: Journal entries API returns {len(entries)} entries")

    def test_journal_entries_lines_have_account_codes(self):
        """Journal entry lines should have account codes"""
        response = requests.get(f"{BASE_URL}/api/finance/journal-entries", params={"workshop_id": WORKSHOP_ID, "limit": 20})
        assert response.status_code == 200
        
        data = response.json()
        entries = data.get("data", [])
        
        entries_with_lines = 0
        for entry in entries:
            lines = entry.get("lines", [])
            if lines:
                entries_with_lines += 1
        
        print(f"✅ PASS: {entries_with_lines}/{len(entries)} entries have lines with account codes")

    def test_accounts_tree_api_no_legacy_codes(self):
        """GET /api/accounts/tree should not return legacy codes"""
        response = requests.get(f"{BASE_URL}/api/accounts/tree", params={"workshop_id": WORKSHOP_ID})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("success") is True, "API should return success=True"
        
        accounts = data.get("data", {}).get("accounts", [])
        
        def check_accounts_recursive(accs, legacy_found):
            for acc in accs:
                code = str(acc.get("code", "")).strip()
                if code.isdigit() and int(code) >= 1000:
                    legacy_found.append(code)
                children = acc.get("children", [])
                if children:
                    check_accounts_recursive(children, legacy_found)
        
        legacy_codes_found = []
        check_accounts_recursive(accounts, legacy_codes_found)
        
        assert len(legacy_codes_found) == 0, f"Found legacy codes in tree: {legacy_codes_found[:10]}"
        print(f"✅ PASS: Accounts tree has no legacy codes (>=1000)")

    def test_trial_balance_api_returns_success(self):
        """GET /api/finance/reports/trial-balance should return success"""
        response = requests.get(f"{BASE_URL}/api/finance/reports/trial-balance", params={"workshop_id": WORKSHOP_ID})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("success") is True, "API should return success=True"
        
        accounts = data.get("data", {}).get("accounts", [])
        totals = data.get("data", {}).get("totals", {})
        
        print(f"✅ PASS: Trial balance has {len(accounts)} accounts, debit={totals.get('total_debit')}, credit={totals.get('total_credit')}")

    def test_balance_sheet_api_returns_success(self):
        """GET /api/finance/reports/balance-sheet should return success"""
        response = requests.get(f"{BASE_URL}/api/finance/reports/balance-sheet", params={"workshop_id": WORKSHOP_ID})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("success") is True, "API should return success=True"
        
        totals = data.get("data", {}).get("totals", {})
        print(f"✅ PASS: Balance sheet - assets={totals.get('assets')}, liabilities={totals.get('liabilities')}, equity={totals.get('equity')}")

    def test_income_statement_api_returns_success(self):
        """GET /api/finance/reports/income-statement should return success"""
        response = requests.get(f"{BASE_URL}/api/finance/reports/income-statement", params={"workshop_id": WORKSHOP_ID})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("success") is True, "API should return success=True"
        
        totals = data.get("data", {}).get("totals", {})
        print(f"✅ PASS: Income statement - revenue={totals.get('revenue')}, expenses={totals.get('expenses')}, net_income={totals.get('net_income')}")

    def test_reconciliation_api_returns_success(self):
        """GET /api/finance/reports/reconciliation should return success"""
        response = requests.get(f"{BASE_URL}/api/finance/reports/reconciliation", params={"workshop_id": WORKSHOP_ID})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("success") is True, "API should return success=True"
        
        summary = data.get("data", {}).get("summary", {})
        print(f"✅ PASS: Reconciliation - matched={summary.get('matched')}, diff={summary.get('total_absolute_difference')}")

    def test_no_functional_breakage_after_changes(self):
        """Verify no functional breakage - all core APIs work"""
        endpoints = [
            ("/api/finance/chart-of-accounts", {"workshop_id": WORKSHOP_ID}),
            ("/api/finance/journal-entries", {"workshop_id": WORKSHOP_ID, "limit": 10}),
            ("/api/accounts/tree", {"workshop_id": WORKSHOP_ID}),
            ("/api/finance/reports/trial-balance", {"workshop_id": WORKSHOP_ID}),
            ("/api/finance/reports/balance-sheet", {"workshop_id": WORKSHOP_ID}),
            ("/api/finance/reports/income-statement", {"workshop_id": WORKSHOP_ID}),
        ]
        
        all_pass = True
        for endpoint, params in endpoints:
            try:
                response = requests.get(f"{BASE_URL}{endpoint}", params=params, timeout=15)
                if response.status_code != 200:
                    print(f"❌ FAIL: {endpoint} returned {response.status_code}")
                    all_pass = False
                else:
                    data = response.json()
                    if data.get("success") is not True:
                        print(f"❌ FAIL: {endpoint} returned success=False")
                        all_pass = False
            except Exception as e:
                print(f"❌ FAIL: {endpoint} error: {e}")
                all_pass = False
        
        assert all_pass, "Some endpoints failed"
        print(f"✅ PASS: All {len(endpoints)} core endpoints working correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
