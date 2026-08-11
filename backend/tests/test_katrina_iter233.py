"""
Iteration 233 — Katrina (كاترينا) L16 assistant backend tests.

Covers:
- POST /api/assistant/chat write-intent execution (Arabic phrasings/dialects) -> mode=action, executed.status=committed
- POST /api/assistant/tool/customers.search nickname/kunya + hamza/article tolerant
- POST /api/assistant/chat pure question -> mode=normal + firewall.health_score in tool_results
- POST /api/assistant/chat risky delete -> mode=action, status=pending_approval + ApprovalCard
- GET /api/assistant/models -> default 'sonnet', first id 'sonnet', label 'Claude Sonnet 4.6'
"""
import os
import pytest
import requests
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://finance-overhaul-7.preview.emergentagent.com").rstrip("/")
PROPOSER = "مدير"
SESSION = f"iter233-{int(time.time())}"

created_artifacts = []  # collect for cleanup report


def _chat(message, model="sonnet", proposer=PROPOSER, session_id=None):
    payload = {"message": message, "model": model, "proposer": proposer, "session_id": session_id or SESSION}
    r = requests.post(f"{BASE_URL}/api/assistant/chat", json=payload, timeout=90)
    assert r.status_code == 200, f"chat {message!r} returned {r.status_code}: {r.text[:400]}"
    body = r.json()
    assert body.get("success") is True, f"envelope success!=True: {body}"
    return body.get("data") or {}


# --------------------------------------------------------------------------
# Models endpoint
# --------------------------------------------------------------------------
class TestAssistantModels:
    def test_models_default_is_sonnet(self):
        r = requests.get(f"{BASE_URL}/api/assistant/models", timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        data = body.get("data") if isinstance(body, dict) and "data" in body else body
        # Accept either flat or wrapped
        default = data.get("default") if isinstance(data, dict) else None
        models = data.get("models") if isinstance(data, dict) else None
        assert default == "sonnet", f"default should be 'sonnet', got {default}. body={body}"
        assert isinstance(models, list) and len(models) > 0, f"models list missing: {body}"
        first = models[0]
        assert first.get("id") == "sonnet", f"first model id should be 'sonnet', got {first}"
        label = (first.get("label") or first.get("name") or "")
        assert "Claude" in label and "Sonnet" in label, f"label should mention 'Claude Sonnet', got {label!r}"
        # explicit: should not advertise gpt as primary/default
        for m in models:
            mid = (m.get("id") or "").lower()
            if mid == default:
                assert "gpt" not in mid, f"default model should not be gpt-based: {m}"


# --------------------------------------------------------------------------
# Write-intent execution (must EXECUTE not give instructions)
# --------------------------------------------------------------------------
class TestExecuteWriteIntent:
    @pytest.mark.parametrize("msg,kind", [
        ("سجل عميل اسمه خالد المطيري جواله 0501234501", "create_customer_classical"),
        ("ابغى اضيف عميل تجريبي ٢ جواله 0501234502", "create_customer_dialect"),
        ("ضيف مركبة لوحة 7788 تويوتا كامري 2021", "create_vehicle"),
    ])
    def test_write_intent_executes(self, msg, kind):
        data = _chat(msg)
        mode = data.get("mode")
        executed = data.get("executed") or {}
        response = (data.get("response") or "")
        assert mode == "action", f"[{kind}] mode should be 'action', got {mode!r}. data={data}"
        status = executed.get("status")
        # Accept committed OR duplicate-prevention (system already executed once on prior run)
        acceptable = {"committed", "duplicate", "deduped", "exists"}
        is_dup = ("موجود" in response) or ("مكرر" in response) or status in acceptable - {"committed"}
        assert status == "committed" or is_dup, \
            f"[{kind}] executed.status should be 'committed' (or duplicate-blocked), got {status!r}. executed={executed} response={response[:200]!r}"
        # Response must clearly mark success OR duplicate-prevention (i.e. ACTED, not just instructions)
        ok_markers = ("✅" in response) and ("تم بنجاح" in response or "نجاح" in response)
        dup_markers = ("⚠️" in response) and ("موجود" in response)
        assert ok_markers or dup_markers, \
            f"[{kind}] response should be a success ✅ or duplicate ⚠️ marker, got: {response[:200]!r}"
        # Collect any created entity id for cleanup
        result = executed.get("result") or {}
        rid = result.get("id") or result.get("customer_id") or result.get("vehicle_id")
        created_artifacts.append({"kind": kind, "msg": msg, "id": rid, "result": result})


# --------------------------------------------------------------------------
# Nickname / kunya / hamza tolerant search
# --------------------------------------------------------------------------
class TestCustomersSearchTolerant:
    @pytest.mark.parametrize("query", [
        "ابو مصري",
        "ابو المصري",
        "أبو المصري",
    ])
    def test_kunya_search_returns_results(self, query):
        r = requests.post(
            f"{BASE_URL}/api/assistant/tool/customers.search",
            json={"query": query},
            timeout=45,
        )
        assert r.status_code == 200, f"{query!r} -> {r.status_code}: {r.text[:300]}"
        body = r.json()
        # Envelope is {success, tool, agent, result:{query, matches, count, cards}, write}
        # Or possibly {success, data:{...}}; handle both
        container = body.get("result") or body.get("data") or body
        count = None
        if isinstance(container, dict):
            count = container.get("count")
            if count is None:
                matches = container.get("matches") or container.get("results") or container.get("items") or []
                count = len(matches) if isinstance(matches, list) else 0
        assert (count or 0) >= 1, f"query {query!r} returned 0 matches. body={body}"


# --------------------------------------------------------------------------
# Pure question -> read path (no execution)
# --------------------------------------------------------------------------
class TestQuestionReadPath:
    def test_health_score_question_is_normal_mode(self):
        data = _chat("كم درجة الصحة المالية؟")
        mode = data.get("mode")
        tool_results = data.get("tool_results") or data.get("toolResults") or {}
        response = (data.get("response") or "")
        assert mode == "normal", f"mode should be 'normal' for a pure question, got {mode!r}. data keys={list(data.keys())}"
        # tool_results can be dict {tool: result} or list of {name,...}
        names = []
        if isinstance(tool_results, dict):
            names = list(tool_results.keys())
        elif isinstance(tool_results, list):
            names = [t.get("name") or t.get("tool") for t in tool_results if isinstance(t, dict)]
        assert any("firewall.health_score" in (n or "") for n in names), \
            f"tool_results should include firewall.health_score, got names={names}"
        assert "✅ تم" not in response, f"reply should not claim execution: {response[:200]!r}"


# --------------------------------------------------------------------------
# Risky delete -> approval card
# --------------------------------------------------------------------------
class TestRiskyDeleteApproval:
    def test_delete_operation_requires_approval(self):
        data = _chat("احذف العملية رقم 123")
        mode = data.get("mode")
        executed = data.get("executed") or {}
        cards = data.get("cards") or []
        assert mode == "action", f"mode should be 'action', got {mode!r}"
        status = executed.get("status")
        assert status == "pending_approval", f"risky delete should be pending_approval, got {status!r}. executed={executed}"
        # ApprovalCard present
        types = []
        for c in cards if isinstance(cards, list) else []:
            if isinstance(c, dict):
                types.append(c.get("type") or c.get("kind") or c.get("card_type"))
        assert any("Approval" in (t or "") for t in types), \
            f"cards should include an ApprovalCard, got types={types}"


# --------------------------------------------------------------------------
# Cleanup report (always run last to surface created artifacts)
# --------------------------------------------------------------------------
def test_zz_report_created_artifacts():
    # Not really an assertion — just print so the report shows what to clean up.
    print("\n[ITER233] Created artifacts during write-intent tests:")
    for a in created_artifacts:
        print(f"  - {a.get('kind')}: msg={a.get('msg')!r} id={a.get('id')} result_keys={list((a.get('result') or {}).keys())}")
    assert True
