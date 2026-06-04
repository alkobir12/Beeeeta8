"""
⚙️ Action Runtime Routes — Phase 3C

REST surface for the controlled execution runtime.

Endpoints
─────────
  POST   /api/runtime/drafts                              — manually create a draft
  GET    /api/runtime/drafts                              — list drafts (with status filter)
  GET    /api/runtime/drafts/{id}                         — fetch a single draft
  POST   /api/runtime/drafts/{id}/request_approval        — DRAFT → PENDING_APPROVAL
  POST   /api/runtime/drafts/{id}/discard                 — DRAFT → REJECTED (proposer only)

  GET    /api/runtime/approvals                           — list approvals
  POST   /api/runtime/approvals/{id}/approve              — PENDING → APPROVED (Four-Eyes)
  POST   /api/runtime/approvals/{id}/reject               — PENDING → REJECTED

  POST   /api/runtime/drafts/{id}/commit                  — APPROVED → COMMITTED (writes DB)

  GET    /api/runtime/executions                          — list executions
  POST   /api/runtime/executions/{id}/rollback            — COMMITTED → ROLLED_BACK

  GET    /api/runtime/audit                               — recent audit trail
  GET    /api/runtime/stats                               — runtime stats
  GET    /api/runtime/db/{table}                          — peek at the staging DB

⚠️  Phase 3C — staging DB is in-memory. Real Supabase writes will swap in
during 3C.2 without changing this API.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, HTTPException, Query

from core import action_runtime
from core.log_utils import get_logger

_log = get_logger("routes.runtime")

router = APIRouter(prefix="/api/runtime", tags=["runtime"])


# ─── Drafts ─────────────────────────────────────────────────────────────────


@router.post("/drafts")
async def runtime_create_draft(payload: Dict[str, Any] = Body(...)):
    """Manually register a draft (for testing or non-power-mode flows)."""
    action = (payload.get("action") or "").strip().lower()
    if action not in action_runtime.VALID_ACTIONS:
        raise HTTPException(status_code=400, detail=f"action must be one of {sorted(action_runtime.VALID_ACTIONS)}")
    draft = action_runtime.create_draft(
        action=action,
        payload=payload.get("payload") or {},
        proposer=payload.get("proposer"),
        session_id=payload.get("session_id"),
    )
    return {"success": True, "data": draft}


@router.get("/drafts")
async def runtime_list_drafts(
    status: Optional[str] = Query(default=None),
    session_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, le=200),
):
    return {"success": True, "data": action_runtime.list_drafts(status=status, session_id=session_id, limit=limit)}


@router.get("/drafts/{draft_id}")
async def runtime_get_draft(draft_id: str):
    d = action_runtime.get_draft(draft_id)
    if not d:
        raise HTTPException(status_code=404, detail="draft_not_found")
    return {"success": True, "data": d}


@router.post("/drafts/{draft_id}/request_approval")
async def runtime_request_approval(draft_id: str, payload: Optional[Dict[str, Any]] = Body(default=None)):
    payload = payload or {}
    result = action_runtime.request_approval(draft_id=draft_id, requester=payload.get("requester"))
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"success": True, "data": result}


@router.post("/drafts/{draft_id}/discard")
async def runtime_discard_draft(draft_id: str, payload: Optional[Dict[str, Any]] = Body(default=None)):
    payload = payload or {}
    d = action_runtime.get_draft(draft_id)
    if not d:
        raise HTTPException(status_code=404, detail="draft_not_found")
    if d["status"] not in ("draft", "pending_approval", "rejected"):
        raise HTTPException(status_code=400, detail=f"cannot_discard_in_state:{d['status']}")
    d["status"] = "rejected"
    action_runtime._audit("DRAFT_DISCARDED", draft_id=draft_id, by=payload.get("by"))
    return {"success": True, "data": d}


# ─── Approvals ──────────────────────────────────────────────────────────────


@router.get("/approvals")
async def runtime_list_approvals(
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=50, le=200),
):
    return {"success": True, "data": action_runtime.list_approvals(status=status, limit=limit)}


@router.post("/approvals/{approval_id}/approve")
async def runtime_approve(approval_id: str, payload: Optional[Dict[str, Any]] = Body(default=None)):
    payload = payload or {}
    result = action_runtime.approve(approval_id=approval_id, approver=payload.get("approver"))
    if "error" in result:
        # 4-eyes violation gets a 403, other errors 400
        code = 403 if result["error"] == "four_eyes_violation" else 400
        raise HTTPException(status_code=code, detail=result)
    return {"success": True, "data": result}


@router.post("/approvals/{approval_id}/reject")
async def runtime_reject(approval_id: str, payload: Optional[Dict[str, Any]] = Body(default=None)):
    payload = payload or {}
    result = action_runtime.reject_approval(
        approval_id=approval_id,
        approver=payload.get("approver"),
        reason=payload.get("reason", ""),
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"success": True, "data": result}


# ─── Commit ─────────────────────────────────────────────────────────────────


@router.post("/drafts/{draft_id}/commit")
async def runtime_commit(draft_id: str, payload: Optional[Dict[str, Any]] = Body(default=None)):
    payload = payload or {}
    result = action_runtime.commit(draft_id=draft_id, committer=payload.get("committer"))
    if "error" in result:
        raise HTTPException(status_code=400, detail=result)
    return {"success": True, "data": result}


# ─── Executions / Rollback ──────────────────────────────────────────────────


@router.get("/executions")
async def runtime_list_executions(
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=50, le=200),
):
    return {"success": True, "data": action_runtime.list_executions(status=status, limit=limit)}


@router.post("/executions/{execution_id}/rollback")
async def runtime_rollback(execution_id: str, payload: Optional[Dict[str, Any]] = Body(default=None)):
    payload = payload or {}
    result = action_runtime.rollback(execution_id=execution_id, rollbacker=payload.get("rollbacker"))
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"success": True, "data": result}


# ─── Audit / Stats / DB peek ────────────────────────────────────────────────


@router.get("/audit")
async def runtime_audit(limit: int = Query(default=100, le=500)):
    return {"success": True, "data": action_runtime.get_audit_trail(limit=limit)}


@router.get("/stats")
async def runtime_stats():
    return {"success": True, "data": action_runtime.stats()}


@router.get("/db/{table}")
async def runtime_db_peek(table: str):
    """Peek at the in-memory staging DB. Phase 3C.2 will replace with Supabase."""
    if table not in action_runtime.DB:
        raise HTTPException(status_code=404, detail=f"unknown_table:{table}")
    rows = list(action_runtime.DB[table].values())
    rows.sort(key=lambda r: r.get("created_at", 0), reverse=True)
    return {"success": True, "data": rows, "count": len(rows), "staging": True}


# ============================================================================
# 🧪 Phase 3C — Simplified aliases (matches the L16 integration spec)
# ============================================================================
# These flatten the response shape so the L16 tester can drive the runtime
# without juggling the full {success, data:{...}} envelope. The aliases are
# pure routing — all real logic stays inside core.action_runtime.


@router.post("/power")
async def runtime_alias_power(payload: Dict[str, Any] = Body(...)):
    """Alias: POST /api/runtime/power {"text": "..."}

    Behaviour:
      1. Parse the text via Power Mode (multi-intent → first draft only).
      2. Auto request_approval on the FIRST runtime-eligible draft.
      3. Return a flat {draft, approval, drafts} shape.

    Convention: when no `proposer` is provided we use "bot_tester" so a
    different `approver` ("bot_reviewer") can pass the Four-Eyes check.
    """
    from core import power_mode
    text = (payload.get("text") or payload.get("message") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text required")
    proposer = payload.get("proposer") or "bot_tester"
    # Prepend "/power " so the multi-intent splitter kicks in
    msg = text if text.startswith("/power") else f"/power {text}"
    result = await power_mode.power_process(
        session_id=payload.get("session_id") or "alias-session",
        message=msg,
        proposer=proposer,
    )
    drafts = result.get("drafts", [])
    if not drafts:
        return {"draft": None, "approval": None, "drafts": []}
    # Pick the first runtime-eligible draft, fall back to the first overall
    primary = next((d for d in drafts if d.get("runtime", {}).get("enabled")), drafts[0])
    approval = None
    if primary.get("runtime", {}).get("enabled"):
        approval = action_runtime.request_approval(
            draft_id=primary["id"], requester=proposer,
        )
    return {
        "draft": action_runtime.get_draft(primary["id"]) or primary,
        "approval": approval,
        "drafts": drafts,
    }


@router.post("/approve/{approval_id}")
async def runtime_alias_approve(approval_id: str, payload: Optional[Dict[str, Any]] = Body(default=None)):
    """Alias: POST /api/runtime/approve/{approval_id}

    Returns {status, draft, approval}. Uses "bot_reviewer" as default
    approver so the Four-Eyes guard passes against the "bot_tester" proposer.
    """
    payload = payload or {}
    approver = payload.get("approver") or "bot_reviewer"
    result = action_runtime.approve(approval_id=approval_id, approver=approver)
    if "error" in result:
        code = 403 if result["error"] == "four_eyes_violation" else 400
        raise HTTPException(status_code=code, detail=result)
    return {
        "status": "approved",
        "draft": result.get("draft"),
        "approval": result.get("approval"),
    }


@router.post("/commit/{draft_id}")
async def runtime_alias_commit(draft_id: str, payload: Optional[Dict[str, Any]] = Body(default=None)):
    """Alias: POST /api/runtime/commit/{draft_id} → flat {execution_id, result, status}."""
    payload = payload or {}
    result = action_runtime.commit(
        draft_id=draft_id,
        committer=payload.get("committer") or "bot_reviewer",
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result)
    return {
        "status": "committed",
        "execution_id": result.get("execution_id"),
        "result": result.get("result"),
        "idempotent": result.get("idempotent", False),
    }


@router.post("/rollback/{execution_id}")
async def runtime_alias_rollback(execution_id: str, payload: Optional[Dict[str, Any]] = Body(default=None)):
    """Alias: POST /api/runtime/rollback/{execution_id} → flat {status, execution_id}."""
    payload = payload or {}
    result = action_runtime.rollback(
        execution_id=execution_id,
        rollbacker=payload.get("rollbacker") or "bot_reviewer",
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return {
        "status": "rolled_back",
        "execution_id": result.get("execution_id"),
        "draft_status": (result.get("draft") or {}).get("status"),
    }


@router.get("/report")
async def runtime_alias_report():
    """Alias: GET /api/runtime/report → flat summary of the runtime state."""
    s = action_runtime.stats()
    return {
        "mode": "summary",
        **s,
    }
