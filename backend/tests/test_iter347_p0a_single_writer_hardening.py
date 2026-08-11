from __future__ import annotations

import ast
import inspect
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.append(str(BACKEND))

import routes_extended
import routes_finance
import routes_suppliers_extended
from core import accounting_engine
from core.financial_actions import mark_temp_deferred_settled
from core.financial_reset_engine import execute_reset
if str(BACKEND) not in sys.path:
    sys.path.append(str(BACKEND))


def _request(path: str = "/api/test") -> Request:
    return Request({"type": "http", "method": "POST", "path": path, "headers": []})


def _function_node(path: Path, name: str):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"function not found: {path}:{name}")


def _first_statement_after_docstring(node):
    body = list(node.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]
    assert body
    return body[0]


def test_no_direct_journal_mutations_outside_accounting_engine():
    offenders = []
    mutation_names = {"insert", "update", "delete", "upsert", "insert_one", "update_one", "delete_one", "delete_many", "replace_one"}
    for path in BACKEND.rglob("*.py"):
        rel = path.relative_to(BACKEND).as_posix()
        if rel.startswith(("tests/", "scripts/")) or rel == "core/accounting_engine.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in mutation_names:
                continue
            constants = {child.value for child in ast.walk(node.func.value) if isinstance(child, ast.Constant) and isinstance(child.value, str)}
            attrs = {child.attr for child in ast.walk(node.func.value) if isinstance(child, ast.Attribute)}
            if "journal_entries" in constants or "journal_entries" in attrs:
                offenders.append(f"{rel}:{node.lineno}:{node.func.attr}")
    assert offenders == []


def test_all_post_entry_callers_disable_engine_fallback():
    offenders = []
    for path in BACKEND.rglob("*.py"):
        rel = path.relative_to(BACKEND).as_posix()
        if rel.startswith("tests/") or rel == "core/accounting_engine.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute) or node.func.attr != "post_entry":
                continue
            fallback = next((kw.value for kw in node.keywords if kw.arg == "fallback"), None)
            if not isinstance(fallback, ast.Constant) or fallback.value is not False:
                offenders.append(f"{rel}:{node.lineno}")
    assert offenders == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("call", "action"),
    [
        (lambda: routes_finance.reclassify_payment_accounts(workshop_id="finmodule-sync", apply_changes=True), "reclassify_payment_accounts"),
        (lambda: routes_finance.apply_bank_revenue_policy(workshop_id="finmodule-sync", apply_changes=True), "apply_bank_revenue_policy"),
        (lambda: routes_finance.repost_bank_and_fix_imbalance(workshop_id="finmodule-sync", apply_changes=False), "repost_bank_and_fix_imbalance_balancing_plug"),
        (lambda: routes_finance.reclassify_vehicle_workshop_dues(workshop_id="finmodule-sync", apply_changes=True), "reclassify_vehicle_workshop_dues"),
        (lambda: routes_finance.migrate_legacy_account_codes(workshop_id="finmodule-sync", apply_changes=True), "migrate_legacy_account_codes"),
        (lambda: routes_finance.reclassify_revenue_sub_accounts(workshop_id="finmodule-sync", apply_changes=True), "reclassify_revenue_sub_accounts"),
        (lambda: routes_finance.backfill_missing_operation_journals(workshop_id="finmodule-sync", apply_changes=True), "reconciliation_backfill_43_operations"),
    ],
)
async def test_legacy_mutation_endpoints_are_blocked_before_data_access(call, action):
    with pytest.raises(HTTPException) as exc:
        await call()
    assert exc.value.status_code == 410
    assert exc.value.detail["action"] == action


@pytest.mark.asyncio
async def test_operations_integrity_bulk_backfill_is_blocked():
    with pytest.raises(HTTPException) as exc:
        await routes_extended.operations_integrity_fix_all({})
    assert exc.value.status_code == 410
    assert exc.value.detail["error"] == "operations_integrity_backfill_blocked"


def test_financial_reset_execute_is_unconditionally_blocked():
    with pytest.raises(ValueError, match="financial_reset_execution_blocked_p0_single_writer"):
        execute_reset(workshop_id="finmodule-sync", confirmation_text="anything", dry_run_token="anything", actor={})
    node = _function_node(BACKEND / "core" / "financial_reset_engine.py", "execute_reset")
    assert isinstance(_first_statement_after_docstring(node), ast.Raise)


def test_repost_balancing_plug_is_unconditionally_blocked():
    node = _function_node(BACKEND / "routes_finance.py", "repost_bank_and_fix_imbalance")
    first = _first_statement_after_docstring(node)
    assert isinstance(first, ast.Expr)
    assert isinstance(first.value, ast.Call)
    assert getattr(first.value.func, "id", "") == "_raise_legacy_financial_mutation_blocked"


def test_temp_deferred_status_does_not_mutate_journal():
    source = inspect.getsource(mark_temp_deferred_settled)
    assert "journal_entries" not in source
    assert mark_temp_deferred_settled("ref-1", fully=True) is None


@pytest.mark.asyncio
async def test_manual_journal_empty_engine_result_fails_closed(monkeypatch):
    monkeypatch.setattr(accounting_engine, "post_entry", lambda *_args, **_kwargs: [])
    invalidations = []
    monkeypatch.setattr(routes_finance, "invalidate_finance_caches", lambda: invalidations.append(True))
    entry = {
        "description": "fixture only",
        "source": "manual",
        "lines": [
            {"account": "003", "debit": 100, "credit": 0},
            {"account": "026", "debit": 0, "credit": 100},
        ],
    }
    with pytest.raises(HTTPException) as exc:
        await routes_finance.create_journal_entry(entry, _request(), workshop_id="finmodule-sync")
    assert exc.value.status_code == 502
    assert invalidations == []


@pytest.mark.asyncio
async def test_manual_journal_update_is_blocked():
    with pytest.raises(HTTPException) as exc:
        await routes_finance.update_journal_entry("journal-1", {}, workshop_id="finmodule-sync")
    assert exc.value.status_code == 410


@pytest.mark.asyncio
async def test_supplier_import_validates_all_rows_before_posting(monkeypatch):
    calls = []
    monkeypatch.setattr(routes_suppliers_extended, "supabase", object())
    monkeypatch.setattr(accounting_engine, "post_entry", lambda *_args, **_kwargs: calls.append(True) or [{"id": "fixture"}])
    payload = {
        "rows": [["مورد", "100", "2026-08-11", "credit"], ["مورد", "0", "2026-08-11", "credit"]],
        "mapping": {"name_col": 0, "amount_col": 1, "date_col": 2, "type_col": 3},
        "workshop_id": "finmodule-sync",
    }
    with pytest.raises(HTTPException) as exc:
        await routes_suppliers_extended.import_execute(payload)
    assert exc.value.status_code == 400
    assert calls == []


@pytest.mark.asyncio
async def test_supplier_import_empty_engine_result_is_not_success(monkeypatch):
    monkeypatch.setattr(routes_suppliers_extended, "supabase", object())
    monkeypatch.setattr(accounting_engine, "post_entry", lambda *_args, **_kwargs: [])
    payload = {
        "rows": [["مورد", "100", "2026-08-11", "credit"]],
        "mapping": {"name_col": 0, "amount_col": 1, "date_col": 2, "type_col": 3},
        "workshop_id": "finmodule-sync",
    }
    with pytest.raises(HTTPException) as exc:
        await routes_suppliers_extended.import_execute(payload)
    assert exc.value.status_code == 502
    assert exc.value.detail["error"] == "supplier_import_post_failed"


def test_payment_post_helper_rejects_empty_engine_result(monkeypatch):
    monkeypatch.setattr(accounting_engine, "post_entry", lambda *_args, **_kwargs: [])
    with pytest.raises(RuntimeError, match="accounting_engine_rejected_entry"):
        routes_extended._safe_insert_journal_entry(SimpleNamespace(), {"id": "fixture", "lines": []})


def test_payment_and_operation_paths_have_no_silent_financial_fallbacks():
    payment_source = inspect.getsource(routes_extended.confirm_operation_payment)
    create_source = inspect.getsource(routes_extended.create_operation)
    assert "base_journal_required" in payment_source
    assert "Missing-base fallback" not in payment_source
    assert "operations_delete" in create_source
    assert "reverse_entry" in create_source
    assert "financial_provider_unavailable" in create_source
    assert "except Exception as je_error" in create_source
    assert "raise HTTPException" in create_source


def test_close_period_and_manual_journal_require_persisted_engine_ids():
    close_source = inspect.getsource(routes_finance.close_period)
    manual_source = inspect.getsource(routes_finance.create_journal_entry)
    assert "fallback=False" in close_source
    assert "persisted_journal_id" in close_source
    assert "fallback=False" in manual_source
    assert "entry_data[\"id\"]" not in manual_source.split("response_data =", 1)[1]


def test_legacy_vehicle_parts_auto_posting_is_blocked():
    source = inspect.getsource(__import__("server").save_vehicle_parts_and_create_journal)
    blocked_at = source.index("legacy_vehicle_parts_auto_posting_disabled")
    legacy_operation_write_at = source.index('table("operations").insert')
    assert blocked_at < legacy_operation_write_at