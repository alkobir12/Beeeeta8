"""
Iter 196 — Period Close final verifications (idempotency + income statement + trial balance + firewall).

Spec being verified:
  1) POST /api/finance/period-close — first call may close (closed:true) OR already-closed (closed:false).
     If closed:true: returns balanced JE (total_debit==total_credit), net_income_transferred number.
  2) Repeated POST with the same as_of_date — must return closed:false with
     message "يوجد قيد إقفال مسبق بتاريخ ..." and existing_journal_entry_id.
  3) GET /api/finance/reports/income-statement (after close) — Revenue=0, Expenses=0, Net=0.
  4) GET /api/finance/reports/trial-balance — total_debit==total_credit (balanced).
  5) GET /api/firewall/status — balance_health_percent == 100, unbalanced count == 0.
"""
import os
import datetime as dt
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://erp-compliance-check.preview.emergentagent.com").rstrip("/")
WORKSHOP_ID = "finmodule-sync"
TODAY = dt.date.today().isoformat()


def _post_close(as_of: str = TODAY):
    return requests.post(
        f"{BASE_URL}/api/finance/period-close",
        params={"workshop_id": WORKSHOP_ID},
        json={"as_of_date": as_of},
        timeout=60,
    )


# --- Period Close core ---
class TestPeriodClose:
    def test_first_call_success_or_already_closed(self):
        r = _post_close()
        assert r.status_code == 200, f"HTTP {r.status_code}: {r.text[:400]}"
        body = r.json()
        assert body.get("success") is True
        data = body.get("data") or {}
        assert data.get("as_of_date") == TODAY
        assert "closed" in data

        if data.get("closed") is True:
            assert data.get("journal_entry_id")
            tot_dr = float(data.get("total_debit") or 0)
            tot_cr = float(data.get("total_credit") or 0)
            assert abs(tot_dr - tot_cr) < 0.01, f"unbalanced close JE dr={tot_dr} cr={tot_cr}"
            assert isinstance(data.get("net_income_transferred"), (int, float))
        else:
            # Already closed earlier — must hint message + existing JE id
            msg = (data.get("message") or "")
            assert "إقفال" in msg or "مسبق" in msg or "already" in msg.lower(), f"unexpected message: {msg}"
            assert data.get("existing_journal_entry_id"), f"missing existing_journal_entry_id: {data}"

    def test_idempotent_second_call_blocked(self):
        # Ensure there is at least one close to lock against
        _post_close()
        r = _post_close()
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        data = body.get("data") or {}
        assert body.get("success") is True
        assert data.get("closed") is False, f"Expected idempotent block but got: {data}"
        assert data.get("existing_journal_entry_id"), f"missing existing_journal_entry_id: {data}"
        msg = data.get("message") or ""
        assert msg, "missing idempotent message"


# --- Income Statement reports Revenue=0, Expenses=0, Net=0 after close ---
class TestIncomeStatementZeroAfterClose:
    def test_income_statement_zero(self):
        # Make sure we're closed first
        _post_close()
        r = requests.get(
            f"{BASE_URL}/api/finance/reports/income-statement",
            params={"workshop_id": WORKSHOP_ID},
            timeout=30,
        )
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        data = body.get("data") if isinstance(body, dict) and "data" in body else body
        # Common shapes: {total_revenue, total_expenses, net_income} or {revenue, expenses, net}
        rev = float(data.get("total_revenue") or data.get("revenue") or data.get("total_revenues") or 0)
        exp = float(data.get("total_expenses") or data.get("expenses") or data.get("total_expense") or 0)
        net = float(data.get("net_income") or data.get("net") or data.get("net_profit") or 0)
        assert abs(rev) < 0.01, f"expected Revenue=0 after close, got {rev}"
        assert abs(exp) < 0.01, f"expected Expenses=0 after close, got {exp}"
        assert abs(net) < 0.01, f"expected Net=0 after close, got {net}"


# --- Trial Balance stays balanced ---
class TestTrialBalanceBalanced:
    def test_trial_balance_total_dr_eq_cr(self):
        r = requests.get(
            f"{BASE_URL}/api/finance/reports/trial-balance",
            params={"workshop_id": WORKSHOP_ID},
            timeout=30,
        )
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        data = body.get("data") if isinstance(body, dict) and "data" in body else body
        tot_dr = float(data.get("total_debit") or data.get("totals", {}).get("debit") or 0)
        tot_cr = float(data.get("total_credit") or data.get("totals", {}).get("credit") or 0)
        assert abs(tot_dr - tot_cr) < 0.01, f"trial-balance unbalanced dr={tot_dr} cr={tot_cr}"


# --- Firewall regression ---
class TestFirewallRegression:
    def test_firewall_100_unbalanced_zero(self):
        r = requests.get(f"{BASE_URL}/api/firewall/status", timeout=30)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        summary = (body.get("data") or {}).get("summary") or body.get("summary") or body.get("data") or body
        health = summary.get("balance_health_percent")
        assert health is not None
        assert float(health) == 100.0, f"Expected 100% health, got {health}"
        unbalanced = summary.get("unbalanced_count")
        if unbalanced is None:
            unbalanced = summary.get("unbalanced") or 0
        assert int(unbalanced or 0) == 0, f"Expected 0 unbalanced, got {unbalanced}"
