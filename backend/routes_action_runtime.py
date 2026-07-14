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

from fastapi import APIRouter, Body, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from core import action_runtime, rbac
from core.log_utils import get_logger

_log = get_logger("routes.runtime")

router = APIRouter(prefix="/api/runtime", tags=["runtime"])


async def _require_approver(request: Request) -> "rbac.Actor":
    """🔐 SEC-002: القراءات المالية على مستوى المنظمة (drafts/approvals/executions/
    audit/db/stats) والإنشاء اليدوي للمسودات تكشف بيانات كل العملاء — لذا تتطلب دوراً
    معتمِداً (admin/manager/supervisor). بلا توكن ⇒ 401، دور غير مخوّل ⇒ 403.
    تذكير الشات يستخدم استدعاءات in-process فلا يتأثر بهذا التقييد."""
    ident = rbac.extract_identity(request)
    if not ident.get("user_id"):
        raise HTTPException(status_code=401, detail="Not authenticated")
    actor = await rbac.resolve_actor(
        user_id=ident["user_id"], name=ident["name"], role_hint=ident["role_hint"]
    )
    rbac.require(rbac.can_approve(actor))
    return actor


# ─── Drafts ─────────────────────────────────────────────────────────────────


@router.post("/drafts")
async def runtime_create_draft(request: Request, payload: Dict[str, Any] = Body(...)):
    """Manually register a draft (for testing or non-power-mode flows)."""
    await _require_approver(request)
    action = (payload.get("action") or "").strip().lower()
    if action not in action_runtime.VALID_ACTIONS:
        raise HTTPException(status_code=400, detail=f"action must be one of {sorted(action_runtime.VALID_ACTIONS)}")
    draft = action_runtime.create_draft(
        action=action,
        payload=payload.get("payload") or {},
        proposer=payload.get("proposer"),
        session_id=payload.get("session_id"),
        trace_id=payload.get("trace_id"),
    )
    return {"success": True, "data": draft}


@router.get("/drafts")
async def runtime_list_drafts(
    request: Request,
    status: Optional[str] = Query(default=None),
    session_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, le=200),
):
    await _require_approver(request)
    return {"success": True, "data": action_runtime.list_drafts(status=status, session_id=session_id, limit=limit)}


@router.get("/drafts/{draft_id}")
async def runtime_get_draft(draft_id: str, request: Request):
    await _require_approver(request)
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
async def runtime_discard_draft(draft_id: str, request: Request, payload: Optional[Dict[str, Any]] = Body(default=None)):
    payload = payload or {}
    d = action_runtime.get_draft(draft_id)
    if not d:
        raise HTTPException(status_code=404, detail="draft_not_found")
    if d["status"] not in ("draft", "pending_approval", "rejected"):
        raise HTTPException(status_code=400, detail=f"cannot_discard_in_state:{d['status']}")
    # RBAC: المُنشئ نفسه يمكنه التجاهل، أو من يملك صلاحية الاعتماد
    ident = rbac.extract_identity(request, payload)
    actor = await rbac.resolve_actor(user_id=ident["user_id"], name=ident["name"], role_hint=ident["role_hint"])
    actor_ident = actor.name or actor.id or ""
    if actor_ident != d.get("proposer"):
        rbac.require(rbac.can_approve(actor))
    d["status"] = "rejected"
    action_runtime._audit("DRAFT_DISCARDED", draft_id=draft_id, by=actor_ident or payload.get("by"))
    return {"success": True, "data": d}


# ─── 🛠️ Phase 2 — Draft patching (inline edits from the chat card) ────────

@router.post("/drafts/{draft_id}/patch")
async def runtime_patch_draft(draft_id: str, request: Request, payload: Dict[str, Any] = Body(...)):
    """يُطبّق قائمة عمليات تعديل صغيرة على مسودة معلّقة (شراء) قبل الاعتماد.

    الجسم: `{"ops": [{"op":"set_payment_method","value":"cash"}, ...]}`
    القيود: المسودة يجب أن تكون في `draft` أو `pending_approval` — ولا يُقبل تعديل بعد الالتزام.
    الأذونات: المُقترِح نفسه، أو من يملك صلاحية الاعتماد.
    """
    d = action_runtime.get_draft(draft_id)
    if not d:
        raise HTTPException(status_code=404, detail="draft_not_found")
    ident = rbac.extract_identity(request, payload)
    actor = await rbac.resolve_actor(user_id=ident["user_id"], name=ident["name"], role_hint=ident["role_hint"])
    actor_ident = actor.name or actor.id or ""
    if actor_ident != d.get("proposer"):
        rbac.require(rbac.can_approve(actor))
    ops = payload.get("ops") or []
    if not isinstance(ops, list) or not ops:
        raise HTTPException(status_code=400, detail="ops must be a non-empty list")
    result = action_runtime.patch_draft(draft_id=draft_id, ops=ops, actor=actor_ident)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result)
    return {"success": True, "data": result}


@router.post("/drafts/{draft_id}/spawn_supplier")
async def runtime_spawn_supplier(draft_id: str, request: Request, payload: Optional[Dict[str, Any]] = Body(default=None)):
    """🆕 ينشئ سجل مورّد فوراً من مسودة شراء معلّقة، ثم يُلحق `supplier.id`
    بمسودة الشراء (يُبطل الوسم `is_new=true`).

    الأذونات: المُقترِح أو من يملك صلاحية الاعتماد. يُلتزم فوراً (auto-commit)
    باعتبار زر «➕ إضافة المورد» هو التأكيد الصريح للمستخدم.
    """
    payload = payload or {}
    d = action_runtime.get_draft(draft_id)
    if not d:
        raise HTTPException(status_code=404, detail="draft_not_found")
    if d.get("action") != "purchase":
        raise HTTPException(status_code=400, detail="not_a_purchase_draft")
    if d["status"] not in ("draft", "pending_approval"):
        raise HTTPException(status_code=400, detail=f"immutable_state:{d['status']}")

    ident = rbac.extract_identity(request, payload)
    actor = await rbac.resolve_actor(user_id=ident["user_id"], name=ident["name"], role_hint=ident["role_hint"])
    actor_ident = actor.name or actor.id or "auto:phase2"
    if actor_ident != d.get("proposer"):
        rbac.require(rbac.can_approve(actor))

    src_supplier = (d.get("payload") or {}).get("supplier") or {}
    if isinstance(src_supplier, str):
        src_supplier = {"name": src_supplier}
    name = str(src_supplier.get("name") or "").strip() or (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="supplier_name_missing")

    # 1) create supplier draft + auto-approve + commit (زر واحد صريح = تأكيد المستخدم)
    supplier_draft = action_runtime.create_draft(
        action="supplier",
        payload={"name": name, "phone": payload.get("phone")},
        proposer=actor_ident,
        session_id=d.get("session_id"),
    )
    req = action_runtime.request_approval(draft_id=supplier_draft["id"], requester=actor_ident)
    if "error" in req:
        raise HTTPException(status_code=400, detail=req)
    approver_id = f"auto:phase2:{actor_ident or 'anon'}"
    apr = action_runtime.approve(approval_id=req["approval_id"], approver=approver_id)
    if "error" in apr and apr.get("error") != "already_approved":
        raise HTTPException(status_code=400, detail=apr)
    committed = action_runtime.commit(draft_id=supplier_draft["id"], committer=approver_id)
    if isinstance(committed, dict) and "error" in committed:
        raise HTTPException(status_code=400, detail=committed)

    new_supplier_id = (committed.get("result") or {}).get("id")

    # 2) update the purchase draft with the new supplier id (is_new=False)
    patch_res = action_runtime.patch_draft(
        draft_id=draft_id,
        ops=[
            {"op": "set_supplier_name", "name": name},
            {"op": "set_supplier_id", "id": new_supplier_id},
        ],
        actor=actor_ident,
    )
    return {"success": True, "data": {"supplier": committed.get("result"), "purchase": patch_res.get("draft")}}


# ─── Approvals ──────────────────────────────────────────────────────────────


@router.get("/approvals")
async def runtime_list_approvals(
    request: Request,
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=50, le=200),
):
    await _require_approver(request)
    return {"success": True, "data": action_runtime.list_approvals(status=status, limit=limit)}


@router.post("/approvals/{approval_id}/approve")
async def runtime_approve(approval_id: str, request: Request, payload: Optional[Dict[str, Any]] = Body(default=None)):
    payload = payload or {}
    # ── RBAC: حلّ هوية المُعتمِد الحقيقية وتحقق من صلاحيته ──
    ident = rbac.extract_identity(request, payload)
    actor = await rbac.resolve_actor(user_id=ident["user_id"], name=ident["name"], role_hint=ident["role_hint"])
    rbac.require(rbac.can_approve(actor))
    # الهوية الحقيقية للمُعتمِد (بدون بادئة reviewer:) → الأربع أعين الصارم
    approver = actor.name or actor.id or "anonymous"
    result = action_runtime.approve(approval_id=approval_id, approver=approver)
    if "error" in result:
        # 4-eyes violation gets a 403, other errors 400
        code = 403 if result["error"] == "four_eyes_violation" else 400
        raise HTTPException(status_code=code, detail=result)
    # 🆕 Auto-commit on approval — approving a risky action means "execute it now".
    draft_id = (result.get("draft") or {}).get("id")
    committed = None
    if draft_id:
        committed = action_runtime.commit(draft_id=draft_id, committer=approver)
        if isinstance(committed, dict) and "error" in committed:
            raise HTTPException(status_code=400, detail=committed)
    return {"success": True, "data": {**result, "committed": committed}}


@router.post("/approvals/{approval_id}/reject")
async def runtime_reject(approval_id: str, request: Request, payload: Optional[Dict[str, Any]] = Body(default=None)):
    payload = payload or {}
    # RBAC: المُعتمِد أو صاحب الطلب نفسه (إلغاء ذاتي مسموح — عكس الاعتماد الذاتي)
    ident = rbac.extract_identity(request, payload)
    actor = await rbac.resolve_actor(user_id=ident["user_id"], name=ident["name"], role_hint=ident["role_hint"])
    actor_ident = actor.name or actor.id or ""
    approval = next((a for a in action_runtime.list_approvals(limit=200) if a.get("id") == approval_id), None)
    requester = (approval or {}).get("requester") or (approval or {}).get("proposer")
    if actor_ident != requester:
        rbac.require(rbac.can_approve(actor))
    result = action_runtime.reject_approval(
        approval_id=approval_id,
        approver=actor_ident or payload.get("approver"),
        reason=payload.get("reason", ""),
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"success": True, "data": result}


# ─── Commit ─────────────────────────────────────────────────────────────────


@router.post("/drafts/{draft_id}/commit")
async def runtime_commit(draft_id: str, request: Request, payload: Optional[Dict[str, Any]] = Body(default=None)):
    payload = payload or {}
    ident = rbac.extract_identity(request, payload)
    actor = await rbac.resolve_actor(user_id=ident["user_id"], name=ident["name"], role_hint=ident["role_hint"])
    rbac.require(rbac.can_approve(actor))
    result = action_runtime.commit(draft_id=draft_id, committer=actor.name or actor.id or payload.get("committer"))
    if "error" in result:
        raise HTTPException(status_code=400, detail=result)
    return {"success": True, "data": result}


# ─── Executions / Rollback ──────────────────────────────────────────────────


@router.get("/executions")
async def runtime_list_executions(
    request: Request,
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=50, le=200),
):
    await _require_approver(request)
    return {"success": True, "data": action_runtime.list_executions(status=status, limit=limit)}


@router.post("/executions/{execution_id}/rollback")
async def runtime_rollback(execution_id: str, request: Request, payload: Optional[Dict[str, Any]] = Body(default=None)):
    payload = payload or {}
    ident = rbac.extract_identity(request, payload)
    actor = await rbac.resolve_actor(user_id=ident["user_id"], name=ident["name"], role_hint=ident["role_hint"])
    rbac.require(rbac.can_approve(actor))
    result = action_runtime.rollback(execution_id=execution_id, rollbacker=actor.name or actor.id or payload.get("rollbacker"))
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"success": True, "data": result}


# ─── Audit / Stats / DB peek ────────────────────────────────────────────────


@router.get("/audit")
async def runtime_audit(request: Request, limit: int = Query(default=100, le=500)):
    await _require_approver(request)
    return {"success": True, "data": action_runtime.get_audit_trail(limit=limit)}


@router.get("/stats")
async def runtime_stats(request: Request):
    await _require_approver(request)
    return {"success": True, "data": action_runtime.stats()}


@router.get("/db/{table}")
async def runtime_db_peek(table: str, request: Request):
    """Peek at the in-memory staging DB. Phase 3C.2 will replace with Supabase."""
    await _require_approver(request)
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
async def runtime_alias_approve(approval_id: str, request: Request, payload: Optional[Dict[str, Any]] = Body(default=None)):
    """Alias: POST /api/runtime/approve/{approval_id} — RBAC-guarded (أربع أعين حقيقي)."""
    payload = payload or {}
    ident = rbac.extract_identity(request, payload)
    actor = await rbac.resolve_actor(user_id=ident["user_id"], name=ident["name"], role_hint=ident["role_hint"])
    rbac.require(rbac.can_approve(actor))
    approver = actor.name or actor.id or "anonymous"
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
async def runtime_alias_commit(draft_id: str, request: Request, payload: Optional[Dict[str, Any]] = Body(default=None)):
    """Alias: POST /api/runtime/commit/{draft_id} — RBAC-guarded."""
    payload = payload or {}
    ident = rbac.extract_identity(request, payload)
    actor = await rbac.resolve_actor(user_id=ident["user_id"], name=ident["name"], role_hint=ident["role_hint"])
    rbac.require(rbac.can_approve(actor))
    result = action_runtime.commit(
        draft_id=draft_id,
        committer=actor.name or actor.id or payload.get("committer"),
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
async def runtime_alias_rollback(execution_id: str, request: Request, payload: Optional[Dict[str, Any]] = Body(default=None)):
    """Alias: POST /api/runtime/rollback/{execution_id} — RBAC-guarded."""
    payload = payload or {}
    ident = rbac.extract_identity(request, payload)
    actor = await rbac.resolve_actor(user_id=ident["user_id"], name=ident["name"], role_hint=ident["role_hint"])
    rbac.require(rbac.can_approve(actor))
    result = action_runtime.rollback(
        execution_id=execution_id,
        rollbacker=actor.name or actor.id or payload.get("rollbacker"),
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return {
        "status": "rolled_back",
        "execution_id": result.get("execution_id"),
        "draft_status": (result.get("draft") or {}).get("status"),
    }


@router.get("/report")
async def runtime_alias_report(request: Request):
    """Alias: GET /api/runtime/report → flat summary of the runtime state."""
    await _require_approver(request)
    s = action_runtime.stats()
    return {
        "mode": "summary",
        **s,
    }


# ============================================================================
# 🧠 Phase 3C.3 — LLM Intent Parser (text → Action → draft+approval)
# ============================================================================


@router.post("/intent/parse")
async def runtime_parse_intent(payload: Dict[str, Any] = Body(...)):
    """POST /api/runtime/intent/parse

    Body: {"text": "...", "session_id": "..."}
    Uses Emergent LLM (gpt-4o-mini) to extract a strict Action JSON. Does NOT
    create a draft — pure parsing. Useful for "preview" UX.
    """
    from core.llm_intent_parser import parse_intent_with_llm
    text = (payload.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text required")
    action = await parse_intent_with_llm(text, session_id=payload.get("session_id"))
    return {"success": True, "data": action.model_dump()}


@router.post("/intent/execute")
async def runtime_execute_intent(payload: Dict[str, Any] = Body(...)):
    """POST /api/runtime/intent/execute

    Pipeline: text → LLM-parsed Action → register as Action Runtime draft →
    auto request_approval → return {draft, approval, action} so the caller
    can continue with /approve → /commit.

    Read-only intents (`get_active_visits`) short-circuit and return live data
    without creating a draft.
    """
    from core.llm_intent_parser import parse_intent_with_llm
    text = (payload.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text required")
    proposer = payload.get("proposer") or "bot_tester"

    action = await parse_intent_with_llm(text, session_id=payload.get("session_id"))
    action_name = action.action

    # ── Read-only path: get_active_visits — never a draft ──
    if action_name == "get_active_visits":
        return {
            "success": True,
            "data": {
                "action": action.model_dump(),
                "mode": "read_only",
                "result": action_runtime.get_active_visits(limit=int(payload.get("limit") or 50)),
            },
        }

    # ── Map LLM action_name → runtime action token ──
    runtime_action = {
        "create_customer": "customer",
        "create_vehicle": "vehicle",
        "create_visit": "visit",
        "close_visits": "close_visits",
    }.get(action_name)

    if not runtime_action:
        return {
            "success": False,
            "data": {"action": action.model_dump(), "mode": "unknown", "hint": "could_not_parse_intent"},
        }

    # Register as a draft + auto request_approval
    draft = action_runtime.create_draft(
        action=runtime_action,
        payload=action.payload,
        proposer=proposer,
        session_id=payload.get("session_id"),
    )
    approval = action_runtime.request_approval(draft_id=draft["id"], requester=proposer)
    return {
        "success": True,
        "data": {
            "action": action.model_dump(),
            "mode": "draft",
            "draft": draft,
            "approval": approval,
        },
    }


@router.get("/visits/active")
async def runtime_get_active_visits(limit: int = Query(default=50, le=200)):
    """Read-only — current active visits (vehicles with status != مُسلَّمة)."""
    return {"success": True, "data": action_runtime.get_active_visits(limit=limit)}


# ============================================================================
# 🚀 Phase 3C.4 — Unified Execution Engine (policy-driven single entrypoint)
# ============================================================================


@router.post("/execute")
async def runtime_execute_unified(request: Request, payload: Dict[str, Any] = Body(...)):
    """POST /api/runtime/execute  — the L16 single-shot endpoint.

    Body: {"text": "...", "proposer": "?", "session_id": "?"}

    Pipeline: text → LLM intent → policy decision → runtime.

    Returned `status` is one of:
      • "rejected"          — unknown action
      • "read_only"         — pure query (no draft)
      • "pending_approval"  — risky → draft + approval, waiting human
      • "committed"         — safe → auto-approved and written
      • "error"             — runtime failure (e.g. four_eyes_violation)
    """
    from core.unified_executor import execute_text
    text = (payload.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text required")
    # 🔐 الهوية الحقيقية من JWT — مرساة الأربع أعين
    ident = rbac.extract_identity(request, payload)
    result = await execute_text(
        text,
        proposer=ident.get("name") or payload.get("proposer"),
        session_id=payload.get("session_id"),
        auto_approver=payload.get("auto_approver") or "auto:policy",
    )
    # Always return HTTP 200 for "rejected" (text we understood but is not an
    # executable action — usually a question). Returning 422 made the frontend
    # axios call throw and surface a scary red error bubble for normal chat
    # text; now the UI can inspect `status` and gracefully fall back to the
    # chat/answer path. Genuine runtime failures still return 400.
    status_code = 400 if result.get("status") == "error" else 200
    return JSONResponse(content={"success": result.get("status") not in ("error",), "data": result}, status_code=status_code)
