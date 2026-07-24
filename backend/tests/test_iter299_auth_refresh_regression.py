"""Iter 299 — regression for /api/auth/refresh:
- cookie only
- bearer only
- stale-cookie + valid-bearer (previously caused 401 refresh_reuse_detected)
"""
import os
import requests
import pytest
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://stamp-approval-flow.preview.emergentagent.com").rstrip("/")
BYPASS = os.environ.get("RATE_LIMIT_BYPASS_TOKEN", "")

HDR = {"x-ratelimit-bypass": BYPASS, "Content-Type": "application/json"}

LOGIN_PAYLOAD = {"username": "مدير", "pin": "123123"}


def _login():
    r = requests.post(f"{BASE_URL}/api/auth/login", json=LOGIN_PAYLOAD, headers=HDR, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    data = r.json()
    assert data.get("access_token") and data.get("refresh_token")
    return data, r.cookies


def test_login_smoke():
    data, _ = _login()
    assert data["username"] == "مدير"


def test_refresh_cookie_only():
    _, cookies = _login()
    r = requests.post(f"{BASE_URL}/api/auth/refresh", headers=HDR, cookies=cookies, timeout=20)
    assert r.status_code == 200, f"cookie-only refresh failed: {r.status_code} {r.text}"
    j = r.json()
    assert j.get("access_token") and j.get("refresh_token")


def test_refresh_bearer_only():
    data, _ = _login()
    h = {**HDR, "Authorization": f"Bearer {data['refresh_token']}"}
    r = requests.post(f"{BASE_URL}/api/auth/refresh", headers=h, timeout=20)
    assert r.status_code == 200, f"bearer-only refresh failed: {r.status_code} {r.text}"
    j = r.json()
    assert j.get("access_token")


def test_refresh_stale_cookie_plus_valid_bearer():
    """The important case: cookie holds an old (rotated) refresh token, Authorization holds the new one."""
    data, cookies = _login()
    # rotate once using bearer → new refresh_token; cookie still holds the old one (server sets new cookie in resp, but we keep original session cookies)
    r1 = requests.post(f"{BASE_URL}/api/auth/refresh",
                       headers={**HDR, "Authorization": f"Bearer {data['refresh_token']}"},
                       timeout=20)
    assert r1.status_code == 200, r1.text
    new_refresh = r1.json()["refresh_token"]

    # Now craft request: old cookie + new bearer
    r2 = requests.post(f"{BASE_URL}/api/auth/refresh",
                       headers={**HDR, "Authorization": f"Bearer {new_refresh}"},
                       cookies=cookies,  # original (now stale) refresh_token cookie
                       timeout=20)
    assert r2.status_code == 200, f"stale-cookie+valid-bearer refresh failed: {r2.status_code} {r2.text}"
    j = r2.json()
    assert j.get("access_token") and j.get("refresh_token")


def test_refresh_no_creds_returns_401():
    r = requests.post(f"{BASE_URL}/api/auth/refresh", headers=HDR, timeout=20)
    assert r.status_code == 401
