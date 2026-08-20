"""
routes_smart_accounting.py
Smart account dropdowns + Supplier balance payment + Vehicle archive
"""
from fastapi import APIRouter, HTTPException, Query, Body
from typing import Any, Dict, List
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

try:
    from routes_finance import supabase, invalidate_finance_caches
except Exception:
    supabase = None
    def invalidate_finance_caches(): pass

router = APIRouter(prefix="/api/smart-accounting", tags=["smart-accounting"])

_LAST_USED_FILE = Path("/app/backend/uploads/last_used_accounts.json")

# ── خريطة الحسابات المنطقية لكل نوع عملية (الأكواد الحالية من الدليل الحي) ──
OPERATION_ACCOUNT_MAP = {
    "sale": {
        "debit":  ["003", "004", "005", "006"],   # نقد، بنك، عملاء، POS
        "credit": ["025", "026", "027", "028", "041"],  # إيراد خدمات + قطع
    },
    "service": {
        "debit":  ["003", "004", "005", "006"],
        "credit": ["026", "027", "028"],
    },
    "purchase": {
        "debit":  ["029", "030", "035"],           # تكلفة + مصروف
        "credit": ["004", "003", "2101"],           # بنك + نقد + موردون آجل
    },
    "expense": {
        "debit":  ["034", "035", "036", "029"],
        "credit": ["003", "004", "006"],
    },
    "transfer": {
        "debit":  ["004"],
        "credit": ["003"],
    },
    "payment_order": {
        "debit":  ["005"],            # عملاء (تحصيل)
        "credit": ["003", "004", "006"],
    },
    "supplier_payment": {
        "debit":  ["2101"],           # موردون آجل
        "credit": ["003", "004"],
    },
    "credit": {                       # بيع آجل
        "debit":  ["005"],
        "credit": ["026", "027", "041"],
    },
}

ACCOUNT_NAMES = {
    "003": "النقد", "004": "البنك", "005": "العملاء (ذمم مدينة)",
    "006": "نقاط بيع", "025": "إيرادات الخدمات",
    "026": "إيرادات خدمات ميكانيكية", "027": "إيرادات إصلاح محركات",
    "028": "إيرادات فرامل وتعليق", "029": "تكلفة الخدمات",
    "030": "تكاليف مباشرة", "034": "المصروفات التشغيلية",
    "035": "مصروفات عامة وإدارية", "036": "رواتب إدارية",
    "041": "ايراد قطع الورشه", "167": "تكلفة قطع الورشة",
    "2101": "الموردون (آجل)",
}


# ── حفظ/قراءة آخر الحسابات المستخدمة (localStorage بديل) ────────────────────
def _load_last_used() -> Dict[str, List[str]]:
    try:
        if _LAST_USED_FILE.exists():
            return json.loads(_LAST_USED_FILE.read_text("utf-8"))
    except Exception:
        pass
    return {}


def _save_last_used(data: Dict[str, List[str]]) -> None:
    _LAST_USED_FILE.parent.mkdir(parents=True, exist_ok=True)
    _LAST_USED_FILE.write_text(json.dumps(data, ensure_ascii=False), "utf-8")


def _push_last_used(field_key: str, account_code: str) -> None:
    data = _load_last_used()
    lst = data.get(field_key, [])
    if account_code in lst:
        lst.remove(account_code)
    lst.insert(0, account_code)
    data[field_key] = lst[:3]
    _save_last_used(data)


# ─────────────────────────────────────────────────────────────────────────────
# 1. SMART ACCOUNTS ENDPOINT
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/accounts")
async def smart_accounts(
    operation_type: str = Query("sale"),
    field_key: str = Query("debit"),
    include_all: bool = Query(False),
):
    """
    يُعيد قائمة الحسابات المنطقية لنوع العملية مع تمييز آخر 3 حسابات مستخدمة.
    """
    # جلب كل الحسابات من Supabase
    all_accounts: List[Dict] = []
    if supabase:
        try:
            res = supabase.table("accounts").select("id,code,name,type").execute()
            all_accounts = res.data or []
        except Exception as e:
            print(f"smart_accounts: fetch failed: {e}")

    acc_by_code = {a["code"]: a for a in all_accounts if a.get("code")}

    # الأكواد المنطقية لنوع + حقل العملية
    op_map = OPERATION_ACCOUNT_MAP.get(operation_type, OPERATION_ACCOUNT_MAP["sale"])
    logical_codes = op_map.get(field_key, op_map.get("debit", []))

    # آخر 3 مستخدمة
    last_used_data = _load_last_used()
    last_codes = last_used_data.get(f"{operation_type}.{field_key}", [])

    def _build_item(code: str, recently_used: bool = False) -> Dict:
        acc = acc_by_code.get(code, {})
        return {
            "code":          code,
            "id":            acc.get("id", code),
            "name":          acc.get("name") or ACCOUNT_NAMES.get(code, code),
            "type":          acc.get("type", ""),
            "recently_used": recently_used,
        }

    seen: set = set()
    result: List[Dict] = []

    # أولاً: آخر 3 حسابات
    for code in last_codes:
        if code not in seen:
            seen.add(code)
            result.append(_build_item(code, recently_used=True))

    # ثانياً: بقية الحسابات المنطقية
    for code in logical_codes:
        if code not in seen:
            seen.add(code)
            result.append(_build_item(code))

    # اختياري: كل الحسابات (للبحث)
    if include_all:
        for acc in all_accounts:
            code = acc.get("code", "")
            if code and code not in seen:
                seen.add(code)
                result.append(_build_item(code))

    return {"success": True, "data": result}


@router.post("/accounts/track-usage")
async def track_account_usage(payload: Dict[str, Any] = Body(...)):
    """تسجيل حساب استُخدم مؤخراً."""
    operation_type = str(payload.get("operation_type", "sale"))
    field_key      = str(payload.get("field_key", ""))
    account_code   = str(payload.get("account_code", ""))
    # تجنب ازدواجية operation_type.field_key
    if field_key.startswith(f"{operation_type}."):
        full_key = field_key
    else:
        full_key = f"{operation_type}.{field_key}" if field_key else operation_type
    if full_key and account_code:
        _push_last_used(full_key, account_code)
    return {"success": True}


# ─────────────────────────────────────────────────────────────────────────────
# 2. SUPPLIER BALANCE PAYMENT
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/supplier-balance-payment")
async def supplier_balance_payment(payload: Dict[str, Any] = Body(...)):
    """
    سداد من رصيد المورد:
    - يُنشئ قيد Dr 2101 (موردون) / Cr المورد (يقلل الرصيد)
    - يُحدّث رصيد المورد في Supabase
    """
    supplier_id   = str(payload.get("supplier_id", ""))
    amount        = float(payload.get("amount", 0))
    workshop_id   = str(payload.get("workshop_id", "finmodule-sync"))
    operation_id  = str(payload.get("operation_id", ""))
    notes_text    = str(payload.get("notes", "سداد من رصيد مورد"))
    supplier_name_payload = str(payload.get("supplier_name", "")).strip()

    if not supplier_id:
        raise HTTPException(status_code=400, detail="supplier_id مطلوب")

    if amount <= 0:
        raise HTTPException(status_code=400, detail="المبلغ يجب أن يكون أكبر من صفر")

    if not supabase:
        raise HTTPException(status_code=503, detail="Supabase غير متصل")

    # جلب بيانات المورد (قد لا يكون جدول suppliers موجوداً في بعض البيئات)
    supplier = {}
    suppliers_table_available = True
    try:
        sup_res = supabase.table("suppliers").select("id,name,credit_balance,debit_balance").eq("id", supplier_id).execute()
        supplier = (sup_res.data or [{}])[0]
    except Exception as e:
        suppliers_table_available = False
        print(f"supplier_balance_payment: suppliers table unavailable ({e})")

    if not suppliers_table_available:
        raise HTTPException(
            status_code=503,
            detail="جدول الموردين غير متاح؛ تم إيقاف سداد المورد لمنع نجاح مالي دون سجل مورد حقيقي",
        )

    sup_name = supplier.get("name") or supplier_name_payload or f"مورد {supplier_id[:8]}"
    credit_bal = float(supplier.get("credit_balance") or 0)

    if suppliers_table_available and credit_bal < amount:
        raise HTTPException(
            status_code=400,
            detail=f"رصيد المورد {credit_bal:,.2f} ر.س أقل من المبلغ المطلوب {amount:,.2f} ر.س"
        )

    # إنشاء قيد محاسبي
    entry = {
        "id":          str(uuid.uuid4()),
        "workshop_id": workshop_id,
        "date":        datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "description": f"سداد من رصيد مورد — {sup_name} ({notes_text})",
        "lines": [
            {"account": "2101", "account_name": f"مورد - {sup_name}", "debit": amount, "credit": 0},
            {"account": "004",  "account_name": "البنك", "debit": 0, "credit": amount},
        ],
        "total":  amount,
        "source": "supplier_balance_payment",
        "reference_id": operation_id or None,
    }
    from core import accounting_engine
    inserted = accounting_engine.post_entry(entry, fallback=False)
    from core.journal_attribution import record_attribution
    record_attribution(inserted, entry)
    if not inserted:
        raise HTTPException(
            status_code=500,
            detail="تعذّر ترحيل قيد سداد المورد عبر المحرك المحاسبي",
        )

    # تحديث رصيد المورد إن كان جدول الموردين متاحاً
    new_credit = max(0, credit_bal - amount)
    supabase.table("suppliers").update({"credit_balance": new_credit}).eq("id", supplier_id).execute()

    invalidate_finance_caches()
    return {
        "success":          True,
        "journal_entry_id": entry["id"],
        "new_credit_balance": new_credit,
        "balance_tracking_skipped": False,
        "message": f"تم سداد {amount:,.2f} ر.س من رصيد المورد. الرصيد الجديد: {new_credit:,.2f} ر.س",
    }


@router.post("/operations/{op_id}/confirm-via-supplier-balance")
async def confirm_operation_via_supplier_balance(op_id: str, payload: Dict[str, Any] = Body(...)):
    """
    تسوية عملية آجل عبر رصيد المورد:
    - إنشاء حركة رصيد مورد (journal entry + تحديث رصيد المورد)
    - تحديث حالة العملية (paid/partial)
    """
    if not supabase:
        raise HTTPException(status_code=503, detail="Supabase غير متصل")

    op_rows = supabase.table("operations").select("*").eq("id", op_id).execute().data or []
    if not op_rows:
        raise HTTPException(status_code=404, detail="operation not found")

    op_row = op_rows[0]
    workshop_id = (
        str(payload.get("workshop_id") or payload.get("workshopId") or "")
        or str(op_row.get("workshop_id") or op_row.get("workshopId") or "")
    )
    if not workshop_id:
        raise HTTPException(status_code=400, detail="workshop_id مطلوب")

    total = float(op_row.get("total") or 0)
    if total <= 0:
        raise HTTPException(status_code=400, detail="invalid operation total")

    already_paid = 0.0
    try:
        prev = (
            supabase.table("journal_entries")
            .select("total")
            .in_("source", ["operation_payment", "supplier_balance_payment"])
            .eq("reference_id", op_id)
            .execute()
            .data
            or []
        )
        already_paid = sum(float(x.get("total") or 0) for x in prev)
    except Exception as e:
        print(f"confirm_via_supplier_balance: paid lookup failed: {e}")

    remaining = max(0.0, total - already_paid)
    if remaining <= 0.0001:
        return {
            "success": True,
            "data": {
                "paid": 0,
                "remaining": 0,
                "status": "paid",
                "payment_method": "supplier_balance",
            },
            "message": "لا يوجد رصيد متبقٍ للتسوية",
        }

    amount_raw = payload.get("amount")
    if amount_raw is None:
        pay_amount = remaining
    else:
        try:
            pay_amount = float(amount_raw)
        except Exception:
            raise HTTPException(status_code=400, detail="invalid amount")

    if pay_amount <= 0:
        raise HTTPException(status_code=400, detail="amount must be > 0")
    pay_amount = min(pay_amount, remaining)

    supplier_id = str(
        payload.get("supplier_id")
        or op_row.get("supplierId")
        or op_row.get("supplier_id")
        or (op_row.get("partnerId") if str(op_row.get("partnerType") or "").lower() == "supplier" else "")
        or ""
    )
    if not supplier_id:
        raise HTTPException(status_code=400, detail="supplier_id مطلوب للسداد عبر رصيد المورد")

    notes_text = str(payload.get("notes") or f"تسوية عملية {op_id} عبر رصيد المورد")
    settlement_result = await supplier_balance_payment({
        "supplier_id": supplier_id,
        "amount": pay_amount,
        "workshop_id": workshop_id,
        "operation_id": op_id,
        "notes": notes_text,
    })

    remaining_after = max(0.0, remaining - pay_amount)
    new_status = "paid" if remaining_after <= 0.0001 else "partial"
    new_method = "supplier_balance" if new_status == "paid" else "credit"

    update_payload = {
        "payment_method": new_method,
        "paymentMethod": new_method,
        "payment_status": new_status,
        "paymentStatus": new_status,
    }
    try:
        supabase.table("operations").update(update_payload).eq("id", op_id).execute()
    except Exception as e:
        print(f"confirm_via_supplier_balance: operation update failed: {e}")

    invalidate_finance_caches()
    return {
        "success": True,
        "data": {
            "paid": round(pay_amount, 2),
            "remaining": round(remaining_after, 2),
            "status": new_status,
            "payment_method": new_method,
            "supplier_id": supplier_id,
            "journal_entry_id": settlement_result.get("journal_entry_id") if isinstance(settlement_result, dict) else None,
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3. VEHICLE ARCHIVE
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/vehicle/{vehicle_id}/archive")
async def archive_vehicle(
    vehicle_id: str,
    payload: Dict[str, Any] = Body(default={}),
):
    """تأريخ ملف المركبة — يُحدّث حالة الزيارة/المركبة."""
    if not supabase:
        raise HTTPException(status_code=503, detail="Supabase غير متصل")

    archived_at = datetime.now(timezone.utc).isoformat()

    # جرّب تحديث الزيارة أولاً (vehicle_visits)
    for table, id_col in [("vehicle_visits", "id"), ("vehicles", "id")]:
        try:
            row = supabase.table(table).select("id,status").eq(id_col, vehicle_id).execute()
            if row.data:
                update_data = {"status": "archived"}
                # أضف archived_at فقط إذا كان العمود موجوداً
                try:
                    supabase.table(table).update({**update_data, "archived_at": archived_at}).eq(id_col, vehicle_id).execute()
                except Exception:
                    supabase.table(table).update(update_data).eq(id_col, vehicle_id).execute()
                return {
                    "success": True,
                    "vehicle_id": vehicle_id,
                    "table": table,
                    "status": "archived",
                    "archived_at": archived_at,
                }
        except Exception as e:
            print(f"archive_vehicle: {table} failed: {e}")
            continue

    # احتياطي: حفظ في ملف محلي
    archive_file = Path("/app/backend/uploads/archived_vehicles.json")
    data = {}
    if archive_file.exists():
        try:
            data = json.loads(archive_file.read_text("utf-8"))
        except Exception:
            pass
    data[vehicle_id] = {"status": "archived", "archived_at": archived_at}
    archive_file.parent.mkdir(parents=True, exist_ok=True)
    archive_file.write_text(json.dumps(data, ensure_ascii=False), "utf-8")
    return {"success": True, "vehicle_id": vehicle_id, "status": "archived", "archived_at": archived_at, "stored": "local"}


@router.get("/vehicle/{vehicle_id}/archive-status")
async def get_vehicle_archive_status(vehicle_id: str):
    """استعلام عن حالة أرشفة المركبة."""
    if not supabase:
        return {"success": True, "data": {"status": "unknown"}}
    for table in ("vehicles", "vehicle_visits"):
        try:
            res = supabase.table(table).select("id,status,archived_at").eq("id", vehicle_id).execute()
            rows = res.data or []
            if rows:
                return {"success": True, "data": rows[0]}
        except Exception:
            continue
    return {"success": True, "data": {"status": "not_found"}}
