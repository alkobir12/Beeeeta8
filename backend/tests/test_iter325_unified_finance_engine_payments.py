"""Iter325: unified finance engine endpoints + dry-run payment confirmation checks."""

import os
from datetime import datetime
from typing import Dict, Any

import pytest
import requests


# Module: unified-v1 vehicle summary + AR endpoints + dry_run confirm payment flow.


@pytest.fixture(scope="session")
def base_url() -> str:
    value = (os.environ.get("REACT_APP_BACKEND_URL") or "").strip().rstrip("/")
    if not value:
        pytest.skip("REACT_APP_BACKEND_URL is required")
    return value


@pytest.fixture(scope="session")
def api_client() -> requests.Session:
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="session")
def auth_client(base_url: str, api_client: requests.Session) -> requests.Session:
    response = api_client.post(
        f"{base_url}/api/auth/login",
        json={"username": "مدير", "pin": "123123"},
        timeout=30,
    )
    assert response.status_code == 200, f"Login failed: {response.status_code} {response.text}"
    payload = response.json()
    token = payload.get("access_token")
    assert isinstance(token, str) and token
    api_client.headers.update({"Authorization": f"Bearer {token}"})

    set_cookie = response.headers.get("set-cookie", "")
    assert "HttpOnly" in set_cookie
    return api_client


@pytest.fixture(scope="session")
def test_vehicle_id() -> str:
    return "f6590225-aef6-452b-af39-e0e42061fd81"


def _find_open_visit(summary: Dict[str, Any]) -> Dict[str, Any]:
    visits = summary.get("visits") or []
    if not visits:
        return {}
    with_balance = [v for v in visits if float(v.get("display_remaining") or 0) > 0]
    return with_balance[0] if with_balance else visits[0]


def test_vehicle_financial_summary_uses_unified_engine(
    base_url: str,
    auth_client: requests.Session,
    test_vehicle_id: str,
):
    response = auth_client.get(f"{base_url}/api/vehicles/{test_vehicle_id}/financial-summary", timeout=30)
    assert response.status_code == 200, response.text
    data = response.json()

    assert data.get("engine_version") == "unified-v1"
    total_workshop = float(data.get("total_workshop") or 0)
    parts_charge_total = float(data.get("parts_charge_total") or 0)
    customer_total = float(data.get("customer_total") or 0)
    assert abs(customer_total - (total_workshop + parts_charge_total)) < 0.01


def test_ar_customers_returns_non_empty_current_snapshot(base_url: str, auth_client: requests.Session):
    as_of = datetime.utcnow().strftime("%Y-%m-%d")
    response = auth_client.get(
        f"{base_url}/api/finance/ar/customers",
        params={"workshop_id": "finmodule-sync", "as_of": as_of},
        timeout=40,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload.get("success") is True
    data = payload.get("data") or {}
    assert isinstance(data.get("customers"), list)
    assert len(data.get("customers") or []) > 0


def test_ar_ledger_returns_non_empty_rows(base_url: str, auth_client: requests.Session):
    response = auth_client.get(
        f"{base_url}/api/finance/ar/ledger",
        params={"workshop_id": "finmodule-sync"},
        timeout=40,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload.get("success") is True
    rows = (payload.get("data") or {}).get("rows") or []
    assert isinstance(rows, list)
    assert len(rows) > 0


def test_confirm_payment_dry_run_does_not_mutate_data(
    base_url: str,
    auth_client: requests.Session,
    test_vehicle_id: str,
):
    summary_before_response = auth_client.get(
        f"{base_url}/api/vehicles/{test_vehicle_id}/financial-summary",
        timeout=30,
    )
    assert summary_before_response.status_code == 200
    summary_before = summary_before_response.json()

    selected_visit = _find_open_visit(summary_before)
    visit_id = selected_visit.get("visit_id")
    if not visit_id:
        pytest.skip("No visit available for dry_run payment test")

    confirmed_before = float(summary_before.get("confirmed_paid") or 0)
    remaining_before = float(summary_before.get("display_remaining") or 0)

    dry_run_payload = {
        "amount": 200,
        "method": "cash",
        "dry_run": True,
        "workshop_id": "finmodule-sync",
        "reference": "iter325-dry-run",
    }
    dry_run_response = auth_client.post(
        f"{base_url}/api/finance-engine/visits/{visit_id}/payments/confirm",
        json=dry_run_payload,
        timeout=40,
    )
    assert dry_run_response.status_code == 200, dry_run_response.text
    dry_run_data = dry_run_response.json()

    assert dry_run_data.get("dry_run") is True
    assert dry_run_data.get("engine_version") == "unified-v1"
    payment = dry_run_data.get("payment") or {}
    assert payment.get("confirmed") is True
    assert payment.get("status") == "confirmed"
    assert isinstance(dry_run_data.get("journal_preview"), dict)

    summary_preview = dry_run_data.get("summary") or {}
    assert float(summary_preview.get("confirmed_paid") or 0) >= confirmed_before
    assert float(summary_preview.get("display_remaining") or 0) <= remaining_before

    summary_after_response = auth_client.get(
        f"{base_url}/api/vehicles/{test_vehicle_id}/financial-summary",
        timeout=30,
    )
    assert summary_after_response.status_code == 200
    summary_after = summary_after_response.json()

    assert abs(float(summary_after.get("confirmed_paid") or 0) - confirmed_before) < 0.01
    assert abs(float(summary_after.get("display_remaining") or 0) - remaining_before) < 0.01
