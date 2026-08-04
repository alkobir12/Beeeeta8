from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from core.unified_financial_engine import build_current_ar_snapshot, parse_notes  # noqa: E402
from financial_reconciliation import journal_lines, table_fetch_all  # noqa: E402
from supabase_service import SupabaseService  # noqa: E402

OUTPUT_JSON = ROOT / "test_reports" / "financial_engine_readiness_audit.json"
OUTPUT_MD = ROOT / "memory" / "FINANCIAL_ENGINE_READINESS_AUDIT.md"
AR_CODES = {"005", "1103", "113"}
SALE_SOURCES = {"active_vehicle_ar_repair", "hist_vehicle_ar_repair", "operation", "visit_sale", "manual_receivable_repair"}
PAYMENT_SOURCES = {"unified_visit_payment", "operation_payment", "payment", "visit_receipt_voucher", "operation_discount", "visit_discount"}
HIDDEN_STATUSES = {"delivered", "archived", "cancelled", "canceled", "ملغي", "ملغى", "مؤرشف", "مسلم", "تم التسليم"}


def dec(value: Any) -> Decimal:
    try:
        return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        return Decimal("0.00")


def money(value: Any) -> str:
    return f"{dec(value):,.2f}"


def text(value: Any) -> str:
    return str(value or "").strip()


def item_amount(item: Dict[str, Any]) -> Decimal:
    if item.get("total") is not None:
        return dec(item.get("total"))
    return dec(item.get("price")) * dec(item.get("quantity") or item.get("qty") or 1)


def include_item(item: Dict[str, Any]) -> bool:
    if not isinstance(item, dict):
        return False
    status = text(item.get("status")).lower()
    if item.get("cancelled") or item.get("deleted") or status in {"cancelled", "canceled", "deleted", "void", "ملغي", "ملغى"}:
        return False
    if item.get("chargedToCustomer") is False or item.get("customer_charge") is False:
        return False
    if item.get("internalOnly") is True or item.get("workshopExpense") is True:
        return False
    return item_amount(item) > 0


def is_pending_payment(payment: Dict[str, Any]) -> bool:
    status = text(payment.get("status") or payment.get("paymentStatus") or payment.get("payment_status")).lower()
    return payment.get("confirmed") is False or status in {"pending", "pending_confirmation", "awaiting_confirmation", "unconfirmed", "بانتظار التأكيد", "بانتظار_التأكيد"}


def payment_amount(payment: Dict[str, Any]) -> Decimal:
    return dec(payment.get("amount"))


def visit_date(row: Dict[str, Any]) -> str:
    return text(row.get("entry_date") or row.get("created_at"))[:10]


def extract_vehicle_id(entry: Dict[str, Any]) -> str:
    desc = text(entry.get("description"))
    match = re.search(r"\[VEHICLE:([^\]]+)\]", desc)
    return match.group(1).strip() if match else ""


def extract_visit_id(entry: Dict[str, Any]) -> str:
    desc = text(entry.get("description"))
    match = re.search(r"\[VISIT:([^\]]+)\]", desc)
    return match.group(1).strip() if match else text(entry.get("reference_id"))


def journal_ar_delta(entry: Dict[str, Any]) -> Decimal:
    delta = Decimal("0.00")
    for line in journal_lines(entry):
        code = text(line.get("account") or line.get("code") or line.get("account_code"))
        if code in AR_CODES:
            delta += dec(line.get("debit")) - dec(line.get("credit"))
    return delta


def main() -> None:
    supa = SupabaseService()
    if supa.mock_mode:
        raise RuntimeError("Readiness audit requires real DB")

    vehicles = table_fetch_all(supa.client, "vehicles")
    visits = table_fetch_all(supa.client, "vehicle_visits")
    operations = table_fetch_all(supa.client, "operations")
    journals = table_fetch_all(supa.client, "journal_entries")
    snapshot = build_current_ar_snapshot(supa.client, "finmodule-sync")

    visits_by_vehicle: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for visit in visits:
        visits_by_vehicle[text(visit.get("vehicle_id"))].append(visit)

    journal_delta_by_vehicle: Dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    journal_delta_by_visit: Dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    journal_count_by_vehicle: Dict[str, int] = defaultdict(int)
    for entry in journals:
        delta = journal_ar_delta(entry)
        if abs(delta) < Decimal("0.01"):
            continue
        vehicle_id = extract_vehicle_id(entry)
        visit_id = extract_visit_id(entry)
        if vehicle_id:
            journal_delta_by_vehicle[vehicle_id] += delta
            journal_count_by_vehicle[vehicle_id] += 1
        if visit_id:
            journal_delta_by_visit[visit_id] += delta

    rows = []
    abnormal_statuses = []
    for vehicle in vehicles:
        vehicle_id = text(vehicle.get("id"))
        raw_status = vehicle.get("status")
        status = text(raw_status).lower()
        if raw_status is None or text(raw_status) == "تشخيص":
            abnormal_statuses.append({"vehicle_id": vehicle_id, "customer": vehicle.get("customer_name"), "plate": vehicle.get("plate_number"), "status": "NULL" if raw_status is None else text(raw_status)})
        if status in HIDDEN_STATUSES:
            continue
        file_items = Decimal("0.00")
        notes_paid = Decimal("0.00")
        pending = Decimal("0.00")
        visit_ids = []
        for visit in visits_by_vehicle.get(vehicle_id, []):
            visit_ids.append(text(visit.get("id")))
            parsed = parse_notes(visit.get("notes"))
            for item in parsed.get("items") or []:
                if include_item(item):
                    file_items += item_amount(item)
            for payment in parsed.get("payments") or []:
                if not isinstance(payment, dict):
                    continue
                amount = payment_amount(payment)
                if amount <= 0:
                    continue
                if is_pending_payment(payment):
                    pending += amount
                else:
                    notes_paid += amount
        file_remaining = max(file_items - notes_paid, Decimal("0.00"))
        journal_ar = journal_delta_by_vehicle.get(vehicle_id, Decimal("0.00"))
        diff = journal_ar - file_remaining
        classification = "matched" if abs(diff) < Decimal("0.01") else "mismatch"
        if file_remaining > 0 and journal_ar <= 0:
            classification = "missing_journal_links"
        elif file_remaining == 0 and abs(journal_ar) > Decimal("0.01"):
            classification = "journal_without_file_balance"
        rows.append({
            "vehicle_id": vehicle_id,
            "customer": vehicle.get("customer_name"),
            "plate": vehicle.get("plate_number"),
            "status": vehicle.get("status"),
            "visit_ids": visit_ids,
            "file_items_total": float(file_items),
            "confirmed_notes_paid": float(notes_paid),
            "pending_payments": float(pending),
            "file_remaining": float(file_remaining),
            "journal_ar_balance": float(journal_ar),
            "difference_journal_minus_file": float(diff),
            "journal_entry_count": journal_count_by_vehicle.get(vehicle_id, 0),
            "classification": classification,
        })

    total_file_remaining = sum((dec(row["file_remaining"]) for row in rows), Decimal("0.00"))
    total_journal_vehicle = sum((dec(row["journal_ar_balance"]) for row in rows), Decimal("0.00"))
    journal_ar_total = sum((journal_ar_delta(entry) for entry in journals), Decimal("0.00"))
    mismatches = [row for row in rows if row["classification"] != "matched"]
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "engine_version": snapshot.get("engine_version"),
        "counts": {
            "vehicles": len(vehicles),
            "vehicle_visits": len(visits),
            "operations": len(operations),
            "journal_entries": len(journals),
            "dashboard_active_vehicles": len(rows),
        },
        "status_counts": dict(Counter(text(row.get("status")) for row in vehicles)),
        "totals": {
            "vehicle_file_remaining_total": float(total_file_remaining),
            "ar_customers_total": float(dec(snapshot.get("total_ar"))),
            "journal_ar_total_all_entries": float(journal_ar_total),
            "journal_ar_total_with_vehicle_tags": float(total_journal_vehicle),
            "difference_ar_customers_minus_vehicle_file": float(dec(snapshot.get("total_ar")) - total_file_remaining),
            "difference_journal_vehicle_minus_file": float(total_journal_vehicle - total_file_remaining),
        },
        "mismatch_count": len(mismatches),
        "abnormal_status_count": len(abnormal_statuses),
        "abnormal_statuses": abnormal_statuses,
        "rows": rows,
        "mismatches": mismatches,
    }
    OUTPUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    render(result)
    print(json.dumps({"report": str(OUTPUT_MD), "totals": result["totals"], "mismatch_count": len(mismatches), "abnormal_status_count": len(abnormal_statuses)}, ensure_ascii=False, indent=2))


def render(result: Dict[str, Any]) -> None:
    totals = result["totals"]
    lines = [
        "# FINANCIAL_ENGINE_READINESS_AUDIT",
        "",
        f"- generated_at: `{result['generated_at']}`",
        "- mode: **READ ONLY** — مقارنة فقط بدون تعديل بيانات.",
        f"- engine_version: `{result['engine_version']}`",
        "",
        "## 1) ملخص الجاهزية",
        "",
        "| المؤشر | النتيجة |",
        "|---|---:|",
        f"| مركبات نشطة/ظاهرة بعد استبعاد delivered/archived | {result['counts']['dashboard_active_vehicles']} |",
        f"| إجمالي المتبقي من ملفات المركبات | {money(totals['vehicle_file_remaining_total'])} |",
        f"| إجمالي AR Customers من المحرك الموحد | {money(totals['ar_customers_total'])} |",
        f"| الفرق AR Customers - ملف المركبة | {money(totals['difference_ar_customers_minus_vehicle_file'])} |",
        f"| إجمالي AR من قيود تحمل VEHICLE tags | {money(totals['journal_ar_total_with_vehicle_tags'])} |",
        f"| الفرق قيود VEHICLE - ملف المركبة | {money(totals['difference_journal_vehicle_minus_file'])} |",
        f"| إجمالي AR من كل القيود | {money(totals['journal_ar_total_all_entries'])} |",
        f"| عدد فروقات المركبات | {result['mismatch_count']} |",
        f"| حالات غير معيارية | {result['abnormal_status_count']} |",
        "",
        "## 2) الفروقات حسب المركبة",
        "",
        "| العميل | اللوحة | الحالة | ملف المركبة: بنود | دفعات مؤكدة | متبقي الملف | رصيد القيود | الفرق | الحكم |",
        "|---|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in result["mismatches"]:
        lines.append(
            f"| {row['customer']} | {row['plate']} | {row['status']} | {money(row['file_items_total'])} | {money(row['confirmed_notes_paid'])} | {money(row['file_remaining'])} | {money(row['journal_ar_balance'])} | {money(row['difference_journal_minus_file'])} | {row['classification']} |"
        )
    if not result["mismatches"]:
        lines.append("| — | — | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | matched |")
    lines.extend(["", "## 3) الحالات غير الطبيعية", ""])
    if result["abnormal_statuses"]:
        lines.extend(["| العميل | اللوحة | vehicle_id | الحالة |", "|---|---|---|---|"])
        for row in result["abnormal_statuses"]:
            lines.append(f"| {row['customer']} | {row['plate']} | `{row['vehicle_id']}` | {row['status']} |")
    else:
        lines.append("- لا توجد حالات NULL أو حالة عربية غير معيارية.")
    lines.extend(["", "## 4) ملف JSON", "", f"- `{OUTPUT_JSON}`", ""])
    OUTPUT_MD.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()