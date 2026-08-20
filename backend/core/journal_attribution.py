"""تسجيل هوية منفّذ الطلب (JWT الموقّع) لكل قيد مرحّل — دون أي مساس بالمحرك المحاسبي.

المبدأ: المحرك المحاسبي مجمّد. الإسناد يُسجَّل في مجموعة Mongo منفصلة `journal_attribution`
من نقاط الاستدعاء بعد نجاح الترحيل، والهوية تُلتقط من JWT عبر contextvar (لا انتحال).
"""
import contextvars
from datetime import datetime, timezone
from typing import Any, Dict, Optional

_current_actor: contextvars.ContextVar = contextvars.ContextVar("journal_request_actor", default=None)


def set_request_actor(identity: Optional[Dict[str, Any]]) -> None:
    _current_actor.set(identity if identity and identity.get("username") else None)


def get_request_actor() -> Optional[Dict[str, Any]]:
    return _current_actor.get()


class ActorContextASGIMiddleware:
    """يلتقط هوية JWT الموقَّعة من الطلب ويضعها في contextvar (Pure ASGI — بلا buffering)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            try:
                from starlette.requests import Request
                from auth_jwt import identity_from_request
                set_request_actor(identity_from_request(Request(scope)))
            except Exception:
                set_request_actor(None)
        await self.app(scope, receive, send)


def _collection():
    from core.accounting_engine import get_engine
    return get_engine().identity.collection().database["journal_attribution"]


def _extract_journal_id(posted: Any) -> Optional[str]:
    if isinstance(posted, list) and posted:
        first = posted[0] or {}
        return str(first.get("id") or "") or None
    if isinstance(posted, dict):
        return str(posted.get("journal_id") or posted.get("id") or "") or None
    if isinstance(posted, str):
        return posted or None
    return None


def record_attribution(posted: Any, entry: Optional[Dict[str, Any]] = None) -> None:
    """يسجّل المستخدم الموثق (من JWT) الذي تسبب بترحيل القيد — fail-safe، لا يعطّل الترحيل أبداً."""
    try:
        actor = _current_actor.get()
        if not actor or not actor.get("username"):
            return
        journal_id = _extract_journal_id(posted)
        if not journal_id:
            return
        _collection().update_one(
            {"journal_id": journal_id},
            {"$setOnInsert": {
                "journal_id": journal_id,
                "username": str(actor.get("username")),
                "role": str(actor.get("role") or ""),
                "source": str((entry or {}).get("source") or ""),
                "ts": datetime.now(timezone.utc).isoformat(),
            }},
            upsert=True,
        )
    except Exception:
        pass
