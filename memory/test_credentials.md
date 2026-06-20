# Test Credentials

## Workshop ERP Login (name-only login — no password)
Login form: enter the username in the "اسم المستخدم" field and click "دخول".
Deny-by-default: ONLY users that exist & are active in the user store can log in and
receive a JWT. Unknown usernames return 401 ("اسم المستخدم غير معروف").

| Username (اسم المستخدم) | Role        | Can approve (Four-Eyes)? |
|-------------------------|-------------|--------------------------|
| `مدير`                  | admin       | ✅ yes                   |
| `احمد1`                 | supervisor  | ✅ yes                   |
| `فرج1`                  | accountant  | ❌ no                    |
| `مستخدم اختبار`         | technician  | ❌ no                    |

## 🔐 Auth model (UPDATED — JWT-based RBAC, headers no longer trusted)
- `POST /api/auth/login {username}` → returns `{access_token, refresh_token, role, expires_in_minutes}`,
  embeds the authenticated `role` inside the signed JWT, and sets httpOnly cookies
  (`access_token`, `refresh_token`).
- Access token: ~60 min (`ACCESS_TOKEN_EXPIRE_MINUTES`). Refresh token: 7 days (`REFRESH_TOKEN_EXPIRE_DAYS`).
- `POST /api/auth/refresh` → mints a new access token from the refresh cookie/Bearer.
- `GET /api/auth/me` → `{username, role, exp}` from the validated token.
- RBAC identity/role is derived ONLY from the signed JWT (`core/rbac.extract_identity`
  → `auth_jwt.identity_from_request`). The old spoofable `x-user-role` / `x-user-id`
  headers are IGNORED. No valid token ⇒ role "unknown" ⇒ 403 (deny-by-default).
- Frontend attaches the Bearer token automatically (utils/authToken.js) and silently
  refreshes on 401.

## RBAC / Four-Eyes notes
- Approver roles (can approve sensitive runtime actions): `admin, manager, supervisor`
  (env `RUNTIME_APPROVER_ROLES`).
- Strict Four-Eyes is ON (`ACTION_RUNTIME_ENFORCE_4EYES=true`): a user CANNOT approve
  their own draft → 403 `four_eyes_violation`. A DIFFERENT approver-role user must approve.
- Approver identity for 4-eyes now comes from the JWT (`sub`), not request body fields.

## Finance-actions API — RBAC protected (JWT), posts via AccountingEngine
- `POST /api/finance-actions/invoice`  (needs invoices.create OR journal_entries.create)
- `POST /api/finance-actions/payment`  (needs debts.settle OR operations.settle)
- `POST /api/finance-actions/expense`  (needs journal_entries.create)
