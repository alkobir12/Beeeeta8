# PHASE_1C1A_SECURITY_REPRODUCIBLE_BUILD_CLOSURE_REPORT
Generated: 2026-09-02 12:40 UTC
Scope: NO DEPLOY / NO PHASE 2 / NO PRODUCTION DATA MUTATION / NO ACCOUNTINGENGINE CHANGES / NO MIGRATIONS

## 1. Phase Status
- PHASE 1C PRE-DEPLOY READINESS = PASS
- PHASE 1C LIVE DEPLOYMENT = NOT EXECUTED
- PHASE 1C FINAL = OPEN

## 2. Historical Secret Exposure Inventory
- Files scanned in Git history: backend/.env, frontend/.env, .env
- Historical env keys inventoried: 55
- Secret values displayed: NO
- Credential class counts: API/LLM KEY=6, CLIENT-PUBLISHABLE=3, DATABASE CREDENTIAL=3, JWT/AUTH SECRET=1, OTHER SECRET=5, PUBLIC/NON-SECRET=35, SERVICE ROLE=2
- Rotation-required historical keys: 16
- Rotation status counts: NOT REQUIRED=39, ROTATION REQUIRED — EXTERNAL ACTION=16
- Classification note: URLs/model names/publishable frontend keys were not treated as secrets by name alone; only credential-bearing classes require rotation.

| key name | file | first exposure | last exposure | class | still active? | rotation required? | rotation status |
|---|---|---|---|---|---|---|---|
| `ACTION_RUNTIME_ENFORCE_4EYES` | `backend/.env` | `7618438dee6b` | `7618438dee6b` | PUBLIC/NON-SECRET | YES | NO | NOT REQUIRED |
| `ANTHROPIC_API_KEY` | `backend/.env` | `7618438dee6b` | `7618438dee6b` | API/LLM KEY | YES | NO | NOT REQUIRED |
| `BLACKBOX_API_KEY` | `backend/.env` | `832adf06a716` | `7618438dee6b` | API/LLM KEY | UNKNOWN | YES | ROTATION REQUIRED — EXTERNAL ACTION |
| `BLACKBOX_API_URL` | `backend/.env` | `832adf06a716` | `7618438dee6b` | PUBLIC/NON-SECRET | YES | NO | NOT REQUIRED |
| `BLACKBOX_BRANCH` | `backend/.env` | `832adf06a716` | `7618438dee6b` | PUBLIC/NON-SECRET | YES | NO | NOT REQUIRED |
| `BLACKBOX_REPO_URL` | `backend/.env` | `832adf06a716` | `7618438dee6b` | PUBLIC/NON-SECRET | YES | NO | NOT REQUIRED |
| `CORS_ORIGINS` | `backend/.env` | `9d2291fac6bf` | `7618438dee6b` | PUBLIC/NON-SECRET | YES | NO | NOT REQUIRED |
| `DATABASE_URL` | `backend/.env` | `33c8d7d67196` | `b119b82b80a7` | DATABASE CREDENTIAL | UNKNOWN | YES | ROTATION REQUIRED — EXTERNAL ACTION |
| `DB_NAME` | `backend/.env` | `9d2291fac6bf` | `7618438dee6b` | PUBLIC/NON-SECRET | YES | NO | NOT REQUIRED |
| `DB_PROVIDER` | `backend/.env` | `33c8d7d67196` | `7618438dee6b` | PUBLIC/NON-SECRET | YES | NO | NOT REQUIRED |
| `DEEPSEEK_API_BASE_URL` | `backend/.env` | `832adf06a716` | `7618438dee6b` | PUBLIC/NON-SECRET | YES | NO | NOT REQUIRED |
| `DEEPSEEK_API_KEY` | `backend/.env` | `832adf06a716` | `7618438dee6b` | API/LLM KEY | UNKNOWN | YES | ROTATION REQUIRED — EXTERNAL ACTION |
| `DEEPSEEK_MODEL` | `backend/.env` | `832adf06a716` | `7618438dee6b` | PUBLIC/NON-SECRET | YES | NO | NOT REQUIRED |
| `DEFAULT_WORKSHOP_ID` | `backend/.env` | `832adf06a716` | `7618438dee6b` | PUBLIC/NON-SECRET | YES | NO | NOT REQUIRED |
| `DEVELOPER_APPROVAL_CODE` | `backend/.env` | `7618438dee6b` | `7618438dee6b` | OTHER SECRET | UNKNOWN | YES | ROTATION REQUIRED — EXTERNAL ACTION |
| `DIRECT_URL` | `backend/.env` | `33c8d7d67196` | `b119b82b80a7` | DATABASE CREDENTIAL | UNKNOWN | YES | ROTATION REQUIRED — EXTERNAL ACTION |
| `EMERGENT_LLM_KEY` | `backend/.env` | `3ce2e243712e` | `7618438dee6b` | API/LLM KEY | UNKNOWN | YES | ROTATION REQUIRED — EXTERNAL ACTION |
| `EMERGENT_SESSION_DATA_URL` | `backend/.env` | `7618438dee6b` | `7618438dee6b` | PUBLIC/NON-SECRET | YES | NO | NOT REQUIRED |
| `GOOGLE_API_KEY` | `backend/.env` | `33c8d7d67196` | `b119b82b80a7` | API/LLM KEY | UNKNOWN | YES | ROTATION REQUIRED — EXTERNAL ACTION |
| `GROQ_API_BASE_URL` | `backend/.env` | `33c8d7d67196` | `7618438dee6b` | PUBLIC/NON-SECRET | YES | NO | NOT REQUIRED |
| `GROQ_API_KEY` | `backend/.env` | `33c8d7d67196` | `7618438dee6b` | API/LLM KEY | UNKNOWN | YES | ROTATION REQUIRED — EXTERNAL ACTION |
| `GROQ_MODEL` | `backend/.env` | `33c8d7d67196` | `7618438dee6b` | PUBLIC/NON-SECRET | YES | NO | NOT REQUIRED |
| `JWT_SECRET` | `backend/.env` | `7618438dee6b` | `7618438dee6b` | JWT/AUTH SECRET | UNKNOWN | YES | ROTATION REQUIRED — EXTERNAL ACTION |
| `LLAMA_MAVERICK_MODEL_ID` | `backend/.env` | `832adf06a716` | `7618438dee6b` | PUBLIC/NON-SECRET | YES | NO | NOT REQUIRED |
| `LLAMA_SCOUT_MODEL_ID` | `backend/.env` | `832adf06a716` | `7618438dee6b` | PUBLIC/NON-SECRET | YES | NO | NOT REQUIRED |
| `LLAMA_STACK_URL` | `backend/.env` | `832adf06a716` | `7618438dee6b` | PUBLIC/NON-SECRET | YES | NO | NOT REQUIRED |
| `MANAGER_QUICK_PIN` | `backend/.env` | `7618438dee6b` | `7618438dee6b` | OTHER SECRET | UNKNOWN | YES | ROTATION REQUIRED — EXTERNAL ACTION |
| `MANAGER_QUICK_USERNAME` | `backend/.env` | `7618438dee6b` | `7618438dee6b` | PUBLIC/NON-SECRET | YES | NO | NOT REQUIRED |
| `MOLTBOT_OPENAI_MODEL` | `backend/.env` | `832adf06a716` | `7618438dee6b` | PUBLIC/NON-SECRET | YES | NO | NOT REQUIRED |
| `MOLTBOT_PROJECT_ROOT` | `backend/.env` | `832adf06a716` | `7618438dee6b` | PUBLIC/NON-SECRET | YES | NO | NOT REQUIRED |
| `MONGO_URL` | `backend/.env` | `9d2291fac6bf` | `7618438dee6b` | DATABASE CREDENTIAL | UNKNOWN | YES | ROTATION REQUIRED — EXTERNAL ACTION |
| `POOLER_HOST` | `backend/.env` | `33c8d7d67196` | `b119b82b80a7` | PUBLIC/NON-SECRET | NO | NO | NOT REQUIRED |
| `POOLER_PORT` | `backend/.env` | `33c8d7d67196` | `b119b82b80a7` | PUBLIC/NON-SECRET | NO | NO | NOT REQUIRED |
| `POOLER_USER` | `backend/.env` | `33c8d7d67196` | `b119b82b80a7` | PUBLIC/NON-SECRET | NO | NO | NOT REQUIRED |
| `POSTGRES_DB` | `backend/.env` | `33c8d7d67196` | `b119b82b80a7` | PUBLIC/NON-SECRET | NO | NO | NOT REQUIRED |
| `POSTGRES_HOST` | `backend/.env` | `33c8d7d67196` | `b119b82b80a7` | PUBLIC/NON-SECRET | NO | NO | NOT REQUIRED |
| `POSTGRES_PASSWORD` | `backend/.env` | `33c8d7d67196` | `b119b82b80a7` | OTHER SECRET | UNKNOWN | YES | ROTATION REQUIRED — EXTERNAL ACTION |
| `POSTGRES_PORT` | `backend/.env` | `33c8d7d67196` | `b119b82b80a7` | PUBLIC/NON-SECRET | NO | NO | NOT REQUIRED |
| `POSTGRES_USER` | `backend/.env` | `33c8d7d67196` | `b119b82b80a7` | PUBLIC/NON-SECRET | NO | NO | NOT REQUIRED |
| `RATE_LIMIT_BYPASS_TOKEN` | `backend/.env` | `7618438dee6b` | `7618438dee6b` | OTHER SECRET | UNKNOWN | YES | ROTATION REQUIRED — EXTERNAL ACTION |
| `RUNTIME_APPROVER_ROLES` | `backend/.env` | `7618438dee6b` | `7618438dee6b` | PUBLIC/NON-SECRET | YES | NO | NOT REQUIRED |
| `SUPABASE_SERVICE_ROLE_KEY` | `backend/.env` | `33c8d7d67196` | `7618438dee6b` | SERVICE ROLE | UNKNOWN | YES | ROTATION REQUIRED — EXTERNAL ACTION |
| `SUPABASE_SERVICE_ROLE_KEY_1` | `backend/.env` | `b119b82b80a7` | `b119b82b80a7` | SERVICE ROLE | UNKNOWN | YES | ROTATION REQUIRED — EXTERNAL ACTION |
| `SUPABASE_URL` | `backend/.env` | `33c8d7d67196` | `7618438dee6b` | PUBLIC/NON-SECRET | YES | NO | NOT REQUIRED |
| `SUPABASE_URL_1` | `backend/.env` | `b119b82b80a7` | `b119b82b80a7` | PUBLIC/NON-SECRET | NO | NO | NOT REQUIRED |
| `TEST_USER_PASSWORD` | `backend/.env` | `7618438dee6b` | `7618438dee6b` | OTHER SECRET | UNKNOWN | YES | ROTATION REQUIRED — EXTERNAL ACTION |
| `DANGEROUSLY_DISABLE_HOST_CHECK` | `frontend/.env` | `7618438dee6b` | `7618438dee6b` | PUBLIC/NON-SECRET | YES | NO | NOT REQUIRED |
| `DISABLE_ESLINT_PLUGIN` | `frontend/.env` | `832adf06a716` | `7618438dee6b` | PUBLIC/NON-SECRET | YES | NO | NOT REQUIRED |
| `DISABLE_HOT_RELOAD` | `frontend/.env` | `b119b82b80a7` | `b119b82b80a7` | PUBLIC/NON-SECRET | NO | NO | NOT REQUIRED |
| `ENABLE_HEALTH_CHECK` | `frontend/.env` | `9d2291fac6bf` | `b119b82b80a7` | PUBLIC/NON-SECRET | NO | NO | NOT REQUIRED |
| `HOST` | `frontend/.env` | `7618438dee6b` | `7618438dee6b` | PUBLIC/NON-SECRET | YES | NO | NOT REQUIRED |
| `REACT_APP_BACKEND_URL` | `frontend/.env` | `9d2291fac6bf` | `7618438dee6b` | CLIENT-PUBLISHABLE | YES | NO | NOT REQUIRED |
| `REACT_APP_ENABLE_VISUAL_EDITS` | `frontend/.env` | `9d2291fac6bf` | `b119b82b80a7` | CLIENT-PUBLISHABLE | NO | NO | NOT REQUIRED |
| `REACT_APP_WORKSHOP_ID` | `frontend/.env` | `832adf06a716` | `7618438dee6b` | CLIENT-PUBLISHABLE | YES | NO | NOT REQUIRED |
| `WDS_SOCKET_PORT` | `frontend/.env` | `9d2291fac6bf` | `b119b82b80a7` | PUBLIC/NON-SECRET | NO | NO | NOT REQUIRED |

## 3. Rotation Requirement
- Any historical valid server-side secret must be rotated/revoked before gate can pass.
- Rotation-required classes found: DATABASE CREDENTIAL, JWT/AUTH SECRET, SERVICE ROLE, API/LLM KEY, OTHER SECRET.
- Agent cannot create/rotate/revoke credentials at Supabase/Mongo/provider/platform from this environment.
- Therefore rotation-required rows are: ROTATION REQUIRED — EXTERNAL ACTION.
- Runtime environment was not updated with new credentials; no new secret value was generated, displayed, or committed.

## 4. Git History Sanitization
- LOCAL_HISTORY_CLEANABLE = YES, technically possible with filter-rewrite/BFG-like process, but NOT executed because it is destructive and requires rollback/remote coordination.
- REMOTE_HISTORY_CLEANABLE = EXTERNAL_ACTION_REQUIRED.
- HISTORY PURGE DOES NOT REPLACE SECRET ROTATION.
- After rotation/revocation, history purge can reduce accidental rediscovery risk, but old exposed credentials must still be considered compromised.

## 5. Current Env Safety
- `.env`, `.env.*`, `*.env` remain IGNORED.
- `.env.example` templates are allowed and contain empty values only.
- REAL ENV TRACKED = 0
- REAL ENV STAGED = 0
- REAL ENV COMMITTABLE BY DEFAULT = 0
- CURRENT REAL ENV SAFETY = SAFE

## 6. Public Framework Route Decision
- API business/public routes are separated from framework routes.
- Production/current build policy:
  - /openapi.json = DISABLED_IN_PRODUCTION_AND_CURRENT_BUILD
  - /docs = DISABLED_IN_PRODUCTION_AND_CURRENT_BUILD
  - /docs/oauth2-redirect = DISABLED_IN_PRODUCTION_AND_CURRENT_BUILD
  - /redoc = DISABLED_IN_PRODUCTION_AND_CURRENT_BUILD
  - /health = INTENTIONALLY_PUBLIC_INTERNAL_FASTAPI_HEALTH_PROBE_NOT_EXTERNAL_INGRESS_ROUTE; external health uses /api/health
- PUBLIC_API_ROUTES = 7
- PUBLIC_FRAMEWORK_ROUTES_INTERNAL_FASTAPI = 1
- PUBLIC_FRAMEWORK_ROUTES_EXTERNAL_INGRESS = 0
- INTERNAL_FASTAPI_PUBLIC_HTTP_ROUTES = 8
- TOTAL_EFFECTIVE_PUBLIC_HTTP_ROUTES = 7 (external ingress reachable API routes)
- Implementation: FastAPI docs/OpenAPI/Redoc disabled via `docs_url=None`, `redoc_url=None`, `openapi_url=None`. `/health` remains internal backend health; externally, ingress health route is `/api/health`.

## 7. Financial Fingerprint Semantic Reconciliation
- Definition file saved: memory/discovery/PHASE_1C_FINANCIAL_FINGERPRINT_DEFINITION.md
- Each metric now has source, exact semantic definition, filters, canonical/comparable flag.
- Reversal discrepancy cause: schema semantics/query definition mismatch. The prior fingerprint used absent fields (`is_reversed`/`reversal_of`); current schema stores reversal rows via `source=reversal` and reference semantics.
- Older static report had reversal=16; current DB read-only snapshot has reversal_entry_count=20. This indicates natural data change or later legitimate entries outside this task. No mutation was performed here.
- Final comparable metric after this point: `reversal_entry_count`, not previous zero-valued `reversal_count`.

## 8. Final Pre-Deploy Financial Fingerprint
- Files saved: memory/discovery/FINAL_PHASE_1C_PREDEPLOY_FINANCIAL_FINGERPRINT.json and .md
- journal_entry_count: 190
- journal_active_business_record_count: 190
- reversed_original_count: 0
- reversal_entry_count: 20
- explicit_reversal_link_count: 20
- total_debit: 283671.06
- total_credit: 283671.06
- canonical_accounts_receivable_estimate: 25948.0
- canonical_accounts_payable_estimate: 1820.0
- latest_journal_timestamp: 2026-09-02T08:19:25.050963+00:00
- latest_journal_id: bcaa53f8-6f75-4d1c-959e-78dc5b493c91
- source_distribution: {'active_vehicle_ar_repair': 7, 'ajel_supplier_purchase': 3, 'fin_engine_align_v1': 7, 'hist_vehicle_ar_repair': 3, 'historical_financial_repair': 3, 'manual': 7, 'operation': 36, 'operation_payment': 2, 'period_close': 1, 'reversal': 20, 'unified_visit_payment': 56, 'vehicle_visit': 45}
- orphan_reference_counts: {'operations_missing_vehicle_reference': 0, 'operations_count': 120, 'vehicles_count': 231, 'accounts_count': 210}
- FINANCIAL_FINGERPRINT_CHECKSUM: 0f6c0f761d4bd6ec636fdddf9529e2a4abfa474212cf520b23a860c11e985edf
- mutation_performed: NO

## 9. Clean Reproducible Source State
- SOURCE_COMMIT: 0ceb2ddc47724d6d2dc788edd1476680960f13d5
- WORKING_TREE_STATE: DIRTY
- BUILD_IDENTIFIER: 0ceb2ddc4772-dirty
- CLEAN requirement met: NO
- Reason: current report/templates/code change are not represented by a clean commit/checkpoint inside this environment.
- Agent did not create git commit/checkpoint; use platform/GitHub save workflow after external rotation decision.

## 10. Regenerated Authorization Fingerprint
- File saved: memory/discovery/PHASE_1C1A_AUTHORIZATION_REPRODUCIBLE_FINGERPRINT.json
- AUTH_MATRIX_CHECKSUM: 40ef104b7953e060d885c0c8ed55cd51f2de146904618c5bcecb8bb61cf50358
- WRITER_MATRIX_CHECKSUM: 257da342a2c8878995c16d575063dda3931ff321728cfba9ac88f698819fb895
- endpoint_totals: {'AUTHZ_COMPLETE_MUTATION': 267, 'GENERAL_AUTHENTICATED_READ': 109, 'ROLE_RESTRICTED': 16, 'PUBLIC_INTENTIONAL': 8, 'SELF_ONLY': 6, 'PERMISSION_RESTRICTED': 106}
- endpoint_total_sum: 512
- public_api_routes: 7
- public_framework_routes: 1
- total_effective_public_http_routes: 7
- MISSING_AUTHZ: 0
- POLICY_DECISION_REQUIRED: 0
- AUTH_ONLY_NO_OBJECT_CHECK: 0
- UNKNOWN: 0
- writer_count: 286
- writer_UNKNOWN: 0

## 11. Tests
- Local pytest: test_authz_ssot.py + test_authorization_phase1b.py + test_phase1b_final_consistency_iter365.py => 21 passed / 0 failed.
- Deployment readiness agent after docs disabling: PASS.
- Independent testing agent iteration 369: PASS for artifacts/tests (21/21) and confirmed no DB/deploy/mutation; it found external `/health` ECONNREFUSED, now documented as internal-only behind ingress with external `/api/health` as the valid health route.
- Independent testing agent iteration 370: found one stale markdown total (`total_effective_public_http_routes: 8`) in Section 10.
- Independent testing agent iteration 371: PASS; stale total corrected to 7, fingerprint aligned, docs/openapi/redoc disabled, external `/api/health` 200, targeted non-destructive pytest 21/21, no MOCKED APIs.

## 12. Checkpoint / Rollback Artifact
- PRE_DEPLOY_COMMIT: NOT_CREATED_BY_AGENT
- ROLLBACK_COMMIT: NOT_FINALIZED
- AUTH_MATRIX_CHECKSUM: 40ef104b7953e060d885c0c8ed55cd51f2de146904618c5bcecb8bb61cf50358
- WRITER_MATRIX_CHECKSUM: 257da342a2c8878995c16d575063dda3931ff321728cfba9ac88f698819fb895
- FINANCIAL_FINGERPRINT_CHECKSUM: 0f6c0f761d4bd6ec636fdddf9529e2a4abfa474212cf520b23a860c11e985edf
- Blocker: exact clean commit/rollback source cannot be identified until the source is saved as a clean checkpoint after external secret rotation/revocation decision.

## 13. FINAL GATE
- PRE-DEPLOY GATE = FAIL
- BLOCKER: 16 historical active/unknown server-side secrets require external rotation/revocation
- BLOCKER: remote/shared Git history sanitization is EXTERNAL_ACTION_REQUIRED and was not executed
- BLOCKER: working tree is DIRTY; exact clean commit/checkpoint not created
- no production data mutation: YES
- no AccountingEngine changes: YES
- no migrations: YES
- no deploy: YES
- no Phase 2: YES
