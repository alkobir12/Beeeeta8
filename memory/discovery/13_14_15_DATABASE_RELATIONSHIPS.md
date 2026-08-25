# 13/14/15 DATABASE + RELATIONSHIP + FINANCIAL-LINK (read-only)

## Tables (Supabase) columns

- **vehicles** (25 cols) FK-like: customer_id, technician_id
- **vehicle_visits** (9 cols) FK-like: technician_id, vehicle_id
- **operations** (16 cols) FK-like: account_id, vehicle_id, visit_id
- **journal_entries** (11 cols) FK-like: reference_id, workshop_id
- **accounts** (9 cols) FK-like: parent_id
- **customers** (12 cols) FK-like: —
- **parts** (12 cols) FK-like: —
- **services** (10 cols) FK-like: —
- **invoices** (21 cols) FK-like: customer_id, operation_id, vehicle_id, workshop_id
- **approval_requests** (18 cols) FK-like: customer_id, vehicle_id
- **business_accounts** (8 cols) FK-like: —
- **transactions** (11 cols) FK-like: account_id, vehicle_id
- **technicians** (9 cols) FK-like: —

## Orphan / referential integrity (application-level FKs)

- visits_bad_vehicle: 0
- ops_bad_vehicle: 0
- ops_bad_visit: 0

## Financial link integrity

- journal_entries: 150
- with_business_link: 142
- without_any_reference: 8
- reversal_entries: 16
- duplicate_reversal_targets: {}
- entries_touching_AR005: 107
- legacy_source_entries: 20
- source_distribution: {"operation": 31, "unified_visit_payment": 37, "vehicle_visit": 33, "reversal": 16, "hist_vehicle_ar_repair": 3, "manual": 7, "fin_engine_align_v1": 7, "period_close": 1, "historical_financial_repair": 3, "ajel_supplier_purchase": 3, "active_vehicle_ar_repair": 7, "operation_payment": 2}