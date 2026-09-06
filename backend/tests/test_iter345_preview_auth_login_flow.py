"""Iter345: Preview auth login regression (API contracts for /api/auth/*)."""

import os
import uuid
from pathlib import Path

import pytest
import requests


def _base_url() -> str:
    url = (os.environ.get("REACT_APP_BACKEND_URL") or "").strip().rstrip("/")
    if url:
        return url
    env_file = Path("/app/frontend/.env")
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().rstrip("/")
    return ""


BASE_URL = _base_url()
MANAGER_USERNAME = "مدير"
ACCOUNTANT_USERNAME = "احمد"
TEMP_PASSWORD = "010101"
OLD_PIN = "123123"


@pytest.fixture(scope="session")
def api_url():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is missing")
    return BASE_URL


@pytest.fixture()
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _login(session_obj: requests.Session, api_url: str, payload: dict, *, ip: str | None = None):
    headers = {"Content-Type": "application/json"}
    if ip:
        headers["x-forwarded-for"] = ip
    return session_obj.post(f"{api_url}/api/auth/login", json=payload, headers=headers, timeout=30)


# Feature: login hardening contracts (no name-only, old pin rejected)
def test_login_name_only_returns_401(session, api_url):
    res = _login(session, api_url, {"username": MANAGER_USERNAME})
    assert res.status_code == 401
    body = res.json()
    assert isinstance(body.get("detail"), str)


def test_login_old_pin_returns_401(session, api_url):
    res = _login(session, api_url, {"username": MANAGER_USERNAME, "pin": OLD_PIN})
    assert res.status_code == 401
    body = res.json()
    assert isinstance(body.get("detail"), str)


# Feature: temporary password auth for preview users + role assertions
def test_manager_password_login_success_with_admin_role_and_pin_not_configured(session, api_url):
    res = _login(session, api_url, {"username": MANAGER_USERNAME, "password": TEMP_PASSWORD})
    assert res.status_code == 200, res.text[:400]
    data = res.json()
    assert data.get("username") == MANAGER_USERNAME
    assert data.get("role") == "admin"
    assert data.get("pin_configured") is False
    assert isinstance(data.get("access_token"), str) and data.get("access_token")


def test_accountant_password_login_success_with_accountant_role(session, api_url):
    res = _login(session, api_url, {"username": ACCOUNTANT_USERNAME, "password": TEMP_PASSWORD})
    assert res.status_code == 200, res.text[:400]
    data = res.json()
    assert data.get("username") == ACCOUNTANT_USERNAME
    assert data.get("role") == "accountant"
    assert data.get("role") != "admin"
    assert data.get("pin_configured") is False


# Feature: cookie + /api/auth/me regression checks
def test_success_login_sets_httponly_cookies(session, api_url):
    res = _login(session, api_url, {"username": MANAGER_USERNAME, "password": TEMP_PASSWORD})
    assert res.status_code == 200, res.text[:400]

    set_cookie = res.headers.get("set-cookie", "")
    lower = set_cookie.lower()
    assert "access_token=" in lower
    assert "refresh_token=" in lower
    assert "httponly" in lower


def test_auth_me_returns_logged_in_user(session, api_url):
    login_res = _login(session, api_url, {"username": MANAGER_USERNAME, "password": TEMP_PASSWORD})
    assert login_res.status_code == 200, login_res.text[:400]

    me_res = session.get(f"{api_url}/api/auth/me", timeout=30)
    assert me_res.status_code == 200, me_res.text[:400]
    me = me_res.json()
    assert me.get("username") == MANAGER_USERNAME
    assert me.get("role") == "admin"


# Feature: brute-force lockout after five failures (identifier+IP scoped)
def test_lockout_after_five_failed_attempts(session, api_url):
    ip = f"203.0.113.{(uuid.uuid4().int % 200) + 10}"
    bad_passwords = [f"wrong-{idx}-{uuid.uuid4().hex[:6]}" for idx in range(6)]
    statuses = []
    for pw in bad_passwords:
        r = _login(session, api_url, {"username": MANAGER_USERNAME, "password": pw}, ip=ip)
        statuses.append(r.status_code)
    assert statuses[:5] == [401, 401, 401, 401, 401]
    assert statuses[5] == 429


# Feature: CORS credentials contract for preview origin (public endpoint)
def test_login_cors_headers_for_preview_origin(session, api_url):
    origin = "https://financial-ssot.preview.emergentagent.com"
    res = session.post(
        f"{api_url}/api/auth/login",
        headers={"Content-Type": "application/json", "Origin": origin},
        json={"username": MANAGER_USERNAME, "password": TEMP_PASSWORD},
        timeout=30,
    )
    assert res.status_code == 200, res.text[:400]
    assert res.headers.get("access-control-allow-credentials") == "true"
    assert res.headers.get("access-control-allow-origin") == origin


# Feature: bcrypt storage format for seeded preview users
def test_preview_users_password_hashes_are_bcrypt_2b():
    mongo_url = (os.environ.get("MONGO_URL") or "").strip()
    db_name = (os.environ.get("DB_NAME") or "").strip()
    if not mongo_url or not db_name:
        pytest.skip("MONGO_URL/DB_NAME missing")

    pymongo = pytest.importorskip("pymongo")
    client = pymongo.MongoClient(mongo_url, serverSelectionTimeoutMS=5000)
    col = client[db_name]["auth_credentials"]
    for username in (MANAGER_USERNAME, ACCOUNTANT_USERNAME):
        doc = col.find_one({"username": username}, {"_id": 0, "password_hash": 1})
        assert doc and isinstance(doc.get("password_hash"), str)
        assert doc["password_hash"].startswith("$2b$")
