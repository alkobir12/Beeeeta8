"""Iter324: vehicle financial summary contract and arithmetic acceptance scenarios."""

import os
import sys
from pathlib import Path
from typing import Dict

import pytest
import requests

sys.path.append(str(Path(__file__).resolve().parents[1]))
from routes_extended import _calc_visit_financial


# Module: public financial-summary API contract + formula checks (no data mutation).


@pytest.fixture(scope="session")
def base_url() -> str:
    value = (os.environ.get("REACT_APP_BACKEND_URL") or "").strip().rstrip("/")
    if not value:
        pytest.skip("REACT_APP_BACKEND_URL is required for public-endpoint testing")
    return value


@pytest.fixture(scope="session")
def api_client() -> requests.Session:
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="session")
def auth_context(base_url: str, api_client: requests.Session) -> Dict[str, str]:
    response = api_client.post(
        f"{base_url}/api/auth/login",
        json={"username": "مدير", "pin": "123123"},
        timeout=30,
    )
    assert response.status_code == 200, f"Login failed: {response.status_code} {response.text}"
    data = response.json()
    access_token = data.get("access_token")
    assert isinstance(access_token, str) and access_token
    return {
        "access_token": access_token,
        "set_cookie": response.headers.get("set-cookie", ""),
    }


@pytest.fixture(scope="session")
def auth_client(api_client: requests.Session, auth_context: Dict[str, str]) -> requests.Session:
    api_client.headers.update({"Authorization": f"Bearer {auth_context['access_token']}"})
    return api_client


@pytest.fixture(scope="session")
def test_vehicle_id(base_url: str, auth_client: requests.Session) -> str:
    preferred_id = "f6590225-aef6-452b-af39-e0e42061fd81"
    preferred = auth_client.get(f"{base_url}/api/vehicles/{preferred_id}/financial-summary", timeout=30)
    if preferred.status_code == 200:
        return preferred_id

    vehicle_list = auth_client.get(f"{base_url}/api/vehicles", timeout=30)
    assert vehicle_list.status_code == 200, f"Vehicles list failed: {vehicle_list.status_code} {vehicle_list.text}"
    rows = vehicle_list.json() if isinstance(vehicle_list.json(), list) else []
    if not rows:
        pytest.skip("No vehicles available for financial-summary tests")
    candidate = rows[0].get("id")
    assert candidate, "Vehicle id missing in /api/vehicles payload"
    return candidate


def _assert_financial_formula(payload: Dict):
    total_workshop = float(payload.get("total_workshop") or 0)
    parts_charge_total = float(payload.get("parts_charge_total") or 0)
    customer_total = float(payload.get("customer_total") or 0)
    confirmed_paid = float(payload.get("confirmed_paid") or 0)
    applied_paid = float(payload.get("applied_paid") or 0)
    display_remaining = float(payload.get("display_remaining") or 0)
    customer_credit = float(payload.get("customer_credit") or 0)

    assert abs(customer_total - (total_workshop + parts_charge_total)) < 0.01
    assert abs(applied_paid - min(confirmed_paid, customer_total)) < 0.01
    assert abs(display_remaining - max(customer_total - applied_paid, 0.0)) < 0.01
    assert abs(customer_credit - max(confirmed_paid - customer_total, 0.0)) < 0.01


def test_login_sets_secure_httponly_cookie_flags(auth_context: Dict[str, str]):
    set_cookie = auth_context.get("set_cookie", "")
    assert "HttpOnly" in set_cookie
    assert "Secure" in set_cookie
    assert "SameSite=None" in set_cookie


def test_vehicle_financial_summary_formula_contract(base_url: str, auth_client: requests.Session, test_vehicle_id: str):
    response = auth_client.get(f"{base_url}/api/vehicles/{test_vehicle_id}/financial-summary", timeout=30)
    assert response.status_code == 200, response.text
    data = response.json()

    expected_fields = {
        "total_workshop",
        "parts_charge_total",
        "customer_total",
        "confirmed_paid",
        "applied_paid",
        "display_remaining",
        "customer_credit",
        "pending_payment_total",
    }
    assert expected_fields.issubset(set(data.keys()))
    _assert_financial_formula(data)


def test_invalid_vehicle_id_returns_404(base_url: str, auth_client: requests.Session):
    response = auth_client.get(f"{base_url}/api/vehicles/not-a-uuid/financial-summary", timeout=30)
    assert response.status_code == 404


@pytest.mark.parametrize(
    "parsed_notes,expected",
    [
        (
            {
                "items": [
                    {"itemType": "service", "total": 1800},
                    {"itemType": "supplier", "total": 975},
                ],
                "payments": [],
            },
            {"customer_total": 2775.0, "applied_paid": 0.0, "display_remaining": 2775.0, "customer_credit": 0.0},
        ),
        (
            {
                "items": [
                    {"itemType": "service", "total": 31},
                    {"itemType": "part", "total": 271},
                ],
                "payments": [{"amount": 200, "status": "confirmed", "confirmed": True}],
            },
            {"customer_total": 302.0, "applied_paid": 200.0, "display_remaining": 102.0, "customer_credit": 0.0},
        ),
        (
            {
                "items": [
                    {"itemType": "service", "total": 31},
                    {"itemType": "part", "total": 271},
                ],
                "payments": [{"amount": 400, "status": "confirmed", "confirmed": True}],
            },
            {"customer_total": 302.0, "applied_paid": 302.0, "display_remaining": 0.0, "customer_credit": 98.0},
        ),
    ],
)
def test_acceptance_arithmetic_scenarios(parsed_notes: Dict, expected: Dict):
    result = _calc_visit_financial(parsed_notes)
    customer_total = float(result["customer_total"])
    confirmed_paid = float(result["paid_on_account"])
    applied_paid = min(confirmed_paid, customer_total)
    display_remaining = max(customer_total - applied_paid, 0.0)
    customer_credit = max(confirmed_paid - customer_total, 0.0)

    assert abs(customer_total - expected["customer_total"]) < 0.01
    assert abs(applied_paid - expected["applied_paid"]) < 0.01
    assert abs(display_remaining - expected["display_remaining"]) < 0.01
    assert abs(customer_credit - expected["customer_credit"]) < 0.01
