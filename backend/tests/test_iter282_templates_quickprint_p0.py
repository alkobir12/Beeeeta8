"""Iteration 282 — P0 document template registry/resolve/use + CORS auth evidence.

Modules/features covered:
- Unified template resolve/use/default enforcement for tenant+type+locale
- Explicit invalid template must stay 409 (no silent fallback)
- Auth login CORS header evidence on preview origin
"""

from __future__ import annotations

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
RATE_BYPASS = (os.environ.get("RATE_LIMIT_BYPASS_TOKEN") or "").strip().strip('"')
PREVIEW_ORIGIN = "https://canonical-integrity.preview.emergentagent.com"


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
        pytest.skip(f"Manager login unavailable in preview: {login.status_code} {login.text[:120]}")

    body = login.json() if login.headers.get("content-type", "").startswith("application/json") else {}
    token = body.get("access_token")
    if not token:
        pytest.skip("Login succeeded but access_token missing")

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


def test_resolve_returns_template_content_with_reason(auth_session: requests.Session):
    # Module: canonical resolver contract for DocumentPrint.
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


def test_use_endpoint_returns_explicit_reason_and_content(auth_session: requests.Session):
    # Module: QuickPrint must call /document-templates/{id}/use and receive explicit reason.
    rows = _list_templates(auth_session, tenant_id="default", locale="ar-SA")
    candidate = next(
        (
            row
            for row in rows
            if row.get("document_type") == "invoice"
            and row.get("file_type") == "html"
            and row.get("status") == "valid"
            and row.get("active") is True
        ),
        None,
    )
    assert candidate, "No valid active invoice template available"

    response = auth_session.post(
        f"{API}/document-templates/{candidate['id']}/use",
        json={"document_type": "invoice", "tenant_id": "default", "locale": "ar-SA"},
        timeout=30,
    )
    assert response.status_code == 200, response.text[:300]
    data = response.json()
    assert data.get("template", {}).get("id") == candidate["id"]
    assert data.get("selection_reason") == "explicit_document_template"
    assert isinstance(data.get("content"), str) and len(data["content"]) > 100


def test_explicit_invalid_template_stays_409_no_fallback(auth_session: requests.Session):
    # Module: Explicit invalid template must fail with 409 (no silent fallback).
    rows = _list_templates(auth_session, tenant_id="default", locale="ar-SA")
    invalid = next(
        (
            row
            for row in rows
            if row.get("document_type") == "invoice"
            and (row.get("active") is not True or row.get("status") != "valid" or row.get("file_type") != "html")
        ),
        None,
    )
    if not invalid:
        pytest.skip("No invalid invoice template found in shared preview environment")

    response = auth_session.post(
        f"{API}/document-templates/resolve",
        json={"tenant_id": "default", "document_type": "invoice", "locale": "ar-SA", "template_id": invalid["id"]},
        timeout=30,
    )
    assert response.status_code == 409, response.text[:300]
    detail = response.json().get("detail") if response.headers.get("content-type", "").startswith("application/json") else {}
    assert isinstance(detail, dict)
    assert detail.get("code") == "explicit_template_unavailable"


def test_set_default_keeps_single_default_per_scope(auth_session: requests.Session):
    # Module: Set default from backend must preserve one default for tenant/type/locale.
    rows = _list_templates(auth_session, tenant_id="default", locale="ar-SA")
    candidates = [
        row
        for row in rows
        if row.get("document_type") == "invoice"
        and row.get("file_type") == "html"
        and row.get("status") == "valid"
        and row.get("active") is True
    ]
    assert candidates, "No eligible invoice template to set default"

    target = next((r for r in candidates if r.get("tenant_id") == "default"), candidates[0])
    response = auth_session.post(
        f"{API}/document-templates/{target['id']}/set-default",
        json={"tenant_id": "default", "locale": "ar-SA"},
        timeout=30,
    )
    assert response.status_code == 200, response.text[:300]
    payload = response.json()
    assert payload.get("success") is True

    fresh = _list_templates(auth_session, tenant_id="default", locale="ar-SA")
    scoped_defaults = [
        row
        for row in fresh
        if row.get("tenant_id") == "default"
        and row.get("document_type") == "invoice"
        and row.get("locale") == "ar-SA"
        and row.get("active") is True
        and row.get("status") == "valid"
        and row.get("is_default") is True
    ]
    assert len(scoped_defaults) == 1, f"Expected exactly one default; got {len(scoped_defaults)}"


def test_auth_login_cors_preview_origin_evidence_noted():
    # Module: CORS auth/login evidence for preview origin.
    headers = {"Content-Type": "application/json", "Origin": PREVIEW_ORIGIN}
    if RATE_BYPASS:
        headers["x-ratelimit-bypass"] = RATE_BYPASS

    response = requests.post(
        f"{API}/auth/login",
        json={"username": MANAGER_USERNAME, "pin": MANAGER_PIN},
        headers=headers,
        timeout=30,
    )
    assert response.status_code == 200, response.text[:200]
    allow_origin = response.headers.get("Access-Control-Allow-Origin", "")
    allow_credentials = response.headers.get("Access-Control-Allow-Credentials", "")

    # Evidence-first assertion: response must be credentialed; origin may be rewritten by preview edge.
    assert allow_credentials.lower() == "true"
    assert allow_origin in {PREVIEW_ORIGIN, "*"}
