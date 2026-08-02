# P0.2 — تدقيق مالي شامل — production

قراءة فقط: لا إنشاء حساب، لا قيد، لا تعديل، لا حذف، لا ترحيل، لا تغيير واجهات.

## تطابق لوحة التحكم
- expected_dashboard_count_from_user: `17`
- actual_dashboard_count_from_dom_logic: `17`
- report_count: `17`
- ids_equal: `True`
- count_matches_user_expected: `True`
- dashboard_vehicle_ids: `['a422209f-8cec-48a6-b06a-49e0c89972e6', 'f6590225-aef6-452b-af39-e0e42061fd81', 'b885d618-a2fa-45df-b14f-0a9e9ff1b484', 'a57b698d-752d-43bf-be66-41a0337de9eb', 'a717c745-3d53-43d0-b235-ef90a794311f', 'c02cc9c7-6ff5-4fc7-9414-b15787fa9000', 'd5376421-bd6e-420e-8585-ba36c3314082', 'b9fe95f6-e4c3-4466-b853-c0103dc75929', 'c5bfe993-c45a-4412-b196-be1cdd310c40', 'ce2e776e-d750-4e34-b20a-ef21f49cad63', '0ee51492-8405-4235-8c63-4ca01b6bccc8', '235cb00f-facb-46aa-a4eb-8db039ec21ee', '523451c4-01a9-455e-902c-b21ae944a85f', '9004d4bd-ed82-4e0d-afa4-fd62e6e3d8fa', 'c92405eb-2097-4f42-aa3e-ccd455d9812f', '6a8ace60-5ed7-48dd-bfd1-7d47d408f706', 'bea27237-7274-4fe2-84b3-8106740645d7']`
- report_vehicle_ids: `['a422209f-8cec-48a6-b06a-49e0c89972e6', 'f6590225-aef6-452b-af39-e0e42061fd81', 'b885d618-a2fa-45df-b14f-0a9e9ff1b484', 'a57b698d-752d-43bf-be66-41a0337de9eb', 'a717c745-3d53-43d0-b235-ef90a794311f', 'c02cc9c7-6ff5-4fc7-9414-b15787fa9000', 'd5376421-bd6e-420e-8585-ba36c3314082', 'b9fe95f6-e4c3-4466-b853-c0103dc75929', 'c5bfe993-c45a-4412-b196-be1cdd310c40', 'ce2e776e-d750-4e34-b20a-ef21f49cad63', '0ee51492-8405-4235-8c63-4ca01b6bccc8', '235cb00f-facb-46aa-a4eb-8db039ec21ee', '523451c4-01a9-455e-902c-b21ae944a85f', '9004d4bd-ed82-4e0d-afa4-fd62e6e3d8fa', 'c92405eb-2097-4f42-aa3e-ccd455d9812f', '6a8ace60-5ed7-48dd-bfd1-7d47d408f706', 'bea27237-7274-4fe2-84b3-8106740645d7']`
- missing_in_report: `[]`
- extra_in_report: `[]`

## ملخص الصفحات
| الصفحة | المصادر | العدد | الظاهر | الصحيح | التكرارات | غير مرتبط | النتيجة | الملاحظات |
|---|---|---:|---:|---:|---:|---:|---|---|
| لوحة التحكم | /api/vehicles, /api/technicians, /api/finance/ar/customers | 17 | 17 | 17 | 0 | 5 | PASS |  |
| ملف المركبة | /api/vehicles, /api/vehicles/{vehicle_id}/visits, /api/vehicles/{vehicle_id}/financial-summary | 17 | 25505.0 | 12579.0 | 0 | 5 | BLOCKER | supplier total shown separately; not customer AR |
| الزيارات وجميع تبويباتها | /api/vehicles/{vehicle_id}/visits, /api/visits/{visit_id}/operations | 19 | 12579.0 | 12579.0 | 0 | 5 | BLOCKER |  |
| صفحة العمليات | /api/operations | 12 | 9343.86 | 12579.0 | 0 | 5 | BLOCKER | requires P1 engine to enforce single source |
| متابعة الذمم والتحصيل | /api/finance/ar/customers, /api/finance/ar/ledger | 1 | -200.0 | 12548.0 | 0 | 5 | BLOCKER |  |
| دفتر اليومية | /api/finance/journal-entries | 10 | 5343.86 | 5343.86 | 0 | 5 | BLOCKER | orphan refs: 5 |
| القوائم والتقارير المالية | /api/finance/reports/income-statement, /api/finance/reconciliation-audit | 0 | 200 | 31.0 | 0 | 5 | BLOCKER |  |
| النقد والبنك ونقاط البيع | /api/finance/journal-entries, /api/biz-accounts | 10 | حسب journal lines | يحتاج breakdown من journal lines بعد P1 | 0 | 5 | WARNING | read-only endpoint لا يعطي breakdown موحد حالياً |
| POS | /api/operations, /api/finance/journal-entries | 0 | 0 | 0 | 0 | 5 | WARNING | requires endpoint-level enforcement audit in P1 |
| الموردون والمشتريات | /api/suppliers-ext/movements, /api/suppliers-ext/purchases, /api/suppliers-ext/suppliers | 0 | 12926.0 | 12926.0 | 0 | 5 | WARNING | supplier endpoints غير متاحة/تحتاج صلاحية أو مسار مختلف |
| العملاء وأرصدة العملاء المقدمة | /api/customers, /api/finance/ar/customers | 216 | 169.0 | 169.0 | 0 | 5 | WARNING | account not created by design in P0.2 |
| الأرشيف والاستعادة | /api/archive/vehicles, /api/vehicles | 0 | 0 | 0 | 0 | 5 | PASS |  |
| كاترينا وسجل إجراءاتها | /api/runtime/approvals, /api/assistant/*, /api/workshop-bot/* | 0 | 0 | 0 | 0 | 5 | WARNING | static scan shows assistant can preview/create financial actions; P1 must enforce backend engine |
| شجرة الحسابات والسنة المالية | /api/chart-of-accounts, /api/accounts | 189 | 0 | 0 | 0 | 5 | PASS |  |
| زر حذف العمليات وأثر الحذف السابق | /api/operations, /api/finance/journal-entries | 12 | 0 | 0 | 0 | 5 | BLOCKER | journal references missing due previous deletion |
| Endpoints ذات أثر مالي | static scan + listed APIs | 0 | 0 | 0 | 0 | 5 | WARNING | see mutation_endpoints_scan |

## الإجماليات المالية الصحيحة حسب القاعدة
- workshop_service_total: `12579.0`
- supplier_cost_archive_total: `12926.0`
- confirmed_received_no_duplicates: `200.0`
- applied_to_service: `31.0`
- remaining_on_customer: `12548.0`
- customer_advance_pending: `169.0`

## الحالة المرجعية 31/271/200
- environment: `production`
- vehicle_id: `f6590225-aef6-452b-af39-e0e42061fd81`
- visit_id: `1d40d657-f682-40a5-b404-4bea38757a12`
- customer: `خالد القبيشي`
- workshop_service_total: `31.0`
- supplier_cost_archive_total: `271.0`
- received_amount: `200.0`
- applied_to_service: `31.0`
- remaining_on_customer: `0.0`
- customer_advance_pending: `169.0`
- status_expected: `مسدد + رصيد عميل`
- invalid_values_absent: `['102', '400', '-98']`

## إثبات توازن اليومية
- total_debit: `5343.86`
- total_credit: `5343.86`
- balanced: `True`
- imbalanced_entries_count_sampled: `0`

## الاستثناءات
| severity | type | details |
|---|---|---|
| BLOCKER | orphan_journal_entries_detected | `{"severity": "BLOCKER", "type": "orphan_journal_entries_detected", "count": 5, "note": "قيود ذات مراجع غير مرتبطة تحتاج تفسير قبل P1."}` |
| WARNING | notes_payment_not_verified | `{"severity": "WARNING", "type": "notes_payment_not_verified", "vehicle_id": "a717c745-3d53-43d0-b235-ef90a794311f", "visit_id": "73ea8c01-e3b2-4c8c-9696-08f7cbcdf48e", "amount": 3000.0, "classification": "قيدها مفقود بسبب الحذف السابق", "journalEntryId": "f4a335b3-29a2-440e-bdad-a818abdbf3a0"}` |
| WARNING | notes_payment_not_verified | `{"severity": "WARNING", "type": "notes_payment_not_verified", "vehicle_id": "a717c745-3d53-43d0-b235-ef90a794311f", "visit_id": "73ea8c01-e3b2-4c8c-9696-08f7cbcdf48e", "amount": 5000.0, "classification": "تحتاج تأكيد المالك", "journalEntryId": ""}` |
| WARNING | notes_payment_not_verified | `{"severity": "WARNING", "type": "notes_payment_not_verified", "vehicle_id": "d5376421-bd6e-420e-8585-ba36c3314082", "visit_id": "3aa0a6dc-bddb-46f2-ba49-3dbfbf386f14", "amount": 1950.0, "classification": "قيدها مفقود بسبب الحذف السابق", "journalEntryId": "f6611322-da47-45c4-8bce-7a40909696ac"}` |
| WARNING | notes_payment_not_verified | `{"severity": "WARNING", "type": "notes_payment_not_verified", "vehicle_id": "b9fe95f6-e4c3-4466-b853-c0103dc75929", "visit_id": "2635ecf1-fd3b-4fe2-9629-f658f9a2c26d", "amount": 2000.0, "classification": "قيدها مفقود بسبب الحذف السابق", "journalEntryId": "1828fc4c-156a-4af5-9451-3b906ba220ac"}` |
| WARNING | notes_payment_not_verified | `{"severity": "WARNING", "type": "notes_payment_not_verified", "vehicle_id": "ce2e776e-d750-4e34-b20a-ef21f49cad63", "visit_id": "5f3b0fd2-b225-407c-8c8d-d3e82c9a129a", "amount": 2350.0, "classification": "قيدها مفقود بسبب الحذف السابق", "journalEntryId": "3715d6c3-831e-402e-8bc8-a61df148297d"}` |
| WARNING | notes_payment_not_verified | `{"severity": "WARNING", "type": "notes_payment_not_verified", "vehicle_id": "235cb00f-facb-46aa-a4eb-8db039ec21ee", "visit_id": "822ca57a-2cd2-4b2f-84c6-f5001170ce73", "amount": 1000.0, "classification": "قيدها مفقود بسبب الحذف السابق", "journalEntryId": "6194a071-fded-42df-a6cc-6bd42be9736e"}` |
| WARNING | notes_payment_not_verified | `{"severity": "WARNING", "type": "notes_payment_not_verified", "vehicle_id": "235cb00f-facb-46aa-a4eb-8db039ec21ee", "visit_id": "2fa1bd0a-9b77-43da-8944-9680a3671f94", "amount": 877.0, "classification": "تحتاج تأكيد المالك", "journalEntryId": ""}` |
| WARNING | notes_payment_not_verified | `{"severity": "WARNING", "type": "notes_payment_not_verified", "vehicle_id": "6a8ace60-5ed7-48dd-bfd1-7d47d408f706", "visit_id": "ba89782c-65b1-4c4e-8fa7-30707379e2b2", "amount": 100.0, "classification": "تحتاج تأكيد المالك", "journalEntryId": ""}` |
| WARNING | notes_payment_not_verified | `{"severity": "WARNING", "type": "notes_payment_not_verified", "vehicle_id": "bea27237-7274-4fe2-84b3-8106740645d7", "visit_id": "4075cc96-b1c1-4bd3-9f7b-6b35c7ab666f", "amount": 250.0, "classification": "تحتاج تأكيد المالك", "journalEntryId": ""}` |
| WARNING | orphan_journal_reference | `{"severity": "WARNING", "type": "orphan_journal_reference", "details": {"journal_entry_id": "607b2ed6-4e78-4f52-b508-98eecfabf3e1", "reference_id": "b1305e60-4c05-4c10-bbf7-185601cbe66c", "source": "operation", "total": 400.0}}` |
| WARNING | orphan_journal_reference | `{"severity": "WARNING", "type": "orphan_journal_reference", "details": {"journal_entry_id": "8a4ac035-c30d-4906-afcd-f85fdcc93af5", "reference_id": "b1305e60-4c05-4c10-bbf7-185601cbe66c", "source": "operation_payment", "total": 400.0}}` |
| WARNING | orphan_journal_reference | `{"severity": "WARNING", "type": "orphan_journal_reference", "details": {"journal_entry_id": "4e7442fc-00d5-49ab-be18-838d07e985dc", "reference_id": "574e6384-7436-4751-9474-c673676e6c9e", "source": "operation", "total": 37.0}}` |
| WARNING | orphan_journal_reference | `{"severity": "WARNING", "type": "orphan_journal_reference", "details": {"journal_entry_id": "5ee0f987-f2f5-44e3-b288-6ab6aaf0ba9d", "reference_id": "c95623c4-b0b3-4ac8-9f77-a6cc89587bb5", "source": "operation", "total": 126.0}}` |
| WARNING | orphan_journal_reference | `{"severity": "WARNING", "type": "orphan_journal_reference", "details": {"journal_entry_id": "08dcd95b-cf12-4fdd-9081-66ec3ab27f6f", "reference_id": "0b422be3-52eb-4de3-9616-47283db56f42", "source": "operation", "total": 498.86}}` |

## قائمة منافذ الإنشاء/التعديل/الحذف ذات الأثر المالي
- DELETE `/invoice-templates/{tid}` — `/app/backend/routes_templates_extended.py`
- PUT `/invoice-templates/{tid}` — `/app/backend/routes_templates_extended.py`
- POST `/invoice-templates/create-blank` — `/app/backend/routes_templates_extended.py`
- POST `/invoice-templates/{tid}/design` — `/app/backend/routes_templates_extended.py`
- POST `/invoice-templates/{tid}/save-json` — `/app/backend/routes_templates_extended.py`
- POST `/invoice-templates/{tid}/make-default` — `/app/backend/routes_templates_extended.py`
- POST `/invoice-templates/{tid}/update-mapping` — `/app/backend/routes_templates_extended.py`
- POST `/invoice-templates/{tid}/save-named` — `/app/backend/routes_templates_extended.py`
- POST `/invoice-templates/{tid}/auto-save` — `/app/backend/routes_templates_extended.py`
- POST `/print/invoice-xlsx` — `/app/backend/routes_templates_extended.py`
- POST `/accounts` — `/app/backend/routes_accounts_extended.py`
- PUT `/accounts/{account_id}` — `/app/backend/routes_accounts_extended.py`
- PATCH `/accounts/{account_id}/active` — `/app/backend/routes_accounts_extended.py`
- DELETE `/accounts/{account_id}` — `/app/backend/routes_accounts_extended.py`
- POST `/accounts/reindex-display-codes` — `/app/backend/routes_accounts_extended.py`
- PATCH `/accounts/{account_id}/touch` — `/app/backend/routes_accounts_extended.py`
- POST `/accounts/init-defaults` — `/app/backend/routes_accounts_extended.py`
- PUT `/{invoice_id}` — `/app/backend/routes_invoices.py`
- POST `/invoice` — `/app/backend/routes_financial_actions.py`
- POST `/payment` — `/app/backend/routes_financial_actions.py`
- POST `/confirm-payment` — `/app/backend/idempotency.py`
- POST `/customers` — `/app/backend/routes_notion.py`
- POST `/reports/reconciliation/backfill-journals` — `/app/backend/routes_finance.py`
- POST `/chart-of-accounts` — `/app/backend/routes_finance.py`
- POST `/journal-entries` — `/app/backend/routes_finance.py`
- PUT `/journal-entries/{entry_id}` — `/app/backend/routes_finance.py`
- DELETE `/journal-entries/{entry_id}` — `/app/backend/routes_finance.py`
- POST `/reports/reclassify-payment-accounts` — `/app/backend/routes_finance.py`
- POST `/reports/repost-bank-and-fix-imbalance` — `/app/backend/routes_finance.py`
- POST `/reports/reclassify-vehicle-workshop-dues` — `/app/backend/routes_finance.py`
- DELETE `/reset-ops-journals-keep-debts` — `/app/backend/routes_finance.py`
- POST `/ar/migrate-operations-workshop` — `/app/backend/routes_finance.py`
- POST `/reports/reclassify-revenue-sub-accounts` — `/app/backend/routes_finance.py`
- POST `/biz-accounts` — `/app/backend/routes_extended.py`
- POST `/biz-accounts/cleanup` — `/app/backend/routes_extended.py`
- PUT `/biz-accounts/{aid}` — `/app/backend/routes_extended.py`
- DELETE `/biz-accounts/{aid}` — `/app/backend/routes_extended.py`
- POST `/operations/integrity/check` — `/app/backend/routes_extended.py`
- POST `/operations/integrity/fix-all` — `/app/backend/routes_extended.py`
- POST `/vehicles/dashboard/summaries` — `/app/backend/routes_extended.py`
- PUT `/operations/{op_id}` — `/app/backend/routes_extended.py`
- DELETE `/operations/{op_id}` — `/app/backend/routes_extended.py`
- DELETE `/operations` — `/app/backend/routes_extended.py`
- POST `/operations/{op_id}/confirm-payment` — `/app/backend/routes_extended.py`
- POST `/operations` — `/app/backend/routes_extended.py`
- POST `/vehicles/{vehicle_id}/visits` — `/app/backend/routes_extended.py`
- PUT `/visits/{visit_id}` — `/app/backend/routes_extended.py`
- DELETE `/visits/{visit_id}` — `/app/backend/routes_extended.py`
- PUT `/{account_id}` — `/app/backend/routes_accounts_chart.py`
- DELETE `/{account_id}` — `/app/backend/routes_accounts_chart.py`
- POST `/{account_id}/adjust` — `/app/backend/routes_accounts_chart.py`
- POST `/customers` — `/app/backend/routes_import.py`
- POST `/accounts/track-usage` — `/app/backend/routes_smart_accounting.py`
- POST `/supplier-balance-payment` — `/app/backend/routes_smart_accounting.py`
- POST `/operations/{op_id}/confirm-via-supplier-balance` — `/app/backend/routes_smart_accounting.py`
- POST `/vehicle/{vehicle_id}/archive` — `/app/backend/routes_smart_accounting.py`
- POST `/drafts/{draft_id}/spawn_supplier` — `/app/backend/routes_action_runtime.py`
- POST `/vehicles/{vehicle_id}/upload-file` — `/app/backend/routes_vehicle_files.py`
- POST `/vehicles/compare-diagnostics` — `/app/backend/routes_vehicle_files.py`
- POST `/{supplier_id}/settlements` — `/app/backend/routes_suppliers_extended.py`
- DELETE `/{supplier_id}/settlements/{settlement_id}` — `/app/backend/routes_suppliers_extended.py`
- PUT `/{vehicle_id}` — `/app/backend/domains/vehicles/router.py`
- DELETE `/{vehicle_id}` — `/app/backend/domains/vehicles/router.py`
- PUT `/{customer_id}` — `/app/backend/domains/customers/router.py`
- DELETE `/{customer_id}` — `/app/backend/domains/customers/router.py`
- PUT `/{supplier_id}` — `/app/backend/domains/suppliers/router.py`
- DELETE `/{supplier_id}` — `/app/backend/domains/suppliers/router.py`

## ملف JSON
- `/app/test_reports/p02_production_financial_audit_raw.json`