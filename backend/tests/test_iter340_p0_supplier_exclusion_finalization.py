"""Iter340: P0 supplier exclusion + explicit final customer total regression checks."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from core.operation_journal_adapter import _build_operation_journal_entry
from core.unified_financial_engine import build_vehicle_summary, serialize_notes


# Module: vehicle summary/customer AR separation + operation journal supplier exclusion.


def _visit_with_service_and_supplier(*, paid_amount: float = 300):
    return {
        "id": "visit-iter340",
        "vehicle_id": "vehicle-iter340",
        "notes": serialize_notes(
            {
                "items": [
                    {"itemType": "service", "total": 1000},
                    {"itemType": "supplier", "name": "مورد", "total": 500},
                ],
                "payments": [{"amount": paid_amount, "confirmed": True, "status": "confirmed"}],
            }
        ),
    }


def test_supplier_items_are_archive_only_before_delivery_for_customer_ar_remaining():
    summary = build_vehicle_summary({"id": "vehicle-iter340", "notes": "{}"}, [_visit_with_service_and_supplier()], [], [])

    assert summary["total_workshop"] == 1000
    assert summary["supplier_archive_total"] == 500
    assert summary["customer_total"] == 1000
    assert summary["display_remaining"] == 700


def test_final_customer_total_is_explicit_and_drives_remaining_1500_and_1400():
    visits = [_visit_with_service_and_supplier()]

    summary_1500 = build_vehicle_summary(
        {
            "id": "vehicle-iter340",
            "notes": serialize_notes(
                {
                    "financial_finalization": {
                        "final_customer_total": 1500,
                        "finalized_at": "2026-02-01T10:00:00Z",
                        "finalized_by": "manager",
                        "finalization_source": "vehicle_delivery",
                        "previous_service_total": 1000,
                    }
                }
            ),
        },
        visits,
        [],
        [],
    )
    assert summary_1500["final_customer_total"] == 1500
    assert summary_1500["customer_total"] == 1500
    assert summary_1500["display_remaining"] == 1200
    assert summary_1500["finalized_at"] == "2026-02-01T10:00:00Z"
    assert summary_1500["finalized_by"] == "manager"
    assert summary_1500["finalization_source"] == "vehicle_delivery"
    assert summary_1500["previous_service_total"] == 1000

    summary_1400 = build_vehicle_summary(
        {
            "id": "vehicle-iter340",
            "notes": serialize_notes(
                {
                    "financial_finalization": {
                        "final_customer_total": 1400,
                        "finalized_at": "2026-02-02T10:00:00Z",
                        "finalized_by": "manager",
                        "finalization_source": "vehicle_delivery",
                        "previous_service_total": 1000,
                    }
                }
            ),
        },
        visits,
        [],
        [],
    )
    assert summary_1400["final_customer_total"] == 1400
    assert summary_1400["customer_total"] == 1400
    assert summary_1400["display_remaining"] == 1100


def test_final_customer_total_controls_remaining_not_supplier_totals():
    summary = build_vehicle_summary(
        {
            "id": "vehicle-iter340",
            "notes": serialize_notes({"financial_finalization": {"final_customer_total": 1400}}),
        },
        [_visit_with_service_and_supplier(paid_amount=1300)],
        [],
        [],
    )

    assert summary["total_workshop"] == 1000
    assert summary["supplier_archive_total"] == 500
    assert summary["confirmed_paid"] == 1300
    assert summary["customer_total"] == 1400
    assert summary["display_remaining"] == 100


def test_operation_journal_adapter_does_not_map_supplier_lines_to_revenue():
    operation = {
        "id": "op-iter340",
        "type": "service",
        "paymentMethod": "credit",
        "paymentStatus": "credit",
        "total": 1500,
        "items": [
            {"itemType": "service", "name": "أجرة", "total": 1000},
            {
                "itemType": "supplier",
                "name": "شركة توريد",
                "total": 500,
                "revenueAccountCode": "041",
                "linkedPart": "part-123",
            },
        ],
    }

    entry = _build_operation_journal_entry(operation, "finmodule-sync")

    assert entry is not None
    assert float(entry["total"]) == 1000
    assert float(entry["workshop_total"]) == 1000
    assert float(entry["supplier_archive_total"]) == 500

    credits = {line["account"]: float(line.get("credit") or 0) for line in entry["lines"]}
    assert sum(credits.values()) == 1000
    assert credits.get("041", 0) == 0
