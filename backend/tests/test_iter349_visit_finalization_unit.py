from __future__ import annotations

import json
from types import SimpleNamespace

from core import accounting_engine
from core.unified_financial_engine import build_vehicle_summary, build_visit_payment_journal_entry
from core.vehicle_finalization_posting import post_visit_finalization_canonical_entry


class Query:
    def __init__(self, rows):
        self.rows = rows
        self.filters = []
        self.limit_value = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, key, value):
        self.filters.append((key, value))
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def execute(self):
        rows = [row for row in self.rows if all(str(row.get(key)) == str(value) for key, value in self.filters)]
        if self.limit_value is not None:
            rows = rows[: self.limit_value]
        return SimpleNamespace(data=rows)


class Client:
    def __init__(self, journals):
        self.journals = journals

    def table(self, name):
        assert name == "journal_entries"
        return Query(self.journals)


def notes(final_total, paid, service_total, supplier_total):
    return json.dumps({
        "items": [
            {"itemType": "service", "billingType": "workshop", "quantity": 1, "price": service_total, "total": service_total},
            {"itemType": "supplier", "billingType": "supplier", "quantity": 1, "price": supplier_total, "total": supplier_total},
        ],
        "payments": [{"id": f"pay-{final_total}", "amount": paid, "status": "confirmed", "confirmed": True}],
        "financial_finalization": {
            "final_customer_total": final_total,
            "finalized_at": "2026-08-11T00:00:00Z",
            "finalized_by": "fixture",
            "finalization_source": "isolated_fixture",
        },
    })


def test_two_visits_have_independent_canonical_totals_payments_and_supplier_exclusion(monkeypatch):
    journals = []
    client = Client(journals)
    vehicle = {"id": "vehicle-1", "customer_id": "customer-1", "customer_name": "Fixture", "plate_number": "TEST"}
    visit_a = {"id": "visit-a", "vehicle_id": "vehicle-1", "notes": notes(1200, 300, 1000, 500)}
    visit_b = {"id": "visit-b", "vehicle_id": "vehicle-1", "notes": notes(800, 200, 700, 200)}

    def post_entry(entry, fallback=False):
        assert fallback is False
        existing = [row for row in journals if row.get("reference_id") == entry.get("reference_id")]
        if existing:
            return existing
        persisted = {**entry, "id": f"journal-{len(journals) + 1}"}
        journals.append(persisted)
        return [persisted]

    monkeypatch.setattr(accounting_engine, "post_entry", post_entry)

    for visit, total in ((visit_a, 1200), (visit_b, 800)):
        first = post_visit_finalization_canonical_entry(
            client,
            visit,
            vehicle,
            final_customer_total=total,
            finalized_at="2026-08-11T00:00:00Z",
            finalized_by="fixture",
            posting_source="isolated_fixture",
            workshop_id="finmodule-sync",
        )
        replay = post_visit_finalization_canonical_entry(
            client,
            visit,
            vehicle,
            final_customer_total=total,
            finalized_at="2026-08-11T00:00:00Z",
            finalized_by="fixture",
            posting_source="isolated_fixture",
            workshop_id="finmodule-sync",
        )
        assert first["posted"] is True
        assert replay["idempotent"] is True
        assert replay["matches_requested_total"] is True

    canonical = [row for row in journals if row.get("journal_semantic_class") == "CANONICAL_BUSINESS"]
    assert len(canonical) == 2
    assert {row["reference_id"] for row in canonical} == {"visitfinal:visit-a", "visitfinal:visit-b"}
    assert {row["business_event_id"] for row in canonical} == {"visit_finalization::visit-a", "visit_finalization::visit-b"}
    assert sum(float(row["total"]) for row in canonical) == 2000

    payment_a = build_visit_payment_journal_entry(
        visit=visit_a, vehicle=vehicle, amount=300, method="cash", date_value="2026-08-11", payment_id="payment-a", workshop_id="finmodule-sync"
    )
    payment_b = build_visit_payment_journal_entry(
        visit=visit_b, vehicle=vehicle, amount=200, method="bank", date_value="2026-08-11", payment_id="payment-b", workshop_id="finmodule-sync"
    )
    assert payment_a["reference_id"] == "visit-a"
    assert payment_b["reference_id"] == "visit-b"
    assert payment_a["reference_id"] != payment_b["reference_id"]

    summary = build_vehicle_summary(vehicle, [visit_a, visit_b], [], canonical)
    assert summary["customer_total"] == 2000
    assert summary["visit_final_customer_total"] == 2000
    assert summary["finalized_visit_count"] == 2
    assert summary["workshop_service_total"] == 1700
    assert summary["supplier_archive_total"] == 700
    assert summary["confirmed_paid"] == 500
    assert summary["display_remaining"] == 1500
    assert [row["final_customer_total"] for row in summary["visits"]] == [1200, 800]

    revenue_lines = [
        line for row in canonical for line in row.get("lines") or []
        if str(line.get("account")) in {"026", "027"}
    ]
    assert sum(float(line.get("credit") or 0) for line in revenue_lines) == 2000
    assert all(float(line.get("credit") or 0) not in {500, 200, 700} for line in revenue_lines)