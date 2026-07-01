"""
💰 core/financial_actions.py — أوامر الكتابة المالية عبر المحرك المركزي

ثلاثة إجراءات مالية تمرّ كلها عبر `AccountingEngine`:
  • create_invoice  — إصدار فاتورة (بيع نقدي أو آجل)
  • collect_payment — تحصيل دفعة من عميل (تسديد ذمم)
  • create_expense  — تسجيل مصروف (نقدي أو آجل من مورد)

كلها تنتج قيدًا مزدوجًا متوازنًا، وتُمنع من التكرار تلقائيًا (البند+السعر+الوقت+العميل)
عبر طبقة الـIdempotency في المحرك.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.accounting_engine import DEFAULT_WORKSHOP_ID, get_engine

# أكواد دليل الحسابات — تُحلّ ديناميكياً من الدليل الحي (chart_resolver) مع fallback
_FALLBACK_CODES = {
    "cash": "003", "bank": "004", "pos": "006", "ar": "005", "ap": "2101",
    "revenue_mech": "026", "admin_expense": "035",
}


def _codes() -> Dict[str, str]:
    try:
        from core.chart_resolver import semantic_codes
        sem = semantic_codes()
        return {k: sem.get(k) or v for k, v in _FALLBACK_CODES.items()}
    except Exception:
        return dict(_FALLBACK_CODES)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_amount(value: Any) -> float:
    try:
        return round(float(str(value).replace(",", "")), 2)
    except (TypeError, ValueError):
        return 0.0


def _payment_account(method: Optional[str]) -> tuple[str, str]:
    sem = _codes()
    m = str(method or "cash").strip().lower()
    if m in ("bank", "transfer", "bank_transfer", "تحويل", "بنك", "حوالة"):
        return sem["bank"], "البنك"
    if m in ("pos", "mada", "card", "visa", "mastercard", "شبكة", "بطاقة", "بطاقه"):
        return sem["pos"], "نقاط بيع"
    return sem["cash"], "النقد"


def _is_credit(method: Optional[str], status: Optional[str] = None) -> bool:
    m = str(method or "").strip().lower()
    s = str(status or "").strip().lower()
    return m in ("credit", "اجل", "آجل", "deferred") or s in ("credit", "unpaid", "اجل", "آجل", "deferred")


def _items_total(items: Optional[List[Dict[str, Any]]]) -> float:
    total = 0.0
    for it in items or []:
        line_total = it.get("total")
        if line_total is None:
            line_total = _to_amount(it.get("price")) * _to_amount(it.get("quantity") or it.get("qty") or 1)
        total += _to_amount(line_total)
    return round(total, 2)


# ─────────────────────────────────────────────────────────────────────────────
# 1) إصدار فاتورة
# ─────────────────────────────────────────────────────────────────────────────

def create_invoice(
    *,
    customer: str,
    items: Optional[List[Dict[str, Any]]] = None,
    total: Optional[float] = None,
    payment_method: str = "credit",
    date: Optional[str] = None,
    reference_id: Optional[str] = None,
    workshop_id: str = DEFAULT_WORKSHOP_ID,
    actor: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """فاتورة بيع. آجل → مدين العملاء/دائن الإيرادات. نقدي → مدين النقد/دائن الإيرادات."""
    amount = _to_amount(total) if total is not None else _items_total(items)
    if amount <= 0:
        return {"posted": False, "error": "invalid_amount"}
    entry_date = date or _now_iso()
    sem = _codes()

    if _is_credit(payment_method):
        debit_acc, debit_name = sem["ar"], f"العملاء — {customer}"
    else:
        debit_acc, debit_name = _payment_account(payment_method)
    lines = [
        {"account": debit_acc, "account_name": debit_name, "debit": amount, "credit": 0},
        {"account": sem["revenue_mech"], "account_name": "إيرادات خدمات ميكانيكية", "debit": 0, "credit": amount},
    ]
    desc = f"فاتورة — {customer}" + (f" ({len(items)} بند)" if items else "")
    return get_engine().post(
        lines=lines, date=entry_date, description=desc, total=amount,
        source="invoice", transaction_type="sale", reference_id=reference_id,
        workshop_id=workshop_id, party=customer, items=items, actor=actor,
        extra={"party_label": customer, "party_type": "customer"},
    )


# ─────────────────────────────────────────────────────────────────────────────
# 2) تحصيل دفعة من عميل
# ─────────────────────────────────────────────────────────────────────────────

def collect_payment(
    *,
    customer: str,
    amount: float,
    payment_method: str = "cash",
    date: Optional[str] = None,
    reference_id: Optional[str] = None,
    workshop_id: str = DEFAULT_WORKSHOP_ID,
    actor: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """تحصيل: مدين النقد/البنك / دائن العملاء (تخفيض ذمم العميل)."""
    amt = _to_amount(amount)
    if amt <= 0:
        return {"posted": False, "error": "invalid_amount"}
    entry_date = date or _now_iso()
    pay_acc, pay_name = _payment_account(payment_method)
    lines = [
        {"account": pay_acc, "account_name": pay_name, "debit": amt, "credit": 0},
        {"account": _codes()["ar"], "account_name": f"العملاء — {customer}", "debit": 0, "credit": amt},
    ]
    return get_engine().post(
        lines=lines, date=entry_date, description=f"تحصيل من {customer}", total=amt,
        source="payment", transaction_type="payment", reference_id=reference_id,
        workshop_id=workshop_id, party=customer, actor=actor,
        extra={"party_label": customer, "party_type": "customer", "payment_method": payment_method},
    )


# ─────────────────────────────────────────────────────────────────────────────
# 3) تسجيل مصروف
# ─────────────────────────────────────────────────────────────────────────────

def create_expense(
    *,
    description: str,
    amount: float,
    category: Optional[str] = None,
    supplier: Optional[str] = None,
    payment_method: str = "cash",
    date: Optional[str] = None,
    reference_id: Optional[str] = None,
    workshop_id: str = DEFAULT_WORKSHOP_ID,
    actor: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """مصروف: مدين المصروفات / دائن النقد/البنك (نقدي) أو الموردون (آجل)."""
    amt = _to_amount(amount)
    if amt <= 0:
        return {"posted": False, "error": "invalid_amount"}
    entry_date = date or _now_iso()
    expense_name = f"مصروف — {category}" if category else "مصروفات عامة وإدارية"
    sem = _codes()

    if _is_credit(payment_method) and supplier:
        credit_acc, credit_name = sem["ap"], f"مورد — {supplier}"
    else:
        credit_acc, credit_name = _payment_account(payment_method)
    lines = [
        {"account": sem["admin_expense"], "account_name": expense_name, "debit": amt, "credit": 0},
        {"account": credit_acc, "account_name": credit_name, "debit": 0, "credit": amt},
    ]
    party = supplier or category or "مصروف"
    return get_engine().post(
        lines=lines, date=entry_date, description=f"{description}", total=amt,
        source="expense", transaction_type="expense", reference_id=reference_id,
        workshop_id=workshop_id, party=party, actor=actor,
        extra={"party_label": supplier or "مفتوح",
               "party_type": "supplier" if supplier else "open"},
    )


# ─────────────────────────────────────────────────────────────────────────────
# 4) قيد عكسي (Reversal / Contra-entry) — No Hard Delete
# ─────────────────────────────────────────────────────────────────────────────

def reverse_entry(
    *,
    journal_id: Optional[str] = None,
    reference_id: Optional[str] = None,
    reason: str = "",
    actor: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """عكس قيد/قيود مرتبطة دون حذف الأصل — يمرّ عبر المحرك المركزي."""
    return get_engine().reverse(
        journal_id=journal_id, reference_id=reference_id, reason=reason, actor=actor,
    )
