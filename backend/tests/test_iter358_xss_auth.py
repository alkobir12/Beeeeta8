"""Iteration 358 - XSS hardening + cookie auth contract regression tests."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://financial-ssot.preview.emergentagent.com").rstrip("/")

USERNAME = "احمد"
PASSWORD = "010101"


def _login():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"username": USERNAME, "password": PASSWORD}, timeout=20)
    return s, r


def test_login_returns_access_token_and_sets_httponly_cookies():
    s, r = _login()
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:300]}"
    body = r.json()
    assert "access_token" in body and isinstance(body["access_token"], str) and body["access_token"]
    cookies = {c.name: c for c in s.cookies}
    assert "access_token" in cookies, f"missing access_token cookie; got: {list(cookies)}"
    assert "refresh_token" in cookies, f"missing refresh_token cookie; got: {list(cookies)}"
    # httpOnly flag
    for name in ("access_token", "refresh_token"):
        c = cookies[name]
        rest = getattr(c, "_rest", {}) or {}
        keys = {k.lower() for k in rest.keys()}
        assert "httponly" in keys, f"{name} cookie is not HttpOnly (rest={rest})"


def test_me_works_with_cookies_only_no_bearer():
    s, r = _login()
    assert r.status_code == 200
    # Explicitly do NOT send Authorization header
    r2 = s.get(f"{BASE_URL}/api/auth/me", timeout=15)
    assert r2.status_code == 200, f"/me failed with cookies: {r2.status_code} {r2.text[:300]}"
    data = r2.json()
    assert data.get("username") == USERNAME
    assert "role" in data


def test_refresh_via_cookie_omits_refresh_token_in_body():
    s, r = _login()
    assert r.status_code == 200
    r2 = s.post(f"{BASE_URL}/api/auth/refresh", timeout=15)
    assert r2.status_code == 200, f"cookie refresh failed: {r2.status_code} {r2.text[:300]}"
    body = r2.json()
    assert "access_token" in body and body["access_token"]
    assert "refresh_token" not in body, f"XSS contract violated: refresh_token leaked in body via cookie refresh: {list(body.keys())}"
    # Cookie should be rotated (Set-Cookie present)
    set_cookie = r2.headers.get("set-cookie", "") or ""
    assert "refresh_token" in set_cookie.lower() or "access_token" in set_cookie.lower(), \
        f"expected Set-Cookie rotation, got headers: {dict(r2.headers)}"


def test_refresh_via_bearer_includes_refresh_token_in_body():
    # Login and grab refresh from cookie jar
    s, r = _login()
    assert r.status_code == 200
    refresh_cookie = None
    for c in s.cookies:
        if c.name == "refresh_token":
            refresh_cookie = c.value
    assert refresh_cookie, "no refresh_token cookie captured"
    # Fresh session with NO cookies, only Bearer header
    plain = requests.Session()
    r2 = plain.post(
        f"{BASE_URL}/api/auth/refresh",
        headers={"Authorization": f"Bearer {refresh_cookie}"},
        timeout=15,
    )
    assert r2.status_code == 200, f"bearer refresh failed: {r2.status_code} {r2.text[:300]}"
    body = r2.json()
    assert "access_token" in body and body["access_token"]
    assert "refresh_token" in body and body["refresh_token"], \
        f"API-client compatibility broken: bearer refresh missing refresh_token; keys={list(body.keys())}"


def test_logout_revokes_session_old_cookies_cannot_refresh():
    s, r = _login()
    assert r.status_code == 200
    # capture cookies before logout
    pre_cookies = requests.cookies.RequestsCookieJar()
    for c in s.cookies:
        pre_cookies.set_cookie(c)
    lo = s.post(f"{BASE_URL}/api/auth/logout", timeout=15)
    assert lo.status_code in (200, 204), f"logout unexpected: {lo.status_code} {lo.text[:300]}"
    # New session, replay the OLD refresh cookie
    replay = requests.Session()
    replay.cookies.update(pre_cookies)
    r2 = replay.post(f"{BASE_URL}/api/auth/refresh", timeout=15)
    assert r2.status_code == 401, f"revoked refresh should return 401, got {r2.status_code} {r2.text[:300]}"


# ---- Regression: finance balance sheet ----

def test_balance_sheet_balances():
    s, lr = _login()
    assert lr.status_code == 200
    r = s.get(
        f"{BASE_URL}/api/finance/reports/balance-sheet",
        params={"workshop_id": "finmodule-sync"},
        timeout=30,
    )
    assert r.status_code == 200, f"balance-sheet failed: {r.status_code} {r.text[:300]}"
    payload = r.json()
    data = payload.get("data", payload)
    totals = data.get("totals") or data
    assets = totals.get("assets") if isinstance(totals.get("assets"), (int, float)) else totals.get("total_assets")
    liab = totals.get("liabilities") if isinstance(totals.get("liabilities"), (int, float)) else totals.get("total_liabilities")
    equity = totals.get("equity") if isinstance(totals.get("equity"), (int, float)) else totals.get("total_equity")
    assert assets is not None and liab is not None and equity is not None, f"missing totals in: {data}"
    gap = round(float(assets) - (float(liab) + float(equity)), 2)
    assert abs(gap) < 0.01, f"balance sheet gap {gap}: assets={assets} L+E={float(liab)+float(equity)}"


# ---- Regression: AR summary canonical ----

def test_ar_summary_matches_customers_total():
    # authenticated call - assistant/dashboard likely requires auth
    s, r = _login()
    assert r.status_code == 200
    dash = s.get(f"{BASE_URL}/api/assistant/dashboard", timeout=30)
    assert dash.status_code == 200, f"assistant dashboard failed: {dash.status_code} {dash.text[:300]}"
    dash_json = dash.json()
    # assistant/dashboard shape: {success, data:{panels:[{id:"total_ar", value:...}]}}
    panels = (dash_json.get("data") or {}).get("panels") or []
    dash_ar = None
    for p in panels:
        if p.get("id") == "total_ar":
            dash_ar = p.get("value")
            break
    assert dash_ar is not None, f"total_ar panel not found: {panels}"

    cust = s.get(
        f"{BASE_URL}/api/finance/ar/customers",
        params={"workshop_id": "finmodule-sync", "as_of": "2026-12-31"},
        timeout=30,
    )
    assert cust.status_code == 200, f"ar customers failed: {cust.status_code} {cust.text[:300]}"
    cust_json = cust.json()
    cust_ar = (cust_json.get("data") or cust_json).get("total_ar")
    assert cust_ar is not None, f"total_ar not found in ar/customers payload"
    assert round(float(dash_ar) - float(cust_ar), 2) == 0.0, f"AR mismatch dashboard={dash_ar} customers={cust_ar}"
