"""🕵️ مدقق المسودات — فحوصات ما قبل الاعتماد (يشمل مدقق النظام المالي).

يفحص كل مسودة مالية قبل عرضها للاعتماد ويرجع ملاحظات نصية تُعرض داخل
بطاقة الاعتماد: مبلغ شاذ، تكرار محتمل مع عملية منفذة حديثاً، وملاحظات
التدقيق المفتوحة في مركز التحكم المالي (AuditRulesEngine).
"""
import time
from typing import Any, Dict, List, Optional

HIGH_AMOUNT_THRESHOLD = 50000.0


def _norm(s: Any) -> str:
    try:
        from core.arabic_nlp import normalize_arabic
        return normalize_arabic(str(s or "").strip()).lower()
    except Exception:
        return str(s or "").strip().lower()


def _amount_of(payload: Dict[str, Any]) -> float:
    echo = payload.get("_echo") or {}
    for src in (echo, payload):
        for k in ("amount", "total", "gross"):
            try:
                f = float(src.get(k))
                if f:
                    return f
            except (TypeError, ValueError):
                continue
    return 0.0


def _entity_of(payload: Dict[str, Any]) -> str:
    echo = payload.get("_echo") or {}
    ent = echo.get("entity")
    if not ent:
        sup = payload.get("supplier")
        ent = ((sup.get("name") if isinstance(sup, dict) else sup)
               or payload.get("customer") or payload.get("name"))
    return _norm(ent)


def _stock_guard_notes(payload: Dict[str, Any]) -> List[str]:
    """📦 L11: تحذير حاجب عند بيع كمية أكبر من المخزون المتاح لقطعة معروفة."""
    notes: List[str] = []
    echo = payload.get("_echo") or {}
    items = payload.get("items") or echo.get("items") or []
    if not isinstance(items, list) or not items:
        return notes
    try:
        from supabase_service import SupabaseService
        supa = SupabaseService()
        parts = supa.client.table("parts").select("name,quantity").limit(2000).execute().data or []
    except Exception:
        return notes
    for it in items:
        if not isinstance(it, dict):
            continue
        name = str(it.get("name") or "").strip()
        try:
            qty = float(it.get("qty") or it.get("quantity") or 1)
        except (TypeError, ValueError):
            qty = 1
        if not name or qty <= 0:
            continue
        nn = _norm(name)
        match = next((p for p in parts if nn and (nn in _norm(p.get("name")) or _norm(p.get("name")) in nn)), None)
        if match is not None:
            available = float(match.get("quantity") or 0)
            if qty > available:
                notes.append(
                    f"⛔ مخزون غير كافٍ: «{match.get('name')}» المتاح {available:g} والمطلوب {qty:g} — "
                    "المخزون لا يصبح سالباً، راجع قبل الاعتماد")
    return notes


def audit_draft(runtime_action: str, payload: Dict[str, Any],
                *, draft_id: Optional[str] = None) -> List[str]:
    """فحوصات متزامنة خفيفة (بدون شبكة)."""
    notes: List[str] = []
    try:
        amount = _amount_of(payload)
        entity = _entity_of(payload)
        if amount <= 0:
            notes.append("🔴 المبلغ صفر أو سالب — راجع قبل الاعتماد")
        elif amount >= HIGH_AMOUNT_THRESHOLD:
            notes.append(f"⚠️ مبلغ مرتفع ({amount:,.0f} ر.س) — يتجاوز عتبة التنبيه")
        # 📦 حارس المخزون: بيع كمية أكبر من المتاح لا يجوز أن يمر بصمت (L11)
        if runtime_action == "invoice":
            notes.extend(_stock_guard_notes(payload))
        # تكرار محتمل: عملية بنفس الجهة والمبلغ نُفذت خلال آخر 24 ساعة
        from core import action_runtime
        cutoff = time.time() - 24 * 3600
        for d in action_runtime.list_drafts(status=None, limit=100):
            if draft_id and d.get("id") == draft_id:
                continue
            if d.get("action") != runtime_action:
                continue
            if d.get("status") not in ("committed", "approved"):
                continue
            if (d.get("created_at") or 0) < cutoff:
                continue
            p2 = d.get("payload") or {}
            if (amount > 0 and abs(_amount_of(p2) - amount) < 0.01
                    and _entity_of(p2) == entity):
                notes.append("⚠️ تكرار محتمل: عملية مماثلة (نفس الجهة والمبلغ) نُفذت خلال آخر 24 ساعة")
                break
    except Exception:
        pass
    return notes


async def audit_draft_with_findings(runtime_action: str, payload: Dict[str, Any],
                                    *, draft_id: Optional[str] = None) -> List[str]:
    """الفحوصات الخفيفة + ملاحظات مدقق النظام (AuditRulesEngine) المفتوحة."""
    notes = audit_draft(runtime_action, payload, draft_id=draft_id)
    try:
        import os
        import httpx
        from core.tool_router import _int_headers
        base = os.environ.get("INTERNAL_API_BASE", "http://localhost:8001")
        async with httpx.AsyncClient(timeout=5.0, headers=_int_headers()) as client:
            r = await client.get(f"{base}/api/financial-control/findings",
                                 params={"status": "open", "limit": 100})
            body = r.json() if r.status_code == 200 else {}
        rows = (body.get("data") or body.get("items") or []) if isinstance(body, dict) else []
        entity = _entity_of(payload)
        related = []
        if entity and rows:
            from core.arabic_nlp import arabic_match
            related = [f for f in rows
                       if arabic_match(entity, f.get("title"), f.get("description"))]
        if related:
            notes.append(f"🕵️ مدقق النظام: {len(related)} ملاحظة تدقيق مفتوحة تخص نفس الجهة — راجع مركز التحكم المالي")
        elif rows:
            notes.append(f"🕵️ مدقق النظام: {len(rows)} ملاحظة تدقيق مفتوحة على مستوى النظام")
    except Exception:
        pass
    return notes
