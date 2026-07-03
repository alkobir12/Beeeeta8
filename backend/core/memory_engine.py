"""🧠 Memory Engine — RRR المرحلة 2 (قواعد الترقية الخمس المعتمدة في /app/memory/ROADMAP.md).

الطبقات: session (shared_memory) → short → long → knowledge (Mongo: assistant_memory)
1. Session→Short: تلقائي فقط للعناصر المصنفة (decision/correction/tool_failure) — الثرثرة لا تُرقّى.
2. Short→Long: (تكرار في 3 جلسات مختلفة أو تصحيح صريح من admin) + عمر < 30 يوماً.
   غير المُرقّى خلال 30 يوماً يُحذف (تنظيف كسول).
3. Long→Knowledge: اعتماد بشري فقط عبر محرك الاعتمادات (Learning Candidate → draft
   action=memory_promote → admin يعتمد → commit يرقّي). لا ترقية تلقائية إطلاقاً.
4. التلوث: معرفة تتعارض مع أحدث → تُعلَّم disputed وتُجمّد من الحقن حتى يفصل admin.
5. السقف: المعرفة المحقونة ≤ 2000 token؛ التجاوز يمنع إضافة جديد حتى الدمج/الأرشفة.
قرار معماري: top-k retrieval انتقائي — لا حقن كامل.
"""
from __future__ import annotations

import os
import re
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

from core.log_utils import get_logger, redact

_log = get_logger("memory_engine")

COL = "assistant_memory"
KNOWLEDGE_TOKEN_CAP = 2000
SHORT_TTL_DAYS = 30
PROMOTE_SESSIONS = 3

_client = None
_db = None
_lock = threading.Lock()
_ENABLED: Optional[bool] = None


def _database():
    global _client, _db
    if _db is not None:
        return _db
    with _lock:
        if _db is not None:
            return _db
        from pymongo import MongoClient
        uri = os.environ["MONGO_URL"]
        name = os.environ["DB_NAME"]
        _client = MongoClient(uri, serverSelectionTimeoutMS=3000)
        db = _client[name]
        db[COL].create_index("id", unique=True)
        db[COL].create_index([("layer", 1), ("status", 1)])
        _db = db
        return _db


def is_enabled() -> bool:
    global _ENABLED
    if _ENABLED is not None:
        return _ENABLED
    try:
        _database().command("ping")
        _ENABLED = True
    except Exception as e:
        _log.warning("memory store disabled: %s", redact(str(e), max_len=80))
        _ENABLED = False
    return _ENABLED


def _norm(s: Any) -> str:
    try:
        from core.arabic_nlp import normalize_arabic
        t = normalize_arabic(str(s or ""))
    except Exception:
        t = str(s or "")
    return re.sub(r"\s+", " ", t).strip().lower()


def _tokens(s: str) -> set:
    return {w for w in _norm(s).split() if len(w) > 2}


def _approx_tokens(text: str) -> int:
    return max(1, len(str(text or "")) // 3)


def _cleanup_expired(col, now: float) -> None:
    """القاعدة 2ج: short غير المُرقّى خلال 30 يوماً يُحذف."""
    col.delete_many({"layer": "short", "created_at": {"$lt": now - SHORT_TTL_DAYS * 86400}})


def record(kind: str, content: str, *, session_id: Optional[str] = None,
           user: Optional[str] = None, topic: Optional[str] = None,
           admin: bool = False) -> Optional[Dict[str, Any]]:
    """القاعدتان 1+2: تسجيل عنصر مصنف + ترقية short→long عند استيفاء الشروط."""
    if not content or not is_enabled():
        return None
    try:
        now = time.time()
        col = _database()[COL]
        _cleanup_expired(col, now)
        ncontent = _norm(content)[:500]
        doc = col.find_one({"ncontent": ncontent, "layer": {"$in": ["short", "long"]},
                            "status": "active"})
        if doc:
            sessions = set(doc.get("seen_sessions") or [])
            if session_id:
                sessions.add(session_id)
            upd: Dict[str, Any] = {"last_seen_at": now, "seen_sessions": list(sessions)[:20]}
            if doc.get("layer") == "short":
                age_ok = (now - doc.get("created_at", now)) < SHORT_TTL_DAYS * 86400
                if age_ok and (len(sessions) >= PROMOTE_SESSIONS or (admin and kind == "correction")):
                    upd["layer"] = "long"
                    upd["promoted_at"] = now
            col.update_one({"id": doc["id"]}, {"$set": upd})
            doc.update(upd)
            doc.pop("_id", None)
            return doc
        doc = {
            "id": uuid.uuid4().hex[:12], "layer": "short", "kind": kind,
            "content": str(content)[:800], "ncontent": ncontent,
            "topic": (_norm(topic)[:80] or None) if topic else None,
            "session_id": session_id, "user": user,
            "created_at": now, "last_seen_at": now,
            "seen_sessions": [session_id] if session_id else [],
            "status": "active",
        }
        if admin and kind == "correction":
            doc["layer"] = "long"
            doc["promoted_at"] = now
        col.insert_one(dict(doc))
        return doc
    except Exception as e:
        _log.warning("memory record failed: %s", redact(str(e), max_len=80))
        return None


def knowledge_tokens_used() -> int:
    col = _database()[COL]
    return sum(_approx_tokens(d.get("content", ""))
               for d in col.find({"layer": "knowledge", "status": "active"}))


def propose_knowledge(memory_id: Optional[str] = None, *, content: Optional[str] = None,
                      topic: Optional[str] = None,
                      proposer: Optional[str] = None) -> Dict[str, Any]:
    """القاعدة 3: ترشيح Learning Candidate → مسودة + طلب اعتماد بشري."""
    if not is_enabled():
        return {"error": "memory_store_unavailable"}
    col = _database()[COL]
    if memory_id:
        doc = col.find_one({"id": memory_id})
        if not doc:
            return {"error": "memory_not_found"}
    else:
        doc = record("fact", content or "", topic=topic, user=proposer)
        if not doc:
            return {"error": "memory_store_unavailable"}
        col.update_one({"id": doc["id"]}, {"$set": {"layer": "long"}})
        doc["layer"] = "long"
    # القاعدة 5: فحص السقف قبل الترشيح
    if knowledge_tokens_used() + _approx_tokens(doc.get("content", "")) > KNOWLEDGE_TOKEN_CAP:
        return {"error": "knowledge_cap_full",
                "detail": "سقف المعرفة (2k tokens) ممتلئ — ادمج/أرشف قبل إضافة جديد"}
    from core import action_runtime
    draft = action_runtime.create_draft(
        action="memory_promote",
        payload={"memory_id": doc["id"],
                 "_echo": {"type": "ترقية للمعرفة",
                           "entity": (doc.get("topic") or doc.get("content", ""))[:70],
                           "amount": None}},
        proposer=proposer or "katrina",
    )
    approval = action_runtime.request_approval(draft_id=draft["id"],
                                               requester=proposer or "katrina")
    return {"draft": draft, "approval": approval,
            "memory": {"id": doc["id"], "content": doc.get("content")}}


def promote_to_knowledge(memory_id: str) -> Dict[str, Any]:
    """يُستدعى من commit() بعد الاعتماد البشري فقط (قاعدة 3) + كشف التلوث (4) + السقف (5)."""
    if not is_enabled():
        return {"error": "memory_store_unavailable"}
    col = _database()[COL]
    now = time.time()
    doc = col.find_one({"id": memory_id})
    if not doc:
        return {"error": "memory_not_found"}
    if knowledge_tokens_used() + _approx_tokens(doc.get("content", "")) > KNOWLEDGE_TOKEN_CAP:
        return {"error": "knowledge_cap_full",
                "detail": "سقف المعرفة ممتلئ — ادمج/أرشف قبل الترقية"}
    disputed: List[str] = []
    if doc.get("topic"):
        for old in col.find({"layer": "knowledge", "topic": doc["topic"],
                             "status": "active", "id": {"$ne": memory_id}}):
            if old.get("ncontent") != doc.get("ncontent"):
                col.update_one({"id": old["id"]},
                               {"$set": {"status": "disputed", "disputed_at": now}})
                disputed.append(old["id"])
    col.update_one({"id": memory_id},
                   {"$set": {"layer": "knowledge", "promoted_at": now, "status": "active"}})
    return {"promoted": memory_id, "disputed": disputed}


def retrieve(query: str, *, k: int = 5) -> str:
    """top-k انتقائي من short+long + كل المعرفة النشطة ضمن سقف 2k — نص جاهز للحقن."""
    if not is_enabled():
        return ""
    try:
        col = _database()[COL]
        qt = _tokens(query or "")
        scored = []
        for d in col.find({"layer": {"$in": ["short", "long"]}, "status": "active"}
                          ).sort("last_seen_at", -1).limit(200):
            ov = len(qt & _tokens(d.get("content", "")))
            if ov > 0:
                scored.append((ov + (1 if d.get("layer") == "long" else 0), d))
        scored.sort(key=lambda x: -x[0])
        lines = [f"  • [{d['layer']}/{d.get('kind')}] {d.get('content', '')[:200]}"
                 for _, d in scored[:k]]
        ktext, used = [], 0
        for d in col.find({"layer": "knowledge", "status": "active"}).sort("promoted_at", -1):
            t = _approx_tokens(d.get("content", ""))
            if used + t > KNOWLEDGE_TOKEN_CAP:
                break
            used += t
            ktext.append(f"  ★ {d.get('content', '')[:300]}")
        if not lines and not ktext:
            return ""
        out = "🧠 ذاكرة كاترينا (استرجاع انتقائي top-k):\n"
        if ktext:
            out += "المعرفة المعتمدة:\n" + "\n".join(ktext) + "\n"
        if lines:
            out += "خبرات ذات صلة:\n" + "\n".join(lines)
        return out
    except Exception as e:
        _log.warning("memory retrieve failed: %s", redact(str(e), max_len=80))
        return ""


def stats() -> Dict[str, Any]:
    if not is_enabled():
        return {"enabled": False}
    col = _database()[COL]
    return {
        "enabled": True,
        "short": col.count_documents({"layer": "short", "status": "active"}),
        "long": col.count_documents({"layer": "long", "status": "active"}),
        "knowledge": col.count_documents({"layer": "knowledge", "status": "active"}),
        "disputed": col.count_documents({"status": "disputed"}),
        "knowledge_tokens": knowledge_tokens_used(),
        "cap": KNOWLEDGE_TOKEN_CAP,
    }
