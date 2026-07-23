"""Iteration 290 — QuickPrint template selection/output baseline contracts.

Modules/features covered:
- auth/login baseline for manager quick PIN
- document-templates list + explicit /use by selected template id
- outbound resolve-message baseline for WhatsApp payload readiness
"""

from __future__ import annotations

import os
import uuid

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


@pytest.fixture(scope="module")
def auth_session() -> requests.Session:
    """Authenticated session using manager quick PIN."""
    session = requests.Session()
    if RATE_BYPASS:
        session.headers["x-ratelimit-bypass"] = RATE_BYPASS

    login = session.post(
        f"{API}/auth/login",
        json={"username": MANAGER_USERNAME, "pin": MANAGER_PIN},
        timeout=30,
    )
    if login.status_code != 200:
        pytest.skip(f"Manager login unavailable in preview: {login.status_code} {login.text[:120]}")

    body = login.json() if login.headers.get("content-type", "").startswith("application/json") else {}
    token = body.get("access_token")
    assert token, "access_token missing from login response"
    session.headers.update({"Authorization": f"Bearer {token}"})
    return session


def test_login_sets_cookie_security_flags(auth_session: requests.Session):
    """Auth contract: login should return secure cookie flags for browser sessions."""
    login = auth_session.post(
        f"{API}/auth/login",
        json={"username": MANAGER_USERNAME, "pin": MANAGER_PIN},
        timeout=30,
    )
    assert login.status_code == 200, login.text[:200]
    set_cookie = login.headers.get("set-cookie", "")
    lowered = set_cookie.lower()
    assert "httponly" in lowered
    assert "samesite=none" in lowered


def test_document_templates_explicit_use_returns_selected_template_content(auth_session: requests.Session):
    """Selected template id must be honored by /use endpoint."""
    list_resp = auth_session.get(f"{API}/document-templates", timeout=30)
    assert list_resp.status_code == 200, list_resp.text[:300]
    templates = list_resp.json().get("templates") if isinstance(list_resp.json(), dict) else []
    assert isinstance(templates, list)

    invoice_templates = [
        row for row in templates
        if (row.get("document_type") or row.get("type") or "invoice") == "invoice"
        and row.get("file_type") == "html"
        and row.get("status") == "valid"
        and row.get("active") is True
    ]
    if not invoice_templates:
        pytest.skip("No active valid invoice HTML templates in preview environment")

    selected = invoice_templates[0]
    use_resp = auth_session.post(
        f"{API}/document-templates/{selected['id']}/use",
        json={"document_type": "invoice", "tenant_id": "default", "locale": "ar-SA"},
        timeout=30,
    )
    assert use_resp.status_code == 200, use_resp.text[:300]
    data = use_resp.json()

    assert data.get("template", {}).get("id") == selected["id"]
    content = data.get("content") or ""
    assert isinstance(content, str) and len(content.strip()) > 0


def test_outbound_resolve_message_success_when_phone_workshop_vehicle_present(auth_session: requests.Session):
    """WhatsApp resolve baseline should succeed with valid customer/workshop/vehicle data."""
    payload = {
        "doc_type": "invoice",
        "status": "draft",
        "payload": {
            "settings": {
                "document_number": f"ITER290-{uuid.uuid4().hex[:6]}",
                "date": "2026-02-16",
            },
            "workshop": {
                "name": "ورشة الاختبار",
                "phone": "0555555555",
            },
            "customer": {
                "name": "عميل اختبار",
                "phone": "0501234567",
            },
            "vehicle": {
                "plateNumber": "أ ب ج 1234",
            },
            "items": [{"description": "فحص", "quantity": 1, "unit_price": 100}],
        },
    }

    response = auth_session.post(f"{API}/outbound/resolve-message", json=payload, timeout=30)
    assert response.status_code == 200, response.text[:300]
    data = response.json()
    assert data.get("success") is True
    assert data.get("missing_variables") == []
    phone = data.get("phone") or {}
    assert phone.get("valid") is True