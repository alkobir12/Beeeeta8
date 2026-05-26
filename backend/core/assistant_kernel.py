"""
🤖 AssistantKernel — المنسّق المركزي لجميع وكلاء AI

يستبدل التشتت بين:
  • UnifiedBotWidget chat
  • WorkshopAIBot
  • FinanceBot
  • FirewallPanel (insights)

كل المحادثات تمر من هنا → ذاكرة موحدة + أدوات موحدة + context موحّد.

العملاء (Agents):
  • FinanceAgent — استعلامات مالية (ذمم، تحصيلات، مبيعات)
  • WorkshopAgent — استعلامات تشغيلية (مركبات، زيارات، عمليات)
  • FirewallAgent — تنبيهات وصحة مالية

الـ Kernel يختار الوكيل المناسب حسب الـ intent، ويوفر للـ LLM:
  • system prompt + context snapshot
  • tools registry (firewall.*, finance.*, workshop.*)
  • conversation history
"""

from __future__ import annotations
import os
import re
import uuid
from typing import Any, Dict, List, Optional

from core import alert_bus, shared_memory, ai_context, tool_router


# ---------- Intent → Agent routing ----------

_AGENT_KEYWORDS = {
    "FirewallAgent": [
        "تنبيه", "تنبيهات", "صحة", "خطر", "تكرار", "alert", "firewall", "حماية", "تدقيق", "مخاطر", "شذوذ"
    ],
    "FinanceAgent": [
        "ذمم", "تحصيل", "دين", "مدين", "دائن", "إيراد", "مصروف", "ربح", "خسارة", "رصيد", "العميل", "المورد", "فاتورة"
    ],
    "WorkshopAgent": [
        "مركبة", "زيارة", "خدمة", "ميكانيكي", "فني", "قطعة", "صيانة", "ورشة", "لوحة"
    ],
}


def detect_agent(text: str) -> str:
    t = (text or "").strip().lower()
    if not t:
        return "FinanceAgent"
    scores: Dict[str, int] = {a: 0 for a in _AGENT_KEYWORDS}
    for agent, kws in _AGENT_KEYWORDS.items():
        for kw in kws:
            if kw in t:
                scores[agent] += 1
    best = max(scores.items(), key=lambda x: x[1])
    return best[0] if best[1] > 0 else "FinanceAgent"


# ---------- LLM Helper ----------

def _emergent_llm_key() -> Optional[str]:
    return os.getenv("EMERGENT_LLM_KEY")


async def _llm_chat(
    *,
    session_id: str,
    system_message: str,
    user_message: str,
    history: List[Dict[str, str]],
    max_tokens: int = 800,
    model_provider: str = "openai",
    model_name: str = "gpt-4o-mini",
) -> str:
    api_key = _emergent_llm_key()
    if not api_key:
        return ""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
    except Exception as e:
        print(f"[AssistantKernel] LLM import failed: {e}")
        return ""
    try:
        chat = LlmChat(
            api_key=api_key,
            session_id=session_id,
            system_message=system_message,
        ).with_model(model_provider, model_name)
        # حقن المحادثة (LlmChat لا يحفظ history افتراضياً عبر sessions، نحقنها كرسائل)
        msg_text = user_message
        if history:
            history_text = "\n".join([f"{m['role']}: {m['content']}" for m in history[-10:]])
            msg_text = f"السياق السابق للمحادثة:\n{history_text}\n\nالسؤال الحالي:\n{user_message}"
        response = await chat.send_message(UserMessage(text=msg_text))
        return str(response or "").strip()
    except Exception as e:
        print(f"[AssistantKernel] LLM call failed: {e}")
        return ""


# ---------- Tool intent detector ----------

_TOOL_PATTERNS = [
    (re.compile(r"(صح[ةه]|درج[ةه]|نقاط|score|health)", re.IGNORECASE), "firewall.health_score"),
    (re.compile(r"(تنبي[هه]ات|alerts|أهم.*تنبي|top alerts|التنبي)", re.IGNORECASE), "firewall.top_alerts"),
    (re.compile(r"(تدفق|cash flow|إيراد|مصاريف|cash_flow)", re.IGNORECASE), "firewall.cash_flow"),
    (re.compile(r"(ذمم|مدين|debtors|دين العميل|ar summary)", re.IGNORECASE), "finance.ar_summary"),
    (re.compile(r"(زيار[ةه] نشط|مركبات مفتوح|active visits|كم زيار)", re.IGNORECASE), "workshop.active_visits"),
]


def detect_tools(text: str) -> List[str]:
    t = (text or "").strip()
    matched = []
    for rgx, tool_name in _TOOL_PATTERNS:
        if rgx.search(t):
            matched.append(tool_name)
    return matched


# ---------- Public API ----------

async def chat(
    *,
    session_id: Optional[str] = None,
    message: str,
    workshop_id: Optional[str] = None,
    force_agent: Optional[str] = None,
    use_ai: bool = True,
) -> Dict[str, Any]:
    """نقطة الدخول الموحدة. يُعيد {agent, tool_results, response, session_id}."""
    sid = session_id or f"session-{uuid.uuid4().hex[:10]}"
    shared_memory.append_message(sid, "user", message)

    # 1) اختر الوكيل
    agent = force_agent or detect_agent(message)

    # 2) كشف الأدوات المطلوبة
    tool_names = detect_tools(message)
    tool_results: List[Dict[str, Any]] = []
    for tn in tool_names:
        result = await tool_router.call_tool(tn, workshop_id=workshop_id or "finmodule-sync")
        tool_results.append(result)

    # 3) ابنِ السياق
    snapshot = ai_context.build_context_snapshot(
        workshop_id=workshop_id,
        include_alerts=(agent == "FirewallAgent"),
        include_cash_flow=True,
    )
    context_text = ai_context.context_to_text(snapshot)

    # 4) ابنِ system message
    system_msg = ai_context.build_system_prompt(agent_name=agent) + "\n\n" + context_text

    # 5) أضف نتائج الأدوات لو موجودة
    if tool_results:
        tool_section = "\n\n🛠️ نتائج الأدوات المُنفّذة لهذا السؤال:\n"
        for tr in tool_results:
            tool_section += f"  • {tr.get('tool')}: {tr.get('result') if tr.get('success') else tr.get('error')}\n"
        system_msg += tool_section

    # 6) محادثة سابقة
    history = ai_context.get_conversation_history(sid, limit=10)

    # 7) استدعاء LLM
    response_text = ""
    if use_ai:
        response_text = await _llm_chat(
            session_id=sid,
            system_message=system_msg,
            user_message=message,
            history=history[:-1],  # exclude current user message
        )

    # Fallback: إذا فشل AI، استخدم نتائج الأدوات + قواعد
    if not response_text:
        if tool_results:
            parts = [f"نفّذتُ {len(tool_results)} أداة لك:"]
            for tr in tool_results:
                if tr.get("success"):
                    parts.append(f"• {tr.get('tool')}: {tr.get('result')}")
                else:
                    parts.append(f"• فشل {tr.get('tool')}: {tr.get('error')}")
            response_text = "\n".join(parts)
        else:
            response_text = "النظام يعمل بقواعد محلية حالياً. لتفعيل ردود أعمق، تأكد من تكوين Emergent LLM Key."

    shared_memory.append_message(sid, "assistant", response_text, meta={
        "agent": agent,
        "tools": [t.get("tool") for t in tool_results],
        "snapshot_keys": list(snapshot.keys()),
    })

    return {
        "session_id": sid,
        "agent": agent,
        "tool_results": tool_results,
        "response": response_text,
        "context_snapshot": snapshot,
        "ai_used": bool(use_ai and _emergent_llm_key()),
    }


def get_session_messages(session_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    return shared_memory.get_messages(session_id, limit=limit)


def list_available_tools(agent: Optional[str] = None) -> List[Dict[str, Any]]:
    return tool_router.list_tools(agent=agent)


def get_recent_alerts_for_assistant(limit: int = 5) -> List[Dict[str, Any]]:
    """من alert_bus مباشرة (بدون scan كامل)."""
    return alert_bus.get_active_alerts()[:limit]


def kernel_stats() -> Dict[str, Any]:
    return {
        "memory": shared_memory.stats(),
        "alert_bus": alert_bus.stats(),
        "tools_registered": len(tool_router.list_tools()),
        "ai_enabled": bool(_emergent_llm_key()),
    }
