"""Iteration 258 — L14 Remediation regression (أمر علاج L14).

كل بند علاج له اختباره:
  D5: حارس تطابق بلوك النتائج (يحجب المختلق، يسمح بالمنفَّذ)
  D1: توجيه «اعرضي الذمم» / «راجعي القيود» / «آخر عمليتين» + نزع الأفعال المؤنثة
      + الحل الترتيبي «أول عميل في القائمة»
  D2: سجل نسخ الـ prompt + rollback فوري
  D6: طبقات ar_ledger (SSOT) متسقة وبلا لمس أرقام
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")

import pytest


# ---- D5: provenance guard -----------------------------------------------------

FABRICATED_BLOCK = (
    "دعيني أستدعي أداة العمليات الأخيرة مباشرةً.\n"
    "🛠️ نتائج الأدوات المنفّذة لهذا السؤال:\n"
    "• operations.recent: {'count': 2, 'items': [{'id': 'OP-2025-0187', 'date': '2025-07-10'}]}\n"
    "هذه آخر عمليتين."
)


def test_d5_blocks_fabricated_tool_block():
    from core import provenance_guard
    executed = [{"tool": "customers.search"}, {"tool": "operations.search"}]
    out, violations = provenance_guard.enforce(FABRICATED_BLOCK, executed)
    assert len(violations) == 1
    assert violations[0]["claimed_tool"] == "operations.recent"
    assert "OP-2025-0187" not in out
    assert "حُجب بلوك نتائج غير موثّق" in out


def test_d5_allows_executed_tool_block():
    from core import provenance_guard
    text = "• operations.recent: {'count': 2, 'items': []}"
    out, violations = provenance_guard.enforce(text, [{"tool": "operations.recent"}])
    assert violations == []
    assert out == text


def test_d5_ignores_plain_mentions():
    from core import provenance_guard
    text = "يمكنك استخدام أداة finance.ar_summary لعرض الذمم."
    out, violations = provenance_guard.enforce(text, [])
    assert violations == []
    assert out == text


# ---- D1: routing --------------------------------------------------------------

@pytest.mark.parametrize("message,expected", [
    ("اعرضي الذمم", "finance.ar_summary"),
    ("اعرض الذمم", "finance.ar_summary"),
    ("راجعي القيود", "accounting.journal_entries"),
    ("اعرضي آخر عمليتين", "operations.recent"),
    ("آخر عمليتين", "operations.recent"),
])
def test_d1_routing(message, expected):
    from core.assistant_kernel import detect_tools
    assert expected in detect_tools(message), f"{message} → {detect_tools(message)}"


def test_d1_feminine_verb_strip_no_residue():
    from core.assistant_kernel import _extract_query
    q = _extract_query("ابحثي عن محمد الحربي", "customers.search")
    assert not q.startswith("ي "), q
    assert "محمد" in q


def test_d1_ordinal_reference_regex():
    from core.assistant_kernel import _ORDINAL_LIST_RE
    m = _ORDINAL_LIST_RE.search("ابحثي عن أول عميل في القائمة")
    assert m and m.group(1) == "أول"
    assert _ORDINAL_LIST_RE.search("آخر واحد في القائمة")
    assert not _ORDINAL_LIST_RE.search("اعرضي قائمة العملاء")


# ---- D2: prompt registry + rollback -------------------------------------------

def test_d2_register_activate_rollback():
    from core import prompt_registry as pr
    ver0, _ = pr.get_active()
    try:
        pr.register("vtest-iter258", "PROMPT TEST CONTENT", activated_by="pytest")
        pr._invalidate()
        v, content = pr.get_active()
        assert v == "vtest-iter258" and content == "PROMPT TEST CONTENT"
        # rollback فوري إلى baseline
        pr.activate(pr.BASELINE_VERSION, activated_by="pytest")
        pr._invalidate()
        v2, content2 = pr.get_active()
        assert v2 == pr.BASELINE_VERSION and content2 is None
    finally:
        # استرجاع الحالة الأصلية + تنظيف نسخة الاختبار
        col = pr._collection()
        if col is not None:
            col.delete_one({"version": "vtest-iter258"})
        pr.activate(ver0, activated_by="pytest-restore")
        pr._invalidate()


# ---- D8: نافذة تاريخ المحادثة تغطي معيار S3 (رقم + 5 رسائل وسيطة + سؤال) ----

def test_d8_history_window_covers_s3_criterion():
    from core import shared_memory, ai_context
    sid = "test-d8-window-iter258"
    shared_memory.clear_session(sid) if hasattr(shared_memory, "clear_session") else None
    for i in range(7):  # 7 دورات = 14 رسالة (أكثر من سيناريو S3)
        shared_memory.append_message(sid, "user", f"سؤال {i}")
        shared_memory.append_message(sid, "assistant", f"رد {i} — الرقم المرجعي 10,850" if i == 0 else f"رد {i}")
    hist = ai_context.get_conversation_history(sid, limit=24)
    assert len(hist) == 14
    assert any("10,850" in m["content"] for m in hist), "رد الدورة الأولى يجب أن يبقى داخل النافذة"


# ---- D9: وسم ردود التاريخ بأدواتها (منع الاعتراف الكاذب عبر الدورات) ----------

def test_d9_history_carries_per_turn_tool_provenance():
    from core import shared_memory, ai_context
    sid = "test-d9-provenance-iter258"
    shared_memory.clear_session(sid)
    shared_memory.append_message(sid, "user", "اعرضي الذمم")
    shared_memory.append_message(sid, "assistant", "إجمالي الذمم 10,850",
                                 meta={"tools": ["finance.ar_summary"]})
    shared_memory.append_message(sid, "assistant", "رد بلا أدوات", meta={"tools": []})
    hist = ai_context.get_conversation_history(sid, limit=24)
    tagged = [m for m in hist if m["role"] == "assistant" and "أدوات هذه الدورة المنفَّذة فعلاً" in m["content"]]
    assert len(tagged) == 1
    assert "finance.ar_summary" in tagged[0]["content"]
    assert hist[0]["content"] == "اعرضي الذمم"  # رسائل المستخدم بلا وسم


def test_d9_prompt_v3_active_with_cross_turn_rule():
    from core import prompt_registry as pr
    pr._invalidate()
    ver, content = pr.get_active()
    assert ver == "v3-d2.1-cross-turn"
    assert content and "provenance الدورات السابقة" in content


def test_d9_llm_reply_tag_mimicry_is_stripped():
    """الرد الجديد لا يجوز أن يبدأ بوسم السجل الداخلي حتى لو قلّده النموذج."""
    import re
    text = "[أدوات هذه الدورة المنفَّذة فعلاً: customers.search]\n# نتيجة البحث\nتم."
    cleaned = re.sub(r"^\[أدوات هذه الدورة المنفَّذة فعلاً:[^\]\n]*\]\s*", "",
                     text.strip(), flags=re.MULTILINE).strip()
    assert cleaned.startswith("# نتيجة البحث")


# ---- D6: ar_ledger SSOT layers -------------------------------------------------

def test_d6_ar_ledger_layers_consistent():
    from core import ar_ledger
    s = asyncio.run(ar_ledger.summary())
    assert s["ssot"] == "journal_entries"
    assert round(s["ledger_ar_total"] + s["pending_unjournalized_total"], 2) == s["effective_ar"]
    assert round(sum(x["balance"] for x in s["stored_top_debtors"]), 2) == s["stored_balances_total"]
    assert round(s["stored_balances_total"] - s["ledger_ar_total"], 2) == s["reconciliation_gap"]
    assert s["pending_unjournalized_total"] == round(
        sum(o["total"] for o in s["pending_unjournalized_ops"]), 2)
    assert "قرار للمالك" in s["data_freeze_note"]


def test_d6_tool_keeps_legacy_numbers_untouched():
    """total_ar (المعروض تاريخياً) = مجموع الأرصدة المخزنة — بلا أي تعديل بيانات."""
    from core import tool_router
    res = asyncio.run(tool_router.call_tool("finance.ar_summary"))
    assert res.get("success"), res
    d = res["result"]
    assert d["total_ar"] == round(sum(x["balance"] for x in d["stored_top_debtors"]), 2)
    assert "ledger_ar_total" in d and "effective_ar" in d
