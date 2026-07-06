"""Iteration 250 — Security hotfixes regression tests (isolated diffs).

Hotfix 1 — RBAC on POST /api/assistant/tool/{name} (was: any authenticated user
           could execute ANY tool):
  1. No token            → 401
  2. فرج1 (accountant)   → 403 (non-approver role)
  3. مدير (admin)        → 200 + tool executes

Hotfix 2 — whatsapp.send is a WRITE tool (external side-effect via Infobip).
           Under the Phase 3A contract it must NOT be registered while
           BOT_ALLOW_WRITES != 1:
  4. Absent from GET /api/assistant/tools registry
  5. Direct invocation (even as admin) → "tool not found"

Hotfix 3 — Print/PDF workshop identity (unified_document_service):
  6. Empty-string workshop fields from the caller do NOT wipe profile data —
     generated HTML contains the stored workshop name.
  7. Explicit caller values still override the profile (merge order preserved).

DATA SAFETY: read-only; document generation does not persist anything.
"""
from __future__ import annotations

import os

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"
API = f"{BASE_URL}/api"

READ_TOOL = "services.categories"  # harmless read-only tool for RBAC probes


def _fresh_session() -> requests.Session:
    s = requests.Session()
    s.headers["Content-Type"] = "application/json"
    return s


def _login(username: str) -> str:
    s = _fresh_session()
    r = s.post(f"{API}/auth/login", json={"username": username}, timeout=30)
    assert r.status_code == 200, f"login {username} failed: {r.status_code} {r.text[:200]}"
    tok = r.json().get("access_token")
    assert tok, "no access_token in login response"
    return tok


@pytest.fixture(scope="module")
def admin_token() -> str:
    return _login("مدير")


@pytest.fixture(scope="module")
def accountant_token() -> str:
    return _login("فرج1")


# ----- Hotfix 1 — RBAC on /assistant/tool/{name} -----------------------------

def test_tool_endpoint_no_token_401():
    s = _fresh_session()
    r = s.post(f"{API}/assistant/tool/{READ_TOOL}", json={}, timeout=30)
    assert r.status_code == 401, f"expected 401, got {r.status_code}: {r.text[:200]}"


def test_tool_endpoint_non_approver_403(accountant_token):
    s = _fresh_session()
    s.headers["Authorization"] = f"Bearer {accountant_token}"
    r = s.post(f"{API}/assistant/tool/{READ_TOOL}", json={}, timeout=30)
    assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text[:200]}"
    detail = r.json().get("detail", {})
    assert detail.get("error") == "permission_denied"
    assert detail.get("role") == "accountant"


def test_tool_endpoint_admin_executes(admin_token):
    s = _fresh_session()
    s.headers["Authorization"] = f"Bearer {admin_token}"
    r = s.post(f"{API}/assistant/tool/{READ_TOOL}", json={}, timeout=60)
    assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text[:200]}"
    body = r.json()
    assert body.get("success") is True
    assert body.get("tool") == READ_TOOL


# ----- Hotfix 2 — whatsapp.send write contract --------------------------------

def test_whatsapp_send_not_registered(admin_token):
    s = _fresh_session()
    s.headers["Authorization"] = f"Bearer {admin_token}"
    r = s.get(f"{API}/assistant/tools", timeout=30)
    assert r.status_code == 200
    names = [t["name"] for t in r.json()["data"]]
    assert "whatsapp.send" not in names, (
        "whatsapp.send must not be registered while BOT_ALLOW_WRITES != 1"
    )


def test_whatsapp_send_invocation_blocked(admin_token):
    s = _fresh_session()
    s.headers["Authorization"] = f"Bearer {admin_token}"
    r = s.post(
        f"{API}/assistant/tool/whatsapp.send",
        json={"to": "0550000000", "message": "TESTQA"},
        timeout=30,
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("success") is False
    assert "tool not found" in (body.get("error") or "")


# ----- Hotfix 3 — print workshop identity fallback ----------------------------

_EMPTY_WS_PAYLOAD = {
    "doc_type": "invoice",
    "workshop": {"name": "", "address": "", "phone": "", "email": "", "commercial_register": ""},
    "customer": {"name": "TESTQA عميل"},
    "vehicle": {},
    "items": [{"description": "TESTQA بند", "quantity": 1, "unit_price": 100, "discount": 0}],
    "settings": {"theme": "أزرق", "style": "حديث", "tax_rate": 0},
}


def _profile_name(admin_token: str) -> str:
    s = _fresh_session()
    s.headers["Authorization"] = f"Bearer {admin_token}"
    r = s.get(f"{API}/profile", timeout=30)
    assert r.status_code == 200
    return (r.json().get("name") or "").strip()


def test_print_empty_workshop_fields_fallback_to_profile(admin_token):
    name = _profile_name(admin_token)
    assert name, "workshop profile must have a name for this test"
    s = _fresh_session()
    s.headers["Authorization"] = f"Bearer {admin_token}"
    r = s.post(f"{API}/documents/generate", json=_EMPTY_WS_PAYLOAD, timeout=60)
    assert r.status_code == 200
    body = r.json()
    assert body.get("success") is True
    assert name in body.get("html", ""), (
        "empty caller workshop fields must not wipe stored profile identity"
    )


def test_print_explicit_caller_value_overrides_profile(admin_token):
    payload = {**_EMPTY_WS_PAYLOAD, "workshop": {**_EMPTY_WS_PAYLOAD["workshop"], "name": "TESTQA ورشة صريحة"}}
    s = _fresh_session()
    s.headers["Authorization"] = f"Bearer {admin_token}"
    r = s.post(f"{API}/documents/generate", json=payload, timeout=60)
    assert r.status_code == 200
    html = r.json().get("html", "")
    assert "TESTQA ورشة صريحة" in html, "explicit caller value must still win the merge"
