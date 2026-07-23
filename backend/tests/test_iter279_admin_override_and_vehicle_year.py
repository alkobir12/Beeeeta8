"""Iteration 279 — Admin override + vehicles/year regression.

Modules/features covered:
- /api/vehicles returns 200 and safe integer `year` values
- admin self-approval without developer_code logs APPROVAL_GRANTED_ADMIN_OVERRIDE
- accountant self-approval remains blocked by Four-Eyes policy
"""

from __future__ import annotations

import os
import uuid
from typing import Any, Dict, Optional

import pytest
import requests
from dotenv import load_dotenv


load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"
API = f"{BASE_URL}/api"

RATE_BYPASS = (os.environ.get("RATE_LIMIT_BYPASS_TOKEN") or "").strip().strip('"')


def _session_for(username: str, pin: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    if RATE_BYPASS:
        s.headers["x-ratelimit-bypass"] = RATE_BYPASS

    login = s.post(f"{API}/auth/login", json={"username": username, "pin": pin}, timeout=30)
    assert login.status_code == 200, f"login failed for {username}: {login.status_code} {login.text[:200]}"
    token = login.json().get("access_token")
    assert token, f"missing access_token for {username}"
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def admin_session() -> requests.Session:
    return _session_for("مدير", "123123")


@pytest.fixture(scope="module")
def accountant_session() -> requests.Session:
    return _session_for("احمد", "123123")


def _create_vehicle_draft(session: requests.Session, marker: str) -> str:
    payload = {
        "action": "vehicle",
        "payload": {
            "plate": f"{marker}-{uuid.uuid4().hex[:6]}",
            "brand": "TOYOTA",
            "model": "CAMRY",
            "year": "2023",
            "name": marker,
            "phone": "0555000000",
        },
        "session_id": f"iter279-{marker}",
    }
    res = session.post(f"{API}/runtime/drafts", json=payload, timeout=30)
    assert res.status_code == 200, res.text[:300]
    body = res.json()
    draft_id = ((body.get("data") or {}).get("id") or "").strip()
    assert draft_id
    return draft_id


def _request_approval(session: requests.Session, draft_id: str) -> str:
    res = session.post(f"{API}/runtime/drafts/{draft_id}/request_approval", json={}, timeout=30)
    assert res.status_code == 200, res.text[:300]
    approval_id = ((res.json().get("data") or {}).get("approval_id") or "").strip()
    assert approval_id
    return approval_id


def _extract_committed_vehicle_id(approve_body: Dict[str, Any]) -> Optional[str]:
    committed = (approve_body.get("data") or {}).get("committed") or {}
    result = committed.get("result") if isinstance(committed, dict) else {}
    if isinstance(result, dict):
        return result.get("id")
    return None


def test_get_vehicles_admin_returns_200_and_year_int(admin_session: requests.Session):
    """Dashboard regression: /vehicles should stay stable and return integer year values."""
    res = admin_session.get(f"{API}/vehicles", timeout=40)
    assert res.status_code == 200, res.text[:300]

    rows = res.json()
    assert isinstance(rows, list)
    for row in rows:
        if "year" in row:
            assert isinstance(row.get("year"), int), f"vehicle {row.get('id')} has non-int year={row.get('year')}"


def test_admin_can_self_approve_without_developer_code_and_audit_logged(admin_session: requests.Session):
    """Admin self-approval should pass and emit APPROVAL_GRANTED_ADMIN_OVERRIDE audit event."""
    draft_id = _create_vehicle_draft(admin_session, "TEST_SAFE_ADMIN_OVERRIDE")
    approval_id = _request_approval(admin_session, draft_id)

    approve = admin_session.post(f"{API}/runtime/approvals/{approval_id}/approve", json={}, timeout=40)
    assert approve.status_code == 200, approve.text[:400]
    approve_body = approve.json()

    draft = (approve_body.get("data") or {}).get("draft") or {}
    assert draft.get("status") in {"approved", "committed"}

    audit = admin_session.get(f"{API}/runtime/audit", params={"limit": 250}, timeout=40)
    assert audit.status_code == 200, audit.text[:300]
    events = (audit.json().get("data") or [])
    hit = [
        e for e in events
        if e.get("event") == "APPROVAL_GRANTED_ADMIN_OVERRIDE" and e.get("draft_id") == draft_id
    ]
    assert hit, "Expected APPROVAL_GRANTED_ADMIN_OVERRIDE event not found for draft"

    # Best-effort cleanup for any committed vehicle record
    created_vehicle_id = _extract_committed_vehicle_id(approve_body)
    if created_vehicle_id:
        admin_session.delete(f"{API}/vehicles/{created_vehicle_id}", timeout=30)


def test_accountant_self_approval_still_blocked_by_four_eyes(accountant_session: requests.Session):
    """Non-admin approver must still be blocked from approving own draft."""
    draft_id = _create_vehicle_draft(accountant_session, "TEST_ACCOUNTANT_SELF_APPROVAL")
    approval_id = _request_approval(accountant_session, draft_id)

    approve = accountant_session.post(f"{API}/runtime/approvals/{approval_id}/approve", json={}, timeout=40)
    assert approve.status_code == 403, approve.text[:400]
    detail = approve.json().get("detail")
    if isinstance(detail, dict):
        assert detail.get("error") == "four_eyes_violation"
    else:
        assert "four_eyes_violation" in str(detail)
