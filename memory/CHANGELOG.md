# CHANGELOG

## 19 June 2026 — P0 Enterprise Operator: Centralized Accounting + Persistence + RBAC + Financial Actions

### 🏦 Phase 1 — Centralized Accounting Engine (`core/accounting_engine.py`)
- Single writer to Supabase `journal_entries`; validates double-entry balance (debit==credit).
- `IdentityStore` on MongoDB with UNIQUE index on `tx_hash` → race-safe idempotency. Hash = **item+price+time+customer** (+reference_id).
- `SupabaseGuardedClient` blocks direct journal_entries writes; `_insert_adaptive` strips unknown columns; `post_entry(entry)` adapter with safe fallback. Tested 9/9 (12-thread race → 1 winner).

### 💾 Phase 2 — Durable runtime state (`core/runtime_store.py`)
- Drafts/approvals/executions/audit persisted to MongoDB (`assistant_*`); write-through + hydrate on startup; survives restarts. Tested 11/11.

### 🔐 Phase 3 — Backend RBAC + Strict Four-Eyes (`core/rbac.py`, `routes_action_runtime.py`)
- Role/permission resolution from users store + `config/role_permissions.json`. Approver roles `admin,manager,supervisor`.
- Removed `reviewer:` bypass; approver = REAL identity. Strict Four-Eyes (`ACTION_RUNTIME_ENFORCE_4EYES=true`): self-approval → 403 `four_eyes_violation`; non-approver → 403 `permission_denied`. Tested 9/9 module + live API.
- ⚠️ BEHAVIOR CHANGE: solo self-approval of risky actions now blocked (needs 2nd approver, or set `ACTION_RUNTIME_ENFORCE_4EYES=false`).

### 💰 Phase 4 — Financial actions via engine (`core/financial_actions.py`, `routes_financial_actions.py`)
- `POST /api/finance-actions/{invoice,payment,expense}` — balanced, idempotent, RBAC-protected. Tested 6/6.

### 🧹 Journal daybook cleanup (`pages/JournalEntries.jsx`)
- Strip raw tags `[PARTY:..][VEHICLE_REF:..][VISIT:..][PARTY_TYPE:..]`; `cleanDescription` removes duplicated party/plate. Verified visually.

### 🔗 Single-source-of-truth wiring (COMPLETE)
- ALL `journal_entries` writes now route through `AccountingEngine.post_entry` (engine is `entry_id`-aware, adaptive columns, idempotent):
  `routes_extended` (`_safe_insert_journal_entry` + integrity_auto_fix), `routes_finance` (manual create + period-close + repair backfill), `routes_smart_accounting`, `routes_suppliers_extended`, `routes_firewall` auto-fix, `server.py` (cash-fix + operation sale).
- Verified: manual create dedups (repost → same id, 1 row); reports (trial-balance/income/cash-flow/balance-sheet) + firewall reconciliation all 200.

### 🔗 Full linkage verified (iteration 239 — 9/9 backend + frontend)
- engine → journal page → dashboard KPIs → reports → firewall reconciliation all consistent; clean daybook descriptions; bot auto-commit + Four-Eyes intact.


## 13 May 2026 — Smart POS reference operations + journal card clarity
- Smart POS now creates reference operations via `POST /api/operations` for most templates instead of only writing standalone journal entries.
- Journal entries API now exposes `payment_method`, `payment_method_label_ar`, `payment_status`, and `payment_status_label_ar`.
- Journal Entries cards now show clearer payment method/source/status pills in Arabic.
- Bank deposit remains a direct journal-entry flow for now.

## 13 May 2026 — OperationCard payment visibility fix
- Operations page now refetches operation data on mount instead of relying on stale cached status.
- Added explicit payment status pill, paid amount, and remaining balance display to `OperationCard.jsx`.
- Improved journal entry text fallback so service operations show `إيرادات الخدمات` instead of incomplete `الحساب` text.
- Verified on the real case: paid 300 / remaining 2000 is now clearly visible in the UI.

## 13 May 2026 — Live vehicle updates reflected in operations
- `GET /api/operations` and `GET /api/operations/{id}` now enrich vehicle-linked operations with live vehicle/customer fields from the current vehicle record.
- Operations responses now include `customerName`, `customerPhone`, `vehiclePlate`, `vehicleBrand`, and `vehicleModel` for linked vehicle operations.
- `OperationCard.jsx` now prefers live vehicle customer data for customer-linked vehicle operations.

## 13 May 2026 — Supplier/vehicle reference-page linking
- Added supplier journal-token parsing so supplier-linked manual/POS journal entries can be surfaced inside supplier movements.
- Added linked journal entries panel in `VehicleDetails.jsx` so vehicle/customer/visit-related journal entries appear inside the vehicle file.
- Improved suppliers loading state copy for long-running balance/movement fetches.
- Fixed `extractJournalTag` regex parsing in VehicleDetails after test feedback.

## 12 May 2026 — Payments ↔ Operations sync completed
- Linked operation payment fields to live visit payment data in `supabase_service.py`.
- `GET /api/operations` and `GET /api/operations/{id}` now surface `paymentMethod`, `paymentStatus`, `paymentAmount`, `totalPaid`, `advancePaid`, and `balance` from the linked visit when available.
- Verified the visit-linked operation flow without creating new test data.

## 12 May 2026 — Vehicle files + receipt vouchers + account mapping audit
- Fixed vehicle `fileNumber` and `customerFileNumber` save flow across backend and VehicleDetails UI.
- Fixed Smart POS account mapping so salary uses `036 رواتب إدارية` and payment methods map correctly to `003/004/006`.
- Added visit payment journal posting from VehicleDetails using `source=visit_receipt_voucher` and visit/customer/vehicle tokens.
- Improved `GET /api/finance/journal-entries/{entry_id}` to expose top-level fields plus backward-compatible `data`.
- Cleaned recent test data (test vehicles, test journal entries, and extra temporary payment artifacts).

## 11 May 2026 — Smart POS Journal completed
- Completed `SmartPOSJournal.jsx` as a single-screen Smart POS for journal entries.
- Added 8 templates: instant sale, cash sale, bank/card sale, salary, cash expense, collect customer, pay supplier, bank deposit.
- Merged the old cashier cart into the **items section** inside the same Smart POS flow.
- Added customer, vehicle, and items fields with live lookup from customers, suppliers, vehicles, parts, and services APIs.
- Saving now posts balanced journal entries to `POST /api/finance/journal-entries` with `[PARTY]`, `[PARTY_TYPE]`, `[VEHICLE_REF]` description tags.
- Added recent-entry copy flow and kept POS/full view toggle working.
- Hardened `JournalEntries.jsx` fetch lifecycle with `AbortController` during navigation.

## Verification
- `/app/test_reports/iteration_206.json` → PASS
- `/app/test_reports/iteration_205.json` → PASS
- `/app/test_reports/iteration_203.json` → PASS
- `/app/test_reports/iteration_202.json` → PASS
- `/app/test_reports/iteration_201.json` → PASS
- `/app/test_reports/iteration_200.json` → PASS (with low note fixed afterward)
- `/app/test_reports/iteration_199.json` → PASS
- `auto_frontend_testing_agent` → PASS
- `deep_testing_backend_v2` → 7/7 PASS

## 20 June 2026 — P0 Security Remediation (Pre-Deploy Audit fixes)
- FIXED broken login (undefined `ACCESS_TOKEN_EXPIRE_MINUTES`) that returned HTTP 500.
- Migrated RBAC from spoofable HTTP headers (`x-user-role`/`x-user-id`) to a signed JWT
  that embeds the authenticated role (`auth_jwt.create_access_token` + `identity_from_request`;
  `core/rbac.extract_identity` now reads identity/role ONLY from the JWT).
- Deny-by-default: `POST /api/auth/login` now rejects unknown/inactive users (401/403);
  no valid JWT ⇒ role `unknown` ⇒ 403 on protected routes.
- Token strategy: access token 60 min + refresh token 7 days; new `POST /api/auth/refresh`.
  Frontend (`utils/authToken.js`) silently refreshes on 401 and retries.
- Updated `routes_accounts_extended.py`, `routes_finance.py`, `routes_extended.py`,
  `routes_financial_actions.py`, `routes_action_runtime.py` to use JWT identity.
- Restricted CORS: `CORS_ORIGINS` no longer `*`; `allow_credentials=True` with explicit origins.
- Removed dormant duplicate repo: moved `/app/autoprofit-pro` (+ stray test scripts) out of `/app`.

## Verification (iteration_240)
- `/app/test_reports/iteration_240.json` → backend 30/31 PASS (97%), frontend 90%.
- Impersonation re-tested: spoofed `x-user-role: admin` w/o JWT → 403 on invoice/payment/expense.
- Four-Eyes: approver-role JWT required; accountant/technician/no-JWT rejected.
- Open (deferred, per user "no P1 this session"): edge-proxy CORS wildcard at preview ingress
  (app-level CORS is correct); silent unknown-user login toast (UX); button-nesting warning.

## 20 June 2026 — Reversal/Contra-Entry + Governance Doctrine compliance
- Implemented `AccountingEngine.reverse()` (core/accounting_engine.py): contra entry with dr/cr
  SWAPPED per line, preserves the ORIGINAL (No Hard Delete), source='reversal',
  reference_id='reversal::<orig>', idempotent (no double reversal).
- Added `reverse_entry()` wrapper (core/financial_actions.py) + RBAC-protected
  `POST /api/finance-actions/reverse` (needs journal_entries.delete OR approver role).
- GOVERNANCE FIX: action_runtime.delete_operation no longer hard-deletes journal_entries
  (Single-Writer violation) — it now REVERSES them through the engine.
- FIXED CRITICAL FE bug: Login.jsx fired loginAndIssueToken() fire-and-forget then did a
  full-page redirect, aborting the JWT request → no token stored → UI writes 403.
  Now AWAITs token issuance before redirect (all 3 login paths). Verified: auth_token
  stored, JWT role=admin.
- Bot verified: 21 read-only tools (write=false), /api/assistant/chat routes to real
  finance tools and returns grounded Arabic replies (proposer-only).

## Verification (iteration_241)
- `/app/test_reports/iteration_241.json` → backend 15/15 PASS (reversal, governance, bot).
- Reversal correctness verified against DB (line-swap, original preserved, balanced).
- FE JWT login race fixed & re-verified manually (token persisted before redirect).

## 20 June 2026 — Bot Capability Governance: Phase A + B (financial actions wired to كاترينا)
Per BOT CAPABILITY GOVERNANCE + DECISIONS (start A+B, stop for review, then C):
- Phase A: encoded Principle ① (real-source-only, resolve entity, ASK on missing/ambiguous)
  + tiered model (L1 quick-confirm / L2 four-eyes) + echo-back + financial-no-auto-commit
  in the assistant system prompt and intent parser.
- Phase B: wired create_invoice / collect_payment / create_expense / reverse_entry to the bot:
  * llm_intent_parser: 4 new ALLOWED_ACTIONS + prompt + examples.
  * unified_executor: financial actions are RISKY (always Four-Eyes, never auto-commit);
    _resolve_financial_target resolves the real customer/entry, builds echo-back, asks on
    missing/ambiguous (no guessing).
  * action_runtime: VALID_ACTIONS + commit() financial handler → financial_actions.* →
    accounting_engine (single writer), audit COMMIT_FINANCIAL.
  * assistant_kernel: financial verbs in looks_like_action, echo-back approval card
    (النوع/الطرف/المبلغ/الأثر المحاسبي + red line), clarification 'ask' messages.
- DX: chat 'executed' now includes approval_id; REST /finance-actions/invoice accepts amount alias.
- BOT_ALLOW_WRITES stays 0; financial writes flow via the runtime approval pipeline only.

## Verification (iteration_242) — 21/21 backend PASS
- Bot proposes invoice/payment/expense/reverse → ALWAYS pending_approval + echo-back (never auto-commit).
- Principle ①: missing amount / unknown customer → clarify (no fabricated values).
- Four-Eyes: same proposer → 403; different approver (احمد1) → committed via engine.
- Accounting integrity 100%: 50 recent journal entries all balanced (dr==cr); single-writer holds;
  reverse contra preserves original; site REST regression intact; safe entity actions still auto-commit.
- Phase C (L1 quick-confirm for safe entity actions) intentionally deferred for user review.

## 2 July 2026 — إصلاح جذري: البوت كان "أعمى" بعد تفعيل حارس المصادقة
المشكلة (أبلغ عنها المستخدم): كاترينا لا ترى أي بيانات — بحث INV001214 يرجع "لا توجد نتائج"
رغم وجود الفاتورة. السبب الجذري: auth_guard أصبح يفرض JWT على كل /api/* بينما أدوات البوت
(tool_router) تستدعي API الداخلي بلا توكن → 401 → قوائم فارغة.
- tool_router: توكن خدمة داخلي `_int_headers()` (كاترينا-internal, admin) مُرفق بكل 15 استدعاء httpx داخلي.
- operations.search: استخراج رقم الفاتورة من الاستعلام (extract_entities) + مطابقة inv-number
  متسامحة (شرطات/مسافات/حالة)، وكلمات عامة (فاتورة/رقم/عملية) لا تُشترط في الحقول.
- بطاقات/نتائج العمليات ترجع invoice_number (INVxxxxx) بدل بادئة UUID — تحسين UX مطلوب سابقاً.
- زيارة عبر البوت: تُنشئ الآن سجل العميل الحقيقي في customers (كانت الاسم فقط على المركبة)
  وتمرر الماركة (brand) للمركبة (كانت تُحفظ "غير محدد").
- فاتورة عبر البوت: اسم الخدمة يُقرأ من items[0].name/description (كان يسقط إلى "خدمة").
- test_accounting_integrity_v1.py: تسجيل دخول + تمرير JWT (كان يفشل 401 بعد الحماية).
### التحقق (يدوي كامل E2E)
- بحث INV001214 عبر /api/assistant/chat → وجدها بكامل التفاصيل + بطاقة بعنوان INV001214 ✅
- زيارة كاملة عبر البوت (عميل+جوال+تويوتا كامري+لوحة+خدمة 3200 آجل) → «نعم» →
  customers + vehicles(brand=تويوتا) + vehicle_visits(بند 3200) ✅
- فاتورة مالية 500 آجل → أربع أعين (مدير يقترح، احمد1 يعتمد) → operations(INV001265) +
  قيد متوازن 005/026 عبر katrina_operation ✅ (نُظّفت بيانات الاختبار بعدها)
- اختبار سلامة المحاسبة v1.0: 13/13 ✅ — الواجهة تعمل (لوحة التحكم + بوت عائم) ✅

## 2 July 2026 — Katrina Developer Mode (RRR) — المرحلة 1 ✅
قرارات المستخدم المعتمدة: (1) Proposals فقط — كاترينا لا تلمس ملفات الكود إطلاقاً،
Git/pytest خارج النطاق نهائياً. (2) المرحلة 1 فقط ثم قياس قبل المرحلة 2.
(3) rrr مقصور على admin. شرطان: أي Prompt Learning مستقبلي يتضمن prompt_version + rollback؛
وMemory Engine لا يُبنى قبل تعريف قواعد الترقية Short→Long→Knowledge كتابةً.
### المنفّذ
- core/developer_mode.py (جديد): trigger «rrr»/«rrr off»، admin-only من JWT role،
  بناء سياق مؤسسي كامل (PRD/CHANGELOG/ROADMAP/بنية الملفات/عقود API الحية من FastAPI/
  Schema حي من Supabase+Mongo/حالة محرك التنفيذ والتدقيق) مع كاش 5 دقائق وقياسات.
- assistant_kernel: اعتراض rrr قبل أي مسار + حقن dev_system_addendum في system prompt
  عند التفعيل + علم developer_mode في الرد + معامل proposer_role.
- routes_assistant: تمرير role_hint من JWT في /chat و /chat/stream.
### القياسات (المطلوبة لقرار المرحلة 2)
- حجم السياق: ~14,644 token (43,932 حرف) | زمن بناء السياق: ~3.0s (force) ثم كاش.
- زمن استجابة سؤال هندسي في الوضع: ~55s (claude-sonnet-4-6، ضمن حد 60s timeout — حدّي).
- الجودة: تحليل ديون تقنية دقيق من السياق الحقيقي + Proposal بالتنسيق المتفق
  (ملف/موضع/diff/مبرر/خطورة/فائدة/خطة اختبار) بدون ادعاء تنفيذ.
### التحقق E2E
rrr(admin)=تفعيل+شاشة ✅ | rrr(فرج1/accountant)=رفض ✅ | سؤال هندسي=Proposal صحيح ✅ |
rrr off=إيقاف ✅ | الجلسات العادية غير متأثرة (developer_mode:False) ✅
### توصية للمرحلة 2
الحقن الكامل يقارب حد الـ timeout — يُرجّح top-k retrieval انتقائي (حسب شرط المستخدم:
بعد تعريف قواعد الترقية Short→Long→Knowledge كتابةً).

## 2 يوليو 2026 — RRR: حل مشكلة 55s/60s جذرياً + اكتشاف وإصلاح تجمد النظام
### اكتشاف جوهري أثناء التشخيص
`emergentintegrations.LlmChat.send_message` يستدعي `litellm.completion` (sync!) داخل
async → **الـ event loop كان يتجمد بالكامل طوال توليد أي رد LLM** (قياس: /api/health
أخذ 15-30 ثانية أثناء التوليد). أثّر على كل مستخدمي النظام أثناء أي رد بوت.
### الإصلاحات
1. **إصلاح التجمد**: نقل نداء LLM إلى thread منفصل (asyncio.to_thread + asyncio.run)
   في assistant_kernel._llm_chat و llm_intent_parser → اللوب حر (health = 15ms أثناء التوليد).
2. **تقليص سياق RRR**: PRD مضغوط (عناوين+Backlog+Status)، CHANGELOG آخر إدخالين+عناوين،
   API contracts مدمجة methods/path، Schema أسماء جداول/أعمدة فقط →
   **~7.3K token (كان 14.6K)**.
3. **SSE heartbeat**: حدث progress كل 10 ثوانٍ أثناء التوليد (routes_assistant._stream).
4. **اكتشاف قيد منصة**: الـ ingress يقطع أي طلب عند 60s بالضبط حتى مع بث نشط.
   **الحل الجذري — Job/Poll recovery**: البث يعلن job_id أولاً؛ النتيجة تُخزَّن في
   _CHAT_JOBS عند اكتمال المهمة (تستمر حتى لو انقطع العميل)؛
   GET /api/assistant/chat/result/{job_id} للاسترداد؛ الواجهة (AssistantProvider)
   تستطلع تلقائياً كل 3s عند انقطاع البث ("الرد طويل — جارٍ استكماله…").
5. **مهلة LLM لوضع المطور**: 150s (LLM_TIMEOUT_SECONDS_DEV) — العادي يبقى 60s.
6. **زر «نسخ Proposal»** في UnifiedAssistantDrawer — يظهر على أي رسالة تحوي Proposal.
7. **قواعد الترقية Short→Long→Knowledge** المعتمدة نصاً موثقة في ROADMAP.md (شرط المرحلة 2).
### التحقق E2E
- محلياً: heartbeats كل 10s حتى done بعد 87s ✅
- عبر ingress: بث ينقطع عند 60s → poll يعيد الرد الكامل (12,917 حرف Proposal بوضع المطور) ✅
- اللوب حر أثناء التوليد: health 15ms (كان 15,000-30,000ms) ✅

## 2 يوليو 2026 — تنفيذ PRD Decimal Accounting Validation v1.1 (كامل) ✅
قرارات المستخدم: VAT بنية جاهزة فقط (التفعيل الحي لاحقاً)؛ حساب جديد «فروق تقريب
ضريبية» code=179 (expense) — 166 مرفوض؛ الإعداد vat_rounding_account=179 في
MongoDB settings (عمود Supabase workshop_settings غير قابل للإضافة عبر PostgREST).
### المنفّذ — accounting_engine.py
- `_dec()`: تحويل حدّي صارم → Decimal مكمم للهللة ROUND_HALF_UP؛ يرفض abc/null/
  NaN/Infinity/bool برسالة «Invalid monetary value: X» (Rules 1/6/7 — لا صفر صامت).
- `_line_amount()`: جانب مفقود (None/'') = صفر بنيوي — موثق أنه ليس تحويلاً صامتاً.
- `post()`: Rule 2 (لا سالب)، Rule 3/4 (لا صفر إلا Memo is_memo=True)، Rule 5
  (توازن صارم == بلا سماحية — القديم كان 0.01)، سقف 9,999,999.99 (سياسة التخزين).
- حد التخزين: Decimal → float(quantized) عند التسلسل فقط؛ الحساب كله Decimal.
- **Hash Stability (PRD §9)**: `_norm_amount` بقي حرفياً للبصمة فقط + توثيق التحذير.
- `post_entry`: الـ fallback المباشر أصبح لأخطاء write_failed فقط —
  أخطاء التحقق تُرفض نهائياً (كان يُدرج القيود المرفوضة مباشرة — مخالفة أُغلقت!).
- `reverse()`: يمرر القيم الخام للمحرك + يحفظ original_date/reason/reversed_of؛
  بصمة جديدة دائماً؛ بنود Memo تُستثنى من العكس.
### الجديد — core/vat_policy.py
distribute_vat (توزيع بالتقريب لكل بند + فرق التسوية) + build_settlement_line
(بند واحد، سقف CENT×عدد البنود، حساب 179 حصراً من الإعدادات) + VatConfigError
(الغياب = خطأ تهيئة صريح، لا افتراضي).
### الاختبارات — tests/test_decimal_prd_v1_1.py: **58/58 ✅**
Decimal (precision/parsing/validation/strict-balance) + Hash Regression بـ4 بصمات
حقيقية مثبتة من دفتر الأستاذ + Workshop (فاتورة مختلطة/VAT+تسوية/خصم قبل الضريبة
1006.25/عكس/دفعات جزئية) + Security (تكرار/سالب/صفر/Memo/سقف/توافق قديم) +
Config (غياب الإعداد=خطأ صريح) + Stress (10k بند <5s، KPI تحقق <50ms، ثبات بصمة
500 تكرار، 8 threads تكرار متزامن=قيد واحد).
### الانحدار
اختبار السلامة 13/13 ✅ + فاتورة E2E عبر البوت (INV001266 750.50 آجل → أربع أعين →
قيد متوازن بدقة) ✅ ثم نُظفت بيانات الاختبار.

## 24 فبراير 2026 — هوت فيكس أمنية معزولة (3) + تنفيذ L14 Provenance ✅
### الهوت فيكس (كل واحد diff معزول + إثبات + اختبارات انحدار 7/7 ✅)
1. **RBAC على `POST /api/assistant/tool/{name}`** (`routes_assistant.py`): كان ينفّذ
   أي أداة لأي مستخدم مصادَق → الآن JWT + دور معتمد. إثبات ثلاثي: بلا توكن 401 /
   فرج1 403 / مدير 200.
2. **`whatsapp.send` write=True** (`core/tool_router.py`): تسجيل شرطي تحت عقد
   BOT_ALLOW_WRITES — مع العلم=0 الأداة غير مسجلة إطلاقاً (مقصود ومعتمد من المالك).
3. **الطباعة — هوية الورشة** (`unified_document_service.py`): (أ) fallback البروفايل
   كان يستدعي /api/profile داخلياً بلا توكن → 401 دائماً → استدعاء مباشر للدالة؛
   (ب) القيم الفارغة من الواجهة كانت تمسح البروفايل → فلترة قبل الدمج.
   إثبات قبل/بعد: نفس الحمولة — قبل: بلا اسم/سجل/هاتف؛ بعد: كلها تظهر.
- اختبارات: `backend/tests/test_security_hotfixes_iter250.py` (7 حالات).
### L14 Provenance (تشخيص خالص — صفر إصلاح داخل المستويات)
- **النتيجة: رسوب 4/6 نظيف + 1 جزئي (S2) + 1 فشل (S1)** — التقرير الكامل مع
  trace_id لكل دورة (17 دورة): `/app/docs/diagnostics/L14_PROVENANCE_REPORT.md`.
- **حكم 8,905/9,850 (A6)**: أعيد إنتاج الآلية حياً — «اعرضي الذمم» لا تصل
  `finance.ar_summary` أبداً (نمط سطر 45 + fallback اسمي 137-146 + نزع أفعال يشوّه
  الاستعلام «ي الذمم») → الشات يعرض رقم تنبيه firewall (1,731) بينما الأداة الرسمية
  تقول 11,150 و nl.search يعطي 10,300. ثلاثة مصادر حقيقة = بند A6 (ذمم ×3).
- **اكتشافات جديدة L14-D1..D4** سُجّلت في LEGACY_AUDIT.md بلا إصلاح (حاكمية).
- **G3 Silent Fallback** موثّق بالدليل (kernel أسطر 792-799) في LEGACY_AUDIT.md — مؤجل.
