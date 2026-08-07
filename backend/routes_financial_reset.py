from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from core import rbac
from core.financial_reset_engine import (
    CONFIRMATION_TEXT,
    build_dry_run,
    execute_reset,
    list_reset_audit,
)

router = APIRouter(prefix="/api/finance/reset", tags=["financial-reset"])


class ExecuteResetPayload(BaseModel):
    confirmation_text: str
    dry_run_token: str
    workshop_id: Optional[str] = "finmodule-sync"


async def _require_admin_actor(request: Request):
    ident = rbac.extract_identity(request)
    if not ident.get("user_id"):
        raise HTTPException(status_code=401, detail="Not authenticated")
    actor = await rbac.resolve_actor(user_id=ident["user_id"], name=ident["name"], role_hint=ident["role_hint"])
    if actor.role != "admin":
        raise HTTPException(status_code=403, detail={"error": "admin_only", "msg": "بدء مالي جديد متاح للمدير فقط", "role": actor.role})
    if not actor.active:
        raise HTTPException(status_code=403, detail={"error": "inactive_user", "msg": "المستخدم غير نشط"})
    return actor


@router.get("/dry-run")
async def financial_reset_dry_run(request: Request, workshop_id: str = Query("finmodule-sync")):
    actor = await _require_admin_actor(request)
    try:
        result = build_dry_run(workshop_id=workshop_id, actor=actor.to_dict())
        return {"success": True, "data": result}
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": "dry_run_failed", "msg": str(exc)})


@router.post("/execute")
async def financial_reset_execute(payload: ExecuteResetPayload, request: Request):
    actor = await _require_admin_actor(request)
    try:
        result = execute_reset(
            workshop_id=payload.workshop_id or "finmodule-sync",
            confirmation_text=payload.confirmation_text,
            dry_run_token=payload.dry_run_token,
            actor=actor.to_dict(),
        )
        return {"success": True, "data": result}
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"error": "reset_blocked", "msg": str(exc), "confirmation_text": CONFIRMATION_TEXT})
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": "reset_failed", "msg": str(exc)})


@router.get("/audit")
async def financial_reset_audit(request: Request, limit: int = Query(50, ge=1, le=200)):
    actor = await _require_admin_actor(request)
    return {"success": True, "actor": actor.to_dict(), "data": list_reset_audit(limit=limit)}