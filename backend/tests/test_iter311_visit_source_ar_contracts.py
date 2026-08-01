"""Iter-311 regression: visit-source AR SSOT and supplier exclusion contracts."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import pytest
import requests


# Module: preview-url bootstrap + auth contract
BASE_DIR = Path(__file__).resolve().parents[2]
FRONTEND_ENV_PATH = BASE_DIR / "frontend" / ".env"
WORKSHOP_ID = "finmodule-sync"


def _read_frontend_env_base_url() -> str:
    raw = FRONTEND_ENV_PATH.read_text(encoding="utf-8")
    for line in raw.splitlines():
        if line.strip().startswith("REACT_APP_BACKEND_URL="):
            return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not found in frontend/.env")


BASE_URL = _read_frontend_env_base_url()


@pytest.fixture(scope="session")
def api_client() -> requests.Session:
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="session")
def auth_headers(api_client: requests.Session) -> Dict[str, str]:
    response = api_client.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": "مدير", "pin": "123123"},
        timeout=30,
    )
    assert response.status_code == 200, f"Manager login failed: {response.status_code} {response.text[:250]}"
    payload = response.json()
    token = payload.get("access_token") or payload.get("token")
    assert isinstance(token, str) and token.strip(), "Missing login access token"

    set_cookie = response.headers.get("set-cookie", "")
    assert set_cookie, "Expected Set-Cookie on login"
    assert "httponly" in set_cookie.lower(), "Login cookie is not HttpOnly"

    return {"Authorization": f"Bearer {token}"}


def _api_get(
    api_client: requests.Session,
    path: str,
    *,
    headers: Dict[str, str] | None = None,
    params: Dict[str, Any] | None = None,
) -> Any:
    response = api_client.get(f"{BASE_URL}{path}", headers=headers, params=params, timeout=45)
    assert response.status_code == 200, f"GET {path} failed: {response.status_code} {response.text[:400]}"
    return response.json()


def _to_float(value: Any) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


# Module: /api/finance/ar/customers snapshot and supplier-exclusion checks
def test_ar_customers_snapshot_totals_and_vehicle_count(api_client: requests.Session, auth_headers: Dict[str, str]):
    payload = _api_get(
        api_client,
        "/api/finance/ar/customers",
        headers=auth_headers,
        params={
            "workshop_id": WORKSHOP_ID,
            "as_of": "2026-08-01",
            "include_today": "true",
        },
    )
    assert payload.get("success") is True

    data = payload.get("data") or {}
    vehicles = data.get("vehicles") or []
    customers = data.get("customers") or []

    assert len(vehicles) == 15
    assert _to_float(data.get("total_ar")) == pytest.approx(12570.0, abs=0.01)
    assert len(customers) == 12


def test_ar_customers_vehicle_61fe0b56_supplier_excluded(api_client: requests.Session, auth_headers: Dict[str, str]):
    payload = _api_get(
        api_client,
        "/api/finance/ar/customers",
        headers=auth_headers,
        params={
            "workshop_id": WORKSHOP_ID,
            "as_of": "2026-08-01",
            "include_today": "true",
        },
    )
    data = payload.get("data") or {}
    vehicles = data.get("vehicles") or []

    row = next((v for v in vehicles if str(v.get("vehicle_id") or "").startswith("61fe0b56")), None)
    assert row is not None, "Vehicle 61fe0b56 not found in AR snapshot"
    assert _to_float(row.get("workshop_amount")) == pytest.approx(600.0, abs=0.01)
    assert _to_float(row.get("supplier_amount")) == pytest.approx(179.0, abs=0.01)
    assert _to_float(row.get("receivable")) == pytest.approx(600.0, abs=0.01)


def test_ar_customers_specific_vehicle_examples_match_policy(api_client: requests.Session, auth_headers: Dict[str, str]):
    payload = _api_get(
        api_client,
        "/api/finance/ar/customers",
        headers=auth_headers,
        params={
            "workshop_id": WORKSHOP_ID,
            "as_of": "2026-08-01",
            "include_today": "true",
        },
    )
    data = payload.get("data") or {}
    vehicles = data.get("vehicles") or []

    def by_id_prefix(prefix: str) -> Dict[str, Any]:
        row = next((v for v in vehicles if str(v.get("vehicle_id") or "").startswith(prefix)), None)
        assert row is not None, f"Vehicle with prefix {prefix} not found"
        return row

    sultan = next((v for v in vehicles if "سلطان الشاص" in str(v.get("customer") or "")), None)
    assert sultan is not None, "Customer سلطان الشاص not found in snapshot"
    sultan_visit_ids = [str(v.get("visit_id") or "") for v in (sultan.get("visits") or [])]
    assert any(vid.startswith("b48c0850") for vid in sultan_visit_ids), (
        f"Expected سلطان الشاص example visit prefix b48c0850, got visits={sultan_visit_ids}"
    )
    assert _to_float(sultan.get("workshop_amount")) == pytest.approx(300.0, abs=0.01)
    assert _to_float(sultan.get("confirmed_paid")) == pytest.approx(0.0, abs=0.01)
    assert _to_float(sultan.get("receivable")) == pytest.approx(300.0, abs=0.01)

    faris = next((v for v in vehicles if "فارس عوض" in str(v.get("customer") or "")), None)
    assert faris is not None, "Customer فارس عوض not found in snapshot"
    assert _to_float(faris.get("workshop_amount")) == pytest.approx(2500.0, abs=0.01)
    assert _to_float(faris.get("confirmed_paid")) == pytest.approx(0.0, abs=0.01)
    assert _to_float(faris.get("receivable")) == pytest.approx(2500.0, abs=0.01)

    abu_rakan = next((v for v in vehicles if "ابو ركان" in str(v.get("customer") or "") or "أبو ركان" in str(v.get("customer") or "")), None)
    assert abu_rakan is not None, "Customer ابو ركان not found in snapshot"
    assert _to_float(abu_rakan.get("workshop_amount")) == pytest.approx(2350.0, abs=0.01)
    assert _to_float(abu_rakan.get("confirmed_paid")) == pytest.approx(0.0, abs=0.01)
    assert _to_float(abu_rakan.get("receivable")) == pytest.approx(2350.0, abs=0.01)

    saleh = next((v for v in vehicles if "صالح المهوس" in str(v.get("customer") or "")), None)
    if saleh is not None:
        assert _to_float(saleh.get("workshop_amount")) == pytest.approx(0.0, abs=0.01)
        assert _to_float(saleh.get("receivable")) == pytest.approx(0.0, abs=0.01)


def test_ar_customers_excludes_archived_from_current_totals(api_client: requests.Session, auth_headers: Dict[str, str]):
    payload = _api_get(
        api_client,
        "/api/finance/ar/customers",
        headers=auth_headers,
        params={
            "workshop_id": WORKSHOP_ID,
            "as_of": "2026-08-01",
            "include_today": "true",
        },
    )
    vehicles = (payload.get("data") or {}).get("vehicles") or []
    archived_rows = [v for v in vehicles if str(v.get("raw_status") or "").strip().lower() == "archived"]
    if archived_rows:
        assert all(_to_float(v.get("receivable")) == pytest.approx(0.0, abs=0.01) for v in archived_rows)
        assert all(v.get("included_in_current_ar") is False for v in archived_rows)


# Module: /api/customers must align with AR customers total and count-of-positive
def test_customers_endpoint_aligns_with_ar_totals(api_client: requests.Session, auth_headers: Dict[str, str]):
    rows = _api_get(
        api_client,
        "/api/customers",
        headers=auth_headers,
        params={"workshop_id": WORKSHOP_ID},
    )
    assert isinstance(rows, list)

    positive_rows: List[Dict[str, Any]] = []
    total_due = 0.0
    for row in rows:
        ajel = _to_float(row.get("ajelBalance"))
        overdue = _to_float(row.get("overdueBalance"))
        net = max(ajel, overdue)
        if net > 0.005:
            positive_rows.append(row)
            total_due += net

    assert len(positive_rows) == 12
    assert round(total_due, 2) == pytest.approx(12570.0, abs=0.01)


# Module: AR ledger and income statement contracts
def test_ar_ledger_matches_expected_ending_and_rows(api_client: requests.Session, auth_headers: Dict[str, str]):
    payload = _api_get(
        api_client,
        "/api/finance/ar/ledger",
        headers=auth_headers,
        params={"workshop_id": WORKSHOP_ID},
    )
    assert payload.get("success") is True
    data = payload.get("data") or {}
    rows = data.get("rows") or []

    assert len(rows) == 12
    assert _to_float(data.get("ending_balance")) == pytest.approx(12570.0, abs=0.01)


def test_income_statement_sales_summary_matches_unconfirmed_notes_policy(api_client: requests.Session, auth_headers: Dict[str, str]):
    payload = _api_get(
        api_client,
        "/api/finance/reports/income-statement",
        headers=auth_headers,
        params={"workshop_id": WORKSHOP_ID},
    )
    assert payload.get("success") is True

    data = payload.get("data") or {}
    sales = data.get("sales_summary") or {}

    assert _to_float(sales.get("operations_total")) == pytest.approx(12570.0, abs=0.01)
    assert _to_float(sales.get("operations_credit_total")) == pytest.approx(12570.0, abs=0.01)
    assert _to_float(sales.get("operations_cash_total")) == pytest.approx(0.0, abs=0.01)
    assert _to_float(sales.get("operations_pos_total")) == pytest.approx(0.0, abs=0.01)
    assert _to_float(sales.get("operations_bank_transfer_total")) == pytest.approx(0.0, abs=0.01)


# Module: read-only safety check (no auto journal create during calculations)
def test_reconciliation_audit_read_only_and_zero_journal_entries(api_client: requests.Session, auth_headers: Dict[str, str]):
    payload = _api_get(
        api_client,
        "/api/finance/reconciliation-audit",
        headers=auth_headers,
        params={"workshop_id": WORKSHOP_ID},
    )
    assert payload.get("success") is True
    assert (payload.get("mutation_guard") or {}).get("unchanged") is True

    counts = (payload.get("resolved_exclusive_scopes") or {}).get("counts") or {}
    if "journal_entry_total" in counts:
        assert int(counts.get("journal_entry_total") or 0) == 0
