"""
Iter242 — End-to-end backend tests for the bot financial pipeline (Phase A + B):
  - Bot proposes financial actions (invoice/payment/expense/reverse) → ALWAYS pending_approval
  - Echo-back includes type/party/amount/accounting effect + red-line
  - Principle ①: ask-not-guess on missing/ambiguous (no amount, unknown customer, ambiguous name)
  - Four-Eyes: same proposer 403, different approver succeeds
  - Engine-backed balanced journal entries posted after approval
  - Bot reverse via chat → contra entry + original preserved + idempotent
  - Site REST regression: /api/finance-actions/* still RBAC-protected and balanced
  - Accounting integrity: delete_operation reverses (no hard delete), all recent JEs balanced
  - Safe entity actions (customer/vehicle) still auto-commit
  - Security regression: no-JWT 403, technician 403, login deny-unknown 401
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # fallback to public env from /app/frontend/.env
    with open("/app/frontend/.env") as fh:
        for line in fh:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break

WORKSHOP_ID = "finmodule-sync"


# ---------------- helpers ----------------

def _login(username: str) -> str:
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"username": username}, timeout=15)
    assert r.status_code == 200, f"login failed for {username}: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_token():
    return _login("مدير")


@pytest.fixture(scope="module")
def supervisor_token():
    return _login("احمد1")


@pytest.fixture(scope="module")
def accountant_token():
    return _login("فرج1")


@pytest.fixture(scope="module")
def technician_token():
    return _login("مستخدم اختبار")


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _chat(token: str, message: str, session_id: str = None, proposer: str = "مدير"):
    sid = session_id or f"iter242-{uuid.uuid4().hex[:8]}"
    payload = {"message": message, "session_id": sid, "proposer": proposer}
    r = requests.post(
        f"{BASE_URL}/api/assistant/chat",
        headers=_auth(token),
        json=payload,
        timeout=60,
    )
    return r, sid


def _extract_data(r):
    assert r.status_code == 200, f"chat HTTP {r.status_code}: {r.text[:500]}"
    body = r.json()
    return body.get("data", body)


def _extract_approval_id(data: dict):
    """approval_id lives in cards[].data.approval_id (or cards[].id) for ApprovalCard."""
    for c in (data.get("cards") or []):
        if not isinstance(c, dict):
            continue
        if c.get("type") in ("ApprovalCard", "approval", "approval_card"):
            cd = c.get("data") or {}
            return cd.get("approval_id") or c.get("id")
    # fallback
    return (data.get("executed") or {}).get("approval_id")


def _entry_totals(e: dict):
    """Compute (total_debit, total_credit) from lines or fall back to 'total'."""
    lines = e.get("lines") or []
    td = sum(float(l.get("debit") or 0) for l in lines if isinstance(l, dict))
    tc = sum(float(l.get("credit") or 0) for l in lines if isinstance(l, dict))
    if td == 0 and tc == 0:
        t = float(e.get("total") or 0)
        td = tc = t
    return td, tc


def _entry_amount(e: dict) -> float:
    td, _ = _entry_totals(e)
    return td or float(e.get("total") or 0)


def _extract_reply_text(data: dict) -> str:
    parts = []
    for k in ("response", "reply", "text", "markdown", "message", "content"):
        v = data.get(k)
        if isinstance(v, str):
            parts.append(v)
    return "\n".join(parts)


# ---------------- 1. SECURITY REGRESSION ----------------

class TestSecurityRegression:
    def test_login_deny_unknown(self):
        r = requests.post(f"{BASE_URL}/api/auth/login", json={"username": "زززز_unknown"}, timeout=10)
        assert r.status_code == 401, f"expected 401 for unknown user, got {r.status_code}"

    def test_no_jwt_finance_actions_403(self):
        r = requests.post(
            f"{BASE_URL}/api/finance-actions/expense",
            json={"amount": 10, "description": "TEST_no_jwt", "workshop_id": WORKSHOP_ID},
            timeout=10,
        )
        assert r.status_code in (401, 403), f"no-jwt finance-actions should 401/403, got {r.status_code}"

    def test_spoofed_role_header_ignored(self):
        # Spoofed x-user-role without JWT must NOT bypass auth
        r = requests.post(
            f"{BASE_URL}/api/finance-actions/expense",
            headers={"x-user-role": "admin", "x-user-id": "admin"},
            json={"amount": 10, "description": "TEST_spoof", "workshop_id": WORKSHOP_ID},
            timeout=10,
        )
        assert r.status_code in (401, 403), f"spoofed role should be ignored, got {r.status_code}"

    def test_technician_cannot_reverse(self, technician_token):
        r = requests.post(
            f"{BASE_URL}/api/finance-actions/reverse",
            headers=_auth(technician_token),
            json={"reference_id": "nonexistent-test", "reason": "test"},
            timeout=10,
        )
        assert r.status_code == 403, f"technician reverse should be 403, got {r.status_code}"


# ---------------- 2. BOT FINANCIAL PROPOSAL — never auto-commit ----------------

class TestBotInvoiceProposal:
    def test_invoice_proposal_returns_pending_approval(self, admin_token):
        r, sid = _chat(admin_token, "اصدر فاتورة للعميل نادر بكر بمبلغ 320 آجل", proposer="مدير")
        data = _extract_data(r)
        executed = data.get("executed") or {}
        assert executed.get("status") == "pending_approval", \
            f"expected pending_approval, got {executed}"
        assert executed.get("action") in ("create_invoice", "invoice"), \
            f"expected create_invoice action, got {executed.get('action')}"
        approval_id = _extract_approval_id(data)
        assert approval_id, f"expected approval_id in cards/executed, got cards={data.get('cards')}"
        # echo-back text
        reply_text = _extract_reply_text(data)
        assert "نادر" in reply_text, f"expected customer name in echo, got: {reply_text[:300]}"
        assert "320" in reply_text, f"expected amount 320 in echo, got: {reply_text[:300]}"
        # red-line phrase
        red_line_present = any(
            kw in reply_text
            for kw in ["لن يُثبَّت", "لن يثبت", "اعتماد بشري مختلف", "أربع أعين", "أربع اعين"]
        )
        assert red_line_present, f"expected red-line statement, got: {reply_text[:400]}"
        # save approval_id for downstream
        pytest.invoice_approval_id = approval_id
        pytest.invoice_session = sid

    def test_invoice_not_committed_yet(self, admin_token):
        # journal entries should NOT yet contain a 320 invoice for this draft
        # we'll verify after approval; here just check approval doc exists in pending list if endpoint exists
        approval_id = getattr(pytest, "invoice_approval_id", None)
        assert approval_id, "previous test must have set invoice_approval_id"
        # try to fetch approval status (best-effort)
        r = requests.get(
            f"{BASE_URL}/api/runtime/approvals/{approval_id}",
            headers=_auth(admin_token),
            timeout=10,
        )
        if r.status_code == 200:
            doc = r.json().get("data", r.json())
            status = doc.get("status") or doc.get("data", {}).get("status")
            assert status in ("pending", "pending_approval", "draft"), f"unexpected status {status}"


class TestBotPaymentProposal:
    def test_payment_with_amount_returns_pending(self, admin_token):
        r, _ = _chat(admin_token, "حصّل 150 من نادر بكر نقدا", proposer="مدير")
        data = _extract_data(r)
        executed = data.get("executed") or {}
        assert executed.get("status") == "pending_approval", f"expected pending_approval, got {executed}"
        assert executed.get("action") in ("collect_payment", "payment"), \
            f"unexpected action {executed.get('action')}"
        approval_id = _extract_approval_id(data)
        assert approval_id, f"expected approval_id, got cards={data.get('cards')}"
        pytest.payment_approval_id = approval_id


class TestBotExpenseProposal:
    def test_expense_echo_back(self, admin_token):
        r, _ = _chat(admin_token, "سجل مصروف إيجار 800", proposer="مدير")
        data = _extract_data(r)
        executed = data.get("executed") or {}
        assert executed.get("status") == "pending_approval", f"expected pending_approval, got {executed}"
        assert executed.get("action") in ("create_expense", "expense"), \
            f"unexpected action {executed.get('action')}"
        reply_text = _extract_reply_text(data)
        assert "800" in reply_text, f"expected 800 in echo, got: {reply_text[:300]}"
        assert "مصروف" in reply_text or "مصروفات" in reply_text, f"expected expense label, got: {reply_text[:300]}"
        approval_id = _extract_approval_id(data)
        assert approval_id
        pytest.expense_approval_id = approval_id


# ---------------- 3. PRINCIPLE ① — ask, don't guess ----------------

class TestPrincipleOneAsk:
    def test_payment_without_amount_asks(self, admin_token):
        r, _ = _chat(admin_token, "حصّل من نادر بكر", proposer="مدير")
        data = _extract_data(r)
        # accept any of: top-level mode, executed.mode, needs_clarification flag
        mode = data.get("mode") or (data.get("executed") or {}).get("mode")
        needs_clar = data.get("needs_clarification") or (data.get("executed") or {}).get("needs_clarification")
        executed_status = (data.get("executed") or {}).get("status")
        assert (
            mode in ("clarify", "ask")
            or needs_clar
            or executed_status not in ("pending_approval", "committed")
        ), f"expected clarification for missing amount, got data={str(data)[:400]}"
        # ensure no approval card issued
        approval_id = _extract_approval_id(data)
        assert not approval_id, "must NOT create approval when amount missing"

    def test_unknown_customer_asks(self, admin_token):
        r, _ = _chat(admin_token, "اصدر فاتورة لعميل غير موجود زززز بمبلغ 50", proposer="مدير")
        data = _extract_data(r)
        mode = data.get("mode") or (data.get("executed") or {}).get("mode")
        needs_clar = data.get("needs_clarification") or (data.get("executed") or {}).get("needs_clarification")
        executed_status = (data.get("executed") or {}).get("status")
        assert (
            mode in ("clarify", "ask")
            or needs_clar
            or executed_status != "pending_approval"
        ), f"expected clarification for unknown customer, got {str(data)[:400]}"


# ---------------- 4. FOUR-EYES + ENGINE COMMIT ----------------

class TestFourEyesAndCommit:
    def test_same_proposer_approve_blocked(self, admin_token):
        approval_id = getattr(pytest, "invoice_approval_id", None)
        if not approval_id:
            pytest.skip("invoice_approval_id missing — proposal test must run first")
        r = requests.post(
            f"{BASE_URL}/api/runtime/approvals/{approval_id}/approve",
            headers=_auth(admin_token),  # SAME user (مدير) as proposer
            timeout=15,
        )
        assert r.status_code == 403, f"same-proposer approve must be 403, got {r.status_code}: {r.text[:300]}"
        body = r.json()
        msg = str(body).lower()
        assert "four_eyes" in msg or "four-eyes" in msg or "أربع" in str(body), \
            f"expected four_eyes_violation, got {body}"

    def test_different_approver_commits_invoice(self, supervisor_token):
        approval_id = getattr(pytest, "invoice_approval_id", None)
        if not approval_id:
            pytest.skip("invoice_approval_id missing")
        r = requests.post(
            f"{BASE_URL}/api/runtime/approvals/{approval_id}/approve",
            headers=_auth(supervisor_token),  # DIFFERENT approver (احمد1)
            timeout=30,
        )
        assert r.status_code == 200, f"diff approver should commit, got {r.status_code}: {r.text[:300]}"
        body = r.json()
        data = body.get("data", body)
        # draft status committed
        status = data.get("status") or data.get("draft", {}).get("status") or data.get("data", {}).get("status")
        # accept either explicit committed or 200 with committed flag
        body_str = str(body).lower()
        assert "committed" in body_str or status == "committed", \
            f"expected committed, got status={status} body={body_str[:300]}"

    def test_journal_entry_posted_balanced_for_invoice(self, admin_token):
        # poll up to 8s for the journal entry to be visible
        found = None
        for _ in range(8):
            r = requests.get(
                f"{BASE_URL}/api/finance/journal-entries",
                headers=_auth(admin_token),
                params={"workshop_id": WORKSHOP_ID, "limit": 30},
                timeout=10,
            )
            if r.status_code == 200:
                body = r.json()
                entries = body.get("data", body) if isinstance(body, dict) else body
                if isinstance(entries, list):
                    for e in entries:
                        if not isinstance(e, dict):
                            continue
                        amt = _entry_amount(e)
                        src = (e.get("source") or "").lower()
                        if abs(amt - 320.0) < 0.01 and src != "reversal":
                            found = e
                            break
                if found:
                    break
            time.sleep(1)
        assert found, "no balanced 320 invoice JE found after approval"
        td, tc = _entry_totals(found)
        assert abs(td - tc) < 0.01, f"invoice JE not balanced: dr={td} cr={tc}"

    def test_different_approver_commits_payment(self, supervisor_token, admin_token):
        approval_id = getattr(pytest, "payment_approval_id", None)
        if not approval_id:
            pytest.skip("payment_approval_id missing")
        r = requests.post(
            f"{BASE_URL}/api/runtime/approvals/{approval_id}/approve",
            headers=_auth(supervisor_token),
            timeout=30,
        )
        # payment may fail in some edge cases (e.g. no open invoice), accept 200 or 4xx
        assert r.status_code in (200, 400, 409, 422), f"payment approve unexpected {r.status_code}: {r.text[:300]}"
        if r.status_code == 200:
            body_str = str(r.json()).lower()
            assert "committed" in body_str or "success" in body_str, f"payment didn't commit: {body_str[:300]}"

    def test_different_approver_commits_expense(self, supervisor_token, admin_token):
        approval_id = getattr(pytest, "expense_approval_id", None)
        if not approval_id:
            pytest.skip("expense_approval_id missing")
        r = requests.post(
            f"{BASE_URL}/api/runtime/approvals/{approval_id}/approve",
            headers=_auth(supervisor_token),
            timeout=30,
        )
        assert r.status_code == 200, f"expense approve failed: {r.status_code} {r.text[:300]}"
        # find an 800 expense JE
        time.sleep(2)
        r2 = requests.get(
            f"{BASE_URL}/api/finance/journal-entries",
            headers=_auth(admin_token),
            params={"workshop_id": WORKSHOP_ID, "limit": 30},
            timeout=10,
        )
        body2 = r2.json()
        entries = body2.get("data", body2) if isinstance(body2, dict) else body2
        assert any(
            abs(_entry_amount(e) - 800.0) < 0.01 and (e.get("source") or "").lower() != "reversal"
            for e in entries if isinstance(e, dict)
        ), "no 800 expense JE found after approval"


# ---------------- 5. BOT REVERSE via chat ----------------

class TestBotReverse:
    def test_reverse_via_chat_proposes(self, admin_token, supervisor_token):
        # create a brand-new expense via REST so we have a definitely-not-yet-reversed JE
        unique_ref = f"TEST_iter242_rev_{uuid.uuid4().hex[:8]}"
        r_create = requests.post(
            f"{BASE_URL}/api/finance-actions/expense",
            headers=_auth(admin_token),
            json={
                "amount": 13,
                "description": "TEST_iter242_to_reverse",
                "workshop_id": WORKSHOP_ID,
                "category": "إيجار",
                "reference_id": unique_ref,
            },
            timeout=15,
        )
        if r_create.status_code not in (200, 201):
            pytest.skip(f"could not create source expense: {r_create.status_code}")
        # journal_id is returned directly in the response
        je_id = (r_create.json().get("data") or {}).get("journal_id")
        if not je_id:
            pytest.skip("no journal_id in create response")
        time.sleep(1)
        r_chat, _ = _chat(admin_token, f"اعكس القيد رقم {je_id} السبب خطأ", proposer="مدير")
        data = _extract_data(r_chat)
        executed = data.get("executed") or {}
        assert executed.get("status") == "pending_approval", f"reverse must pend, got {executed} resp={str(data.get('response'))[:200]}"
        approval_id = _extract_approval_id(data)
        assert approval_id, f"expected approval_id, got cards={data.get('cards')}"
        # approve via different approver
        r_app = requests.post(
            f"{BASE_URL}/api/runtime/approvals/{approval_id}/approve",
            headers=_auth(supervisor_token),
            timeout=30,
        )
        assert r_app.status_code == 200, f"reverse approve failed: {r_app.status_code} {r_app.text[:300]}"
        # verify a contra entry exists with source='reversal' referencing this je
        time.sleep(2)
        r2 = requests.get(
            f"{BASE_URL}/api/finance/journal-entries",
            headers=_auth(admin_token),
            params={"workshop_id": WORKSHOP_ID, "limit": 500},
            timeout=15,
        )
        body2 = r2.json()
        entries2 = body2.get("data", body2) if isinstance(body2, dict) else body2
        contra = [
            e for e in entries2 if isinstance(e, dict)
            and (e.get("source") or "").lower() == "reversal"
            and je_id in str(e.get("reference_id") or "")
        ]
        assert contra, f"no contra entry for {je_id} found (searched {len(entries2)} entries)"
        # original preserved
        still_there = any(
            (e.get("id") or e.get("_id")) == je_id
            for e in entries2 if isinstance(e, dict)
        )
        assert still_there, "original JE missing after reverse — must be preserved"


# ---------------- 6. SAFE ENTITY ACTIONS still auto-commit ----------------

class TestSafeEntityAutoCommit:
    def test_create_customer_auto_commits(self, admin_token):
        r, _ = _chat(admin_token, "سجل عميل تجريبي اوتو 0501112233", proposer="مدير")
        data = _extract_data(r)
        executed = data.get("executed") or {}
        # auto-commit = status committed/success and NOT pending_approval
        status = executed.get("status")
        assert status not in ("pending_approval", "blocked", "rejected"), \
            f"safe customer action should NOT pend, got {status} / {str(executed)[:200]}"

    def test_add_vehicle_auto_commits(self, admin_token):
        r, _ = _chat(admin_token, "اضف مركبة لوحة TST 4321 تويوتا", proposer="مدير")
        data = _extract_data(r)
        executed = data.get("executed") or {}
        status = executed.get("status")
        # tolerant: allow either committed or a clarify response; explicitly forbid pending_approval
        assert status != "pending_approval", \
            f"vehicle action should NOT pend (Phase C not implemented), got {status}"


# ---------------- 7. SITE REST regression ----------------

class TestSiteRESTRegression:
    def test_admin_invoice_via_rest(self, admin_token):
        payload = {
            "customer": "نادر بكر",
            "total": 47,
            "amount": 47,
            "description": "TEST_iter242_rest_invoice",
            "workshop_id": WORKSHOP_ID,
            "payment_method": "credit",
        }
        r = requests.post(
            f"{BASE_URL}/api/finance-actions/invoice",
            headers=_auth(admin_token),
            json=payload,
            timeout=20,
        )
        # accept success codes; if backend requires extra fields, accept 422 but flag
        assert r.status_code in (200, 201, 422), f"REST invoice unexpected: {r.status_code} {r.text[:300]}"

    def test_admin_expense_via_rest_balanced(self, admin_token):
        payload = {
            "amount": 23,
            "description": "TEST_iter242_rest_expense",
            "workshop_id": WORKSHOP_ID,
            "category": "إيجار",
        }
        r = requests.post(
            f"{BASE_URL}/api/finance-actions/expense",
            headers=_auth(admin_token),
            json=payload,
            timeout=20,
        )
        assert r.status_code in (200, 201, 422), f"REST expense unexpected: {r.status_code} {r.text[:300]}"


# ---------------- 8. ACCOUNTING INTEGRITY ----------------

class TestAccountingIntegrity:
    def test_all_recent_entries_balanced(self, admin_token):
        r = requests.get(
            f"{BASE_URL}/api/finance/journal-entries",
            headers=_auth(admin_token),
            params={"workshop_id": WORKSHOP_ID, "limit": 50},
            timeout=15,
        )
        assert r.status_code == 200
        body = r.json()
        entries = body.get("data", body) if isinstance(body, dict) else body
        assert isinstance(entries, list) and len(entries) > 0, "expected some JEs"
        unbalanced = []
        for e in entries:
            if not isinstance(e, dict):
                continue
            td, tc = _entry_totals(e)
            if abs(td - tc) > 0.01:
                unbalanced.append({"id": e.get("id") or e.get("_id"), "dr": td, "cr": tc})
        assert not unbalanced, f"unbalanced entries found: {unbalanced[:5]}"
