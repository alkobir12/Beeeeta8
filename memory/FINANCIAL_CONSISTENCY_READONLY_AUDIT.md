# تدقيق الاتساق المالي الشامل — قراءة فقط

- generated_at: `2026-08-11T16:27:35.976077+00:00`
- الفترة الحالية: `2026-08-01` → `2026-08-11`
- mutation_guard: **PASS**
- فحوص ناجحة: **10/17**

## تطابق الذمم الحالية

| المصدر | الرقم |
|---|---:|
| ملفات المركبات | 9,181.00 |
| Unified engine | 9,181.00 |
| متابعة الذمم | 9,181.00 |
| دفتر الذمم | 9,181.00 |
| طبقات AR — الحالي | 9,181.00 |
| دفتر القيود — كل التاريخ | 22,563.84 |
| كاترينا — finance.ar_summary | 0.00 |
| كاترينا — ledger_ar_total | 22,563.84 |
| لوحة كاترينا | 0.00 |

## الفترة الحالية

- دفتر اليومية: مدين **66,739.68** = دائن **66,739.68**.
- قائمة الدخل canonical: إيراد **7,494.00**، مصروف **2,274.00**، صافي **5,220.00**.
- قيود غير مصنفة: **0**، قيود مستبعدة: **21**.
- فرق مطابقة العمليات/القيود: **38,692.16**.

## الافتتاحي والتاريخي منفصلان

- افتتاحي: AR **0.00**، إيراد **0.00**.
- تاريخي قبل الفترة: AR **0.00**، إيراد **0.00**.

## نتائج الفحوص

- ✅ `all_journal_entries_balanced`
- ✅ `no_duplicate_journal_ids`
- ✅ `vehicle_files_match_current_ar`
- ✅ `ar_customers_matches_engine`
- ✅ `ar_ledger_matches_engine`
- ✅ `ar_layers_current_matches_engine`
- ✅ `trial_balance_balanced_current_period`
- ❌ `balance_sheet_equation_balanced`
- ✅ `income_statement_has_no_unknown_entries`
- ❌ `operations_reconciliation_matched`
- ❌ `no_missing_operation_journals`
- ❌ `canonical_finalizations_unique_and_equal`
- ❌ `supplier_only_operations_do_not_touch_ar_or_revenue`
- ❌ `katrina_ar_matches_current_ar`
- ❌ `assistant_dashboard_ar_matches_current_ar`
- ✅ `journal_page_contains_full_ledger`
- ✅ `journal_period_endpoint_count_matches_raw`

## سجل التعارضات والأخطاء

### FIN-P0-01 — P0 — كاترينا لا تستخدم رصيد الذمم الحالي
- الدليل: current_ar=9,181.00 vs katrina=0.00
- السبب: finance.ar_summary يعرض stored_balances_total في total_ar رغم إعلانه أن journal_entries هو SSOT.
- التوصية: اجعل total_ar/current dashboard من current_vehicle_ar_total، واعرض ledger/history كطبقات مستقلة بأسماء صريحة.

### FIN-P0-02 — P0 — قيد تاريخي لمشتريات مورد أثّر في ذمم العملاء والإيراد
- الدليل: violations=1; AR/revenue impact=167.84
- السبب: قيد fin_engine_align_v1 قديم صُنّف بيعًا لعملية تحتوي supplier items فقط.
- التوصية: عكس القيد الخاطئ عبر AccountingEngine بعد اعتماد المالك؛ لا تحذفه ولا تعدله مباشرة.

### FIN-P0-03 — P0 — إجمالي نهائي محفوظ بلا قيد canonical مطابق
- الدليل: mismatches=1; details=[{'vehicle_id': 'b885d618-a2fa-45df-b14f-0a9e9ff1b484', 'final_customer_total': 2300.0, 'canonical_entries': 0, 'canonical_total': 0.0}]
- السبب: حفظ المركبة يسبق posting؛ عند فشل posting يمكن أن يبقى financial_finalization محفوظًا بلا vehfinal entry.
- التوصية: اجعل الحفظ/posting ذريًا أو أضف outbox/retry idempotent، ثم عالج السجل الحالي بموافقة صريحة.

### FIN-P0-04 — P0 — عقد الكاتب الواحد غير مطبق بالكامل
- الدليل: direct journal mutations=8; default fallback calls=5
- السبب: مسارات إصلاح/إقفال قديمة تحدّث journal_entries مباشرة وبعض callers لا تستخدم fallback=False.
- التوصية: مرّر كل mutation عبر AccountingEngine reverse/replace APIs، وأغلق fallback الافتراضي.

### FIN-P1-01 — P1 — الميزانية العمومية غير متوازنة بمقدار 908
- الدليل: assets=22,739.84; liabilities+equity=21,831.84; gap=908.00
- السبب: الحساب 006 رصيده دائن 454 لكن balance-sheet يستخدم abs(balance)، فيحوّل -454 إلى +454 ويضاعف الفرق إلى 908.
- التوصية: احتفظ بإشارة الرصيد أو صنّف contra/overdraft صراحة بدل abs().

### FIN-P1-02 — P1 — تقرير مطابقة العمليات غير متوافق مع نموذج canonical الحالي
- الدليل: difference=38,692.16; missing=43
- السبب: التقرير يتوقع قيدًا لكل operation ويجمع عمليات delivered/قديمة، بينما النموذج الحالي يعتمد قيد vehfinal واحدًا ويستبعد القيود المؤقتة دلاليًا.
- التوصية: أعد بناء reconciliation حول business_event_id/accounting_identity والتصنيف الدلالي، ولا تنفذ backfill الحالي آليًا.

### FIN-P1-03 — P1 — تاريخ as_of في الذمم غير مطبق فعليًا
- الدليل: period_start=9,181.00; today=9,181.00; end_date load count=0
- السبب: build_current_ar_snapshot يقبل end_date لكنه لا يستخدمه لتصفية الزيارات أو القيود.
- التوصية: طبّق cutoff موحدًا على visits/payments/journals واختبر نقاطًا تاريخية مختلفة.

### FIN-P1-04 — P1 — افتراضي اعتماد إجمالي المركبة يضيف مشتريات المورد
- الدليل: VehicleFinancialSummary: itemsTotal = serviceTotal + supplierPreview
- السبب: حقل finalCustomerTotal يبدأ من إجمالي البنود المرئي بدل customer_total/serviceTotal فقط.
- التوصية: اجعل القيمة الافتراضية customer_total فقط مع إبقاء المورد للمعاينة.

### FIN-P1-05 — P1 — متابعة الذمم تحتوي fallback صامتًا وcache قديمًا
- الدليل: عند فشل ar-ledger تُنسخ قيمة engine إلى ledger، وhydrate يبقي القيمة الأعلى حتى لو انخفض الرصيد الحي.
- السبب: منطق UX يخفي فشل المصدر ويمنع انخفاض الرصيد بعد السداد في بعض السباقات.
- التوصية: اعرض حالة source unavailable صراحة واستبدل cache دائمًا بالبيانات الحية ذات الإصدار الأحدث.

### FIN-P1-06 — P1 — ملخص لوحة المركبات لا يستخدم المحرك الموحد
- الدليل: dashboard_summaries_use_unified_engine=False
- السبب: vehicles/dashboard/summaries يحسب estimatedTotal من notes محليًا.
- التوصية: اجعله يستهلك batch summary من نفس read model المستخدم في ملف المركبة.

### FIN-P2-01 — P2 — دفتر اليومية سيعرض KPI جزئيًا بعد 50 قيدًا
- الدليل: current rows=36; frontend limit=50
- السبب: KPI يُحسب من safeEntries المحملة فقط وليس total/count server-side.
- التوصية: أضف totals endpoint أو pagination metadata قبل تجاوز 50 قيدًا.


## عقد المحرك الواحد — فحص الكود

- كتابات مباشرة على journal_entries خارج AccountingEngine: **8**.
- استدعاءات post_entry بدون fallback=False: **5**.
- end_date مستخدم فعليًا في current AR engine: **False**.
- كاترينا تعرض stored balances بدل current AR: **True**.
- افتراضي تسعير المركبة يضيف مشتريات المورد: **True**.
- متابعة الذمم قد تصنع تطابق ledger fallback: **True**.
- متابعة الذمم قد تُبقي cache أعلى من الرصيد الحي: **True**.
- دفتر اليومية مقيد بـ50 صفًا في الصفحة: **True**.
- dashboard summaries يستخدم unified engine: **False**.

## حدود فحص الإنتاج

- health: `200`.
- لم يُنفذ تدقيق بيانات Production لعدم توفر وصول/اعتماد إنتاجي داخل بيئة Preview؛ نتائج الأرقام أعلاه تخص Preview.

- JSON: `/app/test_reports/financial_consistency_readonly_audit.json`