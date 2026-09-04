"""Iteration 375: strict read-only auth/supabase/cors diagnostics on public preview URL."""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
import requests


# Module: environment resolution helpers (public URL from frontend/.env)
def _read_env_file(path: Path, key: str) -> str:
    if not path.exists():
        return ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def _base_url() -> str:
    return (os.environ.get("REACT_APP_BACKEND_URL") or _read_env_file(Path("/app/frontend/.env"), "REACT_APP_BACKEND_URL")).strip().rstrip("/")


def _workshop_id() -> str:
    return (os.environ.get("REACT_APP_WORKSHOP_ID") or _read_env_file(Path("/app/frontend/.env"), "REACT_APP_WORKSHOP_ID")).strip()


def _classify_supabase_key_type(raw: str) -> str:
    value = (raw or "").strip().strip('"').strip("'")
    if not value:
        return "MISSING"
    if value.startswith("eyJ") and value.count(".") == 2:
        return "LEGACY_JWT_SERVICE_ROLE"
    if value.startswith("sb_") or "sb_secret" in value.lower():
        return "NEW_SB_SECRET"
    return "UNKNOWN_FORMAT"


BASE_URL = _base_url()
WORKSHOP_ID = _workshop_id()
ADMIN_USERNAME = "مدير"
ADMIN_PASSWORD = "010101"
PROBE_ORIGIN = "https://accounting-ssot-fix.preview.emergentagent.com"


@pytest.fixture(scope="session")
def api_url() -> str:
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL missing")
    return BASE_URL


@pytest.fixture()
def api_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture()
def login_payload() -> dict:
    return {"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}


@pytest.fixture()
def auth_token(api_session: requests.Session, api_url: str, login_payload: dict) -> str:
    # Module: password login success probe using approved preview credential
    r = api_session.post(f"{api_url}/api/auth/login", json=login_payload, timeout=30)
    assert r.status_code == 200, r.text[:400]
    data = r.json()
    assert data.get("username") == ADMIN_USERNAME
    assert data.get("role") == "admin"
    token = data.get("access_token")
    assert isinstance(token, str) and token
    return token


# Module: health endpoint baseline
def test_health_status_and_body(api_session: requests.Session, api_url: str):
    r = api_session.get(f"{api_url}/api/health", timeout=20)
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, dict)
    assert "status" in body


# Module: sanitized key-type diagnostic (no secret value output)
def test_sanitized_supabase_key_type_available_to_code():
    runtime_raw = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    file_raw = _read_env_file(Path("/app/backend/.env"), "SUPABASE_SERVICE_ROLE_KEY")

    runtime_type = _classify_supabase_key_type(runtime_raw)
    file_type = _classify_supabase_key_type(file_raw)

    assert runtime_type in {"MISSING", "LEGACY_JWT_SERVICE_ROLE", "NEW_SB_SECRET", "UNKNOWN_FORMAT"}
    assert file_type in {"MISSING", "LEGACY_JWT_SERVICE_ROLE", "NEW_SB_SECRET", "UNKNOWN_FORMAT"}


# Module: login-authenticated self identity
def test_auth_me_after_password_login(api_session: requests.Session, api_url: str, auth_token: str):
    r = api_session.get(
        f"{api_url}/api/auth/me",
        headers={"Authorization": f"Bearer {auth_token}"},
        timeout=20,
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("username") == ADMIN_USERNAME
    assert data.get("role") == "admin"


# Module: httpOnly cookie contract on successful login
def test_login_sets_httponly_cookies(api_session: requests.Session, api_url: str, login_payload: dict):
    r = api_session.post(f"{api_url}/api/auth/login", json=login_payload, timeout=30)
    assert r.status_code == 200
    set_cookie = r.headers.get("Set-Cookie", "")
    assert "access_token=" in set_cookie
    assert "refresh_token=" in set_cookie
    assert "HttpOnly" in set_cookie


# Module: representative read-only endpoints (no business mutation)
@pytest.mark.parametrize(
    "path,params",
    [
        ("/api/users", None),
        ("/api/vehicles", None),
        ("/api/customers", None),
        ("/api/accounts", None),
        ("/api/finance/journal-entries", {"workshop_id": WORKSHOP_ID, "limit": 50}),
    ],
)
def test_read_endpoints_no_500(
    api_session: requests.Session,
    api_url: str,
    auth_token: str,
    path: str,
    params: dict | None,
):
    if path.endswith("journal-entries") and not WORKSHOP_ID:
        pytest.skip("REACT_APP_WORKSHOP_ID missing")
    r = api_session.get(
        f"{api_url}{path}",
        params=params,
        headers={"Authorization": f"Bearer {auth_token}"},
        timeout=45,
    )
    assert r.status_code == 200, f"{path} -> {r.status_code}: {r.text[:250]}"
    payload = r.json()
    if path.endswith("journal-entries") and isinstance(payload, dict):
        assert payload.get("success") is True
        assert isinstance(payload.get("data"), list)
    else:
        assert isinstance(payload, (list, dict))


# Module: CORS credential contract probe for cross-origin auth
def test_cross_origin_login_cors_contract(api_session: requests.Session, api_url: str, login_payload: dict):
    r = api_session.post(
        f"{api_url}/api/auth/login",
        headers={"Origin": PROBE_ORIGIN, "Content-Type": "application/json"},
        json=login_payload,
        timeout=30,
    )
    assert r.status_code == 200
    allow_origin = r.headers.get("Access-Control-Allow-Origin")
    allow_credentials = r.headers.get("Access-Control-Allow-Credentials")

    # expected credentialed CORS contract for browser include-credentials login
    assert allow_credentials == "true"
    assert allow_origin == PROBE_ORIGIN


# Module: static code scan for risky key-format assumptions/fallbacks
def test_static_code_auth_supabase_key_usage_contract():
    files = [
        Path("/app/backend/auth_jwt.py"),
        Path("/app/backend/supabase_service.py"),
        Path("/app/backend/routes_finance.py"),
        Path("/app/backend/auth_guard.py"),
        Path("/app/backend/core/auth_store.py"),
    ]
    merged = "\n".join(p.read_text(encoding="utf-8") for p in files if p.exists())

    # jwt.decode must not be applied to SUPABASE_SERVICE_ROLE_KEY anywhere in this scope
    risky = re.search(r"jwt\.decode\([^\n]*SUPABASE_SERVICE_ROLE_KEY", merged)
    assert risky is None

    # key_1 secondary var presence is allowed for reads; ensure no hardcoded service-role literal appears
    assert "SUPABASE_SERVICE_ROLE_KEY_1" in merged
    assert "eyJhbGciOiJI" not in merged
