# CHANGELOG

## 19 June 2026 — P0 Enterprise Operator: Centralized Accounting + Persistence + RBAC + Financial Actions

### 🏦 Phase 1 — Centralized Accounting Engine (`core/accounting_engine.py`)
- Single writer to Supabase `journal_entries`; validates double-entry balance (debit==credit).
- `IdentityStore` on MongoDB with UNIQUE index on `tx_hash` → race-safe idempotency. Hash = **item+price+time+customer** (+reference_id).
- `SupabaseGuardedClient` blocks direct journal_entries writes; `_insert_adaptive` strips unknown columns; `post_entry(entry)` adapter with safe fallback. Tested 9/9 (12-thread race → 1 winner).

### 💾 Phase 2 — Durable runtime state (`core/runtime_store.py`)
- Drafts/approvals/executions/audit persisted to MongoDB (`assistant_*`); write-through + hydrate on startup; survives restarts. Tested 11/11.

### 🔐 Phase 3 — Backend RBAC + Strict Four-Eyes (`core/rbac.py`, `routes_action_runtime.py`)
- Role/permission resolution from users store + `config/role_permissions.json`. Approver roles `admin,manager,supervisor`.
- Removed `reviewer:` bypass; approver = REAL identity. Strict Four-Eyes (`ACTION_RUNTIME_ENFORCE_4EYES=true`): self-approval → 403 `four_eyes_violation`; non-approver → 403 `permission_denied`. Tested 9/9 module + live API.
- ⚠️ BEHAVIOR CHANGE: solo self-approval of risky actions now blocked (needs 2nd approver, or set `ACTION_RUNTIME_ENFORCE_4EYES=false`).

### 💰 Phase 4 — Financial actions via engine (`core/financial_actions.py`, `routes_financial_actions.py`)
- `POST /api/finance-actions/{invoice,payment,expense}` — balanced, idempotent, RBAC-protected. Tested 6/6.

### 🧹 Journal daybook cleanup (`pages/JournalEntries.jsx`)
- Strip raw tags `[PARTY:..][VEHICLE_REF:..][VISIT:..][PARTY_TYPE:..]`; `cleanDescription` removes duplicated party/plate. Verified visually.

### 🔗 Single-source-of-truth wiring (COMPLETE)
- ALL `journal_entries` writes now route through `AccountingEngine.post_entry` (engine is `entry_id`-aware, adaptive columns, idempotent):
  `routes_extended` (`_safe_insert_journal_entry` + integrity_auto_fix), `routes_finance` (manual create + period-close + repair backfill), `routes_smart_accounting`, `routes_suppliers_extended`, `routes_firewall` auto-fix, `server.py` (cash-fix + operation sale).
- Verified: manual create dedups (repost → same id, 1 row); reports (trial-balance/income/cash-flow/balance-sheet) + firewall reconciliation all 200.

### 🔗 Full linkage verified (iteration 239 — 9/9 backend + frontend)
- engine → journal page → dashboard KPIs → reports → firewall reconciliation all consistent; clean daybook descriptions; bot auto-commit + Four-Eyes intact.


## 13 May 2026 — Smart POS reference operations + journal card clarity
- Smart POS now creates reference operations via `POST /api/operations` for most templates instead of only writing standalone journal entries.
- Journal entries API now exposes `payment_method`, `payment_method_label_ar`, `payment_status`, and `payment_status_label_ar`.
- Journal Entries cards now show clearer payment method/source/status pills in Arabic.
- Bank deposit remains a direct journal-entry flow for now.

## 13 May 2026 — OperationCard payment visibility fix
- Operations page now refetches operation data on mount instead of relying on stale cached status.
- Added explicit payment status pill, paid amount, and remaining balance display to `OperationCard.jsx`.
- Improved journal entry text fallback so service operations show `إيرادات الخدمات` instead of incomplete `الحساب` text.
- Verified on the real case: paid 300 / remaining 2000 is now clearly visible in the UI.

## 13 May 2026 — Live vehicle updates reflected in operations
- `GET /api/operations` and `GET /api/operations/{id}` now enrich vehicle-linked operations with live vehicle/customer fields from the current vehicle record.
- Operations responses now include `customerName`, `customerPhone`, `vehiclePlate`, `vehicleBrand`, and `vehicleModel` for linked vehicle operations.
- `OperationCard.jsx` now prefers live vehicle customer data for customer-linked vehicle operations.

## 13 May 2026 — Supplier/vehicle reference-page linking
- Added supplier journal-token parsing so supplier-linked manual/POS journal entries can be surfaced inside supplier movements.
- Added linked journal entries panel in `VehicleDetails.jsx` so vehicle/customer/visit-related journal entries appear inside the vehicle file.
- Improved suppliers loading state copy for long-running balance/movement fetches.
- Fixed `extractJournalTag` regex parsing in VehicleDetails after test feedback.

## 12 May 2026 — Payments ↔ Operations sync completed
- Linked operation payment fields to live visit payment data in `supabase_service.py`.
- `GET /api/operations` and `GET /api/operations/{id}` now surface `paymentMethod`, `paymentStatus`, `paymentAmount`, `totalPaid`, `advancePaid`, and `balance` from the linked visit when available.
- Verified the visit-linked operation flow without creating new test data.

## 12 May 2026 — Vehicle files + receipt vouchers + account mapping audit
- Fixed vehicle `fileNumber` and `customerFileNumber` save flow across backend and VehicleDetails UI.
- Fixed Smart POS account mapping so salary uses `036 رواتب إدارية` and payment methods map correctly to `003/004/006`.
- Added visit payment journal posting from VehicleDetails using `source=visit_receipt_voucher` and visit/customer/vehicle tokens.
- Improved `GET /api/finance/journal-entries/{entry_id}` to expose top-level fields plus backward-compatible `data`.
- Cleaned recent test data (test vehicles, test journal entries, and extra temporary payment artifacts).

## 11 May 2026 — Smart POS Journal completed
- Completed `SmartPOSJournal.jsx` as a single-screen Smart POS for journal entries.
- Added 8 templates: instant sale, cash sale, bank/card sale, salary, cash expense, collect customer, pay supplier, bank deposit.
- Merged the old cashier cart into the **items section** inside the same Smart POS flow.
- Added customer, vehicle, and items fields with live lookup from customers, suppliers, vehicles, parts, and services APIs.
- Saving now posts balanced journal entries to `POST /api/finance/journal-entries` with `[PARTY]`, `[PARTY_TYPE]`, `[VEHICLE_REF]` description tags.
- Added recent-entry copy flow and kept POS/full view toggle working.
- Hardened `JournalEntries.jsx` fetch lifecycle with `AbortController` during navigation.

## Verification
- `/app/test_reports/iteration_206.json` → PASS
- `/app/test_reports/iteration_205.json` → PASS
- `/app/test_reports/iteration_203.json` → PASS
- `/app/test_reports/iteration_202.json` → PASS
- `/app/test_reports/iteration_201.json` → PASS
- `/app/test_reports/iteration_200.json` → PASS (with low note fixed afterward)
- `/app/test_reports/iteration_199.json` → PASS
- `auto_frontend_testing_agent` → PASS
- `deep_testing_backend_v2` → 7/7 PASS
