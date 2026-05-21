# AutoPro Workshop Management System PRD

## Original Problem Statement
نظام إدارة ورشة سيارات متكامل يدعم اللغة العربية، مع وحدات محاسبية ومالية شاملة.

---

## Code Architecture
```
/app
├── backend
│   ├── server.py
│   ├── routes_finance.py          ← legacy→new code migration, updated _infer_account_type
│   ├── routes_extended.py         ← ACCOUNT_NAME_MAP, LEGACY_TO_NEW_CODE, new codes in JE builder
│   ├── routes_finance_bot.py
│   ├── smart_inventory_service.py ← Rakan analytics fix (items scan)
│   └── accounting_auditor.py
└── frontend
    └── src
        ├── components/Sidebar.jsx  ← UX overhaul (collapse all, scroll to group)
        └── pages/
            ├── JournalEntries.jsx  ← LEGACY_MAP for display
            ├── ComprehensiveFinancial.jsx
            ├── VehicleDetails.jsx  ← RakanLinkedPartPicker (clean)
            └── PartsDashboard.jsx
```

---

## What's Been Implemented

### 🛠️ إصلاح شامل عاجل (Theme + Runtime + Backend Recovery) — (21 May 2026)

**الأعراض المبلّغ عنها:**
- الثيم لا يتغير.
- Runtime errors (Cannot find module '@/lib/utils').
- Invalid Host header في Preview.

**الإصلاحات المنفذة:**
- تحويل `App.css` من فرض dark mode إلى CSS Theme-aware باستخدام متغيرات الثيم.
- تثبيت حزم frontend المفقودة (Radix / DnD / i18n / markdown / pdf / xlsx).
- توحيد استيرادات `@/lib/utils` داخل مكونات UI إلى مسارات ثابتة متوافقة.
- استرجاع ملفات backend الحرجة التي كانت Placeholder (من git history):
  - `server.py`
  - `models.py`
  - `supabase_service.py`

**التحقق:**
- Theme toggle: PASS (تغير فعلي من dark إلى light).
- Preview runtime overlay: PASS (اختفاء خطأ module).
- Backend APIs: `GET /api/health` = 200، `GET /api/vehicles` = 200.

**توثيق إضافي:**
- تم إنشاء تقرير مراجعة شامل لملف CSV في: `/app/memory/Problemss_review_report.md`.

### 🎨 تحسين تباين صفحة ملف المركبة (VehicleDetails) — (21 May 2026)

**طلب المستخدم:**
- الألوان ما زالت باهتة وصعبة القراءة داخل صفحة ملف المركبة.

**ما تم تنفيذه في `frontend/src/pages/VehicleDetails.jsx`:**
- رفع التباين في عناصر الزيارة (VisitCard) وإلغاء تأثيرات التمويه التي سببت مظهراً باهتاً.
- تصحيح ألوان الملخصات/الشرائح التي كانت فاتحة جداً على خلفية فاتحة (خصوصاً بطاقات الإحصاءات والنصوص الثانوية).
- تحسين وضوح: قائمة الطباعة المنسدلة، مودال مصدر الملخص المالي، مودال الماسح، وأزرار الإغلاق.
- إضافة طبقة **Contrast hardening** داخل الصفحة لمعالجة أي ألوان inline قديمة متبقية بسرعة وبشكل موحد.

**التحقق:**
- `mcp_lint_javascript` على الملف: **PASS**.
- لقطة smoke على Preview أظهرت `Invalid Host header`.
- لقطة smoke محلية أظهرت أن التطبيق لا يُبنى حالياً بسبب dependencies مفقودة في المشروع (حالة بيئية قائمة حالياً)، لذلك التحقق البصري الكامل من واجهة المركبة **محجوب مؤقتاً** حتى استقرار البناء.

### 🧩 توسيع الربط: POS الذكي ↔ العمليات + توضيح كروت القيود (13 May 2026)

**طلب المستخدم:**
- توسيع الربط بحيث لا يبقى POS الذكي معزولاً عن الصفحات المرجعية.
- جعل كروت القيود في دفتر اليومية أوضح، خصوصاً من ناحية نوع العملية وطريقة الدفع (نقدي/بنك/نقاط بيع/آجل).

**ما تم تنفيذه:**
- `SmartPOSJournal.jsx` أصبح ينشئ **Operation مرجعية** عبر `POST /api/operations` لمعظم القوالب:
  - بيع فوري
  - بيع نقدي
  - بيع بنكي/بطاقة
  - رواتب
  - صرف نقدي
  - تحصيل من عميل
  - سداد لمورد
- الاستثناء الوحيد حالياً: **إيداع بنكي** يبقى قيد يومية مباشر.
- بهذه الخطوة أصبح ما يُنشأ من POS يظهر في المسارات المرجعية عبر طبقة العمليات واليومية، وليس كقيد محاسبي فقط.

- في `routes_finance.py` تم إثراء `GET /api/finance/journal-entries` ليُرجع أيضاً:
  - `payment_method`
  - `payment_method_label_ar`
  - `payment_status`
  - `payment_status_label_ar`
- حتى القيود غير المرتبطة مباشرةً بعملية يتم استنتاج طريقة الدفع فيها من سطور القيد (`003/004/006`).

- في `JournalEntries.jsx` تم تحسين كروت القيود لتُظهر بوضوح:
  - **طريقة الدفع**
  - **حالة السداد** عند توفرها
  - **المصدر** (عملية / POS / سند قبض / يدوي / إقفال)

**التحقق:**
- `testing_agent`: `/app/test_reports/iteration_206.json`
  - Backend: **8/8 PASS**
  - Frontend: التنفيذ صحيح، مع ملاحظة شبكة متقطعة في Preview Full View وليست bug منطقية بالكود.
- لا توجد بيانات اختبارية جديدة في هذه الجولة.

### ✅ إصلاح عرض حالة السداد والرصيد داخل بطاقة العملية (13 May 2026)

**المشكلة التي أبلغ عنها المستخدم:**
- بعد تسجيل دفعة 300 على عملية إجماليها 2300 كان المستخدم يرى أن العملية تبدو مكتملة السداد أو لا يرى الرصيد المتبقي بوضوح.
- كما كان نص القيد المحاسبي ينتهي إلى: `إلى حساب الحساب` عند غياب `accountingAccountId`.

**ما تم إصلاحه:**
- في `Operations.jsx` تم تقليل stale time وتفعيل `refetchOnMount` للعمليات حتى لا تعتمد الصفحة على cache قديم مضلل.
- في `OperationCard.jsx` تمت إضافة:
  - شارة حالة سداد واضحة مثل **مدفوع جزئياً**
  - ملخص ظاهر داخل البطاقة يتضمن:
    - الحالة
    - المدفوع
    - المتبقي
  - بطاقات تفصيلية داخل العرض الموسّع لـ:
    - المدفوع
    - المتبقي
- تم تحسين fallback اسم الحساب ليظهر اسم منطقي مثل **إيرادات الخدمات** بدلاً من النص الناقص `الحساب`.

**التحقق على نفس الحالة الفعلية:**
- العملية: `99970dc5-5e16-481f-a925-65cce2d374f7`
- القيم الصحيحة الآن:
  - `paymentStatus = partial`
  - `totalPaid = 300`
  - `balance = 2000`
- `testing_agent`: `/app/test_reports/iteration_205.json`
  - Frontend visual verification: **PASS 100%**
  - لا توجد بيانات اختبارية جديدة.

### 🔄 انعكاس تحديثات ملف المركبة على العمليات (13 May 2026)

**طلب المستخدم:** أي تحديث في صفحة ملف المركبة يجب أن ينعكس على العمليات.

**ما تم تنفيذه:**
- تم إثراء `GET /api/operations` و `GET /api/operations/{id}` من بيانات المركبة الحية نفسها داخل `supabase_service.py`.
- العمليات المرتبطة بمركبة أصبحت تُرجع الآن حقولاً حية من سجل المركبة الحالي:
  - `customerName`
  - `customerPhone`
  - `vehiclePlate`
  - `vehicleBrand`
  - `vehicleModel`
- بهذا أصبح أي تعديل على ملف المركبة/العميل ينعكس في صفحة العمليات عبر القراءة الحية بدلاً من الاعتماد على بيانات قديمة مخزنة داخل العملية.
- في `OperationCard.jsx` تم تفضيل اسم العميل الحالي القادم من المركبة للعمليات المرتبطة بمركبة عندما يكون `partnerType=customer`.

**التحقق:**
- `testing_agent`: `/app/test_reports/iteration_203.json`
  - Backend: **7/7 PASS**
  - Frontend: **100% PASS**
- لا توجد بيانات اختبارية جديدة في هذه الجولة (read-only).

### 🚚 Supplier Movements + Vehicle Linked Journal Entries (13 May 2026)

**ما تم في هذه الجولة:**
- تم توسيع ربط الموردين بحيث تلتقط الصفحة الآن الحركات المرتبطة من اليومية حتى لو جاءت من قيود POS/يدوية تحمل:
  - `[PARTY:اسم المورد]`
  - `[PARTY_TYPE:supplier]`
- تم تحسين `_augment_supplier_movements_from_journal` في `server.py` لقراءة الـtokens وربط السطر المورد الصحيح بدلاً من الاعتماد فقط على اسم الحساب.

- داخل `VehicleDetails.jsx` أضفت لوحة **«قيود دفتر اليومية المرتبطة»** تعرض القيود المرتبطة بالمركبة/العميل/الزيارة عبر:
  - `reference_id` الخاص بالزيارة
  - أو tokens مثل `[VEHICLE_REF:...]` و`[PARTY:...]`
- هذا يجعل قيود POS الذكي و`visit_receipt_voucher` مرئية مباشرة داخل ملف المركبة.

- تم أيضاً تحسين حالة التحميل في صفحة الموردين بإظهار رسالة أوضح أثناء احتساب الأرصدة والحركات.

**إصلاح إضافي خرج من الاختبار:**
- تم تثبيت regex parsing في `extractJournalTag` داخل `VehicleDetails.jsx` حتى تظهر القيود المرتبطة بشكل صحيح بدون كسر الصفحة.

**التحقق:**
- `testing_agent`: `/app/test_reports/iteration_202.json`
  - Backend: **14/14 PASS**
  - Frontend: **100% PASS**
- `auto_frontend_testing_agent`: **PASS**
- `deep_testing_backend_v2`: **PASS**
- لا توجد بيانات اختبارية جديدة أُنشئت في هذه الجولة.

### 🔗 Payments ↔ Operations Sync (12 May 2026)

**نطاق هذه الجولة (حسب اختيار المستخدم):** البدء أولاً بربط **الدفعات والعمليات**.

**ما تم تنفيذه:**
- تم تحديث طبقة قراءة العمليات في `supabase_service.py` بحيث تستمد من الزيارة المرتبطة (`visit_id`) البيانات التالية مباشرة من `visit.notes`:
  - `paymentMethod`
  - `paymentStatus`
  - `paymentAmount`
  - `totalPaid`
  - `advancePaid`
  - `balance`
- هذا يعني أن العملية المرتبطة بالمركبة تتحدث تلقائياً عند تغيير دفعات الزيارة من ملف المركبة، حتى لو كان جدول `operations` لا يملك كل الأعمدة المخزنة فعلياً في بعض البيئات.
- `GET /api/operations` و `GET /api/operations/{id}` أصبحا يعكسان حالة السداد الحية للزيارة المرتبطة.

**الأثر الوظيفي:**
- إذا كان إجمالي العملية 100 وتم تسجيل دفعة 50 من ملف المركبة:
  - تنعكس الدفعة في الزيارة
  - يظهر سند قبض محاسبي في دفتر اليومية (`visit_receipt_voucher`)
  - تتحدث العملية المرتبطة في صفحة العمليات بحالة السداد والرصيد

**التحقق:**
- `testing_agent`: `/app/test_reports/iteration_201.json`
  - Backend: **12/12 PASS**
  - Frontend: **100% PASS**
- `auto_frontend_testing_agent`: **PASS** (بدون إنشاء بيانات جديدة)
- `deep_testing_backend_v2`: **PASS** (read-only)

### 🧾 Vehicle Files + Smart POS Accounts + Visit Receipt Vouchers + Test Data Cleanup (12 May 2026)

**1. إصلاح حفظ رقم ملف المركبة / العميل**
- تم توسيع `VehicleUpdate` ليقبل حقول المركبة الأساسية + `customerFileNumber`.
- تم تحديث `PUT /api/vehicles/{vehicle_id}` ليحفظ:
  - `fileNumber`
  - `customerFileNumber`
- في Supabase/Mongo/Memory يعود الرد الآن بالبيانات المحدثة مع إلحاق `customerFileNumber` بشكل صحيح.
- واجهة `VehicleDetails.jsx` أصبحت تدعم تعديل:
  - رقم ملف المركبة
  - رقم ملف العميل المرتبط

**2. تصحيح ربط الحسابات في Smart POS**
- تم إصلاح mapping الحسابات في `SmartPOSJournal.jsx` بحيث:
  - **الرواتب** → `036 رواتب إدارية`
  - **البيع** → حساب إيراد خدمات صحيح (`025/026/027` حسب المتاح)
  - **وسائل الدفع** → `003 نقد` / `004 بنك` / `006 نقاط بيع`
- تمت إزالة الاعتماد الخاطئ على الأكواد التي كانت تشير في هذه البيئة إلى حسابات غير مناسبة مثل `037 إيجار المركز`.

**3. الحساب الافتراضي حسب نوع العملية في صفحة Operations**
- `Operations.jsx` يختار الآن الحساب الافتراضي المناسب بحسب نوع العملية:
  - sale → revenue
  - payment/settlement customer → `005 العملاء`
  - payment supplier → `2101 الموردون`
  - purchase/expense → حساب مصروف مناسب

**4. سندات القبض لدفعات الزيارة (دفعة مقدمة / تحت الحساب)**
- عند حفظ دفعات الزيارة في `VehicleDetails.jsx` يتم الآن:
  - احتسابها ضمن `payments`
  - إنشاء قيد محاسبي فعلي في `journal_entries`
  - المصدر: `visit_receipt_voucher`
  - الربط عبر `reference_id = visit_id`
  - وصف القيد يتضمن tokens:
    - `[PARTY:...]`
    - `[PARTY_TYPE:customer]`
    - `[VEHICLE_REF:...]`
    - `[VISIT:...]`
- ربط الحسابات في سند القبض:
  - مدين: وسيلة التحصيل (`003/004/006`)
  - دائن: `005 العملاء`

**5. تحسين Endpoint القيد المفرد**
- `GET /api/finance/journal-entries/{entry_id}` أصبح يعيد الحقول الأساسية أيضاً على المستوى الأعلى، مع الإبقاء على `data` للتوافق العكسي.

**6. تنظيف البيانات الاختبارية**
- تم حذف بيانات الاختبار التي أنشأتها جولات الاختبار الأخيرة، بما يشمل:
  - مركبات تجريبية `TEST-* / UPD-* / CUST-*`
  - قيود يومية بوصف `TEST_*`
  - إزالة دفعة اختبارية إضافية وقيدها المرتبط
- تم إرجاع أرقام الملفات التجريبية على المركبة الحقيقية المستخدمة للفحص السريع.

**التحقق والاختبار:**
- `testing_agent`: `/app/test_reports/iteration_200.json`
  - Backend: **13/14 PASS**
  - Frontend: **100% PASS**
  - الملاحظة المنخفضة الوحيدة (شكل رد endpoint القيد المفرد) تم إصلاحها.
- `auto_frontend_testing_agent`: **PASS**
- `deep_testing_backend_v2`: **PASS**

### 💳 Smart POS Journal — User-requested completion (11 May 2026)

**ملخص التنفيذ النهائي لطلب المستخدم الأخير:**
- إعادة بناء `SmartPOSJournal.jsx` كواجهة POS موحدة بدلاً من فصل «سلة كاشير» — تم **دمج السلة داخل قسم البنود** نفسه.
- إضافة **8 قوالب جاهزة** داخل شاشة واحدة:
  - ⚡ بيع فوري
  - 💵 بيع نقدي
  - 💳 بيع بنكي/بطاقة
  - 👷 رواتب
  - 🧾 صرف نقدي
  - 🤝 تحصيل من عميل
  - 📦 سداد لمورد
  - 🏧 إيداع بنكي
- إضافة الحقول المطلوبة من المستخدم داخل الـPOS:
  - **العميل**
  - **المركبة**
  - **البنود**
- ربط lookup فعلي مع APIs:
  - `GET /api/customers`
  - `GET /api/suppliers`
  - `GET /api/vehicles`
  - `GET /api/parts`
  - `GET /api/services`
- دعم احتساب الإجمالي تلقائياً من البنود مع الإبقاء على الإدخال اليدوي للمبلغ عند الحاجة.
- الحفظ يرسل قيداً متوازناً إلى `POST /api/finance/journal-entries` مع tokens داخل الوصف:
  - `[PARTY:...]`
  - `[PARTY_TYPE:...]`
  - `[VEHICLE_REF:...]`
- شريط «آخر القيود» ما زال يدعم **نسخ القيد** لإعادة الاستخدام بسرعة.
- تحصين `JournalEntries.jsx` باستخدام `AbortController` لتقليل ضوضاء fetch عند التنقل/الإلغاء أثناء التحميل.

**التحقق والاختبار:**
- `testing_agent`: `/app/test_reports/iteration_199.json`
  - Frontend: **100% PASS**
  - Backend: **100% PASS**
  - تم التحقق من جميع القوالب، ومن دمج سلة الكاشير، ومن حفظ قيود متوازنة فعلياً.
- `auto_frontend_testing_agent`: **PASS كامل**
  - تم التحقق بصرياً من القوالب، الحقول الشرطية، البنود، وحفظ البيع الفوري مع toast نجاح.
- `deep_testing_backend_v2`: **7/7 PASS**
  - تم التحقق من قوالب: instant_sale / salary / collect_customer / pay_supplier
  - وتم التحقق من رفض القيد غير المتوازن كما يجب.

**ملاحظات هندسية:**
- `SmartPOSJournal.jsx` أصبح الآن المرجع الأساسي لتجربة POS داخل `/accounting/journal-entries`.
- `JournalEntries.jsx` ما زال يحتفظ بمفتاح التبديل بين **POS الذكي** و**العرض الكامل**.
- تمت إضافة ملفات ذاكرة مساندة:
  - `/app/memory/CHANGELOG.md`
  - `/app/memory/ROADMAP.md`

### 💳 Smart POS Journal + Recent Pages + Duplicate Customer Alert (11 Feb 2026)

**1. 💳 POS الذكي لدفتر اليومية (`SmartPOSJournal.jsx`, 586 سطر)**
- **مفتاح تبديل أعلى الصفحة** (محفوظ في localStorage): POS الذكي ↔ العرض الكامل.
- **وضع القوالب** (6 قوالب جاهزة بألوان مختلفة):
  - 💵 بيع نقدي (003 ↔ 042)
  - 💳 بيع بنكي/بطاقة (004 ↔ 042)
  - 🧾 صرف نقدي (035 ↔ 003)
  - 🤝 تحصيل من عميل (003 ↔ 005)
  - 📦 سداد لمورد (2101 ↔ 003)
  - 🏧 إيداع بنكي (004 ↔ 003)
- **Numpad 4×4**: أرقام + C + ⌫ + . + 00 + 000 + OK (الحفظ).
- **وضع السلة (Cashier)**: إضافة خدمات/قطع متعددة، حساب الإجمالي، تحديد طريقة الدفع (cash/bank/pos)، حفظ بقيد متوازن واحد.
- **شريط جانبي «آخر القيود»**: 5 قيود مع زر «نسخ» لإعادة الاستخدام.
- يستدعي POST /api/finance/journal-entries — الجدار يضمن التوازن.

**2. 📜 السايدبار: أحدث الصفحات (الأعلى)**
- Hook جديد `useRecentPagesTracker` يلتقط التنقل عبر `useLocation` ويخزّن آخر 5 صفحات في localStorage (`recentPages.v1`).
- قسم بأعلى السايدبار يعرض القائمة مع labels عربية + emojis + زر «مسح».
- يدعم 18 مسار معروف بأسماء عربية friendly، fallback لأي مسار آخر.

**3. 🚨 تنبيه العميل المتكرر في «استقبال مركبة»**
- يحسب `duplicateCustomerInfo` بناءً على `customerDirectory` و `vehicleSearchIndex` (بحث بالاسم/الهاتف).
- يظهر `new-vehicle-duplicate-customer-alert` بطاقة كهرمانية inline **فقط عندما** يكون لدى العميل **مركبة واحدة** سابقة (يُستثنى العملاء بـ ≥2 مركبات).
- يعرض اسم العميل + عدد المركبات + أرقام اللوحات (حتى 5).

**Verification (`/app/test_reports/iteration_198.json`)**
- Backend: **100%** — جدار الحماية 100% balance health، 70/70 قيد، اختبار POS save end-to-end ناجح (entries grew 67→69 via testing).
- Frontend: **95%** — كل التطبيقات تعمل + bug حرج تم اكتشافه وإصلاحه (`onSaved={() => fetchJournalEntries()}` بدل `fetchEntries`).



**🐛 المشكلة المُكتشفة (من قبل المستخدم)**: كرت صافي الدخل يعرض أرقاماً سالبة خاطئة بعد الإقفال:
- Revenue: -23,775 ر.س ❌
- Net Income card top: +23,539 ❌ (علامة معكوسة مقابل detail)
- السبب: قيود `period_close` كانت تُحتسب ضمن إيراد/مصروف، فتطرح من نشاط فترة الفلتر.

**🔧 الإصلاح المحاسبي الصحيح**
- `income_statement` يستثني الآن `source="period_close"` من حساب الإيراد/المصروف (لأنها تحويلات للأرباح المحتجزة، ليست حركة فعلية).
- الأرقام الآن **موجبة وصحيحة**: revenue=35,791، expenses=1,836، net=33,955، margin=94.9%.

**🆕 ميزات إضافية**
- **Endpoint جديد**: `GET /api/finance/period-close/last?workshop_id=...` يُرجع آخر قيد إقفال للورشة.
- **Preset جديد «بعد آخر إقفال»** في شريط الفترات: يقفز تلقائياً إلى `last_close_date + 1 day`. معطّل إذا لا يوجد إقفال سابق.
- **شارة «🧾 آخر إقفال: YYYY-MM-DD»** بجوار الـ presets — مرجع بصري دائم لتاريخ الإقفال الفعّال.

**Verification (`/app/test_reports/iteration_197.json`)**
- Backend pytest: **5/5 PASS** — Revenue موجب، Expenses موجب، Net موجب على نافذة كل الفترة + نافذة 30 يوم.
- Frontend: **100%** — 10 testids + preset جديد + badge + قيم موجبة بصرية.
- ⚡ المسار الـ idempotent: 1.03 ثانية (من 26 ثانية في iter196 → **25× أسرع**).



**1. POST /api/finance/period-close — قيد إقفال محاسبي صحيح**
- يصفّر أرصدة الإيرادات (debit) والمصروفات (credit) إلى **الحساب 023 (أرباح محتجزة)**.
- متوازن دوماً (مدين = دائن) — يمر عبر `Double-Entry Firewall`.
- **Idempotency**: فحص مبكّر يمنع إنشاء قيد إقفال مكرر لنفس التاريخ. الإجابة الـ idempotent تنتهي خلال **~1.8 ثانية** (مقابل 26 ثانية قبل التحسين).
- يُحدّث `balance=0` لكل حساب إيراد/مصروف ويُضيف `net_income` إلى رصيد 023.
- المُحاسبة الذكية: `income_statement` يضم قيود `period_close` في الحساب فيتقاصّ الإيراد/المصروف إلى صفر طبيعياً.

**2. تحسينات لوحة المؤشرات المالية**
- **شريط أزرار سريعة للفترات**: اليوم، ٧ أيام، ٣٠ يوم، ٩٠ يوم، منذ بداية السنة، كل الفترة + مؤشر مخصص.
- **زر «إقفال الفترة»** بلون كهرماني + dialog تأكيد بـ 5 نقاط تفصيلية:
  - تاريخ الإقفال
  - قيد متوازن واحد
  - رفض تلقائي من الجدار
  - الأرصدة → 023
  - صافي الدخل = 0 بعد الإقفال
- **3 حالات للنتيجة** (مفصولة بـ data-testid مستقلة):
  - `financial-close-period-success` (أخضر): closed=true، تفاصيل المبلغ المُحوَّل.
  - `financial-close-period-already-closed` (كهرماني): closed=false مع ID القيد السابق.
  - `financial-close-period-error` (أحمر): على فشل الـ HTTP.
- **بطاقات أنظف** (`ExpandableMetricCard`):
  - قيمة كبيرة `text-3xl lg:text-4xl` بدلاً من `2xl`.
  - شريط لون gradient في الأعلى + هالة decorative في الزاوية.
  - chips مصغّرة (حد أقصى 3) مع علامة `+N` عند الزيادة.

**Verification (`/app/test_reports/iteration_196.json` + post-fix)**
- Backend pytest: **5/5 PASS** + اللاتنسي **26s → 1.8s** (14× أسرع).
- Frontend: 12/12 testids + 3 states منفصلة + dialog flow كامل.
- ✅ قبل الإقفال: Revenue=35,691، Expenses=1,836، Net=33,855
- ✅ بعد الإقفال: Revenue=0، Expenses=0، Net=0، 23 (أرباح محتجزة) +=33,855
- ✅ جدار الحماية: 66 قيد متوازن، 100% health.



**1. Auditor Integration (`/api/finance/audit-system`)**
- New method `AccountingSystemAuditor.check_firewall_health(firewall_data)`:
  - **Critical**: unbalanced entries in DB > 0 OR drift > threshold.
  - **Warning**: lifetime_rejections ≥ 20 OR missing COGS despite activity.
  - Emits structured `status`/`issues`/`warnings`/`metrics` and appends to `corrections_needed`.
- Endpoint `/api/finance/audit-system` now fetches firewall status live and feeds it to the auditor.
- Audit response includes `data.details.firewall_check` with full metrics.

**2. Financial Assistant Integration (`/api/finance-bot/chat`)**
- New helper `build_firewall_context(workshop_id)` builds a live snapshot string.
- Context auto-injected before every LLM call (no client opt-in needed).
- `FINANCE_SYSTEM_PROMPT` updated with explicit firewall awareness instructions.

**3. Firewall Panel UX Upgrades**
- **Quick Actions bar**: تشغيل تدقيق المحاسبة، فتح المساعد المالي، تصدير CSV، نسخ تقرير الحالة.
- **Settings panel** (localStorage-persisted): عتبة تنبيه الرفضيات، حد سلامة التوازن (٪)، فاصل التحديث (ث)، تفعيل التنبيهات.
- **Toast alerts**: تُظهر تلقائياً عند تجاوز عتبات المستخدم (auto-dismiss بعد 6ث).
- **Audit result card**: نتيجة التدقيق inline مع health_score + firewall_check + issues/warnings.
- **Live pulse indicator**: نقطة خضراء تنبض مع كل refresh.
- **Rejection detail modal**: النقر على أي رفض يفتح JSON كامل + زر نسخ.
- **Configurable refresh interval** بدل 15ث ثابتة.

**Verification (`/app/test_reports/iteration_194.json`)**
- Backend: **100% (3/3 pytest PASS)** — `check_firewall_health` + bot context + status endpoint.
- Frontend: **100% (17/17 testids + جميع التدفقات تعمل)**.
- **0 critical / 0 minor issues**.



**Phase 1 — Database Purge (Supabase)**
- Deleted **9 Rakan accounts** (043, 044, 048, 053-058, 21010001) + 1 part + 1 operation.
- **Created NEW account `0421`** = «تكلفة قطع الورشة» (expense) — mirror of `042` (revenue).
- Audit + purge scripts at `/app/backend/scripts/rakan_audit.py` & `rakan_purge.py` & `rakan_purge_phase1b.py`.

**Phase 2 — Backend Code Neutralization**
- `routes_smart_inventory.py`: Removed `/api/inventory/rakan-analytics` endpoint (returns 404 now).
- `smart_inventory_service.py`: All `_is_rakan_*` helpers now return `False`; `get_rakan_analytics()` returns a stub `{removed: True}`.
- `routes_finance.py`: `_is_rakan_account_code`, `_is_rakan_journal_entry`, `_is_rakan_operation_row` all return `False`.
- `routes_extended.py`: Same — Rakan helpers neutered. `OPERATION_KIND` mapper redirects `RAKAN_PARTS_OPERATION` → `WORKSHOP_OPERATION`.
- **COGS routing changed** from `030 (تكلفة الخدمات)` → `0421 (تكلفة قطع الورشة)` (verified end-to-end via real operation test).

**Phase 3 — Frontend Radical Removal**
- **Deleted entirely**: `RakanPriceTimelinePanel.jsx`, `RakanExpenseTrackingPanel.jsx`.
- **PartsDashboard.jsx**: Rakan tab + state + fetches all deleted (1072→715 lines, -33%). Now uses NEW `WORKSHOP_ACCOUNT_TARGETS` with 3 cards: workshop-parts-revenue (042), workshop-parts-cost (0421), engine-repair.
- **Operations.jsx**: Removed Rakan tab buttons, credit-reminder line, validation messages, empty-state text. `OPERATION_KIND_LABELS/META` no longer contain Rakan.
- **PartsInventory.jsx**: `loadBusinessAccounts` no longer auto-creates a Rakan biz account.
- **VehicleDetails.jsx**: `RakanLinkedPartPicker` returns `null` (never renders).
- **UnifiedBotWidget.jsx**: Removed `rakanRev` from finContext + SPECIAL_ACCOUNTS no longer lists 043/044/053.

**Phase 4 — Test Cleanup**
- Deleted 7 Rakan-specific test files: `test_rakan_5000_routing.py`, `test_rakan_operations.py`, `test_full_operations.py`, `test_parts_operations.py`, `test_reset_totals.py`, `test_smart_inventory.py`, `test_operation_kinds_validation.py`.

**Phase 5 — server.py Continued Refactor**
- Extracted Services CRUD → `routes_services.py` (89 lines, -69 from server.py).
- Extracted Parts GET/POST/PUT → `routes_parts.py` (98 lines, -81 from server.py).
- `server.py`: **3,418 → 3,219 lines** (cumulative -199, -5.8%).

**Verification (`/app/test_reports/iteration_193.json`):**
- Backend: **100% (20/20 pytest PASS)** at `/app/backend/tests/test_rakan_removal_iter193.py`.
- Frontend smoke: PartsDashboard renders 3 workshop cards only (no Rakan), Operations has no Rakan tabs/reminders, Firewall + Journal Entries pages clean.
- COGS routing **verified end-to-end** via real operation: account 0421 (debit) + 1105 (credit), perfectly balanced.
- Firewall: 100% balance health, 0 unbalanced entries (no historical data corrupted).
- 0 Rakan accounts remain in chart of accounts.



**Goal:** تقسيم `routes_extended.py` و `server.py` إلى Routers أصغر دون كسر أي شيء.

**النتائج:**
| الملف | قبل | بعد | الفرق |
|---|---|---|---|
| `routes_extended.py` | 8,639 | **5,093** | **-3,546 (-41%)** |
| `server.py` | 3,418 | **3,364** | -54 |

**الملفات الجديدة (5 routers + 2 shared modules):**
- `app_state.py` (87 سطر) — حالة مشتركة (`db`, `DB_PROVIDER`, `supabase_service`, `mem_read`, `mem_write`).
- `mem_store.py` (44 سطر) — helpers لـ `_mem_read/_mem_write` بدون تكرار.
- `routes_workshop_config.py` (295 سطر) — Settings, Profile, Logo Upload, Auth OTP.
- `routes_approvals.py` (547 سطر) — Approval CRUD, public view, SSE stream, Notifications, Approval logs.
- `routes_accounts_extended.py` (2,003 سطر) — Chart of Accounts بكاملها (list, tree, status, transactions, sparkline, usage, reconciliation, export, init-defaults).
- `routes_templates_extended.py` (674 سطر) — Print Templates + Invoice Designer + xlsx + Public Agent Chat (+ **إصلاح import مفقود** لـ `LlmChat`).
- `routes_technicians.py` (68 سطر) — Technicians CRUD مع pattern `app_state` المشترك.

**Verification (`/app/test_reports/iteration_192.json`):**
- Backend: **100% (20/20 pytest assertions PASS)**.
- Frontend smoke: **100% (3/3 pages — home, /accounting/firewall, /accounting/journal-entries)**. 0 console errors.
- **0 regressions**. كل مسارات الـ API احتفظت بسلوكها الأصلي.
- مجموعة اختبار regression محفوظة في `/app/backend/tests/test_refactor_regression_iter192.py` للاستخدام المستقبلي.

### 🧹 Test Data Cleanup + 🧩 Templates Router Extraction (11 Feb 2026)

**Cleanup:**
- اكتشاف الجداول الفعلية في Supabase (suppliers غير موجود — مدمج مع customers/business_accounts).
- حذف **16 سجل اختبار** نظيف عبر `/app/backend/scripts/cleanup_test_data_feb2026.py`:
  - 15 قيد يومية (TEST-PRECISION × 10, TEST-SALE × 1, DEMO_FIREWALL × 4)
  - 1 عملية شراء تجريبية (DEMO-IDEMP)
- ✅ post-cleanup: journal_entries 78→63، operations 70→69، balance health 100%.

**Refactoring — Templates Domain Extraction:**
- Extracted lines 7999-8640 of `routes_extended.py` into new module `routes_templates_extended.py`.
- Moved domains (~640 سطر):
  - `/api/templates` GET/POST/DELETE + `/templates/{id}/make-default` + `/templates/{id}/apply-to-all`
  - `/api/print/render`, `/api/print/resolve-template`, `/api/print/invoice-xlsx`
  - `/api/invoice-templates` (GET list/single, POST create-blank, PUT, DELETE soft, design, save-json, save-named, auto-save, update-mapping, make-default)
  - `/api/public-agent/chat` (+ **fixed** missing `LlmChat`/`UserMessage` import using local lazy import)
- Wired in `server.py` via `templates_extended_router` + `set_db_templates_extended(db)`.
- **No URL path changes** — fully backwards-compatible.
- `routes_extended.py`: 8,639 → **7,998 lines** (-7.4%, -641 lines).
- New file `routes_templates_extended.py`: **670 lines** (clean & self-contained).

**Verification:**
- Backend restart: ✅ all routers loaded.
- Smoke test (curl): `/api/templates`, `/api/invoice-templates`, `/api/print/render`, `/api/firewall/status`, `/api/operations`, `/api/accounts`, `/api/vehicles`, `/api/finance/reports/trial-balance` → all HTTP 200.
- Pre-existing 500s (`/api/coa/tree`, `/api/print/resolve-template` in non-mongo path) are **not regressions** — they were broken in master before the refactor.



### 🛡️ Accounting Firewall Dashboard (11 Feb 2026)

**طلب المستخدم:** بناء لوحة جدار حماية المحاسبة لعرض حالة الحماية لحظياً.

**ما تم تنفيذه:**

1. **Backend**
   - ملف جديد `firewall_state.py` (rolling buffer in-memory مع 3 أنواع أحداث: unbalanced_rejection, idempotency_hit, cogs_generated).
   - ملف جديد `routes_firewall.py` — Endpoint:
     - `GET /api/firewall/status?workshop_id=...&recent_limit=20`
     - يحلل جميع قيود `journal_entries` ويُعيد:
       - `summary` (total/balanced/unbalanced/cogs/idempotency counters + balance_health_percent)
       - `drift` (max/avg/threshold)
       - `recent_rejections`, `recent_idempotency_hits`, `recent_cogs_events`
       - `recent_cogs_entries`, `unbalanced_entries_in_db`
   - **Hooks جديدة:**
     - `routes_finance.py` يستدعي `firewall_state.log_event("unbalanced_rejection", ...)` قبل رفع 400 الخاص بالقيد غير المتوازن.
     - `routes_extended.py` يستدعي `firewall_state.log_event("idempotency_hit", ...)` عند رصد عملية مكررة.
     - `routes_extended.py` يستدعي `firewall_state.log_event("cogs_generated", ...)` بعد توليد قيد COGS تلقائياً.

2. **Frontend**
   - صفحة جديدة `/accounting/firewall` (`FirewallPanel.jsx`) بأسلوب Liquid:
     - 5 بطاقات إحصائيات: سلامة التوازن، رفضيات الجلسة، ضربات منع التكرار، قيود COGS، أقصى انحراف.
     - 4 لوحات تفصيلية: آخر القيود المرفوضة، ضربات منع التكرار، قيود COGS الأخيرة، قيود غير متوازنة تسربت إلى DB (يجب 0).
     - زر **عرض تجريبي للحماية** (`firewall-run-demo-button`) ينفّذ live demo: محاولة قيد غير متوازن (يُرفض) + قيد متوازن (يُقبل) ثم يُحدث اللوحة.
     - تحديث تلقائي كل 15 ثانية + زر تحديث يدوي.
     - شريط حالة (`firewall-health-badge`) يلون السلامة (أخضر/أحمر).
     - ملاحظة توضيحية أن العدادات لحظية لهذه الجلسة.
   - رابط في الـ Sidebar داخل قسم "💰 المالية والمحاسبة": **🛡️ جدار حماية المحاسبة**.
   - مسار جديد في `App.js`: `accounting/firewall → <FirewallPanel/>`.

**التحقق:**
- Backend curl tests: ✅ Unbalanced 100/50 مرفوض، Balanced 100/100 مقبول، idempotency تعيد نفس ID.
- Frontend screenshot: ✅ كل البطاقات والـ panels تظهر مع البيانات الحقيقية.
- Testing agent (`/app/test_reports/iteration_190_firewall_panel.json`):
  - Frontend: **100% (14/14 testids + demo + reload + sidebar)**
  - Backend: **3/4 PASS** (idempotency via /api/operations تخطّت بسبب اشتراط مورد — تم اختبارها يدوياً عبر curl وعملت).
  - **0 blocking issues**.



### Accounting Audit Hardening (11 May 2026)

**Based on user-requested 5-point accounting audit plan, implemented and verified:**

1. **Double-Entry Firewall (Backend Enforcement)**
   - Updated `POST /api/finance/journal-entries` in `routes_finance.py`.
   - Added strict line normalization and balance validation.
   - Unbalanced entries are now rejected with HTTP 400 and clear Arabic detail.

2. **Idempotency Guard for Operations**
   - Updated `create_operation` in `routes_extended.py`.
   - Added transaction/reference key extraction (`transaction_id`, `reference`, `referenceId`, etc.).
   - Added `[IDEMP:<key>]` note tagging and lookup to return existing operation instead of creating duplicates.

3. **Inventory + COGS Auto-Posting (Supabase Path)**
   - Added automatic parts quantity decrement/increment for operations with `itemType=part` in Supabase mode.
   - Added auto-generated COGS journal entry (`source=operation_cogs`):
     - Dr `030` (تكلفة الخدمات)
     - Cr `1105` (مخزون قطع غيار)

4. **Finance Cache Invalidation After Operation Journals**
   - Added safe finance cache invalidation after posting operation journals/COGS to ensure immediate visibility in trial balance.

**Verification Reports:**
- Initial audit (before fixes): `/app/test_reports/iteration_187_accounting_audit.json` (2 pass / 3 fail)
- Post-fix audit: `/app/test_reports/iteration_189_accounting_audit_after_fixes.json` (**5 pass / 0 fail**)

**Verified outcomes after fixes:**
- ✅ Real-time ledger linkage (003/027/042) reflects immediately.
- ✅ Unbalanced entry rejection works.
- ✅ Part quantity changes + COGS entry generation works.
- ✅ Idempotency returns same operation ID for repeated same reference.
- ✅ Decimal precision scenario (0.55) remains balanced with zero drift.

### AI Financial Page → Assistant-Only Mode (11 May 2026)

**طلب المستخدم:** تحويل صفحة `/ai-financial` إلى صفحة مساعد فقط، وإزالة البيانات/القوائم المالية الجذرية لتفادي أخطاء الربط المالي.

**ما تم تنفيذه في `AIFinancial.jsx`:**
1. تفعيل وضع `assistantOnlyMode = true` مع **early return** لواجهة مساعد فقط.
2. تعطيل استدعاءات البيانات المالية الجذرية في الصفحة (income/balance/trial/accounts/vehicle) عبر حراسة `useEffect`.
3. إظهار واجهة واضحة تتضمن:
   - `data-testid="ai-financial-assistant-only-page"`
   - `data-testid="assistant-only-description"`
   - `data-testid="assistant-only-workshop-panel"`
4. الاعتماد على `WorkshopAIBot` فقط داخل الصفحة، مع رسالة توجيه أن القوائم الرسمية في:
   - `/accounting/comprehensive`

**التحقق:**
- Frontend testing agent: ✅ PASS كامل
  - العناصر الجديدة ظهرت بنجاح
  - العناصر المالية القديمة اختفت (مثل `trial-balance-count` و`unified-assistant-tab-finance`)
  - الصفحة تعمل كمساعد فقط بدون عرض قوائم مالية.

### Centralizing Financial Statements (11 May 2026)

**طلب المستخدم:** إزالة القوائم المالية من صفحة المساعد المالي (تبويب التحليل المالي)، واعتماد القوائم الرئيسية فقط في صفحة القوائم المالية بالقسم المالي.

**ما تم تنفيذه في `AIFinancial.jsx`:**
1. إزالة قسم قائمة **ميزان المراجعة التفصيلي** من تبويب التحليل المالي.
2. إضافة بطاقة توضيحية تؤكد أن القوائم المالية أصبحت مركزية في صفحة القسم المالي.
3. إضافة زر مباشر للانتقال إلى صفحة القوائم المالية:
   - `data-testid="assistant-go-financial-statements-button"`
   - الوجهة: `/accounting/comprehensive`
4. إضافة معرف اختبار للرسالة التوضيحية:
   - `data-testid="assistant-financial-statements-centralized-note"`

**التحقق:**
- Frontend test agent: ✅ جميع النقاط PASS
  - ظهور الرسالة التوضيحية
  - ظهور زر الانتقال
  - اختفاء `trial-balance-count`
  - نجاح الانتقال إلى `/accounting/comprehensive`

### P0 Fix — Journal Entries Crash After Data Cleanup (11 May 2026)

**المشكلة:** انهيار React في صفحة دفتر اليومية `/accounting/journal-entries` بعد حذف بيانات اختبار.

**الإصلاح المنفذ:**
1. **`JournalEntries.jsx`**
   - إضافة طبقة `null-safe` عند قراءة API (تطبيع `entries` و `lines` قبل الاستخدام).
   - منع أي crash ناتج عن عناصر `null` أو هياكل بيانات ناقصة.
   - تحصين الطباعة وتفاصيل القيد ضد `lines` غير الصالحة.
2. **`SmartAccountSelect.jsx`**
   - تطبيع آمن للحسابات الواردة من `allAccounts` أو API.
   - منع crash عند وجود عناصر حسابات ناقصة/فارغة.

**التحقق والاختبار:**
- Lint: ✅ بدون أخطاء لملفي الواجهة المعدلين.
- Testing Agent: `/app/test_reports/iteration_186.json`
  - Frontend: **100% PASS**
  - لا `Script error` ولا `handleError` في Console.
  - فتح المودال + SmartAccountSelect يعملان بدون انهيار.

### Preview Visibility + Smart Accounting UI Verification (10 May 2026)

**ما تم في هذه الجولة:**
1. **ربط SmartAccountSelect فعلياً داخل صفحة العمليات** (`Operations.jsx`):
   - استبدال حقل الحساب التقليدي بمكوّن `SmartAccountSelect`.
   - إظهار تلميح واضح بأن آخر 3 حسابات مستخدمة تُعرض أولاً.
   - تم التحقق بصرياً وبتقرير اختبار أن العنصر يظهر في تبويب **الربط**.

2. **تحسين منطق خيارات الدفع في `ConfirmPaymentDialog.jsx`:**
   - طرق الدفع الأساسية أصبحت: `bank`, `cash`, `pos`.
   - خيار `supplier_balance` يظهر فقط عند توفر شرطين معًا:
     - `allowSupplierBalance=true`
     - `supplierId` موجود.

3. **ربط سداد رصيد المورد من زيارة المركبة** (`VehicleDetails.jsx`):
   - استخراج الموردين من بنود الزيارة (itemType='supplier').
   - تفعيل السداد من رصيد المورد فقط عند وجود **مورد واحد** في الزيارة.
   - عند تعدد الموردين، يظهر تنبيه واجهة يوضح تعطيل الخيار حتى لا يحدث التباس.
   - إضافة استدعاء backend إلى:
     - `POST /api/smart-accounting/supplier-balance-payment`

4. **اختبار واجهة شامل عبر testing agent:**
   - التقرير: `/app/test_reports/iteration_168.json`
   - النتيجة: **Frontend 100% PASS**
   - لا توجد Bugs أو Action Items مفتوحة في الجولة الحالية.

### Journal Entry Create Form: SmartAccountSelect + Context Filtering (10 May 2026)

**تحديثات صفحة إنشاء القيد (`JournalEntries.jsx`):**
1. استبدال اختيار الحساب التقليدي داخل بنود القيد بمكوّن `SmartAccountSelect` لكل سطر.
2. تطبيق فلترة ذكية للحسابات حسب:
   - نوع الحركة (`sale` / `purchase` / `expense`)
   - جهة السطر (`debit` أو `credit`)
3. إضافة حقل طرف ديناميكي `entry-party-name-input`:
   - عند `sale` يظهر كـ **العميل**
   - عند `purchase/expense` يظهر كـ **المورد**
4. عند الحفظ يتم تطبيع الوصف وإضافة وسوم الطرف:
   - `[PARTY:...]`
   - `[PARTY_TYPE:customer|supplier|open]`

**الاختبار:**
- تقرير الاختبار: `/app/test_reports/iteration_169.json`
- النتيجة: **Frontend 100% PASS**
- جميع data-testid المطلوبة موجودة وتعمل.

### SmartAccountSelect Upgrade (Based on user-provided script) — 10 May 2026

**تمت ترقية المكوّن `SmartAccountSelect.jsx` ليشمل المنطق الذكي المتقدم:**
1. دعم Props أوسع ومتوافق مع القديم:
   - `entryType/lineType/description`
   - مع الإبقاء على `operationType/fieldKey` لضمان عدم كسر الصفحات الحالية.
2. فلترة حسب نوع الحركة + اتجاه السطر + البحث بالنص (اسم/كود).
3. ترتيب النتائج داخل أقسام UX واضحة:
   - `مقترح من الوصف`
   - `المفضلة`
   - `الأخيرة`
   - `كل الحسابات المتاحة`
4. إضافة keywords suggestions من الوصف (مثل: إيجار/رواتب/صيانة/تحصيل…).
5. إضافة `data-testid` تفصيلية لعناصر القائمة الذكية (dropdown/search/sections/options).

**التحقق بعد الترقية:**
- تقرير الاختبار: `/app/test_reports/iteration_170.json`
- النتيجة: **Frontend 100% PASS**
- تم التحقق من:
  - ظهور خيارات الحسابات (187 خيار في اختبار line-account-0)
  - وجود البحث داخل القائمة
  - استمرار عمل الفلترة الطرفية (عميل/مورد)
  - عدم وجود Regression في صفحة العمليات.

### Supplier-Balance Payment Restore + Operation Duplicate Guard (10 May 2026)

**1) استعادة ميزة السداد عبر رصيد المورد في ConfirmPaymentDialog**
- إعادة إظهار خيار `supplier_balance` في نافذة تأكيد السداد.
- عند عدم توفر `supplierId` مسبقاً، أصبح يمكن اختيار المورد مباشرة داخل النافذة.
- تمرير `supplierId` المختار إلى callbacks لجميع المسارات (Operations / Debt / Vehicle).

**2) ربط السداد عبر رصيد المورد بسجل حركة المورد**
- إضافة endpoint جديد:
  - `POST /api/smart-accounting/operations/{op_id}/confirm-via-supplier-balance`
- هذا المسار يقوم بـ:
  - إنشاء حركة سداد من رصيد المورد (`supplier_balance_payment` journal source)
  - تحديث حالة العملية إلى `paid/partial` حسب المتبقي.
- تحسين robustness في `supplier_balance_payment`:
  - تحقق صريح من `supplier_id` (بدلاً من 500)
  - معالجة بيئات لا تحتوي جدول `suppliers` بدون كسر endpoint.

**3) تعزيز منع تكرار العمليات قبل الحفظ**
- تطوير منطق كشف التكرار في `Operations.jsx` ليقارن أكثر من إشارة:
  - النوع + المبلغ + الشريك + اللوحة + التاريخ + الفاتورة + توقيع البنود
- إضافة استثناء ذكي: **نفس العميل مع لوحة مختلفة** لا يُعتبر تكراراً مباشراً.
- عند الاشتباه، يظهر prompt تأكيد واضح قبل متابعة الحفظ.

**الاختبار والتحقق**
- تم تشغيل اختبارات backend المضافة:
  - `pytest -q /app/backend/tests/test_supplier_balance_payment_iter171.py -q`
  - النتيجة: PASS (مع warnings فقط داخل ملف الاختبار نفسه).
- تم إصلاح خطأ 500 الذي ظهر أثناء اختبار endpoint الجديد.

### Operation Type/Payment Mapping Hardening + Flow Consistency (10 May 2026)

**استجابة لطلب مطابقة المسميات والربط المحاسبي الكامل:**

1. **تحديث أنواع الحركة في واجهة العمليات**
   - إضافة/تأكيد الأنواع التالية في `OPERATION_TYPE_OPTIONS`:
     - شراء
     - بيع
     - سند قبض (مركبة)
     - تسوية (عميل/مورد)
     - مرتجع بيع
   - الإبقاء على الأنواع الإضافية المطلوبة تشغيلياً (مرتجع شراء/سداد مستحقات/مصروف نقدي).

2. **إزالة خيار محفظة نهائياً من تبويب الربط/الدفع**
   - `PAYMENT_METHOD_OPTIONS` أصبحت: `cash`, `card`, `transfer`, `credit` فقط.
   - تم التأكد أيضاً أن `ConfirmPaymentDialog` لا يحتوي أي خيار Wallet.

3. **تشديد قواعد الربط (Frontend + Backend)**
   - بيع/مرتجع بيع: يجب ربط العملية بمركبة أو عميل.
   - شراء/مرتجع شراء: يجب تحديد مورد.
   - سند قبض (`receipt_voucher`): يجب ربط العملية بمركبة.
   - تسوية (`settlement`): يجب ربطها بعميل أو مورد.
   - تم تنفيذ نفس القواعد في backend داخل `create_operation` لمنع أي تجاوز حتى لو تم الالتفاف على الواجهة.

4. **توحيد الربط المحاسبي لطريقة الدفع**
   - تم تحديث التوجيه المحاسبي بحيث `card` → حساب POS (`006`) وليس البنك.
   - في `payment_order` مع عميل: تم تصحيح حساب الذمم المدينة إلى `005` بدلاً من الكود القديم `1103`.

5. **تحسين فلترة الحسابات في تبويب الربط**
   - `SmartAccountSelect` في العمليات أصبح `includeAll=false` لإظهار الحسابات ذات الصلة فقط بنوع الحركة/جهة القيد.

**نتيجة الاختبار (Testing Agent):**
- التقرير: `/app/test_reports/iteration_171.json`
- Backend: **100% (14/14 PASS)**
- Frontend: **100% PASS**
- تم التحقق صراحةً من غياب Wallet وصحة قواعد الربط المذكورة.

### Sub-screens Alignment + Journal Explanation Screen (10 May 2026)

**1) توحيد قواعد الربط في شاشة القيود اليدوية (`JournalEntries`)**
- إضافة أنواع الحركة الفرعية المتوافقة مع نفس منطق العمليات:
  - `receipt_voucher` = سند قبض (مرتبط بمركبة)
  - `settlement` = تسوية (عميل/مورد)
- إضافة حقل `entry-vehicle-reference-input` (مرجع المركبة).
- إضافة validation في القيود اليدوية:
  - بيع/مرتجع بيع → يتطلب عميل أو مرجع مركبة.
  - سند قبض → يتطلب مرجع مركبة.
  - تسوية → تتطلب طرف (عميل/مورد) ونوع طرف صحيح.
- دعم toggle واضح في التسوية لاختيار عميل/مورد.

**2) إضافة شاشة/بطاقة "تفسير القيد" داخل صفحة العمليات**
- إضافة بطاقة `operation-journal-explanation-card` في خطوات إنشاء العملية.
- البطاقة تعرض:
  - سطور مدين/دائن المتوقعة
  - كود الحساب المتوقع لكل طرف
  - سبب الاختيار (reasoning) حسب نوع الحركة وطريقة الدفع.

**نتائج الاختبار:**
- تقرير: `/app/test_reports/iteration_172.json`
- Frontend: **100% PASS**
- تم التحقق من وجود الأنواع الجديدة، مرجع المركبة، قواعد التحقق، وبطاقة تفسير القيد، واستمرار غياب خيار Wallet.

### JournalEntries Liquid System UI Upgrade (10 May 2026)

**طلب المستخدم:** تحويل صفحة **دفتر اليومية** إلى أسلوب Liquid مع الحفاظ الكامل على الوظائف.

**ما تم تنفيذه في `JournalEntries.jsx`:**
1. إعادة تصميم بصري Liquid للصفحة كاملة:
   - خلفية متعددة الطبقات (radial gradients)
   - عناصر orb ضوئية خفيفة
   - بطاقات زجاجية (glass) مع borders ولمعان داخلي
2. تحسين البطاقات الرئيسية:
   - Header card
   - AI assistant card
   - Stat cards
   - Filters card
   - Journal entries table card
3. الحفاظ على كل الوظائف والـ data-testid بدون كسر:
   - فتح مودال قيد جديد
   - البحث والفلاتر
   - الأزرار التشغيلية (تحديث/حذف الكل مع إبقاء الذمم)

**نتائج الاختبار:**
- تقرير: `/app/test_reports/iteration_173.json`
- Frontend: **100% PASS**
- لا توجد مشاكل UI/Integration/Design في التقرير.

### Mobile UX Fix — Journal Entry Account Names & Overflow (10 May 2026)

**مشكلة المستخدم:** في شاشة إنشاء قيد على الجوال، أسماء الحسابات/الكود غير واضحة والحجم كبير، مع overflow أفقي.

**الإصلاحات المنفذة:**
1. `SmartAccountSelect.jsx`
   - إضافة `compact` mode.
   - تحسين عرض النص ليكون:
     - `[code] name` عند توفر الاسم
     - `[code]` كـ fallback عند غياب الاسم
   - تحسين truncate/width لقراءة أفضل على الجوال.

2. `JournalEntries.jsx`
   - إضافة layout موبايل مستقل لبنود القيد (`entry-lines-mobile-list`) على شكل cards.
   - إخفاء جدول الديسكتوب على الجوال (`hidden md:table`).
   - إبقاء إدخال المدين/الدائن واضحاً ضمن شبكة 2 عمود في الجوال.

**نتيجة الاختبار:**
- تقرير: `/app/test_reports/iteration_175.json`
- Frontend: **100% PASS**
- تم إصلاح overflow بالكامل: من ~12px إلى **0px** على viewport 390x844.

### Debit/Credit Color Safety + Account Dropdown Stability (10 May 2026)

**طلبات المستخدم المنفذة:**
1. تمييز بصري واضح لتجنب خطأ القيد:
   - عند اختيار حساب:
     - حقل **مدين** يظهر بخلفية/حدود خضراء.
     - حقل **دائن** يظهر بخلفية/حدود حمراء.
   - إضافة Legend ثابت داخل المودال:
     - `مدين = أخضر`
     - `دائن = أحمر`

2. إصلاح ظهور قائمة الحسابات السفلية:
   - ربط مباشر بـ `coaAccounts` داخل JournalEntries.
   - إضافة fallback قوي داخل `SmartAccountSelect` (`CORE_FALLBACK_ACCOUNTS`) عند بطء/فشل التحميل حتى لا تظهر القائمة فارغة.

**الاختبار:**
- تقرير: `/app/test_reports/iteration_176.json`
- Frontend: **100% PASS**
- تم التحقق من:
  - التلوين الأحمر/الأخضر يعمل حسب اختيار الحساب.
  - القائمة لم تعد فارغة (ظهور 187 خيار في الاختبار).
  - الجوال والديسكتوب يعملان بشكل صحيح.

### Linkage Integrity Layer (Vehicle File ↔ Operations ↔ Journal) — 10 May 2026

**أين يوضع كشف الربط؟ (تم التنفيذ):**
1. **صفحة العمليات**
   - بطاقة ملخص: `operations-integrity-summary-card`
   - داخل كل بطاقة عملية: شارة حالة الربط + تفاصيل التحذيرات عند التوسيع.
2. **ملف المركبة (تبويب الزيارات)**
   - بطاقة ملخص ربط: `vehicle-linkage-summary-card`
   - قائمة مشاكل الربط: `vehicle-linkage-issues-list` (عند وجود أخطاء).
3. **دفتر اليومية**
   - حالة الربط لكل قيد في العرضين (جوال/ديسكتوب):
     - `entry-card-linkage-{id}`
     - `entry-row-linkage-{id}`

**Backend جديد:**
- `POST /api/operations/integrity/check`
  - يدقق العلاقة بين: العملية، المركبة/الزيارة، وقيد اليومية (reference_id).
  - يعيد `items + summary` مع تحذيرات مثل:
    - `missing_journal_entry`
    - `visit_vehicle_mismatch`
    - `potential_duplicate`

**التكرار (Duplicate) والتحذيرات:**
- تم دعم مؤشر تكرار محتمل ضمن endpoint ويظهر في ملخص العمليات.
- تم إصلاح ملاحظة اختبارية مرتبطة بـ `workshop_id` في Supabase داخل endpoint.

**الاختبار:**
- تقرير: `/app/test_reports/iteration_177.json`
- Backend: **PASS 100%**
- Frontend: تم التحقق من ظهور مكونات العمليات بالكامل، وباقي العناصر مثبتة في الكود مع data-testid.

### Interpretive Rule Update (دخل/خرج) — 10 May 2026

**طلب المستخدم:**
- "الذي دخل لك = مدين"
- "الذي خرج منك = دائن"
- تطبيق القاعدة في صفحة إنشاء قيد وتحديث بلوك تفسير القيد في العمليات.

**ما تم تنفيذه:**
1. **Operations.jsx**
   - تحديث `operation-journal-explanation-card` لإظهار القاعدتين النصيتين بشكل ثابت.
   - سطور المعاينة أصبحت تعرض: `side + account + flow` حيث flow = `دخل لك / خرج منك`.
   - تحسين الصياغة التفسيرية خصوصاً في الشراء:
     - المشتريات = مدين
     - الصندوق/البنك أو الذمم = دائن

2. **JournalEntries.jsx (Modal إنشاء قيد)**
   - إضافة بطاقة جديدة `entry-explanation-rule-card` داخل نموذج الإنشاء.
   - تعرض:
     - القاعدتين النصيتين
     - سطر مدين وسطر دائن مع الحساب الملتقط من مدخلات المستخدم.

3. **إصلاح تحذير منخفض من الاختبار**
   - تمت معالجة ملاحظة `Maximum update depth exceeded` في `Operations.jsx` عبر تثبيت dependency الفحص إلى `activeOpsIdsKey` بدلاً من الكائنات المباشرة.

**الاختبار:**
- تقرير: `/app/test_reports/iteration_178.json`
- النتيجة: Frontend **PASS 100%**
- تمت مراجعة logs بعد الإصلاح، ولم يعد يظهر تحذير Maximum update depth.

### Unified Bot Update — Merge Auditor into Quick + Create Linking Enhancements (10 May 2026)

**تنفيذ طلب المستخدم (B):**
1. **دمج تبويب المدقق مع فوري**
   - التبويبات أصبحت 3 فقط:
     - `المساعد`
     - `إنشاء`
     - `فوري`
   - تبويب `فوري` الآن مدمج:
     - Quick action panel (تسجيل فوري)
     - رسائل/أوامر التدقيق المالي في نفس التبويب.

2. **تحسين تبويب إنشاء (ربط وتوافق)**
   - تحسين payload الإنشاء للتوافق مع الصفحات المرتبطة:
     - `originalType`
     - `vehicleId / vehicleInfo`
     - `notes` مع tag: `BOT_TEMPLATE`
   - إضافة validation أقوى للربط:
     - بيع يتطلب عميل/مركبة
     - شراء يتطلب مورد

3. **كروت أنواع العملية تعرض آخر العمليات**
   - كل كرت قالب يعرض `آخر X عمليات`.
   - عند اختيار القالب يظهر block `template-recent-operations-list`:
     - قائمة آخر العمليات لنفس النوع (قابلة للنقر لتعبئة الحقول)
     - أو رسالة: `لا توجد عمليات سابقة لهذا النوع بعد.`

**الاختبار:**
- تقرير: `/app/test_reports/iteration_179.json`
- Frontend: **100% PASS**
- تم التحقق من:
  - اختفاء تبويب المدقق المنفصل
  - عمل الدمج داخل فوري
  - ظهور عدادات وآخر العمليات في كروت الإنشاء
  - عدم وجود Regression في الإنشاء.

### NLP Page Assistant (Rule-based) داخل المساعد الموحد — 10 May 2026

**طلب المستخدم:**
- Page Assistant ذكي يقرأ الصفحة الحالية وحقولها.
- يقترح تصحيحًا ويطبقه فقط بعد موافقة المستخدم.
- النطاق: كل الصفحات المالية (C).
- منطق النسخة الأولى: Rule-based (A).
- واجهة الاقتراحات مدمجة داخل المساعد الموحد.

**ما تم تنفيذه:**
1. **Backend (FastAPI)**
   - إضافة ملف: `routes_nlp_page_assistant.py`
   - Endpoints:
     - `POST /api/nlp/page/context`
     - `POST /api/nlp/page/apply_correction`
   - محرك قواعد Rule-based + تعلم بسيط من:
     - approved_entries
     - corrected_entries
     - rejected_entries
   - أمثلة قواعد مفعلة:
     - card + account 004 ⇒ اقتراح 006
     - sale بدون ربط عميل/مركبة ⇒ اقتراح ربط
     - journal line فيها debit+credit معًا ⇒ اقتراح تصحيح

2. **Frontend (UnifiedBotWidget)**
   - مراقبة تغيّر أي `input/select/textarea` في الصفحات المالية.
   - إرسال page context تلقائيًا إلى endpoint مع debounce.
   - عرض `page-suggestion-box` داخل البوت نفسه (apply / ignore).
   - عند Apply: استدعاء endpoint التطبيق + محاولة تعبئة الحقول المصححة في الواجهة.

3. **تكامل عام**
   - تضمين Router الجديد في `server.py`.
   - الحفاظ على عمل تبويبات البوت الثلاثة (المساعد، إنشاء، فوري) دون كسر.

**الاختبار:**
- تقرير: `/app/test_reports/iteration_180.json`
- Backend: **100% (10/10)**
- Frontend: **100%**
- ملفات الاختبار الناتجة:
  - `/app/backend/tests/test_nlp_page_assistant.py`
  - `/app/test_reports/pytest/pytest_nlp_page_assistant_iter180.xml`

### Floating Bot Open/Visibility Fix (All Pages) — 10 May 2026

**المشكلة:**
- المستخدم أبلغ أن البوت العائم لا يفتح عند الضغط عليه في كل الصفحات.

**الإصلاح:**
1. في `UnifiedBotWidget.jsx`:
   - استبدال toggle بفتح صريح عبر `forceOpenBotPanel`.
   - رفع طبقات العرض:
     - trigger z-index = `2147483000`
     - panel z-index = `2147482999`
   - الحفاظ على الإغلاق من زر `unified-bot-close` داخل النافذة.

**التحقق:**
- تقرير: `/app/test_reports/iteration_181.json`
- Frontend: **100% (12/12)** عبر 3 صفحات:
  - operations
  - accounting/journal-entries
  - suppliers
- النتيجة: **FIXED** (الزر يظهر والنافذة تفتح بشكل صحيح).

### Mobile Chat Panel Layout Fix (Unified Bot) — 10 May 2026

**مشكلة المستخدم:**
- الزر صحيح، لكن نافذة المحادثة لا تظهر بشكل صحيح على الجوال.
- المطلوب: الجوال صحيح + سطح المكتب بالأسفل لليسار.

**الإصلاح المنفذ في `UnifiedBotWidget.jsx`:**
1. تثبيت تموضع النافذة كـ `fixed` فعلياً (إزالة تعارض `relative` الذي كان يفسد القياسات).
2. تحسين أبعاد الجوال:
   - عرض: `92vw`
   - max-width: `420px`
   - تموضع: `left-3` + bottom مع safe-area.
3. الحفاظ على تموضع الديسكتوب بالأسفل لليسار:
   - `lg:left-6` + `lg:bottom-20`.
4. الحفاظ على z-index عالي جدًا لضمان الظهور فوق كل عناصر الصفحة.

**نتيجة الاختبار (وكيل الاختبار):**
- Mobile 390x844: PASS (النافذة كاملة داخل الشاشة وبدون قص).
- Desktop 1920x1080: PASS (النافذة أسفل يسار كما طُلب).
- Close button + Tabs + z-index: PASS.

### Mobile Chat Input Overlap Fix (Unified Bot) — 10 May 2026

**مشكلة جديدة من المستخدم:**
- الدردشة لا تعمل على الجوال لأن زر البوت العائم كان يغطي خانة إدخال الرسائل.

**الإصلاح المطبق:**
1. إخفاء زر البوت العائم عند فتح النافذة:
   - تطبيق شرط render: `!open && (...)` على `unified-bot-trigger`.
2. التأكد من إمكانية الإغلاق وإعادة الظهور:
   - زر `unified-bot-close` داخل النافذة يغلق panel.
   - trigger يعود للظهور بعد الإغلاق.
3. تحسين قابلية الاختبار:
   - إضافة `data-testid="unified-bot-close"`.

**الاختبار:**
- تقرير: `/app/test_reports/iteration_182.json`
- Frontend: **100% (5/5)**
- النتيجة: **FIXED**
  - trigger يختفي عند فتح panel
  - input قابل للكتابة والإرسال على الجوال
  - لا توجد Regression على الديسكتوب.

### Create-Intent Response Fix (No More "هات تقرير/كشف") — 10 May 2026

**مشكلة المستخدم:**
- عند كتابة أمر إنشاء عملية باللهجة العربية، كان البوت يرد برد خاطئ من نوع:
  - "هات تقرير/كشف..."

**المطلوب:**
- نمط B:
  - عرض **ملخص قبل التنفيذ**
  - إظهار **النواقص**
  - منع أسئلة "تقرير/كشف" في أوامر الإنشاء.

**الإصلاح المطبق في `UnifiedBotWidget.jsx`:**
1. إضافة `parseCreateIntent` مع تطبيع عربي (`normalizeArabicText`) لالتقاط الصيغ:
   - انشى / انشي / سجل / سوي ...
2. معالجة أوامر الإنشاء محلياً (بدون المرور لردود LLM العامة).
3. استخراج ذكي:
   - نوع العملية (بيع قطع/شراء/رواتب/مصروف...)
   - الطرف (بعد "على ...")
   - المبلغ (إن وجد)
4. إظهار `create-result` يحتوي:
   - 🧾 ملخص قبل التنفيذ
   - ⚠️ النواقص (مثال: المبلغ)

**الاختبار:**
- تقرير: `/app/test_reports/iteration_183.json`
- Frontend: **100%**
- النتيجة: **FIXED**
  - لا توجد عبارات تقرير/كشف في أوامر الإنشاء
  - القالب المناسب يتحدد (مثال: بيع قطع)
  - النواقص تظهر كما طُلب.

### Interactive Draft Cards for Create Commands (10 May 2026)

**طلب المستخدم:**
- ردود البوت تكون تفاعلية عند أوامر الإنشاء.
- النواقص/المعاينة تظهر كروت قابلة للنقر.
- عند وجود عميل بدون مركبة محددة:
  - عرض المركبات المسجلة بنفس الاسم
  - أو خيار إضافة مركبة جديدة.

**ما تم تنفيذه في `UnifiedBotWidget.jsx`:**
1. إضافة حالة `interactiveDraft`.
2. عند أمر مثل:
   - `انشى عمليه بيع قطعه قلب هاي من قطع راكان على ماجد العنزي`
   - يتم:
     - التحويل تلقائيًا لتبويب `إنشاء`
     - عرض `interactive-draft-cards`
3. محتوى الكروت التفاعلية:
   - كرت النوع
   - كرت الطرف
   - كرت المبلغ
   - شرائح النواقص القابلة للنقر (chips)
4. ربط المركبات:
   - `findVehiclesForPartner` يبحث في المركبات بالاسم المطبع.
   - عرض قائمة مركبات مطابقة أو رسالة عدم وجود.
   - زر `+ إضافة مركبة جديدة`.
5. أزرار إجراءات مباشرة:
   - `تأكيد الآن`
   - `تعديل الحقول`
   - `إلغاء`

**الاختبار:**
- تقرير: `/app/test_reports/iteration_184.json`
- Frontend: **100% (all 6 scenarios passed)**
- تم التحقق من:
  - ظهور كل الكروت التفاعلية المطلوبة
  - استخراج اسم العميل من النص
  - منع ردود "تقرير/كشف"
  - ظهور قسم المركبات وزر الإضافة الجديدة.

### Test Data Cleanup + Full Pages Smoke Test (10 May 2026)

**طلب المستخدم:**
- حذف جميع البيانات الاختبارية/التجريبية، بما يشمل: الحسابات، الخدمات، القطع، وباقي الجداول.
- ثم اختبار كل الصفحات.

**التنظيف المنفذ (Supabase):**
- تم حذف البيانات التي تطابق كلمات تجريبية مثل:
  - test/demo/dummy/sample/qa
  - اختبار/تجريبي
  - BOT_TEMPLATE / BOT_CREATE

**نتيجة التنظيف (counts):**
- `vehicle_visits`: deleted 34
- `operations`: deleted 13
- `journal_entries`: deleted 4
- `customers`: deleted 6
- `services`: 0 matched
- `parts`: 0 matched
- `accounts`: 0 matched
- `vehicles`: 0 matched
- `suppliers`: جدول غير موجود في schema الحالي (PGRST205)

**اختبار شامل بعد التنظيف:**
- تقرير: `/app/test_reports/iteration_185.json`
- Frontend smoke/integration: **100% PASS**
- الصفحات المختبرة: operations, vehicle details, suppliers, debts follow-up, journal entries, inventory, vehicles
- Unified Bot: PASS على كل التبويبات والفتح/الإغلاق.

### P1: Auto-Linking + Contradiction Engine + Escalation Workflow (26 Apr 2026)

**3 محركات جديدة في `routes_finance_bot.py`:**

1. **Auto-Linking Engine** (`_auto_link_finding`):
   - عند `open_investigation` يجلب تلقائياً القيود المحاسبية المرتبطة بالحساب/المبلغ (هامش ±10%)
   - يجلب العمليات المرتبطة زمنياً
   - يُعيد `{journal_entries, operations, accounts_involved, summary_text}`
   - endpoint: `POST /api/finance-bot/auto-link`

2. **Contradiction Engine** (`_detect_contradictions`):
   - فحص 1: إيراد الملاحظة vs. قائمة الدخل الفعلية (score threshold 15%)
   - فحص 2: تناقضات داخلية بين findings على نفس الحساب
   - فحص 3: وصف يذكر مبالغ لكن القيمة المسجّلة صفر
   - endpoint: `POST /api/finance-bot/detect-contradictions`

3. **Escalation Workflow** (`_build_escalation_report`):
   - Auto-Escalation: بعد 6 جولات probing بدون حل على finding بخطورة high/critical
   - تقرير تصعيد كامل: finding details + توضيح المستخدم + التناقضات + الأدلة
   - endpoint: `GET /api/finance-bot/sessions/{session_id}/report`

**Frontend (`AbuFahadFloatingChat.jsx`):**
- عرض `contradictions` المكتشفة (amber panel)
- عرض `linked_data` القيود المرتبطة (sky panel)
- زر "تقرير التصعيد الكامل" عند `state=escalated`

**النتائج المؤكدة:**
- Auto-link: 3 قيود مرتبطة لحساب 005 ✅
- Contradiction: كشف revenue_mismatch (50000 vs 27081) بخطورة high ✅
- Auto-Escalation: يُفعَّل في الجولة السادسة بالضبط ✅
- Escalation Report: تقرير كامل مع التوصية ✅

### شامل: تنظيف البيانات + ترحيل الأكواد (25 Apr 2026)
**ما تم:**
1. **حذف بيانات الاختبار**: 6 عمليات + 2 قيد يومية تجريبية حُذفت نهائياً
2. **ترحيل 45 قيد**: جميع سطور قيود اليومية بالأكواد القديمة (1101→003، 1102→004، 1103→005، 1104→006، 4100→026، 4000→025، 6100→036، 6101→037) ترحيلاً فعلياً في Supabase
3. **endpoint جديد**: `POST /api/finance/reports/migrate-legacy-codes?workshop_id=...&apply_changes=true`
4. **routes_extended.py**:
   - `ACCOUNT_NAME_MAP` محدّث بالأكواد الجديدة + القديمة للتوافق
   - `LEGACY_TO_NEW_CODE` map جديد
   - `_normalize_account_code` يحوّل legacy تلقائياً
   - `_build_operation_journal_entry` يستخدم أكواداً جديدة: 003/004/005/026/036
5. **routes_finance.py**:
   - `_infer_account_type_from_code` يتعرف على الأكواد الجديدة (001-059) والقديمة (1000-6999)
   - `AR_ACCOUNT_CODES`, `CASH_ACCOUNT_CODES`, `BANK_ACCOUNT_CODES` محدّثة
   - `_to_new_code()` helper جديد
   - جميع دوال القراءة (income-statement, balance-sheet, reclassify) تدعم الأكوادين
6. **حذف ملفات backup**: AIFinancial_chat_backup, BalanceSheet_backup, CashFlow_backup, IncomeStatement_backup, Invoices_backup, TrialBalance_backup, Settings_broken

**نتائج الاختبار 8/8 (100%):**
- ✅ لا عمليات اختبار
- ✅ لا قيود بأكواد قديمة
- ✅ income-statement: 27,081 ر.س
- ✅ تحليلات راكان: 153 ر.س

### Journal Entry UUID Bug Fix (25 Apr 2026)
- `_build_operation_journal_entry`: UUID لا يُستخدم كـ revenue code → يُستخدم 026 بدلاً منه
- تقرير اختبار: `/app/test_reports/iteration_166.json` — 32/32 PASS

### Sidebar UX Overhaul (25 Apr 2026)
- جميع المجموعات تبدأ مطوية + scroll تلقائي عند الفتح

### Rakan Analytics Fix (25 Apr 2026)
- `_is_rakan_operation` يفحص `items` داخل العملية → اكتشاف قطع راكان من ملف المركبة

### RakanLinkedPartPicker Cleanup (25 Apr 2026)
- إزالة العنوان والتحذير من المكوّن + إزالة سجل الموردين من ملف المركبة

### Raw Field Arabic Display + Visit Number Format (13 May 2026)
- أُضيفت خرائط عرض عربية مشتركة للعمليات، طرق الدفع، حالات السداد، مصادر القيود، وأنواع الحسابات في `frontend/src/utils/displayLabels.js`.
- أُزيل ظهور UUIDs والمفاتيح الإنجليزية من بطاقة العملية، نافذة تفاصيل العملية، صفحة المخزون، ملف المركبة، العملاء، الموردين، والبوت الموحد.
- أرقام الزيارات تُعرض الآن بصيغة 3 خانات (`001`, `002`, `003`) من `/api/operations` و`/api/vehicles/{id}/visits`، مع تخزين آمن للرقم داخل ملاحظات الزيارة في Supabase عند إنشاء زيارات جديدة.
- الاختبار: Pytest regression `/app/backend/tests/test_iteration_207_visit_display_and_labels.py` نجح 4/4، وفحص API اليدوي أكد `visitNumberDisplay=001`، ووكيل الاختبار أكد صفحة العمليات بدون raw ظاهر؛ تم إصلاح ملاحظة المخزون `parts_pos/rakan_parts_pos` بعد تقرير الاختبار.

### Partial Visit Payment Display Fix (13 May 2026)
- تم إصلاح حالة عملية الزيارة التي تحتوي دفعة مقدمة فقط داخل الزيارة بينما البنود محفوظة في العملية؛ لم تعد الواجهة تعرض `مسدد بالكامل` أو رصيد `0` خطأ.
- المثال المتحقق: مركبة `1060 /// ب ص م 7782` / بند `توضيب مكينة` / إجمالي `2300` / مدفوع `300` أصبح يظهر: `مدفوع جزئياً`، المتبقي `2000`، وملاحظة `عملية من الزيارة 001`.
- تم تحسين بطاقة العملية: منع عبارة `حساب حساب`، منع `التصنيف: غير مصنف` للعمليات ذات النوع المعروف، وتحويل تاريخ العملية إلى تقويم ميلادي بدون وقت مضلل عند تاريخ العملية فقط.
- الاختبار: `/app/backend/tests/test_iteration_207_visit_display_and_labels.py` نجح 5/5، ووكيل الاختبار أضاف وتحقق من `/app/backend/tests/test_iteration_208_specific_operation_display.py` بنجاح 1/1؛ لا توجد APIs MOCKED.

### Vehicle ↔ Operations ↔ Journal ↔ Financial Summary Linkage Fix (13 May 2026)
- تم ربط كروت الملخص المالي داخل ملف المركبة بقيود التحصيل المرتبطة بالعملية (`operation_payment`, `operation_payment_income`, `supplier_balance_payment`) بدل الاعتماد فقط على دفعات ملاحظات الزيارة.
- تم إصلاح ملف المركبة للمثال `5287aa8d... / 99970dc5...`: الملخص المالي يعرض الآن إجمالي الورشة `2300`، المدفوع `2300`، المتبقي `0`، والزيارة نفسها `paid_full`.
- تم توسيع `/api/finance/journal-entries` ليُرجع `party_label` و`vehicle_label` للقيود المرتبطة عبر `reference_id` حتى تظهر في ملف المركبة ضمن “قيود دفتر اليومية المرتبطة”.
- تم تطبيع أسطر القيود المعروضة إلى الأكواد الجديدة (`003`, `027`...) ومنع ظهور أكواد قديمة مثل `1101/1102/1103/1104` في القيود المرتبطة المستهدفة.
- تم منع تكرار POS: عند تحصيل عميل مرتبط بمركبة، الواجهة تستخدم `/operations/{id}/confirm-payment` على العملية الأصلية، والباكند يحمي أيضًا من إنشاء `payment_order` مكرر عبر تحويله إلى سداد للعملية المفتوحة.
- تم إخفاء زر “تأكيد سداد الآجل” عندما تكون العملية `paid_full` أو الرصيد `0` حتى لو بقيت قيمة تاريخية لطريقة الدفع.
- تمت إضافة خرائط عربية لمصادر القيود الناقصة مثل `operation_payment_income` لمنع ظهور مفاتيح raw داخل ملف المركبة.
- الاختبار: وكيل الاختبار Iteration 209 أكد backend بنسبة 100% وأضاف `/app/backend/tests/test_iteration_209_vehicle_5287_linkage.py`، وبعد إصلاح خريطة المصدر نجحت اختبارات `iteration_208` و`iteration_209` جميعها 7/7. لا توجد APIs MOCKED.

### Granular User Permissions + UI Cleanup (14 May 2026)
- تم توسيع نموذج الصلاحيات ليشمل صفحات ووظائف مستقلة: `dashboard`, `operations`, `journal_entries`, `archive` مع وظائف مثل `view/create/edit/delete/settle/pos` حسب الصفحة.
- تم تعديل القائمة الجانبية والحماية المباشرة للمسارات بحيث الصفحات غير المصرح بها لا تظهر نهائيًا ولا تفتح بالرابط المباشر؛ يتم تحويل المستخدم لأول صفحة مسموحة.
- تم تحديث إدارة المستخدمين لعرض صلاحيات الصفحة ووظائفها بدون ربط إجباري بين صفحات غير مرتبطة.
- تم ربط أزرار العمليات بالصلاحيات: تأكيد السداد، التعديل، الحذف، وتعديل البنود تختفي عند عدم وجود صلاحية.
- تم إخفاء بلوك “عملية جديدة” من صفحة العمليات، وإخفاء إرشاد “تأكيد السداد” لمن لا يملك صلاحية التسوية.
- تم إزالة كرت “المساعد المالي” من دفتر اليومية.
- تم ربط دفتر اليومية بصلاحيات الوظائف: `قيد جديد`، `حذف الكل`، تعديل/حذف القيود، وPOS تظهر فقط عند السماح.
- تم إخفاء مبالغ “آخر القيود” داخل تبويب POS؛ تبقى بيانات غير مالية فقط.
- تم تحديث backend normalization في `/api/users` لضمان دعم الصلاحيات الجديدة للبيانات القديمة والجديدة.
- الاختبار: lint نجح، وكيل الاختبار Iteration 210 أكد الصلاحيات والواجهة والباكند، وتمت إضافة `/app/backend/tests/test_permissions_iter210.py`. لا توجد APIs MOCKED. تم أيضًا self-test لصلاحية عمليات view-only وإخفاء إرشاد السداد ومبالغ آخر القيود في المصدر.

### Smart POS Recent Journal Entry Detail Fix (14 May 2026)
- بناءً على طلب المستخدم الأخير، تم إعادة إظهار مبلغ آخر القيود داخل POS مع توضيح كامل للقيد بدل الاكتفاء بالطرف والمركبة.
- بطاقة آخر القيود في POS تعرض الآن: المبلغ، مصدر القيد بالعربية، طريقة الدفع إن وجدت، الطرف، المركبة، وملخص أسطر القيد مدين/دائن بأسماء الحسابات والمبالغ.
- تم تنظيف وصف القيد من رموز خام مثل `[VISIT:uuid]` و`[IDEMP:...]` حتى لا يظهر `99970dc5...` للمستخدم.
- تم تعديل `JournalEntries.jsx` لتمرير `total/date/vehicle_label/lines` إلى `SmartPOSJournal`، وتعديل backend في `routes_finance.py` لاستخراج `vehicle_label` من `[VEHICLE_REF:...]` عند غياب الربط المباشر.
- تم إضافة تحميل احتياطي داخل `SmartPOSJournal` لآخر القيود حتى لا تبقى القائمة فارغة إذا تأخر تمرير البيانات من دفتر اليومية.
- الاختبار: lint نجح، ووكيل الاختبار Iteration 211 أكد ظهور `500.00 ر.س`، `سند قبض زيارة`، الطرف `1060 /// ابو ياسر الزويد`، المركبة `1060 /// ب ص م 7782`، وملخص القيد، مع نجاح pytest 7/7. لا توجد APIs MOCKED.

### Users Page + Faraj1 Dashboard Access Fix (14 May 2026)
- تم إصلاح صفحة المستخدمين لتعرض صفحة `UsersManagement` المحدثة مع `اسم الدخول` وبطاقات الصلاحيات الجديدة مثل `صفحة العمليات` و`دفتر اليومية` و`الأرشيف`.
- تم تحديث backend models/routes للمستخدمين لإرجاع `username`، وتطبيع الصلاحيات الجديدة، ومنع تسريب `password` في الاستجابة.
- تم إصلاح تحديث المستخدم بحيث لا يمسح الصلاحيات عند تعديل حقل بسيط مثل الاسم فقط.
- تم تعديل تسجيل الدخول ليقبل `username` أو `name` أو `phone`، ويمسح cookie قديمة قبل حفظ جلسة جديدة.
- تم إضافة تحديث تلقائي لصلاحيات الجلسة من `/api/users` داخل `Protected` لمنع بقاء صلاحيات قديمة بعد تعديل المستخدم.
- تم تحسين لوحة التحكم حتى لا تبقى عالقة على التحميل عند بطء endpoint واحد، باستخدام `Promise.allSettled` مع timeout، وتم إخفاء زر `استقبال مركبة` لمن لا يملك `vehicles.create`.
- التحقق: دخول `فرج1` في Preview يفتح لوحة التحكم بنجاح، العمليات مخفية له، وزر استقبال مركبة مخفي. صفحة `/users` تعرض 4 بطاقات ومن ضمنها `اسم الدخول: فرج1`.
- الاختبار: lint نجح، ووكيل الاختبار Iteration 212 أكد backend/frontend 100%، وpytest مع `REACT_APP_BACKEND_URL` نجح 4/4. لا توجد APIs MOCKED. تم تحديث `/app/memory/test_credentials.md` بإضافة `فرج1`.

### Archive File Access via Page Permissions Fix (14 May 2026)
- تم إصلاح مشكلة فرج1 حيث كانت لوحة التحكم تظهر لكن فتح ملفات المركبات لا يعمل بسبب أن مسار `/vehicle/:id` كان يعتمد فقط على `vehicles.view` رغم أن المستخدم يملك صلاحية `archive.view`.
- تم دعم صلاحيات بديلة للمسارات: `/vehicle/:id` يفتح إذا كان لدى المستخدم `vehicles.view` أو `archive.view`، و`/new-vehicle` يفتح إذا كان لديه `vehicles.create` أو `archive.create`.
- تم تحديث `App`, `Layout`, و`Sidebar` لاستخدام `hasRoutePermission` مع `anyOf` بدل شرط صلاحية واحد.
- تم تحسين الأرشيف ليبدأ على فلتر `الكل` بدل `تم التسليم`، مع إعادة محاولة تحميل الملفات وحالة تحميل واضحة حتى لا تظهر الصفحة فارغة عند بطء الطلب.
- تم ربط أزرار الأرشيف بصلاحياته: التحرير يظهر عند `archive.edit`، والحذف يختفي عند عدم وجود `archive.delete`.
- تم إصلاح ملاحظة runtime في القائمة الجانبية (`onNavigate` غير معرف) وإزالة تكرار مسار `/templates`.
- التحقق: self-test أثبت أن فرج1 يرى 119 ملفًا في الأرشيف ويفتح ملف مركبة بنجاح بدون `غير مصرح`. وكيل الاختبار أكد نفس التدفق، وlint ناجح، وpytest الخاص بالمستخدمين 4/4. لا توجد APIs MOCKED.

### Mobile Dashboard Status Cards Square Layout (15 May 2026)
- تم تعديل كروت حالة لوحة التحكم على شاشة الجوال لتظهر كمربعات في عمودين بدل مستطيلات عريضة بعمود واحد.
- أُضيفت class خاصة `dashboard-stats-grid` و`dashboard-stat-card` مع CSS responsive عند أقل من `640px` يفرض `aspect-ratio: 1/1` ويضبط المسافات الداخلية والأيقونات.
- التحقق: لقطة Playwright بعرض `390px` أثبتت أن الكروت الأربعة أصبحت `165x165` بنسبة `1.00` لكل كرت. لا توجد APIs MOCKED.

### Light Dash Pro Theme + Dashboard/Operations Search Improvements (15 May 2026)
- تم تحويل طابع `dashPro` إلى ثيم فاتح بخلفية off-white ومتغيرات ألوان فاتحة، مع الحفاظ على الخط الحالي ونبرة Dash Pro.
- تم تحسين لوحة التحكم بخلفية فاتحة، كروت أخف، وحدود وظلال أقل حدة، مع الحفاظ على مربعات حالة الجوال.
- تم تحسين بحث لوحة التحكم ليبحث في: اسم العميل، رقم الملف، رقم ملف العميل، اللوحة، الماركة، الموديل، الحالة، نوع الخدمة، والبنود؛ وعند وجود بحث يتم البحث في كل المركبات وليس فقط الظاهرة في لوحة التحكم.
- تم نقل رقم الملف داخل كرت المركبة في لوحة التحكم ليظهر أسفل الماركة/الموديل وبنفس الحجم تقريبًا بصيغة `رقم ملف: 1060`.
- تم إضافة بحث صفحة العمليات مع placeholder عربي، ويبحث في: العميل/المورد، رقم العملية/الفاتورة، اللوحة، رقم الملف المرتبط، نوع العملية، الزيارة، الحساب، الملاحظات، البنود والمبالغ.
- تم جعل بحث العمليات cross-tab بحيث يعرض النتيجة من أي قسم عند كتابة استعلام، بدل أن يبقى مقيدًا بتبويب الورشة/راكان.
- تم إصلاح تقسيم عمليات راكان/الورشة حتى لا تُعامل العمليات ذات account id فارغ كعمليات راكان.
- تم تنظيف عرض كروت `PageCustomCardsDock` والقائمة الأخيرة من نصوص اختبار خام مثل `DOM-CHECK`, `page-description`, `[VISIT]`, `[IDEMP]`.
- تم تقوية تحميل العمليات عند تسجيل الدخول الطبيعي عبر warm cache، ومددنا timeout إلى 8 ثوانٍ حتى يكون بحث العمليات مستقرًا بعد تسجيل الدخول.
- الاختبار: lint ناجح، ووكيل الاختبار Iteration 216 أكد 100%: بحث العمليات `7782` يعرض النتائج بدون تحميل/فراغ، بحث لوحة التحكم `1060` يعرض كرتًا فيه `رقم ملف: 1060`، كروت الجوال مربعة، الخلفية off-white، ولا تظهر DOM-CHECK/page-description. لا توجد APIs MOCKED.

### Light Theme Contrast Fix — Dashboard + Operations (18 May 2026)
- تم تصحيح ألوان النصوص الباهتة في الثيم الفاتح، خصوصًا حقل لوحة المركبة ورقم الملف داخل كروت لوحة التحكم.
- أصبحت لوحة المركبة ورقم الملف والماركة/الموديل باللون الأسود الصريح `rgb(0,0,0)` مع خلفية بيضاء وحدود واضحة.
- تم تحويل كروت العمليات وتفاصيلها إلى خلفيات فاتحة ونصوص داكنة، بما يشمل: الإجمالي، ملخص المركبة، الحساب، تفاصيل المركبة، الملاحظات، الجداول، بنود الموردين، وصندوق القيد المحاسبي.
- تم تعديل `GuidanceStepper` ليكون فاتحًا بنص داكن بدل النص الرمادي/الأبيض الباهت.
- أُضيفت قواعد CSS خاصة بـ `dashPro` تفرض التباين الداكن على كروت المركبات والعمليات لمنع رجوع النصوص الباهتة.
- الاختبار: lint ناجح. Playwright أكد في لوحة التحكم أن `plateColor`, `fileColor`, `titleColor` كلها `rgb(0, 0, 0)`. وفي العمليات أكد أن `totalColor`, `vehicleColor`, `accountColor` كلها `rgb(0, 0, 0)` مع ظهور نتيجة `7782`. لا توجد APIs MOCKED.

---

## Legacy → New Code Mapping (المرجع)
| Legacy | جديد | الاسم |
|--------|------|-------|
| 1101 | 003 | النقد |
| 1102 | 004 | البنك |
| 1103 | 005 | العملاء |
| 1104 | 006 | نقاط بيع |
| 4000 | 025 | الإيرادات |
| 4100 | 026 | إيرادات الخدمات |
| 5000 | 030 | تكلفة الخدمات |
| 6000 | 035 | المصروفات التشغيلية |
| 6100 | 036 | مصروفات عامة وإدارية |
| 6101 | 037 | رواتب إدارية |

---

## Prioritized Backlog

### P1 (Next)
- تحسين مسار تحميل صفحة العمليات لتقليل حالة التذبذب المؤقتة في المعاينة التي قد تظهر 0 بطاقة أثناء أتمتة Playwright قبل اكتمال الطلبات.
- إضافة رابط/فلتر مباشر داخل صفحة العمليات لفتح عملية محددة بالـ invoice/operation id لتسهيل التحقق من زر السداد والربط دون الاعتماد على التمرير.
- إضافة seed اختباري غير دائم لصفحة العمليات وPOS حتى يمكن لوكيل الاختبار التحقق من أزرار كروت العمليات وقائمة آخر القيود على بيانات مضمونة.
- تحسين حماية الجلسة لاحقًا بتحويل cookie إلى HttpOnly من الخادم بدل cookie مكتوبة من المتصفح.
- إعادة فحص بصري هادئ لصفحات العملاء/الموردين بعد ثبات التنقل في Playwright للتأكد النهائي من عدم ظهور raw visit ids في كل حالات البيانات.
- Auto-map لعبارة «من قطع راكان» إلى الحساب `042` داخل بطاقات إنشاء Unified Bot.

### Refactoring (in progress)
- ✅ **Templates** domain extracted (642 lines → routes_templates_extended.py).
- ✅ **Workshop Config** (Settings/Profile/Auth-OTP) extracted (348 lines → routes_workshop_config.py).
- ✅ **Approvals** (+ SSE + Notifications) extracted (591 lines → routes_approvals.py).
- ✅ **Accounts/COA** extracted (1,966 lines → routes_accounts_extended.py).
- ✅ **Technicians** extracted from server.py (54 lines → routes_technicians.py).
- ✅ **Services** extracted from server.py (69 lines → routes_services.py).
- ✅ **Parts** GET/POST/PUT extracted from server.py (81 lines → routes_parts.py).
- ⏳ **Backlog candidates from routes_extended.py (5,094 سطر متبقية):** Visits APIs (~400 lines), Operations CRUD (~700 lines), Vehicles (~200 lines).
- ⏳ **Backlog candidates from server.py (3,219 سطر متبقية):** Vehicles, Customers, Suppliers, Parts sell/restock.

### P2
- OCR / التحقق من المستندات المرفوعة في البوت المالي.

### Refactoring
- تفكيك `server.py` و`routes_extended.py` إلى Routers أصغر (vehicle / nlp / suppliers / bot domains).

## Key API Endpoints
- `GET /api/finance/reports/income-statement`
- `GET /api/suppliers`
- `GET /api/accounts/tree`
- `GET /api/inventory/rakan-analytics`
- `POST /api/finance/reports/migrate-legacy-codes`
