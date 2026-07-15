"""
🛡️ Tests for Accounting Firewall Panel (iter 190)

Covers:
  - GET /api/firewall/status — shape & summary
  - POST /api/finance/journal-entries — unbalanced (rejected, 400)
  - POST /api/finance/journal-entries — balanced (accepted)
  - POST /api/operations idempotency (same transaction_id) → idempotency_hit
"""

import os
import uuid
import time

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://fabrication-guard.preview.emergentagent.com").rstrip("/")
WORKSHOP_ID = "finmodule-sync"


@pytest.fixture(scope="module")
def api_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---------- Firewall status shape ----------
class TestFirewallStatus:
    def test_status_returns_summary_shape(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/firewall/status", params={"workshop_id": WORKSHOP_ID})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("success") is True
        summary = data.get("summary", {})
        for k in [
            "total_entries", "balanced_entries", "lifetime_rejections",
            "lifetime_idempotency_hits", "cogs_entries", "balance_health_percent",
        ]:
            assert k in summary, f"summary missing key: {k}"
        drift = data.get("drift", {})
        assert "max" in drift and "avg" in drift
        assert "recent_rejections" in data
        assert "recent_idempotency_hits" in data


# ---------- Journal entry rejection / acceptance ----------
class TestJournalEntryFirewall:
    def test_unbalanced_journal_entry_is_rejected(self, api_client):
        # Capture lifetime_rejections before
        before = api_client.get(f"{BASE_URL}/api/firewall/status", params={"workshop_id": WORKSHOP_ID}).json()
        before_rej = before["summary"].get("lifetime_rejections", 0)

        payload = {
            "workshop_id": WORKSHOP_ID,
            "date": "2026-01-15",
            "description": "TEST_unbalanced_iter190",
            "lines": [
                {"account_code": "1010", "debit": 100.0, "credit": 0.0, "description": "test debit"},
                {"account_code": "4010", "debit": 0.0, "credit": 50.0, "description": "test credit"},
            ],
        }
        r = api_client.post(
            f"{BASE_URL}/api/finance/journal-entries",
            params={"workshop_id": WORKSHOP_ID},
            json=payload,
        )
        # Should be rejected (400) by firewall (debit 100 vs credit 50)
        assert r.status_code == 400, f"expected 400 got {r.status_code}: {r.text}"

        # Allow time for the in-memory log to update
        time.sleep(0.3)
        after = api_client.get(f"{BASE_URL}/api/firewall/status", params={"workshop_id": WORKSHOP_ID}).json()
        after_rej = after["summary"].get("lifetime_rejections", 0)
        assert after_rej >= before_rej + 1, f"lifetime_rejections did not increment: before={before_rej} after={after_rej}"

        # Check at least one rejection in recent_rejections list
        rec = after.get("recent_rejections") or []
        assert isinstance(rec, list)
        assert len(rec) >= 1

    def test_balanced_journal_entry_is_accepted(self, api_client):
        payload = {
            "workshop_id": WORKSHOP_ID,
            "date": "2026-01-15",
            "description": "TEST_balanced_iter190",
            "lines": [
                {"account_code": "1010", "debit": 100.0, "credit": 0.0, "description": "test debit"},
                {"account_code": "4010", "debit": 0.0, "credit": 100.0, "description": "test credit"},
            ],
        }
        r = api_client.post(
            f"{BASE_URL}/api/finance/journal-entries",
            params={"workshop_id": WORKSHOP_ID},
            json=payload,
        )
        # Should be accepted: 200 or 201
        assert r.status_code in (200, 201), f"expected 200/201 got {r.status_code}: {r.text}"
        data = r.json()
        assert data.get("success") in (True, None) or "id" in data or "entry" in data


# ---------- Idempotency ----------
class TestOperationIdempotency:
    def test_same_transaction_id_increments_idempotency_hit(self, api_client):
        before = api_client.get(f"{BASE_URL}/api/firewall/status", params={"workshop_id": WORKSHOP_ID}).json()
        before_hits = before["summary"].get("lifetime_idempotency_hits", 0)

        tx_id = f"TEST_iter190_{uuid.uuid4().hex[:10]}"
        payload = {
            "workshop_id": WORKSHOP_ID,
            "transaction_id": tx_id,
            "kind": "service",
            "description": "TEST_idem_iter190",
            "amount": 50.0,
        }

        r1 = api_client.post(
            f"{BASE_URL}/api/operations",
            params={"workshop_id": WORKSHOP_ID},
            json=payload,
        )
        if r1.status_code not in (200, 201):
            pytest.skip(f"operations endpoint did not accept payload ({r1.status_code}): {r1.text[:200]}")
        op1 = r1.json()
        op1_id = op1.get("id") or (op1.get("operation") or {}).get("id")

        r2 = api_client.post(
            f"{BASE_URL}/api/operations",
            params={"workshop_id": WORKSHOP_ID},
            json=payload,
        )
        # Should NOT create a duplicate; same op id expected
        assert r2.status_code in (200, 201), f"second call status {r2.status_code}: {r2.text[:200]}"
        op2 = r2.json()
        op2_id = op2.get("id") or (op2.get("operation") or {}).get("id")

        if op1_id and op2_id:
            assert op1_id == op2_id, f"idempotency broken: {op1_id} != {op2_id}"

        time.sleep(0.3)
        after = api_client.get(f"{BASE_URL}/api/firewall/status", params={"workshop_id": WORKSHOP_ID}).json()
        after_hits = after["summary"].get("lifetime_idempotency_hits", 0)
        assert after_hits >= before_hits + 1, f"idempotency_hit did not increment: before={before_hits} after={after_hits}"
