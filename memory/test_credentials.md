# Test Credentials

## Workshop ERP Login — P1 Production Auth (multi-method)
`POST /api/auth/login` accepts: `{username|email, password?, pin?, device_id?, remember_device?}`

| Username (اسم المستخدم) | Role        | Can approve (Four-Eyes)? | Login method |
|-------------------------|-------------|--------------------------|--------------|
| `مدير`                  | admin       | ✅ yes                   | name-only (no password set) |
| `احمد1`                 | supervisor  | ✅ yes                   | name-only (no password set) |
| `فرج1`                  | accountant  | ❌ no                    | name-only (no password set) |
| `مستخدم اختبار`         | technician  | ❌ no                    | name-only (test suites may temporarily set a password from `TEST_USER_PASSWORD` in `/app/backend/.env` — they clean up after) |

## 🔐 Auth model (P1 / SEC-003 — 2026-07-07)
- **name-only** login works ONLY while the user has NO credentials set (back-compat).
- Once a password is set (Settings → الملف الشخصي → أمان الحساب), name-only is
  rejected with 401 «كلمة المرور مطلوبة لهذا الحساب».
- **PIN login**: `{username, pin, device_id}` — device_id issued by
  `POST /api/auth/set-pin` or `remember_device=true` on password login.
  Stored client-side in localStorage key `trusted_device`.
- **Google SSO**: login page button → auth.emergentagent.com → returns
  `#session_id=...` → `POST /api/auth/google/session`. Maps by EMAIL to an
  existing user (no auto-provisioning). No Google test account is linked yet.
- Refresh ROTATION + reuse detection: reusing an old refresh token → 401 and
  the whole token family is revoked.
- Brute force: 5 failed login attempts in 15 min → 429 lockout.
- Sessions: `GET /api/auth/sessions`, `POST /api/auth/sessions/revoke {family_id}`.
- Audit: `GET /api/auth/audit` (approver roles only).

## Rate-limit bypass for automated tests
Backend middleware skips rate limiting when header
`x-ratelimit-bypass: $RATE_LIMIT_BYPASS_TOKEN` matches `/app/backend/.env`.
Test suites load it via dotenv (see `tests/test_auth_p1_iter256.py`).

## RBAC / Four-Eyes notes
- Approver roles: `admin, manager, supervisor` (env `RUNTIME_APPROVER_ROLES`).
- Strict Four-Eyes ON: proposer cannot approve own draft → 403 `four_eyes_violation`.
- Approve+auto-commit endpoint: `POST /api/runtime/approvals/{id}/approve`.
  Aliases: `/api/runtime/approve/{approval_id}` (approve only) +
  `/api/runtime/commit/{draft_id}`.

## Finance-actions API — RBAC protected (JWT), posts via AccountingEngine
- `POST /api/finance-actions/invoice`  (needs invoices.create OR journal_entries.create)
- `POST /api/finance-actions/payment`  (needs debts.settle OR operations.settle)
- `POST /api/finance-actions/expense`  (needs journal_entries.create)
