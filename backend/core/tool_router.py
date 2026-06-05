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
            async with httpx.AsyncClient(timeout=15.0) as client:
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
            async with httpx.AsyncClient(timeout=15.0) as client:
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
            async with httpx.AsyncClient(timeout=15.0) as client:
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
            async with httpx.AsyncClient(timeout=15.0) as client:
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
        description="🧾 آخر N عمليات (بيع/شراء/مصاريف/تحصيل) مع المبلغ وحالة السداد.",
        handler=_operations_recent,
        params={"workshop_id": "string?", "limit": "int?"},
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
