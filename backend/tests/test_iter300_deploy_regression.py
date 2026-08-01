"""Iter 300 — quick backend regression after deployment-readiness fixes.

Verifies:
- Env-var move (EMERGENT_SESSION_DATA_URL) did not break Google session endpoint import
- Login (username+PIN) still works
- Core APIs still reachable (GET /api/vehicles)
- Document template resolve still returns unified-invoice-a4-mobile-v1 for invoice
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL", "https://ar-ledger-ssot.preview.emergentagent.com"
).rstrip("/")
BYPASS = os.environ.get("RATE_LIMIT_BYPASS_TOKEN", "")

HDR = {"x-ratelimit-bypass": BYPASS, "Content-Type": "application/json"}
LOGIN_PAYLOAD = {"username": "مدير", "pin": "123123"}


# --- shared token ---
def _admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json=LOGIN_PAYLOAD, headers=HDR, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    j = r.json()
    assert j.get("access_token") and j.get("refresh_token")
    return j["access_token"]


# --- auth ---
def test_admin_login_returns_tokens():
    r = requests.post(f"{BASE_URL}/api/auth/login", json=LOGIN_PAYLOAD, headers=HDR, timeout=20)
    assert r.status_code == 200
    j = r.json()
    assert j.get("access_token")
    assert j.get("refresh_token")
    assert j.get("username") == "مدير"


# --- Google SSO env-var move ---
def test_google_session_endpoint_reachable_and_not_500():
    """After moving _EMERGENT_SESSION_DATA_URL to env var, module import & endpoint
    must still work. Invalid session_id should yield 4xx (401/400), NOT 500."""
    r = requests.post(
        f"{BASE_URL}/api/auth/google/session",
        json={"session_id": "invalid-session-id-iter300"},
        headers=HDR,
        timeout=20,
    )
    assert r.status_code != 500, f"unexpected 500 (module broken?): {r.text[:400]}"
    assert 400 <= r.status_code < 500, f"expected 4xx, got {r.status_code}: {r.text[:400]}"


# --- core API reachability ---
def test_vehicles_reachable_with_admin():
    tok = _admin_token()
    hdr = dict(HDR)
    hdr["Authorization"] = f"Bearer {tok}"
    r = requests.get(f"{BASE_URL}/api/vehicles?limit=3", headers=hdr, timeout=30)
    assert r.status_code == 200, f"{r.status_code} {r.text[:400]}"
    body = r.json()
    # accept list or {items: [...]}
    items = body if isinstance(body, list) else body.get("items") or body.get("data") or []
    assert isinstance(items, list)
    # Should have at least one vehicle (188 present per iter299 context)
    assert len(items) >= 1, "expected vehicles in supabase"


# --- template resolve ---
def test_invoice_template_resolves_to_unified_default():
    tok = _admin_token()
    hdr = dict(HDR)
    hdr["Authorization"] = f"Bearer {tok}"
    r = requests.post(
        f"{BASE_URL}/api/document-templates/resolve",
        json={"document_type": "invoice"},
        headers=hdr,
        timeout=20,
    )
    assert r.status_code == 200, f"{r.status_code} {r.text[:400]}"
    j = r.json()
    # Endpoint returns the resolved template payload — check id/slug
    slug = (
        j.get("id")
        or j.get("slug")
        or j.get("template_id")
        or (j.get("template") or {}).get("id")
        or (j.get("template") or {}).get("slug")
    )
    assert slug == "unified-invoice-a4-mobile-v1", f"expected default 'unified-invoice-a4-mobile-v1', got {slug!r} payload={j}"
