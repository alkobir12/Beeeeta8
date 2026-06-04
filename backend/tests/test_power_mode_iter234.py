"""Phase 3B Round 2 — Power Mode + Multi-Intent + Drafts.

These tests verify the core invariants of the new layer:
  1. Mode detection (/power vs normal)
  2. Multi-intent command splitting
  3. Intent kind classification
  4. Entity extraction (plate / phone / amount / name)
  5. Draft card shape + read-only contract (no writes possible)
  6. Context resolution from session memory
  7. End-to-end power_process produces drafts list
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Make the backend importable regardless of pytest cwd
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest

from core import power_mode, shared_memory


# ── 1. Mode detection ──────────────────────────────────────────────────────


def test_detect_mode_power_slash():
    assert power_mode.detect_mode("/power do x") == "power"
    assert power_mode.detect_mode("  /power do x") == "power"
    assert power_mode.detect_mode("/POWER something") == "power"


def test_detect_mode_normal():
    assert power_mode.detect_mode("كم درجة الصحة المالية؟") == "normal"
    assert power_mode.detect_mode("") == "normal"
    assert power_mode.detect_mode("power things") == "normal"  # no leading slash


def test_strip_power_prefix():
    assert power_mode.strip_power_prefix("/power سجل عميل") == "سجل عميل"
    assert power_mode.strip_power_prefix("/POWER:  go") == "go"


# ── 2. Multi-intent splitting ──────────────────────────────────────────────


def test_extract_commands_arabic_comma():
    cmds = power_mode.extract_commands("سجل عميل احمد، أضف مركبة 9935، افتح زيارة")
    assert len(cmds) == 3
    assert "احمد" in cmds[0]
    assert "9935" in cmds[1]
    assert "زيارة" in cmds[2]


def test_extract_commands_newlines():
    cmds = power_mode.extract_commands("سجل عميل\nأضف مركبة\nافتح زيارة")
    assert len(cmds) == 3


def test_extract_commands_dot_and_thumma():
    cmds = power_mode.extract_commands("سجل عميل احمد ثم أضف مركبة 9935. افتح زيارة")
    assert len(cmds) == 3


def test_extract_commands_empty_returns_empty_list():
    assert power_mode.extract_commands("") == []
    assert power_mode.extract_commands("   ") == []


# ── 3. Intent kind ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("text,expected", [
    ("سجل عميل احمد", "customer"),
    ("أضف مركبة جديدة لوحة 1234", "vehicle"),
    ("افتح زيارة جديدة", "visit"),
    ("أضف عملية صيانة", "operation"),
    ("اصدر فاتورة بيع", "invoice"),
    ("تحصيل من العميل 500 ريال", "collection"),
    ("ادفع للمورد 300", "payment"),
    ("كم سعر الزيت", "part_search"),
    ("ما هي القطع الناقصة", "inventory"),
    ("أضف مورد جديد", "supplier"),
    ("بدون نية واضحة هنا", "unknown"),
])
def test_detect_intent_kind(text, expected):
    assert power_mode.detect_intent_kind(text) == expected


# ── 4. Entity extraction ───────────────────────────────────────────────────


def test_extract_entities_plate():
    e = power_mode.extract_entities("أضف مركبة لوحة 9935", "vehicle")
    assert e.get("plate") == "9935"


def test_extract_entities_phone():
    e = power_mode.extract_entities("سجل عميل احمد 0501234567", "customer")
    assert e.get("phone") == "0501234567"


def test_extract_entities_amount():
    e = power_mode.extract_entities("تحصيل 500 ريال من العميل", "collection")
    assert e.get("amount") == 500.0


def test_extract_entities_amount_with_decimal():
    e = power_mode.extract_entities("ادفع 1,250.75 للمورد", "payment")
    assert e.get("amount") == 1250.75


def test_extract_entities_name_arabic():
    e = power_mode.extract_entities("سجل عميل محمد العلي", "customer")
    assert "محمد" in (e.get("name") or "")


def test_extract_entities_doesnt_confuse_phone_with_amount():
    # 0501234567 must be a phone, not an amount
    e = power_mode.extract_entities("سجل عميل احمد 0501234567", "customer")
    assert e.get("phone") == "0501234567"
    assert "amount" not in e  # customer intent doesn't capture amounts anyway


# ── 5. Draft card shape ────────────────────────────────────────────────────


def test_build_draft_shape():
    d = power_mode.build_draft("customer", {"name": "احمد", "phone": "0501234567"})
    assert d["type"] == "CustomerDraftCard"
    assert d["status"] == "draft"
    assert d["intent_kind"] == "customer"
    assert d["data"]["section"] == "customer"
    assert "draft_id" in d["data"]
    # All actions must be deferred (Phase 3C)
    assert all(a["intent"] == "deferred" for a in d["actions"])
    # Title carries the name
    assert "احمد" in d["title"]


def test_build_draft_has_three_actions_review_discard_commit():
    d = power_mode.build_draft("vehicle", {"plate": "9935"})
    action_ids = sorted([a["id"] for a in d["actions"]])
    assert action_ids == sorted(["review", "discard", "commit"])


# ── 6. Context resolution from session memory ─────────────────────────────


def test_context_resolve_fills_from_last_vehicle():
    sid = "test-ctx-1"
    shared_memory.clear_session(sid)
    shared_memory.set_context(sid, "last_vehicle", {"id": "v123", "title": "9935 — تويوتا", "plate": "9935"})
    enriched = power_mode.context_resolve(sid, "operation", {"raw": "صيانة كاملة"})
    assert enriched.get("plate") == "9935"
    assert enriched.get("entity_id") == "v123"
    assert enriched["_resolved_from"]["id"] == "v123"


def test_context_resolve_does_not_overwrite_explicit_fields():
    sid = "test-ctx-2"
    shared_memory.clear_session(sid)
    shared_memory.set_context(sid, "last_vehicle", {"id": "v999", "title": "OLD", "plate": "0000"})
    enriched = power_mode.context_resolve(sid, "operation", {"raw": "x", "plate": "1111"})
    assert enriched["plate"] == "1111"  # explicit wins


def test_context_resolve_no_session_returns_unchanged():
    enriched = power_mode.context_resolve("", "operation", {"raw": "x"})
    assert "_resolved_from" not in enriched


# ── 7. End-to-end power_process ────────────────────────────────────────────


def test_power_process_produces_drafts():
    sid = "test-e2e-1"
    shared_memory.clear_session(sid)
    result = asyncio.run(power_mode.power_process(
        session_id=sid,
        # Each command now MUST have a useful entity (Phase 3C.6 guard)
        message="/power سجل عميل احمد العتيبي 0501234567، أضف مركبة 9935، افتح زيارة لـ 9935",
    ))
    assert result["mode"] == "power"
    assert result["executed"] == 3
    drafts = result["drafts"]
    kinds = [d["intent_kind"] for d in drafts if d.get("type", "").endswith("DraftCard")]
    assert "customer" in kinds
    assert "vehicle" in kinds
    # Each draft is a draft and runtime-enabled (Phase 3C)
    for d in drafts:
        if d.get("type", "").endswith("DraftCard"):
            assert d["status"] == "draft"
            intents = [a["intent"] for a in d["actions"]]
            assert "runtime" in intents


def test_power_process_updates_section_memory():
    sid = "test-e2e-2"
    shared_memory.clear_session(sid)
    asyncio.run(power_mode.power_process(
        session_id=sid,
        message="/power سجل عميل خالد 0501112233، أضف مركبة 1234",
    ))
    last_section = shared_memory.get_context(sid, "last_section")
    last_vehicle = shared_memory.get_context(sid, "last_vehicle")
    assert last_section == "vehicle"
    assert last_vehicle is not None
    assert last_vehicle["plate"] == "1234"


def test_power_process_uses_context_when_missing_entity():
    sid = "test-e2e-3"
    shared_memory.clear_session(sid)
    asyncio.run(power_mode.power_process(
        session_id=sid,
        message="/power أضف مركبة 5544 تويوتا",
    ))
    # 2nd turn — operation with no plate, should pull from context
    result = asyncio.run(power_mode.power_process(
        session_id=sid,
        message="/power أضف عملية صيانة بقيمة 350",
    ))
    op_draft = result["drafts"][0]
    # context_resolve should pull plate from last_vehicle
    assert op_draft["data"].get("plate") == "5544"


# ── 8. Read-only contract (cannot accidentally commit) ─────────────────────


def test_drafts_have_no_implicit_write_actions():
    """Phase 3C: power-mode drafts NEVER auto-commit. Phase 3C.6 also added
    a guidance card for unknown intents — they have NO actions at all.
    """
    result = asyncio.run(power_mode.power_process(
        session_id=None,
        message="/power سجل عميل خالد 0501112233، أضف مركبة 9935، تحصيل 500",
    ))
    for d in result["drafts"]:
        kind = d.get("intent_kind")
        ctype = d.get("type", "")
        if ctype == "GuidanceCard":
            # Guidance cards never have action chips
            assert d.get("actions", []) == []
            continue
        for a in d["actions"]:
            if a["intent"] == "runtime":
                assert "endpoint" in a and "/api/runtime/" in a["endpoint"]
                assert a.get("method", "POST") in ("POST", "GET")
            else:
                assert a["intent"] == "deferred", f"unexpected intent {a['intent']} on {kind}"
                assert a.get("phase")


# ── 9. Diagnose endpoint helper ────────────────────────────────────────────


def test_diagnose_for_power_message():
    d = power_mode.diagnose("/power سجل عميل احمد، أضف مركبة 9935")
    assert d["mode"] == "power"
    assert len(d["commands"]) == 2
    assert d["intents"][0]["kind"] == "customer"
    assert d["intents"][1]["kind"] == "vehicle"


def test_diagnose_for_normal_message():
    d = power_mode.diagnose("كم درجة الصحة المالية؟")
    assert d["mode"] == "normal"
    # normal returns the whole message as 1 "command"
    assert len(d["commands"]) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
