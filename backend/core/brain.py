"""
🧠 Brain Layer — assistant_kernel.brain() wrapper (Phase 3B Round 3)

Composes Vector Memory + Power Mode into a single "brain" entrypoint:

  Pipeline
  ────────
  1. Memory hit?  → return the recalled entity (no DB read, no LLM call)
  2. Power Mode?  → multi-intent drafting (read-only, deferred to Phase 3C)
  3. WhatsApp?    → SIMULATED outbox (clearly marked as MOCKED)
  4. Auto-report? → session-scoped counts (drafts + last_section pointers)

⚠️  Read-only contract is preserved end-to-end:
    • create_entity → build_draft (no DB write)
    • send_whatsapp → MOCKED outbox (no real send)
    • generate_report → counts session memory only
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from core import power_mode, shared_memory, vector_memory
from core.log_utils import get_logger

_log = get_logger("brain")


# ─────────────────────────────────────────────────────────────────────────────
# 1) WhatsApp simulated outbox (READ-ONLY / MOCKED)
# ─────────────────────────────────────────────────────────────────────────────


def whatsapp_outbox(session_id: str) -> List[Dict[str, Any]]:
    """Returns the per-session simulated WhatsApp outbox (FIFO)."""
    sess = shared_memory.get_or_create(session_id)
    return sess.setdefault("whatsapp_outbox", [])


def send_whatsapp_mocked(
    *,
    session_id: str,
    to: Optional[str],
    message: str,
) -> Dict[str, Any]:
    """🚫 MOCKED — Does NOT send a real WhatsApp message.

    Phase 3D will replace this with a real WhatsApp Cloud API call. For now
    we append the message to a session-scoped outbox so the UI can preview
    what would be sent and the operator can review before flipping the bit.
    """
    entry = {
        "id": f"wa_{int(time.time()*1000)}",
        "to": to or "(missing)",
        "message": message[:1000],  # cap to avoid runaway logs
        "status": "MOCKED",
        "channel": "whatsapp",
        "ts": time.time(),
        "phase_unlocked_in": "3D",
    }
    whatsapp_outbox(session_id).append(entry)
    _log.info("whatsapp send (MOCKED) to=%s len=%d", entry["to"], len(entry["message"]))
    return entry


# ─────────────────────────────────────────────────────────────────────────────
# 2) Auto-report (read-only counts of session activity)
# ─────────────────────────────────────────────────────────────────────────────


def generate_report(session_id: str) -> Dict[str, Any]:
    """Per-session live report: drafts + memory + last-* pointers."""
    sess = shared_memory.get_or_create(session_id)
    vec = vector_memory.stats(session_id)
    # Count drafts by type from the assistant message log (meta.cards)
    drafts_by_type: Dict[str, int] = {}
    for m in sess.get("messages", []):
        for c in (m.get("meta") or {}).get("cards") or []:
            t = c.get("type") or "?"
            if t.endswith("DraftCard"):
                drafts_by_type[t] = drafts_by_type.get(t, 0) + 1
    last_pointers: Dict[str, Any] = {}
    for key in ("last_customer", "last_vehicle", "last_visit", "last_operation",
                "last_invoice", "last_supplier", "last_part", "last_section"):
        val = sess.get("context", {}).get(key)
        if val is not None:
            last_pointers[key] = val
    return {
        "session_id": session_id,
        "drafts_by_type": drafts_by_type,
        "drafts_total": sum(drafts_by_type.values()),
        "vector_memory": vec,
        "last_pointers": last_pointers,
        "outbox_pending": len(sess.get("whatsapp_outbox", [])),
        "generated_at": time.time(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3) Brain entrypoint — composes memory + power + whatsapp
# ─────────────────────────────────────────────────────────────────────────────


def _wants_whatsapp(text: str) -> bool:
    if not text:
        return False
    lower = text.replace("\u200f", "")
    triggers = ("أرسل", "ارسل", "ارسلي", "واتساب", "whatsapp", "wa:")
    return any(k in lower for k in triggers)


def _strip_search_verbs(text: str) -> str:
    """Removes leading "ابحث عن"/"اعرض"/etc so the actual entity keywords match."""
    import re as _re
    return _re.sub(
        r"^\s*(?:ابحث\s+عن|أبحث\s+عن|اعرض\s*(?:لي)?|عرض|بيانات|أين|اين|ارني|أرني|من\s+هو|كم\s+(?:يستحق|رصيد))\s+",
        "", text, count=1, flags=_re.IGNORECASE,
    ).strip()


async def brain(*, session_id: str, message: str) -> Dict[str, Any]:
    """The brain pipeline. Returns one of:

      • {mode: "memory_hit",  hit, ...}
      • {mode: "power",       power: <power_block>, drafts, ...}
      • {mode: "whatsapp",    outbox_entry: <MOCKED>, ...}
      • {mode: "report",      report}
      • {mode: "passthrough", note}   ← caller should delegate to the LLM path
    """
    msg = (message or "").strip()
    if not msg:
        return {"mode": "noop", "session_id": session_id}

    # 1) Memory hit (cheap, no LLM). Strip search verbs to maximise hit rate.
    search_text = _strip_search_verbs(msg) or msg
    hit = vector_memory.memory_hit(session_id=session_id, query=search_text)
    if hit and hit.get("score", 0) >= 0.4:
        return {
            "mode": "memory_hit",
            "session_id": session_id,
            "hit": hit,
        }

    # 2) Power Mode (multi-intent drafting)
    if power_mode.detect_mode(msg) == "power":
        block = await power_mode.power_process(session_id=session_id, message=msg)
        # Mirror the produced drafts into vector_memory for future recall
        for d in block.get("drafts", []) or []:
            descriptor = " ".join(
                str(v) for v in (d.get("data") or {}).values()
                if isinstance(v, (str, int, float)) and str(v)
            )[:300]
            vector_memory.store_memory(
                session_id=session_id,
                text=descriptor,
                entity_type=d.get("type") or "DraftCard",
                entity_id=d.get("id"),
                payload={"draft": True, "intent_kind": d.get("intent_kind")},
            )
        return {
            "mode": "power",
            "session_id": session_id,
            "power": block,
            "drafts": block.get("drafts", []),
        }

    # 3) WhatsApp simulated trigger
    if _wants_whatsapp(msg):
        # Pull the last entity (customer/vehicle) for the destination phone
        last_customer = shared_memory.get_context(session_id, "last_customer") or {}
        outbox_entry = send_whatsapp_mocked(
            session_id=session_id,
            to=(last_customer.get("payload") or {}).get("phone") or last_customer.get("plate") or last_customer.get("title"),
            message=msg,
        )
        return {
            "mode": "whatsapp",
            "session_id": session_id,
            "outbox_entry": outbox_entry,
            "note": "🚫 MOCKED — لم تُرسل رسالة واتساب فعلية. Phase 3D سيُفعّل الإرسال الحقيقي.",
        }

    # 4) Report intent
    if any(k in msg for k in ("تقرير", "report", "ملخص الجلسة", "ملخصي")):
        return {
            "mode": "report",
            "session_id": session_id,
            "report": generate_report(session_id),
        }

    # 5) Passthrough — caller will use the full kernel.chat() pipeline
    return {
        "mode": "passthrough",
        "session_id": session_id,
        "note": "no shortcut matched; defer to LLM pipeline",
    }
