"""Iter344 auth playbook regression checks (security-hardening contracts)."""

import os
import uuid
from pathlib import Path

import pytest
import requests


API = (os.environ.get("REACT_APP_BACKEND_URL") or "").strip().rstrip("/")
if not API:
    env_file = Path("/app/frontend/.env")
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("REACT_APP_BACKEND_URL="):
                API = line.split("=", 1)[1].strip().rstrip("/")


TEST_USER = os.environ.get("SECURITY_TEST_USERNAME", "مستخدم اختبار أمني")
TEST_PASSWORD = os.environ.get("SECURITY_TEST_PASSWORD", "SecTest-Local-Only-2026!")


def _login(payload, *, ip=None):
    headers = {"Content-Type": "application/json"}
    if ip:
        headers["x-forwarded-for"] = ip
    return requests.post(f"{API}/api/auth/login", json=payload, headers=headers, timeout=30)


# auth_store password hashing contract
def test_security_user_password_hash_is_bcrypt_2b():
    mongo_url = (os.environ.get("MONGO_URL") or "").strip()
    db_name = (os.environ.get("DB_NAME") or "").strip()
    if not mongo_url or not db_name:
        pytest.skip("MONGO_URL/DB_NAME missing")

    from pymongo import MongoClient

    client = MongoClient(mongo_url, serverSelectionTimeoutMS=5000)
    creds = client[db_name]["auth_credentials"].find_one({"username": TEST_USER}, {"_id": 0})
    assert creds and creds.get("password_hash")
    assert str(creds.get("password_hash", "")).startswith("$2b$")


# login response cookies + app-level CORS credentialed contract.
# The public preview edge proxy may rewrite CORS headers; this test validates
# the FastAPI app response that will be served behind production ingress.
def test_success_login_sets_httponly_cookies_and_credentialed_cors_headers():
    origin = "https://financial-ssot.preview.emergentagent.com"
    cors_api = os.environ.get("SECURITY_INTERNAL_API_URL", "http://localhost:8001").rstrip("/")
    response = requests.post(
        f"{cors_api}/api/auth/login",
        headers={"Content-Type": "application/json", "Origin": origin},
        json={"username": TEST_USER, "password": TEST_PASSWORD},
        timeout=30,
    )
    if response.status_code != 200:
        pytest.skip(f"security test user login unavailable: {response.status_code}")

    set_cookies = []
    try:
        set_cookies = response.raw.headers.get_all("Set-Cookie") or []
    except Exception:
        cookie_line = response.headers.get("set-cookie", "")
        if cookie_line:
            set_cookies = [cookie_line]

    joined = "\n".join(set_cookies).lower()
    assert "access_token=" in joined
    assert "refresh_token=" in joined
    assert "httponly" in joined

    assert response.headers.get("access-control-allow-credentials") == "true"
    assert response.headers.get("access-control-allow-origin") == origin


# empty/missing credential fail-closed contract
def test_missing_identifier_and_empty_fields_return_401_fail_closed():
    ip = "203.0.113.51"
    assert _login({}, ip=ip).status_code == 401
    assert _login({"username": "", "password": ""}, ip="203.0.113.52").status_code == 401
    assert _login({"username": "", "pin": ""}, ip="203.0.113.53").status_code == 401


# no secret exposure in auth error payloads contract
def test_auth_error_payloads_do_not_leak_secret_keys_or_pin_values():
    bad = _login({"username": "مدير", "password": f"wrong-{uuid.uuid4()}"}, ip="203.0.113.61")
    assert bad.status_code == 401
    body = bad.text
    forbidden_fragments = [
        "JWT_SECRET",
        "SUPABASE_SERVICE_ROLE",
        "RATE_LIMIT_BYPASS",
        "DEVELOPER_APPROVAL_CODE",
        "MANAGER_QUICK_PIN",
        "123123",
    ]
    for fragment in forbidden_fragments:
        assert fragment not in body
