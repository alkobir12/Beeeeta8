"""Phase 3C.3 — LLM Intent Parser tests.

We don't hit the actual LLM here — we drive the synchronous variant
`parse_intent_sync` with a stub client. This keeps tests fast/offline.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest

from core import action_runtime
from core.llm_intent_parser import (
    Action,
    ALLOWED_ACTIONS,
    _extract_json,
    parse_intent_sync,
    parse_intent_with_llm,
)


@pytest.fixture(autouse=True)
def _reset_runtime():
    action_runtime.reset_for_tests()
    yield
    action_runtime.reset_for_tests()


# ── JSON extraction ─────────────────────────────────────────────────────────


def test_extract_json_plain():
    assert _extract_json('{"action":"create_customer"}') == {"action": "create_customer"}


def test_extract_json_markdown_fenced():
    s = '```json\n{"action":"create_vehicle","payload":{"plate":"9935"}}\n```'
    assert _extract_json(s) == {"action": "create_vehicle", "payload": {"plate": "9935"}}


def test_extract_json_with_prose():
    s = 'هنا الإجابة: {"action":"create_customer","payload":{"name":"احمد"}} انتهى.'
    res = _extract_json(s)
    assert res["action"] == "create_customer"
    assert res["payload"]["name"] == "احمد"


def test_extract_json_returns_none_for_garbage():
    assert _extract_json("لا يوجد JSON هنا") is None


# ── Sync parsing with stub LLM ──────────────────────────────────────────────


def _stub_llm(response: str):
    return lambda text: response


def test_parse_intent_create_customer():
    res = parse_intent_sync(
        "سجل عميل أحمد العتيبي",
        llm_client=_stub_llm('{"action":"create_customer","payload":{"name":"أحمد العتيبي","phone":"0501234567"}}'),
    )
    assert isinstance(res, Action)
    assert res.action == "create_customer"
    assert res.payload["name"] == "أحمد العتيبي"


def test_parse_intent_create_vehicle():
    res = parse_intent_sync(
        "أضف مركبة 9935",
        llm_client=_stub_llm('{"action":"create_vehicle","payload":{"plate":"9935"}}'),
    )
    assert res.action == "create_vehicle"
    assert res.payload["plate"] == "9935"


def test_parse_intent_close_visits():
    res = parse_intent_sync(
        "أغلق كل الزيارات النشطة",
        llm_client=_stub_llm('{"action":"close_visits","payload":{}}'),
    )
    assert res.action == "close_visits"


def test_parse_intent_get_active_visits():
    res = parse_intent_sync(
        "كم زيارة نشطة الآن؟",
        llm_client=_stub_llm('{"action":"get_active_visits","payload":{}}'),
    )
    assert res.action == "get_active_visits"


def test_parse_intent_unknown_action_downgrades():
    """Even if the LLM hallucinates a bogus action, we reject it."""
    res = parse_intent_sync(
        "افعل شيئاً غريباً",
        llm_client=_stub_llm('{"action":"delete_database","payload":{}}'),
    )
    assert res.action == "unknown"
    assert res.payload.get("hint") == "rejected_action"
    assert res.payload.get("raw") == "delete_database"


def test_parse_intent_garbage_response():
    res = parse_intent_sync(
        "أي شيء",
        llm_client=_stub_llm("ما هذه إجابة"),
    )
    assert res.action == "unknown"


def test_parse_intent_empty_text():
    res = parse_intent_sync("", llm_client=_stub_llm('{"action":"create_customer"}'))
    assert res.action == "unknown"


def test_parse_intent_llm_raises():
    def explode(_t):
        raise RuntimeError("boom")
    res = parse_intent_sync("شيء", llm_client=explode)
    assert res.action == "unknown"


# ── Async path (no real LLM call — Emergent key missing → unknown) ──────────


def test_parse_intent_with_llm_no_key(monkeypatch):
    """Without EMERGENT_LLM_KEY the async parser returns 'unknown' safely."""
    monkeypatch.delenv("EMERGENT_LLM_KEY", raising=False)
    res = asyncio.run(parse_intent_with_llm("سجل عميل"))
    assert res.action == "unknown"


# ── Allowed-actions whitelist ───────────────────────────────────────────────


def test_allowed_actions_whitelist_size():
    """If you add an action to the whitelist, add a runtime handler too."""
    assert ALLOWED_ACTIONS == {
        "create_customer", "create_vehicle", "create_visit",
        "close_visits", "get_active_visits",
    }


def test_close_visits_action_is_valid_in_runtime():
    """The runtime must accept close_visits — otherwise commits fail."""
    assert "close_visits" in action_runtime.VALID_ACTIONS


# ── Integration: Intent → Draft → Approve → Commit ─────────────────────────


def test_intent_to_draft_pipeline():
    """An LLM-parsed action flows through Action Runtime correctly."""
    parsed = parse_intent_sync(
        "سجل عميل احمد",
        llm_client=_stub_llm('{"action":"create_customer","payload":{"name":"احمد","phone":"0501112233"}}'),
    )
    assert parsed.action == "create_customer"

    # Manually mimic what /intent/execute does — register as draft.
    draft = action_runtime.create_draft(
        action="customer",  # runtime token
        payload=parsed.payload,
        proposer="bot_tester",
    )
    assert draft["status"] == "draft"
    req = action_runtime.request_approval(draft_id=draft["id"], requester="bot_tester")
    assert "error" not in req
    res = action_runtime.approve(approval_id=req["approval_id"], approver="bot_reviewer")
    assert "error" not in res
    # We don't commit here — that would write to live Supabase.
    assert draft["status"] == "approved"


def test_get_active_visits_returns_list():
    """get_active_visits returns a (possibly empty) list of vehicles."""
    res = action_runtime.get_active_visits(limit=5)
    assert isinstance(res, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
