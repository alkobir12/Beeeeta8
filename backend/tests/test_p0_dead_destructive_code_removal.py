"""PART A — P0-DEAD-DESTRUCTIVE-CODE-REMOVAL. Static / mocked only.

No reset is executed, no database is touched, no deploy.
"""

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from core import destructive_guard  # noqa: E402

DEAD_CODE_TARGETS = {"reset_all_financial_data", "reset_ops_journals_keep_debts_only"}

# reachable FastAPI routes whose body performs an unfiltered destructive write
GUARDED_ROUTES = {
    "routes_extended.py": "delete_all_operations",
    "server.py": "reset_inventory_data",
    "routes_accounts_chart.py": "reset_accounts_chart",
}

# stand-alone scripts that wipe collections; must be fail-closed at the CLI
GUARDED_SCRIPTS = [
    "clear_data.py",
    "clean_and_add_services.py",
    "adopt_unified_workflow_template.py",
    "reset_primary_invoice_template.py",
]


def _tree(name: str) -> ast.Module:
    return ast.parse((BACKEND_DIR / name).read_text(encoding="utf-8"))


def _functions(name: str):
    for node in ast.walk(_tree(name)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


# ------------------------------------------------- dead destructive code gone
def test_legacy_reset_endpoints_contain_nothing_after_the_410():
    found = set()
    for node in _functions("routes_finance.py"):
        if node.name not in DEAD_CODE_TARGETS:
            continue
        found.add(node.name)
        body = list(node.body)
        if isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
            body = body[1:]
        assert len(body) == 1, f"{node.name} still has {len(body)} statements after the docstring"
        assert isinstance(body[0], ast.Raise), f"{node.name} first statement is not a raise"
    assert found == DEAD_CODE_TARGETS


def test_legacy_reset_endpoints_still_raise_410():
    source = (BACKEND_DIR / "routes_finance.py").read_text(encoding="utf-8")
    assert "legacy_reset_all_data_disabled" in source
    assert "legacy_keep_debts_only_disabled" in source
    # the per-branch 410 guards that lived inside the removed dead code are gone with it
    assert "legacy_reset_all_data_disabled_no_journal_delete" not in source
    assert "legacy_keep_debts_only_disabled_no_journal_delete" not in source


def test_no_destructive_operation_remains_in_routes_finance():
    source = (BACKEND_DIR / "routes_finance.py").read_text(encoding="utf-8")
    for forbidden in ("delete_many({})", 'delete().neq("id", "")', ".drop()", "drop_database"):
        assert forbidden not in source, f"routes_finance.py still contains {forbidden}"


def test_removal_did_not_delete_the_endpoints_themselves():
    source = (BACKEND_DIR / "routes_finance.py").read_text(encoding="utf-8")
    assert '@router.delete("/reset-all-data")' in source
    assert '@router.delete("/reset-ops-journals-keep-debts")' in source


def test_no_replacement_destructive_route_was_introduced():
    """The contract: delete the dead code, do not re-enable it or route around it."""
    source = (BACKEND_DIR / "routes_finance.py").read_text(encoding="utf-8")
    assert "require_destructive_authorization" not in source, (
        "the legacy 410 endpoints must stay disabled, not be re-armed behind the guard"
    )


# ------------------------------------------------------- reachable routes guarded
@pytest.mark.parametrize("module,func", sorted(GUARDED_ROUTES.items()))
def test_reachable_destructive_route_calls_the_guard_first(module, func):
    node = next(n for n in _functions(module) if n.name == func)
    body = list(node.body)
    if isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]

    guard_line = None
    destructive_line = None
    for statement in body:
        for sub in ast.walk(statement):
            if isinstance(sub, ast.Call):
                target = sub.func
                label = getattr(target, "attr", None) or getattr(target, "id", None)
                if label == "require_destructive_authorization" and guard_line is None:
                    guard_line = sub.lineno
                if label in {"delete_many", "update_many", "delete"} and destructive_line is None:
                    destructive_line = sub.lineno

    assert guard_line is not None, f"{module}:{func} does not call require_destructive_authorization"
    if destructive_line is not None:
        assert guard_line < destructive_line, (
            f"{module}:{func} performs a destructive call at line {destructive_line} "
            f"before the guard at line {guard_line}"
        )


def test_accounts_chart_reset_is_now_authenticated():
    node = next(n for n in _functions("routes_accounts_chart.py") if n.name == "reset_accounts_chart")
    args = [a.arg for a in node.args.args]
    assert "request" in args, "the chart-of-accounts reset must receive the Request to be authorizable"
    assert "confirm" in args


# ------------------------------------------------------------ CLI fail-closed
@pytest.mark.parametrize("script", GUARDED_SCRIPTS)
def test_destructive_script_refuses_without_authorization(script):
    env = {k: v for k, v in os.environ.items() if k != destructive_guard.ENABLE_FLAG_ENV}
    result = subprocess.run(
        [sys.executable, script],
        cwd=str(BACKEND_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    combined = result.stdout + result.stderr
    assert "REFUSED" in combined, f"{script} did not refuse: {combined[-400:]}"
    assert "Nothing was touched" in combined


@pytest.mark.parametrize("script", GUARDED_SCRIPTS)
def test_destructive_script_invokes_the_cli_guard(script):
    source = (BACKEND_DIR / script).read_text(encoding="utf-8")
    assert "require_destructive_cli" in source


def test_cli_guard_requires_flag_then_db_then_explicit_argument(monkeypatch):
    monkeypatch.delenv(destructive_guard.ENABLE_FLAG_ENV, raising=False)
    with pytest.raises(SystemExit) as exc:
        destructive_guard.require_destructive_cli("x", argv=[destructive_guard.CLI_CONFIRM_ARG])
    assert "disabled" in str(exc.value)

    monkeypatch.setenv(destructive_guard.ENABLE_FLAG_ENV, "true")
    monkeypatch.setenv("DB_NAME", "db1")
    monkeypatch.delenv(destructive_guard.ALLOWED_DB_ENV, raising=False)
    with pytest.raises(SystemExit) as exc:
        destructive_guard.require_destructive_cli("x", argv=[destructive_guard.CLI_CONFIRM_ARG])
    assert "not authorized" in str(exc.value)

    monkeypatch.setenv(destructive_guard.ALLOWED_DB_ENV, "db1")
    with pytest.raises(SystemExit) as exc:
        destructive_guard.require_destructive_cli("x", argv=[])
    assert destructive_guard.CLI_CONFIRM_ARG in str(exc.value)

    # all three satisfied -> returns without raising
    destructive_guard.require_destructive_cli("x", argv=[destructive_guard.CLI_CONFIRM_ARG])


def test_runtime_store_clear_all_is_fail_closed(monkeypatch):
    from core import runtime_store

    monkeypatch.delenv(destructive_guard.ENABLE_FLAG_ENV, raising=False)
    calls = []
    monkeypatch.setattr(runtime_store, "_database", lambda: calls.append("db") or {})
    runtime_store.clear_all()
    assert calls == [], "clear_all touched the database with the enable flag absent"


# ------------------------------------------------- repository-wide final sweep
def test_no_unguarded_unfiltered_destructive_write_remains():
    """Every unfiltered destructive DB write must be guarded, benign, or unreachable."""
    allow = {
        # single-default / single-active invariants — not data loss
        ("routes_templates_extended.py", "update_many"),
        ("core/prompt_registry.py", "update_many"),
        # guarded routes
        ("routes_extended.py", "delete_many"),
        ("server.py", "update_many"),
        ("routes_accounts_chart.py", "delete"),
        # fail-closed CLI scripts
        ("clear_data.py", "delete_many"),
        ("clean_and_add_services.py", "delete_many"),
        ("adopt_unified_workflow_template.py", "delete_many"),
        ("reset_primary_invoice_template.py", "delete_many"),
        # fail-closed library helper
        ("core/runtime_store.py", "delete_many"),
    }

    unexpected = []
    for path in BACKEND_DIR.rglob("*.py"):
        rel = path.relative_to(BACKEND_DIR).as_posix()
        if rel.startswith("tests/") or rel.startswith("scripts/"):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if "delete_many({})" in text and (rel, "delete_many") not in allow:
            unexpected.append(f"{rel}: delete_many({{}})")
        if "update_many({}" in text and (rel, "update_many") not in allow:
            unexpected.append(f"{rel}: update_many({{}})")
        if 'delete().neq("id", "")' in text and (rel, "delete") not in allow:
            unexpected.append(f'{rel}: delete().neq("id", "")')

    assert not unexpected, "unguarded unfiltered destructive writes: " + "; ".join(unexpected)
