"""Iter343 live read-only verification for canonical finalization posting contracts."""

import os
import re
from pathlib import Path
from typing import Dict, Tuple

import pytest
import requests


VEHICLE_ID = "af49ee7e-24b5-4fd1-a4c6-2dc3c8f08f5c"
VISIT_ID = "76d7fe6d-f2dc-48fe-a7a8-2889cde85f87"
WORKSHOP_ID = "finmodule-sync"
CANONICAL_REF = f"vehfinal:{VEHICLE_ID}"


def _resolve_base_url() -> str:
    value = (os.environ.get("REACT_APP_BACKEND_URL") or "").strip()
    if value:
        return value.rstrip("/")
    env_file = Path("/app/frontend/.env")
    if not env_file.exists():
        return ""
    for line in env_file.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, val = raw.split("=", 1)
        if key.strip() == "REACT_APP_BACKEND_URL":
            return val.strip().rstrip("/")
    return ""


def _manager_creds_from_memory() -> Tuple[str, str]:
    username = (os.environ.get("TEST_MANAGER_USERNAME") or "").strip()
    pin = (os.environ.get("TEST_MANAGER_PIN") or "").strip()
    if username and pin:
        return username, pin

    path = Path("/app/memory/test_credentials.md")
    if not path.exists():
        return "", ""
    text = path.read_text(encoding="utf-8")
    user_match = re.search(r"\| `([^`]+)`\s+\| admin\s+\|", text)
    pin_match = re.search(r"admin\s+\|[^\n]+quick PIN `([^`]+)`", text)
    return (
        user_match.group(1).strip() if user_match else "",
        pin_match.group(1).strip() if pin_match else "",
    )


@pytest.fixture(scope="session")
def base_url() -> str:
    value = _resolve_base_url()
    if not value:
        pytest.skip("REACT_APP_BACKEND_URL missing")
    return value


@pytest.fixture(scope="session")
def auth_headers(base_url: str) -> Dict[str, str]:
    username, pin = _manager_creds_from_memory()
    if not username or not pin:
        pytest.skip("Manager credentials missing in /app/memory/test_credentials.md")

    response = requests.post(
        f"{base_url}/api/auth/login",
        json={"username": username, "pin": pin},
        timeout=30,
    )
    assert response.status_code == 200, response.text[:300]
    token = (response.json() or {}).get("access_token") or (response.json() or {}).get("token")
    assert token, "Missing access token in login response"
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _get_journal_entries(base_url: str, auth_headers: Dict[str, str], *, skip: int = 0, limit: int = 1000):
    # Module: finance journal list read-only verification
    response = requests.get(
        f"{base_url}/api/finance/journal-entries",
        params={"workshop_id": WORKSHOP_ID, "skip": skip, "limit": limit},
        headers=auth_headers,
        timeout=60,
    )
    assert response.status_code == 200, response.text[:300]
    payload = response.json() or {}
    assert payload.get("success") is True
    return payload.get("data") or []


def _find_entries_by_reference(base_url: str, auth_headers: Dict[str, str], reference_id: str):
    seen = []
    step = 500
    for offset in range(0, 5000, step):
        rows = _get_journal_entries(base_url, auth_headers, skip=offset, limit=step)
        if not rows:
            break
        found = [r for r in rows if str(r.get("reference_id") or "") == reference_id]
        if found:
            seen.extend(found)
        if len(rows) < step:
            break
    return seen


def test_live_vehicle_has_exactly_one_canonical_finalization_entry(base_url: str, auth_headers: Dict[str, str]):
    # Module: canonical business posting uniqueness + entry payload contract
    matches = _find_entries_by_reference(base_url, auth_headers, CANONICAL_REF)
    assert len(matches) == 1, f"Expected 1 canonical entry for {CANONICAL_REF}, got {len(matches)}"

    entry = matches[0]
    assert entry.get("source") == "vehicle_visit"
    assert entry.get("transaction_type") == "sale"
    assert round(float(entry.get("total") or 0), 2) == 1500.00

    description = str(entry.get("description") or "")
    assert "[BUSINESS_EVENT_ID:vehicle_finalization::af49ee7e-24b5-4fd1-a4c6-2dc3c8f08f5c]" in description
    assert "[ACCOUNTING_IDENTITY:vehfinal:af49ee7e-24b5-4fd1-a4c6-2dc3c8f08f5c]" in description
    assert "[FINAL_CUSTOMER_TOTAL:1500.0]" in description


def test_visit_has_no_temporary_sale_posting_after_visit_sync_change(base_url: str, auth_headers: Dict[str, str]):
    # Module: visit sync should not create temporary sale revenue entries
    visit_rows = _find_entries_by_reference(base_url, auth_headers, VISIT_ID)
    assert visit_rows, "Expected at least one journal entry for target visit reference"

    assert any(
        str(r.get("transaction_type") or "").strip().lower() == "payment"
        or str(r.get("source") or "") in {"operation_payment", "visit_receipt_voucher"}
        for r in visit_rows
    ), f"No payment journal entry found for visit. sources={sorted({str(r.get('source') or '') for r in visit_rows})} tx={sorted({str(r.get('transaction_type') or '') for r in visit_rows})}"
    forbidden = [
        r
        for r in visit_rows
        if str(r.get("source") or "") == "operation" and str(r.get("transaction_type") or "") == "sale"
    ]
    assert not forbidden, f"Unexpected temporary sale posting found for visit {VISIT_ID}"


def test_vehicle_financial_summary_matches_expected_numbers(base_url: str, auth_headers: Dict[str, str]):
    # Module: unified vehicle financial summary expected values
    response = requests.get(
        f"{base_url}/api/vehicles/{VEHICLE_ID}/financial-summary",
        headers=auth_headers,
        timeout=45,
    )
    assert response.status_code == 200, response.text[:300]
    data = response.json() or {}

    assert round(float(data.get("total_workshop") or 0), 2) == 1210.00
    assert round(float(data.get("supplier_archive_total") or 0), 2) == 1090.00
    assert round(float(data.get("final_customer_total") or 0), 2) == 1500.00
    assert round(float(data.get("confirmed_paid") or 0), 2) == 300.00
    assert round(float(data.get("display_remaining") or 0), 2) == 1200.00


def test_august_income_statement_includes_new_canonical_entry_and_zero_payment_revenue(
    base_url: str,
    auth_headers: Dict[str, str],
):
    # Module: August income-statement canonical revenue + payment classification contract
    response = requests.get(
        f"{base_url}/api/finance/reports/income-statement",
        params={
            "workshop_id": WORKSHOP_ID,
            "start_date": "2026-08-01",
            "end_date": "2026-08-31",
        },
        headers=auth_headers,
        timeout=60,
    )
    assert response.status_code == 200, response.text[:300]
    payload = response.json() or {}
    assert payload.get("success") is True

    data = payload.get("data") or {}
    totals = data.get("totals") or {}
    audit = data.get("revenue_source_audit") or {}
    counts = audit.get("classification_counts") or {}

    assert round(float(totals.get("revenue") or 0), 2) == 7494.00
    assert round(float(audit.get("canonical_revenue") or 0), 2) == 7494.00

    canonical = counts.get("CANONICAL_BUSINESS") or {}
    payment = counts.get("PAYMENT") or {}
    assert int(canonical.get("entries") or 0) >= 4
    assert int(payment.get("entries") or 0) >= 1
    assert round(float(payment.get("revenue") or 0), 2) == 0.00
