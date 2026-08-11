from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
load_dotenv(BACKEND / ".env")

from core import accounting_engine  # noqa: E402
from core.vehicle_finalization_posting import (  # noqa: E402
    accounting_identity_for_vehicle_finalization,
    post_vehicle_finalization_canonical_entry,
)
from core.unified_financial_engine import vehicle_finalization  # noqa: E402
from supabase_service import SupabaseService  # noqa: E402

WORKSHOP_ID = os.environ.get("DEFAULT_WORKSHOP_ID") or "finmodule-sync"
VEHICLE_2300 = "b885d618-a2fa-45df-b14f-0a9e9ff1b484"
VISIT_2300 = "174f49a1-5482-43d5-b333-ede2743a7d79"
VEHICLE_SUPPLIER = "8708bbd6-18be-4fb0-93a4-f9818b2b91ad"
VISIT_SUPPLIER = "3b1ccedf-29c6-4d9e-9108-f11a7bcc5c5e"
TARGET_SPECS = [
    {"vehicle_id": VEHICLE_2300, "visit_id": VISIT_2300, "source": "fin_engine_align_v1", "amount": "2300.00"},
    {"vehicle_id": VEHICLE_2300, "visit_id": VISIT_2300, "source": "operation", "amount": "1210.00"},
    {"vehicle_id": VEHICLE_SUPPLIER, "visit_id": VISIT_SUPPLIER, "source": "fin_engine_align_v1", "amount": "167.84"},
]
REPORT = ROOT / "test_reports" / "p0b_targeted_correction.json"
CENT = Decimal("0.01")


def dec(value: Any) -> Decimal:
    return Decimal(str(value or 0)).quantize(CENT, rounding=ROUND_HALF_UP)


def line_code(line: Dict[str, Any]) -> str:
    return str(line.get("account") or line.get("code") or line.get("account_code") or "").strip()


def impact(rows: List[Dict[str, Any]]) -> Dict[str, float]:
    ar = revenue = Decimal("0.00")
    for row in rows:
        for line in row.get("lines") or []:
            code = line_code(line)
            debit = dec(line.get("debit"))
            credit = dec(line.get("credit"))
            if code in {"005", "1103", "113"}:
                ar += debit - credit
            if code in {"024", "025", "026", "027", "041", "042", "4000", "4100", "4101", "4102"}:
                revenue += credit - debit
    return {"ar": float(ar), "revenue": float(revenue)}


def one(client: Any, table: str, **filters: str) -> Dict[str, Any]:
    query = client.table(table).select("*")
    for key, value in filters.items():
        query = query.eq(key, value)
    rows = query.limit(1).execute().data or []
    if not rows:
        raise RuntimeError(f"missing_required_row:{table}:{filters}")
    return rows[0]


def by_reference(client: Any, reference_id: str) -> List[Dict[str, Any]]:
    return client.table("journal_entries").select("*").eq("reference_id", reference_id).execute().data or []


def resolve_original(client: Any, spec: Dict[str, str]) -> Dict[str, Any]:
    rows = (
        client.table("journal_entries")
        .select("*")
        .eq("reference_id", spec["visit_id"])
        .eq("source", spec["source"])
        .execute()
        .data
        or []
    )
    matches = [row for row in rows if dec(row.get("total")) == dec(spec["amount"])]
    if len(matches) != 1:
        raise RuntimeError(f"target_lineage_count_invalid:{spec}:{len(matches)}")
    return matches[0]


def correction_reference(journal_id: str) -> str:
    return f"p0b-correction:{journal_id}"


def build_correction(original: Dict[str, Any], target: Dict[str, str]) -> Dict[str, Any]:
    journal_id = str(original.get("id") or "")
    swapped = []
    for line in original.get("lines") or []:
        if line.get("is_memo") or line_code(line) == "META":
            continue
        swapped.append({
            **line,
            "debit": float(dec(line.get("credit"))),
            "credit": float(dec(line.get("debit"))),
        })
    if not swapped:
        raise RuntimeError(f"correction_has_no_financial_lines:{journal_id}")
    now = datetime.now(timezone.utc).isoformat()
    business_event_id = f"p0b_targeted_correction::{journal_id}"
    reference_id = correction_reference(journal_id)
    return {
        "workshop_id": WORKSHOP_ID,
        "date": now,
        "description": (
            f"[HISTORICAL_FINANCIAL_REPAIR] عكس مستهدف للقيد {journal_id} "
            f"[REVERSAL_OF:{journal_id}] [BUSINESS_EVENT_ID:{business_event_id}] "
            f"[VEHICLE:{target['vehicle_id']}] [VISIT:{target['visit_id']}]"
        ),
        "lines": swapped,
        "total": float(dec(original.get("total"))),
        "source": "historical_financial_repair",
        "transaction_type": "repair_reversal",
        "reference_id": reference_id,
        "journal_semantic_class": "HISTORICAL_REPAIR",
        "business_event_id": business_event_id,
        "accounting_identity": reference_id,
        "vehicle_id": target["vehicle_id"],
        "visit_id": target["visit_id"],
        "posting_source": "p0b_targeted_correction",
        "posted_at": now,
    }


def main() -> None:
    apply_changes = os.environ.get("P0B_APPLY") == "true"
    supa = SupabaseService()
    if supa.mock_mode:
        raise RuntimeError("real_supabase_required")
    client = supa.client
    originals = []
    targets: Dict[str, Dict[str, str]] = {}
    plan = []
    for target in TARGET_SPECS:
        original = resolve_original(client, target)
        journal_id = str(original.get("id"))
        targets[journal_id] = target
        originals.append(original)
        existing = by_reference(client, correction_reference(journal_id))
        plan.append({
            "journal_id": journal_id,
            "target": target,
            "original_impact": impact([original]),
            "correction_reference": correction_reference(journal_id),
            "already_corrected": len(existing) == 1,
        })

    vehicle = one(client, "vehicles", id=VEHICLE_2300)
    finalization = vehicle_finalization(vehicle)
    if dec(finalization.get("final_customer_total")) != Decimal("2300.00"):
        raise RuntimeError(f"vehicle_final_total_changed:{finalization}")
    canonical_reference = accounting_identity_for_vehicle_finalization(VEHICLE_2300)
    canonical_before = by_reference(client, canonical_reference)
    if len(canonical_before) > 1:
        raise RuntimeError("duplicate_canonical_exists_before_correction")

    result = {
        "mode": "apply" if apply_changes else "dry_run",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "plan": plan,
        "canonical_before": [row.get("id") for row in canonical_before],
        "posted_corrections": [],
        "canonical_posting": None,
    }
    if not apply_changes:
        REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    for original in originals:
        journal_id = str(original.get("id"))
        existing = by_reference(client, correction_reference(journal_id))
        if existing:
            result["posted_corrections"].append({"journal_id": existing[0].get("id"), "idempotent": True})
            continue
        posted = accounting_engine.post_entry(build_correction(original, targets[journal_id]), fallback=False)
        if not isinstance(posted, list) or not posted or not (posted[0] or {}).get("id"):
            raise RuntimeError(f"accounting_engine_rejected_correction:{journal_id}")
        result["posted_corrections"].append({"journal_id": posted[0]["id"], "idempotent": False})

    result["canonical_posting"] = post_vehicle_finalization_canonical_entry(
        client,
        vehicle,
        final_customer_total=2300.0,
        finalized_at=finalization.get("finalized_at"),
        finalized_by=finalization.get("finalized_by") or "p0b-approved",
        posting_source="p0b_targeted_missing_canonical",
        workshop_id=WORKSHOP_ID,
    )

    correction_rows = []
    for journal_id in targets:
        rows = by_reference(client, correction_reference(journal_id))
        if len(rows) != 1:
            raise RuntimeError(f"correction_identity_count_invalid:{journal_id}:{len(rows)}")
        correction_rows.extend(rows)
    canonical_after = by_reference(client, canonical_reference)
    if len(canonical_after) != 1 or dec(canonical_after[0].get("total")) != Decimal("2300.00"):
        raise RuntimeError(f"canonical_after_invalid:{canonical_after}")

    a_original_ids = {journal_id for journal_id, target in targets.items() if target["vehicle_id"] == VEHICLE_2300}
    b_original_ids = {journal_id for journal_id, target in targets.items() if target["vehicle_id"] == VEHICLE_SUPPLIER}
    a_correction_refs = {correction_reference(journal_id) for journal_id in a_original_ids}
    b_correction_refs = {correction_reference(journal_id) for journal_id in b_original_ids}
    a_rows = [row for row in originals if str(row.get("id")) in a_original_ids]
    a_rows += [row for row in correction_rows if str(row.get("reference_id")) in a_correction_refs]
    a_rows += canonical_after
    b_rows = [row for row in originals if str(row.get("id")) in b_original_ids]
    b_rows += [row for row in correction_rows if str(row.get("reference_id")) in b_correction_refs]
    result["verification"] = {
        "missing_canonical_2300": "PASS",
        "duplicate_canonical": len(canonical_after) - 1,
        "vehicle_2300_net_effect": impact(a_rows),
        "supplier_net_effect": impact(b_rows),
        "supplier_archive_effect": 167.84,
    }
    if result["verification"]["vehicle_2300_net_effect"] != {"ar": 2300.0, "revenue": 2300.0}:
        raise RuntimeError(f"vehicle_2300_net_effect_invalid:{result['verification']}")
    if result["verification"]["supplier_net_effect"] != {"ar": 0.0, "revenue": 0.0}:
        raise RuntimeError(f"supplier_net_effect_invalid:{result['verification']}")

    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()