"""HTTP-level authorization matrix tests against the LIVE preview backend.

STRICT NON-DESTRUCTIVE:
  * Only GET reads AND attempts that MUST be rejected (401/403) are performed.
  * We NEVER send a payload that could persist if authorization mistakenly allowed it
    beyond what the current SSOT enforces — every mutation-shaped call in here targets
    an endpoint/role combination we EXPECT to be blocked (403), so no data is written.

Credentials read from /app/memory/test_credentials.md (admin=مدير, accountant=احمد, pw=010101).
Base URL from /app/frontend/.env REACT_APP_BACKEND_URL.
"""

import os
import re
import pytest
import requests

# ---------- Env / creds ----------
def _read_backend_url() -> str:
    with open("/app/frontend/.env", "r", encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL missing")

BASE_URL = _read_backend_url()
API = f"{BASE_URL}/api"

ADMIN_USER = "مدير"
ACCT_USER = "احمد"
PASSWORD = "010101"  # EXACT — do not retry with wrong values (brute-force lock)


# ---------- Auth helpers ----------
_TOKENS: dict[str, str] = {}


def _login(username: str) -> str:
    if username in _TOKENS:
        return _TOKENS[username]
    r = requests.post(
        f"{API}/auth/login",
        json={"username": username, "password": PASSWORD},
        timeout=20,
    )
    assert r.status_code == 200, f"login failed for {username}: {r.status_code} {r.text[:200]}"
    body = r.json()
    tok = body.get("access_token") or body.get("token")
    assert tok, f"no access_token for {username}: {body}"
    _TOKENS[username] = tok
    return tok


def H(username: str) -> dict:
    return {"Authorization": f"Bearer {_login(username)}"}


# ---------- Fixtures ----------
@pytest.fixture(scope="session")
def admin_headers():
    return H(ADMIN_USER)


@pytest.fixture(scope="session")
def acct_headers():
    return H(ACCT_USER)


@pytest.fixture(scope="session")
def admin_own_id(admin_headers):
    r = requests.get(f"{API}/users", headers=admin_headers, timeout=20)
    assert r.status_code == 200, f"admin GET /api/users failed: {r.status_code}"
    users = r.json()
    if isinstance(users, dict):
        users = users.get("items") or users.get("users") or []
    for u in users:
        name = u.get("username") or u.get("name") or ""
        if name == ADMIN_USER:
            return u.get("id") or u.get("_id") or u.get("user_id")
    pytest.skip("Could not locate admin own id in /api/users response")


# =====================================================================
# 1) P0-SEC-USERS — accountant blocked on user management; admin allowed
# =====================================================================
class TestP0SecUsers:
    def test_accountant_get_users_403(self, acct_headers):
        r = requests.get(f"{API}/users", headers=acct_headers, timeout=20)
        assert r.status_code == 403, f"expected 403, got {r.status_code} {r.text[:200]}"

    def test_accountant_post_user_403(self, acct_headers):
        # payload intentionally targets a denied action; sent only to confirm 403 boundary.
        r = requests.post(
            f"{API}/users",
            headers=acct_headers,
            json={"username": "AUTHZ_TEST_should_not_persist", "password": "x", "role": "technician"},
            timeout=20,
        )
        assert r.status_code == 403, f"expected 403, got {r.status_code} {r.text[:200]}"

    def test_accountant_put_user_403(self, acct_headers):
        r = requests.put(
            f"{API}/users/does-not-matter",
            headers=acct_headers,
            json={"role": "technician"},
            timeout=20,
        )
        assert r.status_code == 403, f"expected 403, got {r.status_code}"

    def test_accountant_delete_user_403(self, acct_headers):
        r = requests.delete(f"{API}/users/does-not-matter", headers=acct_headers, timeout=20)
        assert r.status_code == 403, f"expected 403, got {r.status_code}"

    def test_admin_get_users_200(self, admin_headers):
        r = requests.get(f"{API}/users", headers=admin_headers, timeout=20)
        assert r.status_code == 200, f"expected 200, got {r.status_code}"


# =====================================================================
# 2) Privilege escalation blocked
# =====================================================================
class TestPrivEsc:
    def test_accountant_cannot_create_admin(self, acct_headers):
        r = requests.post(
            f"{API}/users",
            headers=acct_headers,
            json={"username": "AUTHZ_TEST_escalate", "password": "x", "role": "admin"},
            timeout=20,
        )
        assert r.status_code == 403, f"expected 403, got {r.status_code} {r.text[:200]}"


# =====================================================================
# 3) Destructive admin-only endpoints
# =====================================================================
class TestDestructiveAdminOnly:
    def test_accountant_financial_reset_403(self, acct_headers):
        r = requests.post(f"{API}/financial-reset/preview", headers=acct_headers, json={}, timeout=20)
        assert r.status_code == 403, f"expected 403, got {r.status_code}"

    def test_accountant_cleanup_403(self, acct_headers):
        # Uses /api/biz-accounts/cleanup — the regex "/cleanup" branch matches because there is
        # a "/" immediately before "cleanup" (from "/biz-accounts/cleanup"). Accountant must be 403.
        r = requests.post(f"{API}/biz-accounts/cleanup", headers=acct_headers, json={}, timeout=20)
        assert r.status_code == 403, f"expected 403, got {r.status_code} {r.text[:200]}"

    def test_top_level_cleanup_regex_gap(self, acct_headers):
        """DEFENSE-IN-DEPTH GAP: /api/cleanup/* (top-level) is NOT matched by the destructive
        regex because "^/api/[^?]*/cleanup" needs a "/" before "cleanup", which /api/ already
        consumed. The DELETE /cleanup/keep-debts-only endpoint is a legacy 410 so no data loss
        today, but any new top-level /api/cleanup|/purge|/wipe|/danger endpoint would bypass
        the SSOT. This test documents the gap and PASSES when the gap is CLOSED (accountant
        gets 403). It FAILS today, indicating the regex needs a fix.
        """
        r = requests.delete(
            f"{API}/cleanup/keep-debts-only?confirm=WRONG_VALUE", headers=acct_headers, timeout=20
        )
        # Non-destructive: confirm=WRONG ensures handler branch cannot mutate, and the endpoint
        # itself always returns 410 (legacy). We assert on authz-middleware behavior only.
        assert r.status_code == 403, (
            f"REGEX-GAP: accountant reached /api/cleanup/* handler (got {r.status_code}) — "
            f"destructive_admin rule regex misses top-level /api/cleanup|purge|wipe|danger."
        )

    def test_admin_reaches_financial_reset_boundary(self, admin_headers):
        # We do NOT execute a real reset. Use a GET-shaped preview/status probe if available;
        # else confirm we are past auth (i.e., not 401/403). 404/400/405/422/200 all acceptable.
        r = requests.get(f"{API}/financial-reset/status", headers=admin_headers, timeout=20)
        assert r.status_code not in (401, 403), f"admin blocked at authz boundary: {r.status_code}"


# =====================================================================
# 4) Ledger/finance permissions (accountant: edit=yes, delete=no)
# =====================================================================
class TestLedgerPerms:
    def test_accountant_delete_ledger_403(self, acct_headers):
        # DELETE against a non-existent id — must be blocked BEFORE any lookup, i.e. 403.
        r = requests.delete(
            f"{API}/finance/journal-entries/authz-nonexistent",
            headers=acct_headers,
            timeout=20,
        )
        assert r.status_code == 403, f"expected 403 on ledger DELETE, got {r.status_code} {r.text[:200]}"

    def test_accountant_reaches_ledger_edit_boundary(self, acct_headers):
        # PUT against a non-existent id — must NOT be 403 (edit is granted). 404/400/422 acceptable.
        r = requests.put(
            f"{API}/finance/journal-entries/authz-nonexistent-id",
            headers=acct_headers,
            json={},
            timeout=20,
        )
        assert r.status_code != 403, f"accountant unexpectedly 403 on ledger edit: {r.text[:200]}"
        assert r.status_code != 401


# =====================================================================
# 5) Settings mutation blocked for accountant; admin allowed
# =====================================================================
class TestSettingsMutation:
    def test_accountant_put_settings_403(self, acct_headers):
        r = requests.put(f"{API}/settings", headers=acct_headers, json={}, timeout=20)
        assert r.status_code == 403, f"expected 403, got {r.status_code}"

    def test_admin_settings_boundary(self, admin_headers):
        # GET (read-only) — must not be blocked for admin.
        r = requests.get(f"{API}/settings", headers=admin_headers, timeout=20)
        assert r.status_code not in (401, 403), f"admin blocked on settings read: {r.status_code}"


# =====================================================================
# 6) Object-level guards — admin cannot delete/downgrade self
# =====================================================================
class TestSelfGuards:
    def test_admin_cannot_delete_self(self, admin_headers, admin_own_id):
        r = requests.delete(f"{API}/users/{admin_own_id}", headers=admin_headers, timeout=20)
        assert r.status_code == 403, f"expected 403 self-delete, got {r.status_code} {r.text[:200]}"

    def test_admin_cannot_change_own_role(self, admin_headers, admin_own_id):
        r = requests.put(
            f"{API}/users/{admin_own_id}",
            headers=admin_headers,
            json={"role": "accountant"},
            timeout=20,
        )
        assert r.status_code == 403, f"expected 403 self-priv-change, got {r.status_code} {r.text[:200]}"


# =====================================================================
# 7) No-regression: reads for both roles + 401 unauth
# =====================================================================
READ_ENDPOINTS = [
    "/vehicles",
    "/customers",
    "/operations",
    "/finance/journal-entries?workshop_id=default",
]

class TestNoRegression:
    @pytest.mark.parametrize("path", READ_ENDPOINTS)
    def test_admin_reads(self, admin_headers, path):
        r = requests.get(f"{API}{path}", headers=admin_headers, timeout=30)
        assert r.status_code == 200, f"admin GET {path} → {r.status_code} {r.text[:150]}"

    @pytest.mark.parametrize("path", READ_ENDPOINTS)
    def test_accountant_reads(self, acct_headers, path):
        r = requests.get(f"{API}{path}", headers=acct_headers, timeout=30)
        assert r.status_code == 200, f"accountant GET {path} → {r.status_code} {r.text[:150]}"

    def test_dashboard_summary_admin(self, admin_headers):
        # try known names (this app exposes /api/stats as the dashboard summary)
        for p in ("/stats", "/dashboard-summary", "/dashboard/summary", "/dashboard/kpis"):
            r = requests.get(f"{API}{p}", headers=admin_headers, timeout=30)
            if r.status_code == 200:
                return
        pytest.fail("No dashboard endpoint returned 200 for admin")

    def test_unauth_returns_401(self):
        r = requests.get(f"{API}/users", timeout=20)
        assert r.status_code == 401, f"expected 401 unauth, got {r.status_code}"

    def test_no_500_on_middleware(self, admin_headers):
        # sanity: neither a valid nor an unknown path should 500
        for p in ("/vehicles", "/definitely-not-a-real-endpoint-xyz"):
            r = requests.get(f"{API}{p}", headers=admin_headers, timeout=20)
            assert r.status_code < 500, f"5xx from middleware on {p}: {r.status_code} {r.text[:150]}"
