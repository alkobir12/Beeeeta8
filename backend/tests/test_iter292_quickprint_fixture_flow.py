"""Iteration 292 - QuickPrint fixture regression checks.

Modules/features covered:
- Fixture vehicle retrieval after seeding
- Vehicle visits linkage for fixture vehicle
- Explicit template use contract for fixture template id
"""

from __future__ import annotations

import os

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

FIXTURE_VEHICLE_ID = "fixture-quickprint-vehicle-001"
FIXTURE_VISIT_ID = "fixture-quickprint-visit-001"
FIXTURE_TEMPLATE_ID = "fixture-quickprint-template-001"


@pytest.fixture(scope="module")
def api_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    if RATE_BYPASS:
        session.headers["x-ratelimit-bypass"] = RATE_BYPASS
    login = session.post(
        f"{API}/auth/login",
        json={"username": MANAGER_USERNAME, "pin": MANAGER_PIN},
        timeout=30,
    )
    if login.status_code != 200:
        pytest.skip(f"Manager login unavailable: {login.status_code} {login.text[:140]}")
    token = (login.json() or {}).get("access_token")
    if not token:
        pytest.skip("access_token missing from login response")
    session.headers.update({"Authorization": f"Bearer {token}"})
    return session


def test_fixture_vehicle_get_returns_seeded_vehicle(api_session: requests.Session):
    """Vehicle module: GET fixture vehicle id returns seeded identity fields."""
    response = api_session.get(f"{API}/vehicles/{FIXTURE_VEHICLE_ID}", timeout=30)
    assert response.status_code == 200, response.text[:220]
    data = response.json()
    assert data.get("id") == FIXTURE_VEHICLE_ID
    assert data.get("plateNumber") == "P0 2026"
    assert data.get("customerId") == "fixture-quickprint-customer-001"


def test_fixture_vehicle_visits_include_fixture_visit(api_session: requests.Session):
    """Visit module: fixture vehicle visits endpoint includes fixture visit id and linkage."""
    response = api_session.get(f"{API}/vehicles/{FIXTURE_VEHICLE_ID}/visits", timeout=30)
    assert response.status_code == 200, response.text[:220]
    rows = response.json()
    assert isinstance(rows, list)
    target = next((row for row in rows if row.get("id") == FIXTURE_VISIT_ID), None)
    assert target is not None, f"Fixture visit {FIXTURE_VISIT_ID} not found in visits list"
    assert target.get("vehicleId") == FIXTURE_VEHICLE_ID
    assert str(target.get("status") or "") == "in_progress"


def test_fixture_template_use_returns_same_template_id(api_session: requests.Session):
    """Templates module: explicit /use call keeps selected fixture template id in response."""
    response = api_session.post(
        f"{API}/document-templates/{FIXTURE_TEMPLATE_ID}/use",
        json={"document_type": "invoice", "tenant_id": "default", "locale": "ar-SA"},
        timeout=30,
    )
    assert response.status_code == 200, response.text[:260]
    data = response.json()
    template = data.get("template") or {}
    assert template.get("id") == FIXTURE_TEMPLATE_ID
    assert template.get("document_type") == "invoice"
    assert isinstance(data.get("content"), str) and len(data.get("content", "").strip()) > 0
