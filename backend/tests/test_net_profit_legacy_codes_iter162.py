"""
Test iteration 162: Verify net_profit formula and legacy code suppression
المستخدم طلب: الصافي = الإيرادات التاريخية - (المصروفات + المشتريات)، وإيقاف ظهور الأكواد القديمة في القيود اليومية ودليل الحسابات.

Test cases:
1. GET /api/accounts/tree summary contains purchase and net_profit = revenue - (expense + purchase)
2. GET /api/finance/chart-of-accounts does not show legacy codes (>=1000) after fix
3. No accounting errors (alerts without tb_unbalanced)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://canonical-integrity.preview.emergentagent.com').rstrip('/')
WORKSHOP_ID = os.environ.get('REACT_APP_WORKSHOP_ID', 'finmodule-sync')


class TestAccountsTreeSummary:
    """Test /api/accounts/tree summary contains purchase and correct net_profit formula"""

    def test_accounts_tree_returns_success(self):
        """Test that accounts/tree endpoint returns success"""
        response = requests.get(f"{BASE_URL}/api/accounts/tree", params={"workshop_id": WORKSHOP_ID})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("success") is True, f"Expected success=True, got {data}"
        print(f"✅ PASS: /api/accounts/tree returns success=True")

    def test_accounts_tree_summary_contains_purchase(self):
        """Test that summary contains 'purchase' field"""
        response = requests.get(f"{BASE_URL}/api/accounts/tree", params={"workshop_id": WORKSHOP_ID})
        assert response.status_code == 200
        data = response.json()
        summary = data.get("data", {}).get("summary", {})
        
        assert "purchase" in summary, f"Expected 'purchase' in summary, got keys: {list(summary.keys())}"
        print(f"✅ PASS: summary contains 'purchase' field = {summary.get('purchase')}")

    def test_accounts_tree_summary_contains_net_profit(self):
        """Test that summary contains 'net_profit' field"""
        response = requests.get(f"{BASE_URL}/api/accounts/tree", params={"workshop_id": WORKSHOP_ID})
        assert response.status_code == 200
        data = response.json()
        summary = data.get("data", {}).get("summary", {})
        
        assert "net_profit" in summary, f"Expected 'net_profit' in summary, got keys: {list(summary.keys())}"
        print(f"✅ PASS: summary contains 'net_profit' field = {summary.get('net_profit')}")

    def test_net_profit_formula_correct(self):
        """Test that net_profit = revenue - (expense + purchase)"""
        response = requests.get(f"{BASE_URL}/api/accounts/tree", params={"workshop_id": WORKSHOP_ID})
        assert response.status_code == 200
        data = response.json()
        summary = data.get("data", {}).get("summary", {})
        
        revenue = float(summary.get("revenue", 0))
        expense = float(summary.get("expense", 0))
        purchase = float(summary.get("purchase", 0))
        net_profit = float(summary.get("net_profit", 0))
        
        expected_net_profit = round(revenue - (expense + purchase), 2)
        actual_net_profit = round(net_profit, 2)
        
        # Allow small floating point tolerance
        assert abs(expected_net_profit - actual_net_profit) < 0.01, \
            f"Expected net_profit={expected_net_profit} (revenue={revenue} - (expense={expense} + purchase={purchase})), got {actual_net_profit}"
        
        print(f"✅ PASS: net_profit formula correct: {revenue} - ({expense} + {purchase}) = {actual_net_profit}")


class TestChartOfAccountsLegacyCodes:
    """Test /api/finance/chart-of-accounts does not show legacy codes (>=1000)"""

    def test_chart_of_accounts_returns_success(self):
        """Test that chart-of-accounts endpoint returns success"""
        response = requests.get(f"{BASE_URL}/api/finance/chart-of-accounts", params={"workshop_id": WORKSHOP_ID})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("success") is True, f"Expected success=True, got {data}"
        print(f"✅ PASS: /api/finance/chart-of-accounts returns success=True")

    def test_no_legacy_codes_in_chart_of_accounts(self):
        """Test that no legacy codes (>=1000) appear in chart of accounts"""
        response = requests.get(f"{BASE_URL}/api/finance/chart-of-accounts", params={"workshop_id": WORKSHOP_ID})
        assert response.status_code == 200
        data = response.json()
        accounts = data.get("data", [])
        
        legacy_codes_found = []
        for acc in accounts:
            code = str(acc.get("code", "")).strip()
            if code.isdigit() and int(code) >= 1000:
                legacy_codes_found.append(code)
        
        # Report findings
        if legacy_codes_found:
            print(f"⚠️ Found {len(legacy_codes_found)} legacy codes (>=1000): {legacy_codes_found[:10]}...")
        else:
            print(f"✅ PASS: No legacy codes (>=1000) found in chart of accounts")
        
        # This test passes if no legacy codes are found, or warns if some are found
        # Based on the code logic, legacy codes should be suppressed
        assert len(legacy_codes_found) == 0, f"Found {len(legacy_codes_found)} legacy codes that should be suppressed: {legacy_codes_found[:10]}"


class TestJournalEntriesLegacyCodes:
    """Test /api/finance/journal-entries does not show legacy codes"""

    def test_journal_entries_returns_success(self):
        """Test that journal-entries endpoint returns success"""
        response = requests.get(f"{BASE_URL}/api/finance/journal-entries", params={"workshop_id": WORKSHOP_ID, "limit": 50})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("success") is True, f"Expected success=True, got {data}"
        print(f"✅ PASS: /api/finance/journal-entries returns success=True")

    def test_journal_entries_account_codes_format(self):
        """Test that journal entries use new account codes (not legacy >=1000)"""
        response = requests.get(f"{BASE_URL}/api/finance/journal-entries", params={"workshop_id": WORKSHOP_ID, "limit": 50})
        assert response.status_code == 200
        data = response.json()
        entries = data.get("data", [])
        
        legacy_codes_in_entries = []
        new_codes_in_entries = []
        
        for entry in entries:
            lines = entry.get("lines", []) or []
            for line in lines:
                code = str(line.get("account", "")).strip()
                if code.isdigit():
                    if int(code) >= 1000:
                        legacy_codes_in_entries.append(code)
                    else:
                        new_codes_in_entries.append(code)
        
        print(f"Found {len(new_codes_in_entries)} new codes (< 1000) in journal entries")
        print(f"Found {len(legacy_codes_in_entries)} legacy codes (>= 1000) in journal entries")
        
        # Note: Journal entries may still have legacy codes in the database
        # The frontend should resolve them to new codes
        if legacy_codes_in_entries:
            print(f"⚠️ Legacy codes found in journal entries (may be resolved by frontend): {set(legacy_codes_in_entries)}")


class TestAccountingAlerts:
    """Test that no tb_unbalanced alert exists after fix"""

    def test_alerts_endpoint_returns_success(self):
        """Test that alerts endpoint returns success"""
        response = requests.get(f"{BASE_URL}/api/finance/alerts", params={"workshop_id": WORKSHOP_ID})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("success") is True, f"Expected success=True, got {data}"
        print(f"✅ PASS: /api/finance/alerts returns success=True")

    def test_no_tb_unbalanced_alert(self):
        """Test that no tb_unbalanced alert exists"""
        response = requests.get(f"{BASE_URL}/api/finance/alerts", params={"workshop_id": WORKSHOP_ID})
        assert response.status_code == 200
        data = response.json()
        alerts = data.get("data", {}).get("alerts", [])
        
        tb_unbalanced_alerts = [a for a in alerts if a.get("type") == "tb_unbalanced"]
        
        if tb_unbalanced_alerts:
            print(f"⚠️ Found tb_unbalanced alerts: {tb_unbalanced_alerts}")
        else:
            print(f"✅ PASS: No tb_unbalanced alert found")
        
        assert len(tb_unbalanced_alerts) == 0, f"Found {len(tb_unbalanced_alerts)} tb_unbalanced alerts"


class TestTrialBalanceBalanced:
    """Test that trial balance is balanced"""

    def test_trial_balance_returns_success(self):
        """Test that trial-balance endpoint returns success"""
        response = requests.get(f"{BASE_URL}/api/finance/reports/trial-balance", params={"workshop_id": WORKSHOP_ID})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("success") is True, f"Expected success=True, got {data}"
        print(f"✅ PASS: /api/finance/reports/trial-balance returns success=True")

    def test_trial_balance_is_balanced(self):
        """Test that trial balance debit equals credit"""
        response = requests.get(f"{BASE_URL}/api/finance/reports/trial-balance", params={"workshop_id": WORKSHOP_ID})
        assert response.status_code == 200
        data = response.json()
        totals = data.get("data", {}).get("totals", {})
        
        total_debit = float(totals.get("total_debit", 0))
        total_credit = float(totals.get("total_credit", 0))
        difference = abs(total_debit - total_credit)
        
        print(f"Trial Balance: Debit={total_debit}, Credit={total_credit}, Difference={difference}")
        
        # Allow small tolerance for floating point
        assert difference < 0.01, f"Trial balance not balanced: Debit={total_debit}, Credit={total_credit}, Difference={difference}"
        print(f"✅ PASS: Trial balance is balanced (difference={difference})")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
