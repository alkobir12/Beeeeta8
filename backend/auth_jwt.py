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
ACCESS_TOKEN_EXPIRE_DAYS = 30  # 30 days for the name-only login UX


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


def create_access_token(username: str) -> str:
    """إنشاء JWT access token صالح لـ 30 يوم."""
    payload = {
        "sub": username,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS),
        "type": "access",
    }
    return jwt.encode(payload, _get_jwt_secret(), algorithm=JWT_ALGORITHM)


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
    """Dependency: يتطلب توكن صالح."""
    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return {"username": payload.get("sub"), "exp": payload.get("exp")}


async def get_current_user_optional(request: Request) -> Optional[dict]:
    """Dependency permissive: يُرجِع المستخدم إن وُجد، None إذا لا توكن."""
    token = _extract_token(request)
    if not token:
        return None
    payload = decode_token(token)
    if not payload:
        return None
    return {"username": payload.get("sub"), "exp": payload.get("exp")}


# =========================================
# Auth Router
# =========================================
router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginPayload(BaseModel):
    username: str


@router.post("/login")
async def login(payload: LoginPayload, response: Response):
    """
    تسجيل الدخول بالاسم فقط (بدون كلمة مرور — حسب اختيار المالك).
    يُرجِع JWT token + يضبط httpOnly cookie.
    """
    username = (payload.username or "").strip()
    if not username or len(username) > 100:
        raise HTTPException(status_code=400, detail="اسم المستخدم مطلوب")

    token = create_access_token(username)
    # Set httpOnly cookie for additional defense in depth
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=False,  # set True if HTTPS-only
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_DAYS * 24 * 3600,
        path="/",
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "username": username,
        "expires_in_days": ACCESS_TOKEN_EXPIRE_DAYS,
    }


@router.post("/logout")
async def logout(response: Response):
    """مسح cookie الجلسة."""
    response.delete_cookie(key="access_token", path="/")
    return {"success": True, "message": "Logged out"}


@router.get("/me")
async def auth_me(current_user: dict = Depends(get_current_user)):
    """يُرجِع بيانات المستخدم الحالي من التوكن."""
    return current_user
