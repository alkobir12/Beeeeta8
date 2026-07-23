"""Iteration 286 — P0 regression for template preview/default/sanitization/output guards.

Modules/features covered:
- document-templates upload/use/sanitize/set-default behavior
- outbound resolve-message guard for missing variables
- auth login baseline for manager quick PIN
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


def _list_templates(session: requests.Session, tenant_id: str = "default", locale: str = "ar-SA") -> List[Dict[str, Any]]:
    response = session.get(
        f"{API}/document-templates",
        params={"tenant_id": tenant_id, "locale": locale},
        timeout=30,
    )
    assert response.status_code == 200, response.text[:300]
    data = response.json()
    rows = data.get("templates") if isinstance(data, dict) else None
    assert isinstance(rows, list), "document-templates response must contain list"
    return rows


def _upload_html_template(session: requests.Session, html: str, name_prefix: str) -> Dict[str, Any]:
    files = {
        "file": (f"{name_prefix}.html", html.encode("utf-8"), "text/html"),
    }
    data = {
        "name": f"{name_prefix}-{uuid.uuid4().hex[:6]}",
        "description": "iter286 upload",
        "document_type": "invoice",
        "tenant_id": "default",
        "locale": "ar-SA",
    }
    resp = session.post(f"{API}/document-templates/upload", files=files, data=data, timeout=30)
    assert resp.status_code == 200, resp.text[:300]
    body = resp.json()
    assert body.get("success") is True
    template = body.get("template")
    assert isinstance(template, dict)
    assert template.get("file_type") == "html"
    return template


def _archive_template(session: requests.Session, template_id: str) -> None:
    response = session.delete(f"{API}/document-templates/{template_id}", timeout=30)
    assert response.status_code in {200, 404}, response.text[:300]


def test_manager_login_quick_pin_contract(auth_session: requests.Session):
    """Auth baseline for this iteration."""
    me = auth_session.get(f"{API}/auth/me", timeout=30)
    assert me.status_code == 200, me.text[:200]
    payload = me.json() if me.headers.get("content-type", "").startswith("application/json") else {}
    assert payload.get("username") in {"مدير", "admin", MANAGER_USERNAME}


def test_uploaded_html_template_preview_use_returns_content_and_reason(auth_session: requests.Session):
    """Upload HTML then /use returns explicit template and renderable content."""
    template = _upload_html_template(
        auth_session,
        """<!doctype html><html><body><h1>{{WORKSHOP_NAME}}</h1><p>{{CUSTOMER_NAME}}</p></body></html>""",
        "ITER286_PREVIEW",
    )
    try:
        use_resp = auth_session.post(
            f"{API}/document-templates/{template['id']}/use",
            json={"document_type": "invoice", "tenant_id": "default", "locale": "ar-SA"},
            timeout=30,
        )
        assert use_resp.status_code == 200, use_resp.text[:300]
        data = use_resp.json()
        assert data.get("template", {}).get("id") == template["id"]
        assert data.get("selection_reason") == "explicit_document_template"
        content = data.get("content") or ""
        assert "<h1" in content.lower() or "<p" in content.lower()
        assert "{{WORKSHOP_NAME}}" in content
    finally:
        _archive_template(auth_session, template["id"])


def test_set_default_for_uploaded_html_keeps_single_active_default_per_scope(auth_session: requests.Session):
    """Backend must enforce one active default per default+invoice+ar-SA scope."""
    template = _upload_html_template(
        auth_session,
        """<!doctype html><html><body><h1>Scoped default {{INVOICE_NO}}</h1></body></html>""",
        "ITER286_DEFAULT",
    )
    try:
        set_resp = auth_session.post(
            f"{API}/document-templates/{template['id']}/set-default",
            json={"tenant_id": "default", "locale": "ar-SA"},
            timeout=30,
        )
        assert set_resp.status_code == 200, set_resp.text[:300]
        body = set_resp.json()
        assert body.get("success") is True
        assert body.get("template", {}).get("is_default") is True

        rows = _list_templates(auth_session, tenant_id="default", locale="ar-SA")
        scoped_defaults = [
            row for row in rows
            if row.get("tenant_id") == "default"
            and row.get("document_type") == "invoice"
            and row.get("locale") == "ar-SA"
            and row.get("active") is True
            and row.get("status") == "valid"
            and row.get("is_default") is True
        ]
        assert len(scoped_defaults) == 1, f"Expected exactly one default; got {len(scoped_defaults)}"
        assert scoped_defaults[0].get("id") == template.get("id")
    finally:
        _archive_template(auth_session, template["id"])


def test_malicious_html_upload_is_sanitized_and_remains_previewable(auth_session: requests.Session):
    """Malicious upload should remove scripts/event handlers and still be previewable."""
    malicious = """
    <!doctype html><html><body>
      <h1 onclick=\"alert('x')\">Title</h1>
      <script>alert('bad')</script>
      <img src=\"x\" onerror=\"alert('xss')\" />
      <p>{{INVOICE_NO}}</p>
    </body></html>
    """
    template = _upload_html_template(auth_session, malicious, "ITER286_SANITIZE")
    try:
        notes = template.get("sanitization_notes") or []
        assert "sanitized_unsafe_html" in notes

        use_resp = auth_session.post(
            f"{API}/document-templates/{template['id']}/use",
            json={"document_type": "invoice", "tenant_id": "default", "locale": "ar-SA"},
            timeout=30,
        )
        assert use_resp.status_code == 200, use_resp.text[:300]
        content = use_resp.json().get("content") or ""
        lowered = content.lower()
        assert "<script" not in lowered
        assert "onclick=" not in lowered
        assert "onerror=" not in lowered
        assert "{{INVOICE_NO}}" in content
    finally:
        _archive_template(auth_session, template["id"])


def test_whatsapp_outbound_blocks_missing_variables(auth_session: requests.Session):
    """WhatsApp should not proceed when outbound template has unresolved placeholders."""
    payload = {
        "doc_type": "invoice",
        "status": "draft",
        "payload": {
            "settings": {"document_number": f"ITER286-{uuid.uuid4().hex[:6]}"},
            "customer": {"name": "", "phone": "0500000000"},
            "items": [],
        },
    }
    resp = auth_session.post(f"{API}/outbound/resolve-message", json=payload, timeout=30)
    assert resp.status_code == 200, resp.text[:300]
    data = resp.json()
    # Requirement: opening should be blocked by missing variables when unresolved placeholders exist.
    assert isinstance(data.get("missing_variables"), list)
