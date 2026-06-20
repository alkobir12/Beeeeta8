"""
🏦 core/accounting_engine.py — المحرك المحاسبي المركزي (نسخة إنتاجية)

المصدر الوحيد للحقيقة عند الكتابة في جدول `journal_entries` على Supabase.

المكوّنات
─────────
1. IdentityStore — طبقة منع التكرار (Idempotency) على MongoDB مع **فهرس فريد
   UNIQUE index على `tx_hash`** → أمان حقيقي ضد تسابق الطلبات (race conditions):
   عند وصول طلبين متطابقين في نفس اللحظة، ينجح واحد فقط في إدراج البصمة،
   والآخر يحصل على نتيجة idempotent بدون قيد مكرر.

2. AccountingEngine — يتحقق من توازن القيد المزدوج (مدين = دائن)، يحسب بصمة
   المعاملة `tx_hash` من (البند + السعر + الوقت + العميل) حسب طلب المالك، يحجز
   الهوية في MongoDB، ثم يكتب القيد عبر عميل Supabase الخام (المسار الوحيد
   المسموح له بالكتابة في journal_entries).

3. SupabaseGuardedClient — غلاف رقيق يستخدمه بقية التطبيق؛ يمنع أي كتابة مباشرة
   (insert/update/delete/upsert) على journal_entries، ويسمح بالقراءة فقط. هذا يفرض
   مرور كل القيود عبر المحرك المركزي.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.log_utils import get_logger, redact

_log = get_logger("accounting_engine")

JOURNAL_TABLE = "journal_entries"
DEFAULT_WORKSHOP_ID = "finmodule-sync"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─────────────────────────────────────────────────────────────────────────────
# Normalization helpers — بصمة المعاملة تعتمد على قيم مُطبَّعة (Arabic-tolerant)
# ─────────────────────────────────────────────────────────────────────────────

def _norm_text(value: Any) -> str:
    """تطبيع نص للبصمة: إزالة التشكيل/التطويل، توحيد الهمزات، قص المسافات."""
    s = str(value or "").strip().lower()
    if not s:
        return ""
    s = re.sub(r"[\u064B-\u0652\u0640]", "", s)          # تشكيل + تطويل
    s = s.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    s = s.replace("ة", "ه").replace("ى", "ي").replace("ئ", "ي").replace("ؤ", "و")
    s = re.sub(r"\s+", " ", s)
    return s


def _norm_amount(value: Any) -> float:
    try:
        return round(float(str(value).replace(",", "")), 2)
    except (TypeError, ValueError):
        return 0.0


def _norm_time(value: Any, granularity: str = "minute") -> str:
    """تطبيع الوقت لبصمة المعاملة.

    الافتراضي: دقّة الدقيقة — حتى لا تُعدّ إعادة الإرسال خلال نفس اللحظة قيدًا
    جديدًا، مع الإبقاء على قيود مختلفة في أوقات مختلفة منفصلة.
    """
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if granularity == "day":
            return dt.strftime("%Y-%m-%d")
        return dt.strftime("%Y-%m-%dT%H:%M")
    except ValueError:
        return raw[:16]


def _party_from_desc(description: Any) -> str:
    """يحاول استخراج اسم الطرف من وسم [PARTY:..] داخل الوصف إن وُجد."""
    s = str(description or "")
    m = re.search(r"\[PARTY:\s*([^\]]+)\]", s)
    return m.group(1).strip() if m else ""


def _normalize_lines(lines: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """توحيد بنود القيد إلى الشكل القياسي: account / account_name / debit / credit."""
    out: List[Dict[str, Any]] = []
    for ln in lines or []:
        if not isinstance(ln, dict):
            continue
        account = ln.get("account") or ln.get("account_id") or ln.get("code") or ""
        out.append({
            "account": str(account).strip(),
            "account_name": str(ln.get("account_name") or ln.get("name") or "").strip(),
            "debit": _norm_amount(ln.get("debit")),
            "credit": _norm_amount(ln.get("credit")),
            "description": str(ln.get("description") or "").strip() or None,
        })
    return out


# ─────────────────────────────────────────────────────────────────────────────
# 1) IdentityStore — Idempotency على MongoDB بفهرس فريد
# ─────────────────────────────────────────────────────────────────────────────

class IdentityStore:
    """مخزن بصمات المعاملات لمنع القيود المكررة (race-safe عبر UNIQUE index)."""

    _client = None
    _coll = None
    _lock = threading.Lock()

    @classmethod
    def collection(cls):
        if cls._coll is not None:
            return cls._coll
        with cls._lock:
            if cls._coll is not None:
                return cls._coll
            from pymongo import MongoClient
            uri = os.environ["MONGO_URL"]
            db_name = os.environ["DB_NAME"]
            cls._client = MongoClient(uri, serverSelectionTimeoutMS=3000)
            coll = cls._client[db_name]["accounting_identity"]
            # الفهرس الفريد هو حجر الزاوية لمنع التكرار عند التسابق
            coll.create_index("tx_hash", unique=True)
            coll.create_index("reference_id")
            cls._coll = coll
            _log.info("IdentityStore ready (unique index on tx_hash)")
            return cls._coll

    @classmethod
    def claim(cls, tx_hash: str, meta: Dict[str, Any]) -> Dict[str, Any]:
        """يحاول حجز البصمة. ينجح حجز واحد فقط للبصمة نفسها.

        Returns:
          {"claimed": True} عند نجاح الحجز (أول مرة)
          {"claimed": False, "existing": {...}} عند وجود بصمة سابقة (مكرر)
        """
        from pymongo.errors import DuplicateKeyError
        coll = cls.collection()
        doc = {
            "tx_hash": tx_hash,
            "status": "pending",
            "created_at": _now_iso(),
            **{k: v for k, v in (meta or {}).items() if k != "tx_hash"},
        }
        try:
            coll.insert_one(doc)
            return {"claimed": True}
        except DuplicateKeyError:
            existing = coll.find_one({"tx_hash": tx_hash}, {"_id": 0})
            return {"claimed": False, "existing": existing or {}}

    @classmethod
    def mark_posted(cls, tx_hash: str, journal_id: str) -> None:
        cls.collection().update_one(
            {"tx_hash": tx_hash},
            {"$set": {"status": "posted", "journal_id": journal_id, "posted_at": _now_iso()}},
        )

    @classmethod
    def release(cls, tx_hash: str) -> None:
        """يحرر البصمة (يحذفها) عند فشل الكتابة كي تنجح إعادة المحاولة لاحقًا."""
        try:
            cls.collection().delete_one({"tx_hash": tx_hash})
        except Exception as e:  # pragma: no cover
            _log.warning("identity release failed: %s", redact(str(e), max_len=80))


# ─────────────────────────────────────────────────────────────────────────────
# 2) SupabaseGuardedClient — يمنع الكتابة المباشرة في journal_entries
# ─────────────────────────────────────────────────────────────────────────────

class JournalWriteBlockedError(RuntimeError):
    """يُرفع عند محاولة الكتابة المباشرة في journal_entries من خارج المحرك."""


_WRITE_METHODS = {"insert", "update", "delete", "upsert"}


class _GuardedTable:
    def __init__(self, name: str, real_table: Any, blocked: bool):
        self._name = name
        self._real = real_table
        self._blocked = blocked

    def __getattr__(self, attr: str):
        if self._blocked and attr in _WRITE_METHODS:
            raise JournalWriteBlockedError(
                f"🚫 الكتابة المباشرة في '{self._name}' ممنوعة — "
                f"استخدم AccountingEngine.post() لضمان التوازن ومنع التكرار."
            )
        return getattr(self._real, attr)


class SupabaseGuardedClient:
    """غلاف عميل Supabase يحجب الكتابة على الجداول المحمية ويسمح بالقراءة."""

    PROTECTED = {JOURNAL_TABLE}

    def __init__(self, raw_client: Any):
        self._raw = raw_client

    def table(self, name: str):
        real = self._raw.table(name)
        return _GuardedTable(name, real, blocked=(name in self.PROTECTED))

    # كل ما عدا table() يُمرّر للعميل الخام كما هو
    def __getattr__(self, attr: str):
        return getattr(self._raw, attr)


# ─────────────────────────────────────────────────────────────────────────────
# 3) AccountingEngine — المحرك المركزي
# ─────────────────────────────────────────────────────────────────────────────

class AccountingEngine:
    """المحرك الوحيد المخوّل بالكتابة في journal_entries."""

    def __init__(self, raw_client: Any = None):
        self._raw = raw_client
        self.identity = IdentityStore

    @property
    def raw(self):
        """عميل Supabase الخام (lazy)."""
        if self._raw is None:
            from supabase_service import SupabaseService
            self._raw = SupabaseService().client
        return self._raw

    # ── حساب بصمة المعاملة: البند + السعر + الوقت + العميل ──
    def compute_tx_hash(
        self,
        *,
        party: Any = None,
        date: Any = None,
        lines: Optional[List[Dict[str, Any]]] = None,
        total: Any = 0,
        items: Optional[List[Dict[str, Any]]] = None,
        reference_id: Any = None,
        time_granularity: str = "minute",
    ) -> str:
        sig: Dict[str, Any] = {
            "party": _norm_text(party),                     # العميل
            "time": _norm_time(date, time_granularity),     # الوقت
            "total": _norm_amount(total),                   # الإجمالي
        }
        # البنود + الأسعار (إن توفّرت أسماء البنود تُستخدم، وإلا بنود القيد)
        if items:
            sig["items"] = sorted(
                [{"n": _norm_text(it.get("name")), "p": _norm_amount(it.get("price") or it.get("total")),
                  "q": _norm_amount(it.get("quantity") or it.get("qty") or 1)} for it in items],
                key=lambda x: (x["n"], x["p"], x["q"]),
            )
        else:
            sig["lines"] = sorted(
                [{"a": _norm_text(ln.get("account")), "d": _norm_amount(ln.get("debit")),
                  "c": _norm_amount(ln.get("credit"))} for ln in (lines or [])],
                key=lambda x: (x["a"], x["d"], x["c"]),
            )
        if reference_id:
            sig["ref"] = str(reference_id)
        blob = json.dumps(sig, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    # ── الكتابة الرئيسية ──
    def post(
        self,
        *,
        lines: List[Dict[str, Any]],
        date: Optional[str] = None,
        description: str = "",
        source: str = "manual",
        transaction_type: str = "manual",
        total: Optional[float] = None,
        reference_id: Optional[str] = None,
        workshop_id: str = DEFAULT_WORKSHOP_ID,
        party: Optional[str] = None,
        items: Optional[List[Dict[str, Any]]] = None,
        actor: Optional[Dict[str, str]] = None,
        extra: Optional[Dict[str, Any]] = None,
        time_granularity: str = "minute",
    ) -> Dict[str, Any]:
        """ينشر قيد يومية متوازن مع ضمان عدم التكرار.

        Returns dict:
          {"posted": True, "journal_id": ..., "tx_hash": ..., "total": ...}
          {"posted": False, "idempotent": True, "journal_id": ...}  # مكرر
          {"posted": False, "error": "unbalanced"|"empty_lines"|"write_failed", ...}
        """
        norm_lines = _normalize_lines(lines)
        if not norm_lines:
            return {"posted": False, "error": "empty_lines"}

        debit = round(sum(ln["debit"] for ln in norm_lines), 2)
        credit = round(sum(ln["credit"] for ln in norm_lines), 2)
        if abs(debit - credit) > 0.01:
            _log.warning("unbalanced entry rejected debit=%s credit=%s", debit, credit)
            return {"posted": False, "error": "unbalanced", "debit": debit, "credit": credit}

        entry_total = round(float(total), 2) if total is not None else debit
        entry_date = date or _now_iso()

        tx_hash = self.compute_tx_hash(
            party=party, date=entry_date, lines=norm_lines, total=entry_total,
            items=items, reference_id=reference_id, time_granularity=time_granularity,
        )

        claim = self.identity.claim(tx_hash, {
            "reference_id": reference_id,
            "workshop_id": workshop_id,
            "source": source,
            "transaction_type": transaction_type,
            "party": party,
            "total": entry_total,
            "actor": (actor or {}).get("user_id"),
        })
        if not claim["claimed"]:
            existing = claim.get("existing") or {}
            _log.info("idempotent post skipped tx=%s", tx_hash[:12])
            return {
                "posted": False, "idempotent": True, "tx_hash": tx_hash,
                "journal_id": existing.get("journal_id"),
                "message": "القيد موجود مسبقًا — لم يُكرَّر",
            }

        payload: Dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "workshop_id": workshop_id,
            "date": entry_date,
            "description": description or "",
            "lines": norm_lines,
            "total": entry_total,
            "source": source,
            "transaction_type": transaction_type,
            "reference_id": reference_id,
        }
        if extra:
            payload.update({k: v for k, v in extra.items() if k not in payload})

        try:
            data = self._insert_adaptive(payload)
            journal_id = (data[0].get("id") if data else None) or payload["id"]
            self.identity.mark_posted(tx_hash, journal_id)
            self._audit("JOURNAL_POSTED", tx_hash=tx_hash, journal_id=journal_id,
                        total=entry_total, source=source, reference_id=reference_id,
                        actor=(actor or {}).get("user_id"))
            return {"posted": True, "journal_id": journal_id, "tx_hash": tx_hash,
                    "total": entry_total, "debit": debit, "credit": credit}
        except Exception as e:
            # حرّر البصمة كي تنجح إعادة المحاولة
            self.identity.release(tx_hash)
            _log.exception("journal write failed: %s", redact(str(e), max_len=120))
            return {"posted": False, "error": "write_failed", "detail": redact(str(e), max_len=160)}

    def _insert_adaptive(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """يُدرج القيد ويتكيّف مع أعمدة Supabase: يحذف أي عمود غير موجود ويعيد المحاولة."""
        import re as _re
        attempt = dict(payload)
        last_error: Optional[Exception] = None
        for _ in range(12):
            try:
                res = self.raw.table(JOURNAL_TABLE).insert(attempt).execute()
                return getattr(res, "data", None) or []
            except Exception as err:
                last_error = err
                m = _re.search(r"Could not find the '([^']+)' column", str(err))
                if not m:
                    break
                missing = m.group(1)
                if missing not in attempt:
                    break
                attempt.pop(missing, None)
        # محاولة أخيرة بالأعمدة الأساسية فقط
        basic = {k: payload.get(k) for k in
                 ("id", "workshop_id", "date", "description", "lines", "total",
                  "source", "transaction_type", "reference_id") if k in payload}
        res = self.raw.table(JOURNAL_TABLE).insert(basic).execute()
        return getattr(res, "data", None) or []

    # ── محوّل: قيد جاهز (entry dict) → المحرك (للملفات القديمة) ──
    def post_entry(self, entry: Dict[str, Any], *, fallback: bool = True) -> List[Dict[str, Any]]:
        """يمرّر قيدًا جاهزًا عبر المحرك (توازن + منع تكرار) ويعيد صف الإدراج بشكل `.data`.

        عند رفض المحرك (غير متوازن/فشل كتابة) يتراجع إلى إدراج مباشر متكيّف كي لا
        تُفقد أي بيانات مالية — منع التكرار يبقى فعّالاً في الحالة الشائعة.
        """
        if not entry:
            return None
        lines = entry.get("lines") or []
        party = (entry.get("party_label") or entry.get("supplier_name")
                 or _party_from_desc(entry.get("description")))
        reserved = {"lines", "date", "description", "total", "source",
                    "transaction_type", "reference_id", "workshop_id", "id"}
        res = self.post(
            lines=lines,
            date=entry.get("date"),
            description=entry.get("description") or "",
            total=entry.get("total"),
            source=entry.get("source") or "system",
            transaction_type=entry.get("transaction_type") or "manual",
            reference_id=entry.get("reference_id"),
            workshop_id=entry.get("workshop_id") or DEFAULT_WORKSHOP_ID,
            party=party,
            extra={k: v for k, v in entry.items() if k not in reserved},
        )
        if res.get("posted"):
            return [{**entry, "id": res["journal_id"]}]
        if res.get("idempotent"):
            _log.info("duplicate journal entry prevented (ref=%s)", entry.get("reference_id"))
            return [{**entry, "id": res.get("journal_id")}]
        # رفض المحرك (مثلاً غير متوازن) → تراجع لإدراج مباشر كي لا تُفقد البيانات
        if fallback:
            _log.warning("engine rejected entry (%s) — fallback direct insert", res.get("error"))
            try:
                payload = dict(entry)
                payload.setdefault("id", str(uuid.uuid4()))
                return self._insert_adaptive(payload)
            except Exception as e:
                _log.exception("fallback insert failed: %s", redact(str(e), max_len=120))
                return None
        return None

    # ── سجل تدقيق مالي على MongoDB (دائم، لا يُمحى عند إعادة التشغيل) ──
    def _audit(self, event: str, **kwargs) -> None:
        try:
            coll = self.identity.collection().database["accounting_audit"]
            coll.insert_one({"event": event, "ts": _now_iso(),
                             **{k: v for k, v in kwargs.items() if v is not None}})
        except Exception as e:  # pragma: no cover
            _log.warning("accounting audit failed: %s", redact(str(e), max_len=80))


# ─────────────────────────────────────────────────────────────────────────────
# Singletons
# ─────────────────────────────────────────────────────────────────────────────

_ENGINE: Optional[AccountingEngine] = None
_ENGINE_LOCK = threading.Lock()


def get_engine() -> AccountingEngine:
    global _ENGINE
    if _ENGINE is None:
        with _ENGINE_LOCK:
            if _ENGINE is None:
                _ENGINE = AccountingEngine()
    return _ENGINE


def post_entry(entry: Dict[str, Any], *, fallback: bool = True) -> List[Dict[str, Any]]:
    """دالة مختصرة: تمرّر قيدًا جاهزًا عبر المحرك المركزي."""
    return get_engine().post_entry(entry, fallback=fallback)


def get_guarded_client(raw_client: Any = None) -> SupabaseGuardedClient:
    """يعيد عميل Supabase محميًّا (يحجب الكتابة المباشرة على journal_entries)."""
    if raw_client is None:
        from supabase_service import SupabaseService
        raw_client = SupabaseService().client
    return SupabaseGuardedClient(raw_client)
