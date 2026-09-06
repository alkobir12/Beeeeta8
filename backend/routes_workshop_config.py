"""
⚙️ Workshop Config Router — Settings, Profile, Auth OTP

Domain: workshop-level configuration (settings, profile, logo upload, OTP).
Extracted from routes_extended.py (lines 149-495) on 2026-02-11.

URL paths preserved as-is. The shared `db` (Mongo) reference is injected via
`set_db(db)` and the in-memory JSON store helpers are imported from
`mem_store.py`.
"""

import base64
import os
import urllib.parse
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict

from fastapi import APIRouter, Body, File, HTTPException, Request, UploadFile

from mem_store import _mem_read, _mem_write
from supabase_service import SupabaseService
from core import authz as _authz

router = APIRouter(prefix="/api", tags=["workshop_config"])

# Injected by server.py via set_db(database)
db = None

_FORBIDDEN_PRIVILEGE_FIELDS = {
    "role", "roles", "permission", "permissions", "isadmin", "is_admin", "admin",
    "adminflags", "admin_flags", "status", "isactive", "is_active", "ownerid",
    "owner_id", "userid", "user_id", "createdby", "created_by", "updatedby",
    "updated_by", "audit", "auditlog", "audit_log", "security", "securityconfig",
    "security_config", "password", "passwordhash", "password_hash", "token",
    "access_token", "refresh_token",
}
_SETTINGS_WRITABLE_FIELDS = {
    "currency", "taxRate", "language", "timezone", "invoicePrefix", "workshopName",
    "workshopPhone", "workshopAddress", "workshopEmail", "menuConfig", "printDefaults",
    "theme", "style", "notifications", "vatNumber", "taxNumber", "updatedAt",
}
_PROFILE_WRITABLE_FIELDS = {
    "name", "nameEnglish", "phone", "whatsapp", "email", "address", "city",
    "postalCode", "commercialRegister", "workingHours", "invoiceFooter",
    "termsAndConditions", "slogan", "logo", "taxNumber",
}


def set_db(database):
    global db
    db = database


def _flatten_keys(payload: Any, prefix: str = "") -> set[str]:
    keys: set[str] = set()
    if isinstance(payload, dict):
        for key, value in payload.items():
            name = str(key)
            keys.add((prefix + name).lower().replace("-", "").replace(".", ""))
            keys |= _flatten_keys(value, prefix="")
    elif isinstance(payload, list):
        for item in payload:
            keys |= _flatten_keys(item, prefix="")
    return keys


def _reject_privileged_fields(payload: Dict[str, Any], *, surface: str) -> None:
    present = _flatten_keys(payload)
    blocked = sorted(k for k in present if k in _FORBIDDEN_PRIVILEGE_FIELDS)
    if blocked:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "privileged_field_rejected",
                "surface": surface,
                "fields": blocked,
                "msg": "لا يمكن تعديل حقول الصلاحيات/الأمان عبر هذا المسار",
            },
        )


def _allowlisted(payload: Dict[str, Any], allowed: set[str], *, surface: str) -> Dict[str, Any]:
    _reject_privileged_fields(payload, surface=surface)
    return {k: v for k, v in (payload or {}).items() if k in allowed}


# --------------------- Settings ---------------------
@router.get("/settings")
async def get_settings():
    try:
        DB_PROVIDER = os.environ.get("DB_PROVIDER", "mongo").lower()

        default_settings = {
            "id": "app_settings",
            "currency": "SAR",
            "taxRate": 0.0,
            "language": "ar",
            "timezone": "Asia/Riyadh",
            "invoicePrefix": "INV",
            "workshopName": "ورشة السيارات",
            "workshopPhone": "",
            "workshopAddress": "",
            "workshopEmail": "",
            "menuConfig": {
                "simple": False,
                "items": [
                    {"path": "/", "label": "الرئيسية", "enabled": True},
                    {"path": "/operations", "label": "العمليات", "enabled": True},
                    {"path": "/services", "label": "الخدمات", "enabled": True},
                    {"path": "/parts", "label": "قطع الغيار", "enabled": True},
                    {"path": "/catalog", "label": "كتالوج القطع", "enabled": True},
                    {"path": "/customers", "label": "العملاء", "enabled": True},
                    {"path": "/technicians", "label": "الفنيون", "enabled": True},
                    {"path": "/business-accounts", "label": "الفروع", "enabled": True},
                    {"path": "/invoice-templates", "label": "مصمم الفواتير", "enabled": True},
                    {"path": "/analytics", "label": "التحليلات", "enabled": True},
                    {"path": "/settings", "label": "الإعدادات", "enabled": True},
                ],
            },
        }

        if DB_PROVIDER == "supabase":
            supabase = SupabaseService()
            try:
                res = (
                    supabase.client.table("workshop_settings")
                    .select("*")
                    .eq("id", "app_settings")
                    .maybe_single()
                    .execute()
                )
                if res.data:
                    return res.data
                supabase.client.table("workshop_settings").insert(default_settings).execute()
                return default_settings
            except Exception:
                return default_settings

        if DB_PROVIDER == "memory":
            return default_settings

        doc = await db.settings.find_one({"id": "app_settings"})
        if not doc:
            doc = default_settings
            await db.settings.insert_one(doc)
        doc.pop("_id", None)
        return doc
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/settings")
async def save_settings(payload: Dict[str, Any] = Body(...)):
    try:
        payload = _allowlisted(payload, _SETTINGS_WRITABLE_FIELDS, surface="settings")
        DB_PROVIDER = os.environ.get("DB_PROVIDER", "mongo").lower()

        if DB_PROVIDER == "supabase":
            supabase = SupabaseService()
            payload["id"] = "app_settings"
            payload["updatedAt"] = datetime.utcnow().isoformat()
            try:
                res = (
                    supabase.client.table("workshop_settings")
                    .update(payload)
                    .eq("id", "app_settings")
                    .execute()
                )
                if res.data:
                    return res.data[0]
                res = supabase.client.table("workshop_settings").insert(payload).execute()
                return res.data[0]
            except Exception:
                return payload

        if DB_PROVIDER == "memory":
            return {**payload, "id": "app_settings", "updatedAt": datetime.utcnow().isoformat()}

        payload = {**payload, "id": "app_settings", "updatedAt": datetime.utcnow()}
        await db.settings.update_one({"id": "app_settings"}, {"$set": payload}, upsert=True)
        doc = await db.settings.find_one({"id": "app_settings"})
        doc.pop("_id", None)
        return doc
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --------------------- Workshop Profile ---------------------
_DEFAULT_PROFILE = {
    "id": "workshop_profile",
    "name": "ورشتي",
    "nameEnglish": "My Workshop",
    "phone": "",
    "whatsapp": "",
    "email": "",
    "address": "",
    "city": "",
    "postalCode": "",
    "commercialRegister": "",
    "workingHours": "",
    "invoiceFooter": "",
    "termsAndConditions": "",
    "slogan": "",
    "logo": "",
}


@router.get("/profile")
async def get_workshop_profile():
    try:
        provider = os.environ.get("DB_PROVIDER", "mongo").lower()
        if provider == "supabase":
            rows = _mem_read("workshop_profile")
            if rows:
                return rows[0]
            profile = dict(_DEFAULT_PROFILE)
            _mem_write("workshop_profile", [profile])
            return profile

        if provider == "memory" or db is None:
            rows = _mem_read("workshop_profile")
            if rows:
                return rows[0]
            profile = {**_DEFAULT_PROFILE, "taxNumber": ""}
            _mem_write("workshop_profile", [profile])
            return profile

        doc = await db.workshop_profile.find_one({"id": "workshop_profile"}, {"_id": 0})
        if not doc:
            doc = {**_DEFAULT_PROFILE, "taxNumber": ""}
            await db.workshop_profile.insert_one(dict(doc))
        return doc
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/profile")
async def update_workshop_profile(request: Request, payload: Dict[str, Any] = Body(...)):
    try:
        actor = await _authz.resolve_request_actor(request)
        target_user = str((payload or {}).get("userId") or (payload or {}).get("user_id") or "").strip()
        if target_user:
            _authz.ensure_self_actor(actor, target_user)
        payload = _allowlisted(payload, _PROFILE_WRITABLE_FIELDS, surface="profile")
        provider = os.environ.get("DB_PROVIDER", "mongo").lower()

        if provider in ("supabase", "memory") or db is None:
            rows = _mem_read("workshop_profile")
            profile = {**(rows[0] if rows else {}), **payload, "id": "workshop_profile"}
            _mem_write("workshop_profile", [profile])
            return profile

        payload = {**payload, "id": "workshop_profile", "updatedAt": datetime.utcnow()}
        await db.workshop_profile.update_one(
            {"id": "workshop_profile"}, {"$set": payload}, upsert=True
        )
        doc = await db.workshop_profile.find_one({"id": "workshop_profile"}, {"_id": 0})
        return doc
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/profile/upload-logo")
async def upload_workshop_logo(request: Request, file: UploadFile = File(...)):
    """Upload workshop logo image (max 2MB) and store as data: URL."""
    try:
        await _authz.resolve_request_actor(request)
        content = await file.read()
        if len(content) > 2 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File size must be less than 2MB")
        content_type = file.content_type or "image/png"
        if not str(content_type).startswith("image/"):
            raise HTTPException(status_code=415, detail="Logo upload accepts image files only")

        base64_image = base64.b64encode(content).decode("utf-8")
        logo_url = f"data:{content_type};base64,{base64_image}"

        provider = os.environ.get("DB_PROVIDER", "mongo").lower()
        if provider in ("supabase", "memory") or db is None:
            rows = _mem_read("workshop_profile")
            profile = {
                **(rows[0] if rows else {}),
                "logo": logo_url,
                "id": "workshop_profile",
            }
            _mem_write("workshop_profile", [profile])
        else:
            await db.workshop_profile.update_one(
                {"id": "workshop_profile"},
                {"$set": {"logo": logo_url, "updatedAt": datetime.utcnow()}},
                upsert=True,
            )
        return {"success": True, "logo_url": logo_url, "url": logo_url}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --------------------- Auth (WhatsApp OTP) ---------------------
@router.post("/auth/request-otp")
async def request_otp(payload: Dict[str, Any] = Body(...)):
    try:
        phone = (payload or {}).get("phone", "")
        otp_type = (payload or {}).get("type", "login")
        if not phone:
            raise HTTPException(status_code=400, detail="phone required")

        # Normalize phone (SA conventions, matches legacy logic)
        norm = "".join([c for c in phone if c.isdigit() or c == "+"])
        if norm.startswith("00"):
            norm = norm[2:]
        if norm.startswith("+"):
            norm = norm[1:]
        if norm.startswith("05"):
            norm = "966" + norm[1:]
        if norm.startswith("5") and len(norm) == 9:
            norm = "966" + norm
        if not norm.startswith("966"):
            norm = "966" + norm

        token = f"OTP-{str(uuid.uuid4())[:6].upper()}"
        doc = {
            "id": str(uuid.uuid4()),
            "phone": norm,
            "token": token,
            "type": otp_type,
            "createdAt": datetime.utcnow(),
            "expiresAt": datetime.utcnow() + timedelta(minutes=10),
            "used": False,
        }
        if db is not None:
            try:
                await db.auth_otps.insert_one(doc)
            except Exception as e:
                print(f"auth/request-otp: db insert failed: {e}")

        msg = f"رمز الدخول الخاص بك: {token} — صالح لمدة 10 دقائق"
        deeplink = f"https://wa.me/{norm}?text={urllib.parse.quote(msg)}"
        return {
            "token": token,
            "whatsappDeeplink": deeplink,
            "expiresAt": doc["expiresAt"].isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
