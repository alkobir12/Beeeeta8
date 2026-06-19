"""
💾 core/runtime_store.py — حفظ دائم لحالة Action Runtime على MongoDB

يستبدل التخزين المؤقّت في الذاكرة (الذي يُمحى عند إعادة التشغيل) بطبقة دائمة:
  • assistant_drafts      — المسودات
  • assistant_approvals   — الموافقات
  • assistant_executions  — التنفيذات
  • assistant_audit_log   — سجل التدقيق

التصميم: كتابة مزدوجة (write-through). تبقى الحالة في الذاكرة للسرعة وتُكتب فورًا
إلى MongoDB عند كل تحوّل. عند الإقلاع يُعاد تحميل الحالة من MongoDB (hydrate).
لو كانت MongoDB غير متاحة، يتراجع النظام بصمت إلى الذاكرة فقط (لا ينكسر).
"""
from __future__ import annotations

import os
import threading
from typing import Any, Dict

from core.log_utils import get_logger, redact

_log = get_logger("runtime_store")

_client = None
_db = None
_lock = threading.Lock()
_ENABLED: bool | None = None

DRAFTS = "assistant_drafts"
APPROVALS = "assistant_approvals"
EXECUTIONS = "assistant_executions"
AUDIT = "assistant_audit_log"


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
        db[DRAFTS].create_index("id", unique=True)
        db[APPROVALS].create_index("id", unique=True)
        db[EXECUTIONS].create_index("id", unique=True)
        _db = db
        return _db


def is_enabled() -> bool:
    global _ENABLED
    if _ENABLED is not None:
        return _ENABLED
    try:
        _database().command("ping")
        _ENABLED = True
        _log.info("runtime persistence: ENABLED (MongoDB)")
    except Exception as e:
        _ENABLED = False
        _log.warning("runtime persistence DISABLED (in-memory only): %s", redact(str(e), max_len=80))
    return _ENABLED


def _clean(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in doc.items() if k != "_id"}


def _upsert(coll: str, doc: Any) -> None:
    if not is_enabled() or not isinstance(doc, dict) or "id" not in doc:
        return
    try:
        _database()[coll].replace_one({"id": doc["id"]}, _clean(doc), upsert=True)
    except Exception as e:
        _log.warning("%s upsert failed: %s", coll, redact(str(e), max_len=80))


def save_draft(state: Dict[str, Any], draft_id: str) -> None:
    _upsert(DRAFTS, state["drafts"].get(draft_id))


def save_approval(state: Dict[str, Any], approval_id: str) -> None:
    _upsert(APPROVALS, state["approvals"].get(approval_id))


def save_execution(state: Dict[str, Any], execution_id: str) -> None:
    _upsert(EXECUTIONS, state["executions"].get(execution_id))


def append_audit(row: Dict[str, Any]) -> None:
    if not is_enabled():
        return
    try:
        _database()[AUDIT].insert_one(dict(row))  # نسخة كي لا يُحقن _id في كائن الذاكرة
    except Exception as e:
        _log.warning("audit append failed: %s", redact(str(e), max_len=80))


def hydrate(state: Dict[str, Any]) -> None:
    """يعيد تحميل الحالة من MongoDB إلى الذاكرة عند الإقلاع."""
    if not is_enabled():
        return
    try:
        db = _database()
        for d in db[DRAFTS].find({}, {"_id": 0}):
            state["drafts"][d["id"]] = d
        for a in db[APPROVALS].find({}, {"_id": 0}):
            state["approvals"][a["id"]] = a
        for e in db[EXECUTIONS].find({}, {"_id": 0}):
            state["executions"][e["id"]] = e
        for row in db[AUDIT].find({}, {"_id": 0}).sort("ts", 1).limit(500):
            state["audit"].append(row)
        _log.info("runtime hydrated: %d drafts, %d approvals, %d executions",
                  len(state["drafts"]), len(state["approvals"]), len(state["executions"]))
    except Exception as e:
        _log.warning("hydrate failed: %s", redact(str(e), max_len=100))


def clear_all() -> None:  # pragma: no cover — للاختبارات فقط
    if not is_enabled():
        return
    try:
        db = _database()
        for c in (DRAFTS, APPROVALS, EXECUTIONS, AUDIT):
            db[c].delete_many({})
    except Exception as e:
        _log.warning("clear_all failed: %s", redact(str(e), max_len=80))
