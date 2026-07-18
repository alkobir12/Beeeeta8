# Auth Testing Notes (P1 / SEC-003) — adapted for this app

This app does NOT use the generic `session_token` cookie pattern. The backend
exchanges the Emergent Google `session_id` for the app's OWN JWT
(`POST /api/auth/google/session` → `{access_token, refresh_token, username, role}`),
mapped to an existing app user BY EMAIL (no auto-provisioning).

## Login methods (POST /api/auth/login)
1. name-only: `{username}` — allowed only while the user has NO credentials set.
2. password: `{username|email, password, remember_device?}` — once a password is set,
   name-only is rejected (401 "كلمة المرور مطلوبة لهذا الحساب").
3. manager quick PIN: `{username: "مدير", pin: "123123"}` — accepts a new device,
   then `remember_device=true` issues a trusted device id. Other users still require
   `{username, pin, device_id}` from `POST /api/auth/set-pin`.

## Manager quick-login checks
1. PIN login succeeds without `device_id` and returns access/refresh tokens.
2. A wrong PIN returns 401; repeated failures reach the temporary lockout.
3. A successful login resets the effective failure window without deleting audit history.
4. Login cookies remain Secure + SameSite=None; `/auth/me` and refresh rotation work.
5. Login UI shows fixed username `مدير`, a six-digit PIN input, and password fallback.
6. Production calls its own same-origin `/api`; preview-edge preflight may normalize the
   response origin to `*`, while the backend's actual response still carries credentials.

## Google SSO flow (frontend)
- Login page button → `https://auth.emergentagent.com/?redirect=<origin>/`
- Returns to `<origin>/#session_id=...` → App.js renders `pages/AuthCallback.jsx`
  synchronously (before routing) → POST /api/auth/google/session → app JWT stored.
- Email must match an existing user's email field, else 403
  "هذا البريد غير مرتبط بأي مستخدم في النظام".

## Backend test suite
`cd /app/backend && python -m pytest tests/test_auth_p1_iter256.py -q` (8 tests)
Uses header `x-ratelimit-bypass: $RATE_LIMIT_BYPASS_TOKEN` (backend/.env) to skip
the in-memory rate limiter. Suite is self-cleaning (removes credentials it creates
for «مستخدم اختبار»).

The manager seed is environment-driven: `MANAGER_QUICK_USERNAME` and
`MANAGER_QUICK_PIN`. Startup stores only a bcrypt hash in MongoDB and fails fast if
the configured PIN is not exactly six digits.

## Simulating a Google session for E2E (no real Google account)
Not possible without a real Emergent session_id; test the error paths instead:
- `POST /api/auth/google/session {"session_id": ""}` → 400
- `POST /api/auth/google/session {"session_id": "fake"}` → 401
