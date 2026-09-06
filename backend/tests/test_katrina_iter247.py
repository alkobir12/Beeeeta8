"""Backend tests for Katrina Chat-to-CRUD & Four-Eyes (iter 247).

Covers:
- Purchase intent (present & past tense) → pending_approval
- 'اعتمادات كاترينا' → runtime.pending_approvals tool
- Contextual cancel — no journal_id prompt
- Four-Eyes regression — same-user approve blocked, different approver OK
"""
import os
import uuid
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://financial-ssot.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


def _login(username: str) -> str:
    r = requests.post(f"{API}/auth/login", json={"username": username}, timeout=30)
    assert r.status_code == 200, f"login {username}: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def tokens():
    return {
        "مدير": _login("مدير"),
        "احمد1": _login("احمد1"),
    }


def _chat(token: str, message: str, session_id: str) -> dict:
    r = requests.post(
        f"{API}/assistant/chat",
        json={"message": message, "session_id": session_id},
        headers={"Authorization": f"Bearer {token}"},
        timeout=90,
    )
    assert r.status_code == 200, f"chat: {r.status_code} {r.text[:400]}"
    body = r.json()
    # response wrapped in {success, data}
    data = body.get("data", body)
    return data


# ---- Purchase intent tests ----

def test_purchase_present_tense_pending(tokens):
    sid = f"iter247-{uuid.uuid4().hex[:8]}"
    data = _chat(tokens["مدير"], "اشتري فلتر زيت بـ 40 ريال من مورد التقوى كاش", sid)
    intent = data.get("intent") or data.get("mode")
    executed = data.get("executed") or {}
    text = (data.get("reply") or data.get("message") or "") + str(data)
    assert "NameError" not in text
    assert intent in ("action", "action_pending", "purchase"), f"intent={intent} data keys={list(data.keys())}"
    assert executed.get("status") == "pending_approval", f"status={executed.get('status')} executed={executed}"


def test_purchase_past_tense_pending(tokens):
    sid = f"iter247-{uuid.uuid4().hex[:8]}"
    data = _chat(tokens["مدير"], "اشتريت بواجي بـ 80 ريال من مورد النخبة كاش", sid)
    intent = data.get("intent") or data.get("mode")
    executed = data.get("executed") or {}
    assert intent in ("action", "action_pending", "purchase"), f"past-tense should route to action, got intent={intent}"
    assert executed.get("status") == "pending_approval"


# ---- اعتمادات كاترينا ----

def test_pending_approvals_intent(tokens):
    sid = f"iter247-{uuid.uuid4().hex[:8]}"
    data = _chat(tokens["مدير"], "اعتمادات كاترينا", sid)
    tool_results = data.get("tool_results") or []
    tools_used = [tr.get("tool") for tr in tool_results]
    assert "runtime.pending_approvals" in tools_used, f"expected runtime.pending_approvals in tools, got {tools_used}"
    response_text = str(data.get("response") or data.get("reply") or "")
    assert "اعتمادات" in response_text or "معلّق" in response_text or "معلق" in response_text


# ---- Contextual cancel ----

def test_contextual_cancel_no_journal_prompt(tokens):
    sid = f"iter247-{uuid.uuid4().hex[:8]}"
    d1 = _chat(tokens["مدير"], "اشتري بطارية بـ 120 ريال من مورد الاختبار كاش", sid)
    assert (d1.get("executed") or {}).get("status") == "pending_approval"

    d2 = _chat(tokens["مدير"], "الغي آخر عملية شراء", sid)
    reply = str(d2.get("reply") or d2.get("message") or "")
    executed = d2.get("executed") or {}
    assert "journal_id" not in reply.lower(), f"should not prompt for journal_id: {reply}"
    assert "المسودة" in reply or executed.get("status") == "cancelled", f"expected cancel, got reply={reply} executed={executed}"


# ---- Four-Eyes regression ----

def test_four_eyes_regression(tokens):
    sid = f"iter247-{uuid.uuid4().hex[:8]}"
    d = _chat(tokens["مدير"], "اشتري زيت بـ 55 ريال من مورد فور آيز كاش", sid)
    executed = d.get("executed") or {}
    approval_id = executed.get("approval_id") or executed.get("id") or (executed.get("approval") or {}).get("id")
    # try to find via list
    if not approval_id:
        r = requests.get(f"{API}/runtime/approvals?status=pending",
                         headers={"Authorization": f"Bearer {tokens['مدير']}"}, timeout=30)
        assert r.status_code == 200
        items = r.json().get("data") or r.json().get("items") or r.json()
        if isinstance(items, list) and items:
            # take the last one created by مدير
            approval_id = items[-1].get("id") or items[-1].get("approval_id")
    assert approval_id, f"no approval_id found: {d}"

    # Same user approves → 403
    r_same = requests.post(
        f"{API}/runtime/approvals/{approval_id}/approve",
        headers={"Authorization": f"Bearer {tokens['مدير']}"},
        json={},
        timeout=30,
    )
    assert r_same.status_code == 403, f"same-user approve should be 403, got {r_same.status_code} {r_same.text[:200]}"
    assert "four_eyes" in r_same.text.lower() or "four eyes" in r_same.text.lower()

    # Different approver → success
    r_diff = requests.post(
        f"{API}/runtime/approvals/{approval_id}/approve",
        headers={"Authorization": f"Bearer {tokens['احمد1']}"},
        json={},
        timeout=30,
    )
    assert r_diff.status_code in (200, 201), f"different approver should succeed, got {r_diff.status_code} {r_diff.text[:200]}"
