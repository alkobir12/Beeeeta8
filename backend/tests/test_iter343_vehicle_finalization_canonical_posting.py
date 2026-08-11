"""Iter343: final_customer_total creates one canonical posting identity."""

import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from core.vehicle_finalization_posting import (  # noqa: E402
    accounting_identity_for_vehicle_finalization,
    build_vehicle_finalization_entry,
)


def test_finalization_entry_uses_final_customer_total_not_supplier_or_service_sum():
    vehicle = {
        "id": "vehicle-iter343",
        "plateNumber": "ت ج ر 343",
        "customerId": "customer-iter343",
        "customerName": "اختبار اعتماد نهائي",
    }
    entry = build_vehicle_finalization_entry(
        vehicle,
        final_customer_total=1500,
        finalized_at="2026-08-11T10:00:00+00:00",
        finalized_by="مدير",
        posting_source="test_finalization",
        workshop_id="finmodule-sync",
    )

    assert entry["source"] == "vehicle_visit"
    assert entry["transaction_type"] == "sale"
    assert entry["reference_id"] == accounting_identity_for_vehicle_finalization("vehicle-iter343")
    assert entry["total"] == 1500
    assert entry["journal_semantic_class"] == "CANONICAL_BUSINESS"
    assert entry["business_event_id"] == "vehicle_finalization::vehicle-iter343"
    assert entry["accounting_identity"] == "vehfinal:vehicle-iter343"
    assert entry["final_customer_total"] == 1500

    posting_lines = [line for line in entry["lines"] if not line.get("is_memo")]
    assert sum(float(line.get("debit") or 0) for line in posting_lines) == 1500
    assert sum(float(line.get("credit") or 0) for line in posting_lines) == 1500
    assert any(line["account"] == "005" and line["debit"] == 1500 for line in posting_lines)
    assert any(line["account"] in {"026", "025", "027"} and line["credit"] == 1500 for line in posting_lines)


def test_finalization_entry_carries_required_metadata_in_memo_line():
    entry = build_vehicle_finalization_entry(
        {"id": "vehicle-meta", "customerId": "customer-meta", "customerName": "عميل", "plateNumber": "م ي ت 1"},
        final_customer_total=1400,
        finalized_at="2026-08-11T10:15:00+00:00",
        finalized_by="مدير",
        posting_source="vehicle_financial_summary_card",
        workshop_id="finmodule-sync",
    )
    memo_lines = [line for line in entry["lines"] if line.get("is_memo")]
    assert len(memo_lines) == 1
    metadata = json.loads(memo_lines[0]["description"])
    assert metadata["journal_semantic_class"] == "CANONICAL_BUSINESS"
    assert metadata["business_event_id"] == "vehicle_finalization::vehicle-meta"
    assert metadata["accounting_identity"] == "vehfinal:vehicle-meta"
    assert metadata["vehicle_id"] == "vehicle-meta"
    assert metadata["customer_id"] == "customer-meta"
    assert metadata["reference_id"] == "vehfinal:vehicle-meta"
    assert metadata["final_customer_total"] == 1400
    assert metadata["posting_source"] == "vehicle_financial_summary_card"
    assert metadata["posted_at"] == "2026-08-11T10:15:00+00:00"


def test_accounting_identity_is_stable_for_retries_refresh_and_timeout():
    identities = {accounting_identity_for_vehicle_finalization("vehicle-stable") for _ in range(5)}
    assert identities == {"vehfinal:vehicle-stable"}
