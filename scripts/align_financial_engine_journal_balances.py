from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from core.accounting_engine import get_engine  # noqa: E402
from financial_reconciliation import table_fetch_all  # noqa: E402
from supabase_service import SupabaseService  # noqa: E402

AUDIT_JSON = ROOT / "test_reports" / "financial_engine_readiness_audit.json"
OUTPUT_JSON = ROOT / "test_reports" / "financial_engine_journal_alignment_result.json"
OUTPUT_MD = ROOT / "memory" / "FINANCIAL_ENGINE_JOURNAL_ALIGNMENT_RESULT.md"
SOURCE = "fin_engine_align_v1"
WORKSHOP_ID = "finmodule-sync"


def dec(value: Any) -> Decimal:
    try:
        return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        return Decimal("0.00")


def money(value: Any) -> str:
    return f"{dec(value):,.2f}"


def text(value: Any) -> str:
    return str(value or "").strip()


def existing_refs(journals: List[Dict[str, Any]]) -> set[str]:
    return {text(row.get("reference_id")) for row in journals if text(row.get("source")) == SOURCE and text(row.get("reference_id"))}


def latest_visit_id(row: Dict[str, Any]) -> str:
    visits = [text(value) for value in row.get("visit_ids") or [] if text(value)]
    return visits[-1] if visits else text(row.get("vehicle_id"))


def build_entry(row: Dict[str, Any]) -> Dict[str, Any]:
    diff = dec(row.get("difference_journal_minus_file"))
    vehicle_id = text(row.get("vehicle_id"))
    visit_id = latest_visit_id(row)
    customer = text(row.get("customer")) or "عميل"
    plate = text(row.get("plate"))

    if diff < 0:
        amount = abs(diff)
        lines = [
            {"account": "005", "account_name": "العملاء (ذمم مدينة)", "debit": float(amount), "credit": 0.0},
            {"account": "026", "account_name": "إيرادات خدمات ميكانيكية", "debit": 0.0, "credit": float(amount)},
        ]
        tx_type = "sale"
        description = f"[محاذاة المحرك المالي: استكمال ذمة ناقصة] {customer} / {plate} [VISIT:{visit_id}] [VEHICLE:{vehicle_id}]"
    else:
        amount = diff
        lines = [
            {"account": "003", "account_name": "النقد", "debit": float(amount), "credit": 0.0},
            {"account": "005", "account_name": "العملاء (ذمم مدينة)", "debit": 0.0, "credit": float(amount)},
        ]
        tx_type = "payment"
        description = f"[محاذاة المحرك المالي: إثبات سداد تاريخي مؤكد] {customer} / {plate} [VISIT:{visit_id}] [VEHICLE:{vehicle_id}]"

    return {
        "id": str(uuid.uuid4()),
        "workshop_id": WORKSHOP_ID,
        "date": datetime.now(timezone.utc).isoformat(),
        "description": description,
        "lines": lines,
        "total": float(amount),
        "source": SOURCE,
        "transaction_type": tx_type,
        "reference_id": visit_id,
        "party_label": customer,
    }


def run(commit: bool) -> Dict[str, Any]:
    audit = json.loads(AUDIT_JSON.read_text(encoding="utf-8"))
    candidates = [row for row in audit.get("mismatches") or [] if abs(dec(row.get("difference_journal_minus_file"))) >= Decimal("0.01")]
    supa = SupabaseService()
    before_counts = {table: len(table_fetch_all(supa.client, table, "id")) for table in ("vehicles", "vehicle_visits", "journal_entries")}
    journals = table_fetch_all(supa.client, "journal_entries")
    existing = existing_refs(journals)
    engine = get_engine()
    rows = []
    total_positive = Decimal("0.00")
    total_negative = Decimal("0.00")
    for row in candidates:
        ref = latest_visit_id(row)
        diff = dec(row.get("difference_journal_minus_file"))
        entry = build_entry(row)
        if ref in existing:
            rows.append({"vehicle_id": row.get("vehicle_id"), "customer": row.get("customer"), "visit_id": ref, "diff": float(diff), "status": "skipped_existing_alignment"})
            continue
        if not commit:
            rows.append({"vehicle_id": row.get("vehicle_id"), "customer": row.get("customer"), "visit_id": ref, "diff": float(diff), "status": "dry_run", "entry": entry})
        else:
            posted = engine.post_entry(entry, fallback=False)
            journal_id = posted[0].get("id") if posted and isinstance(posted, list) else None
            rows.append({"vehicle_id": row.get("vehicle_id"), "customer": row.get("customer"), "visit_id": ref, "diff": float(diff), "status": "posted" if journal_id else "failed", "journal_id": journal_id})
        if diff < 0:
            total_positive += abs(diff)
        else:
            total_negative += diff
    after_counts = {table: len(table_fetch_all(supa.client, table, "id")) for table in ("vehicles", "vehicle_visits", "journal_entries")}
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "COMMIT" if commit else "DRY_RUN",
        "source": SOURCE,
        "before_counts": before_counts,
        "after_counts": after_counts,
        "journal_entries_delta": after_counts["journal_entries"] - before_counts["journal_entries"],
        "candidate_count": len(candidates),
        "total_ar_increase": float(total_positive),
        "total_ar_decrease": float(total_negative),
        "net_alignment_delta": float(total_positive - total_negative),
        "rows": rows,
    }
    OUTPUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    render(result)
    return result


def render(result: Dict[str, Any]) -> None:
    lines = [
        "# FINANCIAL_ENGINE_JOURNAL_ALIGNMENT_RESULT",
        "",
        f"- generated_at: `{result['generated_at']}`",
        f"- mode: **{result['mode']}**",
        f"- source: `{SOURCE}`",
        f"- journal_entries_delta: **{result['journal_entries_delta']}**",
        f"- total_ar_increase: **{money(result['total_ar_increase'])}**",
        f"- total_ar_decrease: **{money(result['total_ar_decrease'])}**",
        f"- net_alignment_delta: **{money(result['net_alignment_delta'])}**",
        "",
        "| العميل | vehicle_id | visit_id | فرق القيود-الملف | الحالة | journal_id |",
        "|---|---|---|---:|---|---|",
    ]
    for row in result["rows"]:
        lines.append(f"| {row.get('customer')} | `{row.get('vehicle_id')}` | `{row.get('visit_id')}` | {money(row.get('diff'))} | {row.get('status')} | `{row.get('journal_id') or '—'}` |")
    lines.extend(["", "## ملف JSON", "", f"- `{OUTPUT_JSON}`", ""])
    OUTPUT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit", action="store_true")
    args = parser.parse_args()
    result = run(commit=args.commit)
    print(json.dumps({"mode": result["mode"], "journal_entries_delta": result["journal_entries_delta"], "candidate_count": result["candidate_count"], "net_alignment_delta": result["net_alignment_delta"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()