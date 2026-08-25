from fastapi import APIRouter, HTTPException, Request
from datetime import datetime
from typing import List
import uuid
import os
import json

from models_users import User, UserCreate, UserUpdate
from supabase_service import SupabaseService
from core import authz as _authz

router = APIRouter(prefix="/api")


def _actor_is_admin(actor) -> bool:
    return actor.role == "admin" or actor.can("users", "delete")


def _grants_privileged_perms(perms) -> bool:
    if not isinstance(perms, dict):
        return False
    for mod in ("users", "settings"):
        m = perms.get(mod) or {}
        if m.get("create") or m.get("edit") or m.get("delete"):
            return True
    return False

DB_PROVIDER = os.environ.get("DB_PROVIDER", "mongo").lower()
USERS_FILE = os.path.join(os.path.dirname(__file__), "uploads", "users.json")

supabase = SupabaseService()
_db = None


def _normalize_permissions(raw_permissions):
    if not isinstance(raw_permissions, dict):
        return {}

    if not any(key.startswith("can") for key in raw_permissions.keys()):
        normalized = dict(raw_permissions)
        if "operations" not in normalized and isinstance(raw_permissions.get("work_orders"), dict):
            work_orders = raw_permissions.get("work_orders") or {}
            debts = raw_permissions.get("debts") or {}
            normalized["operations"] = {
                "view": work_orders.get("view") is True,
                "settle": work_orders.get("edit") is True or debts.get("settle") is True,
                "edit": work_orders.get("edit") is True,
                "delete": work_orders.get("delete") is True,
            }
        if "journal_entries" not in normalized and isinstance(raw_permissions.get("reports"), dict):
            reports = raw_permissions.get("reports") or {}
            normalized["journal_entries"] = {
                "view": reports.get("view") is True,
                "create": reports.get("create") is True,
                "edit": reports.get("edit") is True,
                "delete": reports.get("delete") is True,
                "pos": reports.get("view") is True,
            }
        if "archive" not in normalized and isinstance(raw_permissions.get("vehicles"), dict):
            vehicles = raw_permissions.get("vehicles") or {}
            normalized["archive"] = {
                "view": vehicles.get("view") is True,
                "create": vehicles.get("create") is True,
                "edit": vehicles.get("edit") is True,
                "delete": vehicles.get("delete") is True,
            }
        return normalized

    normalized = {}

    def enable(module_key, actions):
        if module_key not in normalized:
            normalized[module_key] = {}
        for action in actions:
            normalized[module_key][action] = True

    if raw_permissions.get("canViewDashboard"):
        enable("dashboard", ["view"])
    if raw_permissions.get("canManageVehicles"):
        enable("vehicles", ["view", "create", "edit", "delete"])
        enable("archive", ["view", "create", "edit", "delete"])
    if raw_permissions.get("canManageCustomers"):
        enable("customers", ["view", "create", "edit", "delete"])
    if raw_permissions.get("canManageParts"):
        enable("inventory", ["view", "create", "edit", "delete"])
    if raw_permissions.get("canManageServices"):
        enable("work_orders", ["view", "create", "edit", "delete"])
        enable("operations", ["view", "settle", "edit", "delete"])
    if raw_permissions.get("canViewReports"):
        enable("reports", ["view"])
        enable("journal_entries", ["view", "create", "edit", "delete", "pos"])
    if raw_permissions.get("canManageFinance"):
        enable("debts", ["view", "settle"])
        enable("invoices", ["view", "create", "edit", "delete"])
    if raw_permissions.get("canManageUsers"):
        enable("users", ["view", "create", "edit", "delete"])
    if raw_permissions.get("canManageSettings"):
        enable("settings", ["view", "edit"])

    return normalized


def _normalize_user_row(row: dict) -> dict:
    user = dict(row or {})
    user["permissions"] = _normalize_permissions(user.get("permissions"))
    if not user.get("username"):
        user["username"] = user.get("name") or user.get("phone") or ""
    user.pop("password", None)
    return user


def _prepare_user_payload(payload: dict, *, is_create: bool = False) -> dict:
    doc = dict(payload or {})
    if is_create and not doc.get("username"):
        doc["username"] = doc.get("name") or doc.get("phone") or ""
    elif not is_create and any(key in doc for key in ("username", "name", "phone")) and not doc.get("username"):
        doc["username"] = doc.get("name") or doc.get("phone") or ""
    doc.pop("password", None)
    if is_create:
        doc["id"] = str(uuid.uuid4())
        doc["createdAt"] = datetime.utcnow().isoformat()
        doc.setdefault("lastLogin", None)
        doc.setdefault("isActive", True)
    if "permissions" in doc:
        doc["permissions"] = _normalize_permissions(doc.get("permissions") or {})
    return doc


def set_db(database):
    global _db
    _db = database


# ---------- helpers for memory provider ----------
def _ensure_users_file():
    os.makedirs(os.path.join(os.path.dirname(__file__), "uploads"), exist_ok=True)
    if not os.path.exists(USERS_FILE):
        seed = [
            {
                "id": str(uuid.uuid4()),
                "name": "مدير",
                "email": None,
                "phone": "0500000000",
                "role": "admin",
                "permissions": {},
                "isActive": True,
                "guidanceEnabled": True,
                "createdAt": datetime.utcnow().isoformat(),
                "lastLogin": None,
            }
        ]
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(seed, f, ensure_ascii=False, indent=2)


def _ensure_builtin_privileged_users(users: List[dict]) -> List[dict]:
    """يحافظ على حسابات التشغيل السريعة المطلوبة للاختبار/المعاينة عند استخدام ملف fallback."""
    rows = list(users or [])
    changed = False
    required = [
        {
            "name": (os.environ.get("MANAGER_QUICK_USERNAME") or "مدير").strip(),
            "role": "admin",
            "phone": "0500000000",
        },
        {
            "name": "احمد",
            "role": "accountant",
            "phone": "0500000001",
        },
    ]

    for item in required:
        name = item["name"]
        if not name:
            continue
        found = None
        for row in rows:
            if str(row.get("name") or "").strip() == name or str(row.get("username") or "").strip() == name:
                found = row
                break
        if found is None:
            rows.append({
                "id": str(uuid.uuid4()),
                "name": name,
                "username": name,
                "email": None,
                "phone": item["phone"],
                "role": item["role"],
                "permissions": {},
                "isActive": True,
                "guidanceEnabled": True,
                "createdAt": datetime.utcnow().isoformat(),
                "lastLogin": None,
            })
            changed = True
            continue
        if item["role"] in {"admin", "accountant"} and found.get("role") != item["role"]:
            found["role"] = item["role"]
            changed = True
        if not found.get("username"):
            found["username"] = name
            changed = True
        if found.get("isActive") is False:
            found["isActive"] = True
            changed = True
        if found.get("guidanceEnabled") is None:
            found["guidanceEnabled"] = True
            changed = True

    if changed:
        _write_users(rows)
    return rows


def _read_users() -> List[dict]:
    _ensure_users_file()
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            users = json.load(f)
            for user in users:
                if user.get("guidanceEnabled") is None:
                    user["guidanceEnabled"] = True
            return _ensure_builtin_privileged_users(users)
    except Exception:
        return []


def _write_users(users: List[dict]):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


# ------------------ USERS MANAGEMENT ------------------
@router.get("/users", response_model=List[User])
async def get_users():
    try:
        if DB_PROVIDER == "supabase" and not supabase.mock_mode:
            rows = supabase.users_list()
            normalized_rows = [_normalize_user_row(row) for row in rows]
            return [User(**r) for r in normalized_rows]
        if DB_PROVIDER == "memory":
            rows = _read_users()
            normalized_rows = [_normalize_user_row(row) for row in rows]
            return [User(**r) for r in normalized_rows]
        # Mongo fallback
        users = await _db.users.find({}).to_list(length=1000)
        out = []
        for u in users:
            u.pop("_id", None)
            out.append(User(**_normalize_user_row(u)))
        return out
    except Exception:
        # Fallback to memory on any error (e.g., Mongo down)
        rows = _read_users()
        normalized_rows = [_normalize_user_row(row) for row in rows]
        return [User(**r) for r in normalized_rows]


@router.post("/users", response_model=User)
async def create_user(user_data: UserCreate, request: Request):
    # 🔐 object-level guard: only admin may create admin/privileged users
    actor = await _authz.resolve_request_actor(request)
    if not _actor_is_admin(actor):
        if str(getattr(user_data, "role", "") or "").lower() == "admin":
            raise HTTPException(status_code=403, detail={"error": "privilege_escalation_forbidden",
                                                         "msg": "لا يمكن إنشاء مستخدم بدور admin"})
        if _grants_privileged_perms(getattr(user_data, "permissions", None)):
            raise HTTPException(status_code=403, detail={"error": "privilege_escalation_forbidden",
                                                         "msg": "لا يمكن منح صلاحيات إدارة المستخدمين/الإعدادات"})
    try:
        if DB_PROVIDER == "supabase" and not supabase.mock_mode:
            payload = _prepare_user_payload(user_data.dict(), is_create=True)
            created = supabase.users_create(payload)
            return User(**_normalize_user_row(created))
        if DB_PROVIDER == "memory":
            users = _read_users()
            if any(
                (u.get("phone") == user_data.phone and user_data.phone) for u in users
            ):
                raise HTTPException(status_code=400, detail="رقم الهاتف مسجل مسبقاً")
            doc = _prepare_user_payload(user_data.dict(), is_create=True)
            users.append(doc)
            _write_users(users)
            return User(**_normalize_user_row(doc))
        # Mongo
        existing = await _db.users.find_one({"phone": user_data.phone})
        if existing:
            raise HTTPException(status_code=400, detail="رقم الهاتف مسجل مسبقاً")
        user_dict = _prepare_user_payload(user_data.dict(), is_create=True)
        user_dict["createdAt"] = datetime.utcnow()
        await _db.users.insert_one(user_dict)
        user_dict.pop("_id", None)
        return User(**_normalize_user_row(user_dict))
    except HTTPException:
        raise
    except Exception:
        # fallback to memory
        users = _read_users()
        doc = _prepare_user_payload(user_data.dict(), is_create=True)
        users.append(doc)
        _write_users(users)
        return User(**_normalize_user_row(doc))


@router.put("/users/{user_id}", response_model=User)
async def update_user(user_id: str, update_data: UserUpdate, request: Request):
    # 🔐 object-level guards: no self privilege change, no privilege escalation
    actor = await _authz.resolve_request_actor(request)
    _data = {k: v for k, v in update_data.dict().items() if v is not None}
    if str(user_id) == str(actor.id) and any(k in _data for k in ("role", "permissions", "isActive")):
        raise HTTPException(status_code=403, detail={"error": "self_privilege_change_forbidden",
                                                     "msg": "لا يمكنك تعديل دورك/صلاحياتك/حالتك بنفسك"})
    if not _actor_is_admin(actor):
        if str(_data.get("role", "") or "").lower() == "admin":
            raise HTTPException(status_code=403, detail={"error": "privilege_escalation_forbidden",
                                                         "msg": "لا يمكن ترقية مستخدم إلى admin"})
        if _grants_privileged_perms(_data.get("permissions")):
            raise HTTPException(status_code=403, detail={"error": "privilege_escalation_forbidden",
                                                         "msg": "لا يمكن منح صلاحيات إدارة المستخدمين/الإعدادات"})
    try:
        if DB_PROVIDER == "supabase" and not supabase.mock_mode:
            payload = _prepare_user_payload({k: v for k, v in update_data.dict().items() if v is not None})
            updated = supabase.users_update(user_id, payload)
            return User(**_normalize_user_row(updated))
        if DB_PROVIDER == "memory":
            users = _read_users()
            idx = next((i for i, u in enumerate(users) if u.get("id") == user_id), -1)
            if idx == -1:
                raise HTTPException(status_code=404, detail="المستخدم غير موجود")
            upd = _prepare_user_payload({k: v for k, v in update_data.dict().items() if v is not None})
            users[idx].update(upd)
            _write_users(users)
            return User(**_normalize_user_row(users[idx]))
        # Mongo fallback
        user = await _db.users.find_one({"id": user_id})
        if not user:
            raise HTTPException(status_code=404, detail="المستخدم غير موجود")
        update_dict = _prepare_user_payload({k: v for k, v in update_data.dict().items() if v is not None})
        if update_dict:
            await _db.users.update_one({"id": user_id}, {"$set": update_dict})
            user = await _db.users.find_one({"id": user_id})
        user.pop("_id", None)
        return User(**_normalize_user_row(user))
    except HTTPException:
        raise
    except Exception:
        # fallback to memory
        users = _read_users()
        idx = next((i for i, u in enumerate(users) if u.get("id") == user_id), -1)
        if idx == -1:
            raise HTTPException(status_code=404, detail="المستخدم غير موجود")
        upd = _prepare_user_payload({k: v for k, v in update_data.dict().items() if v is not None})
        users[idx].update(upd)
        _write_users(users)
        return User(**_normalize_user_row(users[idx]))


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, request: Request):
    # 🔐 object-level guard: cannot delete self
    actor = await _authz.resolve_request_actor(request)
    if str(user_id) == str(actor.id):
        raise HTTPException(status_code=403, detail={"error": "cannot_delete_self",
                                                     "msg": "لا يمكنك حذف حسابك الخاص"})
    try:
        if DB_PROVIDER == "supabase" and not supabase.mock_mode:
            supabase.users_delete(user_id)
            return {"status": "ok", "message": "تم حذف المستخدم"}
        if DB_PROVIDER == "memory":
            users = _read_users()
            nusers = [u for u in users if u.get("id") != user_id]
            if len(nusers) == len(users):
                raise HTTPException(status_code=404, detail="المستخدم غير موجود")
            _write_users(nusers)
            return {"status": "ok", "message": "تم حذف المستخدم"}
        # Mongo
        result = await _db.users.delete_one({"id": user_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="المستخدم غير موجود")
        return {"status": "ok", "message": "تم حذف المستخدم"}
    except HTTPException:
        raise
    except Exception:
        # fallback to memory
        users = _read_users()
        nusers = [u for u in users if u.get("id") != user_id]
        if len(nusers) == len(users):
            raise HTTPException(status_code=404, detail="المستخدم غير موجود")
        _write_users(nusers)
        return {"status": "ok", "message": "تم حذف المستخدم"}
