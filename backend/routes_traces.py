"""🔬 /api/traces — استعلام سجلات llm_traces (admin/supervisor فقط)."""

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from core import llm_traces
from core.rbac import APPROVER_ROLES, extract_identity

router = APIRouter(prefix="/api/traces", tags=["traces"])


def _require_approver(request: Request) -> Dict[str, Any]:
    ident = extract_identity(request, None)
    role = (ident.get("role_hint") or "").strip().lower()
    if role not in APPROVER_ROLES:
        raise HTTPException(status_code=403, detail="traces: approver role required")
    return ident


@router.get("/stats")
async def traces_stats(request: Request):
    _require_approver(request)
    return {"success": True, "data": llm_traces.stats()}


@router.get("/{trace_id}")
async def get_trace(trace_id: str, request: Request):
    _require_approver(request)
    doc = llm_traces.get_trace(trace_id)
    if not doc:
        raise HTTPException(status_code=404, detail="trace not found")
    return {"success": True, "data": doc}


@router.get("")
async def list_traces(
    request: Request,
    session_id: Optional[str] = Query(default=None),
    limit: int = Query(default=20, le=200),
    full: bool = Query(default=False),
):
    _require_approver(request)
    rows = llm_traces.list_traces(session_id=session_id, limit=limit, full=full)
    return {"success": True, "data": rows, "count": len(rows)}
