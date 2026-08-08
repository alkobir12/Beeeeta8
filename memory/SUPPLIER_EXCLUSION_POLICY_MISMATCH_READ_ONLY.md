# Read-only Audit — Supplier Exclusion Policy Mismatch

Policy: ALL SUPPLIER ITEMS ARE ARCHIVE / SUPPLIER MOVEMENT ONLY and excluded from workshop revenue/customer receivable/customer balance/payment allocation.

- operations_scanned: 55
- journal_entries_scanned: 29
- supplier_policy_violations_count: 7
- duplicate_non_supplier_over_expected_not_included_in_policy_count: 3

## 1. Operation `1d40d657-f682-40a5-b404-4bea38757a12` — LEGACY_ACCOUNTING_POLICY_MISMATCH
- type: **service**
- partner: **خالد القبيشي**
- operation_total_field: **31.0**
- workshop_service_total: **31.0**
- supplier_archive_total: **271.0**
- expected_customer_receivable: **31.0**
- actual_journal_receivable: **302.0**
- actual_revenue: **302.0**
- difference: **271.0**
- revenue_difference: **271.0**
- journal_entries:
  - `2933cb91-682e-4844-8913-37ba6c48140b` source=active_vehicle_ar_repair tx=sale total=302.0 ar_debit=302.0 revenue_credit=302.0
- supplier_items_sample:
  - {'name': 'فلتر ديزل', 'total': 119.0, 'itemType': 'supplier', 'billingType': 'supplier'}
  - {'name': 'فلتر هواء', 'total': 152.0, 'itemType': 'supplier', 'billingType': 'supplier'}

## 2. Operation `73ea8c01-e3b2-4c8c-9696-08f7cbcdf48e` — LEGACY_ACCOUNTING_POLICY_MISMATCH
- type: **service**
- partner: **خالد عماش الحربي**
- operation_total_field: **2251.0**
- workshop_service_total: **2121.0**
- supplier_archive_total: **5879.0**
- expected_customer_receivable: **2121.0**
- actual_journal_receivable: **0**
- actual_revenue: **2251.0**
- difference: **-2121.0**
- revenue_difference: **130.0**
- journal_entries:
  - `f8dff8a6-4499-40c7-a0e2-4a6dfcb4d5bd` source=operation tx=sale total=2251.0 ar_debit=0 revenue_credit=2251.0
- supplier_items_sample:
  - {'name': 'الحميدان التركي', 'total': 1869.0, 'itemType': 'supplier', 'billingType': 'supplier'}
  - {'name': 'الحميدان التركي', 'total': 299.0, 'itemType': 'supplier', 'billingType': 'supplier'}
  - {'name': 'الدريويش', 'total': 200.0, 'itemType': 'supplier', 'billingType': 'supplier'}
  - {'name': 'القرعاوي', 'total': 450.0, 'itemType': 'supplier', 'billingType': 'supplier'}
  - {'name': 'القرعاوي', 'total': 364.0, 'itemType': 'supplier', 'billingType': 'supplier'}
  - {'name': 'مخرطه', 'total': 300.0, 'itemType': 'supplier', 'billingType': 'supplier'}
  - {'name': 'مخرطه', 'total': 1100.0, 'itemType': 'supplier', 'billingType': 'supplier'}
  - {'name': 'المزيد', 'total': 136.0, 'itemType': 'supplier', 'billingType': 'supplier'}

## 3. Operation `174f49a1-5482-43d5-b333-ede2743a7d79` — LEGACY_ACCOUNTING_POLICY_MISMATCH
- type: **service**
- partner: **فيصل الجفير**
- operation_total_field: **1210.0**
- workshop_service_total: **1210.0**
- supplier_archive_total: **1090.0**
- expected_customer_receivable: **1210.0**
- actual_journal_receivable: **3510.0**
- actual_revenue: **3510.0**
- difference: **2300.0**
- revenue_difference: **2300.0**
- journal_entries:
  - `ea999c19-4bfc-4771-83f1-ebae1dae70c9` source=fin_engine_align_v1 tx=sale total=2300.0 ar_debit=2300.0 revenue_credit=2300.0
  - `e4333a1d-6785-4ebe-a381-b2b990dfd1b6` source=operation tx=sale total=1210.0 ar_debit=1210.0 revenue_credit=1210.0
- supplier_items_sample:
  - {'name': 'الراكضي', 'total': 470.0, 'itemType': 'supplier', 'billingType': 'supplier'}
  - {'name': 'مخرطة العوفي', 'total': 420.0, 'itemType': 'supplier', 'billingType': 'supplier'}
  - {'name': 'الراكضي', 'total': 200.0, 'itemType': 'supplier', 'billingType': 'supplier'}

## 4. Operation `3b1ccedf-29c6-4d9e-9108-f11a7bcc5c5e` — LEGACY_ACCOUNTING_POLICY_MISMATCH
- type: **service**
- partner: **مد الله الثواتي**
- operation_total_field: **0.0**
- workshop_service_total: **0**
- supplier_archive_total: **167.84**
- expected_customer_receivable: **0**
- actual_journal_receivable: **167.84**
- actual_revenue: **167.84**
- difference: **167.84**
- revenue_difference: **167.84**
- journal_entries:
  - `1b91f14d-caa0-4212-a34b-f5d4f7c7cca3` source=fin_engine_align_v1 tx=sale total=167.84 ar_debit=167.84 revenue_credit=167.84
- supplier_items_sample:
  - {'name': 'اليمني', 'total': 77.84, 'itemType': 'supplier', 'billingType': 'supplier'}
  - {'name': 'مؤسسة وليد الجبيل التجارية', 'total': 90.0, 'itemType': 'supplier', 'billingType': 'supplier'}

## 5. Operation `2635ecf1-fd3b-4fe2-9629-f658f9a2c26d` — LEGACY_ACCOUNTING_POLICY_MISMATCH
- type: **service**
- partner: **فارس عوض **
- operation_total_field: **2300.0**
- workshop_service_total: **2300.0**
- supplier_archive_total: **7381.0**
- expected_customer_receivable: **2300.0**
- actual_journal_receivable: **5981.0**
- actual_revenue: **5981.0**
- difference: **3681.0**
- revenue_difference: **3681.0**
- journal_entries:
  - `5abdbff4-cbc9-4a55-ab95-8280d491d367` source=fin_engine_align_v1 tx=sale total=3181.0 ar_debit=3181.0 revenue_credit=3181.0
  - `e90e9a39-19ff-4d94-b33b-b6be613530e0` source=active_vehicle_ar_repair tx=sale total=500.0 ar_debit=500.0 revenue_credit=500.0
  - `74045e29-c57a-4266-b6ce-aed98066cdc6` source=operation tx=sale total=2300.0 ar_debit=2300.0 revenue_credit=2300.0
- supplier_items_sample:
  - {'name': 'القرعاوي', 'total': 7199.0, 'itemType': 'supplier', 'billingType': 'supplier'}
  - {'name': 'القرعاوي', 'total': 182.0, 'itemType': 'supplier', 'billingType': 'supplier'}

## 6. Operation `3aa0a6dc-bddb-46f2-ba49-3dbfbf386f14` — LEGACY_ACCOUNTING_POLICY_MISMATCH
- type: **service**
- partner: **فهد الطريسي**
- operation_total_field: **1843.0**
- workshop_service_total: **1700.0**
- supplier_archive_total: **2578.0**
- expected_customer_receivable: **1700.0**
- actual_journal_receivable: **2428.0**
- actual_revenue: **4271.0**
- difference: **728.0**
- revenue_difference: **2571.0**
- journal_entries:
  - `9416bb26-9bbb-423c-baa7-3b3b7ec2ad14` source=operation tx=sale total=1843.0 ar_debit=0 revenue_credit=1843.0
  - `e3ef28ca-459a-423d-a7d6-c03e51be5e5a` source=active_vehicle_ar_repair tx=sale total=2428.0 ar_debit=2428.0 revenue_credit=2428.0
- supplier_items_sample:
  - {'name': 'القرعاوي', 'total': 143.0, 'itemType': 'supplier', 'billingType': 'supplier'}
  - {'name': 'كتاوت', 'total': 143.0, 'itemType': 'part', 'billingType': 'supplier'}
  - {'name': 'القرعاوي', 'total': 1947.0, 'itemType': 'supplier', 'billingType': 'supplier'}
  - {'name': 'ساسكو', 'total': 150.0, 'itemType': 'supplier', 'billingType': 'supplier'}
  - {'name': 'الموسى', 'total': 195.0, 'itemType': 'supplier', 'billingType': 'supplier'}

## 7. Operation `6484969a-7714-43f8-b0b9-782c915b8abc` — LEGACY_ACCOUNTING_POLICY_MISMATCH
- type: **service**
- partner: **ابراهيم صالح **
- operation_total_field: **1800.0**
- workshop_service_total: **1000.0**
- supplier_archive_total: **975.0**
- expected_customer_receivable: **1000.0**
- actual_journal_receivable: **1975.0**
- actual_revenue: **1975.0**
- difference: **975.0**
- revenue_difference: **975.0**
- journal_entries:
  - `6e010906-442f-41e1-ae0d-dae98bf5b094` source=active_vehicle_ar_repair tx=sale total=1975.0 ar_debit=1975.0 revenue_credit=1975.0
- supplier_items_sample:
  - {'name': 'الراكضي', 'total': 175.0, 'itemType': 'supplier', 'billingType': 'supplier'}
  - {'name': 'كراسي تيمن مع مسامير وعصافير ', 'total': 800.0, 'itemType': 'part', 'billingType': 'supplier'}

## Non-supplier duplicates observed but excluded from this policy report
- `ca32e1a6-a0d5-46f0-b2c0-ede7439c1da0` expected=150.0 actual_ar=300.0 actual_revenue=300.0
- `0fd379c7-8d78-4151-b32f-beeb32dae664` expected=2500.0 actual_ar=5000.0 actual_revenue=5000.0
- `f5813fbd-f4b4-4561-9f13-9893d1880cc8` expected=800.0 actual_ar=1600.0 actual_revenue=1600.0
