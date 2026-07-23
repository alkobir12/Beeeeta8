"""Iteration 284 — Template completeness guard and event logging checks.

Modules/features covered:
- /api/document-templates/events records template_incomplete/load_failed/render_failed
- Uploaded incomplete template remains selectable (frontend must block render/PDF)
- System template resolve contract remains healthy
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient


load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"
API = f"{BASE_URL}/api"

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")

MANAGER_USERNAME = "مدير"
MANAGER_PIN = "123123"
RATE_BYPASS = (os.environ.get("RATE_LIMIT_BYPASS_TOKEN") or "").strip().strip('"')


@pytest.fixture(scope="module")
def auth_session() -> requests.Session:
    # Module: authenticated API session for document-template endpoints.
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
        pytest.skip(f"Manager login unavailable in preview: {login.status_code} {login.text[:120]}")

    body = login.json() if login.headers.get("content-type", "").startswith("application/json") else {}
    token = body.get("access_token")
    if not token:
        pytest.skip("Login succeeded but access_token missing")

    session.headers.update({"Authorization": f"Bearer {token}"})
    return session


@pytest.fixture(scope="module")
def mongo_collection():
    # Module: read-back verification for persisted template events in Mongo audit collection.
    if not MONGO_URL or not DB_NAME:
        pytest.skip("MONGO_URL or DB_NAME missing; cannot verify event persistence")
    client = MongoClient(MONGO_URL)
    collection = client[DB_NAME]["document_template_resolution_audit"]
    try:
        yield collection
    finally:
        client.close()


@pytest.fixture(scope="module")
def uploaded_incomplete_template(auth_session: requests.Session) -> Dict[str, Any]:
    # Module: upload an HTML template containing unresolved placeholders for UI guard testing.
    name = f"ITER284_INCOMPLETE_{int(time.time())}"
    html = """
<!doctype html>
<html lang="ar" dir="rtl"><head><meta charset="utf-8" /><title>Incomplete</title></head>
<body>
  <h1>مستند اختبار ناقص</h1>
  <p>العميل: {CUSTOMER_NAME}</p>
  <p>الإجمالي: [[TOTAL]]</p>
  <p>رقم الفاتورة: <%= INVOICE_NO %></p>
</body></html>
""".strip()

    files = {"file": (f"{name}.html", html.encode("utf-8"), "text/html")}
    data = {
        "name": name,
        "description": "ITER284 incomplete placeholders template",
        "document_type": "invoice",
        "tenant_id": "default",
        "locale": "ar-SA",
    }
    # Multipart upload requires removing JSON content-type inherited from session defaults.
    previous_content_type = auth_session.headers.pop("Content-Type", None)
    try:
        response = auth_session.post(f"{API}/document-templates/upload", files=files, data=data, timeout=30)
    finally:
        if previous_content_type:
            auth_session.headers["Content-Type"] = previous_content_type
    assert response.status_code == 200, response.text[:300]
    payload = response.json()
    template = payload.get("template") or {}
    assert template.get("id")
    assert template.get("name") == name
    assert template.get("file_type") == "html"

    yield template

    # Cleanup uploaded template to avoid polluting shared preview environment.
    auth_session.delete(f"{API}/document-templates/{template['id']}", timeout=30)


def test_resolve_system_template_contract_is_still_healthy(auth_session: requests.Session):
    # Module: regression check — valid system/default template still resolves normally.
    response = auth_session.post(
        f"{API}/document-templates/resolve",
        json={"tenant_id": "default", "document_type": "invoice", "locale": "ar-SA"},
        timeout=30,
    )
    assert response.status_code == 200, response.text[:300]
    data = response.json()
    assert isinstance(data.get("template"), dict)
    assert isinstance(data.get("content"), str) and len(data["content"]) > 100
    assert data.get("selection_reason") in {"tenant_default", "system_default", "explicit_document_template"}


@pytest.mark.parametrize(
    "event_name,reason,missing_variables",
    [
        ("template_incomplete", "iter284_incomplete_guard", ["CUSTOMER_NAME", "TOTAL", "INVOICE_NO"]),
        ("template_load_failed", "iter284_load_failure", []),
        ("template_render_failed", "iter284_render_failure", []),
    ],
)
def test_events_endpoint_persists_supported_events(
    auth_session: requests.Session,
    mongo_collection,
    uploaded_incomplete_template: Dict[str, Any],
    event_name: str,
    reason: str,
    missing_variables: list[str],
):
    # Module: verify /events accepts supported events and persists fields for audit.
    response = auth_session.post(
        f"{API}/document-templates/events",
        json={
            "event": event_name,
            "template_id": uploaded_incomplete_template["id"],
            "document_type": "invoice",
            "missing_variables": missing_variables,
            "reason": reason,
            "tenant_id": "default",
            "locale": "ar-SA",
        },
        timeout=30,
    )
    assert response.status_code == 200, response.text[:300]
    body = response.json()
    assert body.get("success") is True
    event_id = body.get("event_id")
    assert isinstance(event_id, str) and len(event_id) > 10

    saved = mongo_collection.find_one({"id": event_id})
    assert isinstance(saved, dict), "Event row not found in Mongo audit collection"
    assert saved.get("event") == event_name
    assert saved.get("template_id") == uploaded_incomplete_template["id"]
    assert saved.get("document_type") == "invoice"
    if event_name == "template_incomplete":
        assert set(saved.get("missing_variables") or []) >= {"CUSTOMER_NAME", "TOTAL", "INVOICE_NO"}


def test_events_endpoint_rejects_unsupported_event(auth_session: requests.Session):
    # Module: validate backend guard for unsupported event names.
    response = auth_session.post(
        f"{API}/document-templates/events",
        json={"event": "unknown_event", "template_id": "x", "document_type": "invoice"},
        timeout=30,
    )
    assert response.status_code == 422, response.text[:300]
    detail = response.json().get("detail") if response.headers.get("content-type", "").startswith("application/json") else {}
    assert isinstance(detail, dict)
    assert detail.get("code") == "unsupported_template_event"


def test_uploaded_incomplete_template_is_resolvable_for_frontend_guard(
    auth_session: requests.Session,
    uploaded_incomplete_template: Dict[str, Any],
):
    # Module: backend returns uploaded HTML as-is; frontend guard must stop unresolved placeholders.
    response = auth_session.post(
        f"{API}/document-templates/{uploaded_incomplete_template['id']}/use",
        json={"document_type": "invoice", "tenant_id": "default", "locale": "ar-SA"},
        timeout=30,
    )
    assert response.status_code == 200, response.text[:300]
    data = response.json()
    content = data.get("content") or ""
    assert "{CUSTOMER_NAME}" in content
    assert "[[TOTAL]]" in content
    assert "<%= INVOICE_NO %>" in content
