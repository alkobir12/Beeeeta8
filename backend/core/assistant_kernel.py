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
import asyncio
import os
import re
import time
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
    (re.compile(r"(integrity|ربط|قيد\s*مفقود|قيود\s*مفقود|بدون\s*قيد|بدون\s*قيود|بلا\s*قيد|بلا\s*قيود|ليس\s+لها\s+قيد|ما\s+لها\s+قيد|سلام[ةه]|تنبيه.*عمل|كروت|بطاق[ةه]|warning.*op|missing.*journal|عمليات.*خطأ|عمليات.*مشكل|قيود.*مفقود|عمليات.*بدون)", re.IGNORECASE), "firewall.operation_integrity"),
    (re.compile(r"((?:تقرير|ملخص|مارايك|رأيك|اعرض|أعطني|اعطني|كم)\s*(?:ال)?(?:مبيعات|ايراد|إيراد|الايراد|الإيراد)|(?:ال)?(?:مبيعات|ايراد|إيراد)\s*(?:هذا\s*(?:الأسبوع|الاسبوع|الشهر)|اليوم|كل\s*(?:ال)?مد[ةه]|الإجمالي|الاجمالي|الكامل|كامل))", re.IGNORECASE), "finance.sales_report"),
    (re.compile(r"(تدفق|cash\s*flow|مصاريف|مصروف|cash_flow|سيول[ةه])", re.IGNORECASE), "firewall.cash_flow"),
    # Finance read-only
    # 🕒 القيود المؤقتة للبيع الآجل (قاعدة المالك) → ملخص الذمم SSOT
    (re.compile(r"(قيود\s*مؤقت|قيد\s*مؤقت|(?:ال)?قيود\s*(?:ال)?مؤقت[ةه]?|بيع\s*آجل|بيع\s*اجل|مبيعات\s*آجل[ةه]?|مبيعات\s*اجل[ةه]?|deferred\s*sales?)", re.IGNORECASE), "finance.ar_summary"),
    (re.compile(r"(ذمم\s*(?:ال)?عملاء|مدين|debtors?|دين العميل|ar\s*summary|متأخر|آجل\s*(?:ال)?عملاء|^\s*ذمم\s*$|ذمم\s*مدين|(?:اجمالي|إجمالي|مجموع|كم)\s*(?:ال)?ذمم|(?:ال)?ذمم\s*(?:ال)?حالي|(?:اعرضي?|أعرضي?|عرضي?|وريني|شوفي?)\s*(?:لي\s*)?(?:ال)?ذمم|^\s*(?:ال)?ذمم\s*$)", re.IGNORECASE), "finance.ar_summary"),
    # Suppliers AP
    (re.compile(r"(ذمم\s*(?:ال)?مورد|دائن|دائنين|payables?|ap\s*summary|نستحق|نحن\s*مدين|للمورد|ذمم\s*ال?ورش[ةه])", re.IGNORECASE), "finance.payables_summary"),
    # Supplier search / statement — لا تُرسل الموردين إلى customers.search
    (re.compile(r"((?:سجل|حرك[ةه]|كشف|قيود|عمليات|بيانات|ابحث|أبحث|عرض|اعرض|أعطني|اعطني|عطني).*?(?:ال)?مورد|(?:ال)?مورد\s+\S{2,})", re.IGNORECASE), "suppliers.search"),
    (re.compile(r"((?:سجل|حرك[ةه]|كشف|قيود|عمليات).*?(?:ال)?مورد|(?:قيود|حرك[ةه])\s+(?:المورد|مورد))", re.IGNORECASE), "accounting.journal_entries"),
    # Inventory low stock
    (re.compile(r"((?:ال)?قطع\s*(?:ال)?ناقص|مخزون\s*منخفض|low\s*stock|(?:ال)?قطع\s*انتهت|قطع\s*أوشكت|نفاد|نفذت\s*(?:ال)?قطع|(?:ل?ل?)?(?:ال)?حد\s*(?:ال)?أدنى|قطع.*ناقص|نواقص\s*المخزون|تنبيه.*مخزون|تنبيهات\s*المخزون)", re.IGNORECASE), "inventory.low_stock"),
    # Parts search — "بيع X" / "أبيع X" / "سعر X" / "كم سعر X" / "كم عندي X" / "هل عندنا X"
    (re.compile(r"(\bبيع\b|\bأبيع\b|\bابيع\b|اشتري|شراء\s+قطع|كم\s*سعر|سعر\s+(?:ال)?(?:قطع|فلتر|زيت|بطار|طرمب|ربلات|مساحات|بواجي|بلف|كبسول|كمبيوتر|مكيف|ايرباغ|دبري|كبائن|سلندر|طقم|كرنك|كومة|كوب|كولر|سير|تيل|قرص|دريم|قار|بوش|طبه)|تكلفة\s+قطع|كم\s+ع?ندي|كم\s+يتوفر|متوفر\s+لدينا|هل\s+ع?ندنا|أبحث\s+عن\s+قطع|ابحث\s+عن\s+قطع|بحث\s+عن\s+قطع|كم\s+مخزون|كم\s+ع?ندك\s+من|أحتاج\s+قطع|احتاج\s+قطع)", re.IGNORECASE), "parts.search"),
    # Recent operations — يدعم «آخر خمس/عشر/5 عمليات»
    (re.compile(r"((?:آخر|أخر|اخر|أحدث|احدث)\s*(?:ال)?(?:خمسه?|خمس|عشره?|عشر|ثلاثه?|ثلاث|اربعه?|أربعه?|اربع|أربع|ست[ةه]?|سبع[ةه]?|ثمانيه?|تسع[ةه]?|\d+)?\s*(?:ال)?(?:عمليات|عمليتين|عمليتان|مبيعات)|recent\s*operations?|عمليات\s*اليوم)", re.IGNORECASE), "operations.recent"),
    (re.compile(r"((?:آخر|أخر|اخر|أحدث|احدث|تفاصيل)\s*(?:ال)?(?:\d+\s*)?(?:مركب[ةه]|سيار[ةه]|مركبات|سيارات)|ماهي\s*(?:آخر|اخر)\s*مركب[ةه])", re.IGNORECASE), "vehicles.recent"),
    # 🏆 Top sold services — «اكثر الخدمات بيعاً/مبيعاً/طلباً»
    (re.compile(r"((?:اكثر|أكثر|اعلي|أعلى|اكبر|أكبر)\s*(?:ال)?(?:خدم(?:ات|ة|ه)|بند|بنود|صنف|اصناف|أصناف|قطع[ةه]?)\s*(?:بيع|مبيع|طلب|تكرار)?|(?:ال)?(?:خدمات|بنود|اصناف|أصناف)\s*(?:الأكثر|الاكثر)\s*(?:بيع|مبيع|طلب)|بنود\s*(?:ال)?سيارات|top\s*(?:sold\s*)?services)", re.IGNORECASE), "operations.top_services"),
    # 🚗 Vehicle counts by status — «كم مركبة حالية» / «عدد المركبات»
    (re.compile(r"(كم\s*(?:ال)?مركب|عدد\s*(?:ال)?مركبات|كم\s*(?:ال)?سيار|عدد\s*(?:ال)?سيارات|(?:ال)?مركبات\s*(?:ال)?(?:حالي|موجود)|مركبات\s*(?:في|ب)\s*(?:ال)?ورش)", re.IGNORECASE), "vehicles.status_summary"),
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
    # Pending approvals — لهجات ومسميات مختلفة (اعتمادات كاترينا / المسوّدات المعلّقة / إلخ)
    (re.compile(r"(اعتمادات\s*(?:كاترينا|(?:ال)?معلّ?ق|كاتري)|(?:ال)?اعتمادات\s*(?:ال)?معلّ?ق[ةه]?|موافقات\s*(?:معلق|بانتظار)|المسوّ?دات\s*(?:المعلّ?ق|بانتظار)|الطلبات\s*المعلّ?قه?|بانتظار\s*(?:ال)?(?:اعتماد|موافقه?|موافقة)|pending\s*approvals?|تحت\s*المراجع|تنتظر\s*موافق|تحتاج\s*اعتماد|كم\s*(?:في|عندي)\s*اعتماد|في\s*(?:ال)?اعتمادات|شوف\s*(?:ال)?اعتمادات)", re.IGNORECASE), "runtime.pending_approvals"),
    # Audit trail
    (re.compile(r"(سجل\s*(?:ال)?تدقيق|audit\s*trail|آخر\s*(?:ال)?أحداث|أحداث\s*النظام|من\s*غيّر|تتبع\s*التغيير)", re.IGNORECASE), "runtime.audit_recent"),
    # Services + Parts catalog awareness
    (re.compile(r"(تصنيفات\s*(?:ال)?خدمات|أقسام\s*(?:ال)?خدمات|اقسام\s*(?:ال)?خدمات|service\s*categor|أنواع\s*(?:ال)?خدمات|انواع\s*(?:ال)?خدمات)", re.IGNORECASE), "services.categories"),
    (re.compile(r"(الخدمات\s*المتوفرة|الخدمات\s*المتاحة|اظهر\s*(?:ال)?خدمات|أظهر\s*(?:ال)?خدمات|كم\s*سعر\s*(?:خدمة|تغيير|إصلاح|اصلاح|فحص)|سعر\s*خدمة|قائمة\s*(?:ال)?خدمات|service\s*list)", re.IGNORECASE), "services.search"),
    (re.compile(r"(قطع\s*(?:ال)?غيار|كم\s*(?:عندي|عندنا)\s*(?:قطعة|قطع)|كم\s*سعر\s*القطعة|بحث\s*(?:عن\s*)?قطعة|inventory\s*list|parts\s*list)", re.IGNORECASE), "parts.list"),
    # Accounting journal entries (real journal_entries table) — قيود يومية / دفتر اليومية / ميزان مراجعة
    (re.compile(r"(قيد\s*محاسب|قيود\s*محاسب|دفتر\s*(?:ال)?يومي[ةه]?|قيود\s*(?:ال)?يومي|القيود\s*المالي|ميزان\s*(?:ال)?مراجع|journal\s*entr|القيود\s*في\s*(?:ال)?دفتر|القيد\s*رقم|تفاصيل\s*(?:ال)?قيد|القيود\s*(?:ال)?محاسب|كل\s*(?:ال)?قيود|جميع\s*(?:ال)?قيود|(?:ال)?قيود\s*(?:ال)?كامل|كامل\s*(?:ال)?قيود|(?:اعرض|أعرض|عرض|اعطني|أعطني)\s*(?:ال)?قيود|راجعي?\s*(?:ال)?قيود|مراجعة\s*(?:ال)?قيود)", re.IGNORECASE), "accounting.journal_entries"),
    (re.compile(r"(ملفات\s*بدون\s*بنود|زيارات\s*بدون\s*بنود|عمليات\s*بدون\s*بنود|فواتير\s*بدون\s*بنود)", re.IGNORECASE), "operations.empty_items"),
]


# Tools that accept a `query` parameter parsed from the user's free text
_QUERY_AWARE_TOOLS = {"customers.search", "vehicles.search", "suppliers.search", "parts.search", "nl.search", "services.search", "parts.list", "operations.search", "accounting.journal_entries", "finance.sales_report"}


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
        r"^(?:كم\s+رصيد|كم\s+سعر|سعر|تكلفة|كم\s+ع?ندي|كم\s+ع?ندك\s*من|كم\s+مخزون|كم\s+يتوفر|متوفر\s+لدينا|هل\s+ع?ندنا|ابحثي?\s*عن|أبحثي?\s*عن|بحثي?\s*عن|اعرضي?|أعرضي?|عرضي?|بيانات|أين|أرني|ارني|لوحة|رقم\s*لوحة|رقم\s*(?:ال)?لوحة|رصيد\s*(?:ال)?عميل|ذمم\s*(?:ال)?عميل|أبيع|ابيع|بيع|اشتري|شراء|أحتاج|احتاج|أعطني|اعطني|عطني|أعطيني|ابغى|أبغى|أريد|اريد|وريني|اخبرني|أخبرني)\s*",
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
    elif tool_name == "suppliers.search":
        raw = re.sub(r"(?:ال)?مورد(?:ين)?|سجل|حرك[ةه]|كشف|قيود|عمليات", " ", raw, flags=re.IGNORECASE)
    elif tool_name == "accounting.journal_entries":
        raw = re.sub(r"(?:سجل|حرك[ةه]|كشف|قيود|قيد|محاسب(?:ي)?|دفتر|يومي(?:ه|ة)?|(?:ال)?مورد(?:ين)?)", " ", raw, flags=re.IGNORECASE)
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

    # رقم لوحة عارٍ مثل «ب د ل 1854» أو «ابحث عن ب د ل 1854» يجب أن يذهب للمركبات.
    if t and "vehicles.search" not in matched:
        if re.search(r"(?:^|\s)[\u0621-\u064A]{1,3}\s+[\u0621-\u064A]{1,3}\s+[\u0621-\u064A]{1,3}\s+\d{3,5}(?:\s|$)", t):
            matched.append("vehicles.search")

    if "suppliers.search" in matched and "customers.search" in matched:
        matched = [m for m in matched if m != "customers.search"]

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


# 🎯 L14-D1: إشارة ترتيبية لقائمة معروضة سابقاً («أول عميل في القائمة»)
_ORDINAL_LIST_RE = re.compile(
    r"(أول|اول|ثاني|ثالث|رابع|خامس|آخر|اخر)\s*(?:عميل|مورد|واحد|اسم)?\s*(?:في|من)?\s*(?:ال)?قائم[ةه]"
)

# ---------- L16: write-action intent gate + executor wiring ----------

# Strong write verbs (MSA + Saudi/Qassimi dialect). NOTE: "بيع" is intentionally
# excluded — "بيع X" is a parts-search pattern in this domain, not a write.
_ACTION_VERB_RE = re.compile(
    r"(?:^|\s)(?:سجّ?ل|اضف|أضف|اضيف|أضيف|ضيف|ضع|حط|انشئ|أنشئ|انشاء|افتح|أفتح|"
    r"اصدر|أصدر|اعمل|سوّ?ي|احذف|أحذف|امسح|شيل|الغ|ألغ|اغلق|أغلق|اقفل|"
    r"حصّ?ل|سدّ?د|اعكس|أعكس|فوتر|"
    r"اشتري|اشترى|شرا|شراء|شريت|شرينا|"
    r"عدّ?ل|غيّ?ر|حدّ?ث|register|create|add|delete|close|open|update|purchase|buy)"
    r"(?:تها|ته|تهم|تم|ت|ها|ه|هم|هن|ني|نا|وا|وه|ي|ين)?(?=\s|$)",
    re.IGNORECASE,
)
# Dialect "I want to <do>" → treat as an action even without a leading verb.
_DIALECT_INTENT_RE = re.compile(
    r"(?:ابغى|أبغى|ابي|أبي|ودّ?ي|بغيت|ابا|أبا)\s+(?:اضيف|أضيف|اسجّ?ل|أسجّ?ل|افتح|"
    r"احذف|امسح|شيل|اغلق|اقفل|ضيف|حط|اعمل|انشئ)",
    re.IGNORECASE,
)
# 🆕 Financial masdar/noun action forms the imperative verb regex misses
# (e.g. «تحصيل من فلان 2200 تحويل»، «300 خصم إداري»). These route to
# collect_payment / create_expense in the executor. Fires ONLY with a concrete
# amount and no question lead — so «كم التحصيل؟» stays on the read path.
_FIN_MASDAR_RE = re.compile(
    r"(?:تحصيل|سداد|دفعة|دفعه|دفع|خصم\s*إ?داري|خصم\s*اداري|إسقاط\s*رصيد|اسقاط\s*رصيد|"
    r"شطب\s*رصيد|إعفاء\s*رصيد|اعفاء\s*رصيد)",
    re.IGNORECASE,
)
# Clear read/question lead-ins — keep these on the answering path.
_QUESTION_LEAD_RE = re.compile(
    r"^\s*(?:ما|ماذا|كم|كيف|متى|اين|أين|هل|من\s|لماذا|ليش|وش|ايش|إيش|وين|ابحث|أبحث|"
    r"اعرض|أعرض|عرض|اعطني|أعطني|عطني|اخبرني|أخبرني|ارني|أرني|وريني|"
    r"why|what|how|when|where|who|show|find|search|list)",
    re.IGNORECASE,
)
# Phase C — bare confirmation / cancellation replies for a pending safe draft.
_CONFIRM_RE = re.compile(
    r"^\s*(?:نعم|أكّ?د|اكّ?د|تمام|موافق|ماشي|أوكي|اوكي|اوك|أوك|ok|okay|yes|"
    r"نفّ?ذ|اعتمد|إعتمد|أجل|ايوه|ايوا|إيه|اي\s*نعم|صح|أكيد|اكيد|كمّ?ل|أكمل|اكمل)\s*[.!؟]*\s*$",
    re.IGNORECASE,
)
_CANCEL_RE = re.compile(
    r"^\s*(?:لا|كلا|إلغاء|الغاء|ألغِ?|الغِ?|تجاهل|وقف|أوقف|تراجع|cancel|no|stop)\s*[.!؟]*\s*$",
    re.IGNORECASE,
)
# 🆕 «الغي آخر عملية / المسودة المعلقة» — سحب سياقي لآخر مسودة بانتظار الاعتماد
_CANCEL_DRAFT_VERB_RE = re.compile(
    r"(?:^|\s)(?:الغ|ألغ|إلغاء|الغاء|اسحب|إسحب|تراجع)", re.IGNORECASE,
)
_CANCEL_DRAFT_MARKER_RE = re.compile(
    r"(?:آخر|اخر|الأخيره?|الاخيره?|الأخيرة|الاخيرة|مسوّ?ده?|المسوّ?ده?|مسودة|المسودة|"
    r"معلّ?ق|المعلّ?ق|بانتظار|قيد\s*الانتظار)",
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
    is_question = bool(_QUESTION_LEAD_RE.search(raw) or _QUESTION_LEAD_RE.search(norm))
    if is_question and re.search(r"(?:ال)?مورد|supplier", raw, re.IGNORECASE):
        return False
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
    # 🆕 Financial masdar command (تحصيل/سداد/خصم إداري/إسقاط رصيد) with a concrete
    # amount and no question lead → EXECUTE (routes to collect_payment/create_expense).
    # Fixes «التحصيل لا يُثبَّت»: the bare masdar was missed here, so the message fell to
    # the LLM which faked a «اكتب نعم» card that could never commit.
    if (_FIN_MASDAR_RE.search(raw) or _FIN_MASDAR_RE.search(norm)) and not is_question:
        return True
    if (has_phone or has_vehicle_year) and not is_question:
        return True
    return False


def _build_approval_actions(action: str, draft_id: str, approval_id: str,
                            payload: Dict[str, Any], echo: Dict[str, Any]) -> List[Dict[str, Any]]:
    """يُنشئ قائمة الأزرار السياقية لبطاقة الاعتماد. الأزرار الأساسية (اعتماد/رفض) دائماً.
    الأزرار الإضافية تظهر فقط لنية الشراء (المرحلة 2)."""
    actions: List[Dict[str, Any]] = [
        {"id": "approve", "label": "✓ اعتماد", "intent": "runtime",
         "endpoint": f"/api/runtime/approvals/{approval_id}/approve", "method": "POST"},
        {"id": "reject", "label": "✗ رفض", "intent": "runtime",
         "endpoint": f"/api/runtime/approvals/{approval_id}/reject", "method": "POST"},
    ]
    if action != "create_purchase":
        return actions

    # 🛒 أزرار سياقية للشراء
    pm = str((echo or {}).get("payment_method") or payload.get("payment_method") or "cash").lower()
    # زر تبديل طريقة الدفع (يظهر الطريقة البديلة الأكثر شيوعاً)
    if pm == "cash":
        actions.append({
            "id": "switch_transfer", "label": "↔ تحويل بنكي",
            "intent": "runtime",
            "endpoint": f"/api/runtime/drafts/{draft_id}/patch", "method": "POST",
            "body": {"ops": [{"op": "set_payment_method", "value": "transfer"}]},
        })
    elif pm == "transfer":
        actions.append({
            "id": "switch_cash", "label": "↔ نقدي",
            "intent": "runtime",
            "endpoint": f"/api/runtime/drafts/{draft_id}/patch", "method": "POST",
            "body": {"ops": [{"op": "set_payment_method", "value": "cash"}]},
        })
    else:  # credit → toggle to cash as the safest default
        actions.append({
            "id": "switch_cash", "label": "↔ نقدي",
            "intent": "runtime",
            "endpoint": f"/api/runtime/drafts/{draft_id}/patch", "method": "POST",
            "body": {"ops": [{"op": "set_payment_method", "value": "cash"}]},
        })

    # زر تبديل الضريبة (none ↔ excluded 15%)
    vat = payload.get("vat") or {}
    vat_mode = str(vat.get("mode") or "none").lower()
    if vat_mode == "none":
        actions.append({
            "id": "add_vat", "label": "➕ إضافة ضريبة 15%",
            "intent": "runtime",
            "endpoint": f"/api/runtime/drafts/{draft_id}/patch", "method": "POST",
            "body": {"ops": [{"op": "set_vat_mode", "value": "excluded", "rate": 0.15}]},
        })
    else:
        actions.append({
            "id": "remove_vat", "label": "🚫 بدون ضريبة",
            "intent": "runtime",
            "endpoint": f"/api/runtime/drafts/{draft_id}/patch", "method": "POST",
            "body": {"ops": [{"op": "set_vat_mode", "value": "none"}]},
        })

    # زر «إضافة المورد» يظهر إما بوسم is_new صريح من الـ LLM/resolver، أو عندما
    # يوجد اسم مورد بلا id مربوط (حالة الشراء من مورد جديد افتراضياً).
    supplier = payload.get("supplier") or {}
    if isinstance(supplier, str):
        supplier = {"name": supplier}
    supplier_name = str(supplier.get("name") or "").strip()
    supplier_id = supplier.get("id")
    supplier_is_new = bool(supplier.get("is_new") or payload.get("supplier_is_new"))
    if supplier_name and (supplier_is_new or not supplier_id):
        actions.append({
            "id": "add_supplier",
            "label": f"➕ إضافة المورد «{supplier_name}»",
            "intent": "runtime",
            "endpoint": f"/api/runtime/drafts/{draft_id}/spawn_supplier",
            "method": "POST",
            "body": {"name": supplier_name},
        })

    return actions


def _build_action_chat_response(*, sid: str, message: str, exec_res: Dict[str, Any]) -> Dict[str, Any]:
    """Format a Unified-Executor result as a chat reply (confirmation + cards)."""
    status = exec_res.get("status")
    action = (exec_res.get("action") or {}).get("action") or "unknown"
    label = {
        "create_customer": "عميل", "create_vehicle": "مركبة", "create_visit": "زيارة",
        "create_supplier": "مورّد",
        "delete_operation": "حذف عملية", "close_visits": "إغلاق الزيارات",
        "delete_customer": "حذف عميل", "delete_vehicle": "حذف مركبة",
        "update_customer": "تعديل عميل", "update_vehicle": "تعديل مركبة",
        "create_invoice": "فاتورة", "collect_payment": "تحصيل دفعة",
        "create_expense": "مصروف", "reverse_entry": "قيد عكسي",
        "create_purchase": "شراء",
    }.get(action, action)
    cards: List[Dict[str, Any]] = []  # 🆕 collected from each tool result
    entity_id = None
    approval_id = None
    if status == "committed":
        r = exec_res.get("result") or {}
        entity_id = r.get("id")
        if action in ("delete_customer", "delete_vehicle"):
            nm = r.get("name") or r.get("id")
            response_text = (f"✅ **تم الحذف** — {label}: {nm}"
                             if r.get("deleted") else f"⚠️ لم أعثر على ما يُحذف ({label}).")
        elif action in ("update_customer", "update_vehicle"):
            nm = r.get("name") or r.get("plate_number") or r.get("id")
            fields = "، ".join(r.get("_updated_fields") or [])
            response_text = f"✅ **تم التعديل** — {label}: {nm}\n📝 حُدّث: {fields}"
        else:
            name = (r.get("name") or r.get("plate_number") or r.get("plateNumber")
                    or r.get("id") or "")
            if r.get("_duplicate"):
                response_text = f"⚠️ **{label} موجود مسبقاً** — {name}\nلم أُنشئ نسخة مكررة."
            else:
                response_text = f"✅ **تم بنجاح** — {label}: {name}\n📌 حُفظ في قاعدة البيانات."
    elif status == "awaiting_confirmation":
        # Phase C — safe action echo-back: nothing saved until the user says «نعم».
        response_text = exec_res.get("confirm_text") or (
            f"📋 بانتظار تأكيدك ({label}) — رد بـ «نعم» للتنفيذ أو «لا» للإلغاء.")
    else:  # pending_approval
        approval_id = (exec_res.get("approval") or {}).get("approval_id")
        draft_id = (exec_res.get("draft") or {}).get("id")
        is_duplicate = bool(exec_res.get("duplicate"))
        payload = ((exec_res.get("action") or {}).get("payload") or {})
        if is_duplicate:
            # المسودة الموجودة هي مصدر الحقيقة — نعرض بياناتها لا بيانات الطلب الجديد
            payload = (exec_res.get("draft") or {}).get("payload") or payload
        audit_notes = exec_res.get("audit_notes") or []
        audit_block = ""
        if audit_notes:
            audit_block = ("\n🕵️ **ملاحظات المدقق قبل الاعتماد:**\n"
                           + "\n".join(f"  {n}" for n in audit_notes))
        header = ("♻️ **طلب مطابق معلق بالفعل** — لن أُنشئ نسخة مكررة، هذه بطاقة الطلب الموجود:\n"
                  if is_duplicate else
                  "⏳ **بانتظار اعتماد طرف ثانٍ (أربع أعين)** — عملية مالية حسّاسة.\n")
        tgt = payload.get("_target_label")
        echo = payload.get("_echo") or {}
        if echo:
            amt = echo.get("amount")
            amt_line = f"\n💰 المبلغ: {amt}" if amt not in (None, "", 0) else ""
            # 🛒 عرض بنود الشراء (اسم × سعر × كمية) إن وُجدت — مسودة واحدة، بنود متعددة
            items_block = ""
            items = echo.get("items") or []
            if action == "create_purchase" and items:
                lines_ = ["📦 البنود:"]
                for it in items:
                    n = it.get("name") or "—"
                    p = it.get("price") or 0
                    q = it.get("qty") or 1
                    tl = it.get("line_total") or (float(p) * float(q))
                    match = " 🔗" if it.get("matched_id") else ""
                    lines_.append(f"  • {n} — {p:,.2f} × {q} = {tl:,.2f}{match}")
                items_block = "\n" + "\n".join(lines_)
            # 🏷️ افتراضات موسومة (⚠️/🔗/🆕)
            assumptions = echo.get("assumptions") or []
            assumptions_block = ""
            if assumptions:
                assumptions_block = "\n" + "\n".join(assumptions)
            response_text = (
                header
                + f"🧾 النوع: {echo.get('type') or label}\n"
                f"👤 الطرف: {echo.get('entity') or '—'}{amt_line}"
                f"{items_block}\n"
                f"📒 الأثر المحاسبي: {echo.get('accounts') or '—'}"
                f"{assumptions_block}{audit_block}\n"
                "🔴 لن يُثبَّت أي قيد مالي دون اعتماد بشري مختلف."
            )
        else:
            response_text = (f"{header}🧾 عملية حساسة "
                             f"({label}{': ' + str(tgt) if tgt else ''}).{audit_block}")
        cards = [{
            "type": "ApprovalCard", "id": approval_id,
            "title": f"موافقة — {label}", "status": "pending",
            "data": {"approval_id": approval_id, "draft_id": draft_id, "status": "pending",
                     "action": action, "echo": echo, "payload": payload,
                     "audit_notes": audit_notes, "duplicate": is_duplicate},
            "actions": _build_approval_actions(action, draft_id, approval_id, payload, echo),
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
        "executed": {"status": status, "action": action, "entity_id": entity_id, "approval_id": approval_id},
        "power": None,
    }


def _build_clarification_response(*, sid: str, message: str, exec_res: Dict[str, Any]) -> Dict[str, Any]:
    """When a delete/update target can't be uniquely resolved, ask the user
    to disambiguate instead of guessing (data-safety)."""
    reason = exec_res.get("reason")
    entity = exec_res.get("entity")
    ent_ar = {"customer": "عميل", "vehicle": "مركبة", "supplier": "مورّد",
              "financial": "طرف مالي"}.get(entity, "سجل")
    cands = exec_res.get("candidates") or []
    ask = exec_res.get("ask")
    if ask:
        response_text = ask
    elif reason == "not_found":
        _payload = (exec_res.get("action") or {}).get("payload") or {}
        _target_name = str(_payload.get("customer") or _payload.get("customer_name")
                           or _payload.get("name") or "").strip()
        if entity == "customer" and _target_name:
            response_text = (
                f"🔎 لم أجد عميلاً باسم «{_target_name}» في النظام.\n\n"
                f"هل تريد **إضافته كعميل جديد**؟ أرسل:\n"
                f"«اضف عميل {_target_name} جوال 05xxxxxxxx»\n"
                f"ثم أعد أمرك الأصلي — أو تأكّد من كتابة الاسم/رقم الجوال."
            )
        else:
            response_text = (f"🔎 لم أجد {ent_ar} مطابقاً لطلبك. "
                             f"تأكّد من الاسم أو رقم الجوال/اللوحة وحاول مرة أخرى.")
    else:  # ambiguous
        lines = []
        for c in cands:
            if entity == "customer":
                lines.append(f"• {c.get('name')} — {c.get('phone') or 'بدون جوال'}")
            else:
                lines.append(f"• لوحة {c.get('plate')} — {c.get('brand') or ''} {c.get('model') or ''}".strip())
        listing = "\n".join(lines)
        response_text = (f"⚠️ وجدت أكثر من {ent_ar} مطابق — أيّهم تقصد؟\n{listing}\n\n"
                         f"حدّد بالاسم الكامل أو رقم الجوال/اللوحة.")
    shared_memory.append_message(sid, "assistant", response_text,
                                 meta={"intent": "clarify", "reason": reason})
    try:
        action_name = ((exec_res.get("action") or {}).get("action") or "")
        if reason == "missing_fields" and action_name in {"create_invoice", "collect_payment", "create_expense", "create_purchase"}:
            shared_memory.set_context(sid, "pending_action_clarification", {
                "action": exec_res.get("action"),
                "original_message": message,
                "created_at": time.time(),
            })
    except Exception:
        pass
    return {
        "session_id": sid, "agent": "Assistant", "assistant_name": ASSISTANT_NAME,
        "assistant_version": ASSISTANT_VERSION, "intent": "clarify",
        "tool_results": [], "response": response_text, "cards": [],
        "context_snapshot": {}, "recent_actions": shared_memory.get_recent_actions(sid, limit=10),
        "ai_used": False, "model_used": None, "read_only": False, "mode": "clarify",
        "executed": None, "power": None,
    }




def _plain_chat_response(*, sid: str, text: str, intent: str = "action",
                         status: Optional[str] = None) -> Dict[str, Any]:
    """رد نصي بسيط من مسار التنفيذ (بدون LLM)."""
    shared_memory.append_message(sid, "assistant", text, meta={"intent": intent, "status": status})
    return {
        "session_id": sid, "agent": "Assistant", "assistant_name": ASSISTANT_NAME,
        "assistant_version": ASSISTANT_VERSION, "intent": intent,
        "tool_results": [], "response": text, "cards": [],
        "context_snapshot": {}, "recent_actions": shared_memory.get_recent_actions(sid, limit=10),
        "ai_used": False, "model_used": None, "read_only": False, "mode": intent,
        "executed": ({"status": status, "action": None, "entity_id": None, "approval_id": None}
                     if status else None),
        "power": None,
    }


def _summarize_tool_result_for_user(tool: Optional[str], result: Any) -> str:
    """تلخيص عربي قصير لنتائج الأدوات عند تعطيل LLM أو فشل الرد الذكي."""
    if not isinstance(result, dict):
        return f"  {str(result)[:900]}"
    tool = tool or ""
    if tool == "suppliers.search":
        rows = result.get("matches") or []
        if not rows:
            return "  لم أجد مورداً مطابقاً."
        lines = [f"  وجدت {len(rows)} مورد/موردين:"]
        for r in rows[:5]:
            lines.append(f"  • {r.get('name')} — الرصيد {float(r.get('balance') or 0):,.2f} ر.س — حركات: {r.get('movements_count') or 0}")
        return "\n".join(lines)
    if tool == "vehicles.recent":
        rows = result.get("items") or []
        if not rows:
            return "  لا توجد مركبات مطابقة."
        lines = [f"  آخر {len(rows)} مركبة:"]
        for r in rows[:10]:
            lines.append(f"  • {r.get('plate') or 'بدون لوحة'} — {r.get('owner') or 'بدون عميل'} — {r.get('status') or 'بدون حالة'}")
        return "\n".join(lines)
    if tool == "finance.sales_report":
        return (f"  الفترة: {result.get('period')} — عدد العمليات: {result.get('count')} — "
                f"إجمالي المبيعات: {float(result.get('total_sales') or 0):,.2f} ر.س — "
                f"المحصّل: {float(result.get('paid_amount') or 0):,.2f} ر.س — "
                f"المتبقي: {float(result.get('unpaid_amount') or 0):,.2f} ر.س")
    if tool == "operations.empty_items":
        rows = result.get("items") or []
        lines = [f"  عدد العمليات/الملفات بدون بنود: {result.get('count') or 0}"]
        for r in rows[:8]:
            lines.append(f"  • {r.get('type') or 'عملية'} — {r.get('partner') or r.get('id')} — {r.get('total') or 0} ر.س")
        return "\n".join(lines)
    if tool == "runtime.pending_approvals":
        return f"  عدد الاعتمادات المعلقة: {result.get('count') or 0}"
    if tool == "firewall.operation_integrity":
        return f"  نتيجة فحص القيود/العمليات: {str(result)[:700]}"
    if tool == "operations.top_services":
        return f"  أكثر البنود/الخدمات حسب البيانات: {str(result)[:700]}"
    if tool == "vehicles.search":
        rows = result.get("matches") or result.get("items") or []
        return f"  نتائج المركبات: {len(rows)}" + (f" — {rows[:3]}" if rows else "")
    return f"  {str(result)[:900]}"


def _try_cancel_last_draft(*, sid: str, message: str,
                           proposer: Optional[str]) -> Optional[Dict[str, Any]]:
    """«الغي آخر عملية» → سحب آخر مسودة معلقة من هذه الجلسة (أو لنفس المُنشئ)
    بدل مطالبة المستخدم بـ journal_id. يرجع None إذا لا توجد مسودة معلقة."""
    from core import action_runtime
    drafts = action_runtime.list_drafts(status="pending_approval", session_id=sid, limit=10)
    if not drafts and proposer:
        drafts = [d for d in action_runtime.list_drafts(status="pending_approval", limit=30)
                  if d.get("proposer") == proposer]
    if not drafts:
        return None
    if "شرا" in (message or ""):
        purchases = [d for d in drafts if d.get("action") in ("create_purchase", "purchase")]
        if purchases:
            drafts = purchases
    draft = drafts[0]
    approval_id = draft.get("last_approval_id")
    if approval_id:
        action_runtime.reject_approval(
            approval_id=approval_id, approver=proposer or "chat",
            reason="سحب من المُنشئ عبر المحادثة",
        )
    label = {
        "create_purchase": "شراء", "purchase": "شراء", "create_invoice": "فاتورة",
        "invoice": "فاتورة", "collect_payment": "تحصيل دفعة", "payment": "دفعة",
        "create_expense": "مصروف", "expense": "مصروف",
        "reverse_entry": "قيد عكسي", "delete_operation": "حذف عملية",
        "create_visit": "زيارة", "visit": "زيارة",
    }.get(draft.get("action"), draft.get("action") or "عملية")
    echo = (draft.get("payload") or {}).get("_echo") or {}
    detail = f" — {echo.get('entity')}" if echo.get("entity") else ""
    amt = echo.get("amount")
    if amt not in (None, "", 0):
        detail += f" (المبلغ: {amt})"
    text = (f"🚫 **تم إلغاء المسودة المعلقة** — {label}{detail}\n"
            "لم يُثبَّت أي قيد مالي، وسُجّل السحب في سجل التدقيق.")
    resp = _plain_chat_response(sid=sid, text=text, intent="action", status="cancelled")
    resp["executed"] = {"status": "cancelled", "action": draft.get("action"),
                        "entity_id": draft.get("id"), "approval_id": approval_id}
    return resp


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
    timeout_seconds: Optional[float] = None,
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
        from core.pdpl_redactor import redact_pii
        chat = LlmChat(
            api_key=api_key,
            session_id=session_id,
            system_message=redact_pii(system_message),
        ).with_model(model_provider, model_name)
        msg_text = user_message
        if history:
            history_text = "\n".join([f"{m['role']}: {m['content']}" for m in history[-24:]])
            msg_text = f"السياق السابق للمحادثة:\n{history_text}\n\nالسؤال الحالي:\n{user_message}"
        # 🔐 PDPL: تنقيح المعرّفات الشخصية قبل مغادرة النص للمزوّد الخارجي
        msg_text = redact_pii(msg_text)
        from core import llm_traces
        _t0 = time.time()
        response = await asyncio.wait_for(
            # ⚠️ litellm.completion داخل المكتبة sync — thread منفصل حتى لا يتجمد اللوب
            asyncio.to_thread(
                lambda: asyncio.run(chat.send_message(UserMessage(text=msg_text)))
            ),
            timeout=timeout_seconds or float(os.environ.get("LLM_TIMEOUT_SECONDS", "60")),
        )
        llm_traces.add_llm_call(
            purpose="chat", provider=model_provider, model=model_name,
            system_message=redact_pii(system_message),
            request_messages=[{"role": "user", "content": msg_text}],
            response_raw=str(response or ""), duration_ms=(time.time() - _t0) * 1000,
        )
        return str(response or "").strip()
    except asyncio.TimeoutError:
        _log.warning("LLM call timed out after %ss", os.environ.get("LLM_TIMEOUT_SECONDS", "60"))
        from core import llm_traces
        llm_traces.add_llm_call(purpose="chat", provider=model_provider, model=model_name,
                                error="timeout")
        return ""
    except Exception as e:
        # Phase 3A: replace `print` with structured logger; never leak raw user content.
        _log.warning("LLM call failed: %s", redact(str(e), max_len=160))
        from core import llm_traces
        llm_traces.add_llm_call(purpose="chat", provider=model_provider, model=model_name,
                                error=str(e)[:300])
        return ""


# ---------- Public API ----------

ASSISTANT_NAME = "كاترينا"
ASSISTANT_VERSION = "L16"


def _baseline_prompt() -> str:
    """L5 system prompt — النسخة المدمجة (v1-baseline، مرجع rollback الدائم).

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
        "  • accounting.journal_entries (القيود المحاسبية الفعلية / دفتر اليومية)\n"
        "  • workshop.active_visits / inventory.low_stock / operations.recent\n"
        "  • customers.search / vehicles.search / operations.search / parts.search\n\n"
        "🏛️ **قدرات النظام المحاسبية (موجودة فعلاً — لا تنكريها)**:\n"
        "  • النظام فيه محاسبة كاملة: **شجرة حسابات، قيود يومية (journal_entries)، ميزان مراجعة، تقارير مالية**.\n"
        "  • للاطلاع على القيود الفعلية استخدمي أداة **accounting.journal_entries**، أو أحيلي المستخدم لصفحة «المالية والمحاسبة ← القيود المحاسبية».\n"
        "  • **لا تقولي أبداً إن النظام لا يحتوي قيوداً محاسبية أو دفتر يومية** — هذا غير صحيح.\n\n"
        "🛑 **قواعد الصدق المطلقة (الأهم على الإطلاق)**:\n"
        "  • **ممنوع منعاً باتاً اختراع أي أرقام أو قيود أو حسابات.** لا تُنشئي قيداً محاسبياً افتراضياً، ولا ميزان مراجعة من عندك، ولا 'قيد رقم X' وهمي — اعرضي فقط ما ترجعه الأدوات فعلاً من قاعدة البيانات.\n"
        "  • إذا لم تتوفّر البيانات أو رجعت الأداة فارغة → قولي بوضوح «لا تتوفّر بيانات كافية» أو «لم أجد قيوداً مطابقة»، **ولا تخمّني المصدر ولا تلفّقي تفسيراً**.\n"
        "  • قد يختلف الرقم الإجمالي في تقرير (مثل التدفق النقدي) عن مجموع العمليات المفردة — إن ظهر فرق، وضّحي أنه **فرق في طريقة الاحتساب** واقترحي فتح صفحة القيود المحاسبية للتفصيل؛ **لا تختلقي عمليات أو قيوداً لتغطية الفرق**.\n"
        "  • فرّقي بصراحة بين «تمثيل توضيحي» و«بيانات فعلية»، ولا تعرضي أي تمثيل توضيحي وكأنه قيد حقيقي مسجّل في النظام.\n"
        "  • **ممنوع منعاً باتاً اختلاق أسماء عملاء/موردين أو قيود وادّعاء أنها «من جلسة/رسالة سابقة».** أي اسم أو رقم قيد تعرضينه يجب أن يكون حاضراً في نتائج الأدوات في هذه اللحظة — إن لم يرجع من الأداة الآن فقولي «لم تُرجع الأداة قيوداً» وأحيلي لصفحة القيود المحاسبية، ولا تملئي الفراغ من ذاكرتك.\n"
        "  • **ممنوع منعاً باتاً الادعاء بتنفيذ أي عملية كتابة** (إضافة/تعديل/حذف عميل/مورد/مركبة/فاتورة...). "
        "التنفيذ يتم حصراً عبر محرك التنفيذ، ورسالة «✅ تم بنجاح» تصدر من النظام نفسه — ليست منكِ. "
        "إذا وصلك طلب تنفيذ إلى هنا فهذا يعني أن المحرك لم يلتقطه: قولي بوضوح «لم يُنفَّذ بعد» "
        "واطلبي إعادة الصياغة كأمر مباشر في رسالة واحدة (مثال: 'اضف مورد باسم راكان جوال 0501001220'). "
        "**لا تقولي أبداً «تم» أو «جاري الإضافة» أو «سأضيفه» من عندك.**\n\n"
        "📊 **التعامل مع النتائج**:\n"
        "  • نتيجة فارغة → قولي مباشرة 'لا توجد بيانات' بدون اعتذار.\n"
        "  • نتيجة ناجحة → نسّقيها (جدول Markdown/قائمة) وبفواصل آلاف للأرقام.\n\n"
        "⚙️ **التنفيذ ونموذج المستويين (حوكمة القدرات)**:\n"
        "  • تفهمين وتقترحين أي أمر (عميل/مركبة/جوال/فاتورة/دفعة/مصروف/عكس/حذف). التأكيد حاجز أمان على لحظة التثبيت فقط.\n"
        "  • **المستوى ١ (منخفض الخطر)**: إنشاء/تعديل عميل، مورّد، مركبة، زيارة → النظام يعرض ملخص echo-back ويطلب من المستخدم الرد بـ«نعم» قبل الحفظ (لا حفظ صامت).\n"
        "  • **المستوى ٢ (عالي الخطر)**: المالية (فاتورة/دفعة/مصروف/عكس) والحذف والإغلاق الجماعي → **أربع أعين** (اعتماد بشري مختلف) + بطاقة echo-back كاملة.\n"
        "  • 🔴 **الخط الأحمر**: لا يُثبَّت أي قيد مالي تلقائياً أبداً — لا auto-commit مالي تحت أي ظرف.\n"
        "  • قبل أي تثبيت اعرضي echo-back: النوع + الكيان الحقيقي المُحلَّل من القاعدة + المبلغ + الحسابات المتأثرة. عند الغموض/عدم التطابق → اسألي، لا تخمّني.\n"
        "  • إذا نقص حقل ضروري (الاسم/المبلغ/رقم الجوال) → **اطلبي الحقل الناقص بوضوح**، ولا تقولي 'افتح الصفحة وأضف يدوياً'.\n\n"
        "⚠️ **قواعد حاسمة**:\n"
        "  1. **ممنوع** 'دعني أتحقق' أو 'سأعود إليك' — أكملي الإجابة فوراً في نفس الرسالة.\n"
        "  2. **ممنوع** الرد بـ 'لا يمكنني، افتح الصفحة' عند طلب تنفيذ — إمّا نفّذتِ أو اطلبتِ المعلومة الناقصة.\n"
        "  3. كل رد نهائي ومفيد، بالعربية الواضحة، Markdown مسموح ومفضّل.\n"
    )


# 🔐 L13-T6 — أدوات تكشف الإيرادات: تتطلب دور معتمد أو صلاحية reports.revenue
_REVENUE_TOOLS = {"firewall.cash_flow", "services.top"}


def _can_view_revenue(role: Optional[str]) -> bool:
    r = (role or "").strip().lower()
    try:
        from core.rbac import APPROVER_ROLES, get_role_permissions
        if r in APPROVER_ROLES:
            return True
        return bool((get_role_permissions(r).get("reports") or {}).get("revenue"))
    except Exception:
        return False


async def _chat_impl(
    *,
    session_id: Optional[str] = None,
    message: str,
    workshop_id: Optional[str] = None,
    force_agent: Optional[str] = None,  # kept for backward-compat; ignored in L5
    use_ai: bool = True,
    model: Optional[str] = None,  # 🆕 'gpt' (Emergent default) | 'ollama' (local)
    proposer: Optional[str] = None,  # 🆕 Phase 3C — Four-Eyes anchor (current user)
    proposer_role: Optional[str] = None,  # 🧠 RRR — دور المستخدم من JWT (admin فقط يفعّل)
) -> Dict[str, Any]:
    """Core chat logic — يُستدعى عبر chat() الذي يضيف تذكير المعلقات.

    Args:
      model: 'gpt' → Emergent gpt-4o-mini (default), 'ollama' → local llama3.2:3b.
             Any other value falls back to 'gpt'.

    Returns: {session_id, response, tool_results, recent_actions,
              context_snapshot, ai_used, model_used}
    """
    sid = session_id or f"session-{uuid.uuid4().hex[:10]}"
    shared_memory.append_message(sid, "user", message)

    # 🧠 Developer Mode (RRR) — Phase 1: اعتراض الأمر قبل أي مسار آخر (admin فقط)
    from core import developer_mode as _dev
    dev_resp = _dev.handle_trigger(sid, message, role=proposer_role)
    if dev_resp is not None:
        return _plain_chat_response(sid=sid, text=dev_resp["text"],
                                    intent="developer_mode", status=dev_resp.get("status"))

    # 🆕 Phase C — resolve a pending safe-action confirmation («نعم»/«لا») BEFORE
    # any intent parsing, so a bare confirmation commits the REAL draft instead
    # of falling into the LLM (which must never claim execution success).
    pending_confirm = shared_memory.get_context(sid, "pending_confirm")
    if pending_confirm:
        from core import unified_executor as _ux
        if _CONFIRM_RE.match(message or ""):
            shared_memory.set_context(sid, "pending_confirm", None)
            exec_res = _ux.confirm_pending(pending_confirm)
            if exec_res.get("status") in ("committed", "pending_approval"):
                return _build_action_chat_response(sid=sid, message=message, exec_res=exec_res)
            return _plain_chat_response(
                sid=sid,
                text=(f"⚠️ تعذّر التثبيت: {exec_res.get('reason') or 'خطأ غير متوقع'} — "
                      "أعد صياغة الطلب من جديد."),
                intent="action", status="error",
            )
        if _CANCEL_RE.match(message or ""):
            shared_memory.set_context(sid, "pending_confirm", None)
            _ux.cancel_pending(pending_confirm)
            return _plain_chat_response(
                sid=sid, text="🚫 تم الإلغاء — لم يُحفظ أي شيء.",
                intent="action", status="cancelled",
            )
        # أي رسالة أخرى → تُعامل طبيعياً (قد تكون تعديلاً على الطلب)

    # 🧩 متابعة أمر مالي ناقص: مثال «دفعة 444 للمورد...» ثم «55sr Today».
    pending_clarification = shared_memory.get_context(sid, "pending_action_clarification")
    if pending_clarification and message:
        if _CANCEL_RE.match(message or ""):
            shared_memory.set_context(sid, "pending_action_clarification", None)
            return _plain_chat_response(sid=sid, text="🚫 تم إلغاء الطلب الناقص — لم يُحفظ أي شيء.", intent="action", status="cancelled")
        if re.search(r"\d", message) or re.search(r"(اليوم|today|حوال|تحويل|نقد|كاش|آجل|اجل)", message, re.IGNORECASE):
            try:
                from core import unified_executor as _ux
                original = str(pending_clarification.get("original_message") or "").strip()
                combined = f"{original} {message}".strip()
                shared_memory.set_context(sid, "pending_action_clarification", None)
                exec_res = await _ux.execute_text(combined, proposer=proposer, session_id=sid)
                if exec_res and exec_res.get("status") in ("committed", "pending_approval", "awaiting_confirmation"):
                    return _build_action_chat_response(sid=sid, message=combined, exec_res=exec_res)
                if exec_res and exec_res.get("status") == "needs_clarification":
                    return _build_clarification_response(sid=sid, message=combined, exec_res=exec_res)
            except Exception as e:
                _log.warning("pending clarification continue failed: %s", redact(str(e), max_len=100))

    # 🆕 سحب سياقي: «الغي آخر عملية/المسودة المعلقة» → إلغاء آخر مسودة معلقة
    # في هذه الجلسة بدل الدخول في مسار delete_operation ومطالبة المستخدم بـ id.
    if _CANCEL_DRAFT_VERB_RE.search(message or "") and _CANCEL_DRAFT_MARKER_RE.search(message or ""):
        cancel_resp = _try_cancel_last_draft(sid=sid, message=message, proposer=proposer)
        if cancel_resp is not None:
            return cancel_resp

    # 🧠 Memory Engine (RRR المرحلة 2) — أوامر الذاكرة المباشرة
    if re.match(r"^\s*(?:الذاكرة|حالة\s+الذاكرة|ذاكرتك)\s*[؟?]?\s*$", message or ""):
        try:
            from core import memory_engine
            st = memory_engine.stats()
            if not st.get("enabled"):
                txt = "🧠 مخزن الذاكرة غير متاح حالياً (MongoDB)."
            else:
                txt = ("🧠 **ذاكرة كاترينا (المرحلة 2 — قواعد الترقية الخمس):**\n"
                       f"  • قصيرة: **{st['short']}** | طويلة: **{st['long']}** | معرفة معتمدة: **{st['knowledge']}**\n"
                       f"  • متنازع عليها (مجمّدة من الحقن): **{st['disputed']}**\n"
                       f"  • حجم المعرفة المحقونة: ~**{st['knowledge_tokens']}/{st['cap']}** token\n"
                       "  💡 «احفظ في المعرفة: <نص>» لترشيح معلومة — تدخل الذاكرة الدائمة "
                       "بعد اعتماد بشري فقط (أربع أعين).")
            return _plain_chat_response(sid=sid, text=txt, intent="question")
        except Exception as e:
            _log.warning("memory stats failed: %s", redact(str(e), max_len=80))

    _mem_save = re.match(
        r"^\s*(?:احفظي?|اعتمدي?|رشّ?حي?|أضيفي?|اضيفي?)\s*(?:في|إلى|الى|لل)?\s*"
        r"(?:الذاكرة|المعرفة|ذاكرتك)\s*[:：]\s*(.+)$",
        message or "", re.S)
    if _mem_save:
        try:
            from core import memory_engine
            res = memory_engine.propose_knowledge(
                content=_mem_save.group(1).strip()[:500], proposer=proposer)
            if res.get("error"):
                return _plain_chat_response(
                    sid=sid, intent="action",
                    text=f"🚫 تعذّر الترشيح: {res.get('detail') or res['error']}")
            ap = res.get("approval") or {}
            approval_id = ap.get("approval_id")
            draft_id = (res.get("draft") or {}).get("id")
            resp = _plain_chat_response(
                sid=sid, intent="action", status="pending_approval",
                text=("🧠 **رُشّحت للمعرفة (Learning Candidate)** — لن تدخل ذاكرة كاترينا "
                      "الدائمة إلا بعد اعتماد بشري من طرف ثانٍ (أربع أعين)."))
            resp["cards"] = [{
                "type": "ApprovalCard", "id": approval_id,
                "title": "موافقة — ترقية للمعرفة", "status": "pending",
                "data": {"approval_id": approval_id, "draft_id": draft_id,
                         "status": "pending", "action": "memory_promote",
                         "echo": {"type": "ترقية للمعرفة",
                                  "entity": (res.get("memory") or {}).get("content", "")[:80]}},
                "actions": _build_approval_actions("memory_promote", draft_id,
                                                   approval_id, {}, {}),
            }]
            resp["executed"] = {"status": "pending_approval", "action": "memory_promote",
                                "entity_id": draft_id, "approval_id": approval_id}
            return resp
        except Exception as e:
            _log.warning("memory propose failed: %s", redact(str(e), max_len=80))


    # 🔄 التوحيد (خطة 2026-07-03): كل الرسائل — /power أو عادية — تمرّ عبر
    # `unified_executor.execute_text()` كمصدر حقيقة وحيد. المقسِّم النصي القديم
    # (`power_mode.power_process`) تم تعطيله كي لا يُنتج مسودات متعددة لأمر واحد.
    power_prefix_hit = power_mode.detect_mode(message) == "power"
    if power_prefix_hit:
        message = power_mode.strip_power_prefix(message)
        shared_memory.track_action(sid, "power_mode_shortcut", {"unified": True})

    # 🆕 L16 (كاترينا) — Unified action execution. If the message is a WRITE
    # command (create/delete/close/...), execute it directly through the
    # Unified Execution Engine and return a confirmation. This is the backend
    # safety-net that guarantees execution even if the frontend router missed it.
    if power_prefix_hit or looks_like_action(message):
        try:
            from core import unified_executor
            exec_res = await unified_executor.execute_text(
                message, proposer=proposer, session_id=sid,
            )
        except Exception as e:
            _log.warning("unified action execution failed: %s", redact(str(e), max_len=120))
            exec_res = None
        if exec_res and exec_res.get("status") in ("committed", "pending_approval", "awaiting_confirmation"):
            return _build_action_chat_response(sid=sid, message=message, exec_res=exec_res)
        if exec_res and exec_res.get("status") == "needs_clarification":
            return _build_clarification_response(sid=sid, message=message, exec_res=exec_res)
        # 🆕 CR-2 (G3 fix): a genuine execution FAILURE (exception → exec_res is None,
        # or status == "error") for an action-looking message must be surfaced honestly
        # instead of silently falling to the read/LLM path — which hides the failure
        # from the operator and can produce a misleading "as-if-done" reply.
        if exec_res is None or exec_res.get("status") == "error":
            _detail = ""
            if exec_res:
                _detail = redact(str(exec_res.get("error") or exec_res.get("reason") or ""), max_len=140)
            _err_text = (
                "⚠️ لم يُنفَّذ الأمر — حدث خطأ أثناء المعالجة، ولم يُحفظ أو يُعدَّل أي شيء.\n"
                "أعد صياغة الطلب بوضوح (مثال: «سجّل تحصيل 500 من محمد نقدًا») أو حاول لاحقًا."
            )
            if _detail:
                _err_text += f"\n\n🔧 التفاصيل: {_detail}"
            return _plain_chat_response(sid=sid, text=_err_text, intent="action_error", status="error")
        # read_only / rejected → fall through to the normal read path

    # 1) Detect which read-only tools to invoke
    # 🎯 L14-D1: حل الإشارات الترتيبية («أول عميل في القائمة») من آخر قائمة معروضة بالجلسة
    forced_query = None
    _ord_m = _ORDINAL_LIST_RE.search(message)
    if _ord_m:
        _last_list = shared_memory.get_context(sid, "last_list") or []
        if _last_list:
            _idx_map = {"أول": 0, "اول": 0, "ثاني": 1, "ثالث": 2, "رابع": 3,
                        "خامس": 4, "آخر": -1, "اخر": -1}
            _idx = _idx_map.get(_ord_m.group(1), 0)
            try:
                forced_query = str(_last_list[_idx]).strip() or None
            except (IndexError, TypeError):
                forced_query = None
    if forced_query:
        tool_names = ["customers.search"]
    else:
        tool_names = detect_tools(message)
    # 🔐 L13-T6: حجب أدوات الإيرادات عن الأدوار غير المخوّلة (بنك كاترينا الأمني)
    _rev_blocked = [t for t in tool_names if t in _REVENUE_TOOLS and not _can_view_revenue(proposer_role)]
    if _rev_blocked:
        tool_names = [t for t in tool_names if t not in _rev_blocked]
        if not tool_names:
            return _plain_chat_response(
                sid=sid,
                text="🚫 بيانات الإيرادات والتدفق النقدي غير مصرّحة لدورك الحالي — تواصل مع المدير إن كنت تحتاج هذه الصلاحية.",
                intent="permission_denied", status="blocked")
    tool_results: List[Dict[str, Any]] = []
    cards: List[Dict[str, Any]] = []  # 🆕 collected from each tool result
    for tn in tool_names:
        kwargs: Dict[str, Any] = {"workshop_id": workshop_id or "finmodule-sync"}
        if tn in {"vehicles.recent", "operations.recent", "accounting.journal_entries"}:
            m_limit = re.search(r"\b(\d{1,3})\b", message or "")
            if m_limit:
                try:
                    kwargs["limit"] = max(1, min(int(m_limit.group(1)), 100))
                except Exception:
                    pass
        if tn in _QUERY_AWARE_TOOLS:
            q = forced_query or _extract_query(message, tn)
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
    # 🎯 L14-D1: خزّن آخر قائمة أسماء معروضة لحل الإشارات الترتيبية لاحقاً
    try:
        for _tr2 in tool_results:
            if not _tr2.get("success"):
                continue
            _res2 = _tr2.get("result") or {}
            _names: List[str] = []
            if _tr2.get("tool") == "finance.ar_summary":
                _names = [d.get("name") for d in
                          (_res2.get("stored_top_debtors") or _res2.get("top_debtors") or [])
                          if isinstance(d, dict) and d.get("name")]
            elif _tr2.get("tool") == "customers.search":
                _names = [r2.get("name") for r2 in (_res2.get("matches") or [])
                          if isinstance(r2, dict) and r2.get("name")]
            if _names:
                shared_memory.set_context(sid, "last_list", _names)
    except Exception:
        pass

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

    # 🧠 Memory Engine (RRR المرحلة 2): تسجيل فشل الأدوات + استرجاع انتقائي top-k
    memory_block = ""
    try:
        from core import memory_engine as _mem
        for _tr in tool_results:
            if not _tr.get("success"):
                _mem.record("tool_failure",
                            f"فشل أداة {_tr.get('tool')}: {str(_tr.get('error'))[:120]}",
                            session_id=sid, user=proposer)
        memory_block = _mem.retrieve(message, k=5)
    except Exception:
        memory_block = ""

    # 3) System message (L5: single assistant, no agent persona)
    # 📜 L14-D2: الـ prompt من سجل النسخ (مع rollback) — والنسخة تُسجَّل في الـtrace
    from core import prompt_registry as _preg
    _pver, _pcontent = _preg.get_active()
    from core import llm_traces as _lt
    _lt.set_meta("prompt_version", _pver)
    system_msg = (_pcontent or _baseline_prompt()) + "\n\n" + context_text
    if brief_text:
        system_msg += "\n\n" + brief_text
    if memory_block:
        system_msg += "\n\n" + memory_block
    # 🧠 RRR — حقن السياق المؤسسي الكامل عندما يكون وضع المطور مفعّلاً
    _dev_active = _dev.is_active(sid)
    if _dev_active:
        system_msg += "\n\n" + _dev.dev_system_addendum()

    # 4) Append tool results
    if tool_results:
        tool_section = "\n\n🛠️ نتائج الأدوات المنفّذة لهذا السؤال:\n"
        for tr in tool_results:
            tool_section += f"  • {tr.get('tool')}: {tr.get('result') if tr.get('success') else tr.get('error')}\n"
        system_msg += tool_section

    # 5) Get conversation history
    # 🔧 L14-D8: نافذة 10 رسائل أسقطت مصدر الرقم بعد 5 رسائل وسيطة (S3) — وُسّعت لـ24
    history = ai_context.get_conversation_history(sid, limit=24)

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
                # 🧠 RRR: الردود الهندسية (Proposals) طويلة — مهلة أوسع في وضع المطور
                timeout_seconds=(float(os.environ.get("LLM_TIMEOUT_SECONDS_DEV", "150"))
                                 if _dev_active else None),
            )
            if response_text:
                model_used = "emergent/claude-sonnet-4-6"

    # Fallback: aggregated tool output + canned message
    if not response_text:
        if tool_results:
            parts = [f"✅ استدعيت {len(tool_results)} أداة مناسبة لهذا السؤال:"]
            for tr in tool_results:
                if tr.get("success"):
                    parts.append(f"• **{tr.get('tool')}**")
                    parts.append(_summarize_tool_result_for_user(tr.get("tool"), tr.get("result")))
                else:
                    parts.append(f"• فشل {tr.get('tool')}: {tr.get('error')}")
            response_text = "\n".join(parts)
        else:
            response_text = "النظام يعمل بقواعد محلية حالياً. لتفعيل ردود أعمق، تأكد من تكوين Emergent LLM Key."

    # 🔐 L14-D5: حارس تطابق بلوك النتائج — أي ادعاء مخرجات أداة بلا تنفيذ مسجَّل يُحجَب
    try:
        # 🧹 L14-D9: أزل تقليد وسم التاريخ الداخلي من الرد الجديد (النظام يكتبه في السجل حصراً)
        response_text = re.sub(
            r"^\[أدوات هذه الدورة المنفَّذة فعلاً:[^\]\n]*\]\s*", "",
            (response_text or "").strip(), flags=re.MULTILINE,
        ).strip()
        from core import provenance_guard as _pg
        response_text, _prov = _pg.enforce(response_text, tool_results)
        # 🔐 L14-D5 (حارس الاختلاق): معرّفات منظَّمة في الرد بلا وجود في أدلة الدورة → تُحجَب
        _evidence_parts = [system_msg or "", message or ""]
        try:
            _evidence_parts += [str(h.get("content") or "") for h in (history or [])]
        except Exception:
            pass
        response_text, _prov_ent = _pg.enforce_entities(response_text, "\n".join(_evidence_parts))
        _prov = (_prov or []) + (_prov_ent or [])
        if _prov:
            from core import llm_traces as _lt2
            _lt2.add_provenance_violations(_prov)
            _log.warning("D5 provenance violations blocked: %s",
                         [v.get("claimed_tool") or v.get("value") for v in _prov])
    except Exception as _pge:
        _log.warning("provenance guard failed (non-fatal): %s", redact(str(_pge), max_len=120))

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
        # بعد توحيد المحرك (2026-07-03): مسار /power يمر عبر unified_executor —
        # لا يوجد سياق `power_block` منفصل بعد الآن.
        "mode": "power_shortcut" if power_prefix_hit else "normal",
        "power": None,
        "developer_mode": _dev_active,  # 🧠 RRR
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


def _build_pending_reminder(*, proposer: Optional[str],
                            proposer_role: Optional[str]) -> Optional[Dict[str, Any]]:
    """🔔 تذكير أول رسالة بالجلسة: اعتمادات تنتظر قرار المستخدم + مسوداته المعلقة."""
    from core import action_runtime
    from core.rbac import APPROVER_ROLES
    from core.card_builder import cards_from_approvals
    pending = action_runtime.list_approvals(status="pending", limit=50)
    if not pending:
        return None
    mine = [a for a in pending if proposer and a.get("proposer") == proposer]
    is_approver = (proposer_role or "").strip().lower() in APPROVER_ROLES
    for_me = [a for a in pending if a.get("proposer") != proposer] if is_approver else []
    if not mine and not for_me:
        return None
    lines = ["🔔 **تذكير — عمليات معلقة لم تُستكمل:**"]
    if for_me:
        lines.append(f"  ⏳ **{len(for_me)}** بانتظار **قرارك** — اعتمد/ارفض من البطاقات أدناه مباشرة.")
    if mine:
        lines.append(f"  📝 **{len(mine)}** أنشأتها أنت وتنتظر معتمداً آخر (أربع أعين).")
    lines.append("  💡 اكتب «اعتمادات كاترينا» للقائمة كاملة، أو «الغي آخر عملية» لسحب مسودتك.")
    return {"text": "\n".join(lines), "cards": cards_from_approvals(for_me[:3])}


async def chat(
    *,
    session_id: Optional[str] = None,
    message: str,
    workshop_id: Optional[str] = None,
    force_agent: Optional[str] = None,
    use_ai: bool = True,
    model: Optional[str] = None,
    proposer: Optional[str] = None,
    proposer_role: Optional[str] = None,
    daily_summary: bool = True,
) -> Dict[str, Any]:
    """Main entry point — يلفّ _chat_impl ويضيف الملخص اليومي + تذكير المعلقات في أول رسالة."""
    from core import llm_traces
    llm_traces.start_trace(session_id=session_id, user=proposer,
                           role=proposer_role, channel="chat", message=message)
    prior_msgs = len(shared_memory.get_messages(session_id, limit=2)) if session_id else 0
    try:
        resp = await _chat_impl(
            session_id=session_id, message=message, workshop_id=workshop_id,
            force_agent=force_agent, use_ai=use_ai, model=model,
            proposer=proposer, proposer_role=proposer_role,
        )
    except Exception as e:
        llm_traces.finish_trace(session_id=session_id, status="error", error=str(e))
        raise
    if prior_msgs == 0 and resp.get("intent") == "question" and not resp.get("tool_results"):
        try:
            blocks: List[str] = []
            # 📅 الملخص اليومي — أول رسالة في اليوم، أرقام من استعلامات مباشرة، حسب الدور
            if daily_summary:
                from core import daily_summary as _ds
                summary = await _ds.build_daily_summary(user=proposer, role=proposer_role)
                if summary:
                    blocks.append(summary)
            has_approval_cards = any(
                (c or {}).get("type") == "ApprovalCard" for c in (resp.get("cards") or []))
            reminder = None if has_approval_cards else _build_pending_reminder(
                proposer=proposer, proposer_role=proposer_role)
            if reminder:
                blocks.append(reminder["text"])
                resp["cards"] = reminder["cards"] + (resp.get("cards") or [])
            if blocks:
                resp["response"] = "\n\n".join(blocks) + f"\n\n---\n\n{resp.get('response') or ''}"
        except Exception:
            pass
    resp["trace_id"] = llm_traces.finish_trace(
        session_id=resp.get("session_id"),
        final_response=resp.get("response"),
        intent=resp.get("intent"),
        status=(resp.get("executed") or {}).get("status") or resp.get("status"),
        executed=resp.get("executed"),
    )
    return resp


# ---------- Deprecated (kept for backward compat with /api/assistant/* routes) ----------

def detect_agent(text: str) -> str:  # noqa: ARG001
    """DEPRECATED in L5 — always returns 'Assistant'. Kept so existing imports don't break."""
    return "Assistant"
