from fastapi import APIRouter, Query, Body, HTTPException, Request
from fastapi.responses import StreamingResponse

from accounting_auditor import AccountingSystemAuditor
from bulk_delete_audit import list_bulk_delete_events, record_bulk_delete_event
import firewall_state

from datetime import datetime, timedelta, timezone
from collections import defaultdict
from typing import Optional, Dict, Any, List
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import uuid
import os
import re
import json
import io
from supabase import create_client
from motor.motor_asyncio import AsyncIOMotorClient
import openpyxl
from financial_reconciliation import build_reconciliation_audit

router = APIRouter(prefix="/api/finance", tags=["finance"])

# Supabase connections:
# - Primary (write)
# - Secondary (read) - used فقط للدمج إن كان موجود
try:
    supabase_url = os.getenv("SUPABASE_URL", "")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

    if supabase_url and supabase_key:
        supabase = create_client(supabase_url, supabase_key)
        print("✅ Supabase connected for Finance API (primary)")
    else:
        supabase = None
        print("⚠️ Supabase credentials missing (primary)")

    supabase_url_1 = os.getenv("SUPABASE_URL_1", "")
    supabase_key_1 = os.getenv("SUPABASE_SERVICE_ROLE_KEY_1", "")
    if supabase_url_1 and supabase_key_1 and supabase_url_1 != supabase_url:
        try:
            supabase_1 = create_client(supabase_url_1, supabase_key_1)
            print("✅ Supabase connected for Finance API (secondary)")
        except Exception as e:
            supabase_1 = None
            print(f"⚠️ Supabase secondary connection failed: {e}")
    else:
        supabase_1 = None
except Exception as e:
    supabase = None
    supabase_1 = None
    print(f"⚠️ Supabase connection failed: {e}")

# MongoDB connection for reading operations (financial reports)
mongo_client = None
finance_db = None


def init_mongo_connection():
    global mongo_client, finance_db

    mongo_uri = os.getenv("MONGO_URL")
    db_name = os.getenv("DB_NAME")

    # Do not attempt to connect if required config is missing
    if not mongo_uri or not db_name:
        finance_db = None
        return

    try:
        mongo_client = AsyncIOMotorClient(mongo_uri)
        finance_db = mongo_client.get_database(db_name)
        print("✅ MongoDB connected for Finance API")
    except Exception as e:
        print(f"⚠️ MongoDB connection failed: {e}")
        finance_db = None


# Initialize on module load
init_mongo_connection()

# Legacy: DB will be set from server.py (for backward compatibility)
db = None


def set_db(database):
    global db
    db = database


def _safe_float(value) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _normalize_payment_method(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""

    bank_like = {"bank", "transfer", "bank_transfer", "تحويل", "تحويل_بنكي", "تحويل بنكي", "بنك"}
    pos_like = {"card", "pos", "mada", "visa", "mastercard", "بطاقة", "بطاقه", "شبكة", "نقاط بيع", "نقاط_بيع", "point_of_sale"}
    cash_like = {"cash", "نقد", "نقدي", "كاش"}
    credit_like = {"credit", "اجل", "آجل", "unpaid", "pending", "partial"}

    if raw in credit_like:
        return "credit"
    if raw in pos_like:
        return "pos"
    if raw in bank_like:
        return "bank_transfer"
    if raw in cash_like:
        return "cash"
    return raw


def _current_live_vehicle_ids(workshop_id: Optional[str] = None) -> set:
    """Resolved live scope used by current pages: exactly vehicles not delivered.

    The two raw `archived` vehicles remain live for now because the owner confirmed
    the current active set is 15; this is a read-side filter only and does not
    mutate any vehicle status.
    """
    ids = set()
    if not supabase:
        return ids
    try:
        rows = []
        if workshop_id:
            try:
                rows = supabase.table("vehicles").select("id,status").eq("workshop_id", workshop_id).execute().data or []
            except Exception:
                rows = []
        if not rows:
            rows = supabase.table("vehicles").select("id,status").execute().data or []
        for row in rows:
            vehicle_id = str(row.get("id") or "").strip()
            status = str(row.get("status") or "").strip().lower()
            if vehicle_id and status != "delivered":
                ids.add(vehicle_id)
    except Exception as exc:
        print(f"live vehicle scope lookup failed: {exc}")
    return ids


def _operation_vehicle_map(workshop_id: Optional[str] = None) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    if not supabase:
        return mapping
    try:
        rows = []
        if workshop_id:
            try:
                rows = supabase.table("operations").select("id,vehicle_id").eq("workshop_id", workshop_id).execute().data or []
            except Exception:
                rows = []
        if not rows:
            rows = supabase.table("operations").select("id,vehicle_id").execute().data or []
        for row in rows:
            op_id = str(row.get("id") or "").strip()
            vehicle_id = str(row.get("vehicle_id") or "").strip()
            if op_id:
                mapping[op_id] = vehicle_id
    except Exception as exc:
        print(f"operation vehicle scope map failed: {exc}")
    return mapping


def _visit_vehicle_map(workshop_id: Optional[str] = None) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    if not supabase:
        return mapping
    try:
        rows = []
        if workshop_id:
            try:
                rows = supabase.table("vehicle_visits").select("id,vehicle_id").eq("workshop_id", workshop_id).execute().data or []
            except Exception:
                rows = []
        if not rows:
            rows = supabase.table("vehicle_visits").select("id,vehicle_id").execute().data or []
        for row in rows:
            visit_id = str(row.get("id") or "").strip()
            vehicle_id = str(row.get("vehicle_id") or "").strip()
            if visit_id:
                mapping[visit_id] = vehicle_id
    except Exception as exc:
        print(f"visit vehicle scope map failed: {exc}")
    return mapping


def _entry_vehicle_id(entry: Dict[str, Any], operation_map: Dict[str, str], visit_map: Dict[str, str], live_vehicle_ids: set) -> str:
    ref = str(entry.get("reference_id") or "").strip()
    vehicle_id = operation_map.get(ref) or visit_map.get(ref) or ""
    if not vehicle_id:
        desc = str(entry.get("description") or "")
        match = re.search(r"\[VISIT:([^\]]+)\]", desc, re.I)
        if match:
            vehicle_id = visit_map.get(match.group(1).strip(), "")
    if not vehicle_id and ref in live_vehicle_ids:
        vehicle_id = ref
    return vehicle_id


def _filter_live_journal_entries(entries: List[Dict[str, Any]], workshop_id: Optional[str] = None) -> List[Dict[str, Any]]:
    live_vehicle_ids = _current_live_vehicle_ids(workshop_id)
    operation_map = _operation_vehicle_map(workshop_id)
    visit_map = _visit_vehicle_map(workshop_id)
    filtered: List[Dict[str, Any]] = []
    for entry in entries or []:
        source = str(entry.get("source") or "").strip().lower()
        if source == "opening_balance_correction" or str(entry.get("reference_id") or "").startswith("opening-"):
            continue
        vehicle_id = _entry_vehicle_id(entry, operation_map, visit_map, live_vehicle_ids)
        if vehicle_id:
            if vehicle_id in live_vehicle_ids:
                filtered.append(entry)
            continue
        # Standalone/manual POS remains eligible only when it is actually posted.
        filtered.append(entry)
    return filtered


def _filter_live_operations(rows: List[Dict[str, Any]], workshop_id: Optional[str] = None, *, keep_standalone: bool = True) -> List[Dict[str, Any]]:
    live_vehicle_ids = _current_live_vehicle_ids(workshop_id)
    filtered: List[Dict[str, Any]] = []
    for row in rows or []:
        vehicle_id = str(row.get("vehicle_id") or row.get("vehicleId") or "").strip()
        if vehicle_id:
            if vehicle_id in live_vehicle_ids:
                filtered.append(row)
        elif keep_standalone:
            filtered.append(row)
    return filtered


def _live_ar_balances_by_customer(workshop_id: str, end_date: Optional[str] = None) -> Dict[str, Any]:
    entries = _fetch_journal_entries(workshop_id, end_date=end_date, limit=10000, include_rakan=False)
    entries = _filter_live_journal_entries(entries, workshop_id)
    operations = {str(row.get("id") or "").strip(): row for row in (supabase.table("operations").select("id,partner_name,vehicle_id,visit_id,total").execute().data or []) if row.get("id")}
    visits = {str(row.get("id") or "").strip(): row for row in (supabase.table("vehicle_visits").select("id,vehicle_id").execute().data or []) if row.get("id")}
    vehicles = {str(row.get("id") or "").strip(): row for row in (supabase.table("vehicles").select("id,customer_name,plate_number,status").execute().data or []) if row.get("id")}
    op_vehicle = {op_id: str(row.get("vehicle_id") or "").strip() for op_id, row in operations.items()}
    visit_vehicle = {visit_id: str(row.get("vehicle_id") or "").strip() for visit_id, row in visits.items()}
    balances: Dict[str, float] = defaultdict(float)
    rows: List[Dict[str, Any]] = []
    for entry in entries:
        amount = 0.0
        for line in entry.get("lines") or []:
            if str(line.get("account") or line.get("code") or "").strip() in {"005", "1103", "113"}:
                amount += _safe_float(line.get("debit")) - _safe_float(line.get("credit"))
        if abs(amount) < 0.005:
            continue
        ref = str(entry.get("reference_id") or "").strip()
        vehicle_id = op_vehicle.get(ref) or visit_vehicle.get(ref) or ""
        if not vehicle_id:
            desc = str(entry.get("description") or "")
            match = re.search(r"\[VISIT:([^\]]+)\]", desc, re.I)
            if match:
                vehicle_id = visit_vehicle.get(match.group(1).strip(), "")
        vehicle = vehicles.get(vehicle_id, {})
        customer = (operations.get(ref, {}).get("partner_name") or vehicle.get("customer_name") or "غير محدد").strip() or "غير محدد"
        balances[customer] += amount
        rows.append({
            "journal_entry_id": entry.get("id"),
            "date": entry.get("date"),
            "reference_id": ref,
            "vehicle_id": vehicle_id,
            "customer": customer,
            "amount": round(amount, 2),
            "source": entry.get("source"),
            "description": entry.get("description"),
        })
    customers = [
        {"customer": name, "balance": round(balance, 2)}
        for name, balance in sorted(balances.items())
        if abs(balance) >= 0.01
    ]
    total_ar = round(sum(row["balance"] for row in customers), 2)
    return {"total_ar": total_ar, "customers": customers, "ledger_rows": rows}


def _parse_json_notes(notes: Any) -> Dict[str, Any]:
    if isinstance(notes, dict):
        return notes
    if isinstance(notes, str):
        raw = notes.strip()
        if raw.startswith("{") and raw.endswith("}"):
            try:
                parsed = json.loads(raw)
                return parsed if isinstance(parsed, dict) else {}
            except Exception:
                return {}
    return {}


def _visit_item_totals(notes: Any) -> Dict[str, float]:
    parsed = _parse_json_notes(notes)
    workshop = 0.0
    suppliers = 0.0
    for item in parsed.get("items") or []:
        if not isinstance(item, dict):
            continue
        qty = _safe_float(item.get("quantity") or item.get("qty") or 1) or 1.0
        price = _safe_float(item.get("price") or item.get("unit_price") or item.get("amount") or 0)
        total = _safe_float(item.get("total")) or round(qty * price, 2)
        item_type = str(item.get("itemType") or item.get("type") or "").strip().lower()
        billing_type = str(item.get("billingType") or item.get("billing_type") or "").strip().lower()
        if item_type == "supplier" or billing_type == "supplier":
            suppliers += total
        else:
            workshop += total
    return {"workshop": round(workshop, 2), "suppliers": round(suppliers, 2)}


def _confirmed_payment_amount(entry: Dict[str, Any]) -> float:
    amount = 0.0
    for line in entry.get("lines") or []:
        code = str(line.get("account") or line.get("code") or line.get("account_code") or "").strip()
        if code in {"005", "1103", "113"}:
            amount += max(_safe_float(line.get("credit")) - _safe_float(line.get("debit")), 0.0)
    if amount > 0:
        return round(amount, 2)
    return round(_safe_float(entry.get("total")), 2)


def build_current_visit_ar_snapshot(workshop_id: str = "finmodule-sync", end_date: Optional[str] = None) -> Dict[str, Any]:
    """Current AR from vehicle visits only: workshop items - confirmed journal payments.

    This intentionally ignores supplier items and unposted payments stored in notes.
    It does not create or mutate journal entries/operations.
    """
    if not supabase:
        return {"total_ar": 0.0, "customers": [], "vehicles": [], "ledger_rows": []}

    vehicles = supabase.table("vehicles").select("id,customer_name,plate_number,status,entry_date").execute().data or []
    visits = supabase.table("vehicle_visits").select("id,vehicle_id,status,notes,entry_date,created_at").execute().data or []
    operations = supabase.table("operations").select("id,vehicle_id,visit_id,partner_name,total,payment_method").execute().data or []
    entries = _fetch_journal_entries(workshop_id, end_date=end_date, limit=10000, include_rakan=False)

    vehicle_by_id = {str(v.get("id") or "").strip(): v for v in vehicles if v.get("id")}
    visits_by_vehicle: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    ops_by_visit: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for visit in visits:
        visits_by_vehicle[str(visit.get("vehicle_id") or "").strip()].append(visit)
    for op in operations:
        visit_id = str(op.get("visit_id") or "").strip()
        if visit_id:
            ops_by_visit[visit_id].append(op)

    refs_by_visit: Dict[str, set] = defaultdict(set)
    for visit in visits:
        visit_id = str(visit.get("id") or "").strip()
        if visit_id:
            refs_by_visit[visit_id].add(visit_id)
    for op in operations:
        visit_id = str(op.get("visit_id") or "").strip()
        op_id = str(op.get("id") or "").strip()
        if visit_id and op_id:
            refs_by_visit[visit_id].add(op_id)

    payments_by_ref: Dict[str, float] = defaultdict(float)
    payment_method_by_ref: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for entry in entries:
        source = str(entry.get("source") or "").strip().lower()
        if source not in {"operation_payment", "payment"}:
            continue
        ref = str(entry.get("reference_id") or "").strip()
        if not ref:
            continue
        amount = _confirmed_payment_amount(entry)
        if amount <= 0:
            continue
        payments_by_ref[ref] += amount
        method = "unknown"
        for line in entry.get("lines") or []:
            code = str(line.get("account") or line.get("code") or "").strip()
            if _safe_float(line.get("debit")) <= 0:
                continue
            if code in {"003", "1101"}:
                method = "cash"
            elif code in {"006", "1104"}:
                method = "pos"
            elif code in {"004", "1102"}:
                method = "bank_transfer"
        payment_method_by_ref[ref][method] += amount

    live_vehicles = [v for v in sorted(vehicles, key=lambda r: str(r.get("entry_date") or ""), reverse=True) if str(v.get("status") or "").strip().lower() != "delivered"]
    customer_balances: Dict[str, float] = defaultdict(float)
    ledger_rows: List[Dict[str, Any]] = []
    vehicle_rows: List[Dict[str, Any]] = []
    totals = {"workshop_total": 0.0, "confirmed_paid": 0.0, "receivable": 0.0, "supplier_total": 0.0, "cash": 0.0, "pos": 0.0, "bank_transfer": 0.0}

    for vehicle in live_vehicles:
        vehicle_id = str(vehicle.get("id") or "").strip()
        status = str(vehicle.get("status") or "").strip().lower()
        excluded = status in {"archived", "delivered"}
        customer = str(vehicle.get("customer_name") or "غير محدد").strip() or "غير محدد"
        vehicle_workshop = 0.0
        vehicle_suppliers = 0.0
        vehicle_confirmed = 0.0
        visit_rows = []

        for visit in visits_by_vehicle.get(vehicle_id, []):
            visit_id = str(visit.get("id") or "").strip()
            item_totals = _visit_item_totals(visit.get("notes"))
            refs = refs_by_visit.get(visit_id, {visit_id})
            confirmed = round(sum(payments_by_ref.get(ref, 0.0) for ref in refs), 2)
            by_method = defaultdict(float)
            for ref in refs:
                for method, amount in payment_method_by_ref.get(ref, {}).items():
                    by_method[method] += amount
            if not excluded:
                totals["cash"] += by_method.get("cash", 0.0)
                totals["pos"] += by_method.get("pos", 0.0)
                totals["bank_transfer"] += by_method.get("bank_transfer", 0.0)
            remaining = max(item_totals["workshop"] - confirmed, 0.0)
            vehicle_workshop += item_totals["workshop"]
            vehicle_suppliers += item_totals["suppliers"]
            vehicle_confirmed += confirmed
            visit_rows.append({
                "visit_id": visit_id,
                "status": visit.get("status"),
                "workshop_amount": item_totals["workshop"],
                "supplier_amount": item_totals["suppliers"],
                "confirmed_paid": confirmed,
                "remaining": round(remaining, 2),
                "classification": "آجل — غير مسدد" if item_totals["workshop"] > 0 and confirmed <= 0 else ("سداد جزئي" if remaining > 0 else "مسدد بالكامل"),
                "operation_ids": [str(op.get("id")) for op in ops_by_visit.get(visit_id, []) if op.get("id")],
            })

        vehicle_remaining = max(vehicle_workshop - vehicle_confirmed, 0.0)
        if excluded:
            receivable = 0.0
            reason = "مركبة مؤرشفة/مسلمة لا تدخل في الذمم الحالية"
        elif vehicle_workshop <= 0:
            receivable = 0.0
            reason = "لا توجد بنود ورشة"
        else:
            receivable = round(vehicle_remaining, 2)
            reason = "بنود الورشة - قيود السداد المؤكدة"
            customer_balances[customer] += receivable
            if receivable > 0:
                ledger_rows.append({
                    "date": str((visits_by_vehicle.get(vehicle_id) or [{}])[0].get("entry_date") or ""),
                    "customer": customer,
                    "vehicle_id": vehicle_id,
                    "reference_id": vehicle_id,
                    "amount": receivable,
                    "description": reason,
                })

        if not excluded:
            totals["workshop_total"] += vehicle_workshop
            totals["supplier_total"] += vehicle_suppliers
            totals["confirmed_paid"] += vehicle_confirmed
            totals["receivable"] += receivable

        vehicle_rows.append({
            "vehicle_id": vehicle_id,
            "customer": customer,
            "plate": vehicle.get("plate_number"),
            "raw_status": vehicle.get("status"),
            "included_in_current_ar": not excluded,
            "exclusion_reason": reason if excluded or vehicle_workshop <= 0 else "",
            "workshop_amount": round(vehicle_workshop, 2),
            "supplier_amount": round(vehicle_suppliers, 2),
            "confirmed_paid": round(vehicle_confirmed, 2),
            "receivable": round(receivable, 2),
            "visits": visit_rows,
        })

    customers = [{"customer": name, "balance": round(balance, 2)} for name, balance in sorted(customer_balances.items()) if balance > 0.005]
    return {
        "total_ar": round(sum(row["balance"] for row in customers), 2),
        "customers": customers,
        "vehicles": vehicle_rows,
        "ledger_rows": ledger_rows,
        "totals": {key: round(value, 2) for key, value in totals.items()},
    }


def _extract_request_actor(request: Optional[Request]) -> Dict[str, str]:
    # 🔐 سمات التدقيق تُشتقّ من JWT الموقَّع (لا الترويسات القابلة للانتحال)
    ident = {}
    try:
        from auth_jwt import identity_from_request
        ident = identity_from_request(request) if request else {}
    except Exception:
        ident = {}
    user_id = str(ident.get("username") or "system").strip() or "system"
    user_role = str(ident.get("role") or "unknown").strip() or "unknown"
    return {"user_id": user_id, "user_role": user_role}


def _require_reconciliation_admin(request: Request) -> Dict[str, str]:
    actor = _extract_request_actor(request)
    role = str(actor.get("user_role") or "").strip().lower()
    user_id = str(actor.get("user_id") or "").strip()
    allowed_roles = {"admin", "manager", "system_manager", "مدير", "مدير النظام"}
    if role not in allowed_roles and user_id != "مدير":
        raise HTTPException(status_code=403, detail={"error": "permission_denied", "msg": "تقرير المصالحة المالي متاح للمدير أو مدير النظام فقط", "role": role or "unknown"})
    return actor


def _count_value(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 2)
    return value


@router.get("/reconciliation-audit")
async def get_financial_reconciliation_audit(
    request: Request,
    workshop_id: str = Query("finmodule-sync", description="معرف الورشة"),
):
    _require_reconciliation_admin(request)
    if not supabase:
        raise HTTPException(status_code=503, detail="Supabase not connected")
    try:
        return build_reconciliation_audit(supabase, workshop_id=workshop_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"reconciliation_audit_failed: {str(exc)[:200]}") from exc


def _normalize_date_string(value: Optional[str]) -> Optional[str]:
    if not value:
        return value
    raw = str(value).strip()
    if not raw:
        return raw

    # already ISO date-like
    if len(raw) >= 10 and raw[4] == "-" and raw[7] == "-":
        return raw[:10]

    for fmt in ("%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except Exception:
            continue
    return raw

# الأكواد الجديدة + القديمة للتوافق مع السجلات التاريخية
AR_ACCOUNT_CODES = {"005", "1103", "113"}   # العملاء (ذمم مدينة)
AP_ACCOUNT_CODES = {"2101", "211"}           # الموردون (ذمم دائنة)
CASH_ACCOUNT_CODES = {"003", "1101"}         # النقد
BANK_ACCOUNT_CODES = {"004", "1102", "006", "1104"}  # البنك + نقاط بيع

# خريطة التحويل من legacy إلى جديد (يُستخدم في القراءة والكتابة) — مطابقة لجدول accounts الحي
_LEGACY_CODE_MAP = {
    "1101": "003", "1102": "004", "1103": "005", "1104": "006",
    "1105": "007", "1106": "008",
    "4000": "024", "4100": "025", "4101": "026", "4102": "027", "4103": "028",
    "5000": "029", "5100": "030", "5101": "031", "5102": "032", "5103": "033",
    "6000": "034", "6100": "035", "6101": "036", "6102": "037",
    "3102": "021", "1201": "010",
    "042": "041", "0421": "167", "211": "166",
}

def _to_new_code(code: str) -> str:
    """تحويل الكود القديم إلى الجديد إذا كان موجوداً في الخريطة."""
    return _LEGACY_CODE_MAP.get(str(code or "").strip(), str(code or "").strip())


def _infer_account_type_from_code(code: str) -> str:
    c = str(code or "").strip()
    try:
        numeric = int(c)
    except (ValueError, TypeError):
        return "other"
    # أكواد حالية (مطابقة لجدول accounts الحي بعد إعادة الترقيم)
    if numeric == 41:
        return "revenue"   # ايراد قطع الورشه
    if 1 <= numeric <= 13:
        return "asset"
    if 14 <= numeric <= 17:
        return "liability"
    if 18 <= numeric <= 23:
        return "equity"
    if 24 <= numeric <= 28:
        return "revenue"
    if 29 <= numeric <= 48:
        return "expense"
    if 49 <= numeric <= 128:
        return "asset"      # حسابات العملاء الفرعية
    if 129 <= numeric <= 165:
        return "liability"  # حسابات الموردين الفرعية
    if numeric == 166:
        return "equity"     # حساب فروقات ترحيل
    if numeric == 167:
        return "expense"    # تكلفة قطع الورشة
    if numeric == 211:
        return "equity"
    if 2101 <= numeric <= 2199:
        return "liability"
    if numeric >= 21010000:
        return "liability"  # حسابات موردين فرعية (2101xxxx)
    # أكواد قديمة (legacy)
    if 1000 <= numeric <= 1999:
        return "asset"
    if 2000 <= numeric <= 2999:
        return "liability"
    if 3000 <= numeric <= 3999:
        return "equity"
    if 4000 <= numeric <= 4999:
        return "revenue"
    if 5000 <= numeric <= 6999:
        return "expense"
    return "other"


RAKAN_ACCOUNT_CODE_PREFIX = "5000"


def _normalize_account_code(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if raw.startswith("acc-") and raw[4:].isdigit():
        return raw[4:]
    return raw


def _is_rakan_account_code(value: Any) -> bool:
    # 🔥 Rakan logic permanently removed (Feb 2026) — always returns False.
    return False


def _line_account_code(line: Dict[str, Any], id_to_code: Dict[str, str]) -> str:
    account_code = line.get("account") or line.get("account_code") or line.get("code")
    if not account_code:
        account_id = line.get("account_id") or line.get("accountId")
        if account_id:
            account_code = id_to_code.get(str(account_id)) or account_id
    return _normalize_account_code(account_code)


def _is_rakan_journal_entry(entry: Dict[str, Any], id_to_code: Dict[str, str]) -> bool:
    # 🔥 Rakan logic permanently removed (Feb 2026) — always returns False.
    return False


_ACCOUNT_ALIAS_CACHE: Dict[str, str] = {}
_ACCOUNT_ALIAS_CACHE_AT: float = 0.0

# In-memory TTL caches for hot endpoints (accounts/tree, reports).
_ACCOUNTS_CACHE: List[Dict[str, Any]] = []
_ACCOUNTS_CACHE_AT: float = 0.0
_ACCOUNTS_CACHE_TTL: float = 10.0  # seconds

_JOURNAL_CACHE: Dict[str, tuple] = {}  # key -> (cached_at, rows)
_JOURNAL_CACHE_TTL: float = 5.0  # seconds


def invalidate_finance_caches():
    """Invalidate in-memory caches. Called after writes (journal entry create/update/delete)."""
    global _ACCOUNTS_CACHE_AT, _JOURNAL_CACHE, _ACCOUNT_ALIAS_CACHE_AT, _OPERATIONS_CACHE
    _ACCOUNTS_CACHE_AT = 0.0
    _ACCOUNT_ALIAS_CACHE_AT = 0.0
    _JOURNAL_CACHE = {}
    _OPERATIONS_CACHE = {}


def _fetch_account_code_aliases() -> Dict[str, str]:
    """Sync read of account_code_aliases (account_id -> legacy_code).
    Tries MongoDB first then falls back to the on-disk JSON used by routes_extended.
    Cached for 30 seconds to avoid hitting Mongo per request."""
    global _ACCOUNT_ALIAS_CACHE, _ACCOUNT_ALIAS_CACHE_AT
    import time
    now = time.time()
    if _ACCOUNT_ALIAS_CACHE and (now - _ACCOUNT_ALIAS_CACHE_AT) < 30:
        return _ACCOUNT_ALIAS_CACHE

    out: Dict[str, str] = {}

    # 1) Try MongoDB
    try:
        from pymongo import MongoClient
        mongo_uri = os.getenv("MONGO_URL")
        db_name = os.getenv("DB_NAME")
        if mongo_uri and db_name:
            client = MongoClient(mongo_uri, serverSelectionTimeoutMS=2000)
            db_local = client[db_name]
            rows = list(db_local["account_code_aliases"].find({}, {"_id": 0}))
            client.close()
            for row in rows:
                if row.get("accountId") and row.get("legacyCode"):
                    out[str(row["accountId"])] = str(row["legacyCode"])
    except Exception as e:
        print(f"_fetch_account_code_aliases (mongo) failed: {e}")

    # 2) Fallback to on-disk JSON (used by routes_extended _mem_read)
    if not out:
        try:
            p = os.path.join(os.path.dirname(__file__), "uploads", "account_code_aliases.json")
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    rows = json.load(f) or []
                for row in rows:
                    if row.get("accountId") and row.get("legacyCode"):
                        out[str(row["accountId"])] = str(row["legacyCode"])
        except Exception as e:
            print(f"_fetch_account_code_aliases (file) failed: {e}")

    _ACCOUNT_ALIAS_CACHE = out
    _ACCOUNT_ALIAS_CACHE_AT = now
    return out


def _fetch_accounts():
    if not supabase:
        raise Exception("Supabase not connected")

    # Try TTL cache first (accounts list changes rarely — 10s TTL is safe)
    global _ACCOUNTS_CACHE, _ACCOUNTS_CACHE_AT
    import time
    now_ts = time.time()
    if _ACCOUNTS_CACHE and (now_ts - _ACCOUNTS_CACHE_AT) < _ACCOUNTS_CACHE_TTL:
        return _ACCOUNTS_CACHE

    primary_accounts = []
    secondary_accounts = []

    try:
        res = supabase.table("accounts").select("*").order("code").execute()
        primary_accounts = res.data or []
    except Exception as e:
        print(f"Primary accounts fetch failed: {e}")

    if supabase_1 is not None:
        try:
            res2 = (
                supabase_1.table("chart_of_accounts").select("*").order("code").execute()
            )
            secondary_accounts = res2.data or []
        except Exception as e:
            print(f"Secondary chart_of_accounts fetch failed: {e}")

        if not secondary_accounts:
            try:
                res3 = (
                    supabase_1.table("business_accounts").select("*").order("code").execute()
                )
                secondary_accounts = res3.data or []
            except Exception as e:
                print(f"Secondary business_accounts fetch failed: {e}")

    merged = []
    seen_codes = set()

    def add_list(lst):
        for a in (lst or []):
            if not isinstance(a, dict):
                continue
            code = str(a.get("code") or "").strip()
            if not code or code in seen_codes:
                continue

            seen_codes.add(code)
            if not a.get("name_ar"):
                a["name_ar"] = a.get("name")
            merged.append(a)

    # عند وجود بيانات أساسية من Supabase، لا ندمج نسخة Mongo القديمة لتفادي ظهور أكواد legacy.
    if primary_accounts:
        add_list(primary_accounts)
    else:
        add_list(secondary_accounts)

    # Hydrate legacy_code from MongoDB account_code_aliases (account_id -> legacy_code)
    # so trial-balance / balance-sheet can map old journal lines (1102, 1101 ...)
    # to the current sequential codes (004, 003 ...).
    aliases = _fetch_account_code_aliases()
    if aliases:
        for acc in merged:
            aid = str(acc.get("id") or "").strip()
            if aid and aid in aliases and not acc.get("legacy_code"):
                acc["legacy_code"] = aliases[aid]

    # Populate cache
    _ACCOUNTS_CACHE = merged
    _ACCOUNTS_CACHE_AT = now_ts

    return merged


def _build_account_maps(accounts):
    id_to_code = {}
    code_to_name = {}
    code_to_type = {}
    legacy_to_current = {}
    for acc in accounts or []:
        code = str(acc.get("code") or "").strip()
        if not code:
            continue
        code_to_name[code] = acc.get("name_ar") or acc.get("name") or code
        if acc.get("id"):
            id_to_code[str(acc.get("id"))] = code
        if acc.get("type"):
            code_to_type[code] = acc.get("type")
        legacy = str(acc.get("legacy_code") or "").strip()
        if legacy and legacy != code:
            legacy_to_current[legacy] = code
    # Stash legacy map in id_to_code under a reserved key for backward compatibility
    # so callers that only consume id_to_code still get legacy lookups via the same dict.
    for legacy_code, current_code in legacy_to_current.items():
        # Only add if not already mapped as an id (avoid collisions)
        # Note: If the ID is acc-4100 but legacy_code is 4100, we need to map BOTH
        # to the current_code, since acc-4100 is just the internal ID.
        id_to_code[legacy_code] = current_code
        id_to_code[f"acc-{legacy_code}"] = current_code
    return id_to_code, code_to_name, code_to_type


def _normalize_line(line, id_to_code, code_to_name):
    if not isinstance(line, dict):
        return None
    account_code = line.get("account") or line.get("account_code") or line.get("code")
    if not account_code:
        account_id = line.get("account_id") or line.get("accountId")
        if account_id:
            account_code = id_to_code.get(str(account_id))
    if not account_code:
        return None
    account_code = str(account_code)
    # Map account IDs OR legacy codes to current codes via id_to_code
    # (legacy codes are injected into id_to_code by _build_account_maps).
    if account_code in id_to_code:
        account_code = id_to_code[account_code]
    account_code = _normalize_account_code(account_code)
    account_name = (
        line.get("account_name")
        or line.get("accountName")
        or code_to_name.get(account_code)
        or account_code
    )
    debit = _safe_float(
        line.get("debit")
        if line.get("debit") is not None
        else line.get("debit_amount") or line.get("debitAmount")
    )
    credit = _safe_float(
        line.get("credit")
        if line.get("credit") is not None
        else line.get("credit_amount") or line.get("creditAmount")
    )
    return {
        "account": account_code,
        "account_name": account_name,
        "code": account_code,
        "name": account_name,
        "debit": debit,
        "credit": credit,
    }


def _fetch_journal_entries(
    workshop_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    skip: int = 0,
    limit: Optional[int] = None,
    include_rakan: bool = False,
):
    if not supabase:
        raise Exception("Supabase not connected")

    # Cache raw Supabase fetch (before rakan filter) keyed on query params.
    global _JOURNAL_CACHE
    import time
    now_ts = time.time()
    cache_key = f"{workshop_id}|{start_date or ''}|{end_date or ''}|{skip}|{limit}"
    cached = _JOURNAL_CACHE.get(cache_key)
    if cached and (now_ts - cached[0]) < _JOURNAL_CACHE_TTL:
        rows = cached[1]
    else:
        query = (
            supabase.table("journal_entries")
            .select("*")
            .eq("workshop_id", workshop_id)
            .neq("workshop_id", None)
        )
        normalized_start = _normalize_date_string(start_date)
        normalized_end = _normalize_date_string(end_date)

        if normalized_start:
            query = query.gte("date", normalized_start)
        if normalized_end:
            query = query.lte("date", normalized_end)
        if limit is not None:
            query = query.range(skip, skip + limit - 1)
        rows = query.order("date", desc=True).execute().data or []
        _JOURNAL_CACHE[cache_key] = (now_ts, rows)
        # Opportunistically purge stale entries to keep memory small.
        if len(_JOURNAL_CACHE) > 32:
            stale = [k for k, v in _JOURNAL_CACHE.items() if (now_ts - v[0]) >= _JOURNAL_CACHE_TTL]
            for k in stale:
                _JOURNAL_CACHE.pop(k, None)

    if include_rakan:
        return rows

    try:
        accounts = _fetch_accounts()
        id_to_code, _, _ = _build_account_maps(accounts)
    except Exception:
        id_to_code = {}

    return [
        entry
        for entry in rows
        if not _is_rakan_journal_entry(entry, id_to_code)
    ]


def _compute_trial_balance_map(
    workshop_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    include_rakan: bool = False,
):
    accounts = _fetch_accounts()
    id_to_code, code_to_name, _ = _build_account_maps(accounts)
    entries = _fetch_journal_entries(
        workshop_id,
        start_date=start_date,
        end_date=end_date,
        limit=10000,
        include_rakan=include_rakan,
    )
    entries = _filter_live_journal_entries(entries, workshop_id)
    accounts_balances = {}
    for entry in entries:
        for line in entry.get("lines", []) or []:
            normalized = _normalize_line(line, id_to_code, code_to_name)
            if not normalized:
                continue
            code = normalized["code"]
            if code not in accounts_balances:
                accounts_balances[code] = {
                    "name": normalized["name"],
                    "debit": 0,
                    "credit": 0,
                }
            accounts_balances[code]["debit"] += normalized["debit"]
            accounts_balances[code]["credit"] += normalized["credit"]
    return accounts_balances, accounts


@router.get("/reports/balance-sheet")
async def get_balance_sheet(
    workshop_id: str = Query(..., description="معرف الورشة"),
    as_of_date: Optional[str] = Query(None, description="تاريخ التقرير (YYYY-MM-DD)"),
):
    """
    الميزانية العمومية - محسوبة من دليل الحسابات
    """
    try:
        target_date = _normalize_date_string(as_of_date) or datetime.now().strftime("%Y-%m-%d")
        balances_map, accounts = _compute_trial_balance_map(
            workshop_id,
            end_date=target_date,
            include_rakan=False,
        )
        _, code_to_name, code_to_type = _build_account_maps(accounts)

        assets_accounts = []
        liabilities_accounts = []
        equity_accounts = []
        net_income_period = 0.0

        for code, row in balances_map.items():
            debit = _safe_float(row.get("debit"))
            credit = _safe_float(row.get("credit"))

            acc_type = code_to_type.get(code) or _infer_account_type_from_code(code)
            if acc_type == "asset":
                balance = debit - credit
            elif acc_type in {"liability", "equity"}:
                balance = credit - debit
            elif acc_type == "revenue":
                net_income_period += credit - debit
                continue
            elif acc_type == "expense":
                net_income_period -= debit - credit
                continue
            else:
                continue

            if abs(balance) < 0.0001:
                continue

            account_data = {
                "id": code,
                "code": code,
                "name": row.get("name") or code_to_name.get(code) or code,
                "balance": round(abs(balance), 2),
            }

            if acc_type == "asset":
                assets_accounts.append(account_data)
            elif acc_type == "liability":
                liabilities_accounts.append(account_data)
            else:
                equity_accounts.append(account_data)

        total_assets = sum(acc["balance"] for acc in assets_accounts)
        total_liabilities = sum(acc["balance"] for acc in liabilities_accounts)
        total_equity = sum(acc["balance"] for acc in equity_accounts)

        # صافي دخل الفترة يُرحَّل لحقوق الملكية (توازن الميزانية: أصول = خصوم + حقوق)
        if abs(net_income_period) >= 0.005:
            equity_accounts.append({
                "id": "023",
                "code": "023",
                "name": "صافي الربح/الخسارة (الفترة)",
                "balance": round(net_income_period, 2),
            })
            total_equity += net_income_period
        
        return {
            "success": True,
            "data": {
                "as_of": target_date,
                "totals": {
                    "assets": round(total_assets, 2),
                    "liabilities": round(total_liabilities, 2),
                    "equity": round(total_equity, 2),
                    "liabilities_plus_equity": round(total_liabilities + total_equity, 2),
                },
                "sections": {
                    "assets": assets_accounts,
                    "liabilities": liabilities_accounts,
                    "equity": equity_accounts,
                },
            },
        }
    
    except Exception as e:
        print(f"Balance sheet error: {e}")
        return {
            "success": False,
            "message": f"خطأ في حساب الميزانية: {str(e)}",
            "data": {
                "as_of": target_date if 'target_date' in locals() else datetime.now().strftime("%Y-%m-%d"),
                "totals": {"assets": 0, "liabilities": 0, "equity": 0, "liabilities_plus_equity": 0},
                "sections": {"assets": [], "liabilities": [], "equity": []},
            },
        }



@router.get("/reports/income-statement")
async def get_income_statement(
    workshop_id: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    """
    قائمة الدخل محسوبة من دليل الحسابات
    """
    try:
        effective_workshop_id = workshop_id or os.environ.get("DEFAULT_WORKSHOP_ID")
        if not effective_workshop_id:
            raise HTTPException(status_code=400, detail="معرف الورشة مطلوب")

        end_date = _normalize_date_string(end_date) or datetime.now().strftime("%Y-%m-%d")
        start_date = _normalize_date_string(start_date)

        accounts = _fetch_accounts()
        id_to_code, code_to_name, code_to_type = _build_account_maps(accounts)
        entries = _fetch_journal_entries(
            effective_workshop_id,
            start_date=start_date,
            end_date=end_date,
            limit=10000,
            include_rakan=False,
        )
        entries = _filter_live_journal_entries(entries, effective_workshop_id)

        references_with_base_entries = {
            str(entry.get("reference_id") or "").strip()
            for entry in entries
            if str(entry.get("reference_id") or "").strip()
            and str(entry.get("source") or "").strip().lower()
            not in {"operation_payment"}
        }

        revenue_accounts: Dict[str, Dict[str, Any]] = {}
        expense_accounts: Dict[str, Dict[str, Any]] = {}

        for entry in entries:
            entry_source = str(entry.get("source") or "").strip().lower()
            entry_reference = str(entry.get("reference_id") or "").strip()
            # 🧾 قيود إقفال الفترة تُستثنى من حساب الإيراد/المصروف لأنها تحويلات
            # للأرباح المحتجزة وليست حركة فعلية. الأرصدة المتأثرة تظهر صفراً
            # في الحسابات (balance=0) — أما قائمة الدخل فتعرض حركة فعلية فقط.
            if entry_source == "period_close":
                continue
            for line in entry.get("lines", []) or []:
                normalized = _normalize_line(line, id_to_code, code_to_name)
                if not normalized:
                    continue

                code = normalized["code"]
                acc_type = code_to_type.get(code) or _infer_account_type_from_code(code)
                debit = _safe_float(normalized.get("debit"))
                credit = _safe_float(normalized.get("credit"))
                name = normalized.get("name") or code_to_name.get(code) or code

                if acc_type == "revenue":
                    amount = credit - debit
                    if code not in revenue_accounts:
                        revenue_accounts[code] = {"name": name, "amount": 0.0}
                    revenue_accounts[code]["amount"] += amount
                elif acc_type == "expense":
                    amount = debit - credit
                    if code not in expense_accounts:
                        expense_accounts[code] = {"name": name, "amount": 0.0}
                    expense_accounts[code]["amount"] += amount

        revenue_accounts = {
            code: {"name": data["name"], "amount": round(float(data["amount"]), 2)}
            for code, data in revenue_accounts.items()
            if abs(float(data.get("amount") or 0)) >= 0.0001
        }
        expense_accounts = {
            code: {"name": data["name"], "amount": round(float(data["amount"]), 2)}
            for code, data in expense_accounts.items()
            if abs(float(data.get("amount") or 0)) >= 0.0001
        }

        total_revenue = sum(float(v.get("amount") or 0) for v in revenue_accounts.values())
        total_expenses = sum(float(v.get("amount") or 0) for v in expense_accounts.values())

        operations_cash_total = 0.0
        operations_bank_total = 0.0
        operations_pos_total = 0.0
        operations_credit_total = 0.0
        operations_sales_total = 0.0
        operations_sales_count = 0

        # لا نسمح لفشل fetch ثانوي (sales summary) بإرجاع التقرير كاملًا بصفر.
        try:
            visit_ar = build_current_visit_ar_snapshot(effective_workshop_id, end_date=end_date)
            visit_totals = visit_ar.get("totals") or {}
            operations_sales_total = _safe_float(visit_totals.get("workshop_total"))
            operations_sales_count = sum(1 for row in visit_ar.get("vehicles") or [] if _safe_float(row.get("workshop_amount")) > 0 and row.get("included_in_current_ar"))
            operations_credit_total = _safe_float(visit_totals.get("receivable"))
            operations_cash_total = _safe_float(visit_totals.get("cash"))
            operations_bank_total = _safe_float(visit_totals.get("bank_transfer"))
            operations_pos_total = _safe_float(visit_totals.get("pos"))
        except Exception as operations_error:
            print(f"Income statement sales summary skipped: {operations_error}")
        
        net_income = total_revenue - total_expenses
        
        return {
            "success": True,
            "data": {
                "period": {"start_date": start_date, "end_date": end_date},
                "totals": {
                    "revenue": round(total_revenue, 2),
                    "expenses": round(total_expenses, 2),
                    "net_income": round(net_income, 2),
                },
                "sales_summary": {
                    "operations_total": round(operations_sales_total, 2),
                    "operations_count": int(operations_sales_count),
                    "operations_cash_total": round(operations_cash_total, 2),
                    "operations_bank_total": round(operations_bank_total, 2),
                    "operations_bank_transfer_total": round(operations_bank_total, 2),
                    "operations_pos_total": round(operations_pos_total, 2),
                    "operations_credit_total": round(operations_credit_total, 2),
                },
                "details": {
                    "revenue_by_account": revenue_accounts,
                    "expenses_by_account": expense_accounts,
                },
            },
        }
    
    except Exception as e:
        print(f"Income statement error: {e}")
        return {
            "success": False,
            "message": f"خطأ في حساب قائمة الدخل: {str(e)}",
            "data": {
                "period": {"start_date": start_date, "end_date": end_date},
                "totals": {"revenue": 0, "expenses": 0, "net_income": 0},
                "sales_summary": {
                    "operations_total": 0,
                    "operations_count": 0,
                    "operations_cash_total": 0,
                    "operations_bank_total": 0,
                    "operations_bank_transfer_total": 0,
                    "operations_pos_total": 0,
                    "operations_credit_total": 0,
                },
                "details": {"revenue_by_account": {}, "expenses_by_account": {}},
            },
        }


@router.get("/reports/cash-flow")
async def get_cash_flow(
    workshop_id: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    """
    قائمة التدفقات النقدية من قيود اليومية في Supabase
    """
    try:
        effective_workshop_id = workshop_id or os.environ.get("DEFAULT_WORKSHOP_ID")
        if not effective_workshop_id:
            raise HTTPException(status_code=400, detail="معرف الورشة مطلوب")

        end_date = _normalize_date_string(end_date) or datetime.now().strftime("%Y-%m-%d")
        start_date = _normalize_date_string(start_date) or (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

        accounts = _fetch_accounts()
        id_to_code, code_to_name, _ = _build_account_maps(accounts)
        entries = _fetch_journal_entries(
            effective_workshop_id, start_date=start_date, end_date=end_date, limit=10000
        )

        # Improve categorization using the other side of each cash/bank line.
        cash_from_customers = 0.0
        cash_to_suppliers = 0.0
        cash_for_salaries = 0.0
        equipment_purchases = 0.0
        owner_drawings = 0.0

        def _is_code_in_range(code: str, start: int, end: int) -> bool:
            try:
                n = int(str(code))
                return start <= n <= end
            except Exception:
                return False

        for entry in entries:
            # find cash/bank movement line, then infer category from the counterpart accounts
            cash_lines = []
            other_lines = []
            for line in entry.get("lines", []) or []:
                normalized = _normalize_line(line, id_to_code, code_to_name)
                if not normalized:
                    continue
                if normalized["code"] in ("003", "004", "006", "1101", "1102", "1104"):
                    cash_lines.append(normalized)
                else:
                    other_lines.append(normalized)

            if not cash_lines:
                continue

            for cl in cash_lines:
                amount_in = float(cl.get("debit") or 0)
                amount_out = float(cl.get("credit") or 0)

                # Classify inflows
                if amount_in > 0:
                    # If counterpart is AR (1103), it's customer collection (settlement)
                    if any(ol.get("code") in ("005", "1103") for ol in other_lines):
                        cash_from_customers += amount_in
                    # If counterpart is revenue (025-029 new, or 4xxx legacy)
                    elif any(_is_code_in_range(ol.get("code"), 25, 29) or _is_code_in_range(ol.get("code"), 4000, 4999) for ol in other_lines):
                        cash_from_customers += amount_in
                    else:
                        cash_from_customers += amount_in

                # Classify outflows
                if amount_out > 0:
                    # Supplier payments: AP (2101)
                    if any(ol.get("code") in ("2101", "211") for ol in other_lines):
                        cash_to_suppliers += amount_out
                    # Salaries expense (6101) or accrued salaries (2103)
                    elif any(ol.get("code") in ("6101", "2103") for ol in other_lines):
                        cash_for_salaries += amount_out
                    # Equipment purchases (fixed assets 12xx)
                    elif any(_is_code_in_range(ol.get("code"), 1200, 1299) for ol in other_lines):
                        equipment_purchases += amount_out
                    # Owner drawings (equity 3102)
                    elif any(ol.get("code") == "3102" for ol in other_lines):
                        owner_drawings += amount_out
                    else:
                        # default treat as supplier/operating outflow
                        cash_to_suppliers += amount_out

        net_operating_cash = cash_from_customers - (cash_to_suppliers + cash_for_salaries)
        net_investing_cash = -equipment_purchases
        net_financing_cash = -owner_drawings
        net_change_in_cash = net_operating_cash + net_investing_cash + net_financing_cash

        return {
            "success": True,
            "data": {
                "period": f"{start_date} إلى {end_date}",
                "operating_activities": {
                    "cash_from_customers": round(cash_from_customers, 2),
                    "cash_to_suppliers": round(-cash_to_suppliers, 2),
                    "cash_for_salaries": round(-cash_for_salaries, 2),
                    "net_operating_cash": round(net_operating_cash, 2),
                },
                "investing_activities": {
                    "equipment_purchases": round(-equipment_purchases, 2),
                    "asset_sales": 0,
                    "net_investing_cash": round(net_investing_cash, 2),
                },
                "financing_activities": {
                    "owner_drawings": round(-owner_drawings, 2),
                    "capital_injections": 0,
                    "new_loans": 0,
                    "loan_payments": 0,
                    "net_financing_cash": round(net_financing_cash, 2),
                },
                "net_change_in_cash": round(net_change_in_cash, 2),
                "beginning_cash": 0,
                "ending_cash": round(net_change_in_cash, 2),
            },
        }

    except Exception as e:
        print(f"Error in get_cash_flow: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "data": {
                "period": f"{start_date} إلى {end_date}",
                "operating_activities": {
                    "cash_from_customers": 0,
                    "cash_to_suppliers": 0,
                    "net_operating_cash": 0,
                },
                "investing_activities": {
                    "equipment_purchase": 0,
                    "net_investing_cash": 0,
                },


                "financing_activities": {
                    "loan_proceeds": 0,
                    "loan_payments": 0,
                    "net_financing_cash": 0,
                },
                "net_change_in_cash": 0,
                "beginning_cash": 0,
                "ending_cash": 0,
            },
        }


@router.get("/reports/trial-balance")
async def get_trial_balance(
    workshop_id: str = Query(...),
    date: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    include_rakan: bool = False,
):
    """
    ميزان المراجعة من البيانات الحقيقية في Supabase
    """
    try:
        if date is not None and not isinstance(date, str):
            date = None
        if start_date is not None and not isinstance(start_date, str):
            start_date = None
        if end_date is not None and not isinstance(end_date, str):
            end_date = None

        target_date = date or datetime.now().strftime("%Y-%m-%d")
        end_bound = end_date or target_date
        start_bound = start_date

        accounts_balances, merged_accounts = _compute_trial_balance_map(
            workshop_id,
            start_date=start_bound,
            end_date=end_bound,
            include_rakan=include_rakan,
        )
        _, code_to_name, _ = _build_account_maps(merged_accounts)

        accounts_list = []
        total_debit = 0
        total_credit = 0

        for code in sorted(accounts_balances.keys()):
            acc = accounts_balances[code]
            debit = round(acc["debit"], 2)
            credit = round(acc["credit"], 2)
            name = acc.get("name") or code_to_name.get(code) or code
            if str(name).strip() == code and code_to_name.get(code):
                name = code_to_name.get(code)
            accounts_list.append(
                {"code": code, "name": name, "debit": debit, "credit": credit}
            )
            total_debit += debit
            total_credit += credit

        return {
            "success": True,
            "data": {
                "period": f"حتى {target_date}",
                "accounts": accounts_list,
                "totals": {
                    "total_debit": round(total_debit, 2),
                    "total_credit": round(total_credit, 2),
                },
            },
        }

    except Exception as e:
        print(f"Error in get_trial_balance: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "data": {
                "period": f"حتى {date or datetime.now().strftime('%Y-%m-%d')}",
                "accounts": [],
                "totals": {"total_debit": 0, "total_credit": 0},
            },
        }


def _merge_by_id(primary_list, secondary_list):
    """دمج قائمتين بدون تكرار بحسب id.

    القاعدة: أي عنصر موجود في primary يأخذ أولوية.
    """
    merged = []
    seen = set()

    for item in (primary_list or []):
        if not isinstance(item, dict):
            continue
        _id = item.get("id")
        if _id and _id in seen:
            continue
        if _id:
            seen.add(_id)
        merged.append(item)

    for item in (secondary_list or []):
        if not isinstance(item, dict):
            continue
        _id = item.get("id")
        if _id and _id in seen:
            continue
        if _id:
            seen.add(_id)
        merged.append(item)

    return merged


def _normalize_account_type(account_type: Optional[str]) -> str:
    allowed = {"asset", "liability", "equity", "revenue", "expense"}
    normalized = str(account_type or "asset").strip().lower()
    return normalized if normalized in allowed else "asset"


_OPERATIONS_CACHE: Dict[str, tuple] = {}  # key -> (cached_at, rows)
_OPERATIONS_CACHE_TTL: float = 5.0


def _fetch_operations_for_reconciliation(
    workshop_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    if not supabase:
        raise Exception("Supabase not connected")

    # TTL cache keyed on filter params.
    import time
    global _OPERATIONS_CACHE
    now_ts = time.time()
    cache_key = f"live-scope-v2|{workshop_id}|{start_date or ''}|{end_date or ''}"
    cached = _OPERATIONS_CACHE.get(cache_key)
    if cached and (now_ts - cached[0]) < _OPERATIONS_CACHE_TTL:
        return cached[1]

    def _build(scoped: bool, select_expr: str):
        q = supabase.table("operations").select(select_expr)
        if scoped:
            q = q.eq("workshop_id", workshop_id)
        if start_date:
            q = q.gte("op_date", start_date)
        if end_date:
            q = q.lte("op_date", end_date)
        return q.order("op_date", desc=False)

    def _run(scoped: bool):
        preferred_select = (
            "id,type,total,payment_method,paymentMethod,payment_status,paymentStatus,scope,source,business_unit,op_date,workshop_id,notes"
        )
        try:
            return _build(scoped, preferred_select).execute().data or []
        except Exception as schema_error:
            if "does not exist" not in str(schema_error).lower():
                raise
            try:
                fallback_select = "id,type,total,payment_method,paymentMethod,payment_status,paymentStatus,source,op_date,workshop_id,notes"
                return _build(scoped, fallback_select).execute().data or []
            except Exception:
                return _build(scoped, "*").execute().data or []

    try:
        rows = _run(scoped=True)
        if workshop_id and not rows:
            rows = _run(scoped=False)
    except Exception:
        rows = _run(scoped=False)

    _OPERATIONS_CACHE[cache_key] = (now_ts, rows)
    # Purge stale
    if len(_OPERATIONS_CACHE) > 32:
        stale = [k for k, v in _OPERATIONS_CACHE.items() if (now_ts - v[0]) >= _OPERATIONS_CACHE_TTL]
        for k in stale:
            _OPERATIONS_CACHE.pop(k, None)
    return rows


def _is_rakan_operation_row(row: Dict[str, Any]) -> bool:
    # 🔥 Rakan logic permanently removed (Feb 2026) — always returns False.
    return False


def _normalize_operation_type_for_reconciliation(op_type: Optional[str]) -> Optional[str]:
    normalized = str(op_type or "").strip().lower()
    if not normalized:
        return None
    if normalized == "service":
        return "sale"
    return normalized


def _infer_tx_type_from_journal_entry(
    entry: Dict[str, Any],
    id_to_code: Optional[Dict[str, str]] = None,
    code_to_name: Optional[Dict[str, str]] = None,
) -> Optional[str]:
    description = str(entry.get("description") or "").strip().lower()
    source = str(entry.get("source") or "").strip().lower()
    lines = entry.get("lines") or []

    if source == "operation_payment":
        return "payment_order"

    if "payment_order" in description or "سداد" in description:
        return "payment_order"
    if "purchase_return" in description:
        return "purchase_return"
    if "sale_return" in description:
        return "sale_return"
    if "purchase" in description or "مشت" in description:
        return "purchase"
    if "expense" in description or "مصروف" in description:
        return "expense"
    if "sale" in description or "service" in description or "بيع" in description:
        return "sale"

    credits_by_code: Dict[str, float] = {}
    debits_by_code: Dict[str, float] = {}
    id_to_code = id_to_code or {}
    code_to_name = code_to_name or {}

    for line in lines:
        normalized = _normalize_line(line, id_to_code, code_to_name)
        if not normalized:
            continue
        code = str(normalized.get("code") or "").strip()
        if not code:
            continue
        debits_by_code[code] = debits_by_code.get(code, 0.0) + _safe_float(normalized.get("debit"))
        credits_by_code[code] = credits_by_code.get(code, 0.0) + _safe_float(normalized.get("credit"))

    if any(code in AR_ACCOUNT_CODES and credits_by_code.get(code, 0.0) > 0 for code in credits_by_code):
        return "payment_order"
    if any(code in AP_ACCOUNT_CODES and debits_by_code.get(code, 0.0) > 0 for code in debits_by_code):
        return "payment_order"

    if any(code.startswith("4") and credits_by_code.get(code, 0.0) > 0 for code in credits_by_code):
        return "sale"
    if any(code.startswith("5") and debits_by_code.get(code, 0.0) > 0 for code in debits_by_code):
        return "purchase"
    if any(code.startswith("6") and debits_by_code.get(code, 0.0) > 0 for code in debits_by_code):
        return "expense"

    return None


def _extract_operation_account_label(
    operation: Dict[str, Any],
    account_id_to_code: Optional[Dict[str, str]] = None,
    code_to_name: Optional[Dict[str, str]] = None,
) -> str:
    account_id_to_code = account_id_to_code or {}
    code_to_name = code_to_name or {}

    notes_blob = str(operation.get("notes") or operation.get("description") or "")
    target_match = re.search(r"ACCOUNTING_TARGET\s*:\s*([^\n\r]+)", notes_blob, re.IGNORECASE)
    if target_match and target_match.group(1).strip():
        return target_match.group(1).strip()

    code_match = re.search(r"ACCOUNT_CODE\s*:\s*([0-9]+)", notes_blob, re.IGNORECASE)
    code = code_match.group(1).strip() if code_match else ""

    if not code:
        code = str(
            operation.get("accounting_account_code")
            or operation.get("accountCode")
            or operation.get("account_number")
            or operation.get("accountNumber")
            or ""
        ).strip()

    if not code:
        account_id = str(operation.get("account_id") or operation.get("accountId") or "").strip()
        if account_id:
            code = str(account_id_to_code.get(account_id) or "").strip()

    if not code:
        return "غير محدد"

    name = code_to_name.get(code)
    return f"{name} ({code})" if name else code


def _transaction_type_label_ar(tx_type: Optional[str]) -> str:
    labels = {
        "sale": "بيع",
        "purchase": "شراء",
        "expense": "مصروف",
        "sale_return": "مرتجع بيع",
        "purchase_return": "مرتجع شراء",
        "payment_order": "أمر سداد",
        "payment": "تحصيل/سداد",
        "service": "خدمة",
    }
    normalized = str(tx_type or "").strip().lower()
    return labels.get(normalized, normalized or "غير محدد")


def _payment_method_label_ar(method: Optional[str]) -> str:
    normalized = _normalize_payment_method(method)
    labels = {
        "cash": "نقدي",
        "bank": "بنك",
        "pos": "نقاط بيع",
        "credit": "آجل",
    }
    return labels.get(normalized, normalized or "غير محدد")


def _payment_status_label_ar(status: Optional[str]) -> str:
    normalized = str(status or "").strip().lower()
    labels = {
        "paid": "مسدد",
        "paid_full": "مسدد بالكامل",
        "partial": "مدفوع جزئياً",
        "unpaid": "غير مسدد",
        "credit": "آجل",
        "pending": "بانتظار السداد",
    }
    return labels.get(normalized, normalized or "-")


def _infer_payment_method_from_lines(lines: List[Dict[str, Any]]) -> str:
    for line in lines or []:
        account_code = str(line.get("account") or line.get("account_code") or "").strip()
        if account_code == "006":
            return "pos"
        if account_code == "004":
            return "bank"
        if account_code == "003":
            return "cash"
    return ""


def _build_repair_journal_entry_from_operation(
    operation: Dict[str, Any],
    workshop_id: str,
    account_id_to_code: Optional[Dict[str, str]] = None,
) -> Optional[Dict[str, Any]]:
    op_type = _normalize_operation_type_for_reconciliation(operation.get("type"))
    if not op_type:
        return None

    total = _safe_float(operation.get("total"))
    if total <= 0:
        return None

    payment_method = _normalize_payment_method(operation.get("payment_method") or operation.get("paymentMethod") or "cash")
    is_credit = payment_method == "credit"
    cash_code = "004" if payment_method == "bank" else ("006" if payment_method == "pos" else "003")
    selected_code = (
        operation.get("accounting_account_code")
        or operation.get("accountCode")
        or operation.get("account_number")
        or operation.get("accountNumber")
    )
    notes_blob = str(operation.get("notes") or operation.get("description") or "")
    notes_code_match = re.search(r"ACCOUNT_CODE\s*:\s*([0-9]+)", notes_blob, re.IGNORECASE)
    if notes_code_match:
        selected_code = notes_code_match.group(1)

    if not selected_code:
        account_id_to_code = account_id_to_code or {}
        account_id = str(operation.get("account_id") or operation.get("accountId") or "").strip()
        if account_id:
            selected_code = account_id_to_code.get(account_id)

    # تحويل الكود المختار من legacy إلى جديد إذا لزم
    selected_code = _to_new_code(str(selected_code or "").strip()) or None

    lines: List[Dict[str, Any]] = []
    transaction_type = op_type

    if op_type == "sale":
        debit_code = "005" if is_credit else cash_code
        credit_code = selected_code or "026"  # إيرادات خدمات ميكانيكية (الدليل الحي)
        lines = [
            {"account": debit_code, "account_name": debit_code, "debit": total, "credit": 0},
            {"account": credit_code, "account_name": credit_code, "debit": 0, "credit": total},
        ]
    elif op_type == "purchase":
        debit_code = selected_code if selected_code and _infer_account_type_from_code(selected_code) == "expense" else "035"
        credit_code = "2101" if is_credit else cash_code
        lines = [
            {"account": debit_code, "account_name": debit_code, "debit": total, "credit": 0},
            {"account": credit_code, "account_name": credit_code, "debit": 0, "credit": total},
        ]
    elif op_type == "expense":
        debit_code = selected_code or "035"
        lines = [
            {"account": debit_code, "account_name": debit_code, "debit": total, "credit": 0},
            {"account": cash_code, "account_name": cash_code, "debit": 0, "credit": total},
        ]
    elif op_type == "sale_return":
        credit_code = "005" if is_credit else cash_code
        debit_code = selected_code or "026"
        lines = [
            {"account": debit_code, "account_name": debit_code, "debit": total, "credit": 0},
            {"account": credit_code, "account_name": credit_code, "debit": 0, "credit": total},
        ]
    elif op_type == "purchase_return":
        debit_code = "2101" if is_credit else cash_code
        credit_code = selected_code if selected_code and _infer_account_type_from_code(selected_code) == "expense" else "036"
        lines = [
            {"account": debit_code, "account_name": debit_code, "debit": total, "credit": 0},
            {"account": credit_code, "account_name": credit_code, "debit": 0, "credit": total},
        ]
    elif op_type == "payment_order":
        partner_type = str(operation.get("partner_type") or operation.get("partnerType") or "").strip().lower()
        if partner_type == "customer":
            lines = [
                {"account": cash_code, "account_name": cash_code, "debit": total, "credit": 0},
                {"account": "1103", "account_name": "1103", "debit": 0, "credit": total},
            ]
        else:
            lines = [
                {"account": "2101", "account_name": "2101", "debit": total, "credit": 0},
                {"account": cash_code, "account_name": cash_code, "debit": 0, "credit": total},
            ]
    else:
        return None

    op_id = str(operation.get("id") or "").strip()
    op_date = operation.get("op_date") or operation.get("date") or datetime.now().isoformat()
    description = (
        operation.get("notes")
        or operation.get("description")
        or f"Backfill journal for operation {op_type}"
    )

    return {
        "id": str(uuid.uuid4()),
        "workshop_id": workshop_id,
        "date": op_date,
        "description": description,
        "lines": lines,
        "total": round(total, 2),
        "source": "operation",
        "transaction_type": transaction_type,
        "reference_id": op_id,
    }


def _insert_repair_journal_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    if not supabase:
        raise Exception("Supabase not connected")
    # 🏦 المسار المركزي: AccountingEngine (توازن + منع تكرار)
    from core import accounting_engine
    res = accounting_engine.post_entry(entry)
    if res:
        return res[0]
    raise Exception("Insert not persisted: AccountingEngine returned no row")


@router.get("/reports/reconciliation")
async def get_financial_reconciliation(
    workshop_id: str = Query(...),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    include_rakan: bool = Query(False),
):
    """مطابقة العمليات مقابل القيود اليومية للفترة المحددة."""
    try:
        end_date = end_date or datetime.now().strftime("%Y-%m-%d")
        start_date = start_date or (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")

        operations = _fetch_operations_for_reconciliation(
            workshop_id=workshop_id,
            start_date=start_date,
            end_date=end_date,
        )
        if not include_rakan:
            operations = [op for op in operations if not _is_rakan_operation_row(op)]

        accounts = _fetch_accounts()
        account_id_to_code, code_to_name, _ = _build_account_maps(accounts)

        tracked_types = [
            "sale",
            "purchase",
            "expense",
            "sale_return",
            "purchase_return",
            "payment_order",
        ]
        operation_totals = {t: 0.0 for t in tracked_types}
        operation_counts = {t: 0 for t in tracked_types}
        operation_type_by_id: Dict[str, str] = {}
        untracked_operations = {"count": 0, "total": 0.0}

        for op in operations:
            op_type = _normalize_operation_type_for_reconciliation(op.get("type"))
            op_id = str(op.get("id") or "").strip()
            if op_id and op_type:
                operation_type_by_id[op_id] = op_type
            if op_type not in operation_totals:
                untracked_operations["count"] += 1
                untracked_operations["total"] += _safe_float(op.get("total"))
                continue
            operation_totals[op_type] += _safe_float(op.get("total"))
            operation_counts[op_type] += 1

        journal_entries = _fetch_journal_entries(
            workshop_id=workshop_id,
            start_date=start_date,
            end_date=end_date,
            limit=10000,
            include_rakan=include_rakan,
        )
        id_to_code = account_id_to_code
        journal_totals = {t: 0.0 for t in tracked_types}
        journal_counts = {t: 0 for t in tracked_types}
        account_labels_by_type = {t: set() for t in tracked_types}
        unclassified_journals = {"count": 0, "total": 0.0}

        for entry in journal_entries:
            tx_type = _normalize_operation_type_for_reconciliation(entry.get("transaction_type"))
            reference_id = str(entry.get("reference_id") or "").strip()
            source = str(entry.get("source") or "").strip().lower()

            # إذا كان القيد مربوطًا بعملية، نُقدّم نوع العملية كمصدر الحقيقة
            if reference_id and reference_id in operation_type_by_id and source in {"operation", "operation_rakan_parts"}:
                tx_type = operation_type_by_id.get(reference_id)

            if not tx_type:
                if reference_id and reference_id in operation_type_by_id:
                    tx_type = operation_type_by_id.get(reference_id)

            if not tx_type:
                tx_type = _infer_tx_type_from_journal_entry(
                    entry,
                    id_to_code=id_to_code,
                    code_to_name=code_to_name,
                )

            if tx_type not in journal_totals:
                unclassified_journals["count"] += 1
                unclassified_journals["total"] += _safe_float(entry.get("total"))
                continue

            journal_totals[tx_type] += _safe_float(entry.get("total"))
            journal_counts[tx_type] += 1

            normalized_lines = []
            for line in entry.get("lines", []) or []:
                normalized = _normalize_line(line, id_to_code, code_to_name)
                if normalized:
                    normalized_lines.append(normalized)

            for line in normalized_lines:
                code = str(line.get("code") or "").strip()
                name = line.get("name") or code_to_name.get(code) or code
                if str(name).strip() == code and code_to_name.get(code):
                    name = code_to_name.get(code)
                debit = _safe_float(line.get("debit"))
                credit = _safe_float(line.get("credit"))

                is_target = False
                if tx_type == "sale":
                    is_target = code.startswith("4") and credit > 0
                elif tx_type == "purchase":
                    is_target = code.startswith("5") and debit > 0
                elif tx_type == "expense":
                    is_target = code.startswith("6") and debit > 0
                elif tx_type == "sale_return":
                    is_target = code.startswith("4") and debit > 0
                elif tx_type == "purchase_return":
                    is_target = (code.startswith("5") or code.startswith("6")) and credit > 0
                elif tx_type == "payment_order":
                    is_target = code in {"003", "004", "005", "006", "2101", "1101", "1102", "1103", "2101"}

                if is_target:
                    account_labels_by_type[tx_type].add(f"{name} ({code})")

        existing_operation_refs = {
            str(entry.get("reference_id") or "").strip()
            for entry in journal_entries
            if str(entry.get("source") or "").strip().lower() in {"operation", "operation_rakan_parts"}
            and str(entry.get("reference_id") or "").strip()
        }
        missing_operation_journals = [
            op
            for op in operations
            if str(op.get("id") or "").strip()
            and _normalize_operation_type_for_reconciliation(op.get("type")) in journal_totals
            and _safe_float(op.get("total")) > 0.01
            and str(op.get("id") or "").strip() not in existing_operation_refs
        ]

        rows = []
        total_absolute_difference = 0.0
        for tx_type in tracked_types:
            op_total = round(operation_totals.get(tx_type, 0.0), 2)
            je_total = round(journal_totals.get(tx_type, 0.0), 2)
            difference = round(op_total - je_total, 2)
            total_absolute_difference += abs(difference)
            rows.append(
                {
                    "type": tx_type,
                    "type_label_ar": _transaction_type_label_ar(tx_type),
                    "operations_count": operation_counts.get(tx_type, 0),
                    "journal_entries_count": journal_counts.get(tx_type, 0),
                    "operations_total": op_total,
                    "journal_entries_total": je_total,
                    "difference": difference,
                    "matched": abs(difference) < 0.01,
                    "account_labels": sorted(
                        [label for label in account_labels_by_type.get(tx_type, set()) if label]
                    )[:6],
                }
            )

        return {
            "success": True,
            "data": {
                "period": {"start_date": start_date, "end_date": end_date},
                "summary": {
                    "matched": total_absolute_difference < 0.01,
                    "total_absolute_difference": round(total_absolute_difference, 2),
                    "untracked_operations": {
                        "count": int(untracked_operations["count"]),
                        "total": round(float(untracked_operations["total"]), 2),
                    },
                    "unclassified_journal_entries": {
                        "count": int(unclassified_journals["count"]),
                        "total": round(float(unclassified_journals["total"]), 2),
                    },
                    "missing_operation_journals": {
                        "count": len(missing_operation_journals),
                        "total": round(
                            sum(_safe_float(op.get("total")) for op in missing_operation_journals),
                            2,
                        ),
                        "sample_operation_ids": [
                            str(op.get("id")) for op in missing_operation_journals[:10]
                        ],
                    },
                },
                "rows": rows,
            },
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "data": {
                "period": {"start_date": start_date, "end_date": end_date},
                "summary": {"matched": False, "total_absolute_difference": 0},
                "rows": [],
            },
        }


@router.post("/reports/reconciliation/backfill-journals")
async def backfill_missing_operation_journals(
    workshop_id: str = Query(...),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    include_rakan: bool = Query(False),
    apply_changes: bool = Query(False),
    max_records: int = Query(200, ge=1, le=1000),
):
    """فحص/ترميم القيود المفقودة للعمليات التاريخية.

    - `apply_changes=false` => معاينة فقط (dry-run)
    - `apply_changes=true`  => إنشاء قيود للعمليات التي لا تملك قيدًا مرجعيًا
    """
    try:
        end_date = end_date or datetime.now().strftime("%Y-%m-%d")
        start_date = start_date or (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")

        operations = _fetch_operations_for_reconciliation(
            workshop_id=workshop_id,
            start_date=start_date,
            end_date=end_date,
        )
        if not include_rakan:
            operations = [op for op in operations if not _is_rakan_operation_row(op)]

        accounts = _fetch_accounts()
        account_id_to_code, _, _ = _build_account_maps(accounts)

        journal_entries = _fetch_journal_entries(
            workshop_id=workshop_id,
            start_date=start_date,
            end_date=end_date,
            limit=10000,
            include_rakan=include_rakan,
        )

        tracked_types = {
            "sale",
            "purchase",
            "expense",
            "sale_return",
            "purchase_return",
            "payment_order",
        }
        existing_operation_refs = {
            str(entry.get("reference_id") or "").strip()
            for entry in journal_entries
            if str(entry.get("source") or "").strip().lower() in {"operation", "operation_rakan_parts"}
            and str(entry.get("reference_id") or "").strip()
        }

        missing_operations = []
        for op in operations:
            op_id = str(op.get("id") or "").strip()
            op_type = _normalize_operation_type_for_reconciliation(op.get("type"))
            if not op_id or op_type not in tracked_types:
                continue
            if op_id in existing_operation_refs:
                continue
            candidate_entry = _build_repair_journal_entry_from_operation(
                op,
                workshop_id,
                account_id_to_code=account_id_to_code,
            )
            if candidate_entry:
                missing_operations.append({"operation": op, "journal": candidate_entry})

        preview = [
            {
                "operation_id": str(item["operation"].get("id")),
                "type": str(item["operation"].get("type")),
                "total": round(_safe_float(item["operation"].get("total")), 2),
                "journal_transaction_type": item["journal"].get("transaction_type"),
                "journal_accounts": [
                    str(line.get("account")) for line in (item["journal"].get("lines") or [])
                ],
            }
            for item in missing_operations[:20]
        ]

        if not apply_changes:
            return {
                "success": True,
                "mode": "dry_run",
                "data": {
                    "period": {"start_date": start_date, "end_date": end_date},
                    "missing_count": len(missing_operations),
                    "missing_total": round(
                        sum(_safe_float(item["operation"].get("total")) for item in missing_operations),
                        2,
                    ),
                    "preview": preview,
                },
            }

        created = 0
        created_items = []
        failed = []
        for item in missing_operations[:max_records]:
            try:
                inserted = _insert_repair_journal_entry(item["journal"])
                created += 1
                created_items.append(
                    {
                        "journal_id": str(inserted.get("id") or item["journal"].get("id")),
                        "reference_id": str(
                            inserted.get("reference_id") or item["journal"].get("reference_id")
                        ),
                        "transaction_type": inserted.get("transaction_type")
                        or item["journal"].get("transaction_type"),
                        "workshop_id": inserted.get("workshop_id") or item["journal"].get("workshop_id"),
                        "date": inserted.get("date") or item["journal"].get("date"),
                        "source": inserted.get("source") or item["journal"].get("source"),
                    }
                )
            except Exception as insert_error:
                failed.append(
                    {
                        "operation_id": str(item["operation"].get("id")),
                        "error": str(insert_error),
                    }
                )

        return {
            "success": True,
            "mode": "apply",
            "data": {
                "period": {"start_date": start_date, "end_date": end_date},
                "found_missing": len(missing_operations),
                "created": created,
                "created_items": created_items[:50],
                "failed": failed,
                "preview": preview,
            },
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "mode": "error",
            "data": {
                "period": {"start_date": start_date, "end_date": end_date},
                "missing_count": 0,
                "preview": [],
            },
        }


@router.get("/reports/account-tree-details")
async def get_account_tree_details(
    workshop_id: str = Query(...),
    account_code: str = Query(...),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    include_descendants: bool = Query(True),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """تفاصيل حساب شجرية: الحساب الفرعي + العمليات المرتبطة مع ترقيم صفحات."""
    try:
        accounts = _fetch_accounts()
        id_to_code, code_to_name, code_to_type = _build_account_maps(accounts)
        code_map = {str(acc.get("code") or "").strip(): acc for acc in accounts}

        account_code = str(account_code or "").strip()
        selected = code_map.get(account_code)
        if not selected:
            raise HTTPException(status_code=404, detail="الحساب غير موجود")

        selected_id = str(selected.get("id") or "").strip()

        direct_children = [
            acc
            for acc in accounts
            if str(acc.get("parent_id") or "").strip() == selected_id
        ]

        descendants_codes = {account_code}
        if include_descendants:
            queue = [selected_id]
            while queue:
                current_id = queue.pop(0)
                for acc in accounts:
                    if str(acc.get("parent_id") or "").strip() == current_id:
                        child_id = str(acc.get("id") or "").strip()
                        child_code = str(acc.get("code") or "").strip()
                        if child_code:
                            descendants_codes.add(child_code)
                        if child_id:
                            queue.append(child_id)

        entries = _fetch_journal_entries(
            workshop_id=workshop_id,
            start_date=start_date,
            end_date=end_date,
            limit=20000,
            include_rakan=False,
        )

        operation_link_sources = {"operation", "operation_rakan_parts", "operation_payment", "supplier_balance_payment"}
        operation_refs = [
            str(e.get("reference_id") or "").strip()
            for e in entries
            if str(e.get("source") or "").strip().lower() in operation_link_sources
            and str(e.get("reference_id") or "").strip()
        ]
        operation_refs = list(dict.fromkeys(operation_refs))

        operation_map: Dict[str, Dict[str, Any]] = {}
        visit_map: Dict[str, Dict[str, Any]] = {}
        if operation_refs and supabase:
            try:
                op_rows = (
                    supabase.table("operations")
                    .select("*")
                    .in_("id", operation_refs)
                    .execute()
                    .data
                    or []
                )
                operation_map = {str(row.get("id") or ""): row for row in op_rows}

                visit_ids = [
                    str(row.get("visit_id") or row.get("visitId") or "").strip()
                    for row in op_rows
                    if str(row.get("visit_id") or row.get("visitId") or "").strip()
                ]
                visit_ids = list(dict.fromkeys(visit_ids))
                if visit_ids:
                    visit_rows = (
                        supabase.table("vehicle_visits")
                        .select("*")
                        .in_("id", visit_ids)
                        .execute()
                        .data
                        or []
                    )
                    visit_map = {str(row.get("id") or ""): row for row in visit_rows}
            except Exception:
                operation_map = {}
                visit_map = {}

        # دعم إضافي: استخراج معرف الزيارة من الوصف عند غياب ربط العملية
        if supabase:
            try:
                visit_ids_from_desc = []
                for e in entries:
                    desc = str(e.get("description") or "")
                    match = re.search(r"الزيارة\s+([a-zA-Z0-9-]+)", desc)
                    if match:
                        visit_ids_from_desc.append(match.group(1).strip())
                visit_ids_from_desc = [v for v in dict.fromkeys(visit_ids_from_desc) if v]
                missing_visit_ids = [v for v in visit_ids_from_desc if v not in visit_map]
                if missing_visit_ids:
                    extra_visits = (
                        supabase.table("vehicle_visits")
                        .select("id,customer_name,vehicle_plate,plate_number,car_type,vehicle_number,customer_id")
                        .in_("id", missing_visit_ids)
                        .execute()
                        .data
                        or []
                    )
                    for row in extra_visits:
                        visit_map[str(row.get("id") or "")] = row
            except Exception:
                pass

        operations = []
        for entry in entries:
            normalized_lines = []
            for line in entry.get("lines", []) or []:
                normalized = _normalize_line(line, id_to_code, code_to_name)
                if normalized:
                    normalized_lines.append(normalized)

            matched_debit = 0.0
            matched_credit = 0.0
            cash_component = 0.0
            bank_component = 0.0
            receivable_component = 0.0
            counterpart_accounts = []

            for line in normalized_lines:
                line_code = str(line.get("code") or "").strip()
                if line_code in descendants_codes:
                    matched_debit += _safe_float(line.get("debit"))
                    matched_credit += _safe_float(line.get("credit"))
                else:
                    counterpart_accounts.append(
                        {
                            "code": line_code,
                            "name": line.get("name") or code_to_name.get(line_code) or line_code,
                        }
                    )

                # مكونات التحصيل/الآجل (يدعم الأكواد الجديدة والقديمة)
                if line_code in ("003", "1101"):
                    cash_component += _safe_float(line.get("debit"))
                if line_code in ("004", "006", "1102", "1104"):
                    bank_component += _safe_float(line.get("debit"))
                if line_code in {"005", "1103", "113"}:
                    receivable_component += _safe_float(line.get("debit"))

            if matched_debit == 0 and matched_credit == 0:
                continue

            operations.append(
                {
                    "entry_id": str(entry.get("id") or ""),
                    "date": entry.get("date"),
                    "description": entry.get("description") or "",
                    "transaction_type": entry.get("transaction_type") or "",
                    "transaction_type_label_ar": _transaction_type_label_ar(entry.get("transaction_type")),
                    "source": entry.get("source") or "",
                    "reference_id": entry.get("reference_id") or "",
                    "entry_total": _safe_float(entry.get("total")),
                    "operation_payment_method": "",
                    "debit": round(matched_debit, 2),
                    "credit": round(matched_credit, 2),
                    "cash_component": round(cash_component, 2),
                    "bank_component": round(bank_component, 2),
                    "receivable_component": round(receivable_component, 2),
                    "counterpart_accounts": counterpart_accounts[:6],
                }
            )

            ref = str(entry.get("reference_id") or "").strip()
            src = str(entry.get("source") or "").strip().lower()
            if ref and src in operation_link_sources:
                op_row = operation_map.get(ref) or {}
                visit_id = str(op_row.get("visit_id") or op_row.get("visitId") or "").strip()
                visit_row = visit_map.get(visit_id) or {}
                operations[-1]["operation_payment_method"] = _normalize_payment_method(
                    op_row.get("payment_method") or op_row.get("paymentMethod") or ""
                )

                customer_label = (
                    op_row.get("partner_name")
                    or op_row.get("partnerName")
                    or visit_row.get("customer_name")
                    or ""
                )
                vehicle_label = (
                    visit_row.get("vehicle_plate")
                    or visit_row.get("plate_number")
                    or visit_row.get("vehicle_number")
                    or visit_row.get("car_type")
                    or ""
                )

                if customer_label or vehicle_label:
                    prefix = _transaction_type_label_ar(entry.get("transaction_type"))
                    parts = [prefix]
                    if customer_label:
                        parts.append(f"عميل: {customer_label}")
                    if vehicle_label:
                        parts.append(f"مركبة: {vehicle_label}")
                    operations[-1]["description"] = " - ".join(parts)
            else:
                desc = str(operations[-1].get("description") or "")
                match = re.search(r"الزيارة\s+([a-zA-Z0-9-]+)", desc)
                if match:
                    visit_id = match.group(1).strip()
                    visit_row = visit_map.get(visit_id) or {}
                    customer_label = visit_row.get("customer_name") or ""
                    vehicle_label = (
                        visit_row.get("vehicle_plate")
                        or visit_row.get("plate_number")
                        or visit_row.get("vehicle_number")
                        or visit_row.get("car_type")
                        or ""
                    )
                    if customer_label or vehicle_label:
                        prefix = _transaction_type_label_ar(entry.get("transaction_type"))
                        parts = [prefix]
                        if customer_label:
                            parts.append(f"عميل: {customer_label}")
                        if vehicle_label:
                            parts.append(f"مركبة: {vehicle_label}")
                        operations[-1]["description"] = " - ".join(parts)

        operations.sort(key=lambda x: str(x.get("date") or ""), reverse=True)
        operations_cash_total = 0.0
        operations_bank_total = 0.0
        operations_credit_total = 0.0
        for item in operations:
            payment_method = _normalize_payment_method(item.get("operation_payment_method") or "")
            amount = _safe_float(item.get("credit"))
            cash_component_value = _safe_float(item.get("cash_component"))
            bank_component_value = _safe_float(item.get("bank_component"))
            if payment_method == "credit":
                operations_credit_total += amount
            elif payment_method == "bank":
                operations_bank_total += amount
            elif payment_method:
                operations_cash_total += amount
            else:
                operations_cash_total += cash_component_value
                operations_bank_total += bank_component_value

        summary = {
            "total_debit": round(sum(_safe_float(item.get("debit")) for item in operations), 2),
            "total_credit": round(sum(_safe_float(item.get("credit")) for item in operations), 2),
            "total_cash_component": round(sum(_safe_float(item.get("cash_component")) for item in operations), 2),
            "total_bank_component": round(sum(_safe_float(item.get("bank_component")) for item in operations), 2),
            "total_receivable_component": round(sum(_safe_float(item.get("receivable_component")) for item in operations), 2),
            "operations_cash_total": round(operations_cash_total, 2),
            "operations_bank_total": round(operations_bank_total, 2),
            "operations_credit_total": round(operations_credit_total, 2),
        }
        total_items = len(operations)
        total_pages = max(1, (total_items + page_size - 1) // page_size)
        page = min(page, total_pages)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size

        children_payload = []
        for child in direct_children:
            child_id = str(child.get("id") or "").strip()
            has_children = any(
                str(acc.get("parent_id") or "").strip() == child_id for acc in accounts
            )
            child_code = str(child.get("code") or "")
            children_payload.append(
                {
                    "id": child_id,
                    "code": child_code,
                    "name": child.get("name") or child.get("name_ar") or child_code,
                    "type": child.get("type") or code_to_type.get(child_code) or "",
                    "has_children": has_children,
                }
            )

        return {
            "success": True,
            "data": {
                "account": {
                    "id": selected_id,
                    "code": account_code,
                    "name": selected.get("name") or selected.get("name_ar") or account_code,
                    "type": selected.get("type") or code_to_type.get(account_code) or "",
                },
                "children": children_payload,
                "operations": {
                    "items": operations[start_idx:end_idx],
                    "summary": summary,
                    "pagination": {
                        "page": page,
                        "page_size": page_size,
                        "total_items": total_items,
                        "total_pages": total_pages,
                        "has_next": page < total_pages,
                        "has_prev": page > 1,
                    },
                },
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "data": {
                "account": {"code": account_code, "name": account_code, "type": ""},
                "children": [],
                "operations": {
                    "items": [],
                    "summary": {
                        "total_debit": 0,
                        "total_credit": 0,
                        "total_cash_component": 0,
                        "total_bank_component": 0,
                        "total_receivable_component": 0,
                        "operations_cash_total": 0,
                        "operations_bank_total": 0,
                        "operations_credit_total": 0,
                    },
                    "pagination": {
                        "page": page,
                        "page_size": page_size,
                        "total_items": 0,
                        "total_pages": 1,
                        "has_next": False,
                        "has_prev": False,
                    },
                },
            },
        }


@router.get("/alerts")
async def get_finance_alerts(
    workshop_id: str = Query(...),
):
    """تنبيهات موحّدة — تُشتق مباشرة من محرك جدار الحماية (المصدر الوحيد للحقيقة).

    نفس التنبيهات التي يعرضها /api/firewall/dashboard والبوت (كاترينا)،
    مُهيّأة بصيغة FinanceAlertsWidget (severity/title/message/action/route).
    """
    from firewall_engine import FirewallEngine

    analysis = FirewallEngine(workshop_id).run_full_analysis()

    category_route = {
        "balance_integrity": ("/accounting/firewall", "فتح مركز جدار الحماية"),
        "duplicate_detection": ("/accounting/firewall", "فتح مركز جدار الحماية"),
        "consistency": ("/accounting/firewall", "فتح مركز جدار الحماية"),
        "anomaly": ("/accounting/firewall", "فتح مركز جدار الحماية"),
        "integrity": ("/accounting/firewall", "فتح مركز جدار الحماية"),
        "profitability": ("/accounting/comprehensive", "لوحة المؤشرات"),
        "receivables": ("/debts-followup", "متابعة الذمم"),
        "payables": ("/suppliers", "صفحة الموردين"),
        "overdue": ("/debts-followup", "متابعة الذمم"),
        "cash_flow": ("/accounting/comprehensive", "لوحة المؤشرات"),
    }
    sev_map = {"critical": "high", "high": "high", "medium": "medium", "low": "low", "info": "low"}

    alerts = []
    for a in analysis.get("alerts", []):
        route, route_label = category_route.get(
            a.get("category"), ("/accounting/firewall", "فتح مركز جدار الحماية")
        )
        alerts.append({
            "id": a.get("id"),
            "severity": sev_map.get(a.get("severity"), "low"),
            "title": a.get("title"),
            "message": a.get("description"),
            "action": (a.get("auto_fix_preview") or {}).get("message") or a.get("root_cause"),
            "route": route,
            "route_label": route_label,
        })

    return {
        "success": True,
        "data": {
            "alerts": alerts,
            "health": analysis.get("health"),
            "cash_flow": analysis.get("cash_flow"),
            "profitability": analysis.get("profitability"),
            "source": "firewall_engine",
            "generated_at": analysis.get("generated_at"),
        },
    }


@router.get("/chart-of-accounts")
async def get_chart_of_accounts(
    workshop_id: str = Query(...),
    include_rakan: bool = False,
):
    """
    دليل الحسابات محسوب من العمليات الحقيقية في Supabase
    """
    try:
        accounts_balances, merged_accounts = _compute_trial_balance_map(
            workshop_id,
            include_rakan=include_rakan,
        )
        _, code_to_name, code_to_type = _build_account_maps(merged_accounts)

        merged_by_code = {}
        for acc in merged_accounts:
            code = str(acc.get("code") or "").strip()
            if not code:
                continue
            merged_by_code[code] = acc

        alias_to_current: Dict[str, str] = {}
        for acc in merged_accounts:
            current_code = str(acc.get("code") or "").strip()
            legacy_code = str(acc.get("legacy_code") or acc.get("legacyCode") or "").strip()
            if current_code and legacy_code:
                alias_to_current[legacy_code] = current_code

        if db is not None:
            try:
                alias_rows = await db.account_code_aliases.find({}, {"_id": 0, "accountId": 1, "legacyCode": 1}).to_list(length=5000)
                account_id_to_current = {
                    str(acc.get("id") or "").strip(): str(acc.get("code") or "").strip()
                    for acc in merged_accounts
                    if str(acc.get("id") or "").strip() and str(acc.get("code") or "").strip()
                }
                for row in alias_rows:
                    account_id = str(row.get("accountId") or "").strip()
                    legacy_code = str(row.get("legacyCode") or "").strip()
                    current_code = account_id_to_current.get(account_id)
                    if legacy_code and current_code:
                        alias_to_current[legacy_code] = current_code
            except Exception:
                pass

        # fallback mapping بالاسم/البادئة لإخفاء الأكواد القديمة من العرض
        def _find_code_by_name(*needles: str) -> str:
            for acc in merged_accounts:
                name = str(acc.get("name") or acc.get("name_ar") or "").strip().lower()
                code = str(acc.get("code") or "").strip()
                if not code:
                    continue
                if all(n in name for n in needles):
                    return code
            return ""

        ar_code_fallback = _find_code_by_name("العملاء")
        ap_code_fallback = _find_code_by_name("المورد")
        revenue_code_fallback = _find_code_by_name("الإيراد") or _find_code_by_name("ايراد")
        expense_code_fallback = _find_code_by_name("المصروف")
        cost_code_fallback = _find_code_by_name("تكلفة")

        def _map_legacy_prefix(code: str) -> str:
            if code.startswith("1103") and ar_code_fallback:
                return ar_code_fallback
            if code.startswith("2101") and ap_code_fallback:
                return ap_code_fallback
            if code.startswith("400") or code.startswith("410"):
                return revenue_code_fallback or code
            if code.startswith("600") or code.startswith("610"):
                return expense_code_fallback or code
            if code.startswith("500") or code.startswith("510"):
                return cost_code_fallback or expense_code_fallback or code
            return code

        balances_by_current: Dict[str, Dict[str, float]] = {}

        for code, data in accounts_balances.items():
            mapped_code = alias_to_current.get(code, code)
            mapped_code = _map_legacy_prefix(mapped_code)
            if mapped_code not in merged_by_code:
                # لا نُظهر أكواد قديمة مجهولة إذا تعذر ربطها بدليل الحسابات الجديد
                if mapped_code == code and (code.isdigit() and int(code) >= 1000) and code != "2101":
                    continue

                merged_by_code[mapped_code] = {
                    "id": mapped_code,
                    "code": mapped_code,
                    "name": data.get("name") or code_to_name.get(code) or mapped_code,
                    "name_ar": data.get("name") or code_to_name.get(code) or mapped_code,
                    "type": code_to_type.get(mapped_code) or code_to_type.get(code) or "other",
                }

            bucket = balances_by_current.setdefault(mapped_code, {"debit": 0.0, "credit": 0.0})
            bucket["debit"] += _safe_float(data.get("debit"))
            bucket["credit"] += _safe_float(data.get("credit"))

        results = []
        for code in sorted(merged_by_code.keys()):
            acc = merged_by_code[code]
            acc_type = acc.get("type") or "asset"
            debit = balances_by_current.get(code, {}).get("debit", 0)
            credit = balances_by_current.get(code, {}).get("credit", 0)

            if acc_type in ("asset", "expense"):
                balance = debit - credit
            elif acc_type in ("liability", "equity", "revenue"):
                balance = credit - debit
            else:
                balance = debit - credit

            is_rakan = _is_rakan_account_code(code)
            results.append(
                {
                    **acc,
                    "name_ar": acc.get("name_ar") or acc.get("name"),
                    "balance": round(balance, 2),
                    "is_rakan": is_rakan,
                    "business_unit": "rakan_parts" if is_rakan else "workshop",
                    "module": "parts_dashboard" if is_rakan else "default_accounting_flow",
                    "department": "Rakan Parts" if is_rakan else "Workshop",
                }
            )

        results = sorted(results, key=lambda x: str(x.get("code", "")))

        return {"success": True, "data": results, "source": "journal_entries"}

    except Exception as e:
        print(f"Error in get_chart_of_accounts: {str(e)}")
        return {"success": False, "error": str(e), "data": []}


@router.post("/chart-of-accounts")
async def create_chart_of_accounts_account(
    payload: dict = Body(...), workshop_id: Optional[str] = Query(None)
):
    """إنشاء حساب جديد في دليل الحسابات.

    يحفظ مباشرة في جدول accounts (Supabase) إن كان متاحاً،
    وإلا يستخدم Mongo fallback.
    """
    try:
        code = str((payload or {}).get("code") or "").strip()
        name = str((payload or {}).get("name") or (payload or {}).get("name_ar") or "").strip()
        account_type = _normalize_account_type((payload or {}).get("type"))
        parent_id = (payload or {}).get("parent_id") or (payload or {}).get("parentId")

        if not code:
            raise HTTPException(status_code=400, detail="رمز الحساب مطلوب")
        if not name:
            raise HTTPException(status_code=400, detail="اسم الحساب مطلوب")

        account_id = str(uuid.uuid4())
        row = {
            "id": account_id,
            "code": code,
            "name": name,
            "name_en": (payload or {}).get("name_en") or (payload or {}).get("nameEn") or "",
            "type": account_type,
            "parent_id": parent_id,
            "is_system": False,
            "balance": 0.0,
            "created_at": datetime.now().isoformat(),
        }

        if supabase:
            exists = (
                supabase.table("accounts")
                .select("id,code")
                .eq("code", code)
                .limit(1)
                .execute()
            )
            if exists.data:
                raise HTTPException(status_code=400, detail="رمز الحساب موجود مسبقاً")

            inserted = supabase.table("accounts").insert(row).execute()
            saved = (inserted.data or [row])[0]
            return {
                "success": True,
                "data": {
                    "id": saved.get("id"),
                    "code": saved.get("code"),
                    "name": saved.get("name"),
                    "name_ar": saved.get("name"),
                    "type": _normalize_account_type(saved.get("type")),
                    "parent_id": saved.get("parent_id"),
                    "balance": float(saved.get("balance") or 0),
                },
            }

        if db is not None:
            duplicate = await db.accounts.find_one({"code": code}, {"_id": 0, "id": 1})
            if duplicate:
                raise HTTPException(status_code=400, detail="رمز الحساب موجود مسبقاً")

            doc = {
                "id": account_id,
                "code": code,
                "name": name,
                "name_ar": (payload or {}).get("name_ar") or name,
                "type": account_type,
                "parent_id": parent_id,
                "is_system": False,
                "balance": 0.0,
                "created_at": datetime.now().isoformat(),
            }
            await db.accounts.insert_one(doc)
            return {"success": True, "data": doc}

        raise HTTPException(status_code=503, detail="مصدر البيانات غير متاح حالياً")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"تعذر إنشاء الحساب: {str(e)}")


# NOTE: First definition of get_journal_entries removed to fix duplicate function definition

# NOTE: legacy duplicated definition of get_journal_entries was removed to fix syntax


@router.get("/ar-ledger")
async def get_ar_ledger(workshop_id: str = Query("finmodule-sync")):
    """📒 L14-D6 (تقني): طبقات الذمم — SSOT القيود + الآجل غير المقيّد + الأرصدة المخزنة."""
    from core import ar_ledger
    return {"success": True, "data": await ar_ledger.summary(workshop_id)}


@router.post("/ar-repair")
async def ar_repair(dry_run: bool = Query(False)):
    """🛠️ إصلاح ترابط الذمم: إعادة مزامنة كل الزيارات ذات البنود → عمليات + قيود (بيع آجل/تحصيل).
    Idempotent — يعيد تقريراً بما أُنشئ/حُدِّث."""
    from supabase_service import SupabaseService
    from visit_sync import _sync_visit_to_operation

    supa = SupabaseService()
    visits = supabase.table("vehicle_visits").select("*").limit(3000).execute().data or []
    before = supabase.table("journal_entries").select("id").limit(5000).execute().data or []
    processed, skipped, errors = [], 0, []
    for v in visits:
        vid = str(v.get("id") or "")
        notes = v.get("notes")
        has_items = False
        try:
            payload = json.loads(notes) if isinstance(notes, str) and notes.strip().startswith("{") else (notes if isinstance(notes, dict) else {})
            has_items = bool((payload or {}).get("items"))
        except Exception:
            has_items = False
        if not has_items:
            skipped += 1
            continue
        if dry_run:
            processed.append(vid)
            continue
        try:
            await _sync_visit_to_operation(vid, {"vehicleId": v.get("vehicle_id"), "notes": notes}, supa_service=supa)
            processed.append(vid)
        except Exception as e:
            errors.append({"visit_id": vid, "error": str(e)[:200]})
    after = supabase.table("journal_entries").select("id").limit(5000).execute().data or []
    return {
        "success": True,
        "dry_run": dry_run,
        "visits_processed": len(processed),
        "visits_skipped_no_items": skipped,
        "journal_entries_before": len(before),
        "journal_entries_after": len(after),
        "errors": errors,
    }


@router.get("/journal-entries")
async def get_journal_entries(
    workshop_id: str = Query(...),
    skip: int = Query(0),
    limit: int = Query(50),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    include_rakan: bool = False,
):
    """
    القيود المحاسبية من Supabase و MongoDB operations
    """
    try:
        entries = _fetch_journal_entries(
            workshop_id,
            start_date=start_date,
            end_date=end_date,
            skip=skip,
            limit=limit,
            include_rakan=include_rakan,
        )

        operation_link_sources = {"operation", "operation_rakan_parts", "operation_payment", "supplier_balance_payment"}
        operation_refs = [
            str(e.get("reference_id") or "").strip()
            for e in entries
            if str(e.get("source") or "").strip().lower() in operation_link_sources
            and str(e.get("reference_id") or "").strip()
        ]
        operation_refs = list(dict.fromkeys(operation_refs))

        operation_map: Dict[str, Dict[str, Any]] = {}
        visit_map: Dict[str, Dict[str, Any]] = {}
        vehicle_map: Dict[str, Dict[str, Any]] = {}
        if operation_refs and supabase:
            try:
                op_rows = (
                    supabase.table("operations")
                    .select("*")
                    .in_("id", operation_refs)
                    .execute()
                    .data
                    or []
                )
                operation_map = {str(row.get("id") or ""): row for row in op_rows}
                vehicle_ids = [
                    str(row.get("vehicle_id") or row.get("vehicleId") or "").strip()
                    for row in op_rows
                    if str(row.get("vehicle_id") or row.get("vehicleId") or "").strip()
                ]
                vehicle_ids = list(dict.fromkeys(vehicle_ids))
                if vehicle_ids:
                    vehicle_rows = (
                        supabase.table("vehicles")
                        .select("*")
                        .in_("id", vehicle_ids)
                        .execute()
                        .data
                        or []
                    )
                    vehicle_map = {str(v.get("id") or ""): v for v in vehicle_rows}
                visit_ids = [
                    str(row.get("visit_id") or row.get("visitId") or "").strip()
                    for row in op_rows
                    if str(row.get("visit_id") or row.get("visitId") or "").strip()
                ]
                visit_ids = list(dict.fromkeys(visit_ids))
                if visit_ids:
                    visit_rows = (
                        supabase.table("vehicle_visits")
                        .select("*")
                        .in_("id", visit_ids)
                        .execute()
                        .data
                        or []
                    )
                    visit_map = {str(v.get("id") or ""): v for v in visit_rows}
            except Exception:
                operation_map = {}
                visit_map = {}
                vehicle_map = {}

        type_labels = {
            "sale": "بيع",
            "service": "خدمة",
            "purchase": "شراء",
            "expense": "مصروف",
            "sale_return": "مرتجع بيع",
            "purchase_return": "مرتجع شراء",
            "payment_order": "أمر سداد",
            "payment": "تحصيل/سداد",
        }

        formatted = []
        for entry in entries:
            source = str(entry.get("source") or "manual").strip().lower()
            tx_type = str(entry.get("transaction_type") or "").strip().lower()
            reference_id = str(entry.get("reference_id") or "").strip()
            description = entry.get("description", "قيد")
            lines = entry.get("lines", [])

            op = operation_map.get(reference_id, {}) if reference_id else {}
            visit_id = str(op.get("visit_id") or op.get("visitId") or "").strip()
            visit = visit_map.get(visit_id, {}) if visit_id else {}
            vehicle = vehicle_map.get(str(op.get("vehicle_id") or op.get("vehicleId") or "").strip(), {})

            party_type = str(op.get("partner_type") or op.get("partnerType") or "").strip().lower()
            if not party_type and source in operation_link_sources:
                party_type = "open"

            party_label = (
                op.get("partner_name")
                or op.get("partnerName")
                or visit.get("customer_name")
                or ""
            )
            if not party_label:
                if party_type == "supplier":
                    party_label = "مورد غير محدد"
                elif party_type == "customer":
                    party_label = "عميل غير محدد"
                elif source in operation_link_sources:
                    party_label = "مفتوح"

            vehicle_label = (
                op.get("vehicle_label")
                or op.get("vehicleLabel")
                or op.get("vehicle_plate")
                or op.get("vehiclePlate")
                or op.get("plate_number")
                or op.get("plateNumber")
                or op.get("vehicle_number")
                or op.get("vehicleNumber")
                or op.get("car_type")
                or vehicle.get("plate_number")
                or vehicle.get("plateNumber")
                or vehicle.get("vehicle_number")
                or vehicle.get("vehicleNumber")
                or " ".join([str(vehicle.get("brand") or "").strip(), str(vehicle.get("model") or "").strip()]).strip()
                or visit.get("vehicle_plate")
                or visit.get("plate_number")
                or visit.get("vehicle_number")
                or visit.get("car_type")
                or ""
            )

            # allow quick manual override in description token: [PARTY:...]
            manual_party_match = re.search(r"\[PARTY:([^\]]+)\]", str(description or ""))
            manual_party_type_match = re.search(r"\[PARTY_TYPE:([^\]]+)\]", str(description or ""))
            manual_vehicle_match = re.search(r"\[VEHICLE_REF:([^\]]+)\]", str(description or ""))
            if manual_party_match:
                party_label = manual_party_match.group(1).strip()
                party_type = str(manual_party_type_match.group(1)).strip().lower() if manual_party_type_match else "manual"
            if manual_vehicle_match and not vehicle_label:
                vehicle_label = manual_vehicle_match.group(1).strip()

            operation_type_label = type_labels.get(tx_type, tx_type or "غير محدد")
            payment_method = _normalize_payment_method(op.get("payment_method") or op.get("paymentMethod") or "")
            if not payment_method:
                payment_method = _infer_payment_method_from_lines(lines)
            payment_status = str(op.get("payment_status") or op.get("paymentStatus") or "").strip().lower()
            if not payment_status and payment_method == "credit":
                payment_status = "unpaid"

            normalized_lines = []
            try:
                accounts = _fetch_accounts()
                id_to_code, code_to_name, _ = _build_account_maps(accounts)
                normalized_lines = [ln for ln in (_normalize_line(line, id_to_code, code_to_name) for line in (lines or [])) if ln]
            except Exception:
                normalized_lines = lines or []

            formatted.append(
                {
                    "id": entry.get("id"),
                    "date": entry.get("date", ""),
                    "description": description,
                    "lines": normalized_lines,
                    "total": entry.get("total", 0),
                    "source": source,
                    "transaction_type": tx_type,
                    "transaction_type_label_ar": _transaction_type_label_ar(tx_type),
                    "reference_id": reference_id,
                    "party_type": party_type or "open",
                    "party_label": party_label or "مفتوح",
                    "vehicle_label": vehicle_label,
                    "operation_type_label": operation_type_label,
                    "payment_method": payment_method,
                    "payment_method_label_ar": _payment_method_label_ar(payment_method),
                    "payment_status": payment_status,
                    "payment_status_label_ar": _payment_status_label_ar(payment_status),
                }
            )

        return {"success": True, "data": formatted, "total": len(formatted)}

    except Exception as e:
        print(f"Error in get_journal_entries: {str(e)}")
        # بيانات تجريبية في حالة الخطأ
        return {
            "success": True,
            "data": [
                {
                    "id": "entry-001",
                    "date": "2025-01-20",
                    "description": "قيد بيع خدمة صيانة",
                    "lines": [
                        {
                            "account": "1103",
                            "account_name": "ذمم مدينة",
                            "debit": 5000,
                            "credit": 0,
                        },
                        {
                            "account": "411",
                            "account_name": "إيرادات خدمات",
                            "debit": 0,
                            "credit": 5000,
                        },
                    ],
                    "total": 5000,
                    "source": "demo",
                }
            ],
            "total": 1,
        }


@router.get("/period-close/last")
async def get_last_close(workshop_id: str = Query(...)):
    """🧾 يعيد تاريخ آخر قيد إقفال (لمساعدة الواجهة في إظهار فترة «ما بعد الإقفال»)."""
    try:
        provider = os.environ.get("DB_PROVIDER", "mongo").lower()
        if provider != "supabase":
            return {"success": True, "data": {"last_close_date": None}}
        from supabase_service import SupabaseService
        supa = SupabaseService()
        res = (
            supa.client.table("journal_entries")
            .select("id, date, total, created_at")
            .eq("source", "period_close")
            .order("date", desc=True)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if not res.data:
            return {"success": True, "data": {"last_close_date": None}}
        row = res.data[0]
        return {
            "success": True,
            "data": {
                "last_close_date": row.get("date"),
                "journal_entry_id": row.get("id"),
                "total": row.get("total"),
                "created_at": row.get("created_at"),
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/period-close")
async def close_period(
    workshop_id: str = Query(...),
    payload: dict = Body(default=None),
):
    """
    🧾 قيد إقفال محاسبي صحيح: يصفر الإيرادات والمصروفات إلى حساب «الأرباح المحتجزة» (023).

    منطق المحاسبة:
        - كل حساب إيراد له رصيد دائن ⇒ نخصمه (debit) لإقفاله.
        - كل حساب مصروف له رصيد مدين ⇒ ندفعه (credit) لإقفاله.
        - الفرق (صافي الدخل) يُرحَّل إلى الأرباح المحتجزة:
            • ربح → credit للأرباح المحتجزة
            • خسارة → debit للأرباح المحتجزة

    Body اختياري:
        {
          "as_of_date": "2026-02-11",
          "description": "إقفال الفترة المنتهية في 2026-02-11",
          "equity_account_code": "023"  # افتراضي 023
        }

    Returns: تفاصيل القيد المنشأ + ملخص الإقفال.
    """
    try:
        body = payload or {}
        as_of = body.get("as_of_date") or datetime.now(timezone.utc).date().isoformat()
        description = body.get("description") or f"إقفال الفترة حتى {as_of}"
        equity_code = str(body.get("equity_account_code") or "023").strip()

        provider = os.environ.get("DB_PROVIDER", "mongo").lower()
        if provider != "supabase":
            raise HTTPException(
                status_code=400,
                detail="Period-close requires Supabase provider",
            )
        from supabase_service import SupabaseService
        supa = SupabaseService()

        # ⚡ Idempotency early-check — قبل أي جلب ثقيل (يوفر ~25ث على المسار idempotent)
        existing_close = (
            supa.client.table("journal_entries")
            .select("id, date, total")
            .eq("source", "period_close")
            .eq("date", as_of)
            .limit(1)
            .execute()
        )
        if existing_close.data:
            return {
                "success": True,
                "data": {
                    "closed": False,
                    "message": f"يوجد قيد إقفال مسبق بتاريخ {as_of}",
                    "as_of_date": as_of,
                    "existing_journal_entry_id": existing_close.data[0]["id"],
                },
            }

        # 1) جلب كل الحسابات (لا يوجد عمود workshop_id في accounts)
        accs_res = supa.client.table("accounts").select("*").execute()
        accounts = accs_res.data or []

        # 2) جلب جميع قيود اليومية حتى التاريخ
        try:
            je_res = (
                supa.client.table("journal_entries")
                .select("*")
                .eq("workshop_id", workshop_id)
                .lte("date", as_of)
                .limit(20000)
                .execute()
            )
            entries = je_res.data or []
        except Exception:
            entries = []
        if not entries:
            je_res = (
                supa.client.table("journal_entries")
                .select("*")
                .lte("date", as_of)
                .limit(20000)
                .execute()
            )
            entries = je_res.data or []

        # 3) لكل حساب اجمع debit/credit للوصول إلى الرصيد الحالي
        # نتخطّى قيود period_close السابقة لتجنّب احتسابها كحركة إيراد/مصروف.
        balances: Dict[str, float] = {}
        for je in entries:
            if str(je.get("source") or "").lower() == "period_close":
                continue
            for ln in je.get("lines") or []:
                code = str(ln.get("account") or ln.get("account_code") or "").strip()
                if not code:
                    continue
                dr = float(ln.get("debit") or 0)
                cr = float(ln.get("credit") or 0)
                balances[code] = balances.get(code, 0.0) + dr - cr

        # 4) بناء أسطر قيد الإقفال
        closing_lines = []
        total_revenue_closed = 0.0
        total_expense_closed = 0.0

        for acc in accounts:
            code = str(acc.get("code") or "").strip()
            t = (acc.get("type") or "").lower()
            name = acc.get("name") or acc.get("name_ar") or code
            if not code or code == equity_code:
                continue
            net = balances.get(code, 0.0)
            if abs(net) < 0.01:
                continue
            if t == "revenue":
                # رصيد دائن طبيعي: net سالب (لأن credits > debits) — نقفله بـ debit
                amount = abs(net) if net <= 0 else net
                closing_lines.append({
                    "account": code,
                    "account_name": name,
                    "debit": round(amount, 2),
                    "credit": 0,
                })
                total_revenue_closed += amount
            elif t == "expense":
                # رصيد مدين طبيعي: net موجب — نقفله بـ credit
                amount = abs(net) if net >= 0 else net
                closing_lines.append({
                    "account": code,
                    "account_name": name,
                    "debit": 0,
                    "credit": round(amount, 2),
                })
                total_expense_closed += amount

        if not closing_lines:
            return {
                "success": True,
                "data": {
                    "closed": False,
                    "message": "لا توجد أرصدة إيرادات/مصروفات للإقفال.",
                    "as_of_date": as_of,
                },
            }

        # 5) سطر التسوية إلى الأرباح المحتجزة
        equity_acc = next((a for a in accounts if str(a.get("code") or "") == equity_code), None)
        equity_name = (equity_acc or {}).get("name") or "أرباح محتجزة"
        net_income = round(total_revenue_closed - total_expense_closed, 2)
        if net_income >= 0:
            # ربح ⇒ credit للأرباح المحتجزة
            closing_lines.append({
                "account": equity_code,
                "account_name": equity_name,
                "debit": 0,
                "credit": net_income,
            })
        else:
            # خسارة ⇒ debit للأرباح المحتجزة
            closing_lines.append({
                "account": equity_code,
                "account_name": equity_name,
                "debit": abs(net_income),
                "credit": 0,
            })

        # 6) تحقق توازن (إجباري — الجدار سيرفض غير ذلك)
        total_dr = round(sum(float(ln["debit"]) for ln in closing_lines), 2)
        total_cr = round(sum(float(ln["credit"]) for ln in closing_lines), 2)
        if abs(total_dr - total_cr) > 0.009:
            raise HTTPException(
                status_code=500,
                detail=f"بناء قيد الإقفال أنتج فرقاً: مدين {total_dr} ≠ دائن {total_cr}",
            )

        # 7) أدرج القيد عبر نفس مسار create_journal_entry (يضمن الجدار)
        new_entry = {
            "id": str(uuid.uuid4()),
            "workshop_id": workshop_id,
            "date": as_of,
            "description": description,
            "transaction_type": "closing",
            "source": "period_close",
            "lines": closing_lines,
            "total": total_dr,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            from core import accounting_engine
            accounting_engine.post_entry(new_entry)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"فشل حفظ قيد الإقفال: {e}")

        # 8) تحديث رصيد الحسابات (balance=0 للإيرادات/المصروفات، يضاف net للأرباح المحتجزة)
        try:
            for acc in accounts:
                t = (acc.get("type") or "").lower()
                if t in ("revenue", "expense"):
                    supa.client.table("accounts").update({"balance": 0}).eq("id", acc["id"]).execute()
            if equity_acc:
                old_bal = float(equity_acc.get("balance") or 0)
                new_bal = round(old_bal + net_income, 2)
                supa.client.table("accounts").update({"balance": new_bal}).eq("id", equity_acc["id"]).execute()
        except Exception as e:
            print(f"period-close: balance update warning: {e}")

        return {
            "success": True,
            "data": {
                "closed": True,
                "as_of_date": as_of,
                "journal_entry_id": new_entry["id"],
                "total_revenue_closed": round(total_revenue_closed, 2),
                "total_expense_closed": round(total_expense_closed, 2),
                "net_income_transferred": net_income,
                "equity_account": {"code": equity_code, "name": equity_name},
                "lines_count": len(closing_lines),
                "total_debit": total_dr,
                "total_credit": total_cr,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/journal-entries")
async def create_journal_entry(entry: dict, request: Request, workshop_id: str = Query(...)):
    """إنشاء قيد محاسبي يدوي جديد في Supabase مع نوع حركة واضح.

    المثال المتوقع للـ payload من الواجهة:
    {
        "date": "2026-01-25",
        "description": "شراء مواد تنظيف للورشة",
        "transaction_type": "purchase",  # purchase | sale | expense | other
        "lines": [...],
        "total": 500
    }

    🔒 Idempotency: يدعم header `Idempotency-Key` لمنع القيود المكررة عند النقر المزدوج أو إعادة المحاولة.
    """
    # 🔒 Idempotency check
    from idempotency import get_idempotency_key, get_cached_response, store_response
    _idem_key = get_idempotency_key(request)
    _cached = get_cached_response(_idem_key) if _idem_key else None
    if _cached is not None:
        return {**_cached, "idempotent_replay": True}

    try:
        def _to_decimal(value: Any) -> Decimal:
            try:
                return Decimal(str(value if value is not None else 0))
            except (InvalidOperation, ValueError, TypeError):
                return Decimal("0")

        raw_lines = entry.get("lines", [])
        if not isinstance(raw_lines, list) or len(raw_lines) == 0:
            raise HTTPException(status_code=400, detail="يجب إدخال سطور القيد")

        normalized_lines = []
        total_debit = Decimal("0")
        total_credit = Decimal("0")

        for idx, line in enumerate(raw_lines):
            if not isinstance(line, dict):
                raise HTTPException(status_code=400, detail=f"سطر غير صالح عند الموضع {idx + 1}")

            debit = _to_decimal(line.get("debit"))
            credit = _to_decimal(line.get("credit"))

            if debit < 0 or credit < 0:
                raise HTTPException(status_code=400, detail="لا يسمح بقيم سالبة في سطور القيد")

            total_debit += debit
            total_credit += credit

            normalized_lines.append(
                {
                    "account": line.get("account"),
                    "account_name": line.get("account_name") or "",
                    "debit": float(debit.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                    "credit": float(credit.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                }
            )

        diff = (total_debit - total_credit).copy_abs()
        if diff > Decimal("0.009"):
            # 🛡️ Firewall: log rejection event before raising
            firewall_state.log_event(
                "unbalanced_rejection",
                {
                    "reason": "debit_credit_mismatch",
                    "debit": float(total_debit),
                    "credit": float(total_credit),
                    "drift": float(diff),
                    "description": entry.get("description") or "",
                    "workshop_id": workshop_id,
                    "source": entry.get("source") or "manual",
                },
            )
            raise HTTPException(
                status_code=400,
                detail=f"القيد غير متوازن: مدين {float(total_debit):.2f} ≠ دائن {float(total_credit):.2f}",
            )

        normalized_total = total_debit.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        transaction_type = entry.get("transaction_type", "manual")

        # Base entry data with required fields
        entry_data = {
            "id": str(uuid.uuid4()),
            "workshop_id": workshop_id,
            "date": entry.get("date", datetime.now(timezone.utc).isoformat()),
            "description": entry.get("description", ""),
            "lines": normalized_lines,
            "total": float(normalized_total),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source": entry.get("source", "manual"),
            "reference_id": entry.get("reference_id"),
        }

        # 🏦 المسار المركزي: AccountingEngine (توازن + منع تكرار + أعمدة متكيّفة)
        full_entry_data = {**entry_data, "transaction_type": transaction_type}
        from core import accounting_engine
        response_data = accounting_engine.post_entry(full_entry_data)

        invalidate_finance_caches()
        result = {
            "success": True,
            "message": "تم إنشاء القيد المحاسبي بنجاح",
            "id": (response_data[0].get("id") if response_data else entry_data["id"]),
            "data": response_data,
        }
        if _idem_key:
            try:
                store_response(_idem_key, result)
            except Exception:
                pass
        return result

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in create_journal_entry: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "message": "فشل في إنشاء القيد المحاسبي",
        }


@router.get("/operations")
async def get_financial_operations(
    workshop_id: str = Query(...), skip: int = Query(0), limit: int = Query(50)
):
    """
    جميع العمليات المالية (مبيعات، مشتريات، مصروفات)
    """
    # يمكن لاحقاً ربطها بـ operations collection في MongoDB
    return {"success": True, "data": [], "total": 0}


@router.put("/journal-entries/{entry_id}")
async def update_journal_entry(
    entry_id: str, entry: dict, workshop_id: str = Query(...)
):
    """تعديل قيد محاسبي يدوي في Supabase مع إمكانية تعديل نوع الحركة."""
    try:
        if not supabase:
            raise Exception("Supabase not connected")

        existing = (
            supabase.table("journal_entries")
            .select("*")
            .eq("id", entry_id)
            .eq("workshop_id", workshop_id)
            .execute()
        )

        if not existing.data or len(existing.data) == 0:
            return {
                "success": False,
                "error": "القيد غير موجود",
                "message": "لم يتم العثور على القيد المطلوب",
            }

        # Base update data
        update_data = {
            "date": entry.get("date"),
            "description": entry.get("description", ""),
            "lines": entry.get("lines", []),
            "total": entry.get("total", 0),
            "updated_at": datetime.now().isoformat(),
        }

        # Add transaction_type if provided
        if entry.get("transaction_type") is not None:
            update_data["transaction_type"] = entry.get("transaction_type")

        # Remove None values
        update_data = {k: v for k, v in update_data.items() if v is not None}

        try:
            response = (
                supabase.table("journal_entries")
                .update(update_data)
                .eq("id", entry_id)
                .execute()
            )
            
            invalidate_finance_caches()
            return {
                "success": True,
                "message": "تم تحديث القيد المحاسبي بنجاح",
                "data": response.data,
            }
            
        except Exception as schema_error:
            # If transaction_type column doesn't exist, try without it
            if "transaction_type" in update_data:
                print(f"Schema error with transaction_type, trying without: {schema_error}")
                update_data_basic = {k: v for k, v in update_data.items() if k != "transaction_type"}
                
                response = (
                    supabase.table("journal_entries")
                    .update(update_data_basic)
                    .eq("id", entry_id)
                    .execute()
                )
                
                invalidate_finance_caches()
                return {
                    "success": True,
                    "message": "تم تحديث القيد المحاسبي بنجاح (بدون transaction_type)",
                    "data": response.data,
                    "note": "تم التحديث بدون حقل transaction_type - يحتاج تحديث قاعدة البيانات"
                }
            else:
                raise schema_error

    except Exception as e:
        print(f"Error in update_journal_entry: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "message": "فشل في تحديث القيد المحاسبي",
        }


@router.delete("/journal-entries/{entry_id}")
async def delete_journal_entry(entry_id: str, workshop_id: str = Query(...)):
    """
    حذف قيد محاسبي يدوي من Supabase
    """
    try:
        if not supabase:
            raise Exception("Supabase not connected")

        # التحقق من وجود القيد
        existing = (
            supabase.table("journal_entries")
            .select("*")
            .eq("id", entry_id)
            .eq("workshop_id", workshop_id)
            .execute()
        )

        if not existing.data or len(existing.data) == 0:
            # بعض القيود القديمة قد لا تحتوي workshop_id أو تحتوي قيمة مختلفة
            # لإزالة العائق على المستخدم، نحاول التحقق/الحذف بالـ id فقط.
            existing2 = (
                supabase.table("journal_entries")
                .select("*")
                .eq("id", entry_id)
                .execute()
            )
            if not existing2.data or len(existing2.data) == 0:
                return {
                    "success": False,
                    "error": "القيد غير موجود",
                    "message": "لم يتم العثور على القيد المطلوب",
                }

        # حذف القيد
        supabase.table("journal_entries").delete().eq("id", entry_id).execute()

        invalidate_finance_caches()
        return {"success": True, "message": "تم حذف القيد المحاسبي بنجاح"}

    except Exception as e:
        print(f"Error in delete_journal_entry: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "message": "فشل في حذف القيد المحاسبي",
        }


@router.get("/journal-entries/{entry_id}")
async def get_journal_entry(entry_id: str, workshop_id: str = Query(...)):
    """
    جلب قيد محاسبي واحد
    """
    try:
        if not supabase:
            raise Exception("Supabase not connected")

        response = (
            supabase.table("journal_entries")
            .select("*")
            .eq("id", entry_id)
            .eq("workshop_id", workshop_id)
            .execute()
        )

        if not response.data or len(response.data) == 0:
            return {
                "success": False,
                "error": "القيد غير موجود",
                "message": "لم يتم العثور على القيد المطلوب",
            }

        entry = response.data[0]
        normalized_entry = {
            "id": entry.get("id"),
            "date": entry.get("date", ""),
            "description": entry.get("description", "قيد يدوي"),
            "lines": entry.get("lines", []),
            "total": entry.get("total", 0),
            "source": entry.get("source", "manual"),
            "reference_id": entry.get("reference_id"),
        }
        return {
            "success": True,
            "data": normalized_entry,
            **normalized_entry,
        }

    except Exception as e:
        print(f"Error in get_journal_entry: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "message": "فشل في جلب القيد المحاسبي",
        }




# -------------------- Accounts Receivable (AR) Reports --------------------

def _parse_date_str(d: Optional[str]) -> Optional[str]:
    if not d:
        return None
    if not isinstance(d, str):
        return None
    return d


def _fetch_credit_sales_ops(
    workshop_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """Fetch credit sales/service operations (AR invoices) from Supabase operations table.

    Note: some schemas may not have workshop_id on operations; we try to scope if possible.
    """
    if not supabase:
        raise Exception("Supabase not connected")

    def _build(scoped: bool):
        q = (
            supabase.table("operations")
            .select("*")
            .in_("type", ["sale", "service"])
            .eq("payment_method", "credit")
        )
        if scoped:
            q = q.eq("workshop_id", workshop_id)
        if start_date:
            q = q.gte("op_date", start_date)
        if end_date:
            q = q.lte("op_date", end_date)
        return q.order("op_date", desc=False)

    # Try scoped first, fallback to unscoped
    try:
        return _build(scoped=True).execute().data or []
    except Exception:
        return _build(scoped=False).execute().data or []


def _fetch_payment_entries(
    workshop_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """Fetch payment journal entries that settle AR (source=operation_payment).

    Important:
    - We scope by workshop_id to avoid cross-workshop contamination.
    - Payments without reference_id are ignored downstream (can't be allocated to invoices).
    """
    if not supabase:
        raise Exception("Supabase not connected")

    q = (
        supabase.table("journal_entries")
        .select("*")
        .eq("source", "operation_payment")
        .eq("workshop_id", workshop_id)
    )
    if start_date:
        q = q.gte("date", start_date)
    if end_date:
        q = q.lte("date", end_date)
    return q.order("date", desc=False).execute().data or []


def _op_to_customer(op_row: dict) -> str:
    return (op_row.get("partner_name") or "").strip() or "(بدون اسم)"


def _op_date(op_row: dict) -> str:
    return op_row.get("op_date") or op_row.get("date") or ""


def _due_date_from_op_date(op_date_str: str) -> Optional[str]:
    try:
        # op_date_str may be ISO with timezone; datetime.fromisoformat can parse "+00:00"
        d = op_date_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(d)
        return (dt + timedelta(days=30)).date().isoformat()
    except Exception:
        return None


def _to_date(dt_str: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except Exception:
        try:
            return datetime.fromisoformat(dt_str)
        except Exception:
            return None


def _payment_amount_affecting_ar(entry: dict) -> float:
    """Return the amount that credits AR (1103/legacy 113) from a payment journal entry."""
    try:
        lines = entry.get("lines") or []
        amt = 0.0
        for ln in lines:
            if str(ln.get("account")) in AR_ACCOUNT_CODES:
                amt += float(ln.get("credit") or 0)
        if amt > 0:
            return amt
    except Exception:
        pass
    try:
        return float(entry.get("total") or 0)
    except Exception:
        return 0.0


@router.get("/ar/ledger")
async def ar_ledger(
    workshop_id: str = Query(...),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    """دفتر الأستاذ لحساب ذمم مدينة عملاء (1103).

    المصدر:
    - مبيعات آجل من operations (payment_method='credit') → زيادة AR
    - تحصيلات من journal_entries (source='operation_payment') → تخفيض AR
    """
    try:
        start_date = _parse_date_str(start_date)
        end_date = _parse_date_str(end_date)

        ledger_ar = build_current_visit_ar_snapshot(workshop_id, end_date=end_date)
        ledger_rows = []
        balance = 0.0
        for row in sorted(ledger_ar["ledger_rows"], key=lambda item: str(item.get("date") or "")):
            amount = float(row.get("amount") or 0)
            if start_date:
                # ledger_rows are current snapshot rows; date filtering remains handled by _fetch_journal_entries end_date.
                pass
            balance += amount
            ledger_rows.append({
                "date": row.get("date"),
                "customer": row.get("customer"),
                "type": "sale" if amount > 0 else "payment",
                "reference_id": row.get("reference_id"),
                "debit": round(amount, 2) if amount > 0 else 0.0,
                "credit": round(abs(amount), 2) if amount < 0 else 0.0,
                "description": row.get("description"),
                "journal_entry_id": row.get("journal_entry_id"),
                "source": row.get("source") or "vehicle_visit_current_ar",
                "running_balance": round(balance, 2),
            })
        return {"success": True, "data": {"account": {"code": "1103", "name": "ذمم مدينة عملاء"}, "rows": ledger_rows, "ending_balance": round(balance, 2)}}

        # نحتاج العمليات حتى end_date لربط التحصيلات حتى لو كانت الفاتورة قبل start_date
        ops_all = _filter_live_operations(_fetch_credit_sales_ops(workshop_id, end_date=end_date), workshop_id, keep_standalone=False)
        op_by_id = {str(o.get("id")): o for o in (ops_all or []) if o.get("id")}

        # صفوف الفواتير ضمن الفترة المطلوبة
        ops_in_period = _filter_live_operations(_fetch_credit_sales_ops(workshop_id, start_date=start_date, end_date=end_date), workshop_id, keep_standalone=False)
        pays = _fetch_payment_entries(workshop_id, start_date=start_date, end_date=end_date)

        rows = []
        # Debits from credit sales
        for op in ops_in_period:
            total = float(op.get("total") or 0)
            if total <= 0:
                continue
            rows.append(
                {
                    "date": _op_date(op),
                    "customer": _op_to_customer(op),
                    "type": "invoice_credit_sale",
                    "reference_id": str(op.get("id")),
                    "debit": round(total, 2),
                    "credit": 0.0,
                    "description": op.get("notes") or "فاتورة آجل",
                }
            )

        # Credits from payments
        for je in pays:
            ref = str(je.get("reference_id") or "")
            if not ref:
                continue
            # تجاهل أي تحصيلات legacy غير مرتبطة بفاتورة آجل موجودة
            op_ref = op_by_id.get(ref)
            if not op_ref:
                continue

            amt = _payment_amount_affecting_ar(je)
            if amt <= 0:
                continue

            customer = _op_to_customer(op_ref)

            rows.append(
                {
                    "date": je.get("date"),
                    "customer": customer,
                    "type": "payment",
                    "reference_id": str(ref or ""),
                    "debit": 0.0,
                    "credit": round(float(amt), 2),
                    "description": je.get("description") or "تحصيل/سداد",
                    "journal_entry_id": je.get("id"),
                    "source": je.get("source"),
                }
            )

        # sort by date
        def sort_key(r):
            dt = _to_date(r.get("date") or "")
            if dt is None:
                return datetime.min.replace(tzinfo=None)
            # normalize timezone-aware to naive for safe compare
            if getattr(dt, "tzinfo", None) is not None:
                return dt.replace(tzinfo=None)
            return dt

        rows.sort(key=sort_key)

        balance = 0.0
        for r in rows:
            balance += float(r.get("debit") or 0) - float(r.get("credit") or 0)
            r["running_balance"] = round(balance, 2)

        return {
            "success": True,
            "data": {
                "account": {"code": "1103", "name": "ذمم مدينة عملاء"},
                "rows": rows,
                "ending_balance": round(balance, 2),
            },
        }

    except Exception as e:
        return {"success": False, "error": str(e), "data": {"rows": []}}


@router.get("/ar/customers")
async def ar_customers(
    workshop_id: str = Query(...),
    as_of: str = Query(..., description="YYYY-MM-DD"),
    include_today: bool = Query(True, description="لإدراج حركات اليوم عند اختلاف التوقيت"),
):
    """أرصدة العملاء (ذمم مدينة) حتى تاريخ محدد."""
    try:
        as_of = _parse_date_str(as_of) or datetime.now().date().isoformat()

        # Use end-of-day cutoff to avoid timezone edge cases when op_date is stored with timezone
        # Example: op_date=2026-01-29T14:xxZ should be included for as_of=2026-01-29
        as_of_eod = f"{as_of}T23:59:59Z" if include_today else as_of

        ledger_ar = build_current_visit_ar_snapshot(workshop_id, end_date=as_of_eod)
        return {"success": True, "data": {"as_of": as_of, "total_ar": ledger_ar["total_ar"], "customers": ledger_ar["customers"], "vehicles": ledger_ar["vehicles"], "totals": ledger_ar["totals"]}}

        # all credit ops up to as_of (EOD)
        ops = _filter_live_operations(_fetch_credit_sales_ops(workshop_id, end_date=as_of_eod), workshop_id, keep_standalone=False)
        pays = _fetch_payment_entries(workshop_id, end_date=as_of_eod)

        sales_by_op = {}
        cust_by_op = {}
        for op in ops:
            op_id = str(op.get("id"))
            total = float(op.get("total") or 0)
            if total <= 0:
                continue
            sales_by_op[op_id] = sales_by_op.get(op_id, 0.0) + total
            cust_by_op[op_id] = _op_to_customer(op)

        paid_by_op = {}
        for je in pays:
            ref = str(je.get("reference_id") or "")
            if not ref:
                continue
            amt = _payment_amount_affecting_ar(je)
            if amt <= 0:
                continue
            paid_by_op[ref] = paid_by_op.get(ref, 0.0) + float(amt)

        balances = {}
        for op_id, inv_total in sales_by_op.items():
            paid = paid_by_op.get(op_id, 0.0)
            remaining = round(max(0.0, inv_total - paid), 2)
            if remaining <= 0:
                continue
            customer = cust_by_op.get(op_id, "(غير معروف)")
            balances[customer] = round(balances.get(customer, 0.0) + remaining, 2)

        customers = [
            {"customer": c, "balance": b}
            for c, b in sorted(balances.items(), key=lambda x: x[0])
        ]
        total_ar = round(sum(b["balance"] for b in customers), 2)

        return {
            "success": True,
            "data": {
                "as_of": as_of,
                "customers": customers,
                "total_ar": total_ar,
                "check": {
                    "sum_customer_balances": total_ar,
                    "ar_account_balance": total_ar,
                },
            },
        }

    except Exception as e:
        return {"success": False, "error": str(e), "data": {"customers": []}}


@router.get("/reports/ar-customers")
async def reports_ar_customers(
    workshop_id: str = Query(...),
    as_of: Optional[str] = Query(None),
    include_today: bool = Query(True),
):
    """Compatibility alias for AR customers reporting endpoint."""
    resolved_as_of = as_of or datetime.now().date().isoformat()
    return await ar_customers(
        workshop_id=workshop_id,
        as_of=resolved_as_of,
        include_today=include_today,
    )


@router.get("/ar/ledger/export")
async def export_ar_ledger_excel(
    workshop_id: str = Query(...),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    as_of: Optional[str] = Query(None),
    customer: Optional[str] = Query(None),
):
    ledger_response = await ar_ledger(
        workshop_id=workshop_id,
        start_date=start_date,
        end_date=end_date,
    )
    if not ledger_response.get("success"):
        raise HTTPException(status_code=400, detail=ledger_response.get("error") or "تعذر تجهيز دفتر الذمم")

    export_as_of = _parse_date_str(as_of) or _parse_date_str(end_date) or datetime.now().date().isoformat()
    customers_response = await ar_customers(workshop_id=workshop_id, as_of=export_as_of, include_today=True)
    aging_response = await ar_aging(workshop_id=workshop_id, as_of=export_as_of)
    statement_response = None
    if customer:
        statement_response = await ar_customer_statement(
            workshop_id=workshop_id,
            customer=customer,
            start_date=start_date,
            end_date=end_date,
        )

    workbook = openpyxl.Workbook()
    summary_sheet = workbook.active
    summary_sheet.title = "AR-1103-Summary"

    ledger_data = ledger_response.get("data") or {}
    customers_data = customers_response.get("data") or {}
    aging_data = aging_response.get("data") or {}

    summary_rows = [
        ("ورشة", workshop_id),
        ("الحساب", "1103 - ذمم مدينة عملاء"),
        ("من", start_date or "بداية مفتوحة"),
        ("إلى", end_date or export_as_of),
        ("حتى تاريخ", export_as_of),
        ("العميل المحدد", customer or "الكل"),
        ("عدد سطور الدفتر", len(ledger_data.get("rows") or [])),
        ("الرصيد الختامي", _safe_float(ledger_data.get("ending_balance"))),
        ("إجمالي ذمم العملاء", _safe_float(customers_data.get("total_ar"))),
    ]
    for row_index, (label, value) in enumerate(summary_rows, start=1):
        summary_sheet.cell(row=row_index, column=1, value=label)
        summary_sheet.cell(row=row_index, column=2, value=value)

    summary_sheet.cell(row=12, column=1, value="تقادم الذمم")
    summary_sheet.append(["الفئة", "المبلغ"])
    for label, value in [
        ("0-30", _safe_float((aging_data.get("buckets") or {}).get("0_30"))),
        ("31-60", _safe_float((aging_data.get("buckets") or {}).get("31_60"))),
        ("61-90", _safe_float((aging_data.get("buckets") or {}).get("61_90"))),
        ("90+", _safe_float((aging_data.get("buckets") or {}).get("90_plus"))),
    ]:
        summary_sheet.append([label, value])

    customers_sheet = workbook.create_sheet("Customers")
    customers_sheet.append(["العميل", "الرصيد"])
    for row in customers_data.get("customers") or []:
        customers_sheet.append([
            row.get("customer") or "(غير معروف)",
            _safe_float(row.get("balance")),
        ])

    ledger_sheet = workbook.create_sheet("AR-1103-Ledger")
    ledger_sheet.append([
        "التاريخ",
        "العميل",
        "النوع",
        "المرجع",
        "مدين",
        "دائن",
        "الرصيد الجاري",
        "الوصف",
        "المصدر",
        "قيد اليومية",
    ])
    for row in ledger_data.get("rows") or []:
        ledger_sheet.append([
            str(row.get("date") or "")[:10],
            row.get("customer") or "",
            row.get("type") or "",
            row.get("reference_id") or "",
            _safe_float(row.get("debit")),
            _safe_float(row.get("credit")),
            _safe_float(row.get("running_balance")),
            row.get("description") or "",
            row.get("source") or "",
            row.get("journal_entry_id") or "",
        ])

    aging_sheet = workbook.create_sheet("Open-Invoices")
    aging_sheet.append([
        "رقم العملية",
        "العميل",
        "تاريخ الفاتورة",
        "تاريخ الاستحقاق",
        "أيام التأخر",
        "المتبقي",
        "الفئة",
    ])
    for row in aging_data.get("open_invoices") or []:
        aging_sheet.append([
            row.get("operation_id") or "",
            row.get("customer") or "",
            row.get("invoice_date") or "",
            row.get("due_date") or "",
            _safe_float(row.get("days_past_due")),
            _safe_float(row.get("remaining")),
            row.get("bucket") or "",
        ])

    if statement_response and statement_response.get("success"):
        statement_data = statement_response.get("data") or {}
        statement_sheet = workbook.create_sheet("Customer-Statement")
        statement_sheet.append(["العميل", statement_data.get("customer") or customer or ""])
        statement_sheet.append(["الرصيد الختامي", _safe_float(statement_data.get("ending_balance"))])
        statement_sheet.append([])
        statement_sheet.append(["التاريخ", "النوع", "المرجع", "مدين", "دائن", "الرصيد الجاري", "الوصف"])
        for row in statement_data.get("rows") or []:
            statement_sheet.append([
                str(row.get("date") or "")[:10],
                row.get("type") or "",
                row.get("reference_id") or "",
                _safe_float(row.get("debit")),
                _safe_float(row.get("credit")),
                _safe_float(row.get("running_balance")),
                row.get("description") or "",
            ])

    for sheet in workbook.worksheets:
        sheet.freeze_panes = "A2"
        for column in sheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                value = "" if cell.value is None else str(cell.value)
                max_length = max(max_length, len(value))
            sheet.column_dimensions[column_letter].width = min(max(max_length + 2, 12), 40)

    buffer = io.BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    filename = f"ar-1103-reconciliation-{export_as_of}.xlsx"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


@router.get("/ar/customer-statement")
async def ar_customer_statement(
    workshop_id: str = Query(...),
    customer: str = Query(...),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    """كشف حساب لعميل محدد ضمن فترة."""
    try:
        customer = (customer or "").strip()
        start_date = _parse_date_str(start_date)
        end_date = _parse_date_str(end_date)

        ops = _filter_live_operations(_fetch_credit_sales_ops(workshop_id, start_date=start_date, end_date=end_date), workshop_id, keep_standalone=False)
        pays = _fetch_payment_entries(workshop_id, start_date=start_date, end_date=end_date)

        # map operation totals for this customer
        customer_ops = {}
        rows = []
        for op in ops:
            if _op_to_customer(op) != customer:
                continue
            op_id = str(op.get("id"))
            total = float(op.get("total") or 0)
            if total <= 0:
                continue
            customer_ops[op_id] = total
            rows.append(
                {
                    "date": _op_date(op),
                    "type": "invoice",
                    "reference_id": op_id,
                    "debit": round(total, 2),
                    "credit": 0.0,
                    "description": op.get("notes") or "فاتورة آجل",
                }
            )

        # payments linked to those operations
        for je in pays:
            ref = str(je.get("reference_id") or "")
            if not ref or ref not in customer_ops:
                continue
            amt = _payment_amount_affecting_ar(je)
            if amt <= 0:
                continue
            rows.append(
                {
                    "date": je.get("date"),
                    "type": "payment",
                    "reference_id": ref,
                    "debit": 0.0,
                    "credit": round(float(amt), 2),
                    "description": je.get("description") or "تحصيل",
                    "journal_entry_id": je.get("id"),
                }
            )

        def _row_dt(r):
            dt = _to_date(r.get("date") or "")
            if dt is None:
                return datetime.min.replace(tzinfo=None)
            if getattr(dt, "tzinfo", None) is not None:
                return dt.replace(tzinfo=None)
            return dt

        rows.sort(key=_row_dt)

        bal = 0.0
        for r in rows:
            bal += float(r.get("debit") or 0) - float(r.get("credit") or 0)
            r["running_balance"] = round(bal, 2)

        return {
            "success": True,
            "data": {
                "customer": customer,
                "rows": rows,
                "ending_balance": round(bal, 2),
            },
        }

    except Exception as e:
        return {"success": False, "error": str(e), "data": {"rows": []}}


@router.get("/ar/aging")
async def ar_aging(
    workshop_id: str = Query(...),
    as_of: str = Query(...),
):
    """Aging Report للذمم المدينة.

    التصنيف يعتمد على تاريخ الاستحقاق = تاريخ العملية + 30 يوم.
    """
    try:
        as_of = _parse_date_str(as_of) or datetime.now().date().isoformat()
        as_of_dt = _to_date(as_of) or datetime.now()

        ops = _filter_live_operations(_fetch_credit_sales_ops(workshop_id, end_date=as_of), workshop_id, keep_standalone=False)
        pays = _fetch_payment_entries(workshop_id, end_date=as_of)

        paid_by_op = {}
        for je in pays:
            ref = str(je.get("reference_id") or "")
            if not ref:
                continue
            amt = _payment_amount_affecting_ar(je)
            if amt <= 0:
                continue
            paid_by_op[ref] = paid_by_op.get(ref, 0.0) + float(amt)

        buckets = {
            "0_30": 0.0,
            "31_60": 0.0,
            "61_90": 0.0,
            "90_plus": 0.0,
        }
        open_invoices = []

        for op in ops:
            op_id = str(op.get("id"))
            inv_total = float(op.get("total") or 0)
            if inv_total <= 0:
                continue
            paid = paid_by_op.get(op_id, 0.0)
            remaining = round(max(0.0, inv_total - paid), 2)
            if remaining <= 0:
                continue

            op_date_str = _op_date(op)
            due = _due_date_from_op_date(op_date_str)
            due_dt = _to_date(due) if due else None
            days_past_due = 0
            if due_dt:
                days_past_due = (as_of_dt.date() - due_dt.date()).days
            if days_past_due <= 30:
                buckets["0_30"] += remaining
                bucket = "0-30"
            elif days_past_due <= 60:
                buckets["31_60"] += remaining
                bucket = "31-60"
            elif days_past_due <= 90:
                buckets["61_90"] += remaining
                bucket = "61-90"
            else:
                buckets["90_plus"] += remaining
                bucket = "90+"

            open_invoices.append(
                {
                    "operation_id": op_id,
                    "customer": _op_to_customer(op),
                    "invoice_date": op_date_str,
                    "due_date": due,
                    "days_past_due": days_past_due,
                    "remaining": remaining,
                    "bucket": bucket,
                }
            )

        total = round(sum(buckets.values()), 2)
        buckets = {k: round(v, 2) for k, v in buckets.items()}

        return {
            "success": True,
            "data": {
                "as_of": as_of,
                "buckets": buckets,
                "total_ar": total,
                "open_invoices": open_invoices,
            },
        }

    except Exception as e:
        return {"success": False, "error": str(e), "data": {"buckets": {}}}


@router.get("/ar/turnover")
async def ar_turnover(
    workshop_id: str = Query(...),
    start_date: str = Query(...),
    end_date: str = Query(...),
    credit_sales_total: float = Query(..., description="إجمالي المبيعات الآجلة خلال الفترة"),
):
    """حساب معدل دوران الذمم المدينة خلال فترة.

    turnover = credit_sales_total / avg_receivables
    avg_receivables = (opening + closing) / 2
    """
    try:
        start_date = _parse_date_str(start_date) or start_date
        end_date = _parse_date_str(end_date) or end_date

        open_resp = await ar_customers(workshop_id=workshop_id, as_of=start_date)
        close_resp = await ar_customers(workshop_id=workshop_id, as_of=end_date)

        opening = float(((open_resp.get("data") or {}).get("total_ar") or 0))
        closing = float(((close_resp.get("data") or {}).get("total_ar") or 0))
        avg = (opening + closing) / 2.0 if (opening + closing) != 0 else 0.0

        turnover = None
        days = None
        if avg > 0:
            turnover = float(credit_sales_total) / avg
            if turnover > 0:
                days = 365.0 / turnover

        return {
            "success": True,
            "data": {
                "period": {"start_date": start_date, "end_date": end_date},
                "credit_sales_total": float(credit_sales_total),
                "opening_receivables": round(opening, 2),
                "closing_receivables": round(closing, 2),
                "avg_receivables": round(avg, 2),
                "turnover": round(turnover, 4) if turnover is not None else None,
                "days_sales_outstanding": round(days, 2) if days is not None else None,
            },
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/reports/operation-trace")
async def get_operation_trace_report(
    workshop_id: str = Query(...),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    include_rakan: bool = Query(False),
):
    """شرح مسار الأرقام المالية حسب نوع العملية والقيود الناتجة."""
    try:
        end_date = end_date or datetime.now().strftime("%Y-%m-%d")
        start_date = start_date or (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

        operations = _fetch_operations_for_reconciliation(
            workshop_id=workshop_id,
            start_date=start_date,
            end_date=end_date,
        )
        if not include_rakan:
            operations = [op for op in operations if not _is_rakan_operation_row(op)]

        accounts = _fetch_accounts()
        id_to_code, code_to_name, _ = _build_account_maps(accounts)
        entries = _fetch_journal_entries(
            workshop_id=workshop_id,
            start_date=start_date,
            end_date=end_date,
            limit=15000,
            include_rakan=include_rakan,
        )

        op_type_by_id: Dict[str, str] = {}
        by_type: Dict[str, Dict[str, Any]] = {}

        for op in operations:
            op_type = _normalize_operation_type_for_reconciliation(op.get("type")) or "other"
            op_id = str(op.get("id") or "").strip()
            if op_id:
                op_type_by_id[op_id] = op_type

            row = by_type.setdefault(op_type, {
                "type": op_type,
                "type_label_ar": _transaction_type_label_ar(op_type),
                "operations_count": 0,
                "operations_total": 0.0,
                "journal_entries_count": 0,
                "journal_entries_total": 0.0,
                "payment_methods": {},
                "impact": {
                    "cash": {"debit": 0.0, "credit": 0.0, "net": 0.0},
                    "bank": {"debit": 0.0, "credit": 0.0, "net": 0.0},
                    "ar": {"debit": 0.0, "credit": 0.0, "net": 0.0},
                    "ap": {"debit": 0.0, "credit": 0.0, "net": 0.0},
                    "assets": {"debit": 0.0, "credit": 0.0, "net": 0.0},
                    "revenue": {"debit": 0.0, "credit": 0.0, "net": 0.0},
                    "expenses": {"debit": 0.0, "credit": 0.0, "net": 0.0},
                },
                "accounts_touched": {},
            })
            row["operations_count"] += 1
            row["operations_total"] += _safe_float(op.get("total"))
            pay_method = _normalize_payment_method(op.get("payment_method") or op.get("paymentMethod") or "unknown")
            row["payment_methods"][pay_method] = row["payment_methods"].get(pay_method, 0) + 1

        def account_bucket(code: str) -> str:
            c = str(code or "")
            if c in ("003", "1101"):
                return "cash"
            if c in ("004", "006", "1102", "1104"):
                return "bank"
            if c in ("005", "1103"):
                return "ar"
            if c in ("2101", "211"):
                return "ap"
            try:
                n = int(c)
                if 1 <= n <= 13:
                    return "assets"
                if 14 <= n <= 18:
                    return "ap"
                if 25 <= n <= 29:
                    return "revenue"
                if 30 <= n <= 59:
                    return "expenses"
            except (ValueError, TypeError):
                pass
            if c.startswith("1"):
                return "assets"
            if c.startswith("4"):
                return "revenue"
            if c.startswith("5") or c.startswith("6"):
                return "expenses"
            return "assets"

        for entry in entries:
            tx_type = _normalize_operation_type_for_reconciliation(entry.get("transaction_type"))
            ref = str(entry.get("reference_id") or "").strip()
            if ref and ref in op_type_by_id:
                tx_type = op_type_by_id[ref]
            tx_type = tx_type or "other"
            row = by_type.setdefault(tx_type, {
                "type": tx_type,
                "type_label_ar": _transaction_type_label_ar(tx_type),
                "operations_count": 0,
                "operations_total": 0.0,
                "journal_entries_count": 0,
                "journal_entries_total": 0.0,
                "payment_methods": {},
                "impact": {
                    "cash": {"debit": 0.0, "credit": 0.0, "net": 0.0},
                    "bank": {"debit": 0.0, "credit": 0.0, "net": 0.0},
                    "ar": {"debit": 0.0, "credit": 0.0, "net": 0.0},
                    "ap": {"debit": 0.0, "credit": 0.0, "net": 0.0},
                    "assets": {"debit": 0.0, "credit": 0.0, "net": 0.0},
                    "revenue": {"debit": 0.0, "credit": 0.0, "net": 0.0},
                    "expenses": {"debit": 0.0, "credit": 0.0, "net": 0.0},
                },
                "accounts_touched": {},
            })
            row["journal_entries_count"] += 1
            row["journal_entries_total"] += _safe_float(entry.get("total"))

            for line in entry.get("lines", []) or []:
                norm = _normalize_line(line, id_to_code, code_to_name)
                if not norm:
                    continue
                code = str(norm.get("code") or "")
                debit = _safe_float(norm.get("debit"))
                credit = _safe_float(norm.get("credit"))
                bucket = account_bucket(code)
                impact = row["impact"][bucket]
                impact["debit"] += debit
                impact["credit"] += credit
                impact["net"] += (debit - credit)

                touched = row["accounts_touched"].setdefault(code, {
                    "code": code,
                    "name": norm.get("name") or code_to_name.get(code) or code,
                    "debit": 0.0,
                    "credit": 0.0,
                })
                touched["debit"] += debit
                touched["credit"] += credit

        rows = []
        for key in sorted(by_type.keys()):
            row = by_type[key]
            row["operations_total"] = round(_safe_float(row.get("operations_total")), 2)
            row["journal_entries_total"] = round(_safe_float(row.get("journal_entries_total")), 2)
            for impact_key in row["impact"]:
                item = row["impact"][impact_key]
                row["impact"][impact_key] = {
                    "debit": round(_safe_float(item.get("debit")), 2),
                    "credit": round(_safe_float(item.get("credit")), 2),
                    "net": round(_safe_float(item.get("net")), 2),
                }
            touched = list((row.get("accounts_touched") or {}).values())
            touched.sort(key=lambda x: abs(_safe_float(x.get("debit")) - _safe_float(x.get("credit"))), reverse=True)
            row["accounts_touched"] = [
                {
                    "code": r.get("code"),
                    "name": r.get("name"),
                    "debit": round(_safe_float(r.get("debit")), 2),
                    "credit": round(_safe_float(r.get("credit")), 2),
                }
                for r in touched[:8]
            ]
            rows.append(row)

        return {
            "success": True,
            "data": {
                "period": {"start_date": start_date, "end_date": end_date},
                "rows": rows,
                "summary": {
                    "operations_total": round(sum(_safe_float(r.get("operations_total")) for r in rows), 2),
                    "journal_total": round(sum(_safe_float(r.get("journal_entries_total")) for r in rows), 2),
                    "types_count": len(rows),
                },
                "explainers": {
                    "cash": "1101: عمليات نقدية مباشرة",
                    "bank": "1102: بطاقات/تحويلات",
                    "ar": "1103: ذمم مدينة",
                    "ap": "2101: ذمم موردين",
                },
            },
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "data": {"period": {"start_date": start_date, "end_date": end_date}, "rows": []},
        }


@router.post("/reports/reclassify-payment-accounts")
async def reclassify_payment_accounts(
    workshop_id: str = Query(...),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    apply_changes: bool = Query(False),
):
    """
    تصحيح القيود التي سُجلت على النقد 1101 بدل البنك 1102 (أو العكس)
    بحسب طريقة الدفع في العملية المرجعية.
    """
    end_date = end_date or datetime.now().strftime("%Y-%m-%d")
    start_date = start_date or "2000-01-01"

    account_id_to_code_local = {
        "acc-1101": "003", "acc-1102": "004",
        "acc-003": "003", "acc-004": "004",
    }
    account_name_local = {
        "003": "النقد", "004": "البنك",
        "1101": "النقد", "1102": "البنك",
    }

    try:
        operations = _fetch_operations_for_reconciliation(
            workshop_id=workshop_id,
            start_date=start_date,
            end_date=end_date,
        )
        op_method = {}
        for op in operations:
            op_id = str(op.get("id") or "").strip()
            if not op_id:
                continue
            method = _normalize_payment_method(op.get("payment_method") or op.get("paymentMethod") or "cash") or "cash"
            op_method[op_id] = method

        entries = _fetch_journal_entries(
            workshop_id=workshop_id,
            start_date=start_date,
            end_date=end_date,
            limit=20000,
            include_rakan=True,
        )

        updated = 0
        changed_entries = []

        for entry in entries:
            entry_id = str(entry.get("id") or "").strip()
            ref = str(entry.get("reference_id") or "").strip()
            if not entry_id or not ref or ref not in op_method:
                continue

            method = op_method[ref]
            if method == "credit":
                continue
            expected_cash = "004" if method == "bank" else "003"

            lines = entry.get("lines") or []
            if not isinstance(lines, list) or not lines:
                continue

            has_change = False
            new_lines = []
            for line in lines:
                if not isinstance(line, dict):
                    new_lines.append(line)
                    continue

                account_val = str(line.get("account") or "").strip()
                mapped = account_id_to_code_local.get(account_val, account_val)
                # تحويل legacy إلى جديد
                mapped = _LEGACY_CODE_MAP.get(mapped, mapped)
                if mapped in {"003", "004"} and mapped != expected_cash:
                    line = {**line}
                    line["account"] = expected_cash
                    if str(line.get("account_name") or "") in {"003", "004", "1101", "1102", "النقد", "البنك", "acc-1101", "acc-1102", ""}:
                        line["account_name"] = account_name_local.get(expected_cash, expected_cash)
                    has_change = True

                new_lines.append(line)

            if has_change:
                changed_entries.append({
                    "entry_id": entry_id,
                    "reference_id": ref,
                    "payment_method": method,
                    "expected_cash_account": expected_cash,
                })
                if apply_changes and supabase:
                    supabase.table("journal_entries").update({"lines": new_lines}).eq("id", entry_id).execute()
                    updated += 1

        return {
            "success": True,
            "data": {
                "period": {"start_date": start_date, "end_date": end_date},
                "candidates": len(changed_entries),
                "updated": updated,
                "changes": changed_entries[:50],
                "applied": apply_changes,
            },
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "data": {
                "period": {"start_date": start_date, "end_date": end_date},
                "candidates": 0,
                "updated": 0,
                "changes": [],
                "applied": apply_changes,
            },
        }


@router.post("/reports/apply-bank-revenue-policy")
async def apply_bank_revenue_policy(
    workshop_id: str = Query(...),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    apply_changes: bool = Query(True),
):
    """
    سياسة مالك الورشة:
    1) تحويل جميع الحركات على 1101 -> 1102 (لتصفير الكاش تاريخيًا)
    2) تحويل عمليات البيع/الخدمة النقدية إلى bank في جدول operations
    3) التأكد من وجود حساب نقاط بيع 1104 كحساب فرعي تحت البنك 1102
    """
    end_date = end_date or datetime.now().strftime("%Y-%m-%d")
    start_date = start_date or "2000-01-01"

    cash_accounts = {"1101", "acc-1101"}
    bank_account_by_style = {
        "1101": "1102",
        "acc-1101": "acc-1102",
    }
    bank_like_names = {"1101", "acc-1101", "النقد", "كاش", "cash", ""}

    async def _ensure_pos_under_bank() -> Dict[str, Any]:
        result = {"created": False, "updated": False, "account": None}
        try:
            if supabase:
                rows = supabase.table("accounts").select("id,code,name,parent_id,type,is_system").execute().data or []
                by_code = {str(r.get("code") or "").strip(): r for r in rows}
                bank = by_code.get("1102")
                current_assets = by_code.get("1100")
                pos = by_code.get("1104")

                target_parent = (bank or {}).get("id") or (current_assets or {}).get("id")
                if not pos and apply_changes:
                    new_row = {
                        "id": f"acc-{uuid.uuid4().hex[:12]}",
                        "code": "1104",
                        "name": "نقاط بيع",
                        "name_en": "POS",
                        "type": "asset",
                        "parent_id": target_parent,
                        "is_system": True,
                        "balance": 0.0,
                    }
                    inserted = supabase.table("accounts").insert(new_row).execute().data or [new_row]
                    result["created"] = True
                    result["account"] = inserted[0]
                elif pos:
                    needs_update = (
                        str(pos.get("name") or "") != "نقاط بيع"
                        or str(pos.get("parent_id") or "") != str(target_parent or "")
                    )
                    if needs_update and apply_changes:
                        updated = (
                            supabase.table("accounts")
                            .update({"name": "نقاط بيع", "name_en": "POS", "parent_id": target_parent})
                            .eq("id", pos.get("id"))
                            .execute()
                            .data
                            or [pos]
                        )
                        result["updated"] = True
                        result["account"] = updated[0]
                    else:
                        result["account"] = pos
                return result

            if db is not None:
                rows = await db.accounts.find(
                    {"code": {"$in": ["1100", "1102", "1104"]}},
                    {"_id": 0},
                ).to_list(length=20)
                by_code = {str(r.get("code") or "").strip(): r for r in rows}
                bank = by_code.get("1102")
                current_assets = by_code.get("1100")
                pos = by_code.get("1104")
                target_parent = (bank or {}).get("id") or (current_assets or {}).get("id")

                if not pos and apply_changes:
                    doc = {
                        "id": f"acc-{uuid.uuid4().hex[:12]}",
                        "code": "1104",
                        "name": "نقاط بيع",
                        "nameEn": "POS",
                        "type": "asset",
                        "parentId": target_parent,
                        "isSystem": True,
                        "balance": 0.0,
                    }
                    await db.accounts.insert_one(doc)
                    result["created"] = True
                    result["account"] = doc
                elif pos:
                    needs_update = (
                        str(pos.get("name") or "") != "نقاط بيع"
                        or str(pos.get("parentId") or "") != str(target_parent or "")
                    )
                    if needs_update and apply_changes:
                        await db.accounts.update_one(
                            {"id": pos.get("id")},
                            {"$set": {"name": "نقاط بيع", "nameEn": "POS", "parentId": target_parent}},
                        )
                        updated_doc = await db.accounts.find_one({"id": pos.get("id")}, {"_id": 0})
                        result["updated"] = True
                        result["account"] = updated_doc or pos
                    else:
                        result["account"] = pos
                return result
        except Exception as pos_error:
            result["error"] = str(pos_error)
        return result

    try:
        pos_result = await _ensure_pos_under_bank()

        entries = _fetch_journal_entries(
            workshop_id=workshop_id,
            start_date=start_date,
            end_date=end_date,
            limit=30000,
            include_rakan=True,
        )

        changed_entries = []
        updated_entries = 0
        for entry in entries:
            entry_id = str(entry.get("id") or "").strip()
            lines = entry.get("lines") or []
            if not entry_id or not isinstance(lines, list) or not lines:
                continue

            has_change = False
            new_lines = []
            for line in lines:
                if not isinstance(line, dict):
                    new_lines.append(line)
                    continue

                current_account = str(line.get("account") or "").strip()
                if current_account in cash_accounts:
                    target_account = bank_account_by_style.get(current_account, "1102")
                    new_line = {**line, "account": target_account}
                    current_name = str(new_line.get("account_name") or "").strip().lower()
                    if current_name in bank_like_names:
                        new_line["account_name"] = "البنك"
                    has_change = True
                    new_lines.append(new_line)
                    continue

                new_lines.append(line)

            if has_change:
                changed_entries.append(entry_id)
                if apply_changes:
                    if supabase:
                        supabase.table("journal_entries").update({"lines": new_lines}).eq("id", entry_id).execute()
                        updated_entries += 1
                    elif db is not None:
                        await db.journal_entries.update_one({"id": entry_id}, {"$set": {"lines": new_lines}})
                        updated_entries += 1

        operations = _fetch_operations_for_reconciliation(
            workshop_id=workshop_id,
            start_date=start_date,
            end_date=end_date,
        )

        op_candidates = []
        op_updated = 0
        for op in operations:
            op_id = str(op.get("id") or "").strip()
            if not op_id:
                continue
            op_type = _normalize_operation_type_for_reconciliation(op.get("type"))
            if op_type != "sale":
                continue

            method = _normalize_payment_method(op.get("payment_method") or op.get("paymentMethod") or "")
            if method in {"", "bank", "credit"}:
                continue

            op_candidates.append(op_id)
            if apply_changes:
                if supabase:
                    try:
                        supabase.table("operations").update({"payment_method": "bank", "paymentMethod": "bank"}).eq("id", op_id).execute()
                    except Exception:
                        supabase.table("operations").update({"payment_method": "bank"}).eq("id", op_id).execute()
                    op_updated += 1
                elif db is not None:
                    await db.operations.update_one(
                        {"id": op_id},
                        {"$set": {"payment_method": "bank", "paymentMethod": "bank"}},
                    )
                    op_updated += 1

        return {
            "success": True,
            "data": {
                "period": {"start_date": start_date, "end_date": end_date},
                "applied": apply_changes,
                "pos_account": pos_result,
                "journal": {
                    "candidates": len(changed_entries),
                    "updated": updated_entries,
                    "sample_entry_ids": changed_entries[:50],
                },
                "operations": {
                    "candidates": len(op_candidates),
                    "updated": op_updated,
                    "sample_operation_ids": op_candidates[:50],
                },
            },
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "data": {
                "period": {"start_date": start_date, "end_date": end_date},
                "applied": apply_changes,
                "journal": {"candidates": 0, "updated": 0, "sample_entry_ids": []},
                "operations": {"candidates": 0, "updated": 0, "sample_operation_ids": []},
            },
        }


@router.post("/reports/repost-bank-and-fix-imbalance")
async def repost_bank_and_fix_imbalance(
    workshop_id: str = Query(...),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    apply_changes: bool = Query(True),
):
    """
    1) إعادة تطبيق سياسة تحويل العمليات للبنك
    2) إصلاح القيود ذات الحساب الفارغ (account='') وربطها بالبنك
    3) موازنة أي قيد غير متوازن بإضافة سطر موازنة على حساب فروقات ترحيل
    """
    end_date = end_date or datetime.now().strftime("%Y-%m-%d")
    start_date = start_date or "2000-01-01"

    try:
        # 1) إعادة ترحيل العمليات المنقولة للبنك
        migration_result = await apply_bank_revenue_policy(
            workshop_id=workshop_id,
            start_date=start_date,
            end_date=end_date,
            apply_changes=apply_changes,
        )

        accounts = _fetch_accounts()

        def _find_account_code(name_keywords: List[str], fallback: str = "") -> str:
            for acc in accounts:
                name = str(acc.get("name") or acc.get("name_ar") or "").strip().lower()
                code = str(acc.get("code") or "").strip()
                if not code:
                    continue
                if any(k in name for k in name_keywords):
                    return code
            return fallback

        bank_code = _find_account_code(["بنك", "bank"], "1102")
        bank_name = "البنك"

        suspense_code = _find_account_code(["فروقات", "معلق", "suspense"], "")
        suspense_name = "حساب فروقات ترحيل"

        # إنشاء حساب فروقات إذا غير موجود
        created_suspense = False
        if not suspense_code and apply_changes and supabase:
            try:
                numeric_codes = []
                for acc in accounts:
                    code = str(acc.get("code") or "").strip()
                    if code.isdigit():
                        numeric_codes.append(int(code))
                next_code = f"{(max(numeric_codes) + 1) if numeric_codes else 900:03d}"

                equity_parent = None
                for acc in accounts:
                    name = str(acc.get("name") or acc.get("name_ar") or "").lower()
                    if "حقوق" in name and "ملكية" in name:
                        equity_parent = acc.get("id")
                        break

                suspense_id = f"acc-{uuid.uuid4().hex[:12]}"
                row = {
                    "id": suspense_id,
                    "code": next_code,
                    "name": suspense_name,
                    "name_en": "Suspense",
                    "type": "equity",
                    "parent_id": equity_parent,
                    "is_system": False,
                    "balance": 0.0,
                }
                supabase.table("accounts").insert(row).execute()
                suspense_code = next_code
                created_suspense = True
            except Exception:
                suspense_code = bank_code  # fallback آمن

        if not suspense_code:
            suspense_code = bank_code

        entries = _fetch_journal_entries(
            workshop_id=workshop_id,
            start_date=start_date,
            end_date=end_date,
            limit=50000,
            include_rakan=True,
        )

        touched_entries = 0
        fixed_blank_lines = 0
        added_balance_lines = 0

        for entry in entries:
            entry_id = str(entry.get("id") or "").strip()
            lines = entry.get("lines") or []
            if not entry_id or not isinstance(lines, list) or not lines:
                continue

            changed = False
            new_lines = []

            for ln in lines:
                if not isinstance(ln, dict):
                    new_lines.append(ln)
                    continue
                acc = str(ln.get("account") or "").strip()
                if not acc:
                    patched = {**ln, "account": bank_code, "account_name": bank_name}
                    new_lines.append(patched)
                    fixed_blank_lines += 1
                    changed = True
                else:
                    new_lines.append(ln)

            debit_total = sum(_safe_float((ln or {}).get("debit")) for ln in new_lines if isinstance(ln, dict))
            credit_total = sum(_safe_float((ln or {}).get("credit")) for ln in new_lines if isinstance(ln, dict))
            diff = round(debit_total - credit_total, 2)

            if abs(diff) > 0.01:
                if diff > 0:
                    # debit أكبر => نضيف credit
                    balancing_line = {
                        "account": suspense_code,
                        "account_name": suspense_name,
                        "debit": 0.0,
                        "credit": abs(diff),
                    }
                else:
                    balancing_line = {
                        "account": suspense_code,
                        "account_name": suspense_name,
                        "debit": abs(diff),
                        "credit": 0.0,
                    }
                new_lines.append(balancing_line)
                added_balance_lines += 1
                changed = True

            if changed:
                touched_entries += 1
                if apply_changes:
                    if supabase:
                        supabase.table("journal_entries").update({"lines": new_lines}).eq("id", entry_id).execute()
                    elif db is not None:
                        await db.journal_entries.update_one({"id": entry_id}, {"$set": {"lines": new_lines}})

        tb = await get_trial_balance(
            workshop_id=workshop_id,
            start_date=start_date,
            end_date=end_date,
            include_rakan=False,
        )
        totals = (tb.get("data") or {}).get("totals") or {}
        total_debit = _safe_float(totals.get("total_debit"))
        total_credit = _safe_float(totals.get("total_credit"))

        return {
            "success": True,
            "data": {
                "period": {"start_date": start_date, "end_date": end_date},
                "applied": apply_changes,
                "migration": migration_result.get("data") if isinstance(migration_result, dict) else migration_result,
                "repair": {
                    "touched_entries": touched_entries,
                    "fixed_blank_lines": fixed_blank_lines,
                    "added_balance_lines": added_balance_lines,
                    "suspense_code": suspense_code,
                    "suspense_created": created_suspense,
                    "bank_code_used": bank_code,
                },
                "trial_balance_after": {
                    "total_debit": round(total_debit, 2),
                    "total_credit": round(total_credit, 2),
                    "difference": round(total_debit - total_credit, 2),
                    "matched": abs(total_debit - total_credit) <= 0.01,
                },
            },
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "data": {
                "period": {"start_date": start_date, "end_date": end_date},
                "applied": apply_changes,
            },
        }


@router.post("/reports/reclassify-vehicle-workshop-dues")
async def reclassify_vehicle_workshop_dues(
    workshop_id: str = Query(...),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    apply_changes: bool = Query(False),
):
    """Exclude supplier item amounts from vehicle revenue/dues (sale/service)."""
    end_date = end_date or datetime.now().strftime("%Y-%m-%d")
    start_date = start_date or (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    def _split_totals(items: Any, current_total: float) -> Dict[str, float]:
        if not isinstance(items, list):
            return {"workshop_total": current_total, "supplier_total": 0.0}
        workshop = 0.0
        supplier = 0.0
        for item in items:
            if not isinstance(item, dict):
                continue
            qty = _safe_float(item.get("quantity") or item.get("qty") or 1)
            price = _safe_float(item.get("price"))
            line_total = _safe_float(item.get("total"))
            if line_total <= 0:
                line_total = qty * price
            item_type = str(item.get("itemType") or item.get("type") or "").strip().lower()
            if item_type == "supplier":
                supplier += line_total
            else:
                workshop += line_total
        if workshop <= 0 and current_total > 0:
            workshop = max(current_total - supplier, 0.0)
        return {"workshop_total": round(workshop, 2), "supplier_total": round(supplier, 2)}

    try:
        operations = _fetch_operations_for_reconciliation(
            workshop_id=workshop_id,
            start_date=start_date,
            end_date=end_date,
        )

        candidates = []
        updated = 0

        for op in operations:
            op_type = str(op.get("type") or "").strip().lower()
            if op_type not in {"sale", "service"}:
                continue
            op_id = str(op.get("id") or "").strip()
            if not op_id:
                continue
            current_total = _safe_float(op.get("total"))
            split = _split_totals(op.get("items"), current_total)
            workshop_total = split["workshop_total"]
            supplier_total = split["supplier_total"]
            if supplier_total <= 0:
                continue
            if abs(current_total - workshop_total) <= 0.009:
                continue

            candidates.append({
                "operation_id": op_id,
                "type": op_type,
                "current_total": round(current_total, 2),
                "workshop_total": workshop_total,
                "supplier_total": supplier_total,
            })

            if apply_changes and supabase:
                # 1) operation total => workshop only
                try:
                    supabase.table("operations").update({
                        "total": workshop_total,
                        "subtotal": workshop_total,
                        "workshop_total": workshop_total,
                        "supplier_archive_total": supplier_total,
                    }).eq("id", op_id).execute()
                except Exception:
                    supabase.table("operations").update({
                        "total": workshop_total,
                        "subtotal": workshop_total,
                    }).eq("id", op_id).execute()

                # 2) operation journal entries => adjust to workshop total
                try:
                    entries = (
                        supabase.table("journal_entries")
                        .select("id,lines,total,source")
                        .eq("reference_id", op_id)
                        .in_("source", ["operation", "operation_rakan_parts"])
                        .execute()
                        .data
                        or []
                    )
                except Exception:
                    entries = []

                for entry in entries:
                    lines = entry.get("lines") or []
                    if not isinstance(lines, list):
                        continue
                    patched = []
                    for line in lines:
                        if not isinstance(line, dict):
                            patched.append(line)
                            continue
                        account = str(line.get("account") or "").strip()
                        debit = _safe_float(line.get("debit"))
                        credit = _safe_float(line.get("credit"))
                        next_line = dict(line)

                        if account in {"1101", "1102", "1103", "acc-1101", "acc-1102", "acc-1103"} and debit > 0:
                            next_line["debit"] = workshop_total
                        if (account.startswith("4") or account.startswith("acc-4")) and credit > 0:
                            next_line["credit"] = workshop_total
                        patched.append(next_line)

                    supabase.table("journal_entries").update({"lines": patched, "total": workshop_total}).eq("id", entry.get("id")).execute()

                updated += 1

        return {
            "success": True,
            "data": {
                "period": {"start_date": start_date, "end_date": end_date},
                "candidates": len(candidates),
                "updated": updated,
                "changes": candidates[:50],
                "applied": apply_changes,
            },
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "data": {
                "period": {"start_date": start_date, "end_date": end_date},
                "candidates": 0,
                "updated": 0,
                "changes": [],
                "applied": apply_changes,
            },
        }


_BUDGETS_FILE = os.path.join(os.path.dirname(__file__), "uploads", "finance_budgets.json")


def _read_budgets() -> List[Dict[str, Any]]:
    try:
        os.makedirs(os.path.dirname(_BUDGETS_FILE), exist_ok=True)
        if not os.path.exists(_BUDGETS_FILE):
            with open(_BUDGETS_FILE, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False, indent=2)
        with open(_BUDGETS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def _write_budgets(rows: List[Dict[str, Any]]):
    os.makedirs(os.path.dirname(_BUDGETS_FILE), exist_ok=True)
    with open(_BUDGETS_FILE, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)


@router.get("/budgets")
async def get_budgets(
    workshop_id: str = Query(...),
    month: Optional[str] = Query(None, description="YYYY-MM")
):
    rows = _read_budgets()
    filtered = [r for r in rows if str(r.get("workshop_id") or "") == str(workshop_id)]
    if month:
        filtered = [r for r in filtered if str(r.get("month") or "") == str(month)]

    totals = {
        "planned": round(sum(float(r.get("planned") or 0) for r in filtered), 2),
        "actual": round(sum(float(r.get("actual") or 0) for r in filtered), 2),
    }
    totals["variance"] = round(totals["planned"] - totals["actual"], 2)

    return {
        "success": True,
        "data": {
            "rows": filtered,
            "totals": totals,
        },
    }


@router.post("/budgets")
async def create_budget(payload: Dict[str, Any] = Body(...)):
    workshop_id = str(payload.get("workshop_id") or "").strip()
    month = str(payload.get("month") or "").strip()
    name = str(payload.get("name") or "").strip()
    if not workshop_id or not month or not name:
        raise HTTPException(status_code=400, detail="workshop_id و month و name مطلوبة")

    row = {
        "id": str(uuid.uuid4()),
        "workshop_id": workshop_id,
        "month": month,
        "name": name,
        "category": str(payload.get("category") or "operating").strip() or "operating",
        "planned": float(payload.get("planned") or 0),
        "actual": float(payload.get("actual") or 0),
        "notes": str(payload.get("notes") or "").strip(),
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }

    rows = _read_budgets()
    rows.append(row)
    _write_budgets(rows)
    return {"success": True, "data": row}


@router.put("/budgets/{budget_id}")
async def update_budget(budget_id: str, payload: Dict[str, Any] = Body(...)):
    rows = _read_budgets()
    idx = next((i for i, r in enumerate(rows) if str(r.get("id") or "") == str(budget_id)), -1)
    if idx < 0:
        raise HTTPException(status_code=404, detail="budget not found")

    current = rows[idx]
    updated = {
        **current,
        "name": str(payload.get("name", current.get("name") or "")).strip() or current.get("name"),
        "category": str(payload.get("category", current.get("category") or "operating")).strip() or "operating",
        "planned": float(payload.get("planned", current.get("planned") or 0)),
        "actual": float(payload.get("actual", current.get("actual") or 0)),
        "notes": str(payload.get("notes", current.get("notes") or "")).strip(),
        "month": str(payload.get("month", current.get("month") or "")).strip() or current.get("month"),
        "updated_at": datetime.utcnow().isoformat(),
    }
    rows[idx] = updated
    _write_budgets(rows)
    return {"success": True, "data": updated}


@router.delete("/budgets/{budget_id}")
async def delete_budget(budget_id: str, workshop_id: str = Query(...)):
    rows = _read_budgets()
    next_rows = [
        r for r in rows
        if not (str(r.get("id") or "") == str(budget_id) and str(r.get("workshop_id") or "") == str(workshop_id))
    ]
    deleted = len(rows) - len(next_rows)
    _write_budgets(next_rows)
    return {"success": True, "deleted": deleted}

@router.delete("/reset-all-data")
async def reset_all_financial_data(
    request: Request,
    workshop_id: str = Query(..., description="معرف الورشة"),
    confirm: str = Query(..., description="يجب أن تكون 'DELETE_ALL' للتأكيد")
):
    """
    حذف جميع البيانات المالية والعمليات للبدء من الصفر
    يحذف: Chart of Accounts، Operations، Journal Entries، Invoices
    """
    if confirm != "DELETE_ALL":
        return {
            "success": False,
            "message": "يجب تأكيد الحذف عن طريق إرسال confirm=DELETE_ALL"
        }
    
    try:
        deleted_counts = {
            "chart_of_accounts": 0,
            "operations": 0,
            "journal_entries": 0,
            "invoices": 0
        }
        
        # حذف من Supabase إذا كان متصلاً
        if supabase:
            # مهم: لا تجعل فشل جدول واحد يمنع حذف الجداول الأخرى
            # العمليات
            try:
                ops_del = (
                    supabase.table("operations")
                    .delete()
                    .gte("created_at", "1900-01-01")
                    .execute()
                )
                ops_count = len(ops_del.data) if ops_del.data else 0
                deleted_counts["operations"] = ops_count if ops_count > 0 else "all"
                print(f"✅ Deleted {ops_count} operations from Supabase")
            except Exception as e:
                print(f"Supabase operations deletion error: {e}")

            # دليل الحسابات (قد يكون غير موجود في بعض المخططات)
            try:
                coa_del = (
                    supabase.table("chart_of_accounts")
                    .delete()
                    .gte("created_at", "1900-01-01")
                    .execute()
                )
                coa_count = len(coa_del.data) if coa_del.data else 0
                deleted_counts["chart_of_accounts"] = coa_count if coa_count > 0 else "all"
                print(f"✅ Deleted {coa_count} chart of accounts from Supabase")
            except Exception as e:
                print(f"Supabase chart_of_accounts deletion skipped/failed: {e}")

            # القيود المحاسبية
            try:
                je_del = (
                    supabase.table("journal_entries")
                    .delete()
                    .eq("workshop_id", workshop_id)
                    .execute()
                )
                je_count = len(je_del.data) if je_del.data else 0
                deleted_counts["journal_entries"] = je_count
                print(f"✅ Deleted {je_count} journal entries (scoped) from Supabase")
            except Exception as e:
                print(f"Supabase journal_entries deletion error: {e}")

            # تنظيف legacy rows بدون workshop_id (إن وُجدت)
            try:
                supabase.table("journal_entries").delete().is_("workshop_id", "null").execute()
                print("✅ Deleted legacy journal entries with NULL workshop_id")
            except Exception as e:
                print(f"Legacy NULL workshop_id delete skipped: {e}")


            # الفواتير
            try:
                inv_del = (
                    supabase.table("invoices")
                    .delete()
                    .gte("created_at", "1900-01-01")
                    .execute()
                )
                inv_count = len(inv_del.data) if inv_del.data else 0
                deleted_counts["invoices"] = inv_count if inv_count > 0 else "all"
                print(f"✅ Deleted {inv_count} invoices from Supabase")
            except Exception as e:
                print(f"Invoices table deletion: {e}")

            print("✅ Supabase: Deleted all financial data")
        
        # حذف من MongoDB
        if finance_db is not None:
            try:
                # حذف العمليات
                ops_result = await finance_db.operations.delete_many({})
                deleted_counts["operations"] = ops_result.deleted_count
                
                # حذف Chart of Accounts
                coa_result = await finance_db.chart_of_accounts.delete_many({})
                deleted_counts["chart_of_accounts"] = coa_result.deleted_count
                
                # حذف Journal Entries
                je_result = await finance_db.journal_entries.delete_many({})
                deleted_counts["journal_entries"] = je_result.deleted_count
                
                print(f"✅ MongoDB: Deleted {deleted_counts}")
            except Exception as e:
                print(f"MongoDB deletion error: {e}")
        
        # حذف من الـ DB الرئيسي (إذا كان MongoDB)
        if db and not finance_db:
            try:
                await db.operations.delete_many({})
                await db.chart_of_accounts.delete_many({})
                await db.journal_entries.delete_many({})
                print("✅ Main DB: Deleted all financial data")
            except Exception as e:
                print(f"Main DB deletion error: {e}")
        
        actor = _extract_request_actor(request)
        audit_event = record_bulk_delete_event(
            action="reset_all_financial_data",
            source_endpoint="/api/finance/reset-all-data",
            workshop_id=workshop_id,
            user_id=actor["user_id"],
            user_role=actor["user_role"],
            items={key: _count_value(value) for key, value in deleted_counts.items()},
            meta={"confirm": confirm},
        )

        return {
            "success": True,
            "message": "تم حذف جميع البيانات المالية بنجاح من جميع الأنظمة",
            "deleted_counts": deleted_counts,
            "audit_event": audit_event,
        }
    
    except Exception as e:
        return {
            "success": False,
            "message": f"حدث خطأ أثناء الحذف: {str(e)}"
        }


@router.get("/audit-logs")
async def get_bulk_delete_audit_logs(
    workshop_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    limit: int = Query(30, ge=1, le=200),
):
    rows = list_bulk_delete_events(workshop_id=workshop_id, action=action, limit=limit)
    return {
        "success": True,
        "data": {
            "rows": rows,
            "count": len(rows),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    }


def _is_debt_related_operation(op: Dict[str, Any]) -> bool:
    op_type = str(op.get("type") or "").strip().lower()
    payment_method = str(op.get("payment_method") or op.get("paymentMethod") or "").strip().lower()
    payment_status = str(op.get("payment_status") or op.get("paymentStatus") or "").strip().lower()

    if op_type == "payment_order":
        return True

    if payment_method == "credit":
        return True

    if payment_status in {"credit", "unpaid", "pending", "partial"}:
        return True

    return False


@router.delete("/reset-ops-journals-keep-debts")
async def reset_ops_journals_keep_debts_only(
    workshop_id: str = Query(..., description="معرف الورشة"),
    confirm: str = Query(..., description="يجب أن تكون KEEP_DEBTS_ONLY للتأكيد")
):
    """
    تنظيف مالي مع الإبقاء على الذمم فقط:
    - حذف جميع القيود اليومية
    - حذف العمليات غير المرتبطة بالذمم
    - الإبقاء فقط على عمليات الذمم (credit / unpaid / payment_order)
    """
    if confirm != "KEEP_DEBTS_ONLY":
        return {
            "success": False,
            "message": "يجب تأكيد العملية عبر confirm=KEEP_DEBTS_ONLY"
        }

    try:
        result = {
            "operations_kept": 0,
            "operations_deleted": 0,
            "journal_entries_deleted": 0,
        }

        if supabase:
            try:
                scoped_ops_query = (
                    supabase.table("operations")
                    .select("id,type,payment_method,paymentMethod,payment_status,paymentStatus,workshop_id")
                    .eq("workshop_id", workshop_id)
                    .range(0, 9999)
                )
                scoped_operations = scoped_ops_query.execute().data or []
            except Exception:
                scoped_operations = []

            try:
                legacy_ops_query = (
                    supabase.table("operations")
                    .select("id,type,payment_method,paymentMethod,payment_status,paymentStatus,workshop_id")
                    .is_("workshop_id", "null")
                    .range(0, 9999)
                )
                legacy_operations = legacy_ops_query.execute().data or []
            except Exception:
                legacy_operations = []

            operations_map: Dict[str, Dict[str, Any]] = {}
            for op in (scoped_operations + legacy_operations):
                op_id = str(op.get("id") or "").strip()
                if op_id:
                    operations_map[op_id] = op
            operations = list(operations_map.values())

            if not operations:
                try:
                    operations = (
                        supabase.table("operations")
                        .select("id,type,payment_method,paymentMethod,payment_status,paymentStatus,workshop_id")
                        .range(0, 9999)
                        .execute()
                        .data
                        or []
                    )
                except Exception:
                    operations = []

            keep_ids: List[str] = []
            delete_ids: List[str] = []
            for op in operations:
                op_id = str(op.get("id") or "").strip()
                if not op_id:
                    continue
                if _is_debt_related_operation(op):
                    keep_ids.append(op_id)
                else:
                    delete_ids.append(op_id)

            for idx in range(0, len(delete_ids), 200):
                chunk = delete_ids[idx: idx + 200]
                if not chunk:
                    continue
                try:
                    supabase.table("operations").delete().in_("id", chunk).execute()
                except Exception as delete_err:
                    print(f"Failed deleting operations chunk: {delete_err}")

            result["operations_kept"] = len(keep_ids)
            result["operations_deleted"] = len(delete_ids)

            try:
                scoped_journal_rows = (
                    supabase.table("journal_entries")
                    .select("id")
                    .eq("workshop_id", workshop_id)
                    .range(0, 9999)
                    .execute()
                    .data
                    or []
                )

                legacy_journal_rows = (
                    supabase.table("journal_entries")
                    .select("id")
                    .is_("workshop_id", "null")
                    .range(0, 9999)
                    .execute()
                    .data
                    or []
                )

                journal_map: Dict[str, bool] = {}
                for row in (scoped_journal_rows + legacy_journal_rows):
                    row_id = str(row.get("id") or "").strip()
                    if row_id:
                        journal_map[row_id] = True

                je_ids = list(journal_map.keys())

                if not je_ids:
                    fallback_rows = (
                        supabase.table("journal_entries")
                        .select("id")
                        .range(0, 9999)
                        .execute()
                        .data
                        or []
                    )
                    je_ids = [str(row.get("id") or "").strip() for row in fallback_rows if row.get("id")]

                for idx in range(0, len(je_ids), 200):
                    chunk = je_ids[idx: idx + 200]
                    if not chunk:
                        continue
                    try:
                        supabase.table("journal_entries").delete().in_("id", chunk).execute()
                    except Exception as delete_err:
                        print(f"Failed deleting journal chunk: {delete_err}")
                result["journal_entries_deleted"] = len(je_ids)
            except Exception as je_err:
                print(f"Journal cleanup failed: {je_err}")

        if finance_db is not None:
            ops_query: Dict[str, Any] = {
                "$or": [
                    {"workshop_id": workshop_id},
                    {"workshop_id": {"$exists": False}},
                    {"workshop_id": None},
                    {"workshop_id": ""},
                ]
            }
            operations = await finance_db.operations.find(ops_query, {"_id": 0}).to_list(length=10000)

            keep_ids: List[str] = []
            delete_ids: List[str] = []
            for op in operations:
                op_id = str(op.get("id") or "").strip()
                if not op_id:
                    continue
                if _is_debt_related_operation(op):
                    keep_ids.append(op_id)
                else:
                    delete_ids.append(op_id)

            if delete_ids:
                await finance_db.operations.delete_many({"id": {"$in": delete_ids}})

            je_result = await finance_db.journal_entries.delete_many({
                "$or": [
                    {"workshop_id": workshop_id},
                    {"workshop_id": {"$exists": False}},
                    {"workshop_id": None},
                    {"workshop_id": ""},
                ]
            })
            result["operations_kept"] += len(keep_ids)
            result["operations_deleted"] += len(delete_ids)
            result["journal_entries_deleted"] += je_result.deleted_count

        if db is not None and db is not finance_db:
            operations = await db.operations.find({
                "$or": [
                    {"workshop_id": workshop_id},
                    {"workshop_id": {"$exists": False}},
                    {"workshop_id": None},
                    {"workshop_id": ""},
                ]
            }, {"_id": 0}).to_list(length=10000)
            keep_ids: List[str] = []
            delete_ids: List[str] = []
            for op in operations:
                op_id = str(op.get("id") or "").strip()
                if not op_id:
                    continue
                if _is_debt_related_operation(op):
                    keep_ids.append(op_id)
                else:
                    delete_ids.append(op_id)
            if delete_ids:
                await db.operations.delete_many({"id": {"$in": delete_ids}})
            je_result = await db.journal_entries.delete_many({
                "$or": [
                    {"workshop_id": workshop_id},
                    {"workshop_id": {"$exists": False}},
                    {"workshop_id": None},
                    {"workshop_id": ""},
                ]
            })
            result["operations_kept"] += len(keep_ids)
            result["operations_deleted"] += len(delete_ids)
            result["journal_entries_deleted"] += je_result.deleted_count

        return {
            "success": True,
            "message": "تم حذف القيود والعمليات غير المرتبطة بالذمم بنجاح",
            "data": result,
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"تعذر تنفيذ التنظيف: {str(e)}"
        }


@router.post("/ar/migrate-operations-workshop")
async def ar_migrate_operations_workshop(payload: dict = Body(...)):
    """ترحيل عمليات الآجل القديمة التي لا تحتوي workshop_id.

    حسب طلبك: نرحّل فقط أصحاب الذمم (عمليات الآجل payment_method='credit')
    واللي workshop_id فيها NULL.

    مهم: هذا endpoint إداري للاستخدام مرة واحدة.
    """
    if not supabase:
        return {"success": False, "message": "Supabase not connected"}

    workshop_id = payload.get("workshop_id") or payload.get("workshopId")
    confirm = payload.get("confirm")
    if not workshop_id:
        return {"success": False, "message": "workshop_id مطلوب"}
    if confirm != "MIGRATE_NULL_WORKSHOP":
        return {"success": False, "message": "يجب تأكيد العملية عبر confirm=MIGRATE_NULL_WORKSHOP"}

    try:
        q = (
            supabase.table("operations")
            .select("id")
            .in_("type", ["sale", "service"])
            .eq("payment_method", "credit")
            .is_("workshop_id", "null")
        )
        candidates = (q.execute().data or [])

        updated = 0
        failed = 0
        for row in candidates:
            op_id = row.get("id")
            if not op_id:
                continue
            try:
                supabase.table("operations").update({"workshop_id": workshop_id}).eq("id", op_id).execute()
                updated += 1
            except Exception:
                failed += 1

        return {
            "success": True,
            "data": {
                "workshop_id": workshop_id,
                "matched": len(candidates),
                "updated": updated,
                "failed": failed,
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/audit-system")
async def audit_accounting_system(
    workshop_id: str = Query(..., description="معرف الورشة")
):
    """
    تدقيق شامل للنظام المحاسبي
    يفحص: معادلة المحاسبة، اتساق القوائم، القيود اليومية، الأنماط غير العادية
    """
    try:
        # جمع البيانات المالية
        financial_data = {}
        
        # 1. جلب الميزانية العمومية
        try:
            balance_sheet_data = await get_balance_sheet(workshop_id=workshop_id, as_of_date=None)
            if balance_sheet_data and balance_sheet_data.get('success'):
                bs = balance_sheet_data['data']
                financial_data['balance_sheet'] = {
                    'assets': bs['totals']['assets'],
                    'liabilities': bs['totals']['liabilities'],
                    'equity': bs['totals']['equity']
                }
        except Exception:
            pass
        
        # 2. جلب قائمة الدخل
        try:
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            income_data = await get_income_statement(workshop_id, start_date, end_date)
            if income_data and income_data.get('success'):
                ins = income_data['data']
                financial_data['income_statement'] = {
                    'revenue': ins['totals']['revenue'],
                    'expenses': ins['totals']['expenses'],
                    'net_profit': ins['totals']['net_income']
                }
        except Exception:
            pass
        
        # 3. جلب التدفقات النقدية
        try:
            cashflow_data = await get_cash_flow(workshop_id, start_date, end_date)
            if cashflow_data and cashflow_data.get('success'):
                cf = cashflow_data['data']
                financial_data['cash_flow'] = {
                    'operating': cf['operating_activities'].get('net_operating_cash', 0),
                    'investing': cf['investing_activities'].get('net_investing_cash', 0),
                    'financing': cf['financing_activities'].get('net_financing_cash', 0)
                }
        except Exception:
            pass

        # 4. 🛡️ جلب حالة جدار حماية المحاسبة (لحظي)
        try:
            from routes_firewall import firewall_status
            firewall_data = await firewall_status(workshop_id=workshop_id, recent_limit=10)
            if firewall_data and firewall_data.get('success'):
                financial_data['firewall'] = firewall_data
        except Exception as e:
            print(f"audit-system: firewall fetch failed: {e}")

        # تشغيل التدقيق
        auditor = AccountingSystemAuditor("نظام الخدمات المحاسبي")


        audit_report = auditor.run_comprehensive_audit(financial_data)
        
        return {
            "success": True,
            "data": audit_report
        }
    
    except Exception as e:
        return {
            "success": False,
            "message": f"خطأ في التدقيق: {str(e)}"
        }



@router.post("/reports/migrate-legacy-codes")
async def migrate_legacy_account_codes(
    workshop_id: str = Query(...),
    apply_changes: bool = Query(False),
):
    """
    يحوّل أكواد الحسابات القديمة (1101/1102/1103/4100/6100…) إلى الأكواد التسلسلية الجديدة
    (003/004/005/026/036…) في جميع سطور قيود اليومية.
    """
    LEGACY_MAP = {
        "1101": "003", "acc-1101": "003",
        "1102": "004", "acc-1102": "004",
        "1103": "005", "acc-1103": "005",
        "1104": "006", "acc-1104": "006",
        "1105": "007", "acc-1105": "007",
        "4000": "024", "acc-4000": "024",
        "4100": "025", "acc-4100": "025",
        "4101": "026", "acc-4101": "026",
        "4102": "027", "acc-4102": "027",
        "5000": "029", "acc-5000": "029",
        "5100": "030", "acc-5100": "030",
        "6000": "034", "acc-6000": "034",
        "6100": "035", "acc-6100": "035",
        "6101": "036", "acc-6101": "036",
        "3102": "021", "acc-3102": "021",
        "1201": "010", "acc-1201": "010",
        "042": "041", "0421": "167", "211": "166",
    }
    NAME_MAP = {
        "003": "النقد", "004": "البنك", "005": "العملاء",
        "006": "نقاط بيع", "007": "مخزون قطع غيار",
        "024": "الإيرادات", "025": "إيرادات الخدمات",
        "026": "إيرادات خدمات ميكانيكية", "027": "إيرادات إصلاح محركات",
        "029": "تكلفة الخدمات", "030": "تكاليف مباشرة",
        "034": "المصروفات التشغيلية", "035": "مصروفات عامة وإدارية",
        "036": "رواتب إدارية", "021": "مسحوبات المالك",
        "010": "معدات ميكانيكية", "041": "ايراد قطع الورشه",
        "166": "حساب فروقات ترحيل", "167": "تكلفة قطع الورشة",
        "2101": "الموردون",
    }

    # مسح الـ cache أولاً للحصول على أحدث البيانات
    invalidate_finance_caches()
    entries = _fetch_journal_entries(
        workshop_id, "2000-01-01",
        datetime.now().strftime("%Y-%m-%d"),
        limit=5000,
        include_rakan=True,
    )
    candidates = []
    for entry in entries:
        new_lines = []
        changed = False
        for line in (entry.get("lines") or []):
            acc = str(line.get("account") or "").strip()
            new_acc = LEGACY_MAP.get(acc, acc)
            if new_acc != acc:
                changed = True
                new_line = dict(line)
                new_line["account"] = new_acc
                new_line["account_name"] = NAME_MAP.get(new_acc, new_line.get("account_name", new_acc))
                new_lines.append(new_line)
            else:
                new_lines.append(line)
        if changed:
            candidates.append({"id": entry.get("id"), "lines": new_lines})

    updated = 0
    if apply_changes:
        provider = os.environ.get("DB_PROVIDER", "mongo").lower()
        for c in candidates:
            eid = c["id"]
            try:
                if provider == "supabase":
                    from supabase_service import SupabaseService as _SB
                    supa = _SB()
                    supa.client.table("journal_entries").update(
                        {"lines": c["lines"]}
                    ).eq("id", eid).execute()
                elif db:
                    await db.journal_entries.update_one(
                        {"id": eid}, {"$set": {"lines": c["lines"]}}
                    )
                updated += 1
            except Exception as e:
                print(f"migrate_legacy_codes: failed {eid}: {e}")
        invalidate_finance_caches()

    return {
        "success": True,
        "candidates": len(candidates),
        "updated": updated if apply_changes else 0,
        "apply_changes": apply_changes,
        "sample": [{"id": c["id"]} for c in candidates[:5]],
    }



@router.post("/reports/reclassify-revenue-sub-accounts")
async def reclassify_revenue_sub_accounts(
    workshop_id: str = Query(...),
    apply_changes: bool = Query(False),
):
    """
    يُعيد تصنيف قيود الإيراد من الحسابات العامة (024/025/4001/4000/4100)
    إلى الحسابات الفرعية الصحيحة:
    - بنود تحتوي "توضيب" → 027 (إيرادات إصلاح محركات)
    - غير ذلك → 026 (إيرادات خدمات ميكانيكية)
    """
    OLD_REV_CODES = {"024", "025", "4001", "4000", "4100"}
    TOWDHEEB_KW = ["توضيب", "تلميع مكينة", "غسيل مكينة", "تنظيف مكينة"]
    NAME_MAP = {
        "026": "إيرادات خدمات ميكانيكية",
        "027": "إيرادات إصلاح محركات",
    }

    def _pick_code(op_text: str) -> str:
        for kw in TOWDHEEB_KW:
            if kw in op_text:
                return "027"
        return "026"

    invalidate_finance_caches()
    entries = _fetch_journal_entries(
        workshop_id, "2000-01-01",
        datetime.now().strftime("%Y-%m-%d"),
        limit=5000,
        include_rakan=True,
    )

    # بناء خريطة معرّف_العملية → نص_العملية لتحديد الكود
    op_text_map: Dict[str, str] = {}
    if supabase:
        try:
            # العمليات لا تملك workshop_id — نجلبها بدون فلتر
            ops_res = supabase.table("operations").select(
                "id, notes, description, items"
            ).limit(2000).execute()
            for op in (ops_res.data or []):
                items = op.get("items") or []
                text = " ".join(
                    [str(op.get("notes") or ""), str(op.get("description") or "")]
                    + [str(it.get("name") or "") for it in items]
                )
                op_text_map[str(op.get("id") or "")] = text
        except Exception as e:
            print(f"reclassify_revenue: ops fetch failed: {e}")

    candidates = []
    for entry in entries:
        lines = entry.get("lines") or []
        new_lines = []
        changed = False
        for line in lines:
            acc = str(line.get("account") or "")
            credit = float(line.get("credit") or 0)
            if acc in OLD_REV_CODES and credit > 0:
                # تحديد الكود الصحيح من العملية المرتبطة
                ref_id = str(entry.get("reference_id") or "")
                op_text = op_text_map.get(ref_id, "")
                # أيضاً من وصف القيد نفسه
                op_text += " " + str(entry.get("description") or "")
                new_acc = _pick_code(op_text)
                new_line = dict(line)
                new_line["account"] = new_acc
                new_line["account_name"] = NAME_MAP[new_acc]
                new_lines.append(new_line)
                changed = True
            else:
                new_lines.append(line)
        if changed:
            candidates.append({"id": entry.get("id"), "lines": new_lines})

    updated = 0
    if apply_changes and supabase:
        for c in candidates:
            try:
                supabase.table("journal_entries").update(
                    {"lines": c["lines"]}
                ).eq("id", c["id"]).execute()
                updated += 1
            except Exception as e:
                print(f"reclassify_revenue: update {c['id']} failed: {e}")
        invalidate_finance_caches()

    return {
        "success": True,
        "candidates": len(candidates),
        "updated": updated if apply_changes else 0,
        "apply_changes": apply_changes,
    }
