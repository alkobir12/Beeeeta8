"""
📡 Alert Bus — Unified Event Bus

نظام نشر/اشتراك خفيف لربط:
  • Firewall Engine → ينشر alerts الجديدة
  • AssistantKernel → يشترك على alerts ليُحفظ في الذاكرة المشتركة
  • Future: WebSocket / WhatsApp / Push notifications

كل alert يتضمن:
  • id
  • category (duplicate_detection, balance_integrity, ...)
  • severity (critical/high/medium/low/info)
  • title, description, financial_impact, evidence, …
  • lifecycle: new → acknowledged → resolved/dismissed
"""

from __future__ import annotations
import threading
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Callable, Deque, Dict, List, Optional


_lock = threading.RLock()
_subscribers: List[Callable[[Dict[str, Any]], None]] = []
_event_log: Deque[Dict[str, Any]] = deque(maxlen=500)  # آخر 500 حدث للسجل
_alert_index: Dict[str, Dict[str, Any]] = {}  # alert_id → آخر نسخة


def subscribe(callback: Callable[[Dict[str, Any]], None]) -> None:
    """يشترك في الأحداث الجديدة."""
    with _lock:
        if callback not in _subscribers:
            _subscribers.append(callback)


def unsubscribe(callback: Callable[[Dict[str, Any]], None]) -> None:
    with _lock:
        if callback in _subscribers:
            _subscribers.remove(callback)


def publish(event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """ينشر حدثاً لجميع المشتركين.

    event_type: alert.new | alert.resolved | alert.dismissed | system.tick
    """
    event = {
        "type": event_type,
        "payload": payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ts_unix": time.time(),
    }
    with _lock:
        _event_log.append(event)
        # حفظ آخر نسخة للـ alert في الفهرس
        if event_type.startswith("alert.") and isinstance(payload, dict):
            alert_id = payload.get("id")
            if alert_id:
                _alert_index[alert_id] = {**payload, "_last_event": event_type, "_last_event_at": event["timestamp"]}
        listeners = list(_subscribers)
    # خارج اللوك لتجنّب deadlock
    for cb in listeners:
        try:
            cb(event)
        except Exception as e:
            print(f"[alert_bus] subscriber error: {e}")
    return event


def publish_alerts_batch(alerts: List[Dict[str, Any]]) -> int:
    """نشر مجموعة تنبيهات (يُستخدم من firewall_engine بعد كل run)."""
    published = 0
    seen: set = set()
    with _lock:
        seen = {a.get("id") for a in _alert_index.values() if a.get("id")}
    for alert in alerts or []:
        aid = alert.get("id")
        if not aid:
            continue
        is_new = aid not in seen
        publish("alert.new" if is_new else "alert.refresh", alert)
        published += 1
    return published


def get_recent_events(limit: int = 50, event_type: Optional[str] = None) -> List[Dict[str, Any]]:
    with _lock:
        events = list(_event_log)
    if event_type:
        events = [e for e in events if e["type"] == event_type]
    return events[-limit:][::-1]  # newest first


def get_active_alerts(severity: Optional[str] = None, category: Optional[str] = None) -> List[Dict[str, Any]]:
    """يُرجع كل التنبيهات النشطة (التي لم تُحلّ أو تُتجاهَل)."""
    with _lock:
        alerts = list(_alert_index.values())
    out = []
    for a in alerts:
        last = a.get("_last_event")
        if last in {"alert.resolved", "alert.dismissed"}:
            continue
        if severity and a.get("severity") != severity:
            continue
        if category and a.get("category") != category:
            continue
        out.append(a)
    return out


def mark_alert_resolved(alert_id: str, by: str = "system") -> bool:
    with _lock:
        a = _alert_index.get(alert_id)
    if not a:
        return False
    publish("alert.resolved", {**a, "resolved_by": by})
    return True


def mark_alert_dismissed(alert_id: str, by: str = "user", expires_in_hours: int = 24) -> bool:
    with _lock:
        a = _alert_index.get(alert_id)
    if not a:
        return False
    publish("alert.dismissed", {**a, "dismissed_by": by, "expires_in_hours": expires_in_hours})
    return True


def stats() -> Dict[str, Any]:
    with _lock:
        return {
            "subscribers_count": len(_subscribers),
            "events_in_log": len(_event_log),
            "alerts_tracked": len(_alert_index),
        }
