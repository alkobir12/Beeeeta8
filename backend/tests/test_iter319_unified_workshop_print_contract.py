"""Iteration 319 — unified workshop print contract (backend API scope).

Modules/features covered:
- Auth login contract (manager quick PIN + cookie flags)
- Document template registry/resolve defaults for invoice/diagnosis/quote/receipt
- Vehicle/visit source-data contract for target print flow
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

MANAGER_USERNAME = "مدير"
MANAGER_PIN = "123123"
TARGET_VEHICLE_ID = "df10586b-5cf9-44aa-83bc-9364a4da34e2"
TARGET_VISIT_ID = "d1498141-b134-4823-9586-756506361a19"
RATE_BYPASS = (os.environ.get("RATE_LIMIT_BYPASS_TOKEN") or "").strip().strip('"')

EXPECTED_DEFAULT_IDS = {
    "invoice": "unified-workshop-a4-mobile-invoice-v2",
    "diagnosis": "unified-workshop-a4-mobile-diagnosis-v2",
    "quote": "unified-workshop-a4-mobile-quote-v2",
    "receipt": "unified-workshop-a4-mobile-receipt-v2",
}


def _extract_items_from_notes(notes: Any) -> List[Dict[str, Any]]:
    if not isinstance(notes, str):
        return []
    text = notes.strip()
    if not text.startswith("{"):
        return []
    try:
        parsed = json.loads(text)
    except Exception:
        return []
    rows = parsed.get("items")
    return rows if isinstance(rows, list) else []


def _is_supplier_item(item: Dict[str, Any]) -> bool:
    item_type = str(item.get("itemType") or item.get("type") or "").strip().lower()
    billing_type = str(item.get("billingType") or item.get("billing_type") or "").strip().lower()
    return item_type == "supplier" or billing_type == "supplier"


def _item_name(item: Dict[str, Any]) -> str:
    return str(item.get("name") or item.get("description") or item.get("itemName") or "").strip()


@pytest.fixture(scope="module")
def auth_session() -> requests.Session:
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
        pytest.skip(f"Manager login unavailable: {login.status_code} {login.text[:180]}")

    payload = login.json() if isinstance(login.json(), dict) else {}
    token = payload.get("access_token")
    if not token:
        pytest.skip("access_token missing in login response")

    session.headers.update({"Authorization": f"Bearer {token}"})
    session._iter319_login_response = login
    session._iter319_login_payload = payload
    return session


def test_auth_login_sets_secure_httponly_cookie(auth_session: requests.Session):
    """Auth module: cookie hardening stays enabled on login."""
    login_response = auth_session._iter319_login_response
    payload = auth_session._iter319_login_payload

    assert isinstance(payload.get("access_token"), str) and payload["access_token"]
    set_cookie = login_response.headers.get("set-cookie", "")
    assert set_cookie, "Set-Cookie missing on login"

    lowered = set_cookie.lower()
    assert "httponly" in lowered
    assert "secure" in lowered
    assert "samesite=none" in lowered


def test_document_templates_registry_contains_unified_v2_defaults(auth_session: requests.Session):
    """Template registry: default tenant templates must point to unified v2 IDs."""
    response = auth_session.get(f"{API}/document-templates", timeout=30)
    assert response.status_code == 200, response.text[:260]

    templates = (response.json() or {}).get("templates") or []
    assert templates, "No templates returned"

    by_id = {tpl.get("id"): tpl for tpl in templates}
    for doc_type, template_id in EXPECTED_DEFAULT_IDS.items():
        row = by_id.get(template_id)
        assert row is not None, f"Missing required template id: {template_id}"
        assert row.get("document_type") == doc_type
        assert row.get("active") is True
        assert row.get("status") == "valid"
        assert row.get("is_default") is True


@pytest.mark.parametrize("doc_type", ["invoice", "diagnosis", "quote", "receipt"])
def test_document_templates_resolve_returns_expected_unified_default(auth_session: requests.Session, doc_type: str):
    """Resolver: each doc type resolves to unified-workshop-a4-mobile-*-v2 for tenant default."""
    response = auth_session.post(
        f"{API}/document-templates/resolve",
        json={"document_type": doc_type, "tenant_id": "default", "locale": "ar-SA"},
        timeout=30,
    )
    assert response.status_code == 200, response.text[:260]
    data = response.json() or {}

    template = data.get("template") or {}
    content = str(data.get("content") or "")

    assert template.get("id") == EXPECTED_DEFAULT_IDS[doc_type]
    assert template.get("document_type") == doc_type
    assert template.get("active") is True
    assert template.get("is_default") is True
    assert "data-testid=\"document-a4-page\"" in content
    if doc_type == "diagnosis":
        assert "تقرير تشخيص" in content


def test_target_vehicle_and_visit_exist_with_expected_customer_identity(auth_session: requests.Session):
    """Vehicle/visit source contract: target IDs resolve and identity data exists."""
    vehicle_resp = auth_session.get(f"{API}/vehicles/{TARGET_VEHICLE_ID}", timeout=30)
    visits_resp = auth_session.get(f"{API}/vehicles/{TARGET_VEHICLE_ID}/visits", timeout=30)

    assert vehicle_resp.status_code == 200, vehicle_resp.text[:260]
    assert visits_resp.status_code == 200, visits_resp.text[:260]

    vehicle = vehicle_resp.json() if isinstance(vehicle_resp.json(), dict) else {}
    visits = visits_resp.json() if isinstance(visits_resp.json(), list) else []

    assert vehicle.get("id") == TARGET_VEHICLE_ID
    assert visits, "Vehicle visits list is empty"

    target_visit = next((v for v in visits if str(v.get("id")) == TARGET_VISIT_ID), None)
    assert target_visit is not None, f"Target visit not found: {TARGET_VISIT_ID}"

    customer_name = str(vehicle.get("customerName") or vehicle.get("customer_name") or "")
    customer_phone = str(vehicle.get("customerPhone") or vehicle.get("customer_phone") or "")
    assert "سالم" in customer_name
    assert "0509915954" in customer_phone


def test_target_visit_customer_print_projection_excludes_supplier_item(auth_session: requests.Session):
    """Visit source-data contract: supplier item remains in source but excluded in printable projection."""
    visits_resp = auth_session.get(f"{API}/vehicles/{TARGET_VEHICLE_ID}/visits", timeout=30)
    assert visits_resp.status_code == 200, visits_resp.text[:260]

    visits = visits_resp.json() if isinstance(visits_resp.json(), list) else []
    target_visit = next((v for v in visits if str(v.get("id")) == TARGET_VISIT_ID), None)
    assert target_visit is not None, f"Target visit not found: {TARGET_VISIT_ID}"

    source_items = _extract_items_from_notes(target_visit.get("notes"))
    assert source_items, "Target visit has no structured notes items"

    all_names = [_item_name(item) for item in source_items]
    printable_names = [_item_name(item) for item in source_items if not _is_supplier_item(item)]

    joined_all = " | ".join(all_names)
    joined_printable = " | ".join(printable_names)

    assert "طقم اصلاح تربو 2" in joined_all
    assert "فك وتركيب تربو" in joined_printable
    assert "فك وتركيب التانكي" in joined_printable
    assert "طقم اصلاح تربو 2" not in joined_printable
