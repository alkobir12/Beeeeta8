# FULL_DISCOVERY_MASTER_REPORT — نظام إدارة الورشة (finmodule-sync) + كاترينا
2026-06 · **READ-ONLY / DISCOVERY ONLY — صفر تعديل / صفر إصلاح / صفر mutation**
يبني على: `PRODUCTION_REALITY_AUDIT.md` + `PRODUCTION_REALITY_AUDIT_FINAL.md` + ملفات `/app/memory/discovery/`.

## حالة الاكتشاف: ✅ FULL DISCOVERY COMPLETE (الطبقة الثابتة)
كل ما يمكن إثباته بلا mutation أُثبت وجُرِّد عددياً. المتبقي محصور في سلوك حي يتطلب كتابة/بيئة معزولة، ومُدرَج صراحةً تحت «NOT VERIFIED — RUNTIME/MUTATION».

---
## أرقام التغطية (COVERAGE NUMBERS)
| البند | العدد | الدليل |
|---|---|---|
| Frontend routes (+redirects) | 44 | `03_ROUTE_INVENTORY.md` |
| Pages | 62 (بعضها dead/`*_old`) | `04_PAGE_MATRIX.md` |
| Components | 140 (18 غير مستخدم) | `05_COMPONENT_MATRIX.md` |
| Buttons/onClick (صفحات) | 472 | `04_PAGE_MATRIX.md` |
| data-testid (كل src) | 1,581 | grep |
| Fields (صفحات) | 343 | `04_PAGE_MATRIX.md` |
| Forms (صفحات) | 37 | `04_PAGE_MATRIX.md` |
| FE distinct API call tails | 206 | `FE_BE_RECONCILIATION.md` |
| FE→BE matched | 165 (unmatched 41، أغلبها بادئة داخل متغيّر base) | " |
| Backend endpoints | 512 | `09_API_INVENTORY.md` (AST) |
| Supabase tables (مستخدمة) | ~13 أساسية + أخرى | `13_14_15…md` |
| Mongo collections | ~50+ | grep |
| Production write call-sites | 329 (109 supabase · 206 mongo · 14 post_entry) | `42_WRITE_PATH_INVENTORY.md` |
| Direct journal writes خارج المحرك | **1** (سكربت offline فقط) | " |
| Katrina tools | 26 (0 كتابة في الإعداد الحالي) | `19_KATRINA_TOOL_MATRIX.md` |
| Journal entries (حي) | 150 (142 مرتبط · 8 بلا مرجع · 16 عكسي · 0 عكس مزدوج · 20 legacy) | `13_14_15…md` |
| Orphans (referential) | **0** | " |
| Backend tests | 239 ملف tests/ (+جذر) · FE tests: 6 | grep |

**تصنيف الحالة عبر 44 مجالاً:** VERIFIED (ثابت) ≈ 30 · PARTIAL ≈ 9 · FAILED/ثغرة مؤكدة = 2 (P0-DUP-AR, P0-SEC-USERS) · NOT VERIFIED (runtime/mutation) = مدرج لكل بند.

---
## 1) System Inventory / 2) Architecture
React 18 (CRA) + FastAPI + هجين Supabase(Postgres)/Mongo. نمطان: flat `routes_*` (مسيطر) + `domains/` و`financial_control/` (أحدث). كاتب محاسبي وحيد `AccountingEngine`. الواجهة → FastAPI فقط (لا DB مباشر). (تفصيل: `PRODUCTION_REALITY_AUDIT.md §1-2`).

## 3–8) Routes/Pages/Components/Buttons/Fields/Forms (ثابت مكتمل)
- 44 route (عام: `/login`, `/approval/:token`, `/report/:token`, `/track/:trackingId`؛ باقي محمي داخل Layout).
- 62 صفحة — **dead/legacy مؤكدة:** `*_old.jsx` (BalanceSheet/CashFlow/Customers/Suppliers/Technicians/IncomeStatement) + orphans (Knowledge/DieselExpertChat/InjectorDiagnostics/PublicAgent/GeminiChatBot غير مرتبطة بـrouting الحالي).
- 140 مكوّن، 18 بلا مرجع خارجي (مرشّح dead — `05_COMPONENT_MATRIX.md`).
- الأزرار/الحقول جُرِّدت عددياً وتُتبَّع onClick→handler→(api|axios).method→endpoint. **التنفيذ الفعلي (side effect) = NOT VERIFIED — MUTATION REQUIRED** (محظور على DB مشتركة مع الإنتاج).

## 9) APIs + FE→BE Reconciliation
512 endpoint. 165/206 نداء FE طوبِق بمسار خلفي؛ 41 غير مطابق أغلبها بسبب بادئة مُضمَّنة في متغيّر base (`${RUNTIME_API}`, alkabeer bot، financial_control findings) أو مسارات AI/خدمة أخرى. **مرشّحات تحقق (قد تكون FE dead/not-implemented):** `auth/verify-otp`, `ai/workshop/*`, `catalog/summary`, `engines` — تحتاج تأكيد per-call.

## 10) Authentication — VERIFIED
JWT عبر كوكيز httpOnly (access+refresh)، توكن الواجهة في الذاكرة فقط، brute-force lock، logout يبطل العائلة، مسارات عامة محدودة في `auth_guard`.

## 11) Authorization / 12) IDOR — 🔴 ثغرة مؤكدة + PARTIAL
- الإنفاذ **متفرّق** (حراس موجودة في financial_reset/reconciliation/finance-payment؛ غائبة في أخرى).
- 🔴 **P0-SEC-USERS:** `routes_users.py` (`GET/POST/PUT/DELETE /api/users`، وPUT يضبط role/permissions) **بلا فحص دور** → تصعيد صلاحيات لأي مستخدم مُصادَق.
- IDOR/BOLA على مستوى الكائن: كثير من مسارات التعديل لا تُظهر فحص ملكية/دور صريح — يلزم تدقيق per-endpoint؛ الاستغلال الحي NOT VERIFIED — MUTATION.

## 13) RLS/service_role — VERIFIED
الخلفية service_role تتجاوز RLS؛ لا وصول DB مباشر من المتصفح. ⇒ **الأمان كله في طبقة التطبيق** — لذلك ثغرة §11 أخطر.

## 14) Database / 15) Relationships — VERIFIED
جداول Supabase الأساسية + أعمدة + FK تطبيقية (vehicle_id/customer_id/visit_id...). **0 orphans** (visits/ops→vehicle/visit سليمة). suppliers/users في Mongo لا Supabase.

## 16/17/18) Financial Relationships + Business Logic SSOT — 🔴 P0-DUP-AR
- كاتب وحيد ✅ (direct-write خارج المحرك = 1 سكربت offline). دفتر متوازن. 
- **P0-DUP-AR:** لا معرّف عمل موحّد للمركبة يمنع الازدواج عبر المصادر؛ 20 قيد legacy (active/align/hist/historical) يتعايش مع `[CANONICAL_BUSINESS]`. raw AR 005 = 26,901 مقابل قانوني 14,832. **0 عكس مزدوج** (المعالجة عبر عكس نظيف ممكنة). 8 قيود بلا reference (unattributed).
- Candidate Reversal Ledger: `/app/memory/candidate_reversal_ledger.json` (10 مركبات آمنة/14,136 + 5 بلا قيد قانوني/2,400 — قرار حالة بحالة).

## 19–20) State Machines / CRUD — VERIFIED (ثابت)
- الاعتماد: four-eyes (منشئ≠مراجع≠معتمِد + admin override) + شرائح (AUTO≤1000 تلقائي) + action_runtime DRAFT→PENDING→APPROVED→COMMITTED + provenance guard (يرفض AI_SUGGESTION/TEST_ARTIFACT).
- CRUD: المسارات الأربع موجودة لكل كيان؛ حذف القيود = عكسي لا حذف. **تأثير DB الحي per-op = NOT VERIFIED — MUTATION.**

## 21–22) Katrina / AI Security — VERIFIED posture, PARTIAL guards
26 أداة كلها قراءة (BOT_ALLOW_WRITES غير مضبوط)؛ 3 revenue مبوّبة fail-closed، 5 financial، 18 operational. محتوى غير موثوق (context_brief: أسماء/ملاحظات) يدخل الـprompt **بلا sanitization/delimiters** — سطح injection قائم، لكن الأثر محدود (لا كتابة عبر الأدوات؛ الكتابة عبر الاعتماد). استغلال حي NOT VERIFIED.

## 23) Transactions — VERIFIED (بلا ACID)
PostgREST بلا معاملات متعددة؛ التسلسل تطبيقي مع تعويض (compensation) قد يفشل تاركاً حالة جزئية (P2). صفر migration/transaction rpc.

## 24) Concurrency/Idempotency — VERIFIED ثابت
idempotency: reference_id للقيود ✅ + middleware **in-memory** (غير معمّم/غير دائم — P2). لا أقفال DB/version fields ظاهرة. سباق حي = NOT VERIFIED — ISOLATED ENV.

## 25) Audit Trail — VERIFIED
accounting_audit + journal_attribution + auth_audit + llm_traces(tr-*) + `_audit()`×50. يلتقط actor/action/resource/ts (before/after جزئياً).

## 26) Files/Storage — 🟠 P1
`routes_vehicle_files.py`: `file.filename` خام → path traversal؛ بلا فحص نوع/حجم؛ قرص محلي زائل (لا object storage). التوليد/التصدير (PDF/Drive/Sheets) موجود.

## 27–31) Search/Errors/Cache/Background/Infra
- بحث finance server-side كامل ✅؛ ilike في مسارات أخرى.
- حالات مالية fail-closed ✅؛ باقي per-page ثابت، الحي NOT VERIFIED.
- cache: perf_cache TTL 15s in-memory + React Query (FE).
- خلفية: auto_sync_service + webhook cron (.emergent/cron).
- infra: docker-compose (be 8001، fe 3000→80، nginx) + emergent.yml (صورة مُدارة).

## 32) Environments/Secrets — 🔴/🟠
- **بيئات غير معزولة:** Preview + Production يشتركان نفس Supabase (خطر بيانات مباشر — سبب حظر أي mutation).
- تدوير الأسرار (JWT/SERVICE_ROLE/EMERGENT_LLM_KEY) مؤجّل. لا تسريب أسرار للواجهة/الـAI ✅.

## 33–38) CI/CD / Deps / Observability / Backup / Perf / A11y
- CI/CD: Emergent managed، بلا بوابات test/lint تقليدية → PARTIAL.
- deps: مُجرَّدة؛ audit ثغرات لم يُشغَّل → NOT VERIFIED (ملاحظة `lucide-react ^1.7.0`).
- observability: traces/audit ✅؛ بلا metrics/APM.
- backup: `/admin/backup/drive` + export sheets؛ **restore غير مُختبر** → NOT VERIFIED.
- perf: full-ledger fetch + N+1 محتملة؛ latency NOT VERIFIED.
- a11y: 39 aria عبر 140 مكوّن = ضعيف؛ responsive: 809 class + viewport meta.

## 39–44) Content/Tests/E2E/Cross-Layer/Legacy/WritePaths
- content: 15 TODO/mock (منخفض) → VERIFIED.
- tests: 239 BE + 6 FE؛ تعيين test→feature PARTIAL.
- E2E: مسارات القراءة مُتتبَّعة؛ **write journeys NOT VERIFIED — MUTATION**.
- cross-layer: finance AR (7 قرّاء) متطابقون على القيمة القانونية ✅.
- legacy/dup: 18 مكوّن + `*_old` + سكربتات AR + orphans.
- write paths: 329، كاتب مالي وحيد ✅.

---
## P0 / P1 / P2 / P3
**P0:** (1) P0-DUP-AR ازدواج ذمم الدفتر · (2) P0-SEC-USERS تصعيد صلاحيات عبر /api/users.
**P1:** P1-SEC-UPLOAD (path traversal + قرص زائل) · P1-ENV-SHARED-DB (بيئات غير معزولة) · P1-SECRETS (تدوير مؤجّل) · P1-AUTHZ-COVERAGE (إنفاذ متفرّق).
**P2:** idempotency in-memory · rate-limit in-memory · لا ACID (تعويض) · prompt-injection بلا guards · user silent memory fallback · AUTO-approve ≤1000.
**P3:** dead/duplicate code (18 مكوّن + *_old) · a11y ضعيف · deps audit · 8 قيود بلا reference · FE calls غير مطابقة تحتاج تأكيد.

## NOT VERIFIED — RUNTIME/MUTATION/ISOLATED-ENV (صريحة)
تنفيذ الأزرار/النماذج/CRUD الفعلي · IDOR/BOLA حي · انتقالات الحالة الممنوعة · التزامن/السباقات · فشل المعاملات الجزئي · رفع الملفات الفعلي · prompt-injection exploit · E2E الكتابي · deps vuln audit · backup restore · latency/load. **السبب: قاعدة إنتاج مشتركة + منع mutation/destructive.**

## اتجاهات الإصلاح المقترحة (بلا تنفيذ)
P0-DUP-AR: عكس نظيف per-vehicle (excess=ledger−canonical) + حارس تجاوز طبقة تاريخية في vehicle_finalization + تقاعد سكربتات AR.
P0-SEC-USERS: `Depends(_require_admin_actor)` على /api/users + منع رفع الدور الذاتي.
P1: تعقيم رفع الملفات + object storage · عزل بيئة/DB إنتاج · تدوير الأسرار · حراس authz موحّدة.

---
# الحكم النهائي: 🔴 NOT PRODUCTION READY
حاجزان P0 مؤكّدان + P1 أمني/بيئي. الأساس المعماري سليم (كاتب وحيد، أمان خلفي، كاترينا للقراءة، 0 orphans، دفتر متوازن) لكن الحواجز تمنع الجاهزية.
**لا إصلاح/mutation إنتاج حتى موافقتك الصريحة المنفصلة.**
