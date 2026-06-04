"""Phase 3C — Action Runtime tests.

Covers the full state machine:
  DRAFT → PENDING_APPROVAL → APPROVED → COMMITTED → ROLLED_BACK
  + Four-Eyes Principle
  + Idempotent commits
  + Rejection flow
  + Audit trail
  + Power Mode → Action Runtime integration
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest

from core import action_runtime, power_mode


@pytest.fixture(autouse=True)
def _reset_runtime():
    """Reset state before each test."""
    action_runtime.reset_for_tests()
    yield
    action_runtime.reset_for_tests()


# ─── Draft creation ────────────────────────────────────────────────────────


def test_create_draft_sets_status_draft():
    d = action_runtime.create_draft(action="customer", payload={"name": "احمد"}, proposer="فرج1")
    assert d["status"] == "draft"
    assert d["proposer"] == "فرج1"
    assert d["action"] == "customer"
    assert d["payload"]["name"] == "احمد"
    assert action_runtime.get_draft(d["id"]) is d


def test_create_draft_appends_audit_row():
    d = action_runtime.create_draft(action="customer", payload={}, proposer="x")
    audit = action_runtime.get_audit_trail()
    assert any(row["event"] == "DRAFT_CREATED" and row["draft_id"] == d["id"] for row in audit)


# ─── State machine — happy path ───────────────────────────────────────────


def test_full_happy_path_draft_to_committed():
    d = action_runtime.create_draft(action="customer", payload={"name": "احمد", "phone": "0501"}, proposer="فرج1")
    # 1) request approval
    req = action_runtime.request_approval(draft_id=d["id"], requester="فرج1")
    assert "error" not in req
    assert d["status"] == "pending_approval"
    approval_id = req["approval_id"]
    # 2) approve (different user → 4-eyes ok)
    approved = action_runtime.approve(approval_id=approval_id, approver="مدير")
    assert "error" not in approved
    assert d["status"] == "approved"
    # 3) commit
    result = action_runtime.commit(draft_id=d["id"], committer="مدير")
    assert "error" not in result
    assert "execution_id" in result
    assert d["status"] == "committed"
    # 4) entity exists in staging DB
    assert result["result"]["name"] == "احمد"
    assert result["result"]["id"] in action_runtime.DB["customers"]


# ─── Four-Eyes Principle ──────────────────────────────────────────────────


def test_four_eyes_blocks_same_user_approver():
    d = action_runtime.create_draft(action="customer", payload={"name": "x"}, proposer="فرج1")
    req = action_runtime.request_approval(draft_id=d["id"], requester="فرج1")
    res = action_runtime.approve(approval_id=req["approval_id"], approver="فرج1")
    assert res.get("error") == "four_eyes_violation"
    # draft still pending
    assert d["status"] == "pending_approval"


def test_four_eyes_can_be_disabled_via_env(monkeypatch):
    monkeypatch.setenv("ACTION_RUNTIME_ENFORCE_4EYES", "false")
    d = action_runtime.create_draft(action="customer", payload={"name": "x"}, proposer="فرج1")
    req = action_runtime.request_approval(draft_id=d["id"], requester="فرج1")
    res = action_runtime.approve(approval_id=req["approval_id"], approver="فرج1")  # same user
    assert "error" not in res
    assert d["status"] == "approved"


# ─── Commit constraints ────────────────────────────────────────────────────


def test_commit_blocked_when_not_approved():
    d = action_runtime.create_draft(action="customer", payload={}, proposer="x")
    res = action_runtime.commit(draft_id=d["id"], committer="y")
    assert res.get("error") == "not_approved"


def test_commit_is_idempotent():
    d = action_runtime.create_draft(action="customer", payload={"name": "x"}, proposer="فرج1")
    req = action_runtime.request_approval(draft_id=d["id"])
    action_runtime.approve(approval_id=req["approval_id"], approver="مدير")
    r1 = action_runtime.commit(draft_id=d["id"], committer="مدير")
    r2 = action_runtime.commit(draft_id=d["id"], committer="مدير")
    assert r2.get("idempotent") is True
    assert r2["execution_id"] == r1["execution_id"]


def test_commit_unknown_action_returns_error():
    # Bypass create_draft's normal flow to inject an invalid action
    d = action_runtime.create_draft(action="customer", payload={}, proposer="x")
    d["action"] = "weird"  # tamper
    req = action_runtime.request_approval(draft_id=d["id"])
    action_runtime.approve(approval_id=req["approval_id"], approver="y")
    res = action_runtime.commit(draft_id=d["id"], committer="y")
    assert res.get("error") == "unknown_action"


# ─── Rejection flow ───────────────────────────────────────────────────────


def test_reject_approval_flips_draft_to_rejected():
    d = action_runtime.create_draft(action="customer", payload={}, proposer="فرج1")
    req = action_runtime.request_approval(draft_id=d["id"])
    res = action_runtime.reject_approval(approval_id=req["approval_id"], approver="مدير", reason="no")
    assert "error" not in res
    assert d["status"] == "rejected"
    assert res["approval"]["status"] == "rejected"


def test_rejected_draft_can_be_resubmitted():
    d = action_runtime.create_draft(action="customer", payload={}, proposer="x")
    req = action_runtime.request_approval(draft_id=d["id"])
    action_runtime.reject_approval(approval_id=req["approval_id"], approver="y", reason="fix it")
    # Re-request approval after rejection
    req2 = action_runtime.request_approval(draft_id=d["id"])
    assert "error" not in req2
    assert d["status"] == "pending_approval"


# ─── Rollback ──────────────────────────────────────────────────────────────


def test_rollback_removes_entity_from_db():
    d = action_runtime.create_draft(action="customer", payload={"name": "rollme"}, proposer="فرج1")
    req = action_runtime.request_approval(draft_id=d["id"])
    action_runtime.approve(approval_id=req["approval_id"], approver="مدير")
    res = action_runtime.commit(draft_id=d["id"], committer="مدير")
    eid = res["execution_id"]
    customer_id = res["result"]["id"]
    assert customer_id in action_runtime.DB["customers"]
    # Now rollback
    rb = action_runtime.rollback(execution_id=eid, rollbacker="مدير")
    assert rb["status"] == "rolled_back"
    assert customer_id not in action_runtime.DB["customers"]
    assert d["status"] == "rolled_back"


def test_double_rollback_is_safe():
    d = action_runtime.create_draft(action="customer", payload={"name": "x"}, proposer="فرج1")
    req = action_runtime.request_approval(draft_id=d["id"])
    action_runtime.approve(approval_id=req["approval_id"], approver="مدير")
    res = action_runtime.commit(draft_id=d["id"], committer="مدير")
    eid = res["execution_id"]
    action_runtime.rollback(execution_id=eid)
    r2 = action_runtime.rollback(execution_id=eid)
    assert r2.get("error") == "already_rolled_back"


# ─── Audit trail ──────────────────────────────────────────────────────────


def test_audit_records_all_transitions():
    d = action_runtime.create_draft(action="customer", payload={}, proposer="فرج1")
    req = action_runtime.request_approval(draft_id=d["id"])
    action_runtime.approve(approval_id=req["approval_id"], approver="مدير")
    res = action_runtime.commit(draft_id=d["id"], committer="مدير")
    action_runtime.rollback(execution_id=res["execution_id"], rollbacker="مدير")
    events = [r["event"] for r in action_runtime.get_audit_trail()]
    for needed in ("DRAFT_CREATED", "APPROVAL_REQUESTED", "APPROVAL_GRANTED", "COMMIT", "ROLLBACK"):
        assert needed in events, f"missing event {needed} in {events}"


# ─── Integration with Power Mode ──────────────────────────────────────────


def test_power_mode_registers_drafts_in_runtime():
    """`/power سجل عميل احمد` should produce a runtime-registered draft."""
    result = asyncio.run(power_mode.power_process(
        session_id="pm-rt-1",
        message="/power سجل عميل احمد",
        proposer="فرج1",
    ))
    assert result["executed"] == 1
    d = result["drafts"][0]
    assert d["intent_kind"] == "customer"
    assert d.get("runtime", {}).get("enabled") is True
    # Confirm it's findable in the runtime
    rt_draft = action_runtime.get_draft(d["id"])
    assert rt_draft is not None
    assert rt_draft["action"] == "customer"
    assert rt_draft["proposer"] == "فرج1"


def test_power_mode_drafts_have_runtime_actions_not_deferred():
    """Phase 3C: runtime drafts get clickable chips (not all deferred)."""
    result = asyncio.run(power_mode.power_process(
        session_id="pm-rt-2",
        message="/power سجل عميل احمد",
        proposer="فرج1",
    ))
    d = result["drafts"][0]
    intents = [a["intent"] for a in d["actions"]]
    assert "runtime" in intents, f"Expected runtime intent, got {intents}"


# ─── Stats ────────────────────────────────────────────────────────────────


def test_stats_snapshot_shape():
    action_runtime.create_draft(action="customer", payload={}, proposer="x")
    action_runtime.create_draft(action="vehicle", payload={}, proposer="x")
    s = action_runtime.stats()
    assert s["drafts"] == 2
    assert s["drafts_by_status"]["draft"] == 2
    assert "db_rows" in s
    assert "enforce_4eyes" in s


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
