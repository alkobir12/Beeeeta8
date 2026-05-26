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


def register_tool(
    name: str,
    *,
    agent: str,
    description: str,
    handler: Callable[..., Awaitable[Any]],
    params: Optional[Dict[str, Any]] = None,
) -> None:
    """يسجل أداة في الـ Router."""
    _TOOLS[name] = {
        "name": name,
        "agent": agent,
        "description": description,
        "handler": handler,
        "params": params or {},
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
        })
    return out


async def call_tool(name: str, **kwargs) -> Dict[str, Any]:
    tool = _TOOLS.get(name)
    if not tool:
        return {"success": False, "error": f"tool not found: {name}"}
    try:
        result = await tool["handler"](**kwargs)
        return {"success": True, "tool": name, "agent": tool["agent"], "result": result}
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


_bootstrap()
