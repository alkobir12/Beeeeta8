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
        async with httpx.AsyncClient(timeout=10) as client:
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
        async with httpx.AsyncClient(timeout=15.0) as client:
            params = {"search": query} if query else {}
            r = await client.get(f"{base}/api/customers", params=params)
            customers = r.json() if r.status_code == 200 else []
    except Exception as e:
        return {"error": str(e)}
    if not isinstance(customers, list):
        customers = []
    # filter additionally if query did not propagate
    if query:
        q = query.lower().strip()
        customers = [
            c for c in customers
            if q in str(c.get("name") or "").lower()
            or q in str(c.get("phone") or "").lower()
        ]
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
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(f"{base}/api/vehicles")
            vehicles = r.json() if r.status_code == 200 else []
    except Exception as e:
        return {"error": str(e)}
    if not isinstance(vehicles, list):
        vehicles = []
    q = (query or "").lower().strip()
    if q:
        vehicles = [
            v for v in vehicles
            if q in str(v.get("plateNumber") or "").lower()
            or q in str(v.get("plate") or "").lower()
            or q in str(v.get("model") or "").lower()
            or q in str(v.get("brand") or "").lower()
            or q in str(v.get("customerName") or v.get("ownerName") or "").lower()
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
        async with httpx.AsyncClient(timeout=15.0) as client:
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
        async with httpx.AsyncClient(timeout=15.0) as client:
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
        async with httpx.AsyncClient(timeout=15.0) as client:
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
        async with httpx.AsyncClient(timeout=15.0) as client:
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
            "id": (o.get("id") or "")[:8],
            "type": o.get("type"),
            "total": float(o.get("total") or 0),
            "payment_method": o.get("paymentMethod") or o.get("payment_method"),
            "payment_status": o.get("paymentStatus") or o.get("payment_status"),
            "partner": o.get("partnerName") or o.get("customerName") or o.get("supplierName"),
            "date": o.get("createdAt") or o.get("created_at") or o.get("date"),
        } for o in ops],
        "cards": cards_from_operations(ops, limit=limit),
    }


async def _firewall_operation_integrity(workshop_id: Optional[str] = None, limit: int = 20) -> Dict[str, Any]:
    """🆕 يفحص العمليات ويُرجع التي بها مشاكل ربط/تنبيهات (per-card warnings)."""
    try:
        import os
        import httpx
        base = os.environ.get("INTERNAL_API_BASE", "http://localhost:8001")
        async with httpx.AsyncClient(timeout=15.0) as client:
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
    return {
        "total_operations": summary.get("total") or len(items),
        "ok": summary.get("ok"),
        "with_warnings": summary.get("warnings") or len(flagged),
        "duplicates": summary.get("duplicates"),
        "sample": sample,
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
        description="🧾 آخر N عمليات (بيع/شراء/مصاريف/تحصيل) مع المبلغ وحالة السداد.",
        handler=_operations_recent,
        params={"workshop_id": "string?", "limit": "int?"},
    )


_bootstrap()
