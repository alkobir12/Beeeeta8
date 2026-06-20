# Test Credentials

## Workshop ERP Login (name-only login — no password)
Login form: enter the username in the "اسم المستخدم" field and click "دخول".

| Username (اسم المستخدم) | Role        | Can approve (Four-Eyes)? |
|-------------------------|-------------|--------------------------|
| `مدير`                  | admin       | ✅ yes                   |
| `احمد1`                 | supervisor  | ✅ yes                   |
| `فرج1`                  | accountant  | ❌ no                    |
| `مستخدم اختبار`         | technician  | ❌ no                    |

## RBAC / Four-Eyes notes (Phase 3)
- Approver roles (can approve sensitive runtime actions): `admin, manager, supervisor` (env `RUNTIME_APPROVER_ROLES`).
- Strict Four-Eyes is ON (`ACTION_RUNTIME_ENFORCE_4EYES=true`): a user CANNOT approve their own draft → 403 `four_eyes_violation`. A DIFFERENT approver-role user must approve.
- Identity reaches backend via headers `x-user-id` / `x-user-role` (ASCII; Arabic name goes in request body `by`/`approver`).

## Finance-actions API (Phase 4) — RBAC protected, posts via AccountingEngine
- `POST /api/finance-actions/invoice`  (needs invoices.create OR journal_entries.create)
- `POST /api/finance-actions/payment`  (needs debts.settle OR operations.settle)
- `POST /api/finance-actions/expense`  (needs journal_entries.create)
