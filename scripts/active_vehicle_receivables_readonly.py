from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, time, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from core.unified_financial_engine import build_vehicle_summary, journal_payment_amount, parse_notes  # noqa: E402
from financial_reconciliation import journal_lines, table_fetch_all  # noqa: E402
from supabase_service import SupabaseService  # noqa: E402


RIYADH = ZoneInfo("Asia/Riyadh")
UTC = timezone.utc
CENT = Decimal("0.01")
START_RIYADH = datetime.combine(datetime(2026, 7, 5).date(), time.min, tzinfo=RIYADH)
END_RIYADH = datetime.combine(datetime(2026, 8, 4).date(), time.max, tzinfo=RIYADH)

REPORT_PATH = ROOT / "memory" / "ACTIVE_VEHICLES_CURRENT_RECEIVABLES_30_DAYS_READ_ONLY.md"
JSON_PATH = ROOT / "test_reports" / "active_vehicles_current_receivables_30_days_read_only.json"

AR_CODES = {"005", "1103", "113"}
REVENUE_CODES = {"024", "025", "026", "027", "028", "041", "042", "4000", "4100"}
PAYMENT_SOURCES = {"operation_payment", "payment", "supplier_balance_payment", "unified_visit_payment", "visit_receipt_voucher", "operation_discount", "visit_discount"}
ACTIVE_EXCLUDED_STATUSES = {"delivered", "archived", "cancelled", "canceled", "ملغي", "ملغى", "مؤرشف", "مسلم", "تم التسليم"}
VISIT_EXCLUDED_STATUSES = {"cancelled", "canceled", "deleted", "void", "ملغي", "ملغى", "محذوف"}
PENDING_PAYMENT_STATUSES = {"pending", "pending_confirmation", "awaiting_confirmation", "unconfirmed", "بانتظار التأكيد", "بانتظار_التأكيد"}


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


def money(value: Any) -> str:
    return f"{dec(value):,.2f}"


def out(value: Any) -> float:
    return float(dec(value))


def text(value: Any) -> str:
    return str(value or "").strip()


def norm(value: Any) -> str:
    raw = text(value).lower()
    raw = re.sub(r"[\sـ]+", " ", raw)
    return raw.strip()


def row_id(row: Dict[str, Any]) -> str:
    return text(row.get("id"))


def parse_dt(value: Any) -> Optional[datetime]:
    raw = text(value)
    if not raw:
        return None
    try:
        if len(raw) == 10 and raw[4] == "-":
            return datetime.fromisoformat(raw).replace(tzinfo=RIYADH)
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(RIYADH)
    except Exception:
        return None


def date_text(value: Any) -> str:
    dt = parse_dt(value)
    return dt.date().isoformat() if dt else text(value)[:10]


def in_scope_date(value: Any) -> bool:
    dt = parse_dt(value)
    return bool(dt and START_RIYADH <= dt <= END_RIYADH)


def is_active_vehicle(vehicle: Dict[str, Any]) -> bool:
    return norm(vehicle.get("status")) not in ACTIVE_EXCLUDED_STATUSES


def item_amount(item: Dict[str, Any]) -> Decimal:
    if item.get("total") is not None:
        return dec(item.get("total"))
    qty = dec(item.get("quantity") if item.get("quantity") is not None else item.get("qty") or 1)
    price = dec(item.get("price") or item.get("unit_price"))
    return dec(qty * price)


def item_cancelled(item: Dict[str, Any]) -> bool:
    status = norm(item.get("status"))
    return bool(item.get("cancelled") or item.get("deleted") or status in VISIT_EXCLUDED_STATUSES)


def item_is_internal_only(item: Dict[str, Any]) -> bool:
    billing = norm(item.get("billingType") or item.get("billing_type"))
    flags = ["internal", "workshop_expense", "expense", "مصاريف داخلية", "مصروف داخلي"]
    explicitly_not_charged = item.get("chargedToCustomer") is False or item.get("customer_charge") is False
    return explicitly_not_charged or billing in flags or item.get("internalOnly") is True or item.get("workshopExpense") is True


def classify_item(item: Dict[str, Any]) -> str:
    raw_type = norm(item.get("itemType") or item.get("item_type") or item.get("type"))
    billing = norm(item.get("billingType") or item.get("billing_type"))
    if raw_type == "service" or (billing == "workshop" and raw_type not in {"part", "supplier"}):
        return "service"
    if raw_type in {"part", "supplier"} or billing == "supplier":
        return "part_or_customer_charged_supplier_line"
    return "service" if raw_type else "unresolved"


def is_pending_payment(payment: Dict[str, Any]) -> bool:
    status = norm(payment.get("status") or payment.get("paymentStatus") or payment.get("payment_status"))
    return payment.get("confirmed") is False or status in PENDING_PAYMENT_STATUSES


def payment_amount(payment: Dict[str, Any]) -> Decimal:
    return dec(payment.get("amount"))


def journal_has_ar_debit(entry: Dict[str, Any]) -> bool:
    for line in journal_lines(entry):
        code = text(line.get("account") or line.get("code") or line.get("account_code"))
        if code in AR_CODES and dec(line.get("debit")) > 0:
            return True
    return False


def journal_has_revenue_credit(entry: Dict[str, Any]) -> bool:
    for line in journal_lines(entry):
        code = text(line.get("account") or line.get("code") or line.get("account_code"))
        if code in REVENUE_CODES and dec(line.get("credit")) > 0:
            return True
    return False


def compact_item(item: Dict[str, Any]) -> str:
    return f"{text(item.get('name')) or 'بدون اسم'} ×{text(item.get('quantity') or item.get('qty') or 1)} = {money(item_amount(item))}"


def compact_payment(payment: Dict[str, Any]) -> str:
    method = text(payment.get("paymentMethod") or payment.get("method") or payment.get("payment_method")) or "غير محدد"
    return f"{money(payment_amount(payment))} ({method}, {date_text(payment.get('date'))})"


def unique_join(values: Iterable[str], max_items: int = 5) -> str:
    clean = [v for v in dict.fromkeys(text(v) for v in values if text(v))]
    if not clean:
        return "—"
    extra = len(clean) - max_items
    shown = clean[:max_items]
    return "، ".join(shown) + (f"، +{extra}" if extra > 0 else "")


def duplicate_analysis(items: List[Dict[str, Any]], payments: List[Dict[str, Any]]) -> Dict[str, Any]:
    item_ids = [text(item.get("id") or item.get("source_id")) for item in items if text(item.get("id") or item.get("source_id"))]
    confirmed_item_duplicates = [item_id for item_id, count in Counter(item_ids).items() if count > 1]

    suspected_groups: List[Dict[str, Any]] = []
    by_signature: Dict[Tuple[str, str, str, str], List[Dict[str, Any]]] = defaultdict(list)
    for item in items:
        sig = (
            norm(item.get("name")),
            text(item.get("quantity") or item.get("qty") or 1),
            money(item.get("price") or 0),
            money(item_amount(item)),
        )
        by_signature[sig].append(item)
    for sig, rows in by_signature.items():
        if len(rows) > 1:
            suspected_groups.append({
                "signature": " | ".join(sig),
                "count": len(rows),
                "amount": out(sum((item_amount(row) for row in rows), Decimal("0"))),
                "item_ids": [text(row.get("id")) for row in rows],
            })

    payment_ids = [text(p.get("id") or p.get("payment_id")) for p in payments if text(p.get("id") or p.get("payment_id"))]
    confirmed_payment_duplicates = [pid for pid, count in Counter(payment_ids).items() if count > 1]
    return {
        "duplicate_confirmed_item_ids": confirmed_item_duplicates,
        "duplicate_confirmed_payment_ids": confirmed_payment_duplicates,
        "duplicate_confirmed_count": len(confirmed_item_duplicates) + len(confirmed_payment_duplicates),
        "duplicate_suspected_groups": suspected_groups,
        "duplicate_suspected_total": out(sum((dec(group["amount"]) for group in suspected_groups), Decimal("0"))),
    }


def collect_journal_refs(entry: Dict[str, Any]) -> List[str]:
    refs = [text(entry.get("reference_id") or entry.get("referenceId"))]
    desc = text(entry.get("description"))
    refs.extend(re.findall(r"\[VISIT:([^\]]+)\]", desc, flags=re.I))
    refs.extend(re.findall(r"\[PAYMENT:([^\]]+)\]", desc, flags=re.I))
    return [ref for ref in refs if ref]


def build_report() -> Dict[str, Any]:
    supa = SupabaseService()
    if supa.mock_mode:
        raise RuntimeError("Supabase mock mode is not allowed for this read-only audit")

    before_counts = {table: len(table_fetch_all(supa.client, table, "id")) for table in ("vehicles", "vehicle_visits", "operations", "journal_entries")}
    vehicles_rows = table_fetch_all(supa.client, "vehicles")
    visits_rows = table_fetch_all(supa.client, "vehicle_visits")
    operations_rows = table_fetch_all(supa.client, "operations")
    journal_rows = table_fetch_all(supa.client, "journal_entries")

    vehicles = {row_id(row): row for row in vehicles_rows if row_id(row)}
    active_vehicles = [row for row in vehicles_rows if row_id(row) and is_active_vehicle(row)]
    active_ids = {row_id(row) for row in active_vehicles}

    visits_by_vehicle: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    ops_by_vehicle: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    ops_by_visit: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    journals_by_ref: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    journals_by_id = {row_id(row): row for row in journal_rows if row_id(row)}

    for visit in visits_rows:
        visits_by_vehicle[text(visit.get("vehicle_id") or visit.get("vehicleId"))].append(visit)
    for op in operations_rows:
        vid = text(op.get("vehicle_id") or op.get("vehicleId"))
        visit_id = text(op.get("visit_id") or op.get("visitId"))
        ops_by_vehicle[vid].append(op)
        if visit_id:
            ops_by_visit[visit_id].append(op)
        if row_id(op):
            ops_by_visit[row_id(op)].append(op)
    for journal in journal_rows:
        for ref in collect_journal_refs(journal):
            journals_by_ref[ref].append(journal)

    rows: List[Dict[str, Any]] = []
    historical_excluded_rows: List[Dict[str, Any]] = []
    manual_review: List[Dict[str, Any]] = []

    for vehicle in sorted(active_vehicles, key=lambda row: text(row.get("entry_date") or row.get("created_at")), reverse=True):
        vehicle_id = row_id(vehicle)
        all_vehicle_visits = sorted(visits_by_vehicle.get(vehicle_id, []), key=lambda row: text(row.get("entry_date") or row.get("created_at")))
        in_scope_visits = []
        excluded_visits = []
        for visit in all_vehicle_visits:
            visit_status = norm(visit.get("status"))
            visit_date_source = visit.get("entry_date") or visit.get("created_at")
            if visit_status in VISIT_EXCLUDED_STATUSES:
                excluded_visits.append((visit, "visit_cancelled_or_deleted"))
            elif in_scope_date(visit_date_source):
                in_scope_visits.append(visit)
            else:
                excluded_visits.append((visit, "historical_excluded"))

        existing_summary = build_vehicle_summary(vehicle, all_vehicle_visits, ops_by_vehicle.get(vehicle_id, []), journal_rows)
        displayed_receivable = dec(existing_summary.get("display_remaining"))

        if not in_scope_visits:
            rows.append({
                "vehicle_id": vehicle_id,
                "customer": text(vehicle.get("customer_name") or vehicle.get("customerName")),
                "vehicle": " ".join([text(vehicle.get("brand")), text(vehicle.get("model")), text(vehicle.get("year"))]).strip() or "—",
                "plate": text(vehicle.get("plate_number") or vehicle.get("plateNumber")),
                "visit_id": "—",
                "visit_date": "—",
                "visit_status": "—",
                "services_current": [],
                "parts_current": [],
                "current_items_total": 0.0,
                "confirmed_payments": [],
                "confirmed_payments_total": 0.0,
                "unapplied_confirmed_payments": 0.0,
                "pending_payments_total": 0.0,
                "correct_remaining": 0.0,
                "displayed_receivable": out(displayed_receivable),
                "difference_current_minus_correct": out(displayed_receivable),
                "file_only_items": [],
                "missing_financial_links": [],
                "duplicate_confirmed": [],
                "duplicate_suspected": [],
                "classification": "historical_excluded",
                "final_judgment": "مركبة نشطة لكن لا توجد زيارة داخل نطاق 2026-07-05 إلى 2026-08-04؛ أي رصيد ظاهر يعود لنطاق قديم مستبعد من هذا التقرير.",
            })
            if displayed_receivable > 0:
                manual_review.append({"vehicle_id": vehicle_id, "reason": "رصيد ظاهر حالياً لكن لا توجد زيارة داخل نطاق آخر 30 يوماً المعتمد", "amount": out(displayed_receivable)})
            continue

        for visit in in_scope_visits:
            visit_id = row_id(visit)
            parsed_notes = parse_notes(visit.get("notes"))
            raw_items = [item for item in (parsed_notes.get("items") or []) if isinstance(item, dict)]
            eligible_items: List[Dict[str, Any]] = []
            excluded_items: List[Dict[str, Any]] = []
            services: List[Dict[str, Any]] = []
            parts: List[Dict[str, Any]] = []
            for item in raw_items:
                amount = item_amount(item)
                reason = ""
                if amount <= 0:
                    reason = "zero_or_negative"
                elif item_cancelled(item):
                    reason = "cancelled"
                elif item_is_internal_only(item):
                    reason = "purchase_supplier_only_or_internal_expense"
                if reason:
                    excluded_items.append({"item": item, "reason": reason})
                    continue
                item_class = classify_item(item)
                if item_class == "service":
                    services.append(item)
                elif item_class == "part_or_customer_charged_supplier_line":
                    parts.append(item)
                else:
                    excluded_items.append({"item": item, "reason": "unresolved_item_type"})
                    continue
                eligible_items.append(item)

            raw_payments = [payment for payment in (parsed_notes.get("payments") or []) if isinstance(payment, dict)]
            confirmed_payments = [payment for payment in raw_payments if payment_amount(payment) > 0 and not is_pending_payment(payment)]
            pending_payments = [payment for payment in raw_payments if payment_amount(payment) > 0 and is_pending_payment(payment)]
            note_journal_ids = {text(payment.get("journalEntryId") or payment.get("journal_entry_id")) for payment in confirmed_payments if text(payment.get("journalEntryId") or payment.get("journal_entry_id"))}

            visit_ops = list({row_id(op): op for op in ops_by_visit.get(visit_id, []) if row_id(op)}.values())
            ref_ids = {visit_id, *[row_id(op) for op in visit_ops if row_id(op)]}
            linked_journals = []
            seen_journal_ids = set()
            for ref in ref_ids:
                for journal in journals_by_ref.get(ref, []):
                    jid = row_id(journal)
                    if jid and jid not in seen_journal_ids:
                        seen_journal_ids.add(jid)
                        linked_journals.append(journal)

            journal_payment_total = Decimal("0")
            for journal in linked_journals:
                source = norm(journal.get("source"))
                if source in PAYMENT_SOURCES and row_id(journal) not in note_journal_ids:
                    journal_payment_total += dec(journal_payment_amount(journal))

            items_total = sum((item_amount(item) for item in eligible_items), Decimal("0"))
            notes_confirmed_total = sum((payment_amount(payment) for payment in confirmed_payments), Decimal("0"))
            confirmed_total = max(notes_confirmed_total, journal_payment_total)
            applied_total = min(items_total, confirmed_total)
            remaining = max(items_total - applied_total, Decimal("0"))
            unapplied = max(confirmed_total - items_total, Decimal("0"))
            pending_total = sum((payment_amount(payment) for payment in pending_payments), Decimal("0"))

            sale_journals = [journal for journal in linked_journals if norm(journal.get("transaction_type")) == "sale" or norm(journal.get("source")) == "operation"]
            has_operation_link = bool(visit_ops)
            has_sale_journal = any(journal_has_revenue_credit(journal) for journal in sale_journals)
            has_ar_sale_journal = any(journal_has_ar_debit(journal) and journal_has_revenue_credit(journal) for journal in sale_journals)

            missing_links: List[str] = []
            if items_total > 0 and not has_operation_link:
                missing_links.append("operation_id مفقود للزيارة")
            if items_total > 0 and not has_sale_journal:
                missing_links.append("قيد إيراد/بيع مفقود")
            if remaining > 0 and not has_ar_sale_journal:
                missing_links.append("قيد ذمة مدينة AR مفقود أو غير مثبت")
            for payment in confirmed_payments:
                jid = text(payment.get("journalEntryId") or payment.get("journal_entry_id"))
                if jid and jid not in journals_by_id:
                    missing_links.append(f"قيد دفعة مذكور في notes وغير موجود حالياً: {jid}")
                if payment.get("backendSyncPending") is True:
                    missing_links.append(f"دفعة مؤكدة/مدخلة في notes تحتاج ربط خلفي: {text(payment.get('id')) or money(payment_amount(payment))}")

            duplicates = duplicate_analysis(eligible_items, confirmed_payments)
            duplicate_confirmed = duplicates["duplicate_confirmed_item_ids"] + duplicates["duplicate_confirmed_payment_ids"]
            duplicate_suspected = duplicates["duplicate_suspected_groups"]

            if items_total <= 0:
                classification = "unresolved" if raw_items else "historical_excluded"
            elif duplicates["duplicate_confirmed_count"] > 0:
                classification = "duplicate_confirmed"
            elif remaining <= Decimal("0.00"):
                classification = "paid"
            elif confirmed_total > 0:
                classification = "partially_paid"
            elif missing_links:
                classification = "valid_receivable_missing_financial_links"
            else:
                classification = "valid_receivable"

            if remaining > 0 and missing_links:
                link_receivable_class = "valid_receivable_missing_financial_links"
            elif remaining > 0:
                link_receivable_class = "valid_receivable"
            else:
                link_receivable_class = classification

            if duplicate_suspected:
                manual_review.append({"vehicle_id": vehicle_id, "visit_id": visit_id, "reason": "تكرار محتمل في بنود الزيارة", "amount": duplicates["duplicate_suspected_total"]})
            if pending_total > 0:
                manual_review.append({"vehicle_id": vehicle_id, "visit_id": visit_id, "reason": "دفعات بانتظار التأكيد غير محسوبة", "amount": out(pending_total)})
            if unapplied > 0:
                manual_review.append({"vehicle_id": vehicle_id, "visit_id": visit_id, "reason": "دفعات مؤكدة زائدة/غير مطبقة", "amount": out(unapplied)})

            rows.append({
                "vehicle_id": vehicle_id,
                "customer": text(vehicle.get("customer_name") or vehicle.get("customerName")),
                "vehicle": " ".join([text(vehicle.get("brand")), text(vehicle.get("model")), text(vehicle.get("year"))]).strip() or "—",
                "plate": text(vehicle.get("plate_number") or vehicle.get("plateNumber")),
                "visit_id": visit_id,
                "visit_date": date_text(visit.get("entry_date") or visit.get("created_at")),
                "visit_status": text(visit.get("status")),
                "services_current": [compact_item(item) for item in services],
                "parts_current": [compact_item(item) for item in parts],
                "current_items_total": out(items_total),
                "confirmed_payments": [compact_payment(payment) for payment in confirmed_payments],
                "confirmed_payments_total": out(confirmed_total),
                "unapplied_confirmed_payments": out(unapplied),
                "pending_payments_total": out(pending_total),
                "correct_remaining": out(remaining),
                "displayed_receivable": out(displayed_receivable),
                "difference_current_minus_correct": out(displayed_receivable - remaining),
                "file_only_items": [compact_item(item) for item in eligible_items if not has_operation_link or not has_sale_journal],
                "missing_financial_links": sorted(set(missing_links)),
                "operation_ids": [row_id(op) for op in visit_ops if row_id(op)],
                "journal_entry_ids": [row_id(journal) for journal in linked_journals if row_id(journal)],
                "duplicate_confirmed": duplicate_confirmed,
                "duplicate_suspected": duplicate_suspected,
                "classification": classification,
                "receivable_link_classification": link_receivable_class,
                "final_judgment": (
                    "ذمة صحيحة مستحقة لكن روابطها المالية ناقصة/محذوفة" if remaining > 0 and missing_links else
                    "ذمة صحيحة مستحقة وروابطها المالية الأساسية موجودة" if remaining > 0 else
                    "البنود الحالية مغطاة بالكامل بدفعات مؤكدة" if items_total > 0 and remaining <= 0 else
                    "لا توجد بنود حالية مؤهلة داخل النطاق"
                ),
            })

        for visit, reason in excluded_visits:
            parsed_notes = parse_notes(visit.get("notes"))
            items = [item for item in (parsed_notes.get("items") or []) if isinstance(item, dict) and not item_cancelled(item) and not item_is_internal_only(item)]
            amount = sum((item_amount(item) for item in items), Decimal("0"))
            if amount > 0:
                historical_excluded_rows.append({
                    "vehicle_id": vehicle_id,
                    "visit_id": row_id(visit),
                    "visit_date": date_text(visit.get("entry_date") or visit.get("created_at")),
                    "customer": text(vehicle.get("customer_name") or vehicle.get("customerName")),
                    "amount": out(amount),
                    "reason": reason,
                })

    after_counts = {table: len(table_fetch_all(supa.client, table, "id")) for table in ("vehicles", "vehicle_visits", "operations", "journal_entries")}

    total_valid_receivable = sum((dec(row["correct_remaining"]) for row in rows if dec(row["correct_remaining"]) > 0), Decimal("0"))
    total_missing_links = sum((dec(row["correct_remaining"]) for row in rows if row.get("receivable_link_classification") == "valid_receivable_missing_financial_links"), Decimal("0"))
    paid_vehicle_ids = {row["vehicle_id"] for row in rows if dec(row["current_items_total"]) > 0 and dec(row["correct_remaining"]) <= 0}
    receivable_vehicle_ids = {row["vehicle_id"] for row in rows if dec(row["correct_remaining"]) > 0}
    paid_wrongly_shown = sum((dec(row["displayed_receivable"]) for row in rows if dec(row["current_items_total"]) > 0 and dec(row["correct_remaining"]) <= 0 and dec(row["displayed_receivable"]) > 0), Decimal("0"))
    duplicate_confirmed_total = Decimal("0")
    for row in rows:
        if row.get("duplicate_confirmed"):
            duplicate_confirmed_total += dec(row.get("current_items_total"))

    summary = {
        "active_vehicle_count": len(active_vehicles),
        "active_vehicle_status_counts": dict(Counter(text(row.get("status") or "NULL") for row in active_vehicles)),
        "vehicles_paid_count": len(paid_vehicle_ids),
        "vehicles_with_valid_receivables_count": len(receivable_vehicle_ids),
        "total_valid_receivables": out(total_valid_receivable),
        "total_valid_receivables_missing_financial_links": out(total_missing_links),
        "total_paid_items_wrongly_shown_as_receivables": out(paid_wrongly_shown),
        "total_duplicate_confirmed": out(duplicate_confirmed_total),
        "total_duplicate_suspected": out(sum((dec(group.get("amount")) for row in rows for group in row.get("duplicate_suspected", [])), Decimal("0"))),
        "total_unapplied_confirmed_payments": out(sum((dec(row.get("unapplied_confirmed_payments")) for row in rows), Decimal("0"))),
        "manual_review_count": len(manual_review),
        "historical_excluded_amount_for_active_vehicles": out(sum((dec(row.get("amount")) for row in historical_excluded_rows), Decimal("0"))),
    }

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "READ_ONLY",
        "read_only": True,
        "scope": {
            "timezone": "Asia/Riyadh",
            "start": START_RIYADH.isoformat(),
            "end": END_RIYADH.isoformat(),
            "active_vehicle_rule": "status not in delivered/archived/cancelled; NULL status treated as active because it appears in current active dashboard data",
            "source_of_truth": "active vehicle -> current visit -> current services/customer-charged parts -> confirmed payments",
        },
        "mutation_guard": {"before_counts": before_counts, "after_counts": after_counts, "unchanged": before_counts == after_counts},
        "summary": summary,
        "rows": rows,
        "historical_excluded_rows": historical_excluded_rows,
        "manual_review": manual_review,
    }


def render_markdown(report: Dict[str, Any]) -> str:
    summary = report["summary"]
    lines: List[str] = []
    lines.append("# ACTIVE_VEHICLES_CURRENT_RECEIVABLES_30_DAYS_READ_ONLY")
    lines.append("")
    lines.append(f"- generated_at: `{report['generated_at']}`")
    lines.append("- mode: **READ ONLY** — لم يتم حذف أو إنشاء أو تعديل أي سجل.")
    lines.append(f"- timezone: `{report['scope']['timezone']}`")
    lines.append("- النطاق الزمني المعتمد: `2026-07-05 00:00` إلى `2026-08-04 23:59:59` بتوقيت الرياض.")
    lines.append("- مصدر الحقيقة: **المركبة النشطة ← الزيارة الحالية ← الخدمات/القطع المحملة على العميل ← الدفعات المؤكدة**.")
    lines.append("- العمليات ودفتر اليومية ومتابعة الذمم استخدمت للمقارنة وكشف الروابط المفقودة فقط، وليس لنفي الذمة.")
    lines.append("")
    lines.append("## 1) حارس عدم التعديل")
    lines.append("")
    guard = report["mutation_guard"]
    lines.append(f"- قبل الفحص: `{guard['before_counts']}`")
    lines.append(f"- بعد الفحص: `{guard['after_counts']}`")
    lines.append(f"- النتيجة: **{'UNCHANGED' if guard['unchanged'] else 'CHANGED — تحقق فوراً'}**")
    lines.append("")
    lines.append("## 2) النتائج النهائية")
    lines.append("")
    lines.append("| المؤشر | النتيجة |")
    lines.append("|---|---:|")
    lines.append(f"| عدد المركبات النشطة | {summary['active_vehicle_count']} |")
    lines.append(f"| عدد المركبات المسددة داخل النطاق | {summary['vehicles_paid_count']} |")
    lines.append(f"| عدد المركبات ذات الذمم الصحيحة | {summary['vehicles_with_valid_receivables_count']} |")
    lines.append(f"| إجمالي الذمم الصحيحة | {money(summary['total_valid_receivables'])} |")
    lines.append(f"| إجمالي الذمم الصحيحة التي فقدت روابطها المالية بسبب الحذف/النقص | {money(summary['total_valid_receivables_missing_financial_links'])} |")
    lines.append(f"| إجمالي البنود المسددة التي تظهر خطأ كذمم | {money(summary['total_paid_items_wrongly_shown_as_receivables'])} |")
    lines.append(f"| إجمالي التكرارات المؤكدة | {money(summary['total_duplicate_confirmed'])} |")
    lines.append(f"| إجمالي التكرارات المحتملة | {money(summary['total_duplicate_suspected'])} |")
    lines.append(f"| إجمالي الدفعات المؤكدة غير المطبقة | {money(summary['total_unapplied_confirmed_payments'])} |")
    lines.append(f"| الحالات التي تحتاج مراجعة يدوية | {summary['manual_review_count']} |")
    lines.append("")
    lines.append("## 3) تفصيل كل مركبة نشطة")
    lines.append("")
    lines.append("| vehicle_id | العميل | المركبة/اللوحة | visit_id | تاريخ الزيارة | الخدمات الحالية | القطع/البنود المحملة | إجمالي البنود | الدفعات المؤكدة | الدفعات غير المطبقة | المتبقي الصحيح | الذمة المعروضة حالياً | الفرق | البنود في ملف المركبة فقط | الروابط المالية المفقودة | التكرارات | الحكم النهائي |")
    lines.append("|---|---|---|---|---:|---|---|---:|---:|---:|---:|---:|---:|---|---|---|---|")
    for row in report["rows"]:
        services = unique_join(row.get("services_current") or [], 3)
        parts = unique_join(row.get("parts_current") or [], 3)
        payments = unique_join(row.get("confirmed_payments") or [], 3)
        file_only = unique_join(row.get("file_only_items") or [], 3)
        missing = unique_join(row.get("missing_financial_links") or [], 3)
        duplicates = "—"
        if row.get("duplicate_confirmed"):
            duplicates = "مؤكد: " + unique_join(row.get("duplicate_confirmed"), 2)
        if row.get("duplicate_suspected"):
            suspected = "; ".join(f"محتمل {group['count']}× {money(group['amount'])}" for group in row.get("duplicate_suspected", [])[:2])
            duplicates = suspected if duplicates == "—" else f"{duplicates}; {suspected}"
        vehicle_label = f"{row.get('vehicle') or '—'} / {row.get('plate') or '—'}"
        lines.append(
            "| "
            + " | ".join([
                f"`{row['vehicle_id']}`",
                row.get("customer") or "—",
                vehicle_label,
                f"`{row.get('visit_id') or '—'}`",
                row.get("visit_date") or "—",
                services,
                parts,
                money(row.get("current_items_total")),
                f"{money(row.get('confirmed_payments_total'))}<br>{payments}",
                money(row.get("unapplied_confirmed_payments")),
                money(row.get("correct_remaining")),
                money(row.get("displayed_receivable")),
                money(row.get("difference_current_minus_correct")),
                file_only,
                missing,
                duplicates,
                f"{row.get('classification')}<br>{row.get('final_judgment')}",
            ])
            + " |"
        )
    lines.append("")
    lines.append("## 4) بنود تاريخية مستبعدة من المركبات النشطة")
    lines.append("")
    lines.append(f"- إجمالي بنود زيارات قديمة/خارج النطاق داخل مركبات نشطة: **{money(summary['historical_excluded_amount_for_active_vehicles'])}**")
    lines.append("- هذه البنود لم تدخل في الذمة الصحيحة الحالية لأنها خارج آخر 30 يوماً المعتمدة أو زيارة ملغاة/قديمة.")
    if report.get("historical_excluded_rows"):
        lines.append("")
        lines.append("| vehicle_id | العميل | visit_id | تاريخ الزيارة | المبلغ | السبب |")
        lines.append("|---|---|---|---:|---:|---|")
        for row in report["historical_excluded_rows"][:50]:
            lines.append(f"| `{row['vehicle_id']}` | {row['customer']} | `{row['visit_id']}` | {row['visit_date']} | {money(row['amount'])} | {row['reason']} |")
    lines.append("")
    lines.append("## 5) الحالات التي تحتاج مراجعة يدوية")
    lines.append("")
    if report.get("manual_review"):
        lines.append("| vehicle_id | visit_id | السبب | المبلغ |")
        lines.append("|---|---|---|---:|")
        for row in report["manual_review"]:
            lines.append(f"| `{row.get('vehicle_id')}` | `{row.get('visit_id') or '—'}` | {row.get('reason')} | {money(row.get('amount'))} |")
    else:
        lines.append("- لا توجد حالات مراجعة يدوية ضمن قواعد هذا التقرير.")
    lines.append("")
    lines.append("## 6) الاستنتاج")
    lines.append("")
    lines.append("- لا يتم استبعاد أي بند مؤهل لمجرد غياب `operation_id` أو `journal_entry_id`.")
    lines.append("- البنود المؤهلة داخل ملفات المركبات النشطة خلال النطاق تُعد ذمة صحيحة إذا لم تُغطَّ بدفعات مؤكدة.")
    lines.append("- الروابط المالية المفقودة تعني أن السجل المالي في العمليات/القيود ناقص، وليس أن الذمة غير موجودة.")
    lines.append("- لم يتم إنشاء قيد افتتاحي، ولم يتم حذف أو تعديل أي سجل، ولم يتم تشغيل keep-debts-only.")
    lines.append("")
    lines.append("## 7) ملف JSON التفصيلي")
    lines.append("")
    lines.append(f"- `{JSON_PATH}`")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    report = build_report()
    JSON_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({"report": str(REPORT_PATH), "json": str(JSON_PATH), "summary": report["summary"], "mutation_guard": report["mutation_guard"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()