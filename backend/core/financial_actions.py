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

# أكواد دليل الحسابات (الجديدة)
CASH = "003"      # النقد
BANK = "004"      # البنك
POS = "006"       # نقاط بيع
AR = "005"        # العملاء (ذمم مدينة)
AP = "2101"       # الموردون (ذمم دائنة)
REVENUE = "025"   # الإيرادات
EXPENSE = "030"   # المصروفات


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_amount(value: Any) -> float:
    try:
        return round(float(str(value).replace(",", "")), 2)
    except (TypeError, ValueError):
        return 0.0


def _payment_account(method: Optional[str]) -> tuple[str, str]:
    m = str(method or "cash").strip().lower()
    if m in ("bank", "transfer", "bank_transfer", "تحويل", "بنك", "حوالة"):
        return BANK, "البنك"
    if m in ("pos", "mada", "card", "visa", "mastercard", "شبكة", "بطاقة", "بطاقه"):
        return POS, "نقاط بيع"
    return CASH, "النقد"


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

    if _is_credit(payment_method):
        debit_acc, debit_name = AR, f"العملاء — {customer}"
    else:
        debit_acc, debit_name = _payment_account(payment_method)
    lines = [
        {"account": debit_acc, "account_name": debit_name, "debit": amount, "credit": 0},
        {"account": REVENUE, "account_name": "الإيرادات", "debit": 0, "credit": amount},
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
        {"account": AR, "account_name": f"العملاء — {customer}", "debit": 0, "credit": amt},
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
    expense_name = f"مصروف — {category}" if category else "مصروفات عامة"

    if _is_credit(payment_method) and supplier:
        credit_acc, credit_name = AP, f"مورد — {supplier}"
    else:
        credit_acc, credit_name = _payment_account(payment_method)
    lines = [
        {"account": EXPENSE, "account_name": expense_name, "debit": amt, "credit": 0},
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
