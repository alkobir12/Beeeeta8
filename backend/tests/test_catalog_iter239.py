"""Phase 3C.9 — Services catalog + parts + context brief tests."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest

from core import card_builder, context_brief, tool_router
from core.llm_intent_parser import _SYSTEM_PROMPT, parse_intent_sync


# ─── Service card ────────────────────────────────────────────────────────


def test_service_card_shape():
    c = card_builder.service_card({
        "id": "s1", "name": "تغيير زيت", "category": "محرك",
        "price": 50.0, "duration_minutes": 30, "active": True,
    })
    assert c["type"] == "ServiceCard"
    assert "تغيير زيت" in c["title"]
    assert c["data"]["category"] == "محرك"
    assert c["data"]["price"] == 50.0


# ─── Tool registration ──────────────────────────────────────────────────


def test_services_tools_registered():
    tools = {t["name"] for t in tool_router.list_tools()}
    assert "services.search" in tools
    assert "services.categories" in tools
    assert "parts.list" in tools


# ─── Context brief ──────────────────────────────────────────────────────


def test_brief_text_handles_empty():
    txt = context_brief.to_llm_brief_text({})
    assert "لمحة مباشرة" in txt


def test_brief_text_with_data():
    txt = context_brief.to_llm_brief_text({
        "tables": {"customers": 167, "vehicles": 200, "services": 520, "parts": 148},
        "active_visits_count": 12,
        "service_categories": [
            {"name": "محرك", "count": 30}, {"name": "فرامل", "count": 25},
        ],
        "low_stock_parts": [{"name": "فلتر زيت"}, {"name": "بطارية"}],
    })
    assert "167" in txt
    assert "520" in txt
    assert "12" in txt
    assert "محرك" in txt


# ─── LLM prompt awareness ───────────────────────────────────────────────


def test_llm_prompt_includes_vehicle_types():
    """The system prompt MUST distinguish vehicle types from plates."""
    assert "صالون" in _SYSTEM_PROMPT
    assert "جيب" in _SYSTEM_PROMPT
    # Critical correction the user complained about
    assert "vehicle_type" in _SYSTEM_PROMPT
    assert "لا تضع نوع السيارة في plate" in _SYSTEM_PROMPT


def test_llm_prompt_includes_visit_service_example():
    assert "create_visit" in _SYSTEM_PROMPT
    assert "service" in _SYSTEM_PROMPT
    assert "price" in _SYSTEM_PROMPT


def test_llm_parse_with_stub_vehicle_type():
    """When the LLM correctly returns vehicle_type, we accept it."""
    stub = lambda _t: '{"action":"create_visit","payload":{"vehicle_type":"صالون","year":2009,"customer_phone":"0501234567","service":"توضيب","price":55}}'
    res = parse_intent_sync("اضف صالون 2009 جوال 0501234567 خدمه توضيب سعر ٥٥", llm_client=stub)
    assert res.action == "create_visit"
    assert res.payload["vehicle_type"] == "صالون"
    assert res.payload["year"] == 2009
    assert res.payload["price"] == 55


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
