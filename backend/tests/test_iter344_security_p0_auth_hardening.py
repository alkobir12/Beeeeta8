"""Iter344: Security P0 auth hardening contracts."""

import os
import sys
import time
import uuid
from pathlib import Path

import pytest
import requests

sys.path.append(str(Path(__file__).resolve().parents[1]))


API = (os.environ.get("REACT_APP_BACKEND_URL") or "").strip().rstrip("/")
if not API:
    env_file = Path("/app/frontend/.env")
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("REACT_APP_BACKEND_URL="):
                API = line.split("=", 1)[1].strip().rstrip("/")


TEST_USER = os.environ.get("SECURITY_TEST_USERNAME", "مستخدم اختبار أمني")
TEST_PASSWORD = os.environ.get("SECURITY_TEST_PASSWORD", "SecTest-Local-Only-2026!")


def _unique_test_ip() -> str:
    raw = uuid.uuid4().int
    return f"198.51.{(raw >> 8) % 255}.{raw % 255}"


def _login(payload, *, ip=None):
    headers = {"Content-Type": "application/json"}
    if ip:
        headers["x-forwarded-for"] = ip
    return requests.post(f"{API}/api/auth/login", json=payload, headers=headers, timeout=30)


@pytest.fixture(scope="session", autouse=True)
def _prepare_security_test_user():
    if not API:
        pytest.skip("REACT_APP_BACKEND_URL missing")
    import routes_users
    from core import auth_store
    import asyncio

    async def _prepare():
        rows = routes_users._read_users()
        if not any((r.get("name") == TEST_USER or r.get("username") == TEST_USER) for r in rows):
            rows.append({
                "id": str(uuid.uuid4()),
                "name": TEST_USER,
                "username": TEST_USER,
                "email": None,
                "phone": "0509990001",
                "role": "employee",
                "permissions": {},
                "isActive": True,
                "guidanceEnabled": True,
                "createdAt": "2026-08-11T00:00:00",
            })
            routes_users._write_users(rows)
        await auth_store.set_password(TEST_USER, TEST_PASSWORD)
        await auth_store.revoke_all_for_user(TEST_USER, reason="security_p0_test_reset")

    asyncio.run(_prepare())


def test_name_only_login_is_blocked_for_all_roles():
    ip = _unique_test_ip()
    assert _login({"username": "مدير"}, ip=ip).status_code == 401
    assert _login({"username": "احمد"}, ip=ip).status_code == 401
    assert _login({"username": TEST_USER}, ip=ip).status_code == 401


def test_default_or_shared_pin_login_is_blocked():
    ip = _unique_test_ip()
    retired_pin = (os.environ.get("MANAGER_QUICK_PIN") or "123123").strip().strip('"')
    assert _login({"username": "مدير", "pin": retired_pin}, ip=ip).status_code == 401
    assert _login({"username": "احمد", "pin": retired_pin}, ip=ip).status_code == 401


def test_empty_and_wrong_credentials_fail_closed():
    ip = _unique_test_ip()
    assert _login({"username": "مدير", "password": ""}, ip=ip).status_code == 401
    assert _login({"username": "مدير", "pin": ""}, ip=ip).status_code == 401
    assert _login({"username": "مدير", "password": f"wrong-{uuid.uuid4()}"}, ip=ip).status_code == 401


def test_valid_user_gets_own_non_admin_role_and_cannot_post_admin_finance_action():
    response = _login({"username": TEST_USER, "password": TEST_PASSWORD})
    assert response.status_code == 200, response.text[:300]
    data = response.json()
    assert data.get("role") == "employee"
    assert data.get("role") != "admin"
    token = data.get("access_token")
    assert token

    forbidden = requests.post(
        f"{API}/api/finance-actions/expense",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"description": "security p0 forbidden", "amount": 1},
        timeout=30,
    )
    assert forbidden.status_code == 403


def test_five_failed_attempts_trigger_lockout_or_rate_limit_and_do_not_leak_secrets():
    ip = _unique_test_ip()
    statuses = [
        _login({"username": "مدير", "password": f"bad-{idx}-{uuid.uuid4()}"}, ip=ip).status_code
        for idx in range(6)
    ]
    assert statuses[:5] == [401, 401, 401, 401, 401]
    assert statuses[-1] == 429

    body = _login({"username": "مدير", "pin": (os.environ.get("MANAGER_QUICK_PIN") or "123123")}, ip=_unique_test_ip()).text
    for forbidden in ["JWT_SECRET", "SUPABASE_SERVICE_ROLE", "RATE_LIMIT_BYPASS", "DEVELOPER_APPROVAL_CODE"]:
        assert forbidden not in body


def test_code_no_longer_seeds_quick_manager_or_allows_name_only_or_pin_bypass():
    auth_src = Path("/app/backend/auth_jwt.py").read_text(encoding="utf-8")
    server_src = Path("/app/backend/server.py").read_text(encoding="utf-8")
    assert "method = \"name_only\"" not in auth_src
    assert "quick_pin_login" not in auth_src
    assert "auth_store.ensure_pin" not in server_src
    assert "MANAGER_QUICK_PIN" not in server_src
