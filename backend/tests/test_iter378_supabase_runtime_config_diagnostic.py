"""Iteration 378: Supabase runtime config source diagnostic (strict read-only)."""

from __future__ import annotations

import base64
import os
import re
from pathlib import Path

import pytest
import requests
from dotenv import load_dotenv


# Module: fixed paths and constants for diagnostic scope
SERVER_FILE = Path("/app/backend/server.py")
BACKEND_ENV = Path("/app/backend/.env")
FRONTEND_ENV = Path("/app/frontend/.env")
AUTH_JWT_FILE = Path("/app/backend/auth_jwt.py")
FINANCE_FILE = Path("/app/backend/routes_finance.py")
SUPABASE_SERVICE_FILE = Path("/app/backend/supabase_service.py")
CREDS_FILE = Path("/app/memory/test_credentials.md")
EXPECTED_PROJECT_REF = "beeeta8"


# Module: helpers (no secret output)
def _read_env_file_value(path: Path, key: str) -> str:
    if not path.exists():
        return ""
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k.strip() == key:
            return v.strip().strip('"').strip("'")
    return ""


def _project_ref_from_url(url: str) -> str:
    value = (url or "").strip()
    match = re.search(r"https://([a-z0-9-]+)\.supabase\.co", value)
    return match.group(1) if match else ""


def _classify_supabase_key_type(raw_value: str) -> str:
    value = (raw_value or "").strip().strip('"').strip("'")
    if not value:
        return "MISSING"
    if value.startswith("eyJ") and value.count(".") == 2:
        return "LEGACY_JWT_SERVICE_ROLE"
    if value.startswith("sb_") or "sb_secret" in value.lower():
        return "NEW_SB_SECRET"
    return "UNKNOWN_FORMAT"


def _read_admin_preview_credentials() -> tuple[str, str]:
    text = CREDS_FILE.read_text(encoding="utf-8") if CREDS_FILE.exists() else ""
    if "`مدير`" not in text or "`010101`" not in text:
        pytest.skip("Required admin preview credentials not found in /app/memory/test_credentials.md")
    return "مدير", "010101"


def _decode_jwt_payload_unsafe(jwt_token: str) -> dict:
    """Decode JWT payload for metadata-only checks; no signature verification, no prints."""
    token = (jwt_token or "").strip().strip('"').strip("'")
    parts = token.split(".")
    if len(parts) != 3:
        return {}
    payload_b64 = parts[1]
    padding = "=" * ((4 - len(payload_b64) % 4) % 4)
    try:
        raw = base64.urlsafe_b64decode(payload_b64 + padding).decode("utf-8", errors="ignore")
    except Exception:
        return {}
    try:
        import json

        payload = json.loads(raw)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


BASE_URL = _read_env_file_value(FRONTEND_ENV, "REACT_APP_BACKEND_URL").rstrip("/")


@pytest.fixture(scope="module")
def api_session() -> requests.Session:
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL missing in /app/frontend/.env")
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def admin_auth_token(api_session: requests.Session) -> str:
    username, password = _read_admin_preview_credentials()
    response = api_session.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": username, "password": password},
        timeout=30,
    )
    assert response.status_code == 200, f"Login failed: status={response.status_code}"
    data = response.json()
    assert data.get("username") == username
    assert data.get("role") == "admin"
    token = data.get("access_token")
    assert isinstance(token, str) and bool(token)
    return token


# Module: static source-of-truth checks for dotenv loading
def test_server_loads_backend_env_with_override_false():
    content = SERVER_FILE.read_text(encoding="utf-8")
    assert 'load_dotenv(ROOT_DIR / ".env", override=False)' in content


# Module: process/platform env absence check from current shell context
def test_shell_process_env_absent_for_supabase_keys_before_explicit_load():
    assert os.environ.get("SUPABASE_URL") in (None, "")
    assert os.environ.get("SUPABASE_SERVICE_ROLE_KEY") in (None, "")


# Module: app-equivalent dotenv initialization behavior
def test_app_equivalent_dotenv_sets_primary_keys_and_not_secondary(monkeypatch: pytest.MonkeyPatch):
    for key in (
        "SUPABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_URL_1",
        "SUPABASE_SERVICE_ROLE_KEY_1",
    ):
        monkeypatch.delenv(key, raising=False)

    load_dotenv(BACKEND_ENV, override=False)

    assert isinstance(os.environ.get("SUPABASE_URL"), str) and bool(os.environ.get("SUPABASE_URL"))
    assert isinstance(os.environ.get("SUPABASE_SERVICE_ROLE_KEY"), str) and bool(
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    )
    assert os.environ.get("SUPABASE_URL_1") in (None, "")
    assert os.environ.get("SUPABASE_SERVICE_ROLE_KEY_1") in (None, "")


# Module: metadata-only project-ref validation (no secret exposure)
def test_backend_env_project_ref_mismatch_expected_beeeta8():
    supabase_url = _read_env_file_value(BACKEND_ENV, "SUPABASE_URL")
    current_ref = _project_ref_from_url(supabase_url)
    assert current_ref
    assert current_ref != EXPECTED_PROJECT_REF


# Module: key type classification verification without printing value
def test_effective_key_type_classification_after_app_equivalent_load(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    load_dotenv(BACKEND_ENV, override=False)
    key_value = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    key_type = _classify_supabase_key_type(key_value)
    assert key_type == "LEGACY_JWT_SERVICE_ROLE"


# Module: verify legacy JWT payload metadata matches URL project ref
def test_legacy_jwt_ref_matches_backend_supabase_url_project_ref():
    key_value = _read_env_file_value(BACKEND_ENV, "SUPABASE_SERVICE_ROLE_KEY")
    key_type = _classify_supabase_key_type(key_value)
    if key_type != "LEGACY_JWT_SERVICE_ROLE":
        pytest.skip("Supabase key is not legacy JWT format in backend/.env")

    payload = _decode_jwt_payload_unsafe(key_value)
    jwt_ref = str(payload.get("ref") or "").strip()
    url_ref = _project_ref_from_url(_read_env_file_value(BACKEND_ENV, "SUPABASE_URL"))
    assert jwt_ref
    assert url_ref
    assert jwt_ref == url_ref


# Module: ensure auth login path does not decode Supabase key
def test_login_path_does_not_decode_supabase_service_role_key():
    auth_content = AUTH_JWT_FILE.read_text(encoding="utf-8")
    login_block_match = re.search(r"@router\.post\(\"/login\"\)([\s\S]*?)@router\.post\(\"/logout\"\)", auth_content)
    assert login_block_match is not None
    login_block = login_block_match.group(1)

    assert "SUPABASE_SERVICE_ROLE_KEY" not in login_block
    assert re.search(r"jwt\.decode\([^\n]*SUPABASE_SERVICE_ROLE_KEY", login_block) is None


# Module: verify secondary key vars exist only as optional fallback paths
def test_secondary_supabase_vars_only_optional_and_not_used_in_login():
    finance_content = FINANCE_FILE.read_text(encoding="utf-8")
    auth_content = AUTH_JWT_FILE.read_text(encoding="utf-8")
    assert "SUPABASE_URL_1" in finance_content
    assert "SUPABASE_SERVICE_ROLE_KEY_1" in finance_content
    assert "SUPABASE_URL_1" not in auth_content
    assert "SUPABASE_SERVICE_ROLE_KEY_1" not in auth_content


# Module: verify primary key path for shared Supabase client initialization
def test_supabase_service_initializes_client_from_primary_env_vars_only():
    content = SUPABASE_SERVICE_FILE.read_text(encoding="utf-8")
    assert 'self.supabase_url = os.environ.get("SUPABASE_URL", "")' in content
    assert 'self.supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")' in content


# Module: live login + representative read-only endpoint pass checks
def test_live_login_and_read_pass(api_session: requests.Session, admin_auth_token: str):
    me = api_session.get(
        f"{BASE_URL}/api/auth/me",
        headers={"Authorization": f"Bearer {admin_auth_token}"},
        timeout=25,
    )
    assert me.status_code == 200
    me_data = me.json()
    assert me_data.get("username") == "مدير"
    assert me_data.get("role") == "admin"

    users = api_session.get(
        f"{BASE_URL}/api/users",
        headers={"Authorization": f"Bearer {admin_auth_token}"},
        timeout=30,
    )
    assert users.status_code == 200
    users_data = users.json()
    assert isinstance(users_data, list)
