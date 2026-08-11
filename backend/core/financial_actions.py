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
    "inventory_parts": "007",   # 🛒 المخزون (لمعالجة الشراء)
    "vat_input": "0451",        # 🧾 ضريبة القيمة المضافة — المدخلات (fallback؛ يُنشأ لاحقاً)
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


# ─── 🕒 القيد المؤقت للبيع الآجل (قاعدة المالك) ─────────────────────────────
TEMP_DEFERRED_TAG = "[قيد مؤقت — بيع آجل]"
PARTIAL_TAG = "[قيد مؤقت — بيع آجل | مُحصَّل جزئياً]"
SETTLED_TAG = "[بيع آجل — مُسوَّى ✓]"


def mark_temp_deferred_settled(reference_id: Optional[str], fully: Optional[bool] = None) -> None:
    """توافق قديم فقط؛ حالة السداد تُحفظ في operation ولا تُغيّر القيد المحاسبي."""
    return None


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
    if _is_credit(payment_method):
        desc = f"{TEMP_DEFERRED_TAG} {desc}"
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
    result = get_engine().post(
        lines=lines, date=entry_date, description=f"تحصيل من {customer}", total=amt,
        source="payment", transaction_type="payment", reference_id=reference_id,
        workshop_id=workshop_id, party=customer, actor=actor,
        extra={"party_label": customer, "party_type": "customer", "payment_method": payment_method},
    )
    # 🕒 عند التحصيل: حدّث وسم القيد المؤقت المرتبط (إن وُجد) إلى مُسوَّى
    if reference_id and isinstance(result, dict) and (result.get("posted") or result.get("journal_id")):
        mark_temp_deferred_settled(reference_id)
    return result


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
# 4) شراء من مورد (Purchase from Supplier) — مخزون مدين + دائن حسب طريقة الدفع
# ─────────────────────────────────────────────────────────────────────────────

def _purchase_credit_account(method: Optional[str], supplier: Optional[str]) -> tuple[str, str]:
    """يحدد الحساب الدائن للشراء بحسب طريقة الدفع.
    نقدي→الصندوق(003) · تحويل→البنك(004) · آجل→الموردون(2101 + اسم المورد)."""
    sem = _codes()
    m = str(method or "cash").strip().lower()
    if m in ("credit", "اجل", "آجل", "deferred", "on_account"):
        return sem["ap"], f"مورد — {supplier or 'مفتوح'}"
    if m in ("bank", "transfer", "bank_transfer", "تحويل", "بنك", "حوالة"):
        return sem["bank"], "البنك"
    return sem["cash"], "النقد"


def _compute_purchase_totals(items: List[Dict[str, Any]], vat: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """يحسب صافي/ضريبة/إجمالي الشراء بـ Decimal تحت `vat_policy` (بلا سماحية)."""
    from decimal import Decimal
    from core.vat_policy import compute_vat_split

    # حساب صافي البنود بالـ Decimal دون سماحية
    net = Decimal("0.00")
    normalized: List[Dict[str, Any]] = []
    for it in items or []:
        try:
            price = Decimal(str(it.get("price") or 0))
            qty = Decimal(str(it.get("qty") or it.get("quantity") or 1))
        except Exception:
            price, qty = Decimal("0"), Decimal("1")
        line = (price * qty)
        net += line
        normalized.append({
            "name": str(it.get("name") or "").strip(),
            "price": float(price),
            "qty": float(qty),
            "line_total": float(line),
            "matched_id": it.get("matched_id"),
        })

    vat_cfg = vat or {"mode": "none"}
    split = compute_vat_split(net, vat_cfg)   # {net, vat, gross}
    return {
        "items": normalized,
        "net": split["net"],
        "vat_amount": split["vat"],
        "gross": split["gross"],
        "vat_mode": str(vat_cfg.get("mode") or "none"),
        "vat_rate": float(vat_cfg.get("rate") or 0),
    }


def create_purchase(
    *,
    supplier: Optional[str],
    items: List[Dict[str, Any]],
    payment_method: str = "cash",
    vat: Optional[Dict[str, Any]] = None,
    date: Optional[str] = None,
    reference_id: Optional[str] = None,
    workshop_id: str = DEFAULT_WORKSHOP_ID,
    actor: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """شراء بضاعة/قطع غيار من مورد.

    مدين: المخزون (007) بالصافي [+ ضريبة المدخلات (VAT) إن وُجدت].
    دائن: النقد (003) أو البنك (004) أو الموردون (2101) حسب `payment_method`.
    """
    if not items:
        return {"posted": False, "error": "no_items"}

    totals = _compute_purchase_totals(items, vat)
    net = totals["net"]
    vat_amt = totals["vat_amount"]
    gross = totals["gross"]
    if gross <= 0:
        return {"posted": False, "error": "invalid_amount"}

    entry_date = date or _now_iso()
    sem = _codes()
    credit_acc, credit_name = _purchase_credit_account(payment_method, supplier)

    lines: List[Dict[str, Any]] = [
        {"account": sem["inventory_parts"], "account_name": "مخزون قطع غيار",
         "debit": net, "credit": 0},
    ]
    if vat_amt and float(vat_amt) > 0:
        # ملاحظة: نستخدم كود ضريبة المدخلات إن وُجد ضمن chart_resolver مستقبلاً؛
        # حالياً نضيفه كبند مدين باسم واضح (كود fallback: 0451) — التوازن سيبقى صحيحاً.
        lines.append({
            "account": (sem.get("vat_input") or "0451"),
            "account_name": "ضريبة القيمة المضافة — المدخلات",
            "debit": vat_amt, "credit": 0,
        })
    lines.append({"account": credit_acc, "account_name": credit_name,
                  "debit": 0, "credit": gross})

    item_count = len(totals["items"])
    desc_supplier = supplier or "مفتوح"
    desc = f"شراء — {desc_supplier} ({item_count} بند)"

    result = get_engine().post(
        lines=lines, date=entry_date, description=desc, total=gross,
        source="purchase", transaction_type="purchase", reference_id=reference_id,
        workshop_id=workshop_id, party=supplier, items=totals["items"], actor=actor,
        extra={
            "party_label": desc_supplier,
            "party_type": "supplier",
            "payment_method": payment_method,
            "vat_mode": totals["vat_mode"],
            "net_amount": float(net),
            "vat_amount": float(vat_amt),
        },
    )
    if isinstance(result, dict):
        result.setdefault("total", float(gross))
        result["net"] = float(net)
        result["vat"] = float(vat_amt)
        result["items_count"] = item_count
    return result


# ─────────────────────────────────────────────────────────────────────────────
# 5) قيد عكسي (Reversal / Contra-entry) — No Hard Delete
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
