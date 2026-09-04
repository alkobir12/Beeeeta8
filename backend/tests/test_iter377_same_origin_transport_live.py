"""Phase 1C same-origin auth transport live checks (read-only)."""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
import requests


# Module: environment + credential resolution
FRONTEND_ENV = Path("/app/frontend/.env")
CREDS_MD = Path("/app/memory/test_credentials.md")


def _frontend_env_value(key: str) -> str:
    if not FRONTEND_ENV.exists():
        return ""
    for raw in FRONTEND_ENV.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k.strip() == key:
            return v.strip()
    return ""


def _read_admin_credentials() -> tuple[str, str]:
    text = CREDS_MD.read_text(encoding="utf-8") if CREDS_MD.exists() else ""
    user_match = re.search(r"`مدير`", text)
    pass_match = re.search(r"`010101`", text)
    if not user_match or not pass_match:
        pytest.skip("Admin preview credentials missing in /app/memory/test_credentials.md")
    return "مدير", "010101"


BASE_URL = _frontend_env_value("REACT_APP_BACKEND_URL").rstrip("/")


@pytest.fixture(scope="module")
def api_client() -> requests.Session:
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL missing in /app/frontend/.env")
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# Module: same-origin public routing checks
def test_same_origin_api_health_is_reachable(api_client: requests.Session):
    r = api_client.get(f"{BASE_URL}/api/health", timeout=20)
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, dict)
    assert "status" in body


# Module: auth + cookie transport checks
def test_login_sets_cookie_security_attributes_and_me_persists(api_client: requests.Session):
    username, password = _read_admin_credentials()
    login = api_client.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": username, "password": password},
        timeout=25,
    )
    assert login.status_code == 200
    body = login.json()
    assert body.get("username") == username
    assert body.get("role") == "admin"

    raw_set_cookie = login.headers.get("set-cookie", "")
    lowered = raw_set_cookie.lower()
    assert "httponly" in lowered
    assert "secure" in lowered
    assert "samesite=" in lowered
    assert "path=/" in lowered

    me_1 = api_client.get(f"{BASE_URL}/api/auth/me", timeout=20)
    assert me_1.status_code == 200
    me_data_1 = me_1.json()
    assert me_data_1.get("username") == username
    assert me_data_1.get("role") == "admin"

    me_2 = api_client.get(f"{BASE_URL}/api/auth/me", timeout=20)
    assert me_2.status_code == 200
    me_data_2 = me_2.json()
    assert me_data_2.get("username") == username
    assert me_data_2.get("role") == "admin"


# Module: read-only authenticated resource checks
def test_authenticated_readonly_vehicles_and_customers(api_client: requests.Session):
    vehicles = api_client.get(f"{BASE_URL}/api/vehicles", timeout=25)
    assert vehicles.status_code == 200
    vehicles_data = vehicles.json()
    assert isinstance(vehicles_data, list)

    customers = api_client.get(f"{BASE_URL}/api/customers", timeout=25)
    assert customers.status_code == 200
    customers_data = customers.json()
    assert isinstance(customers_data, list)


# Module: CORS behavior evidence (edge may add wildcard; must not authorize credentialed untrusted)
def test_untrusted_origin_is_not_credential_authorized(api_client: requests.Session):
    untrusted = "https://evil.example"
    r = api_client.options(
        f"{BASE_URL}/api/auth/login",
        headers={
            "Origin": untrusted,
            "Access-Control-Request-Method": "POST",
        },
        timeout=20,
    )
    assert r.status_code in (200, 204, 400)
    acao = r.headers.get("Access-Control-Allow-Origin", "")
    acac = r.headers.get("Access-Control-Allow-Credentials", "")
    assert not (acao == untrusted and acac.lower() == "true")


# Module: auth seed/hash sanity from Mongo (skip gracefully when unavailable)
def test_admin_bcrypt_hash_starts_with_2b():
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        pytest.skip("MONGO_URL/DB_NAME missing")

    pymongo = pytest.importorskip("pymongo")
    client = pymongo.MongoClient(mongo_url, serverSelectionTimeoutMS=3000)
    try:
        db = client[db_name]
        doc = db.auth_credentials.find_one({"username": "مدير"}, {"password_hash": 1, "_id": 0})
        if not doc:
            pytest.skip("auth_credentials for مدير not found")
        password_hash = str(doc.get("password_hash") or "")
        assert password_hash.startswith("$2b$")
    finally:
        client.close()
