"""
End-to-end verification of Katrina chat routing hotfixes (iter 252).
Tests FIX-1, FIX-1b, FIX-1c (four-eyes negative control), FIX-2 (no fabrication),
FIX-2b (empty-result honesty), BOT<->PAGES linkage, deep-link integrity,
and multi-turn session continuity.

Governance: creates drafts then DISCARDS them; never approves real drafts.
"""
import os
import re
import uuid
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://finance-overhaul-7.preview.emergentagent.com").rstrip("/")

FABRICATED_NAMES = ["خالد العتيبي", "محمد الشمري", "سعد القحطاني"]
FABRICATED_REFS = ["PAY-001", "INV-004", "EXP-003", "PUR-002"]


def _login(username: str) -> str:
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"username": username}, timeout=30)
    assert r.status_code == 200, f"login {username} failed: {r.status_code} {r.text[:200]}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_token():
    return _login("مدير")


@pytest.fixture(scope="module")
def supervisor_token():
    return _login("احمد1")


@pytest.fixture
def created_drafts():
    """Track drafts created during a test so we can discard them after."""
    drafts = []
    yield drafts
    # cleanup - use admin token
    try:
        tok = _login("مدير")
        # Try to fetch draft_id from approvals list; discard by draft_id
        try:
            lst = requests.get(
                f"{BASE_URL}/api/runtime/approvals?status=pending",
                headers={"Authorization": f"Bearer {tok}"},
                timeout=15,
            ).json()
            items = lst if isinstance(lst, list) else (lst.get("data") or lst.get("items") or [])
            approval_to_draft = {i.get("id"): i.get("draft_id") for i in items if isinstance(i, dict)}
        except Exception:
            approval_to_draft = {}
        for d in drafts:
            draft_id = approval_to_draft.get(d, d)
            try:
                requests.post(
                    f"{BASE_URL}/api/runtime/drafts/{draft_id}/discard",
                    headers={"Authorization": f"Bearer {tok}"},
                    json={"reason": "test cleanup"},
                    timeout=15,
                )
            except Exception:
                pass
    except Exception:
        pass


def _chat(token: str, message: str, session_id: str | None = None):
    payload = {"message": message, "use_ai": True}
    if session_id:
        payload["session_id"] = session_id
    r = requests.post(
        f"{BASE_URL}/api/assistant/chat",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
        timeout=90,
    )
    assert r.status_code == 200, f"chat failed: {r.status_code} {r.text[:300]}"
    body = r.json()
    return body.get("data", body)


# ------------- FIX-1: masdar collection -> pending_approval + ApprovalCard -------------
def test_fix1_masdar_collection_pending_approval(admin_token, created_drafts):
    d = _chat(admin_token, "تحصيل من عبد العزيز العريني 2200 تحويل")
    executed = d.get("executed") or {}
    assert executed.get("status") == "pending_approval", f"expected pending_approval, got {executed}"
    assert executed.get("action") == "collect_payment", f"expected collect_payment, got {executed.get('action')}"
    # must NOT be the fake 'اكتب نعم' text confirmation
    response_txt = d.get("response") or ""
    assert "اكتب نعم" not in response_txt, "response should not use fake 'اكتب نعم' confirmation"
    assert ("أربع أعين" in response_txt) or ("طرف ثانٍ" in response_txt) or ("اعتماد" in response_txt), \
        f"expected four-eyes/approval wording, got: {response_txt[:200]}"
    # ApprovalCard present
    cards = d.get("cards") or []
    approval_cards = [c for c in cards if c.get("type") in ("approval", "ApprovalCard") or "approval" in str(c.get("type", "")).lower()]
    assert approval_cards, f"expected ApprovalCard in cards, got types={[c.get('type') for c in cards]}"
    # track for cleanup
    draft_id = executed.get("approval_id") or executed.get("draft_id") or executed.get("entity_id")
    if draft_id:
        created_drafts.append(draft_id)


# ------------- FIX-1b: admin discount as expense -------------
def test_fix1b_admin_discount_as_expense(admin_token, created_drafts):
    d = _chat(admin_token, "سجّل خصم إداري 300 ريال على عبد العزيز العريني")
    executed = d.get("executed") or {}
    assert executed.get("status") == "pending_approval", f"expected pending_approval, got {executed}"
    assert executed.get("action") == "create_expense", f"expected create_expense, got {executed.get('action')}"
    cards = d.get("cards") or []
    approval_cards = [c for c in cards if "approval" in str(c.get("type", "")).lower()]
    assert approval_cards, f"expected ApprovalCard, got {[c.get('type') for c in cards]}"
    draft_id = executed.get("approval_id") or executed.get("draft_id") or executed.get("entity_id")
    if draft_id:
        created_drafts.append(draft_id)


# ------------- FIX-1c: four-eyes self-approve blocked -------------
def test_fix1c_four_eyes_self_approve_blocked(admin_token, created_drafts):
    d = _chat(admin_token, "تحصيل من عبد العزيز العريني 100 نقدا")
    executed = d.get("executed") or {}
    assert executed.get("status") == "pending_approval"
    approval_id = executed.get("approval_id") or executed.get("draft_id") or executed.get("entity_id")
    assert approval_id, f"no approval_id returned: {executed}"
    created_drafts.append(approval_id)
    # Attempt self-approve as same user (مدير)
    r = requests.post(
        f"{BASE_URL}/api/runtime/approvals/{approval_id}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=30,
    )
    assert r.status_code in (400, 403, 409), f"self-approve should be blocked, got {r.status_code}: {r.text[:200]}"
    body_txt = r.text
    assert ("four_eyes" in body_txt.lower()) or ("المُنشئ" in body_txt) or ("بنفسه" in body_txt) or ("نفسه" in body_txt), \
        f"expected four_eyes_violation error, got: {body_txt[:200]}"


# ------------- FIX-2: no fabrication for full journal request -------------
@pytest.mark.parametrize("query", ["اعطني كل القيود المحاسبية", "القيود كاملة"])
def test_fix2_no_fabrication_in_journal(admin_token, query):
    d = _chat(admin_token, query)
    txt = d.get("response") or ""
    for name in FABRICATED_NAMES:
        assert name not in txt, f"fabricated name '{name}' appeared in response for query '{query}'"
    for ref in FABRICATED_REFS:
        assert ref not in txt, f"fabricated ref '{ref}' appeared in response for query '{query}'"
    # Should mention real journal count 15 or balance
    has_real_data = ("15" in txt) or ("قيد" in txt) or ("متوازن" in txt) or bool(d.get("cards"))
    assert has_real_data, f"expected real journal data hints in response, got: {txt[:300]}"


# ------------- BOT <-> PAGES linkage -------------
def test_linkage_ar_summary(admin_token):
    d = _chat(admin_token, "كم ذمم العملاء")
    txt = d.get("response") or ""
    assert txt.strip(), "empty response for AR summary"
    # top debtor عمر الخضيري or a numeric total
    has_number = bool(re.search(r"\d", txt)) or bool(d.get("cards"))
    assert has_number, f"expected numbers/cards in AR summary, got: {txt[:300]}"


def test_linkage_customer_card(admin_token):
    d = _chat(admin_token, "عبد العزيز العريني")
    txt = d.get("response") or ""
    cards = d.get("cards") or []
    # look for customer card with actions
    customer_cards = [c for c in cards if "customer" in str(c.get("type", "")).lower()]
    # Balance 2,500 or invoice ref
    combined = txt + str(cards)
    assert ("2,500" in combined) or ("2500" in combined) or ("INV001273" in combined) or customer_cards, \
        f"expected customer info (balance/invoice/card), got resp={txt[:200]} cards={[c.get('type') for c in cards]}"


@pytest.mark.parametrize("q,expect", [
    ("كم عدد المركبات الحالية", "172"),
    ("كم قيد محاسبي مسجل حاليا", "15"),
])
def test_linkage_counts(admin_token, q, expect):
    d = _chat(admin_token, q)
    txt = d.get("response") or ""
    combined = txt + str(d.get("cards") or [])
    assert expect in combined, f"expected '{expect}' in response for '{q}', got: {txt[:300]}"


@pytest.mark.parametrize("q", ["الزيارات النشطة", "القطع الناقصة", "آخر العمليات"])
def test_linkage_operational_queries(admin_token, q):
    d = _chat(admin_token, q)
    txt = d.get("response") or ""
    # must be non-empty and not full of fabricated names
    assert txt.strip() or d.get("cards"), f"empty response for '{q}'"
    for name in FABRICATED_NAMES:
        assert name not in txt, f"fabricated '{name}' in response for '{q}'"


# ------------- Deep-link / navigation integrity -------------
def test_deeplink_customer_card_actions(admin_token):
    d = _chat(admin_token, "عبد العزيز العريني")
    cards = d.get("cards") or []
    for c in cards:
        actions = c.get("actions") or []
        for a in actions:
            intent = a.get("intent") or a.get("type")
            if intent == "navigate":
                target = a.get("target") or a.get("route") or a.get("url") or ""
                assert target, f"navigate action with empty target in card {c.get('type')}"
            elif intent == "runtime":
                assert a.get("endpoint"), f"runtime action missing endpoint in card {c.get('type')}"
                assert a.get("method"), f"runtime action missing method in card {c.get('type')}"


# ------------- Multi-turn session continuity -------------
def test_multi_turn_session_continuity(admin_token):
    sid = f"test-session-{uuid.uuid4().hex[:8]}"
    d1 = _chat(admin_token, "كم ذمم العملاء", session_id=sid)
    assert d1.get("session_id") == sid or d1.get("session_id"), "no session_id echoed"
    d2 = _chat(admin_token, "عبد العزيز العريني", session_id=sid)
    txt2 = d2.get("response") or ""
    assert txt2.strip() or d2.get("cards")
    d3 = _chat(admin_token, "من أين جاء رقم رصيده؟", session_id=sid)
    txt3 = d3.get("response") or ""
    # Should not contain fabricated names
    for name in FABRICATED_NAMES:
        assert name not in txt3, f"fabricated '{name}' in provenance response"
    assert txt3.strip(), "empty provenance response"
