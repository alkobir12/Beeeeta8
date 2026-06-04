"""
🧠 Vector Memory — Semantic Brain Layer (Phase 3B Round 3)

A session-scoped semantic recall layer for the Floating Assistant.

NOT a real vector DB — we do *normalized substring + token-set* matching here,
which is good enough for "find the customer I just mentioned" and "what was
the last invoice number" without dragging in numpy/sentence-transformers.

When the assistant produces or surfaces an entity (Customer, Vehicle, Invoice,
Operation, …), we call `store_memory()` so subsequent queries inside the same
session can find it via `search_memory(query)`. This dramatically improves
context-resolution for L16 conversations:

    Turn 1 user:  "سجل عميل احمد العتيبي 0501112233"
    Turn 2 user:  "كم استحق احمد؟"   → search_memory("احمد") → CustomerEntry hit

⚠️  Read-only contract preserved: store_memory only writes into the in-memory
ring buffer attached to `shared_memory[sid]['vector_mem']`. No DB writes.
"""
from __future__ import annotations

import re
import time
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

from core import shared_memory

# Each session's vector memory is capped — prevents unbounded growth.
_MAX_PER_SESSION = 100

# How long an entry "lives" inside the ring buffer (matches shared_memory TTL).
_DEFAULT_TTL_SECONDS = 3600


# ─────────────────────────────────────────────────────────────────────────────
# Text normalization (cheap, no external deps)
# ─────────────────────────────────────────────────────────────────────────────

_ARABIC_DIACRITICS = re.compile(r"[\u064B-\u0652\u0670]")
_NON_ALPHANUM = re.compile(r"[^\w\u0621-\u064A0-9]+")
_ALEF_VARIANTS = re.compile(r"[إأآا]")
_YEH_VARIANTS = re.compile(r"[ىئي]")
_TEH_MARBUTA = re.compile(r"ة")


def normalize(text: str) -> str:
    """Cheap Arabic-friendly normalization:
      - lowercase
      - strip diacritics + control marks
      - unify alef/yeh variants and teh marbuta
      - collapse non-word runs into spaces
    """
    if not text:
        return ""
    t = unicodedata.normalize("NFKC", str(text).lower())
    t = _ARABIC_DIACRITICS.sub("", t)
    t = _ALEF_VARIANTS.sub("ا", t)
    t = _YEH_VARIANTS.sub("ي", t)
    t = _TEH_MARBUTA.sub("ه", t)
    t = _NON_ALPHANUM.sub(" ", t)
    return " ".join(t.split())


def tokens(text: str) -> set:
    """Tokenize a normalized string into a set of unique tokens."""
    return set([w for w in normalize(text).split() if len(w) >= 2])


def jaccard(a: set, b: set) -> float:
    """Token-set similarity (0.0 — 1.0)."""
    if not a or not b:
        return 0.0
    return len(a & b) / max(1, len(a | b))


# ─────────────────────────────────────────────────────────────────────────────
# Storage primitives — backed by shared_memory's session dict
# ─────────────────────────────────────────────────────────────────────────────


def _bucket(session_id: str) -> List[Dict[str, Any]]:
    """Lazy-init the session's vector_mem list."""
    sess = shared_memory.get_or_create(session_id)
    return sess.setdefault("vector_mem", [])


def store_memory(
    *,
    session_id: str,
    text: str,
    entity_type: str,
    entity_id: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Add an entity description to the session's vector memory.

    Returns the stored entry (with id + ts) so callers can chain.
    """
    if not session_id or not text:
        return {}
    entry = {
        "text": text,
        "norm": normalize(text),
        "tokens": list(tokens(text)),
        "type": entity_type,
        "id": entity_id,
        "payload": payload or {},
        "ts": time.time(),
    }
    bucket = _bucket(session_id)
    bucket.append(entry)
    # Trim ring buffer
    if len(bucket) > _MAX_PER_SESSION:
        del bucket[: len(bucket) - _MAX_PER_SESSION]
    return entry


def search_memory(
    *,
    session_id: str,
    query: str,
    entity_type: Optional[str] = None,
    limit: int = 5,
    threshold: float = 0.25,
    ttl_seconds: int = _DEFAULT_TTL_SECONDS,
) -> List[Dict[str, Any]]:
    """Return the top-N matching entries for a query.

    Strategy:
      1. exact normalized substring hits (score = 1.0)
      2. fallback to Jaccard token overlap (score = ratio)
    Only entries newer than `ttl_seconds` are considered.
    """
    if not session_id or not query:
        return []
    bucket = _bucket(session_id)
    if not bucket:
        return []
    q_norm = normalize(query)
    q_tokens = tokens(query)
    now = time.time()
    candidates: List[Tuple[float, Dict[str, Any]]] = []

    for entry in bucket:
        # TTL guard
        if (now - entry.get("ts", 0)) > ttl_seconds:
            continue
        # Type filter
        if entity_type and entry.get("type") != entity_type:
            continue

        # 1) substring hit
        score = 0.0
        if q_norm and q_norm in entry.get("norm", ""):
            score = 1.0
        else:
            # 2) Jaccard token overlap
            e_tokens = set(entry.get("tokens") or [])
            sim = jaccard(q_tokens, e_tokens)
            if sim >= threshold:
                score = sim

        if score > 0:
            candidates.append((score, entry))

    # Newest-first when scores tie
    candidates.sort(key=lambda c: (c[0], c[1].get("ts", 0)), reverse=True)
    return [
        {**c[1], "score": round(c[0], 3)}
        for c in candidates[:limit]
    ]


def memory_hit(
    *,
    session_id: str,
    query: str,
    entity_type: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Convenience: return top-1 hit (or None) for L16 brain queries."""
    hits = search_memory(session_id=session_id, query=query, entity_type=entity_type, limit=1)
    return hits[0] if hits else None


def stats(session_id: str) -> Dict[str, Any]:
    """How many entries does this session have right now?"""
    bucket = _bucket(session_id)
    by_type: Dict[str, int] = {}
    for e in bucket:
        by_type[e.get("type", "?")] = by_type.get(e.get("type", "?"), 0) + 1
    return {"total": len(bucket), "by_type": by_type}


def clear(session_id: str) -> int:
    """Wipe the vector memory for one session. Returns # entries removed."""
    bucket = _bucket(session_id)
    n = len(bucket)
    bucket.clear()
    return n
