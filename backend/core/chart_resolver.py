"""محلّل دليل الحسابات — مصدر الحقيقة الوحيد للأكواد الحالية.

أكواد الحسابات في جدول `accounts` قابلة لإعادة الترقيم (resequence)،
بينما معرّفات الحسابات (acc-1101...) والأسماء ثابتة. هذا المحلّل يحوّل
المعرّف/الاسم الدلالي إلى الكود الحالي وقت الكتابة، مع fallback ثابت.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Dict, Optional

# semantic_key: (stable_account_id, exact_name, fallback_code)
SEMANTIC_ACCOUNTS = {
    "cash": ("acc-1101", "النقد", "003"),
    "bank": ("acc-1102", "البنك", "004"),
    "ar": ("acc-1103", "العملاء", "005"),
    "pos": (None, "نقاط بيع", "006"),
    "inventory_parts": ("acc-1105", "مخزون قطع غيار", "007"),
    "equipment": ("acc-1201", "معدات ميكانيكية", "010"),
    "owner_draw": ("acc-3102", "مسحوبات المالك", "021"),
    "revenue_parent": ("acc-4000", "الإيرادات", "024"),
    "revenue_services": ("acc-4100", "إيرادات الخدمات", "025"),
    "revenue_mech": ("acc-4101", "إيرادات خدمات ميكانيكية", "026"),
    "revenue_engine": ("acc-4102", "إيرادات إصلاح محركات", "027"),
    "revenue_brakes": ("acc-4103", "إيرادات فرامل وتعليق", "028"),
    "cost_services": ("acc-5000", "تكلفة الخدمات", "029"),
    "direct_costs": ("acc-5100", "تكاليف مباشرة", "030"),
    "tech_wages": ("acc-5101", "أجور فنيين مباشرة", "031"),
    "opex": ("acc-6000", "المصروفات التشغيلية", "034"),
    "admin_expense": ("acc-6100", "مصروفات عامة وإدارية", "035"),
    "salaries": ("acc-6101", "رواتب إدارية", "036"),
    "parts_revenue": (None, "ايراد قطع الورشه", "041"),
    "parts_cogs": (None, "تكلفة قطع الورشة", "167"),
    "migration_diff": (None, "حساب فروقات ترحيل", "166"),
    "ap": ("acc-2101", "الموردون", "2101"),
}

_CACHE_TTL = 30.0
_lock = threading.Lock()
_cache: Dict[str, Any] = {"at": 0.0, "accounts": []}


def _load_accounts():
    now = time.time()
    if _cache["accounts"] and (now - _cache["at"]) < _CACHE_TTL:
        return _cache["accounts"]
    with _lock:
        if _cache["accounts"] and (time.time() - _cache["at"]) < _CACHE_TTL:
            return _cache["accounts"]
        try:
            from supabase_service import SupabaseService
            rows = (SupabaseService().client.table("accounts")
                    .select("id,code,name,type").execute().data or [])
            if rows:
                _cache["accounts"] = rows
                _cache["at"] = time.time()
        except Exception:
            pass
        return _cache["accounts"]


def invalidate_cache() -> None:
    _cache["at"] = 0.0
    _cache["accounts"] = []


def semantic_codes() -> Dict[str, str]:
    """يعيد {semantic_key: current_code} من الجدول الحي مع fallback ثابت."""
    rows = _load_accounts()
    by_id = {str(r.get("id") or "").strip(): r for r in rows}
    by_name = {str(r.get("name") or "").strip(): r for r in rows}
    out: Dict[str, str] = {}
    for key, (acc_id, name, fallback) in SEMANTIC_ACCOUNTS.items():
        row = (by_id.get(acc_id) if acc_id else None) or by_name.get(name)
        code = str((row or {}).get("code") or "").strip()
        out[key] = code or fallback
    return out


def name_of(code: str) -> Optional[str]:
    c = str(code or "").strip()
    for r in _load_accounts():
        if str(r.get("code") or "").strip() == c:
            return str(r.get("name") or "").strip() or None
    return None


def type_of(code: str) -> Optional[str]:
    """نوع الحساب من الجدول الحي (asset/liability/equity/revenue/expense)."""
    c = str(code or "").strip()
    for r in _load_accounts():
        if str(r.get("code") or "").strip() == c:
            return str(r.get("type") or "").strip().lower() or None
    return None
