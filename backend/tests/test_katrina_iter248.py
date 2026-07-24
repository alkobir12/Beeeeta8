"""
Iter 248 — Backend E2E for Katrina session-start reminders, duplicate-prevention,
auditor pre-approval notes, Arabic historical queries, and regressions.
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://stamp-approval-flow.preview.emergentagent.com").rstrip("/")


# ---------- fixtures ----------
def _login(username: str) -> str:
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"username": username}, timeout=30)
    assert r.status_code == 200, f"login {username} failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def tok_admin():
    return _login("مدير")


@pytest.fixture(scope="module")
def tok_ahmed():
    return _login("احمد1")


@pytest.fixture(scope="module")
def tok_farag():
    return _login("فرج1")


def _chat(token: str, message: str, session_id: str) -> dict:
    r = requests.post(
        f"{BASE_URL}/api/assistant/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": message, "session_id": session_id, "language": "ar"},
        timeout=90,
    )
    assert r.status_code == 200, f"/chat failed: {r.status_code} {r.text[:400]}"
    body = r.json()
    assert body.get("success") is True, f"chat not success: {body}"
    return body.get("data", {})


def _pending_count(token: str) -> int:
    r = requests.get(
        f"{BASE_URL}/api/runtime/approvals?status=pending",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    assert r.status_code == 200, f"pending list failed: {r.status_code} {r.text[:200]}"
    body = r.json()
    if isinstance(body, dict):
        data = body.get("data", body)
        items = data if isinstance(data, list) else data.get("items") or data.get("approvals") or []
    else:
        items = body
    return len(items)


# ---------- 1) auth ----------
class TestAuth:
    def test_admin_login(self, tok_admin):
        assert tok_admin and isinstance(tok_admin, str) and len(tok_admin) > 20

    def test_ahmed_login(self, tok_ahmed):
        assert tok_ahmed and isinstance(tok_ahmed, str)

    def test_farag_login(self, tok_farag):
        assert tok_farag and isinstance(tok_farag, str)

    def test_unknown_user_rejected(self):
        r = requests.post(f"{BASE_URL}/api/auth/login", json={"username": "no_such_user_xyz"}, timeout=15)
        assert r.status_code == 401


# ---------- 2) duplicate prevention + auditor inclusion ----------
class TestDuplicateAndAuditor:
    def test_duplicate_prevented_and_auditor_included(self, tok_admin):
        sid = f"iter248-dup-{uuid.uuid4().hex[:8]}"
        # unique amount ensures fresh draft (avoids collision with residual test data)
        unique_amt = 60 + (int(time.time()) % 30)
        before = _pending_count(tok_admin)

        msg = f"اشتري رشاش ماء بـ {unique_amt} ريال من مورد البدر كاش"

        d1 = _chat(tok_admin, msg, sid)
        r1 = d1.get("response", "")
        assert "pending" in str(d1).lower() or "اعتماد" in r1 or "🔒" in r1, f"first response missing approval: {r1[:300]}"
        # auditor pre-approval section
        assert "🕵️" in r1 or "المدقق" in r1, f"auditor section missing in first response: {r1[:400]}"

        # confirm one new pending draft was created
        mid = _pending_count(tok_admin)
        assert mid >= before + 1, f"expected +1 pending draft, before={before} mid={mid}"

        # second identical message → must be dedup
        d2 = _chat(tok_admin, msg, sid)
        r2 = d2.get("response", "")
        assert ("مطابق" in r2 and "معلق" in r2) or "♻️" in r2 or "بالفعل" in r2, (
            f"duplicate not detected in second response: {r2[:400]}"
        )
        after = _pending_count(tok_admin)
        assert after == mid, f"duplicate created new draft! before={before} mid={mid} after={after}"

        # cleanup: contextual cancel in same session
        d3 = _chat(tok_admin, "الغي آخر عملية شراء", sid)
        r3 = d3.get("response", "")
        assert "إلغاء" in r3 or "تم" in r3, f"cancel failed: {r3[:300]}"


# ---------- 3) historical Arabic queries ----------
class TestHistoricalQueries:
    def test_last_month_query(self, tok_admin):
        sid = f"iter248-hist-{uuid.uuid4().hex[:8]}"
        d = _chat(tok_admin, "كم عملية صارت الشهر الماضي؟", sid)
        # Look through tool_results for operations.search with period info
        tools = d.get("tool_results") or []
        found_period = False
        for t in tools:
            name = t.get("tool") or t.get("name") or ""
            if "operations" in name and "search" in name:
                res = t.get("result") or t.get("data") or {}
                period = str(res.get("period", "")) if isinstance(res, dict) else ""
                if period or "2026" in str(res):
                    found_period = True
                    break
        resp = d.get("response", "")
        # Accept either tool-level period OR response text containing month-window keywords
        assert found_period or ("2026" in resp) or ("الشهر" in resp), f"no period info: tools={tools} resp={resp[:300]}"

    def test_month_ago_query_no_crash(self, tok_admin):
        sid = f"iter248-histb-{uuid.uuid4().hex[:8]}"
        d = _chat(tok_admin, "بحث عمليات قبل شهر", sid)
        assert d.get("response") is not None
        # any structured response without error keywords
        resp = d.get("response", "")
        assert "traceback" not in resp.lower() and "internal" not in resp.lower()


# ---------- 4) session-start reminder ----------
class TestSessionReminder:
    def test_greeting_returns_reminder(self, tok_ahmed):
        sid = f"iter248-remind-{uuid.uuid4().hex[:8]}"
        d = _chat(tok_ahmed, "مرحبا", sid)
        resp = d.get("response", "")
        # reminder emoji + "تذكير" per spec
        assert "🔔" in resp or "تذكير" in resp, f"reminder header missing: {resp[:400]}"
        # should reference approvals awaiting decision
        assert "اعتماد" in resp or "موافق" in resp or "معلق" in resp, f"approval mention missing: {resp[:400]}"


# ---------- 5) four-eyes regression ----------
class TestFourEyes:
    def test_admin_cannot_approve_own_draft(self, tok_admin, tok_ahmed):
        sid = f"iter248-4eyes-{uuid.uuid4().hex[:8]}"
        # unique amount for a fresh draft
        unique_price = 100 + (int(time.time()) % 500)
        msg = f"اشتري قطعة اختبار iter248 بـ {unique_price} ريال من مورد اختبار iter248 كاش"
        d = _chat(tok_admin, msg, sid)
        # Always resolve via pending list to get the correct approval `id`
        draft_id = None
        r = requests.get(
            f"{BASE_URL}/api/runtime/approvals?status=pending",
            headers={"Authorization": f"Bearer {tok_admin}"},
            timeout=30,
        )
        body = r.json()
        arr = body.get("data", body) if isinstance(body, dict) else body
        items = arr if isinstance(arr, list) else arr.get("items") or arr.get("approvals") or []
        for it in reversed(items):
            pay = str(it.get("payload", ""))
            if it.get("requester") == "مدير" and str(unique_price) in pay and "iter248" in pay:
                draft_id = it.get("id")
                break
        if not draft_id and items:
            # newest requested by مدير
            for it in reversed(items):
                if it.get("requester") == "مدير":
                    draft_id = it.get("id"); break

        assert draft_id, f"could not resolve approval id; items sample: {items[:2]}"

        r = requests.post(
            f"{BASE_URL}/api/runtime/approvals/{draft_id}/approve",
            headers={"Authorization": f"Bearer {tok_admin}"},
            json={},
            timeout=30,
        )
        assert r.status_code == 403, f"expected 403 four-eyes, got {r.status_code}: {r.text[:200]}"

        # clean up: cancel
        _chat(tok_admin, "الغي آخر عملية شراء", sid)


# ---------- 6) Katrina approvals list intent ----------
class TestKatrinaApprovalsList:
    def test_pending_intent(self, tok_admin):
        sid = f"iter248-list-{uuid.uuid4().hex[:8]}"
        d = _chat(tok_admin, "اعتمادات كاترينا", sid)
        resp = d.get("response", "")
        assert "موافقة" in resp or "شراء" in resp or "معلق" in resp or "اعتماد" in resp, (
            f"list intent response weak: {resp[:400]}"
        )
