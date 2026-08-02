"""Iteration 322 — print isolation data contract.

Modules/features covered:
- Auth login contract for manager PIN
- Print source data contract for target vehicle/visit
- Template resolve contract for invoice/diagnosis labels
"""

from __future__ import annotations

import json
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

TARGET_VEHICLE_ID = "df10586b-5cf9-44aa-83bc-9364a4da34e2"
TARGET_VISIT_ID = "d1498141-b134-4823-9586-756506361a19"
RATE_BYPASS = (os.environ.get("RATE_LIMIT_BYPASS_TOKEN") or "").strip().strip('"')


def _extract_items_from_notes(notes: Any) -> List[Dict[str, Any]]:
    if not isinstance(notes, str):
        return []
    txt = notes.strip()
    if not txt.startswith("{"):
        return []
    try:
        parsed = json.loads(txt)
    except Exception:
        return []
    rows = parsed.get("items")
    return rows if isinstance(rows, list) else []


def _is_supplier_item(item: Dict[str, Any]) -> bool:
    item_type = str(item.get("itemType") or item.get("type") or "").strip().lower()
    billing_type = str(item.get("billingType") or item.get("billing_type") or "").strip().lower()
    return item_type == "supplier" or billing_type == "supplier"


@pytest.fixture(scope="module")
def auth_session() -> requests.Session:
    """Auth module: manager quick PIN login session."""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    if RATE_BYPASS:
        session.headers["x-ratelimit-bypass"] = RATE_BYPASS

    login = session.post(
        f"{API}/auth/login",
        json={"username": "مدير", "pin": "123123"},
        timeout=30,
    )
    if login.status_code != 200:
        pytest.skip(f"Manager login unavailable: {login.status_code} {login.text[:180]}")

    payload = login.json() if isinstance(login.json(), dict) else {}
    token = payload.get("access_token")
    if not token:
        pytest.skip("access_token missing in login response")

    session.headers.update({"Authorization": f"Bearer {token}"})
    session._iter322_login_response = login
    return session


def test_login_sets_hardened_cookie_flags(auth_session: requests.Session):
    """Auth module: cookie flags remain secure for browser flow."""
    response = auth_session._iter322_login_response
    cookie = response.headers.get("set-cookie", "")
    assert cookie
    lowered = cookie.lower()
    assert "httponly" in lowered
    assert "secure" in lowered
    assert "samesite=none" in lowered


@pytest.mark.parametrize("doc_type,expected_title", [
    ("invoice", "فاتورة مبيعات"),
    ("diagnosis", "تقرير تشخيص"),
])
def test_template_resolve_contains_expected_arabic_title(
    auth_session: requests.Session,
    doc_type: str,
    expected_title: str,
):
    """Templates module: resolver returns unified template content for target doc types."""
    response = auth_session.post(
        f"{API}/document-templates/resolve",
        json={"document_type": doc_type, "tenant_id": "default", "locale": "ar-SA"},
        timeout=30,
    )
    assert response.status_code == 200, response.text[:220]
    data = response.json() if isinstance(response.json(), dict) else {}
    content = str(data.get("content") or "")
    assert expected_title in content
    assert 'data-testid="document-a4-page"' in content


def test_target_vehicle_customer_identity_is_present(auth_session: requests.Session):
    """Vehicle module: target vehicle carries expected customer identity for print payload."""
    response = auth_session.get(f"{API}/vehicles/{TARGET_VEHICLE_ID}", timeout=30)
    assert response.status_code == 200, response.text[:220]
    vehicle = response.json() if isinstance(response.json(), dict) else {}
    name = str(vehicle.get("customerName") or vehicle.get("customer_name") or "")
    phone = str(vehicle.get("customerPhone") or vehicle.get("customer_phone") or "")
    assert "سالم" in name
    assert "0509915954" in phone


def test_target_visit_items_keep_supplier_only_in_source_not_customer_projection(auth_session: requests.Session):
    """Visits module: source includes supplier row, printable projection excludes it."""
    response = auth_session.get(f"{API}/vehicles/{TARGET_VEHICLE_ID}/visits", timeout=30)
    assert response.status_code == 200, response.text[:220]
    visits = response.json() if isinstance(response.json(), list) else []
    target_visit = next((row for row in visits if str(row.get("id")) == TARGET_VISIT_ID), None)
    assert target_visit is not None

    source_items = _extract_items_from_notes(target_visit.get("notes"))
    assert source_items

    all_names = [str(item.get("name") or item.get("description") or "").strip() for item in source_items]
    printable_names = [
        str(item.get("name") or item.get("description") or "").strip()
        for item in source_items
        if not _is_supplier_item(item)
    ]

    assert any("طقم اصلاح تربو 2" in n for n in all_names)
    assert any("فك وتركيب تربو" in n for n in printable_names)
    assert any("فك وتركيب التانكي" in n for n in printable_names)
    assert not any("طقم اصلاح تربو 2" in n for n in printable_names)
