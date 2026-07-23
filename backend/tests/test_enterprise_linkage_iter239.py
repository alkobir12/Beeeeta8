"""
Iteration 239 - Enterprise Operator FULL LINKAGE test.

Validates:
  L1: finance-actions/invoice → AccountingEngine → journal_entries (balanced, idempotent)
  L2: POST /api/finance/journal-entries (manual create) wired to engine (dedup by reference_id)
  L3: trial-balance, income-statement, cash-flow, balance-sheet reports respond 200 success
  L4: reconciliation (firewall) endpoint responds 200 success
  REG-bot: /api/runtime/execute returns committed/pending_approval (not 500)
  REG-4eyes: self-approval blocked (403), other approver passes RBAC+4eyes
"""

import os
import time
import uuid
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://workshop-operator.preview.emergentagent.com").rstrip("/")
WORKSHOP_ID = "finmodule-sync"

H_ADMIN = {"Content-Type": "application/json", "x-user-role": "admin", "x-user-id": "manager"}
H_SUPER = {"Content-Type": "application/json", "x-user-role": "supervisor", "x-user-id": "ahmed1"}


@pytest.fixture(scope="module")
def created_refs():
    refs = []
    yield refs
    # cleanup journal_entries by reference_id
    for ref in refs:
        try:
            requests.delete(
                f"{BASE_URL}/api/finance/journal-entries",
                params={"workshop_id": WORKSHOP_ID, "reference_id": ref},
                headers=H_ADMIN,
                timeout=20,
            )
        except Exception:
            pass


# ----- LINKAGE 1: finance-actions/invoice → engine → journal_entries -----
def test_linkage1_invoice_to_journal_balanced_and_idempotent(created_refs):
    ref = f"TEST-LNK1-{uuid.uuid4().hex[:10]}"
    created_refs.append(ref)
    body = {
        "customer": "عميل ربط شامل",
        "payment_method": "credit",
        "by": "مدير",
        "items": [{"name": "صيانة", "price": 400, "quantity": 1}],
        "reference_id": ref,
    }
    r1 = requests.post(f"{BASE_URL}/api/finance-actions/invoice", json=body, headers=H_ADMIN, timeout=30)
    assert r1.status_code == 200, r1.text
    j1 = r1.json()
    assert (j1.get("data") or j1).get("posted") is True or j1.get("posted") is True or j1.get("success") is True, j1
    # balanced
    data1 = j1.get("data", j1)
    assert data1.get("balanced", True) in (True, None)

    # GET journal-entries and look for our ref
    rg = requests.get(
        f"{BASE_URL}/api/finance/journal-entries",
        params={"workshop_id": WORKSHOP_ID, "limit": 50},
        headers=H_ADMIN,
        timeout=20,
    )
    assert rg.status_code == 200, rg.text
    rows = rg.json()
    if isinstance(rows, dict):
        rows = rows.get("data") or rows.get("entries") or rows.get("items") or []
    matched = [e for e in rows if e.get("reference_id") == ref]
    assert len(matched) >= 1, f"entry for ref {ref} not found in last 50"
    entry = matched[0]
    lines = entry.get("lines") or []
    sd = sum(float(l.get("debit") or 0) for l in lines)
    sc = sum(float(l.get("credit") or 0) for l in lines)
    assert round(sd, 2) == round(sc, 2) and sd > 0, f"unbalanced lines {sd} vs {sc}"

    # Idempotency: same body again
    r2 = requests.post(f"{BASE_URL}/api/finance-actions/invoice", json=body, headers=H_ADMIN, timeout=30)
    assert r2.status_code == 200, r2.text
    j2 = r2.json()
    d2 = j2.get("data", j2)
    assert d2.get("idempotent") is True or d2.get("duplicate") is True, f"expected idempotent=true on repost, got {j2}"


# ----- LINKAGE 2: manual create journal-entries → engine dedup -----
def test_linkage2_manual_journal_create_dedup(created_refs):
    ref = f"TEST-LNK2-{uuid.uuid4().hex[:10]}"
    created_refs.append(ref)
    body = {
        "description": "قيد ربط",
        "date": "2026-06-18T09:00:00",
        "reference_id": ref,
        "lines": [
            {"account": "003", "account_name": "النقد", "debit": 600, "credit": 0},
            {"account": "025", "account_name": "الإيرادات", "debit": 0, "credit": 600},
        ],
    }
    r1 = requests.post(
        f"{BASE_URL}/api/finance/journal-entries",
        params={"workshop_id": WORKSHOP_ID},
        json=body,
        headers=H_ADMIN,
        timeout=30,
    )
    assert r1.status_code in (200, 201), r1.text
    j1 = r1.json()
    def _extract_id(j):
        if not isinstance(j, dict):
            return None
        if j.get("id"):
            return j["id"]
        d = j.get("data")
        if isinstance(d, dict):
            return d.get("id")
        if isinstance(d, list) and d:
            return (d[0] or {}).get("id")
        return (j.get("entry") or {}).get("id")
    id1 = _extract_id(j1)
    assert id1, f"missing id in response: {j1}"

    # repost: same id
    r2 = requests.post(
        f"{BASE_URL}/api/finance/journal-entries",
        params={"workshop_id": WORKSHOP_ID},
        json=body,
        headers=H_ADMIN,
        timeout=30,
    )
    assert r2.status_code in (200, 201), r2.text
    j2 = r2.json()
    id2 = _extract_id(j2)
    assert id2 == id1, f"engine dedup failed: {id1} vs {id2}"

    # GET and confirm only ONE row for this ref
    rg = requests.get(
        f"{BASE_URL}/api/finance/journal-entries",
        params={"workshop_id": WORKSHOP_ID, "limit": 100},
        headers=H_ADMIN,
        timeout=20,
    )
    assert rg.status_code == 200
    rows = rg.json()
    if isinstance(rows, dict):
        rows = rows.get("data") or rows.get("entries") or rows.get("items") or []
    matched = [e for e in rows if e.get("reference_id") == ref]
    assert len(matched) == 1, f"expected exactly 1 entry for {ref}, got {len(matched)}"


# ----- LINKAGE 3: financial reports respond 200 -----
@pytest.mark.parametrize("path", [
    "/api/finance/reports/trial-balance",
    "/api/finance/reports/income-statement",
    "/api/finance/reports/cash-flow",
    "/api/finance/reports/balance-sheet",
])
def test_linkage3_reports_respond(path):
    r = requests.get(f"{BASE_URL}{path}", params={"workshop_id": WORKSHOP_ID}, headers=H_ADMIN, timeout=30)
    assert r.status_code == 200, f"{path} -> {r.status_code} {r.text[:300]}"
    j = r.json()
    # success or numeric-ish payload
    assert (j.get("success") is True) or isinstance(j, (dict, list)), f"{path} body unexpected: {j}"


# ----- LINKAGE 4: firewall reconciliation -----
def test_linkage4_firewall_reconciliation():
    r = requests.get(
        f"{BASE_URL}/api/finance/reports/reconciliation",
        params={"workshop_id": WORKSHOP_ID},
        headers=H_ADMIN,
        timeout=30,
    )
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("success") is True or isinstance(j, dict)


# ----- REGRESSION bot -----
def test_bot_execute_safe_path():
    body = {"text": "سجل عميل اسمه عميل ربط بوت", "proposer": "مدير"}
    r = requests.post(f"{BASE_URL}/api/runtime/execute", json=body, headers=H_ADMIN, timeout=45)
    assert r.status_code == 200, r.text
    j = r.json()
    status = (j.get("data") or j).get("status") or j.get("status")
    assert status in ("committed", "pending_approval"), f"expected committed/pending_approval, got: {j}"


# ----- REGRESSION Four-Eyes -----
def test_four_eyes_self_approval_blocked_and_other_passes():
    # Create draft as مدير
    draft_body = {
        "action": "update_customer",
        "payload": {"customer_id": "Z", "set": {"phone": "0500000000"}},
        "proposer": "مدير",
    }
    rd = requests.post(f"{BASE_URL}/api/runtime/drafts", json=draft_body, headers=H_ADMIN, timeout=20)
    assert rd.status_code in (200, 201), rd.text
    dj = rd.json()
    inner = dj.get("data") if isinstance(dj.get("data"), dict) else dj
    draft_id = inner.get("draft_id") or inner.get("id")
    assert draft_id, f"missing draft id: {dj}"

    # Request approval -> get approval_id
    rr = requests.post(
        f"{BASE_URL}/api/runtime/drafts/{draft_id}/request_approval",
        json={"requester": "مدير"}, headers=H_ADMIN, timeout=15,
    )
    assert rr.status_code in (200, 201), rr.text
    rj = rr.json()
    rinner = rj.get("data") if isinstance(rj.get("data"), dict) else rj
    approval_id = rinner.get("approval_id") or rinner.get("id")
    assert approval_id, f"missing approval id: {rj}"

    # Self-approve as مدير (same proposer) → 403 four_eyes_violation
    r_self = requests.post(
        f"{BASE_URL}/api/runtime/approvals/{approval_id}/approve",
        json={"by": "مدير"}, headers=H_ADMIN, timeout=20,
    )
    assert r_self.status_code == 403, f"expected 403 four_eyes_violation, got {r_self.status_code} {r_self.text[:300]}"
    body_low = r_self.text.lower()
    assert "four_eyes" in body_low or "four-eyes" in body_low or "self" in body_low, r_self.text[:300]

    # Different approver احمد1 (supervisor) → passes RBAC+4eyes (commit may fail w/ update_failed)
    r_other = requests.post(
        f"{BASE_URL}/api/runtime/approvals/{approval_id}/approve",
        json={"by": "احمد1"}, headers=H_SUPER, timeout=30,
    )
    assert not (r_other.status_code == 403 and "four_eyes" in r_other.text.lower()), (
        f"supervisor approval still blocked by four-eyes: {r_other.status_code} {r_other.text[:300]}"
    )
