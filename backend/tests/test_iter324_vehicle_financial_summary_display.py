"""Iter324: Vehicle financial summary display contract + auth smoke checks."""

import os
from typing import Dict

import pytest
import requests


# Module scope: validate /api/vehicles/{id}/financial-summary response fields and formulas.


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
    login_payload = {"username": "مدير", "pin": "123123"}
    response = api_client.post(f"{base_url}/api/auth/login", json=login_payload, timeout=30)
    assert response.status_code == 200, f"Login failed: {response.status_code} {response.text}"
    data = response.json()
    access_token = data.get("access_token")
    assert isinstance(access_token, str) and access_token, "Missing access_token in login response"
    return {
        "access_token": access_token,
        "set_cookie": response.headers.get("set-cookie", ""),
        "allow_origin": response.headers.get("access-control-allow-origin", ""),
        "allow_credentials": response.headers.get("access-control-allow-credentials", ""),
    }


@pytest.fixture(scope="session")
def auth_client(base_url: str, api_client: requests.Session, auth_context: Dict[str, str]) -> requests.Session:
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


def test_financial_summary_contains_old_and_new_fields(base_url: str, auth_client: requests.Session, test_vehicle_id: str):
    response = auth_client.get(f"{base_url}/api/vehicles/{test_vehicle_id}/financial-summary", timeout=30)
    assert response.status_code == 200, response.text
    data = response.json()

    expected_fields = {
        "total_workshop",
        "total_suppliers",
        "supplier_archive_total",
        "total_paid",
        "advance_paid",
        "total_amount",
        "balance",
        "total_items",
        "display_remaining",
        "paid_on_account",
        "confirmed_paid",
        "customer_advance_liability",
    }
    missing = expected_fields - set(data.keys())
    assert not missing, f"Missing fields: {sorted(missing)}"


def test_total_items_equals_workshop_plus_suppliers(base_url: str, auth_client: requests.Session, test_vehicle_id: str):
    response = auth_client.get(f"{base_url}/api/vehicles/{test_vehicle_id}/financial-summary", timeout=30)
    assert response.status_code == 200
    data = response.json()

    total_items = float(data.get("total_items") or 0)
    expected = float(data.get("total_workshop") or 0) + float(data.get("total_suppliers") or 0)
    assert abs(total_items - expected) < 0.01, f"total_items={total_items}, expected={expected}"


def test_display_remaining_equals_total_items_minus_total_paid(base_url: str, auth_client: requests.Session, test_vehicle_id: str):
    response = auth_client.get(f"{base_url}/api/vehicles/{test_vehicle_id}/financial-summary", timeout=30)
    assert response.status_code == 200
    data = response.json()

    display_remaining = float(data.get("display_remaining") or 0)
    expected = float(data.get("total_items") or 0) - float(data.get("total_paid") or 0)
    assert abs(display_remaining - expected) < 0.01, f"display_remaining={display_remaining}, expected={expected}"


def test_confirmed_paid_equals_paid_on_account(base_url: str, auth_client: requests.Session, test_vehicle_id: str):
    response = auth_client.get(f"{base_url}/api/vehicles/{test_vehicle_id}/financial-summary", timeout=30)
    assert response.status_code == 200
    data = response.json()
    assert float(data.get("confirmed_paid") or 0) == float(data.get("paid_on_account") or 0)


def test_customer_advance_liability_matches_advance_paid(base_url: str, auth_client: requests.Session, test_vehicle_id: str):
    response = auth_client.get(f"{base_url}/api/vehicles/{test_vehicle_id}/financial-summary", timeout=30)
    assert response.status_code == 200
    data = response.json()
    assert float(data.get("customer_advance_liability") or 0) == float(data.get("advance_paid") or 0)


def test_invalid_vehicle_id_returns_404(base_url: str, auth_client: requests.Session):
    response = auth_client.get(f"{base_url}/api/vehicles/not-a-uuid/financial-summary", timeout=30)
    assert response.status_code == 404


def test_login_sets_secure_httponly_cookie_flags(auth_context: Dict[str, str]):
    set_cookie = auth_context.get("set_cookie", "")
    assert "HttpOnly" in set_cookie
    assert "Secure" in set_cookie
    assert "SameSite=None" in set_cookie
