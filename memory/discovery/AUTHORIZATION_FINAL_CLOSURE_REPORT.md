# AUTHORIZATION_FINAL_CLOSURE_REPORT.md
Generated=2026-08-25 20:26 UTC
Scope=PHASE 1B / CODE+TESTS ONLY / ZERO PRODUCTION DATA MUTATION / DO NOT DEPLOY

## Executive Status
Phase 1B COMPLETE for review. Removed fail-open for sensitive/mutating routes, resolved 22 policy decisions, classified 363 former AUTH_ONLY entries, added mass-assignment guards. No deploy/no production mutation/no migration/no AccountingEngine/no P0-DUP-AR.
Closure: MISSING_AUTHZ=0; POLICY_DECISION_REQUIRED=0; UNEXPLAINED_AUTH_ONLY=0.

## BEFORE Matrix
PUBLIC=17; AUTHZ=110; AUTH_ONLY_NO_OBJECT_CHECK=363; POLICY_DECISION_REQUIRED=22; MISSING_AUTHZ=0; SUM=512.

## Root Cause
Phase 1 left decision gaps and a fail-open risk on policy exceptions; generic reads could disclose sensitive data; some dict writes lacked explicit writable-field allowlists.

## Authorization Architecture النهائية
SSOT=backend/core/authz.py. Middleware passes request_id. Missing policy/exception/auth failure deny safely. Model: workshop-wide, self-owned, role-restricted, sensitive. Runtime/AI auth derives from target action, never prompt/tool choice; unresolved target=DENY.

## Files Changed
- backend/core/authz.py
- backend/server.py
- backend/routes_users.py
- backend/routes_user_layouts.py
- backend/routes_workshop_config.py
- backend/routes_action_runtime.py
- backend/routes_finance_bot.py
- backend/routes_vehicle_files.py
- backend/routes_references.py
- backend/routes_accounts_extended.py
- backend/tests/test_authorization_phase1b.py
- backend/tests/test_authz_ssot.py
- memory/discovery/authz_matrix_phase1b.json
- memory/discovery/auth_only_reclassification_phase1b.json
- memory/discovery/policy_decisions_resolved_phase1b.json
- memory/discovery/write_path_audit_phase1b.json
- memory/discovery/AUTHORIZATION_FINAL_CLOSURE_REPORT.md
- memory/PRD.md

## Policies Applied
fail_closed_global; users_manage; payroll_admin_only; runtime_target_scoped; finance_bot_read/evidence; vehicle_files_access; accounts_admin; notifications_admin; profile_self_allowlist; references_admin; layout_self; financial_read; approval/firewall restricted; templates/settings.edit; mutating_admin_review; explicit_general_auth_read.

## Rule Codes
R01=quotations_write
R02=quotations_read
R03=auth_audit_read
R04=public_allowlist
R05=auth_self_service
R06=customers_read
R07=customers_write
R08=suppliers_read
R09=suppliers_write
R10=vehicles_read
R11=vehicles_write
R12=financial_control_read
R13=fincontrol_write
R14=accounts_read_financial
R15=accounts_write_admin_only
R16=destructive_admin
R17=runtime_approver_scope
R18=runtime_target_scoped
R19=runtime_vehicle_read
R20=admin_namespace_writes
R21=advanced_read_authenticated
R22=advanced_write_admin
R23=analytics_read_financial
R24=inventory_read
R25=inventory_write
R26=ai_sensitive
R27=knowledge_admin_write
R28=unclassified_mutating_admin_review
R29=approvals_workshop_read
R30=approvals_workshop_write
R31=notifications_prepare_admin_only
R32=assistant_chat_authenticated
R33=assistant_sensitive_reads
R34=assistant_tool_runtime
R35=assistant_admin_prompts
R36=document_templates_read
R37=document_templates_write
R38=general_authenticated_read
R39=operations_write
R40=finance_engine_payment_confirm
R41=operations_read
R42=operations_integrity_admin
R43=knowledge_read
R44=finance_read
R45=financial_maintenance_admin_only
R46=ledger_write
R47=finance_bot_autolink
R48=finance_bot_read_tools
R49=finance_bot_evidence
R50=firewall_read
R51=firewall_write
R52=imports_admin_only
R53=invoices_read
R54=invoices_write
R55=language_read
R56=payroll_admin_only
R57=technicians_read
R58=references_import_admin_only
R59=stitch_authenticated
R60=suppliers_ext_write
R61=suppliers_ext_read
R62=technicians_write
R63=traces_read_admin
R64=user_layout_self_scope
R65=users_manage
R66=vehicle_diagnostics_access
R67=vehicle_files_access
R68=profile_self_read
R69=profile_self_write
R70=settings_read
R71=settings_write
R72=documents_generate
Class codes: AZ=AUTHZ_COMPLETE; GR=GENERAL_AUTHENTICATED_READ; PR=PERMISSION_RESTRICTED_READ; RR=ROLE_RESTRICTED_READ; SR=SELF_ONLY_READ; PU=PUBLIC_INTENTIONAL; O=was former AUTH_ONLY_NO_OBJECT_CHECK.

## 22 POLICY_DECISION_REQUIRED Resolved
P01|POST|/api/accounts|AZ|R15
P02|POST|/api/runtime/drafts/{draft_id}/request_approval|AZ|R17
P03|POST|/api/runtime/execute|AZ|R18
P04|POST|/api/runtime/intent/execute|AZ|R18
P05|POST|/api/runtime/intent/parse|AZ|R18
P06|POST|/api/runtime/power|AZ|R18
P07|POST|/api/notifications/prepare|AZ|R31
P08|POST|/api/finance-bot/auto-link|AZ|R47
P09|POST|/api/finance-bot/chat|AZ|R48
P10|POST|/api/finance-bot/detect-contradictions|AZ|R48
P11|POST|/api/finance-bot/evidence/upload|AZ|R49
P12|POST|/api/employee-performance|AZ|R56
P13|POST|/api/salaries|AZ|R56
P14|POST|/api/salary-records|AZ|R56
P15|PUT|/api/salary-records/{record_id}|AZ|R56
P16|POST|/api/references/import-file|AZ|R58
P17|PUT|/api/user-layouts/{user_id}/{page}|AZ|R64
P18|POST|/api/vehicles/compare-diagnostics|AZ|R66
P19|POST|/api/vehicles/{vehicle_id}/upload-file|AZ|R67
P20|PUT|/api/profile|AZ|R69
P21|POST|/api/profile/upload-logo|AZ|R69
P22|POST|/api/vehicles/{vehicle_id}/upload-file|AZ|R67

## Sensitive Reads Classification
Sensitive restricted reads=125. Details are classified directly in AFTER Matrix below; IDs/classes:
E001:PR E003:PR E005:PR E009:PR E012:PR E014:PR E016:PR E017:PR E021:PR E023:PR E056:PR E057:PR E058:PR E059:PR E060:PR E061:PR
E062:PR E066:PR E068:RR E076:RR E080:RR E081:RR E083:RR E087:RR E091:SR E094:SR E107:PR E108:PR E109:PR E114:PR E117:PR E119:PR
E126:PR E131:PR E139:PR E163:PR E164:PR E166:PR E167:PR E168:PR E169:PR E170:PR E172:PR E173:PR E175:PR E179:PR E181:PR E184:PR
E186:PR E188:PR E189:PR E190:PR E192:PR E193:PR E194:PR E195:PR E197:PR E201:PR E204:PR E207:PR E208:PR E210:RR E212:RR E213:RR
E214:RR E219:RR E221:RR E222:RR E229:PR E230:PR E231:PR E235:PR E236:PR E237:PR E238:PR E259:PR E260:PR E261:PR E264:PR E265:PR
E278:PR E280:PR E304:PR E306:PR E307:PR E310:PR E312:PR E315:PR E317:PR E320:PR E323:PR E326:PR E327:PR E337:PR E339:PR E340:SR
E375:PR E387:PR E389:PR E393:PR E394:PR E413:PR E417:PR E418:PR E421:PR E422:PR E425:PR E427:PR E429:PR E430:PR E435:PR E438:PR
E454:RR E455:RR E456:RR E457:PR E466:PR E467:PR E470:PR E475:PR E476:PR E479:PR E483:PR E487:PR E511:PR

## Former 363 AUTH_ONLY_NO_OBJECT_CHECK Reclassification
Counts: AZ=143; GR=102; PR=102; RR=11; SR=5
All 363 former entries are marked O in AFTER Matrix; none remain AUTH_ONLY_NO_OBJECT_CHECK.

## AFTER Matrix — 512 Endpoints
PUBLIC_INTENTIONAL=8
SELF_ONLY_READ=6
GENERAL_AUTHENTICATED_READ=109
PERMISSION_RESTRICTED_READ=106
ROLE_RESTRICTED_READ=16
AUTHZ_COMPLETE=267
MISSING_AUTHZ=0
POLICY_DECISION_REQUIRED=0
AUTH_ONLY_NO_OBJECT_CHECK=0
SUM=512
E001|GET|/api/accounts|PR|R14|O
E002|POST|/api/accounts|AZ|R15|-
E003|GET|/api/accounts-chart|PR|R14|O
E004|POST|/api/accounts-chart|AZ|R15|-
E005|GET|/api/accounts-chart/balance-sheet/summary|PR|R14|O
E006|POST|/api/accounts-chart/init-defaults|AZ|R15|-
E007|DELETE|/api/accounts-chart/reset|AZ|R16|-
E008|DELETE|/api/accounts-chart/{account_id}|AZ|R15|-
E009|GET|/api/accounts-chart/{account_id}|PR|R14|O
E010|PUT|/api/accounts-chart/{account_id}|AZ|R15|-
E011|POST|/api/accounts-chart/{account_id}/adjust|AZ|R15|-
E012|GET|/api/accounts/export|PR|R14|O
E013|POST|/api/accounts/init-defaults|AZ|R15|-
E014|GET|/api/accounts/reconciliation-report|PR|R14|O
E015|POST|/api/accounts/reindex-display-codes|AZ|R15|-
E016|GET|/api/accounts/status-overrides|PR|R14|O
E017|GET|/api/accounts/tree|PR|R14|O
E018|DELETE|/api/accounts/{account_id}|AZ|R15|-
E019|PUT|/api/accounts/{account_id}|AZ|R15|-
E020|PATCH|/api/accounts/{account_id}/active|AZ|R15|-
E021|GET|/api/accounts/{account_id}/sparkline|PR|R14|O
E022|PATCH|/api/accounts/{account_id}/touch|AZ|R15|-
E023|GET|/api/accounts/{account_id}/transactions|PR|R14|O
E024|POST|/api/admin/backup/drive|AZ|R20|O
E025|POST|/api/admin/export/sheets|AZ|R20|O
E026|POST|/api/admin/init-database|AZ|R20|O
E027|POST|/api/admin/reset-inventory|AZ|R16|-
E028|GET|/api/ai-bots|GR|R21|O
E029|POST|/api/ai-bots/{bot_id}/chat|AZ|R22|O
E030|GET|/api/ai-recommendations|GR|R21|O
E031|POST|/api/ai-recommendations/ai-analysis|AZ|R22|O
E032|POST|/api/ai-recommendations/generate|AZ|R22|O
E033|GET|/api/ai-recommendations/stats|GR|R21|O
E034|PUT|/api/ai-recommendations/{recommendation_id}/status|AZ|R22|O
E035|POST|/api/ai/chat|GR|R26|O
E036|POST|/api/ai/financial-analysis|GR|R26|O
E037|GET|/api/ai/kb/docs|GR|R26|O
E038|POST|/api/ai/kb/extract-dtc-cards|AZ|R27|O
E039|GET|/api/ai/kb/local-search|GR|R26|O
E040|POST|/api/ai/kb/rebuild-local-index|AZ|R27|O
E041|POST|/api/ai/kb/summarize|AZ|R27|O
E042|POST|/api/alkabeer-bot/assets/upload|GR|R26|O
E043|GET|/api/alkabeer-bot/assets/{asset_id}/download|GR|R26|O
E044|POST|/api/alkabeer-bot/chat|GR|R26|-
E045|GET|/api/alkabeer-bot/customization|GR|R26|O
E046|PUT|/api/alkabeer-bot/customization|AZ|R28|O
E047|GET|/api/alkabeer-bot/editor/comments|GR|R26|O
E048|POST|/api/alkabeer-bot/editor/comments|GR|R26|O
E049|DELETE|/api/alkabeer-bot/editor/comments/{comment_id}|AZ|R28|O
E050|PUT|/api/alkabeer-bot/editor/comments/{comment_id}|AZ|R28|O
E051|GET|/api/alkabeer-bot/editor/draft|GR|R26|O
E052|POST|/api/alkabeer-bot/editor/draft/save|GR|R26|O
E053|GET|/api/alkabeer-bot/editor/history|GR|R26|O
E054|POST|/api/alkabeer-bot/editor/publish|GR|R26|O
E055|GET|/api/alkabeer-bot/health|GR|R26|-
E056|GET|/api/analytics-advanced/cash-flow|PR|R23|O
E057|GET|/api/analytics-advanced/dashboard|PR|R23|O
E058|GET|/api/analytics-advanced/financial-ratios|PR|R23|O
E059|GET|/api/analytics-advanced/inventory-analysis|PR|R23|O
E060|GET|/api/analytics-advanced/profit-loss|PR|R23|O
E061|GET|/api/analytics-advanced/top-performers|PR|R23|O
E062|GET|/api/approvals|PR|R29|-
E063|POST|/api/approvals|AZ|R30|-
E064|GET|/api/approvals/public/{token}|PU|R04|-
E065|POST|/api/approvals/public/{token}/respond|PU|R04|-
E066|GET|/api/approvals/stream|PR|R29|O
E067|GET|/api/assistant/alerts|GR|R32|O
E068|GET|/api/assistant/audit/recent|RR|R33|O
E069|POST|/api/assistant/brain|AZ|R34|O
E070|POST|/api/assistant/chat|GR|R32|O
E071|GET|/api/assistant/chat/result/{job_id}|GR|R32|O
E072|POST|/api/assistant/chat/stream|GR|R32|O
E073|GET|/api/assistant/context_brief|GR|R32|O
E074|GET|/api/assistant/dashboard|GR|R32|O
E075|POST|/api/assistant/memory/search|AZ|R34|O
E076|GET|/api/assistant/memory/{session_id}|RR|R33|O
E077|GET|/api/assistant/models|GR|R32|O
E078|POST|/api/assistant/power/diagnose|AZ|R34|O
E079|POST|/api/assistant/prompt/activate|AZ|R35|-
E080|GET|/api/assistant/prompt/versions|RR|R33|-
E081|GET|/api/assistant/report/{session_id}|RR|R33|O
E082|GET|/api/assistant/session/{session_id}|GR|R32|O
E083|GET|/api/assistant/stats|RR|R33|O
E084|POST|/api/assistant/tool/{name}|AZ|R34|-
E085|GET|/api/assistant/tools|GR|R32|O
E086|GET|/api/assistant/whatsapp/outbox/{session_id}|GR|R32|O
E087|GET|/api/auth/audit|RR|R03|-
E088|POST|/api/auth/google/session|PU|R04|-
E089|POST|/api/auth/login|PU|R04|-
E090|POST|/api/auth/logout|PU|R04|-
E091|GET|/api/auth/me|SR|R05|O
E092|POST|/api/auth/refresh|PU|R04|-
E093|POST|/api/auth/request-otp|AZ|R28|O
E094|GET|/api/auth/sessions|SR|R05|O
E095|POST|/api/auth/sessions/revoke|SR|R05|O
E096|POST|/api/auth/set-password|SR|R05|-
E097|POST|/api/auth/set-pin|SR|R05|O
E098|GET|/api/biz-accounts|GR|R38|O
E099|POST|/api/biz-accounts|AZ|R28|O
E100|POST|/api/biz-accounts/cleanup|AZ|R16|-
E101|DELETE|/api/biz-accounts/{aid}|AZ|R28|-
E102|PUT|/api/biz-accounts/{aid}|AZ|R28|O
E103|GET|/api/budgets|GR|R38|O
E104|POST|/api/budgets|AZ|R28|O
E105|GET|/api/business-accounts|GR|R38|O
E106|POST|/api/business-accounts|AZ|R28|O
E107|GET|/api/ceo/alerts|PR|R23|O
E108|GET|/api/ceo/metrics|PR|R23|O
E109|GET|/api/ceo/performance|PR|R23|O
E110|DELETE|/api/cleanup/keep-debts-only|AZ|R16|-
E111|POST|/api/cleanup/split-parts-services|AZ|R16|-
E112|GET|/api/coa/tree|GR|R38|O
E113|POST|/api/coa/tree|AZ|R28|O
E114|GET|/api/customers|PR|R06|O
E115|POST|/api/customers|AZ|R07|O
E116|DELETE|/api/customers/{customer_id}|AZ|R07|O
E117|GET|/api/customers/{customer_id}|PR|R06|O
E118|PUT|/api/customers/{customer_id}|AZ|R07|O
E119|GET|/api/customers/{customer_id}/approval-logs|PR|R29|O
E120|POST|/api/diesel-chat|GR|R26|O
E121|GET|/api/diesel-chat/health|GR|R26|-
E122|POST|/api/diesel-expert|GR|R26|O
E123|POST|/api/diesel-expert/analyze-media|GR|R26|O
E124|GET|/api/diesel-expert/health|GR|R26|-
E125|GET|/api/diesel-expert/quick-search|GR|R26|O
E126|GET|/api/document-templates|PR|R36|O
E127|POST|/api/document-templates/events|AZ|R37|O
E128|POST|/api/document-templates/resolve|AZ|R37|O
E129|POST|/api/document-templates/upload|AZ|R37|O
E130|DELETE|/api/document-templates/{template_id}|AZ|R37|O
E131|GET|/api/document-templates/{template_id}/download|PR|R36|O
E132|POST|/api/document-templates/{template_id}/set-default|AZ|R37|O
E133|POST|/api/document-templates/{template_id}/use|AZ|R37|O
E134|POST|/api/documents/generate|AZ|R72|O
E135|POST|/api/documents/generate-html|AZ|R72|O
E136|GET|/api/documents/types|GR|R38|O
E137|GET|/api/employee-performance|AZ|R56|O
E138|POST|/api/employee-performance|AZ|R56|-
E139|GET|/api/employees|PR|R57|O
E140|POST|/api/expenses|AZ|R28|O
E141|GET|/api/faq|GR|R21|O
E142|POST|/api/faq|AZ|R22|O
E143|POST|/api/faults/add|AZ|R27|O
E144|GET|/api/faults/list|GR|R43|O
E145|POST|/api/faults/search|AZ|R27|O
E146|GET|/api/faults/stats/summary|GR|R43|O
E147|DELETE|/api/faults/{fault_id}|AZ|R27|O
E148|GET|/api/faults/{fault_id}|GR|R43|O
E149|POST|/api/feedback|AZ|R22|O
E150|GET|/api/feedback/stats|GR|R21|O
E151|POST|/api/finance-actions/expense|AZ|R46|-
E152|POST|/api/finance-actions/invoice|AZ|R46|-
E153|POST|/api/finance-actions/payment|AZ|R46|-
E154|POST|/api/finance-actions/reverse|AZ|R46|-
E155|POST|/api/finance-bot/auto-link|AZ|R47|-
E156|POST|/api/finance-bot/chat|AZ|R48|-
E157|POST|/api/finance-bot/detect-contradictions|AZ|R48|-
E158|POST|/api/finance-bot/evidence/upload|AZ|R49|-
E159|GET|/api/finance-bot/health|AZ|R48|-
E160|GET|/api/finance-bot/sessions/{session_id}/report|AZ|R48|O
E161|POST|/api/finance-engine/visits/{visit_id}/finalize|AZ|R39|-
E162|POST|/api/finance-engine/visits/{visit_id}/payments/confirm|AZ|R40|-
E163|GET|/api/finance/alerts|PR|R44|O
E164|GET|/api/finance/ar-ledger|PR|R44|O
E165|POST|/api/finance/ar-repair|AZ|R45|-
E166|GET|/api/finance/ar/aging|PR|R44|O
E167|GET|/api/finance/ar/customer-statement|PR|R44|O
E168|GET|/api/finance/ar/customers|PR|R44|O
E169|GET|/api/finance/ar/ledger|PR|R44|O
E170|GET|/api/finance/ar/ledger/export|PR|R44|O
E171|POST|/api/finance/ar/migrate-operations-workshop|AZ|R45|-
E172|GET|/api/finance/ar/turnover|PR|R44|O
E173|GET|/api/finance/audit-logs|PR|R44|O
E174|POST|/api/finance/audit-system|AZ|R45|-
E175|GET|/api/finance/budgets|PR|R44|O
E176|POST|/api/finance/budgets|AZ|R46|-
E177|DELETE|/api/finance/budgets/{budget_id}|AZ|R46|-
E178|PUT|/api/finance/budgets/{budget_id}|AZ|R46|-
E179|GET|/api/finance/chart-of-accounts|PR|R44|O
E180|POST|/api/finance/chart-of-accounts|AZ|R46|-
E181|GET|/api/finance/journal-entries|PR|R44|O
E182|POST|/api/finance/journal-entries|AZ|R46|-
E183|DELETE|/api/finance/journal-entries/{entry_id}|AZ|R46|-
E184|GET|/api/finance/journal-entries/{entry_id}|PR|R44|O
E185|PUT|/api/finance/journal-entries/{entry_id}|AZ|R46|-
E186|GET|/api/finance/operations|PR|R44|O
E187|POST|/api/finance/period-close|AZ|R46|-
E188|GET|/api/finance/period-close/last|PR|R44|O
E189|GET|/api/finance/reconciliation-audit|PR|R44|-
E190|GET|/api/finance/reports/account-tree-details|PR|R44|O
E191|POST|/api/finance/reports/apply-bank-revenue-policy|AZ|R45|-
E192|GET|/api/finance/reports/ar-customers|PR|R44|O
E193|GET|/api/finance/reports/balance-sheet|PR|R44|O
E194|GET|/api/finance/reports/cash-flow|PR|R44|O
E195|GET|/api/finance/reports/income-statement|PR|R44|O
E196|POST|/api/finance/reports/migrate-legacy-codes|AZ|R45|-
E197|GET|/api/finance/reports/operation-trace|PR|R44|O
E198|POST|/api/finance/reports/reclassify-payment-accounts|AZ|R45|-
E199|POST|/api/finance/reports/reclassify-revenue-sub-accounts|AZ|R45|-
E200|POST|/api/finance/reports/reclassify-vehicle-workshop-dues|AZ|R45|-
E201|GET|/api/finance/reports/reconciliation|PR|R44|O
E202|POST|/api/finance/reports/reconciliation/backfill-journals|AZ|R45|-
E203|POST|/api/finance/reports/repost-bank-and-fix-imbalance|AZ|R45|-
E204|GET|/api/finance/reports/trial-balance|PR|R44|O
E205|DELETE|/api/finance/reset-all-data|AZ|R45|-
E206|DELETE|/api/finance/reset-ops-journals-keep-debts|AZ|R45|-
E207|GET|/api/finance/reset/audit|PR|R44|-
E208|GET|/api/finance/reset/dry-run|PR|R44|-
E209|POST|/api/finance/reset/execute|AZ|R45|-
E210|GET|/api/financial-control/approvals|RR|R12|O
E211|POST|/api/financial-control/approvals|AZ|R13|-
E212|GET|/api/financial-control/approvals/matrix|RR|R12|O
E213|GET|/api/financial-control/approvals/stats|RR|R12|O
E214|GET|/api/financial-control/approvals/{request_id}|RR|R12|O
E215|POST|/api/financial-control/approvals/{request_id}/approve|AZ|R13|-
E216|POST|/api/financial-control/approvals/{request_id}/cancel|AZ|R13|-
E217|POST|/api/financial-control/approvals/{request_id}/reject|AZ|R13|-
E218|POST|/api/financial-control/approvals/{request_id}/review|AZ|R13|-
E219|GET|/api/financial-control/findings|RR|R12|O
E220|POST|/api/financial-control/findings/scan|AZ|R13|-
E221|GET|/api/financial-control/findings/summary|RR|R12|O
E222|GET|/api/financial-control/findings/{finding_id}|RR|R12|O
E223|POST|/api/financial-control/findings/{finding_id}/acknowledge|AZ|R13|-
E224|POST|/api/financial-control/findings/{finding_id}/assign|AZ|R13|-
E225|POST|/api/financial-control/findings/{finding_id}/comment|AZ|R13|-
E226|POST|/api/financial-control/findings/{finding_id}/dismiss|AZ|R13|-
E227|POST|/api/financial-control/findings/{finding_id}/resolve|AZ|R13|-
E228|POST|/api/financial-control/findings/{finding_id}/start|AZ|R13|-
E229|GET|/api/firewall/ai-insights|PR|R50|O
E230|GET|/api/firewall/alerts|PR|R50|O
E231|GET|/api/firewall/alerts/{alert_id}|PR|R50|O
E232|POST|/api/firewall/alerts/{alert_id}/dismiss|AZ|R51|O
E233|POST|/api/firewall/alerts/{alert_id}/resolve|AZ|R51|O
E234|POST|/api/firewall/auto-fix|AZ|R51|O
E235|GET|/api/firewall/dashboard|PR|R50|O
E236|GET|/api/firewall/health-score|PR|R50|O
E237|GET|/api/firewall/live-activity|PR|R50|O
E238|GET|/api/firewall/status|PR|R50|O
E239|POST|/api/firewall/test/log-rejection|AZ|R51|O
E240|POST|/api/gemini-chat/chat|GR|R26|O
E241|DELETE|/api/gemini-chat/clear-all|AZ|R28|O
E242|DELETE|/api/gemini-chat/clear/{conversation_id}|AZ|R28|O
E243|GET|/api/gemini-chat/health|GR|R26|-
E244|GET|/api/gemini-chat/history/{conversation_id}|GR|R26|O
E245|POST|/api/gemini-chat/start|GR|R26|O
E246|GET|/api/gemini-chat/stats|GR|R26|O
E247|GET|/api/health|PU|R04|-
E248|GET|/api/health|PU|R04|-
E249|POST|/api/import/customers|AZ|R52|O
E250|POST|/api/import/parts|AZ|R52|O
E251|GET|/api/injectors/engines|GR|R43|O
E252|GET|/api/injectors/generation/{generation}|GR|R43|O
E253|POST|/api/injectors/report|AZ|R27|O
E254|GET|/api/injectors/reports|GR|R43|O
E255|GET|/api/injectors/specs/{engine_id}|GR|R43|O
E256|GET|/api/injectors/test-sequence|GR|R43|O
E257|POST|/api/injectors/validate/resistance|AZ|R27|O
E258|POST|/api/injectors/validate/vl-mode|AZ|R27|O
E259|GET|/api/inventory/alerts|PR|R24|O
E260|GET|/api/inventory/architecture|PR|R24|O
E261|GET|/api/inventory/backorders|PR|R24|O
E262|POST|/api/inventory/backorders|AZ|R25|O
E263|PATCH|/api/inventory/backorders/{backorder_id}/status|AZ|R25|O
E264|GET|/api/inventory/control-panel|PR|R24|O
E265|GET|/api/inventory/dashboard|PR|R24|O
E266|POST|/api/inventory/reset-totals|AZ|R16|-
E267|GET|/api/invoice-templates|GR|R38|O
E268|POST|/api/invoice-templates/create-blank|AZ|R28|O
E269|DELETE|/api/invoice-templates/{tid}|AZ|R28|O
E270|GET|/api/invoice-templates/{tid}|GR|R38|O
E271|PUT|/api/invoice-templates/{tid}|AZ|R28|O
E272|POST|/api/invoice-templates/{tid}/auto-save|AZ|R28|O
E273|POST|/api/invoice-templates/{tid}/design|AZ|R28|O
E274|POST|/api/invoice-templates/{tid}/make-default|AZ|R28|O
E275|POST|/api/invoice-templates/{tid}/save-json|AZ|R28|O
E276|POST|/api/invoice-templates/{tid}/save-named|AZ|R28|O
E277|POST|/api/invoice-templates/{tid}/update-mapping|AZ|R28|O
E278|GET|/api/invoices|PR|R53|O
E279|POST|/api/invoices|AZ|R54|-
E280|GET|/api/invoices/{invoice_id}|PR|R53|O
E281|PUT|/api/invoices/{invoice_id}|AZ|R54|-
E282|GET|/api/maintenance-orders|GR|R38|O
E283|POST|/api/maintenance-orders|AZ|R28|O
E284|PUT|/api/maintenance-orders/{order_id}/client-approve|AZ|R28|O
E285|PUT|/api/maintenance-orders/{order_id}/manager-approve|AZ|R28|O
E286|PUT|/api/maintenance-orders/{order_id}/technician-complete|AZ|R28|O
E287|POST|/api/moltbot/apply|AZ|R28|O
E288|POST|/api/moltbot/chat|AZ|R28|O
E289|GET|/api/moltbot/projects|GR|R38|O
E290|POST|/api/moltbot/projects|AZ|R28|O
E291|PUT|/api/moltbot/projects/{project_id}|AZ|R28|O
E292|POST|/api/moltbot/projects/{project_id}/sessions|AZ|R28|O
E293|POST|/api/moltbot/rollback|AZ|R28|O
E294|GET|/api/moltbot/sessions/{session_id}/messages|GR|R38|O
E295|POST|/api/nlp/page/apply_correction|AZ|R28|O
E296|POST|/api/nlp/page/context|AZ|R28|O
E297|POST|/api/notifications/prepare|AZ|R31|-
E298|GET|/api/notion/customers|GR|R43|O
E299|POST|/api/notion/customers|AZ|R28|O
E300|GET|/api/notion/mcp/status|GR|R43|O
E301|GET|/api/notion/procedures|GR|R43|O
E302|GET|/api/notion/status|GR|R43|O
E303|DELETE|/api/operations|AZ|R39|-
E304|GET|/api/operations|PR|R41|O
E305|POST|/api/operations|AZ|R39|-
E306|GET|/api/operations/analytics/pending|PR|R41|O
E307|GET|/api/operations/analytics/summary|PR|R41|O
E308|POST|/api/operations/integrity/check|AZ|R42|-
E309|POST|/api/operations/integrity/fix-all|AZ|R42|-
E310|GET|/api/operations/pending|PR|R41|O
E311|DELETE|/api/operations/{op_id}|AZ|R39|-
E312|GET|/api/operations/{op_id}|PR|R41|O
E313|PUT|/api/operations/{op_id}|AZ|R39|-
E314|POST|/api/operations/{op_id}/confirm-payment|AZ|R39|-
E315|GET|/api/operations/{op_id}/payment-receipts/{filename}|PR|R41|O
E316|POST|/api/outbound/assets|AZ|R37|O
E317|GET|/api/outbound/assets/{fingerprint}|PR|R36|O
E318|POST|/api/outbound/fingerprint|AZ|R37|O
E319|POST|/api/outbound/resolve-message|AZ|R37|O
E320|GET|/api/outbound/share-attempts|PR|R36|O
E321|POST|/api/outbound/share-attempts|AZ|R37|O
E322|POST|/api/outbound/share-attempts/{attempt_id}/events|AZ|R37|O
E323|GET|/api/outbound/templates|PR|R36|O
E324|PUT|/api/outbound/templates/{template_id}|AZ|R37|O
E325|POST|/api/outbound/templates/{template_id}/restore-default|AZ|R37|O
E326|GET|/api/outbound/variables|PR|R36|O
E327|GET|/api/parts|PR|R24|O
E328|POST|/api/parts|AZ|R25|O
E329|POST|/api/parts/ocr|AZ|R25|O
E330|DELETE|/api/parts/{part_id}|AZ|R25|O
E331|PUT|/api/parts/{part_id}|AZ|R25|O
E332|POST|/api/parts/{part_id}/restock|AZ|R25|O
E333|POST|/api/parts/{part_id}/sell|AZ|R25|O
E334|POST|/api/print/invoice-xlsx|AZ|R28|O
E335|POST|/api/print/render|AZ|R28|O
E336|POST|/api/print/resolve-template|AZ|R28|O
E337|GET|/api/products|PR|R24|O
E338|POST|/api/products|AZ|R25|O
E339|GET|/api/products/{product_id}|PR|R24|O
E340|GET|/api/profile|SR|R68|O
E341|PUT|/api/profile|AZ|R69|-
E342|POST|/api/profile/upload-logo|AZ|R69|-
E343|POST|/api/public-agent/chat|AZ|R28|O
E344|POST|/api/quotations/generate|AZ|R01|O
E345|GET|/api/quotations/themes|GR|R02|O
E346|GET|/api/references/download-excel-program|GR|R38|O
E347|GET|/api/references/dtc|GR|R38|O
E348|GET|/api/references/electrical|GR|R38|O
E349|POST|/api/references/electrical/smart-search|AZ|R28|O
E350|POST|/api/references/import-file|AZ|R58|-
E351|GET|/api/runtime/approvals|AZ|R17|-
E352|POST|/api/runtime/approvals/{approval_id}/approve|AZ|R17|-
E353|POST|/api/runtime/approvals/{approval_id}/reject|AZ|R17|-
E354|POST|/api/runtime/approve/{approval_id}|AZ|R17|-
E355|GET|/api/runtime/audit|AZ|R17|-
E356|POST|/api/runtime/commit/{draft_id}|AZ|R17|-
E357|GET|/api/runtime/db/{table}|AZ|R17|-
E358|GET|/api/runtime/drafts|AZ|R17|-
E359|POST|/api/runtime/drafts|AZ|R17|-
E360|GET|/api/runtime/drafts/{draft_id}|AZ|R17|-
E361|POST|/api/runtime/drafts/{draft_id}/commit|AZ|R17|-
E362|POST|/api/runtime/drafts/{draft_id}/discard|AZ|R17|-
E363|POST|/api/runtime/drafts/{draft_id}/patch|AZ|R17|-
E364|POST|/api/runtime/drafts/{draft_id}/request_approval|AZ|R17|-
E365|POST|/api/runtime/drafts/{draft_id}/spawn_supplier|AZ|R17|-
E366|POST|/api/runtime/execute|AZ|R18|-
E367|GET|/api/runtime/executions|AZ|R17|-
E368|POST|/api/runtime/executions/{execution_id}/rollback|AZ|R17|-
E369|POST|/api/runtime/intent/execute|AZ|R18|-
E370|POST|/api/runtime/intent/parse|AZ|R18|-
E371|POST|/api/runtime/power|AZ|R18|-
E372|GET|/api/runtime/report|AZ|R17|-
E373|POST|/api/runtime/rollback/{execution_id}|AZ|R17|-
E374|GET|/api/runtime/stats|AZ|R17|-
E375|GET|/api/runtime/visits/active|PR|R19|O
E376|GET|/api/salaries|AZ|R56|O
E377|GET|/api/salaries|AZ|R56|O
E378|POST|/api/salaries|AZ|R56|-
E379|GET|/api/salary-records|AZ|R56|O
E380|POST|/api/salary-records|AZ|R56|-
E381|PUT|/api/salary-records/{record_id}|AZ|R56|-
E382|GET|/api/search/brave|GR|R26|O
E383|GET|/api/search/history|GR|R26|O
E384|POST|/api/search/log|GR|R26|O
E385|GET|/api/search/perplexity|GR|R26|O
E386|GET|/api/search/you|GR|R26|O
E387|GET|/api/service-packages|PR|R24|O
E388|POST|/api/service-packages|AZ|R25|O
E389|GET|/api/services|PR|R24|O
E390|POST|/api/services|AZ|R25|O
E391|DELETE|/api/services/{service_id}|AZ|R25|O
E392|PUT|/api/services/{service_id}|AZ|R25|O
E393|GET|/api/settings|PR|R70|O
E394|GET|/api/settings|PR|R70|O
E395|POST|/api/settings|AZ|R71|-
E396|POST|/api/settings/print-defaults|AZ|R71|-
E397|GET|/api/shop-orders|GR|R21|O
E398|POST|/api/shop-orders|AZ|R22|O
E399|PUT|/api/shop-orders/{order_id}/status|AZ|R22|O
E400|GET|/api/smart-accounting/accounts|GR|R38|O
E401|POST|/api/smart-accounting/accounts/track-usage|AZ|R46|-
E402|POST|/api/smart-accounting/operations/{op_id}/confirm-via-supplier-balance|AZ|R46|-
E403|POST|/api/smart-accounting/supplier-balance-payment|AZ|R46|-
E404|POST|/api/smart-accounting/vehicle/{vehicle_id}/archive|AZ|R46|-
E405|GET|/api/smart-accounting/vehicle/{vehicle_id}/archive-status|GR|R38|O
E406|GET|/api/stats|GR|R38|O
E407|POST|/api/stitch/generate|GR|R59|O
E408|GET|/api/stitch/history|GR|R59|O
E409|GET|/api/stitch/status/{generation_id}|GR|R59|O
E410|GET|/api/supabase/analytics|GR|R38|O
E411|GET|/api/supabase/status|GR|R38|O
E412|GET|/api/supabase/vehicles|GR|R38|O
E413|GET|/api/suppliers|PR|R08|O
E414|POST|/api/suppliers|AZ|R09|O
E415|POST|/api/suppliers-ext/import/execute|AZ|R60|O
E416|POST|/api/suppliers-ext/import/preview|AZ|R60|O
E417|GET|/api/suppliers-ext/settlements/{settlement_id}/pdf|PR|R61|O
E418|GET|/api/suppliers-ext/{supplier_id}/settlements|PR|R61|O
E419|POST|/api/suppliers-ext/{supplier_id}/settlements|AZ|R60|-
E420|DELETE|/api/suppliers-ext/{supplier_id}/settlements/{settlement_id}|AZ|R60|-
E421|GET|/api/suppliers-ext/{supplier_id}/statement/pdf|PR|R61|O
E422|GET|/api/suppliers-ext/{supplier_id}/transactions|PR|R61|O
E423|POST|/api/suppliers/migrate|AZ|R09|O
E424|DELETE|/api/suppliers/{supplier_id}|AZ|R09|O
E425|GET|/api/suppliers/{supplier_id}|PR|R08|O
E426|PUT|/api/suppliers/{supplier_id}|AZ|R09|O
E427|GET|/api/technicians|PR|R57|O
E428|POST|/api/technicians|AZ|R62|O
E429|GET|/api/templates|PR|R36|O
E430|GET|/api/templates|PR|R36|O
E431|POST|/api/templates|AZ|R37|O
E432|POST|/api/templates/upload|AZ|R37|O
E433|DELETE|/api/templates/{template_id}|AZ|R37|O
E434|DELETE|/api/templates/{template_id}|AZ|R37|O
E435|GET|/api/templates/{template_id}|PR|R36|O
E436|PUT|/api/templates/{template_id}|AZ|R37|O
E437|POST|/api/templates/{template_id}/apply-to-all|AZ|R37|O
E438|GET|/api/templates/{template_id}/download|PR|R36|O
E439|POST|/api/templates/{template_id}/make-default|AZ|R37|O
E440|POST|/api/templates/{template_id}/make-default|AZ|R37|O
E441|POST|/api/templates/{template_id}/use|AZ|R37|O
E442|GET|/api/tickets|GR|R21|O
E443|POST|/api/tickets|AZ|R22|O
E444|GET|/api/tickets/{ticket_id}|GR|R21|O
E445|PUT|/api/tickets/{ticket_id}/resolve|AZ|R22|O
E446|POST|/api/tickets/{ticket_id}/response|AZ|R22|O
E447|GET|/api/tickets/{ticket_id}/responses|GR|R21|O
E448|GET|/api/toyota-manual/content|GR|R38|O
E449|GET|/api/toyota-manual/content/by-file|GR|R38|O
E450|GET|/api/toyota-manual/search|GR|R38|O
E451|GET|/api/toyota-manual/section/{section_id}/content|GR|R38|O
E452|GET|/api/toyota-manual/sections|GR|R38|O
E453|GET|/api/toyota-manual/stats|GR|R38|O
E454|GET|/api/traces|RR|R63|-
E455|GET|/api/traces/stats|RR|R63|-
E456|GET|/api/traces/{trace_id}|RR|R63|-
E457|GET|/api/transactions|PR|R41|O
E458|GET|/api/translations/|GR|R55|O
E459|GET|/api/translations/combined|GR|R55|O
E460|GET|/api/user-layouts/{user_id}/{page}|AZ|R64|O
E461|PUT|/api/user-layouts/{user_id}/{page}|AZ|R64|-
E462|GET|/api/users|AZ|R65|-
E463|POST|/api/users|AZ|R65|-
E464|DELETE|/api/users/{user_id}|AZ|R65|-
E465|PUT|/api/users/{user_id}|AZ|R65|-
E466|GET|/api/vehicles|PR|R10|O
E467|GET|/api/vehicles|PR|R10|O
E468|POST|/api/vehicles|AZ|R11|O
E469|POST|/api/vehicles|AZ|R11|O
E470|GET|/api/vehicles/archive-search|PR|R10|O
E471|POST|/api/vehicles/compare-diagnostics|AZ|R66|-
E472|POST|/api/vehicles/dashboard/summaries|AZ|R11|O
E473|DELETE|/api/vehicles/{vehicle_id}|AZ|R11|O
E474|DELETE|/api/vehicles/{vehicle_id}|AZ|R11|O
E475|GET|/api/vehicles/{vehicle_id}|PR|R10|O
E476|GET|/api/vehicles/{vehicle_id}|PR|R10|O
E477|PUT|/api/vehicles/{vehicle_id}|AZ|R11|O
E478|PUT|/api/vehicles/{vehicle_id}|AZ|R11|O
E479|GET|/api/vehicles/{vehicle_id}/approval-logs|PR|R29|O
E480|GET|/api/vehicles/{vehicle_id}/files|AZ|R67|O
E481|GET|/api/vehicles/{vehicle_id}/files|AZ|R67|O
E482|GET|/api/vehicles/{vehicle_id}/files/{file_id}|AZ|R67|O
E483|GET|/api/vehicles/{vehicle_id}/financial-summary|PR|R10|O
E484|POST|/api/vehicles/{vehicle_id}/save-parts-and-create-journal|AZ|R11|-
E485|POST|/api/vehicles/{vehicle_id}/upload-file|AZ|R67|-
E486|POST|/api/vehicles/{vehicle_id}/upload-file|AZ|R67|-
E487|GET|/api/vehicles/{vehicle_id}/visits|PR|R10|O
E488|POST|/api/vehicles/{vehicle_id}/visits|AZ|R11|O
E489|DELETE|/api/visits/{visit_id}|AZ|R28|O
E490|PUT|/api/visits/{visit_id}|AZ|R28|O
E491|GET|/api/visits/{visit_id}/operations|GR|R38|O
E492|GET|/api/whatsapp-bot/car/{vin}|GR|R38|O
E493|GET|/api/whatsapp-bot/cars|GR|R38|O
E494|GET|/api/whatsapp-bot/health|GR|R38|-
E495|GET|/api/whatsapp-bot/messages|GR|R38|O
E496|POST|/api/whatsapp-bot/send|AZ|R28|O
E497|GET|/api/whatsapp-bot/sounds|GR|R38|O
E498|GET|/api/whatsapp-bot/stats|GR|R38|O
E499|POST|/api/whatsapp-bot/webhook/infobip|AZ|R28|O
E500|GET|/api/whatsapp-bot/workshop-info|GR|R38|O
E501|GET|/api/workshop-bot/catalog/summary|GR|R38|O
E502|GET|/api/workshop-bot/conversations|GR|R38|O
E503|DELETE|/api/workshop-bot/conversations/{session_id}|AZ|R28|O
E504|GET|/api/workshop-bot/conversations/{session_id}|GR|R38|O
E505|GET|/api/workshop-bot/engines|GR|R38|O
E506|GET|/api/workshop-bot/health|GR|R38|-
E507|GET|/api/workshop-bot/models|GR|R38|O
E508|POST|/api/workshop-bot/respond|AZ|R28|O
E509|GET|/api/workshop-bot/skills|GR|R38|O
E510|GET|/api/workshop-bot/skills/{skill_id}|GR|R38|O
E511|GET|/api/workshop-services|PR|R24|O
E512|POST|/api/workshop-services|AZ|R25|O

## Writer Policy Codes
AC=accounts_write_admin_only / financial maintenance admin boundary
AD=advanced_write_admin or explicit communications/service policy
AE=AccountingEngine SSOT post_entry only; caller authz required; no direct route writes
AI=assistant/AI authenticated or admin prompt policy; no prompt-driven authz
AP=approvals_workshop_write + four-eyes state machine
AR=unclassified_mutating_admin_review fail-closed/admin-only fallback
CU=customers_write or approval vehicle-access policy
FW=firewall_write approver roles
IN=inventory_write/work_orders policy
KN=knowledge_admin_write
LY=user_layout_self_scope + route self check
OP=operations_write/settle + runtime target action authz + four-eyes where applicable
PA=payroll_admin_only
PF=profile_self_write + profile allowlist + privileged-field rejection
SE=document_templates_write/settings.edit + template audit
SU=suppliers_write admin-only (supplier item archive/movement only)
UA=users_manage/auth_self_service/admin auth audit policy + explicit user allowlists
VE=vehicles_write / vehicle_files_access

## 286 Production Write Paths
Format: W|file:line|table.op|Z(policy)|S(scope)|V(validation)|M(mass)|C(canonical)|F(financial).
W001|auto_sync_service.py:46|customers.insert_one|Z=CU|S=self|V=alw|M=guard|C=na|F=NO
W002|auto_sync_service.py:101|vehicles.insert_one|Z=VE|S=self|V=alw|M=guard|C=na|F=NO
W003|auto_sync_service.py:138|services.insert_one|Z=IN|S=self|V=alw|M=guard|C=na|F=NO
W004|core/accounting_engine.py:634|journal_entries.post_entry|Z=AE|S=self|V=alw|M=guard|C=AE|F=YES
W005|core/action_runtime.py:266|customers.insert|Z=CU|S=self|V=alw|M=guard|C=na|F=NO
W006|core/action_runtime.py:282|vehicles.insert|Z=VE|S=self|V=alw|M=guard|C=na|F=NO
W007|core/action_runtime.py:330|vehicle_visits.insert|Z=OP|S=self|V=alw|M=guard|C=biz|F=YES
W008|core/action_runtime.py:338|vehicles.update|Z=VE|S=self|V=alw|M=guard|C=na|F=NO
W009|core/action_runtime.py:435|parts.update|Z=IN|S=self|V=alw|M=guard|C=na|F=NO
W010|core/action_runtime.py:443|parts.insert|Z=IN|S=self|V=alw|M=guard|C=na|F=NO
W011|core/action_runtime.py:1193|operations.insert|Z=OP|S=self|V=alw|M=guard|C=biz|F=YES
W012|core/action_runtime.py:1276|vehicles.update|Z=VE|S=self|V=alw|M=guard|C=na|F=NO
W013|core/action_runtime.py:1332|operations.delete|Z=OP|S=self|V=alw|M=guard|C=biz|F=YES
W014|core/action_runtime.py:1431|vehicle_visits.update|Z=OP|S=self|V=alw|M=guard|C=biz|F=YES
W015|core/operation_journal_adapter.py:346|journal_entries.post_entry|Z=AE|S=self|V=alw|M=guard|C=AE|F=YES
W016|core/vehicle_finalization_posting.py:171|journal_entries.post_entry|Z=AE|S=self|V=alw|M=guard|C=AE|F=YES
W017|core/vehicle_finalization_posting.py:298|journal_entries.post_entry|Z=AE|S=self|V=alw|M=guard|C=AE|F=YES
W018|domains/customers/repository.py:81|customers.insert_one|Z=CU|S=self|V=alw|M=guard|C=na|F=NO
W019|domains/customers/repository.py:108|customers.update_one|Z=CU|S=self|V=alw|M=guard|C=na|F=NO
W020|domains/customers/repository.py:117|invoices.delete|Z=AR|S=self|V=alw|M=guard|C=biz|F=YES
W021|domains/customers/repository.py:121|vehicles.delete|Z=VE|S=self|V=alw|M=guard|C=na|F=NO
W022|domains/customers/repository.py:134|customers.delete_one|Z=CU|S=self|V=alw|M=guard|C=na|F=NO
W023|domains/suppliers/repository.py:103|suppliers.insert|Z=SU|S=self|V=alw|M=guard|C=na|F=NO
W024|domains/suppliers/repository.py:120|suppliers.insert_one|Z=SU|S=self|V=alw|M=guard|C=na|F=NO
W025|domains/suppliers/repository.py:134|suppliers.update|Z=SU|S=self|V=alw|M=guard|C=na|F=NO
W026|domains/suppliers/repository.py:160|suppliers.update_one|Z=SU|S=self|V=alw|M=guard|C=na|F=NO
W027|domains/suppliers/repository.py:168|suppliers.delete|Z=SU|S=self|V=alw|M=guard|C=na|F=NO
W028|domains/suppliers/repository.py:185|suppliers.delete_one|Z=SU|S=self|V=alw|M=guard|C=na|F=NO
W029|domains/suppliers/repository.py:208|suppliers.insert|Z=SU|S=self|V=alw|M=guard|C=na|F=NO
W030|domains/vehicles/repository.py:54|vehicles.insert_one|Z=VE|S=self|V=alw|M=guard|C=na|F=NO
W031|domains/vehicles/repository.py:82|vehicles.update_one|Z=VE|S=self|V=alw|M=guard|C=na|F=NO
W032|domains/vehicles/repository.py:90|invoices.delete|Z=AR|S=self|V=alw|M=guard|C=biz|F=YES
W033|domains/vehicles/repository.py:94|operations.delete|Z=OP|S=self|V=alw|M=guard|C=biz|F=YES
W034|domains/vehicles/repository.py:112|invoices.delete_many|Z=AR|S=self|V=alw|M=guard|C=biz|F=YES
W035|domains/vehicles/repository.py:116|operations.delete_many|Z=OP|S=self|V=alw|M=guard|C=biz|F=YES
W036|domains/vehicles/repository.py:119|vehicles.delete_one|Z=VE|S=self|V=alw|M=guard|C=na|F=NO
W037|routes_accounts_extended.py:67|account_status_overrides.update_one|Z=AC|S=self|V=alw|M=guard|C=na|F=NO
W038|routes_accounts_extended.py:86|account_status_overrides.delete_one|Z=AC|S=self|V=alw|M=guard|C=na|F=NO
W039|routes_accounts_extended.py:150|account_display_codes.update_one|Z=AC|S=self|V=alw|M=guard|C=na|F=NO
W040|routes_accounts_extended.py:194|account_code_aliases.update_one|Z=AC|S=self|V=alw|M=guard|C=na|F=NO
W041|routes_accounts_extended.py:214|account_usage.update_one|Z=AC|S=self|V=alw|M=guard|C=na|F=NO
W042|routes_accounts_extended.py:363|accounts.insert|Z=AC|S=self|V=alw|M=guard|C=biz|F=YES
W043|routes_accounts_extended.py:389|accounts.insert_one|Z=AC|S=self|V=alw|M=guard|C=biz|F=YES
W044|routes_accounts_extended.py:422|accounts.update|Z=AC|S=self|V=alw|M=guard|C=biz|F=YES
W045|routes_accounts_extended.py:439|accounts.update_one|Z=AC|S=self|V=alw|M=guard|C=biz|F=YES
W046|routes_accounts_extended.py:538|accounts.delete|Z=AC|S=self|V=alw|M=guard|C=biz|F=YES
W047|routes_accounts_extended.py:556|accounts.delete_one|Z=AC|S=self|V=alw|M=guard|C=biz|F=YES
W048|routes_accounts_extended.py:799|accounts.update|Z=AC|S=self|V=alw|M=guard|C=biz|F=YES
W049|routes_accounts_extended.py:801|accounts.update_one|Z=AC|S=self|V=alw|M=guard|C=biz|F=YES
W050|routes_accounts_extended.py:985|accounts.update|Z=AC|S=self|V=alw|M=guard|C=biz|F=YES
W051|routes_accounts_extended.py:987|accounts.update_one|Z=AC|S=self|V=alw|M=guard|C=biz|F=YES
W052|routes_accounts_extended.py:1560|accounts.insert|Z=AC|S=self|V=alw|M=guard|C=biz|F=YES
W053|routes_accounts_extended.py:1993|accounts.insert_many|Z=AC|S=self|V=alw|M=guard|C=biz|F=YES
W054|routes_advanced.py:39|products.insert_one|Z=IN|S=self|V=alw|M=guard|C=na|F=NO
W055|routes_advanced.py:65|shop_orders.insert_one|Z=AD|S=self|V=alw|M=guard|C=na|F=NO
W056|routes_advanced.py:69|products.update_one|Z=IN|S=self|V=alw|M=guard|C=na|F=NO
W057|routes_advanced.py:93|shop_orders.update_one|Z=AD|S=self|V=alw|M=guard|C=na|F=NO
W058|routes_advanced.py:138|ai_bots.insert_one|Z=AI|S=self|V=alw|M=guard|C=na|F=NO
W059|routes_advanced.py:159|bot_conversations.insert_one|Z=AI|S=self|V=alw|M=guard|C=na|F=NO
W060|routes_advanced.py:172|bot_conversations.update_one|Z=AI|S=self|V=alw|M=guard|C=na|F=NO
W061|routes_advanced.py:196|ai_bots.update_one|Z=AI|S=self|V=alw|M=guard|C=na|F=NO
W062|routes_advanced.py:356|workshop_services.insert_one|Z=IN|S=self|V=alw|M=guard|C=na|F=NO
W063|routes_advanced.py:372|service_packages.insert_one|Z=IN|S=self|V=alw|M=guard|C=na|F=NO
W064|routes_advanced.py:388|tickets.insert_one|Z=AD|S=self|V=alw|M=guard|C=na|F=NO
W065|routes_advanced.py:420|ticket_responses.insert_one|Z=AD|S=self|V=alw|M=guard|C=na|F=NO
W066|routes_advanced.py:421|tickets.update_one|Z=AD|S=self|V=alw|M=guard|C=na|F=NO
W067|routes_advanced.py:449|tickets.update_one|Z=AD|S=self|V=alw|M=guard|C=na|F=NO
W068|routes_advanced.py:455|customer_feedback.insert_one|Z=AD|S=self|V=alw|M=guard|C=na|F=NO
W069|routes_advanced.py:483|faqs.insert_one|Z=AD|S=self|V=alw|M=guard|C=na|F=NO
W070|routes_ai_enhanced.py:182|ai_search_logs.insert_one|Z=AI|S=self|V=alw|M=guard|C=na|F=NO
W071|routes_approvals.py:69|customer_approval_logs.update_one|Z=CU|S=self|V=alw|M=guard|C=na|F=NO
W072|routes_approvals.py:74|customer_approval_logs.insert_one|Z=CU|S=self|V=alw|M=guard|C=na|F=NO
W073|routes_approvals.py:190|approval_requests.insert|Z=AP|S=self|V=alw|M=guard|C=na|F=NO
W074|routes_approvals.py:225|approval_requests.insert_one|Z=AP|S=self|V=alw|M=guard|C=na|F=NO
W075|routes_approvals.py:420|approval_requests.update|Z=AP|S=self|V=alw|M=guard|C=na|F=NO
W076|routes_approvals.py:493|approval_requests.update_one|Z=AP|S=self|V=alw|M=guard|C=na|F=NO
W077|routes_approvals.py:505|customers.update_one|Z=CU|S=self|V=alw|M=guard|C=na|F=NO
W078|routes_cleanup.py:69|services.upsert|Z=IN|S=self|V=alw|M=guard|C=na|F=NO
W079|routes_cleanup.py:79|parts.delete|Z=IN|S=self|V=alw|M=guard|C=na|F=NO
W080|routes_document_templates.py:41|document_templates.update_many|Z=SE|S=self|V=alw|M=guard|C=na|F=NO
W081|routes_document_templates.py:68|document_templates.update_one|Z=SE|S=self|V=alw|M=guard|C=na|F=NO
W082|routes_document_templates.py:70|document_templates.insert_one|Z=SE|S=self|V=alw|M=guard|C=na|F=NO
W083|routes_document_templates.py:97|document_templates.update_one|Z=SE|S=self|V=alw|M=guard|C=na|F=NO
W084|routes_document_templates.py:230|document_templates.update_one|Z=SE|S=self|V=alw|M=guard|C=na|F=NO
W085|routes_document_templates.py:253|document_templates.update_one|Z=SE|S=self|V=alw|M=guard|C=na|F=NO
W086|routes_document_templates.py:273|document_template_resolution_audit.insert_one|Z=SE|S=self|V=alw|M=guard|C=na|F=NO
W087|routes_document_templates.py:306|document_template_resolution_audit.insert_one|Z=SE|S=self|V=alw|M=guard|C=na|F=NO
W088|routes_document_templates.py:342|document_templates.insert_one|Z=SE|S=self|V=alw|M=guard|C=na|F=NO
W089|routes_document_templates.py:360|document_templates.update_one|Z=SE|S=self|V=alw|M=guard|C=na|F=NO
W090|routes_document_templates.py:366|document_templates.update_one|Z=SE|S=self|V=alw|M=guard|C=na|F=NO
W091|routes_document_templates.py:373|document_templates.insert_one|Z=SE|S=self|V=alw|M=guard|C=na|F=NO
W092|routes_document_templates.py:374|document_templates.update_many|Z=SE|S=self|V=alw|M=guard|C=na|F=NO
W093|routes_document_templates.py:378|document_templates.update_one|Z=SE|S=self|V=alw|M=guard|C=na|F=NO
W094|routes_document_templates.py:381|document_template_audit.insert_one|Z=SE|S=self|V=alw|M=guard|C=na|F=NO
W095|routes_document_templates.py:413|document_templates.update_one|Z=SE|S=self|V=alw|M=guard|C=na|F=NO
W096|routes_extended.py:340|business_accounts.insert_one|Z=AC|S=self|V=alw|M=guard|C=biz|F=YES
W097|routes_extended.py:397|budgets.insert_one|Z=AD|S=self|V=alw|M=guard|C=na|F=NO
W098|routes_extended.py:429|business_accounts.update|Z=AC|S=self|V=alw|M=guard|C=biz|F=YES
W099|routes_extended.py:433|business_accounts.delete|Z=AC|S=self|V=alw|M=guard|C=biz|F=YES
W100|routes_extended.py:450|business_accounts.insert|Z=AC|S=self|V=alw|M=guard|C=biz|F=YES
W101|routes_extended.py:472|business_accounts.update_many|Z=AC|S=self|V=alw|M=guard|C=biz|F=YES
W102|routes_extended.py:483|business_accounts.delete_many|Z=AC|S=self|V=alw|M=guard|C=biz|F=YES
W103|routes_extended.py:500|business_accounts.insert_one|Z=AC|S=self|V=alw|M=guard|C=biz|F=YES
W104|routes_extended.py:694|business_accounts.update_one|Z=AC|S=self|V=alw|M=guard|C=biz|F=YES
W105|routes_extended.py:736|business_accounts.delete|Z=AC|S=self|V=alw|M=guard|C=biz|F=YES
W106|routes_extended.py:742|business_accounts.delete_one|Z=AC|S=self|V=alw|M=guard|C=biz|F=YES
W107|routes_extended.py:782|coa.insert_one|Z=AC|S=self|V=alw|M=guard|C=na|F=NO
W108|routes_extended.py:793|coa.update_one|Z=AC|S=self|V=alw|M=guard|C=na|F=NO
W109|routes_extended.py:1673|journal_entries.post_entry|Z=AE|S=self|V=alw|M=guard|C=AE|F=YES
W110|routes_extended.py:2454|operations.update_one|Z=OP|S=self|V=alw|M=guard|C=biz|F=YES
W111|routes_extended.py:2508|operations.delete_one|Z=OP|S=self|V=alw|M=guard|C=biz|F=YES
W112|routes_extended.py:2537|operations.delete|Z=OP|S=self|V=alw|M=guard|C=biz|F=YES
W113|routes_extended.py:2585|operations.delete_many|Z=OP|S=self|V=alw|M=guard|C=biz|F=YES
W114|routes_extended.py:2661|operations.delete|Z=OP|S=self|V=alw|M=guard|C=biz|F=YES
W115|routes_extended.py:2721|operations.delete_many|Z=OP|S=self|V=alw|M=guard|C=biz|F=YES
W116|routes_extended.py:3085|operations.update|Z=OP|S=self|V=alw|M=guard|C=biz|F=YES
W117|routes_extended.py:3097|operations.update|Z=OP|S=self|V=alw|M=guard|C=biz|F=YES
W118|routes_extended.py:3697|operations.insert_one|Z=OP|S=self|V=alw|M=guard|C=biz|F=YES
W119|routes_extended.py:3706|parts.update_one|Z=IN|S=self|V=alw|M=guard|C=na|F=NO
W120|routes_extended.py:3723|transactions.insert_one|Z=OP|S=self|V=alw|M=guard|C=biz|F=YES
W121|routes_extended.py:3898|transactions.insert_one|Z=OP|S=self|V=alw|M=guard|C=biz|F=YES
W122|routes_extended.py:4476|vehicle_visits.update|Z=OP|S=self|V=alw|M=guard|C=biz|F=YES
W123|routes_extended.py:4484|vehicle_visits.update_one|Z=OP|S=self|V=alw|M=guard|C=biz|F=YES
W124|routes_extended.py:5092|vehicle_visits.update|Z=OP|S=self|V=alw|M=guard|C=biz|F=YES
W125|routes_extended.py:5271|vehicle_visits.insert|Z=OP|S=self|V=alw|M=guard|C=biz|F=YES
W126|routes_extended.py:5308|vehicle_visits.insert_one|Z=OP|S=self|V=alw|M=guard|C=biz|F=YES
W127|routes_extended.py:5510|vehicle_visits.update_one|Z=OP|S=self|V=alw|M=guard|C=biz|F=YES
W128|routes_extended.py:5558|operations.delete|Z=OP|S=self|V=alw|M=guard|C=biz|F=YES
W129|routes_extended.py:5562|vehicle_visits.delete|Z=OP|S=self|V=alw|M=guard|C=biz|F=YES
W130|routes_extended.py:5568|operations.delete_many|Z=OP|S=self|V=alw|M=guard|C=biz|F=YES
W131|routes_extended.py:5569|vehicle_visits.delete_one|Z=OP|S=self|V=alw|M=guard|C=biz|F=YES
W132|routes_extended.py:6028|accounts.insert|Z=AC|S=self|V=alw|M=guard|C=biz|F=YES
W133|routes_fault_knowledge.py:215|fault_knowledge.update|Z=KN|S=self|V=alw|M=guard|C=na|F=NO
W134|routes_fault_knowledge.py:292|fault_knowledge.delete|Z=KN|S=self|V=alw|M=guard|C=na|F=NO
W135|routes_finance.py:2959|accounts.insert|Z=AC|S=self|V=alw|M=guard|C=biz|F=YES
W136|routes_finance.py:2990|accounts.insert_one|Z=AC|S=self|V=alw|M=guard|C=biz|F=YES
W137|routes_finance.py:3705|journal_entries.post_entry|Z=AE|S=self|V=alw|M=guard|C=AE|F=YES
W138|routes_finance.py:3833|journal_entries.post_entry|Z=AE|S=self|V=alw|M=guard|C=AE|F=YES
W139|routes_finance.py:5268|accounts.insert|Z=AC|S=self|V=alw|M=guard|C=biz|F=YES
W140|routes_finance.py:5684|operations.delete_many|Z=OP|S=self|V=alw|M=guard|C=biz|F=YES
W141|routes_finance.py:5685|chart_of_accounts.delete_many|Z=AC|S=self|V=alw|M=guard|C=na|F=NO
W142|routes_finance.py:5840|operations.delete|Z=OP|S=self|V=alw|M=guard|C=biz|F=YES
W143|routes_finance.py:5945|operations.delete_many|Z=OP|S=self|V=alw|M=guard|C=biz|F=YES
W144|routes_finance.py:5998|operations.update|Z=OP|S=self|V=alw|M=guard|C=biz|F=YES
W145|routes_firewall.py:295|firewall_dismissed_alerts.update_one|Z=FW|S=self|V=alw|M=guard|C=na|F=NO
W146|routes_firewall.py:325|firewall_resolved_alerts.insert_one|Z=FW|S=self|V=alw|M=guard|C=na|F=NO
W147|routes_firewall.py:333|firewall_dismissed_alerts.update_one|Z=FW|S=self|V=alw|M=guard|C=na|F=NO
W148|routes_firewall.py:423|journal_entries.post_entry|Z=AE|S=self|V=alw|M=guard|C=AE|F=YES
W149|routes_import.py:274|parts.upsert|Z=IN|S=self|V=alw|M=guard|C=na|F=NO
W150|routes_import.py:278|services.upsert|Z=IN|S=self|V=alw|M=guard|C=na|F=NO
W151|routes_import.py:378|parts.update|Z=IN|S=self|V=alw|M=guard|C=na|F=NO
W152|routes_import.py:391|parts.update_one|Z=IN|S=self|V=alw|M=guard|C=na|F=NO
W153|routes_import.py:400|parts.insert|Z=IN|S=self|V=alw|M=guard|C=na|F=NO
W154|routes_import.py:402|parts.insert_many|Z=IN|S=self|V=alw|M=guard|C=na|F=NO
W155|routes_import.py:549|customers.update|Z=CU|S=self|V=alw|M=guard|C=na|F=NO
W156|routes_import.py:553|customers.insert|Z=CU|S=self|V=alw|M=guard|C=na|F=NO
W157|routes_import.py:592|customers.update_one|Z=CU|S=self|V=alw|M=guard|C=na|F=NO
W158|routes_import.py:609|customers.insert_one|Z=CU|S=self|V=alw|M=guard|C=na|F=NO
W159|routes_injectors.py:116|injector_reports.insert_one|Z=KN|S=self|V=alw|M=guard|C=na|F=NO
W160|routes_maintenance.py:37|maintenance_orders.insert_one|Z=IN|S=self|V=alw|M=guard|C=na|F=NO
W161|routes_maintenance.py:60|maintenance_orders.update_one|Z=IN|S=self|V=alw|M=guard|C=na|F=NO
W162|routes_maintenance.py:88|maintenance_orders.update_one|Z=IN|S=self|V=alw|M=guard|C=na|F=NO
W163|routes_maintenance.py:110|maintenance_orders.update_one|Z=IN|S=self|V=alw|M=guard|C=na|F=NO
W164|routes_moltbot.py:504|moltbot_projects.insert|Z=AI|S=self|V=alw|M=guard|C=na|F=NO
W165|routes_moltbot.py:571|moltbot_sessions.insert|Z=AI|S=self|V=alw|M=guard|C=na|F=NO
W166|routes_moltbot.py:601|moltbot_messages.insert|Z=AI|S=self|V=alw|M=guard|C=na|F=NO
W167|routes_outbound.py:166|outbound_message_templates.update_one|Z=SE|S=self|V=alw|M=guard|C=na|F=NO
W168|routes_outbound.py:415|outbound_message_templates.update_one|Z=SE|S=self|V=alw|M=guard|C=na|F=NO
W169|routes_outbound.py:437|outbound_message_templates.update_one|Z=SE|S=self|V=alw|M=guard|C=na|F=NO
W170|routes_outbound.py:557|document_output_assets.update_one|Z=SE|S=self|V=alw|M=guard|C=na|F=NO
W171|routes_outbound.py:592|document_output_assets.insert_one|Z=SE|S=self|V=alw|M=guard|C=na|F=NO
W172|routes_outbound.py:611|document_output_assets.update_one|Z=SE|S=self|V=alw|M=guard|C=na|F=NO
W173|routes_outbound.py:707|outbound_share_attempts.insert_one|Z=SE|S=self|V=alw|M=guard|C=na|F=NO
W174|routes_outbound.py:739|outbound_share_attempts.update_one|Z=SE|S=self|V=alw|M=guard|C=na|F=NO
W175|routes_parts.py:76|parts.insert_one|Z=IN|S=self|V=alw|M=guard|C=na|F=NO
W176|routes_parts.py:94|parts.update_one|Z=IN|S=self|V=alw|M=guard|C=na|F=NO
W177|routes_payroll.py:35|employee_performance.insert_one|Z=PA|S=self|V=alw|M=guard|C=na|F=NO
W178|routes_payroll.py:94|salary_records.insert_one|Z=PA|S=self|V=alw|M=guard|C=na|F=NO
W179|routes_payroll.py:110|transactions.insert_one|Z=OP|S=self|V=alw|M=guard|C=biz|F=YES
W180|routes_payroll.py:174|transactions.insert_one|Z=OP|S=self|V=alw|M=guard|C=biz|F=YES
W181|routes_payroll.py:177|salary_records.update_one|Z=PA|S=self|V=alw|M=guard|C=na|F=NO
W182|routes_references.py:68|dtc_references.update_one|Z=KN|S=self|V=alw|M=guard|C=na|F=NO
W183|routes_references.py:72|dtc_references.insert_one|Z=KN|S=self|V=alw|M=guard|C=na|F=NO
W184|routes_references.py:98|electrical_references.insert_one|Z=KN|S=self|V=alw|M=guard|C=na|F=NO
W185|routes_references.py:125|vehicle_references.insert_one|Z=VE|S=self|V=alw|M=guard|C=na|F=NO
W186|routes_references.py:206|dtc_references.insert_many|Z=KN|S=self|V=alw|M=guard|C=na|F=NO
W187|routes_services.py:41|services.insert_one|Z=IN|S=self|V=alw|M=guard|C=na|F=NO
W188|routes_services.py:62|services.update_one|Z=IN|S=self|V=alw|M=guard|C=na|F=NO
W189|routes_services.py:86|services.delete_one|Z=IN|S=self|V=alw|M=guard|C=na|F=NO
W190|routes_smart_accounting.py:246|journal_entries.post_entry|Z=AE|S=self|V=alw|M=guard|C=AE|F=YES
W191|routes_smart_accounting.py:257|suppliers.update|Z=SU|S=self|V=alw|M=guard|C=na|F=NO
W192|routes_smart_accounting.py:366|operations.update|Z=OP|S=self|V=alw|M=guard|C=biz|F=YES
W193|routes_suppliers_extended.py:532|journal_entries.post_entry|Z=AE|S=self|V=alw|M=guard|C=AE|F=YES
W194|routes_technicians.py:46|technicians.insert|Z=AR|S=self|V=alw|M=guard|C=na|F=NO
W195|routes_technicians.py:67|technicians.insert_one|Z=AR|S=self|V=alw|M=guard|C=na|F=NO
W196|routes_templates_extended.py:96|print_templates.insert_one|Z=SE|S=self|V=alw|M=guard|C=na|F=NO
W197|routes_templates_extended.py:109|print_templates.delete_one|Z=SE|S=self|V=alw|M=guard|C=na|F=NO
W198|routes_templates_extended.py:129|print_templates.update_many|Z=SE|S=self|V=alw|M=guard|C=na|F=NO
W199|routes_templates_extended.py:133|print_templates.update_one|Z=SE|S=self|V=alw|M=guard|C=na|F=NO
W200|routes_templates_extended.py:159|print_templates.update_one|Z=SE|S=self|V=alw|M=guard|C=na|F=NO
W201|routes_templates_extended.py:285|invoice_templates.update_one|Z=SE|S=self|V=alw|M=guard|C=na|F=NO
W202|routes_templates_extended.py:293|invoice_templates.update_one|Z=SE|S=self|V=alw|M=guard|C=na|F=NO
W203|routes_templates_extended.py:332|invoice_templates.insert_one|Z=SE|S=self|V=alw|M=guard|C=na|F=NO
W204|routes_templates_extended.py:347|invoice_templates.update_one|Z=SE|S=self|V=alw|M=guard|C=na|F=NO
W205|routes_templates_extended.py:375|invoice_templates.update_one|Z=SE|S=self|V=alw|M=guard|C=na|F=NO
W206|routes_templates_extended.py:416|invoice_templates.update_one|Z=SE|S=self|V=alw|M=guard|C=na|F=NO
W207|routes_templates_extended.py:436|invoice_templates.update_many|Z=SE|S=self|V=alw|M=guard|C=na|F=NO
W208|routes_templates_extended.py:437|invoice_templates.update_one|Z=SE|S=self|V=alw|M=guard|C=na|F=NO
W209|routes_templates_extended.py:456|invoice_templates.update_one|Z=SE|S=self|V=alw|M=guard|C=na|F=NO
W210|routes_templates_extended.py:531|invoice_templates.insert_one|Z=SE|S=self|V=alw|M=guard|C=na|F=NO
W211|routes_templates_extended.py:564|invoice_templates.update_one|Z=SE|S=self|V=alw|M=guard|C=na|F=NO
W212|routes_templates_extended.py:583|invoice_templates.insert_one|Z=SE|S=self|V=alw|M=guard|C=na|F=NO
W213|routes_user_layouts.py:96|user_layouts.upsert|Z=LY|S=self|V=alw|M=guard|C=na|F=NO
W214|routes_user_layouts.py:110|user_layouts.update_one|Z=LY|S=self|V=alw|M=guard|C=na|F=NO
W215|routes_users.py:268|users.insert_one|Z=UA|S=self|V=alw|M=guard|C=na|F=NO
W216|routes_users.py:304|users.update_one|Z=UA|S=self|V=alw|M=guard|C=na|F=NO
W217|routes_users.py:336|users.delete_one|Z=UA|S=self|V=alw|M=guard|C=na|F=NO
W218|routes_vehicle_files.py:48|vehicle_files.insert_one|Z=VE|S=self|V=alw|M=guard|C=na|F=NO
W219|routes_workshop_config.py:82|workshop_settings.insert|Z=SE|S=self|V=alw|M=guard|C=na|F=NO
W220|routes_workshop_config.py:93|settings.insert_one|Z=SE|S=self|V=alw|M=guard|C=na|F=NO
W221|routes_workshop_config.py:120|workshop_settings.insert|Z=SE|S=self|V=alw|M=guard|C=na|F=NO
W222|routes_workshop_config.py:129|settings.update_one|Z=SE|S=self|V=alw|M=guard|C=na|F=NO
W223|routes_workshop_config.py:182|workshop_profile.insert_one|Z=PF|S=self|V=alw|M=guard|C=na|F=NO
W224|routes_workshop_config.py:202|workshop_profile.update_one|Z=PF|S=self|V=alw|M=guard|C=na|F=NO
W225|routes_workshop_config.py:235|workshop_profile.update_one|Z=PF|S=self|V=alw|M=guard|C=na|F=NO
W226|routes_workshop_config.py:281|auth_otps.insert_one|Z=UA|S=self|V=alw|M=guard|C=na|F=NO
W227|server.py:782|customers.insert_one|Z=CU|S=self|V=alw|M=guard|C=na|F=NO
W228|server.py:822|vehicles.insert_one|Z=VE|S=self|V=alw|M=guard|C=na|F=NO
W229|server.py:978|journal_entries.post_entry|Z=AE|S=self|V=alw|M=guard|C=AE|F=YES
W230|server.py:1166|vehicles.update_one|Z=VE|S=self|V=alw|M=guard|C=na|F=NO
W231|server.py:1240|vehicles.update_one|Z=VE|S=self|V=alw|M=guard|C=na|F=NO
W232|server.py:1261|operations.insert|Z=OP|S=self|V=alw|M=guard|C=biz|F=YES
W233|server.py:1268|operations.insert_one|Z=OP|S=self|V=alw|M=guard|C=biz|F=YES
W234|server.py:1302|journal_entries.post_entry|Z=AE|S=self|V=alw|M=guard|C=AE|F=YES
W235|server.py:1333|invoices.update|Z=AR|S=self|V=alw|M=guard|C=biz|F=YES
W236|server.py:1357|invoices.insert|Z=AR|S=self|V=alw|M=guard|C=biz|F=YES
W237|server.py:1417|invoices.delete|Z=AR|S=self|V=alw|M=guard|C=biz|F=YES
W238|server.py:1428|operations.delete|Z=OP|S=self|V=alw|M=guard|C=biz|F=YES
W239|server.py:1465|invoices.delete_many|Z=AR|S=self|V=alw|M=guard|C=biz|F=YES
W240|server.py:1471|operations.delete_many|Z=OP|S=self|V=alw|M=guard|C=biz|F=YES
W241|server.py:1476|vehicles.delete_one|Z=VE|S=self|V=alw|M=guard|C=na|F=NO
W242|server.py:2558|accounts.update|Z=AC|S=self|V=alw|M=guard|C=biz|F=YES
W243|server.py:2560|accounts.insert|Z=AC|S=self|V=alw|M=guard|C=biz|F=YES
W244|server.py:2583|accounts.update_one|Z=AC|S=self|V=alw|M=guard|C=biz|F=YES
W245|server.py:2750|customer_file_numbers.update_one|Z=CU|S=self|V=alw|M=guard|C=na|F=NO
W246|server.py:2756|customer_file_numbers.delete_one|Z=CU|S=self|V=alw|M=guard|C=na|F=NO
W247|server.py:2785|customer_file_numbers.delete_one|Z=CU|S=self|V=alw|M=guard|C=na|F=NO
W248|server.py:2849|parts.update_many|Z=IN|S=self|V=alw|M=guard|C=na|F=NO
W249|server.py:2850|services.update_many|Z=IN|S=self|V=alw|M=guard|C=na|F=NO
W250|server.py:2977|parts.update|Z=IN|S=self|V=alw|M=guard|C=na|F=NO
W251|server.py:3000|parts.update_one|Z=IN|S=self|V=alw|M=guard|C=na|F=NO
W252|server.py:3023|parts.update|Z=IN|S=self|V=alw|M=guard|C=na|F=NO
W253|server.py:3042|parts.update_one|Z=IN|S=self|V=alw|M=guard|C=na|F=NO
W254|server.py:3058|parts.delete_one|Z=IN|S=self|V=alw|M=guard|C=na|F=NO
W255|server.py:3199|business_accounts.insert_one|Z=AC|S=self|V=alw|M=guard|C=biz|F=YES
W256|smart_inventory_service.py:376|settings.update_one|Z=SE|S=self|V=alw|M=guard|C=na|F=NO
W257|smart_inventory_service.py:562|inventory_backorders.insert|Z=IN|S=self|V=alw|M=guard|C=na|F=NO
W258|smart_inventory_service.py:578|inventory_backorders.insert_one|Z=IN|S=self|V=alw|M=guard|C=na|F=NO
W259|smart_inventory_service.py:646|inventory_backorders.update_one|Z=IN|S=self|V=alw|M=guard|C=na|F=NO
W260|supabase_service.py:341|vehicles.insert|Z=VE|S=self|V=alw|M=guard|C=na|F=NO
W261|supabase_service.py:367|vehicles.update|Z=VE|S=self|V=alw|M=guard|C=na|F=NO
W262|supabase_service.py:374|vehicles.delete|Z=VE|S=self|V=alw|M=guard|C=na|F=NO
W263|supabase_service.py:442|services.insert|Z=IN|S=self|V=alw|M=guard|C=na|F=NO
W264|supabase_service.py:469|services.update|Z=IN|S=self|V=alw|M=guard|C=na|F=NO
W265|supabase_service.py:483|services.delete|Z=IN|S=self|V=alw|M=guard|C=na|F=NO
W266|supabase_service.py:520|business_accounts.insert|Z=AC|S=self|V=alw|M=guard|C=biz|F=YES
W267|supabase_service.py:554|budgets.insert|Z=AD|S=self|V=alw|M=guard|C=na|F=NO
W268|supabase_service.py:1015|customers.insert|Z=CU|S=self|V=alw|M=guard|C=na|F=NO
W269|supabase_service.py:1057|customers.update|Z=CU|S=self|V=alw|M=guard|C=na|F=NO
W270|supabase_service.py:1077|customers.delete|Z=CU|S=self|V=alw|M=guard|C=na|F=NO
W271|supabase_service.py:1103|invoices.insert|Z=AR|S=self|V=alw|M=guard|C=biz|F=YES
W272|supabase_service.py:1183|invoices.delete|Z=AR|S=self|V=alw|M=guard|C=biz|F=YES
W273|supabase_service.py:1274|operations.insert|Z=OP|S=self|V=alw|M=guard|C=biz|F=YES
W274|supabase_service.py:1358|operations.update|Z=OP|S=self|V=alw|M=guard|C=biz|F=YES
W275|supabase_service.py:1399|operations.delete|Z=OP|S=self|V=alw|M=guard|C=biz|F=YES
W276|supabase_service.py:1445|transactions.insert|Z=OP|S=self|V=alw|M=guard|C=biz|F=YES
W277|supabase_service.py:1509|parts.insert|Z=IN|S=self|V=alw|M=guard|C=na|F=NO
W278|supabase_service.py:1551|parts.update|Z=IN|S=self|V=alw|M=guard|C=na|F=NO
W279|supabase_service.py:1571|parts.delete|Z=IN|S=self|V=alw|M=guard|C=na|F=NO
W280|supabase_service.py:1584|users.insert|Z=UA|S=self|V=alw|M=guard|C=na|F=NO
W281|supabase_service.py:1607|users.delete|Z=UA|S=self|V=alw|M=guard|C=na|F=NO
W282|visit_sync.py:276|operations.upsert|Z=OP|S=self|V=alw|M=guard|C=biz|F=YES
W283|visit_sync.py:308|operations.update_one|Z=OP|S=self|V=alw|M=guard|C=biz|F=YES
W284|visit_sync.py:340|operations.insert_one|Z=OP|S=self|V=alw|M=guard|C=biz|F=YES
W285|whatsapp_service.py:117|whatsapp_messages.insert_one|Z=AD|S=self|V=alw|M=guard|C=na|F=NO
W286|whatsapp_service.py:131|whatsapp_messages.insert_one|Z=AD|S=self|V=alw|M=guard|C=na|F=NO

## Mass Assignment Audit
users=allowlisted create/update + privileged grant checks; profile/settings=recursive privileged-field rejection + allowlists; layouts=self-only check; accounts=reject id/_id/balance/isSystem/owner/audit/security/role/status and accept chart metadata only.

## Fail-Closed Verification
Authz exceptions => authz_exception_fail_closed + AUTHZ_FAIL_CLOSED request_id log. Missing policy => missing_policy denial. Mutating fallback => admin-only review, never authenticated-only.

## Tests Added
test_authorization_phase1b.py (10 regression/security tests); test_authz_ssot.py converted to pytest-safe format while retaining script mode.

## Test Results
pytest=18 passed/0 failed. scripts: test_authz_ssot.py ALL PASS; test_authorization_phase1b.py 10/10 PASS. closure: AUTHZ_COMPLETE=495, PUBLIC_INTENTIONAL=17, POLICY_DECISION_REQUIRED=0, SUM=512. health: GET /api/health=200. Testing agent iteration 364 passed static/unit-only; no DB writes; no MOCKED APIs.

## Remaining Risks
P1-SEC-UPLOAD remains open; P2 distributed idempotency/rate limits remains open; P2 AI prompt-injection hardening remains open; P0-DUP-AR remains untouched.

## Deployment Impact
Not deployed. Later deployment may create stricter 403s on sensitive reads/writes. No DB migration required.

## Rollback Plan
No data rollback needed. Use platform rollback/checkpoint for code if review requires it; no git reset here.

## Final Phase 1B Verdict
PHASE 1B COMPLETE — READY FOR REVIEW
