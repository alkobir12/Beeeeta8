"""
🧠 Shared Memory — ذاكرة محادثة مشتركة عبر الجلسات

يخزّن:
  • محادثة Assistant (history)
  • تنبيهات مرتبطة بكل جلسة
  • context cache (last alerts, last queries)

TTL محدود (1 ساعة لكل جلسة) لمنع تضخّم الذاكرة.
"""

from __future__ import annotations
import threading
import time
from typing import Any, Dict, List, Optional

_SESSION_TTL = 3600  # ساعة
_lock = threading.RLock()
_sessions: Dict[str, Dict[str, Any]] = {}


def _now() -> float:
    return time.time()


def _evict_expired() -> None:
    """احذف الجلسات منتهية الصلاحية."""
    cutoff = _now() - _SESSION_TTL
    expired = [sid for sid, s in _sessions.items() if s.get("last_seen", 0) < cutoff]
    for sid in expired:
        _sessions.pop(sid, None)


def get_or_create(session_id: str) -> Dict[str, Any]:
    with _lock:
        _evict_expired()
        if session_id not in _sessions:
            _sessions[session_id] = {
                "session_id": session_id,
                "messages": [],
                "alerts_seen": set(),
                "context": {},
                "created_at": _now(),
                "last_seen": _now(),
            }
        else:
            _sessions[session_id]["last_seen"] = _now()
        return _sessions[session_id]


def append_message(session_id: str, role: str, content: str, meta: Optional[Dict[str, Any]] = None) -> None:
    with _lock:
        sess = get_or_create(session_id)
        sess["messages"].append({
            "role": role,
            "content": content,
            "meta": meta or {},
            "ts": _now(),
        })
        # حدّ أقصى 60 رسالة لكل جلسة (30 محادثة)
        if len(sess["messages"]) > 60:
            sess["messages"] = sess["messages"][-60:]


def get_messages(session_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    with _lock:
        sess = _sessions.get(session_id)
        if not sess:
            return []
        return sess["messages"][-limit:]


def attach_alert(session_id: str, alert_id: str) -> None:
    with _lock:
        sess = get_or_create(session_id)
        sess["alerts_seen"].add(alert_id)


def set_context(session_id: str, key: str, value: Any) -> None:
    with _lock:
        sess = get_or_create(session_id)
        sess["context"][key] = value


def get_context(session_id: str, key: str, default: Any = None) -> Any:
    with _lock:
        sess = _sessions.get(session_id)
        if not sess:
            return default
        return sess["context"].get(key, default)


def clear_session(session_id: str) -> None:
    with _lock:
        _sessions.pop(session_id, None)


def stats() -> Dict[str, Any]:
    with _lock:
        return {
            "active_sessions": len(_sessions),
            "total_messages": sum(len(s["messages"]) for s in _sessions.values()),
        }
