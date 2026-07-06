"""Iteration 251 — Bot routing hotfixes (unit regression, no network/LLM).

Bug report (live chat): «لم يتم تأكيد سداد عبد العزيز العريني — أيضاً اختلق عميل آخر».

Root causes fixed:
  FIX-1  looks_like_action() missed financial masdar/noun commands
         («تحصيل ... 2200»، «300 خصم إداري») so they fell to the LLM path,
         which faked a «اكتب نعم» card that could never commit → payment lost.
  FIX-2a detect_tools() missed «القيود كاملة / كل القيود / القيود المحاسبية»
         so accounting.journal_entries never ran → the LLM hallucinated
         5 fake journal entries with invented customer names.

These are pure regex-routing units — deterministic, no EMERGENT_LLM_KEY needed.
"""
from __future__ import annotations

import pytest

from core.assistant_kernel import looks_like_action, detect_tools


# ---- FIX-1: financial masdar commands must ROUTE TO EXECUTOR --------------

@pytest.mark.parametrize("msg", [
    "تحصيل من عبد العزيز العريني 2200 تحويل",
    "300 خصم إداري على عبد العزيز العريني",
    "سداد 500 من محمد نقدا",
    "إسقاط رصيد 300 على عبد العزيز",
    "شطب رصيد 150 على العميل",
])
def test_financial_masdar_is_action(msg):
    assert looks_like_action(msg) is True, f"must execute (not answer): {msg}"


@pytest.mark.parametrize("msg", [
    "كم التحصيل هذا الشهر؟",   # question → read path
    "أعطني تقرير التحصيل",      # report request → read path
    "وش خصم عبد العزيز",        # no amount → read path
    "كم ذمم العملاء",           # unrelated finance question
])
def test_financial_question_stays_read(msg):
    assert looks_like_action(msg) is False, f"must answer (not execute): {msg}"


# ---- FIX-2a: journal-entry queries must TRIGGER THE REAL TOOL -------------

@pytest.mark.parametrize("msg", [
    "القيود كاملة",
    "اعطني كل القيود المحاسبية",
    "القيود المحاسبية الكاملة",
    "جميع القيود",
    "كم قيد محاسبي مسجل حاليا",
])
def test_journal_query_detects_tool(msg):
    assert "accounting.journal_entries" in detect_tools(msg), (
        f"journal tool must run so the LLM shows real data, not hallucinate: {msg}"
    )
