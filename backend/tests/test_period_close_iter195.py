"""
Iter 195 — Period Close endpoint + Firewall regression
Tests:
  1) POST /api/finance/period-close — should return success:true.
     Today's close was already executed manually, so we EXPECT closed:false
     (no revenue/expense balances left). Treat that as PASS per agent context.
     If a fresh DB scenario triggers closed:true, additionally assert structural
     fields (total_debit==total_credit, lines_count>0, journal_entry_id, net_income_transferred).
  2) Re-run with the same as_of_date — must still return success:true with
     closed:false (idempotent; period_close-sourced entries are excluded from
     balance computation so no new balances surface).
  3) GET /api/firewall/status — balance_health_percent must remain 100.
  4) GET /api/journal-entries — the existing period_close JE (if any) is still loadable.
"""
import os
import datetime as dt
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://contract-audit-demo.preview.emergentagent.com").rstrip("/")
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
    def test_period_close_returns_success(self):
        r = _post_close()
        assert r.status_code == 200, f"HTTP {r.status_code}: {r.text[:300]}"
        body = r.json()
        assert body.get("success") is True, f"success not True: {body}"
        data = body.get("data") or {}
        assert "closed" in data
        assert data.get("as_of_date") == TODAY

        if data.get("closed") is True:
            # If something was still open, validate structural correctness
            assert data.get("journal_entry_id"), "missing journal_entry_id"
            assert isinstance(data.get("net_income_transferred"), (int, float))
            assert int(data.get("lines_count") or 0) > 0
            # Balanced: total_revenue_closed - total_expense_closed == net_income
            rev = float(data.get("total_revenue_closed") or 0)
            exp = float(data.get("total_expense_closed") or 0)
            net = float(data.get("net_income_transferred") or 0)
            assert abs((rev - exp) - net) < 0.01
        else:
            # Expected path on this DB (already closed manually today)
            assert "message" in data

    def test_period_close_idempotent_second_call(self):
        # Second call with same date must NOT create another close
        r = _post_close()
        assert r.status_code == 200
        body = r.json()
        assert body.get("success") is True
        data = body.get("data") or {}
        # Either was already closed (closed:false now) OR fresh-closed (closed:true).
        # Per main agent note: expected closed:false.
        assert data.get("closed") is False, (
            f"Expected idempotent closed:false on second call but got: {data}"
        )


# --- Firewall regression ---
class TestFirewallRegression:
    def test_firewall_status_health_100(self):
        r = requests.get(f"{BASE_URL}/api/firewall/status", timeout=30)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        # Endpoint shape: {"success":true,"data":{"summary":{...}}} OR flat
        summary = (body.get("data") or {}).get("summary") or body.get("summary") or body.get("data") or body
        health = summary.get("balance_health_percent")
        assert health is not None, f"balance_health_percent missing in {body}"
        assert float(health) == 100.0, f"Expected 100% health, got {health}"


# --- Journal entries regression: period_close source still loadable ---
class TestJournalEntriesRegression:
    def test_journal_entries_loadable(self):
        r = requests.get(
            f"{BASE_URL}/api/finance/journal-entries",
            params={"workshop_id": WORKSHOP_ID, "limit": 200},
            timeout=30,
        )
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        items = data.get("data") if isinstance(data, dict) else data
        if isinstance(items, dict):
            items = items.get("items") or items.get("entries") or []
        assert isinstance(items, list)
        # At least one journal entry exists
        assert len(items) > 0, "No journal entries returned"
        # If any period_close exists, validate structure
        pcs = [e for e in items if str(e.get("source") or "").lower() == "period_close"]
        if pcs:
            je = pcs[0]
            lines = je.get("lines") or []
            assert len(lines) > 0
            tot_dr = sum(float(l.get("debit") or 0) for l in lines)
            tot_cr = sum(float(l.get("credit") or 0) for l in lines)
            assert abs(tot_dr - tot_cr) < 0.01, f"period_close JE unbalanced dr={tot_dr} cr={tot_cr}"
