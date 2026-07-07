"""
Security Remediation Test Suite (iter 240)

Covers:
1. /api/auth/login deny-by-default + token issuance with embedded role
2. /api/auth/me + /api/auth/refresh
3. Impersonation defense — spoofed x-user-role headers ignored (finance-actions/expense, invoice, payment)
4. Valid admin JWT can post expense
5. Role-tiered RBAC (technician denied expense, accountant denied account delete, admin allowed)
6. No-JWT account delete -> 403
7. Four-Eyes runtime (approve/commit/rollback) requires approver JWT, denies non-approver/no-JWT
8. Regression: GET endpoints still return data with auth
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://accounting-engine-6.preview.emergentagent.com").rstrip("/")

USERS = {
    "admin": "مدير",
    "supervisor": "احمد1",
    "accountant": "فرج1",
    "technician": "مستخدم اختبار",
}


def _login(username: str) -> requests.Response:
    return requests.post(f"{BASE_URL}/api/auth/login", json={"username": username}, timeout=30)


@pytest.fixture(scope="session")
def tokens():
    out = {}
    for role, name in USERS.items():
        r = _login(name)
        assert r.status_code == 200, f"Login failed for {role}={name}: {r.status_code} {r.text[:200]}"
        data = r.json()
        out[role] = {
            "access": data["access_token"],
            "refresh": data.get("refresh_token"),
            "role": data.get("role"),
            "username": data.get("username"),
            "expires_in_minutes": data.get("expires_in_minutes"),
            "cookies": r.cookies,
        }
    return out


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ============================================================
# 1. LOGIN: deny-by-default + token issuance
# ============================================================
class TestLogin:
    def test_login_admin_returns_token_with_role(self, tokens):
        t = tokens["admin"]
        assert t["role"] == "admin"
        assert t["username"] == USERS["admin"]
        assert t["expires_in_minutes"] == 60
        assert isinstance(t["access"], str) and len(t["access"]) > 20
        assert isinstance(t["refresh"], str) and len(t["refresh"]) > 20

    def test_login_supervisor_role(self, tokens):
        assert tokens["supervisor"]["role"] == "supervisor"

    def test_login_accountant_role(self, tokens):
        assert tokens["accountant"]["role"] == "accountant"

    def test_login_technician_role(self, tokens):
        assert tokens["technician"]["role"] == "technician"

    def test_login_unknown_user_returns_401(self):
        r = _login("ghost_xyz_123")
        assert r.status_code == 401, f"Expected 401 for unknown user, got {r.status_code}: {r.text[:200]}"
        # No token should be issued
        body = r.json()
        assert "access_token" not in body

    def test_login_empty_username_returns_400(self):
        r = requests.post(f"{BASE_URL}/api/auth/login", json={"username": ""}, timeout=15)
        assert r.status_code == 400


# ============================================================
# 2. /api/auth/me + /api/auth/refresh
# ============================================================
class TestMeAndRefresh:
    def test_me_with_valid_token(self, tokens):
        r = requests.get(f"{BASE_URL}/api/auth/me", headers=_auth(tokens["admin"]["access"]), timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert body["username"] == USERS["admin"]
        assert body["role"] == "admin"
        assert "exp" in body

    def test_me_without_token_401(self):
        r = requests.get(f"{BASE_URL}/api/auth/me", timeout=15)
        assert r.status_code == 401

    def test_me_with_invalid_token_401(self):
        r = requests.get(f"{BASE_URL}/api/auth/me", headers=_auth("not.a.valid.jwt"), timeout=15)
        assert r.status_code == 401

    def test_refresh_via_bearer(self, tokens):
        # Use refresh token via Authorization header (Bearer)
        r = requests.post(
            f"{BASE_URL}/api/auth/refresh",
            headers=_auth(tokens["admin"]["refresh"]),
            timeout=15,
        )
        assert r.status_code == 200, f"refresh failed: {r.status_code} {r.text[:200]}"
        body = r.json()
        assert "access_token" in body
        assert body["role"] == "admin"
        assert body["username"] == USERS["admin"]

    def test_refresh_via_cookie(self, tokens):
        # Use refresh cookie (set during login)
        cookies = {"refresh_token": tokens["admin"]["refresh"]}
        r = requests.post(f"{BASE_URL}/api/auth/refresh", cookies=cookies, timeout=15)
        assert r.status_code == 200
        assert r.json()["role"] == "admin"

    def test_refresh_without_token_401(self):
        r = requests.post(f"{BASE_URL}/api/auth/refresh", timeout=15)
        assert r.status_code == 401


# ============================================================
# 3. IMPERSONATION: spoofed x-user-role header MUST be ignored
# ============================================================
class TestImpersonation:
    # NOTE: Use ASCII-only header values; requests/urllib3 cannot send unicode in headers
    SPOOF = {"x-user-role": "admin", "x-user-id": "spoof-admin"}

    def test_spoof_expense_no_jwt_403(self):
        r = requests.post(
            f"{BASE_URL}/api/finance-actions/expense",
            json={"description": "spoof test", "amount": 10, "category": "general"},
            headers=self.SPOOF, timeout=20,
        )
        assert r.status_code == 403, f"Spoof expense expected 403, got {r.status_code}: {r.text[:200]}"

    def test_spoof_invoice_no_jwt_403(self):
        r = requests.post(
            f"{BASE_URL}/api/finance-actions/invoice",
            json={"customer": "TEST_spoof", "total": 100, "payment_method": "cash"},
            headers=self.SPOOF, timeout=20,
        )
        assert r.status_code == 403, f"Spoof invoice expected 403, got {r.status_code}: {r.text[:200]}"

    def test_spoof_payment_no_jwt_403(self):
        r = requests.post(
            f"{BASE_URL}/api/finance-actions/payment",
            json={"customer": "TEST_spoof", "amount": 50, "payment_method": "cash"},
            headers=self.SPOOF, timeout=20,
        )
        assert r.status_code == 403, f"Spoof payment expected 403, got {r.status_code}: {r.text[:200]}"

    def test_no_jwt_no_headers_403(self):
        r = requests.post(
            f"{BASE_URL}/api/finance-actions/expense",
            json={"description": "no auth", "amount": 5},
            timeout=20,
        )
        assert r.status_code == 403


# ============================================================
# 4. Valid admin JWT can post expense
# ============================================================
class TestValidJWTPosting:
    def test_admin_jwt_post_expense(self, tokens):
        ref = f"TEST_iter240_{uuid.uuid4().hex[:8]}"
        r = requests.post(
            f"{BASE_URL}/api/finance-actions/expense",
            json={
                "description": "Security test expense",
                "amount": 12.34,
                "category": "general",
                "payment_method": "cash",
                "reference_id": ref,
            },
            headers=_auth(tokens["admin"]["access"]),
            timeout=30,
        )
        assert r.status_code == 200, f"admin expense should succeed: {r.status_code} {r.text[:300]}"
        body = r.json()
        # Accept either wrapped {success, data} or raw posted
        data = body.get("data", body)
        assert data.get("posted") is True, f"Expected posted=true: {body}"
        assert "journal_id" in data or "entry_id" in data or data.get("journal_id") is not None


# ============================================================
# 5. Role-tiered RBAC
# ============================================================
class TestRoleRBAC:
    def test_technician_denied_expense(self, tokens):
        r = requests.post(
            f"{BASE_URL}/api/finance-actions/expense",
            json={"description": "tech tries", "amount": 1, "category": "general"},
            headers=_auth(tokens["technician"]["access"]),
            timeout=20,
        )
        assert r.status_code == 403, f"technician should be denied: {r.status_code} {r.text[:200]}"

    def test_accountant_denied_account_delete(self, tokens):
        # Try delete on a non-existent id with accountant token → must be 403 (RBAC fail, not 404)
        r = requests.delete(
            f"{BASE_URL}/api/accounts/nonexistent-id-iter240",
            headers=_auth(tokens["accountant"]["access"]),
            timeout=20,
        )
        assert r.status_code == 403, f"accountant delete expected 403, got {r.status_code}: {r.text[:200]}"

    def test_admin_account_delete_passes_rbac(self, tokens):
        # Admin should pass RBAC; non-existent id returns 404 (RBAC allowed)
        r = requests.delete(
            f"{BASE_URL}/api/accounts/nonexistent-id-iter240-{uuid.uuid4().hex[:6]}",
            headers=_auth(tokens["admin"]["access"]),
            timeout=20,
        )
        assert r.status_code == 404, f"admin should pass RBAC (404 expected), got {r.status_code}: {r.text[:200]}"

    def test_no_jwt_account_delete_403(self):
        r = requests.delete(f"{BASE_URL}/api/accounts/nonexistent-id-iter240", timeout=15)
        assert r.status_code == 403, f"no-jwt delete expected 403, got {r.status_code}: {r.text[:200]}"


# ============================================================
# 6. Four-Eyes runtime: approve requires approver JWT
# ============================================================
class TestFourEyes:
    def test_no_jwt_approve_denied(self):
        r = requests.post(
            f"{BASE_URL}/api/runtime/approvals/nonexistent-draft-iter240/approve",
            json={}, timeout=15,
        )
        assert r.status_code in (401, 403), f"no-jwt approve expected 401/403, got {r.status_code}: {r.text[:200]}"

    def test_no_jwt_commit_denied(self):
        # commit endpoint lives under /api/runtime/drafts/{id}/commit
        r = requests.post(
            f"{BASE_URL}/api/runtime/drafts/nonexistent-draft-iter240/commit",
            json={}, timeout=15,
        )
        assert r.status_code in (401, 403)

    def test_no_jwt_rollback_denied(self):
        # rollback endpoint lives under /api/runtime/executions/{id}/rollback
        r = requests.post(
            f"{BASE_URL}/api/runtime/executions/nonexistent-exec-iter240/rollback",
            json={}, timeout=15,
        )
        assert r.status_code in (401, 403)

    def test_accountant_jwt_approve_denied(self, tokens):
        r = requests.post(
            f"{BASE_URL}/api/runtime/approvals/nonexistent-draft-iter240/approve",
            json={}, headers=_auth(tokens["accountant"]["access"]), timeout=15,
        )
        # accountant is NOT in approver roles → 403
        assert r.status_code == 403, f"accountant approve expected 403, got {r.status_code}: {r.text[:200]}"

    def test_technician_jwt_approve_denied(self, tokens):
        r = requests.post(
            f"{BASE_URL}/api/runtime/approvals/nonexistent-draft-iter240/approve",
            json={}, headers=_auth(tokens["technician"]["access"]), timeout=15,
        )
        assert r.status_code == 403, f"technician approve expected 403, got {r.status_code}: {r.text[:200]}"

    def test_admin_jwt_approve_passes_rbac(self, tokens):
        # Admin in approver_roles → RBAC passes → 404 (not_found) for nonexistent draft
        r = requests.post(
            f"{BASE_URL}/api/runtime/approvals/nonexistent-draft-iter240-{uuid.uuid4().hex[:6]}/approve",
            json={}, headers=_auth(tokens["admin"]["access"]), timeout=15,
        )
        # Acceptable: 404 (not found), or 400 (bad request). NOT 403.
        assert r.status_code != 403, f"admin approve should pass RBAC (not 403): {r.status_code} {r.text[:200]}"


# ============================================================
# 7. Regression: GET endpoints still return data with auth
# ============================================================
class TestRegressionGets:
    def test_accounts_get_with_auth(self, tokens):
        r = requests.get(f"{BASE_URL}/api/accounts", headers=_auth(tokens["admin"]["access"]), timeout=20)
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, (list, dict))

    def test_journal_entries_get_with_auth(self, tokens):
        r = requests.get(f"{BASE_URL}/api/journal-entries", headers=_auth(tokens["admin"]["access"]), timeout=20)
        assert r.status_code in (200, 404)  # 404 if endpoint slug differs

    def test_users_get_with_auth(self, tokens):
        r = requests.get(f"{BASE_URL}/api/users", headers=_auth(tokens["admin"]["access"]), timeout=20)
        assert r.status_code == 200


# ============================================================
# 8. CORS sanity check
# ============================================================
class TestCORS:
    def test_cors_backend_no_wildcard_with_credentials(self):
        """Verify the backend (uvicorn) returns a specific origin (not '*') with allow-credentials.
        NOTE: The edge proxy (Cloudflare) may inject its own CORS headers for OPTIONS; we test the
        backend behavior on POST to the public URL.
        """
        r = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": USERS["admin"]},
            headers={"Origin": "https://accounting-engine-6.preview.emergentagent.com"},
            timeout=15,
        )
        assert r.status_code == 200
        allow_origin = r.headers.get("access-control-allow-origin", "")
        allow_creds = r.headers.get("access-control-allow-credentials", "")
        # If the backend emits CORS headers, they must NOT be wildcard alongside credentials.
        if allow_origin:
            assert allow_origin != "*", (
                f"Backend must not return wildcard CORS with credentials. "
                f"allow-origin={allow_origin} allow-credentials={allow_creds}"
            )
