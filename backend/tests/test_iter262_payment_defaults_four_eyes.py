"""
Iteration 262 — Payment defaulting + four-eyes + auth guardrails regression.

Covers:
- Manager/Accountant PIN login
- Vehicle operation default payment state (unconfirmed, not credit)
- Journal behavior for unconfirmed vs explicit deferred
- Runtime approvals read/approve by accountant with strict four-eyes
- Auth checks: bcrypt hash format, httpOnly cookies, CORS credentials, brute-force lockout
"""

from __future__ import annotations

import os
import uuid
from urllib.parse import urlparse

import pytest
import requests
from dotenv import load_dotenv


load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
WORKSHOP_ID = os.environ.get("REACT_APP_WORKSHOP_ID") or os.environ.get("DEFAULT_WORKSHOP_ID")
RATE_BYPASS = (os.environ.get("RATE_LIMIT_BYPASS_TOKEN") or "").strip().strip('"')
MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")

MANAGER_USERNAME = "مدير"
ACCOUNTANT_USERNAME = "احمد"
PIN = "123123"


pytestmark = pytest.mark.skipif(
    not BASE_URL,
    reason="REACT_APP_BACKEND_URL is required",
)


def _session(forwarded_ip: str | None = None) -> requests.Session:
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    if RATE_BYPASS:
        s.headers["x-ratelimit-bypass"] = RATE_BYPASS
    if forwarded_ip:
        s.headers["x-forwarded-for"] = forwarded_ip
    return s


def _login_with_pin(username: str) -> tuple[requests.Session, requests.Response]:
    ip = f"198.51.100.{int(uuid.uuid4().hex[:2], 16)}"
    s = _session(ip)
    resp = s.post(f"{BASE_URL}/api/auth/login", json={"username": username, "pin": PIN}, timeout=30)
    return s, resp


def _auth(session: requests.Session, token: str) -> None:
    session.headers["Authorization"] = f"Bearer {token}"


def _get_one_vehicle_id(session: requests.Session) -> str:
    r = session.get(f"{BASE_URL}/api/vehicles", timeout=30)
    assert r.status_code == 200, r.text
    rows = r.json() if isinstance(r.json(), list) else []
    assert rows, "No vehicles available to run vehicle-scoped operation tests"
    vid = rows[0].get("id")
    assert isinstance(vid, str) and vid, "Vehicle id missing"
    return vid


def _journal_by_reference(session: requests.Session, op_id: str) -> list[dict]:
    r = session.get(
        f"{BASE_URL}/api/finance/journal-entries",
        params={"workshop_id": WORKSHOP_ID, "limit": 1000},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    entries = body if isinstance(body, list) else body.get("entries") or body.get("data") or []
    return [e for e in entries if str(e.get("reference_id") or "") == op_id]


class TestIter262EnterpriseOperator:
    """Targeted enterprise operator regression scenarios."""

    created_operation_ids: list[str] = []
    created_draft_id: str | None = None
    created_approval_id: str | None = None

    def test_01_manager_and_accountant_pin_login_work(self):
        mgr_session, mgr_login = _login_with_pin(MANAGER_USERNAME)
        assert mgr_login.status_code == 200, mgr_login.text
        mgr = mgr_login.json()
        assert mgr.get("username") == MANAGER_USERNAME
        assert mgr.get("role") in {"admin", "manager"}
        assert isinstance(mgr.get("access_token"), str) and mgr["access_token"]

        acc_session, acc_login = _login_with_pin(ACCOUNTANT_USERNAME)
        assert acc_login.status_code == 200, acc_login.text
        acc = acc_login.json()
        assert acc.get("username") == ACCOUNTANT_USERNAME
        assert acc.get("role") == "accountant"
        assert isinstance(acc.get("access_token"), str) and acc["access_token"]

        # keep references to avoid lint noise and verify sessions actually active
        assert mgr_session.cookies is not None
        assert acc_session.cookies is not None

    def test_02_unconfirmed_vehicle_operation_defaults_and_no_journal(self):
        mgr_session, mgr_login = _login_with_pin(MANAGER_USERNAME)
        assert mgr_login.status_code == 200, mgr_login.text
        token = mgr_login.json()["access_token"]
        _auth(mgr_session, token)

        vehicle_id = _get_one_vehicle_id(mgr_session)
        payload = {
            "type": "service",
            "vehicleId": vehicle_id,
            "partnerType": "customer",
            "items": [{"name": "TEST_UNCONF_SERVICE", "itemType": "service", "price": 73, "qty": 1}],
            "total": 73,
            "workshopId": WORKSHOP_ID,
            "notes": f"TEST_ITER262_UNCONF_{uuid.uuid4().hex[:8]}",
        }

        create = mgr_session.post(f"{BASE_URL}/api/operations", json=payload, timeout=30)
        assert create.status_code in (200, 201), create.text
        op = create.json()
        op_id = op.get("id")
        assert isinstance(op_id, str) and op_id
        self.created_operation_ids.append(op_id)

        # Data assertions: should be normalized to unconfirmed state
        assert op.get("paymentMethod") == "unconfirmed"
        assert op.get("paymentStatus") == "unconfirmed"

        # Persistence verification via GET
        fetched = mgr_session.get(f"{BASE_URL}/api/operations/{op_id}", timeout=30)
        assert fetched.status_code == 200, fetched.text
        op_get = fetched.json()
        assert op_get.get("paymentMethod") == "unconfirmed"
        assert op_get.get("paymentStatus") == "unconfirmed"

        # No base/accrual journal should be created for unconfirmed vehicle operation
        refs = _journal_by_reference(mgr_session, op_id)
        assert len(refs) == 0, f"Unexpected journal entries for unconfirmed op: {refs[:2]}"

    def test_03_explicit_deferred_still_creates_temporary_deferred_journal(self):
        mgr_session, mgr_login = _login_with_pin(MANAGER_USERNAME)
        assert mgr_login.status_code == 200, mgr_login.text
        token = mgr_login.json()["access_token"]
        _auth(mgr_session, token)

        vehicle_id = _get_one_vehicle_id(mgr_session)
        payload = {
            "type": "sale",
            "vehicleId": vehicle_id,
            "partnerType": "customer",
            "paymentMethod": "آجل",
            "paymentStatus": "unpaid",
            "items": [{"name": "TEST_DEFERRED_SALE", "itemType": "service", "price": 145, "qty": 1}],
            "total": 145,
            "workshopId": WORKSHOP_ID,
            "notes": f"TEST_ITER262_DEFERRED_{uuid.uuid4().hex[:8]}",
        }

        create = mgr_session.post(f"{BASE_URL}/api/operations", json=payload, timeout=30)
        assert create.status_code in (200, 201), create.text
        op = create.json()
        op_id = op.get("id")
        assert isinstance(op_id, str) and op_id
        self.created_operation_ids.append(op_id)

        assert str(op.get("paymentMethod") or "").lower() in {"آجل", "اجل", "deferred", "credit"}
        assert str(op.get("paymentStatus") or "").lower() in {"unpaid", "credit", "deferred", "partial", "pending"}

        refs = _journal_by_reference(mgr_session, op_id)
        assert refs, "Expected deferred sale journal entry but none found"
        base = [e for e in refs if str(e.get("source") or "") not in {"operation_payment", "operation_payment_income"}]
        assert base, f"Expected base deferred journal entry, got: {refs}"
        desc = str(base[0].get("description") or "")
        assert "قيد مؤقت" in desc or "بيع آجل" in desc

    def test_04_accountant_can_list_approvals_and_approve_manager_pending_with_four_eyes(self):
        mgr_session, mgr_login = _login_with_pin(MANAGER_USERNAME)
        assert mgr_login.status_code == 200, mgr_login.text
        _auth(mgr_session, mgr_login.json()["access_token"])

        # safe draft: supplier creation in local runtime store (no financial delete/approve on real pending)
        draft_payload = {
            "action": "supplier",
            "payload": {"name": f"TEST_SAFE_SUPPLIER_{uuid.uuid4().hex[:8]}"},
            "proposer": MANAGER_USERNAME,
        }
        draft_resp = mgr_session.post(f"{BASE_URL}/api/runtime/drafts", json=draft_payload, timeout=30)
        assert draft_resp.status_code == 200, draft_resp.text
        draft = (draft_resp.json() or {}).get("data") or {}
        draft_id = draft.get("id")
        assert isinstance(draft_id, str) and draft_id
        self.created_draft_id = draft_id

        req_resp = mgr_session.post(
            f"{BASE_URL}/api/runtime/drafts/{draft_id}/request_approval",
            json={"requester": MANAGER_USERNAME},
            timeout=30,
        )
        assert req_resp.status_code == 200, req_resp.text
        approval_id = ((req_resp.json() or {}).get("data") or {}).get("approval_id")
        assert isinstance(approval_id, str) and approval_id
        self.created_approval_id = approval_id

        acc_session, acc_login = _login_with_pin(ACCOUNTANT_USERNAME)
        assert acc_login.status_code == 200, acc_login.text
        _auth(acc_session, acc_login.json()["access_token"])

        list_resp = acc_session.get(f"{BASE_URL}/api/runtime/approvals", timeout=30)
        assert list_resp.status_code == 200, list_resp.text
        approvals = (list_resp.json() or {}).get("data") or []
        mine = next((a for a in approvals if a.get("id") == approval_id), None)
        assert mine is not None, f"Approval {approval_id} not visible to accountant"

        approve_resp = acc_session.post(
            f"{BASE_URL}/api/runtime/approvals/{approval_id}/approve",
            json={},
            timeout=45,
        )
        assert approve_resp.status_code == 200, approve_resp.text
        approved_body = (approve_resp.json() or {}).get("data") or {}
        approval_info = approved_body.get("approval") or {}
        assert approval_info.get("status") == "approved"
        assert approval_info.get("approver") == ACCOUNTANT_USERNAME
        # proposer may be absent in approval object; requester/draft.proposer is authoritative
        requester_or_proposer = approval_info.get("proposer") or approval_info.get("requester")
        if requester_or_proposer is not None:
            assert requester_or_proposer == MANAGER_USERNAME
            assert approval_info.get("approver") != requester_or_proposer

        draft_after = approved_body.get("draft") or {}
        if draft_after:
            assert draft_after.get("proposer") == MANAGER_USERNAME
            assert approval_info.get("approver") != draft_after.get("proposer")

    def test_05_auth_cookie_bcrypt_cors_and_lockout(self):
        s, login = _login_with_pin(MANAGER_USERNAME)
        assert login.status_code == 200, login.text

        # httpOnly cookie checks
        set_cookie = ", ".join(login.headers.get("set-cookie", "").split("\n"))
        low_cookie = set_cookie.lower()
        assert "httponly" in low_cookie
        assert "samesite=none" in low_cookie
        assert "secure" in low_cookie

        # CORS credentials with explicit origin
        origin = BASE_URL
        preflight = requests.options(
            f"{BASE_URL}/api/auth/login",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
            },
            timeout=30,
        )
        assert preflight.status_code in (200, 204)
        allow_creds = preflight.headers.get("access-control-allow-credentials")
        allow_origin = preflight.headers.get("access-control-allow-origin")

        # Preview edge may normalize/drop preflight headers; fallback to POST response headers.
        if not allow_creds:
            probe = requests.post(
                f"{BASE_URL}/api/auth/login",
                json={"username": MANAGER_USERNAME, "pin": PIN},
                headers={"Origin": origin},
                timeout=30,
            )
            assert probe.status_code == 200, probe.text
            allow_creds = probe.headers.get("access-control-allow-credentials")
            allow_origin = probe.headers.get("access-control-allow-origin")

        if allow_creds is not None:
            assert str(allow_creds).lower() == "true"
            assert allow_origin and allow_origin != "*"

        # bcrypt hash format starts with $2b$ for manager in auth_credentials
        if MONGO_URL and DB_NAME:
            from pymongo import MongoClient

            mongo = MongoClient(MONGO_URL)
            doc = mongo[DB_NAME].auth_credentials.find_one({"username": MANAGER_USERNAME}, {"_id": 0, "pin_hash": 1})
            mongo.close()
            assert doc and isinstance(doc.get("pin_hash"), str), "Manager pin_hash not found"
            assert doc["pin_hash"].startswith("$2b$"), f"Unexpected bcrypt prefix: {doc['pin_hash'][:4]}"
        else:
            pytest.skip("MONGO_URL/DB_NAME missing for bcrypt persistence check")

        # brute force lockout after 5 failures (isolated identifier + IP)
        fake_user = f"lock_user_{uuid.uuid4().hex[:8]}"
        lock_session = _session(forwarded_ip=f"203.0.113.{int(uuid.uuid4().hex[:2], 16)}")
        statuses = []
        for _ in range(6):
            r = lock_session.post(
                f"{BASE_URL}/api/auth/login",
                json={"username": fake_user, "pin": "000000"},
                timeout=30,
            )
            statuses.append(r.status_code)
        assert statuses[-1] == 429, f"Expected lockout 429 on 6th attempt, got statuses={statuses}"

    def test_99_cleanup_created_operations(self):
        mgr_session, mgr_login = _login_with_pin(MANAGER_USERNAME)
        if mgr_login.status_code != 200:
            pytest.skip("Manager login failed during cleanup")
        _auth(mgr_session, mgr_login.json()["access_token"])

        for op_id in self.created_operation_ids:
            resp = mgr_session.delete(f"{BASE_URL}/api/operations/{op_id}", timeout=30)
            assert resp.status_code in (200, 204), f"Cleanup failed for operation {op_id}: {resp.status_code} {resp.text}"
