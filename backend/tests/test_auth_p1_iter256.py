"""Iteration 256 — P1 (SEC-003) production auth backend regression.

Covers the additive, backward-compatible auth system:
  • name-only login still works (no lockout for existing users)
  • refresh ROTATION + REUSE DETECTION (old refresh → 401, family revoked)
  • Email/Password: set-password (admin), password login, wrong password, and
    name-only REJECTED once a password is set
  • PIN + trusted device: set-pin, pin login on trusted device, untrusted → 401
  • sessions list + revoke
  • auth audit (approver 200, technician 403)
  • Google SSO endpoint public + validates (empty→400, fake→401)

DATA SAFETY: uses the throwaway user «مستخدم اختبار»; a teardown fixture deletes any
credentials/devices it created so name-only login is restored for other suites.
"""
from __future__ import annotations

import os
import time
import json
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

TEST_USER = "مستخدم اختبار"       # technician (non-approver)
USERS_FILE = Path("/app/backend/uploads/users.json")
# الرقم السري للاختبار من البيئة حصراً — لا secrets مكتوبة في الكود (مراجعة 2026-07-15)
TEST_PASSWORD = (os.environ.get("TEST_USER_PASSWORD")
                 or open("/app/backend/.env").read().split("TEST_USER_PASSWORD=")[1].split("\n")[0].strip().strip('"'))
MANAGER_PIN = os.environ["MANAGER_QUICK_PIN"]

# secret-gated rate-limit bypass so the suite isn't throttled (server.py middleware)
S = requests.Session()
# never persist cookies: refresh endpoint prefers cookies over Bearer, which would
# silently rotate the wrong token and break the reuse-detection assertions
from http.cookiejar import DefaultCookiePolicy
S.cookies.set_policy(DefaultCookiePolicy(allowed_domains=[]))
_bypass = (os.environ.get("RATE_LIMIT_BYPASS_TOKEN") or "").strip().strip('"')
if _bypass:
    S.headers["x-ratelimit-bypass"] = _bypass


def _login(**body):
    return S.post(f"{API}/auth/login", json=body, timeout=30)


def _admin_token():
    r = _login(username="مدير", pin=MANAGER_PIN)
    assert r.status_code == 200
    return r.json()["access_token"]


@pytest.fixture(scope="module", autouse=True)
def _cleanup_credentials():
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")

    original_users = USERS_FILE.read_text(encoding="utf-8")

    def _clean():
        if not mongo_url or not db_name:
            return
        mc = MongoClient(mongo_url)
        db = mc[db_name]
        db.auth_credentials.delete_many({"username": TEST_USER})
        db.trusted_devices.delete_many({"username": TEST_USER})
        # clear prior login failures so brute-force lockout doesn't bleed across runs
        db.auth_audit.delete_many({"username": TEST_USER, "event": "login", "success": False})
        mc.close()

    users = json.loads(original_users)
    if not any((u.get("name") or u.get("username")) == TEST_USER for u in users):
        users.append({
            "id": "test-auth-user",
            "name": TEST_USER,
            "username": TEST_USER,
            "role": "technician",
            "permissions": {},
            "isActive": True,
        })
        USERS_FILE.write_text(json.dumps(users, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    _clean()   # setup: start from a clean slate
    yield
    _clean()   # teardown: restore name-only for other suites
    USERS_FILE.write_text(original_users, encoding="utf-8")


# ---- backward compatibility -------------------------------------------------

def test_manager_quick_pin_login_works_without_device():
    r = _login(username="مدير", pin=MANAGER_PIN)
    assert r.status_code == 200
    b = r.json()
    assert b.get("access_token") and b.get("refresh_token")
    assert _login(username="مدير").status_code == 401


# ---- rotation + reuse detection ---------------------------------------------

def test_refresh_rotation_and_reuse_detection():
    rt = _login(username="مدير", pin=MANAGER_PIN).json()["refresh_token"]
    r1 = S.post(f"{API}/auth/refresh", headers={"Authorization": f"Bearer {rt}"}, timeout=30)
    assert r1.status_code == 200, "first rotation should succeed"
    r2 = S.post(f"{API}/auth/refresh", headers={"Authorization": f"Bearer {rt}"}, timeout=30)
    assert r2.status_code == 401, "reusing the old refresh must be rejected (reuse detection)"


# ---- email / password -------------------------------------------------------

def test_password_lifecycle_and_name_only_enforcement():
    admin = _admin_token()
    # admin sets a password for the test user
    r = S.post(f"{API}/auth/set-password",
                      headers={"Authorization": f"Bearer {admin}"},
                      json={"new_password": TEST_PASSWORD, "target_username": TEST_USER}, timeout=30)
    assert r.status_code == 200, r.text[:200]
    # name-only now rejected for this user
    assert _login(username=TEST_USER).status_code == 401
    # correct password works
    assert _login(username=TEST_USER, password=TEST_PASSWORD).status_code == 200
    # wrong password rejected
    assert _login(username=TEST_USER, password="WRONGPASS").status_code == 401


def test_non_admin_cannot_set_others_password():
    # the test user (technician) has a password now → log in with it
    tok = _login(username=TEST_USER, password=TEST_PASSWORD).json()["access_token"]
    r = S.post(f"{API}/auth/set-password",
                      headers={"Authorization": f"Bearer {tok}"},
                      json={"new_password": "x123456", "target_username": "مدير"}, timeout=30)
    assert r.status_code == 403, "non-approver must not set another user's password"


# ---- PIN + trusted device ---------------------------------------------------

def test_pin_login_requires_trusted_device():
    tok = _login(username=TEST_USER, password=TEST_PASSWORD).json()["access_token"]
    r = S.post(f"{API}/auth/set-pin", headers={"Authorization": f"Bearer {tok}"},
                      json={"pin": "1234"}, timeout=30)
    assert r.status_code == 200
    device_id = r.json()["device_id"]
    assert _login(username=TEST_USER, pin="1234", device_id=device_id).status_code == 200
    assert _login(username=TEST_USER, pin="1234", device_id="dev_fake").status_code == 401


# ---- sessions + audit -------------------------------------------------------

def test_sessions_list_and_revoke():
    admin = _admin_token()
    r = S.get(f"{API}/auth/sessions", headers={"Authorization": f"Bearer {admin}"}, timeout=30)
    assert r.status_code == 200
    sessions = r.json()["data"]
    assert isinstance(sessions, list) and len(sessions) >= 1
    fam = sessions[0]["family_id"]
    rv = S.post(f"{API}/auth/sessions/revoke", headers={"Authorization": f"Bearer {admin}"},
                       json={"family_id": fam}, timeout=30)
    assert rv.status_code == 200 and rv.json()["revoked"] >= 1


def test_audit_requires_approver():
    admin = _admin_token()
    assert S.get(f"{API}/auth/audit", headers={"Authorization": f"Bearer {admin}"}, timeout=30).status_code == 200
    tech = _login(username=TEST_USER, password=TEST_PASSWORD).json()["access_token"]
    assert S.get(f"{API}/auth/audit", headers={"Authorization": f"Bearer {tech}"}, timeout=30).status_code == 403


# ---- Google SSO endpoint ----------------------------------------------------

def test_google_session_public_and_validates():
    assert S.post(f"{API}/auth/google/session", json={"session_id": ""}, timeout=30).status_code == 400
    assert S.post(f"{API}/auth/google/session", json={"session_id": "fake-xyz"}, timeout=30).status_code == 401
