# Workshop ERP — Product Requirements (PRD)

## Original Problem Statement
نظام إدارة ورشة سيارات متكامل (ERP) يدعم اللغة العربية، يضم وحدات محاسبية صارمة، نظام جرد ذكي، تتبع ذمم، ومدقق مالي بالذكاء الاصطناعي.
هدف المرحلة الحالية: "Enterprise Operator" — ترحيل الحالات المؤقتة إلى قواعد بيانات دائمة، RBAC خلفي صارم، مبدأ أربع أعين حقيقي، محرك محاسبة مركزي (كاتب وحيد)، وإجراءات مالية عبر البوت بحوكمة كاملة.
**وثيقة قبول جديدة**: «اختبار سلامة وترابط النظام المحاسبي v1.0» — 13 قاعدة صارمة (مصدر حقيقة واحد، توازن القيد المزدوج، دورة نقدي/آجل، ميزان مراجعة، قائمة دخل، تزامن UI/بوت/قاعدة، سلامة قاعدة البيانات).

## CHANGELOG — 2026-07-03 · توحيد محرك النوايا + شراء من مورد (المرحلتان 1 و 2)
**مختبَر 100% (29/29 pytest — 18 مرحلة 1 + 11 مرحلة 2 — 4 اختبارات API حرفية e2e)**

### المرحلة 1 — محرك P0 (توحيد المسار + نية الشراء)
- 🔴 **جذر P0 (السبب الحقيقي للـ 4 مسودات)**: المقسِّم النصي القديم في `power_mode._SPLIT_RE` كان يقطع على النقطة `1300.` → يُنتج 4 أجزاء → 4 مسودات. تم **تعطيل `extract_commands`** ليُعيد الرسالة كأمر واحد.
- 🎯 **توحيد المحرك (SSOT)**: `/power` و**الرسائل العادية** كلاهما يمرّ الآن عبر `unified_executor.execute_text()` → مسار LLM موحّد → عقد JSON منظم واحد → مسودة واحدة فقط.
- 🛒 **نية `create_purchase` جديدة** بمخطط JSON صارم: `{supplier:{name,is_new,id}, items[], payment_method, vat:{mode,rate}, assumptions[], missing[]}`.
- 🏦 **التوجيه المحاسبي (Decimal، توازن صارم)**: نقدي→007/003 · تحويل→007/004 · آجل→007/2101(+مورد) · VAT excluded/included→بند مدخلات (0451) + توازن الإجمالي.
- 🏷️ **الافتراضات موسومة بدون تكرار**: `⚠️/🔗/🆕`.
- 📦 **echo-back مضغوط** في الشات مع جدول البنود + الأثر المحاسبي + الافتراضات.

### المرحلة 2 — الأزرار السياقية + التعديل الآمن قبل الاعتماد
- 🛠️ **POST `/api/runtime/drafts/{id}/patch`**: تعديل حقول مسودة شراء معلّقة قبل الاعتماد. العمليات: `set_payment_method`، `set_vat_mode`، `add_item`، `remove_item`، `set_supplier_name`، `set_supplier_id`. يُعيد تشغيل الـ resolver لتحديث `_echo` و`_assumptions` تلقائياً. يُرفض بعد الالتزام (`immutable_state`).
- 🆕 **POST `/api/runtime/drafts/{id}/spawn_supplier`**: إنشاء مورد جديد فوري + Auto-commit (زر الإضافة الصريح = التأكيد) + تحديث `supplier.id` في مسودة الشراء الأصلية.
- 🔘 **الأزرار السياقية في `ApprovalCard`** لنية الشراء (5 أزرار):
   - `✓ اعتماد` / `✗ رفض` (دائماً)
   - `↔ نقدي/تحويل` (تبديل طريقة الدفع)
   - `➕ إضافة ضريبة 15%` أو `🚫 بدون ضريبة` (تبديل VAT)
   - `➕ إضافة المورد «الاسم»` (يظهر عند is_new أو supplier_id غائب)
- ✅ **اختبارات API حرفية e2e**:
   - `اشتري من راكان قلب مستوبيشي L200 بسعر 1300. نقدي` → 1 مسودة فقط، القيد 007/003
   - PATCH cash→transfer → القيد يتحدث إلى 007/004 تلقائياً
   - PATCH set_vat_mode=excluded → gross يعاد حسابه (net + 15%)
   - spawn_supplier → مورد جديد يُنشأ ويُلتزم + supplier_id مربوط في مسودة الشراء

## CHANGELOG — 2026-07-02 · تأمين المنصة 100% (حارس مصادقة عام) + مهلات LLM + تحسين UX الاعتمادات + تنظيف
**مختبَر 100% (iteration_246: خلفية 17/17 أمان + كاترينا + أربع أعين، واجهة 95%)**
- 🔴 **ثغرة أمنية حرجة أُغلقت**: كانت **كل** نقاط `/api/*` مكشوفة بلا مصادقة (تسريب `/api/users` بصلاحياته، كتابة على القاعدة بلا تسجيل دخول). أضفتُ **حارس مصادقة عام** (`auth_guard.py`) داخل `SecurityHeadersAndRateLimitMiddleware` (pure-ASGI) يفرض JWT صالحاً على كل `/api/*` عدا قائمة بيضاء صريحة: OPTIONS، `/health`، `/api/health`، `/api/auth/login|refresh|logout`، `/api/approvals/public/*`. يقبل Bearer أو كوكي access_token. ردود 401 تحمل ترويسات CORS (لا تكسر تدفق التحديث في الواجهة).
- ⏱️ **مهلات LLM صريحة**: `asyncio.wait_for` (افتراضي 60ث عبر `LLM_TIMEOUT_SECONDS`) على `assistant_kernel._llm_generate` و`llm_intent_parser` — يمنع تعليق الطلبات عند بطء المزوّد.
- 🧹 **تنظيف**: حذف 28 حساب مورد اختباري `DDD-TEST-*` (تبقّى 179 حساباً)، وتنظيف كل بيانات اختبار QA (قيود/عملاء/اعتمادات) — الدفتر 8 قيود = 13,550، الصحة 100/100، 0 اعتماد معلّق.
- ✨ **UX صندوق اعتمادات كاترينا**: تأكيد قبل الاعتماد (confirm)، تسمية ودّية للمُقترِح الآلي (`auto:llm` → «كاترينا (طلب آلي)»)، وعرض الأثر المحاسبي المتوقّع لكل قيد.
- 📱 **كشف حساب واتساب محسّن**: رسالة كشف مفصّلة (مدين/دائن/آجل/رصيد مستحق) مع معاينة قابلة للتحرير قبل الإرسال عبر wa.me (المستخدم اختار: مجاني مع معاينة، لكشف الحساب والفاتورة).
- 🔐 **تدقيق الترابط والقدرات**: كاترينا تعمل بكامل قدراتها بعد التأمين (قراءة/بحث/إنشاء عميل/مصروف/فاتورة/تحصيل + دورة أربع أعين كاملة)، وكل الصفحات تحمّل بياناتها مع التوكن. لا ثغرات/أعطال مكتشفة على السطح المُختبَر.

## CHANGELOG — 2026-07-01 (ج) · إصلاح «كاترينا لا تعمل»: صندوق اعتمادات الأربع أعين + هوية JWT + إغلاق ثغرات RBAC
**مختبَر 100% (iteration_245: خلفية 11/11، واجهة كاملة)**
- **الجذر الحقيقي للشكوى**: أوامر كاترينا المالية تتعلق على «أربع أعين» ولا واجهة لاعتمادها — 26 عملية معلقة غير مرئية، وصفحة «مركز التحكم المالي» بأكملها كانت **يتيمة (غير مربوطة بأي مسار)**، وحزمة `financial_control` الخلفية **غير مركّبة في server.py**.
- **صندوق «اعتمادات كاترينا»** الجديد: تبويب رابع في `/financial-control` (KatrinaApprovalsTab.jsx) يعرض `/api/runtime/approvals` ببطاقات عربية (النوع/الطرف/المبلغ/المُقترِح) وأزرار «اعتماد وتنفيذ»/«رفض» + شارة عدّاد حمراء. الاعتماد يلتزم فوراً (auto-commit).
- **هوية الأربع أعين من JWT**: `/api/assistant/chat` و`/chat/stream` و`/api/runtime/execute` تشتق `proposer` من التوكن الموقّع (كانت من جسم الطلب القابل للانتحال → auto:llm). الاعتمادات الجديدة تحمل اسم المستخدم الحقيقي.
- **إغلاق ثغرة تجاوز الأربع أعين**: نقاط alias `/api/runtime/approve|commit|rollback/{id}` كانت بلا أي RBAC (approver افتراضي bot_reviewer!) — الآن جميعها تتطلب JWT + دور اعتماد. نقطة reject تسمح فقط للمعتمدين أو صاحب الطلب (إلغاء ذاتي).
- **أكواد بوت مالية ديناميكية**: `core/financial_actions.py` يحل الأكواد من `chart_resolver` (مصروف→035 مصروفات عامة وإدارية بدل 030 الخاطئ، إيراد فاتورة→026)، ونصوص echo-back في `unified_executor` تعرض الأكواد الحية.
- **صلاحيات المسار**: `/financial-control` متاح لأدوار الاعتماد (admin/manager/supervisor) حتى بدون reports.view — كان المشرف «احمد1» (المعتمِد الثاني) لا يستطيع رؤية الصفحة أصلاً (تعطيل بنيوي للأربع أعين). Sidebar بند «✅ الرقابة والاعتمادات» بدعم roles.
- إصلاح firewall `_parse_iso` (تواريخ DATE بلا timezone) وكاشف تطابق البنود (price×qty).
- تنظيف كامل لبيانات الاختبار (قيود/عملاء/اعتمادات TEST) — الدفتر 8 قيود = 13,550، الصحة 100/100، 26 اعتماداً معلقاً حقيقياً بانتظار مراجعة المستخدم.
- Regression suite جديد: `/app/backend/tests/test_katrina_four_eyes_iter245.py` (11 اختبار).
- ملاحظة: الاعتمادات الـ26 القديمة تظهر proposer=auto:llm (سابقة لإصلاح الهوية) — الجديدة تحمل الاسم الحقيقي.

## CHANGELOG — 2026-07-01 (ب) · إصلاح إزاحة أكواد الدليل + قيود الآجل الثمانية + تدقيق v1.0 (13/13)
**مختبَر 100% (iteration_244: خلفية 8/8، واجهة 11/11) + تدقيق v1.0 (13/13)**
- **السبب الجذري لأكواد قديمة**: جدول accounts أُعيد ترقيمه سابقاً (حذف حساب أزاح الأكواد -1، وresequence حوّل 0421→167 و211→166) بينما بقيت خرائط الكود على الترقيم القديم.
- **محلّل ديناميكي جديد** `core/chart_resolver.py`: يحوّل الحساب الدلالي (بالمعرّف الثابت acc-1101... أو الاسم) إلى الكود الحالي من الجدول الحي (كاش 30ث) — مسار الكتابة محصّن ضد أي إعادة ترقيم مستقبلية.
- **الأكواد الحالية المعتمدة**: نقد 003، بنك 004، عملاء 005، POS 006، مخزون قطع 007، مسحوبات مالك 021، الإيرادات 024، إيرادات خدمات 025، خدمات ميكانيكية 026، إصلاح محركات 027، فرامل 028، تكلفة خدمات 029، مصروفات عامة 035، رواتب 036، ايراد قطع الورشه 041 (كان 042)، تكلفة قطع الورشة 167 (كان 0421)، فروقات ترحيل 166 (كان 211)، موردون 2101.
- **تصحيح كل الخرائط الثابتة**: routes_extended (ACCOUNT_NAME_MAP، LEGACY_TO_NEW_CODE، ACCOUNT_ID_TO_CODE، _infer_revenue_code→026/027، COGS→167/007، خصم→024)، routes_finance (_LEGACY_CODE_MAP، _infer_account_type_from_code بنطاقات حية: 24-28 إيراد +41، 29-48 مصروف +167، 49-128 عملاء، 129-165 موردون، migrate/reclassify endpoints)، firewall_engine (_account_type يقرأ نوع الحساب من الجدول الحي)، routes_smart_accounting، والواجهة (displayLabels، UnifiedBotWidget، PartsDashboard، OperationCard، VehicleDetails revenueAccountCode→041).
- **fix-all بوضع معاينة**: `POST /api/operations/integrity/fix-all {"dry_run": true}` يعرض القيود المخططة دون حفظ؛ التنفيذ يمرّ عبر `_build_operation_journal_entry` (نفس منطق إنشاء العمليات — SSOT) ثم AccountingEngine (توازن + idempotency).
- **قيود الآجل الثمانية نُفّذت بموافقة المستخدم**: 13,550 ر.س — مدين 005 العملاء / دائن 026 أو 027 (توضيب) لكل عملية بمرجعها. التدفق النقدي = صفر (استحقاق).
- **إصلاحات firewall**: _parse_iso يعالج تواريخ DATE بدون timezone؛ كاشف عدم تطابق البنود يحسب price×qty عند غياب total (أزال تنبيهين زائفين). الصحة الآن 100/100 وتنبيه وحيد مشروع (ذمم مفتوحة).
- **الميزانية العمومية**: صافي دخل الفترة يُرحّل تلقائياً لحقوق الملكية (023) — أصول 13,550 = خصوم+حقوق 13,550.
- **تدقيق v1.0**: سكربت `/app/backend/tests/test_accounting_integrity_v1.py` — 13/13 (SSOT، قيد لكل عملية، توازن، لا يتائم، آجل→ذمم، تدفق يستثني الآجل، ميزان، قائمة دخل، دفتر ذمم=13,550، أكواد حية، ميزانية متوازنة، idempotency، لا تكرار). التقرير: `/app/test_reports/accounting_integrity_v1_audit.json`.
- Regression: `/app/backend/tests/test_finance_alignment_iter244.py` (8/8).
- إصلاح ثانوي: زر داخل زر في RecentOperationsWidget (تحذير React DOM).
- ملاحظة بيانات: جدول accounts فيه حسابات موردين اختبارية `DDD-TEST-*` (تلوث من اختبارات سابقة) — مرشحة للتنظيف.

## CHANGELOG — 2026-07-01 (أ) · توحيد مصدر الحقيقة المالية + حوكمة كاترينا المرحلة C (منع الأوامر الوهمية)
المستخدم أبلغ عن: (1) تضارب التنبيهات — صفحة العمليات تعرض 3 تنبيهات بينما الجدار/البوت 0، (2) كاترينا تنفّذ أوامر وهمية
(ادّعت "تم إضافة المورّد بنجاح" بدون أي أداة، حفظت عميل "بدون اسم"، وPower Mode فسّر رقم الجوال كمبلغ 55,555,555).
**تم — مختبَر 10/10 (iteration_243, 100%):**
- **توحيد المصدر (SSOT = FirewallEngine)**: `/api/finance/alerts` أصبح يُشتق كاملاً من `firewall_engine.run_full_analysis()`
  — نفس التنبيهات/الصحة/التدفق النقدي في: شريط «مراقب المحاسبة» (العمليات + لوحة التحكم + الذمم)، جدار الحماية، والبوت.
- **محرك الجدار اكتسب كواشف جديدة**: `analyze_profitability` (هامش/خسارة من القيود آخر 30 يوم بنافذة timedelta صحيحة —
  النافذة القديمة `replace(day=...)` كانت معطوبة)، `detect_missing_journal_entries` (عمليات مالية بدون قيود — كشف فعلياً
  8 عمليات بـ13,550 ر.س بدون أي قيد لأن جدول journal_entries فارغ حالياً)، `detect_open_receivables` (ذمم مدينة/دائنة).
  معيار الصحة `audit_coverage` (placeholder) → `profitability` (الواجهة حُدّثت: HealthScoreGauge label «الربحية»).
- **حوكمة كاترينا المرحلة C**: الإجراءات الآمنة (عميل/مركبة/زيارة/مورد/تعديل) لم تعد auto-commit —
  ترجع `awaiting_confirmation` مع echo-back، والتثبيت فقط عند رد المستخدم «نعم» (و«لا» يلغي). المسودة المعلّقة في
  shared_memory per-session. المالية (فاتورة/دفعة/مصروف/عكس) تبقى أربع أعين pending_approval بلا تغيير.
- **create_supplier حقيقي end-to-end**: intent LLM + regex fallback + commit متزامن إلى `uploads/suppliers.json`
  (جدول suppliers غير موجود في Supabase) + فحص تكرار + إبطال كاش — يظهر فوراً في GET /api/suppliers وصفحة /suppliers.
- **حارس الاسم الإلزامي**: create_customer/create_supplier بدون اسم → needs_clarification («ما اسم العميل/المورّد؟»)
  بدل حفظ «بدون اسم». حُذف السجل الوهمي القديم (ddbae1b7).
- **إصلاح استخراج الكيانات في Power Mode**: الجوال يُلتقط أولاً (05\d{7,9} يشمل الأرقام الناقصة)، المبلغ بكلمة مفتاحية
  (بقيمة/بمبلغ/بسعر) قبل اللوحة، واللوحة بـ negative-lookahead لكلمات (جوال/ريال/باسم...). «بقيمة 4500 ... جوال 0555555555»
  → amount=4500 وphone منفصل.
- **تحصين برومبت الصدق**: ممنوع على الـLLM ادعاء تنفيذ أي كتابة — رسالة «✅ تم بنجاح» تصدر من المحرك فقط.
- Frontend: FinanceAlertsWidget يعرض شريحة الصحة `alerts-health-chip` (92/100) + skeleton أثناء التحميل، ويظهر الآن
  أيضاً على `/` و`/debts-followup`. AssistantProvider يدعم `awaiting_confirmation` و`d.ask`.
- ملفات: firewall_engine.py، routes_finance.py (/alerts)، core/{unified_executor,assistant_kernel,action_runtime,power_mode,llm_intent_parser}.py،
  frontend FinanceAlertsWidget.jsx، useFinanceAlerts.js، AssistantProvider.jsx، HealthScoreGauge.jsx.
- Regression file: /app/backend/tests/test_bot_governance_phase_c_iter243.py (10/10).
- ملاحظة بيانات (ليست خطأ كود): جدول journal_entries في Supabase فارغ حالياً بينما توجد 8 عمليات — التنبيه الأول
  الموحّد يرشد المستخدم لتشغيل «تصحيح القيود المفقودة» (POST /api/operations/integrity/fix-all) من مركز الجدار.

## CHANGELOG — 2026-06-20 (سابق) · JWT RBAC + محرك المحاسبة + بوت مالي بأربع أعين
- ترحيل JWT RBAC كامل (P0)، حصر CORS، إزالة autoprofit-pro، إصلاح race تسجيل الدخول.
- `AccountingEngine.reverse()` قيود عكسية (لا حذف نهائي)؛ حوكمة البوت A+B: إجراءات مالية عبر البوت echo-back + أربع أعين
  (21/21 اختبار — iterations 240-242).

## Core Requirements
- Strict double-entry accounting + Single-Writer AccountingEngine (journal_entries محمي من الكتابة المباشرة)
- Four-Eyes حقيقي للإجراءات المالية والحذف؛ Level-1 confirm-first للإجراءات الآمنة (المرحلة C ✅)
- مصدر حقيقة مالي واحد: FirewallEngine (تنبيهات/صحة/تدفق/ربحية) ✅
- Smart POS Journal Entries / Smart Inventory with COGS / Idempotency
- RBAC (name-only login by design + JWT)

## User Personas
- **مدير** — admin (يعتمد) | **احمد1** — supervisor (يعتمد) | **فرج1** — accountant (لا يعتمد) | **مستخدم اختبار** — technician

## Tech Stack
React 18.3.1 (CRA) + FastAPI + Supabase (relational) + MongoDB (state/audit) + Emergent LLM Key (claude-sonnet-4-6)

## Key API endpoints
- POST /api/auth/login {username} → JWT (httpOnly cookies + Bearer)
- GET /api/finance/alerts?workshop_id= → موحّد من FirewallEngine {alerts, health, cash_flow, profitability, source}
- GET /api/firewall/dashboard?workshop_id= → نفس المصدر
- POST /api/assistant/chat {message, session_id, proposer} → envelope {success, data:{response, executed, cards...}}
- POST /api/runtime/execute {text, proposer, session_id} → status: committed|awaiting_confirmation|pending_approval|needs_clarification|read_only|rejected
- POST /api/finance-actions/{invoice|payment|expense|reverse} (RBAC JWT)
- POST /api/operations/integrity/fix-all (إعادة إنشاء القيود المفقودة)

## Backlog (مرتّب)
- **P0 (RRR المرحلة 2 — بشرط مسبق)**: Memory Engine الطبقي — لا يُبنى قبل تعريف قواعد الترقية Short→Long→Knowledge كتابةً (قرار المستخدم). القياس الحالي: حقن كامل ≈14.6K token و~55s رد — يُرجّح top-k retrieval.
- **P0 (بانتظار المستخدم)**: مراجعة الـ26 اعتماداً المعلقاً في صندوق اعتمادات كاترينا؛ اختيار طريقة واتساب لكشوف حسابات العملاء (wa.me مجاني أو Twilio API)
- **P1**: كشف حساب عميل عبر واتساب من صفحة الذمم + ربط أمر «أرسلي كشف حساب» بكاترينا
- **P1**: تنقيح البيانات الحساسة قبل إرسالها للـLLM
- **P1 (منجز جزئياً)**: Decimal في محرك المحاسبة تم ✅ (PRD v1.1، 58 اختباراً) — يتبقى توسيعه لاحقاً إلى routes_finance/firewall عند الحاجة
- **P1**: refactor server.py / routes_finance.py (224KB) / routes_extended.py (212KB)
- **P2**: تحسين UX صفحة الرقابة المالية/الاعتمادات؛ عرض أرقام تذاكر/زيارات قصيرة في ردود البوت (تم للفواتير INVxxxxx)
- **P2**: ربط whatsapp.send بموجه نوايا البوت؛ deep-links سياقية (?pos= ?part=)؛ Ollama fallback معطوب في بيئة المعاينة
- **P3**: تقسيم مكونات React الضخمة (VehicleDetails 4510 سطر، Operations 3835)؛ CRA→Vite

## Known Status
- journal_entries (Supabase): 8 قيود آجل ✅ (13,550) — الصحة 100/100، تنبيه وحيد: ذمم مفتوحة. 0 اعتماد معلّق.
- **أمان**: كل `/api/*` محمي بـJWT عبر حارس مصادقة عام. أدوات البوت الداخلية تستخدم توكن خدمة موقّعاً (tool_router._int_headers).
- **بوت كاترينا (2 يوليو 2026)**: يرى كل البيانات ✅، يبحث بأرقام الفواتير ✅، ينشئ زيارة كاملة (عميل+مركبة+بند) ✅، يثبّت فاتورة عبر أربع أعين → عملية+قيد متوازن ✅.
- **Developer Mode RRR (2 يوليو 2026)**: أمر `rrr` (admin فقط) يفعّل وضع المطور — سياق مؤسسي كامل + Proposals تفصيلية بلا أي تعديل كود. `rrr off` للإيقاف. قرارات المستخدم: Proposals فقط، Git/pytest خارج النطاق، المرحلة 2 (Memory Engine) مشروطة بتعريف قواعد الترقية كتابةً (وُثقت في ROADMAP.md).
- **PRD Decimal v1.1 (2 يوليو 2026)**: محرك المحاسبة يحسب بـ Decimal حصراً — توازن صارم بلا سماحية، رفض صريح للقيم التالفة/السالبة/الصفرية، Hash Stability محفوظ (_norm_amount للبصمة فقط)، حساب فروق تقريب ضريبية 179 + vat_rounding_account في إعدادات Mongo، حزمة 58 اختباراً إلزامياً ناجحة بالكامل.
- suppliers لا جدول له في Supabase — المخزن الفعلي uploads/suppliers.json (fallback معتمد).
- accounts: حسابات DDD-TEST نُظّفت (179 حساباً). سجل الاعتمادات التاريخي يحوي بقايا اختبار محلولة (غير مؤثّرة، pending=0).
- whatsapp: روابط wa.me مع معاينة (كشف حساب في صفحة الذمم). فاتورة واتساب بمعاينة: تحسين مقترح لاحق.
- 89 npm vulnerabilities كلها في build tooling (تحتاج CRA→Vite).

## Security Status (20 Jun 2026) — كما هو
JWT RBAC ✅ | deny-by-default ✅ | CORS مقيّد ✅ | refresh tokens ✅
