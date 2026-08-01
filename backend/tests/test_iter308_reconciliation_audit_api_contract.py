"""Iteration 308 — reconciliation audit API contract (read-only).

Modules/features covered:
- Auth guard (anonymous rejected, manager allowed)
- Reconciliation acceptance invariants and deterministic read-only behavior
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

import pytest
import requests
from dotenv import load_dotenv


load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"
API = f"{BASE_URL}/api"

MANAGER_USERNAME = "مدير"
MANAGER_PIN = "123123"
RATE_BYPASS = (os.environ.get("RATE_LIMIT_BYPASS_TOKEN") or "").strip().strip('"')

OVERLAP_IDS = {
    "235cb00f-facb-46aa-a4eb-8db039ec21ee",
    "9004d4bd-ed82-4e0d-afa4-fd62e6e3d8fa",
}


def _build_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    if RATE_BYPASS:
        s.headers["x-ratelimit-bypass"] = RATE_BYPASS
    return s


@pytest.fixture(scope="module")
def auth_session() -> requests.Session:
    """Auth module: manager PIN login fixture for protected endpoint checks."""
    s = _build_session()
    login = s.post(
        f"{API}/auth/login",
        json={"username": MANAGER_USERNAME, "pin": MANAGER_PIN},
        timeout=30,
    )
    if login.status_code != 200:
        pytest.skip(f"Manager login unavailable in preview: {login.status_code} {login.text[:180]}")

    payload = login.json() if isinstance(login.json(), dict) else {}
    token = payload.get("access_token")
    if not token:
        pytest.skip("Login succeeded but access_token missing")

    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


def _get_audit_payload(session: requests.Session) -> Dict[str, Any]:
    response = session.get(f"{API}/finance/reconciliation-audit", timeout=60)
    assert response.status_code == 200, response.text[:300]
    data = response.json()
    assert data.get("success") is True
    return data


def test_reconciliation_audit_requires_auth_token():
    """Auth module: endpoint must reject anonymous requests."""
    s = _build_session()
    response = s.get(f"{API}/finance/reconciliation-audit", timeout=30)
    assert response.status_code in (401, 403)


def test_reconciliation_audit_manager_contract_and_readonly_stability(auth_session: requests.Session):
    """Finance module: full acceptance contract + read-only deterministic behavior."""
    report1 = _get_audit_payload(auth_session)
    report2 = _get_audit_payload(auth_session)

    metadata = report1["metadata"]
    assert metadata["read_only"] is True
    assert metadata["production_pages_unchanged"] is True
    assert isinstance(metadata.get("equations_version"), str) and metadata["equations_version"]

    guard1 = report1["mutation_guard"]
    guard2 = report2["mutation_guard"]
    assert guard1["before_counts"] == guard1["after_counts"]
    assert guard2["before_counts"] == guard2["after_counts"]
    assert guard1["unchanged"] is True
    assert guard2["unchanged"] is True

    raw = report1["raw_classification"]
    assert raw["vehicles_total"] == 191
    assert raw["dashboard_visible_current_logic_count"] == 15
    assert raw["raw_archive_status_count"] == 178
    assert set(raw["overlap_active_and_raw_archive_ids"]) == OVERLAP_IDS

    scopes = report1["resolved_exclusive_scopes"]
    vehicle_counts = scopes["vehicle_scope_counts"]
    assert vehicle_counts == {
        "live": 15,
        "archive": 176,
        "total": 191,
        "exclusive_sum_ok": True,
    }

    assert scopes["journal_entry_scope_sum"] == scopes["journal_entry_total"]
    assert scopes["operation_scope_sum"] == scopes["operation_total"]
    assert scopes["journal_entry_exclusive_sum_ok"] is True
    assert scopes["operation_exclusive_sum_ok"] is True

    journal_rows: List[Dict[str, Any]] = report1["record_classification_rows"]["journal_entries"]
    operation_rows: List[Dict[str, Any]] = report1["record_classification_rows"]["operations"]
    assert len(journal_rows) == len({row["journal_entry_id"] for row in journal_rows})
    assert len(operation_rows) == len({row["operation_id"] for row in operation_rows})

    ar = report1["ar_reconciliation"]
    assert ar["credit_sales_total"] == pytest.approx(54135.0)
    assert ar["payment_allocations_total"] == pytest.approx(2900.0)
    assert ar["remaining_by_credit_operations_minus_allocations"] == pytest.approx(51235.0)
    assert ar["owner_reported_page_total_from_baseline"] == pytest.approx(51735.0)
    assert ar["delta_against_owner_reported"] == pytest.approx(500.0)

    allocations = ar["payment_allocations"]
    assert isinstance(allocations, list) and allocations
    required_keys = {
        "payment_id",
        "journal_entry_id",
        "amount",
        "source",
        "operation_id",
        "visit_id",
        "vehicle_id",
        "approval_status",
        "payment_method",
        "resulting_journal_entry",
    }
    for row in allocations:
        assert required_keys.issubset(row.keys())

    candidates = ar["delta_500_candidates"]
    assert any(
        row.get("candidate_type") == "credit_operation_not_payment" and row.get("amount") == 500.0
        for row in candidates
    )

    revenue = report1["revenue_210_reconciliation"]
    assert revenue["account"] == "041"
    assert revenue["total"] == pytest.approx(210.0)
    assert any(row.get("journal_entry_id") for row in revenue.get("rows", []))

    expense = report1["expense_reconciliation"]
    assert expense["account"] == "035"
    assert expense["total"] == pytest.approx(16810.0)
    assert isinstance(expense.get("previous_gap_210_explanation"), str)

    opening = report1["opening_balance_scenarios"]["pending_decision_rows"]
    assert {row["ar_net"] for row in opening} == {16000.0, 300.0}
    assert all(row["resolved_scope"] == "pending_decision" for row in opening)
    opening_je_ids = {row["journal_entry_id"] for row in opening}
    legacy_rows = [r for r in journal_rows if r.get("journal_entry_id") in opening_je_ids and r.get("resolved_scope") == "legacy_excluded"]
    assert not legacy_rows

    standalone_pos = report1["standalone_pos_operations"]
    assert any(row.get("origin_type") == "standalone_pos_sale" for row in standalone_pos)
    assert any(
        row.get("origin_type") == "standalone_pos_sale"
        and row.get("total") == 350.0
        and row.get("resolved_scope") == "posting_missing"
        for row in standalone_pos
    )

    trial = report1["trial_balance"]
    assert trial["balanced"] is True
    assert trial["total_debit"] == pytest.approx(trial["total_credit"])

    assert report1["acceptance_flags"] == report2["acceptance_flags"]
    assert report1["raw_classification"]["vehicles_total"] == report2["raw_classification"]["vehicles_total"]
    assert report1["resolved_exclusive_scopes"]["vehicle_scope_counts"] == report2["resolved_exclusive_scopes"]["vehicle_scope_counts"]
