"""
JWT Authentication module — preserves name-only login UX while securing APIs.

- POST /api/auth/login: accepts {username}, returns JWT access token + sets httpOnly cookie
- get_current_user dependency: validates JWT from Authorization header OR cookie
- Permissive mode: GET endpoints without token still return 200 (back-compat)
- Strict mode: write endpoints (POST/PUT/DELETE) require valid token
"""
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

import jwt
from fastapi import APIRouter, HTTPException, Request, Response, Depends
from pydantic import BaseModel

JWT_ALGORITHM = "HS256"
QUICK_PIN_USERNAME = os.environ["MANAGER_QUICK_USERNAME"]
# Token lifetimes (decision: short-lived access + 7-day refresh)
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.environ.get("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# 🔐 P0 root-cause fix: the app is embedded in a cross-site iframe (Emergent preview).
# Cookies with SameSite=Lax and no Secure are treated as third-party there and are NOT
# sent → /api/auth/refresh (cookie-only) got 401. SameSite=None + Secure makes the
# httpOnly cookies survive the iframe over HTTPS. Configurable via env for local HTTP dev.
_COOKIE_SAMESITE = (os.environ.get("AUTH_COOKIE_SAMESITE") or "none").lower()
_COOKIE_SECURE = (os.environ.get("AUTH_COOKIE_SECURE") or "true").lower() not in ("0", "false", "no")


def _get_jwt_secret() -> str:
    secret = os.environ.get("JWT_SECRET")
    if not secret or len(secret) < 16:
        raise RuntimeError("JWT_SECRET must be configured and at least 16 characters")
    return secret


def create_access_token(username: str, role: Optional[str] = None) -> str:
    """إنشاء JWT access token. يحمل الدور الموثَّق ليعتمده RBAC (لا الترويسة الخام)."""
    payload = {
        "sub": username,
        "role": (role or "").lower() or None,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "type": "access",
    }
    return jwt.encode(payload, _get_jwt_secret(), algorithm=JWT_ALGORITHM)


def create_refresh_token(username: str, jti: str, family_id: Optional[str] = None,
                         device_id: Optional[str] = None) -> str:
    """توكن تجديد طويل العمر يحمل jti (لتدوير خادمي + كشف إعادة الاستخدام)."""
    payload = {
        "sub": username,
        "jti": jti,
        "fam": family_id,
        "did": device_id,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        "type": "refresh",
    }
    return jwt.encode(payload, _get_jwt_secret(), algorithm=JWT_ALGORITHM)


def _refresh_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)


def decode_refresh_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, _get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            return None
        return payload
    except jwt.InvalidTokenError:
        return None


def decode_token(token: str) -> Optional[dict]:
    """فك تشفير التوكن، يُرجِع None إذا غير صالح."""
    try:
        payload = jwt.decode(token, _get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            return None
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def _extract_token(request: Request) -> Optional[str]:
    """يقرأ التوكن من Authorization header أو من cookie."""
    # 1) Authorization: Bearer ...
    auth_header = request.headers.get("Authorization") or request.headers.get("authorization") or ""
    if auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    # 2) Cookie access_token
    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        return cookie_token
    return None


async def get_current_user(request: Request) -> dict:
    """Dependency: يتطلب توكن صالح. يُرجِع الهوية + الدور الموقَّع."""
    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return {"username": payload.get("sub"), "role": payload.get("role"), "exp": payload.get("exp")}


async def get_current_user_optional(request: Request) -> Optional[dict]:
    """Dependency permissive: يُرجِع المستخدم إن وُجد، None إذا لا توكن."""
    token = _extract_token(request)
    if not token:
        return None
    payload = decode_token(token)
    if not payload:
        return None
    return {"username": payload.get("sub"), "role": payload.get("role"), "exp": payload.get("exp")}


def identity_from_request(request: Request) -> dict:
    """🔐 الهوية الموثوقة من JWT الموقَّع فقط (لا الترويسات القابلة للانتحال).

    يُرجِع {'username','role'} عند وجود توكن صالح، وإلا {} (deny-by-default).
    """
    try:
        token = _extract_token(request)
        if not token:
            return {}
        payload = decode_token(token)
        if not payload:
            return {}
        role = (payload.get("role") or "")
        return {"username": payload.get("sub"), "role": (role.lower() or None)}
    except Exception:
        return {}


# =========================================
# Auth Router
# =========================================
router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginPayload(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    pin: Optional[str] = None
    device_id: Optional[str] = None
    remember_device: Optional[bool] = False


def _client_meta(request: Request):
    ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (
        request.client.host if request.client else None)
    return ip, request.headers.get("user-agent", "")


async def _issue_tokens(response: Response, username: str, role: Optional[str],
                        *, device_id: Optional[str] = None, family_id: Optional[str] = None) -> dict:
    """Mint access+refresh, register the refresh jti in the rotation store, set cookies."""
    from core import auth_store
    access_token = create_access_token(username, role)
    jti = f"rt_{uuid.uuid4().hex}"
    refresh_token = create_refresh_token(username, jti, family_id=family_id, device_id=device_id)
    try:
        fam = await auth_store.register_refresh(
            jti=jti, username=username, role=role or "", expires_at=_refresh_expiry(),
            family_id=family_id, device_id=device_id,
        )
    except Exception:
        fam = family_id  # store unavailable → still return tokens (degraded, stateless)
    # re-embed the resolved family so the token and store agree
    refresh_token = create_refresh_token(username, jti, family_id=fam, device_id=device_id)
    _set_auth_cookies(response, access_token, refresh_token)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "username": username,
        "role": role,
        "device_id": device_id,
        "expires_in_minutes": ACCESS_TOKEN_EXPIRE_MINUTES,
    }


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    """httpOnly cookies — دفاع في العمق إضافةً إلى Bearer header.

    🔐 SameSite=None + Secure (افتراضياً) كي تُرسَل داخل iframe المعاينة (cross-site).
    """
    response.set_cookie(
        key="access_token", value=access_token, httponly=True, secure=_COOKIE_SECURE,
        samesite=_COOKIE_SAMESITE, max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60, path="/",
    )
    response.set_cookie(
        key="refresh_token", value=refresh_token, httponly=True, secure=_COOKIE_SECURE,
        samesite=_COOKIE_SAMESITE, max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600, path="/",
    )


@router.post("/login")
async def login(payload: LoginPayload, request: Request, response: Response):
    """تسجيل الدخول متعدد الطرق (متوافق رجعياً مع الاسم فقط).

    الأولوية: password → pin (المدير سريعاً، وبقية الحسابات على جهاز موثوق) → اسم فقط.
    من لديه كلمة مرور مضبوطة يجب أن يقدّمها (لا يُقبل الاسم فقط له).
    """
    from core import rbac, auth_store
    ip, ua = _client_meta(request)
    identifier = (payload.email or payload.username or "").strip()
    if not identifier or len(identifier) > 120:
        raise HTTPException(status_code=400, detail="المعرّف مطلوب")

    # 🔒 brute-force lockout
    if await auth_store.recent_failures(identifier, minutes=15, ip=ip) >= 5:
        await auth_store.audit("login", username=identifier, success=False, ip=ip,
                               user_agent=ua, detail="locked_out")
        raise HTTPException(status_code=429, detail="محاولات كثيرة — حاول بعد قليل")

    creds = await auth_store.get_credentials(identifier)
    resolved_username = (creds or {}).get("username") or identifier

    # resolve role/active from the business user store
    actor = await rbac.resolve_actor(name=resolved_username)
    if not actor.found:
        await auth_store.audit("login", username=identifier, success=False, ip=ip,
                               user_agent=ua, detail="unknown_user")
        raise HTTPException(status_code=401, detail="اسم المستخدم غير معروف")
    if actor.active is False:
        raise HTTPException(status_code=403, detail="هذا الحساب معطل")
    resolved_name = actor.name or resolved_username

    has_password = bool(creds and creds.get("password_hash"))
    has_pin = bool(creds and creds.get("pin_hash"))

    method = None
    if payload.password is not None:
        if not (has_password and auth_store.verify_secret(payload.password, creds["password_hash"])):
            await auth_store.audit("login", username=resolved_name, success=False, ip=ip,
                                   user_agent=ua, detail="bad_password")
            raise HTTPException(status_code=401, detail="بيانات الدخول غير صحيحة")
        method = "password"
    elif payload.pin is not None:
        trusted = await auth_store.is_device_trusted(username=resolved_name, device_id=payload.device_id or "")
        quick_manager_login = resolved_name == QUICK_PIN_USERNAME and len(payload.pin) == 6
        pin_valid = has_pin and auth_store.verify_secret(payload.pin, creds["pin_hash"])
        if not (pin_valid and (trusted or quick_manager_login)):
            await auth_store.audit("login", username=resolved_name, success=False, ip=ip,
                                   user_agent=ua, detail="bad_pin_or_untrusted_device")
            raise HTTPException(status_code=401, detail="رمز PIN غير صحيح")
        method = "pin"
    else:
        # No secret supplied → only allowed if the user has NO credentials set (back-compat).
        if has_password or has_pin:
            # not a credential guess → don't count toward brute-force lockout
            await auth_store.audit("login_challenge", username=resolved_name, success=False,
                                   ip=ip, user_agent=ua, detail="credential_required")
            raise HTTPException(status_code=401, detail="كلمة المرور مطلوبة لهذا الحساب")
        method = "name_only"

    device_id = payload.device_id
    if payload.remember_device and method in ("password", "pin"):
        device_id = await auth_store.trust_device(username=resolved_name, days=30)

    result = await _issue_tokens(response, resolved_name, actor.role, device_id=device_id)
    await auth_store.audit("login", username=resolved_name, success=True, ip=ip,
                           user_agent=ua, detail=f"method={method}")
    return result


@router.post("/logout")
async def logout(request: Request, response: Response):
    """مسح cookies + إبطال عائلة التوكن (كل الجلسة) في المخزن."""
    from core import auth_store
    token = request.cookies.get("refresh_token") or ""
    if not token:
        auth = request.headers.get("Authorization") or ""
        if auth.startswith("Bearer "):
            token = auth[7:].strip()
    payload = decode_refresh_token(token) if token else None
    if payload and payload.get("fam"):
        try:
            await auth_store.revoke_family(payload["fam"], reason="logout")
            await auth_store.audit("logout", username=payload.get("sub"), success=True)
        except Exception:
            pass
    response.delete_cookie(key="access_token", path="/",
                           samesite=_COOKIE_SAMESITE, secure=_COOKIE_SECURE)
    response.delete_cookie(key="refresh_token", path="/",
                           samesite=_COOKIE_SAMESITE, secure=_COOKIE_SECURE)
    return {"success": True, "message": "Logged out"}


@router.post("/refresh")
async def refresh(request: Request, response: Response):
    """تجديد access token مع تدوير refresh خادمي + كشف إعادة الاستخدام."""
    from core import rbac, auth_store
    ip, ua = _client_meta(request)
    token = request.cookies.get("refresh_token")
    if not token:
        auth = request.headers.get("Authorization") or ""
        if auth.startswith("Bearer "):
            token = auth[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")
    payload = decode_refresh_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    username = payload.get("sub")
    old_jti = payload.get("jti")
    device_id = payload.get("did")
    actor = await rbac.resolve_actor(name=username)
    if not actor.found or actor.active is False:
        raise HTTPException(status_code=401, detail="User no longer valid")
    resolved_name = actor.name or username

    # 🔁 rotate with reuse detection (falls back to stateless if no jti / store down)
    new_jti = f"rt_{uuid.uuid4().hex}"
    fam = payload.get("fam")
    if old_jti:
        try:
            rot = await auth_store.rotate_refresh(old_jti=old_jti, new_jti=new_jti,
                                                  expires_at=_refresh_expiry())
            fam = rot.get("family_id") or fam
            device_id = rot.get("device_id") or device_id
        except auth_store.RefreshReuseError as e:
            await auth_store.audit("refresh", username=resolved_name, success=False, ip=ip,
                                   user_agent=ua, detail=str(e))
            raise HTTPException(status_code=401, detail="refresh token revoked")
        except Exception:
            pass  # store unavailable → degrade to stateless refresh

    access_token = create_access_token(resolved_name, actor.role)
    new_refresh = create_refresh_token(resolved_name, new_jti, family_id=fam, device_id=device_id)
    _set_auth_cookies(response, access_token, new_refresh)
    await auth_store.audit("refresh", username=resolved_name, success=True, ip=ip, user_agent=ua)
    return {
        "access_token": access_token,
        "refresh_token": new_refresh,
        "token_type": "bearer",
        "username": resolved_name,
        "role": actor.role,
        "expires_in_minutes": ACCESS_TOKEN_EXPIRE_MINUTES,
    }


# ---------------- P1: credential management + sessions + audit ----------------

class SetPasswordPayload(BaseModel):
    new_password: str
    email: Optional[str] = None
    target_username: Optional[str] = None  # admins may set for others


class SetPinPayload(BaseModel):
    pin: str
    device_id: Optional[str] = None


@router.post("/set-password")
async def set_password(payload: SetPasswordPayload, current_user: dict = Depends(get_current_user)):
    """تعيين كلمة مرور لحسابي؛ الأدمن/المدير يمكنه التعيين لمستخدم آخر."""
    from core import rbac, auth_store
    if not payload.new_password or len(payload.new_password) < 6:
        raise HTTPException(status_code=400, detail="كلمة المرور 6 أحرف على الأقل")
    target = current_user["username"]
    if payload.target_username and payload.target_username != target:
        actor = await rbac.resolve_actor(user_id=current_user.get("username"),
                                         name=current_user.get("username"),
                                         role_hint=current_user.get("role"))
        rbac.require(rbac.can_approve(actor))  # only privileged roles set others' passwords
        target = payload.target_username
    await auth_store.set_password(target, payload.new_password, email=payload.email)
    await auth_store.audit("set_password", username=target, success=True,
                           detail=f"by={current_user['username']}")
    return {"success": True, "username": target}


@router.post("/set-pin")
async def set_pin(payload: SetPinPayload, request: Request, current_user: dict = Depends(get_current_user)):
    """تعيين PIN سريع بعد أول دخول (مربوط بالجهاز الحالي)."""
    from core import auth_store
    if not payload.pin or not (4 <= len(payload.pin) <= 8) or not payload.pin.isdigit():
        raise HTTPException(status_code=400, detail="PIN من 4 إلى 8 أرقام")
    username = current_user["username"]
    await auth_store.set_pin(username, payload.pin)
    device_id = await auth_store.trust_device(username=username, days=30)
    await auth_store.audit("set_pin", username=username, success=True)
    return {"success": True, "device_id": device_id}


@router.get("/sessions")
async def list_my_sessions(current_user: dict = Depends(get_current_user)):
    from core import auth_store
    return {"success": True, "data": await auth_store.list_sessions(current_user["username"])}


class RevokeSessionPayload(BaseModel):
    family_id: str


@router.post("/sessions/revoke")
async def revoke_my_session(payload: RevokeSessionPayload, current_user: dict = Depends(get_current_user)):
    from core import auth_store
    sessions = await auth_store.list_sessions(current_user["username"])
    if payload.family_id not in {s["family_id"] for s in sessions}:
        raise HTTPException(status_code=404, detail="session_not_found")
    n = await auth_store.revoke_family(payload.family_id, reason="user_revoked")
    await auth_store.audit("revoke_session", username=current_user["username"], success=True)
    return {"success": True, "revoked": n}


@router.get("/audit")
async def get_auth_audit(request: Request, username: Optional[str] = None, limit: int = 100):
    """سجل تدقيق المصادقة — للأدوار المعتمِدة فقط (يمكن تصفيته بمستخدم)."""
    from core import rbac, auth_store
    ident = rbac.extract_identity(request)
    if not ident.get("user_id"):
        raise HTTPException(status_code=401, detail="Not authenticated")
    actor = await rbac.resolve_actor(user_id=ident["user_id"], name=ident["name"],
                                     role_hint=ident["role_hint"])
    rbac.require(rbac.can_approve(actor))
    return {"success": True, "data": await auth_store.list_audit(username=username, limit=limit)}


@router.get("/me")
async def auth_me(current_user: dict = Depends(get_current_user)):
    """يُرجِع بيانات المستخدم الحالي من التوكن."""
    return current_user


# ---------------- P1.5: Emergent-managed Google SSO ----------------
# REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
_EMERGENT_SESSION_DATA_URL = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"


class GoogleSessionPayload(BaseModel):
    session_id: str


async def _find_user_by_email(email: str) -> Optional[dict]:
    """Map a Google identity to an existing app user by email (no auto-provisioning)."""
    if not email:
        return None
    email = email.strip().lower()
    try:
        import routes_users
        for u in await routes_users.get_users():
            ud = u.dict() if hasattr(u, "dict") else dict(u)
            if (ud.get("email") or "").strip().lower() == email:
                return ud
    except Exception:
        pass
    return None


@router.post("/google/session")
async def google_session(payload: GoogleSessionPayload, request: Request, response: Response):
    """تبادل session_id من Emergent Google Auth ← ربط بالبريد ← إصدار JWT التطبيق."""
    import httpx
    from core import rbac, auth_store
    ip, ua = _client_meta(request)
    sid = (payload.session_id or "").strip()
    if not sid:
        raise HTTPException(status_code=400, detail="session_id مطلوب")
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(_EMERGENT_SESSION_DATA_URL, headers={"X-Session-ID": sid})
    except Exception:
        raise HTTPException(status_code=502, detail="تعذّر التحقق من Google")
    if r.status_code != 200:
        await auth_store.audit("google_login", success=False, ip=ip, user_agent=ua, detail="bad_session")
        raise HTTPException(status_code=401, detail="جلسة Google غير صالحة")
    data = r.json() or {}
    email = (data.get("email") or "").strip().lower()
    user = await _find_user_by_email(email)
    if not user:
        await auth_store.audit("google_login", username=email, success=False, ip=ip,
                               user_agent=ua, detail="email_not_linked")
        raise HTTPException(status_code=403, detail="هذا البريد غير مرتبط بأي مستخدم في النظام")
    if user.get("isActive") is False:
        raise HTTPException(status_code=403, detail="هذا الحساب معطل")
    actor = await rbac.resolve_actor(name=user.get("name"))
    resolved_name = actor.name or user.get("name")
    result = await _issue_tokens(response, resolved_name, actor.role)
    await auth_store.audit("google_login", username=resolved_name, success=True, ip=ip,
                           user_agent=ua, detail=f"email={email}")
    return {**result, "email": email, "picture": data.get("picture")}
