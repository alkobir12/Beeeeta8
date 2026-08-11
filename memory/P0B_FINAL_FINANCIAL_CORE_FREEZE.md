# P0-B + Visit/QuickPrint Final Acceptance — Financial Core Frozen

## النطاق
- البيئة: **Preview فقط**.
- Production: **لم يُفحص ولم يُعدّل**.
- التصحيح اقتصر على الحالتين المعتمدتين؛ لا Financial Audit جديد ولا cleanup/history repair إضافي.

## P0-B — التصحيح المستهدف

### الحالة A — 2,300
- vehicle: `b885d618-a2fa-45df-b14f-0a9e9ff1b484`
- visit: `174f49a1-5482-43d5-b333-ede2743a7d79`
- originals محفوظة؛ أضيفت correction entries عبر AccountingEngine لعكس alignment `2,300` وtemporary `1,210`.
- canonical واحد فقط: `vehfinal:b885d618-a2fa-45df-b14f-0a9e9ff1b484` بقيمة `2,300`.
- النتيجة: AR=`2,300`، Revenue=`2,300`، duplicate canonical=`0`.

### الحالة B — Supplier 167.84
- vehicle: `8708bbd6-18be-4fb0-93a4-f9818b2b91ad`
- visit: `3b1ccedf-29c6-4d9e-9108-f11a7bcc5c5e`
- original محفوظ؛ أضيف correction entry واحد عبر AccountingEngine.
- النتيجة: customer AR=`0`، customer revenue=`0`، supplier archive=`167.84`، ولا customer canonical sale.

### أثر التقرير الشرعي
- AR Core بقي `9,181`.
- Income Statement: Revenue `9,794`، Expenses `2,274`، Net Income `7,520`.
- `historical_financial_repair` يُستبعد دلاليًا قبل reversal wording؛ القواعد canonical/expense نفسها لم تتغير.
- تقرير التنفيذ: `/app/test_reports/p0b_targeted_correction.json`.

## الزيارات المستقلة
- أضيف canonical identity لكل زيارة: `visitfinal:{visit_id}` وbusiness event `visit_finalization::{visit_id}`.
- `final_customer_total` وpayments وremaining مستقلة لكل زيارة.
- إعادة الطلب بنفس الإجمالي idempotent، واختلاف الإجمالي بعد الاعتماد يفشل 409.
- Supplier items تبقى archive-only ولا تدخل customer revenue.

## QuickPrint
- يطبع الزيارة المختارة من منتقي متعدد الزيارات.
- invoice/receipt يتطلب approved visit `final_customer_total`.
- renderer يستخدم approved final total ولا يعيد حسابه من items.
- paid context يأتي من payments الخاصة بالزيارة المختارة.

## الاختبار النهائي
- Iter349 كشف خطأ precedence واحد في تصنيف correction؛ أُصلح دون تغيير بيانات.
- Iter350 أعاد **نفس** trio فقط: backend live read-only 6/6 + isolated Visit A/B 1/1 + QuickPrint 1/1.
- **MOCKED:** Fixture معزول فقط لاختبار Visit A/B وQuickPrint؛ التحقق الحي لـP0-B كان read-only.
- التقرير: `/app/test_reports/iteration_350.json`.

## الحالة النهائية
- **FINANCIAL CORE = FROZEN**
- **LEGACY RECONCILIATION = BACKLOG**
- لا تبدأ audit أو cleanup أو historical repair إضافيًا دون اعتماد جديد صريح.