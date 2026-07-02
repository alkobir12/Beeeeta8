"""
🛠️ Tool Router — توجيه الأدوات إلى الوكلاء المختصين

يحوّل intent المستخدم → وكيل + أداة. مثلاً:
  "أعطني درجة الصحة المالية" → FirewallAgent.get_health_score()
  "كم بقي للعميل سلطان؟"    → FinanceAgent.get_customer_balance(name="سلطان")
  "ابحث عن مركبة 123"       → WorkshopAgent.find_vehicle(plate="123")

كل أداة:
  • metadata: name, description, agent
  • handler: callable async
  • params: schema للتحقق
"""

from __future__ import annotations
from typing import Any, Awaitable, Callable, Dict, List, Optional


# ---------- Tool registry ----------

_TOOLS: Dict[str, Dict[str, Any]] = {}


# 🛡️ Phase 3A — Write contract
#
# Every tool registered into the floating bot is read-only by default. To
# register a write-capable tool the operator MUST set BOT_ALLOW_WRITES=1 in
# the environment. The flag is read at call-time (not import-time) so tests
# can flip it cleanly.
import os as _os


def _writes_allowed() -> bool:
    """Returns True iff write tools are allowed to be registered AND invoked."""
    return _os.environ.get("BOT_ALLOW_WRITES", "0").lower() in ("1", "true", "yes", "on")


class WriteToolBlockedError(RuntimeError):
    """Raised when a write tool is registered or invoked while the flag is off."""


# 🔐 auth_guard يفرض JWT على كل /api/* — أدوات البوت تستدعي API داخلياً،
# لذا نصكّ توكن خدمة موقّعاً (نفس السر) ونرفقه بكل استدعاء داخلي.
_INT_TOKEN: Dict[str, Any] = {"token": None, "exp": 0.0}


def _int_headers() -> Dict[str, str]:
    import time
    now = time.time()
    if not _INT_TOKEN["token"] or now > _INT_TOKEN["exp"]:
        from auth_jwt import create_access_token
        _INT_TOKEN["token"] = create_access_token("katrina-internal", role="admin")
        _INT_TOKEN["exp"] = now + 30 * 60
    return {"Authorization": f"Bearer {_INT_TOKEN['token']}"}


def register_tool(
    name: str,
    *,
    agent: str,
    description: str,
    handler: Callable[..., Awaitable[Any]],
    params: Optional[Dict[str, Any]] = None,
    write: bool = False,
) -> None:
    """Registers a tool in the router.

    Phase 3A contract:
      • `write=False` (default) — read-only, always allowed.
      • `write=True` — must also have `BOT_ALLOW_WRITES=1` in env, otherwise
        `WriteToolBlockedError` is raised at registration time.
    """
    if write and not _writes_allowed():
        raise WriteToolBlockedError(
            f"Cannot register write-capable tool '{name}' while "
            "BOT_ALLOW_WRITES != '1'. This is a Phase 3A safety contract."
        )
    _TOOLS[name] = {
        "name": name,
        "agent": agent,
        "description": description,
        "handler": handler,
        "params": params or {},
        "write": bool(write),
    }


def list_tools(agent: Optional[str] = None) -> List[Dict[str, Any]]:
    out = []
    for t in _TOOLS.values():
        if agent and t["agent"] != agent:
            continue
        out.append({
            "name": t["name"],
            "agent": t["agent"],
            "description": t["description"],
            "params": t["params"],
            "write": t.get("write", False),
        })
    return out


def is_write_tool(name: str) -> bool:
    """Returns True iff the named tool is registered with `write=True`."""
    t = _TOOLS.get(name)
    return bool(t and t.get("write"))


async def call_tool(name: str, **kwargs) -> Dict[str, Any]:
    tool = _TOOLS.get(name)
    if not tool:
        return {"success": False, "error": f"tool not found: {name}"}
    # 🛡️ Phase 3A — runtime guard. Even if a write tool slipped past
    # registration (shouldn't happen), block the invocation here too.
    if tool.get("write") and not _writes_allowed():
        return {
            "success": False,
            "tool": name,
            "error": (
                "write tool invocation blocked: BOT_ALLOW_WRITES != '1' "
                "(Phase 3A read-only contract)"
            ),
        }
    try:
        result = await tool["handler"](**kwargs)
        return {"success": True, "tool": name, "agent": tool["agent"], "result": result, "write": tool.get("write", False)}
    except Exception as e:
        import traceback
        return {"success": False, "tool": name, "error": str(e), "trace": traceback.format_exc()[-400:]}


# ---------- Built-in tools (FinanceAgent / WorkshopAgent / FirewallAgent) ----------

async def _firewall_health_score(workshop_id: str = "finmodule-sync") -> Dict[str, Any]:
    from firewall_engine import FirewallEngine
    engine = FirewallEngine(workshop_id=workshop_id)
    analysis = engine.run_full_analysis()
    return {
        "score": analysis["health"]["score"],
        "status": analysis["health"]["status"],
        "alerts_count": analysis["alerts_count"],
        "counts_by_severity": analysis["counts_by_severity"],
    }


async def _firewall_top_alerts(workshop_id: str = "finmodule-sync", limit: int = 5) -> List[Dict[str, Any]]:
    from firewall_engine import FirewallEngine
    engine = FirewallEngine(workshop_id=workshop_id)
    analysis = engine.run_full_analysis()
    alerts = analysis.get("alerts", [])[:limit]
    return [{
        "id": a.get("id"),
        "title": a.get("title"),
        "severity": a.get("severity"),
        "category": a.get("category"),
        "financial_impact": a.get("financial_impact"),
        "description": a.get("description"),
    } for a in alerts]


async def _firewall_cash_flow(workshop_id: str = "finmodule-sync") -> Dict[str, Any]:
    from firewall_engine import FirewallEngine
    engine = FirewallEngine(workshop_id=workshop_id)
    return engine.run_full_analysis()["cash_flow"]


async def _finance_ar_summary(workshop_id: str = "finmodule-sync") -> Dict[str, Any]:
    """ملخص ذمم العملاء."""
    import os
    if os.getenv("DB_PROVIDER", "mongo").lower() != "supabase":
        return {"error": "Supabase not enabled"}
    from supabase_service import SupabaseService
    SupabaseService()  # verify supabase is reachable
    import httpx
    base = os.getenv("BACKEND_INTERNAL_URL") or "http://localhost:8001"
    try:
        async with httpx.AsyncClient(timeout=10, headers=_int_headers()) as client:
            r = await client.get(f"{base}/api/customers")
            customers = r.json() if r.status_code == 200 else []
    except Exception:
        customers = []
    debtors = [c for c in customers if float(c.get("ajelBalance") or 0) > 0]
    total = sum(float(c.get("ajelBalance") or 0) for c in debtors)
    top = sorted(debtors, key=lambda x: float(x.get("ajelBalance") or 0), reverse=True)[:5]
    return {
        "total_customers_with_debt": len(debtors),
        "total_ar": round(total, 2),
        "top_debtors": [{"name": c.get("name"), "balance": float(c.get("ajelBalance") or 0)} for c in top],
    }


async def _accounting_journal_entries(workshop_id: str = "finmodule-sync", limit: int = 15, query: str = "") -> Dict[str, Any]:
    """📒 القيود المحاسبية الفعلية (دفتر اليومية) من جدول journal_entries.

    يرجع العدد الكلي + إجمالي المدين/الدائن + آخر القيود. هذه بيانات حقيقية من
    قاعدة البيانات — تمنع البوت من اختلاق قيود افتراضية أو إنكار وجود المحاسبة.
    """
    import os
    import httpx
    base = os.getenv("BACKEND_INTERNAL_URL") or os.getenv("INTERNAL_API_BASE") or "http://localhost:8001"
    try:
        n = max(1, min(int(limit or 15), 100))
    except Exception:
        n = 15
    try:
        async with httpx.AsyncClient(timeout=15.0, headers=_int_headers()) as client:
            r = await client.get(
                f"{base}/api/finance/journal-entries",
                params={"workshop_id": workshop_id or "finmodule-sync", "limit": n},
            )
            payload = r.json() if r.status_code == 200 else {}
    except Exception as e:
        return {"error": str(e)}
    entries = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        entries = []
    if query:
        from core.arabic_nlp import arabic_match
        entries = [
            e for e in entries
            if arabic_match(query, e.get("description"), e.get("party_label"),
                            e.get("vehicle_label"), e.get("date"),
                            e.get("transaction_type_label_ar"))
        ]
    total_debit = 0.0
    total_credit = 0.0
    for e in entries:
        for ln in (e.get("lines") or []):
            try:
                total_debit += float(ln.get("debit") or 0)
                total_credit += float(ln.get("credit") or 0)
            except Exception:
                pass
    items = [{
        "id": e.get("id"),
        "date": e.get("date"),
        "description": e.get("description"),
        "party": e.get("party_label"),
        "type": e.get("transaction_type_label_ar") or e.get("operation_type_label"),
        "total": e.get("total"),
        "payment_status": e.get("payment_status_label_ar"),
    } for e in entries[: min(n, 50)]]
    return {
        "count": len(entries),
        "total_debit": round(total_debit, 2),
        "total_credit": round(total_credit, 2),
        "balanced": abs(total_debit - total_credit) < 0.01,
        "entries": items,
    }


async def _workshop_active_visits(workshop_id: str = "finmodule-sync") -> Dict[str, Any]:
    """عدد الزيارات النشطة (مفتوحة)."""
    import os
    if os.getenv("DB_PROVIDER", "mongo").lower() != "supabase":
        return {"error": "Supabase not enabled"}
    from supabase_service import SupabaseService
    supa = SupabaseService()
    try:
        rows = supa.client.table("vehicle_visits").select("id, status, vehicle_id").execute().data or []
    except Exception as e:
        return {"error": str(e)}
    active = [r for r in rows if str(r.get("status") or "").lower() not in {"delivered", "closed", "cancelled"}]
    return {"active_visits": len(active), "total_visits": len(rows)}


async def _customers_search(workshop_id: str = "finmodule-sync", query: str = "", limit: int = 5) -> Dict[str, Any]:
    """🔍 بحث ذكي عن عميل بالاسم أو الهاتف (يرجع أعلى المطابقات + رصيد الذمم)."""
    import os
    import httpx
    base = os.environ.get("INTERNAL_API_BASE", "http://localhost:8001")
    try:
        async with httpx.AsyncClient(timeout=15.0, headers=_int_headers()) as client:
            params = {"search": query} if query else {}
            r = await client.get(f"{base}/api/customers", params=params)
            customers = r.json() if r.status_code == 200 else []
    except Exception as e:
        return {"error": str(e)}
    if not isinstance(customers, list):
        customers = []
    # filter additionally if query did not propagate — Arabic-tolerant matching
    # (handles hamza/alef variants, taa-marbuta, definite article, nicknames/kunya)
    if query:
        from core.arabic_nlp import arabic_match
        filtered = [
            c for c in customers
            if arabic_match(query, c.get("name"), c.get("phone"),
                            c.get("vehiclePlate"), c.get("fileNumber"))
        ]
        # Fallback: the server-side `search` param may have over-filtered (e.g.
        # it matched the raw hamza form). Refetch ALL and match locally so a
        # nickname like "ابو مصري" / "أبو المصري" still resolves.
        if not filtered:
            try:
                async with httpx.AsyncClient(timeout=15.0, headers=_int_headers()) as client:
                    r2 = await client.get(f"{base}/api/customers")
                    all_customers = r2.json() if r2.status_code == 200 else []
                if isinstance(all_customers, list):
                    filtered = [
                        c for c in all_customers
                        if arabic_match(query, c.get("name"), c.get("phone"),
                                        c.get("vehiclePlate"), c.get("fileNumber"))
                    ]
            except Exception:
                pass
        customers = filtered
    customers = customers[:limit]
    from core.card_builder import cards_from_customers
    return {
        "query": query,
        "matches": [{
            "id": (c.get("id") or "")[:8],
            "name": c.get("name"),
            "phone": c.get("phone"),
            "ajel_balance": float(c.get("ajelBalance") or 0),
            "total_visits": c.get("totalVisits") or 0,
            "vehicle_plate": c.get("vehiclePlate"),
        } for c in customers],
        "count": len(customers),
        "cards": cards_from_customers(customers, limit=limit),
    }


async def _vehicles_search(workshop_id: str = "finmodule-sync", query: str = "", limit: int = 5) -> Dict[str, Any]:
    """🚗 بحث عن مركبة برقم اللوحة/الموديل/الماركة."""
    import os
    import httpx
    base = os.environ.get("INTERNAL_API_BASE", "http://localhost:8001")
    try:
        async with httpx.AsyncClient(timeout=15.0, headers=_int_headers()) as client:
            r = await client.get(f"{base}/api/vehicles")
            vehicles = r.json() if r.status_code == 200 else []
    except Exception as e:
        return {"error": str(e)}
    if not isinstance(vehicles, list):
        vehicles = []
    q = (query or "").strip()
    if q:
        from core.arabic_nlp import arabic_match
        vehicles = [
            v for v in vehicles
            if arabic_match(
                q,
                v.get("plateNumber"), v.get("plate"), v.get("model"), v.get("brand"),
                v.get("customerName"), v.get("ownerName"),
            )
        ]
    vehicles = vehicles[:limit]
    from core.card_builder import cards_from_vehicles
    return {
        "query": query,
        "matches": [{
            "id": (v.get("id") or "")[:8],
            "plate": v.get("plateNumber") or v.get("plate"),
            "brand": v.get("brand"),
            "model": v.get("model"),
            "year": v.get("year"),
            "status": v.get("status") or v.get("visitStatus"),
            "owner": v.get("customerName") or v.get("ownerName"),
        } for v in vehicles],
        "count": len(vehicles),
        "cards": cards_from_vehicles(vehicles, limit=limit),
    }


async def _parts_search(workshop_id: str = "finmodule-sync", query: str = "", limit: int = 8, in_stock_only: bool = False) -> Dict[str, Any]:
    """🔧 بحث ذكي في المخزون بكلمات اسم/تصنيف القطعة — يرجع السعر+الكمية مرتبة (المتوفر أولاً)."""
    import os
    import httpx
    base = os.environ.get("INTERNAL_API_BASE", "http://localhost:8001")
    try:
        async with httpx.AsyncClient(timeout=15.0, headers=_int_headers()) as client:
            r = await client.get(f"{base}/api/parts")
            parts = r.json() if r.status_code == 200 else []
    except Exception as e:
        return {"error": str(e)}
    if not isinstance(parts, list):
        parts = []

    q = (query or "").lower().strip()
    matches: List[tuple] = []  # (score, qty>0 flag, part)

    if q:
        # Tokenize the query so multi-word searches still hit ("فلتر زيت" → ["فلتر","زيت"])
        tokens = [t for t in q.split() if len(t) >= 2]
        for p in parts:
            name = str(p.get("name") or "").lower()
            sku = str(p.get("partNumber") or "").lower()
            cat = str(p.get("category") or "").lower()
            haystack = f"{name} ## {sku} ## {cat}"
            score = sum(1 for t in tokens if t in haystack)
            if score > 0:
                qty_flag = 1 if float(p.get("quantity") or 0) > 0 else 0
                matches.append((score, qty_flag, p))
        # in-stock first within the same score
        matches.sort(key=lambda x: (x[0], x[1]), reverse=True)
        ranked = [m[2] for m in matches]
    else:
        # No keyword → highest-stock items
        ranked = sorted(parts, key=lambda x: float(x.get("quantity") or 0), reverse=True)

    if in_stock_only:
        ranked = [p for p in ranked if float(p.get("quantity") or 0) > 0]

    ranked = ranked[:max(limit, 1)]
    in_stock = [p for p in ranked if float(p.get("quantity") or 0) > 0]

    from core.card_builder import cards_from_parts
    return {
        "query": query,
        "total_inventory": len(parts),
        "matches_count": len(ranked),
        "in_stock_count": len(in_stock),
        "items": [{
            "name": p.get("name"),
            "sku": p.get("partNumber"),
            "category": p.get("category"),
            "selling_price": float(p.get("sellingPrice") or 0),
            "quantity": float(p.get("quantity") or 0),
            "in_stock": float(p.get("quantity") or 0) > 0,
        } for p in ranked],
        "next_action_hint": "لإصدار فاتورة بيع → افتح /operations ثم 'نقطة بيع'.",
        "cards": cards_from_parts(ranked, limit=limit),
    }


async def _inventory_low_stock(workshop_id: str = "finmodule-sync", limit: int = 10) -> Dict[str, Any]:
    """📦 القطع التي مخزونها أقل من الحد الأدنى (low-stock alert)."""
    import os
    import httpx
    base = os.environ.get("INTERNAL_API_BASE", "http://localhost:8001")
    try:
        async with httpx.AsyncClient(timeout=15.0, headers=_int_headers()) as client:
            r = await client.get(f"{base}/api/parts")
            parts = r.json() if r.status_code == 200 else []
    except Exception as e:
        return {"error": str(e)}
    if not isinstance(parts, list):
        parts = []
    low = []
    for p in parts:
        qty = float(p.get("quantity") or p.get("stock") or 0)
        minq = float(p.get("minQuantity") or p.get("minStock") or 0)
        if minq > 0 and qty <= minq:
            low.append({
                "name": p.get("name") or p.get("partName"),
                "sku": p.get("sku") or p.get("partNumber"),
                "quantity": qty,
                "min_quantity": minq,
                "shortage": round(minq - qty, 2),
            })
    low.sort(key=lambda x: x["shortage"], reverse=True)
    from core.card_builder import cards_from_parts
    return {
        "total_parts": len(parts),
        "low_stock_count": len(low),
        "items": low[:limit],
        "cards": cards_from_parts(low, limit=limit),
    }


async def _finance_payables_summary(workshop_id: str = "finmodule-sync", limit: int = 5) -> Dict[str, Any]:
    """💼 ملخص ذمم الموردين (Accounts Payable) + أعلى الموردين دائنية."""
    import os
    import httpx
    base = os.environ.get("INTERNAL_API_BASE", "http://localhost:8001")
    try:
        async with httpx.AsyncClient(timeout=15.0, headers=_int_headers()) as client:
            r = await client.get(f"{base}/api/suppliers")
            suppliers = r.json() if r.status_code == 200 else []
    except Exception as e:
        return {"error": str(e)}
    if not isinstance(suppliers, list):
        suppliers = []
    creditors = [s for s in suppliers if float(s.get("ajelBalance") or s.get("balance") or 0) > 0]
    total = sum(float(s.get("ajelBalance") or s.get("balance") or 0) for s in creditors)
    top = sorted(creditors, key=lambda x: float(x.get("ajelBalance") or x.get("balance") or 0), reverse=True)[:limit]
    from core.card_builder import cards_from_suppliers
    return {
        "total_suppliers_with_balance": len(creditors),
        "total_ap": round(total, 2),
        "top_creditors": [{
            "name": s.get("name"),
            "balance": float(s.get("ajelBalance") or s.get("balance") or 0),
        } for s in top],
        "cards": cards_from_suppliers(top, limit=limit),
    }


async def _operations_recent(workshop_id: str = "finmodule-sync", limit: int = 5) -> Dict[str, Any]:
    """🧾 آخر العمليات (sales/purchases/expenses) مع المبلغ والعميل/المورد."""
    import os
    import httpx
    base = os.environ.get("INTERNAL_API_BASE", "http://localhost:8001")
    try:
        async with httpx.AsyncClient(timeout=15.0, headers=_int_headers()) as client:
            r = await client.get(f"{base}/api/operations", params={"limit": max(limit, 5)})
            ops = r.json() if r.status_code == 200 else []
    except Exception as e:
        return {"error": str(e)}
    if isinstance(ops, dict):
        ops = ops.get("data") or ops.get("items") or []
    if not isinstance(ops, list):
        ops = []
    ops = ops[:limit]
    from core.card_builder import cards_from_operations
    return {
        "count": len(ops),
        "items": [{
            "invoice_number": o.get("invoiceNumber") or o.get("invoice_number") or "",
            "type": o.get("type"),
            "total": float(o.get("total") or 0),
            "payment_method": o.get("paymentMethod") or o.get("payment_method"),
            "payment_status": o.get("paymentStatus") or o.get("payment_status"),
            "partner": o.get("partnerName") or o.get("customerName") or o.get("supplierName"),
            "date": o.get("createdAt") or o.get("created_at") or o.get("date"),
        } for o in ops],
        "cards": cards_from_operations(ops, limit=limit),
    }


# 🗓️ فهم النطاق الزمني العربي («قبل شهر»، «الشهر الماضي»، «آخر اسبوع»...)
_AR_UNIT_DAYS = {
    "يوم": 1, "ايام": 1, "أيام": 1, "يومين": 2,
    "اسبوع": 7, "أسبوع": 7, "اسابيع": 7, "أسابيع": 7, "اسبوعين": 14, "أسبوعين": 14,
    "شهر": 30, "شهور": 30, "اشهر": 30, "أشهر": 30, "شهرين": 60,
    "سنه": 365, "سنة": 365,
}


def _extract_date_range(q: str):
    """يرجع (start_dt, end_dt, cleaned_query) أو None إذا لا توجد إشارة زمنية."""
    import re as _re
    from datetime import datetime, timedelta
    t = q or ""
    now = datetime.now()

    def _clean(rgx):
        return _re.sub(rgx, " ", t, flags=_re.IGNORECASE).strip(" ،,")

    m = _re.search(r"الشهر\s+(?:الماضي|اللي\s+فات|السابق)", t)
    if m:
        first_this = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        start = (first_this - timedelta(days=1)).replace(day=1)
        return start, first_this, _clean(r"الشهر\s+(?:الماضي|اللي\s+فات|السابق)")
    m = _re.search(r"(?:الاسبوع|الأسبوع)\s+(?:الماضي|اللي\s+فات|السابق)", t)
    if m:
        return now - timedelta(days=14), now - timedelta(days=7), _clean(
            r"(?:الاسبوع|الأسبوع)\s+(?:الماضي|اللي\s+فات|السابق)")
    m = _re.search(r"هذا\s+الشهر|الشهر\s+الحالي", t)
    if m:
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0), now, _clean(
            r"هذا\s+الشهر|الشهر\s+الحالي")
    if _re.search(r"(?:^|\s)(?:امس|أمس|البارح[ةه]?)(?:\s|$)", t):
        y = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return y, y + timedelta(days=1), _clean(r"(?:امس|أمس|البارح[ةه]?)")
    if _re.search(r"(?:^|\s)اليوم(?:\s|$)", t):
        return now.replace(hour=0, minute=0, second=0, microsecond=0), now, _clean(r"اليوم")
    unit_re = "|".join(_AR_UNIT_DAYS)
    m = _re.search(rf"(?:آخر|اخر|خلال)\s*(\d+)?\s*({unit_re})", t)
    if m:
        days = _AR_UNIT_DAYS[m.group(2)] * (int(m.group(1)) if m.group(1) else 1)
        return now - timedelta(days=days), now, _clean(rf"(?:آخر|اخر|خلال)\s*\d*\s*(?:{unit_re})")
    m = _re.search(rf"قبل\s*(\d+)?\s*({unit_re})", t)
    if m:
        days = _AR_UNIT_DAYS[m.group(2)] * (int(m.group(1)) if m.group(1) else 1)
        margin = max(3, int(days * 0.25))
        center = now - timedelta(days=days)
        return center - timedelta(days=margin), center + timedelta(days=margin), _clean(
            rf"قبل\s*\d*\s*(?:{unit_re})")
    return None


def _parse_op_dt(o: Dict[str, Any]):
    from datetime import datetime
    s = str(o.get("createdAt") or o.get("created_at") or o.get("date") or "")
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        try:
            return datetime.fromisoformat(s[:19])
        except Exception:
            return None


async def _operations_search(workshop_id: str = "finmodule-sync", query: str = "", limit: int = 10) -> Dict[str, Any]:
    """🔍 بحث عمليات بالاسم/النوع + نطاق زمني عربي («قبل شهر»، «الشهر الماضي»...)."""
    import os
    import httpx
    q = (query or "").strip()
    date_range = _extract_date_range(q)
    fetch_limit = 500 if date_range else 200
    base = os.environ.get("INTERNAL_API_BASE", "http://localhost:8001")
    try:
        async with httpx.AsyncClient(timeout=15.0, headers=_int_headers()) as client:
            r = await client.get(f"{base}/api/operations", params={"limit": fetch_limit})
            ops = r.json() if r.status_code == 200 else []
    except Exception as e:
        return {"error": str(e)}
    if isinstance(ops, dict):
        ops = ops.get("data") or ops.get("items") or []
    if not isinstance(ops, list):
        ops = []
    period_label = None
    if date_range:
        start_dt, end_dt, q = date_range
        # إزالة أفعال/حشو زمني متبقٍ حتى لا تفلتر النتائج بالاسم خطأً
        import re as _re0
        q = _re0.sub(
            r"(?:^|\s)(?:صار|صارت|تم|تمت|حدث|حدثت|سوّ?يت|سوت|كان|كانت|اللي|التي|الذي|فيه|عندنا|لدينا|موجود[ةه]?)(?=\s|$)",
            " ", q)
        q = " ".join(q.split())
        period_label = f"{start_dt:%Y-%m-%d} → {end_dt:%Y-%m-%d}"
        ops = [o for o in ops
               if (lambda d: d is not None and start_dt <= d <= end_dt)(_parse_op_dt(o))]
    if q:
        import re as _re
        from core.arabic_nlp import arabic_match, extract_entities

        def _norm_inv(s):
            return _re.sub(r"[\s\-#]", "", str(s or "")).lower()

        inv_tokens = [_norm_inv(t) for t in (extract_entities(q).get("invoice") or []) if t]
        matched = []
        if inv_tokens:
            for o in ops:
                inv = _norm_inv(o.get("invoiceNumber") or o.get("invoice_number"))
                if inv and any(t in inv for t in inv_tokens):
                    matched.append(o)
        if matched:
            ops = matched
        else:
            # كلمات عامة (فاتورة/عملية/رقم) لا يجب أن تُشترط في حقول العملية نفسها
            q2 = _re.sub(r"(فاتورة|فاتوره|عملية|عمليه|رقم|invoice|inv)", " ", q, flags=_re.IGNORECASE)
            q2 = _re.sub(r"\s+", " ", q2).strip() or q
            ops = [
                o for o in ops
                if arabic_match(
                    q2,
                    o.get("partnerName"), o.get("customerName"), o.get("supplierName"),
                    o.get("notes"), o.get("description"), o.get("type"),
                    o.get("invoiceNumber"), o.get("invoice_number"),
                )
            ]
    ops = ops[:limit]
    from core.card_builder import cards_from_operations
    total_amount = sum(float(o.get("total") or 0) for o in ops)
    return {
        "query": query,
        "period": period_label,
        "count": len(ops),
        "total_amount": round(total_amount, 2),
        "items": [{
            "invoice_number": o.get("invoiceNumber") or o.get("invoice_number") or "",
            "type": o.get("type"),
            "total": float(o.get("total") or 0),
            "payment_method": o.get("paymentMethod") or o.get("payment_method"),
            "payment_status": o.get("paymentStatus") or o.get("payment_status"),
            "partner": o.get("partnerName") or o.get("customerName") or o.get("supplierName"),
            "date": o.get("createdAt") or o.get("created_at") or o.get("date"),
            "notes": (o.get("notes") or "")[:100],
        } for o in ops],
        "cards": cards_from_operations(ops, limit=limit),
    }


async def _firewall_operation_integrity(workshop_id: Optional[str] = None, limit: int = 20) -> Dict[str, Any]:
    """🆕 يفحص العمليات ويُرجع التي بها مشاكل ربط/تنبيهات (per-card warnings)."""
    try:
        import os
        import httpx
        base = os.environ.get("INTERNAL_API_BASE", "http://localhost:8001")
        async with httpx.AsyncClient(timeout=15.0, headers=_int_headers()) as client:
            r = await client.post(f"{base}/api/operations/integrity/check", json={})
            result = r.json()
    except Exception as e:
        return {"error": str(e)}

    data = result.get("data", result) if isinstance(result, dict) else {}
    items = data.get("items") or []
    flagged = [i for i in items if i.get("warnings")]
    summary = data.get("summary") or {}
    sample = []
    for f in flagged[:limit]:
        sample.append({
            "operation_id": (f.get("op_id") or f.get("id") or "")[:8],
            "invoice_number": f.get("invoice_number") or "",
            "label": f.get("display_label"),
            "warnings": f.get("warnings"),
            "status": f.get("status"),
            "duplicate_group_size": f.get("duplicate_group_size"),
        })
    from core.card_builder import finding_card

    def _warn_code(w):
        return w.get("code", "") if isinstance(w, dict) else str(w)

    def _warn_msg(w):
        return w.get("message", w.get("code", "")) if isinstance(w, dict) else str(w)

    cards = [finding_card({
        "type": "warning",
        "title": f"عملية {s.get('operation_id','')} — {', '.join(_warn_code(w) for w in (s.get('warnings') or []))}",
        "description": "; ".join(_warn_msg(w) for w in (s.get("warnings") or [])),
        "severity": "warning",
        "link": "/accounting/firewall",
    }) for s in sample if s.get("warnings")]
    return {
        "total_operations": summary.get("total") or len(items),
        "ok": summary.get("ok"),
        "with_warnings": summary.get("warnings") or len(flagged),
        "duplicates": summary.get("duplicates"),
        "sample": sample,
        "cards": cards,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 🆕 Phase 3C.5 — Natural Language Search + Approval / Audit / WhatsApp tools
# ─────────────────────────────────────────────────────────────────────────────


async def _nl_search(workshop_id: str = "finmodule-sync", query: str = "", limit: int = 5) -> Dict[str, Any]:
    """🧠 Natural Language Search — يفهم استعلامات معقدة بالعربية ويُرجع البطاقات المناسبة.

    أمثلة:
      • "أكثر العملاء مديونية"          → top debtors → CustomerCards
      • "الفواتير المتأخرة"            → overdue invoices → InvoiceCards
      • "أقل المركبات نشاطاً"          → idle vehicles → VehicleCards
      • "آخر العمليات الكبيرة"          → biggest recent ops → InvoiceCards
    """
    import os
    import httpx
    base = os.environ.get("INTERNAL_API_BASE", "http://localhost:8001")
    q = (query or "").strip()
    # Arabic normalization: unify hamza alef variants, yeh, teh marbuta
    qn = q
    for src, dst in (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ى", "ي"), ("ة", "ه"), ("ؤ", "و"), ("ئ", "ي")):
        qn = qn.replace(src, dst)

    # 1) Top debtors
    if any(k in qn for k in ("اكثر العملاء مديونيه", "اعلي المدينين", "اعلى مدين", "اكبر مدينين", "كبار المدينين")):
        try:
            async with httpx.AsyncClient(timeout=15.0, headers=_int_headers()) as client:
                r = await client.get(f"{base}/api/customers")
                customers = r.json() if r.status_code == 200 else []
        except Exception as e:
            return {"error": str(e)}
        debtors = sorted(
            [c for c in customers if isinstance(c, dict)],
            key=lambda c: float(c.get("ajelBalance") or 0),
            reverse=True,
        )[:limit]
        from core.card_builder import cards_from_customers
        return {
            "query": query,
            "kind": "top_debtors",
            "cards": cards_from_customers(debtors, limit=limit),
            "count": len(debtors),
            "summary": f"أعلى {len(debtors)} عملاء مديونية بإجمالي {sum(float(c.get('ajelBalance') or 0) for c in debtors):,.2f} ر.س",
        }

    # 2) Overdue invoices
    if any(k in qn for k in ("الفواتير المتاخره", "فواتير متاخره", "اجل متاخر", "متاخره")):
        try:
            async with httpx.AsyncClient(timeout=15.0, headers=_int_headers()) as client:
                r = await client.get(f"{base}/api/operations?type=sale&limit=200")
                ops = r.json() if r.status_code == 200 else []
        except Exception as e:
            return {"error": str(e)}
        if isinstance(ops, dict):
            ops = ops.get("data") or ops.get("items") or []
        overdue = [
            o for o in ops if isinstance(o, dict) and (
                (o.get("paymentStatus") or "").lower() in ("unpaid", "partial", "overdue")
                or float(o.get("remainingBalance") or 0) > 0
            )
        ][:limit]
        from core.card_builder import cards_from_operations
        return {
            "query": query,
            "kind": "overdue_invoices",
            "cards": cards_from_operations(overdue, limit=limit),
            "count": len(overdue),
            "summary": f"{len(overdue)} فاتورة متأخرة بإجمالي مبالغ متبقية {sum(float(o.get('remainingBalance') or 0) for o in overdue):,.2f} ر.س",
        }

    # 3) Idle vehicles
    if any(k in qn for k in ("اقل المركبات نشاطا", "مركبات راكده", "مركبات بدون زيارات")):
        try:
            async with httpx.AsyncClient(timeout=15.0, headers=_int_headers()) as client:
                r = await client.get(f"{base}/api/vehicles")
                vehs = r.json() if r.status_code == 200 else []
        except Exception as e:
            return {"error": str(e)}
        vehs = sorted(
            [v for v in vehs if isinstance(v, dict)],
            key=lambda v: int(v.get("totalVisits") or v.get("total_visits") or 0),
        )[:limit]
        from core.card_builder import cards_from_vehicles
        return {
            "query": query,
            "kind": "idle_vehicles",
            "cards": cards_from_vehicles(vehs, limit=limit),
            "count": len(vehs),
            "summary": f"{len(vehs)} مركبة قليلة النشاط",
        }

    # 4) Top recent biggest operations
    if any(k in qn for k in ("اكبر العمليات", "اكبر صفقات", "اعلي مبيعات", "كبري العمليات")):
        try:
            async with httpx.AsyncClient(timeout=15.0, headers=_int_headers()) as client:
                r = await client.get(f"{base}/api/operations?limit=100")
                ops = r.json() if r.status_code == 200 else []
        except Exception as e:
            return {"error": str(e)}
        if isinstance(ops, dict):
            ops = ops.get("data") or ops.get("items") or []
        biggest = sorted(
            [o for o in ops if isinstance(o, dict)],
            key=lambda o: float(o.get("total") or 0),
            reverse=True,
        )[:limit]
        from core.card_builder import cards_from_operations
        return {
            "query": query,
            "kind": "biggest_recent",
            "cards": cards_from_operations(biggest, limit=limit),
            "count": len(biggest),
        }

    return {"query": query, "kind": "unknown", "cards": [], "count": 0,
            "hint": "جرّب: 'أكثر العملاء مديونية' / 'الفواتير المتأخرة' / 'أكبر العمليات'"}


async def _runtime_pending_approvals(workshop_id: str = "finmodule-sync", limit: int = 10) -> Dict[str, Any]:
    """⏳ يرجع المسوّدات بانتظار الاعتماد كـ ApprovalCards."""
    from core import action_runtime
    from core.card_builder import cards_from_approvals
    pending = action_runtime.list_approvals(status="pending", limit=limit)
    return {
        "count": len(pending),
        "cards": cards_from_approvals(pending, limit=limit),
        "approvals": pending,
    }


async def _runtime_audit_recent(workshop_id: str = "finmodule-sync", limit: int = 10) -> Dict[str, Any]:
    """📜 آخر N أحداث في الـ audit trail كـ AuditCards."""
    from core import action_runtime
    from core.card_builder import cards_from_audit
    events = list(reversed(action_runtime.get_audit_trail(limit=limit)))
    return {
        "count": len(events),
        "cards": cards_from_audit(events, limit=limit),
        "events": events,
    }


async def _whatsapp_send_real(
    workshop_id: str = "finmodule-sync",
    to: str = "",
    message: str = "",
) -> Dict[str, Any]:
    """📲 إرسال رسالة واتساب حقيقية عبر Infobip (read-only من ناحية DB).

    READ-ONLY: لا يُعدّل أي بيانات داخلية — فقط يستدعي خدمة خارجية.
    """
    from core.card_builder import whatsapp_card
    to_norm = (to or "").strip()
    if not to_norm or not message:
        return {"error": "to + message required", "cards": []}
    # Normalize Saudi phone format
    digits = "".join(c for c in to_norm if c.isdigit())
    if digits.startswith("05"):
        digits = "966" + digits[1:]
    elif digits.startswith("5") and len(digits) == 9:
        digits = "966" + digits
    elif not digits.startswith("966"):
        digits = "966" + digits

    try:
        from routes_whatsapp_bot import infobip
        result = await infobip.send_text(digits, message)
        success = bool(result.get("messages") or result.get("messageId"))
        wa_entry = {
            "id": (result.get("messages") or [{}])[0].get("messageId", "wa") if result.get("messages") else "wa",
            "to": digits,
            "message": message,
            "status": "sent" if success else "failed",
            "provider": "infobip",
            "channel": "whatsapp",
            "sent_at": __import__("time").time(),
        }
    except Exception as e:
        wa_entry = {
            "id": "wa-err",
            "to": digits,
            "message": message,
            "status": "failed",
            "provider": "infobip",
            "channel": "whatsapp",
            "error": str(e)[:120],
        }
    return {
        "to": digits,
        "status": wa_entry.get("status"),
        "provider": "infobip",
        "cards": [whatsapp_card(wa_entry)],
    }


async def _services_search(workshop_id: str = "finmodule-sync", query: str = "", category: Optional[str] = None, limit: int = 10) -> Dict[str, Any]:
    """🔧 يبحث في كتالوج الخدمات بالاسم أو التصنيف. يُرجع ServiceCards."""
    try:
        from supabase_service import SupabaseService
        svc = SupabaseService()
        client = svc.client
    except Exception as e:
        return {"error": f"supabase unavailable: {e}", "cards": []}
    q = (query or "").strip()
    try:
        sel = client.table("services").select("id, name, category, price, duration_minutes").eq("active", True)
        if category:
            sel = sel.eq("category", category)
        if q:
            sel = sel.ilike("name", f"%{q}%")
        res = sel.limit(limit).execute()
        rows = res.data or []
    except Exception as e:
        return {"error": str(e)[:120], "cards": []}
    from core.card_builder import service_card
    return {
        "query": q,
        "category": category,
        "count": len(rows),
        "results": rows,
        "cards": [service_card(r) for r in rows],
    }


async def _services_categories(workshop_id: str = "finmodule-sync") -> Dict[str, Any]:
    """🗂️ يرجع تصنيفات الخدمات + عدد الخدمات في كل تصنيف."""
    try:
        from supabase_service import SupabaseService
        svc = SupabaseService()
        client = svc.client
    except Exception as e:
        return {"error": str(e), "categories": []}
    try:
        res = client.table("services").select("category").eq("active", True).execute()
        rows = res.data or []
    except Exception as e:
        return {"error": str(e)[:120], "categories": []}
    counts: Dict[str, int] = {}
    for r in rows:
        c = r.get("category") or "بدون تصنيف"
        counts[c] = counts.get(c, 0) + 1
    cats = sorted(
        [{"name": k, "service_count": v} for k, v in counts.items()],
        key=lambda x: x["service_count"], reverse=True,
    )
    return {"total_categories": len(cats), "total_services": len(rows), "categories": cats}


async def _parts_list(workshop_id: str = "finmodule-sync", query: str = "", limit: int = 10) -> Dict[str, Any]:
    """📦 يبحث في كتالوج قطع الغيار بالاسم أو الفئة. يُرجع InventoryCards."""
    try:
        from supabase_service import SupabaseService
        svc = SupabaseService()
        client = svc.client
    except Exception as e:
        return {"error": str(e), "cards": []}
    q = (query or "").strip()
    try:
        sel = client.table("parts").select("id, name, part_number, category, selling_price, quantity, min_quantity")
        if q:
            sel = sel.ilike("name", f"%{q}%")
        res = sel.limit(limit).execute()
        rows = res.data or []
    except Exception as e:
        return {"error": str(e)[:120], "cards": []}
    from core.card_builder import inventory_card
    return {
        "query": q,
        "count": len(rows),
        "cards": [inventory_card(r) for r in rows],
    }


# Register built-ins (يُستدعى مرة واحدة عند الاستيراد)
def _bootstrap() -> None:
    if _TOOLS:
        return
    register_tool(
        "firewall.health_score",
        agent="FirewallAgent",
        description="الحصول على درجة الصحة المالية وعدد التنبيهات النشطة.",
        handler=_firewall_health_score,
        params={"workshop_id": "string?"},
    )
    register_tool(
        "firewall.top_alerts",
        agent="FirewallAgent",
        description="أهم 5 تنبيهات مفعّلة في النظام (مرتّبة حسب الخطورة).",
        handler=_firewall_top_alerts,
        params={"workshop_id": "string?", "limit": "int?"},
    )
    register_tool(
        "firewall.cash_flow",
        agent="FirewallAgent",
        description="تدفق نقدي خلال 30 يوماً (الإيرادات vs المصاريف).",
        handler=_firewall_cash_flow,
        params={"workshop_id": "string?"},
    )
    register_tool(
        "firewall.operation_integrity",
        agent="FirewallAgent",
        description="🆕 يفحص جميع العمليات ويرجع التي بها مشاكل ربط/تنبيهات (missing journal, duplicates, mismatch).",
        handler=_firewall_operation_integrity,
        params={"workshop_id": "string?", "limit": "int?"},
    )
    register_tool(
        "finance.ar_summary",
        agent="FinanceAgent",
        description="ملخص ذمم العملاء + أعلى 5 مدينين.",
        handler=_finance_ar_summary,
        params={"workshop_id": "string?"},
    )
    register_tool(
        "workshop.active_visits",
        agent="WorkshopAgent",
        description="عدد الزيارات المفتوحة حالياً في الورشة.",
        handler=_workshop_active_visits,
        params={"workshop_id": "string?"},
    )
    register_tool(
        "customers.search",
        agent="FinanceAgent",
        description="🔍 بحث عن عميل بالاسم أو الهاتف — يرجع المطابقات + رصيد الذمم لكل عميل.",
        handler=_customers_search,
        params={"workshop_id": "string?", "query": "string", "limit": "int?"},
    )
    register_tool(
        "vehicles.search",
        agent="WorkshopAgent",
        description="🚗 بحث عن مركبة برقم اللوحة / الماركة / الموديل / اسم المالك.",
        handler=_vehicles_search,
        params={"workshop_id": "string?", "query": "string", "limit": "int?"},
    )
    register_tool(
        "parts.search",
        agent="WorkshopAgent",
        description="🔧 بحث ذكي في المخزون عن قطعة (بالاسم/التصنيف) — يرجع السعر+الكمية المتاحة. مفيد للأسئلة 'بيع X' و 'سعر X' و 'كم عندي X'.",
        handler=_parts_search,
        params={"workshop_id": "string?", "query": "string", "limit": "int?", "in_stock_only": "bool?"},
    )
    register_tool(
        "inventory.low_stock",
        agent="WorkshopAgent",
        description="📦 يرجع قائمة بقطع الغيار التي مخزونها أقل من الحد الأدنى المُحدّد لها.",
        handler=_inventory_low_stock,
        params={"workshop_id": "string?", "limit": "int?"},
    )
    register_tool(
        "finance.payables_summary",
        agent="FinanceAgent",
        description="💼 ملخص ذمم الموردين (الأرصدة الدائنة) + أعلى 5 موردين مدينين للورشة.",
        handler=_finance_payables_summary,
        params={"workshop_id": "string?", "limit": "int?"},
    )
    register_tool(
        "operations.recent",
        agent="WorkshopAgent",
        description="آخر N عمليات (بيع/شراء/مصاريف/تحصيل) مع المبلغ وحالة السداد.",
        handler=_operations_recent,
        params={"workshop_id": "string?", "limit": "int?"},
    )
    register_tool(
        "operations.search",
        agent="WorkshopAgent",
        description="بحث عمليات بالاسم (عميل/مورد) — يرجع كل عمليات الشخص المحدد مع المبالغ والحالة.",
        handler=_operations_search,
        params={"workshop_id": "string?", "query": "string", "limit": "int?"},
    )
    register_tool(
        "accounting.journal_entries",
        agent="FinanceAgent",
        description="📒 القيود المحاسبية الفعلية (دفتر اليومية) من قاعدة البيانات — يرجع العدد وإجمالي المدين/الدائن وآخر القيود. استخدميها لأي سؤال عن 'القيود' أو 'دفتر اليومية' أو 'ميزان المراجعة' بدل اختلاق قيود.",
        handler=_accounting_journal_entries,
        params={"workshop_id": "string?", "limit": "int?", "query": "string?"},
    )
    # 🆕 Phase 3C.5 — Natural Language Search + Approvals + Audit + WhatsApp
    register_tool(
        "nl.search",
        agent="WorkshopAgent",
        description="🧠 بحث بلغة طبيعية: 'أكثر العملاء مديونية'، 'الفواتير المتأخرة'، 'أكبر العمليات'.",
        handler=_nl_search,
        params={"workshop_id": "string?", "query": "string", "limit": "int?"},
    )
    register_tool(
        "runtime.pending_approvals",
        agent="WorkshopAgent",
        description="⏳ المسوّدات بانتظار الاعتماد (بطاقات Approval).",
        handler=_runtime_pending_approvals,
        params={"workshop_id": "string?", "limit": "int?"},
    )
    register_tool(
        "runtime.audit_recent",
        agent="WorkshopAgent",
        description="📜 آخر N أحداث في سجل التدقيق (بطاقات Audit).",
        handler=_runtime_audit_recent,
        params={"workshop_id": "string?", "limit": "int?"},
    )
    register_tool(
        "whatsapp.send",
        agent="WorkshopAgent",
        description="📲 إرسال رسالة واتساب حقيقية عبر Infobip لرقم محدد.",
        handler=_whatsapp_send_real,
        params={"workshop_id": "string?", "to": "string", "message": "string"},
    )
    # 🆕 Phase 3C.9 — Services + Parts catalog awareness
    register_tool(
        "services.search",
        agent="WorkshopAgent",
        description="🔧 يبحث في كتالوج الخدمات (520+ خدمة) بالاسم أو التصنيف.",
        handler=_services_search,
        params={"workshop_id": "string?", "query": "string?", "category": "string?", "limit": "int?"},
    )
    register_tool(
        "services.categories",
        agent="WorkshopAgent",
        description="🗂️ تصنيفات الخدمات المتاحة (فرامل، تعليق، كهرباء، ...) مع عدد الخدمات.",
        handler=_services_categories,
        params={"workshop_id": "string?"},
    )
    register_tool(
        "parts.list",
        agent="WorkshopAgent",
        description="📦 يبحث في كتالوج قطع الغيار (148 قطعة) ويُرجع السعر والكمية.",
        handler=_parts_list,
        params={"workshop_id": "string?", "query": "string?", "limit": "int?"},
    )


_bootstrap()
