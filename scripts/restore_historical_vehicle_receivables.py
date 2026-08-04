from __future__ import annotations

import argparse
import json
import sys
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from core.accounting_engine import get_engine  # noqa: E402
from core.unified_financial_engine import parse_notes  # noqa: E402
from financial_reconciliation import table_fetch_all  # noqa: E402
from supabase_service import SupabaseService  # noqa: E402

SOURCE = "hist_vehicle_ar_repair"
WORKSHOP_ID = "finmodule-sync"
OUTPUT_JSON = ROOT / "test_reports" / "historical_vehicle_receivables_restore_result.json"
OUTPUT_MD = ROOT / "memory" / "HISTORICAL_VEHICLE_RECEIVABLES_RESTORE_RESULT.md"
CENT = Decimal("0.01")


def dec(value: Any) -> Decimal:
    return Decimal(str(value or 0)).quantize(CENT, rounding=ROUND_HALF_UP)


def money(value: Any) -> str:
    return f"{dec(value):,.2f}"


def text(value: Any) -> str:
    return str(value or "").strip()


def item_amount(item: Dict[str, Any]) -> Decimal:
    if item.get("total") is not None:
        return dec(item.get("total"))
    return dec(item.get("price")) * dec(item.get("quantity") or item.get("qty") or 1)


def include_item(item: Dict[str, Any]) -> bool:
    status = text(item.get("status")).lower()
    if item.get("cancelled") or item.get("deleted") or status in {"cancelled", "canceled", "deleted", "void", "ملغي", "ملغى"}:
        return False
    if item.get("chargedToCustomer") is False or item.get("customer_charge") is False:
        return False
    if item.get("internalOnly") is True or item.get("workshopExpense") is True:
        return False
    return item_amount(item) > 0


def visit_date(row: Dict[str, Any]) -> str:
    return text(row.get("entry_date") or row.get("created_at"))[:10]


def in_current_window(date_value: str) -> bool:
    return "2026-07-05" <= date_value <= "2026-08-04"


def revenue_code(item: Dict[str, Any]) -> str:
    raw_type = text(item.get("itemType") or item.get("type")).lower()
    billing = text(item.get("billingType") or item.get("billing_type")).lower()
    name = text(item.get("name"))
    if raw_type in {"part", "supplier"} or billing == "supplier":
        return "041"
    if any(word in name for word in ("توضيب", "مكين", "مكينة", "راس", "رأس", "تربو", "تربوا")):
        return "027"
    return "026"


def build_entry(candidate: Dict[str, Any]) -> Dict[str, Any]:
    total = dec(candidate["amount"])
    buckets: Dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    for item in candidate["items"]:
        buckets[revenue_code(item)] += item_amount(item)
    lines = [{"account": "005", "account_name": "العملاء (ذمم مدينة)", "debit": float(total), "credit": 0.0}]
    assigned = Decimal("0.00")
    codes = sorted(buckets.keys()) or ["026"]
    for index, code in enumerate(codes):
        amount = total - assigned if index == len(codes) - 1 else (total * buckets[code] / sum(buckets.values())).quantize(CENT, rounding=ROUND_HALF_UP)
        assigned += amount
        if amount > 0:
            account_name = {"026": "إيرادات خدمات ميكانيكية", "027": "إيرادات إصلاح محركات", "041": "ايراد قطع الورشه"}.get(code, code)
            lines.append({"account": code, "account_name": account_name, "debit": 0.0, "credit": float(amount)})
    return {
        "id": str(uuid.uuid4()),
        "workshop_id": WORKSHOP_ID,
        "date": datetime.now(timezone.utc).isoformat(),
        "description": f"[استرجاع بنود تاريخية من ملف المركبة] {candidate['customer']} / {candidate['plate']} [VISIT:{candidate['visit_id']}] [VEHICLE:{candidate['vehicle_id']}]",
        "lines": lines,
        "total": float(total),
        "source": SOURCE,
        "transaction_type": "sale",
        "reference_id": candidate["visit_id"],
        "party_label": candidate["customer"],
    }


def existing_refs(journals: List[Dict[str, Any]]) -> set[str]:
    sources = {SOURCE, "active_vehicle_ar_repair"}
    return {text(row.get("reference_id")) for row in journals if text(row.get("source")) in sources and text(row.get("reference_id"))}


def collect_candidates() -> Dict[str, Any]:
    supa = SupabaseService()
    vehicles = table_fetch_all(supa.client, "vehicles")
    visits = table_fetch_all(supa.client, "vehicle_visits")
    by_vehicle: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for visit in visits:
        by_vehicle[text(visit.get("vehicle_id"))].append(visit)
    candidates = []
    excluded_delivered = []
    for vehicle in vehicles:
        status = vehicle.get("status")
        status_text = text(status) if status is not None else "NULL"
        if status_text == "delivered":
            target_list = excluded_delivered
        else:
            target_list = candidates
        for visit in by_vehicle.get(text(vehicle.get("id")), []):
            date = visit_date(visit)
            if in_current_window(date):
                continue
            notes = parse_notes(visit.get("notes"))
            items = [item for item in notes.get("items") or [] if isinstance(item, dict) and include_item(item)]
            amount = sum((item_amount(item) for item in items), Decimal("0.00"))
            if amount <= 0:
                continue
            row = {
                "vehicle_id": vehicle.get("id"),
                "visit_id": visit.get("id"),
                "customer": vehicle.get("customer_name"),
                "plate": vehicle.get("plate_number"),
                "status": status_text,
                "visit_date": date,
                "amount": float(amount),
                "items": items,
            }
            target_list.append(row)
    # Requested scope: restore historical receivables for currently non-delivered dashboard vehicles.
    return {"candidates": candidates, "excluded_delivered": excluded_delivered}


def run(commit: bool) -> Dict[str, Any]:
    supa = SupabaseService()
    before_counts = {table: len(table_fetch_all(supa.client, table, "id")) for table in ("vehicles", "vehicle_visits", "journal_entries")}
    journals = table_fetch_all(supa.client, "journal_entries")
    refs = existing_refs(journals)
    collected = collect_candidates()
    engine = get_engine()
    rows = []
    total = Decimal("0.00")
    for candidate in collected["candidates"]:
        if text(candidate["visit_id"]) in refs:
            rows.append({**candidate, "status_result": "skipped_existing_journal"})
            continue
        entry = build_entry(candidate)
        amount = dec(candidate["amount"])
        if commit:
            posted = engine.post_entry(entry, fallback=False)
            journal_id = posted[0].get("id") if posted and isinstance(posted, list) else None
            rows.append({**candidate, "status_result": "posted" if journal_id else "failed", "journal_id": journal_id})
            if journal_id:
                total += amount
        else:
            rows.append({**candidate, "status_result": "dry_run", "entry": entry})
            total += amount
    after_counts = {table: len(table_fetch_all(supa.client, table, "id")) for table in ("vehicles", "vehicle_visits", "journal_entries")}
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "COMMIT" if commit else "DRY_RUN",
        "source": SOURCE,
        "before_counts": before_counts,
        "after_counts": after_counts,
        "journal_entries_delta": after_counts["journal_entries"] - before_counts["journal_entries"],
        "posted_or_planned_total": float(total),
        "rows": rows,
        "excluded_delivered": collected["excluded_delivered"],
    }
    OUTPUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    render(result)
    return result


def render(result: Dict[str, Any]) -> None:
    lines = [
        "# HISTORICAL_VEHICLE_RECEIVABLES_RESTORE_RESULT",
        "",
        f"- generated_at: `{result['generated_at']}`",
        f"- mode: **{result['mode']}**",
        f"- source: `{SOURCE}`",
        f"- journal_entries_delta: **{result['journal_entries_delta']}**",
        f"- posted_or_planned_total: **{money(result['posted_or_planned_total'])}**",
        "",
        "## البنود المسترجعة / المرشحة",
        "",
        "| العميل | اللوحة | الحالة | visit_id | تاريخ الزيارة | المبلغ | النتيجة | journal_id |",
        "|---|---|---|---|---:|---:|---|---|",
    ]
    for row in result["rows"]:
        lines.append(f"| {row['customer']} | {row['plate']} | {row['status']} | `{row['visit_id']}` | {row['visit_date']} | {money(row['amount'])} | {row['status_result']} | `{row.get('journal_id') or '—'}` |")
    lines.extend(["", "## بنود تاريخية مستبعدة لأنها لم تعد ضمن لوحة المركبات النشطة", ""])
    if result.get("excluded_delivered"):
        lines.extend(["| العميل | اللوحة | الحالة | visit_id | تاريخ الزيارة | المبلغ |", "|---|---|---|---|---:|---:|"])
        for row in result["excluded_delivered"]:
            lines.append(f"| {row['customer']} | {row['plate']} | {row['status']} | `{row['visit_id']}` | {row['visit_date']} | {money(row['amount'])} |")
    else:
        lines.append("- لا توجد.")
    lines.extend(["", "## ملف JSON", "", f"- `{OUTPUT_JSON}`", ""])
    OUTPUT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit", action="store_true")
    args = parser.parse_args()
    result = run(args.commit)
    print(json.dumps({"mode": result["mode"], "journal_entries_delta": result["journal_entries_delta"], "posted_or_planned_total": result["posted_or_planned_total"], "rows": len(result["rows"]), "excluded_delivered": len(result["excluded_delivered"])}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()