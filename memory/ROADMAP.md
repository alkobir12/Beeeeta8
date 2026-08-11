# الحالة بعد تحديث 2026-08-11

## FINANCIAL CORE — FROZEN
- P0-A وP0-B المستهدف وVisit A/B وQuickPrint final acceptance مكتملة.
- ممنوع audit/cleanup/historical repair إضافي دون اعتماد جديد.
- `LEGACY RECONCILIATION` انتقل إلى Backlog ولا يُنفذ bulk repair.

## P0-A — مكتمل ومتوقف للمراجعة
- `ACCOUNTINGENGINE_SINGLE_WRITER=PASS` وdirect/fallback active paths = 0.
- balancing plug وbackfill 43 وfinancial reset وlegacy vehicle auto-posting محظورة.
- P0-B غير مبدوء: 2,300 و167.84 والميزانية وكاترينا والمصالحة ما زالت كما هي بانتظار اعتماد مستقل.

## P0 — تعارضات التدقيق المالي المؤكدة
1. توحيد كاترينا ولوحتها على `current_vehicle_ar_total` للرقم الحالي، مع فصل ledger/history بوضوح.
2. عكس قيد المورد الخاطئ `1b91f14d...` عبر AccountingEngine فقط بعد موافقة المالك؛ الأثر `167.84` على AR/revenue.
3. جعل حفظ finalization والقيد canonical ذريًا، ثم معالجة المركبة `b885...` ذات `2,300.00` بلا `vehfinal`.
4. إزالة 8 مسارات direct journal mutation وإلزام `fallback=False` في 5 callers.

## P1 — اتساق التقارير والواجهات
1. إصلاح إشارة الميزانية بدل `abs(balance)`؛ الفجوة الحالية `908.00`.
2. إعادة بناء reconciliation حول `business_event_id/accounting_identity` بدل افتراض قيد لكل operation؛ لا تنفذ backfill القديم.
3. تطبيق `end_date/as_of` فعليًا في current AR engine.
4. منع supplierPreview من القيمة الافتراضية للإجمالي النهائي، وإزالة silent fallback/cache الأعلى في متابعة الذمم.
5. توحيد dashboard summaries مع read model المالي المركزي.

## P2 — قابلية التوسع
- نقل KPI دفتر اليومية إلى totals server-side قبل تجاوز 50 قيدًا.

## P0 مصادقة Preview
- مكتمل: دخول `مدير` و`احمد` بكلمة مرور كاملة، ورسائل خطأ مرئية، وتحويل آمن من PIN القديم إلى كلمة المرور.
- إجراء مالك موصى به: تغيير كلمة المرور المؤقتة `010101` من صفحة أمان الحساب بعد التحقق، لأنها اختيار مؤقت وضعيف نسبيًا.
- قيد منصة Preview: الحافة الخارجية تعيد CORS wildcard، بينما FastAPI الداخلي يعيد origin صريحًا وcredentials؛ same-origin login يعمل. لا تُضعف المصادقة أو تضف mock لمعالجة قيد الحافة.
- الإنتاج منفصل: أي تغيير اعتماد أو بيانات في Preview لا ينتقل إلى `https://car-repair-sys.emergent.host` إلا بإعداد/نشر إنتاجي مستقل.

## P0 مكتمل
- Supplier Exclusion: الموردون لا يغيرون AR/Revenue/Remaining ويظلون ظاهرين في ملف المركبة وحركات الموردين.
- Final Customer Total: رقم نهائي صريح مطلوب عند التسليم ومستخدم لحساب المتبقي بعد الاعتماد.

## P1 التالي
- إبقاء اختبار `/app/backend/tests/test_iter340_p0_supplier_exclusion_finalization.py` ضمن الانحدار لحماية عقد P0.
- إبقاء اختبار `/app/backend/tests/test_iter341_income_statement_filtering.py` ضمن الانحدار لحماية فلترة مصادر الإيراد.
- إبقاء اختبار `/app/backend/tests/test_iter342_income_statement_scope_model.py` ضمن الانحدار لحماية استقلال قائمة الدخل عن حالة المركبة.
- Root fix مستقبلي: إنشاء قيد canonical واحد واضح لكل حدث تجاري نهائي، مع إبقاء alignment/repair كـ audit/history فقط.
- P1 مكتمل جزئياً: اعتماد `final_customer_total` أصبح ينشئ قيد canonical idempotent للحدث النهائي. المتبقي لاحقاً: خطة تنظيف/أرشفة القيود التاريخية legacy بدون حذف أو reverse إلا بعد اعتماد المستخدم.

## P0 أمني متبقٍ خارج هذا التعديل
- تدوير أسرار Production/Preview المتأثرة: Supabase service role, JWT secret, LLM/API keys, bypass/developer approval secrets، مع خطة تحديث deployment حتى لا يتوقف النظام.
- إزالة/تنظيف أي ملفات محلية أو تاريخية تحمل أسراراً فعلية من مسارات العمل المستقبلية بعد تدويرها.
- تحسين لاحق مقترح: إضافة تبويب تفصيلي يفرق بين `حركة تشغيلية للفترة` و`حركة دفتر تاريخية` داخل دفتر اليومية.
- ربط QuickPrint والفواتير النهائية بعرض `final_customer_total` المعتمد في قالب الفاتورة النهائي.
- صفحة تحقق عامة للمستندات عبر QR/هاش/اعتمادات.

## P2 لاحقاً
- تنظيف ملفات الواجهة اليتيمة.
- AR Aging 30/60/90 وتنبيهات واتساب مستقبلية.

# ROADMAP

## P0
- لا يوجد عنصر حرج مفتوح مرتبط بطلبات المركبات/الدفعات/Smart POS الحالية.

## P1
- استخراج Customers / Vehicles / Suppliers من `server.py` إلى routers مستقلة.
- استخراج Visits / Operations / Vehicles من `routes_extended.py` إلى ملفات أصغر.
- إكمال الربط المتبقي عبر الصفحات ذات الصلة: العمليات ↔ ملف المركبة ↔ الموردين ↔ POS الذكي.
- استكمال ما تبقى من POS الذكي: دعم تدفق الإيداع البنكي ككيان مرجعي إن لزم، وتحسين ظهور مخرجات POS في الصفحات ذات الصلة.
- تحسين زمن تحميل الصفحات الثقيلة (خصوصاً الموردين والعمليات) أو إضافة loading states أكثر تقدماً عند بطء التجميع المالي.
- توحيد تمثيل ردود `GET journal entry` و`GET journal entries` بالكامل في كل المستهلكين.
- تقليل ضوضاء fetch أثناء الأتمتة/التنقل إذا استمر ظهورها في بيئات الاختبار فقط.

## P2
- إضافة OCR للمستندات المرفوعة في البوت المالي للتدقيق التلقائي للفواتير.

## Enhancement Candidates
- إضافة «حفظ كمسودة POS» أو «آخر عميل/مركبة مستخدمة» لتسريع الكاشير أكثر.
## 🧠 RRR Phase 2 — Memory Engine: قواعد الترقية المعتمدة كتابةً (2 يوليو 2026)
اعتمدها المستخدم نصاً — شرط مسبق لبناء المرحلة 2:
1. **Session → Short**: تلقائي عند نهاية الجلسة — فقط العناصر المصنفة
   (قرار، تصحيح من المستخدم، فشل أداة). الثرثرة لا تُرقّى.
2. **Short → Long**: شرطان معاً: (أ) تكرار المعلومة في 3 جلسات مختلفة
   أو تصحيح صريح من admin، و(ب) عمرها أقل من 30 يوماً.
   ما لم يُرقَّ خلال 30 يوماً يُحذف.
3. **Long → Knowledge**: اعتماد بشري فقط عبر محرك الاعتمادات —
   كاترينا ترشّح (Learning Candidate)، admin يعتمد.
   لا ترقية تلقائية لهذه الطبقة إطلاقاً (تدخل سياق كل جلسة مستقبلية).
4. **قاعدة التلوث**: أي معلومة في Knowledge تتعارض مع معلومة أحدث →
   تُعلَّم `disputed` وتُجمّد من الحقن حتى يفصل admin.
5. **سقف الحجم**: Knowledge ≤ 2k tokens محقونة.
   تجاوزه = إجبار على دمج/أرشفة قبل إضافة جديد.
- قرار معماري معتمد: المرحلة 2 تعتمد top-k retrieval انتقائي (لا حقن كامل).
- شرط Prompt Learning: prompt_version + rollback فوري لآخر نسخة معتمدة.
