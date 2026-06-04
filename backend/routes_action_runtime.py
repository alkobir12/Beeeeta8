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
