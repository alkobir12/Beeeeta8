"""Iteration 287 — P0 retest for template manager + unified output channels.

Modules/features covered:
- document-templates default/resolve/use contracts for invoice scope
- set-default guard for unknown placeholders (missing_variables contract)
- outbound WhatsApp resolve-message missing_variables contract
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
TARGET_TEMPLATE_ID = "3666c919-4cd3-4ee3-91ef-dff5cfd5bf41"
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

    data = login.json() if login.headers.get("content-type", "").startswith("application/json") else {}
    token = data.get("access_token")
    assert token, "access_token missing from login response"
    session.headers.update({"Authorization": f"Bearer {token}"})
    return session


def _list_templates(session: requests.Session, tenant_id: str = "default", locale: str = "ar-SA") -> List[Dict[str, Any]]:
    response = session.get(
        f"{API}/document-templates",
        params={"tenant_id": tenant_id, "locale": locale},
        timeout=30,
    )
    assert response.status_code == 200, response.text[:300]
    body = response.json()
    rows = body.get("templates") if isinstance(body, dict) else None
    assert isinstance(rows, list)
    return rows


def _upload_html_template(session: requests.Session, html: str, name_prefix: str) -> Dict[str, Any]:
    files = {"file": (f"{name_prefix}.html", html.encode("utf-8"), "text/html")}
    data = {
        "name": f"{name_prefix}-{uuid.uuid4().hex[:6]}",
        "description": "iter287 upload",
        "document_type": "invoice",
        "tenant_id": "default",
        "locale": "ar-SA",
    }
    response = session.post(f"{API}/document-templates/upload", files=files, data=data, timeout=30)
    assert response.status_code == 200, response.text[:300]
    payload = response.json()
    assert payload.get("success") is True
    template = payload.get("template")
    assert isinstance(template, dict)
    return template


def _archive_template(session: requests.Session, template_id: str) -> None:
    response = session.delete(f"{API}/document-templates/{template_id}", timeout=30)
    assert response.status_code in {200, 404}, response.text[:300]


def test_template_3666_use_returns_renderable_html(auth_session: requests.Session):
    """Requested template id must be usable via /use with explicit selection reason."""
    response = auth_session.post(
        f"{API}/document-templates/{TARGET_TEMPLATE_ID}/use",
        json={"tenant_id": "default", "document_type": "invoice", "locale": "ar-SA"},
        timeout=30,
    )
    assert response.status_code == 200, response.text[:300]
    data = response.json()
    assert data.get("template", {}).get("id") == TARGET_TEMPLATE_ID
    assert data.get("selection_reason") == "explicit_document_template"
    content = data.get("content") or ""
    assert isinstance(content, str) and len(content) > 100
    assert "<" in content and ">" in content


def test_template_3666_is_default_for_default_invoice_scope(auth_session: requests.Session):
    """P0 requirement: template 3666... should be the effective tenant default for invoice."""
    rows = _list_templates(auth_session, tenant_id="default", locale="ar-SA")
    scoped_defaults = [
        row
        for row in rows
        if row.get("tenant_id") == "default"
        and row.get("document_type") == "invoice"
        and row.get("locale") == "ar-SA"
        and row.get("active") is True
        and row.get("status") == "valid"
        and row.get("is_default") is True
    ]
    assert len(scoped_defaults) == 1, f"Expected exactly one default for default/invoice/ar-SA; got {len(scoped_defaults)}"
    assert scoped_defaults[0].get("id") == TARGET_TEMPLATE_ID


def test_resolve_prefers_tenant_default_when_system_default_also_exists(auth_session: requests.Session):
    """Resolve must pick tenant default (not system) when both exist."""
    response = auth_session.post(
        f"{API}/document-templates/resolve",
        json={"tenant_id": "default", "document_type": "invoice", "locale": "ar-SA"},
        timeout=30,
    )
    assert response.status_code == 200, response.text[:300]
    data = response.json()
    assert data.get("selection_reason") == "tenant_default"
    assert data.get("template", {}).get("tenant_id") == "default"


def test_set_default_rejects_unknown_placeholders_with_missing_variables(auth_session: requests.Session):
    """QuickPrint guard source: set-default must block unknown placeholders and return missing_variables."""
    template = _upload_html_template(
        auth_session,
        """<!doctype html><html><body><h1>{{WORKSHOP_NAME}}</h1><p>{{UNSAFE_UNKNOWN_VAR}}</p></body></html>""",
        "ITER287_GUARD",
    )
    try:
        response = auth_session.post(
            f"{API}/document-templates/{template['id']}/set-default",
            json={"tenant_id": "default", "locale": "ar-SA"},
            timeout=30,
        )
        assert response.status_code == 409, response.text[:300]
        detail = response.json().get("detail")
        assert isinstance(detail, dict)
        assert detail.get("code") == "template_incomplete"
        missing = detail.get("missing_variables") or []
        assert "UNSAFE_UNKNOWN_VAR" in missing
        message = detail.get("message") or ""
        assert "المتغيرات" in message or "المعروفة" in message
    finally:
        _archive_template(auth_session, template["id"])


def test_outbound_resolve_message_reports_missing_variables(auth_session: requests.Session):
    """WhatsApp flow should surface missing_variables contract for unresolved message variables."""
    payload = {
        "doc_type": "invoice",
        "status": "draft",
        "payload": {
            "settings": {"document_number": f"ITER287-{uuid.uuid4().hex[:6]}"},
            "customer": {"name": "", "phone": ""},
            "items": [],
        },
    }
    response = auth_session.post(f"{API}/outbound/resolve-message", json=payload, timeout=30)
    assert response.status_code == 200, response.text[:300]
    data = response.json()
    assert isinstance(data.get("missing_variables"), list)
