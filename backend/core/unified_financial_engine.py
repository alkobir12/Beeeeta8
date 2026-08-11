from __future__ import annotations

import json
import re
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


CASH_ACCOUNT_BY_METHOD = {
    "cash": ("003", "النقد"),
    "bank": ("004", "البنك"),
    "bank_transfer": ("004", "البنك"),
    "transfer": ("004", "البنك"),
    "pos": ("006", "نقاط بيع"),
    "card": ("006", "نقاط بيع"),
}

AR_ACCOUNT = ("005", "العملاء")


def safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def round2(value: Any) -> float:
    return round(safe_float(value), 2)


def parse_notes(notes: Any) -> Dict[str, Any]:
    if isinstance(notes, dict):
        return {**notes, "items": notes.get("items") or [], "payments": notes.get("payments") or []}
    raw = str(notes or "").strip()
    if raw.startswith("{"):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return {**parsed, "items": parsed.get("items") or [], "payments": parsed.get("payments") or []}
        except Exception:
            pass
    return {"text": raw, "items": [], "payments": []}


def serialize_notes(parsed: Dict[str, Any]) -> str:
    return json.dumps(parsed or {}, ensure_ascii=False)


def normalize_method(value: Any) -> str:
    raw = str(value or "cash").strip().lower()
    if raw in {"bank", "transfer", "bank_transfer", "تحويل", "تحويل/بنك", "تحويل بنكي", "بنك"}:
        return "bank_transfer"
    if raw in {"pos", "card", "mada", "visa", "mastercard", "نقاط بيع", "شبكة", "بطاقة", "بطاقه"}:
        return "pos"
    return "cash"


def is_pending_payment(payment: Dict[str, Any]) -> bool:
    status = str(payment.get("status") or payment.get("paymentStatus") or payment.get("payment_status") or "").strip().lower()
    return payment.get("confirmed") is False or status in {
        "pending",
        "pending_confirmation",
        "awaiting_confirmation",
        "unconfirmed",
        "بانتظار التأكيد",
        "بانتظار_التأكيد",
    }


def item_amount(item: Dict[str, Any]) -> float:
    if item.get("total") is not None:
        return safe_float(item.get("total"))
    qty = safe_float(item.get("quantity") if item.get("quantity") is not None else item.get("qty")) or 1.0
    return qty * safe_float(item.get("price") or item.get("unit_price"))


def is_supplier_item(item: Dict[str, Any]) -> bool:
    raw = str(item.get("itemType") or item.get("billingType") or item.get("billing_type") or "").strip().lower()
    return raw == "supplier"


def vehicle_finalization(vehicle: Dict[str, Any]) -> Dict[str, Any]:
    notes = parse_notes(vehicle.get("notes"))
    final = notes.get("financial_finalization") if isinstance(notes, dict) else None
    if not isinstance(final, dict):
        final = {}
    direct_total = vehicle.get("final_customer_total") or vehicle.get("finalCustomerTotal")
    final_total = final.get("final_customer_total") if final.get("final_customer_total") is not None else direct_total
    try:
        final_total_value = float(final_total) if final_total is not None and str(final_total).strip() != "" else None
    except Exception:
        final_total_value = None
    if final_total_value is not None and final_total_value < 0:
        final_total_value = None
    return {
        "final_customer_total": round2(final_total_value) if final_total_value is not None else None,
        "finalized_at": final.get("finalized_at") or vehicle.get("finalized_at") or vehicle.get("finalizedAt"),
        "finalized_by": final.get("finalized_by") or vehicle.get("finalized_by") or vehicle.get("finalizedBy"),
        "finalization_source": final.get("finalization_source") or vehicle.get("finalization_source") or vehicle.get("finalizationSource"),
        "previous_service_total": round2(final.get("previous_service_total") or vehicle.get("previous_service_total") or vehicle.get("previousServiceTotal")),
    }


def visit_finalization(visit: Dict[str, Any]) -> Dict[str, Any]:
    notes = parse_notes(visit.get("notes"))
    final = notes.get("financial_finalization") if isinstance(notes, dict) else None
    if not isinstance(final, dict):
        final = {}
    direct_total = visit.get("final_customer_total") or visit.get("finalCustomerTotal")
    final_total = final.get("final_customer_total") if final.get("final_customer_total") is not None else direct_total
    try:
        final_total_value = float(final_total) if final_total is not None and str(final_total).strip() != "" else None
    except Exception:
        final_total_value = None
    if final_total_value is not None and final_total_value < 0:
        final_total_value = None
    return {
        "final_customer_total": round2(final_total_value) if final_total_value is not None else None,
        "finalized_at": final.get("finalized_at") or visit.get("finalized_at") or visit.get("finalizedAt"),
        "finalized_by": final.get("finalized_by") or visit.get("finalized_by") or visit.get("finalizedBy"),
        "finalization_source": final.get("finalization_source") or visit.get("finalization_source") or visit.get("finalizationSource"),
        "previous_service_total": round2(final.get("previous_service_total") or visit.get("previous_service_total") or visit.get("previousServiceTotal")),
    }


def visit_note_totals(notes: Any) -> Dict[str, Any]:
    parsed = parse_notes(notes)
    workshop = 0.0
    parts = 0.0
    confirmed_notes = 0.0
    pending = 0.0
    note_journal_ids = set()
    note_payment_ids = set()

    for item in parsed.get("items") or []:
        amount = item_amount(item if isinstance(item, dict) else {})
        if is_supplier_item(item if isinstance(item, dict) else {}):
            parts += amount
        else:
            workshop += amount

    for payment in parsed.get("payments") or []:
        if not isinstance(payment, dict):
            continue
        amount = safe_float(payment.get("amount"))
        if amount <= 0:
            continue
        payment_id = str(payment.get("id") or payment.get("payment_id") or "").strip()
        journal_id = str(payment.get("journalEntryId") or payment.get("journal_entry_id") or "").strip()
        if payment_id:
            note_payment_ids.add(payment_id)
        if journal_id:
            note_journal_ids.add(journal_id)
        if is_pending_payment(payment):
            pending += amount
        else:
            confirmed_notes += amount

    customer_total = workshop
    applied = min(confirmed_notes, customer_total)
    return {
        "parsed": parsed,
        "total_workshop": round2(workshop),
        "total_suppliers": round2(parts),
        "parts_charge_total": round2(parts),
        "supplier_cost_total": round2(parts),
        "current_customer_due": round2(workshop),
        "customer_total": round2(customer_total),
        "total_amount": round2(customer_total),
        "total_items": round2(customer_total),
        "notes_confirmed_paid": round2(confirmed_notes),
        "pending_payment_total": round2(pending),
        "note_journal_ids": note_journal_ids,
        "note_payment_ids": note_payment_ids,
        "applied_paid": round2(applied),
        "display_remaining": round2(max(customer_total - applied, 0)),
        "customer_credit": round2(max(confirmed_notes - customer_total, 0)),
    }


def journal_payment_amount(entry: Dict[str, Any]) -> float:
    amount = 0.0
    for line in entry.get("lines") or []:
        code = str(line.get("account") or line.get("code") or line.get("account_code") or "").strip()
        if code in {"005", "1103", "113"}:
            amount += max(safe_float(line.get("credit")) - safe_float(line.get("debit")), 0.0)
    return round2(amount if amount > 0 else entry.get("total"))


def payment_method_from_journal(entry: Dict[str, Any]) -> str:
    for line in entry.get("lines") or []:
        if safe_float(line.get("debit")) <= 0:
            continue
        code = str(line.get("account") or line.get("code") or "").strip()
        if code in {"003", "1101"}:
            return "cash"
        if code in {"004", "1102"}:
            return "bank_transfer"
        if code in {"006", "1104"}:
            return "pos"
    return "unknown"


def build_vehicle_summary(
    vehicle: Dict[str, Any],
    visits: List[Dict[str, Any]],
    operations: List[Dict[str, Any]],
    journal_entries: List[Dict[str, Any]],
) -> Dict[str, Any]:
    vehicle_id = str(vehicle.get("id") or "").strip()
    ops_by_visit: Dict[str, List[str]] = defaultdict(list)
    for op in operations or []:
        visit_id = str(op.get("visit_id") or op.get("visitId") or "").strip()
        op_id = str(op.get("id") or "").strip()
        if visit_id and op_id:
            ops_by_visit[visit_id].append(op_id)

    journal_by_ref: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    opening_receivable_total = 0.0
    for entry in journal_entries or []:
        source = str(entry.get("source") or "").strip().lower()
        if source == "archived_financial_period":
            continue
        if source == "financial_reset_opening_receivable":
            desc = str(entry.get("description") or "")
            match_vehicle = re.search(r"\[VEHICLE:([^\]]+)\]", desc, re.I)
            tagged_vehicle_id = match_vehicle.group(1).strip() if match_vehicle else ""
            if tagged_vehicle_id and tagged_vehicle_id == vehicle_id:
                opening_receivable_total += safe_float(entry.get("total"))
            continue
        if source not in {"operation_payment", "payment", "supplier_balance_payment", "unified_visit_payment"}:
            continue
        ref = str(entry.get("reference_id") or "").strip()
        if ref:
            journal_by_ref[ref].append(entry)
        desc = str(entry.get("description") or "")
        match = re.search(r"\[VISIT:([^\]]+)\]", desc, re.I)
        if match:
            journal_by_ref[match.group(1).strip()].append(entry)

    total_workshop = total_customer_due = total_parts = total_confirmed = total_pending = 0.0
    finalized_visit_count = 0
    cash = pos = bank = 0.0
    visit_rows = []

    for visit in visits or []:
        parsed_notes_for_archive_check = parse_notes(visit.get("notes"))
        if parsed_notes_for_archive_check.get("financial_reset_archived") or parsed_notes_for_archive_check.get("archived_financial_period"):
            continue
        visit_id = str(visit.get("id") or "").strip()
        totals = visit_note_totals(visit.get("notes"))
        visit_final = visit_finalization(visit)
        refs = {visit_id, *ops_by_visit.get(visit_id, [])}
        journal_seen = set()
        journal_paid = 0.0
        method_totals = defaultdict(float)
        for ref in refs:
            for entry in journal_by_ref.get(ref, []):
                entry_id = str(entry.get("id") or "").strip()
                if not entry_id or entry_id in journal_seen or entry_id in totals["note_journal_ids"]:
                    continue
                journal_seen.add(entry_id)
                amount = journal_payment_amount(entry)
                journal_paid += amount
                method_totals[payment_method_from_journal(entry)] += amount

        note_confirmed = safe_float(totals["notes_confirmed_paid"])
        confirmed = max(note_confirmed, journal_paid)
        visit_final_total = visit_final.get("final_customer_total")
        customer_total = safe_float(visit_final_total) if visit_final_total is not None else safe_float(totals["customer_total"])
        if visit_final_total is not None:
            finalized_visit_count += 1
        applied = min(confirmed, customer_total)
        remaining = max(customer_total - applied, 0.0)
        credit = max(confirmed - customer_total, 0.0)

        total_workshop += safe_float(totals["total_workshop"])
        total_customer_due += customer_total
        total_parts += safe_float(totals["parts_charge_total"])
        total_confirmed += confirmed
        total_pending += safe_float(totals["pending_payment_total"])
        cash += method_totals.get("cash", 0.0)
        pos += method_totals.get("pos", 0.0)
        bank += method_totals.get("bank_transfer", 0.0)

        visit_rows.append({
            "visit_id": visit_id,
            "date": visit.get("entry_date") or visit.get("created_at") or "",
            "total_workshop": round2(totals["total_workshop"]),
            "parts_charge_total": round2(totals["parts_charge_total"]),
            "customer_total": round2(customer_total),
            "final_customer_total": round2(visit_final_total) if visit_final_total is not None else None,
            "finalized_at": visit_final.get("finalized_at"),
            "finalized_by": visit_final.get("finalized_by"),
            "finalization_source": visit_final.get("finalization_source"),
            "confirmed_paid": round2(confirmed),
            "applied_paid": round2(applied),
            "display_remaining": round2(remaining),
            "customer_credit": round2(credit),
            "pending_payment_total": round2(totals["pending_payment_total"]),
        })

    if opening_receivable_total > 0:
        total_workshop += opening_receivable_total
        total_customer_due += opening_receivable_total

    finalization = vehicle_finalization(vehicle)
    current_customer_due = total_customer_due
    final_customer_total = finalization.get("final_customer_total")
    customer_total = safe_float(final_customer_total) if final_customer_total is not None else current_customer_due
    applied_paid = min(total_confirmed, customer_total)
    remaining = max(customer_total - applied_paid, 0.0)
    credit = max(total_confirmed - customer_total, 0.0)
    status = "unpaid" if total_confirmed <= 0 else ("paid_full" if remaining <= 0.01 else "partial")
    if credit > 0.01:
        status = "credit"

    return {
        "vehicle_id": vehicle.get("id"),
        "customer_name": vehicle.get("customer_name") or vehicle.get("customerName") or "غير محدد",
        "customer_phone": vehicle.get("customer_phone") or vehicle.get("customerPhone") or "",
        "plate_number": vehicle.get("plate_number") or vehicle.get("plateNumber") or "",
        "total_workshop": round2(total_workshop),
        "opening_receivable_total": round2(opening_receivable_total),
        "total_suppliers": round2(total_parts),
        "supplier_archive_total": round2(total_parts),
        "supplier_cost_total": round2(total_parts),
        "parts_charge_total": round2(total_parts),
        "current_customer_due": round2(current_customer_due),
        "workshop_service_total": round2(total_workshop),
        "final_customer_total": round2(final_customer_total) if final_customer_total is not None else None,
        "visit_final_customer_total": round2(total_customer_due),
        "finalized_visit_count": finalized_visit_count,
        "finalized_at": finalization.get("finalized_at"),
        "finalized_by": finalization.get("finalized_by"),
        "finalization_source": finalization.get("finalization_source"),
        "previous_service_total": round2(finalization.get("previous_service_total")),
        "customer_charge_total": round2(customer_total),
        "customer_total": round2(customer_total),
        "total_amount": round2(customer_total),
        "total_items": round2(customer_total),
        "total_paid": round2(total_confirmed),
        "confirmed_paid": round2(total_confirmed),
        "paid_on_account": round2(total_confirmed),
        "pending_payment_total": round2(total_pending),
        "applied_paid": round2(applied_paid),
        "balance": round2(remaining),
        "display_remaining": round2(remaining),
        "customer_credit": round2(credit),
        "customer_advance_liability": round2(credit),
        "payment_status": status,
        "method_totals": {"cash": round2(cash), "pos": round2(pos), "bank_transfer": round2(bank)},
        "visits": visit_rows,
        "engine_version": "unified-v1",
    }


def fetch_vehicle_summary(supabase_client: Any, vehicle_id: str, workshop_id: Optional[str] = None) -> Dict[str, Any]:
    vehicle_rows = supabase_client.table("vehicles").select("*").eq("id", vehicle_id).limit(1).execute().data or []
    if not vehicle_rows:
        raise ValueError("vehicle not found")
    visits = supabase_client.table("vehicle_visits").select("id,vehicle_id,status,notes,entry_date,created_at").eq("vehicle_id", vehicle_id).execute().data or []
    operations = supabase_client.table("operations").select("id,vehicle_id,visit_id,total,payment_method").eq("vehicle_id", vehicle_id).execute().data or []
    refs = {str(v.get("id")) for v in visits if v.get("id")}
    refs.update(str(o.get("id")) for o in operations if o.get("id"))
    journals: List[Dict[str, Any]] = []
    if refs:
        refs_list = list(refs)
        for idx in range(0, len(refs_list), 100):
            query = supabase_client.table("journal_entries").select("id,reference_id,source,total,lines,date,description")
            if workshop_id:
                query = query.eq("workshop_id", workshop_id)
            journals.extend(query.in_("reference_id", refs_list[idx:idx + 100]).execute().data or [])
    return build_vehicle_summary(vehicle_rows[0], visits, operations, journals)


def build_current_ar_snapshot(supabase_client: Any, workshop_id: str, end_date: Optional[str] = None) -> Dict[str, Any]:
    vehicles = supabase_client.table("vehicles").select("*").execute().data or []
    visits = supabase_client.table("vehicle_visits").select("id,vehicle_id,status,notes,entry_date,created_at").execute().data or []
    operations = supabase_client.table("operations").select("id,vehicle_id,visit_id,total,payment_method").execute().data or []
    journal_query = supabase_client.table("journal_entries").select("id,reference_id,source,total,lines,date,description,workshop_id")
    if workshop_id:
        journal_query = journal_query.eq("workshop_id", workshop_id)
    journal_entries = journal_query.execute().data or []

    visits_by_vehicle: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    operations_by_vehicle: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for visit in visits:
        vehicle_id = str(visit.get("vehicle_id") or "").strip()
        if vehicle_id:
            visits_by_vehicle[vehicle_id].append(visit)
    for operation in operations:
        vehicle_id = str(operation.get("vehicle_id") or "").strip()
        if vehicle_id:
            operations_by_vehicle[vehicle_id].append(operation)

    rows = []
    customers: Dict[str, Dict[str, Any]] = {}
    totals = {"workshop_total": 0.0, "supplier_total": 0.0, "confirmed_paid": 0.0, "receivable": 0.0, "cash": 0.0, "pos": 0.0, "bank_transfer": 0.0}
    ledger_rows = []
    for vehicle in vehicles:
        status = str(vehicle.get("status") or "").strip().lower()
        if status in {"delivered", "archived", "cancelled", "canceled", "ملغي", "ملغى", "مؤرشف", "مسلم", "تم التسليم"}:
            continue
        vehicle_id = str(vehicle.get("id") or "").strip()
        summary = build_vehicle_summary(
            vehicle,
            visits_by_vehicle.get(vehicle_id, []),
            operations_by_vehicle.get(vehicle_id, []),
            journal_entries,
        )
        receivable = safe_float(summary.get("display_remaining"))
        name = summary.get("customer_name") or "غير محدد"
        totals["workshop_total"] += safe_float(summary.get("total_workshop"))
        totals["supplier_total"] += safe_float(summary.get("parts_charge_total"))
        totals["confirmed_paid"] += safe_float(summary.get("confirmed_paid"))
        totals["receivable"] += receivable
        for method, amount in (summary.get("method_totals") or {}).items():
            if method in totals:
                totals[method] += safe_float(amount)
        row = {
            "vehicle_id": summary.get("vehicle_id"),
            "customer": name,
            "name": name,
            "phone": summary.get("customer_phone") or "",
            "plate": summary.get("plate_number"),
            "workshop_amount": summary.get("total_workshop"),
            "supplier_amount": summary.get("parts_charge_total"),
            "customer_total": summary.get("customer_total"),
            "confirmed_paid": summary.get("confirmed_paid"),
            "receivable": round2(receivable),
            "customer_credit": summary.get("customer_credit"),
            "visits": summary.get("visits") or [],
        }
        rows.append(row)
        if receivable > 0.005:
            if name not in customers:
                customers[name] = {"id": str(uuid.uuid5(uuid.NAMESPACE_DNS, name)).replace("-", "")[:16], "customer": name, "name": name, "phone": row["phone"], "balance": 0.0}
            customers[name]["balance"] = round2(customers[name]["balance"] + receivable)
            ledger_rows.append({
                "date": str((summary.get("visits") or [{}])[0].get("date") or ""),
                "customer": name,
                "phone": row["phone"],
                "vehicle_id": summary.get("vehicle_id"),
                "reference_id": summary.get("vehicle_id"),
                "amount": round2(receivable),
                "description": "محرك مالي موحد: إجمالي العميل - المطبق",
                "source": "unified_financial_engine",
            })
    return {"total_ar": round2(sum(c["balance"] for c in customers.values())), "customers": sorted(customers.values(), key=lambda r: r["customer"]), "vehicles": rows, "ledger_rows": ledger_rows, "totals": {k: round2(v) for k, v in totals.items()}, "engine_version": "unified-v1"}


def build_visit_payment_journal_entry(visit: Dict[str, Any], vehicle: Dict[str, Any], amount: float, method: str, date_value: Optional[str], payment_id: str, workshop_id: str) -> Dict[str, Any]:
    normalized_method = normalize_method(method)
    cash_code, cash_name = CASH_ACCOUNT_BY_METHOD.get(normalized_method, CASH_ACCOUNT_BY_METHOD["cash"])
    visit_id = str(visit.get("id") or "")
    customer = vehicle.get("customer_name") or vehicle.get("customerName") or "عميل"
    return {
        "id": str(uuid.uuid4()),
        "workshop_id": workshop_id,
        "date": date_value or datetime.now(timezone.utc).isoformat(),
        "description": f"تحصيل دفعة مؤكدة - {customer} [VISIT:{visit_id}] [PAYMENT:{payment_id}]".strip(),
        "lines": [
            {"account": cash_code, "account_name": cash_name, "debit": round2(amount), "credit": 0},
            {"account": AR_ACCOUNT[0], "account_name": AR_ACCOUNT[1], "debit": 0, "credit": round2(amount)},
        ],
        "total": round2(amount),
        "source": "unified_visit_payment",
        "transaction_type": "payment",
        "reference_id": visit_id,
    }
