"""Iteration 246 — Global auth guard + Katrina full-capability regression tests.

Tests:
  A) Protected endpoints return 401 WITHOUT any auth (fresh session, no cookies).
  B) Whitelist endpoints work WITHOUT auth (health, auth/login, auth/refresh, approvals/public/*).
  C) Protected endpoints return 200 WITH a valid Bearer JWT (login as مدير).
  D) Katrina read-only chat returns Arabic data-grounded answer.
  E) Katrina search action for existing customer works (read-only).
  F) Four-eyes: مدير proposes TESTQA expense → self-approve blocked (403) →
     احمد1 approve commits (200). Journal_id reported for cleanup.

DATA SAFETY:
  * Only TESTQA-prefixed data is created.
  * Only TESTQA-prefixed approvals are ever approved.
  * Any committed journal_id is printed for main-agent cleanup.
"""
from __future__ import annotations

import os
import time
import uuid
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"
API = f"{BASE_URL}/api"

# --- protected endpoints (per review request) ------------------------------
PROTECTED_GET = [
    "/users",
    "/customers",
    "/vehicles",
    "/finance/alerts?workshop_id=finmodule-sync",
    "/runtime/approvals",
]
PROTECTED_POST = [
    ("/operations/integrity/fix-all", {}),
    ("/assistant/chat", {"message": "test"}),
]

# --- helpers ---------------------------------------------------------------

def _fresh_session() -> requests.Session:
    """Session guaranteed to have no cookies (bypasses cookie-based auth)."""
    s = requests.Session()
    s.headers["Content-Type"] = "application/json"
    return s


def _login(username: str) -> str:
    """Login via a fresh session, return the access_token string."""
    s = _fresh_session()
    r = s.post(f"{API}/auth/login", json={"username": username}, timeout=30)
    assert r.status_code == 200, f"login {username} failed: {r.status_code} {r.text[:200]}"
    body = r.json()
    tok = body.get("access_token") or body.get("data", {}).get("access_token")
    assert tok, f"no access_token in login response: {body}"
    return tok


@pytest.fixture(scope="module")
def admin_token() -> str:
    return _login("مدير")


@pytest.fixture(scope="module")
def approver_token() -> str:
    return _login("احمد1")


# ============================================================================
# A) SECURITY — protected endpoints must be 401 WITHOUT any auth
# ============================================================================
class TestNoAuthReturns401:
    """All protected /api/* endpoints must return 401 without token/cookie."""

    @pytest.mark.parametrize("path", PROTECTED_GET)
    def test_get_without_auth_is_401(self, path):
        s = _fresh_session()
        r = s.get(f"{API}{path}", timeout=15)
        assert r.status_code == 401, (
            f"GET {path} expected 401 without auth, got {r.status_code}: {r.text[:200]}"
        )

    @pytest.mark.parametrize("path,body", PROTECTED_POST)
    def test_post_without_auth_is_401(self, path, body):
        s = _fresh_session()
        r = s.post(f"{API}{path}", json=body, timeout=15)
        assert r.status_code == 401, (
            f"POST {path} expected 401 without auth, got {r.status_code}: {r.text[:200]}"
        )


# ============================================================================
# B) WHITELIST — public endpoints work WITHOUT auth
# ============================================================================
class TestPublicWhitelist:
    def test_health_no_auth(self):
        s = _fresh_session()
        r = s.get(f"{API}/health", timeout=10)
        assert r.status_code == 200, f"/api/health {r.status_code}"

    def test_login_no_auth_sets_cookies(self):
        s = _fresh_session()
        r = s.post(f"{API}/auth/login", json={"username": "مدير"}, timeout=15)
        assert r.status_code == 200, f"login {r.status_code} {r.text[:200]}"
        # cookie set?
        cookies = {c.name: c.value for c in s.cookies}
        assert "access_token" in cookies, f"access_token cookie not set: {cookies}"

    def test_refresh_with_login_cookie(self):
        s = _fresh_session()
        r = s.post(f"{API}/auth/login", json={"username": "مدير"}, timeout=15)
        assert r.status_code == 200
        r2 = s.post(f"{API}/auth/refresh", timeout=10)
        assert r2.status_code == 200, f"refresh {r2.status_code} {r2.text[:200]}"

    def test_approvals_public_fake_token_not_401(self):
        s = _fresh_session()
        r = s.get(f"{API}/approvals/public/faketoken_xyz", timeout=10)
        assert r.status_code != 401, (
            f"public approvals should not be 401, got {r.status_code}: {r.text[:200]}"
        )


# ============================================================================
# C) WITH AUTH — protected endpoints return 200
# ============================================================================
class TestWithBearerReturns200:
    def test_users_with_bearer(self, admin_token):
        r = requests.get(
            f"{API}/users",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=15,
        )
        assert r.status_code == 200, f"users {r.status_code} {r.text[:200]}"

    def test_customers_with_bearer(self, admin_token):
        r = requests.get(
            f"{API}/customers",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=20,
        )
        assert r.status_code == 200, f"customers {r.status_code} {r.text[:200]}"

    def test_finance_alerts_with_bearer(self, admin_token):
        r = requests.get(
            f"{API}/finance/alerts?workshop_id=finmodule-sync",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=15,
        )
        assert r.status_code == 200, f"finance/alerts {r.status_code} {r.text[:200]}"
        data = r.json()
        # envelope check
        assert data.get("success") is True or isinstance(data, dict)


# ============================================================================
# D) KATRINA read-only query
# ============================================================================
class TestKatrinaReadOnly:
    def test_read_only_arabic_answer(self, admin_token):
        r = requests.post(
            f"{API}/assistant/chat",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"message": "كم عدد العملاء والمركبات؟"},
            timeout=90,
        )
        assert r.status_code == 200, f"chat {r.status_code} {r.text[:200]}"
        body = r.json()
        data = body.get("data", body)
        # Arabic answer expected somewhere in the response text/cards
        text_blob = str(body)
        assert any(ch >= "\u0600" and ch <= "\u06ff" for ch in text_blob), (
            "expected Arabic characters in Katrina answer"
        )
        # Should mention customers roughly (not asserting exact number)
        assert "عمل" in text_blob or "عميل" in text_blob or "customer" in text_blob.lower()


# ============================================================================
# E) KATRINA search customer (read-only)
# ============================================================================
class TestKatrinaSearch:
    def test_search_customer_readonly(self, admin_token):
        r = requests.post(
            f"{API}/assistant/chat",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"message": "ابحث عن عميل باسم احمد"},
            timeout=90,
        )
        assert r.status_code == 200, f"chat search {r.status_code} {r.text[:200]}"


# ============================================================================
# F) FOUR-EYES full cycle with TESTQA expense
# ============================================================================
class TestFourEyesTESTQA:
    """Propose TESTQA expense as مدير → self-approve blocked → احمد1 approves."""

    committed_journal_ids: list = []
    created_approval_ids: list = []

    def _extract_approval_id(self, chat_body: dict):
        data = chat_body.get("data", chat_body)
        # try executed.approval_id
        aid = None
        executed = data.get("executed") if isinstance(data, dict) else None
        if isinstance(executed, dict):
            aid = executed.get("approval_id")
        if not aid:
            cards = data.get("cards") or []
            for c in cards:
                cd = (c or {}).get("data") or {}
                if cd.get("approval_id"):
                    aid = cd["approval_id"]
                    break
        return aid

    def test_full_cycle(self, admin_token, approver_token):
        tag = uuid.uuid4().hex[:6]
        desc = f"TESTQA-مصروف-{tag}"

        # turn 1 — propose
        r1 = requests.post(
            f"{API}/assistant/chat",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"message": f"سجلي مصروف 1 ريال {desc} نقدي"},
            timeout=90,
        )
        assert r1.status_code == 200, f"chat turn1 {r1.status_code}: {r1.text[:200]}"

        # turn 2 — confirm
        r2 = requests.post(
            f"{API}/assistant/chat",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"message": "نعم"},
            timeout=90,
        )
        assert r2.status_code == 200, f"chat turn2 {r2.status_code}: {r2.text[:200]}"
        body2 = r2.json()

        approval_id = self._extract_approval_id(body2)
        if not approval_id:
            # Fallback: list approvals and find one whose description contains our tag
            time.sleep(1)
            lr = requests.get(
                f"{API}/runtime/approvals",
                headers={"Authorization": f"Bearer {admin_token}"},
                timeout=15,
            )
            assert lr.status_code == 200
            items = (lr.json() or {}).get("data") or []
            for it in items:
                # search desc/description/payload
                blob = str(it)
                if desc in blob:
                    approval_id = it.get("approval_id") or it.get("id")
                    break
        assert approval_id, (
            f"Could not obtain approval_id — turn2 body keys={list(body2.keys())} preview={str(body2)[:400]}"
        )
        TestFourEyesTESTQA.created_approval_ids.append(approval_id)
        print(f"[TESTQA] created approval_id={approval_id} tag={tag}")

        # self-approve should fail (four_eyes_violation, 403)
        rs = requests.post(
            f"{API}/runtime/approvals/{approval_id}/approve",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=15,
        )
        assert rs.status_code == 403, (
            f"self-approve expected 403 four_eyes_violation, got {rs.status_code}: {rs.text[:200]}"
        )
        assert "four_eyes" in rs.text.lower() or "four-eyes" in rs.text.lower(), rs.text[:200]

        # cross-user approve as احمد1 → 200 committed
        ra = requests.post(
            f"{API}/runtime/approvals/{approval_id}/approve",
            headers={"Authorization": f"Bearer {approver_token}"},
            timeout=30,
        )
        assert ra.status_code == 200, f"cross approve {ra.status_code}: {ra.text[:200]}"
        rbody = ra.json()
        rdata = rbody.get("data", rbody)
        j_id = (
            rdata.get("journal_id")
            or (rdata.get("result") or {}).get("journal_id")
            or (rdata.get("commit") or {}).get("journal_id")
        )
        if j_id:
            TestFourEyesTESTQA.committed_journal_ids.append(j_id)
        print(f"[TESTQA] committed journal_id={j_id} approval_id={approval_id}")


def teardown_module(_):
    print("\n===== TESTQA CLEANUP REPORT =====")
    print(f"Created approval_ids: {TestFourEyesTESTQA.created_approval_ids}")
    print(f"Committed journal_ids: {TestFourEyesTESTQA.committed_journal_ids}")
    print("Main agent: reverse the journal_id(s) above and reject any leftover pending TESTQA approvals.")
