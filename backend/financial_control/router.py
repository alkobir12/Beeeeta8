"""
🌐 Financial Control Router — REST API.

Endpoints (all under /api/financial-control):

Approvals:
  POST   /approvals                       — submit a new approval request
  GET    /approvals                       — list with filters
  GET    /approvals/stats                 — counts by status + pending
  GET    /approvals/{id}                  — fetch single
  POST   /approvals/{id}/review           — reviewer step
  POST   /approvals/{id}/approve          — approver step
  POST   /approvals/{id}/reject           — reject
  POST   /approvals/{id}/cancel           — cancel
  GET    /approvals/matrix                — view configured matrix

Findings:
  POST   /findings/scan                   — run all audit rules + persist findings
  GET    /findings                        — list findings
  GET    /findings/summary                — aggregate KPIs
  GET    /findings/{id}                   — single finding
  POST   /findings/{id}/acknowledge
  POST   /findings/{id}/start
  POST   /findings/{id}/resolve
  POST   /findings/{id}/dismiss
  POST   /findings/{id}/assign
  POST   /findings/{id}/comment
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Query

from .approval_engine import ApprovalEngine
from .audit_rules import AuditRulesEngine
from .findings_engine import FindingsEngine
from .four_eyes import FourEyesValidator, FourEyesViolation
from .models import ApprovalStatus, DEFAULT_MATRIX, FindingSeverity, FindingStatus

router = APIRouter(prefix="/api/financial-control", tags=["financial-control"])

# Injected by server.py
_db = None
_supa = None


def set_db(database, supabase=None):
    global _db, _supa
    _db = database
    _supa = supabase


def _approval() -> ApprovalEngine:
    if _db is None:
        raise HTTPException(status_code=500, detail="financial_control: db not initialised")
    return ApprovalEngine(_db)


def _findings() -> FindingsEngine:
    if _db is None:
        raise HTTPException(status_code=500, detail="financial_control: db not initialised")
    return FindingsEngine(_db)


# ============== Approvals ==============

@router.post("/approvals")
async def create_approval(payload: Dict[str, Any] = Body(...)):
    creator = (payload.get("creator") or "").strip()
    if not creator:
        raise HTTPException(status_code=400, detail="creator is required")
    try:
        FourEyesValidator.check(creator=creator)
    except FourEyesViolation as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    eng = _approval()
    req = await eng.submit(
        entity_type=payload.get("entity_type") or "operation",
        amount=float(payload.get("amount") or 0),
        creator=creator,
        creator_role=payload.get("creator_role"),
        title=payload.get("title") or f"موافقة على {payload.get('entity_type') or 'عملية'}",
        entity_id=payload.get("entity_id"),
        entity_payload=payload.get("entity_payload"),
        description=payload.get("description"),
        workshop_id=payload.get("workshop_id") or "finmodule-sync",
        idempotency_key=payload.get("idempotency_key"),
    )
    return {"success": True, "data": req.dict()}


@router.get("/approvals")
async def list_approvals(
    workshop_id: str = Query("finmodule-sync"),
    status: Optional[str] = Query(None),
    creator: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    eng = _approval()
    status_enum = ApprovalStatus(status) if status else None
    items = await eng.list(
        workshop_id=workshop_id, status=status_enum, creator=creator,
        entity_type=entity_type, limit=limit,
    )
    return {"success": True, "data": [i.dict() for i in items]}


@router.get("/approvals/stats")
async def approval_stats(workshop_id: str = Query("finmodule-sync")):
    return {"success": True, "data": await _approval().stats(workshop_id=workshop_id)}


@router.get("/approvals/matrix")
async def get_matrix():
    return {"success": True, "data": [t.dict() for t in DEFAULT_MATRIX]}


@router.get("/approvals/{request_id}")
async def get_approval(request_id: str):
    item = await _approval().get(request_id)
    if not item:
        raise HTTPException(status_code=404, detail="approval not found")
    return {"success": True, "data": item.dict()}


@router.post("/approvals/{request_id}/review")
async def review_approval(request_id: str, payload: Dict[str, Any] = Body(...)):
    reviewer = (payload.get("reviewer") or "").strip()
    if not reviewer:
        raise HTTPException(status_code=400, detail="reviewer is required")
    try:
        req = await _approval().review(
            request_id, reviewer=reviewer,
            reviewer_role=payload.get("reviewer_role"),
            note=payload.get("note"),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"success": True, "data": req.dict()}


@router.post("/approvals/{request_id}/approve")
async def approve_approval(request_id: str, payload: Dict[str, Any] = Body(...)):
    approver = (payload.get("approver") or "").strip()
    if not approver:
        raise HTTPException(status_code=400, detail="approver is required")
    try:
        req = await _approval().approve(
            request_id, approver=approver,
            approver_role=payload.get("approver_role"),
            note=payload.get("note"),
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"success": True, "data": req.dict()}


@router.post("/approvals/{request_id}/reject")
async def reject_approval(request_id: str, payload: Dict[str, Any] = Body(...)):
    actor = (payload.get("actor") or "").strip()
    if not actor:
        raise HTTPException(status_code=400, detail="actor is required")
    try:
        req = await _approval().reject(
            request_id, actor=actor,
            actor_role=payload.get("actor_role"),
            note=payload.get("note"),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"success": True, "data": req.dict()}


@router.post("/approvals/{request_id}/cancel")
async def cancel_approval(request_id: str, payload: Dict[str, Any] = Body(...)):
    actor = (payload.get("actor") or "").strip()
    if not actor:
        raise HTTPException(status_code=400, detail="actor is required")
    try:
        req = await _approval().cancel(request_id, actor=actor, note=payload.get("note"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"success": True, "data": req.dict()}


# ============== Findings ==============

@router.post("/findings/scan")
async def scan_findings(payload: Dict[str, Any] = Body(default={})):
    """Run all 7 audit rules and upsert findings.

    Pulls data from Supabase (preferred) for: journals, operations, parts, invoices.
    Returns scan summary (created/updated counts).
    """
    workshop_id = payload.get("workshop_id") or "finmodule-sync"
    ctx = await _build_audit_context(workshop_id=workshop_id)
    rules = AuditRulesEngine(workshop_id=workshop_id)
    findings = rules.run_all(ctx)
    result = await _findings().bulk_upsert(findings)
    return {
        "success": True,
        "data": {
            "scan": result,
            "context_sizes": {k: len(v) for k, v in ctx.items()},
        },
    }


async def _build_audit_context(*, workshop_id: str) -> Dict[str, List[Dict[str, Any]]]:
    """Load raw data from Supabase if available, else from MongoDB."""
    ctx: Dict[str, List[Dict[str, Any]]] = {
        "journals": [],
        "operations": [],
        "parts": [],
        "invoices": [],
    }
    import os
    if (os.environ.get("DB_PROVIDER") or "mongo").lower() == "supabase":
        try:
            from supabase_service import SupabaseService
            sup = SupabaseService()
            try:
                res = sup.client.table("journal_entries").select("*").eq("workshop_id", workshop_id).order("created_at", desc=True).limit(2000).execute()
                ctx["journals"] = res.data or []
            except Exception:
                pass
            try:
                res = sup.client.table("operations").select("*").order("created_at", desc=True).limit(2000).execute()
                ctx["operations"] = res.data or []
            except Exception:
                pass
            try:
                res = sup.client.table("parts").select("*").limit(2000).execute()
                ctx["parts"] = res.data or []
            except Exception:
                pass
            try:
                res = sup.client.table("invoices").select("*").order("created_at", desc=True).limit(2000).execute()
                ctx["invoices"] = res.data or []
            except Exception:
                pass
            return ctx
        except Exception:
            pass
    # MongoDB fallback
    if _db is not None:
        try:
            ctx["journals"] = await _db.journal_entries.find({}, {"_id": 0}).to_list(2000)
        except Exception:
            pass
        try:
            ctx["operations"] = await _db.operations.find({}, {"_id": 0}).to_list(2000)
        except Exception:
            pass
        try:
            ctx["parts"] = await _db.parts.find({}, {"_id": 0}).to_list(2000)
        except Exception:
            pass
        try:
            ctx["invoices"] = await _db.invoices.find({}, {"_id": 0}).to_list(2000)
        except Exception:
            pass
    return ctx


@router.get("/findings")
async def list_findings(
    workshop_id: str = Query("finmodule-sync"),
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    rule_code: Optional[str] = Query(None),
    assignee: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
):
    status_enum = FindingStatus(status) if status else None
    severity_enum = FindingSeverity(severity) if severity else None
    items = await _findings().list(
        workshop_id=workshop_id, status=status_enum, severity=severity_enum,
        rule_code=rule_code, assignee=assignee, limit=limit,
    )
    return {"success": True, "data": [i.dict() for i in items]}


@router.get("/findings/summary")
async def findings_summary(workshop_id: str = Query("finmodule-sync")):
    return {"success": True, "data": await _findings().summary(workshop_id=workshop_id)}


@router.get("/findings/{finding_id}")
async def get_finding(finding_id: str):
    item = await _findings().get(finding_id)
    if not item:
        raise HTTPException(status_code=404, detail="finding not found")
    return {"success": True, "data": item.dict()}


@router.post("/findings/{finding_id}/acknowledge")
async def acknowledge_finding(finding_id: str, payload: Dict[str, Any] = Body(...)):
    actor = (payload.get("actor") or "").strip()
    if not actor:
        raise HTTPException(status_code=400, detail="actor is required")
    try:
        f = await _findings().acknowledge(finding_id, actor=actor, note=payload.get("note"))
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"success": True, "data": f.dict()}


@router.post("/findings/{finding_id}/start")
async def start_finding(finding_id: str, payload: Dict[str, Any] = Body(...)):
    actor = (payload.get("actor") or "").strip()
    if not actor:
        raise HTTPException(status_code=400, detail="actor is required")
    try:
        f = await _findings().start(finding_id, actor=actor, note=payload.get("note"))
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"success": True, "data": f.dict()}


@router.post("/findings/{finding_id}/resolve")
async def resolve_finding(finding_id: str, payload: Dict[str, Any] = Body(...)):
    actor = (payload.get("actor") or "").strip()
    resolution = (payload.get("resolution") or "").strip()
    if not actor or not resolution:
        raise HTTPException(status_code=400, detail="actor and resolution are required")
    try:
        f = await _findings().resolve(finding_id, actor=actor, resolution=resolution)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"success": True, "data": f.dict()}


@router.post("/findings/{finding_id}/dismiss")
async def dismiss_finding(finding_id: str, payload: Dict[str, Any] = Body(...)):
    actor = (payload.get("actor") or "").strip()
    reason = (payload.get("reason") or "").strip()
    if not actor or not reason:
        raise HTTPException(status_code=400, detail="actor and reason are required")
    try:
        f = await _findings().dismiss(finding_id, actor=actor, reason=reason)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"success": True, "data": f.dict()}


@router.post("/findings/{finding_id}/assign")
async def assign_finding(finding_id: str, payload: Dict[str, Any] = Body(...)):
    assignee = (payload.get("assignee") or "").strip()
    if not assignee:
        raise HTTPException(status_code=400, detail="assignee is required")
    try:
        f = await _findings().assign(finding_id, assignee=assignee, due_date=payload.get("due_date"))
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"success": True, "data": f.dict()}


@router.post("/findings/{finding_id}/comment")
async def comment_finding(finding_id: str, payload: Dict[str, Any] = Body(...)):
    author = (payload.get("author") or "").strip()
    text = (payload.get("text") or "").strip()
    if not author or not text:
        raise HTTPException(status_code=400, detail="author and text are required")
    try:
        f = await _findings().comment(finding_id, author=author, text=text)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"success": True, "data": f.dict()}
