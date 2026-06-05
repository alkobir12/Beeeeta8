"""
🧠 Context Brief — live workshop snapshot fed to the assistant.

A single endpoint that returns a compact JSON briefing of the workshop's
current state: counts, top customers, top services, active visits, low stock.

Used by the LLM as `context_brief` so it answers questions like "ما هي
الخدمات المتوفرة" or "كم زيارة عندي اليوم" without spawning multiple tools.

100% read-only — never mutates anything.
"""
from __future__ import annotations

from typing import Any, Dict, List

from core.log_utils import get_logger

_log = get_logger("context_brief")


def _supabase():
    try:
        from supabase_service import SupabaseService
        return SupabaseService().client
    except Exception as e:
        _log.warning("supabase unavailable: %s", str(e)[:80])
        return None


async def get_context_brief(*, limit_per_kind: int = 5) -> Dict[str, Any]:
    """Returns a compact briefing of the workshop. ~600 tokens at most."""
    client = _supabase()
    out: Dict[str, Any] = {
        "kind": "workshop_brief",
        "tables": {},
        "samples": {},
        "service_categories": [],
        "low_stock_parts": [],
        "active_visits_count": 0,
    }
    if client is None:
        return {**out, "error": "supabase_unavailable"}

    # 1) Counts per table
    for table in ("customers", "vehicles", "services", "parts"):
        try:
            r = client.table(table).select("id", count="exact").limit(1).execute()
            out["tables"][table] = r.count or 0
        except Exception as e:
            _log.debug("count %s failed: %s", table, str(e)[:60])

    # 2) Active visits (vehicles not in closed statuses)
    try:
        closed = ["مُسلَّمة", "مسلمة", "delivered", "closed", "مكتملة", "archived", "مؤرشف"]
        r = client.table("vehicles").select("id, plate_number, status, customer_name", count="exact").not_.in_("status", closed).limit(limit_per_kind).execute()
        out["active_visits_count"] = r.count or 0
        out["samples"]["active_visits"] = r.data or []
    except Exception as e:
        _log.debug("active_visits failed: %s", str(e)[:80])

    # 3) Service categories
    try:
        r = client.table("services").select("category").eq("active", True).execute()
        rows = r.data or []
        counts: Dict[str, int] = {}
        for row in rows:
            c = row.get("category") or "بدون تصنيف"
            counts[c] = counts.get(c, 0) + 1
        out["service_categories"] = sorted(
            [{"name": k, "count": v} for k, v in counts.items()],
            key=lambda x: x["count"], reverse=True,
        )[:10]
    except Exception as e:
        _log.debug("categories failed: %s", str(e)[:80])

    # 4) Low-stock parts (quantity ≤ min_quantity)
    try:
        r = client.table("parts").select("id, name, quantity, min_quantity, selling_price").limit(50).execute()
        low: List[Dict[str, Any]] = []
        for p in r.data or []:
            q = p.get("quantity") or 0
            mn = p.get("min_quantity") or 0
            if q <= mn and mn > 0:
                low.append(p)
        out["low_stock_parts"] = low[:limit_per_kind]
    except Exception as e:
        _log.debug("low_stock failed: %s", str(e)[:80])

    # 5) Top customers (by ajelBalance)
    try:
        r = client.table("customers").select("id, name, ajelBalance, phone").order("ajelBalance", desc=True).limit(limit_per_kind).execute()
        out["samples"]["top_debtors"] = r.data or []
    except Exception as e:
        _log.debug("top_debtors failed: %s", str(e)[:80])

    return out


def to_llm_brief_text(brief: Dict[str, Any]) -> str:
    """Render the brief as a compact bilingual paragraph for the LLM."""
    tables = brief.get("tables") or {}
    cats = brief.get("service_categories") or []
    active = brief.get("active_visits_count", 0)
    low = brief.get("low_stock_parts") or []
    parts = [
        "📊 لمحة مباشرة عن الورشة:",
        f"• العملاء: {tables.get('customers', '?')} | المركبات: {tables.get('vehicles', '?')} | الخدمات: {tables.get('services', '?')} | القطع: {tables.get('parts', '?')}",
        f"• زيارات نشطة الآن: {active}",
    ]
    if cats:
        cat_str = "، ".join([f"{c['name']} ({c['count']})" for c in cats[:6]])
        parts.append(f"• أهم تصنيفات الخدمات: {cat_str}")
    if low:
        parts.append(f"• قطع بحد أدنى: {', '.join([p.get('name', '?') for p in low[:5]])}")
    return "\n".join(parts)
