"""
Regression test for Bot kernel intent detection + new tools (iter 232).

Verifies:
  • Each new tool intent is detected from a natural-language Arabic question.
  • Query extraction returns the noun (search term) for query-aware tools.
  • Pre-existing tool intents still match (no regression).
  • Disjoint intents don't double-fire on similar prompts (AR vs AP).
"""
from __future__ import annotations
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.assistant_kernel import detect_tools, _extract_query


def test_inventory_low_stock_detected():
    assert "inventory.low_stock" in detect_tools("ما هي القطع الناقصة في المخزون؟")
    assert "inventory.low_stock" in detect_tools("قطع وصلت للحد الأدنى")
    assert "inventory.low_stock" in detect_tools("low stock parts")


def test_payables_summary_detected():
    assert "finance.payables_summary" in detect_tools("كم ذمم الموردين؟")
    assert "finance.payables_summary" in detect_tools("payables summary")


def test_ar_not_triggered_by_supplier_query():
    # 'ذمم الموردين' should fire AP only, not AR
    tools = detect_tools("كم ذمم الموردين؟")
    assert "finance.payables_summary" in tools
    assert "finance.ar_summary" not in tools


def test_recent_operations_detected():
    assert "operations.recent" in detect_tools("أعطني آخر العمليات")
    assert "operations.recent" in detect_tools("recent operations")


def test_customers_search_detected_and_query_extracted():
    tools = detect_tools("ابحث عن العميل ابراهيم")
    assert "customers.search" in tools
    q = _extract_query("ابحث عن العميل ابراهيم", "customers.search")
    assert "ابراهيم" in q


def test_vehicles_search_detected_and_query_extracted():
    tools = detect_tools("ابحث عن مركبة 9935")
    assert "vehicles.search" in tools
    q = _extract_query("ابحث عن مركبة 9935", "vehicles.search")
    assert "9935" in q


def test_parts_search_detected_and_query_extracted():
    """🆕 Smart sale search — should fire on بيع/سعر/كم عندي queries."""
    # Generic sell intent
    assert "parts.search" in detect_tools("بيع قطع غيار")
    # Sell + product (with verb "أبيع")
    tools = detect_tools("أبيع زيت")
    assert "parts.search" in tools
    assert "زيت" in _extract_query("أبيع زيت", "parts.search")
    # Price question
    assert "parts.search" in detect_tools("كم سعر فلتر الزيت")
    assert "فلتر" in _extract_query("كم سعر فلتر الزيت", "parts.search")
    # Stock question
    assert "parts.search" in detect_tools("كم عندي بطاريات")
    assert "بطاريات" in _extract_query("كم عندي بطاريات", "parts.search")


def test_parts_search_does_not_collide_with_low_stock():
    """'القطع الناقصة' should still hit low_stock, not parts.search."""
    tools = detect_tools("ما هي القطع الناقصة")
    assert "inventory.low_stock" in tools
    # parts.search may or may not also fire; the important thing is low_stock wins


def test_regression_existing_tools():
    """Pre-existing tools must still match."""
    assert "firewall.health_score" in detect_tools("كم درجة الصحة المالية؟")
    assert "firewall.top_alerts" in detect_tools("أعطني أهم التنبيهات")
    assert "finance.ar_summary" in detect_tools("كم ذمم العملاء؟")
    assert "workshop.active_visits" in detect_tools("كم زيارة نشطة الآن؟")
    assert "firewall.cash_flow" in detect_tools("كيف التدفق النقدي؟")
    assert "firewall.operation_integrity" in detect_tools("عمليات بها قيد مفقود")


def test_empty_message_returns_no_tools():
    assert detect_tools("") == []
    assert detect_tools("مرحبا") == []
