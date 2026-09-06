"""
Iteration 245 — Katrina four-eyes cycle + Financial Control mount + RBAC on alias endpoints.

CRITICAL: Prod Supabase with real user data. Only interact with approvals we create
(description TEST-AGENT-مصروف). Do NOT approve/reject other approvals in list.
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://financial-ssot.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


def _login(session, username):
    r = session.post(f"{API}/auth/login", json={"username": username}, timeout=20)
    assert r.status_code == 200, f"login {username} failed: {r.status_code} {r.text[:300]}"
    return r.json()["access_token"]


def _unwrap(r):
    """Handle both raw JSON and {success, data:...} envelope."""
    j = r.json()
    if isinstance(j, dict) and "data" in j and ("success" in j or "status" in j):
        return j["data"]
    return j


@pytest.fixture(scope="module")
def s_admin():
    ses = requests.Session()
    tok = _login(ses, "مدير")
    ses.headers.update({"Authorization": f"Bearer {tok}"})
    return ses


@pytest.fixture(scope="module")
def s_ahmad():
    ses = requests.Session()
    tok = _login(ses, "احمد1")
    ses.headers.update({"Authorization": f"Bearer {tok}"})
    return ses


# ---------------- Financial Control router mount ----------------
class TestFinancialControlMount:
    def test_findings_summary(self, s_admin):
        r = s_admin.get(f"{API}/financial-control/findings/summary", timeout=20)
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"

    def test_approvals_stats(self, s_admin):
        r = s_admin.get(f"{API}/financial-control/approvals/stats", timeout=20)
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"


# ---------------- RBAC on alias endpoints ----------------
class TestAliasRBAC:
    """Use a fresh session with NO cookies to simulate a truly unauthenticated request."""

    def test_alias_approve_without_auth_denied(self):
        r = requests.post(f"{API}/runtime/approve/nonexistent-approval-id",
                          json={}, timeout=15)
        # 401 = حارس المصادقة العام (أُضيف بعد كتابة الاختبار) — الرفض هو المطلوب
        assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code} {r.text[:300]}"

    def test_alias_commit_without_auth_denied(self):
        r = requests.post(f"{API}/runtime/commit/nonexistent-id", json={}, timeout=15)
        assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code} {r.text[:300]}"

    def test_alias_rollback_without_auth_denied(self):
        r = requests.post(f"{API}/runtime/rollback/nonexistent-id", json={}, timeout=15)
        assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code} {r.text[:300]}"


# ---------------- Full four-eyes cycle ----------------
class TestFourEyesCycle:
    _approval_id = None
    _journal_id = None
    _debit_account = None

    def test_01_chat_propose_and_confirm(self, s_admin):
        session_id = f"test-agent-4eyes-{int(time.time())}"
        r1 = s_admin.post(f"{API}/assistant/chat",
                          json={"message": "سجلي مصروف 1 ريال TEST-AGENT-مصروف نقدي",
                                "session_id": session_id},
                          timeout=90)
        assert r1.status_code == 200, f"chat propose: {r1.status_code} {r1.text[:400]}"
        r2 = s_admin.post(f"{API}/assistant/chat",
                          json={"message": "نعم", "session_id": session_id},
                          timeout=90)
        assert r2.status_code == 200, f"chat confirm: {r2.status_code} {r2.text[:400]}"
        d = _unwrap(r1)
        # look for approval_id in cards
        aid = None
        for c in d.get("cards", []) or []:
            if isinstance(c, dict) and c.get("type") == "ApprovalCard":
                aid = c.get("id") or (c.get("data") or {}).get("approval_id")
                break
        assert aid, f"no approval_id found in chat propose response: {str(d)[:500]}"
        TestFourEyesCycle._approval_id = aid
        print(f"[chat] approval_id={aid}")

    def test_02_list_approvals_shows_proposer_admin(self, s_admin):
        r = s_admin.get(f"{API}/runtime/approvals", timeout=20)
        assert r.status_code == 200
        items = _unwrap(r)
        assert isinstance(items, list) and len(items) > 0
        aid = TestFourEyesCycle._approval_id
        mine = next((it for it in items if it.get("id") == aid), None)
        assert mine is not None, f"our approval {aid} not found in list of {len(items)}"
        proposer = mine.get("proposer") or mine.get("requester")
        assert proposer == "مدير", f"proposer expected 'مدير', got {proposer!r}"
        assert "auto:llm" not in str(proposer).lower()
        # verify payload description
        desc = (mine.get("payload") or {}).get("description", "")
        assert "TEST-AGENT" in desc, f"description mismatch: {desc}"

    def test_03_four_eyes_self_approve_blocked(self, s_admin):
        aid = TestFourEyesCycle._approval_id
        r = s_admin.post(f"{API}/runtime/approvals/{aid}/approve", json={}, timeout=20)
        assert r.status_code == 403, f"self-approve should be 403, got {r.status_code} {r.text[:400]}"
        assert "four_eyes" in r.text.lower() or "four" in r.text.lower() or "eyes" in r.text.lower() \
            or "self" in r.text.lower(), f"expected four_eyes indication: {r.text[:400]}"

    def test_04_second_approver_commits(self, s_ahmad):
        aid = TestFourEyesCycle._approval_id
        r = s_ahmad.post(f"{API}/runtime/approvals/{aid}/approve", json={}, timeout=45)
        assert r.status_code == 200, f"approver commit: {r.status_code} {r.text[:400]}"
        body = r.json()
        body_str = str(body)
        # Extract journal_id if present
        jid = None
        def walk(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    if k in ("journal_id", "journal_entry_id") and isinstance(v, str):
                        return v
                    r = walk(v)
                    if r:
                        return r
            elif isinstance(o, list):
                for it in o:
                    r = walk(it)
                    if r:
                        return r
            return None
        jid = walk(body)
        TestFourEyesCycle._journal_id = jid
        # Assert account 035 مصروفات عامة وإدارية used
        found035 = "035" in body_str
        found_name = "مصروفات عامة وإدارية" in body_str
        print(f"[COMMIT OK] journal_id={jid} account_035={found035} account_name={found_name} keys={list(body.keys())}")
        assert found035 or found_name, f"expected account 035/مصروفات عامة وإدارية in commit response: {body_str[:600]}"


# ---------------- Regression: finance alerts & trial balance ----------------
class TestFinanceRegression:
    def test_alerts_health_is_valid_and_explained(self, s_admin):
        r = s_admin.get(f"{API}/finance/alerts?workshop_id=finmodule-sync", timeout=20)
        assert r.status_code == 200
        d = _unwrap(r)
        health = (d.get("health") or {}).get("score")
        assert isinstance(health, (int, float)) and 0 <= health <= 100, f"invalid health score: {health}"
        alerts = d.get("alerts") or []
        if health < 100:
            assert len(alerts) >= 1, "health below 100 must include at least one explanatory alert"

    def test_trial_balance_balanced(self, s_admin):
        r = s_admin.get(f"{API}/finance/reports/trial-balance?workshop_id=finmodule-sync", timeout=20)
        assert r.status_code == 200
        d = _unwrap(r)
        totals = d.get("totals") or {}
        deb = totals.get("total_debit") or totals.get("debits")
        cred = totals.get("total_credit") or totals.get("credits")
        assert deb is not None and cred is not None, f"missing totals: {totals}"
        assert deb == cred, f"trial balance not balanced: {deb} vs {cred}"
        print(f"[trial-balance] debit={deb} credit={cred}")
