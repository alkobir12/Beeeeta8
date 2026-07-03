"""📅 الملخص اليومي — كرت مضغوط ≤5 أسطر، أول رسالة في اليوم لكل مستخدم.

القيود الإلزامية (قرار المستخدم 2026-07-03):
  أ) محتوى حسب الدور: الإيرادات لـ admin فقط؛ الموظف يرى معلقاته فقط.
  ب) الأرقام من استعلامات مباشرة حصراً — لا توليد LLM.
  ج) ≤5 أسطر وقابل للإيقاف من إعدادات المساعد (daily_summary=false في الطلب).
"""
from __future__ import annotations

import os
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from core.log_utils import get_logger, redact

_log = get_logger("daily_summary")

COL = "assistant_daily_state"
_client = None
_db = None
_lock = threading.Lock()


def _database():
    global _client, _db
    if _db is not None:
        return _db
    with _lock:
        if _db is not None:
            return _db
        from pymongo import MongoClient
        _client = MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=3000)
        _db = _client[os.environ["DB_NAME"]]
        _db[COL].create_index("user", unique=True)
        return _db


def _already_shown_today(user: str, today: str) -> bool:
    try:
        doc = _database()[COL].find_one({"user": user})
        return bool(doc and doc.get("last_date") == today)
    except Exception:
        return True  # مخزن غير متاح → لا نكرر المحاولة كل رسالة


def _mark_shown(user: str, today: str) -> None:
    try:
        _database()[COL].update_one({"user": user},
                                    {"$set": {"user": user, "last_date": today}},
                                    upsert=True)
    except Exception:
        pass


async def _yesterday_revenue() -> Optional[Dict[str, Any]]:
    """إيراد الأمس من /api/operations مباشرة (استعلام مباشر — لا LLM)."""
    try:
        import httpx
        from core.tool_router import _int_headers
        base = os.environ.get("INTERNAL_API_BASE", "http://localhost:8001")
        async with httpx.AsyncClient(timeout=8.0, headers=_int_headers()) as client:
            r = await client.get(f"{base}/api/operations", params={"limit": 500})
            ops = r.json() if r.status_code == 200 else []
        if isinstance(ops, dict):
            ops = ops.get("data") or ops.get("items") or []
        y = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        rows = [o for o in ops
                if str(o.get("createdAt") or o.get("created_at") or o.get("date") or "")[:10] == y
                and str(o.get("type") or "").lower() not in ("purchase", "مشتريات")]
        return {"total": round(sum(float(o.get("total") or 0) for o in rows), 2),
                "count": len(rows)}
    except Exception as e:
        _log.warning("yesterday revenue failed: %s", redact(str(e), max_len=80))
        return None


async def _open_findings_count() -> Optional[int]:
    try:
        import httpx
        from core.tool_router import _int_headers
        base = os.environ.get("INTERNAL_API_BASE", "http://localhost:8001")
        async with httpx.AsyncClient(timeout=5.0, headers=_int_headers()) as client:
            r = await client.get(f"{base}/api/financial-control/findings",
                                 params={"status": "open", "limit": 100})
            body = r.json() if r.status_code == 200 else {}
        rows = (body.get("data") or body.get("items") or []) if isinstance(body, dict) else []
        return len(rows)
    except Exception:
        return None


async def build_daily_summary(*, user: Optional[str], role: Optional[str]) -> Optional[str]:
    """يرجع نص الملخص (≤5 أسطر) أو None إن سبق عرضه اليوم / لا مستخدم."""
    if not user:
        return None
    today = datetime.now().strftime("%Y-%m-%d")
    if _already_shown_today(user, today):
        return None
    role_l = (role or "").strip().lower()
    from core import action_runtime
    from core.rbac import APPROVER_ROLES
    pending = action_runtime.list_approvals(status="pending", limit=100)
    mine = [a for a in pending if a.get("proposer") == user]
    is_approver = role_l in APPROVER_ROLES
    for_me = [a for a in pending if a.get("proposer") != user] if is_approver else []

    lines = [f"📅 **الملخص اليومي — {today}**"]
    if role_l == "admin":
        rev = await _yesterday_revenue()
        if rev is not None:
            lines.append(f"💰 إيرادات الأمس: **{rev['total']:,.2f} ر.س** ({rev['count']} عملية)")
    if is_approver:
        lines.append(f"⏳ اعتمادات معلقة: **{len(pending)}** — منها **{len(for_me)}** بانتظار قرارك")
    if mine:
        lines.append(f"📝 مسوداتك المعلقة: **{len(mine)}** (تنتظر معتمداً آخر)")
    if role_l == "admin":
        fc = await _open_findings_count()
        if fc is not None:
            lines.append(f"🕵️ ملاحظات مدقق مفتوحة: **{fc}**")
    if len(lines) == 1:
        lines.append("✨ لا معلقات لديك — يوم موفق!")
    _mark_shown(user, today)
    return "\n".join(lines[:5])
