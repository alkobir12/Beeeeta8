"""Iteration 254 — Code-review hotfixes (CR-1/CR-2/CR-3 + CR-4 supports).

CR-2 (G3 fix): a genuine execution failure (exception or status=="error") for an
  action-looking message must be surfaced honestly ("لم يُنفَّذ — خطأ") instead of
  silently falling through to the read/LLM path. read_only/rejected still fall through.
CR-3: `_FIN_MASDAR_RE` no longer over-matches the inventory word «توريد», and
  is_question is evaluated on both raw and normalized text.

These are in-process unit tests (monkeypatch execute_text) — no network/LLM needed
for CR-2/CR-3. DATA SAFETY: execute_text is mocked, nothing touches the DB.
"""
from __future__ import annotations

import asyncio

import pytest

import core.assistant_kernel as k
from core.assistant_kernel import looks_like_action


# ---- CR-3: masdar gate precision ----------------------------------------

@pytest.mark.parametrize("msg", [
    "عندنا توريد 5 قطع اليوم",
    "توريد بضاعة 10 كراتين",
    "كم التوريد هذا الشهر؟",
])
def test_tawreed_not_action(msg):
    assert looks_like_action(msg) is False, f"توريد should stay on read path: {msg}"


@pytest.mark.parametrize("msg", [
    "تحصيل من عبد العزيز العريني 2200 تحويل",
    "300 خصم إداري على عبد العزيز",
    "سداد 500 من محمد نقدا",
])
def test_financial_command_still_action(msg):
    assert looks_like_action(msg) is True, f"still must execute: {msg}"


# ---- CR-2: execution failure is surfaced, not swallowed ------------------

def _run_chat(message, **patch):
    async def _go():
        return await k._chat_impl(session_id="cr2-unit", message=message, use_ai=True, proposer="مدير")
    return asyncio.get_event_loop().run_until_complete(_go())


def test_execute_exception_surfaces_error(monkeypatch):
    async def _boom(*a, **kw):
        raise RuntimeError("forced failure for test")
    monkeypatch.setattr(k, "_dummy", None, raising=False)
    import core.unified_executor as ue
    monkeypatch.setattr(ue, "execute_text", _boom, raising=True)
    resp = _run_chat("سجل تحصيل 500 من محمد نقدا")
    assert resp["intent"] == "action_error", resp["intent"]
    assert (resp.get("executed") or {}).get("status") == "error"
    assert "لم يُنفَّذ" in resp["response"]


def test_execute_status_error_surfaces_error(monkeypatch):
    async def _err(*a, **kw):
        return {"status": "error", "error": "db down"}
    import core.unified_executor as ue
    monkeypatch.setattr(ue, "execute_text", _err, raising=True)
    resp = _run_chat("سجل تحصيل 500 من محمد نقدا")
    assert resp["intent"] == "action_error"
    assert (resp.get("executed") or {}).get("status") == "error"
    assert "لم يُنفَّذ" in resp["response"]


def test_execute_read_only_still_falls_through(monkeypatch):
    """A read_only classification must NOT be treated as an error (no regression)."""
    async def _ro(*a, **kw):
        return {"status": "read_only"}
    import core.unified_executor as ue
    monkeypatch.setattr(ue, "execute_text", _ro, raising=True)
    resp = _run_chat("سجل تحصيل 500 من محمد نقدا")
    # falls through to the read path → intent is NOT action_error
    assert resp["intent"] != "action_error", resp.get("intent")
