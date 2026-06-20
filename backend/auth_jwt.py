"""
JWT Authentication module — preserves name-only login UX while securing APIs.

- POST /api/auth/login: accepts {username}, returns JWT access token + sets httpOnly cookie
- get_current_user dependency: validates JWT from Authorization header OR cookie
- Permissive mode: GET endpoints without token still return 200 (back-compat)
- Strict mode: write endpoints (POST/PUT/DELETE) require valid token
"""
import os
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional

import jwt
from fastapi import APIRouter, HTTPException, Request, Response, Depends
from pydantic import BaseModel

JWT_ALGORITHM = "HS256"
# Token lifetimes (decision: short-lived access + 7-day refresh)
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.environ.get("REFRESH_TOKEN_EXPIRE_DAYS", "7"))


def _get_jwt_secret() -> str:
    secret = os.environ.get("JWT_SECRET")
    if not secret or len(secret) < 16:
        # Auto-generate if missing — written to /app/backend/.env on first boot
        # (Safer than crashing during dev; a real prod deploy should set it explicitly.)
        secret = secrets.token_hex(32)
        try:
            env_path = os.path.join(os.path.dirname(__file__), ".env")
            with open(env_path, "a", encoding="utf-8") as f:
                f.write(f"\nJWT_SECRET=\"{secret}\"\n")
            os.environ["JWT_SECRET"] = secret
            print(f"⚠️  JWT_SECRET auto-generated and written to {env_path}")
        except Exception as e:
            print(f"⚠️  JWT_SECRET in-memory only (could not persist): {e}")
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


def create_refresh_token(username: str) -> str:
    """توكن تجديد طويل العمر (لا يُستخدم للتصريح، فقط لإصدار access جديد)."""
    payload = {
        "sub": username,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        "type": "refresh",
    }
    return jwt.encode(payload, _get_jwt_secret(), algorithm=JWT_ALGORITHM)


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
    username: str


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    """httpOnly cookies — دفاع في العمق إضافةً إلى Bearer header."""
    response.set_cookie(
        key="access_token", value=access_token, httponly=True, secure=False,
        samesite="lax", max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60, path="/",
    )
    response.set_cookie(
        key="refresh_token", value=refresh_token, httponly=True, secure=False,
        samesite="lax", max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600, path="/",
    )


@router.post("/login")
async def login(payload: LoginPayload, response: Response):
    """
    تسجيل الدخول بالاسم فقط (بدون كلمة مرور — حسب اختيار المالك).
    Deny-by-default: لا يُصدَر توكن إلا لمستخدم موجود وفعّال في سجل المستخدمين،
    ويُضمَّن دوره الموثَّق داخل JWT (يعتمده RBAC بدل الترويسة الخام).
    """
    username = (payload.username or "").strip()
    if not username or len(username) > 100:
        raise HTTPException(status_code=400, detail="اسم المستخدم مطلوب")

    # 🔐 حلّ الهوية من السجل — المستخدم غير المعروف/المعطّل لا يحصل على توكن
    from core import rbac
    actor = await rbac.resolve_actor(name=username)
    if not actor.found:
        raise HTTPException(status_code=401, detail="اسم المستخدم غير معروف")
    if actor.active is False:
        raise HTTPException(status_code=403, detail="هذا الحساب معطل")

    resolved_name = actor.name or username
    access_token = create_access_token(resolved_name, actor.role)
    refresh_token = create_refresh_token(resolved_name)
    _set_auth_cookies(response, access_token, refresh_token)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "username": resolved_name,
        "role": actor.role,
        "expires_in_minutes": ACCESS_TOKEN_EXPIRE_MINUTES,
    }


@router.post("/logout")
async def logout(response: Response):
    """مسح cookies الجلسة."""
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/")
    return {"success": True, "message": "Logged out"}


@router.post("/refresh")
async def refresh(request: Request, response: Response):
    """إصدار access token جديد اعتماداً على refresh token (cookie أو Bearer)."""
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
    from core import rbac
    actor = await rbac.resolve_actor(name=username)
    if not actor.found or actor.active is False:
        raise HTTPException(status_code=401, detail="User no longer valid")
    resolved_name = actor.name or username
    access_token = create_access_token(resolved_name, actor.role)
    new_refresh = create_refresh_token(resolved_name)
    _set_auth_cookies(response, access_token, new_refresh)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "username": resolved_name,
        "role": actor.role,
        "expires_in_minutes": ACCESS_TOKEN_EXPIRE_MINUTES,
    }


@router.get("/me")
async def auth_me(current_user: dict = Depends(get_current_user)):
    """يُرجِع بيانات المستخدم الحالي من التوكن."""
    return current_user
