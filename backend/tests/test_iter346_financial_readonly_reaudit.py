"""Iteration 346 - Read-only financial consistency re-audit assertions."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import requests


# Module: readonly financial consistency checkpoints from latest audit artifact.

AUDIT_JSON_PATH = Path("/app/test_reports/financial_consistency_readonly_audit.json")
PRODUCTION_HEALTH_URL = "https://car-repair-sys.emergent.host/api/health"


def _load_audit() -> dict:
    assert AUDIT_JSON_PATH.exists(), f"Missing audit artifact: {AUDIT_JSON_PATH}"
    return json.loads(AUDIT_JSON_PATH.read_text(encoding="utf-8"))


def test_audit_artifact_is_recent():
    payload = _load_audit()
    generated_at = payload.get("generated_at")
    assert isinstance(generated_at, str) and generated_at
    generated_dt = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    age_minutes = (datetime.now(timezone.utc) - generated_dt).total_seconds() / 60
    assert age_minutes <= 30, f"Audit artifact is stale ({age_minutes:.1f} min old)"


def test_mutation_guard_counts_unchanged():
    payload = _load_audit()
    guard = payload.get("mutation_guard") or {}
    before = guard.get("before") or {}
    after = guard.get("after") or {}

    assert guard.get("unchanged") is True
    assert before.get("vehicles") == 197 and after.get("vehicles") == 197
    assert before.get("vehicle_visits") == 181 and after.get("vehicle_visits") == 181
    assert before.get("operations") == 56 and after.get("operations") == 56
    assert before.get("journal_entries") == 36 and after.get("journal_entries") == 36


def test_current_ar_alignment_targets():
    payload = _load_audit()
    current_ar = (((payload.get("numbers") or {}).get("current_ar")) or {})

    assert current_ar.get("vehicle_file_remaining_total") == 9181.0
    assert current_ar.get("unified_engine_total") == 9181.0
    assert current_ar.get("ar_customers_total") == 9181.0
    assert current_ar.get("ar_ledger_ending") == 9181.0
    assert current_ar.get("ar_layers_current") == 9181.0


def test_katrina_conflict_targets():
    payload = _load_audit()
    current_ar = (((payload.get("numbers") or {}).get("current_ar")) or {})

    assert current_ar.get("katrina_tool_total_ar") == 0.0
    assert current_ar.get("assistant_dashboard_total_ar") == 0.0
    assert current_ar.get("ledger_all_entries_ar") == 22563.84


def test_journal_balance_and_trial_balance_targets():
    payload = _load_audit()
    current_period = (((payload.get("numbers") or {}).get("current_period")) or {})
    trial = (((payload.get("numbers") or {}).get("trial_balance")) or {})
    counts = payload.get("counts") or {}

    assert counts.get("journal_entries") == 36
    assert current_period.get("journal_debit") == 66739.68
    assert current_period.get("journal_credit") == 66739.68
    assert trial.get("debit") == 55817.68
    assert trial.get("credit") == 55817.68
    assert trial.get("difference") == 0.0


def test_balance_sheet_gap_target():
    payload = _load_audit()
    balance_sheet = (((payload.get("numbers") or {}).get("balance_sheet")) or {})

    assert balance_sheet.get("assets") == 22739.84
    assert balance_sheet.get("liabilities_plus_equity") == 21831.84
    assert balance_sheet.get("difference") == 908.0


def test_income_statement_targets():
    payload = _load_audit()
    current_period = (((payload.get("numbers") or {}).get("current_period")) or {})

    assert current_period.get("income_revenue_canonical") == 7494.0
    assert current_period.get("income_expenses") == 2274.0
    assert current_period.get("income_net") == 5220.0
    assert current_period.get("income_unknown_entries") == 0
    assert current_period.get("income_excluded_legacy_revenue") == 24013.84


def test_reconciliation_targets():
    payload = _load_audit()
    current_period = (((payload.get("numbers") or {}).get("current_period")) or {})
    missing = current_period.get("missing_operation_journals") or {}

    assert current_period.get("operations_reconciliation_difference") == 38692.16
    assert missing.get("count") == 43


def test_vehicle_finalization_mismatch_target():
    payload = _load_audit()
    mismatches = (((payload.get("details") or {}).get("finalization_mismatches")) or [])
    target = next((row for row in mismatches if row.get("vehicle_id") == "b885d618-a2fa-45df-b14f-0a9e9ff1b484"), None)

    assert target is not None
    assert target.get("final_customer_total") == 2300.0
    assert target.get("canonical_entries") == 0


def test_supplier_only_operation_violation_target():
    payload = _load_audit()
    violations = (((payload.get("details") or {}).get("supplier_policy_violations")) or [])
    target = next((row for row in violations if row.get("operation_id") == "3b1ccedf-29c6-4d9e-9108-f11a7bcc5c5e"), None)

    assert target is not None
    assert target.get("journal_ids") == ["1b91f14d-caa0-4212-a34b-f5d4f7c7cca3"]
    impact = target.get("impact") or {}
    assert impact.get("ar") == 167.84
    assert impact.get("revenue") == 167.84


def test_static_single_writer_contract_targets():
    payload = _load_audit()
    contract = payload.get("single_writer_contract") or {}

    assert len(contract.get("direct_journal_mutations_outside_engine") or []) == 8
    assert len(contract.get("post_entry_calls_using_default_fallback") or []) == 5
    assert contract.get("current_ar_end_date_is_effectively_used") is False
    assert contract.get("vehicle_final_default_adds_supplier_archive") is True
    assert contract.get("debt_page_can_synthesize_ledger_totals_from_engine") is True
    assert contract.get("debt_page_can_keep_higher_stale_cache") is True
    assert contract.get("dashboard_summaries_use_unified_engine") is False
    assert contract.get("journal_page_fetch_limit_50") is True


def test_expected_failed_checks_set():
    payload = _load_audit()
    failed = set(payload.get("failed_checks") or [])
    expected = {
        "balance_sheet_equation_balanced",
        "operations_reconciliation_matched",
        "no_missing_operation_journals",
        "canonical_finalizations_unique_and_equal",
        "supplier_only_operations_do_not_touch_ar_or_revenue",
        "katrina_ar_matches_current_ar",
        "assistant_dashboard_ar_matches_current_ar",
    }
    assert failed == expected


def test_production_health_read_only_check():
    response = requests.get(PRODUCTION_HEALTH_URL, timeout=30)
    assert response.status_code == 200
