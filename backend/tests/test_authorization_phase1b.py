"""Phase 1B authorization regression tests (unit/non-destructive)."""
import sys

sys.path.insert(0, "/app/backend")

from fastapi import HTTPException

import auth_guard
from core import authz
from core.rbac import Actor, get_role_permissions
from routes_workshop_config import _allowlisted, _PROFILE_WRITABLE_FIELDS


def _assert(cond, msg):
    if not cond:
        raise AssertionError(msg)


def payload(role):
    return {"role": role, "sub": f"test-{role}"}


def actor(role, user_id="u1", name="user-one"):
    return Actor(
        user_id=user_id,
        name=name,
        role=role,
        permissions=get_role_permissions(role),
        found=True,
        active=True,
    )


def test_authz_internal_exception_denies():
    original = authz.evaluate
    try:
        def boom(*args, **kwargs):
            raise RuntimeError("forced-policy-error")
        authz.evaluate = boom
        denial = authz.enforce_or_none("/api/users", "GET", payload("admin"), request_id="rid-test")
        _assert(denial is not None, "authz engine exception must fail closed")
        _assert(denial["rule"] == "authz_exception_fail_closed", "exception denial rule must be explicit")
        _assert(denial["request_id"] == "rid-test", "request_id must be preserved in denial")
    finally:
        authz.evaluate = original


def test_missing_sensitive_policy_denies():
    original = authz.match_rule
    try:
        authz.match_rule = lambda path, method: None
        denial = authz.evaluate("/api/users", "GET", payload("admin"), request_id="rid-missing")
        _assert(denial is not None, "missing policy must deny")
        _assert(denial["rule"] == "missing_policy", "missing policy denial must be explicit")
    finally:
        authz.match_rule = original


def test_payroll_normal_user_denied():
    denial = authz.enforce_or_none("/api/salaries", "POST", payload("accountant"))
    _assert(denial is not None, "payroll mutation must deny normal financial user")


def test_runtime_cannot_bypass_target_permission():
    denied = False
    try:
        authz.require_runtime_target_permission(actor("technician"), "reverse")
    except HTTPException as exc:
        denied = exc.status_code == 403
    _assert(denied, "runtime reverse action must require target financial permission")


def test_finance_bot_prompt_cannot_grant_rights():
    denial = authz.enforce_or_none("/api/finance-bot/chat", "POST", payload("technician"))
    _assert(denial is not None, "finance-bot chat must require financial read access")


def test_profile_self_edit_allowed_and_privilege_injection_rejected():
    denial = authz.enforce_or_none("/api/profile", "PUT", payload("cashier"))
    _assert(denial is None, "profile self-service edit should be allowed for authenticated actor")
    clean = _allowlisted({"name": "ورشة", "email": "a@example.com"}, _PROFILE_WRITABLE_FIELDS, surface="profile")
    _assert(set(clean.keys()) == {"name", "email"}, "profile allowlist must keep safe fields")
    rejected = False
    try:
        _allowlisted({"name": "ورشة", "role": "admin", "permissions": {"users": {"delete": True}}}, _PROFILE_WRITABLE_FIELDS, surface="profile")
    except HTTPException as exc:
        rejected = exc.status_code == 422
    _assert(rejected, "profile privilege injection must be rejected")


def test_user_layout_cross_user_edit_denied():
    denied = False
    try:
        authz.ensure_self_actor(actor("cashier", user_id="u1", name="alice"), "u2")
    except HTTPException as exc:
        denied = exc.status_code == 403
    _assert(denied, "cross-user layout mutation must be denied")


def test_sensitive_get_denied_to_insufficient_role():
    denial = authz.enforce_or_none("/api/users", "GET", payload("viewer"))
    _assert(denial is not None, "users read must not be generic auth-only")
    denial = authz.enforce_or_none("/api/finance/reports/income-statement", "GET", payload("technician"))
    _assert(denial is not None, "financial report read must require financial access")


def test_public_endpoints_remain_public_intentional():
    _assert(auth_guard.is_public_path("/api/auth/login", "POST"), "login must remain public intentional")
    _assert(auth_guard.is_public_path("/api/approvals/public/abc", "GET"), "public approval verification must remain public intentional")


def test_admin_legitimate_flows_remain_functional():
    for path, method in [
        ("/api/users", "GET"),
        ("/api/users", "POST"),
        ("/api/accounts", "POST"),
        ("/api/salaries", "POST"),
        ("/api/settings", "POST"),
    ]:
        denial = authz.enforce_or_none(path, method, payload("admin"))
        _assert(denial is None, f"admin flow should remain authorized: {method} {path}: {denial}")


def run_all():
    tests = [name for name in sorted(globals()) if name.startswith("test_")]
    failures = []
    for name in tests:
        try:
            globals()[name]()
            print(f"✅ {name}")
        except Exception as exc:
            print(f"❌ {name}: {exc}")
            failures.append((name, exc))
    print(f"\nTOTAL={len(tests)} PASS={len(tests)-len(failures)} FAIL={len(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(run_all())