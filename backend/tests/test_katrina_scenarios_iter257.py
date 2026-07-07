"""Iteration 257 — Katrina owner-scenarios regression (deterministic, no LLM).

Covers the owner's verification list:
  • routing: آخر خمس عمليات / اجمالي الذمم / اكثر الخدمات بيعاً / كم مركبة حالية /
    المصروفات هذا الشهر / عمليات بدون قيود
  • arabic_nlp: «عبدالعزيز» compound ↔ «عبد العزيز»
  • customer resolution: exact-name preference beats partial token overlap
  • new tools registered + return sane shapes (vehicles.status_summary, operations.top_services)
"""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")

import pytest


# ---- deterministic tool routing ---------------------------------------------

@pytest.mark.parametrize("message,expected", [
    ("أعطني آخر خمس عمليات", "operations.recent"),
    ("اخر 5 عمليات", "operations.recent"),
    ("اعطني اجمالي الذمم الحالية", "finance.ar_summary"),
    ("كم الذمم؟", "finance.ar_summary"),
    ("ماهي اكثر الخدمات بيعاً", "operations.top_services"),
    ("كم مركبة حالية", "vehicles.status_summary"),
    ("عدد المركبات في الورشة", "vehicles.status_summary"),
    ("كم المصروفات هذا الشهر", "firewall.cash_flow"),
    ("هل يوجد عمليات بدون قيود محاسبية", "firewall.operation_integrity"),
])
def test_detect_tools_routing(message, expected):
    from core.assistant_kernel import detect_tools
    assert expected in detect_tools(message), f"{message} → {detect_tools(message)}"


# ---- arabic compound normalization -------------------------------------------

def test_abd_compound_matches_both_ways():
    from core.arabic_nlp import arabic_match, normalize_arabic
    assert normalize_arabic("عبد العزيز العريني") == normalize_arabic("عبدالعزيز العريني")
    assert arabic_match("عبدالعزيز العريني", "عبد العزيز العريني")
    assert arabic_match("عبد العزيز العريني", "عبدالعزيز العريني")
    assert not arabic_match("عبدالعزيز العريني", "علي عبدالعزيز العازمي")


# ---- exact-name preference in customer resolution ----------------------------

def test_exact_name_beats_partial(monkeypatch):
    from core import action_runtime
    rows = [
        {"id": "c1", "name": "محمد علي الحربي", "phone": "0546775985"},
        {"id": "c2", "name": "محمد الحربي", "phone": "0500417517"},
    ]
    monkeypatch.setattr(action_runtime, "_fetch_all", lambda table: rows)
    res = action_runtime.resolve_customer_target({"name": "محمد الحربي"})
    assert res.get("row", {}).get("id") == "c2", res
    # a genuinely ambiguous query still asks
    res2 = action_runtime.resolve_customer_target({"name": "الحربي"})
    assert res2.get("error") == "ambiguous"


# ---- new tools registered + sane output --------------------------------------

def test_new_tools_registered():
    from core import tool_router
    names = {t["name"] for t in tool_router.list_tools()}
    assert "vehicles.status_summary" in names
    assert "operations.top_services" in names


def test_vehicles_status_summary_matches_dashboard_rules():
    from core import tool_router
    res = asyncio.run(tool_router.call_tool("vehicles.status_summary"))
    assert res.get("success"), res
    data = res["result"]
    assert "total_current" in data and "by_status" in data
    # dashboard rule: current excludes delivered
    assert all(row["status"] != "delivered" for row in data["by_status"])
    assert data["total_current"] == sum(r["count"] for r in data["by_status"])


def test_top_services_uses_real_sales():
    from core import tool_router
    res = asyncio.run(tool_router.call_tool("operations.top_services"))
    assert res.get("success"), res
    data = res["result"]
    assert "top_by_count" in data and "top_by_revenue" in data
    for row in data["top_by_count"]:
        assert set(row) >= {"service", "times_sold", "revenue"}
