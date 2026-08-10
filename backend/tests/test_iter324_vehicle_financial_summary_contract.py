"""Iter324: vehicle financial summary contract and arithmetic acceptance scenarios."""

import os
import sys
from pathlib import Path
from typing import Dict

import pytest
import requests

sys.path.append(str(Path(__file__).resolve().parents[1]))
from routes_extended import _calc_visit_financial
from core.operation_journal_adapter import _build_operation_journal_entry
from core.unified_financial_engine import build_vehicle_summary, serialize_notes


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

    assert abs(customer_total - total_workshop) < 0.01 or payload.get("final_customer_total") is not None
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
            {"customer_total": 1800.0, "applied_paid": 0.0, "display_remaining": 1800.0, "customer_credit": 0.0},
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


def test_supplier_items_are_archive_only_for_journal_entry():
    op = {
        "id": "op-supplier-archive-only",
        "type": "service",
        "paymentMethod": "credit",
        "paymentStatus": "credit",
        "total": 1500,
        "items": [
            {"itemType": "service", "name": "خدمة", "total": 1000},
            {"itemType": "supplier", "name": "أبو خالد", "total": 500, "revenueAccountCode": "041", "linkedPart": "x"},
        ],
    }
    entry = _build_operation_journal_entry(op, "finmodule-sync")
    assert isinstance(entry, dict)
    assert float(entry["total"]) == 1000
    assert float(entry["workshop_total"]) == 1000
    assert float(entry["supplier_archive_total"]) == 500
    credits = {line["account"]: float(line.get("credit") or 0) for line in entry["lines"]}
    debits = {line["account"]: float(line.get("debit") or 0) for line in entry["lines"]}
    assert debits.get("005") == 1000
    assert sum(credits.values()) == 1000
    assert credits.get("041", 0) == 0


def test_final_customer_total_is_explicit_not_supplier_derived():
    visits = [
        {
            "id": "visit-final",
            "vehicle_id": "vehicle-final",
            "notes": serialize_notes({
                "items": [
                    {"itemType": "service", "total": 1000},
                    {"itemType": "supplier", "total": 500},
                ],
                "payments": [{"amount": 300, "confirmed": True, "status": "confirmed"}],
            }),
        }
    ]
    base = build_vehicle_summary({"id": "vehicle-final", "notes": "{}"}, visits, {}, {})
    assert base["total_workshop"] == 1000
    assert base["supplier_archive_total"] == 500
    assert base["customer_total"] == 1000
    assert base["display_remaining"] == 700

    finalized_1500 = build_vehicle_summary({"id": "vehicle-final", "notes": serialize_notes({"financial_finalization": {"final_customer_total": 1500}})}, visits, {}, {})
    assert finalized_1500["final_customer_total"] == 1500
    assert finalized_1500["customer_total"] == 1500
    assert finalized_1500["display_remaining"] == 1200

    finalized_1400 = build_vehicle_summary({"id": "vehicle-final", "notes": serialize_notes({"financial_finalization": {"final_customer_total": 1400}})}, visits, {}, {})
    assert finalized_1400["final_customer_total"] == 1400
    assert finalized_1400["customer_total"] == 1400
    assert finalized_1400["display_remaining"] == 1100
