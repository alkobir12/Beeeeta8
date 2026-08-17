"""Backend tests for TEST 1 (delete=reversal), TEST 2 (idempotency), TEST 3 (KPI period filtering)."""
import os
import uuid
import random
import pytest
import requests
from datetime import date

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://canonical-integrity.preview.emergentagent.com").rstrip("/")
WORKSHOP = "finmodule-sync"
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{API}/auth/login", json={"username": "مدير", "password": "010101"}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def client(token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def created_entry(client):
    """Create a disposable balanced entry with unique amount+description to avoid POST-dedup collisions with prior test runs."""
    today = date.today().isoformat()
    amount = round(random.uniform(0.11, 0.99), 2)
    payload = {
        "date": today,
        "description": f"قيد اختبار مؤقت للحذف العكسي {uuid.uuid4().hex[:6]}",
        "transaction_type": "other",
        "total": amount,
        "lines": [
            {"account": "003", "account_name": "النقد", "debit": amount, "credit": 0},
            {"account": "024", "account_name": "الإيرادات", "debit": 0, "credit": amount},
        ],
    }
    r = client.post(f"{API}/finance/journal-entries?workshop_id={WORKSHOP}", json=payload, timeout=60)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("success") is True, body
    entry_id = body.get("id")
    if not entry_id:
        d = body.get("data")
        if isinstance(d, list) and d:
            entry_id = d[0].get("id")
        elif isinstance(d, dict):
            entry_id = d.get("id")
    assert entry_id, f"missing id in response: {body}"
    return entry_id


class TestReversal:
    def test_delete_creates_reversal(self, client, created_entry):
        r = client.delete(f"{API}/finance/journal-entries/{created_entry}?workshop_id={WORKSHOP}", timeout=60)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("success") is True, body
        data = body.get("data") or {}
        assert data.get("reversed") is True, f"expected reversed=True: {data}"
        entries = data.get("entries") or []
        assert entries and entries[0].get("posted") is True, f"expected posted reversal entry: {data}"
        assert entries[0].get("journal_id"), f"expected reversal journal_id: {data}"

    def test_original_still_exists(self, client, created_entry):
        r = client.get(f"{API}/finance/journal-entries/{created_entry}?workshop_id={WORKSHOP}", timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("success") is True, body
        assert body.get("data", {}).get("id") == created_entry

    def test_delete_is_idempotent(self, client, created_entry):
        """TEST 2: second DELETE must not create another reversal."""
        r = client.delete(f"{API}/finance/journal-entries/{created_entry}?workshop_id={WORKSHOP}", timeout=60)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("success") is True, body
        data = body.get("data") or {}
        # idempotent flag lives inside data.entries[0] per current engine response shape
        entries = data.get("entries") or []
        assert entries, f"expected entries list: {body}"
        assert entries[0].get("idempotent") is True, f"expected idempotent=True on 2nd delete: {body}"
        assert data.get("reversed") is False, f"reversed should be False on idempotent repeat: {data}"


class TestKPIPeriodFiltering:
    """TEST 3: verify income-statement totals differ by range and future-inclusive >= today-bounded."""

    def _totals(self, client, start, end):
        r = client.get(
            f"{API}/finance/reports/income-statement",
            params={"workshop_id": WORKSHOP, "start_date": start, "end_date": end},
            timeout=60,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        data = body.get("data") or body
        # totals may be under data.totals or top-level revenues/expenses
        totals = data.get("totals") or {}
        revenue = totals.get("revenue") or totals.get("total_revenue") or data.get("total_revenue") or data.get("revenue") or 0
        expenses = totals.get("expenses") or totals.get("total_expenses") or data.get("total_expenses") or data.get("expenses") or 0
        return float(revenue or 0), float(expenses or 0), body

    def test_ranges_differ(self, client):
        today = date.today().isoformat()
        rev_today, exp_today, _ = self._totals(client, today, today)
        rev_ytd, exp_ytd, _ = self._totals(client, "2026-01-01", today)
        rev_all, exp_all, _ = self._totals(client, "2000-01-01", "2099-12-31")

        print(f"today ({today}): rev={rev_today} exp={exp_today}")
        print(f"ytd  : rev={rev_ytd}   exp={exp_ytd}")
        print(f"all  : rev={rev_all}   exp={exp_all}")

        # ALL (with FAR_FUTURE_DATE) must be >= YTD-to-today
        assert rev_all >= rev_ytd, f"all-time revenue ({rev_all}) should be >= YTD-to-today ({rev_ytd})"
        assert exp_all >= exp_ytd, f"all-time expenses ({exp_all}) should be >= YTD-to-today ({exp_ytd})"
        # today range should not exceed all-time
        assert rev_today <= rev_all
        assert exp_today <= exp_all
        # today range should be smaller than all (unless today happens to contain all entries — very unlikely)
        assert rev_today < rev_all or exp_today < exp_all, (
            "today's totals should be smaller than all-time (given multi-day entries exist)"
        )

    def test_far_future_end_date_accepted(self, client):
        """The FAR_FUTURE_DATE=2099-12-31 must be accepted by the backend and return >= today-bounded totals."""
        today = date.today().isoformat()
        rev_today_end, _, _ = self._totals(client, "2000-01-01", today)
        rev_far, _, _ = self._totals(client, "2000-01-01", "2099-12-31")
        assert rev_far >= rev_today_end
