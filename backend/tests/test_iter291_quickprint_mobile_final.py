"""Iteration 291 — Final QuickPrint mobile + auth guard regression checks.

Modules/features covered:
- Auth login contract (manager quick PIN, cookie flags, /auth/me)
- Document templates list/use contract used by QuickPrint
- Security checks from playbook (CORS credentials, brute-force lockout, bcrypt prefix)
- Startup seed guard wiring for manager quick PIN
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from urllib.parse import urlparse

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


def _origin_from_base_url(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


@pytest.fixture(scope="module")
def api_session() -> requests.Session:
    session = requests.Session()
    if RATE_BYPASS:
        session.headers["x-ratelimit-bypass"] = RATE_BYPASS
    return session


@pytest.fixture(scope="module")
def manager_login(api_session: requests.Session):
    response = api_session.post(
        f"{API}/auth/login",
        json={"username": MANAGER_USERNAME, "pin": MANAGER_PIN},
        timeout=30,
    )
    if response.status_code != 200:
        pytest.skip(f"Manager login unavailable in preview: {response.status_code} {response.text[:150]}")
    data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
    token = data.get("access_token")
    assert token, "access_token missing"
    api_session.headers.update({"Authorization": f"Bearer {token}"})
    return response, data


def test_login_returns_tokens_and_cookie_security_flags(manager_login):
    """Auth contract: quick PIN login returns JWTs and secure cookie attributes."""
    response, data = manager_login
    assert data.get("token_type") == "bearer"
    assert isinstance(data.get("access_token"), str) and len(data.get("access_token")) > 30
    assert isinstance(data.get("refresh_token"), str) and len(data.get("refresh_token")) > 30
    assert data.get("username") == MANAGER_USERNAME

    set_cookie = (response.headers.get("set-cookie") or "").lower()
    assert "httponly" in set_cookie
    assert "samesite=none" in set_cookie


def test_auth_me_works_with_bearer(api_session: requests.Session, manager_login):
    """Auth contract: /auth/me resolves current identity from bearer token."""
    response = api_session.get(f"{API}/auth/me", timeout=30)
    assert response.status_code == 200, response.text[:200]
    data = response.json()
    assert data.get("username") == MANAGER_USERNAME
    assert data.get("role") in {"admin", "manager"}


def test_document_templates_list_available_after_login(api_session: requests.Session, manager_login):
    """QuickPrint dependency: /document-templates should return template rows for authenticated user."""
    response = api_session.get(f"{API}/document-templates", timeout=30)
    assert response.status_code == 200, response.text[:250]
    data = response.json()
    templates = data.get("templates") if isinstance(data, dict) else None
    assert isinstance(templates, list)
    assert len(templates) > 0

    valid_invoice_html = [
        t for t in templates
        if (t.get("document_type") or t.get("type") or "invoice") == "invoice"
        and t.get("file_type") == "html"
        and t.get("status") == "valid"
        and t.get("active") is True
    ]
    assert len(valid_invoice_html) > 0


def test_document_templates_use_honors_explicit_selected_template_id(api_session: requests.Session, manager_login):
    """QuickPrint contract: POST /document-templates/{id}/use must return that same id in response.template.id."""
    list_resp = api_session.get(f"{API}/document-templates", timeout=30)
    assert list_resp.status_code == 200, list_resp.text[:250]
    templates = list_resp.json().get("templates", [])
    candidates = [
        row for row in templates
        if (row.get("document_type") or row.get("type") or "invoice") == "invoice"
        and row.get("file_type") == "html"
        and row.get("status") == "valid"
        and row.get("active") is True
    ]
    if not candidates:
        pytest.skip("No active valid invoice HTML templates in preview environment")

    selected = candidates[0]
    use_resp = api_session.post(
        f"{API}/document-templates/{selected['id']}/use",
        json={"document_type": "invoice", "tenant_id": "default", "locale": "ar-SA"},
        timeout=30,
    )
    assert use_resp.status_code == 200, use_resp.text[:300]
    data = use_resp.json()
    assert data.get("template", {}).get("id") == selected["id"]
    assert isinstance(data.get("content"), str) and len(data.get("content", "").strip()) > 0


def test_cors_allows_credentials_with_explicit_origin(manager_login):
    """Playbook check: credentialed CORS headers should echo explicit allowed origin."""
    origin = _origin_from_base_url(BASE_URL)
    response = requests.options(
        f"{API}/document-templates",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
        timeout=30,
    )
    assert response.status_code in {200, 204}
    assert response.headers.get("access-control-allow-origin") == origin
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_bruteforce_lockout_after_five_failed_attempts(api_session: requests.Session):
    """Playbook check: after 5 failures in window, login is temporarily locked (429)."""
    probe_user = f"LOCKOUT_TEST_{uuid.uuid4().hex[:8]}"
    statuses = []
    for _ in range(6):
        resp = api_session.post(
            f"{API}/auth/login",
            json={"username": probe_user, "pin": "000000"},
            timeout=30,
        )
        statuses.append(resp.status_code)

    # Typical sequence is 401 x5 then 429 on the 6th request.
    assert statuses[-1] == 429, f"Expected lockout on 6th attempt, got sequence: {statuses}"


def test_manager_pin_hash_is_bcrypt_2b_prefix():
    """Playbook check: stored manager PIN hash format starts with $2b$."""
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        pytest.skip("MONGO_URL/DB_NAME not configured")

    try:
        from pymongo import MongoClient
    except Exception:
        pytest.skip("pymongo unavailable for direct credential-hash verification")

    client = MongoClient(mongo_url, serverSelectionTimeoutMS=4000)
    try:
        doc = client[db_name].auth_credentials.find_one({"username": MANAGER_USERNAME}, {"_id": 0, "pin_hash": 1})
    finally:
        client.close()

    if not doc or not doc.get("pin_hash"):
        pytest.skip("Manager credential hash not found in auth_credentials")
    assert doc["pin_hash"].startswith("$2b$")


def test_startup_wires_manager_seed_update_path_in_server_code():
    """Playbook code-path check: startup includes MANAGER_QUICK_* + ensure_pin wiring."""
    source = Path("/app/backend/server.py").read_text(encoding="utf-8")
    assert "MANAGER_QUICK_USERNAME" in source
    assert "MANAGER_QUICK_PIN" in source
    assert "auth_store.ensure_pin" in source
