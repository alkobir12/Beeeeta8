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

from core import alert_bus, shared_memory, ai_context, tool_router, power_mode, vector_memory
from core.log_utils import get_logger, redact

# Phase 3A — structured logger replaces ad-hoc print() calls.
_log = get_logger("kernel")


# ---------- Tool intent detector (read-only tools) ----------

_TOOL_PATTERNS = [
    # Firewall / audit insights — تنبيهات وتصحيحات (إفراد + جمع + مرادفات)
    (re.compile(r"(صح[ةه]\s*(?:ال)?(نظام|مال)|درج[ةه]\s*(?:ال)?صح|نقاط|health\s*score|health)", re.IGNORECASE), "firewall.health_score"),
    (re.compile(r"(تنبيه|تنبي?هات|تحذير|تحذيرات|alerts?|تصحيح|تصحيحات|خطأ|أخطاء|مشكل[ةه]|عيب|شذوذ|مخالف[ةه]|audit|إنذار|warning|fix|issue|التنبي)", re.IGNORECASE), "firewall.top_alerts"),
    # Per-operation integrity warnings (missing_journal_entry, duplicates …)
    # NOTE: "ملاحظ" only matches when NOT followed by a proper name (to avoid stealing name-queries)
    (re.compile(r"(integrity|ربط|قيد\s*مفقود|قيود\s*مفقود|بدون\s*قيد|بدون\s*قيود|بلا\s*قيد|بلا\s*قيود|سلام[ةه]|تنبيه.*عمل|كروت|بطاق[ةه]|warning.*op|missing.*journal|عمليات.*خطأ|عمليات.*مشكل|قيود.*مفقود|عمليات.*بدون)", re.IGNORECASE), "firewall.operation_integrity"),
    (re.compile(r"(تدفق|cash\s*flow|إيراد|مصاريف|مصروف|cash_flow|سيول[ةه])", re.IGNORECASE), "firewall.cash_flow"),
    # Finance read-only
    (re.compile(r"(ذمم\s*(?:ال)?عملاء|مدين|debtors?|دين العميل|ar\s*summary|متأخر|آجل\s*(?:ال)?عملاء|^\s*ذمم\s*$|ذمم\s*مدين)", re.IGNORECASE), "finance.ar_summary"),
    # Suppliers AP
    (re.compile(r"(ذمم\s*(?:ال)?مورد|دائن|دائنين|payables?|ap\s*summary|نستحق|نحن\s*مدين|للمورد|ذمم\s*ال?ورش[ةه])", re.IGNORECASE), "finance.payables_summary"),
    # Inventory low stock
    (re.compile(r"((?:ال)?قطع\s*(?:ال)?ناقص|مخزون\s*منخفض|low\s*stock|(?:ال)?قطع\s*انتهت|قطع\s*أوشكت|نفاد|نفذت\s*(?:ال)?قطع|(?:ل?ل?)?(?:ال)?حد\s*(?:ال)?أدنى|قطع.*ناقص|نواقص\s*المخزون|تنبيه.*مخزون|تنبيهات\s*المخزون)", re.IGNORECASE), "inventory.low_stock"),
    # Parts search — "بيع X" / "أبيع X" / "سعر X" / "كم سعر X" / "كم عندي X" / "هل عندنا X"
    (re.compile(r"(\bبيع\b|\bأبيع\b|\bابيع\b|اشتري|شراء\s+قطع|كم\s*سعر|سعر\s+(?:ال)?(?:قطع|فلتر|زيت|بطار|طرمب|ربلات|مساحات|بواجي|بلف|كبسول|كمبيوتر|مكيف|ايرباغ|دبري|كبائن|سلندر|طقم|كرنك|كومة|كوب|كولر|سير|تيل|قرص|دريم|قار|بوش|طبه)|تكلفة\s+قطع|كم\s+ع?ندي|كم\s+يتوفر|متوفر\s+لدينا|هل\s+ع?ندنا|أبحث\s+عن\s+قطع|ابحث\s+عن\s+قطع|بحث\s+عن\s+قطع|كم\s+مخزون|كم\s+ع?ندك\s+من|أحتاج\s+قطع|احتاج\s+قطع)", re.IGNORECASE), "parts.search"),
    # Recent operations
    (re.compile(r"(آخر\s*(?:ال)?عمليات|أحدث\s*(?:ال)?عمليات|آخر\s*(?:ال)?مبيعات|recent\s*operations?|عمليات\s*اليوم|أخر\s*(?:ال)?عمليات)", re.IGNORECASE), "operations.recent"),
    # Operations search by customer/partner name — "عمليات محمد" / "تفاصيل عملية X"
    # Excludes common conjunctions/particles after "عمليات" (و/بدون/بلا/في/من)
    (re.compile(r"(تفاصيل\s*(?:ال)?عملي[ةه]?(?:ات)?\s+[\u0621-\u064A]|عمليات\s+(?!وال|والت|بدون|بلا|في\s|من\s|على\s|إلى)[\u0621-\u064A]{2,}(?:\s|$)|ملف\s*(?:ال)?عملي[ةه]?(?:ات)?\s+[\u0621-\u064A])", re.IGNORECASE), "operations.search"),
    # Customer search — broad patterns including name-based queries + Qassimi dialect
    (re.compile(r"(ابحث\s*عن\s*(?:ال)?عميل|أبحث\s*عن\s*(?:ال)?عميل|اعرض\s*(?:ال)?عميل|عرض\s*(?:ال)?عميل|بيانات\s*(?:ال)?عميل|رصيد\s*(?:ال)?عميل|كم\s*رصيد|كم\s*يستحق\s*(?:ال)?عميل|ذمم\s*(?:ال)?عميل\s+|ابحث\s*(?:ال)?عميل|وش\s+عند|وين\s+(?:ال)?عميل|ابي\s+بيانات|ابغى\s+بيانات)", re.IGNORECASE), "customers.search"),
    # Generic info request with a proper name — "أعطني/عطني ملاحظة/بيانات/تفاصيل [name]"
    (re.compile(r"((?:أعطني|اعطني|عطني|أعطيني|ابغى|أبغى|أريد|اريد|وريني|اخبرني|أخبرني)\s+(?:ملاحظ[ةه]?|ملاحظات|بيانات|تفاصيل|معلومات|ملف|حساب|سجل|رصيد|عمليات?)\s)", re.IGNORECASE), "customers.search"),
    # Vehicle search (intent: "ابحث عن المركبة" / "أين مركبة X")
    (re.compile(r"(ابحث\s*عن\s*(?:ال)?مركب|أبحث\s*عن\s*(?:ال)?مركب|بيانات\s*(?:ال)?مركب|أين\s*(?:ال)?مركب|اعرض\s*(?:ال)?مركب|لوحة\s*(?:ال)?مركب|رقم\s*(?:ال)?لوحة|ابحث\s*(?:ال)?مركب|ابحث\s*(?:ال)?سيار|بيانات\s*(?:ال)?سيار)", re.IGNORECASE), "vehicles.search"),
    # Workshop read-only
    (re.compile(r"(زيار[ةه]\s*نشط|مركبات\s*مفتوح|active\s*visits|كم\s*زيار|مركبات\s*داخل|قائم[ةه]\s*العمل)", re.IGNORECASE), "workshop.active_visits"),
    # Natural Language Search (top debtors / overdue / biggest)
    (re.compile(r"(اكثر\s*(?:ال)?عملاء\s*مديوني|أكثر\s*(?:ال)?عملاء\s*مديوني|اعلي\s*(?:ال)?مدينين|أعلى\s*(?:ال)?مدينين|اكبر\s*مدينين|أكبر\s*مدينين|كبار\s*(?:ال)?مدينين|الفواتير\s*المتأخر|فواتير\s*متأخر|آجل\s*متأخر|اكبر\s*(?:ال)?عمليات|أكبر\s*(?:ال)?عمليات|اعلي\s*مبيعات|أعلى\s*مبيعات|اقل\s*(?:ال)?مركبات\s*نشاط|أقل\s*(?:ال)?مركبات\s*نشاط|مركبات\s*راكد)", re.IGNORECASE), "nl.search"),
    # Pending approvals
    (re.compile(r"(موافقات\s*معلق|اعتمادات\s*معلق|بانتظار\s*(?:ال)?اعتماد|pending\s*approvals?|تحت\s*المراجع|تنتظر\s*موافق)", re.IGNORECASE), "runtime.pending_approvals"),
    # Audit trail
    (re.compile(r"(سجل\s*(?:ال)?تدقيق|audit\s*trail|آخر\s*(?:ال)?أحداث|أحداث\s*النظام|من\s*غيّر|تتبع\s*التغيير)", re.IGNORECASE), "runtime.audit_recent"),
    # Services + Parts catalog awareness
    (re.compile(r"(تصنيفات\s*(?:ال)?خدمات|أقسام\s*(?:ال)?خدمات|اقسام\s*(?:ال)?خدمات|service\s*categor|أنواع\s*(?:ال)?خدمات|انواع\s*(?:ال)?خدمات)", re.IGNORECASE), "services.categories"),
    (re.compile(r"(الخدمات\s*المتوفرة|الخدمات\s*المتاحة|اظهر\s*(?:ال)?خدمات|أظهر\s*(?:ال)?خدمات|كم\s*سعر\s*(?:خدمة|تغيير|إصلاح|اصلاح|فحص)|سعر\s*خدمة|قائمة\s*(?:ال)?خدمات|service\s*list)", re.IGNORECASE), "services.search"),
    (re.compile(r"(قطع\s*(?:ال)?غيار|كم\s*(?:عندي|عندنا)\s*(?:قطعة|قطع)|كم\s*سعر\s*القطعة|بحث\s*(?:عن\s*)?قطعة|inventory\s*list|parts\s*list)", re.IGNORECASE), "parts.list"),
]


# Tools that accept a `query` parameter parsed from the user's free text
_QUERY_AWARE_TOOLS = {"customers.search", "vehicles.search", "parts.search", "nl.search", "services.search", "parts.list", "operations.search"}


def _extract_query(text: str, tool_name: str) -> str:
    """Pull a likely search term out of the message for query-aware tools.

    Strategy:
      • strip the leading verb/keyword (ابحث عن، رصيد، بيانات، بيع، سعر، ...).
      • drop common Arabic stop-words.
      • keep only the noun/proper-noun portion.
    """
    if not text:
        return ""
    # nl.search uses the FULL message (the NL handler does its own matching)
    if tool_name == "nl.search":
        return text.strip()
    raw = text.strip()
    # Remove leading request verbs / question words
    raw = re.sub(
        r"^(?:كم\s+رصيد|كم\s+سعر|سعر|تكلفة|كم\s+ع?ندي|كم\s+ع?ندك\s*من|كم\s+مخزون|كم\s+يتوفر|متوفر\s+لدينا|هل\s+ع?ندنا|ابحث\s*عن|أبحث\s*عن|بحث\s*عن|اعرض|عرض|بيانات|أين|أرني|ارني|لوحة|رقم\s*لوحة|رقم\s*(?:ال)?لوحة|رصيد\s*(?:ال)?عميل|ذمم\s*(?:ال)?عميل|أبيع|ابيع|بيع|اشتري|شراء|أحتاج|احتاج|أعطني|اعطني|عطني|أعطيني|ابغى|أبغى|أريد|اريد|وريني|اخبرني|أخبرني)\s*",
        "",
        raw,
        flags=re.IGNORECASE,
    )
    # Drop info-type nouns (ملاحظة / تفاصيل / معلومات)
    raw = re.sub(
        r"(?:ملاحظ[ةه]?|ملاحظات|تفاصيل|معلومات|بيانات|ملف|حساب|سجل|رصيد)",
        "",
        raw,
        flags=re.IGNORECASE,
    )
    # Drop entity nouns ("العميل" / "المركبة" / "القطعة" / "العملية")
    if tool_name == "customers.search":
        raw = re.sub(r"(?:ال)?عميل[ةه]?|(?:ال)?زبون[ةه]?|(?:ال)?عملي[ةه]?(?:ات)?|(?:ال)?عمل(?:يات)?", "", raw, flags=re.IGNORECASE)
    elif tool_name == "vehicles.search":
        raw = re.sub(r"(?:ال)?مركب[ةه]?|(?:ال)?سيار[ةه]?", "", raw, flags=re.IGNORECASE)
    elif tool_name == "parts.search":
        raw = re.sub(r"(?:ال)?قطع[ةه]?(?:\s*غيار)?|(?:ال)?مخزون", " ", raw, flags=re.IGNORECASE)
    elif tool_name == "operations.search":
        raw = re.sub(r"(?:ال)?عملي[ةه]?(?:ات)?|(?:ال)?عمل(?:يات)?", " ", raw, flags=re.IGNORECASE)
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

    # Smart fallback: if no tools matched AND the message looks like it contains
    # a proper Arabic name (2+ word name), try customers.search + operations.search
    if not matched and t:
        # Detect multi-word Arabic proper name (at least 2 words with 2+ Arabic chars each)
        _name_pattern = re.compile(
            r"[\u0621-\u064A]{2,}\s+(?:ال)?[\u0621-\u064A]{2,}(?:\s+(?:ال)?[\u0621-\u064A]{2,})*"
        )
        # Exclude common non-name phrases
        _non_name = re.compile(r"(?:لا\s+(?:توجد|يوجد|يمكن)|كيف\s+(?:يمكن|اقدر))", re.IGNORECASE)
        if _name_pattern.search(t) and not _non_name.search(t):
            matched.append("customers.search")
            matched.append("operations.search")

    return matched


# ---------- L16: write-action intent gate + executor wiring ----------

# Strong write verbs (MSA + Saudi/Qassimi dialect). NOTE: "بيع" is intentionally
# excluded — "بيع X" is a parts-search pattern in this domain, not a write.
_ACTION_VERB_RE = re.compile(
    r"(?:^|\s)(?:سجّ?ل|اضف|أضف|اضيف|أضيف|ضيف|ضع|حط|انشئ|أنشئ|انشاء|افتح|أفتح|"
    r"اصدر|أصدر|اعمل|سوّ?ي|احذف|أحذف|امسح|شيل|الغ|ألغ|اغلق|أغلق|اقفل|"
    r"عدّ?ل|غيّ?ر|حدّ?ث|register|create|add|delete|close|open|update)"
    r"(?:ها|ه|هم|هن|ني|نا|وا|وه|ي|ين)?(?=\s|$)",
    re.IGNORECASE,
)
# Dialect "I want to <do>" → treat as an action even without a leading verb.
_DIALECT_INTENT_RE = re.compile(
    r"(?:ابغى|أبغى|ابي|أبي|ودّ?ي|بغيت|ابا|أبا)\s+(?:اضيف|أضيف|اسجّ?ل|أسجّ?ل|افتح|"
    r"احذف|امسح|شيل|اغلق|اقفل|ضيف|حط|اعمل|انشئ)",
    re.IGNORECASE,
)
# Clear read/question lead-ins — keep these on the answering path.
_QUESTION_LEAD_RE = re.compile(
    r"^\s*(?:ما|ماذا|كم|كيف|متى|اين|أين|هل|من\s|لماذا|ليش|وش|ايش|إيش|وين|ابحث|أبحث|"
    r"اعرض|أعرض|عرض|اعطني|أعطني|عطني|اخبرني|أخبرني|ارني|أرني|وريني|"
    r"why|what|how|when|where|who|show|find|search|list)",
    re.IGNORECASE,
)


def looks_like_action(text: str) -> bool:
    """Backend safety-net: should this message be EXECUTED (write) instead of
    answered (read)? Arabic-normalised so morphology/dialect/hamza don't break it.

    This is the fix for "البوت يعطي تعليمات بدل التنفيذ": even when the frontend
    regex misses a command, the kernel still routes it through the executor.
    """
    if not text or not text.strip():
        return False
    raw = text.strip()
    try:
        from core.arabic_nlp import normalize_arabic
        norm = normalize_arabic(raw)
    except Exception:
        norm = raw.lower()
    if _DIALECT_INTENT_RE.search(raw) or _DIALECT_INTENT_RE.search(norm):
        return True
    if _ACTION_VERB_RE.search(raw) or _ACTION_VERB_RE.search(norm):
        return True
    # Structured ERP signal (phone, or vehicle type + year) with no question lead.
    has_phone = bool(re.search(r"05\d{7,9}", norm))
    has_vehicle_year = bool(re.search(
        r"(?:صالون|جيب|شاحنه|بكب|فان|نقل|دباب|باص|هايلكس|هايلوكس|كامري|لاندكروزر|"
        r"باترول|اكسنت|سوناتا|النترا|كورولا|يارس|برادو|فورتشنر|ددسن|hilux|camry)\s*\d{4}",
        norm,
    ))
    is_question = bool(_QUESTION_LEAD_RE.search(raw))
    if (has_phone or has_vehicle_year) and not is_question:
        return True
    return False


def _build_action_chat_response(*, sid: str, message: str, exec_res: Dict[str, Any]) -> Dict[str, Any]:
    """Format a Unified-Executor result as a chat reply (confirmation + cards)."""
    status = exec_res.get("status")
    action = (exec_res.get("action") or {}).get("action") or "unknown"
    label = {
        "create_customer": "عميل", "create_vehicle": "مركبة", "create_visit": "زيارة",
        "delete_operation": "حذف عملية", "close_visits": "إغلاق الزيارات",
    }.get(action, action)
    cards: List[Dict[str, Any]] = []
    entity_id = None
    if status == "committed":
        r = exec_res.get("result") or {}
        entity_id = r.get("id")
        name = (r.get("name") or r.get("plate_number") or r.get("plateNumber")
                or r.get("id") or "")
        if r.get("_duplicate"):
            response_text = f"⚠️ **{label} موجود مسبقاً** — {name}\nلم أُنشئ نسخة مكررة."
        else:
            response_text = f"✅ **تم بنجاح** — {label}: {name}\n📌 حُفظ في قاعدة البيانات."
    else:  # pending_approval
        approval_id = (exec_res.get("approval") or {}).get("approval_id")
        draft_id = (exec_res.get("draft") or {}).get("id")
        response_text = f"⏳ **بانتظار اعتمادك** — هذه عملية حساسة ({label})."
        cards = [{
            "type": "ApprovalCard", "id": approval_id,
            "title": f"موافقة — {label}", "status": "pending",
            "data": {"approval_id": approval_id, "draft_id": draft_id, "status": "pending"},
            "actions": [
                {"id": "approve", "label": "✓ اعتماد", "intent": "runtime",
                 "endpoint": f"/api/runtime/approvals/{approval_id}/approve", "method": "POST"},
                {"id": "reject", "label": "✗ رفض", "intent": "runtime",
                 "endpoint": f"/api/runtime/approvals/{approval_id}/reject", "method": "POST"},
            ],
        }]
    shared_memory.append_message(sid, "assistant", response_text, meta={
        "intent": "action", "action": action, "status": status,
    })
    shared_memory.track_action(sid, "action", {
        "message": message[:160], "action": action, "status": status,
    })
    return {
        "session_id": sid, "agent": "Assistant", "assistant_name": ASSISTANT_NAME,
        "assistant_version": ASSISTANT_VERSION, "intent": "action",
        "tool_results": [], "response": response_text, "cards": cards,
        "context_snapshot": {}, "recent_actions": shared_memory.get_recent_actions(sid, limit=10),
        "ai_used": False, "model_used": None, "read_only": False, "mode": "action",
        # 🆕 the frontend dispatches finance:updated when this is a committed write
        "executed": {"status": status, "action": action, "entity_id": entity_id},
        "power": None,
    }



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
    model_provider: str = "anthropic",
    model_name: str = "claude-sonnet-4-6",
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
        # Phase 3A: replace `print` with structured logger; never leak raw user content.
        _log.warning("LLM call failed: %s", redact(str(e), max_len=160))
        return ""


# ---------- Public API ----------

ASSISTANT_NAME = "كاترينا"
ASSISTANT_VERSION = "L16"


def _system_prompt() -> str:
    """L5 system prompt — proactive helpful read-only assistant.

    Important: read-only = backend tools don't write. The assistant SHOULD still
    answer questions, search data, explain findings, summarise reports, etc.
    We only refuse when the user explicitly asks for CREATE/UPDATE/DELETE/APPROVE.
    """
    return (
        f"أنت **{ASSISTANT_NAME}** — المساعِدة الذكية التنفيذية لنظام إدارة «ورشة الكبير للسيارات».\n"
        "أنتِ لستِ مجرد دليل إرشادات — أنتِ مشغّلة فعلية للنظام: تُنفّذين الأوامر، تُجيبين، وتحلّلين.\n\n"
        "🎯 **مهمتك**:\n"
        "  • نفّذي طلبات المستخدم فعلياً (إنشاء عميل/مركبة/زيارة، فتح/إغلاق زيارة، حذف عملية…) — لا تكتفي بشرح الخطوات.\n"
        "  • أجيبي على الأسئلة من البيانات الفعلية (السياق + نتائج الأدوات).\n"
        "  • اشرحي التنبيهات والقيود والذمم والتقارير، ولخّصي الأرقام بذكاء.\n"
        "  • كوني استباقية: بعد أي إجابة اقترحي الخطوة التالية المنطقية.\n\n"
        "🗣️ **شخصيتك ولهجتك**:\n"
        "  • ودودة، خبيرة، واثقة، مختصرة. تحيّة دافئة عند بداية المحادثة (مثل: 'هلا والله 👋').\n"
        "  • افهمي وتجاوبي مع **اللهجة القصيمية/النجدية**: 'وش'=ماذا، 'ابي/ابغى/ودّي'=أريد، 'وين'=أين، 'حط/ضيف'=أضف، 'شيل'=احذف، 'الحين'=الآن، 'كم عليه'=كم رصيده، 'زين'=تمام، 'لا هنت'=شكراً.\n"
        "  • استخدمي إيموجي باعتدال (✅ ⚠️ 🔧 🚗 💰 📊).\n\n"
        "🔧 **معرفتك الفنية (ورشة الكبير)**:\n"
        "  • متخصصة في محركات الديزل والبنزين: Toyota (فورتشنر، لاندكروزر 200/300، هايلكس، برادو)، Isuzu (ديماكس، MU-X)، Mitsubishi (باجيرو، L200).\n"
        "  • تقدّمين **تشخيصاً مبدئياً** للأعطال حسب العَرَض/الصوت (طقطقة، صفير، دخان أسود/أزرق/أبيض)، وتوضّحين الأسباب المحتملة والقطع المرشّحة للفحص.\n"
        "  • تعرفين القطع الشائعة وأرقامها التقريبية (فلتر زيت/ديزل/هواء، بخاخات، تيربو، طرمبة) — وللأسعار الدقيقة تُحيلين لجرد المخزون أو أداة parts.search.\n"
        "  • معلومات الورشة: 📞 0553280100 — الدوام 8ص–12ظ و 4ع–9م (السبت–الخميس، الجمعة إجازة).\n"
        "  • أكّدي دائماً أن أي تشخيص **مبدئي** ويحتاج فحصاً مباشراً.\n\n"
        "🧰 **أدوات القراءة المتاحة** (تُستدعى تلقائياً حسب نية السؤال):\n"
        "  • firewall.health_score / top_alerts / cash_flow / operation_integrity\n"
        "  • finance.ar_summary (ذمم العملاء) / finance.payables_summary (ذمم الموردين)\n"
        "  • workshop.active_visits / inventory.low_stock / operations.recent\n"
        "  • customers.search / vehicles.search / operations.search / parts.search\n\n"
        "📊 **التعامل مع النتائج**:\n"
        "  • نتيجة فارغة → قولي مباشرة 'لا توجد بيانات' بدون اعتذار.\n"
        "  • نتيجة ناجحة → نسّقيها (جدول Markdown/قائمة) وبفواصل آلاف للأرقام.\n\n"
        "⚙️ **التنفيذ**:\n"
        "  • أوامر الإنشاء/الحذف/الإغلاق تُنفَّذ مباشرة عبر محرك التنفيذ — وتظهر للمستخدم رسالة تأكيد '✅ تم'.\n"
        "  • إذا نقص حقل ضروري للتنفيذ (مثل الاسم أو رقم الجوال) → **اطلبي الحقل الناقص بوضوح**، ولا تقولي 'افتح الصفحة وأضف يدوياً'.\n"
        "  • العمليات الحساسة (حذف) تحتاج اعتماداً — اعرضيها كبطاقة موافقة.\n\n"
        "⚠️ **قواعد حاسمة**:\n"
        "  1. **ممنوع** 'دعني أتحقق' أو 'سأعود إليك' — أكملي الإجابة فوراً في نفس الرسالة.\n"
        "  2. **ممنوع** الرد بـ 'لا يمكنني، افتح الصفحة' عند طلب تنفيذ — إمّا نفّذتِ أو اطلبتِ المعلومة الناقصة.\n"
        "  3. كل رد نهائي ومفيد، بالعربية الواضحة، Markdown مسموح ومفضّل.\n"
    )


async def chat(
    *,
    session_id: Optional[str] = None,
    message: str,
    workshop_id: Optional[str] = None,
    force_agent: Optional[str] = None,  # kept for backward-compat; ignored in L5
    use_ai: bool = True,
    model: Optional[str] = None,  # 🆕 'gpt' (Emergent default) | 'ollama' (local)
    proposer: Optional[str] = None,  # 🆕 Phase 3C — Four-Eyes anchor (current user)
) -> Dict[str, Any]:
    """Main entry point for the assistant.

    Args:
      model: 'gpt' → Emergent gpt-4o-mini (default), 'ollama' → local llama3.2:3b.
             Any other value falls back to 'gpt'.

    Returns: {session_id, response, tool_results, recent_actions,
              context_snapshot, ai_used, model_used}
    """
    sid = session_id or f"session-{uuid.uuid4().hex[:10]}"
    shared_memory.append_message(sid, "user", message)

    # 🆕 Phase 3B Round 2 — Power Mode (multi-intent + drafts).
    # If the message starts with "/power", we bypass the LLM and instead return
    # a batch of draft cards (read-only proposals — Phase 3C will commit).
    power_block: Optional[Dict[str, Any]] = None
    if power_mode.detect_mode(message) == "power":
        power_block = await power_mode.power_process(
            session_id=sid,
            message=message,
            # 🆕 Phase 3C: thread the user identity through so Four-Eyes works.
            proposer=proposer,
        )
        # Record in shared_memory for the audit trail
        shared_memory.track_action(sid, "power_mode", {
            "executed": power_block.get("executed", 0),
            "commands": power_block.get("commands", [])[:5],
        })

    # 🆕 L16 (كاترينا) — Unified action execution. If the message is a WRITE
    # command (create/delete/close/...), execute it directly through the
    # Unified Execution Engine and return a confirmation. This is the backend
    # safety-net that guarantees execution even if the frontend router missed it.
    if not power_block and looks_like_action(message):
        try:
            from core import unified_executor
            exec_res = await unified_executor.execute_text(
                message, proposer=proposer, session_id=sid,
            )
        except Exception as e:
            _log.warning("unified action execution failed: %s", redact(str(e), max_len=120))
            exec_res = None
        if exec_res and exec_res.get("status") in ("committed", "pending_approval"):
            return _build_action_chat_response(sid=sid, message=message, exec_res=exec_res)
        # read_only / rejected / error → fall through to the normal read path

    # 1) Detect which read-only tools to invoke
    tool_names = detect_tools(message)
    tool_results: List[Dict[str, Any]] = []
    cards: List[Dict[str, Any]] = []  # 🆕 collected from each tool result
    for tn in tool_names:
        kwargs: Dict[str, Any] = {"workshop_id": workshop_id or "finmodule-sync"}
        if tn in _QUERY_AWARE_TOOLS:
            q = _extract_query(message, tn)
            if q:
                kwargs["query"] = q
        result = await tool_router.call_tool(tn, **kwargs)
        tool_results.append(result)
        # Pull any cards the tool emitted
        if isinstance(result, dict) and result.get("success"):
            tool_cards = (result.get("result") or {}).get("cards") if isinstance(result.get("result"), dict) else None
            if tool_cards and isinstance(tool_cards, list):
                cards.extend(tool_cards)
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

    # 🆕 Phase 3C.9 — inject live workshop brief so the LLM knows the catalog.
    try:
        from core import context_brief as _cb
        _brief = await _cb.get_context_brief(limit_per_kind=5)
        brief_text = _cb.to_llm_brief_text(_brief)
    except Exception as _e:
        brief_text = ""

    # 3) System message (L5: single assistant, no agent persona)
    system_msg = _system_prompt() + "\n\n" + context_text
    if brief_text:
        system_msg += "\n\n" + brief_text

    # 4) Append tool results
    if tool_results:
        tool_section = "\n\n🛠️ نتائج الأدوات المنفّذة لهذا السؤال:\n"
        for tr in tool_results:
            tool_section += f"  • {tr.get('tool')}: {tr.get('result') if tr.get('success') else tr.get('error')}\n"
        system_msg += tool_section

    # 5) Get conversation history
    history = ai_context.get_conversation_history(sid, limit=10)

    # 6) Call LLM — choose provider per `model` param
    response_text = ""
    model_used: Optional[str] = None
    selected = (model or "gpt").lower()
    if use_ai:
        if selected == "ollama":
            # Local Ollama path (Phase 3B kickoff)
            from core import llm_helpers
            if await llm_helpers.is_ollama_alive():
                response_text = await llm_helpers.call_ollama(
                    system_prompt=system_msg,
                    user_message=message,
                    history=history[:-1],
                )
                if response_text:
                    model_used = f"ollama/{llm_helpers.OLLAMA_DEFAULT_MODEL}"
            else:
                _log.info("ollama not reachable; falling back to Emergent claude-sonnet-4-6")
        # Emergent path (default + fallback when Ollama is offline)
        if not response_text:
            response_text = await _llm_chat(
                session_id=sid,
                system_message=system_msg,
                user_message=message,
                history=history[:-1],
            )
            if response_text:
                model_used = "emergent/claude-sonnet-4-6"

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
    # 🆕 If we ran Power Mode, augment the assistant message with a summary
    if power_block:
        drafts = power_block.get("drafts") or []
        # Inject draft cards into the cards stream so the UI renders them
        cards.extend(drafts)
        # Prepend a short Markdown summary to make the chat reply useful
        summary_lines = [
            f"⚡ **Power Mode** — جهّزت {len(drafts)} مسوّدة (read-only):",
        ]
        for i, d in enumerate(drafts, 1):
            kind = d.get("intent_kind") or "?"
            label = (d.get("data") or {}).get("label") or kind
            extra_bits = []
            data = d.get("data") or {}
            if data.get("name"):
                extra_bits.append(data["name"])
            if data.get("plate"):
                extra_bits.append(f"لوحة {data['plate']}")
            if data.get("amount"):
                extra_bits.append(f"{data['amount']:,.2f} ر.س")
            if data.get("_resolved_from"):
                extra_bits.append(f"(من سياق: {data['_resolved_from'].get('title','')})")
            extras = " — ".join([str(x) for x in extra_bits if x]) or "بدون تفاصيل"
            summary_lines.append(f"  {i}. **{label}** — {extras}")
        summary_lines.append("")
        summary_lines.append("> 🛡️ المسوّدات للمراجعة فقط — التنفيذ الفعلي يحتاج موافقة (Phase 3C).")
        power_summary = "\n".join(summary_lines)
        response_text = f"{power_summary}\n\n{response_text}" if response_text else power_summary
        intent = "power_mode"

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

    # 🆕 Phase 3A — persistent audit log (best-effort, never breaks chat).
    ai_used_flag = bool(use_ai and _emergent_llm_key() and response_text)
    try:
        from domains.bot_audit import audit_service
        await audit_service.log_chat(
            session_id=sid,
            user_message=message,
            intent=intent,
            tools_called=[t.get("tool") for t in tool_results if t.get("tool")],
            ai_used=ai_used_flag,
            fallback_used=False,  # wired in Phase 3B with Groq fallback
        )
    except Exception as e:
        _log.warning("audit log dispatch failed (non-fatal): %s", redact(str(e), max_len=120))

    # 🆕 Phase 3B — Conversation memory: remember the first entity of each kind
    for c in cards:
        ctype = c.get("type") or ""
        key = {
            "CustomerCard": "last_customer",
            "VehicleCard": "last_vehicle",
            "InvoiceCard": "last_invoice",
            "OperationCard": "last_operation",
            "SupplierCard": "last_supplier",
            "InventoryCard": "last_part",
        }.get(ctype)
        if key:
            # Persist only the first card of each kind from this exchange
            existing = shared_memory.get_context(sid, key)
            if not existing or existing.get("id") != c.get("id"):
                shared_memory.set_context(sid, key, {
                    "id": c.get("id"),
                    "title": c.get("title"),
                    "type": ctype,
                })
        # 🆕 Round 2: also track section memory for draft cards
        if ctype.endswith("DraftCard"):
            section = (c.get("data") or {}).get("section")
            if section:
                shared_memory.set_context(sid, "last_section", section)
        # 🆕 Round 3: feed Vector Memory for semantic recall
        try:
            descriptor_bits = [c.get("title") or ""]
            data = c.get("data") or {}
            for v in data.values():
                if isinstance(v, (str, int, float)) and str(v):
                    descriptor_bits.append(str(v))
            descriptor = " ".join(descriptor_bits)[:300]
            if descriptor.strip():
                vector_memory.store_memory(
                    session_id=sid,
                    text=descriptor,
                    entity_type=ctype or "Card",
                    entity_id=c.get("id"),
                    payload={"draft": ctype.endswith("DraftCard")},
                )
        except Exception as e:
            _log.debug("vector_memory store_memory skipped: %s", redact(str(e), max_len=100))

    return {
        "session_id": sid,
        # Backward compatibility: include "agent" key but always set to single assistant
        "agent": "Assistant",
        "assistant_name": ASSISTANT_NAME,
        "assistant_version": ASSISTANT_VERSION,
        "intent": intent,
        "tool_results": tool_results,
        "response": response_text,
        "cards": cards,  # 🆕 flat list of cards for the drawer to render
        "context_snapshot": snapshot,
        "recent_actions": shared_memory.get_recent_actions(sid, limit=10),
        "ai_used": ai_used_flag,
        "model_used": model_used,
        "read_only": True,
        # 🆕 Round 2: expose power-mode metadata so the UI can render the
        # "drafts" tray (count + per-command summary). When `mode == 'normal'`
        # this block is null.
        "mode": (power_block or {}).get("mode", "normal"),
        "power": power_block,
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
