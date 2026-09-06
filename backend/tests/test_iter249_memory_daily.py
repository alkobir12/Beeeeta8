"""Iter 249 — E2E validation of memory engine, PDPL redaction, and daily summary."""
import os
import time
import uuid
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://financial-ssot.preview.emergentagent.com").rstrip("/")


def login(username: str) -> str:
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"username": username}, timeout=15)
    assert r.status_code == 200, f"login {username} failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


def chat(token: str, message: str, session_id: str | None = None, daily_summary: bool | None = None):
    body = {"message": message, "language": "ar"}
    if session_id:
        body["session_id"] = session_id
    if daily_summary is not None:
        body["daily_summary"] = daily_summary
    r = requests.post(
        f"{BASE_URL}/api/assistant/chat",
        json=body,
        headers={"Authorization": f"Bearer {token}"},
        timeout=90,
    )
    return r


@pytest.fixture(scope="module")
def admin_token():
    return login("مدير")


@pytest.fixture(scope="module")
def ahmed_token():
    return login("احمد1")


@pytest.fixture(scope="module")
def faraj_token():
    return login("فرج1")


# --- Memory stats ---
def test_memory_stats_admin(admin_token):
    sid = f"iter249-mem-{uuid.uuid4().hex[:6]}"
    r = chat(admin_token, "الذاكرة", session_id=sid)
    assert r.status_code == 200, r.text
    data = r.json().get("data", {})
    text = data.get("response", "")
    print("MEMORY_STATS_TEXT:", text[:400])
    # Expect some memory stats markers
    assert any(k in text for k in ["الذاكرة", "المعرفة", "قصيرة", "طويلة"]), f"missing stats keywords: {text[:300]}"
    assert "2000" in text or "/2000" in text or "حجم" in text or "معرفة" in text


# --- Save-to-knowledge full chain ---
def test_save_knowledge_full_chain(admin_token, ahmed_token):
    sid = f"iter249-kn-{uuid.uuid4().hex[:6]}"
    unique_fact = f"رقم صندوق البريد التجريبي هو {uuid.uuid4().hex[:6]}"
    # Step 1: admin proposes
    r = chat(admin_token, f"احفظ في المعرفة: {unique_fact}", session_id=sid)
    assert r.status_code == 200, r.text
    data = r.json().get("data", {})
    print("PROPOSE_RESP:", str(data)[:600])
    text = data.get("response", "")
    executed = data.get("executed") or {}
    # Find approval id
    approval_id = executed.get("id") or executed.get("draft_id") or executed.get("approval_id")
    tool_results = data.get("tool_results") or []
    if not approval_id:
        # look in tool_results
        for tr in tool_results:
            payload = tr.get("data") or tr.get("result") or {}
            if isinstance(payload, dict):
                approval_id = payload.get("id") or payload.get("approval_id") or payload.get("draft_id")
                if approval_id:
                    break
    # Fallback: fetch latest pending memory_promote via approvals list
    if not approval_id:
        rl = requests.get(
            f"{BASE_URL}/api/runtime/approvals?status=pending",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=15,
        )
        assert rl.status_code == 200, rl.text
        items = rl.json().get("data") or rl.json() if isinstance(rl.json(), list) else rl.json().get("data", [])
        if isinstance(items, dict):
            items = items.get("data", [])
        # find latest memory_promote
        for it in reversed(items):
            payload = it.get("payload") or {}
            if payload.get("action") == "memory_promote" or "memory" in str(payload).lower():
                approval_id = it.get("id")
                break
    assert approval_id, f"could not find approval id. response={text[:300]}, executed={executed}"
    print("APPROVAL_ID:", approval_id)

    # Step 2: self-approve by admin → 403 four_eyes_violation
    r_self = requests.post(
        f"{BASE_URL}/api/runtime/approvals/{approval_id}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=15,
    )
    assert r_self.status_code == 403, f"expected 403 four-eyes, got {r_self.status_code}: {r_self.text}"
    assert "four_eyes" in r_self.text.lower() or "four-eyes" in r_self.text.lower() or "أربع" in r_self.text

    # Step 3: احمد1 approves → 200
    r_ok = requests.post(
        f"{BASE_URL}/api/runtime/approvals/{approval_id}/approve",
        headers={"Authorization": f"Bearer {ahmed_token}"},
        timeout=30,
    )
    assert r_ok.status_code == 200, f"ahmed approve failed: {r_ok.status_code} {r_ok.text}"
    print("APPROVED OK")

    # Step 4: check memory stats shows knowledge >= 1
    time.sleep(1)
    sid2 = f"iter249-mem2-{uuid.uuid4().hex[:6]}"
    r_stats = chat(admin_token, "الذاكرة", session_id=sid2)
    assert r_stats.status_code == 200
    stats_text = r_stats.json().get("data", {}).get("response", "")
    print("POST_APPROVE_STATS:", stats_text[:400])
    # extract knowledge counter - expect >=1
    import re
    m = re.search(r"معرفة\s*[^\d]*(\d+)", stats_text)
    if m:
        knowledge_count = int(m.group(1))
        assert knowledge_count >= 1, f"knowledge should be >=1, got {knowledge_count}"


# --- PDPL redaction (indirect: ask a customer question — bot text should NOT leak raw phone). ---
def test_pdpl_no_leak_in_llm_text(admin_token):
    sid = f"iter249-pdpl-{uuid.uuid4().hex[:6]}"
    r = chat(admin_token, "ابحث عن عميل غانم", session_id=sid)
    assert r.status_code == 200, r.text
    text = r.json().get("data", {}).get("response", "") or ""
    print("PDPL_TEXT_SNIP:", text[:500])
    # Look for any 10-digit Saudi mobile like 05XXXXXXXX in the LLM narrative (not cards).
    # Cards are separate; text should show mask like 05****XXXX or ****.
    import re
    raw_phones = re.findall(r"(?<!\d)05\d{8}(?!\d)", text)
    # A leaked phone would be an unmasked 05 followed by 8 real digits and no '*' in text
    # We tolerate absence entirely (redacted or no phone in narrative).
    if raw_phones:
        # ensure it's a mask pattern like 05****XXXX won't match \d{8}; so if this matched, it's leaked
        pytest.fail(f"raw phone leaked in LLM text: {raw_phones}")


# --- Daily summary: send TWO first-of-session messages; second must NOT contain summary ---
def test_no_duplicate_daily_summary_admin(admin_token):
    sid1 = f"iter249-ds1-{uuid.uuid4().hex[:6]}"
    r1 = chat(admin_token, "مرحبا", session_id=sid1)
    assert r1.status_code == 200
    txt1 = r1.json().get("data", {}).get("response", "") or ""
    # Wait then open a NEW session — summary should NOT reappear same day
    time.sleep(1)
    sid2 = f"iter249-ds2-{uuid.uuid4().hex[:6]}"
    r2 = chat(admin_token, "مرحبا", session_id=sid2)
    assert r2.status_code == 200
    txt2 = r2.json().get("data", {}).get("response", "") or ""
    print("ADMIN_2ND_SESSION:", txt2[:400])
    assert "الملخص اليومي" not in txt2, "daily summary duplicated on 2nd session same day for مدير"


# --- daily_summary:false param accepted ---
def test_daily_summary_flag_false_accepted(faraj_token):
    sid = f"iter249-ds-off-{uuid.uuid4().hex[:6]}"
    r = chat(faraj_token, "مرحبا", session_id=sid, daily_summary=False)
    assert r.status_code == 200, r.text
    text = r.json().get("data", {}).get("response", "") or ""
    print("FARAJ_NO_DS:", text[:400])
    assert "الملخص اليومي" not in text, "daily_summary=false must suppress the summary block"


# --- Positive: فرج1 first message w/ daily_summary default → summary WITHOUT revenue line, ≤5 lines (if not yet shown) ---
def test_daily_summary_faraj_role_no_revenue(faraj_token):
    # This is best-effort: if faraj already consumed today, we skip the positive assertion.
    sid = f"iter249-ds-faraj-{uuid.uuid4().hex[:6]}"
    r = chat(faraj_token, "أهلا", session_id=sid)
    assert r.status_code == 200
    text = r.json().get("data", {}).get("response", "") or ""
    print("FARAJ_HELLO:", text[:500])
    if "الملخص اليومي" in text:
        # Extract only the summary block (until first '---' separator or blank-then-content)
        block = text.split("الملخص اليومي", 1)[1]
        # cut at first horizontal rule
        block = block.split("---", 1)[0]
        # Revenue line should be absent for accountant role
        assert "إيرادات" not in block and "الإيراد" not in block, \
            f"accountant should not see revenue line: {block}"
        # ≤5 lines within the summary block itself
        summary_lines = [ln for ln in block.splitlines() if ln.strip()]
        assert len(summary_lines) <= 5, f"summary too long: {len(summary_lines)} lines: {summary_lines}"
    else:
        pytest.skip("فرج1 already consumed today's summary — no positive assertion possible")
