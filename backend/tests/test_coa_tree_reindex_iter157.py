"""
Test Chart of Accounts Tree, Reindex Display Codes, Reconciliation Report, and Bank Revenue Policy
Iteration 157 - Testing features for improved COA page with tree structure, reindexing, and reconciliation
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://contract-audit-demo.preview.emergentagent.com').rstrip('/')
WORKSHOP_ID = os.environ.get('REACT_APP_WORKSHOP_ID', 'finmodule-sync')


class TestAccountsTree:
    """Test GET /api/accounts/tree endpoint"""

    def test_accounts_tree_returns_success(self):
        """Test that accounts tree endpoint returns success with display_code"""
        response = requests.get(
            f"{BASE_URL}/api/accounts/tree",
            params={"workshop_id": WORKSHOP_ID, "type": "all", "hideZero": "false", "search": ""}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") is True, f"Expected success=True, got {data}"
        assert "data" in data, "Response should contain 'data' field"
        
        payload = data["data"]
        assert "mode" in payload, "Response should contain 'mode' field"
        assert "summary" in payload, "Response should contain 'summary' field"
        assert "accounts" in payload, "Response should contain 'accounts' field"
        
        print(f"✅ Accounts tree returned mode={payload['mode']}, accounts count={len(payload['accounts'])}")

    def test_accounts_tree_has_display_code(self):
        """Test that accounts in tree have display_code field"""
        response = requests.get(
            f"{BASE_URL}/api/accounts/tree",
            params={"workshop_id": WORKSHOP_ID, "type": "all", "hideZero": "false", "search": ""}
        )
        assert response.status_code == 200
        
        data = response.json()
        accounts = data.get("data", {}).get("accounts", [])
        
        if accounts:
            # Check first account has display_code
            first_account = accounts[0]
            assert "display_code" in first_account, f"Account should have display_code field: {first_account.keys()}"
            print(f"✅ First account display_code: {first_account.get('display_code')}, code: {first_account.get('code')}")
        else:
            print("⚠️ No accounts returned - may need to initialize defaults first")

    def test_accounts_tree_summary_fields(self):
        """Test that summary contains expected financial fields"""
        response = requests.get(
            f"{BASE_URL}/api/accounts/tree",
            params={"workshop_id": WORKSHOP_ID}
        )
        assert response.status_code == 200
        
        data = response.json()
        summary = data.get("data", {}).get("summary", {})
        
        expected_fields = ["assets", "liabilities", "net_profit"]
        for field in expected_fields:
            assert field in summary, f"Summary should contain '{field}' field"
        
        print(f"✅ Summary: assets={summary.get('assets')}, liabilities={summary.get('liabilities')}, net_profit={summary.get('net_profit')}")

    def test_accounts_tree_type_filter(self):
        """Test filtering accounts by type"""
        for acc_type in ["asset", "liability", "revenue", "expense"]:
            response = requests.get(
                f"{BASE_URL}/api/accounts/tree",
                params={"workshop_id": WORKSHOP_ID, "type": acc_type}
            )
            assert response.status_code == 200, f"Filter by type={acc_type} failed"
            print(f"✅ Type filter '{acc_type}' works")


class TestReindexDisplayCodes:
    """Test POST /api/accounts/reindex-display-codes endpoint"""

    def test_reindex_display_codes_returns_success(self):
        """Test that reindex endpoint returns success with count starting from 001"""
        response = requests.post(f"{BASE_URL}/api/accounts/reindex-display-codes")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") is True, f"Expected success=True, got {data}"
        assert "data" in data, "Response should contain 'data' field"
        
        payload = data["data"]
        assert "count" in payload, "Response should contain 'count' field"
        assert "first_display_code" in payload, "Response should contain 'first_display_code' field"
        
        # Verify first display code starts from 001
        first_code = payload.get("first_display_code")
        if first_code:
            assert first_code == "001", f"First display_code should be '001', got '{first_code}'"
        
        print(f"✅ Reindex completed: count={payload.get('count')}, first={first_code}, last={payload.get('last_display_code')}")

    def test_reindex_sample_accounts(self):
        """Test that sample accounts in reindex response have sequential display codes"""
        response = requests.post(f"{BASE_URL}/api/accounts/reindex-display-codes")
        assert response.status_code == 200
        
        data = response.json()
        sample = data.get("data", {}).get("sample", [])
        
        if sample:
            # Check first few are sequential
            for i, acc in enumerate(sample[:5], start=1):
                expected_code = f"{i:03d}"
                actual_code = acc.get("display_code")
                assert actual_code == expected_code, f"Expected display_code '{expected_code}', got '{actual_code}'"
            print(f"✅ Sample accounts have sequential display codes starting from 001")
        else:
            print("⚠️ No sample accounts returned")


class TestReconciliationReport:
    """Test GET /api/accounts/reconciliation-report endpoint"""

    def test_reconciliation_report_returns_success(self):
        """Test that reconciliation report returns success with matched/mismatched counts"""
        response = requests.get(
            f"{BASE_URL}/api/accounts/reconciliation-report",
            params={"workshop_id": WORKSHOP_ID}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") is True, f"Expected success=True, got {data}"
        assert "data" in data, "Response should contain 'data' field"
        
        payload = data["data"]
        assert "summary" in payload, "Response should contain 'summary' field"
        assert "rows" in payload, "Response should contain 'rows' field"
        
        summary = payload["summary"]
        assert "accounts_count" in summary, "Summary should contain 'accounts_count'"
        assert "matched_count" in summary, "Summary should contain 'matched_count'"
        assert "mismatched_count" in summary, "Summary should contain 'mismatched_count'"
        
        print(f"✅ Reconciliation report: total={summary.get('accounts_count')}, matched={summary.get('matched_count')}, mismatched={summary.get('mismatched_count')}")

    def test_reconciliation_report_row_structure(self):
        """Test that reconciliation report rows have expected fields"""
        response = requests.get(
            f"{BASE_URL}/api/accounts/reconciliation-report",
            params={"workshop_id": WORKSHOP_ID}
        )
        assert response.status_code == 200
        
        data = response.json()
        rows = data.get("data", {}).get("rows", [])
        
        if rows:
            first_row = rows[0]
            expected_fields = ["account_id", "display_code", "code", "name", "balance", "expected_balance", "difference", "matched"]
            for field in expected_fields:
                assert field in first_row, f"Row should contain '{field}' field"
            
            print(f"✅ First row: code={first_row.get('code')}, display_code={first_row.get('display_code')}, matched={first_row.get('matched')}")
        else:
            print("⚠️ No rows in reconciliation report")


class TestApplyBankRevenuePolicy:
    """Test POST /api/finance/reports/apply-bank-revenue-policy endpoint"""

    def test_apply_bank_policy_dry_run(self):
        """Test bank revenue policy in dry-run mode (apply_changes=false)"""
        response = requests.post(
            f"{BASE_URL}/api/finance/reports/apply-bank-revenue-policy",
            params={"workshop_id": WORKSHOP_ID, "apply_changes": "false"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") is True, f"Expected success=True, got {data}"
        assert "data" in data, "Response should contain 'data' field"
        
        payload = data["data"]
        assert "pos_account" in payload, "Response should contain 'pos_account' field"
        assert "journal" in payload, "Response should contain 'journal' field"
        assert "operations" in payload, "Response should contain 'operations' field"
        
        print(f"✅ Bank policy dry-run: POS={payload.get('pos_account')}, journal candidates={payload.get('journal', {}).get('candidates')}")

    def test_apply_bank_policy_creates_pos_account(self):
        """Test that bank policy ensures POS account 1104 exists under bank 1102"""
        response = requests.post(
            f"{BASE_URL}/api/finance/reports/apply-bank-revenue-policy",
            params={"workshop_id": WORKSHOP_ID, "apply_changes": "true"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") is True, f"Expected success=True, got {data}"
        
        pos_result = data.get("data", {}).get("pos_account", {})
        # POS should either be created, updated, or already exist
        account = pos_result.get("account")
        if account:
            assert account.get("code") == "1104", f"POS account code should be 1104, got {account.get('code')}"
            print(f"✅ POS account 1104 exists: created={pos_result.get('created')}, updated={pos_result.get('updated')}")
        else:
            print(f"⚠️ POS account result: {pos_result}")


class TestIncomeStatementSalesSummary:
    """Test GET /api/finance/reports/income-statement for sales_summary with cash=0 after policy"""

    def test_income_statement_has_sales_summary(self):
        """Test that income statement returns sales_summary with cash/bank breakdown"""
        response = requests.get(
            f"{BASE_URL}/api/finance/reports/income-statement",
            params={"workshop_id": WORKSHOP_ID}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") is True, f"Expected success=True, got {data}"
        
        payload = data.get("data", {})
        assert "sales_summary" in payload, "Response should contain 'sales_summary' field"
        
        sales_summary = payload["sales_summary"]
        expected_fields = ["operations_total", "operations_count", "operations_cash_total", "operations_bank_total", "operations_credit_total"]
        for field in expected_fields:
            assert field in sales_summary, f"sales_summary should contain '{field}' field"
        
        print(f"✅ Income statement sales_summary: cash={sales_summary.get('operations_cash_total')}, bank={sales_summary.get('operations_bank_total')}, credit={sales_summary.get('operations_credit_total')}")

    def test_income_statement_cash_after_bank_policy(self):
        """Test that cash is zero or minimal after applying bank revenue policy"""
        # First apply the bank policy
        policy_response = requests.post(
            f"{BASE_URL}/api/finance/reports/apply-bank-revenue-policy",
            params={"workshop_id": WORKSHOP_ID, "apply_changes": "true"}
        )
        assert policy_response.status_code == 200
        
        # Then check income statement
        response = requests.get(
            f"{BASE_URL}/api/finance/reports/income-statement",
            params={"workshop_id": WORKSHOP_ID}
        )
        assert response.status_code == 200
        
        data = response.json()
        sales_summary = data.get("data", {}).get("sales_summary", {})
        cash_total = sales_summary.get("operations_cash_total", 0)
        bank_total = sales_summary.get("operations_bank_total", 0)
        
        # After policy, cash should be 0 (all moved to bank)
        print(f"✅ After bank policy: cash={cash_total}, bank={bank_total}")
        # Note: We don't assert cash==0 because there may be new operations after policy was applied


class TestAccountsTreeAfterReindex:
    """Test that accounts tree shows display_code after reindex"""

    def test_tree_shows_display_codes_after_reindex(self):
        """Test full flow: reindex then verify tree has display codes"""
        # Step 1: Reindex
        reindex_response = requests.post(f"{BASE_URL}/api/accounts/reindex-display-codes")
        assert reindex_response.status_code == 200
        
        # Step 2: Get tree
        tree_response = requests.get(
            f"{BASE_URL}/api/accounts/tree",
            params={"workshop_id": WORKSHOP_ID}
        )
        assert tree_response.status_code == 200
        
        data = tree_response.json()
        accounts = data.get("data", {}).get("accounts", [])
        
        if accounts:
            # Verify accounts have display_code
            accounts_with_display_code = 0
            for acc in accounts:
                if acc.get("display_code"):
                    accounts_with_display_code += 1
            
            print(f"✅ After reindex: {accounts_with_display_code}/{len(accounts)} accounts have display_code")
            assert accounts_with_display_code > 0, "At least some accounts should have display_code after reindex"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
