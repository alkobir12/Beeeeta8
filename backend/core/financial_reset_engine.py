from __future__ import annotations

import json
import os
import re
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.accounting_engine import get_engine
from core.unified_financial_engine import build_current_ar_snapshot, parse_notes
from financial_reconciliation import journal_lines, table_fetch_all
from supabase_service import SupabaseService

CENT = Decimal("0.01")
WORKSHOP_ID = "finmodule-sync"
RESET_OPENING_SOURCE = "financial_reset_opening_receivable"
ARCHIVED_PERIOD_SOURCE = "archived_financial_period"
SNAPSHOT_DIR = Path(__file__).resolve().parent.parent / "uploads" / "financial_reset_snapshots"
AUDIT_PATH = SNAPSHOT_DIR / "financial_reset_audit_log.json"
CONFIRMATION_TEXT = "أؤكد بدء مالي جديد وترحيل الذمم"
HIDDEN_STATUSES = {"delivered", "archived", "cancelled", "canceled", "ملغي", "ملغى", "مؤرشف", "مسلم", "تم التسليم"}
AR_CODES = {"005", "1103", "113"}


def dec(value: Any) -> Decimal:
    try:
        return Decimal(str(value or 0)).quantize(CENT, rounding=ROUND_HALF_UP)
    except Exception:
        return Decimal("0.00")


def out(value: Any) -> float:
    return float(dec(value))


def text(value: Any) -> str:
    return str(value or "").strip()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_audit() -> List[Dict[str, Any]]:
    try:
        if not AUDIT_PATH.exists():
            return []
        data = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _write_audit(rows: List[Dict[str, Any]]) -> None:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_PATH.write_text(json.dumps(rows[-500:], ensure_ascii=False, indent=2), encoding="utf-8")


def append_audit(event: Dict[str, Any]) -> Dict[str, Any]:
    rows = _read_audit()
    event = {"id": event.get("id") or str(uuid.uuid4()), "created_at": now_iso(), **event}
    rows.append(event)
    _write_audit(rows)
    return event


def list_reset_audit(limit: int = 50) -> List[Dict[str, Any]]:
    rows = _read_audit()
    rows.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
    return rows[: max(1, min(int(limit or 50), 200))]


def _visit_has_archive_flag(visit: Dict[str, Any]) -> bool:
    parsed = parse_notes(visit.get("notes"))
    return bool(parsed.get("financial_reset_archived") or parsed.get("archived_financial_period"))


def _journal_ar_delta(entry: Dict[str, Any]) -> Decimal:
    total = Decimal("0.00")
    for line in journal_lines(entry):
        code = text(line.get("account") or line.get("code") or line.get("account_code"))
        if code in AR_CODES:
            total += dec(line.get("debit")) - dec(line.get("credit"))
    return total


def _vehicle_id_from_entry(entry: Dict[str, Any]) -> str:
    desc = text(entry.get("description"))
    match = re.search(r"\[VEHICLE:([^\]]+)\]", desc)
    return match.group(1).strip() if match else ""


def _current_tables(supa: SupabaseService) -> Dict[str, List[Dict[str, Any]]]:
    return {
        "vehicles": table_fetch_all(supa.client, "vehicles"),
        "vehicle_visits": table_fetch_all(supa.client, "vehicle_visits"),
        "operations": table_fetch_all(supa.client, "operations"),
        "journal_entries": table_fetch_all(supa.client, "journal_entries"),
        "customers": table_fetch_all(supa.client, "customers"),
    }


def _existing_completed_reset() -> Optional[Dict[str, Any]]:
    for row in list_reset_audit(limit=200):
        if row.get("event") == "execute" and row.get("status") == "completed":
            return row
    return None


def create_full_snapshot(reset_id: str, actor: Dict[str, Any], dry_run: Dict[str, Any]) -> str:
    supa = SupabaseService()
    tables = _current_tables(supa)
    payload = {
        "reset_id": reset_id,
        "created_at": now_iso(),
        "actor": actor,
        "dry_run": dry_run,
        "tables": tables,
        "schema": {name: sorted(list(rows[0].keys())) if rows else [] for name, rows in tables.items()},
    }
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SNAPSHOT_DIR / f"financial_reset_snapshot_{reset_id}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return str(path)


def build_dry_run(workshop_id: str = WORKSHOP_ID, actor: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    supa = SupabaseService()
    if supa.mock_mode:
        raise RuntimeError("Financial Reset Engine requires real database data")
    tables = _current_tables(supa)
    vehicles = tables["vehicles"]
    visits = tables["vehicle_visits"]
    operations = tables["operations"]
    journals = tables["journal_entries"]
    snapshot = build_current_ar_snapshot(supa.client, workshop_id=workshop_id)
    active_vehicles = [row for row in vehicles if text(row.get("status")).lower() not in HIDDEN_STATUSES]

    vehicle_rows = snapshot.get("vehicles") or []
    receivable_rows = []
    zero_balance_rows = []
    needs_review = []
    seen_vehicle_ids = Counter()
    current_ar_by_vehicle = defaultdict(lambda: Decimal("0.00"))
    for entry in journals:
        if text(entry.get("source")) == ARCHIVED_PERIOD_SOURCE:
            continue
        vehicle_id = _vehicle_id_from_entry(entry)
        if vehicle_id:
            current_ar_by_vehicle[vehicle_id] += _journal_ar_delta(entry)

    for row in vehicle_rows:
        vehicle_id = text(row.get("vehicle_id"))
        amount = dec(row.get("receivable"))
        seen_vehicle_ids[vehicle_id] += 1
        if amount > 0:
            journal_balance = current_ar_by_vehicle.get(vehicle_id, Decimal("0.00"))
            diff = journal_balance - amount
            reasons = []
            if abs(diff) > Decimal("0.01"):
                reasons.append("journal_vehicle_balance_mismatch")
            if seen_vehicle_ids[vehicle_id] > 1:
                reasons.append("duplicate_vehicle_receivable_row")
            item = {
                "vehicle_id": vehicle_id,
                "customer": row.get("customer"),
                "plate": row.get("plate"),
                "opening_balance_amount": out(amount),
                "journal_vehicle_balance": out(journal_balance),
                "difference": out(diff),
                "source_vehicle_id": vehicle_id,
            }
            if reasons:
                needs_review.append({**item, "reasons": reasons})
            else:
                receivable_rows.append(item)
        else:
            zero_balance_rows.append({"vehicle_id": vehicle_id, "customer": row.get("customer"), "plate": row.get("plate"), "amount": out(amount)})

    opening_total = sum((dec(row["opening_balance_amount"]) for row in receivable_rows), Decimal("0.00"))
    needs_review_total = sum((dec(row["opening_balance_amount"]) for row in needs_review), Decimal("0.00"))
    valid_before_total = dec(snapshot.get("total_ar")) - needs_review_total
    duplicate_rows = [row for row in receivable_rows if seen_vehicle_ids[row["vehicle_id"]] > 1]
    archived_visit_count = sum(1 for visit in visits if _visit_has_archive_flag(visit))
    already_reset = _existing_completed_reset()
    equality_ok = abs(opening_total - valid_before_total) <= Decimal("0.01")
    blocked_reasons = []
    if needs_review:
        blocked_reasons.append("needs_review_not_empty")
    if not equality_ok:
        blocked_reasons.append("opening_total_mismatch")
    if already_reset:
        blocked_reasons.append("previous_reset_completed")
    return {
        "success": True,
        "mode": "dry_run",
        "engine": "Financial Reset Engine",
        "generated_at": now_iso(),
        "workshop_id": workshop_id,
        "actor": actor or {},
        "confirmation_text": CONFIRMATION_TEXT,
        "can_execute": not blocked_reasons,
        "blocked_reasons": blocked_reasons,
        "previous_reset": already_reset,
        "summary": {
            "active_vehicle_count": len(active_vehicles),
            "vehicles_with_receivables": len(receivable_rows),
            "vehicles_zero_balance": len(zero_balance_rows),
            "total_receivables_before_reset": out(snapshot.get("total_ar")),
            "total_opening_receivables_after_reset": out(opening_total),
            "needs_review_total": out(needs_review_total),
            "duplicate_confirmed_count": len(duplicate_rows),
            "duplicate_suspected_count": 0,
            "paid_excluded_count": len(zero_balance_rows),
            "paid_excluded_amount": 0.0,
            "operations_to_archive": len(operations),
            "journal_entries_to_archive": len([j for j in journals if text(j.get("source")) != ARCHIVED_PERIOD_SOURCE]),
            "vehicle_visits_to_mark_archived_period": len([v for v in visits if not _visit_has_archive_flag(v)]),
            "already_archived_visit_count": archived_visit_count,
            "equality_check_passed": equality_ok,
        },
        "opening_receivables": receivable_rows,
        "zero_balance_vehicles": zero_balance_rows,
        "needs_review": needs_review,
        "duplicate_confirmed": duplicate_rows,
        "duplicate_suspected": [],
    }


def _opening_entry(reset_id: str, row: Dict[str, Any], workshop_id: str) -> Dict[str, Any]:
    amount = dec(row.get("opening_balance_amount"))
    return {
        "id": str(uuid.uuid4()),
        "workshop_id": workshop_id,
        "date": now_iso(),
        "description": f"[بدء مالي جديد] Opening Receivable {row.get('customer')} / {row.get('plate')} [RESET:{reset_id}] [VEHICLE:{row.get('vehicle_id')}]",
        "lines": [
            {"account": "005", "account_name": "العملاء (ذمم مدينة)", "debit": float(amount), "credit": 0.0},
            {"account": "020", "account_name": "أرصدة افتتاحية", "debit": 0.0, "credit": float(amount)},
        ],
        "total": float(amount),
        "source": RESET_OPENING_SOURCE,
        "transaction_type": "opening_receivable",
        "reference_id": f"{reset_id}:{row.get('vehicle_id')}",
        "party_label": row.get("customer"),
    }


def _mark_visit_notes_archived(visit: Dict[str, Any], reset_id: str) -> Dict[str, Any]:
    parsed = parse_notes(visit.get("notes"))
    parsed["financial_reset_archived"] = True
    parsed["archived_financial_period"] = reset_id
    parsed["archived_financial_period_at"] = now_iso()
    return {"notes": json.dumps(parsed, ensure_ascii=False)}


def execute_reset(*, workshop_id: str, confirmation_text: str, dry_run_token: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    if confirmation_text != CONFIRMATION_TEXT:
        raise ValueError("confirmation_text_invalid")
    dry = build_dry_run(workshop_id=workshop_id, actor=actor)
    if dry_run_token != dry.get("generated_at"):
        raise ValueError("dry_run_token_stale_or_invalid")
    if not dry.get("can_execute"):
        raise ValueError("dry_run_blocked: " + ",".join(dry.get("blocked_reasons") or []))

    reset_id = str(uuid.uuid4())
    snapshot_path = create_full_snapshot(reset_id, actor, dry)
    append_audit({"event": "snapshot", "status": "created", "reset_id": reset_id, "snapshot_path": snapshot_path, "actor": actor, "summary": dry.get("summary")})

    supa = SupabaseService()
    tables = _current_tables(supa)
    client = supa.client
    archived = {"journal_entries": 0, "operations": 0, "vehicle_visits": 0, "opening_receivables_created": 0}
    try:
        for entry in tables["journal_entries"]:
            entry_id = text(entry.get("id"))
            if not entry_id or text(entry.get("source")) == ARCHIVED_PERIOD_SOURCE:
                continue
            desc = text(entry.get("description"))
            client.table("journal_entries").update({
                "source": ARCHIVED_PERIOD_SOURCE,
                "description": f"{desc} [ARCHIVED_FINANCIAL_PERIOD:{reset_id}]",
                "transaction_type": text(entry.get("transaction_type")) or "archived",
            }).eq("id", entry_id).execute()
            archived["journal_entries"] += 1

        for op in tables["operations"]:
            op_id = text(op.get("id"))
            if not op_id:
                continue
            notes = text(op.get("notes"))
            client.table("operations").update({
                "type": ARCHIVED_PERIOD_SOURCE,
                "notes": f"{notes} [ARCHIVED_FINANCIAL_PERIOD:{reset_id}]".strip(),
            }).eq("id", op_id).execute()
            archived["operations"] += 1

        for visit in tables["vehicle_visits"]:
            visit_id = text(visit.get("id"))
            if not visit_id or _visit_has_archive_flag(visit):
                continue
            client.table("vehicle_visits").update(_mark_visit_notes_archived(visit, reset_id)).eq("id", visit_id).execute()
            archived["vehicle_visits"] += 1

        engine = get_engine()
        for row in dry.get("opening_receivables") or []:
            entry = _opening_entry(reset_id, row, workshop_id)
            engine.post_entry(entry, fallback=False)
            archived["opening_receivables_created"] += 1

        after = build_dry_run(workshop_id=workshop_id, actor=actor)
        event = append_audit({
            "event": "execute",
            "status": "completed",
            "reset_id": reset_id,
            "snapshot_path": snapshot_path,
            "actor": actor,
            "summary_before": dry.get("summary"),
            "summary_after": after.get("summary"),
            "items": archived,
        })
        return {"success": True, "reset_id": reset_id, "snapshot_path": snapshot_path, "items": archived, "audit_event": event, "after": after}
    except Exception as exc:
        append_audit({"event": "execute", "status": "failed", "reset_id": reset_id, "snapshot_path": snapshot_path, "actor": actor, "items": archived, "error": str(exc)})
        raise