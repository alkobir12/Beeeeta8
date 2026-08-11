"""Canonical posting adapter for vehicle finalization.

This is not a financial engine. It builds the final customer billing journal
entry for an approved vehicle final total and delegates the write to the
existing AccountingEngine only.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def _safe_float(value: Any) -> float:
    try:
        return round(float(value or 0), 2)
    except Exception:
        return 0.0


def accounting_identity_for_vehicle_finalization(vehicle_id: str) -> str:
    return f"vehfinal:{vehicle_id}"


def _business_event_id(vehicle_id: str) -> str:
    return f"vehicle_finalization::{vehicle_id}"


def accounting_identity_for_visit_finalization(visit_id: str) -> str:
    return f"visitfinal:{visit_id}"


def _visit_business_event_id(visit_id: str) -> str:
    return f"visit_finalization::{visit_id}"


def _semantic_code(key: str, fallback: str) -> str:
    try:
        from core.chart_resolver import semantic_codes
        return semantic_codes().get(key) or fallback
    except Exception:
        return fallback


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _existing_canonical_entry(client: Any, accounting_identity: str) -> Optional[Dict[str, Any]]:
    res = (
        client.table("journal_entries")
        .select("*")
        .eq("reference_id", accounting_identity)
        .limit(1)
        .execute()
    )
    rows = getattr(res, "data", None) or []
    return rows[0] if rows else None


def get_existing_vehicle_finalization_entry(client: Any, vehicle_id: str) -> Optional[Dict[str, Any]]:
    return _existing_canonical_entry(client, accounting_identity_for_vehicle_finalization(vehicle_id))


def build_vehicle_finalization_entry(
    vehicle: Dict[str, Any],
    *,
    final_customer_total: float,
    finalized_at: Optional[str] = None,
    finalized_by: Optional[str] = None,
    posting_source: str = "vehicle_finalization",
    workshop_id: str = "finmodule-sync",
) -> Dict[str, Any]:
    vehicle_id = str(vehicle.get("id") or "").strip()
    if not vehicle_id:
        raise ValueError("vehicle_id_required")
    final_total = _safe_float(final_customer_total)
    if final_total <= 0:
        raise ValueError("final_customer_total_must_be_positive")

    business_event_id = _business_event_id(vehicle_id)
    accounting_identity = accounting_identity_for_vehicle_finalization(vehicle_id)
    customer_id = str(vehicle.get("customerId") or vehicle.get("customer_id") or "").strip()
    customer_name = str(vehicle.get("customerName") or vehicle.get("customer_name") or "عميل").strip()
    plate = str(vehicle.get("plateNumber") or vehicle.get("plate_number") or vehicle_id).strip()
    posted_at = finalized_at or _now_iso()
    ar_code = _semantic_code("ar", "005")
    revenue_code = _semantic_code("revenue_mech", "026")

    metadata = {
        "journal_semantic_class": "CANONICAL_BUSINESS",
        "business_event_id": business_event_id,
        "accounting_identity": accounting_identity,
        "vehicle_id": vehicle_id,
        "customer_id": customer_id,
        "reference_id": accounting_identity,
        "final_customer_total": final_total,
        "posting_source": posting_source,
        "posted_at": posted_at,
        "finalized_by": finalized_by or "system",
    }
    metadata_json = json.dumps(metadata, ensure_ascii=False, sort_keys=True)
    description = (
        f"[CANONICAL_BUSINESS] اعتماد الإجمالي النهائي للمركبة {plate} — {customer_name} "
        f"[BUSINESS_EVENT_ID:{business_event_id}] [ACCOUNTING_IDENTITY:{accounting_identity}] "
        f"[VEHICLE:{vehicle_id}] [CUSTOMER:{customer_id}] [FINAL_CUSTOMER_TOTAL:{final_total}]"
    )

    return {
        "workshop_id": workshop_id,
        "date": posted_at,
        "description": description,
        "lines": [
            {"account": ar_code, "account_name": "العملاء (ذمم مدينة)", "debit": final_total, "credit": 0},
            {"account": revenue_code, "account_name": "إيرادات خدمات ميكانيكية", "debit": 0, "credit": final_total},
            {"account": "META", "account_name": "Canonical Posting Metadata", "debit": 0, "credit": 0, "is_memo": True, "description": metadata_json},
        ],
        "total": final_total,
        "source": "vehicle_visit",
        "transaction_type": "sale",
        "reference_id": accounting_identity,
        "journal_semantic_class": "CANONICAL_BUSINESS",
        "business_event_id": business_event_id,
        "accounting_identity": accounting_identity,
        "vehicle_id": vehicle_id,
        "customer_id": customer_id,
        "final_customer_total": final_total,
        "posting_source": posting_source,
        "posted_at": posted_at,
        "party_label": customer_name,
        "vehicle_label": plate,
    }


def post_vehicle_finalization_canonical_entry(
    client: Any,
    vehicle: Dict[str, Any],
    *,
    final_customer_total: float,
    finalized_at: Optional[str],
    finalized_by: Optional[str],
    posting_source: str,
    workshop_id: str,
) -> Dict[str, Any]:
    vehicle_id = str(vehicle.get("id") or "").strip()
    accounting_identity = accounting_identity_for_vehicle_finalization(vehicle_id)
    existing = _existing_canonical_entry(client, accounting_identity)
    final_total = _safe_float(final_customer_total)
    if existing:
        existing_total = _safe_float(existing.get("total"))
        return {
            "posted": False,
            "idempotent": True,
            "journal_id": existing.get("id"),
            "accounting_identity": accounting_identity,
            "business_event_id": _business_event_id(vehicle_id),
            "final_customer_total": existing_total,
            "matches_requested_total": abs(existing_total - final_total) < 0.01,
        }

    entry = build_vehicle_finalization_entry(
        vehicle,
        final_customer_total=final_total,
        finalized_at=finalized_at,
        finalized_by=finalized_by,
        posting_source=posting_source,
        workshop_id=workshop_id,
    )
    from core import accounting_engine
    posted = accounting_engine.post_entry(entry, fallback=False)
    if not posted:
        raise RuntimeError("accounting_engine_rejected_finalization_entry")
    journal_id = (posted[0] or {}).get("id")
    if not journal_id:
        raise RuntimeError("accounting_engine_did_not_confirm_finalization_entry")
    return {
        "posted": True,
        "journal_id": journal_id,
        "accounting_identity": accounting_identity,
        "business_event_id": _business_event_id(vehicle_id),
        "final_customer_total": final_total,
    }


def build_visit_finalization_entry(
    visit: Dict[str, Any],
    vehicle: Dict[str, Any],
    *,
    final_customer_total: float,
    finalized_at: Optional[str] = None,
    finalized_by: Optional[str] = None,
    posting_source: str = "visit_finalization",
    workshop_id: str = "finmodule-sync",
) -> Dict[str, Any]:
    visit_id = str(visit.get("id") or "").strip()
    vehicle_id = str(visit.get("vehicle_id") or visit.get("vehicleId") or vehicle.get("id") or "").strip()
    if not visit_id or not vehicle_id:
        raise ValueError("visit_and_vehicle_id_required")
    final_total = _safe_float(final_customer_total)
    if final_total <= 0:
        raise ValueError("final_customer_total_must_be_positive")

    accounting_identity = accounting_identity_for_visit_finalization(visit_id)
    business_event_id = _visit_business_event_id(visit_id)
    customer_id = str(vehicle.get("customerId") or vehicle.get("customer_id") or "").strip()
    customer_name = str(vehicle.get("customerName") or vehicle.get("customer_name") or "عميل").strip()
    plate = str(vehicle.get("plateNumber") or vehicle.get("plate_number") or vehicle_id).strip()
    posted_at = finalized_at or _now_iso()
    ar_code = _semantic_code("ar", "005")
    revenue_code = _semantic_code("revenue_mech", "026")
    metadata = {
        "journal_semantic_class": "CANONICAL_BUSINESS",
        "business_event_id": business_event_id,
        "accounting_identity": accounting_identity,
        "vehicle_id": vehicle_id,
        "visit_id": visit_id,
        "customer_id": customer_id,
        "reference_id": accounting_identity,
        "final_customer_total": final_total,
        "posting_source": posting_source,
        "posted_at": posted_at,
        "finalized_by": finalized_by or "system",
    }
    metadata_json = json.dumps(metadata, ensure_ascii=False, sort_keys=True)
    description = (
        f"[CANONICAL_BUSINESS] اعتماد الإجمالي النهائي للزيارة {visit_id} للمركبة {plate} — {customer_name} "
        f"[BUSINESS_EVENT_ID:{business_event_id}] [ACCOUNTING_IDENTITY:{accounting_identity}] "
        f"[VEHICLE:{vehicle_id}] [VISIT:{visit_id}] [CUSTOMER:{customer_id}] "
        f"[FINAL_CUSTOMER_TOTAL:{final_total}]"
    )
    return {
        "workshop_id": workshop_id,
        "date": posted_at,
        "description": description,
        "lines": [
            {"account": ar_code, "account_name": "العملاء (ذمم مدينة)", "debit": final_total, "credit": 0},
            {"account": revenue_code, "account_name": "إيرادات خدمات ميكانيكية", "debit": 0, "credit": final_total},
            {"account": "META", "account_name": "Canonical Posting Metadata", "debit": 0, "credit": 0, "is_memo": True, "description": metadata_json},
        ],
        "total": final_total,
        "source": "vehicle_visit",
        "transaction_type": "sale",
        "reference_id": accounting_identity,
        "journal_semantic_class": "CANONICAL_BUSINESS",
        "business_event_id": business_event_id,
        "accounting_identity": accounting_identity,
        "vehicle_id": vehicle_id,
        "visit_id": visit_id,
        "customer_id": customer_id,
        "final_customer_total": final_total,
        "posting_source": posting_source,
        "posted_at": posted_at,
        "party_label": customer_name,
        "vehicle_label": plate,
    }


def post_visit_finalization_canonical_entry(
    client: Any,
    visit: Dict[str, Any],
    vehicle: Dict[str, Any],
    *,
    final_customer_total: float,
    finalized_at: Optional[str],
    finalized_by: Optional[str],
    posting_source: str,
    workshop_id: str,
) -> Dict[str, Any]:
    visit_id = str(visit.get("id") or "").strip()
    accounting_identity = accounting_identity_for_visit_finalization(visit_id)
    existing = _existing_canonical_entry(client, accounting_identity)
    final_total = _safe_float(final_customer_total)
    if existing:
        existing_total = _safe_float(existing.get("total"))
        return {
            "posted": False,
            "idempotent": True,
            "journal_id": existing.get("id"),
            "accounting_identity": accounting_identity,
            "business_event_id": _visit_business_event_id(visit_id),
            "final_customer_total": existing_total,
            "matches_requested_total": abs(existing_total - final_total) < 0.01,
        }

    entry = build_visit_finalization_entry(
        visit,
        vehicle,
        final_customer_total=final_total,
        finalized_at=finalized_at,
        finalized_by=finalized_by,
        posting_source=posting_source,
        workshop_id=workshop_id,
    )
    from core import accounting_engine
    posted = accounting_engine.post_entry(entry, fallback=False)
    if not isinstance(posted, list) or not posted or not (posted[0] or {}).get("id"):
        raise RuntimeError("accounting_engine_rejected_visit_finalization_entry")
    return {
        "posted": True,
        "journal_id": posted[0]["id"],
        "accounting_identity": accounting_identity,
        "business_event_id": _visit_business_event_id(visit_id),
        "final_customer_total": final_total,
    }
