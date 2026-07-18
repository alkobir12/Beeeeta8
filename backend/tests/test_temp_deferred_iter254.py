"""
Iteration 254 — Temporary Journal Entry for deferred sales
Covers: full deferred cycle, partial→full settlement, cash-sale regression,
SSOT tool finance.ar_summary, chat routing, prompt versions.
Cleanup: DELETE all created operations at end.
"""
import os
import uuid
import time
import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
WORKSHOP_ID = "finmodule-sync"
RATE_BYPASS = os.environ["RATE_LIMIT_BYPASS_TOKEN"].strip().strip('"')
MANAGER_PIN = os.environ["MANAGER_QUICK_PIN"]

created_ops = []
_state = {}


def _acc(l):
    return l.get("account_number") or l.get("account_code") or l.get("account") or l.get("code")



@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json", "x-ratelimit-bypass": RATE_BYPASS})
    return s


@pytest.fixture(scope="module")
def token(session):
    r = session.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": "مدير", "pin": MANAGER_PIN},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    tok = r.json().get("access_token")
    assert tok
    session.headers["Authorization"] = f"Bearer {tok}"
    return tok


def _find_journal_entry_by_ref(session, ref_id):
    r = session.get(f"{BASE_URL}/api/finance/journal-entries", params={"workshop_id": WORKSHOP_ID, "limit": 1000}, timeout=30)
    assert r.status_code == 200, r.text
    entries = r.json() if isinstance(r.json(), list) else r.json().get("entries") or r.json().get("data") or []
    return [e for e in entries if e.get("reference_id") == ref_id]


def test_1_login(token):
    assert token


def test_2_deferred_sale_creates_temp_entry(session, token):
    payload = {
        "type": "sale",
        "partnerName": "عميل اختبار وكيل",
        "partnerType": "customer",
        "paymentMethod": "آجل",
        "paymentStatus": "unpaid",
        "items": [{"name": "خدمة اختبار", "price": 150, "qty": 1, "itemType": "service"}],
        "total": 150,
        "workshopId": WORKSHOP_ID,
        "notes": "اختبار وكيل الفحص",
    }
    r = session.post(f"{BASE_URL}/api/operations", json=payload, timeout=30)
    assert r.status_code in (200, 201), r.text
    op = r.json()
    op_id = op.get("id") or op.get("_id") or op.get("operation_id")
    assert op_id
    created_ops.append(op_id)

    # give backend a moment to write JE
    time.sleep(1.5)
    entries = _find_journal_entry_by_ref(session, op_id)
    assert entries, f"No journal entry found for op {op_id}"
    # base entry
    base = [e for e in entries if (e.get("source") or "").startswith("operation") and (e.get("source") or "") != "operation_payment"]
    assert base, f"No base operation entry: {entries}"
    b = base[0]
    desc = b.get("description", "")
    assert "[قيد مؤقت — بيع آجل]" in desc, f"Description missing temp tag: {desc!r}"

    lines = b.get("lines") or []
    dr = next((l for l in lines if float(l.get("debit") or 0) > 0), None)
    cr = next((l for l in lines if float(l.get("credit") or 0) > 0), None)
    assert dr and cr, f"Missing dr/cr lines: {lines}"
    assert (_acc(dr)) == "005", f"Debit account not 005: {dr}"
    assert float(dr.get("debit")) == 150.0
    assert float(cr.get("credit")) == 150.0
    _state["op_id_deferred"] = op_id


def test_3_partial_settlement(session, token):
    op_id = _state["op_id_deferred"]
    idem = str(uuid.uuid4())
    r = session.post(
        f"{BASE_URL}/api/operations/{op_id}/confirm-payment",
        json={"amount": 50, "paymentMethod": "cash", "workshopId": WORKSHOP_ID},
        headers={"Idempotency-Key": idem},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    if isinstance(data, dict) and "data" in data and isinstance(data["data"], dict):
        data = data["data"]
    remaining = data.get("remaining") or data.get("remaining_amount")
    status = data.get("status") or data.get("payment_status")
    assert remaining in (100, 100.0, "100", "100.0"), f"remaining={remaining} full resp={data}"
    assert status == "partial", f"status={status}"

    time.sleep(1.5)
    entries = _find_journal_entry_by_ref(session, op_id)
    base = [e for e in entries if (e.get("source") or "") != "operation_payment"]
    assert base
    assert "مُحصَّل جزئياً" in base[0].get("description", ""), f"desc={base[0].get('description')}"

    pay = [e for e in entries if (e.get("source") or "") == "operation_payment"]
    assert pay, f"No payment entry: {entries}"
    lines = pay[0].get("lines") or []
    dr = next((l for l in lines if float(l.get("debit") or 0) > 0), None)
    cr = next((l for l in lines if float(l.get("credit") or 0) > 0), None)
    assert (_acc(dr)) == "003"
    assert (_acc(cr)) == "005"
    assert float(dr.get("debit")) == 50.0
    assert float(cr.get("credit")) == 50.0


def test_4_full_settlement(session, token):
    op_id = _state["op_id_deferred"]
    idem = str(uuid.uuid4())
    r = session.post(
        f"{BASE_URL}/api/operations/{op_id}/confirm-payment",
        json={"amount": 100, "paymentMethod": "cash", "workshopId": WORKSHOP_ID},
        headers={"Idempotency-Key": idem},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    if isinstance(data, dict) and "data" in data and isinstance(data["data"], dict):
        data = data["data"]
    status = data.get("status") or data.get("payment_status")
    assert status == "paid", f"status={status} resp={data}"

    time.sleep(1.5)
    entries = _find_journal_entry_by_ref(session, op_id)
    base = [e for e in entries if (e.get("source") or "") != "operation_payment"]
    desc = base[0].get("description", "")
    assert "[بيع آجل — مُسوَّى ✓]" in desc, f"desc={desc}"


def test_5_cash_sale_regression(session, token):
    payload = {
        "type": "sale",
        "partnerName": "عميل اختبار نقدي",
        "partnerType": "customer",
        "paymentMethod": "cash",
        "paymentStatus": "paid",
        "items": [{"name": "خدمة نقدية", "price": 200, "qty": 1, "itemType": "service"}],
        "total": 200,
        "workshopId": WORKSHOP_ID,
        "notes": "اختبار نقدي",
    }
    r = session.post(f"{BASE_URL}/api/operations", json=payload, timeout=30)
    assert r.status_code in (200, 201), r.text
    op_id = r.json().get("id") or r.json().get("_id")
    assert op_id
    created_ops.append(op_id)

    time.sleep(1.5)
    entries = _find_journal_entry_by_ref(session, op_id)
    assert entries
    b = entries[0]
    desc = b.get("description", "")
    assert "قيد مؤقت" not in desc, f"Cash sale unexpectedly tagged temp: {desc}"
    lines = b.get("lines") or []
    dr = next((l for l in lines if float(l.get("debit") or 0) > 0), None)
    assert (_acc(dr)) == "003", f"Cash sale debit should be 003, got {dr}"


def test_6_ssot_ar_summary(session, token):
    r = session.post(f"{BASE_URL}/api/assistant/tool/finance.ar_summary", json={}, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    result = data.get("result") or data
    assert "temporary_deferred_total" in result, f"Missing key: {list(result.keys())}"
    assert "temporary_deferred_entries" in result
    assert "temporary_deferred_note" in result
    assert isinstance(result["temporary_deferred_total"], (int, float))
    assert isinstance(result["temporary_deferred_entries"], list)


def test_7_chat_routing_to_ar_summary(session, token):
    r = session.post(
        f"{BASE_URL}/api/assistant/chat",
        json={"message": "كم القيود المؤقتة للبيع الآجل؟", "session_id": "qa-temp-deferred"},
        timeout=180,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    if isinstance(data, dict) and "data" in data:
        data = data["data"]
    tool_results = data.get("tool_results") or []
    tools = [t.get("tool") or t.get("name") for t in tool_results]
    assert any("ar_summary" in (t or "") for t in tools), f"tools used: {tools}"


def test_8_chat_greeting_regression(session, token):
    r = session.post(
        f"{BASE_URL}/api/assistant/chat",
        json={"message": "مرحبا", "session_id": "qa-greeting-iter254"},
        timeout=180,
    )
    assert r.status_code == 200, r.text


def test_9_prompt_versions(session, token):
    r = session.get(f"{BASE_URL}/api/assistant/prompt/versions", timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    if isinstance(data, dict) and "data" in data and isinstance(data["data"], dict):
        data = data["data"]
    versions = data.get("versions") or (data if isinstance(data, list) else [])
    active = data.get("active") or data.get("active_version")
    if not active:
        active = next((v.get("version") or v.get("id") for v in (versions or []) if v.get("is_active") or v.get("active")), None)
    assert active, f"No active version found in: {data}"
    r2 = session.post(f"{BASE_URL}/api/assistant/prompt/activate", json={"version": active}, timeout=30)
    assert r2.status_code == 200, r2.text


def test_z_cleanup(session, token):
    failures = []
    for op_id in created_ops:
        r = session.delete(f"{BASE_URL}/api/operations/{op_id}", timeout=30)
        if r.status_code not in (200, 204):
            failures.append((op_id, r.status_code, r.text[:200]))
    # verify no residual entries
    time.sleep(1)
    for op_id in created_ops:
        entries = _find_journal_entry_by_ref(session, op_id)
        if entries:
            failures.append((op_id, "residual JE", len(entries)))
    assert not failures, f"cleanup issues: {failures}"
