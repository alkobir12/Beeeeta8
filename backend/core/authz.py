"""
🔐 core/authz.py — Authorization SSOT (single enforcement model).

Phase 1B closure principles:
  - sensitive or mutating endpoints never fail open;
  - policy errors deny safely and are logged with a request_id;
  - every production writer is covered by an explicit central policy;
  - low-risk reads remain authenticated only, but are explicitly classified;
  - object-scoped self checks live in route helpers where route params are known.
"""
from __future__ import annotations

import re
import uuid
from typing import Dict, List, Optional, Tuple

from core.rbac import get_role_permissions, APPROVER_ROLES
from core.log_utils import get_logger

_log = get_logger("authz")

_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_READ_METHODS = {"GET", "HEAD"}

_USERS_ACTIONS = {"GET": "view", "POST": "create", "PUT": "edit", "PATCH": "edit", "DELETE": "delete"}
_CRUD_ACTIONS = {"POST": "create", "PUT": "edit", "PATCH": "edit", "DELETE": "delete"}
_CRUD_WITH_READ = {**_CRUD_ACTIONS, "GET": "view", "HEAD": "view"}
_EDIT_OR_DELETE = {"POST": "edit", "PUT": "edit", "PATCH": "edit", "DELETE": "delete"}
_EDIT_READ = {"GET": "view", "HEAD": "view", "POST": "edit", "PUT": "edit", "PATCH": "edit", "DELETE": "delete"}
_ADMIN_ROLES = {"admin"}


def _normalize_path(path: str) -> str:
    p = str(path or "").split("?", 1)[0]
    if p == "/api" or p.startswith("/api/"):
        return p
    if p.startswith("/"):
        return "/api" + p
    return "/api/" + p


def _role_can(role: Optional[str], module: str, action: str) -> bool:
    perms = get_role_permissions((role or "").lower())
    return bool((perms.get(module) or {}).get(action) is True)


def _method_action(method: str, mapping: Dict[str, str]) -> Optional[str]:
    return mapping.get(str(method or "").upper())


def _financial_read(role: Optional[str]) -> bool:
    return any(
        _role_can(role, module, action)
        for module, action in (
            ("journal_entries", "view"),
            ("reports", "view"),
            ("debts", "view"),
        )
    )


def _vehicle_access(role: Optional[str]) -> bool:
    return _role_can(role, "vehicles", "view") or _role_can(role, "archive", "view")


def _role_from_payload(payload: Optional[dict]) -> Optional[str]:
    if not isinstance(payload, dict):
        return None
    role = payload.get("role") or payload.get("r") or ""
    role = str(role).strip().lower()
    return role or None


def _denied(reason: str, rule: str, role: Optional[str], *, request_id: Optional[str] = None) -> Dict:
    return {
        "error": "authorization_denied",
        "msg": reason,
        "rule": rule,
        "role": role or "unknown",
        "request_id": request_id,
    }


# kind values:
#   perm             → spec=(module, method_action_map)
#   fixed_perm       → spec=(module, action)
#   any_perm         → spec=[(module, action), ...]
#   all_perm         → spec=[(module, action), ...]
#   role             → spec=set(roles)
#   authenticated    → any authenticated actor; no business privilege grant
#   financial_read   → journal_entries.view OR reports.view OR debts.view
#   vehicle_access   → vehicles.view OR archive.view
#   deny             → explicit temporary deny/admin review boundary
_RAW_RULES: List[Tuple[str, set, str, str, object, bool, str]] = [
    ("auth_audit_read", _READ_METHODS, r"^/api/auth/audit$", "role", set(APPROVER_ROLES), True, "ROLE_RESTRICTED_READ"),
    ("auth_self_service", {"GET", "POST"}, r"^/api/auth/(me|sessions|sessions/revoke|set-pin|set-password)$", "authenticated", None, False, "SELF_ONLY_READ"),

    ("users_manage", {"GET", "POST", "PUT", "PATCH", "DELETE"}, r"^/api/users(/|$)", "perm", ("users", _USERS_ACTIONS), True, "AUTHZ_COMPLETE"),

    ("payroll_admin_only", {"GET", "POST", "PUT", "PATCH", "DELETE"}, r"^/api/(salaries|salary-records|employee-performance)(/|$)", "role", _ADMIN_ROLES, True, "AUTHZ_COMPLETE"),

    ("financial_maintenance_admin_only", _MUTATING_METHODS, r"^/api/finance/(ar-repair|ar/migrate|audit-system|reports/(apply|migrate|reclassify|repost|reconciliation/backfill)|reset|reset-all-data|reset-ops)", "role", _ADMIN_ROLES, True, "AUTHZ_COMPLETE"),
    ("destructive_admin", _MUTATING_METHODS, r"^/api/(?:[^?]*/)?(financial-reset|reset-financial|reset|cleanup|purge|wipe|danger)(?:/|-|$)", "role", _ADMIN_ROLES, True, "AUTHZ_COMPLETE"),
    ("admin_namespace_writes", _MUTATING_METHODS, r"^/api/admin(/|$)", "role", _ADMIN_ROLES, True, "AUTHZ_COMPLETE"),

    ("accounts_write_admin_only", _MUTATING_METHODS, r"^/api/(accounts|accounts-chart)(/|$|[^a-zA-Z0-9_-])", "role", _ADMIN_ROLES, True, "AUTHZ_COMPLETE"),
    ("accounts_read_financial", _READ_METHODS, r"^/api/(accounts|accounts-chart)(/|$|[^a-zA-Z0-9_-])", "financial_read", None, True, "PERMISSION_RESTRICTED_READ"),

    ("settings_write", _MUTATING_METHODS, r"^/api/(settings|workshop-config)(/|$)", "perm", ("settings", {"POST": "edit", "PUT": "edit", "PATCH": "edit", "DELETE": "edit"}), False, "AUTHZ_COMPLETE"),
    ("settings_read", _READ_METHODS, r"^/api/(settings|workshop-config)(/|$)", "perm", ("settings", {"GET": "view", "HEAD": "view"}), False, "PERMISSION_RESTRICTED_READ"),
    ("profile_self_write", {"PUT", "POST"}, r"^/api/profile(/upload-logo)?$", "authenticated", None, True, "AUTHZ_COMPLETE"),
    ("profile_self_read", _READ_METHODS, r"^/api/profile$", "authenticated", None, False, "SELF_ONLY_READ"),
    ("user_layout_self_scope", {"GET", "PUT"}, r"^/api/user-layouts/[^/]+/[^/]+$", "authenticated", None, True, "AUTHZ_COMPLETE"),

    ("runtime_approver_scope", {"GET", "POST", "PUT", "PATCH", "DELETE"}, r"^/api/runtime/(approvals|audit|db|drafts|executions|report|stats|approve|commit|rollback)(/|$)", "role", set(APPROVER_ROLES), True, "AUTHZ_COMPLETE"),
    ("runtime_target_scoped", {"POST"}, r"^/api/runtime/(execute|power|intent/(parse|execute))$", "authenticated", None, True, "AUTHZ_COMPLETE"),
    ("runtime_vehicle_read", _READ_METHODS, r"^/api/runtime/visits/active$", "vehicle_access", None, False, "PERMISSION_RESTRICTED_READ"),

    ("finance_bot_evidence", {"POST"}, r"^/api/finance-bot/evidence/upload$", "all_perm", [("journal_entries", "view"), ("vehicles", "view")], True, "AUTHZ_COMPLETE"),
    ("finance_bot_autolink", {"POST"}, r"^/api/finance-bot/auto-link$", "financial_read", None, True, "AUTHZ_COMPLETE"),
    ("finance_bot_read_tools", {"GET", "POST"}, r"^/api/finance-bot(/|$)", "financial_read", None, True, "AUTHZ_COMPLETE"),

    ("vehicle_files_access", {"GET", "POST"}, r"^/api/vehicles/[^/]+/(files|upload-file)(/|$)", "vehicle_access", None, True, "AUTHZ_COMPLETE"),
    ("vehicle_diagnostics_access", {"POST"}, r"^/api/vehicles/compare-diagnostics$", "vehicle_access", None, True, "AUTHZ_COMPLETE"),
    ("references_import_admin_only", {"POST"}, r"^/api/references/import-file$", "role", _ADMIN_ROLES, True, "AUTHZ_COMPLETE"),

    ("notifications_prepare_admin_only", {"POST"}, r"^/api/notifications/prepare$", "role", _ADMIN_ROLES, True, "AUTHZ_COMPLETE"),
    ("approvals_public_intentional", {"GET", "POST"}, r"^/api/approvals/public/", "authenticated", None, False, "PUBLIC_INTENTIONAL"),
    ("approvals_workshop_read", _READ_METHODS, r"^/api/(approvals|customers/[^/]+/approval-logs|vehicles/[^/]+/approval-logs)(/|$)", "vehicle_access", None, True, "PERMISSION_RESTRICTED_READ"),
    ("approvals_workshop_write", _MUTATING_METHODS, r"^/api/approvals(/|$)", "any_perm", [("vehicles", "edit"), ("invoices", "create")], True, "AUTHZ_COMPLETE"),

    ("financial_control_read", _READ_METHODS, r"^/api/financial-control(/|$)", "role", set(APPROVER_ROLES), True, "ROLE_RESTRICTED_READ"),
    ("fincontrol_write", _MUTATING_METHODS, r"^/api/financial-control(/|$)", "role", set(APPROVER_ROLES), True, "AUTHZ_COMPLETE"),
    ("firewall_read", _READ_METHODS, r"^/api/firewall(/|$)", "financial_read", None, True, "PERMISSION_RESTRICTED_READ"),
    ("firewall_write", _MUTATING_METHODS, r"^/api/firewall(/|$)", "role", set(APPROVER_ROLES), True, "AUTHZ_COMPLETE"),

    ("finance_read", _READ_METHODS, r"^/api/(finance|financial-reset|finance-actions)(/|$)", "financial_read", None, True, "PERMISSION_RESTRICTED_READ"),
    ("ledger_write", _MUTATING_METHODS, r"^/api/(finance/|accounting/|smart-accounting|finance-actions/)", "perm", ("journal_entries", _EDIT_OR_DELETE), True, "AUTHZ_COMPLETE"),
    ("invoices_write", _MUTATING_METHODS, r"^/api/invoices(/|$)", "perm", ("invoices", _CRUD_ACTIONS), False, "AUTHZ_COMPLETE"),
    ("invoices_read", _READ_METHODS, r"^/api/invoices(/|$)", "perm", ("invoices", {"GET": "view", "HEAD": "view"}), False, "PERMISSION_RESTRICTED_READ"),

    ("operations_integrity_admin", _MUTATING_METHODS, r"^/api/operations/integrity/", "role", _ADMIN_ROLES, True, "AUTHZ_COMPLETE"),
    ("finance_engine_payment_confirm", {"POST"}, r"^/api/finance-engine/visits/[^/]+/payments/confirm$", "fixed_perm", ("operations", "settle"), True, "AUTHZ_COMPLETE"),
    ("operations_write", _MUTATING_METHODS, r"^/api/(operations|finance-engine)(/|$)", "perm", ("operations", _EDIT_OR_DELETE), False, "AUTHZ_COMPLETE"),
    ("operations_read", _READ_METHODS, r"^/api/(operations|transactions)(/|$)", "perm", ("operations", {"GET": "view", "HEAD": "view"}), False, "PERMISSION_RESTRICTED_READ"),
    ("vehicles_write", _MUTATING_METHODS, r"^/api/vehicles(/|$)", "perm", ("vehicles", _CRUD_ACTIONS), False, "AUTHZ_COMPLETE"),
    ("vehicles_read", _READ_METHODS, r"^/api/vehicles(/|$)", "vehicle_access", None, False, "PERMISSION_RESTRICTED_READ"),
    ("customers_write", _MUTATING_METHODS, r"^/api/customers(/|$)", "perm", ("customers", _CRUD_ACTIONS), False, "AUTHZ_COMPLETE"),
    ("customers_read", _READ_METHODS, r"^/api/customers(/|$)", "perm", ("customers", {"GET": "view", "HEAD": "view"}), False, "PERMISSION_RESTRICTED_READ"),
    ("suppliers_write", _MUTATING_METHODS, r"^/api/suppliers(/|$)", "role", _ADMIN_ROLES, True, "AUTHZ_COMPLETE"),
    ("suppliers_read", _READ_METHODS, r"^/api/suppliers(/|$)", "any_perm", [("inventory", "view"), ("journal_entries", "view")], False, "PERMISSION_RESTRICTED_READ"),
    ("suppliers_ext_write", _MUTATING_METHODS, r"^/api/suppliers-ext(/|$)", "perm", ("journal_entries", _EDIT_OR_DELETE), True, "AUTHZ_COMPLETE"),
    ("suppliers_ext_read", _READ_METHODS, r"^/api/suppliers-ext(/|$)", "financial_read", None, True, "PERMISSION_RESTRICTED_READ"),
    ("inventory_write", _MUTATING_METHODS, r"^/api/(parts|smart-inventory|inventory|services|workshop-services|products|service-packages)(/|$)", "perm", ("inventory", _CRUD_ACTIONS), False, "AUTHZ_COMPLETE"),
    ("inventory_read", _READ_METHODS, r"^/api/(parts|smart-inventory|inventory|services|workshop-services|products|service-packages)(/|$)", "perm", ("inventory", {"GET": "view", "HEAD": "view"}), False, "PERMISSION_RESTRICTED_READ"),
    ("technicians_write", _MUTATING_METHODS, r"^/api/technicians(/|$)", "perm", ("work_orders", _CRUD_ACTIONS), False, "AUTHZ_COMPLETE"),
    ("technicians_read", _READ_METHODS, r"^/api/(technicians|employees)(/|$)", "perm", ("work_orders", {"GET": "view", "HEAD": "view"}), False, "PERMISSION_RESTRICTED_READ"),

    ("document_templates_write", _MUTATING_METHODS, r"^/api/(document-templates|templates|outbound)(/|$)", "perm", ("settings", {"POST": "edit", "PUT": "edit", "PATCH": "edit", "DELETE": "edit"}), False, "AUTHZ_COMPLETE"),
    ("document_templates_read", _READ_METHODS, r"^/api/(document-templates|templates|outbound)(/|$)", "perm", ("settings", {"GET": "view", "HEAD": "view"}), False, "PERMISSION_RESTRICTED_READ"),
    ("imports_admin_only", _MUTATING_METHODS, r"^/api/import(/|$)", "role", _ADMIN_ROLES, True, "AUTHZ_COMPLETE"),

    ("assistant_admin_prompts", _MUTATING_METHODS, r"^/api/assistant/prompt/", "role", _ADMIN_ROLES, True, "AUTHZ_COMPLETE"),
    ("assistant_sensitive_reads", _READ_METHODS, r"^/api/assistant/(audit|memory|prompt|report|stats)(/|$)", "role", set(APPROVER_ROLES), True, "ROLE_RESTRICTED_READ"),
    ("assistant_tool_runtime", _MUTATING_METHODS, r"^/api/assistant/(tool|power|brain|memory)(/|$)", "authenticated", None, True, "AUTHZ_COMPLETE"),
    ("assistant_chat_authenticated", {"GET", "POST"}, r"^/api/assistant(/|$)", "authenticated", None, False, "GENERAL_AUTHENTICATED_READ"),
    ("knowledge_admin_write", _MUTATING_METHODS, r"^/api/(ai/kb|faults|injectors|dtc)(/|$)", "role", _ADMIN_ROLES, True, "AUTHZ_COMPLETE"),
    ("ai_sensitive", {"GET", "POST"}, r"^/api/(ai|search|gemini-chat|diesel-chat|diesel-expert|alkabeer-bot)(/|$)", "authenticated", None, False, "GENERAL_AUTHENTICATED_READ"),
    ("knowledge_read", _READ_METHODS, r"^/api/(ai/kb|faults|injectors|dtc|toyota|maintenance|notion)(/|$)", "authenticated", None, False, "GENERAL_AUTHENTICATED_READ"),
    ("traces_read_admin", _READ_METHODS, r"^/api/(traces|llm-traces)(/|$)", "role", _ADMIN_ROLES, True, "ROLE_RESTRICTED_READ"),
    ("traces_write_admin", _MUTATING_METHODS, r"^/api/(traces|llm-traces)(/|$)", "role", _ADMIN_ROLES, True, "AUTHZ_COMPLETE"),

    ("analytics_read_financial", _READ_METHODS, r"^/api/(analytics|analytics-advanced|ceo)(/|$)", "financial_read", None, True, "PERMISSION_RESTRICTED_READ"),
    ("advanced_write_admin", _MUTATING_METHODS, r"^/api/(faq|feedback|shop-orders|tickets|ai-bots|ai-recommendations)(/|$)", "role", _ADMIN_ROLES, True, "AUTHZ_COMPLETE"),
    ("advanced_read_authenticated", _READ_METHODS, r"^/api/(faq|feedback|shop-orders|tickets|ai-bots|ai-recommendations)(/|$)", "authenticated", None, False, "GENERAL_AUTHENTICATED_READ"),
    ("language_read", _READ_METHODS, r"^/api/translations(/|$)", "authenticated", None, False, "GENERAL_AUTHENTICATED_READ"),
    ("quotations_write", _MUTATING_METHODS, r"^/api/quotations(/|$)", "any_perm", [("invoices", "create"), ("vehicles", "edit")], False, "AUTHZ_COMPLETE"),
    ("quotations_read", _READ_METHODS, r"^/api/quotations(/|$)", "authenticated", None, False, "GENERAL_AUTHENTICATED_READ"),
    ("documents_generate", _MUTATING_METHODS, r"^/api/documents(/|$)", "any_perm", [("invoices", "create"), ("vehicles", "view")], False, "AUTHZ_COMPLETE"),
    ("stitch_authenticated", {"GET", "POST", "PUT", "PATCH", "DELETE"}, r"^/api/stitch(/|$)", "authenticated", None, False, "GENERAL_AUTHENTICATED_READ"),
]

_GENERAL_READ_RULE = ("general_authenticated_read", _READ_METHODS, re.compile(r"^/api/"), "authenticated", None, False, "GENERAL_AUTHENTICATED_READ")
_DEFAULT_MUTATING_RULE = ("unclassified_mutating_admin_review", _MUTATING_METHODS, re.compile(r"^/api/"), "role", _ADMIN_ROLES, True, "AUTHZ_COMPLETE")

_RULES = [(n, ms, re.compile(rx), kind, spec, crit, cls) for (n, ms, rx, kind, spec, crit, cls) in _RAW_RULES]


def match_rule(path: str, method: str):
    method = str(method or "").upper()
    norm = _normalize_path(path)
    for name, methods, rx, kind, spec, crit, classification in _RULES:
        if method in methods and rx.search(norm):
            return {"name": name, "kind": kind, "spec": spec, "critical": crit, "classification": classification, "path": norm}
    if method in _READ_METHODS and norm.startswith("/api/"):
        name, methods, rx, kind, spec, crit, classification = _GENERAL_READ_RULE
        return {"name": name, "kind": kind, "spec": spec, "critical": crit, "classification": classification, "path": norm}
    if method in _MUTATING_METHODS and norm.startswith("/api/"):
        name, methods, rx, kind, spec, crit, classification = _DEFAULT_MUTATING_RULE
        return {"name": name, "kind": kind, "spec": spec, "critical": crit, "classification": classification, "path": norm}
    return None


def classify(path: str, method: str) -> str:
    rule = match_rule(path, method)
    if not rule:
        return "PUBLIC_INTENTIONAL" if not _normalize_path(path).startswith("/api/") else "SENSITIVE_READ_REQUIRES_POLICY"
    return str(rule.get("classification") or "AUTHZ_COMPLETE")


def _eval_rule(rule: Dict, method: str, role: Optional[str]) -> Optional[Dict]:
    if rule["kind"] == "authenticated":
        if role:
            return None
        return _denied("يتطلب مستخدماً موثق الدور", rule["name"], role)
    if not role:
        return _denied("هوية بلا دور موثوق", rule["name"], role)
    if rule["kind"] == "role":
        if role in rule["spec"]:
            return None
        return _denied(f"الدور '{role}' غير مخوّل لهذا الإجراء", rule["name"], role)
    if rule["kind"] == "financial_read":
        if _financial_read(role):
            return None
        return _denied(f"الدور '{role}' لا يملك صلاحية قراءة مالية", rule["name"], role)
    if rule["kind"] == "vehicle_access":
        if _vehicle_access(role):
            return None
        return _denied(f"الدور '{role}' لا يملك صلاحية وصول للمركبات", rule["name"], role)
    if rule["kind"] == "fixed_perm":
        module, action = rule["spec"]
        if _role_can(role, module, action):
            return None
        return _denied(f"الدور '{role}' لا يملك صلاحية {module}.{action}", rule["name"], role)
    if rule["kind"] == "any_perm":
        if any(_role_can(role, m, a) for m, a in rule["spec"]):
            return None
        needed = " أو ".join(f"{m}.{a}" for m, a in rule["spec"])
        return _denied(f"الدور '{role}' لا يملك أي صلاحية من: {needed}", rule["name"], role)
    if rule["kind"] == "all_perm":
        missing = [(m, a) for m, a in rule["spec"] if not _role_can(role, m, a)]
        if not missing:
            return None
        needed = " و ".join(f"{m}.{a}" for m, a in missing)
        return _denied(f"الدور '{role}' لا يملك الصلاحيات المطلوبة: {needed}", rule["name"], role)
    if rule["kind"] == "deny":
        return _denied("هذا المسار محظور حتى تُثبت سياسة عمل آمنة له", rule["name"], role)
    if rule["kind"] == "perm":
        module, action_map = rule["spec"]
        action = _method_action(method, action_map)
        if action is None:
            return _denied("تكوين سياسة غير مكتمل لهذا الأسلوب", rule["name"], role)
        if _role_can(role, module, action):
            return None
        return _denied(f"الدور '{role}' لا يملك صلاحية {module}.{action}", rule["name"], role)
    return _denied("نوع سياسة غير معروف", rule["name"], role)


def evaluate(path: str, method: str, payload: Optional[dict], *, request_id: Optional[str] = None) -> Optional[Dict]:
    rule = match_rule(path, method)
    role = _role_from_payload(payload)
    if not rule:
        return _denied("لا توجد سياسة تفويض صريحة لهذا المسار", "missing_policy", role, request_id=request_id)
    denial = _eval_rule(rule, str(method or "").upper(), role)
    if denial is not None and request_id:
        denial["request_id"] = request_id
    return denial


def enforce_or_none(path: str, method: str, payload: Optional[dict], *, request_id: Optional[str] = None) -> Optional[Dict]:
    rid = request_id or str(uuid.uuid4())
    try:
        denial = evaluate(path, method, payload, request_id=rid)
    except Exception as exc:  # pragma: no cover
        norm = _normalize_path(path)
        _log.exception("AUTHZ_FAIL_CLOSED request_id=%s method=%s path=%s error=%s", rid, method, norm, str(exc)[:160])
        return _denied("تعذر تقييم سياسة التفويض بأمان", "authz_exception_fail_closed", _role_from_payload(payload), request_id=rid)
    if denial is not None:
        _log.warning("AUTHZ_DENY request_id=%s %s %s role=%s rule=%s", rid, method, _normalize_path(path), denial.get("role"), denial.get("rule"))
    return denial


async def resolve_request_actor(request):
    from core import rbac
    ident = rbac.extract_identity(request)
    return await rbac.resolve_actor(user_id=ident.get("user_id"), name=ident.get("name"), role_hint=ident.get("role_hint"))


def ensure_self_actor(actor, target_user_id: str) -> None:
    candidates = {str(actor.id or "").strip(), str(actor.name or "").strip()}
    if str(target_user_id or "").strip() not in candidates:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail={"error": "self_scope_required", "msg": "هذا المورد ذاتي ولا يمكن تعديله لمستخدم آخر"})


RUNTIME_ACTION_PERMISSION_MAP = {
    "customer": ("customers", "create"),
    "create_customer": ("customers", "create"),
    "update_customer": ("customers", "edit"),
    "delete_customer": ("customers", "delete"),
    "vehicle": ("vehicles", "create"),
    "create_vehicle": ("vehicles", "create"),
    "update_vehicle": ("vehicles", "edit"),
    "delete_vehicle": ("vehicles", "delete"),
    "visit": ("work_orders", "create"),
    "create_visit": ("work_orders", "create"),
    "update_visit": ("work_orders", "edit"),
    "close_visits": ("vehicles", "edit"),
    "payment": ("operations", "settle"),
    "external_operation_payment": ("operations", "settle"),
    "invoice": ("invoices", "create"),
    "external_operation": ("operations", "edit"),
    "delete_operation": ("operations", "delete"),
    "expense": ("journal_entries", "create"),
    "purchase": ("journal_entries", "create"),
    "reverse": ("journal_entries", "delete"),
    "get_active_visits": ("vehicles", "view"),
}
_RUNTIME_ADMIN_ONLY = {"supplier", "memory_promote"}


def runtime_required_permission(action_name: Optional[str]) -> Optional[Tuple[str, str]]:
    action = str(action_name or "").strip().lower()
    return RUNTIME_ACTION_PERMISSION_MAP.get(action)


def runtime_authorized(actor, action_name: Optional[str]) -> bool:
    action = str(action_name or "").strip().lower()
    if action in _RUNTIME_ADMIN_ONLY:
        return getattr(actor, "role", "") == "admin"
    perm = runtime_required_permission(action)
    if not perm:
        return False
    module, operation = perm
    return bool(actor.can(module, operation))


def require_runtime_target_permission(actor, action_name: Optional[str]) -> None:
    from fastapi import HTTPException
    if runtime_authorized(actor, action_name):
        return
    action = str(action_name or "").strip().lower() or "unknown"
    perm = runtime_required_permission(action)
    required = "admin" if action in _RUNTIME_ADMIN_ONLY else (f"{perm[0]}.{perm[1]}" if perm else "target_action_resolved")
    raise HTTPException(status_code=403, detail={"error": "runtime_target_authorization_denied", "action": action, "required": required, "msg": "لا يمكن استخدام Runtime كتجاوز لصلاحيات الإجراء الهدف"})