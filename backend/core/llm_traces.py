"""🔬 llm_traces — نظام التتبع الإلزامي (المرحلة 2 من بروتوكول التشريح).

كل تفاعل شات = trace واحد في MongoDB يحوي:
  • request.messages المرسلة فعلياً للـ LLM (بعد تنقيح PDPL)
  • tool_calls_executed: الأداة + المدخلات + المخرجات الخام (output_raw)
  • response_raw من المزوّد + الرد النهائي للمستخدم
قاعدة الحاكمية: كل نتيجة اختبار بدون trace_id = مرفوضة.
"""

import contextvars
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.log_utils import get_logger, redact

_log = get_logger("core.llm_traces")

_client = None
_col = None

_FIELD_CAP = 60000  # حد أقصى لكل حقل نصي — يكفي للفحص الآلي الحرفي


def _collection():
    global _client, _col
    if _col is not None:
        return _col
    try:
        from pymongo import MongoClient
        _client = MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=3000)
        col = _client[os.environ["DB_NAME"]]["llm_traces"]
        col.create_index("trace_id", unique=True)
        col.create_index([("session_id", 1), ("ts", -1)])
        col.create_index([("ts", -1)])
        _col = col
        return _col
    except Exception as e:
        _log.warning("llm_traces mongo unavailable: %s", redact(str(e), max_len=120))
        return None


def _cap(v: Any) -> Any:
    if v is None:
        return None
    s = v if isinstance(v, str) else repr(v)
    if len(s) <= _FIELD_CAP:
        return s
    return s[:_FIELD_CAP] + f"…[truncated {len(s) - _FIELD_CAP} chars]"


def _safe(v: Any) -> Any:
    """🔐 SEC-005/PDPL: تنقيح المعرّفات الشخصية (هواتف/إيميلات) والأسرار (JWT/مفاتيح)
    قبل تخزين محتوى الـtrace في Mongo، مع الإبقاء على الأسماء والمبالغ العادية
    (< 9 أرقام) كي تظل قيمة التشريح/Provenance سليمة. يحافظ على None ويطبّق نفس الحد."""
    if v is None:
        return None
    s = v if isinstance(v, str) else repr(v)
    return redact(s, max_len=_FIELD_CAP)


_current: "contextvars.ContextVar[Optional[Dict[str, Any]]]" = contextvars.ContextVar(
    "llm_trace", default=None)


def start_trace(*, session_id: Optional[str] = None, user: Optional[str] = None,
                role: Optional[str] = None, channel: str = "chat",
                message: str = "") -> str:
    trace = {
        "trace_id": "tr-" + uuid.uuid4().hex[:12],
        "ts": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "user": user,
        "role": role,
        "channel": channel,
        "user_message": _safe(message),
        "llm_calls": [],
        "tool_calls_executed": [],
        "final_response": None,
        "intent": None,
        "status": None,
        "executed": None,
        "error": None,
        "duration_ms": None,
        "_t0": time.time(),
    }
    _current.set(trace)
    return trace["trace_id"]


def active_trace_id() -> Optional[str]:
    tr = _current.get()
    return tr["trace_id"] if tr else None


def add_tool_call(*, tool: str, tool_input: Optional[Dict[str, Any]] = None,
                  output_raw: Any = None, success: bool = True,
                  error: Optional[str] = None, duration_ms: Optional[float] = None,
                  write: bool = False) -> None:
    tr = _current.get()
    if not tr:
        return
    tr["tool_calls_executed"].append({
        "tool": tool,
        "input": {k: _safe(v) for k, v in (tool_input or {}).items()},
        "output_raw": _safe(output_raw),
        "success": bool(success),
        "error": _safe(error) if error else None,
        "duration_ms": round(duration_ms, 1) if duration_ms is not None else None,
        "write": bool(write),
    })


def add_llm_call(*, purpose: str, provider: str, model: str,
                 system_message: Optional[str] = None,
                 request_messages: Optional[List[Dict[str, Any]]] = None,
                 response_raw: Any = None, duration_ms: Optional[float] = None,
                 error: Optional[str] = None) -> None:
    tr = _current.get()
    if not tr:
        return
    tr["llm_calls"].append({
        "purpose": purpose,
        "provider": provider,
        "model": model,
        "system_message": _safe(system_message),
        "request_messages": [
            {"role": m.get("role"), "content": _safe(m.get("content"))}
            for m in (request_messages or [])
        ],
        "response_raw": _safe(response_raw),
        "duration_ms": round(duration_ms, 1) if duration_ms is not None else None,
        "error": _safe(error) if error else None,
    })


def finish_trace(*, session_id: Optional[str] = None, final_response: Optional[str] = None,
                 intent: Optional[str] = None, status: Optional[str] = None,
                 executed: Optional[Dict[str, Any]] = None,
                 error: Optional[str] = None) -> Optional[str]:
    tr = _current.get()
    if not tr:
        return None
    _current.set(None)
    tr["duration_ms"] = round((time.time() - tr.pop("_t0", time.time())) * 1000, 1)
    if session_id:
        tr["session_id"] = session_id
    tr["final_response"] = _safe(final_response)
    tr["intent"] = intent
    tr["status"] = status
    if executed is not None:
        tr["executed"] = {k: _safe(v) if isinstance(v, str) else v
                          for k, v in executed.items()}
    tr["error"] = _safe(error) if error else None
    col = _collection()
    if col is not None:
        try:
            col.insert_one(dict(tr))
        except Exception as e:
            _log.warning("trace persist failed: %s", redact(str(e), max_len=120))
    return tr["trace_id"]


def get_trace(trace_id: str) -> Optional[Dict[str, Any]]:
    col = _collection()
    if col is None:
        return None
    doc = col.find_one({"trace_id": trace_id}, {"_id": 0})
    return doc


def list_traces(*, session_id: Optional[str] = None, limit: int = 20,
                full: bool = False) -> List[Dict[str, Any]]:
    col = _collection()
    if col is None:
        return []
    q: Dict[str, Any] = {}
    if session_id:
        q["session_id"] = session_id
    proj = {"_id": 0} if full else {
        "_id": 0, "trace_id": 1, "ts": 1, "session_id": 1, "user": 1, "role": 1,
        "channel": 1, "user_message": 1, "intent": 1, "status": 1,
        "duration_ms": 1, "error": 1,
        "llm_calls.purpose": 1, "llm_calls.model": 1, "llm_calls.duration_ms": 1,
        "tool_calls_executed.tool": 1, "tool_calls_executed.success": 1,
        "tool_calls_executed.write": 1,
    }
    return list(col.find(q, proj).sort("ts", -1).limit(min(int(limit), 200)))


def stats() -> Dict[str, Any]:
    col = _collection()
    if col is None:
        return {"enabled": False, "count": 0}
    return {"enabled": True, "count": col.estimated_document_count()}
