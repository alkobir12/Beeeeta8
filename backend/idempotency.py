"""
Idempotency middleware/helper for financial operations.

Usage:
    @router.post("/confirm-payment", dependencies=[Depends(check_idempotency)])

Or call manually:
    cached = idempotency_check_or_store(request, response_data)

Stores keys in an in-memory dict with TTL. Suitable for single-instance deployments.
For multi-instance production, swap _STORE with Redis or Mongo.
"""
import time
import hashlib
import json
from typing import Any, Optional, Dict
from threading import Lock

from fastapi import Request, HTTPException

_TTL_SECONDS = 24 * 3600  # 24 hours
_MAX_ENTRIES = 5000
_STORE: Dict[str, dict] = {}  # idempotency_key -> {"result": ..., "expires": ts}
_LOCK = Lock()


def _gc_if_needed():
    """جامع نفايات بسيط — يُنظِّف الإدخالات المنتهية الصلاحية."""
    if len(_STORE) <= _MAX_ENTRIES:
        return
    now = time.time()
    expired = [k for k, v in _STORE.items() if v.get("expires", 0) < now]
    for k in expired:
        _STORE.pop(k, None)
    # if still oversized, drop the oldest 10%
    if len(_STORE) > _MAX_ENTRIES:
        items = sorted(_STORE.items(), key=lambda kv: kv[1].get("created", 0))
        for k, _ in items[: int(_MAX_ENTRIES * 0.1)]:
            _STORE.pop(k, None)


def get_idempotency_key(request: Request) -> Optional[str]:
    """يقرأ المفتاح من header `Idempotency-Key` أو `X-Idempotency-Key`."""
    return (
        request.headers.get("Idempotency-Key")
        or request.headers.get("idempotency-key")
        or request.headers.get("X-Idempotency-Key")
        or request.headers.get("x-idempotency-key")
    )


def make_idempotency_key(
    user_or_workshop: str,
    operation: str,
    payload: dict,
) -> str:
    """يُولِّد مفتاحاً ثابتاً من المحتوى عند عدم توفر مفتاح من العميل."""
    blob = json.dumps(
        {"u": user_or_workshop, "op": operation, "p": payload}, sort_keys=True, ensure_ascii=False
    )
    return "auto-" + hashlib.sha256(blob.encode("utf-8")).hexdigest()[:32]


def get_cached_response(key: str) -> Optional[Any]:
    """يُرجِع الاستجابة المخزنة إذا المفتاح موجود وصالح."""
    if not key:
        return None
    with _LOCK:
        entry = _STORE.get(key)
        if not entry:
            return None
        if entry.get("expires", 0) < time.time():
            _STORE.pop(key, None)
            return None
        return entry.get("result")


def store_response(key: str, result: Any) -> None:
    """يحفظ الاستجابة لاسترجاعها لاحقاً."""
    if not key:
        return
    with _LOCK:
        _gc_if_needed()
        _STORE[key] = {
            "result": result,
            "expires": time.time() + _TTL_SECONDS,
            "created": time.time(),
        }


def idempotent_replay_or_proceed(request: Request) -> Optional[Any]:
    """
    Helper: إذا الـ Idempotency-Key موجود في الـ headers وقد سبق ورأيناه
    → يُرجِع الاستجابة المخزَّنة (للـ caller أن يُرجعها مباشرة).
    وإلا → يُرجِع None، استكمل المنطق المعتاد ثم نادِ store_response().
    """
    key = get_idempotency_key(request)
    if not key:
        return None
    return get_cached_response(key)
