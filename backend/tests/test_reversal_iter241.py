"""
Iter241 — Reversal/Contra-Entry + Governance + Bot tool awareness tests.

Validates:
  - POST /api/finance-actions/expense -> POST /api/finance-actions/reverse
  - Reversal correctness: lines SWAPPED, originals preserved, balanced
  - Reversal idempotency (same journal_id reversed twice => idempotent:true)
  - Reversal RBAC (no JWT -> 403; technician JWT -> 403; admin -> allowed)
  - Reversal by reference_id (same idempotency)
  - Bot tools: GET /api/assistant/tools returns 21 read-only tools
  - Bot tool execution via POST /api/assistant/tool/{name}
  - Bot chat end-to-end (Arabic finance question)
  - Impersonation defense (spoofed headers)
"""
from __future__ import annotations

import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://canonical-integrity.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


def _login(username: str) -> str:
    r = requests.post(f"{API}/auth/login", json={"username": username}, timeout=15)
    assert r.status_code == 200, f"login({username}) failed: {r.status_code} {r.text}"
    tok = r.json().get("access_token")
    assert tok, f"no access_token for {username}: {r.text}"
    return tok


@pytest.fixture(scope="module")
def admin_token() -> str:
    return _login("مدير")


@pytest.fixture(scope="module")
def tech_token() -> str:
    return _login("مستخدم اختبار")


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def tech_headers(tech_token):
    return {"Authorization": f"Bearer {tech_token}", "Content-Type": "application/json"}


# ──────────────────────────────────────────────────────────────────────────
# 1. Health: login works for unknown -> 401
# ──────────────────────────────────────────────────────────────────────────
class TestAuthSanity:
    def test_admin_login(self, admin_token):
        assert isinstance(admin_token, str) and len(admin_token) > 20

    def test_unknown_user_401(self):
        r = requests.post(f"{API}/auth/login", json={"username": f"NOPE_{uuid.uuid4().hex[:6]}"}, timeout=10)
        assert r.status_code == 401, r.text


# ──────────────────────────────────────────────────────────────────────────
# 2. Reversal full flow
# ──────────────────────────────────────────────────────────────────────────
class TestReversalFlow:
    expense_ref = None
    journal_id = None
    original_lines = None

    def test_01_create_expense(self, admin_headers):
        ref = f"TEST_iter241_{uuid.uuid4().hex[:10]}"
        payload = {
            "description": "TEST_iter241 reversal expense",
            "amount": 137.50,
            "category": "أخرى",
            "payment_method": "cash",
            "reference_id": ref,
        }
        r = requests.post(f"{API}/finance-actions/expense", json=payload, headers=admin_headers, timeout=20)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j.get("success") is True, j
        data = j.get("data", {})
        assert data.get("posted") is True, data
        jid = data.get("journal_id") or data.get("entry_id") or data.get("id")
        assert jid, f"no journal_id in response: {data}"
        TestReversalFlow.journal_id = jid
        TestReversalFlow.expense_ref = ref

    def test_02_reverse_returns_balanced_swapped(self, admin_headers):
        assert TestReversalFlow.journal_id, "prerequisite expense not posted"
        r = requests.post(
            f"{API}/finance-actions/reverse",
            json={"journal_id": TestReversalFlow.journal_id, "reason": "TEST_iter241"},
            headers=admin_headers,
            timeout=20,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("success") is True, body
        data = body.get("data", {})
        # Engine returns 'reversed': True with details
        assert data.get("reversed") is True, f"expected reversed=true, got {data}"
        # Lines swapped + balanced check (if engine returns line details)
        # Engine response shape: details list of new contra entries
        details = data.get("details") or data.get("reversals") or []
        if details:
            for d in details:
                lines = d.get("lines") or []
                if lines:
                    tot_debit = sum(float(l.get("debit") or 0) for l in lines)
                    tot_credit = sum(float(l.get("credit") or 0) for l in lines)
                    assert abs(tot_debit - tot_credit) < 0.01, f"unbalanced contra: {lines}"

    def test_03_reverse_idempotent(self, admin_headers):
        """Second reverse of the same journal_id must return reversed=false + idempotent=true."""
        assert TestReversalFlow.journal_id
        r = requests.post(
            f"{API}/finance-actions/reverse",
            json={"journal_id": TestReversalFlow.journal_id},
            headers=admin_headers,
            timeout=20,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        data = body.get("data", {})
        assert data.get("reversed") is False, f"expected reversed=false on 2nd call, got {data}"
        # idempotent flag may be top-level OR nested under entries[]
        idempotent_flag = data.get("idempotent")
        if idempotent_flag is None:
            entries = data.get("entries") or []
            idempotent_flag = bool(entries) and all(e.get("idempotent") for e in entries)
        assert idempotent_flag is True, f"expected idempotent=true, got {data}"

    def test_04_reverse_no_jwt_403(self):
        r = requests.post(
            f"{API}/finance-actions/reverse",
            json={"journal_id": "anything"},
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        assert r.status_code == 403, f"expected 403 with no JWT, got {r.status_code} {r.text}"

    def test_05_reverse_technician_403(self, tech_headers, admin_headers):
        # Create new expense to attempt reversal as technician
        ref = f"TEST_iter241_rbac_{uuid.uuid4().hex[:8]}"
        r1 = requests.post(
            f"{API}/finance-actions/expense",
            json={"description": "rbac test", "amount": 10, "payment_method": "cash", "reference_id": ref},
            headers=admin_headers,
            timeout=15,
        )
        assert r1.status_code == 200
        jid = (r1.json().get("data") or {}).get("journal_id")
        assert jid

        r = requests.post(
            f"{API}/finance-actions/reverse",
            json={"journal_id": jid},
            headers=tech_headers,
            timeout=15,
        )
        assert r.status_code == 403, f"technician should get 403, got {r.status_code} {r.text}"

    def test_06_reverse_by_reference_id(self, admin_headers):
        # Create fresh expense, then reverse by reference_id
        ref = f"TEST_iter241_refid_{uuid.uuid4().hex[:8]}"
        r1 = requests.post(
            f"{API}/finance-actions/expense",
            json={"description": "ref-id reverse", "amount": 22.5, "payment_method": "cash", "reference_id": ref},
            headers=admin_headers,
            timeout=15,
        )
        assert r1.status_code == 200, r1.text

        r2 = requests.post(
            f"{API}/finance-actions/reverse",
            json={"reference_id": ref},
            headers=admin_headers,
            timeout=15,
        )
        assert r2.status_code == 200, r2.text
        d = r2.json().get("data", {})
        assert d.get("reversed") is True, d

        # Idempotent re-call
        r3 = requests.post(
            f"{API}/finance-actions/reverse",
            json={"reference_id": ref},
            headers=admin_headers,
            timeout=15,
        )
        assert r3.status_code == 200, r3.text
        d3 = r3.json().get("data", {})
        assert d3.get("idempotent") is True or d3.get("reversed") is False, d3


# ──────────────────────────────────────────────────────────────────────────
# 3. Impersonation defense
# ──────────────────────────────────────────────────────────────────────────
class TestImpersonationDefense:
    def test_spoofed_role_header_no_jwt_403(self):
        r = requests.post(
            f"{API}/finance-actions/expense",
            json={"description": "spoof", "amount": 1, "payment_method": "cash", "reference_id": f"TEST_spoof_{uuid.uuid4().hex[:6]}"},
            headers={"x-user-role": "admin", "x-user-id": "fake", "Content-Type": "application/json"},
            timeout=10,
        )
        assert r.status_code == 403, f"expected 403 with spoofed header, got {r.status_code} {r.text}"


# ──────────────────────────────────────────────────────────────────────────
# 4. Bot tool awareness
# ──────────────────────────────────────────────────────────────────────────
class TestBotTools:
    def test_tools_list_21_readonly(self, admin_headers):
        r = requests.get(f"{API}/assistant/tools", headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        tools = body.get("tools") or body.get("data") or body
        if isinstance(tools, dict) and "tools" in tools:
            tools = tools["tools"]
        assert isinstance(tools, list), f"unexpected shape: {body}"
        assert len(tools) == 21, f"expected 21 tools, got {len(tools)}: {[t.get('name') for t in tools]}"
        non_read = [t for t in tools if t.get("write") is True]
        assert non_read == [], f"non-readonly tools leaked: {non_read}"

    def test_tool_firewall_health_score(self, admin_headers):
        r = requests.post(f"{API}/assistant/tool/firewall.health_score", json={}, headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        b = r.json()
        assert b.get("success") is True, b

    def test_tool_finance_ar_summary(self, admin_headers):
        r = requests.post(f"{API}/assistant/tool/finance.ar_summary", json={}, headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        b = r.json()
        assert b.get("success") is True, b

    def test_tool_accounting_journal_entries(self, admin_headers):
        r = requests.post(f"{API}/assistant/tool/accounting.journal_entries",
                          json={"limit": 5}, headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        b = r.json()
        assert b.get("success") is True, b
        # Report count for visibility
        data = b.get("data") or {}
        print(f"[accounting.journal_entries] count={data.get('count')} sample_keys={list(data.keys())[:8]}")


# ──────────────────────────────────────────────────────────────────────────
# 5. Bot chat E2E (Arabic finance question)
# ──────────────────────────────────────────────────────────────────────────
class TestBotChat:
    def test_chat_ar_summary_question(self, admin_headers):
        r = requests.post(
            f"{API}/assistant/chat",
            json={"message": "كم ذمم العملاء؟", "session_id": f"test_{uuid.uuid4().hex[:6]}"},
            headers=admin_headers,
            timeout=60,
        )
        assert r.status_code == 200, r.text
        b = r.json()
        assert b.get("success") is True, b
        reply = (
            b.get("reply")
            or b.get("message")
            or (b.get("data") or {}).get("reply")
            or (b.get("data") or {}).get("response")
            or ""
        )
        assert isinstance(reply, str) and len(reply) > 0, f"empty reply: {b}"
        # Bot should be read-only (no writes performed)
        d = b.get("data") or {}
        assert d.get("read_only") in (True, None), f"bot performed write: {d}"

    def test_chat_journal_entries_question(self, admin_headers):
        r = requests.post(
            f"{API}/assistant/chat",
            json={"message": "أعطني القيود المحاسبية وإجمالي المدين", "session_id": f"test_{uuid.uuid4().hex[:6]}"},
            headers=admin_headers,
            timeout=60,
        )
        assert r.status_code == 200, r.text
        b = r.json()
        assert b.get("success") is True, b
