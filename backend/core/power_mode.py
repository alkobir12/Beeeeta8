"""
⚡ Power Mode — Multi-Intent + Context-Aware Drafts (Phase 3B Round 2)

This is an UPDATE to the existing Floating Assistant Layer.
NOT a new module, NOT a new system.

Capabilities
------------
1. `/power` prefix → multi-intent execution (splits the message by sentence
   separators and processes each command independently in one round-trip).
2. Lightweight Arabic NLP — detects intent kind (customer / vehicle / visit /
   operation / collection / payment / inventory / part-search …).
3. **Draft Cards** — every command returns a *draft* card (status="draft").
   Drafts are READ-ONLY proposals; no writes hit the DB. Phase 3C will turn
   drafts into approval-gated commits.
4. **Context Resolver** — `last_section / last_customer / last_vehicle /
   last_visit / last_invoice / last_operation` provide fallbacks when the user
   says "اعطه ربلات" (no entity → resolve from last context).
5. Entity Extraction — pulls numbers / plates / names / dates / amounts from
   raw text so the draft card carries useful summary fields.

Read-only contract
------------------
Power Mode never mutates the DB. `execute_action()` only:
  • parses
  • optionally calls a *read* tool to enrich the draft
  • returns a draft card

Actual writes are deferred to Phase 3C's Approval Runtime.
"""
from __future__ import annotations

import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

from core import shared_memory


# ─────────────────────────────────────────────────────────────────────────────
# 1) Mode detection
# ─────────────────────────────────────────────────────────────────────────────

POWER_PREFIX_RE = re.compile(r"^\s*/power\b[:\s]*", re.IGNORECASE)


def detect_mode(text: str) -> str:
    """Returns 'power' if the message opens with `/power` (or `power:`)."""
    if not text:
        return "normal"
    return "power" if POWER_PREFIX_RE.match(text) else "normal"


def strip_power_prefix(text: str) -> str:
    """Removes the `/power` prefix from the message for downstream parsing."""
    return POWER_PREFIX_RE.sub("", text or "", count=1).strip()


# ─────────────────────────────────────────────────────────────────────────────
# 2) Multi-intent splitting
# ─────────────────────────────────────────────────────────────────────────────

# Split on: newline | Arabic comma | Arabic semicolon | dot | " ثم " | " and " | " و " (only when surrounded by spaces)
_SPLIT_RE = re.compile(r"\s*(?:\n+|،|؛|\.(?:\s|$)|\bثم\b|\band\b|\s+و\s+)\s*", re.IGNORECASE)


def extract_commands(text: str) -> List[str]:
    """Splits a free-text request into atomic sub-commands.

    Examples
    --------
    >>> extract_commands("سجل عميل احمد، أضف مركبة 1234، افتح زيارة")
    ['سجل عميل احمد', 'أضف مركبة 1234', 'افتح زيارة']
    """
    raw = (text or "").strip()
    if not raw:
        return []
    parts = [p.strip() for p in _SPLIT_RE.split(raw) if p and p.strip()]
    # Drop tiny noise tokens (< 3 chars) that have no verb / noun
    parts = [p for p in parts if len(p) >= 3 or any(c.isalpha() for c in p)]
    return parts


# ─────────────────────────────────────────────────────────────────────────────
# 3) Intent kind detection per command
# ─────────────────────────────────────────────────────────────────────────────

# Order matters — more specific patterns first.
_INTENT_PATTERNS: List[Tuple[str, re.Pattern[str]]] = [
    ("collection", re.compile(r"\b(?:تحصيل|اقبض|قبض|حصّل|دفع\s*(?:ال)?عميل|سدد\s*(?:ال)?عميل|دفعة\s*من)\b", re.IGNORECASE)),
    ("payment", re.compile(r"\b(?:ادفع|دفع\s*(?:ال)?مورد|سداد\s*(?:ال)?مورد|سند\s*صرف|اصرف|اصرفي)\b", re.IGNORECASE)),
    ("invoice", re.compile(r"\b(?:فاتورة|invoice|بيع\s+ل|بع\s+ل|اصدر\s+فاتورة|كشف\s+حساب)\b", re.IGNORECASE)),
    ("part_search", re.compile(r"\b(?:سعر|كم\s+سعر|كم\s+ع?ندي|كم\s+ع?ندنا|متوفر|بيع\s+قطع|أبيع|ابيع|ابحث\s+عن\s+قطع|اشتري\s+قطع)\b", re.IGNORECASE)),
    ("visit", re.compile(r"\b(?:زيارة|افتح\s+زيارة|سجل\s+زيارة|دخل|إدخال|ادخال|استقبال)\b", re.IGNORECASE)),
    ("operation", re.compile(r"\b(?:عملية|أضف\s+عملية|اضف\s+عملية|سجل\s+عملية|خدمة\s+جديدة|أمر\s+شغل)\b", re.IGNORECASE)),
    ("vehicle", re.compile(r"\b(?:مركبة|سيارة|لوحة|رقم\s+اللوحة|أضف\s+مركبة|اضف\s+سيارة)\b", re.IGNORECASE)),
    ("customer", re.compile(r"\b(?:عميل|زبون|عميلة|زبونة|أضف\s+عميل|اضف\s+عميل|سجل\s+عميل|عميل\s+جديد)\b", re.IGNORECASE)),
    ("supplier", re.compile(r"\b(?:مورد|أضف\s+مورد|اضف\s+مورد|سجل\s+مورد)\b", re.IGNORECASE)),
    ("inventory", re.compile(r"\b(?:قطع\s+ناقصة|مخزون|قطع\s+منخفضة|الحد\s+الأدنى|نواقص|القطع\s+الناقصة|low\s*stock)\b", re.IGNORECASE)),
    ("oil", re.compile(r"\b(?:زيت|فلتر|filter|بطار|بواجي|تيل)\b", re.IGNORECASE)),
]


def detect_intent_kind(cmd: str) -> str:
    """Maps a single command to an intent kind (customer/vehicle/visit/...)."""
    if not cmd:
        return "unknown"
    for kind, rgx in _INTENT_PATTERNS:
        if rgx.search(cmd):
            # "oil" is really a part_search ("غيّر زيت" ≈ "أبيع زيت")
            return "part_search" if kind == "oil" else kind
    return "unknown"


# ─────────────────────────────────────────────────────────────────────────────
# 4) Entity extraction (numbers / plates / phones / amounts / names)
# ─────────────────────────────────────────────────────────────────────────────

_PLATE_RE = re.compile(r"\b(\d{3,4}\s*[A-Za-z\u0600-\u06FF]{1,4}|\d{4,5})\b")
_PHONE_RE = re.compile(r"\b(05\d{8}|9665\d{8}|\+9665\d{8})\b")
_AMOUNT_RE = re.compile(r"\b(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)\s*(?:ر\.?س|ريال|sar|sr)?\b", re.IGNORECASE)
# Arabic personal name heuristic: 1-4 words of Arabic letters, no digits
_ARABIC_NAME_RE = re.compile(r"([\u0621-\u064A]{2,}(?:\s+[\u0621-\u064A]+){0,3})")


def extract_entities(cmd: str, intent_kind: str) -> Dict[str, Any]:
    """Lightweight entity pull — enriches the draft card."""
    out: Dict[str, Any] = {"raw": cmd}
    if not cmd:
        return out

    # Plate / vehicle ID
    if intent_kind in ("vehicle", "visit", "operation"):
        m = _PLATE_RE.search(cmd)
        if m:
            out["plate"] = m.group(1).strip()

    # Phone
    pm = _PHONE_RE.search(cmd)
    if pm:
        out["phone"] = pm.group(1)

    # Amount (skip phones / plates already matched)
    cleaned = cmd
    if pm:
        cleaned = cleaned.replace(pm.group(0), " ")
    if "plate" in out:
        cleaned = cleaned.replace(out["plate"], " ")
    am = _AMOUNT_RE.search(cleaned)
    if am and intent_kind in ("collection", "payment", "invoice", "operation"):
        try:
            out["amount"] = float(am.group(1).replace(",", ""))
        except (ValueError, TypeError):
            pass

    # Arabic name (only for customer/supplier intents)
    if intent_kind in ("customer", "supplier"):
        # Strip verbs first
        stripped = re.sub(
            r"\b(?:سجل|أضف|اضف|أنشئ|انشئ|عميل|عميلة|زبون|زبونة|مورد|جديد|جديدة|اسمه|اسمها)\b",
            " ", cmd, flags=re.IGNORECASE,
        )
        nm = _ARABIC_NAME_RE.search(stripped)
        if nm:
            out["name"] = nm.group(1).strip()

    return out


# ─────────────────────────────────────────────────────────────────────────────
# 5) Context resolver — fill missing entities from session memory
# ─────────────────────────────────────────────────────────────────────────────

# Per-intent context mapping: which fields can be pulled from which last_* key.
# This prevents bleed-through (e.g. customer name into vehicle draft).
_CONTEXT_FALLBACK_MAP: Dict[str, List[Tuple[str, List[str]]]] = {
    # vehicle drafts can inherit plate from last_vehicle only
    "vehicle": [("last_vehicle", ["plate", "entity_id"])],
    # visit/operation lean on last_vehicle, then last_customer
    "visit": [("last_vehicle", ["plate", "entity_id"]), ("last_customer", ["name"])],
    "operation": [("last_vehicle", ["plate", "entity_id"]), ("last_customer", ["name"])],
    # invoice/collection are customer-centric
    "invoice": [("last_customer", ["name", "entity_id"]), ("last_vehicle", ["plate"])],
    "collection": [("last_customer", ["name", "entity_id"])],
    # payment to a supplier
    "payment": [("last_supplier", ["name", "entity_id"])],
    # part_search re-uses the last queried part
    "part_search": [("last_part", ["name", "entity_id"])],
}


def context_resolve(session_id: str, intent_kind: str, entities: Dict[str, Any]) -> Dict[str, Any]:
    """Fill missing entities from session memory when the user is brief.

    Strategy: each intent kind declares an *ordered* list of (memory_key, fields)
    pairs. We only pull the listed fields, never blanket-merge — this avoids
    e.g. the customer's name leaking into a vehicle draft.
    """
    if not session_id:
        return entities
    mapping = _CONTEXT_FALLBACK_MAP.get(intent_kind, [])
    if not mapping:
        return entities

    enriched = dict(entities)
    for mem_key, fields in mapping:
        ctx_entity = shared_memory.get_context(session_id, mem_key)
        if not ctx_entity:
            continue
        for field in fields:
            if enriched.get(field):
                continue  # explicit value wins
            # Field-specific pull rules
            if field == "name":
                val = ctx_entity.get("title")
                # Don't pull a "مسوّدة …" placeholder
                if val and not str(val).startswith("مسوّدة"):
                    enriched["name"] = val
            elif field == "plate":
                val = ctx_entity.get("plate")
                if val:
                    enriched["plate"] = val
            elif field == "entity_id":
                val = ctx_entity.get("id")
                if val:
                    enriched["entity_id"] = val
        # Only mark resolution if we actually pulled something useful
        if enriched != entities and "_resolved_from" not in enriched:
            enriched["_resolved_from"] = {
                "key": mem_key,
                "id": ctx_entity.get("id"),
                "title": ctx_entity.get("title"),
            }
    return enriched


# ─────────────────────────────────────────────────────────────────────────────
# 6) Section tracking — keeps "last_section" warm
# ─────────────────────────────────────────────────────────────────────────────

_INTENT_TO_SECTION = {
    "customer": "customer",
    "vehicle": "vehicle",
    "visit": "visit",
    "operation": "operation",
    "invoice": "invoice",
    "collection": "collection",
    "payment": "payment",
    "supplier": "supplier",
    "inventory": "inventory",
    "part_search": "inventory",
}


def update_section_memory(session_id: str, intent_kind: str, draft: Dict[str, Any]) -> None:
    """Persists current section + draft summary into session memory.

    The stored pointer uses the *real* entity field (name/plate) — NOT the
    "مسوّدة …" placeholder title — so context_resolve can read it back cleanly.
    """
    if not session_id:
        return
    section = _INTENT_TO_SECTION.get(intent_kind)
    if not section:
        return
    shared_memory.set_context(session_id, "last_section", section)
    data = draft.get("data") or {}
    # Pick the "real" identifier for the pointer's title — prefer name → plate
    real_title = (
        data.get("name")
        or data.get("plate")
        or (f"{data.get('amount')} ر.س" if data.get("amount") else None)
        or "(بدون اسم)"
    )
    pointer = {
        "id": draft.get("id"),
        "title": real_title,
        "type": draft.get("type"),
        "plate": data.get("plate"),
    }
    shared_memory.set_context(session_id, f"last_{section}", pointer)


# ─────────────────────────────────────────────────────────────────────────────
# 7) Public API — process one command or a full power-mode batch
# ─────────────────────────────────────────────────────────────────────────────


def _section_label(kind: str) -> str:
    return {
        "customer": "عميل", "vehicle": "مركبة", "visit": "زيارة",
        "operation": "عملية", "invoice": "فاتورة", "collection": "تحصيل",
        "payment": "صرف", "supplier": "مورد", "inventory": "مخزون",
        "part_search": "بحث قطع", "unknown": "غير محدد",
    }.get(kind, kind)


def build_draft(intent_kind: str, entities: Dict[str, Any]) -> Dict[str, Any]:
    """Builds a draft card (status='draft', no DB write).

    Returns a card-shaped dict compatible with the existing AssistantCard
    renderer, so the frontend can show it inline.
    """
    draft_id = uuid.uuid4().hex[:10]
    label = _section_label(intent_kind)
    # Build a short title from the most distinctive field
    title_bits = [f"مسوّدة {label}"]
    if entities.get("name"):
        title_bits.append("—")
        title_bits.append(entities["name"])
    elif entities.get("plate"):
        title_bits.append("—")
        title_bits.append(entities["plate"])
    elif entities.get("amount"):
        title_bits.append("—")
        title_bits.append(f"{entities['amount']:,.2f} ر.س")
    title = " ".join(title_bits)

    return {
        "type": f"{intent_kind.capitalize()}DraftCard",
        "id": draft_id,
        "title": title,
        "status": "draft",
        "intent_kind": intent_kind,
        "data": {
            **entities,
            "section": _INTENT_TO_SECTION.get(intent_kind, intent_kind),
            "draft_id": draft_id,
            "label": label,
        },
        "actions": [
            # All deferred to Phase 3C (Approval Runtime). Read-only contract intact.
            {"id": "review", "label": "مراجعة", "intent": "deferred", "phase": "3C"},
            {"id": "discard", "label": "تجاهل", "intent": "deferred", "phase": "3C"},
            {"id": "commit", "label": "تنفيذ", "intent": "deferred", "phase": "3C"},
        ],
    }


async def execute_action(*, session_id: Optional[str], cmd: str, proposer: Optional[str] = None) -> Dict[str, Any]:
    """Process a single sub-command → returns a draft card.

    Pure read-only. Optionally enriches via a read tool result in the future.
    Phase 3C: the draft is also registered in the Action Runtime so it can
    later be approved + committed.

    🆕 Phase 3C.6: If intent is `unknown` OR no useful entity was extracted,
    we return a "guidance card" instead of a draft. This prevents the bot
    from spamming "مسوّدة غير محدد" for general questions like "ماذا تستطيع
    فعله".
    """
    cmd = (cmd or "").strip()
    if not cmd:
        return {"type": "EmptyCommand", "id": "noop", "title": "أمر فارغ", "data": {}, "actions": []}

    intent_kind = detect_intent_kind(cmd)
    entities = extract_entities(cmd, intent_kind)
    if session_id:
        entities = context_resolve(session_id, intent_kind, entities)

    # 🆕 Guard: don't fabricate "غير محدد" drafts. If we couldn't classify a
    # clear intent, return a guidance message — NOT a draft card.
    has_useful_entity = any(entities.get(k) for k in ("name", "plate", "amount", "phone"))
    if intent_kind == "unknown" or (intent_kind in {"customer", "vehicle", "visit", "supplier"} and not has_useful_entity):
        # If the cmd is clearly a *question* (starts with استفهامية / كم / كيف / etc),
        # signal the LLM path. Otherwise show a "what I can do" guide.
        QUESTION_RE = re.compile(
            r"^\s*(?:ما\s|ماذا|كم|كيف|متى|اين|أين|هل|من\s|لماذا|أي\s|اي\s|ابحث|اعطني|أعطني|اعرض|ارني|أرني)",
            re.IGNORECASE,
        )
        is_question = bool(QUESTION_RE.search(cmd))
        return {
            "type": "GuidanceCard",
            "id": f"guide-{uuid.uuid4().hex[:8]}",
            "title": "أحتاج تفاصيل أكثر" if not is_question else "اسأل بصياغة أوضح",
            "kind": "question" if is_question else "no_intent",
            "data": {
                "raw": cmd[:200],
                "hint": (
                    "لتسجيل عميل/مركبة/زيارة، أعطني تفاصيل: الاسم، الجوال، اللوحة، أو المبلغ."
                    if not is_question else
                    "تأكد من ذكر اسم العميل أو رقم اللوحة في سؤالك."
                ),
                "examples": [
                    "سجل عميل احمد العتيبي 0501234567",
                    "أضف مركبة 9935 تويوتا كامري",
                    "أكثر العملاء مديونية",
                    "أرسل واتساب للعميل آخر زيارة",
                ],
            },
            "actions": [],
        }

    draft = build_draft(intent_kind, entities)
    if session_id:
        update_section_memory(session_id, intent_kind, draft)
        shared_memory.track_action(session_id, "power_draft", {
            "intent_kind": intent_kind,
            "draft_id": draft.get("id"),
            "has_context_fallback": bool(entities.get("_resolved_from")),
        })

    # 🆕 Phase 3C: register this draft in the Action Runtime so an approver
    # can later request_approval → approve → commit. The runtime stores its
    # own copy (decoupled from the UI card) under the same id.
    if intent_kind in {"customer", "vehicle", "visit"}:
        try:
            from core import action_runtime
            action_runtime.create_draft(
                action=intent_kind,
                payload=entities,
                proposer=proposer,
                session_id=session_id,
                draft_id=draft.get("id"),
            )
            draft["actions"] = [
                {"id": "request_approval", "label": "طلب اعتماد", "intent": "runtime",
                 "endpoint": f"/api/runtime/drafts/{draft['id']}/request_approval", "method": "POST"},
                {"id": "discard", "label": "تجاهل", "intent": "runtime",
                 "endpoint": f"/api/runtime/drafts/{draft['id']}/discard", "method": "POST"},
            ]
            draft["runtime"] = {"enabled": True, "phase": "3C"}
        except Exception as e:  # never break the draft pipeline
            from core.log_utils import get_logger as _gl, redact as _r
            _gl("power_mode").warning("action_runtime register failed: %s", _r(str(e), max_len=80))
            draft["runtime"] = {"enabled": False, "error": "runtime_unavailable"}

    return draft


async def power_process(*, session_id: Optional[str], message: str, proposer: Optional[str] = None) -> Dict[str, Any]:
    """Run Power Mode end-to-end. Returns drafts + metadata."""
    body = strip_power_prefix(message)
    commands = extract_commands(body)

    drafts: List[Dict[str, Any]] = []
    for cmd in commands:
        draft = await execute_action(session_id=session_id, cmd=cmd, proposer=proposer)
        drafts.append(draft)

    return {
        "mode": "power",
        "executed": len(drafts),
        "drafts": drafts,
        "raw_message": message,
        "commands": commands,
    }


async def normal_process(*, session_id: Optional[str], message: str) -> Dict[str, Any]:
    """Single-command path for normal mode (used as a hint, not a replacement
    for the LLM pipeline). Currently UNUSED by the kernel — kept for future
    quick-action endpoints.
    """
    draft = await execute_action(session_id=session_id, cmd=message)
    return {"mode": "normal", "draft": draft, "raw_message": message}


# ─────────────────────────────────────────────────────────────────────────────
# 8) Diagnostics — exposed for tests / debug endpoint
# ─────────────────────────────────────────────────────────────────────────────


def diagnose(message: str) -> Dict[str, Any]:
    """Return what Power Mode *would* do for a given message, without running it."""
    mode = detect_mode(message)
    body = strip_power_prefix(message) if mode == "power" else message
    cmds = extract_commands(body) if mode == "power" else [body]
    return {
        "mode": mode,
        "commands": cmds,
        "intents": [{"cmd": c, "kind": detect_intent_kind(c), "entities": extract_entities(c, detect_intent_kind(c))} for c in cmds],
    }
