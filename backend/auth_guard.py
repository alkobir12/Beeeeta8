"""حارس المصادقة العام (pure-ASGI helper).

يفرض JWT صالحاً على كل مسارات /api/* عدا قائمة بيضاء صريحة.
يُستدعى من داخل SecurityHeadersAndRateLimitMiddleware في server.py.
"""
from __future__ import annotations

from typing import Dict, Optional

from auth_jwt import decode_token

# مسارات عامة مطابقة تماماً
_PUBLIC_EXACT = {
    "/",
    "/health",
    "/api/health",
    "/api/auth/login",
    "/api/auth/refresh",
    "/api/auth/logout",
    "/api/auth/google/session",  # تبادل جلسة Google قبل تسجيل الدخول (عام)
}

# بادئات مسارات عامة
_PUBLIC_PREFIX = (
    "/api/auth/login",
    "/api/auth/refresh",
    "/api/auth/logout",
    "/api/auth/google/session",
    "/api/approvals/public/",   # روابط الاعتماد العامة بالتوكن
)


def is_public_path(path: str, method: str) -> bool:
    """هل المسار معفى من التحقق؟"""
    if method == "OPTIONS":  # CORS preflight
        return True
    if not path.startswith("/api/"):
        # الخلفية تخدم /api و /health فقط؛ اترك غير ذلك يمرّ (probes/SPA)
        return True
    if path in _PUBLIC_EXACT:
        return True
    for pref in _PUBLIC_PREFIX:
        if path.startswith(pref):
            return True
    return False


def _parse_cookies(cookie_header: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for part in (cookie_header or "").split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def extract_token(headers: Dict[str, str]) -> Optional[str]:
    """يقرأ التوكن من Authorization: Bearer أو من كوكي access_token."""
    auth = headers.get("authorization") or ""
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    cookies = _parse_cookies(headers.get("cookie", ""))
    tok = cookies.get("access_token")
    return tok.strip() if tok else None


def authenticate(path: str, method: str, headers: Dict[str, str]) -> Optional[dict]:
    """يُرجِع payload التوكن إن كان المسار محمياً وصالحاً.

    - إن كان المسار عاماً → يُرجِع {} (اسمح بالمرور).
    - إن كان محمياً وبتوكن صالح → يُرجِع payload (dict غير فارغ).
    - إن كان محمياً بلا توكن/توكن غير صالح → يُرجِع None (ارفض 401).
    """
    if is_public_path(path, method):
        return {}
    token = extract_token(headers)
    if not token:
        return None
    payload = decode_token(token)
    if not payload:
        return None
    return payload
