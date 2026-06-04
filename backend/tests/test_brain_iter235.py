"""Phase 3B Round 3 — Vector Memory + Brain + WhatsApp Outbox + Report.

Tests verify:
  1. Vector memory normalization + storage + retrieval
  2. Semantic search (substring + Jaccard) with TTL
  3. Brain pipeline routes: memory_hit, power, whatsapp (MOCKED), report, passthrough
  4. Read-only contract intact — WhatsApp never actually sends
  5. Report counts drafts/memory accurately
"""
from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest

from core import brain, power_mode, shared_memory, vector_memory


# ─── Vector Memory ─────────────────────────────────────────────────────────


def test_normalize_arabic_diacritics():
    n = vector_memory.normalize("أَحْمَد العتيبي")
    assert "احمد" in n
    assert "العتيبي" in n


def test_normalize_alef_yeh_unification():
    assert vector_memory.normalize("إبراهيم") == vector_memory.normalize("ابراهيم")
    assert vector_memory.normalize("يحيى") == vector_memory.normalize("يحيي")


def test_tokens_excludes_short_words():
    toks = vector_memory.tokens("سجل عميل ا احمد")
    assert "احمد" in toks
    # Single chars are excluded
    assert "ا" not in toks


def test_jaccard_basic():
    a = {"a", "b", "c"}
    b = {"b", "c", "d"}
    score = vector_memory.jaccard(a, b)
    assert 0.4 <= score <= 0.6  # 2/4 = 0.5


def test_store_and_search_memory_substring():
    sid = "vec-test-1"
    shared_memory.clear_session(sid)
    vector_memory.store_memory(
        session_id=sid, text="احمد العتيبي 0501112233",
        entity_type="CustomerCard", entity_id="c1",
    )
    hits = vector_memory.search_memory(session_id=sid, query="احمد")
    assert len(hits) == 1
    assert hits[0]["id"] == "c1"
    assert hits[0]["score"] == 1.0


def test_search_memory_jaccard_fallback():
    sid = "vec-test-2"
    shared_memory.clear_session(sid)
    vector_memory.store_memory(
        session_id=sid, text="مركبة تويوتا كامري 2020 لوحة 9935",
        entity_type="VehicleCard", entity_id="v1",
    )
    # Query partially overlaps — should still hit via Jaccard
    hits = vector_memory.search_memory(session_id=sid, query="تويوتا 9935")
    assert len(hits) >= 1
    assert hits[0]["id"] == "v1"


def test_search_memory_entity_type_filter():
    sid = "vec-test-3"
    shared_memory.clear_session(sid)
    vector_memory.store_memory(session_id=sid, text="احمد العتيبي", entity_type="CustomerCard", entity_id="c1")
    vector_memory.store_memory(session_id=sid, text="احمد محمد المهندس", entity_type="SupplierCard", entity_id="s1")
    cust_hits = vector_memory.search_memory(session_id=sid, query="احمد", entity_type="CustomerCard")
    supp_hits = vector_memory.search_memory(session_id=sid, query="احمد", entity_type="SupplierCard")
    assert len(cust_hits) == 1 and cust_hits[0]["id"] == "c1"
    assert len(supp_hits) == 1 and supp_hits[0]["id"] == "s1"


def test_search_memory_ttl_expiry():
    sid = "vec-test-4"
    shared_memory.clear_session(sid)
    vector_memory.store_memory(session_id=sid, text="قديم", entity_type="X", entity_id="x1")
    # Force TTL=0 so the entry is "expired"
    hits = vector_memory.search_memory(session_id=sid, query="قديم", ttl_seconds=0)
    assert hits == []


def test_memory_hit_returns_top1():
    sid = "vec-test-5"
    shared_memory.clear_session(sid)
    vector_memory.store_memory(session_id=sid, text="احمد", entity_type="CustomerCard", entity_id="c1")
    hit = vector_memory.memory_hit(session_id=sid, query="احمد")
    assert hit is not None
    assert hit["id"] == "c1"


def test_vector_memory_capped_at_max_per_session():
    sid = "vec-test-6"
    shared_memory.clear_session(sid)
    for i in range(150):
        vector_memory.store_memory(session_id=sid, text=f"entry{i}", entity_type="X", entity_id=f"e{i}")
    s = vector_memory.stats(sid)
    assert s["total"] == 100  # capped


# ─── Brain pipeline ────────────────────────────────────────────────────────


def test_brain_passthrough_when_no_shortcut():
    sid = "brain-1"
    shared_memory.clear_session(sid)
    r = asyncio.run(brain.brain(session_id=sid, message="كم درجة الصحة المالية؟"))
    assert r["mode"] == "passthrough"


def test_brain_power_route_returns_drafts():
    sid = "brain-2"
    shared_memory.clear_session(sid)
    r = asyncio.run(brain.brain(session_id=sid, message="/power سجل عميل احمد، أضف مركبة 9935"))
    assert r["mode"] == "power"
    assert len(r["drafts"]) == 2
    # Drafts mirrored into vector memory
    s = vector_memory.stats(sid)
    assert s["total"] >= 2


def test_brain_memory_hit_route_short_circuits():
    sid = "brain-3"
    shared_memory.clear_session(sid)
    # Seed memory with a known entity
    vector_memory.store_memory(
        session_id=sid, text="احمد العتيبي 0501234567 لوحة 9935",
        entity_type="CustomerCard", entity_id="c1",
    )
    r = asyncio.run(brain.brain(session_id=sid, message="ابحث عن احمد العتيبي"))
    assert r["mode"] == "memory_hit"
    assert r["hit"]["id"] == "c1"


def test_brain_whatsapp_route_is_mocked():
    sid = "brain-4"
    shared_memory.clear_session(sid)
    r = asyncio.run(brain.brain(session_id=sid, message="أرسل واتساب للعميل"))
    assert r["mode"] == "whatsapp"
    assert r["outbox_entry"]["status"] == "MOCKED"
    assert r["outbox_entry"]["phase_unlocked_in"] == "3D"
    # Outbox now has the entry
    outbox = brain.whatsapp_outbox(sid)
    assert len(outbox) == 1


def test_brain_whatsapp_never_actually_sends():
    """The MOCKED whatsapp must not have any side-effect outside the outbox."""
    sid = "brain-5"
    shared_memory.clear_session(sid)
    asyncio.run(brain.brain(session_id=sid, message="أرسل واتساب"))
    sess = shared_memory.get_or_create(sid)
    # Only outbox should have a record, not actions/messages with intent='send'
    assert all(m.get("role") != "outbound_whatsapp" for m in sess.get("messages", []))
    # The outbox entries are flagged MOCKED — no real send
    for entry in sess["whatsapp_outbox"]:
        assert entry["status"] == "MOCKED"


def test_brain_report_route():
    sid = "brain-6"
    shared_memory.clear_session(sid)
    asyncio.run(brain.brain(session_id=sid, message="/power سجل عميل، أضف مركبة 1234"))
    r = asyncio.run(brain.brain(session_id=sid, message="أعطني تقرير الجلسة"))
    assert r["mode"] == "report"
    rep = r["report"]
    assert rep["drafts_total"] == 0  # drafts live in messages.meta.cards but kernel.chat wasn't called
    # vector memory should have 2 drafts mirrored
    assert rep["vector_memory"]["total"] == 2


# ─── Auto report ───────────────────────────────────────────────────────────


def test_generate_report_counts_pointers():
    sid = "rep-1"
    shared_memory.clear_session(sid)
    shared_memory.set_context(sid, "last_customer", {"id": "c1", "title": "احمد"})
    shared_memory.set_context(sid, "last_vehicle", {"id": "v1", "title": "9935"})
    rep = brain.generate_report(sid)
    assert "last_customer" in rep["last_pointers"]
    assert "last_vehicle" in rep["last_pointers"]


# ─── Read-only contract guard ──────────────────────────────────────────────


def test_no_implicit_db_writes_anywhere_in_brain():
    """Brain modes never auto-commit. Power drafts can have 'runtime' chips
    (which call /api/runtime/... after explicit user click + approval), but
    no chip directly mutates data without going through the approval matrix.
    """
    sid = "ro-1"
    shared_memory.clear_session(sid)

    # Power Mode — drafts only (no implicit commit)
    r1 = asyncio.run(brain.brain(session_id=sid, message="/power سجل عميل احمد"))
    for d in r1["drafts"]:
        # Every draft is still 'draft' status — never auto-committed
        for a in d["actions"]:
            # Only acceptable intents at this stage
            assert a["intent"] in ("deferred", "runtime"), f"unexpected intent {a['intent']}"
            if a["intent"] == "runtime":
                # Must hit the /api/runtime/ endpoint, NOT a raw DB write
                assert "/api/runtime/" in a.get("endpoint", "")

    # WhatsApp — MOCKED
    r2 = asyncio.run(brain.brain(session_id=sid, message="أرسل واتساب"))
    assert r2["outbox_entry"]["status"] == "MOCKED"

    # tool_router still has no write tools
    from core import tool_router
    for tool_meta in tool_router.list_tools():
        assert tool_meta.get("write") is False, f"Found write-capable tool: {tool_meta}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
