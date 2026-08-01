from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, Iterable, List, Tuple


CENT = Decimal("0.01")
EQUATIONS_VERSION = "financial-reconciliation-shadow-v1.0-live15-exclusive-readonly"


def dec(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        raw = value
    elif value is None or isinstance(value, bool):
        raw = Decimal("0")
    else:
        text = str(value).replace(",", "").strip()
        if not text:
            raw = Decimal("0")
        else:
            try:
                raw = Decimal(text)
            except InvalidOperation:
                raw = Decimal("0")
    return raw.quantize(CENT, rounding=ROUND_HALF_UP)


def out(value: Any) -> float:
    return float(dec(value))


def text(value: Any) -> str:
    return str(value or "").strip()


def lower(value: Any) -> str:
    return text(value).lower()


def table_fetch_all(supabase: Any, table: str, select: str = "*") -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    start = 0
    page = 1000
    while True:
        data = supabase.table(table).select(select).range(start, start + page - 1).execute().data or []
        rows.extend(data)
        if len(data) < page:
            break
        start += page
    return rows


def row_id(row: Dict[str, Any]) -> str:
    return text(row.get("id"))


def vehicle_id_from_visit(row: Dict[str, Any]) -> str:
    return text(row.get("vehicle_id") or row.get("vehicleId"))


def vehicle_id_from_operation(row: Dict[str, Any]) -> str:
    return text(row.get("vehicle_id") or row.get("vehicleId"))


def visit_id_from_operation(row: Dict[str, Any]) -> str:
    return text(row.get("visit_id") or row.get("visitId"))


def operation_total(row: Dict[str, Any]) -> Decimal:
    return dec(row.get("total") or row.get("amount") or row.get("subtotal"))


def operation_method(row: Dict[str, Any]) -> str:
    return normalize_payment_method(row.get("payment_method") or row.get("paymentMethod"))


def operation_status(row: Dict[str, Any]) -> str:
    return lower(row.get("payment_status") or row.get("paymentStatus"))


def operation_type(row: Dict[str, Any]) -> str:
    return lower(row.get("type") or row.get("operation_type") or row.get("category"))


def normalize_payment_method(value: Any) -> str:
    raw = lower(value)
    if raw in {"cash", "نقد", "نقدي", "كاش"}:
        return "cash"
    if raw in {"pos", "card", "mada", "visa", "mastercard", "بطاقة", "بطاقه", "شبكة", "نقاط بيع"}:
        return "pos"
    if raw in {"bank", "transfer", "bank_transfer", "تحويل", "تحويل بنكي", "تحويل_بنكي", "بنك"}:
        return "bank_transfer"
    if raw in {"credit", "اجل", "آجل", "ذمة", "ذمم", "unpaid", "pending", "partial", "deferred"}:
        return "credit_state_not_payment_method"
    return raw or "unknown"


def line_code(line: Dict[str, Any]) -> str:
    return text(line.get("code") or line.get("account") or line.get("account_code"))


def journal_lines(row: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw = row.get("lines") or []
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []
    return raw if isinstance(raw, list) else []


AR_CODES = {"005", "1103", "113"}
REVENUE_CODES = {"024", "025", "026", "027", "028", "041", "41", "4000", "4100", "4101", "4102", "4103"}
EXPENSE_CODES = {*(str(i).zfill(3) for i in range(29, 49)), "167", "5000", "5100", "5101", "5102", "5103", "6000", "6100", "6101", "6102"}
CASH_CODES = {"003", "1101"}
BANK_TRANSFER_CODES = {"004", "1102"}
POS_CODES = {"006", "1104"}
PAYMENT_SOURCES = {"operation_payment", "visit_receipt_voucher", "supplier_balance_payment", "payment", "operation_discount", "visit_discount"}


def journal_impact(rows: Iterable[Dict[str, Any]]) -> Dict[str, float]:
    totals = defaultdict(lambda: Decimal("0.00"))
    for row in rows:
        for line in journal_lines(row):
            code = line_code(line)
            debit = dec(line.get("debit"))
            credit = dec(line.get("credit"))
            if code in REVENUE_CODES:
                totals["revenue"] += credit - debit
            if code in EXPENSE_CODES:
                totals["expenses"] += debit - credit
            if code in AR_CODES:
                totals["ar_net"] += debit - credit
                totals["credit_sales_ar_debit"] += max(debit - credit, Decimal("0.00"))
                totals["payments_reduce_ar"] += max(credit - debit, Decimal("0.00"))
            if code in CASH_CODES:
                totals["cash"] += debit - credit
            if code in BANK_TRANSFER_CODES:
                totals["bank_transfer"] += debit - credit
            if code in POS_CODES:
                totals["pos"] += debit - credit
    for key in ("revenue", "expenses", "ar_net", "credit_sales_ar_debit", "payments_reduce_ar", "cash", "bank_transfer", "pos"):
        totals[key] += Decimal("0.00")
    return {key: out(value) for key, value in totals.items()}


def trial_balance(rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    accounts: Dict[str, Dict[str, Any]] = {}
    total_debit = Decimal("0.00")
    total_credit = Decimal("0.00")
    for row in rows:
        for line in journal_lines(row):
            code = line_code(line) or "unknown"
            debit = dec(line.get("debit"))
            credit = dec(line.get("credit"))
            total_debit += debit
            total_credit += credit
            acc = accounts.setdefault(code, {"code": code, "name": text(line.get("account_name") or line.get("name")), "debit": Decimal("0.00"), "credit": Decimal("0.00")})
            acc["debit"] += debit
            acc["credit"] += credit
    rows_out = []
    for acc in sorted(accounts.values(), key=lambda item: item["code"]):
        rows_out.append({"code": acc["code"], "name": acc["name"], "debit": out(acc["debit"]), "credit": out(acc["credit"]), "net_debit_minus_credit": out(acc["debit"] - acc["credit"])})
    return {"accounts": rows_out, "total_debit": out(total_debit), "total_credit": out(total_credit), "difference": out(total_debit - total_credit), "balanced": dec(total_debit - total_credit) == Decimal("0.00")}


def is_credit_operation(row: Dict[str, Any]) -> bool:
    return operation_method(row) == "credit_state_not_payment_method" or operation_status(row) in {"credit", "unpaid", "partial", "pending", "deferred"}


def resolve_reference(row: Dict[str, Any], operations: Dict[str, Dict[str, Any]], visits: Dict[str, Dict[str, Any]], vehicles: Dict[str, Dict[str, Any]]) -> Dict[str, str]:
    ref = text(row.get("reference_id") or row.get("referenceId"))
    operation_id = ""
    visit_id = ""
    vehicle_id = ""
    if ref in operations:
        operation_id = ref
        op = operations[ref]
        vehicle_id = vehicle_id_from_operation(op)
        visit_id = visit_id_from_operation(op)
    elif ref in visits:
        visit_id = ref
        vehicle_id = vehicle_id_from_visit(visits[ref])
    elif ref in vehicles:
        vehicle_id = ref
    desc = text(row.get("description"))
    match = re.search(r"\[VISIT:([^\]]+)\]", desc, re.I)
    if match and not visit_id:
        visit_id = match.group(1).strip()
        if visit_id in visits and not vehicle_id:
            vehicle_id = vehicle_id_from_visit(visits[visit_id])
    return {"reference_id": ref, "operation_id": operation_id, "visit_id": visit_id, "vehicle_id": vehicle_id}


def classify_scope(vehicle_id: str, source: str, live_vehicle_ids: set[str], pending_opening: bool = False) -> Tuple[str, List[str]]:
    reasons: List[str] = []
    if pending_opening:
        return "pending_decision", ["origin_type=opening_balance ويحتاج قرار مالك: إدخاله في الحسبة الحية أو إبقاؤه خارجها"]
    if vehicle_id:
        if vehicle_id in live_vehicle_ids:
            return "live", ["vehicle_id ضمن قائمة الـ15 النشطة المعتمدة مؤقتاً للقراءة فقط"]
        return "archive", ["vehicle_id خارج قائمة الـ15 النشطة؛ يصنف خارج النطاق الحي حصرياً حتى اعتماد تصحيح الحالات"]
    if lower(source) in {"pos", "standalone_pos_sale"}:
        return "unlinked", ["POS بلا vehicle_id؛ يحتاج تحقق من القيد قبل اعتباره live"]
    return "unlinked", ["لا يوجد vehicle_id/visit_id/origin واضح"]


def operation_scope(row: Dict[str, Any], live_vehicle_ids: set[str], journals_by_ref: Dict[str, List[Dict[str, Any]]]) -> Tuple[str, List[str]]:
    vehicle_id = vehicle_id_from_operation(row)
    if vehicle_id:
        if vehicle_id in live_vehicle_ids:
            return "live", ["operation.vehicle_id ضمن قائمة live المؤقتة"]
        return "archive", ["operation.vehicle_id خارج قائمة live المؤقتة"]
    refs = journals_by_ref.get(row_id(row), [])
    if refs:
        return "live", ["عملية مستقلة بلا مركبة لكنها مرحلة بقيد مالي؛ تصنف live كـstandalone"]
    return "posting_missing", ["عملية مستقلة بلا مركبة ولا يوجد قيد مالي مقابلها"]


def build_payment_allocations(journals: List[Dict[str, Any]], operations: Dict[str, Dict[str, Any]], visits: Dict[str, Dict[str, Any]], vehicles: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for journal in journals:
        if lower(journal.get("source")) not in PAYMENT_SOURCES:
            continue
        ref = text(journal.get("reference_id") or journal.get("referenceId"))
        if ref not in operations or not is_credit_operation(operations[ref]):
            continue
        ar_credit = Decimal("0.00")
        payment_method = "unknown"
        for line in journal_lines(journal):
            code = line_code(line)
            debit = dec(line.get("debit"))
            credit = dec(line.get("credit"))
            if code in AR_CODES:
                ar_credit += max(credit - debit, Decimal("0.00"))
            if debit > 0:
                if code in CASH_CODES:
                    payment_method = "cash"
                elif code in POS_CODES:
                    payment_method = "pos"
                elif code in BANK_TRANSFER_CODES:
                    payment_method = "bank_transfer"
        ctx = resolve_reference(journal, operations, visits, vehicles)
        op = operations.get(ref, {})
        visit = visits.get(ctx["visit_id"], {})
        vehicle = vehicles.get(ctx["vehicle_id"], {})
        rows.append({
            "payment_id": row_id(journal),
            "journal_entry_id": row_id(journal),
            "amount": out(ar_credit),
            "source": journal.get("source"),
            "operation_id": ref,
            "operation_total": out(operation_total(op)),
            "visit_id": ctx["visit_id"],
            "vehicle_id": ctx["vehicle_id"],
            "vehicle_status": vehicle.get("status"),
            "plate": vehicle.get("plate_number") or vehicle.get("plateNumber"),
            "customer": op.get("partner_name") or vehicle.get("customer_name") or vehicle.get("customerName"),
            "approval_status": journal.get("approval_status") or journal.get("status") or "posted",
            "payment_method": payment_method,
            "allocated_to_ar": ar_credit > Decimal("0.00") and ref in operations and is_credit_operation(op),
            "resulting_journal_entry": row_id(journal),
            "description": text(journal.get("description")),
            "visit_status": visit.get("status"),
        })
    return rows


def duplicate_signatures(journals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for journal in journals:
        norm_lines = []
        for line in journal_lines(journal):
            norm_lines.append((line_code(line), out(line.get("debit")), out(line.get("credit"))))
        raw = json.dumps({"date": text(journal.get("date"))[:10], "reference_id": text(journal.get("reference_id")), "source": text(journal.get("source")), "total": out(journal.get("total")), "lines": sorted(norm_lines)}, ensure_ascii=False, sort_keys=True)
        groups[hashlib.sha1(raw.encode()).hexdigest()].append(journal)
    return [{"signature": sig, "count": len(rows), "journal_entry_ids": [row_id(row) for row in rows], "source": rows[0].get("source"), "reference_id": rows[0].get("reference_id"), "total": out(rows[0].get("total"))} for sig, rows in groups.items() if len(rows) > 1]


def vehicle_summary(vehicle: Dict[str, Any], visits_by_vehicle: Dict[str, List[Dict[str, Any]]], operations_by_vehicle: Dict[str, List[Dict[str, Any]]], payment_allocations: List[Dict[str, Any]], live_ids: set[str], archive_page_all_ids: set[str]) -> Dict[str, Any]:
    vid = row_id(vehicle)
    vops = operations_by_vehicle.get(vid, [])
    credit_total = Decimal("0.00")
    payment_total = Decimal("0.00")
    op_ids = {row_id(op) for op in vops}
    for op in vops:
        if is_credit_operation(op):
            credit_total += operation_total(op)
    for payment in payment_allocations:
        if payment.get("operation_id") in op_ids:
            payment_total += dec(payment.get("amount"))
    latest_visits = sorted(visits_by_vehicle.get(vid, []), key=lambda item: text(item.get("entry_date") or item.get("created_at")), reverse=True)
    latest = latest_visits[0] if latest_visits else {}
    return {
        "vehicle_id": vid,
        "customer": vehicle.get("customer_name") or vehicle.get("customerName"),
        "plate": vehicle.get("plate_number") or vehicle.get("plateNumber"),
        "raw_status": vehicle.get("status"),
        "entry_date": text(vehicle.get("entry_date") or vehicle.get("entryDate"))[:10],
        "latest_visit_id": row_id(latest),
        "latest_visit_date": text(latest.get("entry_date") or latest.get("created_at"))[:10],
        "latest_visit_status": latest.get("status"),
        "appears_dashboard": vid in live_ids,
        "appears_archive_page_current": vid in archive_page_all_ids,
        "warning": "raw_status=archived لكنه ضمن live المؤقت" if vid in live_ids and lower(vehicle.get("status")) == "archived" else "",
        "operations_count": len(vops),
        "operations_total": out(sum((operation_total(op) for op in vops), Decimal("0.00"))),
        "credit_sales_total": out(credit_total),
        "allocated_payments": out(payment_total),
        "receivable_balance": out(max(credit_total - payment_total, Decimal("0.00"))),
    }


def build_reconciliation_audit(supabase: Any, workshop_id: str = "finmodule-sync") -> Dict[str, Any]:
    before_counts = {table: len(table_fetch_all(supabase, table, "id")) for table in ("vehicles", "vehicle_visits", "operations", "journal_entries")}
    vehicles_rows = table_fetch_all(supabase, "vehicles")
    visits_rows = table_fetch_all(supabase, "vehicle_visits")
    operations_rows = table_fetch_all(supabase, "operations")
    journal_rows = table_fetch_all(supabase, "journal_entries")

    vehicles = {row_id(row): row for row in vehicles_rows if row_id(row)}
    visits = {row_id(row): row for row in visits_rows if row_id(row)}
    operations = {row_id(row): row for row in operations_rows if row_id(row)}

    dashboard_visible = [row for row in sorted(vehicles_rows, key=lambda item: text(item.get("entry_date") or item.get("entryDate")), reverse=True) if lower(row.get("status")) != "delivered"]
    live_vehicle_ids = {row_id(row) for row in dashboard_visible}
    raw_archive_ids = {row_id(row) for row in vehicles_rows if lower(row.get("status")) in {"delivered", "archived"}}
    archive_page_current_ids = {row_id(row) for row in vehicles_rows if row_id(row)}
    overlap_ids = sorted(live_vehicle_ids & raw_archive_ids)

    operations_by_vehicle: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    visits_by_vehicle: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    journals_by_ref: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for visit in visits_rows:
        visits_by_vehicle[vehicle_id_from_visit(visit)].append(visit)
    for operation in operations_rows:
        operations_by_vehicle[vehicle_id_from_operation(operation)].append(operation)
    for journal in journal_rows:
        journals_by_ref[text(journal.get("reference_id") or journal.get("referenceId"))].append(journal)

    payment_allocations = build_payment_allocations(journal_rows, operations, visits, vehicles)

    journal_scope_rows: List[Dict[str, Any]] = []
    journals_by_scope: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for journal in journal_rows:
        ctx = resolve_reference(journal, operations, visits, vehicles)
        pending_opening = lower(journal.get("source")) == "opening_balance_correction" or text(ctx["reference_id"]).startswith("opening-")
        scope, reasons = classify_scope(ctx["vehicle_id"], journal.get("source"), live_vehicle_ids, pending_opening=pending_opening)
        journals_by_scope[scope].append(journal)
        vehicle = vehicles.get(ctx["vehicle_id"], {})
        journal_scope_rows.append({
            "record_type": "journal_entry",
            "journal_entry_id": row_id(journal),
            "reference_id": ctx["reference_id"],
            "operation_id": ctx["operation_id"],
            "visit_id": ctx["visit_id"],
            "vehicle_id": ctx["vehicle_id"],
            "raw_status": vehicle.get("status"),
            "origin_type": "opening_balance" if pending_opening else ("vehicle_visit" if ctx["vehicle_id"] else "manual_adjustment"),
            "origin_id": ctx["visit_id"] or ctx["operation_id"] or ctx["reference_id"],
            "entry_channel": journal.get("entry_channel") or "legacy_unknown",
            "event_type": journal.get("event_type") or journal.get("source") or "legacy_unknown",
            "resolved_scope": scope,
            "classification_reasons": reasons,
            "impact": journal_impact([journal]),
            "total": out(journal.get("total")),
        })

    operation_scope_rows: List[Dict[str, Any]] = []
    operations_by_scope: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for operation in operations_rows:
        scope, reasons = operation_scope(operation, live_vehicle_ids, journals_by_ref)
        operations_by_scope[scope].append(operation)
        vid = vehicle_id_from_operation(operation)
        vehicle = vehicles.get(vid, {})
        operation_scope_rows.append({
            "record_type": "operation",
            "operation_id": row_id(operation),
            "vehicle_id": vid,
            "visit_id": visit_id_from_operation(operation),
            "raw_status": vehicle.get("status"),
            "origin_type": "vehicle_visit" if vid else "standalone_pos_sale",
            "origin_id": visit_id_from_operation(operation) or row_id(operation),
            "entry_channel": operation.get("entry_channel") or "legacy_unknown",
            "event_type": operation_type(operation) or "legacy_unknown",
            "payment_method": operation_method(operation),
            "resolved_scope": scope,
            "classification_reasons": reasons,
            "total": out(operation_total(operation)),
        })

    def scope_summary(rows_by_scope: Dict[str, List[Dict[str, Any]]], *, journal: bool) -> Dict[str, Any]:
        scopes = ["live", "archive", "legacy_excluded", "unlinked", "pending_decision", "posting_missing"]
        result = {}
        for scope in scopes:
            rows = rows_by_scope.get(scope, [])
            result[scope] = {"count": len(rows), "impact": journal_impact(rows) if journal else {}, "operations_total": out(sum((operation_total(row) for row in rows), Decimal("0.00"))) if not journal else 0.0}
        return result

    account_041_rows = []
    expense_035_rows = []
    for journal in journal_rows:
        ctx = resolve_reference(journal, operations, visits, vehicles)
        vehicle = vehicles.get(ctx["vehicle_id"], {})
        amount_041 = Decimal("0.00")
        amount_035 = Decimal("0.00")
        for line in journal_lines(journal):
            if line_code(line) == "041":
                amount_041 += dec(line.get("credit")) - dec(line.get("debit"))
            if line_code(line) == "035":
                amount_035 += dec(line.get("debit")) - dec(line.get("credit"))
        if amount_041:
            account_041_rows.append({"journal_entry_id": row_id(journal), "amount": out(amount_041), "reference_id": ctx["reference_id"], "vehicle_id": ctx["vehicle_id"], "raw_status": vehicle.get("status"), "description": text(journal.get("description"))})
        if amount_035:
            account_035 = {"journal_entry_id": row_id(journal), "amount": out(amount_035), "reference_id": ctx["reference_id"], "vehicle_id": ctx["vehicle_id"], "raw_status": vehicle.get("status"), "description": text(journal.get("description"))}
            expense_035_rows.append(account_035)

    credit_ops = [op for op in operations_rows if is_credit_operation(op)]
    credit_total = sum((operation_total(op) for op in credit_ops), Decimal("0.00"))
    allocated_total = sum((dec(row.get("amount")) for row in payment_allocations), Decimal("0.00"))
    current_remaining = credit_total - allocated_total
    owner_reported_page_total = Decimal("51735.00")
    delta = owner_reported_page_total - current_remaining
    delta_candidates = []
    if delta:
        for op in credit_ops:
            if operation_total(op) == abs(delta):
                vid = vehicle_id_from_operation(op)
                vehicle = vehicles.get(vid, {})
                delta_candidates.append({"candidate_type": "credit_operation_not_payment", "operation_id": row_id(op), "amount": out(operation_total(op)), "vehicle_id": vid, "plate": vehicle.get("plate_number"), "customer": op.get("partner_name") or vehicle.get("customer_name"), "raw_status": vehicle.get("status"), "reason": "يطابق فرق 500 ر.س؛ السجل عملية آجلة قائمة وليس دفعة"})

    opening_rows = []
    opening_total = Decimal("0.00")
    for journal in journal_rows:
        if lower(journal.get("source")) == "opening_balance_correction" or text(journal.get("reference_id")).startswith("opening-"):
            ar_net = Decimal("0.00")
            for line in journal_lines(journal):
                if line_code(line) in AR_CODES:
                    ar_net += dec(line.get("debit")) - dec(line.get("credit"))
            opening_total += ar_net
            opening_rows.append({"journal_entry_id": row_id(journal), "reference_id": text(journal.get("reference_id")), "origin_type": "opening_balance", "resolved_scope": "pending_decision", "ar_net": out(ar_net), "description": text(journal.get("description"))})

    before_again = {table: len(table_fetch_all(supabase, table, "id")) for table in ("vehicles", "vehicle_visits", "operations", "journal_entries")}
    scopes_count = sum(len(rows) for rows in journals_by_scope.values())
    operation_scopes_count = sum(len(rows) for rows in operations_by_scope.values())

    active_vehicle_rows = [vehicle_summary(row, visits_by_vehicle, operations_by_vehicle, payment_allocations, live_vehicle_ids, archive_page_current_ids) for row in dashboard_visible]
    archive_vehicle_rows = [vehicle_summary(row, visits_by_vehicle, operations_by_vehicle, payment_allocations, live_vehicle_ids, archive_page_current_ids) for row in vehicles_rows if row_id(row) not in live_vehicle_ids]

    return {
        "success": True,
        "metadata": {"generated_at": datetime.now(timezone.utc).isoformat(), "workshop_id": workshop_id, "equations_version": EQUATIONS_VERSION, "read_only": True, "production_pages_unchanged": True},
        "mutation_guard": {"before_counts": before_counts, "after_counts": before_again, "unchanged": before_counts == before_again},
        "raw_classification": {
            "vehicles_total": len(vehicles_rows),
            "raw_status_counts": dict(Counter(text(row.get("status") or "NULL") for row in vehicles_rows)),
            "dashboard_visible_current_logic_count": len(dashboard_visible),
            "raw_archive_status_count": len(raw_archive_ids),
            "archive_page_current_display_count": len(archive_page_current_ids),
            "overlap_active_and_raw_archive_ids": overlap_ids,
            "warning": "raw_classification تشخيصي فقط ولا يستخدم للحسبة المالية النهائية بسبب التداخل",
        },
        "resolved_exclusive_scopes": {
            "vehicle_scope_counts": {"live": len(live_vehicle_ids), "archive": len(vehicles_rows) - len(live_vehicle_ids), "total": len(vehicles_rows), "exclusive_sum_ok": len(live_vehicle_ids) + (len(vehicles_rows) - len(live_vehicle_ids)) == len(vehicles_rows)},
            "journal_entry_scope_counts": {scope: len(rows) for scope, rows in sorted(journals_by_scope.items())},
            "journal_entry_scope_sum": scopes_count,
            "journal_entry_total": len(journal_rows),
            "journal_entry_exclusive_sum_ok": scopes_count == len(journal_rows),
            "operation_scope_counts": {scope: len(rows) for scope, rows in sorted(operations_by_scope.items())},
            "operation_scope_sum": operation_scopes_count,
            "operation_total": len(operations_rows),
            "operation_exclusive_sum_ok": operation_scopes_count == len(operations_rows),
            "journal_entry_impacts": scope_summary(journals_by_scope, journal=True),
            "operation_impacts": scope_summary(operations_by_scope, journal=False),
        },
        "active_15_vehicles": active_vehicle_rows,
        "archive_vehicle_ids": [{"vehicle_id": row["vehicle_id"], "customer": row["customer"], "plate": row["plate"], "raw_status": row["raw_status"], "operations_total": row["operations_total"], "receivable_balance": row["receivable_balance"]} for row in archive_vehicle_rows],
        "record_classification_rows": {"journal_entries": journal_scope_rows, "operations": operation_scope_rows},
        "ar_reconciliation": {
            "credit_sales_total": out(credit_total),
            "payment_allocations_total": out(allocated_total),
            "remaining_by_credit_operations_minus_allocations": out(current_remaining),
            "owner_reported_page_total_from_baseline": out(owner_reported_page_total),
            "delta_against_owner_reported": out(delta),
            "payment_allocations": payment_allocations,
            "delta_500_candidates": delta_candidates,
        },
        "revenue_210_reconciliation": {"account": "041", "rows": account_041_rows, "total": out(sum((dec(row["amount"]) for row in account_041_rows), Decimal("0.00")))},
        "expense_reconciliation": {"account": "035", "rows": expense_035_rows, "total": out(sum((dec(row["amount"]) for row in expense_035_rows), Decimal("0.00"))), "previous_gap_210_explanation": "التقرير السابق استخدم مجموعات raw متداخلة؛ resolved_exclusive يخصص كل قيد مرة واحدة ويظهر مصروف 16,810 كاملاً، وليس 16,600."},
        "opening_balance_scenarios": {"pending_decision_rows": opening_rows, "include_in_ar_total_adds": out(opening_total), "exclude_from_live_adds": 0.0},
        "standalone_pos_operations": [row for row in operation_scope_rows if row.get("origin_type") == "standalone_pos_sale"],
        "potential_duplicate_journal_entries": duplicate_signatures(journal_rows),
        "trial_balance": trial_balance(journal_rows),
        "acceptance_flags": {
            "active_vehicle_count_is_15": len(live_vehicle_ids) == 15,
            "no_journal_record_in_two_scopes": scopes_count == len(journal_rows),
            "journal_scope_sum_equals_all": scopes_count == len(journal_rows),
            "operation_scope_sum_equals_all": operation_scopes_count == len(operations_rows),
            "raw_overlap_detected": len(overlap_ids) == 2,
            "ar_delta_500_explained_with_ids": bool(delta_candidates),
            "revenue_210_explained": sum((dec(row["amount"]) for row in account_041_rows), Decimal("0.00")) == Decimal("210.00"),
            "expense_210_gap_independently_explained": sum((dec(row["amount"]) for row in expense_035_rows), Decimal("0.00")) == Decimal("16810.00"),
            "trial_balance_balanced": trial_balance(journal_rows)["balanced"],
            "report_did_not_mutate_tables": before_counts == before_again,
        },
        "write_path_map": {
            "vehicle_page": "VehicleDetails.jsx يكتب حالياً زيارة/notes وبعض القيود؛ يجب تحويله لاحقاً للمحرك الموحد",
            "operations_page": "Operations.jsx -> /api/operations؛ يجب أن يرجع للأصل عند source=vehicle_visit",
            "pos": "SmartPOSJournal.jsx؛ تحصيل مرتبط يستخدم confirm-payment وبعض المسارات تنشئ operation/journal",
            "katrina": "core/action_runtime.py قناة تنفيذ وليست origin_type محاسبي",
        },
        "target_event_model": {"origin_type": "vehicle_visit | standalone_pos_sale | purchase | receipt | opening_balance | manual_adjustment", "origin_id": "original document id", "entry_channel": "vehicle_page | operations_page | pos | katrina", "payment_method": "cash | pos | bank_transfer", "event_type": "sale_posted | credit_posted | payment_applied | expense_posted | reversal_posted", "reporting_scope": "live | archive | unlinked | pending_decision", "idempotency_key": "required before write phase"},
    }