"""Iteration 283 final checks for P0 template registry and resolver.

Modules/features covered:
- Single active default enforcement per tenant+type+locale scope
- Explicit template use endpoint contract (/document-templates/{id}/use)
- Explicit invalid template must fail with 409 (no silent fallback)
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


def test_default_uniqueness_never_exceeds_one_per_scope(auth_session: requests.Session):
    # Module: verify backend uniqueness behavior in live listing for default tenant scope.
    rows = _list_templates(auth_session, tenant_id="default", locale="ar-SA")
    assert rows, "Expected templates list to be non-empty"

    for doc_type in {"invoice", "diagnosis", "quote", "receipt"}:
        scoped_defaults = [
            row
            for row in rows
            if row.get("tenant_id") == "default"
            and row.get("document_type") == doc_type
            and row.get("locale") == "ar-SA"
            and row.get("active") is True
            and row.get("status") == "valid"
            and row.get("is_default") is True
        ]
        assert len(scoped_defaults) <= 1, f"default scope has duplicates for {doc_type}: {len(scoped_defaults)}"


def test_quick_print_use_endpoint_returns_reason_and_content(auth_session: requests.Session):
    # Module: QuickPrint explicit /use contract.
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


def test_explicit_invalid_template_returns_409_no_fallback(auth_session: requests.Session):
    # Module: explicit invalid template should not silently fallback to another template.
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
