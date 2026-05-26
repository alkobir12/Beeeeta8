"""
🤖 Unified Assistant API — نقطة دخول واحدة لكل بوتات النظام

Endpoints:
  • POST /api/assistant/chat            — محادثة موحدة
  • GET  /api/assistant/session/{id}    — استعلام سجل جلسة
  • GET  /api/assistant/tools           — قائمة الأدوات المتاحة
  • POST /api/assistant/tool/{name}     — استدعاء أداة مباشرة (للاختبار)
  • GET  /api/assistant/alerts          — التنبيهات النشطة من alert_bus
  • GET  /api/assistant/stats           — إحصائيات النواة
"""

from typing import Any, Dict, Optional
from fastapi import APIRouter, Body, HTTPException, Query

from core import assistant_kernel, alert_bus, tool_router, shared_memory

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


@router.post("/chat")
async def assistant_chat(payload: Dict[str, Any] = Body(...)):
    """محادثة موحدة. Body: {message, session_id?, workshop_id?, force_agent?, use_ai?}"""
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
        import traceback
        print(f"[assistant_chat] err: {e}\n{traceback.format_exc()}")
        return {"success": False, "error": str(e)}


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
