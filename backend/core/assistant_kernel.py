"""
🤖 AssistantKernel — Enterprise Assistant L5 (Single, Read-Only)

Per L5 spec:
  - NOT autonomous
  - NOT multi-agent
  - Read-only access to ERP data
  - No writes / no approvals / no policy changes
  - Session memory + recent actions/searches/reports
  - Helpful, fast, accurate, auditable

Tools are ALL read-only:
  • search.* — search ERP data
  • report.* — generate reports
  • analytics.* — compute insights
  • knowledge.* — query knowledge base
"""

from __future__ import annotations
import os
import re
import uuid
from typing import Any, Dict, List, Optional

from core import alert_bus, shared_memory, ai_context, tool_router


# ---------- Tool intent detector (read-only tools) ----------

_TOOL_PATTERNS = [
    # Firewall / audit insights — تنبيهات وتصحيحات (إفراد + جمع + مرادفات)
    (re.compile(r"(صح[ةه]\s*(?:ال)?(نظام|مال)|درج[ةه]\s*(?:ال)?صح|نقاط|health\s*score|health)", re.IGNORECASE), "firewall.health_score"),
    (re.compile(r"(تنبيه|تنبي?هات|alerts?|تصحيح|تصحيحات|خطأ|أخطاء|مشكل[ةه]|عيب|شذوذ|مخالف[ةه]|audit|إنذار|warning|fix|issue|التنبي)", re.IGNORECASE), "firewall.top_alerts"),
    # 🆕 Per-operation integrity warnings (missing_journal_entry, duplicates …)
    (re.compile(r"(ملاحظ|ملاحظات|integrity|ربط|قيد\s*مفقود|قيود\s*مفقود|سلام[ةه]|تنبيه.*عمل|كروت|بطاق[ةه]|warning.*op|missing.*journal|عمليات.*خطأ|عمليات.*مشكل)", re.IGNORECASE), "firewall.operation_integrity"),
    (re.compile(r"(تدفق|cash\s*flow|إيراد|مصاريف|مصروف|cash_flow|سيول[ةه])", re.IGNORECASE), "firewall.cash_flow"),
    # Finance read-only
    (re.compile(r"(ذمم\s*(?:ال)?عملاء|مدين|debtors?|دين العميل|ar\s*summary|متأخر|آجل\s*(?:ال)?عملاء|^\s*ذمم\s*$|ذمم\s*مدين)", re.IGNORECASE), "finance.ar_summary"),
    # 🆕 Suppliers AP
    (re.compile(r"(ذمم\s*(?:ال)?مورد|دائن|دائنين|payables?|ap\s*summary|نستحق|نحن\s*مدين|للمورد|ذمم\s*ال?ورش[ةه])", re.IGNORECASE), "finance.payables_summary"),
    # 🆕 Inventory low stock
    (re.compile(r"((?:ال)?قطع\s*(?:ال)?ناقص|مخزون\s*منخفض|low\s*stock|(?:ال)?قطع\s*انتهت|قطع\s*أوشكت|نفاد|نفذت\s*(?:ال)?قطع|(?:ل?ل?)?(?:ال)?حد\s*(?:ال)?أدنى|قطع.*ناقص|نواقص\s*المخزون|تنبيه.*مخزون|تنبيهات\s*المخزون)", re.IGNORECASE), "inventory.low_stock"),
    # 🆕 Recent operations
    (re.compile(r"(آخر\s*(?:ال)?عمليات|أحدث\s*(?:ال)?عمليات|آخر\s*(?:ال)?مبيعات|recent\s*operations?|عمليات\s*اليوم|أخر\s*(?:ال)?عمليات)", re.IGNORECASE), "operations.recent"),
    # 🆕 Customer search (intent: "ابحث عن العميل X" / "كم رصيد X")
    (re.compile(r"(ابحث\s*عن\s*(?:ال)?عميل|أبحث\s*عن\s*(?:ال)?عميل|اعرض\s*(?:ال)?عميل|عرض\s*(?:ال)?عميل|بيانات\s*(?:ال)?عميل|رصيد\s*(?:ال)?عميل|كم\s*رصيد|كم\s*يستحق\s*(?:ال)?عميل|ذمم\s*(?:ال)?عميل\s+|ابحث\s*(?:ال)?عميل)", re.IGNORECASE), "customers.search"),
    # 🆕 Vehicle search (intent: "ابحث عن المركبة" / "أين مركبة X")
    (re.compile(r"(ابحث\s*عن\s*(?:ال)?مركب|أبحث\s*عن\s*(?:ال)?مركب|بيانات\s*(?:ال)?مركب|أين\s*(?:ال)?مركب|اعرض\s*(?:ال)?مركب|لوحة\s*(?:ال)?مركب|رقم\s*(?:ال)?لوحة|ابحث\s*(?:ال)?مركب|ابحث\s*(?:ال)?سيار|بيانات\s*(?:ال)?سيار)", re.IGNORECASE), "vehicles.search"),
    # Workshop read-only
    (re.compile(r"(زيار[ةه]\s*نشط|مركبات\s*مفتوح|active\s*visits|كم\s*زيار|مركبات\s*داخل|قائم[ةه]\s*العمل)", re.IGNORECASE), "workshop.active_visits"),
]


# Tools that accept a `query` parameter parsed from the user's free text
_QUERY_AWARE_TOOLS = {"customers.search", "vehicles.search"}


def _extract_query(text: str, tool_name: str) -> str:
    """Pull a likely search term out of the message for query-aware tools.

    Strategy:
      • strip the leading verb/keyword (ابحث عن، رصيد، بيانات، ...).
      • drop common Arabic stop-words.
      • keep only the noun/proper-noun portion.
    """
    if not text:
        return ""
    raw = text.strip()
    # Remove leading question words / verbs commonly preceding a search term
    raw = re.sub(
        r"^(?:كم\s+رصيد|ابحث\s*عن|أبحث\s*عن|اعرض|عرض|بيانات|أين|أرني|ارني|لوحة|رقم\s*لوحة|رقم\s*(?:ال)?لوحة|رصيد\s*(?:ال)?عميل|ذمم\s*(?:ال)?عميل)\s*",
        "",
        raw,
        flags=re.IGNORECASE,
    )
    # Drop entity nouns ("العميل" / "المركبة")
    if tool_name == "customers.search":
        raw = re.sub(r"(?:ال)?عميل[ةه]?|(?:ال)?زبون[ةه]?", "", raw, flags=re.IGNORECASE)
    elif tool_name == "vehicles.search":
        raw = re.sub(r"(?:ال)?مركب[ةه]?|(?:ال)?سيار[ةه]?", "", raw, flags=re.IGNORECASE)
    # Drop common particles
    raw = re.sub(r"\b(عن|في|من|إلى|الى|على|ل|لـ|ب|بـ|ك|كـ|و|أو|او|هل|كم|ما)\b", " ", raw)
    raw = re.sub(r"[?\.,!؟،]", " ", raw)
    return " ".join(raw.split()).strip()


def detect_tools(text: str) -> List[str]:
    """Detect which read-only tools to call based on user message keywords."""
    t = (text or "").strip()
    matched = []
    for rgx, tool_name in _TOOL_PATTERNS:
        if rgx.search(t):
            matched.append(tool_name)
    return matched


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
        msg_text = user_message
        if history:
            history_text = "\n".join([f"{m['role']}: {m['content']}" for m in history[-10:]])
            msg_text = f"السياق السابق للمحادثة:\n{history_text}\n\nالسؤال الحالي:\n{user_message}"
        response = await chat.send_message(UserMessage(text=msg_text))
        return str(response or "").strip()
    except Exception as e:
        print(f"[AssistantKernel] LLM call failed: {e}")
        return ""


# ---------- Public API ----------

ASSISTANT_NAME = "Beeeeta8 Assistant"
ASSISTANT_VERSION = "L5.1"


def _system_prompt() -> str:
    """L5 system prompt — proactive helpful read-only assistant.

    Important: read-only = backend tools don't write. The assistant SHOULD still
    answer questions, search data, explain findings, summarise reports, etc.
    We only refuse when the user explicitly asks for CREATE/UPDATE/DELETE/APPROVE.
    """
    return (
        f"أنت {ASSISTANT_NAME} — المساعد الذكي داخل نظام Beeeeta8 لإدارة الورش.\n\n"
        "🎯 وظيفتك الأساسية: **مساعدة المستخدم بفاعلية**.\n"
        "  • أجب على الأسئلة استناداً للبيانات الفعلية المُمرّرة لك (في 'السياق' و 'نتائج الأدوات').\n"
        "  • اشرح التنبيهات والقيود والتقارير المالية والذمم وحالة المركبات.\n"
        "  • لخّص الأرقام واعرض الـ insights الذكية.\n"
        "  • وجّه المستخدم لأي مكان في النظام عبر صياغة واضحة (مثل: 'افتح صفحة /accounting/firewall').\n\n"
        "🧰 الأدوات المتاحة لك (تُستدعى تلقائياً حسب نية السؤال):\n"
        "  • firewall.health_score — درجة الصحة المالية للنظام.\n"
        "  • firewall.top_alerts — أهم 5 تنبيهات نشطة.\n"
        "  • firewall.cash_flow — تدفق نقدي 30 يوماً.\n"
        "  • firewall.operation_integrity — العمليات بها قيود/مشاكل ربط.\n"
        "  • finance.ar_summary — ذمم العملاء + أعلى المدينين.\n"
        "  • finance.payables_summary — ذمم الموردين + أعلى الدائنين.\n"
        "  • workshop.active_visits — عدد الزيارات المفتوحة.\n"
        "  • inventory.low_stock — قطع المخزون التي وصلت للحد الأدنى.\n"
        "  • operations.recent — آخر العمليات (بيع/شراء/مصروف).\n"
        "  • customers.search — بحث عميل بالاسم/الهاتف.\n"
        "  • vehicles.search — بحث مركبة باللوحة/الماركة/المالك.\n\n"
        "📊 كيف تتعامل مع نتائج الأدوات:\n"
        "  • إذا الأداة أعادت قائمة فارغة → قل صراحة 'لا توجد بيانات حالياً' بدون اعتذار طويل.\n"
        "  • إذا الأداة فشلت → اعرض الخطأ بإيجاز واقترح بدائل.\n"
        "  • إذا الأداة نجحت → قدّم النتيجة منسّقة (جدول Markdown أو قائمة أو أرقام واضحة).\n"
        "  • إذا الأرقام كبيرة → نسّقها بفواصل الآلاف عند الكتابة.\n\n"
        "🛡️ القيد الوحيد (read-only backend):\n"
        "  • لا تستدع أداة تكتب/تعدّل/تحذف في DB — كل الأدوات المسجّلة لديك قراءة فقط.\n"
        "  • لو طلب المستخدم 'أنشئ/عدّل/احذف/وافق' → اشرح الخطوات وأرشده للواجهة المناسبة، لكن لا تتذرّع بأنك لا تستطيع 'فتح' أو 'الوصول'.\n"
        "  • **ممنوع** الرد بـ 'لا يمكنني فتح أو تعديل' عند سؤال قراءة عادي — أنت تملك بيانات النظام وتقدر تجيب.\n\n"
        "📐 أسلوبك:\n"
        "  • عربية فصحى مبسطة، مختصرة، رقمية حين تتوفر أرقام.\n"
        "  • Markdown مسموح ومفضّل (جداول | bullets | **bold**) — الواجهة تعرضه بشكل صحيح.\n"
        "  • إذا لم تتوفر بيانات في السياق ولم تُنفّذ أداة → اطلب من المستخدم سؤالاً أكثر تحديداً بدلاً من التخمين.\n"
    )


async def chat(
    *,
    session_id: Optional[str] = None,
    message: str,
    workshop_id: Optional[str] = None,
    force_agent: Optional[str] = None,  # kept for backward-compat; ignored in L5
    use_ai: bool = True,
) -> Dict[str, Any]:
    """Main entry point for the assistant.

    Returns: {session_id, response, tool_results, recent_actions, context_snapshot, ai_used}
    """
    sid = session_id or f"session-{uuid.uuid4().hex[:10]}"
    shared_memory.append_message(sid, "user", message)

    # 1) Detect which read-only tools to invoke
    tool_names = detect_tools(message)
    tool_results: List[Dict[str, Any]] = []
    for tn in tool_names:
        kwargs: Dict[str, Any] = {"workshop_id": workshop_id or "finmodule-sync"}
        if tn in _QUERY_AWARE_TOOLS:
            q = _extract_query(message, tn)
            if q:
                kwargs["query"] = q
        result = await tool_router.call_tool(tn, **kwargs)
        tool_results.append(result)
        # Track tool call in session memory
        shared_memory.track_action(sid, "tool_call", {
            "tool": tn,
            "success": bool(result.get("success")),
        })

    # 2) Build read-only context snapshot
    snapshot = ai_context.build_context_snapshot(
        workshop_id=workshop_id,
        include_alerts=True,
        include_cash_flow=True,
    )
    context_text = ai_context.context_to_text(snapshot)

    # 3) System message (L5: single assistant, no agent persona)
    system_msg = _system_prompt() + "\n\n" + context_text

    # 4) Append tool results
    if tool_results:
        tool_section = "\n\n🛠️ نتائج الأدوات المنفّذة لهذا السؤال:\n"
        for tr in tool_results:
            tool_section += f"  • {tr.get('tool')}: {tr.get('result') if tr.get('success') else tr.get('error')}\n"
        system_msg += tool_section

    # 5) Get conversation history
    history = ai_context.get_conversation_history(sid, limit=10)

    # 6) Call LLM
    response_text = ""
    if use_ai:
        response_text = await _llm_chat(
            session_id=sid,
            system_message=system_msg,
            user_message=message,
            history=history[:-1],
        )

    # Fallback: aggregated tool output + canned message
    if not response_text:
        if tool_results:
            parts = [f"نفّذتُ {len(tool_results)} أداة قراءة فقط:"]
            for tr in tool_results:
                if tr.get("success"):
                    parts.append(f"• {tr.get('tool')}: {tr.get('result')}")
                else:
                    parts.append(f"• فشل {tr.get('tool')}: {tr.get('error')}")
            response_text = "\n".join(parts)
        else:
            response_text = "النظام يعمل بقواعد محلية حالياً. لتفعيل ردود أعمق، تأكد من تكوين Emergent LLM Key."

    # 7) Persist assistant message + classify the message intent
    intent = _classify_intent(message)
    shared_memory.append_message(sid, "assistant", response_text, meta={
        "tools": [t.get("tool") for t in tool_results],
        "intent": intent,
        "snapshot_keys": list(snapshot.keys()),
    })
    # Track this as an action in recent_actions
    shared_memory.track_action(sid, intent, {
        "message": message[:160],
        "tools": [t.get("tool") for t in tool_results],
    })

    return {
        "session_id": sid,
        # Backward compatibility: include "agent" key but always set to single assistant
        "agent": "Assistant",
        "assistant_name": ASSISTANT_NAME,
        "assistant_version": ASSISTANT_VERSION,
        "intent": intent,
        "tool_results": tool_results,
        "response": response_text,
        "context_snapshot": snapshot,
        "recent_actions": shared_memory.get_recent_actions(sid, limit=10),
        "ai_used": bool(use_ai and _emergent_llm_key()),
        "read_only": True,
    }


def _classify_intent(text: str) -> str:
    """Light classification of the user's intent — used for memory tagging."""
    t = (text or "").strip().lower()
    if not t:
        return "other"
    if any(k in t for k in ["ابحث", "search", "find", "أين", "كم عدد"]):
        return "search"
    if any(k in t for k in ["تقرير", "report", "كشف", "ملخص"]):
        return "report"
    if any(k in t for k in ["لماذا", "اشرح", "explain", "وضح", "كيف"]):
        return "explain"
    if any(k in t for k in ["لخص", "summarize", "خلاصة"]):
        return "summarize"
    return "question"


# ---------- Public helpers ----------

def get_session_messages(session_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    return shared_memory.get_messages(session_id, limit=limit)


def get_recent_actions(session_id: str, limit: int = 20, action_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """🆕 L5: returns Recent Actions/Searches/Reports for this session."""
    return shared_memory.get_recent_actions(session_id, limit=limit, action_type=action_type)


def list_available_tools(agent: Optional[str] = None) -> List[Dict[str, Any]]:
    """Returns all registered tools. Filter by agent kept for backward compat (ignored in L5)."""
    return tool_router.list_tools(agent=agent)


def get_recent_alerts_for_assistant(limit: int = 5) -> List[Dict[str, Any]]:
    """From alert_bus directly (no full scan)."""
    return alert_bus.get_active_alerts()[:limit]


def kernel_stats() -> Dict[str, Any]:
    return {
        "assistant_name": ASSISTANT_NAME,
        "assistant_version": ASSISTANT_VERSION,
        "mode": "single_assistant_read_only",
        "memory": shared_memory.stats(),
        "alert_bus": alert_bus.stats(),
        "tools_registered": len(tool_router.list_tools()),
        "ai_enabled": bool(_emergent_llm_key()),
    }


# ---------- Deprecated (kept for backward compat with /api/assistant/* routes) ----------

def detect_agent(text: str) -> str:  # noqa: ARG001
    """DEPRECATED in L5 — always returns 'Assistant'. Kept so existing imports don't break."""
    return "Assistant"
