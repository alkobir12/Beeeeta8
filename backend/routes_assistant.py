"""
🤖 Unified Assistant API — نقطة دخول واحدة لكل بوتات النظام

Endpoints:
  • POST /api/assistant/chat            — محادثة موحدة (rate-limited: 30/min/IP)
  • GET  /api/assistant/session/{id}    — استعلام سجل جلسة
  • GET  /api/assistant/tools           — قائمة الأدوات المتاحة
  • POST /api/assistant/tool/{name}     — استدعاء أداة مباشرة (للاختبار)
  • GET  /api/assistant/alerts          — التنبيهات النشطة من alert_bus
  • GET  /api/assistant/stats           — إحصائيات النواة
  • GET  /api/assistant/audit/recent    — آخر سجل تدقيق (Phase 3A)
"""

import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, HTTPException, Query, Request
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
    """محادثة موحدة. Body: {message, session_id?, workshop_id?, force_agent?, use_ai?}.

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
        )
        return {"success": True, "data": result}
    except Exception as e:
        _log.exception("assistant_chat failed: %s", redact(str(e), max_len=200))
        return {"success": False, "error": redact(str(e), max_len=200)}


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
