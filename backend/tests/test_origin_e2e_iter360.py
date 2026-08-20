"""Iter360 — verification of Creator/Origin Visibility (feature 22).

Focuses on the E2E round-trip that could not be duplicated in the existing
test_creator_origin_visibility.py suite: net-zero POST → GET single → reversal.

Rules honoured:
  - Data is LIVE (shared Supabase). NO absolute financial number assertions.
  - Every test entry we create is net-zero and reversed via DELETE.
  - Description contains [TEST_ORIGIN_QA] tag for traceability.
"""
import os
import sys
import uuid

import pytest
import requests

sys.path.insert(0, "/app/backend")

from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")

from core.journal_origin import _compose, POSTER_LABEL, UNRECORDED_HISTORICAL  # noqa: E402

INTERNAL_URL = "http://localhost:8001"
ADMIN_USER = "مدير"
ADMIN_PASS = "010101"
WORKSHOP_ID = "finmodule-sync"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(
        f"{INTERNAL_URL}/api/auth/login",
        json={"username": ADMIN_USER, "password": ADMIN_PASS},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    tok = r.json().get("access_token")
    assert tok
    return tok


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ─────────────────────── Channel label mapping ────────────────────────

@pytest.mark.parametrize(
    "source,expected",
    [
        ("unified_visit_payment", "ملف مركبة"),
        ("vehicle_visit", "ملف مركبة"),
        ("operation", "عملية"),
        ("reversal", "قيد عكسي"),
        ("manual", "إدخال يدوي"),
        ("smart_pos", "نقاط البيع"),
        ("pos_template", "نقاط البيع"),
        ("pos_instant_sale", "نقاط البيع"),
    ],
)
def test_channel_label_mapping(source, expected):
    o = _compose(source, None, None, None, {}, {})
    assert o["channel_label"] == expected


# ─────────────────────── Live list origin contract ────────────────────

def test_list_all_rows_carry_origin_no_uuid_leak(auth_headers):
    r = requests.get(
        f"{INTERNAL_URL}/api/finance/journal-entries",
        params={"workshop_id": WORKSHOP_ID, "limit": 40},
        headers=auth_headers,
        timeout=30,
    )
    assert r.status_code == 200
    rows = r.json().get("data") or []
    assert rows, "expected live rows"

    for row in rows:
        origin = row.get("origin")
        assert origin, f"origin missing on {row.get('id')}"
        assert origin["poster_label"] == POSTER_LABEL
        for k in ("creator_label", "creator_kind", "approver_label", "channel_label"):
            assert origin.get(k), f"{k} empty on {row.get('id')}"
        # historic entries must show the documented sentinel, not admin/system
        if origin["creator_kind"] == "unknown":
            assert origin["creator_label"] == UNRECORDED_HISTORICAL
            assert origin["approver_label"] == "غير مسجل"
        # no raw UUID leaking into human labels
        for label_key in ("creator_label", "approver_label", "channel_label"):
            val = origin[label_key]
            # A raw uuid has 4 dashes and length 36; ensure not present verbatim
            parts = val.split("-")
            assert not (len(parts) >= 5 and len(val) >= 32 and all(len(p) >= 4 for p in parts[:4])), \
                f"raw UUID leak in {label_key}: {val}"


def test_single_entry_endpoint_returns_origin(auth_headers):
    r = requests.get(
        f"{INTERNAL_URL}/api/finance/journal-entries",
        params={"workshop_id": WORKSHOP_ID, "limit": 1},
        headers=auth_headers,
        timeout=30,
    )
    rows = r.json().get("data") or []
    assert rows
    eid = rows[0]["id"]
    r2 = requests.get(
        f"{INTERNAL_URL}/api/finance/journal-entries/{eid}",
        params={"workshop_id": WORKSHOP_ID},
        headers=auth_headers,
        timeout=30,
    )
    assert r2.status_code == 200
    data = r2.json().get("data") or {}
    origin = data.get("origin") or {}
    assert origin.get("poster_label") == POSTER_LABEL
    assert origin.get("creator_label")
    assert origin.get("channel_label")


# ─────────────────────── E2E attribution round-trip ───────────────────

def test_e2e_manual_entry_attributes_admin_and_reverses(auth_headers):
    """POST net-zero → GET single origin=admin → DELETE reversal."""
    payload = {
        "date": "2026-01-25",
        "description": f"[TEST_ORIGIN_QA] iter360 net-zero {uuid.uuid4().hex[:8]}",
        "transaction_type": "manual",
        "lines": [
            {"account": "003", "account_name": "صندوق", "debit": 1.0, "credit": 0},
            {"account": "003", "account_name": "صندوق", "debit": 0, "credit": 1.0},
        ],
        "total": 1.0,
    }
    r = requests.post(
        f"{INTERNAL_URL}/api/finance/journal-entries",
        params={"workshop_id": WORKSHOP_ID},
        headers={**auth_headers, "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    entry_id = body.get("id") or (body.get("data") or [{}])[0].get("id")
    assert entry_id, f"no entry_id in response: {body}"

    try:
        # GET single — must carry admin attribution
        r2 = requests.get(
            f"{INTERNAL_URL}/api/finance/journal-entries/{entry_id}",
            params={"workshop_id": WORKSHOP_ID},
            headers=auth_headers,
            timeout=30,
        )
        assert r2.status_code == 200, r2.text
        origin = (r2.json().get("data") or {}).get("origin") or {}
        assert origin.get("creator_label") == "مدير (مدير نظام)", origin
        assert origin.get("creator_kind") == "user"
        assert origin.get("approver_label") == "لا يتطلب اعتماد (إجراء مباشر)"
        assert origin.get("poster_label") == POSTER_LABEL
        assert origin.get("channel_label") == "إدخال يدوي"
    finally:
        # Cleanup mandatory — reverse (never hard delete)
        r3 = requests.delete(
            f"{INTERNAL_URL}/api/finance/journal-entries/{entry_id}",
            params={"workshop_id": WORKSHOP_ID},
            headers=auth_headers,
            timeout=30,
        )
        assert r3.status_code == 200, f"reversal failed: {r3.text}"
        rev = r3.json()
        # Reversal succeeded now, or was already reversed (idempotent replay).
        entries = (rev.get("data") or {}).get("entries") or []
        first = entries[0] if entries else {}
        assert rev.get("success") is True and (
            (rev.get("data") or {}).get("reversed") is True
            or first.get("idempotent") is True
        ), rev


# ─────────────────────── Regression: balance sheet balanced ───────────

def test_balance_sheet_still_balanced(auth_headers):
    r = requests.get(
        f"{INTERNAL_URL}/api/finance/reports/balance-sheet",
        params={"workshop_id": WORKSHOP_ID},
        headers=auth_headers,
        timeout=30,
    )
    assert r.status_code == 200, r.text
    totals = ((r.json().get("data") or {}).get("totals") or {})
    assets = float(totals.get("assets", 0))
    lpe = float(totals.get("liabilities_plus_equity", 0))
    # relative check — no absolute assertion
    assert abs(assets - lpe) < 0.01, f"balance sheet gap: assets={assets} L+E={lpe}"


def test_trial_balance_still_balanced(auth_headers):
    r = requests.get(
        f"{INTERNAL_URL}/api/finance/reports/trial-balance",
        params={"workshop_id": WORKSHOP_ID},
        headers=auth_headers,
        timeout=30,
    )
    assert r.status_code == 200, r.text
    data = r.json().get("data") or {}
    totals = data.get("totals") or data
    td = float(totals.get("total_debit") or totals.get("debit") or 0)
    tc = float(totals.get("total_credit") or totals.get("credit") or 0)
    assert abs(td - tc) < 0.01, f"trial balance gap: D={td} C={tc}"
