"""Iter-309 regression: live/archive scope, finance SSOT totals, and write-path guards."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest
import requests


# Module: auth + read-only finance/vehicle API contract checks against preview URL
BASE_DIR = Path(__file__).resolve().parents[2]
FRONTEND_ENV_PATH = BASE_DIR / "frontend" / ".env"


def _read_frontend_env_base_url() -> str:
    if not FRONTEND_ENV_PATH.exists():
        raise RuntimeError(f"Missing frontend env file: {FRONTEND_ENV_PATH}")
    raw = FRONTEND_ENV_PATH.read_text(encoding="utf-8")
    for line in raw.splitlines():
        if line.strip().startswith("REACT_APP_BACKEND_URL="):
            return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not found in frontend/.env")


BASE_URL = _read_frontend_env_base_url()
WORKSHOP_ID = "finmodule-sync"
MANAGER_USERNAME = "مدير"
MANAGER_PIN = "123123"


@pytest.fixture(scope="session")
def api_client() -> requests.Session:
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="session")
def auth_headers(api_client: requests.Session) -> dict:
    response = api_client.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": MANAGER_USERNAME, "pin": MANAGER_PIN},
        timeout=30,
    )
    assert response.status_code == 200, f"Manager login failed: {response.status_code} {response.text[:300]}"
    payload = response.json()
    token = payload.get("access_token") or payload.get("token")
    assert isinstance(token, str) and token.strip(), "Login returned no access token"

    set_cookie = response.headers.get("set-cookie", "")
    assert set_cookie, "Login did not return Set-Cookie header"
    assert "HttpOnly" in set_cookie or "httponly" in set_cookie.lower(), "Login cookie is not HttpOnly"

    return {"Authorization": f"Bearer {token}"}


def _api_get(api_client: requests.Session, path: str, *, headers: dict | None = None, params: dict | None = None):
    response = api_client.get(
        f"{BASE_URL}{path}",
        headers=headers,
        params=params,
        timeout=40,
    )
    assert response.status_code == 200, f"GET {path} failed: {response.status_code} {response.text[:400]}"
    return response.json()


def _unwrap_data(payload):
    if isinstance(payload, dict) and "data" in payload and isinstance(payload["data"], (dict, list)):
        return payload["data"]
    return payload


def _to_rows(payload):
    data = _unwrap_data(payload)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("rows", "items", "operations", "entries", "customers", "data"):
            value = data.get(key)
            if isinstance(value, list):
                return value
    return []


def _to_totals(payload):
    data = _unwrap_data(payload)
    if isinstance(data, dict):
        return data.get("totals", data)
    return {}


def test_reconciliation_audit_contract_stays_read_only_and_15_live_176_archive(api_client: requests.Session, auth_headers: dict):
    payload = _api_get(
        api_client,
        "/api/finance/reconciliation-audit",
        headers=auth_headers,
        params={"workshop_id": WORKSHOP_ID},
    )
    assert payload.get("success") is True

    resolved = payload.get("resolved_exclusive_scopes", {}).get("vehicle_scope_counts", {})
    assert resolved.get("live") == 15
    assert resolved.get("archive") == 176

    mutation_guard = payload.get("mutation_guard", {})
    assert mutation_guard.get("unchanged") is True


def test_vehicles_endpoint_count_and_split_match_expected_without_mutation(api_client: requests.Session, auth_headers: dict):
    rows = _to_rows(_api_get(api_client, "/api/vehicles", headers=auth_headers))
    assert len(rows) == 191

    delivered = [r for r in rows if str(r.get("status") or "").strip().lower() == "delivered"]
    live = [r for r in rows if str(r.get("status") or "").strip().lower() != "delivered"]
    assert len(live) == 15
    assert len(delivered) == 176

    by_id = {str(r.get("id")): r for r in rows}
    assert "235cb00f-facb-46aa-a4eb-8db039ec21ee" in by_id
    assert "9004d4bd-ed82-4e0d-afa4-fd62e6e3d8fa" in by_id


def test_operations_endpoint_filters_archive_and_keeps_live_plus_standalone(api_client: requests.Session, auth_headers: dict):
    rows = _to_rows(_api_get(api_client, "/api/operations", headers=auth_headers))
    assert len(rows) == 15

    with_vehicle = [r for r in rows if str(r.get("vehicle_id") or r.get("vehicleId") or "").strip()]
    standalone = [r for r in rows if not str(r.get("vehicle_id") or r.get("vehicleId") or "").strip()]
    assert len(with_vehicle) == 14
    assert len(standalone) == 1

    total = round(sum(float(r.get("total") or 0) for r in rows), 2)
    assert total == pytest.approx(16080.0, abs=2.0)


def test_income_statement_uses_live_scope_and_payment_method_split(api_client: requests.Session, auth_headers: dict):
    payload = _api_get(
        api_client,
        "/api/finance/reports/income-statement",
        headers=auth_headers,
        params={"workshop_id": WORKSHOP_ID},
    )
    totals = _to_totals(payload)
    assert float(totals.get("revenue") or 0) == pytest.approx(15730.0, abs=0.01)
    assert float(totals.get("expenses") or 0) == pytest.approx(1400.0, abs=0.01)
    assert float(totals.get("net_income") or 0) == pytest.approx(14330.0, abs=0.01)

    data = _unwrap_data(payload)
    sales_summary = data.get("sales_summary", {}) if isinstance(data, dict) else {}
    assert float(sales_summary.get("operations_cash_total") or 0) == pytest.approx(4727.0, abs=0.01)
    assert float(sales_summary.get("operations_bank_transfer_total") or 0) == pytest.approx(6853.0, abs=0.01)
    assert float(sales_summary.get("operations_pos_total") or 0) == pytest.approx(0.0, abs=0.01)
    assert float(sales_summary.get("operations_credit_total") or 0) == pytest.approx(4150.0, abs=0.01)


def test_ar_customers_and_ledger_match_ssot_with_missing_500_present(api_client: requests.Session, auth_headers: dict):
    customers_payload = _api_get(
        api_client,
        "/api/finance/ar/customers",
        headers=auth_headers,
        params={
            "workshop_id": WORKSHOP_ID,
            "as_of": "2026-08-01",
            "include_today": "true",
        },
    )
    customers_data = _unwrap_data(customers_payload)
    assert float(customers_data.get("total_ar") or 0) == pytest.approx(4650.0, abs=0.01)

    customer_rows = _to_rows(customers_payload)
    faris_row = next((r for r in customer_rows if "فارس عوض" in str(r.get("customer") or r.get("name") or "")), None)
    assert faris_row is not None, "Customer فارس عوض not found in AR customers"
    assert float(faris_row.get("balance") or 0) == pytest.approx(500.0, abs=0.01)

    ledger_payload = _api_get(
        api_client,
        "/api/finance/ar/ledger",
        headers=auth_headers,
        params={"workshop_id": WORKSHOP_ID},
    )
    ledger_data = _unwrap_data(ledger_payload)
    ending_balance = ledger_data.get("ending_balance") if isinstance(ledger_data, dict) else None
    assert float(ending_balance or 0) == pytest.approx(4650.0, abs=0.01)


def test_trial_balance_and_balance_sheet_exclude_archive_and_match_targets(api_client: requests.Session, auth_headers: dict):
    trial_payload = _api_get(
        api_client,
        "/api/finance/reports/trial-balance",
        headers=auth_headers,
        params={"workshop_id": WORKSHOP_ID},
    )
    trial_totals = _to_totals(trial_payload)
    debit = float(trial_totals.get("total_debit") or 0)
    credit = float(trial_totals.get("total_credit") or 0)
    assert debit == pytest.approx(19130.0, abs=0.01)
    assert credit == pytest.approx(19130.0, abs=0.01)
    assert abs(debit - credit) <= 0.01

    bs_payload = _api_get(
        api_client,
        "/api/finance/reports/balance-sheet",
        headers=auth_headers,
        params={"workshop_id": WORKSHOP_ID},
    )
    bs_totals = _to_totals(bs_payload)
    assert float(bs_totals.get("assets") or 0) == pytest.approx(15730.0, abs=0.01)
    assert float(bs_totals.get("liabilities") or 0) == pytest.approx(1400.0, abs=0.01)
    assert float(bs_totals.get("equity") or 0) == pytest.approx(14330.0, abs=0.01)

    bs_data = _unwrap_data(bs_payload)
    assets_rows = ((bs_data or {}).get("sections") or {}).get("assets") or []
    ar_row = next((r for r in assets_rows if "عميل" in str(r.get("name") or "") or "ذمم" in str(r.get("name") or "")), None)
    if ar_row:
        assert float(ar_row.get("balance") or 0) == pytest.approx(4650.0, abs=0.01)


# Module: static code guards for forbidden direct journal_entries writes from frontend paths
def test_frontend_guard_no_direct_journal_entry_write_calls_in_target_pages():
    target_files = [
        BASE_DIR / "frontend/src/pages/VehicleDetails.jsx",
        BASE_DIR / "frontend/src/pages/SmartPOSJournal.jsx",
        BASE_DIR / "frontend/src/components/UnifiedBotWidget.jsx",
        BASE_DIR / "frontend/src/pages/JournalEntries.jsx",
    ]

    forbidden_patterns = [
        r"post\([^\n\r]*?/finance/journal-entries",
        r"put\([^\n\r]*?/finance/journal-entries",
        r"delete\([^\n\r]*?/finance/journal-entries",
        r"axios\.post\([^\n\r]*?/finance/journal-entries",
        r"axios\.put\([^\n\r]*?/finance/journal-entries",
        r"axios\.delete\([^\n\r]*?/finance/journal-entries",
    ]

    for file_path in target_files:
        text = file_path.read_text(encoding="utf-8")
        lower_text = text.lower()
        for pattern in forbidden_patterns:
            assert re.search(pattern, lower_text) is None, f"Forbidden direct write found in {file_path.name}: {pattern}"


# Module: backend code guard for confirm-payment anti-duplication behavior
def test_confirm_payment_route_code_does_not_use_operation_payment_income_fallback():
    route_file = BASE_DIR / "backend/routes_extended.py"
    text = route_file.read_text(encoding="utf-8")

    marker = "/operations/{op_id}/confirm-payment"
    idx = text.find(marker)
    assert idx >= 0, "confirm-payment route marker not found"

    block = text[idx: idx + 9000]
    assert "operation_payment_income" not in block, "confirm-payment route still references operation_payment_income"
