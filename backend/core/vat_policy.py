"""سياسة VAT وبند التسوية — PRD Decimal v1.1 §5.

بنية جاهزة (validators + توزيع + بند تسوية). التفعيل الحي للـ VAT في الفواتير
إصدار لاحق بقرار المستخدم — إن أصبح النظام مُصدِراً لفواتير ضريبية حية يُفعَّل فوراً.

الحساب المعتمد: يقرأ حصراً من الإعدادات (`vat_rounding_account`).
الغياب = خطأ تهيئة صريح يوقف الترحيل — لا حساب افتراضي (PRD §5).
"""
from __future__ import annotations

import os
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional

from core.accounting_engine import CENT, _dec

VAT_RATE = Decimal("0.15")
SETTING_KEY = "vat_rounding_account"
SETTLEMENT_ACCOUNT_NAME = "فروق تقريب ضريبية"


class VatConfigError(RuntimeError):
    """غياب حساب فروق التقريب من الإعدادات — يوقف الترحيل صراحةً."""


def get_vat_rounding_account() -> str:
    """يعيد كود حساب فروق التقريب من الإعدادات — أو يرفع VatConfigError."""
    # 1) Supabase workshop_settings (إن أُضيف العمود مستقبلاً)
    try:
        from supabase_service import SupabaseService
        client = SupabaseService().client
        if client:
            res = (client.table("workshop_settings").select(SETTING_KEY)
                   .eq("id", "app_settings").limit(1).execute())
            val = ((res.data or [{}])[0] or {}).get(SETTING_KEY)
            if val:
                return str(val)
    except Exception:
        pass
    # 2) MongoDB settings — المخزن المعتمد حالياً
    try:
        from pymongo import MongoClient
        db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
        doc = db.settings.find_one({"id": "app_settings"}) or {}
        if doc.get(SETTING_KEY):
            return str(doc[SETTING_KEY])
    except Exception:
        pass
    raise VatConfigError(
        "vat_rounding_account is not configured in settings — "
        "VAT settlement posting is blocked (PRD Decimal v1.1 §5)."
    )


def distribute_vat(amounts: List[Any], rate: Decimal = VAT_RATE) -> Dict[str, Any]:
    """يوزّع VAT على بنود متعددة بتقريب ROUND_HALF_UP لكل بند ويحسب فرق التسوية.

    vat_total = الضريبة الرسمية على إجمالي الأساس (المُلزمة).
    settlement = vat_total − مجموع ضرائب البنود (فرق التقريب فقط).
    """
    base = [_dec(a) for a in amounts]
    per_line = [(a * rate).quantize(CENT, rounding=ROUND_HALF_UP) for a in base]
    total_base = sum(base, Decimal("0.00"))
    vat_total = (total_base * rate).quantize(CENT, rounding=ROUND_HALF_UP)
    # settlement = ما زاد في التحليلي (مجموع البنود) عن الرسمي الملزم
    settlement = sum(per_line, Decimal("0.00")) - vat_total
    return {"per_line": per_line, "vat_total": vat_total,
            "settlement": settlement, "total_base": total_base}


def build_settlement_line(diff: Any, n_lines: int) -> Optional[Dict[str, Any]]:
    """بند تسوية واحد فقط — سقفه هللات معدودة (CENT × عدد البنود).

    تجاوز السقف يدل على خطأ حسابي لا فرق تقريب → يُرفض (PRD §5).
    """
    d = _dec(diff)
    if d == 0:
        return None
    cap = CENT * max(1, int(n_lines))
    if abs(d) > cap:
        raise ValueError(
            f"Settlement amount {d} exceeds rounding cap {cap} — calculation error, entry rejected.")
    account = get_vat_rounding_account()
    if d > 0:
        # التحليلي زاد عن الرسمي → مدين (مصروف فرق تقريب) يغلق القيد
        return {"account": account, "account_name": SETTLEMENT_ACCOUNT_NAME,
                "debit": d, "credit": 0, "description": "بند تسوية فروق تقريب VAT"}
    return {"account": account, "account_name": SETTLEMENT_ACCOUNT_NAME,
            "debit": 0, "credit": abs(d), "description": "بند تسوية فروق تقريب VAT"}
