import os
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv


load_dotenv("/app/backend/.env")
sys.path.insert(0, str(Path("/app/backend")))


def _client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        pytest.skip("Supabase env is not configured")
    from supabase import create_client

    return create_client(url, key)


def test_reconciliation_audit_acceptance_contract_read_only():
    from financial_reconciliation import build_reconciliation_audit

    supabase = _client()
    report1 = build_reconciliation_audit(supabase, workshop_id="finmodule-sync")
    report2 = build_reconciliation_audit(supabase, workshop_id="finmodule-sync")

    assert report1["success"] is True
    assert report1["metadata"]["read_only"] is True
    assert report1["mutation_guard"]["unchanged"] is True
    assert report2["mutation_guard"]["unchanged"] is True
    assert report1["mutation_guard"]["before_counts"] == report2["mutation_guard"]["before_counts"]
    assert report1["mutation_guard"]["after_counts"] == report2["mutation_guard"]["after_counts"]

    flags = report1["acceptance_flags"]
    assert flags["active_vehicle_count_is_15"] is True
    assert flags["no_journal_record_in_two_scopes"] is True
    assert flags["journal_scope_sum_equals_all"] is True
    assert flags["operation_scope_sum_equals_all"] is True
    assert flags["raw_overlap_detected"] is True
    assert flags["ar_delta_500_explained_with_ids"] is True
    assert flags["revenue_210_explained"] is True
    assert flags["expense_210_gap_independently_explained"] is True
    assert flags["trial_balance_balanced"] is True
    assert flags["report_did_not_mutate_tables"] is True

    raw = report1["raw_classification"]
    assert raw["dashboard_visible_current_logic_count"] == 15
    assert len(raw["overlap_active_and_raw_archive_ids"]) == 2

    scopes = report1["resolved_exclusive_scopes"]
    assert scopes["vehicle_scope_counts"]["live"] == 15
    assert scopes["vehicle_scope_counts"]["exclusive_sum_ok"] is True
    assert scopes["journal_entry_exclusive_sum_ok"] is True
    assert scopes["operation_exclusive_sum_ok"] is True

    ar = report1["ar_reconciliation"]
    assert ar["delta_against_owner_reported"] == 500.0
    assert len(ar["payment_allocations"]) == 3
    assert any(row["amount"] == 500.0 and row["candidate_type"] == "credit_operation_not_payment" for row in ar["delta_500_candidates"])

    assert report1["revenue_210_reconciliation"]["total"] == 210.0
    assert report1["expense_reconciliation"]["total"] == 16810.0
    assert report1["trial_balance"]["balanced"] is True


def test_reconciliation_audit_uses_exclusive_scopes_for_every_journal_entry():
    from financial_reconciliation import build_reconciliation_audit

    report = build_reconciliation_audit(_client(), workshop_id="finmodule-sync")
    rows = report["record_classification_rows"]["journal_entries"]
    assert len(rows) == report["resolved_exclusive_scopes"]["journal_entry_total"]

    valid_scopes = {"live", "archive", "legacy_excluded", "unlinked", "pending_decision", "posting_missing"}
    ids = [row["journal_entry_id"] for row in rows]
    assert len(ids) == len(set(ids))
    assert all(row["resolved_scope"] in valid_scopes for row in rows)
    assert all(row.get("classification_reasons") for row in rows)

    opening = report["opening_balance_scenarios"]["pending_decision_rows"]
    assert {row["ar_net"] for row in opening} == {16000.0, 300.0}
    assert all(row["resolved_scope"] == "pending_decision" for row in opening)