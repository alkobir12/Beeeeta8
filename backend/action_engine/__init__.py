"""
🎬 Action Engine — Beeeeta8 Controlled Operator Runtime

This package transforms the Assistant from read-only into a controlled
ERP operator. Every action goes through a strict lifecycle:

  Requested → Drafted → Reviewed → ApprovalPending →
  Approved → ExecutionLocked → Executed → Verified → Audited → Archived

Failure paths: Failed, Cancelled, Compensated.

Public surface:
  • ActionEnvelope — the request DTO
  • action_registry — register/get/list actions
  • lifecycle.transition() — only allowed state changes
  • confirmation.is_strong() — distinguish "yes execute" from "ok / 👍"
  • audit.record() — append-only audit log
  • runtime.handle() — orchestration entry point
"""
from .envelope import ActionEnvelope, ActionStatus, RiskClass
from .registry import action_registry, ActionDefinition, register_action
from .lifecycle import transition, ALLOWED_TRANSITIONS
from .confirmation import is_strong_confirmation
from .audit import record_action_audit

__all__ = [
    "ActionEnvelope",
    "ActionStatus",
    "RiskClass",
    "action_registry",
    "ActionDefinition",
    "register_action",
    "transition",
    "ALLOWED_TRANSITIONS",
    "is_strong_confirmation",
    "record_action_audit",
]
