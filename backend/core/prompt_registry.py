"""📜 L14-D2 — سجل نسخ الـ system prompt مع rollback فوري (أمر علاج L14 بند 3).

النسخ في MongoDB (prompt_versions). النسخة المدمجة في الكود = v1-baseline دائماً.
`get_active()` ترجع (version, content|None) — None تعني استخدام الـ baseline.
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from core.log_utils import get_logger, redact

_log = get_logger("core.prompt_registry")

BASELINE_VERSION = "v1-baseline"

_client = None
_col = None
_cache: Dict[str, Any] = {"ts": 0.0, "doc": None}
_TTL = 20.0


def _collection():
    global _client, _col
    if _col is not None:
        return _col
    try:
        from pymongo import MongoClient
        _client = MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=3000)
        col = _client[os.environ["DB_NAME"]]["prompt_versions"]
        col.create_index("version", unique=True)
        _col = col
        return _col
    except Exception as e:
        _log.warning("prompt_registry mongo unavailable: %s", redact(str(e), max_len=120))
        return None


def _invalidate():
    _cache["ts"] = 0.0
    _cache["doc"] = None


def get_active() -> Tuple[str, Optional[str]]:
    now = time.time()
    if now - _cache["ts"] >= _TTL:
        col = _collection()
        _cache["doc"] = col.find_one({"active": True}, {"_id": 0}) if col is not None else None
        _cache["ts"] = now
    doc = _cache["doc"]
    if doc and doc.get("content"):
        return str(doc.get("version")), str(doc.get("content"))
    return BASELINE_VERSION, None


def register(version: str, content: str, activated_by: str, activate_now: bool = True) -> Dict[str, Any]:
    col = _collection()
    if col is None:
        return {"error": "registry_unavailable"}
    doc = {
        "version": version,
        "content": content,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": activated_by,
        "active": False,
    }
    col.update_one({"version": version}, {"$set": doc}, upsert=True)
    if activate_now:
        return activate(version, activated_by)
    return {"version": version, "active": False}


def activate(version: str, activated_by: str) -> Dict[str, Any]:
    """تفعيل نسخة (rollback = تفعيل نسخة أقدم؛ v1-baseline = تعطيل الكل)."""
    col = _collection()
    if col is None:
        return {"error": "registry_unavailable"}
    col.update_many({}, {"$set": {"active": False}})
    if version != BASELINE_VERSION:
        r = col.update_one(
            {"version": version},
            {"$set": {"active": True,
                      "activated_at": datetime.now(timezone.utc).isoformat(),
                      "activated_by": activated_by}},
        )
        if r.matched_count == 0:
            _invalidate()
            return {"error": "version_not_found", "version": version}
    _invalidate()
    _log.info("prompt version activated: %s by %s", version, activated_by)
    return {"version": version, "active": True}


def list_versions() -> List[Dict[str, Any]]:
    col = _collection()
    if col is None:
        return []
    rows = list(col.find({}, {"_id": 0, "content": 0}).sort("created_at", -1))
    return [{"version": BASELINE_VERSION, "active": not any(r.get("active") for r in rows),
             "note": "النسخة المدمجة في الكود (مرجع الـ rollback الدائم)"}] + rows
