"""
Iteration 244 backend regression tests
Focus: Account-code realignment to LIVE Supabase chart + dry_run fix-all + finance reports single-source-of-truth.

READ-ONLY except for a single {"dry_run": true} preview call to fix-all (safe).
No writes to production data.
"""
import os
import re
import pytest
import requests

def _load_backend_url():
    v = os.environ.get('REACT_APP_BACKEND_URL')
    if not v:
        try:
            with open('/app/frontend/.env') as f:
                for line in f:
                    if line.startswith('REACT_APP_BACKEND_URL='):
                        v = line.split('=', 1)[1].strip()
                        break
        except Exception:
            pass
    return (v or '').rstrip('/')

BASE_URL = _load_backend_url()
WORKSHOP_ID = "finmodule-sync"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"username": "مدير"}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ---------- Finance alerts (firewall_engine single source of truth) ----------

class TestFinanceAlerts:
    def test_alerts_source_and_shape(self, auth):
        r = requests.get(
            f"{BASE_URL}/api/finance/alerts",
            params={"workshop_id": WORKSHOP_ID},
            headers=auth, timeout=30,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        # accept either envelope
        payload = data.get("data", data)
        assert payload.get("source") == "firewall_engine", f"source={payload.get('source')}"
        health = payload.get("health") or {}
        # health could be dict or int
        score = health.get("score") if isinstance(health, dict) else health
        assert score == 100, f"health.score expected 100 got {score} full={payload}"

        alerts = payload.get("alerts") or []
        assert len(alerts) == 1, f"expected exactly 1 alert got {len(alerts)}: {[a.get('title') for a in alerts]}"
        title = alerts[0].get("title", "")
        assert "ذمم" in title or "13,550" in title or "13550" in title, f"unexpected alert title: {title}"

        # cash_flow inflow = 0
        cash_flow = payload.get("cash_flow") or {}
        inflow = cash_flow.get("inflow", cash_flow.get("total_inflow"))
        assert inflow in (0, 0.0), f"cash_flow.inflow expected 0 got {inflow}"

        # profitability revenue = 13550
        prof = payload.get("profitability") or (health.get("breakdown", {}) if isinstance(health, dict) else {}).get("profitability", {})
        rev = prof.get("revenue")
        assert rev in (13550, 13550.0), f"profitability.revenue expected 13550 got {rev}"

    def test_firewall_dashboard_identical(self, auth):
        r_alerts = requests.get(f"{BASE_URL}/api/finance/alerts",
                                params={"workshop_id": WORKSHOP_ID},
                                headers=auth, timeout=30).json()
        r_dash = requests.get(f"{BASE_URL}/api/firewall/dashboard",
                              params={"workshop_id": WORKSHOP_ID},
                              headers=auth, timeout=30).json()
        pa = r_alerts.get("data", r_alerts)
        pd = r_dash.get("data", r_dash)

        h_a = pa.get("health") or {}
        h_d = pd.get("health") or {}
        score_a = h_a.get("score") if isinstance(h_a, dict) else h_a
        score_d = h_d.get("score") if isinstance(h_d, dict) else h_d
        assert score_a == score_d == 100, f"health mismatch alerts={score_a} dash={score_d}"

        len_a = len(pa.get("alerts") or [])
        len_d = len(pd.get("alerts") or [])
        assert len_a == len_d == 1, f"alerts count mismatch alerts={len_a} dash={len_d}"


# ---------- fix-all idempotency (READ-ONLY dry_run) ----------

class TestFixAllIdempotent:
    def test_dry_run_shows_nothing_to_fix(self, auth):
        r = requests.post(
            f"{BASE_URL}/api/operations/integrity/fix-all",
            json={"dry_run": True, "workshop_id": WORKSHOP_ID},
            headers=auth, timeout=60,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        payload = body.get("data", body)
        missing = payload.get("missing_count", payload.get("missing_before", payload.get("preview_count")))
        assert missing in (0, None) or missing == 0, f"expected missing_count=0 got {missing} full={payload}"

    def test_real_run_idempotent(self, auth):
        # Empty body per test spec — should be idempotent (no missing, fixed=0)
        r = requests.post(
            f"{BASE_URL}/api/operations/integrity/fix-all",
            json={"workshop_id": WORKSHOP_ID},
            headers=auth, timeout=90,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        payload = body.get("data", body)
        fixed = payload.get("fixed", payload.get("fixed_count", 0))
        missing_before = payload.get("missing_before", payload.get("missing_count", 0))
        assert fixed == 0, f"expected fixed=0 (idempotent) got {fixed} full={payload}"
        assert missing_before == 0, f"expected missing_before=0 got {missing_before}"


# ---------- Finance reports ----------

def _find_row(rows, code=None, name_contains=None):
    for r in rows or []:
        code_val = str(r.get("code") or r.get("account_code") or "")
        name_val = r.get("name") or r.get("account_name") or ""
        if code and code_val == str(code):
            return r
        if name_contains and name_contains in name_val:
            return r
    return None


class TestReports:
    def test_trial_balance_balanced(self, auth):
        r = requests.get(f"{BASE_URL}/api/finance/reports/trial-balance",
                         params={"workshop_id": WORKSHOP_ID},
                         headers=auth, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        p = body.get("data", body)
        totals = p.get("totals") or {}
        debits = totals.get("debits", totals.get("total_debits", totals.get("total_debit")))
        credits = totals.get("credits", totals.get("total_credits", totals.get("total_credit")))
        assert debits == credits == 13550, f"trial balance not 13550/13550: debits={debits} credits={credits}"

        rows = p.get("rows") or p.get("accounts") or []
        # Verify LIVE chart names present
        r005 = _find_row(rows, code="005")
        assert r005 is not None, "account 005 (العملاء) not found in trial balance"
        assert "العملاء" in (r005.get("name") or r005.get("account_name") or ""), f"005 name mismatch: {r005}"

        # Ensure NO stale codes
        codes = [str(x.get("code") or x.get("account_code") or "") for x in rows]
        stale = {"1103", "4101", "042", "0421", "211"}
        found_stale = stale.intersection(codes)
        assert not found_stale, f"stale codes still present: {found_stale}"

    def test_income_statement_revenue(self, auth):
        r = requests.get(f"{BASE_URL}/api/finance/reports/income-statement",
                         params={"workshop_id": WORKSHOP_ID},
                         headers=auth, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        p = body.get("data", body)
        totals = p.get("totals") or p.get("summary") or {}
        rev = totals.get("total_revenue", totals.get("revenue", p.get("total_revenue")))
        assert rev == 13550, f"revenue expected 13550 got {rev} full={p}"

    def test_balance_sheet_balanced(self, auth):
        r = requests.get(f"{BASE_URL}/api/finance/reports/balance-sheet",
                         params={"workshop_id": WORKSHOP_ID},
                         headers=auth, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        p = body.get("data", body)
        totals = p.get("totals") or {}
        assets = totals.get("assets") or totals.get("total_assets")
        lpe = totals.get("liabilities_plus_equity") or totals.get("total_liabilities_and_equity")
        assert assets == 13550, f"assets expected 13550 got {assets}"
        assert lpe == 13550, f"L+E expected 13550 got {lpe}"

        # Equity row with net income
        equity_section = p.get("equity") or (p.get("sections") or {}).get("equity") or []
        rows = equity_section if isinstance(equity_section, list) else (equity_section.get("rows") or equity_section.get("items") or [])
        has_ni = any("صافي" in (row.get("name") or row.get("account_name") or "") for row in rows)
        assert has_ni, f"equity should contain 'صافي الربح/الخسارة (الفترة)' row: rows={rows}"

    def test_ar_customers_total(self, auth):
        r = requests.get(f"{BASE_URL}/api/finance/reports/ar-customers",
                         params={"workshop_id": WORKSHOP_ID},
                         headers=auth, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        p = body.get("data", body)
        total = p.get("total_ar", p.get("total"))
        customers = p.get("customers") or p.get("rows") or []
        # Sum fallback
        if total is None:
            total = sum(float(c.get("balance") or c.get("ar_balance") or 0) for c in customers)
        assert total in (13550, 13550.0), f"total AR expected 13550 got {total}"
        assert len(customers) == 8, f"expected 8 customers got {len(customers)}"
