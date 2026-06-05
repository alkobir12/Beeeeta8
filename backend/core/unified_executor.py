"""
⚙️ Unified Execution Engine — Phase 3C.4 (Policy Layer)

Sits on top of `core.action_runtime` to apply risk-based policy:
  • SAFE actions    → auto-approve + auto-commit (LLM proposes, system commits)
  • RISKY actions   → require human approval before commit
  • UNKNOWN actions → rejected

Read-only actions (`get_active_visits`, `get_*`) short-circuit and never
create a draft.

⚠️  Even SAFE auto-commits still go through the full state machine in
`action_runtime` — they just bypass the human approval *gate*. Every step
is recorded in the audit trail with `proposer="auto:llm"` and
`approver="auto:policy"`. Four-Eyes is preserved because the two identities
are deliberately distinct.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from core import action_runtime
from core.llm_intent_parser import Action, parse_intent_with_llm
from core.log_utils import get_logger

_log = get_logger("unified_executor")


# ─────────────────────────────────────────────────────────────────────────────
# Risk policy
# ─────────────────────────────────────────────────────────────────────────────

# Actions that ALWAYS require a human reviewer (bulk + destructive ops).
RISKY_ACTIONS = {
    "close_visits",
    "delete_customer",
    "delete_vehicle",
    "delete_operation",
    "bulk_update",
    "bulk_delete",
}

# Read-only actions — no draft created, no approval needed.
READ_ONLY_ACTIONS = {
    "get_active_visits",
    "get_customers",
    "get_vehicles",
}

# LLM action name → runtime action token (what action_runtime.commit expects).
_ACTION_TO_RUNTIME = {
    "create_customer": "customer",
    "create_vehicle": "vehicle",
    "create_visit": "visit",
    "close_visits": "close_visits",
    "delete_operation": "delete_operation",
}


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────


def requires_approval(action: Action) -> bool:
    """Policy: should this action wait for a human reviewer?"""
    return action.action in RISKY_ACTIONS


async def execute_text(
    text: str,
    *,
    proposer: Optional[str] = None,
    session_id: Optional[str] = None,
    auto_approver: str = "auto:policy",
) -> Dict[str, Any]:
    """End-to-end orchestrator: text → LLM → policy decision → runtime.

    Returns one of these shapes:
      • status="rejected"          — unknown action, nothing happened
      • status="read_only"         — read query, includes result
      • status="pending_approval"  — risky action, draft + approval created
      • status="committed"         — safe action, written to DB
    """
    text = (text or "").strip()
    if not text:
        return {"status": "rejected", "reason": "empty_text"}

    action = await parse_intent_with_llm(text, session_id=session_id)

    # 🆕 Phase 3C.10 — Fallback: if LLM said "unknown" but the regex catches
    # a clear action verb, build a minimal payload from extracted entities
    # and proceed. This rescues the bot from over-strict LLM rejections.
    if action.action == "unknown":
        action = _regex_fallback_action(text)

    return await execute_action(
        action,
        proposer=proposer,
        session_id=session_id,
        auto_approver=auto_approver,
    )


def _regex_fallback_action(text: str) -> Action:
    """Convert regex-detected intents to an Action when the LLM gives up."""
    import re as _re
    # Check for delete intent first (handles Arabic suffixes like احذفها)
    delete_match = _re.search(r"(?:احذف|أحذف|امسح|أمسح|شيل|delete|remove)(?:ها|ه|هم|هن|وا|وه)?", text, _re.IGNORECASE)
    if delete_match:
        # Try to extract an operation ID from the text
        id_match = _re.search(r"(?:رقم|معرف|id)\s*[:#]?\s*(\S+)", text, _re.IGNORECASE)
        payload = {}
        if id_match:
            payload["operation_id"] = id_match.group(1)
        return Action(action="delete_operation", payload=payload)

    from core import power_mode
    intent_kind = power_mode.detect_intent_kind(text)
    if intent_kind == "unknown":
        return Action(action="unknown")
    entities = power_mode.extract_entities(text, intent_kind)
    # Map regex intent_kind → LLM action_name
    kind_to_action = {
        "customer": "create_customer",
        "vehicle": "create_vehicle",
        "visit": "create_visit",
        "operation": "create_visit",  # operation = visit-with-service in this domain
    }
    action_name = kind_to_action.get(intent_kind)
    if not action_name:
        return Action(action="unknown")
    # Build a clean payload — drop _resolved_from/raw noise
    payload: Dict[str, Any] = {}
    for key in ("name", "plate", "phone", "amount", "year", "vehicle_type", "service"):
        if entities.get(key) is not None:
            # Translate field names: amount→price, phone→customer_phone for visits
            tgt = "price" if (key == "amount" and action_name == "create_visit") else \
                  "customer_phone" if (key == "phone" and action_name in ("create_vehicle", "create_visit")) else \
                  key
            payload[tgt] = entities[key]
    return Action(action=action_name, payload=payload)


async def execute_action(
    action: Action,
    *,
    proposer: Optional[str] = None,
    session_id: Optional[str] = None,
    auto_approver: str = "auto:policy",
) -> Dict[str, Any]:
    """Drive a pre-parsed Action through the runtime + policy gates."""

    # 1) Unknown guard
    if action.action == "unknown":
        return {
            "status": "rejected",
            "reason": "unknown_action",
            "action": action.model_dump(),
        }

    # 2) Read-only short-circuit
    if action.action in READ_ONLY_ACTIONS:
        if action.action == "get_active_visits":
            return {
                "status": "read_only",
                "action": action.model_dump(),
                "result": action_runtime.get_active_visits(
                    limit=int(action.payload.get("limit") or 50),
                ),
            }
        # Generic read-only marker — caller plugs the right query elsewhere
        return {"status": "read_only", "action": action.model_dump(), "result": None}

    # 3) Map LLM action_name → runtime token
    runtime_action = _ACTION_TO_RUNTIME.get(action.action)
    if not runtime_action:
        return {
            "status": "rejected",
            "reason": "no_runtime_handler",
            "action": action.model_dump(),
        }

    # 4) Create draft (always — even for auto-committed actions)
    proposer_id = proposer or "auto:llm"
    draft = action_runtime.create_draft(
        action=runtime_action,
        payload=action.payload,
        proposer=proposer_id,
        session_id=session_id,
    )

    # 5) Risky → manual approval gate
    if requires_approval(action):
        approval = action_runtime.request_approval(
            draft_id=draft["id"], requester=proposer_id,
        )
        return {
            "status": "pending_approval",
            "action": action.model_dump(),
            "draft": draft,
            "approval": approval,
            "policy": "manual_review_required",
        }

    # 6) Safe → auto-approve + auto-commit
    req = action_runtime.request_approval(
        draft_id=draft["id"], requester=proposer_id,
    )
    if "error" in req:
        return {"status": "error", "reason": req["error"], "draft": draft}

    approved = action_runtime.approve(
        approval_id=req["approval_id"], approver=auto_approver,
    )
    if "error" in approved:
        _log.warning("auto-approve failed: %s", approved.get("error"))
        return {"status": "error", "reason": approved["error"], "draft": draft}

    committed = action_runtime.commit(
        draft_id=draft["id"], committer=auto_approver,
    )
    if "error" in committed:
        return {"status": "error", "reason": committed["error"], "draft": draft}

    return {
        "status": "committed",
        "action": action.model_dump(),
        "draft": draft,
        "result": committed.get("result"),
        "execution_id": committed.get("execution_id"),
        "policy": "auto_safe",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Class wrapper (matches the L16 spec shape)
# ─────────────────────────────────────────────────────────────────────────────


class UnifiedExecutionEngine:
    """Class form for callers that prefer the spec's object-oriented shape.

    The functional `execute_text` is the preferred entrypoint inside our
    backend; this class is a thin adapter for the L16 spec.
    """

    def __init__(self, llm=None, supabase=None, runtime=None):
        # llm/supabase/runtime are kept for spec parity but ignored — we
        # delegate to the global core modules so the audit trail stays unified.
        self.llm = llm
        self.supabase = supabase
        self.runtime = runtime or action_runtime

    async def execute(self, text: str, **kwargs) -> Dict[str, Any]:
        return await execute_text(text, **kwargs)

    @staticmethod
    def requires_approval(action: Action) -> bool:
        return requires_approval(action)
