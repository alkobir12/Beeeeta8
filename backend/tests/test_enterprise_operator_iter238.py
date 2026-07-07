"""
Iteration 238 — Enterprise Operator backend tests
Covers:
  Phase 4: Financial actions (/api/finance-actions/{invoice,payment,expense}) + idempotency + RBAC
  Phase 3: Strict Four-Eyes + RBAC on approval
  Phase 2: Runtime drafts persistence (list/stats)
  Regressions: bot auto-commit (/api/runtime/execute), journal-entries fetch
"""
import os
import time
import uuid
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://accounting-engine-6.preview.emergentagent.com").rstrip("/")
WS = "finmodule-sync"

# Common headers for an admin (Arabic name in body, ASCII role header)
H_ADMIN = {"Content-Type": "application/json", "x-user-role": "admin"}
H_SUP = {"Content-Type": "application/json", "x-user-role": "supervisor"}
H_ACC = {"Content-Type": "application/json", "x-user-role": "accountant"}
H_TECH = {"Content-Type": "application/json", "x-user-role": "technician"}


# ---------- Phase 4: Financial actions ----------
class TestFinanceActions:
    def setup_method(self):
        self.ref_invoice = f"TEST_INV_{uuid.uuid4().hex[:8]}"
        self.ref_payment = f"TEST_PAY_{uuid.uuid4().hex[:8]}"
        self.ref_expense = f"TEST_EXP_{uuid.uuid4().hex[:8]}"

    def _assert_balanced(self, je):
        debit = sum(float(l.get("debit") or 0) for l in je.get("lines", []))
        credit = sum(float(l.get("credit") or 0) for l in je.get("lines", []))
        assert round(debit, 2) == round(credit, 2), f"Unbalanced: D={debit} C={credit}"
        assert debit > 0

    def test_invoice_post_and_idempotent(self):
        payload = {
            "customer": "TEST_عميل_اختبار",
            "items": [{"name": "زيت محرك", "price": 100.0, "quantity": 1},
                      {"name": "فلتر", "price": 50.0, "quantity": 2}],
            "payment_method": "credit",
            "by": "مدير",
            "reference_id": self.ref_invoice,
            "workshop_id": WS,
        }
        r1 = requests.post(f"{BASE_URL}/api/finance-actions/invoice", json=payload, headers=H_ADMIN, timeout=30)
        assert r1.status_code == 200, f"invoice failed: {r1.status_code} {r1.text}"
        body1 = r1.json()
        assert body1.get("success") is True, body1
        d1 = body1.get("data", body1)
        assert d1.get("posted") is True or d1.get("idempotent") is True, d1
        # Balance check
        debit = float(d1.get("debit") or 0)
        credit = float(d1.get("credit") or 0)
        if debit or credit:
            assert round(debit, 2) == round(credit, 2), f"Unbalanced: D={debit} C={credit}"

        # Repost same payload — must be idempotent
        r2 = requests.post(f"{BASE_URL}/api/finance-actions/invoice", json=payload, headers=H_ADMIN, timeout=30)
        assert r2.status_code == 200, r2.text
        d2 = r2.json().get("data", r2.json())
        assert d2.get("idempotent") is True or d2.get("duplicate") is True, f"Expected idempotent on repost: {d2}"

    def test_invoice_rbac_technician_403(self):
        payload = {
            "customer": "TEST_عميل_rbac",
            "items": [{"name": "x", "price": 10.0, "quantity": 1}],
            "payment_method": "credit",
            "by": "مستخدم اختبار",
            "reference_id": f"TEST_RBAC_{uuid.uuid4().hex[:6]}",
            "workshop_id": WS,
        }
        r = requests.post(f"{BASE_URL}/api/finance-actions/invoice", json=payload, headers=H_TECH, timeout=20)
        assert r.status_code == 403, f"Expected 403 for technician, got {r.status_code} {r.text}"
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        # detail.error or top-level error
        detail = body.get("detail") if isinstance(body, dict) else None
        err = (detail or {}).get("error") if isinstance(detail, dict) else body.get("error")
        assert err in ("permission_denied", "forbidden", "rbac_denied") or "permission" in str(body).lower()

    def test_payment_post_and_idempotent(self):
        payload = {
            "customer": "TEST_عميل_دفع",
            "amount": 200.0,
            "payment_method": "cash",
            "by": "مدير",
            "reference_id": self.ref_payment,
            "workshop_id": WS,
        }
        r1 = requests.post(f"{BASE_URL}/api/finance-actions/payment", json=payload, headers=H_ADMIN, timeout=30)
        assert r1.status_code == 200, r1.text
        b1 = r1.json(); assert b1.get("success") is True, b1
        r2 = requests.post(f"{BASE_URL}/api/finance-actions/payment", json=payload, headers=H_ADMIN, timeout=30)
        assert r2.status_code == 200, r2.text
        d2 = r2.json().get("data", r2.json())
        assert d2.get("idempotent") is True or d2.get("duplicate") is True, f"Expected idempotent: {d2}"

    def test_expense_post_and_idempotent(self):
        payload = {
            "description": "TEST_مصروف_اختبار",
            "amount": 75.0,
            "category": "قرطاسية",
            "by": "مدير",
            "reference_id": self.ref_expense,
            "workshop_id": WS,
        }
        r1 = requests.post(f"{BASE_URL}/api/finance-actions/expense", json=payload, headers=H_ADMIN, timeout=30)
        assert r1.status_code == 200, r1.text
        b1 = r1.json(); assert b1.get("success") is True, b1
        r2 = requests.post(f"{BASE_URL}/api/finance-actions/expense", json=payload, headers=H_ADMIN, timeout=30)
        assert r2.status_code == 200, r2.text
        d2 = r2.json().get("data", r2.json())
        assert d2.get("idempotent") is True or d2.get("duplicate") is True, d2


# ---------- Phase 3: Four-Eyes + RBAC ----------
class TestFourEyesAndRBAC:
    def _create_draft(self, proposer="مدير", headers=None):
        body = {
            "action": "update_customer",
            "payload": {"customer_id": "X-TEST", "set": {"phone": "0501112233"}},
            "proposer": proposer,
        }
        r = requests.post(f"{BASE_URL}/api/runtime/drafts", json=body, headers=headers or H_ADMIN, timeout=20)
        assert r.status_code in (200, 201), f"draft create failed: {r.status_code} {r.text}"
        body_r = r.json()
        d = body_r.get("data", body_r)
        # Try common keys
        draft_id = d.get("id") or d.get("draft_id") or (d.get("draft") or {}).get("id")
        assert draft_id, f"no draft id in {body_r}"
        return draft_id, d

    def _request_approval(self, draft_id, requester="مدير", headers=None):
        body = {"requester": requester}
        r = requests.post(f"{BASE_URL}/api/runtime/drafts/{draft_id}/request_approval", json=body, headers=headers or H_ADMIN, timeout=20)
        assert r.status_code in (200, 201), f"request_approval failed: {r.status_code} {r.text}"
        body_r = r.json()
        d = body_r.get("data", body_r)
        approval_id = d.get("approval_id") or d.get("id") or (d.get("approval") or {}).get("id")
        assert approval_id, f"no approval id in {body_r}"
        return approval_id

    def test_self_approval_blocked_then_other_approves(self):
        draft_id, _ = self._create_draft(proposer="مدير")
        approval_id = self._request_approval(draft_id, requester="مدير")

        # Self approval by مدير → 403 four_eyes_violation
        r_self = requests.post(
            f"{BASE_URL}/api/runtime/approvals/{approval_id}/approve",
            json={"by": "مدير", "approver": "مدير"},
            headers=H_ADMIN, timeout=20,
        )
        assert r_self.status_code == 403, f"Expected 403 self-approval, got {r_self.status_code} {r_self.text}"
        body = r_self.json()
        detail = body.get("detail") if isinstance(body, dict) else None
        err = (detail or {}).get("error") if isinstance(detail, dict) else body.get("error")
        assert err == "four_eyes_violation", f"Expected four_eyes_violation, got {body}"

        # Different approver (احمد1, supervisor) → success
        r_ok = requests.post(
            f"{BASE_URL}/api/runtime/approvals/{approval_id}/approve",
            json={"by": "احمد1", "approver": "احمد1"},
            headers=H_SUP, timeout=20,
        )
        assert r_ok.status_code == 200, f"Expected approver success, got {r_ok.status_code} {r_ok.text}"
        body_ok = r_ok.json()
        d = body_ok.get("data", body_ok)
        assert d.get("status") in ("approved", "committed") or d.get("approved") is True or body_ok.get("success") is True, body_ok

    def test_approval_rbac_accountant_denied(self):
        draft_id, _ = self._create_draft(proposer="مدير")
        approval_id = self._request_approval(draft_id, requester="مدير")

        r = requests.post(
            f"{BASE_URL}/api/runtime/approvals/{approval_id}/approve",
            json={"by": "فرج1"},
            headers=H_ACC, timeout=20,
        )
        assert r.status_code == 403, f"Expected 403 for accountant, got {r.status_code} {r.text}"
        body = r.json()
        detail = body.get("detail") if isinstance(body, dict) else None
        err = (detail or {}).get("error") if isinstance(detail, dict) else body.get("error")
        assert err in ("permission_denied", "rbac_denied", "forbidden"), f"unexpected: {body}"


# ---------- Phase 2: Runtime persistence ----------
class TestRuntimePersistence:
    def test_draft_list_and_stats(self):
        body = {
            "action": "update_customer",
            "payload": {"customer_id": "X-PERSIST", "set": {"phone": "0509999999"}},
            "proposer": "مدير",
        }
        r = requests.post(f"{BASE_URL}/api/runtime/drafts", json=body, headers=H_ADMIN, timeout=20)
        assert r.status_code in (200, 201), r.text
        body_r = r.json(); d_create = body_r.get("data", body_r)
        draft_id = d_create.get("id") or d_create.get("draft_id") or (d_create.get("draft") or {}).get("id")
        assert draft_id

        r_list = requests.get(f"{BASE_URL}/api/runtime/drafts", headers=H_ADMIN, timeout=20)
        assert r_list.status_code == 200, r_list.text
        body_l = r_list.json()
        data = body_l.get("data", body_l)
        drafts = data if isinstance(data, list) else (data.get("drafts") or data.get("items") or [])
        ids = [d.get("id") for d in drafts if isinstance(d, dict)]
        assert draft_id in ids, f"draft {draft_id} not in list ({len(ids)} items)"

        r_stats = requests.get(f"{BASE_URL}/api/runtime/stats", headers=H_ADMIN, timeout=20)
        assert r_stats.status_code == 200, r_stats.text
        st = r_stats.json()
        assert isinstance(st, dict)


# ---------- Regressions ----------
class TestRegressions:
    def test_bot_safe_auto_commit(self):
        body = {"text": "سجل عميل اسمه عميل تجريبي ريجريشن", "proposer": "مدير"}
        r = requests.post(f"{BASE_URL}/api/runtime/execute", json=body, headers=H_ADMIN, timeout=60)
        assert r.status_code in (200, 201), f"runtime/execute failed: {r.status_code} {r.text}"
        d = r.json()
        status = d.get("status") or (d.get("result") or {}).get("status")
        assert status in ("committed", "pending_approval", "queued", "approved"), f"unexpected status: {d}"

    def test_journal_entries_fetch(self):
        r = requests.get(f"{BASE_URL}/api/finance/journal-entries", params={"workshop_id": WS, "limit": 10}, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("success") is True or "entries" in d or "journal_entries" in d, d
