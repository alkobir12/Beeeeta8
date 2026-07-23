"""Iteration 288 — Final P0 closure checks for templates + outbound WhatsApp contract.

Modules/features covered:
- document-templates set-default scope uniqueness and resolve preference
- outbound resolve-message should not report missing_variables for valid phone + plate/workshop fallbacks
"""

from __future__ import annotations

import os
import uuid
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

    payload = login.json() if login.headers.get("content-type", "").startswith("application/json") else {}
    token = payload.get("access_token")
    assert token, "access_token missing from login response"
    session.headers.update({"Authorization": f"Bearer {token}"})
    return session


def _upload_html_template(session: requests.Session, html: str, name_prefix: str) -> Dict[str, Any]:
    files = {"file": (f"{name_prefix}.html", html.encode("utf-8"), "text/html")}
    data = {
        "name": f"{name_prefix}-{uuid.uuid4().hex[:6]}",
        "description": "iter288 upload",
        "document_type": "invoice",
        "tenant_id": "default",
        "locale": "ar-SA",
    }
    response = session.post(f"{API}/document-templates/upload", files=files, data=data, timeout=30)
    assert response.status_code == 200, response.text[:300]
    body = response.json()
    assert body.get("success") is True
    template = body.get("template")
    assert isinstance(template, dict)
    return template


def _archive_template(session: requests.Session, template_id: str) -> None:
    response = session.delete(f"{API}/document-templates/{template_id}", timeout=30)
    assert response.status_code in {200, 404}, response.text[:300]


def _list_templates(session: requests.Session) -> List[Dict[str, Any]]:
    response = session.get(
        f"{API}/document-templates",
        params={"tenant_id": "default", "locale": "ar-SA"},
        timeout=30,
    )
    assert response.status_code == 200, response.text[:300]
    data = response.json()
    templates = data.get("templates") if isinstance(data, dict) else None
    assert isinstance(templates, list)
    return templates


def test_set_default_scope_remains_single_active_default(auth_session: requests.Session):
    """/set-default must keep one default only for default+invoice+ar-SA scope."""
    template = _upload_html_template(
        auth_session,
        """<!doctype html><html><body><h1>{{WORKSHOP_NAME}}</h1><p>[[CUSTOMER_NAME]]</p></body></html>""",
        "ITER288_SCOPE",
    )
    try:
        set_default = auth_session.post(
            f"{API}/document-templates/{template['id']}/set-default",
            json={"tenant_id": "default", "locale": "ar-SA"},
            timeout=30,
        )
        assert set_default.status_code == 200, set_default.text[:300]
        payload = set_default.json()
        assert payload.get("success") is True
        assert payload.get("template", {}).get("is_default") is True

        templates = _list_templates(auth_session)
        default_rows = [
            row for row in templates
            if row.get("tenant_id") == "default"
            and row.get("document_type") == "invoice"
            and row.get("locale") == "ar-SA"
            and row.get("active") is True
            and row.get("status") == "valid"
            and row.get("is_default") is True
        ]
        assert len(default_rows) == 1, f"Expected one default row, got {len(default_rows)}"
        assert default_rows[0].get("id") == template.get("id")
    finally:
        _archive_template(auth_session, template["id"])


def test_resolve_message_valid_phone_has_no_missing_variables_for_plate_and_workshop(auth_session: requests.Session):
    """Valid phone path should resolve without missing_variables for workshop/plate fallbacks."""
    payload = {
        "doc_type": "invoice",
        "status": "draft",
        "payload": {
            "settings": {
                "document_number": f"ITER288-{uuid.uuid4().hex[:6]}",
                "date": "2026-02-15",
            },
            "workshop": {
                "name": "ورشة الاختبار",
            },
            "customer": {
                "name": "عميل اختبار",
                "phone": "0501234567",
            },
            "vehicle": {
                "plate": "أ ب ج 1234",
            },
            "items": [
                {"description": "فحص", "quantity": 1, "unit_price": 100}
            ],
            "payment": {"paid": 100},
        },
    }
    response = auth_session.post(f"{API}/outbound/resolve-message", json=payload, timeout=30)
    assert response.status_code == 200, response.text[:300]
    data = response.json()

    assert data.get("success") is True
    assert isinstance(data.get("message"), str) and len(data.get("message", "")) > 0

    missing = data.get("missing_variables")
    assert isinstance(missing, list)
    assert "WORKSHOP_PHONE" not in missing
    assert "VEHICLE_INFO" not in missing
    assert "PLATE_NO" not in missing

    phone = data.get("phone") or {}
    assert phone.get("valid") is True
    assert phone.get("e164") == "+966501234567"
