"""
🔐 core/rbac.py — فرض الصلاحيات (RBAC) على الـbackend + مبدأ الأربع أعين

نموذج الهوية: تسجيل بالاسم فقط (بدون كلمة مرور/JWT بقرار المنتج). الهوية تصل عبر
الترويسات `x-user-id` / `x-user-role` أو حقول الجسم (approver/by/proposer)، وتُحلّ
الصلاحيات الفعلية من مخزن المستخدمين + خريطة الأدوار `config/role_permissions.json`.

يوفّر:
  • resolve_actor(...) — تحليل هوية الفاعل إلى {id, name, role, permissions}
  • check_permission(actor, module, action) → PermissionResult
  • require_permission(...) — يرفع HTTP 403 عند الرفض
  • can_approve(actor) — صلاحية اعتماد الإجراءات الحساسة (أدوار قابلة للضبط)
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from core.log_utils import get_logger

_log = get_logger("rbac")

_ROLE_FILE = Path(__file__).resolve().parent.parent / "config" / "role_permissions.json"
_ROLE_MAP: Optional[Dict[str, Any]] = None

# الأدوار المخوّلة باعتماد/تنفيذ الإجراءات الحساسة (قابلة للضبط عبر env)
APPROVER_ROLES = {
    r.strip().lower()
    for r in os.environ.get("RUNTIME_APPROVER_ROLES", "admin,manager,supervisor,accountant").split(",")
    if r.strip()
}


def _load_role_map() -> Dict[str, Any]:
    global _ROLE_MAP
    if _ROLE_MAP is not None:
        return _ROLE_MAP
    try:
        with _ROLE_FILE.open(encoding="utf-8") as f:
            _ROLE_MAP = (json.load(f) or {}).get("roles", {})
    except Exception as e:
        _log.warning("role map load failed: %s", str(e)[:80])
        _ROLE_MAP = {}
    return _ROLE_MAP


def get_role_permissions(role: str) -> Dict[str, Dict[str, bool]]:
    return (_load_role_map().get(str(role or "").lower(), {}) or {}).get("permissions", {})


def _merge_permissions(base: Dict[str, Any], overrides: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not overrides:
        return base
    merged = {m: dict(actions) for m, actions in (base or {}).items()}
    for module, mod_over in overrides.items():
        if not isinstance(mod_over, dict):
            continue
        merged.setdefault(module, {})
        for action, allowed in mod_over.items():
            merged[module][action] = bool(allowed)
    return merged


class PermissionResult:
    def __init__(self, allowed: bool, *, role: str = "", reason: str = ""):
        self.allowed = allowed
        self.role = role
        self.reason = reason

    def __bool__(self) -> bool:
        return self.allowed


class Actor:
    def __init__(self, *, user_id: str, name: str, role: str, permissions: Dict[str, Any], found: bool, active: bool = True):
        self.id = user_id
        self.name = name
        self.role = (role or "unknown").lower()
        self.permissions = permissions or {}
        self.found = found
        self.active = active

    def can(self, module: str, action: str) -> bool:
        return bool(self.permissions.get(module, {}).get(action) is True)

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "name": self.name, "role": self.role, "found": self.found}


async def _all_users() -> List[Dict[str, Any]]:
    try:
        import routes_users
        users = await routes_users.get_users()
        return [u.dict() if hasattr(u, "dict") else dict(u) for u in users]
    except Exception as e:
        _log.debug("users fetch failed: %s", str(e)[:80])
        try:
            import routes_users
            return routes_users._read_users()
        except Exception:
            return []


async def resolve_actor(
    *,
    user_id: Optional[str] = None,
    name: Optional[str] = None,
    role_hint: Optional[str] = None,
) -> Actor:
    """يحلّ هوية الفاعل إلى دور + صلاحيات فعلية من مخزن المستخدمين."""
    from core.arabic_nlp import arabic_match
    ident_id = str(user_id or "").strip()
    ident_name = str(name or "").strip()

    record: Optional[Dict[str, Any]] = None
    if ident_id or ident_name:
        for u in await _all_users():
            uid = str(u.get("id") or "")
            uname = u.get("name") or ""
            if ident_id and uid and uid == ident_id:
                record = u
                break
            if ident_name and (str(uname).strip() == ident_name or arabic_match(ident_name, uname)):
                record = u
                break

    if record:
        role = str(record.get("role") or role_hint or "unknown").lower()
        perms = _merge_permissions(get_role_permissions(role), record.get("permissions"))
        return Actor(user_id=str(record.get("id") or ident_id), name=record.get("name") or ident_name,
                     role=role, permissions=perms, found=True,
                     active=record.get("isActive", True) is not False)

    # لم يُعثر على المستخدم — نعتمد على تلميح الدور (الترويسة) إن وُجد
    role = str(role_hint or "unknown").lower()
    return Actor(user_id=ident_id, name=ident_name, role=role,
                 permissions=get_role_permissions(role), found=False)


def extract_identity(request: Any, body: Optional[Dict[str, Any]] = None) -> Dict[str, Optional[str]]:
    """🔐 الهوية الموثوقة تُؤخذ حصراً من JWT الموقَّع (لا الترويسات/الجسم القابلة للانتحال).

    deny-by-default: بدون توكن صالح لا تُشتقّ هوية ولا دور ⇒ يفشل تحقق الصلاحية لاحقاً.
    """
    try:
        from auth_jwt import identity_from_request
        ident = identity_from_request(request) or {}
    except Exception:
        ident = {}
    username = ident.get("username")
    if not username:
        return {"user_id": None, "name": None, "role_hint": None}
    return {
        "user_id": str(username).strip(),
        "name": str(username).strip(),
        "role_hint": (str(ident.get("role")).strip() if ident.get("role") else None),
    }


def check_permission(actor: Actor, module: str, action: str) -> PermissionResult:
    if actor.can(module, action):
        return PermissionResult(True, role=actor.role)
    return PermissionResult(False, role=actor.role,
                            reason=f"الدور '{actor.role}' لا يملك صلاحية {module}.{action}")


def can_approve(actor: Actor) -> PermissionResult:
    """صلاحية اعتماد/تنفيذ الإجراءات الحساسة."""
    if actor.role in APPROVER_ROLES:
        return PermissionResult(True, role=actor.role)
    # أو إن كان يملك صلاحية حذف/تعديل مالي صريحة
    if actor.can("operations", "delete") or actor.can("journal_entries", "delete"):
        return PermissionResult(True, role=actor.role)
    return PermissionResult(False, role=actor.role,
                            reason=f"الدور '{actor.role}' غير مخوّل باعتماد الإجراءات الحساسة")


def require(result: PermissionResult, status_code: int = 403) -> None:
    if not result.allowed:
        raise HTTPException(status_code=status_code,
                            detail={"error": "permission_denied", "msg": result.reason or "صلاحية غير كافية",
                                    "role": result.role})
