from __future__ import annotations

import os
import json

import pytest

from core.environment_guard import configure_database_environment


def test_test_environment_fails_closed_without_test_credentials(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("SUPABASE_URL", "https://production-ref.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "production-secret")
    monkeypatch.delenv("SUPABASE_TEST_URL", raising=False)
    monkeypatch.delenv("SUPABASE_URL_TEST", raising=False)
    monkeypatch.delenv("SUPABASE_TEST_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY_TEST", raising=False)

    with pytest.raises(RuntimeError, match="test_database_credentials_missing"):
        configure_database_environment()


def test_test_environment_rejects_production_project(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("SUPABASE_URL", "https://same-ref.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "production-secret")
    monkeypatch.setenv("SUPABASE_TEST_URL", "https://same-ref.supabase.co")
    monkeypatch.setenv("SUPABASE_TEST_SERVICE_ROLE_KEY", "test-secret")

    with pytest.raises(RuntimeError, match="test_database_matches_production"):
        configure_database_environment()


def test_test_environment_selects_distinct_project(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("SUPABASE_URL", "https://production-ref.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "production-secret")
    monkeypatch.setenv("SUPABASE_TEST_URL", "https://test-ref.supabase.co")
    monkeypatch.setenv("SUPABASE_TEST_SERVICE_ROLE_KEY", "test-secret")

    assert configure_database_environment() == "test"
    assert os.environ["SUPABASE_URL"] == "https://test-ref.supabase.co"
    assert os.environ["SUPABASE_SERVICE_ROLE_KEY"] == "test-secret"


def test_automated_approver_is_rejected(monkeypatch):
    from core import action_runtime

    monkeypatch.setattr("core.runtime_store.append_audit", lambda row: None)
    monkeypatch.setattr("core.runtime_store.save_draft", lambda state, draft_id: None)
    monkeypatch.setattr("core.runtime_store.save_approval", lambda state, approval_id: None)
    action_runtime.STATE["drafts"].clear()
    action_runtime.STATE["approvals"].clear()
    action_runtime.STATE["executions"].clear()

    draft = action_runtime.create_draft(
        action="visit", payload={"plate": "د ح د 8719"}, proposer="مدير"
    )
    approval = action_runtime.request_approval(draft_id=draft["id"], requester="مدير")
    result = action_runtime.approve(
        approval_id=approval["approval_id"], approver="auto:policy"
    )

    assert result["error"] == "human_approver_required"
    assert action_runtime.get_draft(draft["id"])["status"] == "pending_approval"


@pytest.mark.asyncio
async def test_every_write_action_waits_for_human_approval(monkeypatch):
    from core import action_runtime
    from core.llm_intent_parser import Action
    from core.unified_executor import execute_action

    monkeypatch.setattr("core.runtime_store.append_audit", lambda row: None)
    monkeypatch.setattr("core.runtime_store.save_draft", lambda state, draft_id: None)
    monkeypatch.setattr("core.runtime_store.save_approval", lambda state, approval_id: None)
    action_runtime.STATE["drafts"].clear()
    action_runtime.STATE["approvals"].clear()
    action_runtime.STATE["executions"].clear()

    result = await execute_action(
        Action(action="create_customer", payload={"name": "عميل تجريبي"}),
        proposer="موظف",
        session_id="governance-test",
    )

    assert result["status"] == "pending_approval"
    assert result["policy"] == "manual_review_required"
    assert result["draft"]["status"] == "pending_approval"


def test_external_approval_response_creates_only_pending_draft(monkeypatch):
    from core import action_runtime
    from routes_extended import _external_approval_response

    monkeypatch.setattr("core.runtime_store.append_audit", lambda row: None)
    monkeypatch.setattr("core.runtime_store.save_draft", lambda state, draft_id: None)
    monkeypatch.setattr("core.runtime_store.save_approval", lambda state, approval_id: None)
    action_runtime.STATE["drafts"].clear()
    action_runtime.STATE["approvals"].clear()
    action_runtime.STATE["executions"].clear()

    response = _external_approval_response(
        action="external_operation",
        payload={"type": "sale", "notes": "[SOURCE:SMART_POS]"},
        proposer="موظف",
    )
    body = json.loads(response.body)
    draft = action_runtime.get_draft(body["draft_id"])

    assert response.status_code == 202
    assert body["status"] == "pending_approval"
    assert draft["status"] == "pending_approval"
    assert action_runtime.STATE["executions"] == {}


def test_external_approved_marker_requires_real_human_approval(monkeypatch):
    from core import action_runtime
    from fastapi import HTTPException
    from routes_extended import _external_draft_is_approved

    monkeypatch.setattr("core.runtime_store.append_audit", lambda row: None)
    monkeypatch.setattr("core.runtime_store.save_draft", lambda state, draft_id: None)
    monkeypatch.setattr("core.runtime_store.save_approval", lambda state, approval_id: None)
    action_runtime.STATE["drafts"].clear()
    action_runtime.STATE["approvals"].clear()
    action_runtime.STATE["executions"].clear()

    draft = action_runtime.create_draft(
        action="external_operation_payment", payload={"amount": 100}, proposer="موظف"
    )
    action_runtime.request_approval(draft_id=draft["id"], requester="موظف")

    with pytest.raises(HTTPException) as exc:
        _external_draft_is_approved({"_approved_external_draft": draft["id"]})
    assert exc.value.status_code == 403