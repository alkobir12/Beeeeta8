"""
🛡️ Accounting Firewall Engine — محرك التحليل والكشف المالي الذكي

يكشف:
  • القيود غير المتوازنة
  • تكرار العمليات بنفس المعطيات (المبلغ + الوصف + الطرف)
  • تكرار بنود داخل ملف المركبة
  • عدم تناسق المبالغ (visit total ≠ operation total)
  • شذوذ المصاريف (ارتفاع غير طبيعي)
  • القيود اليتيمة (بدون عملية مرتبطة)
  • العملاء/الموردون بأرصدة سالبة
  • الفواتير المتأخرة
  • تدفق نقدي سلبي

يحسب:
  • Financial Health Score (0-100) من 8 معايير

يقترح:
  • Auto-fix للقيود المعطوبة
  • إجراءات تصحيحية
"""

from __future__ import annotations
import os
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple

# Module-level TTL cache to avoid repeated 30s scans across endpoints/requests
_ANALYSIS_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_CACHE_TTL_SECONDS = 30  # كل 30 ثانية يُعاد التحليل


def invalidate_firewall_cache(workshop_id: Optional[str] = None) -> None:
    """يُبطل الكاش لورشة معينة أو كلها."""
    if workshop_id:
        _ANALYSIS_CACHE.pop(f"ws:{workshop_id}", None)
    else:
        _ANALYSIS_CACHE.clear()

# ------------------------- مساعدات -------------------------

def _to_decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value if value is not None else 0))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


def _round_2(v: Any) -> float:
    return float(_to_decimal(v).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _parse_iso(d: Any) -> Optional[datetime]:
    if not d:
        return None
    s = str(d)
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        try:
            return datetime.strptime(s[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except Exception:
            return None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _alert_id(prefix: str, *parts) -> str:
    """ID ثابت قابل للاسترجاع لتجاهل/إصلاح/تعليم.
    SHA-256 هنا بصمة غير أمنية (fingerprint) وليست تخزين كلمة مرور."""
    import hashlib
    raw = f"{prefix}:{'|'.join(str(p) for p in parts)}"
    return f"{prefix}-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:12]}"


# حسابات الذمم — نفس أكواد routes_finance (مصدر موحّد)
AR_ACCOUNT_CODES = {"005", "1103", "113"}
AP_ACCOUNT_CODES = {"2101", "211"}

# أنواع العمليات المالية التي يجب أن يقابلها قيد محاسبي
FINANCIAL_OP_TYPES = {
    "sale", "service", "instant_sale", "purchase", "expense", "cash_expense",
    "salary", "collect_customer", "receipt_voucher", "payment_order", "pay_supplier",
}

# طرق الدفع الآجلة — تخص الذمم ولا تدخل في التدفق النقدي
CREDIT_METHODS = {"credit", "deferred", "اجل", "آجل", "ذمة", "ذمم"}
# حالات سداد تعني أن النقد لم يُقبض بعد
UNPAID_STATUSES = {"unpaid", "credit", "partial", "deferred", "pending"}


def _account_type(code: Any) -> str:
    """نوع الحساب — من جدول accounts الحي أولاً (SSOT)، ثم fallback بالنطاقات الحالية."""
    code_s = str(code or "").strip()
    try:
        from core.chart_resolver import type_of
        t = type_of(code_s)
        if t in ("revenue", "expense"):
            return t
        if t:
            return "other"
    except Exception:
        pass
    try:
        n = int(code_s)
    except (ValueError, TypeError):
        return "other"
    if n == 41 or 24 <= n <= 28 or 4000 <= n <= 4999:
        return "revenue"
    if n == 167 or 29 <= n <= 48 or 5000 <= n <= 6999:
        return "expense"
    return "other"


def _line_code(ln: Dict[str, Any]) -> str:
    return str(ln.get("account") or ln.get("account_code") or ln.get("code") or "").strip()


# ------------------------- Supabase Helpers -------------------------

def _supa():
    provider = os.environ.get("DB_PROVIDER", "mongo").lower()
    if provider != "supabase":
        return None
    try:
        from supabase_service import SupabaseService
        return SupabaseService()
    except Exception as e:
        print(f"[FirewallEngine] Supabase init failed: {e}")
        return None


def _fetch_table(supa, table: str, *, workshop_id: Optional[str] = None, limit: int = 5000, order_field: str = "created_at") -> List[Dict[str, Any]]:
    if not supa:
        return []
    try:
        q = supa.client.table(table).select("*")
        if workshop_id and table == "journal_entries":
            q = q.eq("workshop_id", workshop_id)
        res = q.order(order_field, desc=True).limit(limit).execute()
        return res.data or []
    except Exception as e:
        print(f"[FirewallEngine] failed to read {table}: {e}")
        return []


# ------------------------- المحرك -------------------------

# Severity levels
SEV_CRITICAL = "critical"
SEV_HIGH = "high"
SEV_MEDIUM = "medium"
SEV_LOW = "low"
SEV_INFO = "info"

# Auto-fix capability flags
FIX_AUTO = "auto"          # المحرك يستطيع إنشاء قيد تصحيحي تلقائي
FIX_GUIDED = "guided"      # نقترح خطوات، المستخدم ينفذها
FIX_NONE = "none"          # لا يوجد إصلاح آلي


class FirewallEngine:
    """محرك تحليل وحماية محاسبية حي."""

    def __init__(self, workshop_id: Optional[str] = None):
        self.workshop_id = workshop_id
        self.supa = _supa()
        self._cache: Dict[str, Any] = {}
        self._dismissed_ids = self._load_dismissed()

    # ---------- تحميل الكاش ----------
    def _load_dismissed(self) -> set:
        """تحميل التنبيهات المُتجاهلة من MongoDB (sync لتجنب event loop conflicts)."""
        try:
            from pymongo import MongoClient
            mongo_uri = os.getenv("MONGO_URL")
            db_name = os.getenv("DB_NAME")
            if not mongo_uri or not db_name:
                return set()
            client = MongoClient(mongo_uri, serverSelectionTimeoutMS=2000)
            db_local = client[db_name]
            now_iso = _now().isoformat()
            docs = list(db_local["firewall_dismissed_alerts"].find(
                {"workshop_id": self.workshop_id or "finmodule-sync"},
                {"_id": 0, "alert_id": 1, "expires_at": 1},
            ).limit(2000))
            client.close()
            return {d["alert_id"] for d in docs if not d.get("expires_at") or d["expires_at"] > now_iso}
        except Exception as e:
            print(f"[FirewallEngine] load_dismissed err: {e}")
            return set()

    # ---------- جلب البيانات الخام ----------
    def _journals(self) -> List[Dict[str, Any]]:
        if "journals" not in self._cache:
            self._cache["journals"] = _fetch_table(self.supa, "journal_entries", workshop_id=self.workshop_id)
        return self._cache["journals"]

    def _operations(self) -> List[Dict[str, Any]]:
        if "operations" not in self._cache:
            self._cache["operations"] = _fetch_table(self.supa, "operations")
        return self._cache["operations"]

    def _visits(self) -> List[Dict[str, Any]]:
        if "visits" not in self._cache:
            self._cache["visits"] = _fetch_table(self.supa, "vehicle_visits")
        return self._cache["visits"]

    def _accounts(self) -> List[Dict[str, Any]]:
        if "accounts" not in self._cache:
            try:
                self._cache["accounts"] = self.supa.client.table("accounts").select("*").execute().data or [] if self.supa else []
            except Exception:
                self._cache["accounts"] = []
        return self._cache["accounts"]

    # =========================================================
    # 1️⃣ Detect Trial Balance / Unbalanced Entries
    # =========================================================
    def detect_trial_balance_issues(self) -> List[Dict[str, Any]]:
        alerts = []
        for entry in self._journals():
            lines = entry.get("lines") or []
            if not isinstance(lines, list):
                continue
            total_d = sum(_to_decimal(ln.get("debit") if isinstance(ln, dict) else 0) for ln in lines)
            total_c = sum(_to_decimal(ln.get("credit") if isinstance(ln, dict) else 0) for ln in lines)
            drift = (total_d - total_c).copy_abs()
            if drift > Decimal("0.009"):
                aid = _alert_id("unbal", entry.get("id"))
                if aid in self._dismissed_ids:
                    continue
                alerts.append({
                    "id": aid,
                    "category": "balance_integrity",
                    "severity": SEV_CRITICAL,
                    "title": "قيد غير متوازن في قاعدة البيانات",
                    "description": f"الفرق بين المدين والدائن = {_round_2(drift)} ر.س",
                    "root_cause": "تم تجاوز جدار الحماية أو حُفظ القيد قبل تفعيله. الـ ledger يعتمد عليه التوازن الكامل.",
                    "financial_impact": _round_2(drift),
                    "affected_accounts": [str(ln.get("account_name") or ln.get("account") or "?") for ln in lines if isinstance(ln, dict)],
                    "related_entries": [entry.get("id")],
                    "evidence": {
                        "journal_id": entry.get("id"),
                        "date": entry.get("date"),
                        "description": entry.get("description"),
                        "debit_total": _round_2(total_d),
                        "credit_total": _round_2(total_c),
                        "drift": _round_2(drift),
                    },
                    "auto_fix": FIX_AUTO,
                    "auto_fix_preview": {
                        "type": "balancing_adjustment",
                        "side": "credit" if total_d > total_c else "debit",
                        "amount": _round_2(drift),
                        "account_code": "9999",
                        "account_name": "تسوية جدار حماية",
                    },
                    "created_at": _now().isoformat(),
                })
        return alerts

    # =========================================================
    # 2️⃣ Detect Duplicate Operations (نفس المعطيات + المبلغ + الوقت)
    # =========================================================
    def detect_duplicate_operations(self) -> List[Dict[str, Any]]:
        """يكشف أي عمليتين بنفس (المبلغ، النوع، طرف، مركبة) خلال نافذة زمنية واسعة."""
        alerts = []
        ops = self._operations()
        # نجمّع باستخدام مفتاح (type, total, partner_id|partner_name, vehicle_id)
        groups: Dict[Tuple, List[Dict[str, Any]]] = defaultdict(list)
        for op in ops:
            key = (
                str(op.get("type") or "").lower(),
                _round_2(op.get("total") or 0),
                str(op.get("partner_id") or op.get("partner_name") or "").strip().lower()[:40],
                str(op.get("vehicle_id") or "").strip(),
            )
            if not key[1] or key[1] == 0:
                continue
            groups[key].append(op)

        for key, items in groups.items():
            if len(items) < 2:
                continue
            # رتّب حسب التاريخ
            items_sorted = sorted(items, key=lambda x: x.get("created_at") or x.get("date") or "")
            # ابني سلسلة عمليات مشبوهة
            base = items_sorted[0]
            base_dt = _parse_iso(base.get("created_at"))
            for dup in items_sorted[1:]:
                aid = _alert_id("duplicate-op", base.get("id"), dup.get("id"))
                if aid in self._dismissed_ids:
                    continue
                dup_dt = _parse_iso(dup.get("created_at"))
                delta = "—"
                if base_dt and dup_dt:
                    diff = dup_dt - base_dt
                    if diff.days >= 1:
                        delta = f"{diff.days} يوماً"
                    else:
                        hrs = diff.seconds // 3600
                        delta = f"{hrs} ساعة" if hrs else f"{diff.seconds // 60} دقيقة"
                # خطورة: قريبة زمنياً = critical، بعيدة = medium
                near = (base_dt and dup_dt and (dup_dt - base_dt).days <= 1)
                alerts.append({
                    "id": aid,
                    "category": "duplicate_detection",
                    "severity": SEV_CRITICAL if near else SEV_HIGH,
                    "title": f"عملية مكررة محتملة: {key[0]} بمبلغ {key[1]} ر.س",
                    "description": f"تم إنشاء عمليتين بنفس النوع/المبلغ/الطرف. الفارق الزمني: {delta}.",
                    "root_cause": "إدخال مزدوج محتمل أو إعادة إرسال نموذج. تحقق من النية قبل الحذف.",
                    "financial_impact": key[1],
                    "affected_accounts": [str(base.get("partner_name") or "?")],
                    "related_entries": [base.get("id"), dup.get("id")],
                    "evidence": {
                        "original_id": base.get("id"),
                        "duplicate_id": dup.get("id"),
                        "type": key[0],
                        "total": key[1],
                        "partner_name": base.get("partner_name"),
                        "partner_id": base.get("partner_id"),
                        "vehicle_id": base.get("vehicle_id"),
                        "original_date": base.get("created_at") or base.get("date"),
                        "duplicate_date": dup.get("created_at") or dup.get("date"),
                        "delta": delta,
                    },
                    "auto_fix": FIX_GUIDED,
                    "auto_fix_preview": {
                        "type": "soft_delete",
                        "target_id": dup.get("id"),
                        "message": "احذف العملية المكررة بعد التأكد من أنها ليست عملية شرعية متشابهة.",
                    },
                    "created_at": _now().isoformat(),
                })
        return alerts

    # =========================================================
    # 3️⃣ Detect Duplicate Items inside one Visit
    # =========================================================
    def detect_duplicate_visit_items(self) -> List[Dict[str, Any]]:
        """يكشف بنوداً متكررة داخل نفس الزيارة بنفس الاسم والسعر."""
        alerts = []
        for visit in self._visits():
            notes_raw = visit.get("notes") or "{}"
            try:
                import json
                meta = json.loads(notes_raw) if isinstance(notes_raw, str) else (notes_raw or {})
            except Exception:
                continue
            items = meta.get("items") if isinstance(meta, dict) else []
            if not isinstance(items, list) or len(items) < 2:
                continue

            seen: Dict[Tuple, List[Dict[str, Any]]] = defaultdict(list)
            for it in items:
                if not isinstance(it, dict):
                    continue
                name = str(it.get("name") or "").strip()
                if not name:
                    continue
                key = (name.lower(), _round_2(it.get("price") or 0))
                seen[key].append(it)

            for (name_l, price), occurrences in seen.items():
                if len(occurrences) < 2:
                    continue
                aid = _alert_id("dup-item", visit.get("id"), name_l, price)
                if aid in self._dismissed_ids:
                    continue
                total_dup_amount = _round_2(sum(_to_decimal(it.get("total") or 0) for it in occurrences[1:]))
                alerts.append({
                    "id": aid,
                    "category": "duplicate_detection",
                    "severity": SEV_HIGH,
                    "title": f"بند مكرر داخل الزيارة: «{occurrences[0].get('name')}»",
                    "description": f"البند مُدرَج {len(occurrences)} مرات بنفس السعر. التأثير المحتمل: {total_dup_amount} ر.س.",
                    "root_cause": "إدخال يدوي مكرر للبند نفسه. قد يضخّم الفاتورة بشكل خاطئ.",
                    "financial_impact": total_dup_amount,
                    "affected_accounts": ["إيرادات خدمات"],
                    "related_entries": [visit.get("id")],
                    "evidence": {
                        "visit_id": visit.get("id"),
                        "vehicle_id": visit.get("vehicle_id"),
                        "item_name": occurrences[0].get("name"),
                        "price": price,
                        "occurrences": len(occurrences),
                        "items_snapshot": occurrences[:5],
                    },
                    "auto_fix": FIX_GUIDED,
                    "auto_fix_preview": {
                        "type": "remove_duplicates",
                        "keep_count": 1,
                        "message": "افتح ملف المركبة → الزيارة → احذف البنود المكررة يدوياً.",
                    },
                    "created_at": _now().isoformat(),
                })
        return alerts

    # =========================================================
    # 4️⃣ Detect Amount Inconsistencies (Visit total vs Operation total)
    # =========================================================
    def detect_amount_inconsistencies(self) -> List[Dict[str, Any]]:
        alerts = []
        ops_by_visit = {str(op.get("visit_id") or ""): op for op in self._operations() if op.get("visit_id")}
        for visit in self._visits():
            notes_raw = visit.get("notes") or "{}"
            try:
                import json
                meta = json.loads(notes_raw) if isinstance(notes_raw, str) else (notes_raw or {})
            except Exception:
                continue
            items = meta.get("items") if isinstance(meta, dict) else []
            if not isinstance(items, list) or not items:
                continue
            visit_total = _to_decimal(sum(
                _to_decimal(it.get("total") or (_to_decimal(it.get("price") or 0) * _to_decimal(it.get("quantity") or it.get("qty") or 1)))
                for it in items if isinstance(it, dict)
            ))
            op = ops_by_visit.get(str(visit.get("id")))
            if not op:
                continue
            op_total = _to_decimal(op.get("total") or 0)
            diff = (visit_total - op_total).copy_abs()
            if diff > Decimal("0.05"):
                aid = _alert_id("mismatch", visit.get("id"))
                if aid in self._dismissed_ids:
                    continue
                alerts.append({
                    "id": aid,
                    "category": "consistency",
                    "severity": SEV_HIGH,
                    "title": "عدم تطابق بين مجموع البنود وإجمالي العملية",
                    "description": f"مجموع البنود = {_round_2(visit_total)} ر.س بينما العملية تسجل = {_round_2(op_total)} ر.س. الفارق {_round_2(diff)} ر.س.",
                    "root_cause": "البنود تم تعديلها بعد إنشاء العملية أو تم تجاوز sync تلقائي.",
                    "financial_impact": _round_2(diff),
                    "affected_accounts": ["إيرادات خدمات", "ذمم العملاء"],
                    "related_entries": [visit.get("id"), op.get("id")],
                    "evidence": {
                        "visit_id": visit.get("id"),
                        "operation_id": op.get("id"),
                        "visit_items_total": _round_2(visit_total),
                        "operation_total": _round_2(op_total),
                        "diff": _round_2(diff),
                    },
                    "auto_fix": FIX_GUIDED,
                    "auto_fix_preview": {
                        "type": "resync_visit",
                        "endpoint": f"PUT /api/visits/{visit.get('id')}",
                        "message": "احفظ ملف المركبة من جديد ليُعاد المزامنة تلقائياً.",
                    },
                    "created_at": _now().isoformat(),
                })
        return alerts

    # =========================================================
    # 5️⃣ Detect Expense Anomalies (ارتفاع غير طبيعي)
    # =========================================================
    def detect_expense_anomalies(self, days_window: int = 14) -> List[Dict[str, Any]]:
        alerts = []
        ops = self._operations()
        now = _now()
        recent_threshold = now - timedelta(days=days_window)
        previous_threshold = now - timedelta(days=days_window * 2)

        recent_exp = Decimal("0")
        previous_exp = Decimal("0")
        for op in ops:
            if str(op.get("type") or "").lower() not in {"expense", "purchase", "cash_expense", "salary"}:
                continue
            dt = _parse_iso(op.get("created_at") or op.get("date"))
            if not dt:
                continue
            amount = _to_decimal(op.get("total") or 0)
            if dt >= recent_threshold:
                recent_exp += amount
            elif dt >= previous_threshold:
                previous_exp += amount

        if previous_exp > 0:
            change = ((recent_exp - previous_exp) / previous_exp) * Decimal("100")
            if change > Decimal("25"):
                aid = _alert_id("exp-anomaly", days_window, _round_2(recent_exp))
                if aid not in self._dismissed_ids:
                    alerts.append({
                        "id": aid,
                        "category": "anomaly",
                        "severity": SEV_HIGH if change > 50 else SEV_MEDIUM,
                        "title": f"ارتفاع غير طبيعي في المصاريف بنسبة {_round_2(change)}%",
                        "description": f"المصاريف خلال آخر {days_window} يوم: {_round_2(recent_exp)} ر.س، بينما الفترة السابقة: {_round_2(previous_exp)} ر.س.",
                        "root_cause": "زيادة في المشتريات/المصاريف. تحقق من التوريد أو الاحتيال.",
                        "financial_impact": _round_2(recent_exp - previous_exp),
                        "affected_accounts": ["المصاريف", "النقد"],
                        "related_entries": [],
                        "evidence": {
                            "recent_period_days": days_window,
                            "recent_total": _round_2(recent_exp),
                            "previous_total": _round_2(previous_exp),
                            "change_percent": _round_2(change),
                        },
                        "auto_fix": FIX_NONE,
                        "auto_fix_preview": {
                            "message": "استعرض المصاريف الكبيرة في فترة الانحراف وحدّد المصدر.",
                        },
                        "created_at": _now().isoformat(),
                    })
        return alerts

    # =========================================================
    # 6️⃣ Detect Orphan Journal Entries (قيود يتيمة)
    # =========================================================
    def detect_orphan_journals(self) -> List[Dict[str, Any]]:
        alerts = []
        op_ids = {str(op.get("id")) for op in self._operations()}
        visit_ids = {str(v.get("id")) for v in self._visits()}
        for entry in self._journals():
            src = str(entry.get("source") or "").lower()
            if src not in {"operation", "operation_payment", "operation_cogs"}:
                continue
            ref = str(entry.get("reference_id") or "")
            if not ref:
                continue
            if ref in op_ids or ref in visit_ids:
                continue
            aid = _alert_id("orphan", entry.get("id"))
            if aid in self._dismissed_ids:
                continue
            alerts.append({
                "id": aid,
                "category": "integrity",
                "severity": SEV_MEDIUM,
                "title": "قيد يومية يتيم (بدون عملية مرتبطة)",
                "description": f"القيد {entry.get('id')} يشير لـ reference_id={ref} لكن العملية الأصلية غير موجودة.",
                "root_cause": "العملية الأصلية حُذفت لكن القيد لم يُحذف معها.",
                "financial_impact": _round_2(entry.get("total") or 0),
                "affected_accounts": [str(ln.get("account_name") or "?") for ln in (entry.get("lines") or []) if isinstance(ln, dict)],
                "related_entries": [entry.get("id")],
                "evidence": {
                    "journal_id": entry.get("id"),
                    "reference_id": ref,
                    "source": src,
                    "total": _round_2(entry.get("total") or 0),
                    "date": entry.get("date"),
                },
                "auto_fix": FIX_AUTO,
                "auto_fix_preview": {
                    "type": "delete_orphan_journal",
                    "journal_id": entry.get("id"),
                    "message": "حذف القيد اليتيم آمن لأن العملية الأصلية محذوفة.",
                },
                "created_at": _now().isoformat(),
            })
        return alerts

    # =========================================================
    # 7️⃣ Suspicious Entries (out-of-hours, very large, manual)
    # =========================================================
    def detect_suspicious_entries(self) -> List[Dict[str, Any]]:
        alerts = []
        # احسب متوسط القيد
        totals = [float(e.get("total") or 0) for e in self._journals() if (e.get("total") or 0) > 0]
        if not totals:
            return alerts
        avg = sum(totals) / len(totals)
        threshold = max(avg * 5, 5000.0)

        for entry in self._journals()[:200]:
            total = float(entry.get("total") or 0)
            dt = _parse_iso(entry.get("created_at") or entry.get("date"))
            is_large = total > threshold
            is_outside_hours = False
            if dt:
                hour = dt.hour
                is_outside_hours = hour < 6 or hour >= 23
            is_manual = str(entry.get("source") or "").lower() == "manual"

            flags = []
            if is_large:
                flags.append(f"مبلغ كبير ({_round_2(total)} ر.س)")
            if is_outside_hours:
                flags.append("خارج ساعات العمل")
            if is_manual:
                flags.append("قيد يدوي")

            if len(flags) >= 2:
                aid = _alert_id("suspicious", entry.get("id"))
                if aid in self._dismissed_ids:
                    continue
                alerts.append({
                    "id": aid,
                    "category": "anomaly",
                    "severity": SEV_MEDIUM,
                    "title": "قيد مشبوه يحتاج مراجعة",
                    "description": f"القيد جمع المؤشرات التالية: {' • '.join(flags)}.",
                    "root_cause": "تركيبة مؤشرات تستدعي مراجعة بشرية.",
                    "financial_impact": _round_2(total),
                    "affected_accounts": [str(ln.get("account_name") or "?") for ln in (entry.get("lines") or []) if isinstance(ln, dict)],
                    "related_entries": [entry.get("id")],
                    "evidence": {
                        "journal_id": entry.get("id"),
                        "flags": flags,
                        "total": _round_2(total),
                        "date": entry.get("date"),
                        "description": entry.get("description"),
                    },
                    "auto_fix": FIX_NONE,
                    "auto_fix_preview": {"message": "مراجعة بشرية مطلوبة. حدّد كمحلول بعد الفحص."},
                    "created_at": _now().isoformat(),
                })
        return alerts

    # =========================================================
    # 7️⃣.b Profitability (من القيود — نفس مصدر قائمة الدخل)
    # =========================================================
    def analyze_profitability(self) -> Dict[str, Any]:
        """الإيراد/المصروف/الهامش خلال آخر 30 يوم من journal_entries."""
        now = _now()
        start = now - timedelta(days=30)
        revenue = Decimal("0")
        expenses = Decimal("0")
        for entry in self._journals():
            if str(entry.get("source") or "").strip().lower() == "period_close":
                continue
            dt = _parse_iso(entry.get("date") or entry.get("created_at"))
            if not dt or dt < start:
                continue
            for ln in (entry.get("lines") or []):
                if not isinstance(ln, dict):
                    continue
                acc_type = _account_type(_line_code(ln))
                debit = _to_decimal(ln.get("debit"))
                credit = _to_decimal(ln.get("credit"))
                if acc_type == "revenue":
                    revenue += credit - debit
                elif acc_type == "expense":
                    expenses += debit - credit
        net = revenue - expenses
        margin = float(net / revenue * 100) if revenue > 0 else None
        return {
            "period_days": 30,
            "revenue": _round_2(revenue),
            "expenses": _round_2(expenses),
            "net_income": _round_2(net),
            "margin_pct": round(margin, 1) if margin is not None else None,
        }

    def detect_profitability_issues(self, prof: Dict[str, Any]) -> List[Dict[str, Any]]:
        alerts = []
        revenue = float(prof.get("revenue") or 0)
        expenses = float(prof.get("expenses") or 0)
        margin = prof.get("margin_pct")
        if revenue > 0 and margin is not None:
            if margin < 10:
                aid = _alert_id("low-margin", "30d")
                if aid not in self._dismissed_ids:
                    alerts.append({
                        "id": aid, "category": "profitability", "severity": SEV_HIGH,
                        "title": "هامش ربح منخفض",
                        "description": f"الهامش الحالي {margin:.1f}% خلال آخر 30 يوم.",
                        "root_cause": "راجع التسعير والمصروفات وهوامش قطع الغيار.",
                        "financial_impact": _round_2(prof.get("net_income")),
                        "affected_accounts": ["الإيرادات", "المصروفات"],
                        "related_entries": [],
                        "evidence": dict(prof),
                        "auto_fix": FIX_NONE,
                        "auto_fix_preview": {"message": "راجع التسعير والمصروفات وهوامش قطع الغيار."},
                        "created_at": _now().isoformat(),
                    })
            elif margin < 20:
                aid = _alert_id("mid-margin", "30d")
                if aid not in self._dismissed_ids:
                    alerts.append({
                        "id": aid, "category": "profitability", "severity": SEV_LOW,
                        "title": "هامش ربح متوسط",
                        "description": f"الهامش الحالي {margin:.1f}% خلال آخر 30 يوم.",
                        "root_cause": "توجد فرصة لتحسين الربحية.",
                        "financial_impact": 0,
                        "affected_accounts": ["الإيرادات"],
                        "related_entries": [],
                        "evidence": dict(prof),
                        "auto_fix": FIX_NONE,
                        "auto_fix_preview": {"message": "توجد فرصة لتحسين الربحية."},
                        "created_at": _now().isoformat(),
                    })
        if revenue > 0 and expenses > revenue:
            aid = _alert_id("op-loss", "30d")
            if aid not in self._dismissed_ids:
                alerts.append({
                    "id": aid, "category": "profitability", "severity": SEV_HIGH,
                    "title": "المصروفات أعلى من الإيرادات",
                    "description": "هناك خسارة تشغيلية خلال آخر 30 يوم.",
                    "root_cause": "تحقق من تسجيل الإيرادات/المصروفات وصحة التصنيف.",
                    "financial_impact": _round_2(expenses - revenue),
                    "affected_accounts": ["الإيرادات", "المصروفات"],
                    "related_entries": [],
                    "evidence": dict(prof),
                    "auto_fix": FIX_NONE,
                    "auto_fix_preview": {"message": "تحقق من تسجيل الإيرادات/المصروفات وصحة التصنيف."},
                    "created_at": _now().isoformat(),
                })
        return alerts

    # =========================================================
    # 7️⃣.c Operations without Journal Entries (missing accounting)
    # =========================================================
    def detect_missing_journal_entries(self) -> List[Dict[str, Any]]:
        refs = {str(e.get("reference_id") or "").strip() for e in self._journals()}
        missing = [
            op for op in self._operations()
            if str(op.get("type") or "").lower() in FINANCIAL_OP_TYPES
            and float(op.get("total") or 0) > 0
            and str(op.get("id") or "") not in refs
        ]
        if not missing:
            return []
        ids = sorted(str(op.get("id") or "") for op in missing)
        aid = _alert_id("missing-journals", *ids)
        if aid in self._dismissed_ids:
            return []
        total_impact = sum(float(op.get("total") or 0) for op in missing)
        return [{
            "id": aid, "category": "integrity", "severity": SEV_HIGH,
            "title": "عمليات مالية بدون قيود محاسبية",
            "description": (f"{len(missing)} عملية مالية بمجموع {_round_2(total_impact)} ر.س "
                            "لا يقابلها أي قيد في دفتر اليومية."),
            "root_cause": "القيود لم تُنشأ عند تسجيل العملية أو حُذفت لاحقًا.",
            "financial_impact": _round_2(total_impact),
            "affected_accounts": ["دفتر اليومية"],
            "related_entries": ids[:20],
            "evidence": {
                "missing_count": len(missing),
                "operations": [
                    {"id": str(op.get("id") or "")[:8], "type": op.get("type"),
                     "total": _round_2(op.get("total") or 0)}
                    for op in missing[:10]
                ],
            },
            "auto_fix": FIX_GUIDED,
            "auto_fix_preview": {
                "type": "fix_missing_journals",
                "endpoint": "POST /api/operations/integrity/fix-all",
                "message": "شغّل «تصحيح القيود المفقودة» من مركز جدار الحماية لإعادة إنشاء القيود.",
            },
            "created_at": _now().isoformat(),
        }]

    # =========================================================
    # 7️⃣.c2 قاعدة المالك (2026-07-09): كل سند قبض مرتبط بزيارة يستوجب فاتورة مقابلة
    # =========================================================
    def detect_receipts_without_invoices(self) -> List[Dict[str, Any]]:
        visit_ids = {str(v.get("id") or "") for v in self._visits()}
        rec: Dict[str, float] = defaultdict(float)
        inv: Dict[str, float] = defaultdict(float)
        for e in self._journals():
            ref = str(e.get("reference_id") or "").strip()
            if ref not in visit_ids:
                continue
            tt = str(e.get("transaction_type") or "").lower()
            total = float(e.get("total") or 0)
            if tt == "payment":
                rec[ref] += total
            elif tt in ("sale", "service"):
                inv[ref] += total
        flagged = []
        for ref, r_total in rec.items():
            gap = round(r_total - inv.get(ref, 0.0), 2)
            if gap > 0.01:
                flagged.append({"visit_id": ref[:8], "receipts": _round_2(r_total),
                                "invoiced": _round_2(inv.get(ref, 0.0)), "gap": gap})
        if not flagged:
            return []
        flagged.sort(key=lambda x: -x["gap"])
        ids = sorted(f["visit_id"] for f in flagged)
        aid = _alert_id("receipt-no-invoice", *ids)
        if aid in self._dismissed_ids:
            return []
        total_gap = round(sum(f["gap"] for f in flagged), 2)
        return [{
            "id": aid, "category": "integrity", "severity": SEV_HIGH,
            "title": "سندات قبض مرتبطة بزيارات بلا فواتير مقابلة",
            "description": (f"{len(flagged)} زيارة عليها سندات قبض دون قيود فواتير مقابلة "
                            f"(مدين ذمم/دائن إيراد) — فجوة إجمالية {total_gap} ر.س."),
            "root_cause": "سندات القبض تُرحّل مباشرة بينما فاتورة الزيارة لا يُنشأ لها قيد.",
            "financial_impact": total_gap,
            "affected_accounts": ["ذمم العملاء (005)", "الإيرادات"],
            "related_entries": [f["visit_id"] for f in flagged[:20]],
            "evidence": {"rule": "قاعدة المالك 2026-07-09: كل سند قبض مرتبط بزيارة يستوجب فاتورة مقابلة",
                         "visits": flagged[:30]},
            "auto_fix": FIX_NONE,
            "auto_fix_preview": {"type": "four_eyes_settlement",
                                 "message": "تسوية عبر مسودات فواتير بمبدأ العيون الأربع — لا إصلاح تلقائي."},
            "created_at": _now().isoformat(),
        }]

    # =========================================================
    # 7️⃣.d Open Receivables / Payables (من القيود)
    # =========================================================
    def detect_open_receivables(self) -> List[Dict[str, Any]]:
        alerts = []
        ar = Decimal("0")
        ap = Decimal("0")
        for entry in self._journals():
            for ln in (entry.get("lines") or []):
                if not isinstance(ln, dict):
                    continue
                code = _line_code(ln)
                debit = _to_decimal(ln.get("debit"))
                credit = _to_decimal(ln.get("credit"))
                if code in AR_ACCOUNT_CODES:
                    ar += debit - credit
                if code in AP_ACCOUNT_CODES:
                    ap += credit - debit
        # 🔧 عمليات آجلة لم تُقيَّد بعد — ذمم فعلية حتى لو غاب القيد (تُستثنى المقيّدة لمنع الازدواج)
        refs = {str(e.get("reference_id") or "").strip() for e in self._journals()}
        ar_ops = Decimal("0")
        ap_ops = Decimal("0")
        for op in self._operations():
            method = str(op.get("payment_method") or "").strip().lower()
            ps = str(op.get("payment_status") or "").strip().lower()
            if method not in CREDIT_METHODS and ps not in UNPAID_STATUSES:
                continue
            if str(op.get("id") or "") in refs:
                continue
            t = str(op.get("type") or "").lower()
            amount = _to_decimal(op.get("total") or 0)
            if t in {"sale", "service", "instant_sale"}:
                ar_ops += amount
            elif t in {"purchase", "expense"}:
                ap_ops += amount
        ar_total = ar + ar_ops
        ap_total = ap + ap_ops
        if ar_total > 0:
            aid = _alert_id("ar-open", "all")
            if aid not in self._dismissed_ids:
                extra = f" (منها {_round_2(ar_ops):,.2f} من عمليات آجلة غير مقيّدة)" if ar_ops > 0 else ""
                alerts.append({
                    "id": aid, "category": "receivables", "severity": SEV_MEDIUM,
                    "title": "ذمم مدينة مفتوحة",
                    "description": f"يوجد آجل (غير محصل) بقيمة {_round_2(ar_total):,.2f} على العملاء{extra}.",
                    "root_cause": "تابع التحصيل أو اربطها بفاتورة/سداد.",
                    "financial_impact": _round_2(ar_total),
                    "affected_accounts": ["ذمم العملاء"],
                    "related_entries": [],
                    "evidence": {"ar_from_journals": _round_2(ar), "ar_from_unjournalized_credit_ops": _round_2(ar_ops)},
                    "auto_fix": FIX_NONE,
                    "auto_fix_preview": {"message": "تابع التحصيل أو اربطها بفاتورة/سداد."},
                    "created_at": _now().isoformat(),
                })
        if ap_total > 0:
            aid = _alert_id("ap-open", "all")
            if aid not in self._dismissed_ids:
                extra = f" (منها {_round_2(ap_ops):,.2f} من عمليات آجلة غير مقيّدة)" if ap_ops > 0 else ""
                alerts.append({
                    "id": aid, "category": "payables", "severity": SEV_MEDIUM,
                    "title": "ذمم دائنة مفتوحة",
                    "description": f"يوجد آجل (غير مسدد) بقيمة {_round_2(ap_total):,.2f} للموردين{extra}.",
                    "root_cause": "راجع التزامات الموردين وجدول السداد.",
                    "financial_impact": _round_2(ap_total),
                    "affected_accounts": ["ذمم الموردين"],
                    "related_entries": [],
                    "evidence": {"ap_from_journals": _round_2(ap), "ap_from_unjournalized_credit_ops": _round_2(ap_ops)},
                    "auto_fix": FIX_NONE,
                    "auto_fix_preview": {"message": "راجع التزامات الموردين وجدول السداد."},
                    "created_at": _now().isoformat(),
                })
        return alerts

    # =========================================================
    # 8️⃣ Cash Flow Analysis (Risk)
    # =========================================================
    def analyze_cash_flow(self) -> Dict[str, Any]:
        ops = self._operations()
        now = _now()
        last_30 = now - timedelta(days=30)
        inflow = Decimal("0")
        outflow = Decimal("0")
        for op in ops:
            dt = _parse_iso(op.get("created_at") or op.get("date"))
            if not dt or dt < last_30:
                continue
            t = str(op.get("type") or "").lower()
            amount = _to_decimal(op.get("total") or 0)
            # 🔧 الآجل يخص الذمم — لا يدخل في التدفق النقدي إطلاقاً
            method = str(op.get("payment_method") or "").strip().lower()
            ps = str(op.get("payment_status") or "").strip().lower()
            if method in CREDIT_METHODS or ps in UNPAID_STATUSES:
                continue
            if t in {"sale", "service", "instant_sale", "collect_customer", "receipt_voucher"}:
                inflow += amount
            elif t in {"purchase", "expense", "cash_expense", "salary", "payment_order"}:
                outflow += amount
        net = inflow - outflow
        return {
            "period_days": 30,
            "inflow": _round_2(inflow),
            "outflow": _round_2(outflow),
            "net": _round_2(net),
            "is_negative": net < 0,
        }

    # =========================================================
    # 9️⃣ Financial Health Score (0-100)
    # =========================================================
    def calculate_financial_health(self, alerts: List[Dict[str, Any]], cash_flow: Dict[str, Any]) -> Dict[str, Any]:
        """يحسب درجة من 100 بناءً على 8 معايير."""
        scores = {}

        # 1) balance integrity (25 points)
        unbal_count = sum(1 for a in alerts if a["category"] == "balance_integrity")
        scores["balance_integrity"] = max(0, 25 - unbal_count * 5)

        # 2) duplicates (15 points)
        dup_count = sum(1 for a in alerts if a["category"] == "duplicate_detection")
        scores["no_duplicates"] = max(0, 15 - dup_count * 2)

        # 3) consistency (15 points)
        incons_count = sum(1 for a in alerts if a["category"] == "consistency")
        scores["consistency"] = max(0, 15 - incons_count * 3)

        # 4) anomaly absence (15 points)
        anom_count = sum(1 for a in alerts if a["category"] == "anomaly")
        scores["no_anomalies"] = max(0, 15 - anom_count * 3)

        # 5) integrity (10 points)
        orphans = sum(1 for a in alerts if a["category"] == "integrity")
        scores["data_integrity"] = max(0, 10 - orphans * 2)

        # 6) cash flow positive (10 points)
        scores["positive_cash_flow"] = 10 if not cash_flow.get("is_negative") else 0

        # 7) profitability (5 points) — هامش/خسارة تشغيلية خلال آخر 30 يوم
        prof_issues = sum(1 for a in alerts if a.get("category") == "profitability" and a.get("severity") in (SEV_CRITICAL, SEV_HIGH))
        scores["profitability"] = 5 if prof_issues == 0 else 0

        # 8) AR overdue (5 points)
        overdue = sum(1 for a in alerts if a.get("category") == "overdue")
        scores["overdue_control"] = max(0, 5 - overdue)

        total_score = sum(scores.values())
        if total_score >= 90:
            status = "ممتاز"
            label_en = "Excellent"
            color = "emerald"
        elif total_score >= 75:
            status = "جيد"
            label_en = "Good"
            color = "lime"
        elif total_score >= 60:
            status = "متوسط"
            label_en = "Fair"
            color = "amber"
        elif total_score >= 40:
            status = "ضعيف"
            label_en = "Poor"
            color = "orange"
        else:
            status = "حرج"
            label_en = "Critical"
            color = "rose"

        return {
            "score": total_score,
            "max": 100,
            "status": status,
            "label_en": label_en,
            "color": color,
            "breakdown": scores,
        }

    # =========================================================
    # 🔄 Master Run — تجميع كل التحليلات (مع TTL Cache)
    # =========================================================
    def run_full_analysis(self, use_cache: bool = True) -> Dict[str, Any]:
        cache_key = f"ws:{self.workshop_id or 'finmodule-sync'}"
        if use_cache:
            cached = _ANALYSIS_CACHE.get(cache_key)
            if cached and (time.time() - cached[0]) < _CACHE_TTL_SECONDS:
                return cached[1]

        # تشغيل كل المحللات
        all_alerts: List[Dict[str, Any]] = []
        all_alerts.extend(self.detect_trial_balance_issues())
        all_alerts.extend(self.detect_duplicate_operations())
        all_alerts.extend(self.detect_duplicate_visit_items())
        all_alerts.extend(self.detect_amount_inconsistencies())
        all_alerts.extend(self.detect_expense_anomalies())
        all_alerts.extend(self.detect_orphan_journals())
        all_alerts.extend(self.detect_suspicious_entries())
        # 🆕 مؤشرات موحّدة (كانت سابقًا في /api/finance/alerts فقط — مصدر واحد الآن)
        profitability = self.analyze_profitability()
        all_alerts.extend(self.detect_profitability_issues(profitability))
        all_alerts.extend(self.detect_missing_journal_entries())
        all_alerts.extend(self.detect_receipts_without_invoices())
        all_alerts.extend(self.detect_open_receivables())

        # رتّب حسب الخطورة
        sev_order = {SEV_CRITICAL: 0, SEV_HIGH: 1, SEV_MEDIUM: 2, SEV_LOW: 3, SEV_INFO: 4}
        all_alerts.sort(key=lambda a: (sev_order.get(a.get("severity"), 99), -float(a.get("financial_impact") or 0)))

        cash_flow = self.analyze_cash_flow()
        health = self.calculate_financial_health(all_alerts, cash_flow)

        # عداد التصنيفات
        counts_by_category = defaultdict(int)
        counts_by_severity = defaultdict(int)
        for a in all_alerts:
            counts_by_category[a["category"]] += 1
            counts_by_severity[a["severity"]] += 1

        # Live activity = آخر 20 قيد
        live = []
        for entry in self._journals()[:20]:
            live.append({
                "id": entry.get("id"),
                "date": entry.get("created_at") or entry.get("date"),
                "description": entry.get("description"),
                "total": _round_2(entry.get("total") or 0),
                "source": entry.get("source"),
            })

        result = {
            "workshop_id": self.workshop_id,
            "generated_at": _now().isoformat(),
            "health": health,
            "alerts": all_alerts,
            "alerts_count": len(all_alerts),
            "counts_by_category": dict(counts_by_category),
            "counts_by_severity": dict(counts_by_severity),
            "cash_flow": cash_flow,
            "profitability": profitability,
            "live_activity": live,
            "stats": {
                "total_journals": len(self._journals()),
                "total_operations": len(self._operations()),
                "total_visits": len(self._visits()),
            },
        }
        if use_cache:
            _ANALYSIS_CACHE[cache_key] = (time.time(), result)
        # 📡 ربط مباشر بـ alert_bus (Phase 3 integration)
        try:
            from core import alert_bus  # lazy import لتجنب circular
            alert_bus.publish_alerts_batch(all_alerts)
        except Exception as _e:
            pass
        return result
