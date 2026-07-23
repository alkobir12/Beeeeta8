"""P0 unified document templates: registry, resolve, set-default, and explicit-failure behavior."""

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

    token = (login.json() if login.headers.get("content-type", "").startswith("application/json") else {}).get("access_token")
    if not token:
        pytest.skip("Login succeeded but access_token is missing")

    session.headers.update({"Authorization": f"Bearer {token}"})
    return session


def _list_templates(session: requests.Session, tenant_id: str = "default", locale: str = "ar-SA") -> List[Dict[str, Any]]:
    r = session.get(f"{API}/document-templates", params={"tenant_id": tenant_id, "locale": locale}, timeout=30)
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    rows = data.get("templates") if isinstance(data, dict) else None
    assert isinstance(rows, list), f"unexpected templates payload: {type(rows)}"
    return rows


def test_list_templates_exposes_required_canonical_fields(auth_session: requests.Session):
    # Module: unified document_templates listing fields + canonical contract
    rows = _list_templates(auth_session, tenant_id="default", locale="ar-SA")
    assert len(rows) > 0, "Expected at least one template row"

    invoice_row = next((r for r in rows if r.get("document_type") == "invoice"), None)
    assert invoice_row, "Expected at least one invoice template"

    for key in ["tenant_id", "document_type", "locale", "version", "status", "active", "is_default"]:
        assert key in invoice_row, f"Missing canonical field in list response: {key}"


def test_resolve_invoice_default_returns_template_content_and_selection_reason(auth_session: requests.Session):
    # Module: resolver service for tenant/system default with explicit reason
    payload = {"tenant_id": "default", "document_type": "invoice", "locale": "ar-SA"}
    r = auth_session.post(f"{API}/document-templates/resolve", json=payload, timeout=30)
    assert r.status_code == 200, r.text[:300]

    data = r.json()
    assert isinstance(data.get("template"), dict)
    assert isinstance(data.get("content"), str) and len(data["content"]) > 100
    assert data.get("selection_reason") in {"tenant_default", "system_default"}


def test_set_default_is_enforced_backend_and_uniqueness_preserved(auth_session: requests.Session):
    # Module: backend-only set-default + one active+default per tenant/type/locale scope
    rows = _list_templates(auth_session, tenant_id="default", locale="ar-SA")
    candidates = [
        r for r in rows
        if r.get("document_type") == "invoice"
        and r.get("file_type") == "html"
        and r.get("status") == "valid"
        and r.get("active") is True
    ]
    assert candidates, "No eligible HTML valid active invoice template to set as default"

    preferred = next((r for r in candidates if r.get("tenant_id") == "default" and r.get("is_default") is True), None)
    target = preferred or next((r for r in candidates if r.get("tenant_id") == "default"), None) or candidates[0]

    r = auth_session.post(
        f"{API}/document-templates/{target['id']}/set-default",
        json={"tenant_id": "default", "locale": "ar-SA"},
        timeout=30,
    )
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    assert body.get("success") is True
    assert isinstance(body.get("template"), dict)

    fresh = _list_templates(auth_session, tenant_id="default", locale="ar-SA")
    scoped_defaults = [
        row for row in fresh
        if row.get("tenant_id") == "default"
        and row.get("document_type") == "invoice"
        and row.get("locale") == "ar-SA"
        and row.get("active") is True
        and row.get("is_default") is True
        and row.get("status") == "valid"
    ]
    assert len(scoped_defaults) == 1, f"Expected exactly one scoped default, got {len(scoped_defaults)}"


def test_explicit_invalid_template_returns_409_without_silent_fallback(auth_session: requests.Session):
    # Module: explicit template failure path must return 409, no silent fallback
    rows = _list_templates(auth_session, tenant_id="default", locale="ar-SA")
    invalid = next(
        (
            r for r in rows
            if r.get("document_type") == "invoice"
            and (
                r.get("active") is not True
                or r.get("status") != "valid"
                or r.get("file_type") != "html"
            )
        ),
        None,
    )
    if not invalid:
        pytest.skip("No invalid explicit invoice template available in shared environment")

    r = auth_session.post(
        f"{API}/document-templates/resolve",
        json={"tenant_id": "default", "document_type": "invoice", "locale": "ar-SA", "template_id": invalid["id"]},
        timeout=30,
    )
    assert r.status_code == 409, r.text[:300]
    detail = r.json().get("detail") if r.headers.get("content-type", "").startswith("application/json") else None
    if isinstance(detail, dict):
        assert detail.get("code") == "explicit_template_unavailable"
