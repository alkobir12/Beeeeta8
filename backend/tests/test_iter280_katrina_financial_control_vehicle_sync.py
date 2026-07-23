"""
Iteration 280 — targeted regression for Katrina finance guard + vehicle open flow.

Modules/features covered:
- Auth (manager PIN login)
- Vehicles API read flow (list -> get by id)
- Unified runtime payment-method guard in Katrina financial actions
"""

from __future__ import annotations

import json
import os
import uuid

import pytest
import requests
from dotenv import load_dotenv


load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
RATE_BYPASS = (os.environ.get("RATE_LIMIT_BYPASS_TOKEN") or "").strip().strip('"')

MANAGER_USERNAME = "مدير"
MANAGER_PIN = "123123"


pytestmark = pytest.mark.skipif(not BASE_URL, reason="REACT_APP_BACKEND_URL is required")


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    if RATE_BYPASS:
        s.headers["x-ratelimit-bypass"] = RATE_BYPASS
    return s


def _extract_data(body: dict) -> dict:
    if isinstance(body, dict) and isinstance(body.get("data"), dict):
        return body["data"]
    return body if isinstance(body, dict) else {}


def _login_manager(session: requests.Session) -> str:
    res = session.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": MANAGER_USERNAME, "pin": MANAGER_PIN},
        timeout=30,
    )
    assert res.status_code == 200, res.text
    data = res.json()
    token = data.get("access_token")
    assert isinstance(token, str) and token
    assert data.get("username") == MANAGER_USERNAME
    session.headers["Authorization"] = f"Bearer {token}"
    return token


def _list_runtime_drafts(session: requests.Session) -> list[dict]:
    res = session.get(f"{BASE_URL}/api/runtime/drafts", timeout=30)
    assert res.status_code == 200, res.text
    body = res.json()
    data = _extract_data(body)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return data["items"]
    return []


class TestIter280KatrinaFinancialGuard:
    def test_01_manager_login_success(self):
        session = _session()
        _ = _login_manager(session)
        assert "Authorization" in session.headers

    def test_02_vehicle_get_by_id_from_list(self):
        session = _session()
        _login_manager(session)

        list_res = session.get(f"{BASE_URL}/api/vehicles", timeout=30)
        assert list_res.status_code == 200, list_res.text
        vehicles = list_res.json() if isinstance(list_res.json(), list) else []
        assert vehicles, "No vehicles found to validate details endpoint"

        vehicle_id = str(vehicles[0].get("id") or "").strip()
        assert vehicle_id

        get_res = session.get(f"{BASE_URL}/api/vehicles/{vehicle_id}", timeout=30)
        assert get_res.status_code == 200, get_res.text
        vehicle = get_res.json()
        assert vehicle.get("id") == vehicle_id
        assert str(vehicle.get("detail") or "").lower().find("not found") == -1

    def test_03_financial_action_without_payment_method_needs_clarification_and_no_draft(self):
        session = _session()
        _login_manager(session)

        marker = f"ITER280_NOPM_{uuid.uuid4().hex[:8]}"
        before = _list_runtime_drafts(session)

        exec_res = session.post(
            f"{BASE_URL}/api/runtime/execute",
            json={"text": f"سجل مصروف {marker} بمبلغ 400"},
            timeout=45,
        )
        assert exec_res.status_code == 200, exec_res.text
        body = exec_res.json()
        data = _extract_data(body)

        assert data.get("status") == "needs_clarification"
        ask = str(data.get("ask") or "")
        assert "طريقة الدفع" in ask
        assert any(word in ask for word in ["نقد", "آجل", "تحويل"])
        assert not data.get("draft")
        assert not data.get("approval")

        after = _list_runtime_drafts(session)
        marked_before = [d for d in before if marker in json.dumps(d, ensure_ascii=False)]
        marked_after = [d for d in after if marker in json.dumps(d, ensure_ascii=False)]
        assert len(marked_after) == len(marked_before), "Unexpected draft created for missing payment_method"

    def test_04_financial_action_with_transfer_goes_pending_approval(self):
        session = _session()
        _login_manager(session)

        marker = f"ITER280_TRANSFER_{uuid.uuid4().hex[:8]}"
        exec_res = session.post(
            f"{BASE_URL}/api/runtime/execute",
            json={"text": f"سجل مصروف {marker} بمبلغ 410 تحويل"},
            timeout=45,
        )
        assert exec_res.status_code == 200, exec_res.text

        data = _extract_data(exec_res.json())
        assert data.get("status") == "pending_approval", data
        draft = data.get("draft") or {}
        approval = data.get("approval") or {}
        assert isinstance(draft.get("id"), str) and draft.get("id")
        assert isinstance(approval.get("approval_id"), str) and approval.get("approval_id")
