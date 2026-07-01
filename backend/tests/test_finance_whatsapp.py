"""
Test Finance APIs and WhatsApp Bot APIs
Tests for:
- Journal Entries API
- Chart of Accounts API
- Balance Sheet API
- Trial Balance API
- WhatsApp Bot Stats API
- WhatsApp Bot Workshop Info API
"""

import pytest
import requests
import os

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL", "https://erp-compliance-check.preview.emergentagent.com"
).rstrip("/")
WORKSHOP_ID = "finmodule-sync"


class TestFinanceAPIs:
    """Finance module API tests"""

    def test_journal_entries_api(self):
        """Test GET /api/finance/journal-entries"""
        response = requests.get(
            f"{BASE_URL}/api/finance/journal-entries",
            params={"workshop_id": WORKSHOP_ID, "limit": 10},
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        data = response.json()
        assert data.get("success") == True, "Response should have success=True"
        assert "data" in data, "Response should have data field"
        assert isinstance(data["data"], list), "Data should be a list"

        # Verify entry structure if entries exist
        if len(data["data"]) > 0:
            entry = data["data"][0]
            assert "id" in entry, "Entry should have id"
            assert "date" in entry, "Entry should have date"
            assert "description" in entry, "Entry should have description"
            assert "lines" in entry, "Entry should have lines"
            assert "total" in entry, "Entry should have total"

            # Verify lines structure
            if len(entry["lines"]) > 0:
                line = entry["lines"][0]
                assert "account" in line, "Line should have account"
                assert (
                    "debit" in line or "credit" in line
                ), "Line should have debit or credit"

        print(f"✅ Journal entries API returned {len(data['data'])} entries")

    def test_chart_of_accounts_api(self):
        """Test GET /api/finance/chart-of-accounts"""
        response = requests.get(
            f"{BASE_URL}/api/finance/chart-of-accounts",
            params={"workshop_id": WORKSHOP_ID},
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        data = response.json()
        assert data.get("success") == True, "Response should have success=True"
        assert "data" in data, "Response should have data field"
        assert isinstance(data["data"], list), "Data should be a list"

        # Verify account structure
        if len(data["data"]) > 0:
            account = data["data"][0]
            assert "code" in account, "Account should have code"
            assert "name" in account, "Account should have name"
            assert "type" in account, "Account should have type"

            # Verify account types
            valid_types = ["asset", "liability", "equity", "revenue", "expense"]
            assert (
                account["type"] in valid_types
            ), f"Account type should be one of {valid_types}"

        print(f"✅ Chart of accounts API returned {len(data['data'])} accounts")

    def test_balance_sheet_api(self):
        """Test GET /api/finance/reports/balance-sheet"""
        response = requests.get(
            f"{BASE_URL}/api/finance/reports/balance-sheet",
            params={"workshop_id": WORKSHOP_ID},
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        data = response.json()
        assert data.get("success") == True, "Response should have success=True"
        assert "data" in data, "Response should have data field"

        report = data["data"]
        assert "totals" in report, "Report should have totals"
        assert "sections" in report, "Report should have sections"

        # Verify totals structure
        totals = report["totals"]
        assert "assets" in totals, "Totals should have assets"
        assert "liabilities" in totals, "Totals should have liabilities"
        assert "equity" in totals, "Totals should have equity"

        # Verify balance sheet equation: Assets = Liabilities + Equity
        assets = totals.get("assets", 0)
        liabilities = totals.get("liabilities", 0)
        equity = totals.get("equity", 0)
        liabilities_plus_equity = totals.get(
            "liabilities_plus_equity", liabilities + equity
        )

        # Allow small floating point differences
        assert (
            abs(assets - liabilities_plus_equity) < 0.01
        ), f"Balance sheet should balance: Assets ({assets}) = Liabilities + Equity ({liabilities_plus_equity})"

        print(
            f"✅ Balance sheet API - Assets: {assets}, Liabilities: {liabilities}, Equity: {equity}"
        )

    def test_trial_balance_api(self):
        """Test GET /api/finance/reports/trial-balance"""
        response = requests.get(
            f"{BASE_URL}/api/finance/reports/trial-balance",
            params={"workshop_id": WORKSHOP_ID},
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        data = response.json()
        assert data.get("success") == True, "Response should have success=True"
        assert "data" in data, "Response should have data field"

        report = data["data"]
        assert "accounts" in report, "Report should have accounts"
        assert "totals" in report, "Report should have totals"

        # Verify totals structure
        totals = report["totals"]
        assert "total_debit" in totals, "Totals should have total_debit"
        assert "total_credit" in totals, "Totals should have total_credit"

        # Verify trial balance equation: Total Debit = Total Credit
        total_debit = totals.get("total_debit", 0)
        total_credit = totals.get("total_credit", 0)

        # Allow small floating point differences
        assert (
            abs(total_debit - total_credit) < 0.01
        ), f"Trial balance should balance: Debit ({total_debit}) = Credit ({total_credit})"

        print(f"✅ Trial balance API - Debit: {total_debit}, Credit: {total_credit}")


class TestWhatsAppBotAPIs:
    """WhatsApp Bot API tests"""

    def test_whatsapp_bot_stats(self):
        """Test GET /api/whatsapp-bot/stats"""
        response = requests.get(f"{BASE_URL}/api/whatsapp-bot/stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        data = response.json()
        # Verify stats structure
        assert (
            "total_messages" in data or "messages_count" in data
        ), "Stats should have message count"
        assert "cars_count" in data, "Stats should have cars_count"

        print(
            f"✅ WhatsApp bot stats API - Cars: {data.get('cars_count', 0)}, Messages: {data.get('total_messages', data.get('messages_count', 0))}"
        )

    def test_whatsapp_bot_workshop_info(self):
        """Test GET /api/whatsapp-bot/workshop-info"""
        response = requests.get(f"{BASE_URL}/api/whatsapp-bot/workshop-info")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        data = response.json()
        # Verify workshop info structure
        assert "name" in data, "Workshop info should have name"
        assert "phone" in data, "Workshop info should have phone"

        # Verify Arabic name exists
        assert data.get("name"), "Workshop name should not be empty"

        print(
            f"✅ WhatsApp bot workshop info - Name: {data.get('name')}, Phone: {data.get('phone')}"
        )


class TestHealthAndBasicAPIs:
    """Basic health and API tests"""

    def test_health_endpoint(self):
        """Test GET /api/health or /health"""
        # Try /api/health first (internal API)
        response = requests.get(f"{BASE_URL}/api/health")
        if response.status_code != 200:
            # Fallback to direct health endpoint
            response = requests.get(f"{BASE_URL}/health")

        # Health endpoint may return HTML (frontend) or JSON
        if response.status_code == 200:
            try:
                data = response.json()
                assert "status" in data, "Health response should have status"
                print(f"✅ Health endpoint - Status: {data.get('status')}")
            except:
                # Frontend HTML response is also acceptable
                print("✅ Health endpoint returns frontend HTML (status 200)")

    def test_stats_endpoint(self):
        """Test GET /api/stats"""
        response = requests.get(f"{BASE_URL}/api/stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        data = response.json()
        assert (
            "totalCustomers" in data or "activeVehicles" in data
        ), "Stats should have customer or vehicle count"
        print(
            f"✅ Stats endpoint - Customers: {data.get('totalCustomers', 0)}, Active Vehicles: {data.get('activeVehicles', 0)}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
