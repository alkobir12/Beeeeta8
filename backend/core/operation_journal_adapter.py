"""Shared operation journal adapter.

This module preserves the existing operation → AccountingEngine path while
removing the historical routes_extended ↔ visit_sync import cycle.
It is not a new engine; final posting remains delegated to AccountingEngine.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
import uuid


ACCOUNT_NAME_MAP = {
    "003": "النقد",
    "004": "البنك",
    "005": "العملاء (ذمم مدينة)",
    "006": "نقاط بيع",
    "007": "مخزون قطع غيار",
    "008": "مخزون مستهلكات",
    "010": "معدات ميكانيكية",
    "021": "مسحوبات المالك",
    "024": "الإيرادات",
    "025": "إيرادات الخدمات",
    "026": "إيرادات خدمات ميكانيكية",
    "027": "إيرادات إصلاح محركات",
    "028": "إيرادات فرامل وتعليق",
    "029": "تكلفة الخدمات",
    "030": "تكاليف مباشرة",
    "031": "أجور فنيين مباشرة",
    "032": "قطع غيار مستخدمة",
    "033": "مستهلكات مستخدمة",
    "034": "المصروفات التشغيلية",
    "035": "مصروفات عامة وإدارية",
    "036": "رواتب إدارية",
    "037": "إيجار المركز",
    "041": "ايراد قطع الورشه",
    "166": "حساب فروقات ترحيل",
    "167": "تكلفة قطع الورشة",
    "2101": "الموردون (ذمم دائنة)",
    "1101": "النقد",
    "1102": "البنك",
    "1103": "العملاء (ذمم مدينة)",
    "1104": "نقاط بيع",
    "1105": "مخزون قطع غيار",
    "4100": "إيرادات الخدمات",
    "4000": "الإيرادات",
    "6101": "رواتب إدارية",
    "3102": "مسحوبات المالك",
    "1201": "معدات ميكانيكية",
    "6100": "مصروفات عامة وإدارية",
    "6000": "المصروفات التشغيلية",
    "042": "ايراد قطع الورشه",
    "0421": "تكلفة قطع الورشة",
    "211": "حساب فروقات ترحيل",
}

LEGACY_TO_NEW_CODE = {
    "1101": "003", "acc-1101": "003",
    "1102": "004", "acc-1102": "004",
    "1103": "005", "acc-1103": "005",
    "1104": "006", "acc-1104": "006",
    "4000": "025", "acc-4000": "025",
    "4100": "026", "acc-4100": "026",
    "5000": "030", "acc-5000": "030",
    "5100": "031", "acc-5100": "031",
    "6000": "034", "acc-6000": "034",
    "6100": "035", "acc-6100": "035",
    "6101": "036", "acc-6101": "036",
    "3102": "022", "acc-3102": "022",
    "1201": "010", "acc-1201": "010",
}
ACCOUNT_ID_TO_CODE = {
    "acc-1101": "003", "acc-1102": "004", "acc-1103": "005", "acc-1104": "006",
    "acc-2101": "2101", "acc-4100": "026", "acc-4000": "025",
    "acc-6101": "036", "acc-3102": "022", "acc-1201": "010", "acc-6100": "035",
    "acc-6000": "034",
}

_TOWDHEEB_KEYWORDS = ["توضيب", "تلميع مكينة", "غسيل مكينة", "تنظيف مكينة"]
_UNCONFIRMED_PAYMENT_STATUSES = {
    "unconfirmed", "not_confirmed", "not_billed", "draft", "quotation",
    "غير مؤكد", "غير_مؤكد", "بانتظار تأكيد", "بانتظار_تأكيد",
}
_UNCONFIRMED_PAYMENT_METHODS = {"unconfirmed", "not_selected", "none", "غير محدد", "غير_محدد"}
_EXPLICIT_CREDIT_PAYMENT_METHODS = {"credit", "deferred", "اجل", "آجل", "ذمة", "ذمم"}
_EXPLICIT_CASH_PAYMENT_METHODS = {
    "cash", "نقد", "نقدي", "كاش", "transfer", "bank", "تحويل", "بنك",
    "pos", "card", "mada", "visa", "mastercard", "نقاط بيع", "نقاط_بيع",
    "point_of_sale", "بطاقة", "بطاقه", "شبكة",
}


def _safe_amount(value: Any) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _sem_code(key: str, fallback: str) -> str:
    try:
        from core.chart_resolver import semantic_codes
        return semantic_codes().get(key) or fallback
    except Exception:
        return fallback


def _normalize_account_code(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if raw in ACCOUNT_ID_TO_CODE:
        return ACCOUNT_ID_TO_CODE[raw]
    if raw.startswith("acc-") and raw[4:].isdigit():
        code = raw[4:]
        return LEGACY_TO_NEW_CODE.get(code, code)
    if raw in LEGACY_TO_NEW_CODE:
        return LEGACY_TO_NEW_CODE[raw]
    return raw


def _is_rakan_account_code(value: Any) -> bool:
    return False


def _resolve_chart_account_meta(account_ref: Optional[str], chart_account_ref_map: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    ref = str(account_ref or "").strip()
    if not ref:
        return {"code": "", "type": "", "name": "", "is_rakan": False}
    normalized = _normalize_account_code(ref)
    return (
        chart_account_ref_map.get(ref)
        or chart_account_ref_map.get(normalized)
        or {"code": normalized or ref, "type": "", "name": normalized or ref, "is_rakan": _is_rakan_account_code(normalized or ref)}
    )


def _infer_revenue_code(op: Dict[str, Any]) -> str:
    try:
        from core.chart_resolver import semantic_codes
        sem = semantic_codes()
    except Exception:
        sem = {}
    items = op.get("items") or []
    all_text = " ".join(
        [str(op.get("notes") or ""), str(op.get("description") or "")]
        + [str(it.get("name") or "") for it in items if str(it.get("itemType") or "").lower() not in ("supplier",)]
    )
    for kw in _TOWDHEEB_KEYWORDS:
        if kw in all_text:
            return sem.get("revenue_engine") or "027"
    return sem.get("revenue_mech") or "026"


def _is_unconfirmed_vehicle_financial_state(op: Dict[str, Any]) -> bool:
    op_type = str(op.get("type") or "").strip().lower()
    if op_type not in {"sale", "service"}:
        return False
    has_vehicle_context = bool(
        op.get("vehicleId")
        or op.get("vehicle_id")
        or str(op.get("scope") or "").strip().lower() == "vehicle"
        or str(op.get("operationKind") or "").strip().upper() == "VEHICLE_OPERATION"
    )
    if not has_vehicle_context:
        return False
    raw_method = op.get("paymentMethod") if "paymentMethod" in op else op.get("payment_method")
    raw_status = op.get("paymentStatus") if "paymentStatus" in op else op.get("payment_status")
    method = str(raw_method or "").strip().lower()
    status = str(raw_status or "").strip().lower()
    if method in _EXPLICIT_CREDIT_PAYMENT_METHODS or method in _EXPLICIT_CASH_PAYMENT_METHODS:
        return False
    return method in _UNCONFIRMED_PAYMENT_METHODS or status in _UNCONFIRMED_PAYMENT_STATUSES


def _split_operation_totals(op: Dict[str, Any]) -> Dict[str, float]:
    total = _safe_amount(op.get("total"))
    items = op.get("items") or []
    if not isinstance(items, list) or not items:
        supplier_total = _safe_amount(op.get("supplier_archive_total") or op.get("total_suppliers"))
        return {
            "combined_total": total,
            "workshop_total": max(total - supplier_total, 0.0) if supplier_total > 0 else total,
            "supplier_total": supplier_total,
        }
    workshop = 0.0
    suppliers = 0.0
    for item in items:
        if not isinstance(item, dict):
            continue
        line_total = _safe_amount(item.get("total"))
        if line_total <= 0:
            line_total = _safe_amount(item.get("price")) * _safe_amount(item.get("quantity") or item.get("qty") or 1)
        if str(item.get("itemType") or item.get("type") or "").strip().lower() == "supplier":
            suppliers += line_total
        else:
            workshop += line_total
    if workshop <= 0 and total > 0:
        workshop = max(total - suppliers, 0.0)
    combined = total if total > 0 else (workshop + suppliers)
    return {"combined_total": round(combined, 2), "workshop_total": round(workshop, 2), "supplier_total": round(suppliers, 2)}


def _build_operation_journal_entry(op: Dict[str, Any], workshop_id: Optional[str], chart_account_ref_map: Optional[Dict[str, Dict[str, Any]]] = None):
    if not workshop_id or _is_unconfirmed_vehicle_financial_state(op):
        return None

    op_type = (op.get("type") or "").lower()
    payment_method = (op.get("paymentMethod") or op.get("payment_method") or "cash").lower()
    totals = _split_operation_totals(op)
    total = _safe_amount(op.get("total"))
    workshop_total = totals.get("workshop_total", total)
    supplier_total = totals.get("supplier_total", 0.0)
    if total <= 0:
        total = workshop_total
    if total <= 0:
        return None

    pay_status = str(op.get("paymentStatus") or op.get("payment_status") or "").strip().lower()
    is_credit = payment_method in _EXPLICIT_CREDIT_PAYMENT_METHODS or pay_status in ("unpaid", "credit", "partial", "deferred", "pending")

    cash_code = _sem_code("cash", "003")
    if payment_method in ("transfer", "bank", "تحويل", "بنك"):
        cash_code = _sem_code("bank", "004")
    elif payment_method in ("pos", "card", "mada", "visa", "mastercard", "نقاط بيع", "نقاط_بيع", "point_of_sale", "بطاقة", "بطاقه", "شبكة"):
        cash_code = _sem_code("pos", "006")

    ar_code = _sem_code("ar", "005")
    ap_code = _sem_code("ap", "2101")
    admin_exp_code = _sem_code("admin_expense", "035")
    chart_account_ref_map = chart_account_ref_map or {}

    def _to_meta(account_ref: Optional[str]) -> Dict[str, Any]:
        return _resolve_chart_account_meta(account_ref, chart_account_ref_map) if str(account_ref or "").strip() else {"code": "", "type": "", "name": "", "is_rakan": False}

    selected_meta = _to_meta(op.get("accountingAccountId") or op.get("accounting_account_id") or op.get("accountId") or op.get("account_id"))
    selected_code = selected_meta.get("code") or ""

    scope = str(op.get("scope") or "").strip().lower()
    business_unit = str(op.get("businessUnit") or op.get("business_unit") or "").strip().lower()
    source = str(op.get("source") or "").strip().lower()
    notes_lower = str(op.get("notes") or "").lower()
    is_rakan_operation = selected_meta.get("is_rakan") or scope == "rakan_parts" or business_unit == "rakan_parts" or "rakan_parts" in source or "[rakan_parts]" in notes_lower
    if is_rakan_operation:
        return None

    items_for_check = op.get("items") or []
    has_part_item = any(str(it.get("itemType") or it.get("item_type") or "").lower() == "part" for it in items_for_check if isinstance(it, dict))
    has_service_item = any(str(it.get("itemType") or it.get("item_type") or "").lower() == "service" for it in items_for_check if isinstance(it, dict))

    lines = []
    transaction_type = None
    if op_type in ("sale", "service"):
        total = workshop_total
        if total <= 0:
            return None
        if op_type == "sale" and has_part_item and not has_service_item and workshop_total <= 0:
            return None
        transaction_type = "sale"
        debit_code = ar_code if is_credit else cash_code
        valid_rev_code = selected_code if selected_code and len(selected_code) <= 12 and "-" not in selected_code else None
        revenue_code = LEGACY_TO_NEW_CODE.get(valid_rev_code, valid_rev_code) if valid_rev_code else _infer_revenue_code(op)
        lines = [
            {"account": debit_code, "account_name": ACCOUNT_NAME_MAP.get(debit_code, debit_code), "debit": total, "credit": 0},
            {"account": revenue_code, "account_name": ACCOUNT_NAME_MAP.get(revenue_code, revenue_code), "debit": 0, "credit": total},
        ]
    elif op_type in ("purchase", "expense"):
        transaction_type = "purchase" if op_type == "purchase" else "expense"

        def _is_expense_code(c):
            if not c:
                return False
            try:
                n = int(c)
                return n in (7, 8, 10, 167) or 29 <= n <= 48
            except (ValueError, TypeError):
                return str(c or "").startswith(("5", "6", "1201"))

        debit_code = selected_code if selected_code and len(selected_code) <= 12 and "-" not in selected_code and _is_expense_code(selected_code) else admin_exp_code
        debit_code = LEGACY_TO_NEW_CODE.get(debit_code, debit_code) if debit_code else debit_code
        credit_code = ap_code if is_credit else cash_code
        lines = [
            {"account": debit_code, "account_name": ACCOUNT_NAME_MAP.get(debit_code, debit_code), "debit": total, "credit": 0},
            {"account": credit_code, "account_name": ACCOUNT_NAME_MAP.get(credit_code, credit_code), "debit": 0, "credit": total},
        ]
    elif op_type == "sale_return":
        transaction_type = "sale_return"
        debit_code = selected_code if selected_code and len(selected_code) <= 12 and "-" not in selected_code else _sem_code("revenue_mech", "026")
        credit_code = ar_code if is_credit else cash_code
        lines = [
            {"account": debit_code, "account_name": ACCOUNT_NAME_MAP.get(debit_code, debit_code), "debit": total, "credit": 0},
            {"account": credit_code, "account_name": ACCOUNT_NAME_MAP.get(credit_code, credit_code), "debit": 0, "credit": total},
        ]
    elif op_type == "purchase_return":
        transaction_type = "purchase_return"
        debit_code = ap_code if is_credit else cash_code
        credit_code = selected_code if str(selected_code or "").startswith(("5", "6")) else admin_exp_code
        lines = [
            {"account": debit_code, "account_name": ACCOUNT_NAME_MAP.get(debit_code, debit_code), "debit": total, "credit": 0},
            {"account": credit_code, "account_name": ACCOUNT_NAME_MAP.get(credit_code, credit_code), "debit": 0, "credit": total},
        ]
    elif op_type == "payment_order":
        transaction_type = "payment_order"
        if str(op.get("partnerType") or op.get("partner_type") or "").strip().lower() == "customer":
            lines = [
                {"account": cash_code, "account_name": ACCOUNT_NAME_MAP.get(cash_code, cash_code), "debit": total, "credit": 0},
                {"account": ar_code, "account_name": ACCOUNT_NAME_MAP.get(ar_code, "العملاء (ذمم مدينة)"), "debit": 0, "credit": total},
            ]
        else:
            lines = [
                {"account": ap_code, "account_name": ACCOUNT_NAME_MAP.get(ap_code, "الموردون (ذمم دائنة)"), "debit": total, "credit": 0},
                {"account": cash_code, "account_name": ACCOUNT_NAME_MAP.get(cash_code, cash_code), "debit": 0, "credit": total},
            ]
    else:
        return None

    description = op.get("notes") or f"عملية {transaction_type} - {op.get('partnerName') or op.get('partner_name') or ''}"
    if is_credit and transaction_type == "sale" and "قيد مؤقت" not in str(description):
        description = f"[قيد مؤقت — بيع آجل] {description}".strip()

    primary_entry = {
        "id": str(uuid.uuid4()),
        "workshop_id": workshop_id,
        "date": op.get("date") or op.get("op_date") or datetime.utcnow().isoformat(),
        "description": description,
        "lines": lines,
        "total": total,
        "operation_total": totals.get("combined_total", total),
        "workshop_total": workshop_total,
        "supplier_archive_total": supplier_total,
        "source": "operation",
        "transaction_type": transaction_type,
        "reference_id": op.get("id"),
    }

    return primary_entry


def _safe_insert_journal_entry(_supa: Any, entry: Dict[str, Any]):
    if not entry:
        return None
    try:
        from core import accounting_engine
        result = accounting_engine.post_entry(entry, fallback=False)
        from core.journal_attribution import record_attribution
        record_attribution(result, entry)
        if not result:
            raise RuntimeError("accounting_engine_rejected_entry")
        return result
    except Exception as error:
        print(f"AccountingEngine post_entry failed; no direct journal fallback: {error}")
        raise
