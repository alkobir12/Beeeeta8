# 11_AUTHORIZATION_MATRIX (static, all 512 endpoints)

Total endpoints: **512** · mutating(POST/PUT/PATCH/DELETE): **272** · financial-domain: **150**

## Totals by classification

- PUBLIC_INTENTIONAL: 17
- AUTHZ_COMPLETE: 0
- ROLE_CHECK_ONLY: 34
- AUTH_ONLY_NO_OBJECT_CHECK: 379
- MISSING_AUTHZ: 82
- UNKNOWN: 0

**SUM = 512 (must equal 512)**

## 🔴 MISSING_AUTHZ (sensitive mutating, no role check in handler) — 82

- `DELETE /api/accounts-chart/reset  [routes_accounts_chart.py]`
- `DELETE /api/accounts-chart/{account_id}  [routes_accounts_chart.py]`
- `DELETE /api/finance/budgets/{budget_id}  [routes_finance.py]`
- `DELETE /api/finance/journal-entries/{entry_id}  [routes_finance.py]`
- `DELETE /api/finance/reset-all-data  [routes_finance.py]`
- `DELETE /api/finance/reset-ops-journals-keep-debts  [routes_finance.py]`
- `DELETE /api/users/{user_id}  [routes_users.py]`
- `PATCH /api/accounts/{account_id}/touch  [routes_accounts_extended.py]`
- `POST /api/accounts  [routes_accounts_extended.py]`
- `POST /api/accounts-chart  [routes_accounts_chart.py]`
- `POST /api/accounts-chart/init-defaults  [routes_accounts_chart.py]`
- `POST /api/accounts-chart/{account_id}/adjust  [routes_accounts_chart.py]`
- `POST /api/accounts/init-defaults  [routes_accounts_extended.py]`
- `POST /api/accounts/reindex-display-codes  [routes_accounts_extended.py]`
- `POST /api/cleanup/split-parts-services  [routes_cleanup.py]`
- `POST /api/employee-performance  [routes_payroll.py]`
- `POST /api/finance-bot/auto-link  [routes_finance_bot.py]`
- `POST /api/finance-bot/chat  [routes_finance_bot.py]`
- `POST /api/finance-bot/detect-contradictions  [routes_finance_bot.py]`
- `POST /api/finance-bot/evidence/upload  [routes_finance_bot.py]`
- `POST /api/finance/ar-repair  [routes_finance.py]`
- `POST /api/finance/ar/migrate-operations-workshop  [routes_finance.py]`
- `POST /api/finance/audit-system  [routes_finance.py]`
- `POST /api/finance/budgets  [routes_finance.py]`
- `POST /api/finance/chart-of-accounts  [routes_finance.py]`
- `POST /api/finance/journal-entries  [routes_finance.py]`
- `POST /api/finance/period-close  [routes_finance.py]`
- `POST /api/finance/reports/apply-bank-revenue-policy  [routes_finance.py]`
- `POST /api/finance/reports/migrate-legacy-codes  [routes_finance.py]`
- `POST /api/finance/reports/reclassify-payment-accounts  [routes_finance.py]`
- `POST /api/finance/reports/reclassify-revenue-sub-accounts  [routes_finance.py]`
- `POST /api/finance/reports/reclassify-vehicle-workshop-dues  [routes_finance.py]`
- `POST /api/finance/reports/reconciliation/backfill-journals  [routes_finance.py]`
- `POST /api/finance/reports/repost-bank-and-fix-imbalance  [routes_finance.py]`
- `POST /api/financial-control/approvals  [financial_control/router.py]`
- `POST /api/financial-control/approvals/{request_id}/cancel  [financial_control/router.py]`
- `POST /api/financial-control/approvals/{request_id}/reject  [financial_control/router.py]`
- `POST /api/financial-control/approvals/{request_id}/review  [financial_control/router.py]`
- `POST /api/financial-control/findings/scan  [financial_control/router.py]`
- `POST /api/financial-control/findings/{finding_id}/acknowledge  [financial_control/router.py]`
- `POST /api/financial-control/findings/{finding_id}/assign  [financial_control/router.py]`
- `POST /api/financial-control/findings/{finding_id}/comment  [financial_control/router.py]`
- `POST /api/financial-control/findings/{finding_id}/dismiss  [financial_control/router.py]`
- `POST /api/financial-control/findings/{finding_id}/resolve  [financial_control/router.py]`
- `POST /api/financial-control/findings/{finding_id}/start  [financial_control/router.py]`
- `POST /api/invoices  [routes_invoices.py]`
- `POST /api/notifications/prepare  [routes_approvals.py]`
- `POST /api/profile/upload-logo  [routes_workshop_config.py]`
- `POST /api/references/import-file  [routes_references.py]`
- `POST /api/runtime/approvals/{approval_id}/reject  [routes_action_runtime.py]`
- `POST /api/runtime/approve/{approval_id}  [routes_action_runtime.py]`
- `POST /api/runtime/commit/{draft_id}  [routes_action_runtime.py]`
- `POST /api/runtime/drafts/{draft_id}/commit  [routes_action_runtime.py]`
- `POST /api/runtime/drafts/{draft_id}/discard  [routes_action_runtime.py]`
- `POST /api/runtime/drafts/{draft_id}/patch  [routes_action_runtime.py]`
- `POST /api/runtime/drafts/{draft_id}/request_approval  [routes_action_runtime.py]`
- `POST /api/runtime/drafts/{draft_id}/spawn_supplier  [routes_action_runtime.py]`
- `POST /api/runtime/execute  [routes_action_runtime.py]`
- `POST /api/runtime/executions/{execution_id}/rollback  [routes_action_runtime.py]`
- `POST /api/runtime/intent/execute  [routes_action_runtime.py]`
- `POST /api/runtime/intent/parse  [routes_action_runtime.py]`
- `POST /api/runtime/power  [routes_action_runtime.py]`
- `POST /api/runtime/rollback/{execution_id}  [routes_action_runtime.py]`
- `POST /api/salaries  [routes_payroll.py]`
- `POST /api/salary-records  [routes_payroll.py]`
- `POST /api/smart-accounting/accounts/track-usage  [routes_smart_accounting.py]`
- `POST /api/smart-accounting/operations/{op_id}/confirm-via-supplier-balance  [routes_smart_accounting.py]`
- `POST /api/smart-accounting/supplier-balance-payment  [routes_smart_accounting.py]`
- `POST /api/smart-accounting/vehicle/{vehicle_id}/archive  [routes_smart_accounting.py]`
- `POST /api/users  [routes_users.py]`
- `POST /api/vehicles/compare-diagnostics  [routes_vehicle_files.py]`
- `POST /api/vehicles/{vehicle_id}/upload-file  [routes_vehicle_files.py]`
- `POST /api/vehicles/{vehicle_id}/upload-file  [server.py]`
- `PUT /api/accounts-chart/{account_id}  [routes_accounts_chart.py]`
- `PUT /api/accounts/{account_id}  [routes_accounts_extended.py]`
- `PUT /api/finance/budgets/{budget_id}  [routes_finance.py]`
- `PUT /api/finance/journal-entries/{entry_id}  [routes_finance.py]`
- `PUT /api/invoices/{invoice_id}  [routes_invoices.py]`
- `PUT /api/profile  [routes_workshop_config.py]`
- `PUT /api/salary-records/{record_id}  [routes_payroll.py]`
- `PUT /api/user-layouts/{user_id}/{page}  [routes_user_layouts.py]`
- `PUT /api/users/{user_id}  [routes_users.py]`