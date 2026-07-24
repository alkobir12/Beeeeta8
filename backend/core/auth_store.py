"""🔐 core/auth_store.py — Mongo-backed authentication store (P1 / SEC-003).

Provides the production-auth foundation shared by every login method:
  • Refresh-token ROTATION with family tracking + reuse detection (revoke family on reuse).
  • Session management (list/revoke active refresh families per user).
  • Trusted-device tokens ("Remember this device").
  • Auth AUDIT log (login/refresh/logout/password/pin/google/new-device).
  • Password & PIN hashing (bcrypt).

Backward-compatible: name-only login keeps working; these are additive capabilities.
All datetimes are timezone-aware UTC and stored as ISO strings.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import bcrypt
from motor.motor_asyncio import AsyncIOMotorClient

_MONGO_URL = os.environ.get("MONGO_URL")
_DB_NAME = os.environ.get("DB_NAME")

_client: Optional[AsyncIOMotorClient] = None
_indexes_ready = False


def _db():
    global _client
    if _client is None:
        if not _MONGO_URL or not _DB_NAME:
            raise RuntimeError("MONGO_URL / DB_NAME not configured")
        _client = AsyncIOMotorClient(_MONGO_URL)
    return _client[_DB_NAME]


async def _ensure_indexes() -> None:
    global _indexes_ready
    if _indexes_ready:
        return
    db = _db()
    await db.auth_refresh_tokens.create_index("jti", unique=True)
    await db.auth_refresh_tokens.create_index("family_id")
    await db.auth_refresh_tokens.create_index("username")
    await db.trusted_devices.create_index("device_id", unique=True)
    await db.trusted_devices.create_index("username")
    await db.auth_audit.create_index("ts")
    await db.auth_audit.create_index("username")
    _indexes_ready = True


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


# --------------------------------------------------------------------------
# Password / PIN hashing (bcrypt; 72-byte input cap handled by encoding)
# --------------------------------------------------------------------------

def hash_secret(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")


def verify_secret(plain: str, hashed: str) -> bool:
    if not plain or not hashed:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8")[:72], hashed.encode("utf-8"))
    except Exception:
        return False


# --------------------------------------------------------------------------
# Refresh-token rotation store (jti + family + reuse detection)
# --------------------------------------------------------------------------

class RefreshReuseError(Exception):
    """Raised when a already-used/revoked refresh jti is presented → family compromised."""


async def register_refresh(
    *, jti: str, username: str, role: str, expires_at: datetime,
    family_id: Optional[str] = None, device_id: Optional[str] = None,
) -> str:
    """Persist a newly-minted refresh token. Returns the family_id."""
    await _ensure_indexes()
    fam = family_id or f"fam_{uuid.uuid4().hex[:16]}"
    await _db().auth_refresh_tokens.insert_one({
        "jti": jti,
        "family_id": fam,
        "username": username,
        "role": role,
        "issued_at": _iso(_now()),
        "expires_at": _iso(expires_at),
        "revoked": False,
        "used": False,
        "replaced_by": None,
        "device_id": device_id,
    })
    return fam


async def rotate_refresh(*, old_jti: str, new_jti: str, expires_at: datetime) -> Dict[str, Any]:
    """Validate + rotate. Reuse detection: if old jti is already used/revoked, the
    whole family is revoked and RefreshReuseError is raised."""
    await _ensure_indexes()
    col = _db().auth_refresh_tokens
    doc = await col.find_one({"jti": old_jti}, {"_id": 0})
    if not doc:
        raise RefreshReuseError("unknown_refresh")
    # expiry
    exp = doc.get("expires_at")
    exp_dt = datetime.fromisoformat(exp) if isinstance(exp, str) else exp
    if exp_dt and exp_dt.tzinfo is None:
        exp_dt = exp_dt.replace(tzinfo=timezone.utc)
    if exp_dt and exp_dt < _now():
        raise RefreshReuseError("expired_refresh")
    # 🚨 reuse detection
    if doc.get("revoked") or doc.get("used"):
        await revoke_family(doc["family_id"], reason="reuse_detected")
        raise RefreshReuseError("refresh_reuse_detected")
    # rotate: mark old used, register new in same family
    await col.update_one({"jti": old_jti}, {"$set": {"used": True, "replaced_by": new_jti, "used_at": _iso(_now())}})
    await col.insert_one({
        "jti": new_jti, "family_id": doc["family_id"], "username": doc["username"],
        "role": doc.get("role"), "issued_at": _iso(_now()), "expires_at": _iso(expires_at),
        "revoked": False, "used": False, "replaced_by": None, "device_id": doc.get("device_id"),
    })
    return {"username": doc["username"], "role": doc.get("role"), "family_id": doc["family_id"],
            "device_id": doc.get("device_id")}


async def pick_active_jti(jtis: list) -> Optional[str]:
    """Return the first jti from the list that is still active (not used/revoked/expired)."""
    await _ensure_indexes()
    col = _db().auth_refresh_tokens
    docs = await col.find({"jti": {"$in": jtis}, "used": False, "revoked": False},
                          {"_id": 0, "jti": 1, "expires_at": 1}).to_list(length=10)
    active = set()
    for d in docs:
        exp = d.get("expires_at")
        exp_dt = datetime.fromisoformat(exp) if isinstance(exp, str) else exp
        if exp_dt and exp_dt.tzinfo is None:
            exp_dt = exp_dt.replace(tzinfo=timezone.utc)
        if not exp_dt or exp_dt >= _now():
            active.add(d["jti"])
    for j in jtis:
        if j in active:
            return j
    return None


async def revoke_family(family_id: str, *, reason: str = "logout") -> int:
    await _ensure_indexes()
    res = await _db().auth_refresh_tokens.update_many(
        {"family_id": family_id, "revoked": False},
        {"$set": {"revoked": True, "revoked_reason": reason, "revoked_at": _iso(_now())}},
    )
    return res.modified_count


async def revoke_all_for_user(username: str, *, reason: str = "revoke_all") -> int:
    await _ensure_indexes()
    res = await _db().auth_refresh_tokens.update_many(
        {"username": username, "revoked": False},
        {"$set": {"revoked": True, "revoked_reason": reason, "revoked_at": _iso(_now())}},
    )
    return res.modified_count


async def list_sessions(username: str) -> List[Dict[str, Any]]:
    """Active (non-revoked, non-expired) refresh families = active sessions."""
    await _ensure_indexes()
    now = _now()
    cur = _db().auth_refresh_tokens.find(
        {"username": username, "revoked": False}, {"_id": 0}
    ).sort("issued_at", -1)
    fams: Dict[str, Dict[str, Any]] = {}
    async for d in cur:
        exp = d.get("expires_at")
        exp_dt = datetime.fromisoformat(exp) if isinstance(exp, str) else exp
        if exp_dt and exp_dt.tzinfo is None:
            exp_dt = exp_dt.replace(tzinfo=timezone.utc)
        if exp_dt and exp_dt < now:
            continue
        fam = d["family_id"]
        if fam not in fams:
            fams[fam] = {
                "family_id": fam, "device_id": d.get("device_id"),
                "issued_at": d.get("issued_at"), "expires_at": d.get("expires_at"),
            }
    return list(fams.values())


# --------------------------------------------------------------------------
# Trusted devices ("Remember this device")
# --------------------------------------------------------------------------

async def trust_device(*, username: str, days: int = 30) -> str:
    await _ensure_indexes()
    device_id = f"dev_{uuid.uuid4().hex}"
    await _db().trusted_devices.insert_one({
        "device_id": device_id, "username": username,
        "issued_at": _iso(_now()), "expires_at": _iso(_now() + timedelta(days=days)),
        "revoked": False,
    })
    return device_id


async def is_device_trusted(*, username: str, device_id: str) -> bool:
    if not device_id:
        return False
    await _ensure_indexes()
    d = await _db().trusted_devices.find_one({"device_id": device_id, "username": username}, {"_id": 0})
    if not d or d.get("revoked"):
        return False
    exp = d.get("expires_at")
    exp_dt = datetime.fromisoformat(exp) if isinstance(exp, str) else exp
    if exp_dt and exp_dt.tzinfo is None:
        exp_dt = exp_dt.replace(tzinfo=timezone.utc)
    return bool(exp_dt and exp_dt >= _now())


# --------------------------------------------------------------------------
# Auth audit log
# --------------------------------------------------------------------------

async def audit(event: str, *, username: Optional[str] = None, success: bool = True,
                ip: Optional[str] = None, user_agent: Optional[str] = None,
                detail: Optional[str] = None) -> None:
    try:
        await _ensure_indexes()
        await _db().auth_audit.insert_one({
            "ts": _iso(_now()), "event": event, "username": username,
            "success": bool(success), "ip": ip,
            "user_agent": (user_agent or "")[:200], "detail": (detail or "")[:300],
        })
    except Exception:
        pass  # audit must never block auth


async def list_audit(*, username: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    await _ensure_indexes()
    q = {"username": username} if username else {}
    return await _db().auth_audit.find(q, {"_id": 0}).sort("ts", -1).to_list(length=min(limit, 500))


# --------------------------------------------------------------------------
# Brute-force lockout (per identifier, in-audit-derived count)
# --------------------------------------------------------------------------

async def recent_failures(identifier: str, *, minutes: int = 15, ip: Optional[str] = None) -> int:
    await _ensure_indexes()
    since = _iso(_now() - timedelta(minutes=minutes))
    identity_filter: Dict[str, Any] = {"username": identifier}
    if ip:
        identity_filter["ip"] = ip
    latest_success = await _db().auth_audit.find_one(
        {**identity_filter, "event": "login", "success": True},
        {"_id": 0, "ts": 1},
        sort=[("ts", -1)],
    )
    if latest_success and latest_success.get("ts", "") > since:
        since = latest_success["ts"]
    return await _db().auth_audit.count_documents({
        **identity_filter, "event": "login", "success": False, "ts": {"$gte": since},
    })


# --------------------------------------------------------------------------
# Credentials store (separate collection — does not touch the users store)
# --------------------------------------------------------------------------

async def _ensure_cred_index() -> None:
    db = _db()
    await db.auth_credentials.create_index("username", unique=True)
    await db.auth_credentials.create_index("email", sparse=True)


async def get_credentials(identifier: str) -> Optional[Dict[str, Any]]:
    """Fetch credentials by username OR email (case-insensitive email)."""
    await _ensure_cred_index()
    db = _db()
    doc = await db.auth_credentials.find_one({"username": identifier}, {"_id": 0})
    if not doc and identifier:
        doc = await db.auth_credentials.find_one(
            {"email": identifier.strip().lower()}, {"_id": 0})
    return doc


async def set_password(username: str, password: str, *, email: Optional[str] = None) -> None:
    await _ensure_cred_index()
    update = {"password_hash": hash_secret(password), "updated_at": _iso(_now())}
    if email:
        update["email"] = email.strip().lower()
    await _db().auth_credentials.update_one(
        {"username": username}, {"$set": update, "$setOnInsert": {"username": username}}, upsert=True)


async def set_pin(username: str, pin: str) -> None:
    await _ensure_cred_index()
    await _db().auth_credentials.update_one(
        {"username": username},
        {"$set": {"pin_hash": hash_secret(pin), "updated_at": _iso(_now())},
         "$setOnInsert": {"username": username}}, upsert=True)


async def ensure_pin(username: str, pin: str) -> bool:
    """Idempotently seed a configured PIN as a bcrypt hash. Returns True when changed."""
    await _ensure_cred_index()
    current = await _db().auth_credentials.find_one(
        {"username": username}, {"_id": 0, "pin_hash": 1}
    )
    if current and verify_secret(pin, current.get("pin_hash", "")):
        return False
    await set_pin(username, pin)
    return True
