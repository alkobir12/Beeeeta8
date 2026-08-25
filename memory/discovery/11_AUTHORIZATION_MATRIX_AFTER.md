# 11_AUTHORIZATION_MATRIX_AFTER (post-repair, all 512)

## Totals AFTER

- PUBLIC_INTENTIONAL: 17
- AUTHZ_COMPLETE: 110
- AUTH_ONLY_NO_OBJECT_CHECK: 363
- POLICY_DECISION_REQUIRED: 22

**SUM = 512 (must equal 512)**

## POLICY_DECISION_REQUIRED (22) — sensitive mutating, policy not yet enforced (needs owner decision)

- `POST /api/accounts  [routes_accounts_extended.py]`
- `POST /api/employee-performance  [routes_payroll.py]`
- `POST /api/finance-bot/auto-link  [routes_finance_bot.py]`
- `POST /api/finance-bot/chat  [routes_finance_bot.py]`
- `POST /api/finance-bot/detect-contradictions  [routes_finance_bot.py]`
- `POST /api/finance-bot/evidence/upload  [routes_finance_bot.py]`
- `POST /api/notifications/prepare  [routes_approvals.py]`
- `POST /api/profile/upload-logo  [routes_workshop_config.py]`
- `POST /api/references/import-file  [routes_references.py]`
- `POST /api/runtime/drafts/{draft_id}/request_approval  [routes_action_runtime.py]`
- `POST /api/runtime/execute  [routes_action_runtime.py]`
- `POST /api/runtime/intent/execute  [routes_action_runtime.py]`
- `POST /api/runtime/intent/parse  [routes_action_runtime.py]`
- `POST /api/runtime/power  [routes_action_runtime.py]`
- `POST /api/salaries  [routes_payroll.py]`
- `POST /api/salary-records  [routes_payroll.py]`
- `POST /api/vehicles/compare-diagnostics  [routes_vehicle_files.py]`
- `POST /api/vehicles/{vehicle_id}/upload-file  [routes_vehicle_files.py]`
- `POST /api/vehicles/{vehicle_id}/upload-file  [server.py]`
- `PUT /api/profile  [routes_workshop_config.py]`
- `PUT /api/salary-records/{record_id}  [routes_payroll.py]`
- `PUT /api/user-layouts/{user_id}/{page}  [routes_user_layouts.py]`