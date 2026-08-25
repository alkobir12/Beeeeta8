"""Security regression tests for the Authorization SSOT (core/authz).

Pure unit tests on the policy engine + user-guard helpers — no HTTP, no DB, no mutation.
Can run with either:
  - pytest /app/backend/tests/test_authz_ssot.py
  - python /app/backend/tests/test_authz_ssot.py
"""
import os
import sys

sys.path.insert(0, "/app/backend")
os.chdir("/app/backend")

from core import authz
from core.rbac import Actor, get_role_permissions
from routes_users import _actor_is_admin, _grants_privileged_perms


def _ev(path, method, role):
    return authz.evaluate(path, method, {"sub": "u", "role": role})


def test_users_privilege_escalation_blocked():
    assert _ev("/api/users/9", "DELETE", "technician") is not None
    assert _ev("/api/users/9", "PUT", "technician") is not None
    assert _ev("/api/users", "POST", "reception") is not None
    assert _ev("/api/users", "GET", "accountant") is not None
    assert _ev("/api/users", "GET", "manager") is None
    assert _ev("/api/users/9", "DELETE", "admin") is None
    assert authz.evaluate("/api/users/9", "DELETE", {"sub": "u"}) is not None


def test_destructive_admin_only():
    assert _ev("/api/financial-reset/run", "POST", "technician") is not None
    assert _ev("/api/financial-reset/run", "POST", "accountant") is not None
    assert _ev("/api/financial-reset/run", "POST", "admin") is None


def test_ledger_mutations_grounded_in_journal_permissions():
    assert _ev("/api/finance/post-x", "POST", "accountant") is None
    assert _ev("/api/finance/post-x", "POST", "technician") is not None
    assert _ev("/api/finance/post-x", "DELETE", "accountant") is not None
    assert _ev("/api/finance/post-x", "DELETE", "admin") is None


def test_operations_mutations():
    assert _ev("/api/operations/5", "PUT", "reception") is None
    assert _ev("/api/operations/5", "DELETE", "reception") is not None
    assert _ev("/api/operations/5", "PUT", "storekeeper") is not None


def test_invoices_and_settings():
    assert _ev("/api/invoices", "POST", "accountant") is None
    assert _ev("/api/invoices", "POST", "storekeeper") is not None
    assert _ev("/api/settings/x", "PUT", "manager") is not None
    assert _ev("/api/settings/x", "PUT", "admin") is None


def test_financial_control_requires_approver_roles():
    assert _ev("/api/financial-control/findings/scan", "POST", "accountant") is None
    assert _ev("/api/financial-control/findings/scan", "POST", "technician") is not None


def test_low_risk_reads_remain_explicitly_classified():
    assert _ev("/api/vehicles", "GET", "technician") is None
    assert _ev("/api/operations/5", "GET", "technician") is None
    assert _ev("/api/dashboard/kpis", "GET", "technician") is None
    assert authz.classify("/api/dashboard/kpis", "GET") == "GENERAL_AUTHENTICATED_READ"


def test_user_guard_helpers_for_privilege_and_mass_assignment():
    admin = Actor(user_id="a", name="a", role="admin", permissions=get_role_permissions("admin"), found=True)
    tech = Actor(user_id="t", name="t", role="technician", permissions=get_role_permissions("technician"), found=True)
    assert _actor_is_admin(admin) is True
    assert _actor_is_admin(tech) is False
    assert _grants_privileged_perms({"users": {"edit": True}}) is True
    assert _grants_privileged_perms({"settings": {"edit": True}}) is True
    assert _grants_privileged_perms({"vehicles": {"edit": True}}) is False


def _script_runner():
    tests = [name for name in sorted(globals()) if name.startswith("test_")]
    fails = []
    for name in tests:
        try:
            globals()[name]()
            print(f"PASS {name}")
        except Exception as exc:
            print(f"FAIL {name}: {exc}")
            fails.append(name)
    print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAILURES: {fails}"))
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(_script_runner())