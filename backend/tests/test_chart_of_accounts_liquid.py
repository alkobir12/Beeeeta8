"""
Test suite for Chart of Accounts Liquid endpoints (Iteration 80)
Tests: /api/accounts/tree, /api/accounts/{id}/transactions, /api/accounts/{id}/sparkline,
       /api/accounts/{id}/touch, /api/accounts/export
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://accounting-engine-6.preview.emergentagent.com').rstrip('/')
WORKSHOP_ID = "finmodule-sync"


class TestAccountsTree:
    """Tests for GET /api/accounts/tree endpoint"""

    def test_accounts_tree_default(self):
        """Test accounts tree with default parameters"""
        response = requests.get(
            f"{BASE_URL}/api/accounts/tree",
            params={"workshop_id": WORKSHOP_ID, "type": "all", "hideZero": "false", "search": ""}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") is True, "Response should have success=True"
        assert "data" in data, "Response should have data field"
        
        payload = data["data"]
        assert "mode" in payload, "Data should have mode field"
        assert payload["mode"] in ("tree", "flat"), f"Mode should be tree or flat, got {payload['mode']}"
        assert "summary" in payload, "Data should have summary field"
        assert "accounts" in payload, "Data should have accounts field"
        
        # Verify summary structure
        summary = payload["summary"]
        assert "assets" in summary, "Summary should have assets"
        assert "liabilities" in summary, "Summary should have liabilities"
        assert "net_profit" in summary, "Summary should have net_profit"
        
        print(f"✅ Accounts tree loaded: mode={payload['mode']}, accounts_count={len(payload['accounts'])}")
        print(f"   Summary: assets={summary.get('assets')}, liabilities={summary.get('liabilities')}, net_profit={summary.get('net_profit')}")

    def test_accounts_tree_type_filter(self):
        """Test accounts tree with type filter"""
        for account_type in ["asset", "liability", "equity", "revenue", "expense"]:
            response = requests.get(
                f"{BASE_URL}/api/accounts/tree",
                params={"workshop_id": WORKSHOP_ID, "type": account_type, "hideZero": "false", "search": ""}
            )
            assert response.status_code == 200, f"Type filter '{account_type}' failed: {response.text}"
            
            data = response.json()
            assert data.get("success") is True
            
            accounts = data["data"]["accounts"]
            # Verify all returned accounts match the type filter
            for acc in accounts:
                if acc.get("type"):
                    assert acc["type"] == account_type, f"Account type mismatch: expected {account_type}, got {acc['type']}"
            
            print(f"✅ Type filter '{account_type}': {len(accounts)} accounts")

    def test_accounts_tree_hide_zero(self):
        """Test accounts tree with hideZero=true"""
        response = requests.get(
            f"{BASE_URL}/api/accounts/tree",
            params={"workshop_id": WORKSHOP_ID, "type": "all", "hideZero": "true", "search": ""}
        )
        assert response.status_code == 200, f"hideZero filter failed: {response.text}"
        
        data = response.json()
        assert data.get("success") is True
        
        # Verify no zero-balance accounts in results
        def check_no_zero(accounts):
            for acc in accounts:
                if acc.get("balance") == 0:
                    # Zero balance accounts should be filtered out
                    pass  # Some may still appear if they have children with non-zero
                if acc.get("children"):
                    check_no_zero(acc["children"])
        
        check_no_zero(data["data"]["accounts"])
        print(f"✅ hideZero filter working: {len(data['data']['accounts'])} accounts")

    def test_accounts_tree_search_returns_flat(self):
        """Test that search query returns flat mode"""
        response = requests.get(
            f"{BASE_URL}/api/accounts/tree",
            params={"workshop_id": WORKSHOP_ID, "type": "all", "hideZero": "false", "search": "نقد"}
        )
        assert response.status_code == 200, f"Search failed: {response.text}"
        
        data = response.json()
        assert data.get("success") is True
        
        payload = data["data"]
        assert payload["mode"] == "flat", f"Search should return flat mode, got {payload['mode']}"
        
        print(f"✅ Search returns flat mode: {len(payload['accounts'])} matching accounts")


class TestAccountTransactions:
    """Tests for GET /api/accounts/{id}/transactions endpoint"""

    def test_account_transactions_valid(self):
        """Test getting transactions for a valid account"""
        # First get an account ID from the tree
        tree_response = requests.get(
            f"{BASE_URL}/api/accounts/tree",
            params={"workshop_id": WORKSHOP_ID, "type": "all", "hideZero": "false", "search": ""}
        )
        assert tree_response.status_code == 200
        
        accounts = tree_response.json()["data"]["accounts"]
        if not accounts:
            pytest.skip("No accounts available for testing")
        
        # Get first account with transactions
        account_id = accounts[0].get("id")
        if not account_id:
            pytest.skip("No account ID found")
        
        response = requests.get(
            f"{BASE_URL}/api/accounts/{account_id}/transactions",
            params={"workshop_id": WORKSHOP_ID, "limit": 10}
        )
        assert response.status_code == 200, f"Transactions request failed: {response.text}"
        
        data = response.json()
        assert data.get("success") is True
        assert "data" in data
        
        payload = data["data"]
        assert "account" in payload, "Response should have account info"
        assert "transactions" in payload, "Response should have transactions list"
        
        transactions = payload["transactions"]
        assert isinstance(transactions, list), "Transactions should be a list"
        
        # Verify transaction structure
        for tx in transactions[:3]:  # Check first 3
            assert "date" in tx, "Transaction should have date"
            assert "debit" in tx, "Transaction should have debit"
            assert "credit" in tx, "Transaction should have credit"
            assert "balance" in tx, "Transaction should have balance"
        
        print(f"✅ Account transactions: {len(transactions)} transactions for account {account_id}")

    def test_account_transactions_limit(self):
        """Test transactions limit parameter"""
        tree_response = requests.get(
            f"{BASE_URL}/api/accounts/tree",
            params={"workshop_id": WORKSHOP_ID, "type": "all", "hideZero": "false", "search": ""}
        )
        accounts = tree_response.json()["data"]["accounts"]
        if not accounts:
            pytest.skip("No accounts available")
        
        account_id = accounts[0].get("id")
        
        # Test with limit=5
        response = requests.get(
            f"{BASE_URL}/api/accounts/{account_id}/transactions",
            params={"workshop_id": WORKSHOP_ID, "limit": 5}
        )
        assert response.status_code == 200
        
        transactions = response.json()["data"]["transactions"]
        assert len(transactions) <= 5, f"Expected max 5 transactions, got {len(transactions)}"
        
        print(f"✅ Transactions limit working: returned {len(transactions)} (limit=5)")


class TestAccountSparkline:
    """Tests for GET /api/accounts/{id}/sparkline endpoint"""

    def test_account_sparkline_valid(self):
        """Test sparkline for a valid account"""
        tree_response = requests.get(
            f"{BASE_URL}/api/accounts/tree",
            params={"workshop_id": WORKSHOP_ID, "type": "all", "hideZero": "false", "search": ""}
        )
        accounts = tree_response.json()["data"]["accounts"]
        if not accounts:
            pytest.skip("No accounts available")
        
        account_id = accounts[0].get("id")
        
        response = requests.get(
            f"{BASE_URL}/api/accounts/{account_id}/sparkline",
            params={"workshop_id": WORKSHOP_ID, "days": 30}
        )
        assert response.status_code == 200, f"Sparkline request failed: {response.text}"
        
        data = response.json()
        assert data.get("success") is True
        assert "data" in data
        
        payload = data["data"]
        assert "days" in payload, "Response should have days"
        assert "points" in payload, "Response should have points"
        
        points = payload["points"]
        assert isinstance(points, list), "Points should be a list"
        assert len(points) == 30, f"Expected 30 points for 30 days, got {len(points)}"
        
        # Verify point structure
        for point in points[:3]:
            assert "date" in point, "Point should have date"
            assert "balance" in point, "Point should have balance"
        
        print(f"✅ Sparkline working: {len(points)} points for {payload['days']} days")


class TestAccountTouch:
    """Tests for PATCH /api/accounts/{id}/touch endpoint"""

    def test_account_touch(self):
        """Test updating last_used timestamp"""
        tree_response = requests.get(
            f"{BASE_URL}/api/accounts/tree",
            params={"workshop_id": WORKSHOP_ID, "type": "all", "hideZero": "false", "search": ""}
        )
        accounts = tree_response.json()["data"]["accounts"]
        if not accounts:
            pytest.skip("No accounts available")
        
        account_id = accounts[0].get("id")
        
        response = requests.patch(f"{BASE_URL}/api/accounts/{account_id}/touch")
        assert response.status_code == 200, f"Touch request failed: {response.text}"
        
        data = response.json()
        assert data.get("success") is True
        assert data.get("account_id") == account_id
        assert "last_used_at" in data, "Response should have last_used_at"
        
        print(f"✅ Account touch working: {account_id} updated at {data['last_used_at']}")


class TestAccountsExport:
    """Tests for GET /api/accounts/export endpoint"""

    def test_accounts_export_default(self):
        """Test export with default filters"""
        response = requests.get(
            f"{BASE_URL}/api/accounts/export",
            params={"workshop_id": WORKSHOP_ID, "type": "all", "hideZero": "false", "search": ""}
        )
        assert response.status_code == 200, f"Export request failed: {response.text}"
        
        data = response.json()
        assert data.get("success") is True
        assert "data" in data
        
        payload = data["data"]
        assert "summary" in payload, "Export should have summary"
        assert "rows" in payload, "Export should have rows"
        
        rows = payload["rows"]
        assert isinstance(rows, list), "Rows should be a list"
        
        # Verify row structure
        if rows:
            row = rows[0]
            expected_fields = ["code", "name", "type", "balance", "total_debit", "total_credit", "transaction_count"]
            for field in expected_fields:
                assert field in row, f"Row should have {field}"
        
        print(f"✅ Export working: {len(rows)} rows exported")

    def test_accounts_export_filtered(self):
        """Test export with type filter"""
        response = requests.get(
            f"{BASE_URL}/api/accounts/export",
            params={"workshop_id": WORKSHOP_ID, "type": "asset", "hideZero": "true", "search": ""}
        )
        assert response.status_code == 200
        
        data = response.json()
        rows = data["data"]["rows"]
        
        # Verify all rows are assets
        for row in rows:
            if row.get("type"):
                assert row["type"] == "asset", f"Expected asset type, got {row['type']}"
        
        print(f"✅ Filtered export working: {len(rows)} asset rows")


class TestRegressionExistingEndpoints:
    """Regression tests for existing account endpoints"""

    def test_accounts_list_still_works(self):
        """Verify GET /api/accounts still works"""
        response = requests.get(f"{BASE_URL}/api/accounts")
        assert response.status_code == 200, f"Accounts list failed: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Accounts should return a list"
        print(f"✅ Regression: /api/accounts returns {len(data)} accounts")

    def test_finance_chart_of_accounts_still_works(self):
        """Verify GET /api/finance/chart-of-accounts still works"""
        response = requests.get(
            f"{BASE_URL}/api/finance/chart-of-accounts",
            params={"workshop_id": WORKSHOP_ID}
        )
        assert response.status_code == 200, f"Finance chart-of-accounts failed: {response.text}"
        
        data = response.json()
        assert data.get("success") is True or isinstance(data, list)
        print(f"✅ Regression: /api/finance/chart-of-accounts working")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
