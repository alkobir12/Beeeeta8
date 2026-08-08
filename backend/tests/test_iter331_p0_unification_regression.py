"""P0 unification regression checks: auth + approvals + financial engine + static guards."""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import pytest
import requests


def _load_base_url() -> str:
    base = os.environ.get("REACT_APP_BACKEND_URL", "").strip()
    if base:
        return base.rstrip("/")

    env_path = Path("/app/frontend/.env")
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().rstrip("/")

    pytest.fail("REACT_APP_BACKEND_URL is missing (env + frontend/.env).")


BASE_URL = _load_base_url()


@pytest.fixture(scope="session")
def api_client() -> requests.Session:
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def manager_login(api_client: requests.Session) -> dict:
    resp = api_client.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": "مدير", "pin": "123123", "remember_device": False},
        timeout=20,
    )
    assert resp.status_code == 200, f"manager login failed: {resp.status_code} {resp.text[:200]}"
    data = resp.json()
    assert isinstance(data.get("access_token"), str) and data["access_token"], "access_token missing"
    assert isinstance(data.get("refresh_token"), str) and data["refresh_token"], "refresh_token missing"
    return {"response": resp, "data": data}


@pytest.fixture(scope="session")
def auth_headers(manager_login: dict) -> dict:
    return {"Authorization": f"Bearer {manager_login['data']['access_token']}"}


# -------------------------
# Auth and runtime API checks
# -------------------------


def test_health_endpoint(api_client: requests.Session):
    resp = api_client.get(f"{BASE_URL}/api/health", timeout=20)
    assert resp.status_code == 200, f"health failed: {resp.status_code}"
    payload = resp.json()
    assert payload.get("status") in {"healthy", "ok", "degraded"}


def test_login_sets_http_only_cookies(manager_login: dict):
    set_cookie = manager_login["response"].headers.get("set-cookie", "")
    lower = set_cookie.lower()
    assert "access_token=" in set_cookie and "refresh_token=" in set_cookie
    assert "httponly" in lower
    assert "samesite=" in lower


def test_cors_credentials_are_explicit(api_client: requests.Session):
    origin = BASE_URL
    headers = {
        "Origin": origin,
        "Access-Control-Request-Method": "POST",
    }
    resp = api_client.options(f"{BASE_URL}/api/auth/login", headers=headers, timeout=20)
    assert resp.status_code in {200, 204}
    allow_origin = resp.headers.get("access-control-allow-origin", "")
    allow_creds = resp.headers.get("access-control-allow-credentials")

    if allow_origin == "*" and allow_creds is None:
        # preview edge may normalize preflight headers; verify backend config statically.
        server_src = Path("/app/backend/server.py").read_text(encoding="utf-8")
        assert "allow_credentials=True" in server_src
        assert "_credentialed_cors_origin" in server_src
    else:
        assert allow_creds == "true"
        assert allow_origin and allow_origin != "*"


def test_bruteforce_lockout_after_five_failures(api_client: requests.Session):
    username = f"LOCKOUT_ITER331_{uuid.uuid4().hex[:8]}"
    url = f"{BASE_URL}/api/auth/login"
    body = {"username": username, "pin": "000000"}

    statuses = []
    for _ in range(6):
        r = api_client.post(url, json=body, timeout=20)
        statuses.append(r.status_code)

    assert 429 in statuses[-2:], f"expected lockout 429 after failures, got {statuses}"


def test_approval_410_not_pending_and_not_approvable(api_client: requests.Session, auth_headers: dict):
    approval_id = "e64a52362b6c"
    list_resp = api_client.get(
        f"{BASE_URL}/api/runtime/approvals",
        params={"limit": 200},
        headers=auth_headers,
        timeout=20,
    )
    assert list_resp.status_code == 200, f"approvals listing failed: {list_resp.status_code}"
    approvals = (list_resp.json() or {}).get("data") or []
    row = next((a for a in approvals if str(a.get("id")) == approval_id), None)
    assert row is not None, "target approval_id e64a52362b6c missing"
    assert row.get("status") != "pending"

    approve_resp = api_client.post(
        f"{BASE_URL}/api/runtime/approvals/{approval_id}/approve",
        headers=auth_headers,
        json={},
        timeout=20,
    )
    assert approve_resp.status_code == 400
    body = approve_resp.json()
    detail = body.get("detail")
    if isinstance(detail, dict):
        assert detail.get("error") == "invalid_state"
        assert detail.get("current") in {"rejected", "approved", "committed", "rolled_back"}
    else:
        assert "invalid_state" in str(detail)


def test_vehicle_financial_summary_uses_unified_engine(api_client: requests.Session, auth_headers: dict):
    vehicles_resp = api_client.get(
        f"{BASE_URL}/api/vehicles",
        params={"limit": 1},
        headers=auth_headers,
        timeout=25,
    )
    assert vehicles_resp.status_code == 200, f"vehicles list failed: {vehicles_resp.status_code}"
    vehicles = vehicles_resp.json() or []
    assert vehicles, "vehicles list empty"
    vehicle_id = vehicles[0]["id"]

    summary_resp = api_client.get(
        f"{BASE_URL}/api/vehicles/{vehicle_id}/financial-summary",
        headers=auth_headers,
        timeout=25,
    )
    assert summary_resp.status_code == 200, f"financial summary failed: {summary_resp.status_code}"
    data = summary_resp.json()
    assert data.get("engine_version") == "unified-v1"
    assert isinstance(data.get("customer_total", data.get("total", 0)), (int, float))


def test_ar_customers_as_of_contract(api_client: requests.Session, auth_headers: dict):
    resp = api_client.get(
        f"{BASE_URL}/api/finance/ar/customers",
        params={"as_of": "2026-08-07", "workshop_id": "finmodule-sync"},
        headers=auth_headers,
        timeout=25,
    )
    assert resp.status_code == 200, f"AR customers failed: {resp.status_code} {resp.text[:180]}"
    body = resp.json()
    assert body.get("success") is True
    data = body.get("data")
    assert isinstance(data, dict)
    assert isinstance(data.get("total_ar"), (int, float))
    assert isinstance(data.get("customers"), list)


# -------------------------
# Static/code-level P0 guard checks
# -------------------------


def test_safe_insert_journal_entry_has_no_direct_fallback_insert():
    src = Path("/app/backend/routes_extended.py").read_text(encoding="utf-8")
    fn_start = src.index("def _safe_insert_journal_entry")
    fn_end = src.index("@router.get(\"/operations\")", fn_start)
    fn = src[fn_start:fn_end]
    assert "accounting_engine.post_entry(entry, fallback=False)" in fn
    assert "journal_entries\").insert" not in fn
    assert "no direct journal fallback" in fn


def test_create_draft_persists_required_provenance_fields():
    src = Path("/app/backend/core/action_runtime.py").read_text(encoding="utf-8")
    start = src.index("def create_draft(")
    end = src.index("def get_draft(", start)
    block = src[start:end]
    required = [
        "\"draft_id\"",
        "\"action_type\"",
        "\"requested_by\"",
        "\"requested_at\"",
        "\"original_input\"",
        "\"validated_payload\"",
        "\"trace_id\"",
        "\"entry_channel\"",
        "\"risk_level\"",
        "\"source_classification\"",
        "\"record_kind\"",
    ]
    for key in required:
        assert key in block, f"missing provenance field in create_draft: {key}"


def test_financial_ai_or_test_artifact_requires_conversion_before_approval():
    src = Path("/app/backend/core/action_runtime.py").read_text(encoding="utf-8")
    start = src.index("def approve(")
    end = src.index("def reject_approval(", start)
    block = src[start:end]
    assert "source_classification" in block
    assert "AI_SUGGESTION" in block and "TEST_ARTIFACT" in block
    assert "converted_by" in block
    assert "provenance_conversion_required" in block


def test_visit_sync_uses_explicit_mismatch_error_and_no_direct_delete():
    src = Path("/app/backend/visit_sync.py").read_text(encoding="utf-8")
    assert "visit_accrual_mismatch_requires_review" in src
    assert ".table(\"journal_entries\").delete" not in src


def test_supplier_balance_payment_blocks_missing_suppliers_and_checks_engine_result():
    src = Path("/app/backend/routes_smart_accounting.py").read_text(encoding="utf-8")
    assert "suppliers_table_available = False" in src
    assert "جدول الموردين غير متاح" in src
    assert "accounting_engine.post_entry(entry, fallback=False)" in src
    assert "if not inserted" in src


def test_upsert_entity_blocks_primary_tables_when_primary_db_unavailable():
    src = Path("/app/backend/core/action_runtime.py").read_text(encoding="utf-8")
    start = src.index("def upsert_entity(")
    end = src.index("def _delete_entity(", start)
    block = src[start:end]
    assert 'if table in {"customers", "vehicles", "visits"}' in block
    assert 'raise RuntimeError(f"primary_db_unavailable:{table}")' in block


def test_auth_hashes_are_bcrypt_2b_and_startup_seeding_wired():
    if "/app/backend" not in sys.path:
        sys.path.append("/app/backend")
    from core import auth_store

    hashed = auth_store.hash_secret("iter331-pin-check")
    assert hashed.startswith("$2b$")

    startup_src = Path("/app/backend/server.py").read_text(encoding="utf-8")
    assert "MANAGER_QUICK_USERNAME" in startup_src
    assert "MANAGER_QUICK_PIN" in startup_src
    assert "auth_store.ensure_pin" in startup_src
