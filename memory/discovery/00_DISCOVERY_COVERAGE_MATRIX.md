# 00_DISCOVERY_COVERAGE_MATRIX — FULL SYSTEM DISCOVERY (READ-ONLY)
مشروع: نظام إدارة الورشة (finmodule-sync) + كاترينا · 2026-06 · صفر تعديل بيانات.
قاعدة الحالة الجديدة: الاكتشاف الثابت (static/code) يُنجز بالكامل ولا يُصنَّف NOT VERIFIED لمجرد منع الـmutation. فقط السلوك الذي يحتاج كتابة فعلية يبقى: **NOT VERIFIED — RUNTIME MUTATION REQUIRED**.
ملفات الأدلة المولّدة: `/app/memory/discovery/{03,04,05,09,13_14_15,19,42,FE_BE_RECONCILIATION}.md` + `*.json`.

| # | المجال | حالة الاكتشاف الثابت | السلوك الحي (runtime) |
|---|---|---|---|
| 1 | System Inventory | ✅ VERIFIED | — |
| 2 | Architecture Map | ✅ VERIFIED | — |
| 3 | Routes | ✅ VERIFIED (44 route/redirect) | reachability = read-only VERIFIED جزئياً |
| 4 | Pages | ✅ VERIFIED (62 صفحة، منها dead/old) | render per-page = NOT VERIFIED (E2E) |
| 5 | Components | ✅ VERIFIED (140، 18 غير مستخدم) | — |
| 6 | Buttons/Actions | ✅ VERIFIED (472 onClick + 1,581 testid مُجرَّدة + تتبّع handler→API) | تنفيذ فعلي = NOT VERIFIED — MUTATION REQUIRED |
| 7 | Fields | ✅ VERIFIED (343 حقل في الصفحات + تتبّع للـschema) | تحقّق خلفي per-field الحي = NOT VERIFIED — MUTATION |
| 8 | Forms | ✅ VERIFIED (37 نموذج) | submit فعلي = NOT VERIFIED — MUTATION |
| 9 | API endpoints | ✅ VERIFIED (512 endpoint، AST) | استجابة لكل مسار = read-only جزئي |
| 10 | Authentication | ✅ VERIFIED (JWT/cookie/refresh/logout) | — |
| 11 | Authorization/RBAC | 🔴 VERIFIED-كثغرة (إنفاذ متفرّق؛ /api/users بلا حارس) | استغلال حي = NOT VERIFIED — MUTATION |
| 12 | IDOR/BOLA | 🟡 PARTIAL (تتبُّع ثابت: كثير من المسارات بلا فحص object-level) | اختبار حي = NOT VERIFIED — MUTATION |
| 13 | service_role/RLS | ✅ VERIFIED (service_role يتجاوز RLS؛ الأمان = التطبيق) | — |
| 14 | Database | ✅ VERIFIED (جداول+أعمدة+عدادات حيّة قراءة) | — |
| 15 | Data Relationships | ✅ VERIFIED (FK تطبيقية، **0 orphans**) | — |
| 16 | Financial Relationships | ✅ VERIFIED (تحليل قراءة) — 🔴 P0-DUP-AR | — |
| 17 | Business Logic SSOT | ✅ VERIFIED (كاتب وحيد) — 🔴 ازدواج عبر المصادر | — |
| 18 | State Machines | ✅ VERIFIED (approval/action_runtime/visit) | انتقالات ممنوعة حيّة = NOT VERIFIED — MUTATION |
| 19 | CRUD | ✅ VERIFIED (مسارات الأربع موجودة لكل كيان) | تأثير DB الفعلي = NOT VERIFIED — MUTATION |
| 20 | Katrina Tools | ✅ VERIFIED (26 أداة، 0 كتابة حالياً) | — |
| 21 | AI Security Surface | ✅ VERIFIED (سطح مكشوف، بلا guards) | استغلال حي = NOT VERIFIED |
| 22 | Transactions | ✅ VERIFIED (لا ACID؛ تعويض تطبيقي) | فشل جزئي حي = NOT VERIFIED — ISOLATED ENV |
| 23 | Concurrency | ✅ VERIFIED (حراس ثابتة: in-memory) | سباق حي = NOT VERIFIED — ISOLATED ENV |
| 24 | Idempotency | ✅ VERIFIED (reference_id + in-memory key) | — |
| 25 | Audit Trail | ✅ VERIFIED (5 آليات) | — |
| 26 | Files/Storage | ✅ VERIFIED (static) — 🟠 P1 (path traversal + قرص محلي) | رفع فعلي = NOT VERIFIED — MUTATION |
| 27 | Search/Filter | ✅ VERIFIED (finance server-side؛ ilike غيره) | — |
| 28 | Error/Loading/Empty | 🟡 PARTIAL (مالي fail-closed؛ باقي per-page ثابت) | حي = NOT VERIFIED |
| 29 | Cache | ✅ VERIFIED (perf_cache 15s in-memory + React Query) | — |
| 30 | Background Jobs | ✅ VERIFIED (auto_sync + webhook cron) | تشغيل فعلي = NOT VERIFIED |
| 31 | Infrastructure | ✅ VERIFIED (docker-compose/nginx/emergent.yml) | — |
| 32 | Environment/Secrets | ✅ VERIFIED — 🔴 بيئات غير معزولة (Preview=Prod DB) + 🟠 تدوير مؤجّل | — |
| 33 | CI/CD | 🟡 PARTIAL (Emergent managed؛ بلا بوابات test/lint) | — |
| 34 | Dependencies | 🟡 PARTIAL (مُجرَّدة؛ audit ثغرات NOT VERIFIED) | — |
| 35 | Observability | ✅ VERIFIED (traces/audit)؛ بلا metrics/APM | — |
| 36 | Backup/Recovery | 🟡 PARTIAL (endpoints موجودة؛ restore NOT VERIFIED) | — |
| 37 | Performance | 🟡 PARTIAL (N+1/full-ledger-fetch ثابت) | latency = NOT VERIFIED |
| 38 | Responsive/A11y | 🟡 PARTIAL (809 responsive class؛ 39 aria=ضعيف) | runtime = NOT VERIFIED |
| 39 | Content Reality | ✅ VERIFIED (15 TODO/mock — منخفض) | — |
| 40 | Test Coverage | ✅ VERIFIED جرد (239 BE + 6 FE) | تعيين test→feature = PARTIAL |
| 41 | E2E | 🟡 read-only مُتتبَّع؛ write journeys = NOT VERIFIED — MUTATION | — |
| 42 | Cross-Layer Consistency | ✅ VERIFIED (finance AR readers متطابقة) / غيره PARTIAL | — |
| 43 | Legacy/Dead/Duplicate | ✅ VERIFIED (18 مكوّن + *_old + سكربتات AR) | — |
| 44 | Write Paths | ✅ VERIFIED (329 موقع؛ كاتب مالي وحيد) | — |
