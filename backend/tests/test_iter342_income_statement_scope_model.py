"""Iter342: Income statement reporting-scope model regression (period + semantic classification)."""

import os
import re
from pathlib import Path

import pytest
import requests


def _resolve_base_url() -> str:
    direct = os.environ.get("REACT_APP_BACKEND_URL")
    if direct:
        return direct
    env_file = Path("/app/frontend/.env")
    if not env_file.exists():
        return ""
    for line in env_file.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        if key.strip() == "REACT_APP_BACKEND_URL":
            return value.strip()
    return ""


BASE_URL = _resolve_base_url()
LOGIN_URL = "/api/auth/login"
INCOME_URL = (
    "/api/finance/reports/income-statement"
    "?workshop_id=finmodule-sync&start_date=2026-08-01&end_date=2026-08-31"
)


def _load_test_credential(field: str) -> str:
    env_key = f"TEST_MANAGER_{field.upper()}"
    value = os.environ.get(env_key, "").strip()
    if value:
        return value
    credentials_path = Path("/app/memory/test_credentials.md")
    if not credentials_path.exists():
        return ""
    text = credentials_path.read_text(encoding="utf-8")
    if field == "username":
        match = re.search(r"\| `([^`]+)`\s+\| admin\s+\|", text)
    else:
        match = re.search(r"\|\s*`مدير`\s*\|\s*admin\s*\|[^\n]*\|\s*`([^`]+)`\s*\|", text)
    return match.group(1).strip() if match else ""


@pytest.fixture(scope="session")
def api_base_url() -> str:
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL missing from environment")
    return BASE_URL.rstrip("/")


@pytest.fixture(scope="session")
def auth_headers(api_base_url: str):
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    manager_username = _load_test_credential("username")
    manager_password = _load_test_credential("password")
    if not manager_username or not manager_password:
        pytest.skip("Manager test credentials missing")

    response = session.post(
        f"{api_base_url}{LOGIN_URL}",
        json={"username": manager_username, "password": manager_password},
        timeout=30,
    )
    if response.status_code != 200:
        pytest.skip(f"Manager password login failed: {response.status_code} {response.text[:180]}")

    body = response.json()
    token = body.get("access_token") or body.get("token")
    if not token:
        pytest.skip("Login succeeded but no access token returned")

    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def august_income_statement(api_base_url: str, auth_headers):
    response = requests.get(
        f"{api_base_url}{INCOME_URL}",
        headers=auth_headers,
        timeout=60,
    )
    assert response.status_code == 200, response.text[:500]
    payload = response.json()
    assert payload.get("success") is True
    return payload.get("data") or {}


# Module: income statement totals and period-based scope behavior
def test_income_statement_august_2026_totals(august_income_statement):
    totals = august_income_statement.get("totals") or {}
    assert totals.get("revenue") >= 5994
    assert totals.get("expenses") >= 2274
    assert totals.get("net_income") == pytest.approx(totals.get("revenue") - totals.get("expenses"), abs=0.01)


# Module: revenue source audit contract values
def test_income_statement_revenue_source_audit_values(august_income_statement):
    audit = august_income_statement.get("revenue_source_audit") or {}
    assert audit.get("canonical_revenue") >= 5994
    assert audit.get("excluded_alignment") == 8948.84
    assert audit.get("excluded_repairs") == 7305
    assert audit.get("excluded_temporary") == 7760
    assert audit.get("excluded_closing") == 30007.84
    assert audit.get("unknown_entries") == []
    expected_margin = ((audit.get("net_income") or 0) / (audit.get("canonical_revenue") or 1)) * 100
    assert audit.get("margin") == pytest.approx(expected_margin, abs=0.02)


# Module: statement safety contract
def test_income_statement_statement_safety_scope_model(august_income_statement):
    safety = august_income_statement.get("statement_safety") or {}
    assert safety.get("reporting_scope_model") == "period_based_semantic_classification_v2"
    assert safety.get("vehicle_status_affects_income_statement") is False
    assert safety.get("unknown_entries_count") == 0


# Module: classification count contract
def test_income_statement_classification_counts(august_income_statement):
    classification_counts = (august_income_statement.get("revenue_source_audit") or {}).get("classification_counts") or {}

    canonical = classification_counts.get("CANONICAL_BUSINESS") or {}
    expense = classification_counts.get("EXPENSE") or {}

    assert canonical.get("entries") >= 3
    assert canonical.get("revenue") >= 5994
    assert expense.get("entries") >= 5
    assert expense.get("expenses") >= 2274


# Module: code-level safeguard that income-statement endpoint no longer uses live-vehicle filter
def test_income_statement_endpoint_no_live_filter_reference():
    src = Path("/app/backend/routes_finance.py").read_text(encoding="utf-8")
    start = src.index('@router.get("/reports/income-statement")')
    end = src.index('@router.get("/reports/cash-flow")', start)
    fn_body = src[start:end]

    assert "_filter_live_journal_entries" not in fn_body
    assert '"vehicle_status_affects_income_statement": False' in fn_body
