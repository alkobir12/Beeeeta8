from __future__ import annotations

import argparse
import json
import sys
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from core.accounting_engine import get_engine  # noqa: E402
from financial_reconciliation import table_fetch_all  # noqa: E402
from supabase_service import SupabaseService  # noqa: E402


SOURCE = "active_vehicle_ar_repair"
WORKSHOP_ID = "finmodule-sync"
REPORT_JSON = ROOT / "test_reports" / "active_vehicles_current_receivables_30_days_read_only.json"
OUTPUT_JSON = ROOT / "test_reports" / "active_vehicle_receivable_journals_post_result.json"
OUTPUT_MD = ROOT / "memory" / "ACTIVE_VEHICLE_RECEIVABLE_JOURNALS_POST_RESULT.md"

CENT = Decimal("0.01")
REVENUE_NAMES = {
    "026": "إيرادات خدمات ميكانيكية",
    "027": "إيرادات إصلاح محركات",
    "041": "ايراد قطع الورشه",
}


def dec(value: Any) -> Decimal:
    return Decimal(str(value or 0)).quantize(CENT, rounding=ROUND_HALF_UP)


def money(value: Any) -> str:
    return f"{dec(value):,.2f}"


def text(value: Any) -> str:
    return str(value or "").strip()


def revenue_code_for_label(label: str, *, is_part: bool) -> str:
    label = text(label)
    if is_part:
        return "041"
    engine_keywords = ("توضيب", "مكين", "مكينة", "راس", "رأس", "تربو", "تربوا")
    if any(keyword in label for keyword in engine_keywords):
        return "027"
    return "026"


def parse_compact_amount(label: str) -> Decimal:
    # compact format: name ×qty = 1,234.00
    if "=" not in label:
        return Decimal("0.00")
    return dec(label.rsplit("=", 1)[-1].replace(",", ""))


def allocate_remaining(row: Dict[str, Any]) -> List[Dict[str, Any]]:
    remaining = dec(row.get("correct_remaining"))
    if remaining <= 0:
        return []
    buckets: Dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    for label in row.get("services_current") or []:
        buckets[revenue_code_for_label(label, is_part=False)] += parse_compact_amount(label)
    for label in row.get("parts_current") or []:
        buckets[revenue_code_for_label(label, is_part=True)] += parse_compact_amount(label)
    total = sum(buckets.values(), Decimal("0.00"))
    if total <= 0:
        return [{"account": "026", "account_name": REVENUE_NAMES["026"], "amount": remaining}]

    allocations: List[Tuple[str, Decimal]] = []
    assigned = Decimal("0.00")
    codes = sorted(buckets.keys())
    for index, code in enumerate(codes):
        if index == len(codes) - 1:
            amount = remaining - assigned
        else:
            amount = (remaining * buckets[code] / total).quantize(CENT, rounding=ROUND_HALF_UP)
            assigned += amount
        if amount > 0:
            allocations.append((code, amount))
    return [{"account": code, "account_name": REVENUE_NAMES.get(code, code), "amount": amount} for code, amount in allocations]


def build_entry(row: Dict[str, Any]) -> Dict[str, Any]:
    amount = dec(row.get("correct_remaining"))
    credits = allocate_remaining(row)
    lines: List[Dict[str, Any]] = [
        {"account": "005", "account_name": "العملاء (ذمم مدينة)", "debit": float(amount), "credit": 0.0}
    ]
    for credit in credits:
        lines.append({
            "account": credit["account"],
            "account_name": credit["account_name"],
            "debit": 0.0,
            "credit": float(credit["amount"]),
        })
    return {
        "id": str(uuid.uuid4()),
        "workshop_id": WORKSHOP_ID,
        "date": datetime.now(timezone.utc).isoformat(),
        "description": f"[إصلاح روابط ذمم المركبات النشطة] {row.get('customer')} / {row.get('plate')} [VISIT:{row.get('visit_id')}] [VEHICLE:{row.get('vehicle_id')}]",
        "lines": lines,
        "total": float(amount),
        "source": SOURCE,
        "transaction_type": "sale",
        "reference_id": row.get("visit_id"),
        "party_label": row.get("customer"),
    }


def existing_repair_refs(journals: List[Dict[str, Any]]) -> set[str]:
    return {text(row.get("reference_id")) for row in journals if text(row.get("source")) == SOURCE and text(row.get("reference_id"))}


def run(commit: bool) -> Dict[str, Any]:
    source_report = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
    candidates = [row for row in source_report["rows"] if dec(row.get("correct_remaining")) > 0]

    supa = SupabaseService()
    before_counts = {table: len(table_fetch_all(supa.client, table, "id")) for table in ("vehicles", "vehicle_visits", "operations", "journal_entries")}
    journals = table_fetch_all(supa.client, "journal_entries")
    already = existing_repair_refs(journals)

    engine = get_engine()
    rows_out = []
    posted_total = Decimal("0.00")
    for row in candidates:
        visit_id = text(row.get("visit_id"))
        amount = dec(row.get("correct_remaining"))
        entry = build_entry(row)
        if visit_id in already:
            rows_out.append({"visit_id": visit_id, "vehicle_id": row.get("vehicle_id"), "customer": row.get("customer"), "amount": float(amount), "status": "skipped_existing_repair"})
            continue
        if not commit:
            rows_out.append({"visit_id": visit_id, "vehicle_id": row.get("vehicle_id"), "customer": row.get("customer"), "amount": float(amount), "status": "dry_run", "entry": entry})
            posted_total += amount
            continue
        result = engine.post_entry(entry, fallback=False)
        journal_id = None
        status = "posted"
        if result and isinstance(result, list):
            journal_id = result[0].get("id")
            posted_total += amount
        else:
            status = "failed"
        rows_out.append({"visit_id": visit_id, "vehicle_id": row.get("vehicle_id"), "customer": row.get("customer"), "amount": float(amount), "status": status, "journal_id": journal_id, "entry": entry})

    after_counts = {table: len(table_fetch_all(supa.client, table, "id")) for table in ("vehicles", "vehicle_visits", "operations", "journal_entries")}
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "COMMIT" if commit else "DRY_RUN",
        "source": SOURCE,
        "before_counts": before_counts,
        "after_counts": after_counts,
        "journal_entries_delta": after_counts["journal_entries"] - before_counts["journal_entries"],
        "candidate_count": len(candidates),
        "rows": rows_out,
        "total_considered": float(sum((dec(row.get("correct_remaining")) for row in candidates), Decimal("0.00"))),
        "total_posted_or_planned": float(posted_total),
    }
    OUTPUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    render_markdown(result)
    return result


def render_markdown(result: Dict[str, Any]) -> None:
    lines = [
        "# ACTIVE_VEHICLE_RECEIVABLE_JOURNALS_POST_RESULT",
        "",
        f"- generated_at: `{result['generated_at']}`",
        f"- mode: **{result['mode']}**",
        f"- source: `{SOURCE}`",
        f"- before_counts: `{result['before_counts']}`",
        f"- after_counts: `{result['after_counts']}`",
        f"- journal_entries_delta: **{result['journal_entries_delta']}**",
        "",
        "| العميل | vehicle_id | visit_id | المبلغ | الحالة | journal_id |",
        "|---|---|---|---:|---|---|",
    ]
    for row in result["rows"]:
        lines.append(f"| {row.get('customer')} | `{row.get('vehicle_id')}` | `{row.get('visit_id')}` | {money(row.get('amount'))} | {row.get('status')} | `{row.get('journal_id') or '—'}` |")
    lines.extend(["", f"- total_posted_or_planned: **{money(result['total_posted_or_planned'])}**"])
    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit", action="store_true")
    args = parser.parse_args()
    result = run(commit=args.commit)
    print(json.dumps({k: result[k] for k in ("mode", "candidate_count", "journal_entries_delta", "total_posted_or_planned", "before_counts", "after_counts")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()