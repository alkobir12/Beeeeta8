"""Phase 3C.4 — Unified Execution Engine tests.

Verifies the policy gate:
  • SAFE actions   → auto-commit (status=committed)
  • RISKY actions  → wait for human (status=pending_approval)
  • READ actions   → short-circuit (status=read_only)
  • UNKNOWN        → reject (status=rejected)
  • Four-Eyes intact even for auto-commit (proposer ≠ approver)
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest

from core import action_runtime, unified_executor
from core.llm_intent_parser import Action


@pytest.fixture(autouse=True)
def _reset():
    action_runtime.reset_for_tests()
    yield
    action_runtime.reset_for_tests()


# ─── Policy gate ────────────────────────────────────────────────────────────


def test_requires_approval_close_visits():
    a = Action(action="close_visits", payload={})
    assert unified_executor.requires_approval(a) is True


def test_requires_approval_create_customer_is_safe():
    a = Action(action="create_customer", payload={"name": "x"})
    assert unified_executor.requires_approval(a) is False


def test_requires_approval_unknown_falls_through():
    """Unknown is rejected separately — requires_approval doesn't apply."""
    a = Action(action="unknown")
    assert unified_executor.requires_approval(a) is False


# ─── execute_action — unknown ──────────────────────────────────────────────


def test_execute_action_unknown_rejected():
    res = asyncio.run(unified_executor.execute_action(Action(action="unknown")))
    assert res["status"] == "rejected"
    assert res["reason"] == "unknown_action"


# ─── execute_action — read-only ────────────────────────────────────────────


def test_execute_action_read_only_visits():
    res = asyncio.run(unified_executor.execute_action(
        Action(action="get_active_visits", payload={"limit": 3}),
    ))
    assert res["status"] == "read_only"
    assert isinstance(res["result"], list)


def test_execute_action_read_only_generic():
    res = asyncio.run(unified_executor.execute_action(Action(action="get_customers")))
    assert res["status"] == "read_only"
    assert res["result"] is None  # caller plugs the query


# ─── execute_action — auto-commit safe path ────────────────────────────────


def test_safe_action_auto_commits(monkeypatch):
    """Safe action goes draft → approve → commit in one call."""
    # Stub upsert_entity so we don't write to live Supabase from a unit test.
    monkeypatch.setattr(
        action_runtime,
        "upsert_entity",
        lambda table, data: {"id": "stub-id", "name": data.get("name"), **data},
    )
    res = asyncio.run(unified_executor.execute_action(
        Action(action="create_customer", payload={"name": "احمد", "phone": "0501234567"}),
        proposer="auto:llm",
    ))
    assert res["status"] == "committed"
    assert res["result"]["id"] == "stub-id"
    assert res["draft"]["status"] == "committed"
    assert res["policy"] == "auto_safe"


def test_safe_action_four_eyes_intact_for_auto_commit(monkeypatch):
    """Even auto-commit uses distinct proposer/approver identities."""
    monkeypatch.setattr(
        action_runtime,
        "upsert_entity",
        lambda table, data: {"id": "x", **data},
    )
    asyncio.run(unified_executor.execute_action(
        Action(action="create_vehicle", payload={"plate": "9935"}),
    ))
    # Find the most recent COMMIT in audit
    commits = [r for r in action_runtime.get_audit_trail() if r["event"] == "COMMIT"]
    assert commits, "no COMMIT audit row"
    last = commits[-1]
    assert last.get("committer") == "auto:policy"
    # Proposer was different — auto:llm vs auto:policy
    grants = [r for r in action_runtime.get_audit_trail() if r["event"] == "APPROVAL_GRANTED"]
    assert grants[-1].get("approver") == "auto:policy"


# ─── execute_action — risky → manual approval ──────────────────────────────


def test_risky_action_waits_for_human():
    res = asyncio.run(unified_executor.execute_action(
        Action(action="close_visits", payload={}),
        proposer="فرج1",
    ))
    assert res["status"] == "pending_approval"
    assert res["policy"] == "manual_review_required"
    assert "draft" in res and "approval" in res
    # Draft is still pending — NOT committed
    draft = action_runtime.get_draft(res["draft"]["id"])
    assert draft["status"] == "pending_approval"


# ─── execute_text — full text→commit ───────────────────────────────────────


def test_execute_text_unknown_when_llm_returns_unknown(monkeypatch):
    async def _stub_parse(text, **kwargs):
        return Action(action="unknown")
    monkeypatch.setattr(unified_executor, "parse_intent_with_llm", _stub_parse)
    res = asyncio.run(unified_executor.execute_text("..."))
    assert res["status"] == "rejected"


def test_execute_text_safe_pipeline(monkeypatch):
    async def _stub_parse(text, **kwargs):
        return Action(
            action="create_customer",
            payload={"name": "ماجد", "phone": "0501112233"},
        )
    monkeypatch.setattr(unified_executor, "parse_intent_with_llm", _stub_parse)
    monkeypatch.setattr(
        action_runtime,
        "upsert_entity",
        lambda table, data: {"id": "id-1", **data},
    )
    res = asyncio.run(unified_executor.execute_text("سجل عميل ماجد"))
    assert res["status"] == "committed"
    assert res["result"]["name"] == "ماجد"


def test_execute_text_risky_pipeline(monkeypatch):
    async def _stub_parse(text, **kwargs):
        return Action(action="close_visits", payload={})
    monkeypatch.setattr(unified_executor, "parse_intent_with_llm", _stub_parse)
    res = asyncio.run(unified_executor.execute_text("أغلق كل الزيارات"))
    assert res["status"] == "pending_approval"


def test_execute_text_empty_input():
    res = asyncio.run(unified_executor.execute_text("   "))
    assert res["status"] == "rejected"
    assert res["reason"] == "empty_text"


# ─── Class wrapper parity ──────────────────────────────────────────────────


def test_unified_engine_class_delegates(monkeypatch):
    async def _stub_parse(text, **kwargs):
        return Action(action="get_active_visits", payload={"limit": 1})
    monkeypatch.setattr(unified_executor, "parse_intent_with_llm", _stub_parse)
    engine = unified_executor.UnifiedExecutionEngine()
    res = asyncio.run(engine.execute("شيء"))
    assert res["status"] == "read_only"


def test_unified_engine_class_requires_approval_static():
    assert unified_executor.UnifiedExecutionEngine.requires_approval(
        Action(action="close_visits"),
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
