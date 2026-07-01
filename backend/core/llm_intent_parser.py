"""
🧠 LLM Intent Parser — Phase 3C.3

Uses the Emergent LLM (gpt-4o-mini) to convert free-form Arabic text into a
strict, validated Action JSON. The output is then routed through the existing
Action Runtime so Four-Eyes / Approval / Audit still apply — i.e. the LLM
proposes, the human disposes.

⚠️  This module NEVER writes to the DB directly. Every parsed action is
returned as a Pydantic `Action` plus a draft id (created via action_runtime).
Phase 3C state machine still owns commits.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from core.log_utils import get_logger, redact

_log = get_logger("llm_intent")


# ─────────────────────────────────────────────────────────────────────────────
# 1) Pydantic schema — what the LLM is allowed to produce
# ─────────────────────────────────────────────────────────────────────────────

# The set of actions the LLM can route through the runtime. NEW actions must
# also be implemented inside core.action_runtime.commit() before being added
# here — otherwise commits will return `unknown_action`.
ALLOWED_ACTIONS = {
    "create_customer",
    "create_vehicle",
    "create_visit",          # staging or Supabase visits table
    "create_supplier",       # 🆕 add a supplier (name required)
    "close_visits",          # bulk close — implemented as a vehicles status flip
    "get_active_visits",     # read-only query, returns immediately
    "delete_operation",      # delete a specific operation by ID — requires approval
    "delete_customer",       # delete a customer (resolved by name/phone/id) — requires approval
    "delete_vehicle",        # delete a vehicle (resolved by plate/id) — requires approval
    "update_customer",       # edit a customer's fields (safe, auto-commit)
    "update_vehicle",        # edit a vehicle's fields (safe, auto-commit)
    # 🏦 Financial actions (HIGH RISK — always Four-Eyes, NEVER auto-commit)
    "create_invoice",        # issue an invoice for a customer
    "collect_payment",       # collect/settle a payment from a customer
    "create_expense",        # record an expense / supplier payment
    "reverse_entry",         # reverse (contra) a prior journal entry — no hard delete
    "get_customers",         # read-only query
    "get_vehicles",          # read-only query
}


class Action(BaseModel):
    action: str = Field(..., description="One of ALLOWED_ACTIONS or 'unknown'")
    entity: Optional[str] = Field(default=None, description="Target entity name (informational)")
    payload: Dict[str, Any] = Field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────────
# 2) Strict JSON system prompt
# ─────────────────────────────────────────────────────────────────────────────


_SYSTEM_PROMPT = (
    "أنت محرك تحليل النوايا لنظام ERP لورش السيارات. وظيفتك الوحيدة: "
    "تحويل نصّ المستخدم العربي إلى كائن JSON واحد فقط بدون أي شرح أو ماركداون.\n\n"
    "📚 معلومات السياق:\n"
    "  • أنواع المركبات (NOT أرقام لوحات): صالون، جيب، شاحنة، بكب، فان، نقل، دباب، باص.\n"
    "  • مثال: 'صالون 2009' = نوع=صالون + سنة=2009 (لا تضعها في plate!).\n"
    "  • أرقام اللوحات: قد تكون 3-4 حروف عربية/إنجليزية + 3-4 أرقام (مثل: 'أ ب ج 1234' أو 'ggg 1111'). إذا غير قياسي اقبله كما هو.\n"
    "  • الأرقام المنفردة 4-5 أرقام = لوحة، السنوات 4 أرقام بين 1980-2030 = year.\n"
    "  • الخدمات الشائعة: توضيب، تنجيد، صبغ، تلميع، غسيل، فحص، إصلاح، تبديل، صيانة.\n"
    "  • أرقام الجوال السعودية تبدأ بـ 05 (10 أرقام). إذا كان الرقم ناقصاً (مثل 0574747) اقبله مع رفع علم incomplete=true.\n\n"
    "Actions المسموح بها:\n"
    "  • create_customer  — payload: {name?, phone?, email?, address?, vehicle_plate?}\n"
    "  • create_supplier  — payload: {name, phone?, category?, payment_terms?} (إضافة مورّد جديد)\n"
    "  • create_vehicle   — payload: {plate?, brand?, model?, year?, vehicle_type?, customer_name?, customer_phone?}\n"
    "  • create_visit     — payload: {plate?, vehicle_type?, year?, customer_name?, customer_phone?, service?, price?, reason?}\n"
    "  • close_visits     — payload: {} (يُغلق كل الزيارات النشطة)\n"
    "  • get_active_visits — payload: {}\n"
    "  • get_customers    — payload: {query?} (بحث عن عميل)\n"
    "  • get_vehicles     — payload: {query?} (بحث عن مركبة)\n"
    "  • delete_operation — payload: {operation_id?, reason?} (حذف عملية بالمعرف — يحتاج موافقة)\n"
    "  • delete_customer  — payload: {name?, phone?, customer_id?} (حذف عميل — يحتاج موافقة)\n"
    "  • delete_vehicle   — payload: {plate?, vehicle_id?} (حذف مركبة — يحتاج موافقة)\n"
    "  • update_customer  — payload: {match:{name?|phone?|customer_id?}, set:{name?,phone?,email?,address?}} (تعديل بيانات عميل)\n"
    "  • update_vehicle   — payload: {match:{plate?|vehicle_id?}, set:{plate?,brand?,model?,year?,status?}} (تعديل بيانات مركبة)\n"
    "  🏦 إجراءات مالية (تحتاج اعتماد أربع أعين دائمًا — لا تُثبَّت تلقائيًا):\n"
    "  • create_invoice   — payload: {customer, total?, items?, payment_method?(credit/cash/card), date?} (إصدار فاتورة لعميل)\n"
    "  • collect_payment  — payload: {customer, amount, payment_method?(cash/bank/card), date?} (تحصيل/سداد دفعة من عميل)\n"
    "  • create_expense   — payload: {description, amount, category?, supplier?, payment_method?(cash/bank)} (تسجيل مصروف/دفعة لمورد)\n"
    "  • reverse_entry    — payload: {journal_id?|reference_id?, reason?} (عكس قيد سابق — قيد عكسي)\n\n"
    "قواعد الإخراج (مهمّة):\n"
    "  1. أرجع JSON واحد بدون ```\n"
    "  2. الشكل: {\"action\":\"...\", \"entity\":\"...\", \"payload\":{...}}\n"
    "  3. إذا كانت الجملة فيها خدمة + سيارة + سعر → create_visit.\n"
    "  4. **لا ترفض الطلب إذا كان فيه فعل إضافة واضح** (اضف/سجل/افتح) — استخرج ما تستطيع وأكمل بأقل بيانات.\n"
    "  5. action='unknown' فقط إذا لم تجد أي verb أو entity واضح.\n"
    "  6. لا تخترع حقولاً غير الموجودة في الـ payload المسموح به أعلاه.\n"
    "  7. الأسماء العربية تُحفظ كما هي (UTF-8).\n"
    "  8. plate = رقم اللوحة فقط. لا تضع نوع السيارة في plate.\n"
    "  9. **افهم اللهجة القصيمية/النجدية**: 'ضيف/حط' = أضف، 'ابي/ابغى' = أريد (create_*)، 'شيل/امسح/احذف' = حذف (delete_*)، 'عدّل/غيّر/حدّث' = تعديل (update_*)، 'وش عندنا' = get_*.\n"
    "  10. للتعديل (update_*): ضع *معرّف* الكيان في match والقيم *الجديدة* في set. مثال 'عدّل جوال خالد إلى 05..' → match.name='خالد', set.phone='05..'.\n\n"
    "أمثلة:\n"
    "  • 'اضف سيارة لوحة ggg 1111 رقم 0574747'\n"
    "    → {\"action\":\"create_vehicle\",\"payload\":{\"plate\":\"ggg 1111\",\"customer_phone\":\"0574747\"}}\n"
    "  • 'اضف صالون 2009 جوال 0501234567 خدمة توضيب سعر 55'\n"
    "    → {\"action\":\"create_visit\",\"payload\":{\"vehicle_type\":\"صالون\",\"year\":2009,\"customer_phone\":\"0501234567\",\"service\":\"توضيب\",\"price\":55}}\n"
    "  • 'سجل عميل أحمد العتيبي 0501234567'\n"
    "    → {\"action\":\"create_customer\",\"payload\":{\"name\":\"أحمد العتيبي\",\"phone\":\"0501234567\"}}\n"
    "  • 'أضف مركبة لوحة 9935 تويوتا كامري 2020'\n"
    "    → {\"action\":\"create_vehicle\",\"payload\":{\"plate\":\"9935\",\"brand\":\"تويوتا\",\"model\":\"كامري\",\"year\":2020}}\n"
    "  • 'احذف العميل خالد المطيري'  → {\"action\":\"delete_customer\",\"payload\":{\"name\":\"خالد المطيري\"}}\n"
    "  • 'شيل المركبة لوحة 9935'      → {\"action\":\"delete_vehicle\",\"payload\":{\"plate\":\"9935\"}}\n"
    "  • 'عدّل جوال خالد المطيري إلى 0509998877'\n"
    "    → {\"action\":\"update_customer\",\"payload\":{\"match\":{\"name\":\"خالد المطيري\"},\"set\":{\"phone\":\"0509998877\"}}}\n"
    "  • 'غيّر حالة المركبة 9935 إلى جاهزة'\n"
    "    → {\"action\":\"update_vehicle\",\"payload\":{\"match\":{\"plate\":\"9935\"},\"set\":{\"status\":\"جاهزة\"}}}\n"
    "  • 'اصدر فاتورة للعميل أحمد العتيبي بمبلغ 500 آجل'\n"
    "    → {\"action\":\"create_invoice\",\"payload\":{\"customer\":\"أحمد العتيبي\",\"total\":500,\"payment_method\":\"credit\"}}\n"
    "  • 'حصّل 300 من خالد المطيري نقدًا'\n"
    "    → {\"action\":\"collect_payment\",\"payload\":{\"customer\":\"خالد المطيري\",\"amount\":300,\"payment_method\":\"cash\"}}\n"
    "  • 'سجل مصروف إيجار 1200'  → {\"action\":\"create_expense\",\"payload\":{\"description\":\"إيجار\",\"amount\":1200}}\n"
    "  • 'اعكس القيد رقم abc123 السبب خطأ إدخال'\n"
    "    → {\"action\":\"reverse_entry\",\"payload\":{\"journal_id\":\"abc123\",\"reason\":\"خطأ إدخال\"}}\n"
    "\n🔒 مبدأ المصدر الحقيقي: لا تخترع أسماء عملاء أو مبالغ. استخرج فقط ما ورد نصًّا. "
    "إن لم يُذكر مبلغ لمصروف/دفعة/فاتورة فاتركه فارغًا (سيُطلب لاحقًا) — لا تخمّنه.\n"
)


# ─────────────────────────────────────────────────────────────────────────────
# 3) JSON extraction — handles fenced ```json blocks and trailing prose
# ─────────────────────────────────────────────────────────────────────────────

_JSON_BLOCK_RE = re.compile(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", re.DOTALL)


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Pull the first balanced JSON object out of a string."""
    if not text:
        return None
    s = text.strip()
    # Strip markdown fences if the LLM ignored "no markdown"
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s, flags=re.IGNORECASE).strip()
    # Try direct parse first
    try:
        return json.loads(s)
    except Exception:
        pass
    # Greedy fallback — grab the first {...} that parses
    for match in _JSON_BLOCK_RE.findall(s):
        try:
            return json.loads(match)
        except Exception:
            continue
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 4) Public API — async LLM call + validation
# ─────────────────────────────────────────────────────────────────────────────


async def parse_intent_with_llm(text: str, *, session_id: Optional[str] = None) -> Action:
    """Parse free-text into an Action using the Emergent LLM key.

    Returns an Action(action="unknown", ...) when the LLM key is missing or
    when the response is unparseable — the caller can then choose to fall
    back to regex (`core.power_mode.detect_intent_kind`).
    """
    if not text or not text.strip():
        return Action(action="unknown", payload={})

    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        _log.info("EMERGENT_LLM_KEY missing — returning unknown intent")
        return Action(action="unknown", payload={})

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
    except Exception as e:
        _log.warning("emergentintegrations import failed: %s", redact(str(e), max_len=80))
        return Action(action="unknown", payload={})

    try:
        chat = LlmChat(
            api_key=api_key,
            session_id=session_id or "intent-parser",
            system_message=_SYSTEM_PROMPT,
        ).with_model("anthropic", "claude-sonnet-4-6")
        msg = UserMessage(text=text.strip())
        raw = await chat.send_message(msg)
        raw = str(raw or "").strip()
    except Exception as e:
        _log.warning("LLM call failed: %s", redact(str(e), max_len=120))
        return Action(action="unknown", payload={})

    parsed = _extract_json(raw)
    if not parsed:
        _log.info("intent_parser: unparseable LLM output (%d chars)", len(raw))
        return Action(action="unknown", payload={})

    # Validate against allowed actions; downgrade to 'unknown' if disallowed
    action_name = str(parsed.get("action") or "").strip()
    if action_name not in ALLOWED_ACTIONS:
        return Action(
            action="unknown",
            entity=parsed.get("entity"),
            payload={"hint": "rejected_action", "raw": action_name},
        )

    return Action(
        action=action_name,
        entity=(parsed.get("entity") or None),
        payload=dict(parsed.get("payload") or {}),
    )


# ─────────────────────────────────────────────────────────────────────────────
# 5) Synchronous wrapper for tests / debugging
# ─────────────────────────────────────────────────────────────────────────────


def parse_intent_sync(text: str, llm_client) -> Action:
    """Synchronous variant — accepts a pluggable llm_client (callable str→str).

    Used by tests so we don't have to spin up Emergent for unit testing.
    """
    if not text or not text.strip():
        return Action(action="unknown")
    try:
        raw = llm_client(text.strip())
    except Exception as e:
        _log.warning("sync llm_client failed: %s", redact(str(e), max_len=80))
        return Action(action="unknown")
    parsed = _extract_json(str(raw or ""))
    if not parsed:
        return Action(action="unknown")
    action_name = str(parsed.get("action") or "").strip()
    if action_name not in ALLOWED_ACTIONS:
        return Action(action="unknown", entity=parsed.get("entity"),
                      payload={"hint": "rejected_action", "raw": action_name})
    return Action(
        action=action_name,
        entity=parsed.get("entity") or None,
        payload=dict(parsed.get("payload") or {}),
    )
