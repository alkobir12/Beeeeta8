# FULL-STACK PRODUCTION REALITY AUDIT — Workshop ERP (finmodule-sync)
تاريخ التنفيذ: 2026-06 · الوضع: Phase 1–7 (Discovery → Root Cause) مكتملة · **قراءة فقط — صفر تعديل بيانات**
نطاق: هذا المشروع فقط (نظام إدارة ورشة + مساعد كاترينا الداخلي). لا استيراد افتراضات من أي مشروع آخر.

مفاتيح الحالة: `VERIFIED` (بدليل) · `PARTIAL` · `FAILED` · `NOT IMPLEMENTED` · `NOT VERIFIED` (يلزم تمريرة عميقة/وكيل اختبار).

---
## 0) الملخص التنفيذي
- **الوضع العام: PARTIAL — غير جاهز للإنتاج بسبب P0 واحد مؤكد (ازدواج ذمم في الدفتر الخام).**
- البنية سليمة معمارياً: كاتب محاسبي وحيد (`AccountingEngine`)، حدود أمان في الخلفية، مساعد كاترينا للقراءة فقط افتراضياً.
- المشكلة الجوهرية الوحيدة الحرجة: **طبقتان تاريخيتان + قانونية تكتبان ذمة العميل (005) لنفس المركبة دون إلغاء متبادل** → تضخّم AR في الدفتر الخام.

---
## 1) SYSTEM_INVENTORY  — `VERIFIED`
- **Frontend:** React 18.3.1 (CRA / react-scripts 5), react-router-dom 6.26, TanStack Query 5, Tailwind 3.4 + shadcn/radix, i18next (عربي أساسي RTL)، recharts، jspdf/html2canvas، sonner. 62 صفحة، ~140 مكوّن.
- **Backend:** FastAPI 0.135 + Starlette 0.52، Python، uvicorn (supervisor). ~53,300 سطر عبر ~90 ملف. أكبر الملفات: `routes_finance.py` (6,264)، `routes_extended.py` (6,064)، `server.py` (3,348).
- **قواعد البيانات (هجين مؤكد):**
  - **Supabase/Postgres** (عبر service_role، PostgREST): vehicles, vehicle_visits, operations, journal_entries, accounts, customers, parts, services, invoices, approval_requests, business_accounts, transactions, technicians.
  - **MongoDB (motor/pymongo):** users, auth_credentials, auth_refresh_tokens, trusted_devices, auth_audit, document_templates, invoice_templates, outbound_*, workshop_profile/settings, suppliers, maintenance_orders, tickets…
  - ⚠️ ملاحظة مؤكدة حياً: جدولا `suppliers` و`users` **غير موجودين في Supabase** (`Could not find table`) — مصدرهما Mongo. أي كود يفترض وجودهما في Supabase = مسار ميت/خطأ محتمل.
- **AI/LLM:** emergentintegrations + litellm + google-genai + openai (كاترينا). **Storage:** boto3/s3 (object storage). **Payments:** stripe (مثبت، غير مؤكد الاستخدام الحي). **Comms:** whatsapp (Infobip)، Notion، Google.
- **Deploy:** Emergent platform؛ الإنتاج `car-repair-sys.emergent.host` يشارك **نفس** قاعدة Supabase مع المعاينة (سجل سابق).

## 2) ARCHITECTURE_MAP — `VERIFIED`
- **نمطان متعايشان:** (أ) الطبقة المسطّحة القديمة `routes_*.py` (المسيطرة)، (ب) بنية domain-driven أحدث `domains/{customers,vehicles,suppliers,bot_audit}` + `financial_control/` (router/four_eyes/findings_engine/approval_engine). كلاهما مُركّب في `server.py`.
- **الكاتب المحاسبي الوحيد:** `core/accounting_engine.py::post_entry`. 14 مستدعياً، جميعها عبر المحرك. ✅
- **حد الأمان:** الواجهة → FastAPI فقط (لا وصول DB مباشر من المتصفح — مؤكد). الخلفية → Supabase بمفتاح service_role (**يتخطى RLS**). ⇒ **RLS ليس حد الأمان؛ الحد هو `auth_guard` + RBAC في الخلفية.**

## 3–7) FRONTEND / PAGE / BUTTON / FIELD / FORM MATRICES — `NOT VERIFIED` (تمريرة عميقة لاحقة)
- الجرد الكمي مؤكد: 62 صفحة، ~140 مكوّن، مسارات محددة في `App.js` (Dashboard, Customers, VehicleDetails, Operations, DebtFollowUp, JournalEntries, ComprehensiveFinancial, FirewallPanel, InvoiceDesignerStudio, Settings, …) + مسارات عامة بلا مصادقة: `/login`, `/approval/:token`, `/report/:token`, `/track/:trackingId`.
- **لم يُنفَّذ** فحص كل زر/حقل/نموذج فردياً (يتطلب `testing_agent` frontend E2E). الحالة الأمينة: `NOT VERIFIED` — لا يجوز ادعاء PASS بلا دليل.
- ملاحظة تنظيف: صفحات `*_old.jsx` مكرّرة (BalanceSheet_old, CashFlow_old, Customers_old, Suppliers_old, Technicians_old, IncomeStatement_old) + orphans (Knowledge, DieselExpertChat, InjectorDiagnostics) = **DEAD CODE** مرشّح للحذف (P3).

## 8) API_INVENTORY — `VERIFIED (كمياً)`
- ~50 راوتر مُركّب في `server.py` (`include_router`). أعلى الكثافة: finance (44 endpoint)، extended (36)، advanced (27)، action_runtime (25)، templates_extended/assistant (20).
- كل المسارات تحت `/api/*` وتخضع لـ`auth_guard` عدا القائمة العامة (login/refresh/logout/google session + المسارات العامة بالـtoken).
- **NOT VERIFIED:** اختبار IDOR/BOLA/mass-assignment لكل endpoint فردياً (Section 12) — يلزم تمريرة أمنية مخصّصة.

## 9) DATABASE_INVENTORY + INTEGRITY — `VERIFIED` (حي، قراءة فقط)
عدادات حيّة (2026-06): vehicles=217, vehicle_visits=202, operations=98, journal_entries=150, accounts=200, customers=230, parts=183, services=583, invoices=460, approval_requests=176, business_accounts=4, transactions=62, technicians=5.
- **الدفتر متوازن:** إجمالي مدين = إجمالي دائن = **205,570.06**؛ قيود غير متوازنة = **0**. ✅
- **رصيد الذمم الخام (حساب 005) في الدفتر = 26,901.00** مقابل **الذمة القانونية (المحرك الموحد) = 14,832.00** عبر 6 مدينين ⇒ **فجوة ≈ 12,069** (كانت 15,691 في لقطة أقدم — البيانات حيّة تتحرك بنشاط الإنتاج).
- **توزيع مصادر القيود (الدليل على الازدواج):** vehicle_visit=33 (قانوني)، unified_visit_payment=37 (دفعات)، operation=31، reversal=16، manual=7, **fin_engine_align_v1=7**, **active_vehicle_ar_repair=7**, **hist_vehicle_ar_repair=3**, historical_financial_repair=3, ajel_supplier_purchase=3, operation_payment=2, period_close=1.

## 10) CRUD REALITY — `PARTIAL`
- كيانات أساسية (vehicle/visit/operation/customer/part/service/invoice/user) لها مسارات CRUD في الخلفية + RBAC. لكن التحقق الفعلي per-entity (خاصة DELETE + rollback + audit) `NOT VERIFIED` بالكامل — يلزم `testing_agent`.
- **مؤكد:** حذف القيود المحاسبية لا يحذف فعلياً — يُنشئ **قيداً عكسياً** عبر `AccountingEngine.reverse_entry` (Immutable Ledger). ✅

## 11–12) API SECURITY — `PARTIAL`
- **VERIFIED:** `auth_guard` ASGI middleware يفرض JWT على `/api/*`؛ RBAC عبر `config/role_permissions.json` + `APPROVER_ROLES={admin,manager,supervisor,accountant}`؛ RateLimit (SlowAPI + SecurityHeaders middleware)؛ CORS بأصول صريحة + credentials (لا wildcard في الكود؛ الـedge الخارجي يضيف wildcard — قيد منصة موثّق).
- **NOT VERIFIED:** IDOR/BOLA/mass-assignment الفعلي لكل مورد؛ يلزم اختبار اختراق مخصّص.

## 13/20) DATABASE / RLS — `VERIFIED (architecture)`
- الخلفية تستخدم service_role ⇒ **RLS متجاوَز بحكم التصميم**. لا يوجد وصول عميل مباشر لـSupabase (مؤكد: صفر استخدام supabase-js في الواجهة عدا رابط لوحة Setup + SQL إرشادي). ⇒ اعتماد الأمان كليّاً على طبقة الخلفية. **توصية P1:** توثيق ذلك صراحة + التأكد أن مفتاح service_role لا يُسرَّب (انظر §36).

## 16 + 28) FINANCIAL SSOT — 🔴 **P0 (السبب الجذري)**
- **SSOT مطبّق جزئياً:** كاتب وحيد `AccountingEngine` ✅؛ صفر كتابة مباشرة على `journal_entries` من مسارات حيّة (الوحيدة في سكربت offline `scripts/cleanup_test_data_feb2026.py`) ✅؛ الواجهات ممنوعة من إنشاء قيود ✅؛ قراءة الذمم موحّدة عبر `build_current_ar_snapshot` ✅.
- **الانتهاك:** لا يوجد **معرّف عمل موحّد للمركبة** يمنع الازدواج **عبر مصادر مختلفة**. الـidempotency مقيّد بـ`reference_id` لكل مصدر (`vehfinal:`/`visitfinal:`)، فلا يمنع تعايش:
  - **طبقة تاريخية (سكربتات لمرة واحدة، أغسطس 4):** `active_vehicle_ar_repair` (`scripts/post_active_vehicle_receivable_journals.py`) + `fin_engine_align_v1` (`scripts/align_financial_engine_journal_balances.py`) + `hist_vehicle_ar_repair` (`scripts/restore_historical_vehicle_receivables.py`) + قيود `operation` المؤقتة `[قيد مؤقت — بيع آجل]`.
  - **طبقة قانونية (حيّة):** `[CANONICAL_BUSINESS]` من `core/vehicle_finalization_posting.py` عبر `server.py` (اعتماد المركبة) و`routes_extended.py POST /finance-engine/visits/{id}/finalize`.
- **النتيجة:** أي مركبة لها ذمة تاريخية ثم اعتُمدت قانونياً → تُدبَّت ذمتها مرتين؛ الدفعات تُسوّي القانونية فقط فيبقى رصيد الطبقة التاريخية زائداً. القارئ القانوني (المحرك الموحد) يقرأ من حالة المركبة/الزيارة لا من الدفتر، فيظهر الرقم الصحيح بينما الدفتر الخام منتفخ. (أدلة المركبات في `reconciliation_ar_report.json`).

## 17/18/19) IDEMPOTENCY / AUTH / AUTHZ — `PARTIAL→VERIFIED`
- **Auth:** JWT عبر كوكيز httpOnly (access+refresh)، الواجهة تحفظ التوكن في الذاكرة فقط (XSS hardening سابق)، brute-force lock، logout يبطل العائلة. `VERIFIED` (سجل سابق + كود).
- **Idempotency:** الترحيل القانوني idempotent per reference_id ✅؛ مسار الدفعات يدعم Idempotency-Key. لكن **الازدواج عبر المصادر غير محمي** (نفس جذر P0).

## 21–25) KATRINA / AI SECURITY — `VERIFIED (posture قوي)`
- 28 أداة مسجّلة في `core/tool_router.py`، **كلها read-only افتراضياً**. أدوات الكتابة تتطلب `BOT_ALLOW_WRITES=1` (غير مضبوط في `.env` ⇒ **الوضع الحالي: قراءة فقط**). الأداة الكتابية الوحيدة = إرسال واتساب، محكومة بالعقد.
- **بوابة صلاحيات server-side:** `sensitivity=revenue` fail-closed (رفض صريح لغير المخوّل، بلا صفر صامت)؛ لا يمكن حقن `actor_role` من جسم الطلب.
- **الكتابة المالية لا تمر عبر أدوات البوت** بل عبر مسار الاعتماد المنفصل (`action_runtime` + أربع أعين). ⇒ كاترينا لا تستطيع Create/Update/Delete سجلات مالية عبر الأدوات.
- **NOT VERIFIED:** اختبار prompt-injection الفعلي عبر محتوى غير موثوق (أسماء عملاء/ملاحظات) — يلزم تمريرة مخصّصة (Section 24).

## 30/31) ERROR HANDLING / OBSERVABILITY — `PARTIAL`
- تتبّع LLM عبر `llm_traces` (tr-*)، `accounting_audit`, `journal_attribution` (من فعل ماذا)، `auth_audit`. حالات UI (loading/error/empty) مؤكدة على دفتر اليومية. الباقي `NOT VERIFIED`.

## 32–39) PERFORMANCE / CACHING / CDN / CI-CD / DEPS / A11Y / MOBILE — `NOT VERIFIED`
- ملاحظة أداء معمارية موثّقة: `_fetch_journal_entries` يجلب كامل الدفتر ثم يفلتر في بايثون (مقبول الآن، يلزم دفع الفلاتر لـSQL عند تجاوز آلاف القيود).

## 36) SECRETS — 🟠 P1
- `.env` أُعيد لـgit (مستودع خاص) لتمكين إعادة البناء. **P0 سابق مؤجّل: تدوير الأسرار** (JWT_SECRET, SUPABASE_SERVICE_ROLE_KEY, EMERGENT_LLM_KEY) — بانتظار قرار المالك. لا أسرار تُكشف للواجهة/للـAI (مؤكد).

---
## 24) ROOT_CAUSE_REPORT — P0-DUP-AR
- **ID:** P0-DUP-AR · **Severity:** P0 · **Component:** Financial ledger (account 005) · **Action:** vehicle/visit finalization.
- **Observed:** رصيد الذمم الخام في الدفتر (26,901) > الذمة القانونية (14,832)؛ فجوة ≈ 12,069.
- **Expected:** الدفتر الخام = القانوني (فجوة 0.00 بعد استبعاد المعكوس).
- **Trace:** finalize (server.py/routes_extended) → `post_vehicle/visit_finalization_canonical_entry` → `post_entry` (يدبّت الإجمالي كاملاً) — **دون فحص/عكس** ذمة تاريخية سابقة لنفس المركبة من سكربتات الإصلاح.
- **First incorrect layer:** طبقة الترحيل القانوني (لا تملك حارس تجاوز/عكس للطبقة التاريخية) + بقاء سكربتات الإصلاح القديمة حيّة في الدفتر.
- **Impact:** تضخّم AR/الإيراد في الدفتر الخام والميزان (ليس في عروض الذمم القانونية التي تقرأ من حالة المركبة).
- **Evidence:** `reconciliation_ar_report.json` + توزيع المصادر الحي أعلاه.

## 25) REPAIR_PLAN (مقترح — لم يُنفَّذ)
- **P0-DUP-AR:**
  - م0: snapshot كامل قبل أي تعديل.
  - م1: عكس قيود الطبقة التاريخية (active_repair/align/hist/operation المؤقتة) **حصراً** للمركبات التي لها قيد `[CANONICAL_BUSINESS]` مطابق — عبر `AccountingEngine.reverse_entry` (بلا حذف).
  - م2 (قرار حالة بحالة): ذمم حيّة بلا قيد قانوني + دفعات ناقصة الترحيل — قائمة قرار، بلا ترحيل تلقائي.
  - م3 (إصلاح جذر منع التكرار): حارس في الترحيل القانوني يعكس/يستبعد ذمة تاريخية لنفس المركبة + تقاعد سكربتات الإصلاح.
  - م4: إعادة تشغيل التسوية لإثبات فجوة 0.00 + `testing_agent` انحدار.
- **P1:** تدوير الأسرار · توثيق حد الأمان (RLS متجاوَز) · تنظيف DEAD CODE (`*_old.jsx`, orphans).

## 26) PRODUCTION_READINESS SCORECARD
| المجال | الحالة |
|---|---|
| Architecture / Single Writer | VERIFIED ✅ |
| Auth / Session | VERIFIED ✅ |
| Authorization (RBAC) | PARTIAL |
| Katrina / AI Security | VERIFIED ✅ (read-only posture) |
| Financial SSOT | 🔴 FAIL (P0-DUP-AR) |
| Data Integrity (ledger balance) | VERIFIED ✅ (متوازن) لكن AR منتفخ |
| API Security (IDOR/BOLA) | NOT VERIFIED |
| Frontend/Buttons/Fields | NOT VERIFIED |
| Performance/Caching/CI-CD/Backup | NOT VERIFIED |
| Secrets rotation | 🟠 P1 مؤجّل |

**النتيجة النهائية: NOT PRODUCTION READY** — بسبب P0-DUP-AR (إضافة إلى مجالات NOT VERIFIED تحتاج تمريرات عميقة).
