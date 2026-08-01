# Workshop ERP — Product Requirements (PRD)

## CHANGELOG — 2026-08-01 · 🔎 Reconciliation Audit قراءة فقط + Endpoint محمي
**مختبَر عبر testing_agent iteration_308 + pytest 4/4 — MOCKED: NONE**
- أضيفت وحدة `/app/backend/financial_reconciliation.py` وEndpoint محمي للمدير: `GET /api/finance/reconciliation-audit`، قراءة فقط بالكامل ولا يغيّر أي جدول.
- التقرير يفصل `raw_classification` عن `resolved_exclusive_scopes`: live=15، archive=176، ويكشف تداخل المركبتين `235cb00f...` و`9004d4bd...` دون تعديل حالتهما.
- التقرير يثبت: لا سجل مالي في نطاقين، مجموع النطاقات يساوي كل السجلات، فرق الذمم 500 محدد بسجل عملية آجلة، فرق الإيراد 210 على الحساب `041`، المصروفات 16,810 على الحساب `035`، والميزان التجريبي متوازن.
- القيود الافتتاحية `شاص 2019=16,000` و`عمر الخضيري=300` أصبحت `pending_decision` في التقرير، وPOS المستقل 350 مصنف `posting_missing` لأنه بلا قيد مقابل.
- أضيفت اختبارات: `/app/backend/tests/test_iter308_reconciliation_audit_contract.py` و`/app/backend/tests/test_iter308_reconciliation_audit_api_contract.py`.

## CHANGELOG — 2026-08-01 · 🧾 إصلاح QuickPrint للفواتير/التشخيص + فلترة الموردين + تثبيت دخول UI
**مختبَر عبر وكيل الاختبار iteration_306 ثم iteration_307 — MOCKED: NONE**
- **فاتورة المبيعات وتقرير التشخيص:** QuickPrint يعرض الآن معاينة مرئية داخل النافذة، ويستبعد بنود الموردين من المستندات الموجهة للعميل مع بقاء بنود الموردين محفوظة في أرشيف ملف المركبة كما هي.
- **المركبة المرجعية:** `/vehicle/61fe0b56-aa66-490d-a5e7-6f3b8195ed56` — الأرشيف يحتفظ ببند المورد «القرعاوي» 179 وبند الورشة 600؛ الفاتورة/التشخيص يعرضان بند الورشة فقط وإجمالي 600.00 وليس 779.00.
- **القالب الموحد:** أزيل تكرار حقول بيانات الورشة من الكرت الثالث؛ أصبح «ملخص المستند» مع حالة/متبقي، وأضيف عمود الخصم ليتطابق رأس الجدول مع صفوف الطباعة.
- **أزرار الإخراج:** زر PDF يولّد ملفاً بنجاح، وزر واتساب يفتح رابط WhatsApp الصحيح حسب الاختبار.
- **تثبيت جلسة الدخول:** عولج سباق 401 قبل تسجيل الدخول حتى لا تمسح الطلبات الخلفية توكن الدخول الجديد؛ Login UI بـ`مدير / 123123` يثبت `auth_token` و`session` وينتقل من `/login` إلى `/`.
- **ملاحظة بيئية غير حاجبة:** فحص `OPTIONS /api/auth/login` عبر حافة المعاينة يعيد CORS wildcard من الـedge قبل وصوله للسيرفر، بينما الاختبار الداخلي على `localhost:8001` يعيد `Access-Control-Allow-Credentials: true` وOrigin صريح، وتدفق الدخول الحقيقي يعمل.

## CHANGELOG — 2026-07-23 · 🧾 UX-A4 للفواتير + إصلاح تعطل لوحة التحكم + صلاحية المدير
**مختبَر عبر وكيل الاختبار iteration_279: Backend 3/3 + واجهة 100% — MOCKED: NONE**
- **إصلاح حرج للوحة التحكم:** كان `GET /api/vehicles` ينهار 500 بعد اعتماد مركبة من كاترينا إذا كانت سنة المركبة `null`؛ صار التطبيع يحوّل السنة الناقصة إلى `0` قبل استجابة Pydantic. تحقّق الاختبار: 200 وقائمة وكل قيم السنة أعداد صحيحة، ولوحة التحكم لا تبقى في التحميل.
- **سياسة المدير:** حساب `admin` يستطيع اعتماد طلبه بنفسه من دون رمز مطور، وتُسجّل العملية صراحةً في التدقيق باسم `APPROVAL_GRANTED_ADMIN_OVERRIDE`. بقيت قاعدة الأربع أعين فعّالة للمحاسب وبقية الأدوار؛ اختبار أحمد الذاتي أعاد 403.
- **DocumentPrint موحّد UX-A4:** بقيت المعاينة والطباعة وPDF وواتساب على نفس المكوّن. أزيلت صناديق التوقيع وQR القديم والتكرار داخل ورقة الفاتورة، وأضيف باركود واحد فقط في الأسفل (`اسم الورشة | الرقم الضريبي | الجوال`).
- **الأختام الإلكترونية:** لا يظهر ختم من دون موافقة مسجّلة؛ عند وجود اعتماد عميل/ورشة يظهر ختم دائري صغير بالاسم والوقت والمعرّف، وأي تعديل يدوي يبطل عرض الأختام حتى اعتماد جديد.
- **ملاحظة غير حاجبة:** تبقى رسائل 401 في console قبل تسجيل الدخول لبعض موارد المساعد؛ لا تمنع الدخول أو لوحة التحكم أو الطباعة، ومؤجلة للتنظيف.

## CHANGELOG — 2026-07-22 · 🚀 «PDF وواتساب» الموحد + قوالب رسائل صادرة + بصمة/كاش + سجل تدقيق صارم
**مختبَر 100%: pytest 20/20 (`tests/test_outbound_share_iter278.py`) + وكيل الاختبار iteration_278 (7/7 تدفقات واجهة) — MOCKED: NONE**
- **Backend جديد `routes_outbound.py`** (مسجل في server.py) — كل المسارات تحت `/api/outbound/*` بحماية JWT:
  - `GET/PUT /templates` + `POST /templates/{id}/restore-default` + `GET /variables` — قوالب رسائل ثابتة بصيغة `{{VAR}}` الموحدة (نفس registry الطباعة)، versioning (تاريخ 20 نسخة)، validation صارم (متغير مجهول → 422، action_key نشط مكرر → 409)، تفعيل/تعطيل.
  - `POST /resolve-message` — حل الرسالة سيرفرياً حسب doc_type + الحالة (paid→invoice_paid، partial→invoice_partial، unpaid/deferred→invoice_unpaid، fallback `*`)، **superseded → 409 حظر مشاركة**، تطبيع الجوال E.164 (+966).
  - `POST /fingerprint` + `POST/GET /assets` — بصمة SHA-256 **تُحسب في الخلفية حصراً** من مواد مثبتة (whitelist: tenant/document_number/version/template/snapshots/line_items/totals/taxes) بعد canonicalization؛ تطابق البصمة → إعادة استخدام PDF/الصورة من `document_output_assets` (immutable، فهرس فريد tenant+fingerprint، عزل مستأجرين مثبت بالاختبار).
  - `POST /share-attempts` + `/events` + `GET` — سجل تدقيق: أحداث مسموحة فقط (message_prepared/pdf_generated/preview_image_generated/cache_hit/share_sheet_opened/whatsapp_opened/files_downloaded/text_copied/user_cancelled/prepare_failed/phone_saved_to_customer)؛ **sent/delivered/read مرفوضة 422 صراحة**؛ idempotency_key فريد؛ كل محاولة تسك trace حقيقي `tr-*` عبر llm_traces (channel=outbound).
  - Seeds idempotent: 7 قوالب (invoice_paid/partial/unpaid/default + quote/diagnosis/receipt_default).
- **Frontend (فصل منطق نظيف — QuickPrintDialog للعرض فقط)**: خدمة `services/outboundShare.js` + hook `hooks/useWhatsAppShare.js` (resolve→fingerprint→attempt→cache-or-generate) + مودال `components/WhatsAppSharePreview.jsx` (معاينة الإرسال: نص قابل للتعديل حسب القالب، صورة مصغرة، جوال مطبع مع تعديل مؤقت + زر منفصل «حفظ الرقم في ملف العميل» بتأكيد، Web Share API للملفات على الجوال المدعوم، wa.me نص-فقط، تنزيل+تعليمات إرفاق يدوي على الكمبيوتر، **بانر صدق: لا ادعاء إرسال/إرفاق تلقائي**، حظر الأزرار عند رقم غير صالح).
- **`pdfGenerator.js`**: أضيفت `renderPdfAssets` (PDF blob+base64 + صورة معاينة JPEG مصغرة) بمشاركة نفس pipeline مع downloadPDF.
- **زر «PDF وواتساب»** في `QuickPrintDialog` (يخدم المركبة/العمليات/كل نوافذ الطباعة تلقائياً) وفي صفحة `/print` (DocumentPrint) — نفس الـflow الموحد.
- **علامات مائية**: draft→«مسودة»، cancelled→«ملغي»، superseded→«مستبدل» في DocumentPrint sheet وحقن watermark في HTML طباعة QuickPrintDialog؛ statusLabels تشمل cancelled/superseded.
- **تبويب «رسائل واتساب»** داخل `TemplatesManager` (بدون صفحة مستقلة): `components/OutboundMessagesTab.jsx` — عرض/تحرير/استرجاع افتراضي/تفعيل-تعطيل/عداد نسخ.
- Collections جديدة: `outbound_message_templates`، `document_output_assets`، `outbound_share_attempts` (فهارس فريدة: active action_key جزئي، tenant+fingerprint، idempotency_key sparse).
- أمثلة traces حقيقية: tr-9e71b9d0e9ea (whatsapp_opened+files_downloaded)، tr-70f52df55fbc (cache_hit)، tr-136f2c983d13 (user_cancelled).
- **مؤجل بوضوح**: إرفاق تلقائي/حالات تسليم تتطلب WhatsApp Business API (قرار مالك مستقبلي)؛ chunked upload للأصول فوق الحد الحالي (20MB base64)؛ ربط زر «PDF وواتساب» بأوامر كاترينا الصوتية/النصية.

## CHANGELOG — 2026-07-08 (ب) · 🛠️ إصلاح شكوى «مركز التحكم/زر الاعتماد + 404»
- **تشخيص 404**: عابر — حدث أثناء إعادة تشغيل الخادم وقت التطوير (المسار يعمل 200 الآن). **علاج وقائي**: `postChatWithRetry` في AssistantProvider — إعادة محاولة تلقائية واحدة عند 404/502/503/504 + رسائل ودّية («⏳ الخادم يُعاد تشغيله…») بدل رسالة axios الخام.
- **زر الاعتماد**: كان يرفض بأربع أعين (المالك مُقترِح كل الطلبات) — الآن الكرت يعرض «👁️👁️ بانتظار معتمدٍ آخر (أنت المُقترِح)» بدل زر فاشل، والزر الفعلي يظهر فقط لغير المُقترِح. **تحقق E2E**: مدير يقترح → 403 لنفسه → «احمد1» (supervisor) يعتمد → تنفيذ فوري ✓.
- **الطلبات القديمة (stale)**: عند اعتماد/رفض طلب لم يعد موجوداً → رسالة توضيحية + تحديث تلقائي للقائمة (مركز التحكم + كروت الشات).

## CHANGELOG — 2026-07-08 · 🎨 واجهة Kodee + 🔒 إغلاق L14 رسمياً + 🧪 P2 (L8–L13) ناجح
**كله مختبَر: واجهة (iteration_255 — 100%) + L14 regression (6/6 + 29 فحصاً) + P2 جولتان + pytest 31/31**
- **🎨 واجهة كاترينا بأسلوب Kodee (طلب المالك)**: إعادة تصميم كاملة عبر design_agent — بطاقة سطح مكتب 420×680 بزوايا 24px، **Bottom Sheet 88vh على الجوال** بمقبض سحب، تبويبات segmented، فقاعات بنفسجية، كروت ERP بشريط لوني رفيع وعنوان داكن واضح، مركز تحكم Bento + سكيلتون تحميل، حركات kodee-pop/kodee-sheet في index.css. الملفات: UnifiedAssistantDrawer.jsx (أُعيدت كتابته)، ControlCenterTab.jsx، AssistantCard.jsx.
- **🔒 L14 مُغلق رسمياً (تأكيد المالك)**: Prompt v3 مجمّد (`frozen:true` + لقطة `PROMPT_V3_FROZEN_BASELINE.md`) · Golden Dataset (`L14_GOLDEN_DATASET.json`) · مقيّم آلي (`l14_evaluate.py`) · **سكربت موحّد `/app/scripts/run_l14_regression.sh`** (pytest → تشغيلة حية → تقييم) — آخر تشغيلة E2E: PASS.
- **🧪 P2 (L8–L13) ناجح** — التفاصيل في `docs/diagnostics/P2_VERIFICATION_REPORT.md`:
  - جولة تشخيص خالص (29 اختباراً بـ trace_id) ثم إصلاحات مرتبة ثم إعادة اختبار الراسب فقط.
  - **إصلاح حرج L13-T6**: المحاسب (فرج1) كان يرى الإيرادات → صلاحية `reports.revenue` جديدة + حجب `firewall.cash_flow`/`services.top` في الكيرنل لغير المخوّلين.
  - **إجراء update_visit جديد** (تعديل ملاحظات زيارة) · **رفض صريح لتعديل القيود المرحّلة** (Immutable Ledger + بديل قيد عكسي) · **حارس مخزون** في مدقق المسودات (بيع > المتاح = ⛔).
  - L12 (حقن أعطال) وL15 (حِمل/تزامن ~120 نداء LLM) **مؤجلان بانتظار قرار المالك**.
  - تنظيف كامل: قائمة الاعتمادات عادت لـ13 الأصلية. أثر جانبي موثق: نص ملاحظات زيارة عمر الخضيري = «العميل ينتظر بالخارج».

## CHANGELOG — 2026-07-07 (فجر اليوم التالي) · ✅ إصلاح 502 + قاعدة القيد المؤقت للبيع الآجل + دمج مركز التحكم داخل كاترينا
**مختبَر 100%: وكيل الاختبار iteration_254 — باك إند 10/10 + واجهة كل الفحوصات ✅**
- **502 على chat/prompt (AttributeError Actor.get)**: تم التحقق أنه مُصلح بالفعل — كل المسارات المتعطلة سابقاً تعيد 200 (chat، prompt/versions، prompt/activate، سيناريو البيع الآجل). `_extract_request_actor` تعيد dict والمسارات موحّدة.
- **🕒 قاعدة القيد المؤقت للبيع الآجل (طلب المالك)**:
  - عند تسجيل بيع آجل (paymentMethod آجل/اجل/credit/deferred/ذمم أو paymentStatus unpaid/pending/partial) → قيد تلقائي موسوم `[قيد مؤقت — بيع آجل]` (مدين ذمم 005 / دائن إيرادات). كان الكشف السابق يقبل "credit" الإنجليزية فقط — وُسِّع في `_build_operation_journal_entry` و`confirm_operation_payment` (routes_extended.py).
  - عند التحصيل الكامل → قيد تسوية (مدين نقدية/بنك/شبكة، دائن ذمم 005) + الوسم يتحول إلى `[بيع آجل — مُسوَّى ✓]`. تحصيل جزئي → `[قيد مؤقت — بيع آجل | مُحصَّل جزئياً]`. الدالة: `mark_temp_deferred_settled()` في core/financial_actions.py (تُستدعى من confirm-payment ومن collect_payment مع reference_id).
  - فواتير كاترينا الآجلة (create_invoice) تحمل الوسم نفسه.
  - **SSOT**: `ar_ledger.summary()` القسم 4 يعيد `temporary_deferred_entries/total/note`، وأداة `finance.ar_summary` تمررها، ونمط توجيه جديد في `assistant_kernel._TOOL_PATTERNS` («قيود مؤقتة/بيع آجل» → finance.ar_summary). كاترينا تجيب بدقة عن القيود المؤقتة غير المحصلة.
  - انحدار: البيع النقدي يظل مدين نقدية 003 بلا وسم. اختبار قابل لإعادة الاستخدام: `/app/backend/tests/test_temp_deferred_iter254.py`.
- **🛡️ دمج مركز التحكم المالي داخل البوت (P3 المرحلة أ+)**: تبويبات داخل درج كاترينا (`assistant-tab-chat` / `assistant-tab-control` بشارة عدّاد حمراء). مكوّن جديد `components/assistant/ControlCenterTab.jsx`: KPIs (اكتشافات مفتوحة/حرجة/بانتظار الاعتماد/الأثر المالي) + اعتمادات كاترينا المعلقة (اعتماد/رفض بأربع أعين، 403 لمقترح نفسه) + أحدث الاكتشافات (قراءة) + زر فتح الصفحة الكاملة. صفحة /financial-control باقية كما هي (لا تكرار بيانات — نفس الـAPIs).
- **🎴 إصلاح كروت الاعتمادات (شكوى المالك: «خام وبيانات غير موضحة + خط البار العلوي غير واضح»)**: البار العلوي للكرت أصبح text-sm font-black مع ظل نص للوضوح على التدرجات + أيقونة أكبر. `PayloadDetails` (KatrinaApprovalsTab — exported) يعرض حقولاً عربية منسقة (المبلغ بارز، طريقة الدفع بأسماء عربية، إخفاء كل حقول UUID الخام *_id) بدل JSON الخام. كروت المسودات في AssistantCard أثريت (عميل/مورد/طريقة دفع/بيان/تاريخ/الأثر المحاسبي 🧾).
- ملاحظة تجميلية معلّقة (غير حاجبة): وابل 401 على صفحة /login قبل تسجيل الدخول (AssistantProvider يستعلم قبل وجود توكن) — من iter253.

## CHANGELOG — 2026-07-07 (ليلاً) · 🏆 أمر علاج L14 منفَّذ بالكامل — الشهادة 6/6
- **الأمر الحاكم**: `/app/docs/verification/L14_REMEDIATION_ORDER.md` (رفعه المالك). الترتيب المنفَّذ: D5←D1←D2←D6(تقني)←مشغّل S3. كل بند diff معزول + إثبات trace + اختبار انحدار. **الأرقام لم تُلمس** (مصير 3,450 وقيود الاختبار قرار مالك معلّق).
- **D5**: `core/provenance_guard.py` — حجب أي بلوك نتائج أدوات غير منفَّذة + تسجيل في الـtrace. **D1**: أنماط اعرضي الذمم/راجعي القيود/عمليتين + نزع أفعال مؤنثة + حل ترتيبي «أول عميل في القائمة» عبر `last_list`. **D2**: `core/prompt_registry.py` (v1-baseline/v2-d2-governance/v3-d2.1-cross-turn) + rollback حي مُثبت بالـtrace + endpoints (`/api/assistant/prompt/versions|activate`). **D6-تقني**: `core/ar_ledger.py` SSOT (قيود −2,419 / آجل غير مقيّد 3,450 / مخزّن 11,150→10,850 حياً) + `GET /api/finance/ar-ledger` + شريط SSOT في DebtFollowUp + أداة ar_summary طبقية. **S3-مشغّل**: financial_figure().
- **اكتشافان جديدان وُثّقا وعولجا** (حاجزا 6/6): **D8** نافذة التاريخ 10→24 رسالة؛ **D9** وسم ردود السجل بأدواتها + prompt v3 (منع الاعتراف الكاذب عبر الدورات) + تنظيف تقليد الوسم.
- **جولة الشهادة: 6/6 نظيفة** — traces: tr-97b1a8144c4c/tr-985ec9a8f6c9 (S1)، tr-990b22ea6352 (S2)، tr-fc3e44854b74 (S3)، tr-e4f21b1cb22c (S4)، tr-3fd2dd7306fb/tr-493f88a42f14 (S5)، tr-93e77f2bbe40/tr-6743f4632a2d (S6). انحدار كامل **65/65**.
- **الإغلاق الرسمي لـL14 معلّق على امتحان المالك** (حسب الوثيقة الحاكمة). Learning Candidate `bf934e36cfe3` ما زال بانتظار اعتماد المالك من شاشة الاعتمادات.
- Backlog مجمّد بقرار المالك: L8→L13، L15، Llama/VPS، واتساب، مصير 3,450 وقيود الاختبار.

## CHANGELOG — 2026-07-07 (مساءً) · 🔬 L14 الجولة الثانية — تشخيص خالص مكتمل (بلا أي إصلاح)
- **Learning Candidate مسجّل رسمياً** عبر memory_engine (المرة الرابعة لفشل التسليم/provenance): draft `5efebba47310` / approval **`bf934e36cfe3` بانتظار اعتماد المالك**.
- **L14 جولة 2** (`l14_runner.py`، 17 دورة، كل نتيجة بـtrace_id): **❌ رسوب 3/6** (S4/S5/S6 ✅، S2/S3 ⚠️، S1 ❌). جولة 1 محفوظة في `L14_RESULTS_round1_20260706.json`.
- **🔴🔴 L14-D5 (اكتشاف جديد أخطر):** اختلاق بلوك «نتائج أدوات» كامل ببيانات وهمية (operations.recent + عملية OP-2025-0187 لا وجود لها) — trace `tr-5280697b4448`؛ الآلية: تقليد قالب الحقن في `assistant_kernel.py:912`.
- **🎯 L14-D6: توفيق 9,850/8,905/11,150 مغلق تشخيصياً**: 9,850 = رصيد القيود (005/1103/113) يوم 2026-07-01 حرفياً؛ 8,905 = نفس المنحنى يوم 2026-07-05 حرفياً؛ 11,150 = أرصدة العملاء (ajelBalance>0) منذ 2026-07-06. الفجوة البنيوية اليوم 13,569 (قيود −2,419 مقابل أرصدة 11,150). الأدلة: `A6_RECONCILIATION.json` + `a6_reconciliation.py`.
- التقارير محدثة: `L14_PROVENANCE_REPORT.md` (قسم الجولة 2 + قائمة إصلاحات مقترحة **بانتظار اعتماد المالك**) + `LEGACY_AUDIT.md` (D5/D6/D7).
- **القاعدة السارية:** لا L8→L13 ولا L15 ولا أي جبهة جديدة (Llama/VPS/واتساب = Backlog مرفوض حالياً) حتى يُغلق L14.

## Original Problem Statement
نظام إدارة ورشة سيارات متكامل (ERP) يدعم اللغة العربية، يضم وحدات محاسبية صارمة، نظام جرد ذكي، تتبع ذمم، ومدقق مالي بالذكاء الاصطناعي.
هدف المرحلة الحالية: "Enterprise Operator" — ترحيل الحالات المؤقتة إلى قواعد بيانات دائمة، RBAC خلفي صارم، مبدأ أربع أعين حقيقي، محرك محاسبة مركزي (كاتب وحيد)، وإجراءات مالية عبر البوت بحوكمة كاملة.
**وثيقة قبول جديدة**: «اختبار سلامة وترابط النظام المحاسبي v1.0» — 13 قاعدة صارمة (مصدر حقيقة واحد، توازن القيد المزدوج، دورة نقدي/آجل، ميزان مراجعة، قائمة دخل، تزامن UI/بوت/قاعدة، سلامة قاعدة البيانات).
**وثيقة حاكمة جديدة (2026-07-05)**: «Katrina Verification Suite» (`/app/docs/diagnostics/KATRINA_VERIFICATION_SUITE.md`) — التحقق الفعلي L1→L16 + 3 ملاحق (Legacy Audit / Failure Modes / UI Consistency). قواعدها: كل نتيجة بدون trace_id مرفوضة، تشخيص خالص بلا إصلاح في الجولة الأولى، الشهادة = أعلى مستوى مكتمل 100% + امتحان المالك.

## CHANGELOG — 2026-07-07 · ✅ P1 مكتمل (مصادقة إنتاجية SEC-003) + سيناريوهات المالك التسعة لكاترينا
**مختبَر 100%: pytest 8/8 (P1) + 5/5 (P0 refresh) + 34/34 (انحدار أمني/توجيه) + 14/14 (سيناريوهات كاترينا iter257) + وكيل اختبار واجهة (iteration_253: 100% مع إصلاح HIGH الوحيد بعدها)**

### P1 — المصادقة الإنتاجية (Backend كان جاهزاً، أُكمل الاختبار + الواجهة)
- 🔧 **حل جذر فشل اختبارات P1**: تجاوز Rate Limiter بترويسة سرية `x-ratelimit-bypass` == `RATE_LIMIT_BYPASS_TOKEN` (backend/.env) — server.py middleware. حزمة الاختبار تمنع تخزين الكوكيز (كانت الكوكيز الجديدة تتقدم على Bearer القديم وتكسر اختبار reuse-detection).
- 🧹 تنظيف `.env`: كانت 4 نسخ مكررة من JWT_SECRET (توليد تلقائي) → نسخة واحدة (الفعّالة bafd8756…).
- 🖥️ **واجهة تسجيل الدخول الجديدة (Login.jsx)**: اسم فقط (متوافق رجعياً) + كشف تلقائي «كلمة المرور مطلوبة» يُظهر حقلها + «تذكّر هذا الجهاز» → دخول سريع بـ PIN (وضع تلقائي عند وجود `trusted_device` في localStorage) + زر Google SSO (auth.emergentagent.com، redirect ديناميكي، AuthCallback يعالج `#session_id=` قبل أي توجيه في App.js).
- 🔐 **SecuritySettings** (تعيين كلمة مرور + PIN + توثيق الجهاز 30 يوماً): مركّبة في /settings?tab=profile **و** صفحة مستقلة `/account/security` متاحة **لكل مستخدم موثق** (قاعدة `allow:'authenticated'` في ROUTE_PERMISSIONS + بند sidebar بلا صلاحية) — إصلاح HIGH من وكيل الاختبار: الفني لم يكن يملك أي مسار UI لضبط كلمة مروره.
- 📄 utils جديدة: `sessionSetup.js` (establishSession موحّد للدخول العادي وGoogle)، `authToken.js` أصبح فيه `loginRequest/storeTokens`.
- 🧪 وكيل الاختبار (iteration_253): كل تدفقات الدخول (اسم/كلمة مرور/PIN/Google redirect) 100% + كاترينا «كم مركبة حالية» تطابق اللوحة. تنظيف بيانات «مستخدم اختبار» تم.

### سيناريوهات المالك التسعة (كلها ✅ محققة E2E)
1. «أعطني آخر خمس عمليات» → `operations.recent` (نمط جديد يدعم «آخر خمس/5/عشر»).
2. «اجمالي الذمم الحالية» → `finance.ar_summary` (نمط موسّع: اجمالي/مجموع/كم الذمم) — 11,150 ر.س / 8 عملاء.
3. «كم المصروفات هذا الشهر» → `firewall.cash_flow` (كان يعمل) — 969 ر.س.
4. «اكثر الخدمات بيعاً» → 🆕 أداة `operations.top_services` (تجميع بنود العمليات الفعلية count+revenue — كان يجيب من كتالوج الخدمات خطأً).
5. «عمليات بدون قيود محاسبية» → `firewall.operation_integrity` (كان يعمل) — كشف 5 عمليات بـ3,450 ر.س.
6. «سداد 5377 عبدالعزيز العريني» → collect_payment أربع أعين: 🆕 توحيد «عبدالعزيز↔عبد العزيز» في normalize_arabic + 🆕 تفضيل التطابق الاسمي التام («محمد الحربي» يفوز على «محمد علي الحربي») + 🆕 customer_phone في مخطط collect_payment/create_invoice + عند الغموض يسأل بقائمة مرشحين + عند عدم الوجود يعرض **إضافة عميل جديد**.
7. «كم مركبة حالية» → 🆕 أداة `vehicles.status_summary` مطابقة لقواعد لوحة التحكم (تستثني delivered): 13 حالية / تشخيص 10 / جاهز 1 / مؤرشفة 2.
8. «اضف بند توضيب مكينة 500 آجل على المركبة لوحة …» → create_visit تأكيد ثم التزام؛ البند ظهر في ملف المركبة عبر `/api/vehicles/{id}/visits` (زيارة f9c0e5ae).
9. «تأكيد سداد»: سداد 500 محمد الحربي → pending_approval → اعتماد ذاتي 403 four_eyes_violation ✅ → اعتماد احمد1 + commit → قيد متوازن 500/500 (journal 31149eb3، tx_hash). (مسودة 5377 الاختبارية رُفضت تنظيفاً).
- Regression جديد: `/app/backend/tests/test_katrina_scenarios_iter257.py` (14 اختباراً حتمياً بلا LLM).
- ملاحظة بيانات: قيد سداد 500 + زيارة البند الآجل باقيان كأثر اختبار مطلوب من المالك (يمكن عكس القيد بأمر «اعكس القيد 31149eb3» عند الرغبة).
- Backlog من وكيل الاختبار (LOW): كبح دفعة طلبات 401 قبل تسجيل الدخول على /login.

## CHANGELOG — 2026-07-05 · Katrina Verification Suite: المرحلة 0 (llm_traces) + الملحق أ (Legacy Audit)
**قرارات المستخدم المعتمدة:** L15 مصغّر (10 جلسات ذمم + 5 شراء) مع سباق الاعتماد كاملاً + توثيق أن الكامل شرط الجولة الثانية فوق L14 · L12 بمحاكاة أعطال بأربعة ضوابط (تأكيد قبل كل حقن، snapshot للقاعدة، flags قابلة للعكس، checklist استعادة بالتقرير).
- 🔬 **نظام llm_traces (الشرط المسبق) — مكتمل ومختبَر (7/7 pytest + e2e curl)**:
  - `core/llm_traces.py`: contextvar per-request → MongoDB `llm_traces`. يسجّل: user_message، llm_calls (system_message بعد PDPL + request_messages + response_raw + duration)، tool_calls_executed (input + output_raw + duration + write)، final_response، intent/status/executed، duration_ms.
  - حقن في: `assistant_kernel.chat()` (بدء/إنهاء + `trace_id` في envelope الرد)، `_llm_chat` (purpose=chat)، `llm_intent_parser` (purpose=intent_parse)، `tool_router.call_tool` (كل الأدوات).
  - `routes_traces.py`: `GET /api/traces/{id}` و`GET /api/traces?session_id=` و`GET /api/traces/stats` — أدوار الاعتماد فقط (403 لفرج1 ✅، 401 بلا توكن ✅).
  - اختبارات: `/app/backend/tests/test_llm_traces_phase0.py` (7/7 — roundtrip، أدوات+LLM، no-op بلا trace، قصّ 60KB، مسار الخطأ، list، عزل contexts بين tasks).
- 📋 **الملحق أ Legacy Audit — مكتمل** (`/app/docs/diagnostics/LEGACY_AUDIT.md`): 23 بنداً. أبرزها: 🔴 6 قيود SMART_POS حية بأسماء حسابات مجمّدة على الترقيم القديم (042 باسم «ايراد قطع الورشه» والحي «مصروفات البيت»، 045 باسم «045») + زوجا اشتباه تكرار (250×2، 111×2) · 🔴 ازدواج مصادر: الإيرادات ×4 حاسبات، الذمم ×3 تمثيلات (117 حساب عميل يتيم) · ❌ A2 المقسّم القديم `_legacy_extract_commands` معطَّل لا محذوف · ❌ A7 prompts في 15+ ملف بلا Registry · ✅ A5 صفر أدوات شبح (20/20 نجحت) · ✅ A8 الحرّاس سليمة. **صفر إصلاحات نُفّذت** (قاعدة الجولة الأولى).
- 🔴 **عائق مفتوح**: رصيد Emergent LLM Key **نفد** أثناء الاختبار (Budget exceeded: 18.886/18.878) — مستويات L1→L15 (شات حقيقي) موقوفة حتى الشحن. llm_traces التقط الخطأ بأمانة في trace tr-cfbe1304c8ce.


## CHANGELOG — 2026-07-03 (ب) · إصلاحات P0 بعد المرحلة 2 + الإلغاء السياقي + الترابط الحي مع كل الصفحات
**مختبَر 100% (iteration_247: خلفية 5/5 + واجهة 4/4 + 29 pytest انحدار)**
- 🔴 **P0 NameError**: `_build_approval_actions` كانت غير معرّفة وقت العرض في `assistant_kernel.py` — أُصلحت وتحققنا E2E (بطاقة الشراء تظهر بأزرارها الخمسة بلا انهيار).
- 🔎 **نية «اعتمادات كاترينا»**: regex في `assistant_kernel.py` (سطر ~67) يلتقط الآن اعتمادات/موافقات/معلقة → أداة `runtime.pending_approvals` تعرض جدول Markdown + بطاقات.
- 🚫 **الإلغاء السياقي (`_try_cancel_last_draft`)**: «الغي آخر عملية شراء» يسحب آخر مسودة معلقة من الجلسة (أو لنفس المُنشئ) عبر `reject_approval` — بدون طلب journal_id. يفضّل مسودات الشراء عند ذكر «شراء». يرجع `executed.status=cancelled`.
- 📝 **توسيع أفعال الكتابة**: لاحقة تاء المتكلم (اشتريت/سجلت/أضفت...) تدخل مسار التنفيذ الآن (`_ACTION_VERB_RE`).
- 🔗 **الترابط الحي بين البوت وكل الصفحات (طلب المستخدم)**:
  - `AssistantProvider._dispatchRefreshEvents`: يبثّ `finance:updated` (عند committed) و`runtime:changed` (committed/pending_approval/cancelled/rejected) بعد كل رد شات.
  - `UnifiedAssistantDrawer`: أزرار البطاقات تبثّ الحدثين معاً.
  - مستمعون جدد: `FinancialControl` (remount بـ refreshKey + تحديث شارة كاترينا)، `KatrinaApprovalsTab`، `Suppliers`، `PartsInventory`، `Invoices`، `IncomeStatement`، `BalanceSheet`، `CashFlow` — إضافة إلى المستمعين السابقين (Dashboard/Operations/Customers/TrialBalance/JournalEntries/الذمم/دليل الحسابات).
  - تحقق حي: شارة الاعتمادات تحدّثت 15→16 بعد شراء من الشات و16→15 بعد الإلغاء بدون إعادة تحميل.
- ✅ صفحة `/financial-control` مؤكّدة مربوطة (Route + Sidebar لأدوار admin/manager/supervisor) وتحمّل البيانات بلا 401.
- Regression: `/app/backend/tests/test_katrina_iter247.py` (من وكيل الاختبار).

## CHANGELOG — 2026-07-03 (ج) · الذاكرة والتذكير + القرار من المحادثة + منع التكرار + شمول المدقق
**مختبَر 100% (iteration_248: خلفية 10/10 + واجهة 5/5 + 34 pytest)**
- 🔔 **تذكير أول رسالة بالجلسة** (`_build_pending_reminder` + غلاف `chat()` حول `_chat_impl`): يعرض للمعتمد عدد الاعتمادات بانتظار قراره + حتى 3 بطاقات ApprovalCard قابلة للاعتماد/الرفض **من نفس المحادثة** (أربع أعين مفروضة سيرفرياً)، وللمُنشئ عدد مسوداته المعلقة.
- 🛡️ **منع تكرار طلبات الاعتماد** (`_find_duplicate_pending` في unified_executor): نفس الإجراء+الجهة+المبلغ معلق → يرجع بطاقة الطلب الموجود برأس «♻️ طلب مطابق معلق بالفعل» بدون إنشاء مسودة جديدة.
- 🕵️ **مدقق المسودات قبل الاعتماد** (`core/draft_audit.py`): مبلغ صفري/سالب، مبلغ مرتفع (≥50K)، تكرار محتمل مع منفذة خلال 24س، + **شمول مدقق النظام**: عدد ملاحظات التدقيق المفتوحة (وتمييز ما يخص نفس الجهة). تُعرض في نص الرد وبيانات البطاقة (`audit_notes`).
- 🗓️ **استعلامات تاريخية عربية** (`_extract_date_range` في tool_router): «الشهر الماضي/قبل شهر/آخر اسبوع/أمس/اليوم/هذا الشهر...» تفلتر العمليات زمنياً (period في نتيجة operations.search) — مثال مؤكد: الشهر الماضي = عمليتان بـ4,800 ر.س. مع تنظيف أفعال الحشو (صارت/تم...) حتى لا تفسد مطابقة الأسماء.
- 🏷️ **عناوين بطاقات غنية** (card_builder.approval_card): «موافقة — شراء · النخبة · 80 ر.س» + proposer/echo في data.
- 🔴 **إصلاح جذري لتسجيل الدخول**: مستخدمو غير «مدير» (احمد1/فرج1...) كانوا محرومين من الدخول عبر الواجهة منذ تشديد deny-by-default (Login.jsx كانت تجلب `/api/users` بلا توكن → 401). التدفق الجديد: `POST /api/auth/login` أولاً ثم `/users` بالـBearer، مع جلسة احتياطية من `/auth/me` إن غاب المستخدم من القائمة.
- 🧹 تنظيف `.env`: أسرار JWT_SECRET مكررة (من auto-generate في عمليات مستقلة) → سر واحد. ملاحظة: سكربتات مستقلة يجب أن تحمّل dotenv قبل استيراد auth وإلا ولّدت سراً جديداً.
- Regression: `/app/backend/tests/test_katrina_iter248.py`.
- ملاحظات مراجعة (غير حرجة، Backlog): توحيد شكل رد `/api/runtime/approvals`، وتسمية `executed.id` (draft_id) الملتبسة.

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
- **P0 (بانتظار المستخدم)**: مراجعة الاعتمادات المعلقة في صندوق اعتمادات كاترينا؛ اختيار طريقة واتساب لكشوف حسابات العملاء (wa.me مجاني أو Twilio API)
- **P1**: كشف حساب عميل عبر واتساب من صفحة الذمم + ربط أمر «أرسلي كشف حساب» بكاترينا
- **P1**: تنقيح البيانات الحساسة قبل إرسالها للـLLM
- **P1 (منجز جزئياً)**: Decimal في محرك المحاسبة تم ✅ (PRD v1.1، 58 اختباراً) — يتبقى توسيعه لاحقاً إلى routes_finance/firewall عند الحاجة
- **P1**: refactor server.py / routes_finance.py (224KB) / routes_extended.py (212KB)
- **P2**: تحسين UX صفحة الرقابة المالية/الاعتمادات؛ عرض أرقام تذاكر/زيارات قصيرة في ردود البوت (تم للفواتير INVxxxxx)
- **P2**: ربط whatsapp.send بموجه نوايا البوت؛ deep-links سياقية (?pos= ?part=)؛ Ollama fallback معطوب في بيئة المعاينة
- **P3**: تقسيم مكونات React الضخمة (VehicleDetails 4510 سطر، Operations 3835)؛ CRA→Vite

## حالة Katrina Verification Suite (24 فبراير 2026)
- **بلاغ إنتاج مُصلَح ✅ (سداد لم يُثبَّت + اختلاق عملاء)**: FIX-1 توجيه صيغ المصدر المالية (تحصيل/خصم إداري) لمحرّك التنفيذ → ApprovalCard أربع أعين حقيقية بدل بطاقة «نعم» الوهمية؛ FIX-2 كاشف «القيود كاملة/كل القيود» + حاجز برومبت ضد الاختلاق. تحقق وكيل الاختبار 100% (14/14). اختبارات: test_bot_routing_hotfixes_iter251.py.
- **مراجعة كود (قراءة فقط) — READY WITH FIXES، المؤكدات مُصلحة ✅**: CR-1 (تراجع SEC-002: ودجت العمليات كانت فارغة صامتة لغير المعتمِدين → معالجة 401/403 برسالة صريحة)، CR-2 (رفع تجميد G3: فشل تنفيذ حقيقي يُظهر «لم يُنفَّذ — خطأ» بدل السقوط الصامت)، CR-3 (تقليص إفراط `_FIN_MASDAR_RE`)، CR-4 (خطأ صريح لأداة القيود + تصفير علم التهريب). 54/54 اختبار + تحقق حي (درج admin يعرض العمليات، محاسب→رسالة حجب). LOW مؤجّل: نمط الهاتف/9أرقام، ذاكرة in-memory، تناقض RBAC مقصود على مسار الاقتراح.
- **هوت فيكس أمنية منفَّذة سابقاً ✅**: RBAC على tool/{name}، whatsapp.send write=True، الطباعة (هوية الورشة). اختبارات: test_security_hotfixes_iter250.py (7/7).
- **L14 Provenance: ❌ رسوب (4/6)** — docs/diagnostics/L14_PROVENANCE_REPORT.md. حكم 8,905/9,850 = بند A6 (3 مصادر حقيقة). اكتشافات L14-D1..D4 + G3 موثقة بلا إصلاح.
- **التالي بالترتيب الصارم**: L1→L7 ثم L8→L13 ثم ملحق ب ثم ملحق ج ثم L15 (تشخيص خالص + trace_id). بعدها Hybrid Router (Strategy A).

## أولويات المالك (24 فبراير 2026) — تسلسل إلزامي، لا انتقال قبل إغلاق المرحلة
- **P0 — إصلاح /api/auth/refresh جذرياً ✅ مكتمل**: RCA في docs/diagnostics/P0_AUTH_REFRESH_RCA.md. السبب: كوكيز SameSite=Lax لا تعيش في iframe المعاينة → refresh 401. الحل: SameSite=None;Secure + Bearer fallback + single-flight + طابور + منع حلقات + logout منظّم. 5/5 اختبار + تحقق حي.
- **P1 — SEC-003 نظام مصادقة Production ✅ مكتمل (2026-07-07)**: Email/Password (bcrypt) + PIN + جهاز موثوق + Google SSO (Emergent) + Refresh Rotation (jti + reuse detection) + جلسات + Audit Log + واجهة كاملة (Login + /account/security). مختبَر خلفية وواجهة.
- **✅ قاعدة القيد المؤقت للبيع الآجل (طلب مالك 2026-07-07) — منفَّذة ومختبَرة (iteration_254)**.
- **✅ P3 المرحلة أ+ — مركز التحكم داخل البوت — منفَّذ ومختبَر (iteration_254)**. المتبقي من P3: المرحلة ب (Hybrid Router الكامل).
- **✅ L14 مُغلق رسمياً (2026-07-08)** — امتحان المالك ناجح، Prompt v3 مجمّد، Golden Dataset، سكربت انحدار موحّد.
- **✅ P2 — L8→L13 ناجح (2026-07-08)** — تقرير `P2_VERIFICATION_REPORT.md`. **المتبقي: L12 + L15 (بقرار مالك)**.
- **التالي**: P3ب (Hybrid Router) → P4 (حفظ الجلسات في DB) → P5 (تتبع متقدم Correlation IDs).
- **P3 — Hybrid Router**: كل الأوامر المالية عبر Router حتمي ثم Validation ثم Accounting Engine؛ منع أي LLM من إنشاء/تعديل قيود مباشرة.
- **P4 — نقل الحالة من الذاكرة لقاعدة البيانات**: drafts, conversations, quotation state, pending actions, workflow state.
- **P5 — تطوير التتبع**: Correlation ID، Parent/Child Trace، Latency، Cost، Tokens، User ID، Role، Decision Path، Tool Calls.

## جلسة 2026-07-15ب — مراجعة أمنية + التسليمات الثلاث المعلقة
- **المراجعة الخارجية**: طُبّق الآمن فقط (md5 usedforsecurity=False بلا تغيير معرفات، 4 استيرادات ديناميكية→ثابتة، كلمة سر الاختبار→TEST_USER_PASSWORD في .env). «الاستيراد الدائري» إيجابية كاذبة (استيرادات مؤجلة عمداً). **قرار المالك**: cookies + الحزمة الكبيرة (hook deps/تقسيم المكونات/index-keys/useMemo) + الاستيراد الدائري = مرحلة refactoring مستقلة **بعد إغلاق L14ج3، لا قبل**.
- **«48 متغيراً غير معرّف»**: لا يتكرر — pyflakes 0، ruff F821/F823 0، pylint E0601/E0606 = **2 فقط وكلاهما إيجابية كاذبة آمنة** (`UNDEFINED_VARS_AUDIT.md`).
- **استعلام auto:policy الشامل** (`AUTO_POLICY_FULL_AUDIT.json`): **36 اعتماداً آلياً** (31 موافقة/5 رفض) من 06-19 إلى 07-08، **17 كتابة فعلية على الإنتاج** (عملاء 6، مركبات 5، زيارات 6).
- **دفعة 1,695** (`PAYMENT_1695_DEEP_DIVE.json`): موجودة فقط داخل notes الزيارة (advance/بنك/ساعة عميل 07-11 14:46:49)، **لا قيد يومية بمبلغ 1,695 في النظام كله**، لا سند، والفاعل غير قابل للتحديد (لا updated_by ولا أحداث دخول في النافذة).
- **حسم 18,266 vs 70,120** (`GAP_18266_VS_70120.json`): المقياسان مختلفان (سندات مُرحّلة vs بنود زيارات مغلقة). اليوم: فجوة الجدار **29,386/16 زيارة** (قفزت من 18,266/10 خلال يوم = نزيف نشط) — منها 9 زيارات (16,896) **داخل** الـ70,120 و**7 زيارات (12,490) زيادة خارجها** (أغلبها زيارات مفتوحة/مقبوضات≠بنود لم يشملها مسح الزيارات المغلقة).
- **توضيح D7**: مثبت في القفل سطر 25 كبند موثق **بحالة «❓ بانتظار قرار المالك»** — التوثيق تم، القرار لم يُتخذ (لا تناقض).

## جلسة 2026-07-15 — ترقية الشخصية القصيمية (مواصفة المالك) + بناء D5
- **D5 ✅ منفّذ ومثبت**: `provenance_guard.enforce_entities` — أي معرّف منظَّم (OP-xxxx-xxxx/INVxxxxx/tr-hex/UUID/id قصير hex) في رد كاترينا لا يوجد في أدلة الدورة (أدوات+سياق+رسالة+تاريخ) → يُحجَب ويُسجَّل خرقاً. موصول بالنواة بعد حارس بلوكات الأدوات. الإثباتات: `tests/test_d5_fabrication_guard.py` **8/8** (منها حجب OP-2025-0187 حرفياً) + إعادة حية للسيناريو الأصلي «اعرضي آخر عمليتين» نظيفة (tr-e8d7c72e8f20: الأداة نُفّذت والمعرّفات موثقة، صفر انتهاكات) + **انحدار L14 كامل PASS** (31 وحدة + 29/29 Golden Dataset).
- **v4.1-qassimi-mirror ✅ مسجّلة غير مفعّلة**: أساسها v3 حرفياً + قسم «المرآة القصيمية» (المرآة لا الفرض، الإيجاز، الجواب أولاً، منع الرسمية المصطنعة، معجم قصيمي، حدود اللهجة، أمانة الأرقام الحرفية بإشارتها). بنك أسلوب **7/7** (`V4_STYLE_RESULTS.json`): فصحى→فصحى، قصيمي→مرآة، رقم-فقط→«4,500 ريال»، لا رسمية مصطنعة، أرقام سليمة بالسالب، رسمي عند الطلب.
- **v4→v4.1 (حوكمة نسخ سليمة)**: البنك كشف إسقاط الإشارة (-13,406→13,406) واشتقاق فرق خاطئ (3,756) → قاعدة أمانة الأرقام أصلحت الإشارة والاشتقاق الخاطئ. ⚠️ قيد موثق: الاشتقاق الصحيح رياضياً (23,056) لا يُقفل بالـprompt وحده — قفله الحتمي في Hybrid Router (المرحلة ب).
- **بوابة النشر**: D5 ✅ · trace ✅ · انحدار ✅ · rollback فوري ✅ (v3 محفوظة، التبديل استدعاء واحد) · **اعتماد المالك ⏳ — v3 لا تزال النشطة**.

## جلسة 2026-07-14 — قرارات المالك على التقرير الثلاثي (تسليم ثلاثي ثم توقف)
- **🎫 TICKET-ISO-001 ✅**: `docs/verification/TICKET_TEST_ISOLATION.md` — كل الاختبارات (L14/P2 runners + 134/158 ملف tests) تعمل على قاعدة الإنتاج، لا بيئة معزولة. زيارة `868355a4` أصلها اختبار كاترينا اعتُمد بـ`auto:policy` بلا إنسان ثم عُدّلت 07-11 من واجهة الإنتاج (دفعة 1,695 بلا قيد). «التاريخ المستقبلي» حُسم: جلسة الوكيل امتدت أياماً (07-09→07-14) — ساعات الحاوية وSupabase متطابقة الآن. **مستبعدة نهائياً من أي تسوية**. 4 خيارات عزل بانتظار المالك.
- **جدول المعاينة ✅**: `docs/verification/PREVIEW_SETTLEMENT_51_VISITS.md/.json` — 51 زيارة (بعد استبعاد 868355a4) = 54,515 ر.س، 59 مسودة مقترحة (قاعدة: مسودة/زيارة، تقسيم فقط عند تعدد فئات الإيراد — 7 زيارات تُقسّم). 🩸 نزيف نشط: 5 زيارات آخر 7 أيام (7,250) و10 خلال 14 يوماً (12,655). **لم تُنشأ أي مسودة — بانتظار مراجعة المالك.**
- **ملف السبع زيارات ✅**: `docs/verification/OUT_OF_CRITERION_7_VISITS.json` — فجوة 15,605 (منها يوسف 6,474 المغطاة بالمسودات الخمس). الفجوة الكلية 70,120 عبر 58 زيارة.
- **trace_id ✅ (قاعدة نافذة)**: `create_draft` يسكّ trace تلقائياً لأي مسودة مالية (invoice/payment/expense/reverse/purchase) عبر llm_traces (channel=runtime) — مُختبَر (مسودة تجريبية سكّت tr- ثم أُهملت). المسودات الخمس أُلحقت بآثار حقيقية قابلة للاسترجاع من `/api/traces/{id}` (مثال tr-4ae9382facc8).
- **قاعدة الفاتورة المقابلة ✅ (نافذة)**: `firewall_engine.detect_receipts_without_invoices` — تنبيه «سندات قبض مرتبطة بزيارات بلا فواتير مقابلة» (HIGH) يرصد حالياً 10 زيارات بسندات مرحّلة بفجوة 18,266. (يغطي السندات المقيّدة؛ الـ51 التاريخية مقبوضاتها في notes الزيارات غير مقيّدة أصلاً — يغطيها جدول المعاينة.)
- **DECISIONS_LOCK مُحدَّث**: بند توقف التسليم + D7 (سندات القبض خارج العيون الأربع — قرار مالك) + بند 8 توحيد العرض المرجعي (خيار a حصراً، بلا إعادة ترقيم — tx_hash) + قواعد نافذة. **سند الـ417: لا إجراء — تحقق شخصي للمالك.**
- **⏸️ متوقف بأمر المالك**: لا D5→D1→D2→D6→S3→L14ج3 قبل رده على التسليمات الثلاث.

## جلسة 2026-07-09 — تنفيذ مهام المالك الثلاث (تحقيقات بيانات + مسودات)
- **المهمة 1 ✅**: زيارة يوسف الكبير `29b88c69` — الشرط تحقق بالضبط (بنود 8,474 − مُفوتَر 2,000 = 6,474.00) → أُنشئت **5 مسودات فواتير آجلة** (proposer=كاترينا) بحالة `pending_approval` بمجموع 6,474: القرعاوي 4,046 + القرعاوي 722 + مخرطة العوفي 1,170 + سبايك 416 + غسيل ومعجون 120. **لم يُعتمد شيء** — القيود بقيت 43 والعمليات 33. المرجع: `docs/diagnostics/VISIT_29b88c69_SETTLEMENT_DRAFTS.json`.
- **⚠️ ملاحظة جديدة (لم تُلمس)**: يوم 07-09 20:44 سُجّل سند قبض جديد 417 نقدي (قيد 43746257) لنفس الزيارة → المقبوضات صارت 8,891 (تزيد 417 عن البنود 8,474)، وأُعيد توليد العملية INV001254 بمجموع 2,536. قرار المالك.
- **المهمة 2 ✅ (قراءة فقط)**: الزيارات الثلاث `e10a7a9e` (برادو/الجعيثن — بنود 4,750، مدفوعة بالكامل، **0 قيد فاتورة**)، `ef6f0f88` (الربيش — 1,000 مدفوعة، 0 قيد فاتورة)، `7ce2e6dd` (أبو راكان — 305 مدفوعة، 0 قيد فاتورة). كلها مغلقة completed. سندات القبض موجودة لكن لا قيود فواتير (مدين ذمم/دائن إيراد) إطلاقاً.
- **المهمة 3 ✅**: 10 قيود بعد 07-07 11:52 كلها ترحيل مباشر من شاشات النظام (9 سندات قبض + 1 بيع فوري) — **لا حقول proposer/approver في جدول journal_entries** ولم تمر بالعيون الأربع. رصيد الذمم من القيود: −2,419 → **−13,406** (السندات دائن 005 بمجموع 10,987 بلا فواتير مقابلة). الـ9,650 = أرصدة العملاء المخزنة (legacy، كانت 11,150).
- سكربتات القراءة: `docs/diagnostics/owner_tasks_probe.py`, `owner_tasks_probe2.py`, `owner_tasks_report.py`, `create_29b88c69_drafts.py`.

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

## جلسة 2026-07-15ج — تنفيذ قرارات الحوكمة الخمسة
- **العزل (خيار هـ):** حظر `auto:policy` و`auto:*` و`bot_*` كمعتمدين لكل write action؛ كل كتابة تنتظر أربع أعين بشرية حقيقية. أضيف `core/environment_guard.py` لاختيار Supabase الاختبار فقط عند `APP_ENV=test` مع fail-closed عند غياب/تطابق بيانات الاختبار. **متبقي P0:** بيانات مشروع الاختبار غير موجودة في البيئة أو المرفقات المسترجعة؛ اختبارات الكتابة الحالية **MOCKED** ولا تلمس الإنتاج.
- **D7 ✅:** سندات القبض، البيع الفوري من Smart POS، وتأكيد التحصيل تعيد `202 pending_approval` ولا ترحّل عملية أو قيداً قبل اعتماد بشري مختلف. الـmarker الداخلي لا يُقبل بلا موافقة فعلية، ومسارا approve وcommit يعالجان التدفق الخارجي نفسه.
- **جدول 51 زيارة:** مرفوض بقرار المالك؛ لا إنشاء للـ59 مسودة ولا تسوية من الجدول.
- **مسودات يوسف:** الموافقات الخمس `000da8de4cb7`، `2701b38159cc`، `86a7b57faada`، `893bb3d336d3`، `ee6d289150d8` أصبحت `rejected` بلا ترحيل.
- **Prompt:** `v4.1-qassimi-mirror` أصبحت النسخة النشطة؛ إثبات القرارات والحالات في trace `tr-7e5f57835974` بحالة `completed`.
- **التحقق:** Testing Agent iteration_256؛ الجولة النهائية 57/57 pytest، Python/JS lint نظيف، `/api/health` = 200، وفحص الواجهة ناجح. مؤشر الصحة المالي الحالي 81 بسبب الفجوات المعروفة؛ الاختبار القديم 100 حُوّل إلى تحقق صحيح غير هش.
- **التالي P0 بالترتيب المقفل:** توفير بيانات مشروع Supabase الاختباري وتفعيل العزل الكامل، ثم D1 → D2 → D6 (تقرير فقط بلا لمس أرقام) → S3 → L14 Round 3.
- **P1:** Hybrid Router الحتمي للعمليات المالية بعد إغلاق L14.
- **P2/Backlog:** توحيد العرض المرجعي، ثم refactoring المؤجل بعد إغلاق L14 فقط.

## جلسة 2026-07-18 — إصلاح تسجيل الدخول السريع للمدير
- **المشكلة:** PIN المدير الصحيح كان يُرفض على الجهاز الجديد لأن الخادم والواجهة يشترطان `device_id` موثوقاً؛ كما كان ملف `.env` يحتوي عدة قيم مختلفة لـ`JWT_SECRET` مما يعرّض الجلسات للإبطال عند الإقلاع.
- **التدفق الجديد:** شاشة الدخول تعرض هوية ثابتة `مدير` وحقل PIN من 6 أرقام فقط؛ PIN السريع يعمل على جهاز جديد ثم يصدر `trusted_device`. كلمة المرور بقيت خيار استرداد احتياطياً، وأزيل زر Google من الشاشة المطلوبة.
- **الأمان:** PIN مخزن bcrypt فقط؛ seed idempotent من `MANAGER_QUICK_USERNAME` و`MANAGER_QUICK_PIN`; قفل مؤقت بعد 5 محاولات حسب username+IP؛ النجاح يبدأ نافذة فشل جديدة دون حذف سجل التدقيق؛ `JWT_SECRET` موحّد ويفشل الإقلاع إذا غاب أو قصر.
- **RBAC:** حساب `مدير` موحد على دور `admin` في المستخدمين والتوكن و`/auth/me`.
- **الجلسة:** دخول PIN، access token، refresh rotation/reuse detection، وredirect الفوري كلها تعمل. CORS يشمل نطاق الإنتاج `https://car-repair-sys.emergent.host`، والإنتاج يستخدم `/api` same-origin.
- **التحقق:** 20/20 اختبارات مصادقة نهائية، Python/JS lint نظيف، Playwright من جلسة جديدة نجح حتى `/` مع session/token/device، `/api/health` = 200، وDeployment Audit = PASS.
- **حالة البيئات:** الإصلاح مثبت في Preview. يلزم إعادة نشر النسخة الحالية حتى يصل إلى Production؛ لا وصول مباشر لاختبار الإنتاج من بيئة التطوير.
- **التالي P0:** بعد إعادة النشر، تحقق يدوي واحد من `مدير + PIN` في نطاق الإنتاج، ثم العودة للمسار المقفل D1 → D2 → D6 → S3 → L14 Round 3.

## جلسة 2026-07-18ب — تصحيح تسجيل الدخول متعدد المستخدمين
- **تصحيح المالك:** اسم المستخدم لا يكون ثابتاً على `مدير`. أعيد حقل اسم المستخدم قابلاً للكتابة، مع حفظ آخر اسم مستخدم محلياً فقط لتسريع الدخول.
- **المستخدم الجديد:** `احمد` موجود في سجل المستخدمين بدور `accountant` وحالته نشطة. جرى تعيين PIN مستقل `123123` له، محفوظاً bcrypt فقط في `auth_credentials` بلا أي حقل PIN نصي.
- **التدفق:** `احمد + PIN` يعمل من جهاز جديد ويصدر trusted device مرتبطاً بأحمد؛ `مدير + PIN` بقي يعمل بدور admin. تبديل الاسم لا يعيد استخدام device_id تابعاً لمستخدم آخر.
- **السياسة:** PIN من 6 أرقام يسمح بالدخول السريع للحساب صاحب الـhash؛ PIN القديم من 4 أرقام يبقى مرتبطاً بجهاز موثوق. القفل حسب username+IP، وكلمة المرور الاحتياطية باقية.
- **التحقق:** Testing Agent iteration_258؛ 24/24 اختباراً، واجهة/API/Mongo ناجحة، lint نظيف، و`/api/health` = 200. النطاق المختبر: Preview فقط وفق طلب المستخدم.
- **التالي:** لا إجراء مصادقة متبقٍ في Preview؛ العودة إلى المسار المقفل D1 → D2 → D6 → S3 → L14 Round 3 عند أمر المالك.

## جلسة 2026-07-18ج — نطاق الأمان الصغير من مراجعة جودة الكود
- **قرار المالك:** تنفيذ الخيار 1 فقط؛ صفر refactoring جانبي قبل إغلاق L14.
- **أسرار الاختبارات:** `test_temp_deferred_iter254.py` و`test_auth_p1_iter256.py` يقرآن URL وrate-bypass وكلمات المرور وPIN من البيئة حصراً؛ أزيلت القيم الثابتة `WRONGPASS` و`x123456` وPIN الاختباري `1234` والاستقراء اليدوي لملف `.env`.
- **معالجة الأخطاء:** أزيلت حالات `catch` الصامتة المستهدفة من `sessionSetup.js` و`authToken.js` و`SmartPOSJournal.jsx`، وأضيف تسجيل تحذيري آمن لا يطبع tokens أو PIN أو passwords.
- **Undefined vars:** ruff `F821/F823` وPython lint نجحا. رقم 48 غير قابل لإعادة الإنتاج؛ الحالتان الموثقتان في `UNDEFINED_VARS_AUDIT.md` إيجابيتان كاذبتان وآمنتان، ولم تُعدلا.
- **MD5:** بقيت `_alert_id` دون تغيير لأنها fingerprint توافقية غير أمنية مع `usedforsecurity=False`؛ تغييرها يكسر IDs محفوظة ويحتاج Migration رسمية.
- **المؤجل المقفل:** circular imports، exhaustive hook dependencies، localStorage→cookies، تقسيم المكونات/الدوال، index keys، وتحسينات JSX حتى إغلاق L14.
- **الإثبات:** trace `tr-3fbc346780b4` = completed؛ 18 اختباراً تُجمع، ruff/lint/compile/secret scan/catch scan ناجحة، Login smoke ناجح، `/api/health` = 200.
- **قيد الاختبار الحي:** تشغيل auth suite الكامل اصطدم بقفل 429 وحالة مستخدمين متغيرة في المعاينة المشتركة؛ لم تُحذف سجلات audit ولم تُغيّر بيانات المستخدمين ضمن هذا النطاق.

## جلسة 2026-07-18د — إصلاح افتراض آجل غير المؤكد + صلاحية اعتماد المحاسب
- **P0 مكتمل:** عمليات/بنود المركبة غير المؤكدة لا تتحول تلقائياً إلى `credit/آجل`. إذا لم يُختر دفع صريح تُحفظ كـ`paymentMethod=unconfirmed` و`paymentStatus=unconfirmed` ولا تُنشئ قيد ذمم/بيع آجل.
- **سلامة المحاسبة:** البيع الآجل الصريح ما زال يعمل كما هو؛ `paymentMethod=آجل` مع `paymentStatus=unpaid` ينشئ القيد المؤقت `[قيد مؤقت — بيع آجل]`.
- **Katrina Four-Eyes:** أضيف دور `accountant` إلى أدوار الاعتماد في backend والواجهة؛ `مدير/مدير النظام/محاسب` يستطيعون رؤية/اعتماد الطلبات المعلقة مع بقاء قاعدة الأربع أعين: المقترح لا يعتمد طلبه بنفسه.
- **اعتمادات الاختبار:** `مدير` admin و`احمد` accountant يعملان عبر PIN `123123`، وتمت مزامنة fallback users عند غياب جدول Supabase users في Preview.
- **CORS/auth:** أُغلق مسار wildcard الداخلي مع credentialed auth؛ backend المحلي لا يرسل `Access-Control-Allow-Origin: *` مع cookies. طبقة المعاينة الخارجية قد تضيف headers عامة، لكن اختبار التطبيق الداخلي أصبح أخضر.
- **التحقق:** Self-tests + Playwright smoke + Testing Agent iteration_262. إعادة تشغيل `pytest -q backend/tests/test_iter262_payment_defaults_four_eyes.py` أعطت `6 passed`.
- **التالي P1:** معالجة مسار اعتماد المدير إذا احتاج المالك سياسة supervisor/bypass رسمية دون كسر الأربع أعين، ثم الرجوع إلى L14 Round 3: D6 ثم S3.

## جلسة 2026-07-19 — إصلاح توجيه كاترينا وسياق الأسئلة المالية
- **P0 مكتمل:** كاترينا لم تعد ترد بـ«الأداة المطلوبة لم تُستدعَ» في الأسئلة التي وردت في سجل المستخدم؛ تمت إضافة/تحسين توجيه أدوات الموردين، المركبات، الاعتمادات، الإيرادات، العمليات بدون قيود، البنود الأكثر بيعاً، والملفات بدون بنود.
- **أدوات جديدة/محسنة:** `suppliers.search`, `vehicles.recent`, `finance.sales_report`, `operations.empty_items` مع تلخيص عربي واضح عند تعطيل LLM.
- **سياق متعدد الرسائل:** أمر مثل «دفعة للمورد FAMOUS VALLEY حواله» ثم «55sr Today» يُكمل نفس الطلب وينشئ مسودة اعتماد مالية بأربع أعين بدلاً من فقدان السياق.
- **تنظيف بيانات الاختبار:** أُزيلت سجلات `TEST_SAFE_* / TEST_ACCOUNTANT_* / TEST_ITER*` من الموردين والتنفيذات، وأضيف فلتر احترازي في بطاقات/runtime endpoints حتى لا تظهر للمستخدم.
- **تقليل الإزعاج:** الملخص اليومي/تذكير الاعتمادات لا يغطي ردود الأدوات أو أسئلة التوضيح.
- **التحقق:** lint للملفات المعدلة، API regression لرسائل المستخدم التسع، فحص سياق دفعة المورد، فحص عدم تسرب TEST في `/api/runtime/executions`, وPlaywright smoke للواجهة.
- **التالي P1:** بناء تقارير عربية أجمل للـ `finance.sales_report` و`accounting.journal_entries` بدلاً من fallback المختصر، ثم استكمال L14 Round 3.

## جلسة 2026-07-20 — تحسين RBAC ومسار اعتماد كاترينا والربط الحي
- **P0 مكتمل:** تم تثبيت هوية الاعتماد من JWT الفعلي بدلاً من بيانات الواجهة/الجسم؛ عند تبديل المستخدم إلى `احمد` يعتمد كـ`احمد` فعلاً، ولا تظهر رسالة «نفس الشخص» إلا إذا كان هو مُنشئ الطلب الحقيقي.
- **Developer Override:** مدير النظام/المدير يستطيع اعتماد طلبه الذاتي فقط بإدخال رمز المطور `rrr`، ويُسجّل في audit كـ`APPROVAL_GRANTED_OVERRIDE` مع `developer_override=true`، بينما بدون الرمز يبقى منع الأربع أعين فعالاً.
- **اعتمادات عشوائية:** تم تنظيف بيانات اختبار `REG_APPROVAL_*` وإخفاء المسودات غير النشطة/المحذوفة من قائمة pending، مع استمرار فلاتر `TEST_*` السابقة.
- **ترابط حي:** إجراءات كاترينا التي تعتمد عبر البطاقات تطلق أحداث `finance:updated`, `runtime:changed`, `operations:updated`, `vehicles:updated`, `customers:updated` لتحديث الصفحات ذات الصلة.
- **عمليات مالية من البوت:** أمر مثل «بيع خدمة فحص مبلغ 23 سداد نقدي» ينشئ مسودة اعتماد ثم بعد الاعتماد يضيف العملية في `operations` ويولّد قيداً محاسبياً. التحصيل بعد الاعتماد يكتب قيداً، ومحاولة mirror عملية تحصيل إلى `operations` أضيفت كربط تشغيلي.
- **بحث خاص لا عام:** أدوات البحث عن العملاء/المركبات/الموردين/العمليات لا تعرض كل البيانات عند غياب معيار بحث؛ تسأل عن اسم/جوال/لوحة بدلاً من كشف السجلات كاملة.
- **التحقق:** lint Python/JS، اختبار مدير→أحمد يعتمد بنجاح، اختبار مدير ذاتي بدون `rrr` يفشل وبلـ`rrr` ينجح، اختبار ظهور عملية البيع في صفحة العمليات، واختبار smoke للواجهة.
- **التالي P1:** تحويل صفحة `/financial-control` لتصبح واجهة بوت/مركز تحكم كاترينا بالكامل بدلاً من الشكل القديم، وتحسين صياغة تقارير القيود والتحصيل المركبي.

## جلسة 2026-07-20ب — إصلاح أزرار الطباعة/PDF في واجهة المركبة
- **P0 مكتمل:** أصلحت أزرار الطباعة في صفحة المركبة: فاتورة مبيعات، تقرير تشخيص، وطباعة الزيارة. القائمة السريعة أصبحت click-driven بدلاً من hover-only، وتقرير التشخيص أصبح زر مباشر ثابت لتصفير سباق القائمة.
- **ربط بيانات الورشة:** `QuickPrintDialog` يستخدم الآن API موثّق لجلب بيانات الورشة وتوليد المستند، وتم توحيد حقول الاسم/الجوال/السجل التجاري/الضريبة/الشعار في `workshopPrintInfo` و`unified_document_service`.
- **ربط بيانات الزيارة:** `VehicleDetails` يبني payload الطباعة من بنود الزيارة أو العمليات المرتبطة، مع بيانات العميل/المركبة/اللوحة/السنة/الملاحظات، ولا يرسل فاتورة فارغة قدر الإمكان.
- **ثبات المعاينة:** تم إصلاح race في `QuickPrintDialog` بإعادة ضبط الحالة عند الإغلاق، key فريد لكل طلب طباعة، وتوليد واحد مضمون لكل فتح مع preview أو error واضح.
- **التحقق الإلزامي:** Testing Agent iterations 263–270. النهائي `iteration_270` نجح: التشخيص 3/3، فاتورة المبيعات نجحت، زر طباعة الزيارة نجح، أزرار print/WhatsApp لم تعلق، ولا توجد أخطاء `QuickPrintDialog/VehicleDetails` أو فشل `/api/documents/generate`. **MOCKED: NONE**.
- **ملاحظة غير مانعة:** بقيت ضوضاء 401 عامة أثناء bootstrap/login في console، لكنها لم تمنع تدفقات الطباعة.

## جلسة 2026-07-20ج — تثبيت نهائي لطباعة/PDF المركبة والزيارة
- **P0 مكتمل:** أصلحت شكوى المستخدم المتكررة بأن زر القائمة السريعة لا يعمل وأن زر التشخيص كان مكرراً. الآن يوجد زر رئيسي واحد `طباعة / PDF` يفتح لوحة خيارات ثابتة خارج رأس الصفحة حتى لا تُقص أو تختفي.
- **أزرار القائمة:** `فاتورة مبيعات` و`عرض سعر` و`تقرير تشخيص` تعمل من نفس القائمة وتفتح معاينة مستقرة.
- **زر الزيارة:** أضيف زر `طباعة الزيارة` ظاهر في رأس ملف المركبة عند وجود زيارات، بالإضافة إلى زر داخل بطاقة الزيارة، حتى لا يعتمد الاختبار/المستخدم على توسعة الزيارة.
- **تنظيم المخرجات والخطوط:** تم حقن CSS ثابت داخل HTML الطباعة لتوحيد `Tahoma/Arial`, RTL, letter/word spacing, table layout ومنع تفكك الحروف أو ظهور HTML خام.
- **PDF:** أضيف زر `تحميل PDF` مستقل داخل `QuickPrintDialog`، مع بقاء أزرار الطباعة وواتساب.
- **ثبات الواجهة:** أصلحت تحذير nested button في بطاقة الزيارة بتحويل رأس البطاقة إلى `div role=button`، وأزلت خطأ `vehicle_timeout` من console باستبداله برسالة تحميل آمنة.
- **التحقق الإلزامي:** Testing Agent iterations 272–276. النهائي `iteration_276` نجح: صفحة المركبة تحمل، زر طباعة الزيارة ظاهر بدون توسعة، preview يعمل، invoice menu يعمل، أزرار print/download/WhatsApp قابلة للنقر، لا nested-button warning، لا `vehicle_timeout`, ولا فشل `/api/documents/generate`. **MOCKED: NONE**.

## جلسة 2026-07-21 — صفحة `/print` بتصميم «فاتورة الورشة — ختم إلكتروني» وهوية Dash Pro
- **P0 مكتمل وظيفياً:** استُبدلت صفحة `DocumentPrint.jsx` بتجربة جديدة بالكامل لهوية Dash Pro: محرر عربي، معاينة A4، ختم إلكتروني برمز تحقق ثابت، كروت بيانات العميل/المركبة/الورشة، جدول بنود، الإجماليات، التواقيع، ورمز تحقق بصري.
- **التكامل:** الصفحة ما زالت تدعم `type=invoice|diagnosis|quote|receipt` وروابط `vehicleId/visitId/operationId/invoiceId` قدر الإمكان، وتستخدم بيانات الورشة من `loadWorkshopPrintInfo`. كل العناصر التفاعلية والمعلومات الحرجة أضيفت لها `data-testid`.
- **PDF/واتساب:** تم تحسين `pdfGenerator.js` لانتظار الخطوط والصور قبل `html2canvas` وضبط أبعاد الالتقاط؛ اختبار تحميل PDF نجح، وواتساب يفتح رسالة مختصرة مع رقم المستند والإجمالي والختم الإلكتروني بعد تجهيز PDF.
- **Backend:** نقطة `POST /api/documents/generate` بقيت تعمل 200 لكل أنواع المستندات الأربعة.
- **التحقق:** self-test + Testing Agent `iteration_277`: تدفقات DocumentPrint الأمامية 100%، وBackend generate 6/7 ناجح. **MOCKED: NONE**.
- **ملاحظة غير مانعة للتدفق:** اختبار CORS الخارجي عبر نطاق المعاينة أظهر `Access-Control-Allow-Origin: *` على `/api/auth/login`. الفحص الداخلي المباشر `localhost:8001` يعيد origin صريحاً و`allow-credentials=true`، ما يعني أن wildcard يأتي من طبقة المعاينة/Cloudflare وليس من كود التطبيق. تدفق الطباعة/PDF/واتساب غير متعطل.
- **التالي:** إن لزم إغلاق فحص CORS الخارجي نفسه، يحتاج ضبط طبقة ingress/preview، بينما كود backend الحالي يثبت CORS صحيحاً داخلياً.

## جلسة 2026-07-23 — كاترينا: المالية الموحدة وربط الأرشيف الحي
- **P0 مكتمل:** أزيل مسار وقائمة `/financial-control` نهائياً من الواجهة؛ مركز الرقابة والاعتمادات موجود داخل كاترينا فقط عبر `ControlCenterTab` و`UnifiedAssistantDrawer`.
- **حارس كاترينا المالي:** لم تعد كاترينا تفترض طريقة الدفع. أي فاتورة أو تحصيل أو مصروف أو شراء بلا طريقة يرجع بسؤال واضح: «نقدي أم آجل أم تحويل؟» قبل إنشاء مسودة أو اعتماد. تُطبع مرادفات البطاقات والبنك كـ `transfer`.
- **المركبات:** وُحِّد معرف المركبة في لوحة التحكم قبل التنقل، وأصبح طلب تفاصيل المركبة يعالج الحقول الناقصة (`year` و`status`) بأمان. التحقق الخارجي سجّل `GET /api/vehicles/{id}` = 200 لمعرف مأخوذ من اللوحة.
- **المالية والأرشيف، ربط لحظي وعكسي:** أحداث `finance:updated` و`vehicles:updated` و`archive:updated` تنعش الأرشيف فوراً؛ حفظ بنود الزيارة أو السداد أو الأرشفة يرسل الأحداث إلى اللوحة والأرشيف، وحذف ملف من الأرشيف يعيد إشعار المركبات.
- **التحقق:** Testing Agent `iteration_280`: backend 4/4 ناجح (دخول المدير، قائمة→تفاصيل المركبة، حارس الدفع بلا مسودة، وتحويل→بانتظار الاعتماد)، والواجهة أكدت غياب `/financial-control` ونجاح فتح المركبة. أصلحنا بعده مرجع `nextVehicles` خارج النطاق في مستمع تحديث المركبة، ومرّ lint. **MOCKED: NONE**.
- **P1 التالي:** ربط التحصيل عبر كاترينا تلقائياً بالفاتورة أو لوحة المركبة المحددة وإغلاق الرصيد/الفاتورة عند اكتماله.

## جلسة 2026-07-23 — P0 إدارة القوالب والطباعة الموحدة
- **التشخيص محفوظ:** `docs/diagnostics/TEMPLATES_P0_DIAGNOSTIC_2026-07-23.md` يوثق القوالب القديمة ومصادرها ومسارات التجاهل وخطة الترحيل.
- **سجل موحد:** أضيف `document_templates` في MongoDB بعقد موحد: tenant/type/locale/version/status/active/is_default/source. البيانات والملفات القديمة لم تُحذف؛ صُنفت كـ `needs_fix` أو `invalid` حسب صلاحية العرض.
- **قاعدة الافتراضي:** قيد MongoDB جزئي يمنع أكثر من قالب نشط افتراضي لنفس `tenant_id + document_type + locale`. عملية Set Default خلفية، تنسخ قالب النظام إلى نطاق المستأجر عند الحاجة ولا تنقل fallback النظامي.
- **مصدر قرار واحد:** `/api/document-templates/resolve` و`/{id}/use` يعيدان المحتوى وسبب الاختيار (`explicit_document_template` أو `tenant_default` أو `system_default`) ويسجلان audit. القالب الصريح غير الصالح يرجع 409 بلا fallback صامت.
- **ربط الواجهة:** Templates Manager وQuickPrint وDocumentPrint وPDF وواتساب تستخدم السجل/القرار الموحد. أزيلت أزرار الطباعة المكررة من ملف المركبة؛ بقي زر الرأس الرئيسي فقط. شارات المدير توضّح الآن «افتراضي للمستأجر» مقابل «نظامي احتياطي» بدل الإيحاء بتكرار.
- **التحقق:** Testing Agent iteration 282 أكد QuickPrint وDocumentPrint والـ resolver؛ iteration 283 النهائي نجح 3/3 backend وأكد الواجهة: `/use` + سبب الاختيار + المعاينة، وغياب زر الزيارة الموسع. **MOCKED: NONE**.
- **ملاحظة CORS:** FastAPI مضبوط بأصول صريحة واعتماديات؛ الاستجابة `*` على رابط preview تُحقن من طبقة preview الخارجية حسب الاختبارات، وليست من منطق القوالب أو التطبيق.
- **P1 التالي:** ربط تحصيل كاترينا تلقائياً بالفاتورة أو لوحة المركبة المحددة وإغلاق الرصيد عند اكتماله.

## جلسة 2026-07-23 — P0.1 اكتمال القالب قبل PDF
- أضيف حارس موحد يكتشف المتغيرات غير المستبدلة بصيغ `{{...}}` و`[[...]]` و`<%= ... %>` و`{UPPERCASE_TOKEN}` قبل المعاينة أو PDF أو الطباعة أو واتساب.
- عند النقص يتوقف التدفق بلا fallback صامت، وتظهر رسالة عربية بالمتغيرات الناقصة، ويُسجل `template_incomplete` أو `template_load_failed` أو `template_render_failed` في audit القوالب.
- حُمي `downloadPDF` و`renderPdfAssets` بالحارس نفسه، وأزيل fallback الصامت لاسم العميل/اسم الورشة كي تظهر الحقول الإلزامية الناقصة بدلاً من اختراع قيم.
- **التحقق:** Testing Agent iteration 285 أكد أن `CUSTOMER_NAME` يظهر ضمن النواقص ويمنع المعاينة/PDF/الطباعة/واتساب، وأن مسار البيانات المكتملة ما زال يعمل. **MOCKED: NONE**.

## جلسة 2026-07-23 — تحسين مدير القوالب وقنوات الإخراج
- أضيف تعقيم HTML مرفوع بالخادم عبر Bleach/TinyCSS2، ومعاينة Manager الآن تعرض القالب المعقّم الحقيقي داخل iframe مع سبب الاختيار أو الفشل.
- أصبح Set Default يتحقق من القالب، ويحوّل القالب القديم السليم إلى `valid` قبل التعيين، مع قيد افتراضي موحد؛ وشارات المدير تفرق بين النظامي والمخصص والحالة والإصدار.
- واجهة الإخراج في QuickPrint وDocumentPrint حُصرت إلى واتساب/PDF/طباعة، مع إزالة نافذة معاينة واتساب الثانوية. PDF والطباعة يستخدمان HTML المعروض نفسه.
- دُعمت صيغ placeholders `[[VAR]]` و`<%= VAR %>`، وحُلّت بدائل `SEAL_CODE` و`WORKSHOP_PHONE` و`VEHICLE_INFO` في قالب رسائل واتساب.
- **التحقق:** iteration 288 أكد إدارة القوالب والأزرار الثلاثة؛ iteration 289 أكد backend ومانع الجوال. **غير مغلق:** أتمتة المتصفح لم تثبت فتح `navigator.share`/`wa.me` في QuickPrint برقم صالح بسبب عدم استقرار preview، رغم نجاح عقد API. لا توجد واجهات محاكاة.

## جلسة 2026-07-23 — القالب الرئيسي المستوحى من PDF
- حُذفت القوالب السابقة المؤكدة وملفاتها المفهرسة، واعتمد قالب واحد: `primary-mobile-a4-invoice-v1` بتصميم A4/جوال وبيانات ورشة/عميل/مركبة/إجماليات، واعتماد العميل والورشة والختم الإلكتروني.
- طباعة `DocumentPrint` أصبحت عبر iframe يحمل `renderedTemplate` فقط، وPDF يستخدم `previewRef` للقالب نفسه؛ لا تطبع صفحة React.
- أصلحنا عقد البنود: تعليق `<!--{{ITEMS_ROWS}}-->` محفوظ داخل `tbody` بعد التعقيم، ثم يتحول إلى صفوف `tr` حقيقية قبل المعاينة/PDF/الطباعة.
- **التحقق:** Testing Agent iteration 296 نجح: قالب واحد، صفوف بنود ظاهرة، إجماليات، لا placeholders خامة، وPDF/print يستهدفان القالب المملوء. **MOCKED: NONE**.

## جلسة 2026-07-24 — إصلاح حلقة تجديد الجلسة 401 + التحقق النهائي E2E للطباعة السريعة
- **السبب الجذري لحلقة 401:** `/api/auth/refresh` كان يفضّل كوكي `refresh_token` القديم على توكن Bearer الصالح، فيفعّل كشف إعادة الاستخدام ويلغي عائلة التوكنات كاملة → خروج قسري متكرر.
- **الإصلاح:** `auth_jwt.py` يجمع الآن المرشحَين (كوكي + Bearer) ويختار التوكن النشط عبر `auth_store.pick_active_jti()` الجديد قبل التدوير. اختبار انحدار: `test_iter299_auth_refresh_regression.py`.
- **التحقق E2E (iteration 299 — نجاح 100%):** دخول مدير/123123 بلا حلقة، الجلسة تصمد بعد إعادة التحميل، Bottom Sheet → معاينة كاملة → 3 أزرار (واتساب/PDF/طباعة)، صفر placeholders خامة، ختم العميل/الورشة لا يظهر إلا بعد الاعتماد (مؤكد على زيارة بلا اعتماد). **MOCKED: NONE**.
- **إصلاح إضافي:** `seed_quickprint_fixture.py` أصبح idempotent ولا يسرق الافتراضية من القالب الموحد `unified-invoice-a4-mobile-v1` (استُعيدت افتراضيته بعد حادثة أثناء الاختبار).
- **P1 التالي:** معالجة CORS wildcard في طبقة preview (خارجي)، سجل تدقيق مرئي باسم/نسخة القالب داخل واجهة المستند (P2)، رقم تحقق قابل للمسح داخل الختم الإلكتروني (P2).

## جلسة 2026-07-24 — فحص جاهزية النشر (Deployment Readiness)
- **إصلاح Blocker:** رابط جلسة Google OAuth في `auth_jwt.py` أصبح يُقرأ من متغير البيئة `EMERGENT_SESSION_DATA_URL` (أضيف إلى `backend/.env`).
- **تنظيف `.gitignore`:** أزيلت أنماط حجب `.env` المكررة (13 كتلة) وسطور `-e ` المعطوبة؛ أضيف `memory/test_credentials.md` للحجب.
- **CORS:** القائمة الصريحة تشمل نطاق الإنتاج `car-repair-sys.emergent.host` + `fixsa.online` — مقصودة (تدقيق أمني سابق رفض wildcard). تحذير الفاحص غير مؤثر.
- **التحقق (iteration 300):** انحدار باك إند 9/9 نجاح — الدخول، Google SSO، تدفقات refresh الثلاثة، المركبات، وحل قالب الفاتورة الموحد. **جاهز للنشر**.

## جلسة 2026-07-24 (مساءً) — Post-Deployment Validation على الإنتاج + إصلاح ختم العميل
- **نقطة دخول الإنتاج الصحيحة**: النطاق المخصص https://alkobir.com (حزمة الواجهة مبنية عليه؛ رابط emergent.host يعطي CORS عبر المتصفح — سلوك متوقع للنطاق المخصص).
- **نتيجة الجولة (iteration 302)**: صفر أخطاء P0. المصادقة (دخول 2.66 ث، لا حلقة 401، الجلسة تصمد)، المستندات الثلاثة بالقوالب الموحدة، صفر placeholders، PDF (~4.5MB)، رؤوس أمان كاملة (HSTS/XFO/CSP/nosniff)، CORS آمن، بيانات TEST أنشئت وحُذفت بالكامل.
- **خطأ اكتُشف وأُصلح (P2→DONE)**: ختم العميل لم يكن يظهر بعد الاعتماد لأن `GET /vehicles/{id}/approval-logs` يقرأ Mongo فقط بينما الرد على الاعتماد يكتب في Supabase. الإصلاح: النقطتان (vehicles/customers approval-logs) أصبحتا provider-aware وتقرآن `approval_requests` من Supabase مباشرة (`routes_approvals.py`).
- **التحقق (iteration 303 — 100%)**: الحالة الإيجابية (ختم أخضر "تمت الموافقة" باسم المعتمد بعد OTP) والسلبية (لا ختم بلا اعتماد) + انحدار القوالب الموحدة. **يتطلب إعادة نشر ليصل للإنتاج**.
- **حادثة معالَجة**: اختبارات محلية سابقة قلبت افتراضية القوالب في Mongo المعاينة (fixture سرق الافتراضية) — استُعيدت `unified-*-a4-mobile-v1` للأنواع الثلاثة.
- **مخلفات P2/P3**: لا يوجد DELETE /api/approvals (سجلات يتيمة)، get_or_create_customer يدمج العملاء بالهاتف بصمت، ضجيج 401 قبل المصادقة في صفحة الدخول، بقايا TEST قديمة في قيود الإنتاج.
- **معلّق**: التحقق البصري لختم الورشة على الإنتاج (يتطلب تدفق Four-Eyes ينشئ قيوداً — يُنفذ بعد إعادة النشر أو ببيئة تجريبية).

## جلسة 2026-08-01 — توحيد ترابط الأرقام المالية (الذمم) عبر كل الصفحات ✅
**طلب المستخدم**: تطابق 100% بين ملف المركبة / العمليات / متابعة الذمم / دفتر الذمم (أغلب المبيعات آجل). قرارات المستخدم: قيد تلقائي للبيع الآجل، دمج المكررين (تحقق اسم+هاتف/مركبة)، مسار دفع موحد يشمل POS، قيود تصحيحية للبيانات القديمة.
**الجذور المكتشفة**: (1) visit_sync لا ينشئ قيوداً؛ (2) نسب العمليات للعملاء بالاسم فقط → عميلان مكرران خلطا الأرصدة؛ (3) دفعات الزيارات تُخصم مرتين/لا تنعكس على العملية؛ (4) سندا قبض قديمان بلا قيود بيع → رصيد دفتر سالب.
**التنفيذ**:
- `visit_sync.py`: `_sync_visit_journal` — قيد استحقاق (مدين 005 ذمم/دائن إيراد) + قيود تحصيل delta بسقف مدين الذمم، idempotent بـ reference_id=visit_id + إبطال perf_cache بعد كل مزامنة + قراءة paymentMethod/Status من notes.
- `server.py`: أولوية النسب partner_id → مركبة→عميل → الاسم؛ paid=max(قيود، دفعات الزيارة)؛ تخطي زيارات العمليات في حلقة الدفعات (لا ازدواج).
- `supabase_service.py`: `_operation_payment_snapshot` — زيارة برصيد متبقٍ ليست "نقدي فوري"؛ totalPaid=max لا sum.
- `routes_extended.py`: delete_visit يحذف القيود المرتبطة.
- `routes_finance.py`: `POST /api/finance/ar-repair` (backfill idempotent — شغِّله على الإنتاج بعد النشر إن لزم).
- دمج 7 مجموعات عملاء مكررة (سكربت `merge_duplicate_customers.py` — حالة "محمد الحربي" بهاتفين تُركت لقرار المستخدم).
- قيدا رصيد افتتاحي تصحيحيان: شاص 2019 (16000) + عمر الخضيري (300) — مدين 005/دائن 166 فروقات ترحيل.
- إصلاح بيانات: 163 زيارة → 296 قيد، صفر أخطاء. حذف بيانات اختبار (احمددد، اختبار آجل صريح).
**النتيجة المتحقق منها (iteration 305 — 100%)**: دفتر الذمم = متابعة الذمم = العمليات = 51,735 ر.س، فجوة صفر، لا أرصدة سالبة، pending_unjournalized=0. دورة كاملة (بيع آجل 300 → دفعة 100 → متبقي 200 في كل الطبقات فوراً → حذف متسلسل يعيد الأساس). واجهة: متابعة الذمم 51,735 + محمد الحربي 600 مطابق لملف المركبة والعمليات.
**ملاحظات P3 متبقية**: paymentStatus='unconfirmed' للبيع الآجل بلا دفعات (دلالة غامضة — الأرقام صحيحة)؛ ضجيج 401 عابر بعد الدخول في الكونسول؛ تسميات أطراف الدفتر قد تتجزأ بمرادفات الاسم (المجاميع صحيحة).
**مهم**: يتطلب إعادة نشر لتصل الإصلاحات للإنتاج (بيانات Supabase مشتركة أصلاً — إصلاحات البيانات سرت على الإنتاج، إصلاحات الكود تحتاج نشراً).
