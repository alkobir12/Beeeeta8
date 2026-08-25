"""
🔐 core/authz.py — Authorization SSOT (single enforcement model).

Unifies the existing rbac.py primitives (role→permission map from
config/role_permissions.json) into ONE central policy that is enforced at a
single point (the ASGI security middleware) plus object-level helpers for the
few endpoints that address a specific resource (users self-or-admin).

Design:
  REQUEST → AUTHENTICATION (auth_guard) → ACTOR (role from signed JWT)
          → POLICY (this module) → [permission | role | object-level]
          → route/business service.

Rules are grounded ONLY in real business roles/permissions. Endpoints whose
correct policy is not unambiguous are NOT force-denied here — they are reported
as POLICY_DECISION_REQUIRED by the static re-audit. Unlisted paths keep the
prior behaviour (authenticated-only) to avoid breaking working flows.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from core.rbac import get_role_permissions, APPROVER_ROLES
from core.log_utils import get_logger

_log = get_logger("authz")

# ─────────────────────────── permission helper ───────────────────────────
def _role_can(role: Optional[str], module: str, action: str) -> bool:
    perms = get_role_permissions((role or "").lower())
    return bool((perms.get(module) or {}).get(action) is True)


def _method_action(method: str, mapping: Dict[str, str]) -> Optional[str]:
    return mapping.get(method)


# CRUD action maps grounded in role_permissions.json actions
_USERS_ACTIONS = {"GET": "view", "POST": "create", "PUT": "edit", "PATCH": "edit", "DELETE": "delete"}
_CRUD_ACTIONS = {"POST": "create", "PUT": "edit", "PATCH": "edit", "DELETE": "delete"}
_EDIT_OR_DELETE = {"POST": "edit", "PUT": "edit", "PATCH": "edit", "DELETE": "delete"}

# ─────────────────────────── central policy registry ─────────────────────
# Each rule: (name, methods, compiled_regex, kind, spec, critical)
#   kind="perm" → spec=(module, action_map)  → require permission[module][action]
#   kind="role" → spec=set(roles)            → require actor.role in roles
# First matching rule wins. Only CONFIDENT, business-grounded rules are enforced.
_RAW_RULES: List[Tuple[str, set, str, str, object, bool]] = [
    # P0 — user/role/permission management (only 'users' permission holders)
    ("users_manage", {"GET", "POST", "PUT", "PATCH", "DELETE"},
     r"^/api/users(/|$)", "perm", ("users", _USERS_ACTIONS), True),

    # Destructive / admin-only maintenance (reset, cleanup, purge, wipe, danger)
    ("destructive_admin", {"POST", "PUT", "PATCH", "DELETE"},
     r"^/api/(?:[^?]*/)?(financial-reset|reset-financial|reset|cleanup|purge|wipe|danger)(?:/|-|$)", "role", {"admin"}, True),

    # Settings mutations
    ("settings_write", {"POST", "PUT", "PATCH", "DELETE"},
     r"^/api/(settings|workshop-config)(/|$)", "perm", ("settings", {"POST": "edit", "PUT": "edit", "PATCH": "edit", "DELETE": "edit"}), False),

    # Invoices mutations
    ("invoices_write", {"POST", "PUT", "PATCH", "DELETE"},
     r"^/api/invoices(/|$)", "perm", ("invoices", _CRUD_ACTIONS), False),

    # Operations / finance-engine mutations (reception & technician keep 'edit')
    ("operations_write", {"POST", "PUT", "PATCH", "DELETE"},
     r"^/api/(operations|finance-engine)(/|$)", "perm", ("operations", _EDIT_OR_DELETE), False),

    # Financial-control (findings / control approvals) mutations → approver roles
    ("fincontrol_write", {"POST", "PUT", "PATCH", "DELETE"},
     r"^/api/financial-control(/|$)", "role", set(APPROVER_ROLES), False),

    # Core ledger / accounting mutations (accountant keeps create/edit; delete=admin)
    ("ledger_write", {"POST", "PUT", "PATCH", "DELETE"},
     r"^/api/(finance/|accounting/|accounts/|accounts-ext|accounts-chart|smart-accounting|chart-of-accounts)", "perm", ("journal_entries", _EDIT_OR_DELETE), False),

    # Supplier settlements / transactions (payables) → treated as ledger edit
    ("suppliers_settle", {"POST", "PUT", "PATCH", "DELETE"},
     r"^/api/suppliers-ext/[^/]+/(settlements|transactions)", "perm", ("journal_entries", {"POST": "edit", "PUT": "edit", "PATCH": "edit", "DELETE": "edit"}), False),
]

_RULES = [(n, ms, re.compile(rx), kind, spec, crit) for (n, ms, rx, kind, spec, crit) in _RAW_RULES]


def match_rule(path: str, method: str):
    for name, methods, rx, kind, spec, crit in _RULES:
        if method in methods and rx.search(path):
            return {"name": name, "kind": kind, "spec": spec, "critical": crit}
    return None


def _denied(reason: str, rule: str, role: Optional[str]) -> Dict:
    return {"error": "authorization_denied", "msg": reason, "rule": rule, "role": role or "unknown"}


def evaluate(path: str, method: str, payload: Optional[dict]) -> Optional[Dict]:
    """Return a denial dict if the actor (from JWT payload) is NOT authorized for
    a matched policy rule; otherwise None (allowed / no rule)."""
    rule = match_rule(path, method)
    if not rule:
        return None
    role = None
    if isinstance(payload, dict):
        role = (payload.get("role") or payload.get("r") or "")
        role = str(role).lower() or None
    # No role on token: fail-closed for CRITICAL rules only; allow others (avoid mass lockout)
    if not role:
        if rule["critical"]:
            return _denied("هوية بلا دور موثوق", rule["name"], role)
        _log.warning("authz: no role on token for %s %s (rule=%s) — allowed non-critical", method, path, rule["name"])
        return None
    if rule["kind"] == "role":
        if role in rule["spec"]:
            return None
        return _denied(f"الدور '{role}' غير مخوّل لهذا الإجراء", rule["name"], role)
    # perm
    module, action_map = rule["spec"]
    action = _method_action(method, action_map)
    if action is None:
        return None
    if _role_can(role, module, action):
        return None
    return _denied(f"الدور '{role}' لا يملك صلاحية {module}.{action}", rule["name"], role)


def enforce_or_none(path: str, method: str, payload: Optional[dict]) -> Optional[Dict]:
    """Middleware entry point. Defensive: internal errors fail-open (never take
    the app down) but real policy denials fail-closed."""
    try:
        denial = evaluate(path, method, payload)
    except Exception as exc:  # pragma: no cover
        _log.error("authz.enforce internal error on %s %s: %s", method, path, str(exc)[:120])
        return None
    if denial is not None:
        _log.warning("AUTHZ_DENY %s %s role=%s rule=%s", method, path, denial.get("role"), denial.get("rule"))
    return denial


# ─────────────────────── object-level helpers (routes) ───────────────────
async def resolve_request_actor(request):
    """Full actor (incl. per-user permission overrides) for explicit route checks."""
    from core import rbac
    ident = rbac.extract_identity(request)
    return await rbac.resolve_actor(user_id=ident.get("user_id"), name=ident.get("name"),
                                    role_hint=ident.get("role_hint"))
