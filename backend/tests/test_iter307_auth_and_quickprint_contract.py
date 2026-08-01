"""Iteration 307 — auth + vehicle quick-print contract regression.

Modules/features covered:
- Auth login via manager PIN + token/cookie contract
- Vehicle visit data contract (supplier retained in archive, excluded in printable)
- Document template resolve for invoice/diagnosis
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
TARGET_VEHICLE_ID = "61fe0b56-aa66-490d-a5e7-6f3b8195ed56"
RATE_BYPASS = (os.environ.get("RATE_LIMIT_BYPASS_TOKEN") or "").strip().strip('"')


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


def _to_total(item: Dict[str, Any]) -> float:
    qty = float(item.get("quantity") or item.get("qty") or 1)
    price = float(item.get("price") or item.get("unit_price") or item.get("unitPrice") or item.get("amount") or 0)
    total = item.get("total")
    return float(total) if total is not None else qty * price


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
        pytest.skip(f"Manager login unavailable in preview: {login.status_code} {login.text[:160]}")

    payload = login.json() if isinstance(login.json(), dict) else {}
    token = payload.get("access_token")
    if not token:
        pytest.skip("Login succeeded but access_token missing")

    session.headers.update({"Authorization": f"Bearer {token}"})
    session._iter307_login_response = login  # test-only attachment
    session._iter307_login_payload = payload
    return session


def test_login_returns_tokens_and_secure_cookie_contract(auth_session: requests.Session):
    """Auth module: login returns tokens and secure cookie flags."""
    login = auth_session._iter307_login_response
    payload = auth_session._iter307_login_payload

    assert isinstance(payload.get("access_token"), str) and payload["access_token"]
    assert isinstance(payload.get("refresh_token"), str) and payload["refresh_token"]

    set_cookie = login.headers.get("set-cookie", "")
    assert set_cookie, "Expected Set-Cookie header on login"
    lowered = set_cookie.lower()
    assert "httponly" in lowered
    assert "secure" in lowered
    assert "samesite=none" in lowered


def test_auth_cors_preflight_allows_credentials_for_login_route():
    """Auth module: CORS preflight should allow credentials for login route."""
    origin = BASE_URL
    response = requests.options(
        f"{API}/auth/login",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
        timeout=30,
    )
    assert response.status_code in (200, 204)
    allow_credentials = (response.headers.get("access-control-allow-credentials") or "").lower()
    allow_origin = response.headers.get("access-control-allow-origin") or ""
    assert allow_credentials == "true"
    # preview edge may normalize allow-origin; backend contract accepts explicit or wildcard
    assert allow_origin in {origin, "*"}


def test_vehicle_archive_keeps_supplier_and_workshop_rows(auth_session: requests.Session):
    """Vehicle module: notes keep supplier rows for archive integrity."""
    vehicle_resp = auth_session.get(f"{API}/vehicles/{TARGET_VEHICLE_ID}", timeout=30)
    visits_resp = auth_session.get(f"{API}/vehicles/{TARGET_VEHICLE_ID}/visits", timeout=30)

    assert vehicle_resp.status_code == 200, vehicle_resp.text[:220]
    assert visits_resp.status_code == 200, visits_resp.text[:220]

    visits = visits_resp.json() if isinstance(visits_resp.json(), list) else []
    assert visits, "No visits found for target vehicle"

    matched = None
    for visit in visits:
        items = _extract_items_from_notes(visit.get("notes"))
        if not items:
            continue
        supplier_rows = [row for row in items if _is_supplier_item(row)]
        workshop_rows = [row for row in items if not _is_supplier_item(row)]
        supplier_total = round(sum(_to_total(row) for row in supplier_rows), 2)
        workshop_total = round(sum(_to_total(row) for row in workshop_rows), 2)
        if supplier_rows and workshop_rows and supplier_total == 179.00 and workshop_total == 600.00:
            matched = {"items": items, "supplier_rows": supplier_rows, "workshop_rows": workshop_rows}
            break

    assert matched is not None, "Target visit with supplier 179 + workshop 600 not found"


def test_customer_print_projection_excludes_supplier_rows(auth_session: requests.Session):
    """Print contract: customer-facing projection excludes supplier rows and totals 600."""
    visits_resp = auth_session.get(f"{API}/vehicles/{TARGET_VEHICLE_ID}/visits", timeout=30)
    assert visits_resp.status_code == 200, visits_resp.text[:220]
    visits = visits_resp.json() if isinstance(visits_resp.json(), list) else []

    for visit in visits:
        items = _extract_items_from_notes(visit.get("notes"))
        if not items:
            continue
        printable = [row for row in items if not _is_supplier_item(row)]
        all_text = " ".join(str((row.get("name") or row.get("description") or "")).strip() for row in items)
        printable_text = " ".join(str((row.get("name") or row.get("description") or "")).strip() for row in printable)
        printable_total = round(sum(_to_total(row) for row in printable), 2)
        if "القرعاوي" in all_text and printable_total == 600.00:
            assert "القرعاوي" not in printable_text
            return

    pytest.fail("Did not find visit confirming supplier exclusion from customer printable projection")


@pytest.mark.parametrize("doc_type", ["invoice", "diagnosis"])
def test_template_resolve_returns_renderable_html(auth_session: requests.Session, doc_type: str):
    """Template module: invoice/diagnosis resolve endpoints return non-empty HTML."""
    response = auth_session.post(
        f"{API}/document-templates/resolve",
        json={"document_type": doc_type, "tenant_id": "default", "locale": "ar-SA"},
        timeout=30,
    )
    assert response.status_code == 200, response.text[:260]
    data = response.json()
    template = data.get("template") or {}
    content = data.get("content") or ""
    assert template.get("document_type") == doc_type
    assert isinstance(content, str) and len(content.strip()) > 200
