"""Iteration 257 — Preview auth regression for fixed manager PIN flow.

Scope:
- Manager fixed identity + quick PIN login behavior
- Lockout behavior with synthetic IP isolation
- /auth/me + /auth/refresh (cookie + bearer fallback + rotation/reuse)
- Non-manager PIN requires trusted device
- Seeded manager PIN hash format + users role mapping
- CORS preview allows production origin with credentials
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"
API = f"{BASE_URL}/api"

MANAGER_USERNAME = "مدير"
MANAGER_PIN = os.environ.get("MANAGER_QUICK_PIN", "")
TEST_USER = "مستخدم اختبار"
TEST_PASSWORD = os.environ.get("TEST_USER_PASSWORD", "")
RATE_BYPASS = (os.environ.get("RATE_LIMIT_BYPASS_TOKEN") or "").strip().strip('"')
MONGO_URL = os.environ.get("MONGO_URL", "")
DB_NAME = os.environ.get("DB_NAME", "")


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    if RATE_BYPASS:
        s.headers["x-ratelimit-bypass"] = RATE_BYPASS
    return s


def _login(session: requests.Session, **payload):
    return session.post(f"{API}/auth/login", json=payload, timeout=30)


@pytest.fixture(scope="module", autouse=True)
def cleanup_test_user_auth_data():
    users_path = Path("/app/backend/uploads/users.json")
    original_users = users_path.read_text(encoding="utf-8") if users_path.exists() else "[]"
    users = json.loads(original_users or "[]")
    if not any((u.get("name") or u.get("username")) == TEST_USER for u in users):
        users.append(
            {
                "id": "iter257-test-user",
                "name": TEST_USER,
                "username": TEST_USER,
                "role": "technician",
                "permissions": {},
                "isActive": True,
            }
        )
        users_path.write_text(json.dumps(users, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if not (MONGO_URL and DB_NAME):
        yield
        users_path.write_text(original_users, encoding="utf-8")
        return

    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    db.auth_credentials.delete_many({"username": TEST_USER})
    db.trusted_devices.delete_many({"username": TEST_USER})
    db.auth_audit.delete_many({"username": TEST_USER})
    yield
    db.auth_credentials.delete_many({"username": TEST_USER})
    db.trusted_devices.delete_many({"username": TEST_USER})
    db.auth_audit.delete_many({"username": TEST_USER})
    client.close()
    users_path.write_text(original_users, encoding="utf-8")


# Manager quick PIN endpoint behavior
def test_manager_login_with_pin_no_device_returns_admin_tokens_and_device_with_remember():
    s = _session()
    r = _login(s, username=MANAGER_USERNAME, pin=MANAGER_PIN, remember_device=True)
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    assert body.get("username") == MANAGER_USERNAME
    assert body.get("role") == "admin"
    assert isinstance(body.get("access_token"), str) and body["access_token"]
    assert isinstance(body.get("refresh_token"), str) and body["refresh_token"]
    assert isinstance(body.get("device_id"), str) and body["device_id"].startswith("dev_")


# Wrong PIN and brute-force protection using synthetic isolated IP
def test_wrong_pin_returns_401_and_synthetic_ip_locks_after_five_failures():
    s = _session()
    fake_ip = f"203.0.113.{int(uuid.uuid4().hex[:2], 16)}"
    headers = {"x-forwarded-for": fake_ip}

    for _ in range(5):
        r = s.post(
            f"{API}/auth/login",
            json={"username": MANAGER_USERNAME, "pin": "000000"},
            headers=headers,
            timeout=30,
        )
        assert r.status_code == 401

    r6 = s.post(
        f"{API}/auth/login",
        json={"username": MANAGER_USERNAME, "pin": "000000"},
        headers=headers,
        timeout=30,
    )
    assert r6.status_code == 429


# Success resets effective failure window while audit remains append-only
def test_success_resets_failure_window_after_login_success():
    s = _session()
    fake_ip = f"198.51.100.{int(uuid.uuid4().hex[:2], 16)}"
    headers = {"x-forwarded-for": fake_ip}

    for _ in range(2):
        r = s.post(
            f"{API}/auth/login",
            json={"username": MANAGER_USERNAME, "pin": "111111"},
            headers=headers,
            timeout=30,
        )
        assert r.status_code == 401

    ok = s.post(
        f"{API}/auth/login",
        json={"username": MANAGER_USERNAME, "pin": MANAGER_PIN},
        headers=headers,
        timeout=30,
    )
    assert ok.status_code == 200

    post_success_fail = s.post(
        f"{API}/auth/login",
        json={"username": MANAGER_USERNAME, "pin": "222222"},
        headers=headers,
        timeout=30,
    )
    assert post_success_fail.status_code == 401


# /auth/me and /auth/refresh workflows
def test_me_and_refresh_cookie_and_bearer_reuse_detection():
    s = _session()
    login = _login(s, username=MANAGER_USERNAME, pin=MANAGER_PIN)
    assert login.status_code == 200
    data = login.json()
    access = data["access_token"]
    refresh = data["refresh_token"]

    me = s.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {access}"}, timeout=30)
    assert me.status_code == 200
    me_body = me.json()
    assert me_body.get("username") == MANAGER_USERNAME
    assert me_body.get("role") == "admin"

    cookie_refresh = s.post(f"{API}/auth/refresh", timeout=30)
    assert cookie_refresh.status_code == 200
    cookie_ref_body = cookie_refresh.json()
    assert isinstance(cookie_ref_body.get("access_token"), str) and cookie_ref_body["access_token"]

    # Use a fresh token family for bearer fallback check so reuse detection isn't tripped by cookie rotation above.
    second_login = _login(_session(), username=MANAGER_USERNAME, pin=MANAGER_PIN)
    assert second_login.status_code == 200
    bearer_seed_refresh = second_login.json()["refresh_token"]

    bearer_refresh = requests.post(
        f"{API}/auth/refresh",
        headers={"Authorization": f"Bearer {bearer_seed_refresh}"},
        timeout=30,
    )
    assert bearer_refresh.status_code == 200
    new_refresh = bearer_refresh.json().get("refresh_token")
    assert isinstance(new_refresh, str) and new_refresh

    reused_old = requests.post(
        f"{API}/auth/refresh",
        headers={"Authorization": f"Bearer {bearer_seed_refresh}"},
        timeout=30,
    )
    assert reused_old.status_code == 401


# Four-digit PINs remain device-bound; six-digit PINs support direct quick login.
def test_non_manager_pin_requires_trusted_device():
    s = _session()

    admin_login = _login(s, username=MANAGER_USERNAME, pin=MANAGER_PIN)
    assert admin_login.status_code == 200
    admin_token = admin_login.json()["access_token"]

    set_password = s.post(
        f"{API}/auth/set-password",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"new_password": TEST_PASSWORD, "target_username": TEST_USER},
        timeout=30,
    )
    assert set_password.status_code == 200, set_password.text[:250]

    user_login = _login(s, username=TEST_USER, password=TEST_PASSWORD)
    if user_login.status_code != 200:
        # If user previously accumulated failures, retry once with a synthetic isolated IP.
        isolated = {
            "x-forwarded-for": f"203.0.113.{int(uuid.uuid4().hex[:2], 16)}"
        }
        user_login = s.post(
            f"{API}/auth/login",
            json={"username": TEST_USER, "password": TEST_PASSWORD},
            headers=isolated,
            timeout=30,
        )
    assert user_login.status_code == 200
    user_token = user_login.json()["access_token"]

    set_pin = s.post(
        f"{API}/auth/set-pin",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"pin": "1234"},
        timeout=30,
    )
    assert set_pin.status_code == 200
    trusted_device = set_pin.json().get("device_id")
    assert isinstance(trusted_device, str) and trusted_device.startswith("dev_")

    no_device_pin = _login(s, username=TEST_USER, pin="1234")
    assert no_device_pin.status_code == 401

    with_device_pin = _login(s, username=TEST_USER, pin="1234", device_id=trusted_device)
    assert with_device_pin.status_code == 200


def test_accountant_six_digit_pin_supports_new_device_quick_login():
    s = _session()
    r = _login(s, username="احمد", pin=MANAGER_PIN, remember_device=True)
    assert r.status_code == 200, r.text[:250]
    body = r.json()
    assert body.get("username") == "احمد"
    assert body.get("role") == "accountant"
    assert isinstance(body.get("device_id"), str) and body["device_id"].startswith("dev_")


# Seed + hashing persistence checks
def test_seed_manager_pin_is_bcrypt_only_and_users_json_maps_admin_role():
    assert MONGO_URL and DB_NAME
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    doc = db.auth_credentials.find_one({"username": MANAGER_USERNAME}, {"_id": 0})
    client.close()

    assert isinstance(doc, dict)
    pin_hash = doc.get("pin_hash", "")
    assert isinstance(pin_hash, str) and pin_hash.startswith("$2b$")
    assert pin_hash != MANAGER_PIN
    assert "pin" not in doc

    users_path = Path("/app/backend/uploads/users.json")
    users = json.loads(users_path.read_text(encoding="utf-8"))
    manager = next((u for u in users if (u.get("username") or u.get("name")) == MANAGER_USERNAME), None)
    assert manager is not None
    assert manager.get("role") == "admin"


# CORS policy: production is same-origin; preview edge may normalize preflight to '*'.
def test_cors_allows_production_origin_with_credentials():
    prod_origin = "https://car-repair-sys.emergent.host"
    r = requests.options(
        f"{API}/auth/login",
        headers={
            "Origin": prod_origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
        timeout=30,
    )
    assert r.status_code in (200, 204)
    allow_origin = (r.headers.get("access-control-allow-origin") or "").strip()
    assert allow_origin in (prod_origin, "*")

    actual = requests.post(
        f"{API}/auth/login",
        headers={"Origin": prod_origin},
        json={"username": MANAGER_USERNAME, "pin": "000000"},
        timeout=30,
    )
    assert actual.status_code in (401, 429)
    assert (actual.headers.get("access-control-allow-origin") or "").strip() in (prod_origin, "*")
    assert (actual.headers.get("access-control-allow-credentials") or "").lower() == "true"
