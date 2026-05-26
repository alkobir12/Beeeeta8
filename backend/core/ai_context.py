"""
🎯 AI Context Builder — يبني context غني للـ AI من Firewall + Bus + Memory

كل استدعاء للذكاء يأخذ:
  • آخر 3-5 تنبيهات حرجة
  • cash flow snapshot
  • health score
  • محادثة سابقة (10 رسائل)

يجمع كل هذا في system message متين.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional

from core import alert_bus, shared_memory


def build_system_prompt(agent_name: str = "UnifiedAssistant") -> str:
    base = (
        "أنت 'الكبير' — المساعد المالي والمحاسبي الذكي لورشة سيارات.\n"
        "تتحدث العربية بشكل افتراضي، بأسلوب محترف موجز.\n"
        "لديك وصول إلى أدوات تحليلية (firewall.*, finance.*, workshop.*).\n"
        "عندما يطلب المستخدم رقماً أو حقيقة (رصيد، عدد، ديون، تنبيهات)، يجب أن تستخدم أداة فعلية لا أن تخمن.\n"
        f"وكيلك الحالي: {agent_name}\n"
    )
    return base


def build_context_snapshot(
    workshop_id: Optional[str] = None,
    include_alerts: bool = True,
    include_cash_flow: bool = True,
    max_alerts: int = 5,
) -> Dict[str, Any]:
    """يبني snapshot جاهز للحقن في system prompt."""
    snapshot: Dict[str, Any] = {"workshop_id": workshop_id or "finmodule-sync"}
    try:
        from firewall_engine import FirewallEngine
        engine = FirewallEngine(workshop_id=workshop_id)
        analysis = engine.run_full_analysis()
        snapshot["health"] = {
            "score": analysis["health"]["score"],
            "status": analysis["health"]["status"],
        }
        if include_alerts:
            snapshot["top_alerts"] = [{
                "title": a["title"],
                "severity": a["severity"],
                "impact": a.get("financial_impact"),
                "category": a["category"],
            } for a in analysis.get("alerts", [])[:max_alerts]]
        if include_cash_flow:
            snapshot["cash_flow"] = analysis.get("cash_flow")
        snapshot["alerts_count"] = analysis.get("alerts_count", 0)
    except Exception as e:
        snapshot["context_error"] = str(e)
    return snapshot


def context_to_text(snapshot: Dict[str, Any]) -> str:
    """يحوّل snapshot إلى نص عربي يُحقن في system prompt."""
    lines: List[str] = ["📊 **سياق النظام الحالي (محدث لحظياً):**"]
    h = snapshot.get("health") or {}
    if h:
        lines.append(f"  • درجة الصحة المالية: {h.get('score')}/100 ({h.get('status')})")
    cf = snapshot.get("cash_flow") or {}
    if cf:
        lines.append(f"  • التدفق النقدي (30 يوم): إيرادات {cf.get('inflow')} ر.س، مصاريف {cf.get('outflow')} ر.س، صافي {cf.get('net')} ر.س")
    alerts = snapshot.get("top_alerts") or []
    if alerts:
        lines.append(f"  • أهم {len(alerts)} تنبيهات:")
        for a in alerts:
            lines.append(f"     - [{a.get('severity')}] {a.get('title')} (تأثير: {a.get('impact')} ر.س)")
    lines.append(f"  • إجمالي التنبيهات النشطة: {snapshot.get('alerts_count', 0)}")
    return "\n".join(lines)


def get_conversation_history(session_id: str, limit: int = 10) -> List[Dict[str, str]]:
    """يحوّل ذاكرة الجلسة إلى صيغة messages قابلة للحقن في LLM."""
    msgs = shared_memory.get_messages(session_id, limit=limit)
    return [{"role": m["role"], "content": m["content"]} for m in msgs]
