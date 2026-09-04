"""Iteration 376: Phase 1C CORS/cookie-session verification (read-only)."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
import requests


# Module: environment + constants
def _read_frontend_env(key: str) -> str:
    env_path = Path("/app/frontend/.env")
    if not env_path.exists():
        return ""
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def _base_url() -> str:
    return (os.environ.get("REACT_APP_BACKEND_URL") or _read_frontend_env("REACT_APP_BACKEND_URL")).strip().rstrip("/")


def _workshop_id() -> str:
    return (os.environ.get("REACT_APP_WORKSHOP_ID") or _read_frontend_env("REACT_APP_WORKSHOP_ID")).strip()


BASE_URL = _base_url()
WORKSHOP_ID = _workshop_id()
INTERNAL_URL = "http://localhost:8001"
TRUSTED_ORIGIN = "https://accounting-ssot-fix.preview.emergentagent.com"
UNTRUSTED_ORIGIN = "https://evil.example.com"
ADMIN_USERNAME = "مدير"
ADMIN_PASSWORD = "010101"


def _h(headers: requests.structures.CaseInsensitiveDict, name: str) -> str:
    return (headers.get(name) or "").strip()


def _assert_cookie_contract(set_cookie: str):
    lower = (set_cookie or "").lower()
    assert "access_token=" in lower
    assert "refresh_token=" in lower
    assert "httponly" in lower
    assert "secure" in lower
    assert "samesite=none" in lower
    assert "path=/" in lower


@pytest.fixture(scope="session")
def api_url() -> str:
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL missing")
    return BASE_URL


@pytest.fixture()
def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# Module: code inspection of CORS + frontend credentials behavior
def test_server_cors_middleware_is_credentialed_without_literal_wildcard_list():
    source = Path("/app/backend/server.py").read_text(encoding="utf-8")
    assert "allow_credentials=True" in source
    assert 'allow_origins=["*"]' not in source


def test_frontend_login_and_refresh_use_credentials_include_only():
    source = Path("/app/frontend/src/utils/authToken.js").read_text(encoding="utf-8")
    assert "credentials: 'include'" in source
    assert "credentials: 'omit'" not in source


# Module: internal backend CORS checks (trusted + untrusted origins)
def test_internal_options_trusted_origin_returns_explicit_origin_and_credentials(session: requests.Session):
    r = session.options(
        f"{INTERNAL_URL}/api/auth/login",
        headers={
            "Origin": TRUSTED_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
        timeout=20,
    )
    assert r.status_code in {200, 204}
    assert _h(r.headers, "Access-Control-Allow-Origin") == TRUSTED_ORIGIN
    assert _h(r.headers, "Access-Control-Allow-Credentials").lower() == "true"


def test_internal_post_trusted_origin_sets_cookie_and_cors_contract(session: requests.Session):
    r = session.post(
        f"{INTERNAL_URL}/api/auth/login",
        headers={"Origin": TRUSTED_ORIGIN, "Content-Type": "application/json"},
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    assert r.status_code == 200
    assert _h(r.headers, "Access-Control-Allow-Origin") == TRUSTED_ORIGIN
    assert _h(r.headers, "Access-Control-Allow-Credentials").lower() == "true"
    _assert_cookie_contract(_h(r.headers, "Set-Cookie"))


def test_internal_options_untrusted_origin_not_allowed(session: requests.Session):
    r = session.options(
        f"{INTERNAL_URL}/api/auth/login",
        headers={
            "Origin": UNTRUSTED_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
        timeout=20,
    )
    assert r.status_code in {400, 403}
    assert _h(r.headers, "Access-Control-Allow-Origin") in {"", "null"}


# Module: external preview effective CORS checks (trusted + untrusted origins)
def test_external_options_trusted_origin_returns_explicit_origin_and_credentials(session: requests.Session, api_url: str):
    r = session.options(
        f"{api_url}/api/auth/login",
        headers={
            "Origin": TRUSTED_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
        timeout=25,
    )
    assert r.status_code in {200, 204}
    assert _h(r.headers, "Access-Control-Allow-Origin") == TRUSTED_ORIGIN
    assert _h(r.headers, "Access-Control-Allow-Credentials").lower() == "true"


def test_external_post_trusted_origin_sets_cookie_and_cors_contract(session: requests.Session, api_url: str):
    r = session.post(
        f"{api_url}/api/auth/login",
        headers={"Origin": TRUSTED_ORIGIN, "Content-Type": "application/json"},
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    assert r.status_code == 200
    assert _h(r.headers, "Access-Control-Allow-Origin") == TRUSTED_ORIGIN
    assert _h(r.headers, "Access-Control-Allow-Credentials").lower() == "true"
    _assert_cookie_contract(_h(r.headers, "Set-Cookie"))


def test_external_options_untrusted_origin_not_allowed(session: requests.Session, api_url: str):
    r = session.options(
        f"{api_url}/api/auth/login",
        headers={
            "Origin": UNTRUSTED_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
        timeout=25,
    )
    assert r.status_code in {200, 204, 400, 403}
    assert _h(r.headers, "Access-Control-Allow-Origin") in {"", "null"}


# Module: auth + representative read-only endpoint sanity (no data mutation)
def test_admin_login_me_and_representative_reads_no_500(session: requests.Session, api_url: str):
    login_res = session.post(
        f"{api_url}/api/auth/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    assert login_res.status_code == 200
    login_data = login_res.json()
    token = login_data.get("access_token")
    assert isinstance(token, str) and token

    auth_headers = {"Authorization": f"Bearer {token}"}
    me_res = session.get(f"{api_url}/api/auth/me", headers=auth_headers, timeout=20)
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data.get("username") == ADMIN_USERNAME
    assert me_data.get("role") == "admin"

    checks = [
        ("/api/users", None),
        ("/api/vehicles", None),
        ("/api/customers", None),
        ("/api/accounts", None),
        ("/api/finance/journal-entries", {"workshop_id": WORKSHOP_ID, "limit": 50}),
    ]
    for path, params in checks:
        if path.endswith("journal-entries") and not WORKSHOP_ID:
            continue
        res = session.get(f"{api_url}{path}", params=params, headers=auth_headers, timeout=45)
        assert res.status_code == 200, f"{path} -> {res.status_code}"


# Module: brute-force lockout (5 fails then lock)
def test_bruteforce_lockout_after_five_failures(session: requests.Session, api_url: str):
    ip = f"198.51.100.{(uuid.uuid4().int % 200) + 20}"
    identifier = f"iter376-lock-{uuid.uuid4().hex[:8]}"
    statuses = []
    for _ in range(6):
        res = session.post(
            f"{api_url}/api/auth/login",
            headers={"x-forwarded-for": ip, "Content-Type": "application/json"},
            json={"username": identifier, "password": "wrong-password"},
            timeout=20,
        )
        statuses.append(res.status_code)
    assert statuses[:5] == [401, 401, 401, 401, 401]
    assert statuses[5] == 429
