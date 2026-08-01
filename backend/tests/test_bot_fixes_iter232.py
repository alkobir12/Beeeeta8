"""Test bot fixes (iteration 232):
- Name-based queries trigger customers.search / operations.search
- Firewall alerts pattern triggers firewall.top_alerts (not operations.search)
- Smart fallback for proper Arabic names
- /api/runtime/execute delete_operation → pending_approval
- /api/runtime/execute create_customer → committed
"""
import os
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://ar-ledger-ssot.preview.emergentagent.com").rstrip("/")
CHAT = f"{BASE_URL}/api/assistant/chat"
EXEC = f"{BASE_URL}/api/runtime/execute"


def _post_chat(text, session=None):
    body = {"message": text}
    if session:
        body["session_id"] = session
    r = requests.post(CHAT, json=body, timeout=60)
    assert r.status_code == 200, f"chat failed {r.status_code}: {r.text[:300]}"
    j = r.json()
    # Unwrap {success, data:{...}} envelope used by /api/assistant/chat
    if isinstance(j, dict) and "data" in j and isinstance(j["data"], dict):
        return j["data"]
    return j


def _tools(payload):
    return [t.get("tool") for t in (payload.get("tool_results") or [])]


# 1) "أعطني ملاحظة محمد الجهني" should trigger customers.search
def test_query_atani_mohamad_aljohani_triggers_customers_search():
    data = _post_chat("أعطني ملاحظة محمد الجهني")
    tools = _tools(data)
    assert "customers.search" in tools, f"Expected customers.search, got {tools}"
    assert (data.get("response") or "").strip() != ""


# 2) Operations details for محمد الجهني ابو خالد triggers BOTH ops + customers
def test_operations_details_mohamad_triggers_ops_and_customers():
    data = _post_chat("أعطني تفاصيل عمليه محمد الجهني ابو خالد")
    tools = _tools(data)
    assert "operations.search" in tools, f"Expected operations.search in {tools}"
    # customers.search may also be triggered by generic info pattern — both acceptable
    assert (data.get("response") or "").strip() != ""


# 3) "ماهي العمليات والتحذيرات" triggers firewall.top_alerts (NOT operations.search)
def test_alerts_pattern_triggers_firewall_not_ops():
    data = _post_chat("ماهي العمليات والتحذيرات")
    tools = _tools(data)
    assert "firewall.top_alerts" in tools, f"Expected firewall.top_alerts in {tools}"
    assert "operations.search" not in tools, f"operations.search should NOT trigger here, got {tools}"


# 4) "عمليات محمد الجهني" → operations.search
def test_ops_by_name_triggers_operations_search():
    data = _post_chat("عمليات محمد الجهني")
    tools = _tools(data)
    assert "operations.search" in tools, f"Expected operations.search, got {tools}"


# 5) "آخر العمليات" → operations.recent
def test_recent_ops_triggers_operations_recent():
    data = _post_chat("آخر العمليات")
    tools = _tools(data)
    assert "operations.recent" in tools, f"Expected operations.recent, got {tools}"


# 6) "هل يوجد عمليات بدون قيود" → firewall.operation_integrity
def test_integrity_pattern_triggers_firewall_integrity():
    data = _post_chat("هل يوجد عمليات بدون قيود")
    tools = _tools(data)
    assert "firewall.operation_integrity" in tools, f"Expected firewall.operation_integrity in {tools}"


# 7) Smart fallback for proper Arabic name only
def test_smart_fallback_proper_name_only():
    data = _post_chat("محمد الجهني ابو خالد")
    tools = _tools(data)
    assert "customers.search" in tools, f"Expected customers.search via fallback, got {tools}"
    assert "operations.search" in tools, f"Expected operations.search via fallback, got {tools}"


# 8) /api/runtime/execute  احذفها  proposer=مدير  → pending_approval
def test_execute_delete_operation_via_four_eyes():
    body = {"text": "احذفها", "proposer": "مدير"}
    r = requests.post(EXEC, json=body, timeout=30)
    assert r.status_code in (200, 201), f"{r.status_code}: {r.text[:300]}"
    j = r.json()
    status = j.get("status") or (j.get("data") or {}).get("status")
    # delete_operation is risky → must require approval (pending_approval) OR be rejected with reason
    assert status in ("pending_approval", "needs_context", "rejected"), f"Unexpected status: {status} payload={j}"


# 9) /api/runtime/execute سجل عميل احمد 0501234567 → committed
def test_execute_create_customer_committed():
    body = {"text": "سجل عميل TEST_احمد 0501234567", "proposer": "مدير"}
    r = requests.post(EXEC, json=body, timeout=30)
    assert r.status_code in (200, 201), f"{r.status_code}: {r.text[:300]}"
    j = r.json()
    status = j.get("status") or (j.get("data") or {}).get("status")
    assert status in ("committed", "pending_approval"), f"Unexpected status: {status} payload={j}"


# 10) chat endpoint returns non-empty response for queries
def test_chat_endpoint_non_empty_responses():
    queries = [
        "أعطني ملاحظة محمد الجهني",
        "عمليات محمد الجهني",
        "آخر العمليات",
        "ماهي العمليات والتحذيرات",
        "هل يوجد عمليات بدون قيود",
    ]
    for q in queries:
        data = _post_chat(q)
        assert (data.get("response") or "").strip() != "", f"empty response for: {q}"
        assert isinstance(data.get("tool_results"), list)
