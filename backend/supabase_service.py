"""
Supabase Service for Workshop Management System
Handles Supabase database interactions
"""

import os
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import json
import re

# Load environment variables at module level
_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    load_dotenv(_env_file)

try:
    from supabase import create_client, Client

    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    print("⚠️ supabase not installed")

# -------- Mapping helpers --------


def to_snake_vehicle(api: Dict[str, Any]) -> Dict[str, Any]:
    # Helper to convert empty strings to None for UUID fields
    def clean_uuid(value):
        return value if value and value.strip() else None

    return {
        "id": api.get("id"),
        "plate_number": api.get("plateNumber"),
        "brand": api.get("brand"),
        "model": api.get("model"),
        "year": api.get("year"),
        "color": api.get("color"),
        "vin": clean_uuid(api.get("vin")),
        "file_number": api.get("fileNumber"),
        "customer_id": clean_uuid(api.get("customerId")),
        "customer_name": api.get("customerName"),
        "customer_phone": api.get("customerPhone"),
        "customer_email": api.get("customerEmail"),
        "status": api.get("status"),
        "entry_date": api.get("entryDate"),
        "estimated_completion": api.get("estimatedCompletion"),
        "completion_date": api.get("completionDate"),
        "tracking_link": api.get("trackingLink"),
        "images": api.get("images") or [],
        "services": api.get("services") or [],
        "parts": api.get("parts") or [],
        "technician_id": clean_uuid(api.get("technicianId")),
        "technician_name": api.get("technicianName"),
        "notes": api.get("notes"),
    }


def to_camel_vehicle(dbrow: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": dbrow.get("id"),
        "plateNumber": dbrow.get("plate_number"),
        "brand": dbrow.get("brand"),
        "model": dbrow.get("model"),
        "year": dbrow.get("year"),
        "color": dbrow.get("color"),
        "vin": dbrow.get("vin"),
        "fileNumber": dbrow.get("file_number"),
        "customerId": dbrow.get("customer_id"),
        "customerName": dbrow.get("customer_name") or "",
        "customerPhone": dbrow.get("customer_phone") or "",
        "customerEmail": dbrow.get("customer_email") or "",
        "status": dbrow.get("status") or "diagnosis",
        "entryDate": dbrow.get("entry_date"),
        "estimatedCompletion": dbrow.get("estimated_completion"),
        "completionDate": dbrow.get("completion_date"),
        "trackingLink": dbrow.get("tracking_link"),
        "images": dbrow.get("images") or [],
        "services": dbrow.get("services") or [],
        "parts": dbrow.get("parts") or [],
        "technicianId": dbrow.get("technician_id"),
        "technicianName": dbrow.get("technician_name"),
        "notes": dbrow.get("notes"),
    }


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _normalize_visit_payment_method(value: Any) -> str:
    raw = str(value or '').strip().lower()
    if raw in {'bank', 'transfer', 'bank_transfer', 'تحويل', 'بنك'}:
        return 'transfer'
    if raw in {'pos', 'card', 'mada', 'visa', 'mastercard', 'بطاقة', 'بطاقه', 'نقاط بيع', 'point_of_sale'}:
        return 'card'
    if raw in {'supplier_balance'}:
        return 'supplier_balance'
    if raw in {'cash', 'نقد', 'نقدي', 'كاش'}:
        return 'cash'
    return raw or 'cash'


def _summarize_visit_notes(notes: Any) -> Dict[str, Any]:
    parsed = {}
    if isinstance(notes, dict):
        parsed = notes
    elif isinstance(notes, str) and notes.strip().startswith('{'):
        try:
            parsed = json.loads(notes)
        except Exception:
            parsed = {}

    items = parsed.get('items') or []
    payments = parsed.get('payments') or []

    total_workshop = 0.0
    total_suppliers = 0.0
    for item in items:
        qty = _safe_float(item.get('quantity') or item.get('qty') or 1, 1.0)
        price = _safe_float(item.get('price') or 0)
        line_total = _safe_float(item.get('total'), qty * price)
        item_type = str(item.get('itemType') or item.get('type') or '').strip().lower()
        if item_type == 'supplier':
            total_suppliers += line_total
        else:
            total_workshop += line_total

    total_paid = 0.0
    advance_paid = 0.0
    last_method = ''
    for payment in payments:
        amount = _safe_float(payment.get('amount') or 0)
        total_paid += amount
        if str(payment.get('kind') or '').strip().lower() == 'advance':
            advance_paid += amount
        method = payment.get('paymentMethod') or payment.get('method') or payment.get('payment_method')
        if method:
            last_method = _normalize_visit_payment_method(method)

    balance = max(round(total_workshop - total_paid, 2), 0.0)
    if total_paid <= 0:
        payment_status = 'unpaid'
    elif balance > 0.01:
        payment_status = 'partial'
    else:
        payment_status = 'paid_full'

    return {
        'total_workshop': round(total_workshop, 2),
        'total_suppliers': round(total_suppliers, 2),
        'total_paid': round(total_paid, 2),
        'advance_paid': round(advance_paid, 2),
        'balance': balance,
        'payment_status': payment_status,
        'last_payment_method': last_method or ('cash' if total_paid > 0 else 'credit'),
        'visitNumber': parsed.get('visitNumber') or parsed.get('visit_number') or parsed.get('visitNumberDisplay'),
    }


def _operation_payment_snapshot(row: Dict[str, Any], visit_summary: Dict[str, Any], operation_total: Any) -> Dict[str, Any]:
    """Return operation-level payment fields without letting an advance-only visit mark a full invoice as paid."""
    total = round(_safe_float(operation_total or row.get('total') or row.get('subtotal') or 0), 2)
    paid = round(_safe_float(visit_summary.get('total_paid') or row.get('total_paid') or row.get('paymentAmount') or 0), 2)
    explicit_balance = row.get('balance') if row.get('balance') is not None else row.get('remaining_balance')
    if explicit_balance is not None:
        balance = round(max(_safe_float(explicit_balance), 0.0), 2)
    else:
        balance = round(max(total - paid, 0.0), 2)

    if paid <= 0:
        status = row.get('payment_status') or row.get('paymentStatus') or 'unpaid'
    elif balance > 0.01:
        status = 'partial'
    else:
        status = 'paid_full'

    method = (
        visit_summary.get('last_payment_method')
        or row.get('payment_method')
        or row.get('paymentMethod')
        or ('cash' if paid > 0 else 'credit')
    )
    row_method = row.get('payment_method') or row.get('paymentMethod')
    if paid > 0 and str(method or '').lower() in {'credit', 'deferred'} and row_method:
        method = row_method

    return {
        'payment_method': method,
        'payment_status': status,
        'total_paid': paid,
        'balance': balance,
    }


def _operation_display_notes(notes: Any, visit_summary: Dict[str, Any]) -> Any:
    if not isinstance(notes, str):
        return notes
    visit_number = visit_summary.get('visit_number') or visit_summary.get('visitNumber') or visit_summary.get('visitNumberDisplay')
    if visit_number:
        return re.sub(r"عملية من الزيارة\s+[0-9a-f]{6,}", f"عملية من الزيارة {visit_number}", notes, flags=re.IGNORECASE)
    return notes


def to_snake_user(api: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": api.get("id"),
        "name": api.get("name"),
        "username": api.get("username"),
        "password": api.get("password"),
        "role": api.get("role"),
        "phone": api.get("phone"),
        "email": api.get("email"),
        "permissions": api.get("permissions"),
        "guidance_enabled": api.get("guidanceEnabled"),
        "created_at": api.get("createdAt"),
        "last_login": api.get("lastLogin"),
        "is_active": api.get("isActive"),
    }


def to_camel_user(dbrow: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": dbrow.get("id"),
        "name": dbrow.get("name"),
        "username": dbrow.get("username"),
        "password": dbrow.get("password"),
        "role": dbrow.get("role"),
        "phone": dbrow.get("phone"),
        "email": dbrow.get("email"),
        "permissions": dbrow.get("permissions"),
        "guidanceEnabled": dbrow.get("guidance_enabled"),
        "createdAt": dbrow.get("created_at"),
        "lastLogin": dbrow.get("last_login"),
        "isActive": dbrow.get("is_active"),
    }


class SupabaseService:
    """Service for Supabase database operations"""

    _shared_client: Optional[Client] = None
    _shared_mock_mode: Optional[bool] = None
    _mock_notice_logged: bool = False

    def __init__(self):
        self.supabase_url = os.environ.get("SUPABASE_URL", "")
        self.supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

        if SupabaseService._shared_mock_mode is None:
            if self.supabase_url and self.supabase_key and SUPABASE_AVAILABLE:
                SupabaseService._shared_client = create_client(
                    self.supabase_url, self.supabase_key
                )
                SupabaseService._shared_mock_mode = False
            else:
                SupabaseService._shared_client = None
                SupabaseService._shared_mock_mode = True
                if not SupabaseService._mock_notice_logged:
                    print(
                        "⚠️ Supabase running in MOCK mode. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY to enable."
                    )
                    SupabaseService._mock_notice_logged = True

        self.client = SupabaseService._shared_client
        self.mock_mode = bool(SupabaseService._shared_mock_mode)

    # -------------------- Vehicles --------------------
    def vehicles_list(self) -> List[Dict[str, Any]]:
        if self.mock_mode:
            return []
        res = (
            self.client.table("vehicles")
            .select("*")
            .order("entry_date", desc=True)
            .execute()
        )
        return [to_camel_vehicle(r) for r in (res.data or [])]

    def vehicles_create(self, api_doc: Dict[str, Any]) -> Dict[str, Any]:
        if self.mock_mode:
            return api_doc
        row = to_snake_vehicle(api_doc)
        res = self.client.table("vehicles").insert(row).execute()
        data = (res.data or [{}])[0]
        return to_camel_vehicle(data)

    def vehicles_get(self, vid: str) -> Optional[Dict[str, Any]]:
        if self.mock_mode:
            return None
        # Use maybe_single() so “0 rows” becomes None instead of raising an exception.
        # This prevents 500s when the frontend navigates to a vehicle id that doesn't exist.
        res = (
            self.client.table("vehicles")
            .select("*")
            .eq("id", vid)
            .maybe_single()
            .execute()
        )
        return to_camel_vehicle(res.data) if res and res.data else None

    def vehicles_update(
        self, vid: str, upd_api: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        if self.mock_mode:
            return None
        upd = to_snake_vehicle(upd_api)
        # remove None to avoid overwriting
        upd = {k: v for k, v in upd.items() if v is not None}
        res = self.client.table("vehicles").update(upd).eq("id", vid).execute()
        data = (res.data or [{}])[0]
        return to_camel_vehicle(data)

    def vehicles_delete(self, vid: str) -> bool:
        if self.mock_mode:
            return True
        self.client.table("vehicles").delete().eq("id", vid).execute()
        return True

    # -------------------- Technicians --------------------
    def technicians_list(self) -> List[Dict[str, Any]]:
        if self.mock_mode:
            return []
        res = (
            self.client.table("technicians")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )
        rows = res.data or []
        # Convert snake_case to camelCase
        out = []
        for r in rows:
            out.append(
                {
                    "id": r.get("id"),
                    "name": r.get("name"),
                    "phone": r.get("phone", ""),
                    "specialty": r.get("specialty", ""),
                    "activeJobs": r.get("active_jobs", 0),
                    "completedJobs": r.get("completed_jobs", 0),
                    "rating": float(r.get("rating", 5.0)),
                }
            )
        return out

    # -------------------- Services --------------------
    def services_list(self) -> List[Dict[str, Any]]:
        if self.mock_mode:
            return []
        res = (
            self.client.table("services")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )
        rows = res.data or []
        out = []
        for r in rows:
            out.append(
                {
                    "id": r.get("id"),
                    "name": r.get("name"),
                    "category": r.get("category"),
                    "price": float(r.get("price") or 0),
                    "duration": r.get("duration_minutes") or 0,
                    "active": r.get("active", True),
                }
            )
        return out

    def services_create(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        if self.mock_mode:
            return doc
        row = {
            "id": doc.get("id"),
            "name": doc.get("name"),
            "category": doc.get("category"),
            "price": doc.get("price", 0),
            "duration_minutes": doc.get("duration", 0),
            "vat_percent": 0,
            "active": doc.get("active", True),
            "notes": doc.get("notes"),
        }
        res = self.client.table("services").insert(row).execute()
        r = (res.data or [{}])[0]
        return {
            "id": r.get("id"),
            "name": r.get("name"),
            "category": r.get("category"),
            "price": float(r.get("price") or 0),
            "duration": r.get("duration_minutes") or 0,
            "active": r.get("active", True),
        }

    def services_update(self, sid: str, upd: Dict[str, Any]) -> Dict[str, Any]:
        if self.mock_mode:
            return upd
        row = {}
        if "name" in upd:
            row["name"] = upd["name"]
        if "category" in upd:
            row["category"] = upd["category"]
        if "price" in upd:
            row["price"] = upd["price"]
        if "duration" in upd:
            row["duration_minutes"] = upd["duration"]
        if "active" in upd:
            row["active"] = upd["active"]
        if "notes" in upd:
            row["notes"] = upd["notes"]
        res = self.client.table("services").update(row).eq("id", sid).execute()
        r = (res.data or [{}])[0]
        return {
            "id": r.get("id"),
            "name": r.get("name"),
            "category": r.get("category"),
            "price": float(r.get("price") or 0),
            "duration": r.get("duration_minutes") or 0,
            "active": r.get("active", True),
        }

    def services_delete(self, sid: str) -> bool:
        if self.mock_mode:
            return True
        self.client.table("services").delete().eq("id", sid).execute()
        return True

    # -------------------- Business Accounts --------------------
    def accounts_list(self) -> List[Dict[str, Any]]:
        if self.mock_mode:
            return []
        res = (
            self.client.table("business_accounts")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )
        rows = res.data or []
        return [
            {
                "id": r.get("id"),
                "name": r.get("name"),
                "code": r.get("code"),
                "currency": r.get("currency") or "SAR",
                "createdAt": r.get("created_at"),
            }
            for r in rows
        ]

    def accounts_create(
        self, name: str, code: Optional[str], currency: str
    ) -> Dict[str, Any]:
        if self.mock_mode:
            return {
                "id": "mock",
                "name": name,
                "code": code or "BR01",
                "currency": currency,
                "createdAt": datetime.utcnow().isoformat(),
            }
        row = {"name": name, "code": code or name[:4].upper(), "currency": currency}
        res = self.client.table("business_accounts").insert(row).execute()
        r = (res.data or [{}])[0]
        return {
            "id": r.get("id"),
            "name": r.get("name"),
            "code": r.get("code"),
            "currency": r.get("currency") or "SAR",
            "createdAt": r.get("created_at"),
        }

    # -------------------- Budgets --------------------
    def budgets_list(
        self, account_id: Optional[str], period: Optional[str]
    ) -> List[Dict[str, Any]]:
        if self.mock_mode:
            return []
        q = self.client.table("budgets").select("*")
        if account_id:
            q = q.eq("account_id", account_id)
        if period:
            q = q.eq("period", period)
        res = q.order("period", desc=True).execute()
        return res.data or []

    def budgets_create(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self.mock_mode:
            return payload
        row = {
            "account_id": payload.get("accountId"),
            "period": payload.get("period"),
            "income_target": payload.get("incomeTarget", 0),
            "expense_target": payload.get("expenseTarget", 0),
            "notes": payload.get("notes"),
        }
        res = self.client.table("budgets").insert(row).execute()
        return (res.data or [{}])[0]

    # -------------------- Operations (minimal) --------------------
    def operations_list(
        self,
        workshop_id: Optional[str] = None,
        account_id: Optional[str] = None,
        type: Optional[str] = None,
        vehicle_id: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        if self.mock_mode:
            return []
        try:
            select_fields = (
                "id,type,account_id,accounting_account_id,vehicle_id,visit_id,"
                "partner_type,partner_id,partner_name,items,subtotal,total,payment_method,"
                "payment_status,notes,op_date,created_at,updated_at,invoice_number,"
                "scope,source,business_unit"
            )
            safe_offset = max(0, int(offset or 0))
            safe_limit = (
                max(1, min(int(limit), 2000))
                if limit is not None
                else 200
            )

            def _fetch_rows(select_expr: str) -> List[Dict[str, Any]]:
                q = self.client.table("operations").select(select_expr)
                if account_id:
                    q = q.eq("account_id", account_id)
                if type:
                    q = q.eq("type", type)
                if vehicle_id:
                    q = q.eq("vehicle_id", vehicle_id)
                q = q.order("created_at", desc=True)
                q = q.range(safe_offset, safe_offset + safe_limit - 1)
                res = q.execute()
                return res.data or []

            try:
                rows = _fetch_rows(select_fields)
            except Exception as schema_error:
                if "does not exist" in str(schema_error).lower():
                    rows = _fetch_rows("*")
                else:
                    raise
        except Exception as e:
            print(f"Supabase operations list error: {e}")
            return []

        visit_summaries = {}
        visit_ids = [
            str(r.get("visit_id") or r.get("visitId") or "").strip()
            for r in rows
            if str(r.get("visit_id") or r.get("visitId") or "").strip()
        ]
        if visit_ids:
            try:
                visit_rows = (
                    self.client.table("vehicle_visits")
                    .select("id,vehicle_id,notes,entry_date,created_at")
                    .in_("id", visit_ids)
                    .execute()
                    .data
                    or []
                )
                visit_summaries = {
                    str(row.get("id") or "").strip(): _summarize_visit_notes(row.get("notes"))
                    for row in visit_rows
                    if str(row.get("id") or "").strip()
                }
                grouped_visits = {}
                for row in visit_rows:
                    grouped_visits.setdefault(str(row.get("vehicle_id") or "open"), []).append(row)
                for grouped_rows in grouped_visits.values():
                    sorted_visit_rows = sorted(
                        grouped_rows,
                        key=lambda row: str(row.get("entry_date") or row.get("created_at") or ""),
                    )
                    for idx, row in enumerate(sorted_visit_rows, start=1):
                        row_id = str(row.get("id") or "").strip()
                        if not row_id:
                            continue
                        notes_payload = _summarize_visit_notes(row.get("notes"))
                        visit_number = notes_payload.get("visitNumber") or notes_payload.get("visit_number") or idx
                        try:
                            visit_display = f"{int(float(visit_number)):03d}"
                        except Exception:
                            visit_display = str(visit_number or idx).zfill(3)
                        visit_summaries.setdefault(row_id, {})["visit_number"] = visit_display
            except Exception as visit_error:
                print(f"Supabase operations list visit-summary warning: {visit_error}")

        vehicle_context = {}
        vehicle_ids = [
            str(r.get("vehicle_id") or r.get("vehicleId") or "").strip()
            for r in rows
            if str(r.get("vehicle_id") or r.get("vehicleId") or "").strip()
        ]
        if vehicle_ids:
            try:
                vehicle_rows = (
                    self.client.table("vehicles")
                    .select("id,plate_number,brand,model,customer_name,customer_phone")
                    .in_("id", vehicle_ids)
                    .execute()
                    .data
                    or []
                )
                vehicle_context = {
                    str(row.get("id") or "").strip(): row
                    for row in vehicle_rows
                    if str(row.get("id") or "").strip()
                }
            except Exception as vehicle_error:
                print(f"Supabase operations list vehicle-context warning: {vehicle_error}")

        operation_payment_totals = {}
        try:
            operation_ids = [str(r.get("id") or "").strip() for r in rows if r.get("id")]
            if operation_ids:
                payment_rows = (
                    self.client.table("journal_entries")
                    .select("reference_id,total,source")
                    .in_("reference_id", operation_ids)
                    .in_("source", ["operation_payment", "operation_payment_income", "supplier_balance_payment"])
                    .execute()
                    .data
                    or []
                )
                for payment_row in payment_rows:
                    ref = str(payment_row.get("reference_id") or "").strip()
                    if ref:
                        operation_payment_totals[ref] = operation_payment_totals.get(ref, 0.0) + _safe_float(payment_row.get("total"))
        except Exception as payment_error:
            print(f"Supabase operations list payment-summary warning: {payment_error}")

        # map snake_case to camelCase if needed, or just return as is if frontend expects it
        # The frontend likely expects camelCase.
        out = []
        for r in rows:
            items = r.get("items") or []
            workshop_total = r.get("workshop_total") or r.get("workshopTotal")
            supplier_archive_total = r.get("supplier_archive_total") or r.get("supplierArchiveTotal") or r.get("total_suppliers")

            if workshop_total is None:
                workshop_calc = 0.0
                supplier_calc = 0.0
                if isinstance(items, list):
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        qty = float(item.get("quantity") or item.get("qty") or 1)
                        price = float(item.get("price") or 0)
                        line_total = float(item.get("total") or (qty * price))
                        item_type = str(item.get("itemType") or item.get("type") or "").strip().lower()
                        if item_type == "supplier":
                            supplier_calc += line_total
                        else:
                            workshop_calc += line_total
                current_total = float(r.get("total") or 0)
                if workshop_calc <= 0 and current_total > 0:
                    workshop_calc = max(current_total - supplier_calc, 0.0)
                workshop_total = workshop_calc if workshop_calc > 0 else current_total
                if supplier_archive_total is None:
                    supplier_archive_total = supplier_calc

            visit_summary = visit_summaries.get(str(r.get("visit_id") or r.get("visitId") or "").strip(), {})
            extra_operation_paid = operation_payment_totals.get(str(r.get("id") or "").strip(), 0.0)
            if extra_operation_paid:
                visit_summary = dict(visit_summary)
                visit_summary["total_paid"] = _safe_float(visit_summary.get("total_paid")) + extra_operation_paid
            has_visit_summary = bool(visit_summary)
            payment_method = visit_summary.get("last_payment_method") if has_visit_summary else None
            if not payment_method:
                payment_method = r.get("payment_method") or r.get("paymentMethod") or visit_summary.get("last_payment_method")
            payment_status = visit_summary.get("payment_status") if has_visit_summary else None
            if not payment_status:
                payment_status = r.get("payment_status") or r.get("paymentStatus") or visit_summary.get("payment_status")
            payment_snapshot = _operation_payment_snapshot(r, visit_summary, workshop_total or r.get("total"))
            vehicle_row = vehicle_context.get(str(r.get("vehicle_id") or r.get("vehicleId") or "").strip(), {})
            partner_type = r.get("partner_type") or r.get("partnerType")
            live_partner_name = vehicle_row.get("customer_name") if str(partner_type or '').lower() == 'customer' else None

            out.append(
                {
                    "id": r.get("id"),
                    "type": r.get("type"),
                    "accountId": r.get("account_id") or r.get("accountId"),
                    "accountingAccountId": r.get("accounting_account_id") or r.get("accountingAccountId"),
                    "vehicleId": r.get("vehicle_id") or r.get("vehicleId"),
                    "visitId": r.get("visit_id") or r.get("visitId"),
                    "visitNumber": visit_summary.get("visit_number") or visit_summary.get("visitNumber"),
                    "visitNumberDisplay": visit_summary.get("visit_number") or visit_summary.get("visitNumber"),
                    "partnerType": partner_type,
                    "partnerId": r.get("partner_id") or r.get("partnerId"),
                    "partnerName": live_partner_name or r.get("partner_name") or r.get("partnerName"),
                    "customerName": vehicle_row.get("customer_name") or '',
                    "customerPhone": vehicle_row.get("customer_phone") or '',
                    "vehiclePlate": vehicle_row.get("plate_number") or '',
                    "vehicleBrand": vehicle_row.get("brand") or '',
                    "vehicleModel": vehicle_row.get("model") or '',
                    "items": r.get("items"),
                    "subtotal": r.get("subtotal"),
                    "total": r.get("total"),
                    "workshopTotal": workshop_total,
                    "supplierArchiveTotal": supplier_archive_total or 0,
                    "paymentMethod": payment_snapshot.get("payment_method") or payment_method,
                    "paymentStatus": payment_snapshot.get("payment_status") or payment_status,
                    "paymentAmount": payment_snapshot.get("total_paid", 0),
                    "totalPaid": payment_snapshot.get("total_paid", 0),
                    "advancePaid": visit_summary.get("advance_paid", 0),
                    "balance": payment_snapshot.get("balance"),
                    "notes": _operation_display_notes(r.get("notes"), visit_summary),
                    "date": r.get("op_date") or r.get("date"),
                    "createdAt": r.get("created_at") or r.get("createdAt"),
                    "updatedAt": r.get("updated_at") or r.get("updatedAt"),
                    "invoiceNumber": r.get("invoice_number") or r.get("invoiceNumber"),
                    "scope": r.get("scope") or ("vehicle" if (r.get("vehicle_id") or r.get("vehicleId")) else "workshop"),
                    "source": r.get("source"),
                    "businessUnit": r.get("business_unit") or r.get("businessUnit"),
                }
            )

        return out

    def operations_get(self, op_id: str) -> Optional[Dict[str, Any]]:
        if self.mock_mode:
            return None
        res = self.client.table("operations").select("*").eq("id", op_id).limit(1).execute()
        rows = res.data or []
        if not rows:
            return None
        r = rows[0]
        items = r.get("items") or []
        workshop_total = r.get("workshop_total") or r.get("workshopTotal")
        supplier_archive_total = r.get("supplier_archive_total") or r.get("supplierArchiveTotal") or r.get("total_suppliers")
        if workshop_total is None:
            workshop_calc = 0.0
            supplier_calc = 0.0
            if isinstance(items, list):
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    qty = float(item.get("quantity") or item.get("qty") or 1)
                    price = float(item.get("price") or 0)
                    line_total = float(item.get("total") or (qty * price))
                    item_type = str(item.get("itemType") or item.get("type") or "").strip().lower()
                    if item_type == "supplier":
                        supplier_calc += line_total
                    else:
                        workshop_calc += line_total
            current_total = float(r.get("total") or 0)
            if workshop_calc <= 0 and current_total > 0:
                workshop_calc = max(current_total - supplier_calc, 0.0)
            workshop_total = workshop_calc if workshop_calc > 0 else current_total
            if supplier_archive_total is None:
                supplier_archive_total = supplier_calc

        visit_summary = {}
        visit_id = str(r.get("visit_id") or r.get("visitId") or "").strip()
        if visit_id:
            try:
                visit_rows = (
                    self.client.table("vehicle_visits")
                    .select("id,vehicle_id,notes,entry_date,created_at")
                    .eq("id", visit_id)
                    .limit(1)
                    .execute()
                    .data
                    or []
                )
                if visit_rows:
                    visit_summary = _summarize_visit_notes(visit_rows[0].get("notes"))
                    visit_number = visit_summary.get("visitNumber") or visit_summary.get("visit_number") or 1
                    try:
                        visit_summary["visit_number"] = f"{int(float(visit_number)):03d}"
                    except Exception:
                        visit_summary["visit_number"] = str(visit_number or "001").zfill(3)
            except Exception as visit_error:
                print(f"Supabase operations get visit-summary warning: {visit_error}")

        try:
            payment_rows = (
                self.client.table("journal_entries")
                .select("total,source")
                .eq("reference_id", op_id)
                .in_("source", ["operation_payment", "operation_payment_income", "supplier_balance_payment"])
                .execute()
                .data
                or []
            )
            operation_payment_total = sum(_safe_float(row.get("total")) for row in payment_rows)
            if operation_payment_total:
                visit_summary = dict(visit_summary)
                visit_summary["total_paid"] = _safe_float(visit_summary.get("total_paid")) + operation_payment_total
        except Exception as payment_error:
            print(f"Supabase operations get payment-summary warning: {payment_error}")

        vehicle_row = {}
        vehicle_id = str(r.get("vehicle_id") or r.get("vehicleId") or "").strip()
        if vehicle_id:
            try:
                vehicle_rows = (
                    self.client.table("vehicles")
                    .select("id,plate_number,brand,model,customer_name,customer_phone")
                    .eq("id", vehicle_id)
                    .limit(1)
                    .execute()
                    .data
                    or []
                )
                if vehicle_rows:
                    vehicle_row = vehicle_rows[0]
            except Exception as vehicle_error:
                print(f"Supabase operations get vehicle-context warning: {vehicle_error}")

        partner_type = r.get("partner_type")
        live_partner_name = vehicle_row.get("customer_name") if str(partner_type or '').lower() == 'customer' else None
        payment_snapshot = _operation_payment_snapshot(r, visit_summary, workshop_total or r.get("total"))

        return {
            "id": r.get("id"),
            "type": r.get("type"),
            "accountId": r.get("account_id"),
            "accountingAccountId": r.get("accounting_account_id"),
            "vehicleId": r.get("vehicle_id"),
            "visitId": r.get("visit_id"),
            "visitNumber": visit_summary.get("visit_number") or visit_summary.get("visitNumber"),
            "visitNumberDisplay": visit_summary.get("visit_number") or visit_summary.get("visitNumber"),
            "partnerType": partner_type,
            "partnerId": r.get("partner_id"),
            "partnerName": live_partner_name or r.get("partner_name"),
            "customerName": vehicle_row.get("customer_name") or '',
            "customerPhone": vehicle_row.get("customer_phone") or '',
            "vehiclePlate": vehicle_row.get("plate_number") or '',
            "vehicleBrand": vehicle_row.get("brand") or '',
            "vehicleModel": vehicle_row.get("model") or '',
            "items": r.get("items"),
            "subtotal": r.get("subtotal"),
            "total": r.get("total"),
            "workshopTotal": workshop_total,
            "supplierArchiveTotal": supplier_archive_total or 0,
            "paymentMethod": payment_snapshot.get("payment_method") or visit_summary.get("last_payment_method") or r.get("payment_method"),
            "paymentStatus": payment_snapshot.get("payment_status") or visit_summary.get("payment_status") or r.get("payment_status"),
            "paymentAmount": payment_snapshot.get("total_paid", 0),
            "totalPaid": payment_snapshot.get("total_paid", 0),
            "advancePaid": visit_summary.get("advance_paid", 0),
            "balance": payment_snapshot.get("balance"),
            "notes": _operation_display_notes(r.get("notes"), visit_summary),
            "date": r.get("op_date"),
            "createdAt": r.get("created_at"),
            "invoiceNumber": r.get("invoice_number"),
            "scope": "vehicle" if r.get("vehicle_id") else "workshop",
        }

    # -------------------- Customers --------------------
    def customers_list(self, search: Optional[str] = None) -> List[Dict[str, Any]]:
        if self.mock_mode:
            return []
        q = self.client.table("customers").select("*")
        if search:
            # simple search on name or phone
            q = q.or_(f"name.ilike.%{search}%,phone.ilike.%{search}%")
        res = q.order("last_visit", desc=True).execute()
        rows = res.data or []
        return [
            {
                "id": r.get("id"),
                "name": r.get("name"),
                "phone": r.get("phone"),
                "email": r.get("email"),
                "address": r.get("address"),
                "vehicleBrand": r.get("vehicle_brand"),
                "vehiclePlate": r.get("vehicle_plate"),
                "vehicleKm": r.get("vehicle_km"),
                "totalVisits": r.get("total_visits", 0),
                "lastVisit": r.get("last_visit"),
                "vehicles": r.get("vehicles") or [],
                "createdAt": r.get("created_at"),
            }
            for r in rows
        ]

    def customers_get(self, cid: str) -> Optional[Dict[str, Any]]:
        if self.mock_mode:
            return None
        res = (
            self.client.table("customers").select("*").eq("id", cid).single().execute()
        )
        r = res.data
        if not r:
            return None
        return {
            "id": r.get("id"),
            "name": r.get("name"),
            "phone": r.get("phone"),
            "email": r.get("email"),
            "address": r.get("address"),
            "vehicleBrand": r.get("vehicle_brand"),
            "vehiclePlate": r.get("vehicle_plate"),
            "vehicleKm": r.get("vehicle_km"),
            "totalVisits": r.get("total_visits", 0),
            "lastVisit": r.get("last_visit"),
            "vehicles": r.get("vehicles") or [],
            "createdAt": r.get("created_at"),
        }

    def customers_find_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        if self.mock_mode or not self.client:
            return None
        try:
            res = (
                self.client.table("customers")
                .select("*")
                .eq("phone", phone)
                .maybe_single()
                .execute()
            )
            r = res.data
            if not r:
                return None
            return {
                "id": r.get("id"),
                "name": r.get("name"),
                "phone": r.get("phone"),
                "email": r.get("email"),
                "address": r.get("address"),
                "vehicleBrand": r.get("vehicle_brand"),
                "vehiclePlate": r.get("vehicle_plate"),
                "vehicleKm": r.get("vehicle_km"),
                "totalVisits": r.get("total_visits", 0),
                "lastVisit": r.get("last_visit"),
                "vehicles": r.get("vehicles") or [],
                "createdAt": r.get("created_at"),
            }
        except Exception as e:
            print(f"Error finding customer by phone: {e}")
            return None

    def customers_create(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self.mock_mode:
            return payload
        row = {
            "name": payload.get("name"),
            "phone": payload.get("phone"),
            "email": payload.get("email"),
            "address": payload.get("address"),
            "vehicle_brand": payload.get("vehicleBrand"),
            "vehicle_plate": payload.get("vehiclePlate"),
            "vehicle_km": payload.get("vehicleKm"),
            "total_visits": payload.get("totalVisits", 0),
            "last_visit": payload.get("lastVisit"),
        }
        if payload.get("id"):
            row["id"] = payload.get("id")

        res = self.client.table("customers").insert(row).execute()
        r = (res.data or [{}])[0]
        return {
            "id": r.get("id"),
            "name": r.get("name"),
            "phone": r.get("phone"),
            "email": r.get("email"),
            "address": r.get("address"),
            "vehicleBrand": r.get("vehicle_brand"),
            "vehiclePlate": r.get("vehicle_plate"),
            "vehicleKm": r.get("vehicle_km"),
            "totalVisits": r.get("total_visits", 0),
            "lastVisit": r.get("last_visit"),
            "vehicles": r.get("vehicles") or [],
            "createdAt": r.get("created_at"),
        }

    def customers_update(self, cid: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self.mock_mode:
            return payload
        row = {}
        if "name" in payload:
            row["name"] = payload["name"]
        if "phone" in payload:
            row["phone"] = payload["phone"]
        if "email" in payload:
            row["email"] = payload["email"]
        if "address" in payload:
            row["address"] = payload["address"]
        if "vehicleBrand" in payload:
            row["vehicle_brand"] = payload["vehicleBrand"]
        if "vehiclePlate" in payload:
            row["vehicle_plate"] = payload["vehiclePlate"]
        if "vehicleKm" in payload:
            row["vehicle_km"] = payload["vehicleKm"]
        if "totalVisits" in payload:
            row["total_visits"] = payload["totalVisits"]
        if "lastVisit" in payload:
            row["last_visit"] = payload["lastVisit"]
        if "vehicles" in payload:
            row["vehicles"] = payload["vehicles"]

        res = self.client.table("customers").update(row).eq("id", cid).execute()
        r = (res.data or [{}])[0]
        return {
            "id": r.get("id"),
            "name": r.get("name"),
            "phone": r.get("phone"),
            "email": r.get("email"),
            "address": r.get("address"),
            "vehicleBrand": r.get("vehicle_brand"),
            "vehiclePlate": r.get("vehicle_plate"),
            "vehicleKm": r.get("vehicle_km"),
            "totalVisits": r.get("total_visits", 0),
            "lastVisit": r.get("last_visit"),
            "vehicles": r.get("vehicles") or [],
            "createdAt": r.get("created_at"),
        }

    def customers_delete(self, cid: str) -> bool:
        if self.mock_mode:
            return True
        self.client.table("customers").delete().eq("id", cid).execute()
        return True

    def invoices_create(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self.mock_mode:
            return payload
        row = {
            "invoice_number": payload.get("invoiceNumber"),
            "workshop_id": payload.get("workshopId"),
            "operation_id": payload.get("operationId"),
            "customer_id": payload.get("customerId"),
            "vehicle_id": payload.get("vehicleId"),
            "partner_name": payload.get("partnerName"),
            "items": payload.get("items"),
            "subtotal": payload.get("subtotal"),
            "discount": payload.get("discount") or 0,
            "tax": 0,
            "total": payload.get("total"),
            "status": payload.get("status"),
            "type": payload.get("type"),
            "payment_method": payload.get("paymentMethod"),
            "notes": payload.get("notes"),
        }
        if payload.get("id"):
            row["id"] = payload.get("id")

        res = self.client.table("invoices").insert(row).execute()
        r = (res.data or [{}])[0]
        return {
            "id": r.get("id"),
            "invoiceNumber": r.get("invoice_number"),
            "customerId": r.get("customer_id"),
            "vehicleId": r.get("vehicle_id"),
            "items": r.get("items"),
            "subtotal": r.get("subtotal"),
            "discount": r.get("discount"),
            "tax": r.get("tax"),
            "total": r.get("total"),
            "status": r.get("status"),
            "type": r.get("type"),
            "paymentMethod": r.get("payment_method"),
            "notes": r.get("notes"),
            "createdAt": r.get("created_at"),
        }

    def invoices_get(self, iid: str) -> Optional[Dict[str, Any]]:
        if self.mock_mode:
            return None
        res = self.client.table("invoices").select("*").eq("id", iid).single().execute()
        r = res.data
        if not r:
            return None
        return {
            "id": r.get("id"),
            "invoiceNumber": r.get("invoice_number"),
            "customerId": r.get("customer_id"),
            "vehicleId": r.get("vehicle_id"),
            "items": r.get("items"),
            "subtotal": r.get("subtotal"),
            "discount": r.get("discount"),
            "tax": r.get("tax"),
            "total": r.get("total"),
            "status": r.get("status"),
            "type": r.get("type"),
            "paymentMethod": r.get("payment_method"),
            "notes": r.get("notes"),
            "createdAt": r.get("created_at"),
        }

    # NOTE: customers_delete defined earlier in this file

    # -------------------- Invoices --------------------
    def invoices_list(
        self, vehicle_id: Optional[str] = None, customer_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        if self.mock_mode:
            return []
        q = self.client.table("invoices").select("*")
        if vehicle_id:
            q = q.eq("vehicle_id", vehicle_id)
        if customer_id:
            q = q.eq("customer_id", customer_id)
        res = q.order("created_at", desc=True).execute()
        rows = res.data or []
        # Map snake to camel
        return [
            {
                "id": r.get("id"),
                "invoiceNumber": r.get("invoice_number"),
                "customerId": r.get("customer_id"),
                "vehicleId": r.get("vehicle_id"),
                "items": r.get("items"),
                "subtotal": r.get("subtotal"),
                "discount": r.get("discount"),
                "tax": r.get("tax"),
                "total": r.get("total"),
                "status": r.get("status"),
                "type": r.get("type"),
                "createdAt": r.get("created_at"),
            }
            for r in rows
        ]

    def invoices_delete_by_vehicle(self, vid: str) -> bool:
        if self.mock_mode:
            return True
        self.client.table("invoices").delete().eq("vehicle_id", vid).execute()
        return True

    def operations_create(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self.mock_mode:
            return payload

        items = payload.get("items") or []
        # قبول كلٍّ من quantity و qty لحساب الكميات
        subtotal = 0.0
        for it in items:
            qty = float(it.get("quantity", it.get("qty", 1)))
            price = float(it.get("price", 0))
            it["total"] = qty * price
            subtotal += it["total"]

        # تنظيف الحقول التي يجب أن تكون UUID أو NULL
        account_id = payload.get("accountId") or payload.get("account_id") or None
        accounting_account_id = payload.get("accountingAccountId") or payload.get("accounting_account_id") or None
        vehicle_id = payload.get("vehicleId") or payload.get("vehicle_id") or None

        # بعض الجداول لدينا تستخدم UUID، لكن دليل الحسابات لدينا يستخدم مُعرّفات نصية مثل acc-1201.
        # لذلك:
        # - vehicle_id / visit_id يجب أن تكون UUID
        # - account_id قد تكون UUID أو نص (acc-xxxx أو code) فنتركها كما هي إذا كانت نصاً.
        def _sanitize_uuid(value):
            if not value:
                return None
            if not isinstance(value, str):
                return None
            if len(value) != 36 or "-" not in value:
                return None
            return value

        def _sanitize_account_ref(value):
            # Allow UUID or string IDs/codes
            if not value:
                return None
            if not isinstance(value, str):
                return None
            v = value.strip()
            if not v:
                return None
            return v

        account_id = _sanitize_account_ref(account_id)
        accounting_account_id = _sanitize_account_ref(accounting_account_id)
        vehicle_id = _sanitize_uuid(vehicle_id)

        visit_id = payload.get("visitId") or payload.get("visit_id") or None
        visit_id = _sanitize_uuid(visit_id)

        op_date = payload.get("date") or payload.get("opDate") or payload.get("op_date")
        workshop_id = payload.get("workshopId") or payload.get("workshop_id")

        row = {
            "type": payload.get("type", "service"),
            "workshop_id": workshop_id,
            "account_id": account_id,
            "accounting_account_id": accounting_account_id,
            "vehicle_id": vehicle_id,
            "visit_id": visit_id,
            "partner_type": payload.get("partnerType"),
            "partner_id": payload.get("partnerId"),
            "partner_name": payload.get("partnerName"),
            "items": items,
            "subtotal": subtotal,
            "total": subtotal,
            "payment_method": payload.get("paymentMethod", "cash"),
            "payment_status": payload.get("paymentStatus", "paid"),
            "payment_amount": payload.get("paymentAmount"),
            "notes": payload.get("notes"),
            "op_date": op_date or datetime.utcnow().isoformat(),
        }
        retry_fields = [
            "visit_id",
            "workshop_id",
            "accounting_account_id",
            "scope",
            "source",
            "business_unit",
            "partner_id",
            "payment_status",
            "payment_amount",
        ]
        last_error = None
        for _ in range(len(retry_fields) + 1):
            try:
                res = self.client.table("operations").insert(row).execute()
                last_error = None
                break
            except Exception as insert_error:
                last_error = insert_error
                error_msg = str(insert_error)
                removed_any = False
                for field in retry_fields:
                    if field in row and field in error_msg:
                        row.pop(field, None)
                        removed_any = True
                if not removed_any:
                    break
        if last_error is not None:
            raise last_error
        r = (res.data or [{}])[0]
        return {
            "id": r.get("id"),
            "type": r.get("type"),
            "accountId": r.get("account_id"),
            "accountingAccountId": accounting_account_id,  # Preserve the original accountingAccountId
            "vehicleId": r.get("vehicle_id") or payload.get("vehicleId"),
            "visitId": r.get("visit_id") or payload.get("visitId"),
            "partnerType": r.get("partner_type"),
            "partnerId": r.get("partner_id"),
            "partnerName": r.get("partner_name"),
            "items": r.get("items"),
            "subtotal": r.get("subtotal"),
            "total": r.get("total"),
            "paymentMethod": r.get("payment_method"),
            "paymentStatus": r.get("payment_status"),
            "notes": r.get("notes"),
            "date": r.get("op_date"),
            "createdAt": r.get("created_at"),
            "invoiceNumber": r.get("invoice_number"),
            "scope": payload.get("scope") or r.get("scope") or ("vehicle" if r.get("vehicle_id") else "workshop"),
            "source": payload.get("source") or r.get("source"),
            "businessUnit": payload.get("businessUnit") or payload.get("business_unit") or r.get("business_unit"),
        }

    def operations_update(self, op_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self.mock_mode:
            return payload
        items = payload.get("items") or []
        subtotal = sum(
            (float(it.get("price", 0)) * float(it.get("quantity", 1))) for it in items
        )
        workshop_id = payload.get("workshopId") or payload.get("workshop_id")

        row = {
            "type": payload.get("type"),
            "workshop_id": workshop_id,
            "account_id": payload.get("accountId"),
            "accounting_account_id": payload.get("accountingAccountId") or payload.get("accounting_account_id"),
            "vehicle_id": payload.get("vehicleId"),
            "partner_type": payload.get("partnerType"),
            "partner_id": payload.get("partnerId"),
            "partner_name": payload.get("partnerName"),
            "items": items,
            "subtotal": subtotal,
            "total": subtotal,
            "payment_method": payload.get("paymentMethod"),
            "payment_status": payload.get("paymentStatus"),
            "payment_amount": payload.get("paymentAmount"),
            "notes": payload.get("notes"),
            "updated_at": datetime.utcnow().isoformat(),
        }
        # إزالة القيم الفارغة
        row = {k: v for k, v in row.items() if v is not None}
        
        retry_fields = [
            "visit_id",
            "workshop_id",
            "accounting_account_id",
            "scope",
            "source",
            "business_unit",
            "partner_id",
            "payment_status",
            "payment_amount",
        ]
        last_error = None
        for _ in range(len(retry_fields) + 1):
            try:
                res = self.client.table("operations").update(row).eq("id", op_id).execute()
                last_error = None
                break
            except Exception as update_error:
                last_error = update_error
                error_msg = str(update_error)
                removed_any = False
                for field in retry_fields:
                    if field in row and field in error_msg:
                        row.pop(field, None)
                        removed_any = True
                if not removed_any:
                    break
        if last_error is not None:
            raise last_error
        r = (res.data or [{}])[0]
        return {
            "id": r.get("id"),
            "type": r.get("type"),
            "accountId": r.get("account_id"),
            "accountingAccountId": r.get("accounting_account_id"),
            "vehicleId": r.get("vehicle_id"),
            "visitId": r.get("visit_id"),
            "partnerType": r.get("partner_type"),
            "partnerId": r.get("partner_id"),
            "partnerName": r.get("partner_name"),
            "items": r.get("items"),
            "subtotal": r.get("subtotal"),
            "total": r.get("total"),
            "paymentMethod": r.get("payment_method"),
            "paymentStatus": r.get("payment_status"),
            "notes": r.get("notes"),
            "date": r.get("op_date"),
            "createdAt": r.get("created_at"),
            "updatedAt": r.get("updated_at"),
        }

    def operations_delete(self, op_id: str) -> bool:
        """حذف عملية واحدة من جدول operations في Supabase"""
        if self.mock_mode:
            return True
        self.client.table("operations").delete().eq("id", op_id).execute()
        return True


    # -------------------- Transactions --------------------
    def transactions_list(
        self, type: Optional[str] = None, account_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        if self.mock_mode:
            return []
        q = self.client.table("transactions").select("*")
        if type:
            q = q.eq("type", type)
        if account_id:
            q = q.eq("account_id", account_id)
        res = q.order("date", desc=True).execute()
        rows = res.data or []
        return [
            {
                "id": r.get("id"),
                "accountId": r.get("account_id"),
                "vehicleId": r.get("vehicle_id"),
                "type": r.get("type"),
                "category": r.get("category"),
                "amount": r.get("amount"),
                "description": r.get("description"),
                "date": r.get("date"),
                "reference": r.get("reference"),
                "createdAt": r.get("created_at"),
            }
            for r in rows
        ]

    def transactions_create(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self.mock_mode:
            return payload
        row = {
            "account_id": payload.get("accountId"),
            "vehicle_id": payload.get("vehicleId"),
            "type": payload.get("type"),
            "category": payload.get("category"),
            "amount": payload.get("amount"),
            "description": payload.get("description"),
            "date": datetime.utcnow().isoformat(),
            "reference": payload.get("reference"),
        }
        res = self.client.table("transactions").insert(row).execute()
        r = (res.data or [{}])[0]
        return {
            "id": r.get("id"),
            "accountId": r.get("account_id"),
            "vehicleId": r.get("vehicle_id"),
            "type": r.get("type"),
            "category": r.get("category"),
            "amount": r.get("amount"),
            "description": r.get("description"),
            "date": r.get("date"),
            "reference": r.get("reference"),
            "createdAt": r.get("created_at"),
        }

    # -------------------- Parts --------------------
    def parts_list(self) -> List[Dict[str, Any]]:
        if self.mock_mode:
            return []
        res = (
            self.client.table("parts")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )
        rows = res.data or []
        out = []
        for r in rows:
            out.append(
                {
                    "id": r.get("id"),
                    "partNumber": r.get("part_number"),
                    "name": r.get("name"),
                    "category": r.get("category"),
                    "purchasePrice": float(r.get("purchase_price") or 0),
                    "sellingPrice": float(r.get("selling_price") or 0),
                    "quantity": int(r.get("quantity") or 0),
                    "minQuantity": int(r.get("min_quantity") or 5),
                    "supplier": r.get("supplier"),
                    "image": r.get("image"),
                    "createdAt": r.get("created_at"),
                    "updatedAt": r.get("updated_at"),
                }
            )
        return out

    def parts_create(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        if self.mock_mode:
            return doc
        row = {
            "part_number": doc.get("partNumber"),
            "name": doc.get("name"),
            "category": doc.get("category"),
            "purchase_price": doc.get("purchasePrice", 0),
            "selling_price": doc.get("sellingPrice", 0),
            "quantity": doc.get("quantity", 0),
            "min_quantity": doc.get("minQuantity", 5),
            "supplier": doc.get("supplier"),
            "image": doc.get("image"),
            "created_at": datetime.utcnow().isoformat(),
        }
        if doc.get("id"):
            row["id"] = doc.get("id")

        res = self.client.table("parts").insert(row).execute()
        r = (res.data or [{}])[0]
        return {
            "id": r.get("id"),
            "partNumber": r.get("part_number"),
            "name": r.get("name"),
            "category": r.get("category"),
            "purchasePrice": float(r.get("purchase_price") or 0),
            "sellingPrice": float(r.get("selling_price") or 0),
            "quantity": int(r.get("quantity") or 0),
            "minQuantity": int(r.get("min_quantity") or 5),
            "supplier": r.get("supplier"),
            "image": r.get("image"),
            "createdAt": r.get("created_at"),
            "updatedAt": r.get("updated_at"),
        }

    def parts_update(self, pid: str, upd: Dict[str, Any]) -> Dict[str, Any]:
        if self.mock_mode:
            return upd
        row = {}
        if "partNumber" in upd:
            row["part_number"] = upd["partNumber"]
        if "name" in upd:
            row["name"] = upd["name"]
        if "category" in upd:
            row["category"] = upd["category"]
        if "purchasePrice" in upd:
            row["purchase_price"] = upd["purchasePrice"]
        if "sellingPrice" in upd:
            row["selling_price"] = upd["sellingPrice"]
        if "quantity" in upd:
            row["quantity"] = upd["quantity"]
        if "minQuantity" in upd:
            row["min_quantity"] = upd["minQuantity"]
        if "supplier" in upd:
            row["supplier"] = upd["supplier"]
        if "image" in upd:
            row["image"] = upd["image"]

        row["updated_at"] = datetime.utcnow().isoformat()

        res = self.client.table("parts").update(row).eq("id", pid).execute()
        r = (res.data or [{}])[0]
        return {
            "id": r.get("id"),
            "partNumber": r.get("part_number"),
            "name": r.get("name"),
            "category": r.get("category"),
            "purchasePrice": float(r.get("purchase_price") or 0),
            "sellingPrice": float(r.get("selling_price") or 0),
            "quantity": int(r.get("quantity") or 0),
            "minQuantity": int(r.get("min_quantity") or 5),
            "supplier": r.get("supplier"),
            "image": r.get("image"),
            "createdAt": r.get("created_at"),
            "updatedAt": r.get("updated_at"),
        }

    def parts_delete(self, pid: str) -> bool:
        if self.mock_mode:
            return True
        self.client.table("parts").delete().eq("id", pid).execute()
        return True

    # -------------------- Users --------------------
    def users_list(self) -> List[Dict[str, Any]]:
        if self.mock_mode:
            return []
        res = self.client.table("users").select("*").execute()
        return [to_camel_user(item) for item in (res.data or [])]

    def users_create(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self.mock_mode:
            return payload
        res = self.client.table("users").insert(to_snake_user(payload)).execute()
        data = res.data or []
        if not data:
            return payload
        return to_camel_user(data[0])

    def users_update(self, user_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self.mock_mode:
            return payload
        res = (
            self.client.table("users")
            .update(to_snake_user(payload))
            .eq("id", user_id)
            .execute()
        )
        data = res.data or []
        if not data:
            return payload
        return to_camel_user(data[0])

    def users_delete(self, user_id: str) -> bool:
        if self.mock_mode:
            return True
        self.client.table("users").delete().eq("id", user_id).execute()
        return True

    # -------------------- Aliases for business_accounts --------------------
    def business_accounts_list(self) -> List[Dict[str, Any]]:
        return self.accounts_list()

    def business_accounts_create(self, account: Dict[str, Any]) -> Dict[str, Any]:
        name = account.get("name", "")
        code = account.get("code")
        currency = account.get("currency", "SAR")
        return self.accounts_create(name, code, currency)
