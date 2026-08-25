# STATIC DISCOVERY CLOSURE REPORT — نظام الورشة (finmodule-sync) + كاترينا
2026-06 · **READ-ONLY بالكامل — صفر إصلاح / صفر تعديل / صفر mutation.**
يُغلق الفجوات الثابتة في FULL_DISCOVERY_MASTER_REPORT دون إعادة العمل المُثبَت. أدلة: `/app/memory/discovery/*.json,*.md`.

---
## 1) FE → BE RECONCILIATION — كل 206 مصنّفة (المجموع = 206 ✓)
| التصنيف | العدد |
|---|---|
| MATCHED_EXACT (method+path) | 165 |
| MATCHED_DYNAMIC_PREFIX (يُحلّ عبر base-var prefix) | 23 |
| MISSING_BACKEND_ENDPOINT | 17 |
| UNRESOLVED (parser artifact: سلسلة متعددة الأسطر) | 1 |
| EXTERNAL_SERVICE / DEAD_FRONTEND_CALL | 0 |
| **المجموع** | **206** |

**الـ23 MATCHED_DYNAMIC_PREFIX** (base-var → prefix مُثبَت): `workshop-bot` (engines, models, catalog/summary, skills, skills/{}, conversations, conversations/{}, respond) · `runtime`+`financial-control`+`/api` (approvals/matrix, approvals/stats, approvals/{}/approve, approvals/{}/reject, approvals/{}/{}) · `financial-control` (findings, findings/scan, findings/summary, findings/{}/{}) · `suppliers-ext` ({}/settlements, {}/settlements/{}, {}/transactions, import/preview, import/execute) · `user-layouts/{}/{page}`.

**الـ17 MISSING_BACKEND_ENDPOINT** (نداء FE بلا endpoint خلفي مطابق — ميزة معطّلة/dead):
| FE call | ملف FE | method | مصدر |
|---|---|---|---|
| `/api/ai/enhanced-chat` | services/api.js (aiAPI.chat) + CustomerChatbot.jsx | POST | — لا endpoint |
| `/api/ai/search-solutions` | services/api.js | GET | — |
| `/api/ai/workshop/info` | services/api.js | GET | — |
| `/api/ai/workshop/diagnose` | services/api.js | POST | — |
| `/api/ai/workshop/search-technical` | services/api.js | POST | — |
| `/api/ai/workshop/service-report` | services/api.js | POST | — |
| `/api/ai/workshop/appointment` | services/api.js | POST | — |
| `/api/auth/verify-otp` | services/api.js (authAPI) | POST | auth_jwt بلا verify-otp |
| `/api/files/upload` | services/api.js (filesAPI) | POST | الرفع الفعلي = /vehicles/{id}/upload-file |
| `/api/customers/{}/approvals` | (caller) | GET | — |
| `/api/customers/{}/history` | (caller) | GET | — |
| `/api/invoice-templates/import` | templates FE | POST | — |
| `/api/invoice-templates/import-url` | templates FE | POST | — |
| `/api/invoice-templates/{}/hard` | templates FE | DELETE | — |
| `/api/reports/public/{}` | ReportPublic.jsx | GET | الموجود=/api/report/{id} (assistant) + /api/approvals/public/{token} |
| `/api/vehicles/track/{}` | services/api.js + CustomerTracking.jsx | GET | — |
| `/api/technicians/{}` | Technicians FE | PUT/DELETE | الموجود=GET/POST فقط |

**ملاحظة تقاطع (item 3/10):** 6 من MATCHED_DYNAMIC_PREFIX (findings*, approvals/matrix, approvals/stats) مصدرها **`FinancialControl.jsx` (صفحة ميتة غير مُوجَّهة)** — الـendpoint موجود لكن الـcaller غير قابل للوصول (dead UI رغم سلامة الـbackend).

---
## 2) STATIC AUTHORIZATION MATRIX — كل 512 endpoint (المجموع = 512 ✓)
| التصنيف | العدد |
|---|---|
| PUBLIC_INTENTIONAL | 17 |
| AUTHZ_COMPLETE (دور + object-level) | **0** |
| ROLE_CHECK_ONLY | 34 |
| AUTH_ONLY_NO_OBJECT_CHECK | 379 |
| **MISSING_AUTHZ** (مسار تعديل حسّاس بلا فحص دور) | **82** |
| UNKNOWN | 0 |
| **المجموع** | **512** |
- endpoints مُعدِّلة (POST/PUT/PATCH/DELETE): **272** · نطاق مالي: **150**.
- 🔴 **النتيجة الحرجة:** **صفر endpoint يفرض تفويضاً على مستوى الكائن (object-level)**؛ 82 مسار تعديل حسّاس (users/roles/financial/files/approvals) بلا أي فحص دور داخل الـhandler — يعتمد فقط على `auth_guard` (مُصادَق بأي دور). القائمة الكاملة في `11_AUTHORIZATION_MATRIX.md`. أمثلة: كل `/api/users*`, أغلب `routes_advanced/accounts_extended/templates_extended/financial_control/services/invoices/parts` المُعدِّلة.
- هذا تصعيد لـ**P1-AUTHZ-COVERAGE → قريب من P0** (منهجي): تصعيد الصلاحيات ليس محصوراً بـ/api/users فقط.

---
## 3) CROSS-LAYER TRACE لكل domain
| Domain | Route→Page→FE API→BE→Authz→Service→DB→Audit | التصنيف |
|---|---|---|
| Finance/Journal | ✅ كامل عبر AccountingEngine (كاتب وحيد) + audit | FULL_STATIC_TRACE |
| Vehicles | ✅ VehicleDetails→routes/domains→supabase | FULL_STATIC_TRACE |
| Customers | ✅ (لكن /customers/{}/approvals,history مفقودة FE) | PARTIAL_STATIC_TRACE |
| Operations/Visits | ✅ + canonical finalization | FULL_STATIC_TRACE |
| Payments | ✅ unified_visit_payment | FULL_STATIC_TRACE |
| Suppliers | ✅ suppliers-ext (settlements/transactions/import) | FULL_STATIC_TRACE |
| Approvals | ازدواج backend (routes_approvals + action_runtime + financial_control)؛ FE حيّ=KatrinaApprovalsTab، ميت=FinancialControl | PARTIAL_STATIC_TRACE |
| Users/Roles | UI مُوجَّه (Users) + backend، لكن **authz مفقود** | BROKEN_TRACE |
| Files/Upload | FE filesAPI→endpoint مفقود؛ vehicle upload=path traversal | BROKEN_TRACE |
| Katrina | ✅ tools قراءة + audit | FULL_STATIC_TRACE |
| Financial-Control (findings UI) | backend حيّ، FE (FinancialControl.jsx) غير مُوجَّه | DEAD |
| Public Report/Tracking | ReportPublic/CustomerTracking → endpoints مفقودة | BROKEN_TRACE |
| AI Chat (CustomerChatbot) | ai/enhanced-chat مفقود | BROKEN_TRACE |
**totals:** FULL=6 · PARTIAL=2 · BROKEN=4 · DEAD=1. (غير FULL مُدرَجة أعلاه).

---
## 4) WRITE-PATH REACHABILITY — كل 329 call-site (المجموع = 329 ✓)
| التصنيف | العدد |
|---|---|
| LIVE_PRODUCTION_API | 283 |
| LIVE_BACKGROUND_JOB (auto_sync) | 3 |
| LIVE_KATRINA | **0** |
| MIGRATION/SEED (seed_database/init_data/adopt/reset/import_services/merge/clean) | 22 |
| OFFLINE_SCRIPT | 10 |
| TEST_ONLY | 11 |
| DEAD_CODE / UNKNOWN | 0 |
| **المجموع** | **329** |
- **مسارات كتابة production-reachable حقيقية = 286** (283 API + 3 background). Katrina لا تكتب (0).
- الكتابة على `journal_entries` = **`post_entry`×14 فقط** (كاتب مالي وحيد؛ الحذف المباشر الوحيد في سكربت offline).
- تفصيل live writers (caller/table/audit/idempotency/financial) في `42_WRITE_PATH_INVENTORY.md` + `WRITE_PATH_REACHABILITY.md`.

---
## 5) BUTTONS / FIELDS / FORMS — مُصنّفة بالكامل (المجموع = total ✓)
**Actions (472):** STATIC_FULLY_TRACED=287 · UI_ONLY=4 · **DEAD=181** · BROKEN/EXTERNAL/UNKNOWN=0 — **SUM 472 ✓**
**Fields (343):** UI_TO_API_TO_SCHEMA_TO_DB=190 · UI_ONLY=11 · **DEAD=142** · UNKNOWN=0 — **SUM 343 ✓**
**Forms (37):** FULL_STATIC_SUBMIT_PATH=21 · **DEAD=16** · UI_ONLY/PARTIAL/UNKNOWN=0 — **SUM 37 ✓**
- 🔴 **~38% من معالجات الأزرار (181/472) و41% من الحقول (142/343) و43% من النماذج (16/37) تقع في 26 صفحة ميتة غير مُوجَّهة** (dead UI surface ضخم). التفاصيل في `closure_misc.json`.

---
## 6) KATRINA COUNT RECONCILIATION (28 ↔ 26)
- **register_tool call-sites = 27** (أسماء أدوات) · العدّ السابق «28» = 27 نداء + سطر `def register_tool` (miscount).
- عند `BOT_ALLOW_WRITES` غير مضبوط (الحالي): **26 أداة مُسجّلة، كلها قراءة.**
- `whatsapp.send` (write=True) تُسجَّل **فقط** عند `BOT_ALLOW_WRITES=1` → غير مُسجّلة حالياً.
- **العدد القانوني النهائي: 27 تعريف · 26 نشطة للقراءة · 1 كتابة مبوّبة (معطّلة حالياً) · 0 مكرّرة/محذوفة.** الفرق مشروح بالاسم (whatsapp.send).

---
## 7) ROUTES COUNT RECONCILIATION (44 ↔ 41)
العدّ القانوني من App.js (`lazy()` + import مباشر):
- `<Route path>` صريحة = **41** · index = 1 · (العدّ السابق «44» كان grep تقريبياً شمل أسطر غير-path).
- التفصيل: **Public = 4** (/login, /approval/:token, /report/:token, /track/:trackingId) · **Protected page routes = 28** · **Redirects (Navigate) = 8** (catalog, profile, import, users, denso-diagnostics, fault-knowledge, ai-financial, moltbot) · **Fallback `*` = 1** · **Test-stub `accounting/test`=div = 1** · **index = 1**.
- **Dynamic routes = 5** (:id ×2، :token ×2، :trackingId). **Dead routes = 0** (كلها تشير لمكوّن حقيقي؛ accounting/test = stub).
- **العدد القانوني: 32 مسار صفحة فعلي (4 عام + 28 محمي) + 8 تحويلات + fallback + index + stub.**

---
## 8) JOURNAL ATTRIBUTION — الفرق + تصنيف القيود الـ8
- **0 referential orphans** = كل vehicle_id/visit_id في العمليات/الزيارات يشير لسجل موجود (سلامة FK تطبيقية). **لا يعني** أن كل قيد له provenance عمل صحيح — لذلك فُحص الـ8 بلا reference منفصلاً.
- **الـ8 قيود بلا reference_id (المجموع = 8 ✓):**
  - `legitimate_unreferenced` = **1** → إقفال فترة (2270c734 «إقفال الفترة حتى 2026-08-10») — سليم.
  - `manual` (test/QA net-zero) = **7** → 6 «قيد اختبار مؤقت للحذف العكسي/probe» + 1 «[TEST_ORIGIN_QA] iter360 net-zero» — **قيود اختبار QA (net-zero، بلا أثر مالي)**.
  - `legacy` / `missing_business_reference` / `unknown` = **0**.
- **الخلاصة:** لا يوجد قيد إنتاجي حقيقي بلا provenance؛ 7 منها قيود اختبار QA يُفضّل تنظيفها (P3، صفر أثر مالي)، و1 إقفال فترة مشروع.

---
## 9) TEST → FEATURE MAPPING (static؛ 240 ملف backend + 6 FE)
| feature حرج | ملفات اختبار (بالاسم) | حالة |
|---|---|---|
| auth/login/otp | 12 + 1 + 1 | ✅ present (unit+integration) |
| authorization/permission/guard | 2 permission + 5 guard | 🟡 ضعيف (لا مصفوفة authz شاملة رغم 82 MISSING_AUTHZ) |
| users | 4 | ✅ |
| financial/journal/reconcil/ledger/account | 25+5+6+1+7 | ✅ قوي |
| payment/settle | 13 | ✅ |
| approvals/four-eyes | 3 + 2 | ✅ |
| katrina/bot/assistant/agent/tool | 8+15+2+1 | ✅ |
| files/upload | 3 + 1 | 🟡 وظيفي لا أمني (لا اختبار path-traversal) |
| reversal | 3 | ✅ |
| **idempotency** | **0 (بالاسم)** | 🔴 فجوة (لا اختبار مخصّص؛ مُغطّى ضمنياً في finance) |
- **فجوات مؤكدة:** مصفوفة تفويض شاملة (authz) · أمان رفع الملفات (path traversal) · idempotency مخصّص.

---
## 10) DEAD / LEGACY REACHABILITY
- **26 صفحة ميتة** (غير مستوردة في App.js ولا في أي مكوّن — تُشذَّب من الحزمة): **DEAD_CONFIRMED** جميعها. تشمل: BalanceSheet/CashFlow/IncomeStatement/TrialBalance (منفصلة — المُوجَّه ComprehensiveFinancial)، ChartOfAccounts (المُوجَّه=ChartOfAccountsLiquid)، FinancialControl، BusinessAccounts، SmartPOSJournal، Users (المُوجَّه=UsersManagement)، References/Templates/PartsCatalog، DieselExpertChat/GeminiChatBot/Knowledge/PublicAgent/InjectorDiagnostics(+V7)/InvoiceTemplateStudio(+V2)، + كل `*_old`.
- **18 مكوّن بلا مرجع:** shadcn ui/* غير مستخدمة (avatar/calendar/slider/…) = DEAD_CONFIRMED (مكتبة، غير مستوردة)؛ مخصّصة (LiquidSiteBuilder/MoltBotCanvasRenderer/MenuEditor/FinanceGradientCard/DialogPortalSafe/VehicleDetailsChrome/workshop-bot Archive*) = DEAD_CONFIRMED.
- **سكربتات مالية legacy** (post_active_vehicle_receivable_journals / align_financial_engine_journal_balances / restore_historical_vehicle_receivables): **SCRIPT_MANUAL_ONLY** (لا تُستدعى من مسارات؛ تشغيل يدوي) — لكنها كتبت 17 قيداً حيّاً في الدفتر (سبب P0-DUP-AR).
- **RUNTIME_REACHABLE dead:** 0 (لا شيفرة ميتة على مسار إنتاج حيّ).

---
## COMPLETION GATE — الحالة
✅ كل 206 FE calls مصنّفة (المجموع 206) · ✅ كل 512 endpoint مصنّف authz (المجموع 512) · ✅ كل domain رئيسي له cross-layer trace/حالة صريحة · ✅ كل 329 write call-site مصنّفة reachability (المجموع 329) · ✅ 472 action + 343 field + 37 form مصنّفة (المجاميع مطابقة) · ✅ تعارض Katrina (26/27/28) محلول بالاسم · ✅ تعارض routes (44/41) محلول · ✅ الـ8 قيود بلا reference مصنّفة · ✅ test→feature للوظائف الحرجة مكتمل مع الفجوات · ✅ dead/legacy reachability مصنّفة.

# ✅ FULL STATIC DISCOVERY COMPLETE
**Runtime المتبقي (منفصل، لا يمنع اكتمال Static):** تنفيذ الأزرار/النماذج/CRUD الفعلي · IDOR/BOLA حي · انتقالات الحالة الممنوعة · التزامن/السباقات · فشل المعاملات · رفع ملف فعلي · prompt-injection exploit · E2E كتابي · deps vuln audit · backup restore · latency/load → **NOT VERIFIED — RUNTIME/MUTATION REQUIRED** (قاعدة إنتاج مشتركة + منع mutation).

## تحديث الحواجز (بلا إصلاح)
- 🔴 P0-DUP-AR (ازدواج ذمم) · 🔴 P0-SEC-USERS · 🔴 **P0/P1-AUTHZ-SYSTEMIC (82 MISSING_AUTHZ + 0 object-level)** — مُصعّد بعد هذه التمريرة.
- 🟠 P1: SEC-UPLOAD + شارد DB (Preview=Prod) + Secrets · 17 endpoint FE مفقود (ميزات معطّلة) · dead UI surface ضخم (181 action).
- 🔵 P3: 7 قيود اختبار QA للتنظيف · 26 صفحة + 18 مكوّن dead · فجوات اختبار (authz/idempotency/upload-security).
