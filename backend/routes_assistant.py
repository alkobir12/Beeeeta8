"""
🤖 Unified Assistant API — نقطة دخول واحدة لكل بوتات النظام

Endpoints:
  • POST /api/assistant/chat            — محادثة موحدة (rate-limited: 30/min/IP)
  • POST /api/assistant/chat/stream     — Streaming SSE (Phase 3B)
  • GET  /api/assistant/dashboard       — لوحة افتتاحية (Phase 3B)
  • GET  /api/assistant/session/{id}    — استعلام سجل جلسة
  • GET  /api/assistant/tools           — قائمة الأدوات المتاحة
  • GET  /api/assistant/models          — قائمة النماذج (GPT/Ollama)
  • POST /api/assistant/tool/{name}     — استدعاء أداة مباشرة (للاختبار)
  • GET  /api/assistant/alerts          — التنبيهات النشطة من alert_bus
  • GET  /api/assistant/stats           — إحصائيات النواة
  • GET  /api/assistant/audit/recent    — آخر سجل تدقيق (Phase 3A)
"""

import asyncio
import json
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from core import alert_bus, assistant_kernel, shared_memory, tool_router
from core.log_utils import get_logger, redact

router = APIRouter(prefix="/api/assistant", tags=["assistant"])

_log = get_logger("routes.assistant")

# Phase 3A — Per-IP rate limit (default 30/min). Override via env.
_CHAT_RATE = os.environ.get("ASSISTANT_CHAT_RATE", "30/minute")

# Limiter exposed at module level so server.py can register the global handler.
limiter = Limiter(key_func=get_remote_address)


@router.post("/chat")
@limiter.limit(_CHAT_RATE)
async def assistant_chat(request: Request, payload: Dict[str, Any] = Body(...)):
    """محادثة موحدة. Body: {message, session_id?, workshop_id?, use_ai?, model?}.

    Args:
      model: "gpt" (default — Emergent gpt-4o-mini) أو "ollama" (محلي llama3.2:3b).

    Rate-limited (Phase 3A): 30 requests/minute per IP by default.
    """
    msg = (payload.get("message") or "").strip()
    if not msg:
        raise HTTPException(status_code=400, detail="message required")
    try:
        result = await assistant_kernel.chat(
            session_id=payload.get("session_id"),
            message=msg,
            workshop_id=payload.get("workshop_id"),
            force_agent=payload.get("force_agent"),
            use_ai=bool(payload.get("use_ai", True)),
            model=payload.get("model"),
        )
        return {"success": True, "data": result}
    except Exception as e:
        _log.exception("assistant_chat failed: %s", redact(str(e), max_len=200))
        return {"success": False, "error": redact(str(e), max_len=200)}


@router.get("/models")
async def assistant_models():
    """🆕 يرجع قائمة النماذج المتاحة للاختيار داخل الواجهة."""
    from core import llm_helpers
    ollama_alive = await llm_helpers.is_ollama_alive()
    ollama_models = await llm_helpers.ollama_list_models() if ollama_alive else []
    return {
        "success": True,
        "data": {
            "default": "gpt",
            "models": [
                {
                    "id": "gpt",
                    "label": "GPT (Emergent)",
                    "provider": "openai",
                    "model": "gpt-4o-mini",
                    "available": bool(os.environ.get("EMERGENT_LLM_KEY")),
                    "description": "سريع وعالي الجودة (cloud)",
                },
                {
                    "id": "ollama",
                    "label": "Ollama (محلي)",
                    "provider": "ollama",
                    "model": llm_helpers.OLLAMA_DEFAULT_MODEL,
                    "available": ollama_alive and (llm_helpers.OLLAMA_DEFAULT_MODEL in ollama_models),
                    "description": "خصوصية تامة (يعمل بدون إنترنت)",
                    "installed_models": ollama_models,
                },
            ],
        },
    }


@router.get("/session/{session_id}")
async def assistant_session(session_id: str, limit: int = Query(default=20, le=100)):
    msgs = assistant_kernel.get_session_messages(session_id, limit=limit)
    return {"success": True, "data": {"session_id": session_id, "messages": msgs}}


@router.get("/tools")
async def assistant_tools(agent: Optional[str] = Query(default=None)):
    return {"success": True, "data": tool_router.list_tools(agent=agent)}


@router.post("/tool/{name}")
async def assistant_call_tool(name: str, payload: Dict[str, Any] = Body(default=None)):
    args = payload or {}
    result = await tool_router.call_tool(name, **args)
    return result


@router.get("/alerts")
async def assistant_alerts(
    severity: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    limit: int = Query(default=20, le=100),
):
    """التنبيهات النشطة من alert_bus (يتم ملؤها تلقائياً من firewall_engine)."""
    alerts = alert_bus.get_active_alerts(severity=severity, category=category)
    return {"success": True, "data": alerts[:limit], "total": len(alerts)}


@router.get("/stats")
async def assistant_stats():
    return {"success": True, "data": assistant_kernel.kernel_stats()}


@router.get("/audit/recent")
async def assistant_audit_recent(limit: int = Query(default=50, le=200)):
    """🆕 Phase 3A — آخر N سجلات تدقيق (metadata فقط، بدون محتوى الرسائل)."""
    try:
        from domains.bot_audit import audit_service
        rows = await audit_service.recent(limit=limit)
        return {"success": True, "data": rows, "count": len(rows)}
    except Exception as e:
        return {"success": False, "error": redact(str(e), max_len=200), "data": []}


# ============================================================================
# 🆕 Phase 3B — Streaming + Dashboard
# ============================================================================


@router.post("/chat/stream")
@limiter.limit(_CHAT_RATE)
async def assistant_chat_stream(request: Request, payload: Dict[str, Any] = Body(...)):
    """🌊 Server-Sent Events streaming variant of /chat.

    The pipeline still runs end-to-end on the backend (tool calls + LLM); we
    emit *progress events* during each phase, then yield the final response
    in a single `event: done` payload. The client can use these events to show
    a granular "thinking" indicator instead of a single spinner.

    Event types:
      • progress  — {phase, label}
      • tool      — {tool, success}
      • token     — {text}   (currently emitted once at end; reserved for true
                              token-streaming when backend LLM supports it)
      • done      — full assistant payload (same shape as /chat)
      • error     — {error}
    """
    msg = (payload.get("message") or "").strip()
    if not msg:
        raise HTTPException(status_code=400, detail="message required")

    async def _stream():
        def _evt(event_type: str, data: Dict[str, Any]) -> str:
            return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

        try:
            yield _evt("progress", {"phase": "thinking", "label": "يفهم سؤالك…"})
            await asyncio.sleep(0.05)
            yield _evt("progress", {"phase": "tools", "label": "جارٍ تشغيل الأدوات…"})
            await asyncio.sleep(0.05)

            result = await assistant_kernel.chat(
                session_id=payload.get("session_id"),
                message=msg,
                workshop_id=payload.get("workshop_id"),
                force_agent=payload.get("force_agent"),
                use_ai=bool(payload.get("use_ai", True)),
                model=payload.get("model"),
            )

            for tr in result.get("tool_results") or []:
                yield _evt("tool", {"tool": tr.get("tool"), "success": tr.get("success", False)})

            yield _evt("progress", {"phase": "rendering", "label": "يصيغ الردّ…"})
            await asyncio.sleep(0.05)

            yield _evt("done", result)
        except Exception as e:
            _log.exception("stream failed: %s", redact(str(e), max_len=200))
            yield _evt("error", {"error": redact(str(e), max_len=200)})

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering for SSE
            "Connection": "keep-alive",
        },
    )


@router.get("/dashboard")
async def assistant_dashboard(workshop_id: str = Query(default="finmodule-sync")):
    """🆕 Phase 3B — لوحة افتتاحية تظهر تلقائياً عند فتح الـDrawer.

    تجمع 8 مؤشرات من firewall + workshop + finance بدون مكالمة LLM.
    """
    from core import tool_router as _tr
    panels = []

    async def _safe_run(label: str, tool: str, **kwargs):
        try:
            r = await _tr.call_tool(tool, workshop_id=workshop_id, **kwargs)
            if r.get("success"):
                return r.get("result")
        except Exception:
            pass
        return None

    # 1. Vehicles in workshop (active visits)
    aw = await _safe_run("vehicles_in_workshop", "workshop.active_visits")
    if aw is not None:
        panels.append({"id": "active_visits", "label": "زيارات نشطة", "value": aw.get("active_visits", 0), "kind": "count"})

    # 2. Health score
    hs = await _safe_run("health", "firewall.health_score")
    if hs is not None:
        panels.append({"id": "health_score", "label": "الصحة المالية", "value": hs.get("score", 0), "kind": "score", "status": hs.get("status")})

    # 3. AR — debtors total
    ar = await _safe_run("ar", "finance.ar_summary")
    if ar is not None:
        panels.append({"id": "total_ar", "label": "إجمالي ذمم العملاء", "value": ar.get("total_ar", 0), "kind": "currency", "secondary": f"{ar.get('total_customers_with_debt',0)} عميل"})

    # 4. AP — supplier debt total
    ap = await _safe_run("ap", "finance.payables_summary")
    if ap is not None:
        panels.append({"id": "total_ap", "label": "إجمالي ذمم الموردين", "value": ap.get("total_ap", 0), "kind": "currency", "secondary": f"{ap.get('total_suppliers_with_balance',0)} مورد"})

    # 5. Cash flow (30-day net)
    cf = await _safe_run("cash_flow", "firewall.cash_flow")
    if cf is not None:
        net = cf.get("net") if isinstance(cf, dict) else None
        if net is not None:
            panels.append({"id": "cash_flow_30d", "label": "صافي التدفّق (30 يوم)", "value": net, "kind": "currency"})

    # 6. Open alerts (severity high+critical)
    alerts_ = await _safe_run("alerts", "firewall.top_alerts", limit=20)
    if isinstance(alerts_, list):
        critical = [a for a in alerts_ if (a.get("severity") or "").lower() in ("high", "critical")]
        panels.append({"id": "critical_findings", "label": "تنبيهات حرجة", "value": len(critical), "kind": "count"})

    # 7. Low-stock parts
    ls = await _safe_run("low_stock", "inventory.low_stock", limit=50)
    if ls is not None:
        panels.append({"id": "low_stock", "label": "قطع منخفضة المخزون", "value": ls.get("low_stock_count", 0), "kind": "count"})

    # 8. Operations with integrity warnings (missing journal entries)
    integ = await _safe_run("integrity", "firewall.operation_integrity", limit=50)
    if isinstance(integ, dict):
        panels.append({"id": "ops_with_warnings", "label": "عمليات بقيود مفقودة", "value": integ.get("with_warnings", 0), "kind": "count"})

    return {"success": True, "data": {"panels": panels, "generated_at": __import__("datetime").datetime.utcnow().isoformat() + "Z"}}


@router.get("/memory/{session_id}")
async def assistant_memory(session_id: str):
    """🆕 Phase 3B — يرجع conversation memory (last_customer/vehicle/...)."""
    keys = [
        # Phase 3B Round 1
        "last_customer", "last_vehicle", "last_invoice",
        "last_operation", "last_supplier", "last_part",
        # 🆕 Phase 3B Round 2 — section + visit + draft pointers
        "last_section", "last_visit", "last_collection",
        "last_payment", "last_inventory",
    ]
    return {
        "success": True,
        "data": {k: shared_memory.get_context(session_id, k) for k in keys if shared_memory.get_context(session_id, k)},
    }


@router.post("/power/diagnose")
async def assistant_power_diagnose(payload: Dict[str, Any] = Body(...)):
    """🆕 Phase 3B Round 2 — Diagnose what Power Mode WOULD do without running it.

    Useful for tests + UX previews of `/power` parsing. NO writes happen.
    Body: {"message": "/power سجل عميل احمد، أضف مركبة 9935"}
    """
    from core import power_mode
    msg = (payload.get("message") or "").strip()
    if not msg:
        raise HTTPException(status_code=400, detail="message required")
    return {"success": True, "data": power_mode.diagnose(msg)}


# ============================================================================
# 🆕 Phase 3B Round 3 — Vector Memory + Brain + WhatsApp Outbox + Report
# ============================================================================


@router.post("/brain")
async def assistant_brain(payload: Dict[str, Any] = Body(...)):
    """🧠 Brain pipeline — composes Vector Memory + Power Mode + WhatsApp + Report.

    Body: {"message": "...", "session_id": "..."}

    Modes returned:
      • memory_hit  → entity recalled from semantic memory (no LLM)
      • power       → multi-intent drafts (read-only)
      • whatsapp    → MOCKED outbox entry (Phase 3D)
      • report      → session-scoped counts
      • passthrough → caller should use /chat for the LLM path
    """
    from core import brain as _brain
    msg = (payload.get("message") or "").strip()
    if not msg:
        raise HTTPException(status_code=400, detail="message required")
    sid = (payload.get("session_id") or "").strip() or f"brain-{int(__import__('time').time()*1000)}"
    result = await _brain.brain(session_id=sid, message=msg)
    return {"success": True, "data": result}


@router.get("/report/{session_id}")
async def assistant_report(session_id: str):
    """🆕 Phase 3B Round 3 — Live per-session report.

    Counts drafts, vector memory entries, last_* pointers, and outbox size.
    100% read-only.
    """
    from core import brain as _brain
    return {"success": True, "data": _brain.generate_report(session_id)}


@router.get("/whatsapp/outbox/{session_id}")
async def assistant_whatsapp_outbox(session_id: str):
    """🚫 MOCKED — Returns the simulated WhatsApp outbox for this session.

    Phase 3D will replace the mock with a real WhatsApp Cloud API call.
    """
    from core import brain as _brain
    outbox = _brain.whatsapp_outbox(session_id)
    return {
        "success": True,
        "mocked": True,
        "phase_unlocked_in": "3D",
        "data": list(outbox),
        "count": len(outbox),
    }


@router.post("/memory/search")
async def assistant_memory_search(payload: Dict[str, Any] = Body(...)):
    """🧠 Search vector memory for a semantic hit. Read-only."""
    from core import vector_memory
    sid = (payload.get("session_id") or "").strip()
    query = (payload.get("query") or "").strip()
    entity_type = payload.get("entity_type")
    if not sid or not query:
        raise HTTPException(status_code=400, detail="session_id + query required")
    hits = vector_memory.search_memory(
        session_id=sid, query=query, entity_type=entity_type, limit=int(payload.get("limit", 5) or 5),
    )
    return {"success": True, "data": {"hits": hits, "count": len(hits)}}
