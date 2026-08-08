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


def _environment_suffix() -> str:
    env = str(os.environ.get("APP_ENV") or os.environ.get("ENVIRONMENT") or os.environ.get("NODE_ENV") or "production").strip().lower()
    if env in {"test", "testing", "pytest"}:
        return "_test"
    if env in {"stage", "staging"}:
        return "_staging"
    return ""


def _is_test_artifact(doc: Any) -> bool:
    if not isinstance(doc, dict):
        return False
    marker = f"{doc.get('source_classification') or ''} {doc.get('action') or ''} {doc.get('payload') or ''} {doc.get('reason') or ''}".upper()
    return any(token in marker for token in ("TEST_ARTIFACT", "TEST_ITER", "ITER280", "ITER331", "TESTQA"))


def _collection_name(base: str, doc: Any = None) -> str:
    if _is_test_artifact(doc):
        return f"{base}_test"
    return f"{base}{_environment_suffix()}"


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
        for suffix in {"", "_test", "_staging", _environment_suffix()}:
            db[f"{DRAFTS}{suffix}"].create_index("id", unique=True)
            db[f"{APPROVALS}{suffix}"].create_index("id", unique=True)
            db[f"{EXECUTIONS}{suffix}"].create_index("id", unique=True)
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
        _database()[_collection_name(coll, doc)].replace_one({"id": doc["id"]}, _clean(doc), upsert=True)
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
        _database()[_collection_name(AUDIT, row)].insert_one(dict(row))  # نسخة كي لا يُحقن _id في كائن الذاكرة
    except Exception as e:
        _log.warning("audit append failed: %s", redact(str(e), max_len=80))


def hydrate(state: Dict[str, Any]) -> None:
    """يعيد تحميل الحالة من MongoDB إلى الذاكرة عند الإقلاع."""
    if not is_enabled():
        return
    try:
        db = _database()
        drafts_coll = _collection_name(DRAFTS)
        approvals_coll = _collection_name(APPROVALS)
        executions_coll = _collection_name(EXECUTIONS)
        audit_coll = _collection_name(AUDIT)
        for d in db[drafts_coll].find({}, {"_id": 0}):
            state["drafts"][d["id"]] = d
        for a in db[approvals_coll].find({}, {"_id": 0}):
            state["approvals"][a["id"]] = a
        for e in db[executions_coll].find({}, {"_id": 0}):
            state["executions"][e["id"]] = e
        for row in db[audit_coll].find({}, {"_id": 0}).sort("ts", 1).limit(500):
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
        for base in (DRAFTS, APPROVALS, EXECUTIONS, AUDIT):
            db[_collection_name(base)].delete_many({})
    except Exception as e:
        _log.warning("clear_all failed: %s", redact(str(e), max_len=80))
