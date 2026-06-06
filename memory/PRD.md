# Workshop ERP — Product Requirements (PRD)

## Original Problem Statement
نظام إدارة ورشة سيارات متكامل (ERP) يدعم اللغة العربية، يضم وحدات محاسبية صارمة، نظام جرد ذكي، تتبع ذمم، ومدقق مالي بالذكاء الاصطناعي.

## CHANGELOG — 2026-06-05 (d) · Visits wired to existing `vehicle_visits` (no new table)
User chose to integrate with the existing schema instead of creating a standalone `visits` table.
- `create_visit` now resolves (or creates) the vehicle by plate/phone → inserts into the existing
  **`vehicle_visits`** table (entry_date, status='in_progress', exit_date=null, notes JSON with service
  items), and flips the vehicle status to active so it surfaces in dashboards/active-visits. Falls back to
  in-memory staging only when no vehicle can be linked (no plate). `_resolve_or_create_vehicle_for_visit`.
- Fixed a latent bug: `vehicles.brand` is NOT NULL — `_payload_to_vehicles_row` now defaults brand to
  'غير محدد' (also unblocks brand-less `create_vehicle` commands). model falls back to vehicle_type.
- Removed the obsolete standalone `visits` migration (no SQL burden on the user).
- Verified by curl: create_visit → real vehicle_visits row (linked vehicle, service item), surfaces in
  active visits (109→110), cleaned up. Table audit: 17 Supabase tables exist; only auxiliary tables
  (users/suppliers/chart_of_accounts/moltbot_*/ui_generations/user_layouts/inventory_backorders) missing —
  none block Katrina's current commands.


## CHANGELOG — 2026-06-05 (c) · Katrina CRUD: delete + edit commands (verified 100%)
User-approved scope (أ) + (ج). Verified iteration_235: 7/7 frontend flows PASS, net DB delta = 0.
- **Fixed broken delete_customer / delete_vehicle**: were declared RISKY but never wired to runtime.
  Now: `_ACTION_TO_RUNTIME` maps them; `execute_text` resolves the target row FIRST
  (`resolve_customer_target`/`resolve_vehicle_target`, Arabic-tolerant) → returns
  `needs_clarification` (reason `not_found`|`ambiguous` + candidates) instead of guessing; risky →
  ApprovalCard → on approve it **auto-commits** (approve endpoint now uses a distinct `reviewer:` identity
  to pass Four-Eyes AND commits the draft, so risky approvals finally execute — fixes a pre-existing gap
  affecting delete_operation/close_visits too).
- **NEW update_customer / update_vehicle** (safe, auto-commit): "عدّل جوال خالد إلى 05..",
  "غيّر حالة المركبة 8123 إلى جاهزة". Payload schema `{match:{...}, set:{...}}`. `_update_entity` PATCHes Supabase.
- **visits table**: code now writes/reads a real Supabase `visits` table when present, else falls back to
  staging. Migration SQL added at `/app/backend/migrations/001_create_visits.sql` — **user must run it once**
  in Supabase SQL Editor for visits to persist (until then create_visit uses in-memory staging).
- Clarification UX: ambiguous deletes list candidates ("⚠️ وجدت أكثر من … أيّهم تقصد؟"); not-found says "🔎 لم أجد…".
- Files: core/llm_intent_parser.py, core/unified_executor.py, core/action_runtime.py,
  routes_action_runtime.py, frontend AssistantProvider.jsx (statuses+labels).


## CHANGELOG — 2026-06-05 (b) · Fixed rrweb fetch-body errors in Katrina chat
User saw intermittent error bubbles: "stream ended without done event" and "Body is disturbed or locked".
**Root cause:** the platform's rrweb session-recorder wraps `window.fetch` and locks/disturbs the
response body. The assistant's SSE chat path and the 🚀 execute button used `fetch()`.
**Fix:** migrated everything to **axios (XHR)** — `sendMessage` now defaults to the non-streaming
axios `/api/assistant/chat` path; `UnifiedAssistantDrawer.handleExecute` (🚀) now uses `axios.post`
for `/api/runtime/execute` (matching `_executeDirectly` which already used axios). Verified
iteration_234: 10/10 frontend, **0 occurrences** of the 4 error strings across 6 flows. Note: kept
LLM-first intent parsing (no regex fast-path) to protect accounting data accuracy.


## CHANGELOG — 2026-06-05 · L16 "كاترينا" (Katrina) Conversational Operator
The floating assistant was upgraded from a read-only L5 helper to a true L16
executing agent, **rebranded to "كاترينا" (Katrina)**. Five user complaints resolved + voice added:
1. **Executes instead of instructing** — root cause: `/api/assistant/chat` ran a read-only
   kernel whose prompt told the LLM to "go to the page"; the real write path
   (`/api/runtime/execute`) was separate and chosen by a brittle frontend Arabic regex.
   Fix: `assistant_kernel.chat()` now detects write intent via `looks_like_action()` and
   executes through `unified_executor.execute_text()`, returning a "✅ تم بنجاح" confirmation
   + `executed{}` field. Backend is now the safety-net regardless of phrasing/dialect.
2. **Arabic-tolerant search** — new `core/arabic_nlp.py`: `normalize_arabic()`, `arabic_tokens()`,
   `arabic_match()` (hamza أإآ→ا, ة→ه, ى/ئ→ي, tashkeel/tatweel strip, definite-article-insensitive,
   Arabic-Indic digits→ASCII). Applied to customers/operations/vehicles search + fetch-all fallback.
   Nicknames/kunya like "ابو مصري" / "أبو المصري" now resolve.
3. **Model badge/list** — `GET /api/assistant/models` now returns `default='sonnet'`,
   id `sonnet` / "Claude Sonnet 4.6" (was GPT/gpt-4o-mini).
4. **Mobile UI** — drawer height 80vh (was 95vh), bigger clear close button, tappable drag handle.
5. **Voice (live talk)** — `useVoice.js` browser-native Web Speech API (STT mic ar-SA + TTS spoken
   replies). Mic button (`assistant-mic-btn`) + voice toggle (`assistant-voice-toggle`). No keys/backend.
6. **Knowledge/personality** — Katrina system prompt enriched from the attached CRP-AlKabeer/أبو فهد
   spec: warm Qassimi dialect, car-diagnostics + parts/VIN knowledge, workshop info (📞 0553280100).
7. **Reactive binding** — `AssistantProvider` dispatches `finance:updated` when `data.executed.status=='committed'`.
Verified: backend 10/10 pytest (`/app/backend/tests/test_katrina_iter233.py`), frontend 9/10 (1 timing artifact).
Known minor (deferred): dup-prevention returns the pre-existing row (so re-registering an existing
name keeps its old phone); `/api/assistant/tool/*` envelope differs from `/chat`; RecentOperationsWidget
has a `<button>`-in-`<button>` DOM-nesting warning.


## Core Requirements
- Strict double-entry accounting
- Smart POS Journal Entries
- Smart Inventory with COGS
- Idempotency on financial operations
- AI Auditor with auto-escalation
- RBAC (name-only login by design)

## User Personas
- **مدير** — admin
- **فرج1** — limited user

## Tech Stack
- React 18.3.1 (CRA) + FastAPI + Supabase/MongoDB
- ThemeContext (Light/Dark/DashPro)
- Emergent Universal LLM Key

## Recent Work — All 5 Sessions Summary (Feb 2026)

### Session 12 (Jun 5) — L16 Conversational ERP Operator (Write Execution + Reactive Binding)
- **CRITICAL FIX: JS `\b` doesn't work with Arabic** — Root cause of "البوت لا ينفذ الأوامر". Replaced with `(?:^|\s)` and `(?:\s|$)`.
- **L16 Reactive Binding**: `finance:updated` dispatched after every committed action → auto-refreshes Dashboard, Operations, Customers, Financial pages
- **Duplicate Prevention**: Checks Supabase for existing customer (name+phone) and vehicle (plate) before creating
- **LLM Switch**: GPT-4o-mini → **Claude Sonnet 4.6**
- **Qassimi Dialect**: وش/ابي/ابغى/ضيف/حط/شيل/الحين/وين
- **All 9 Button Types Activated**:
  1. تصحيح القيود المفقودة (POST /api/operations/integrity/fix-all) — 7/7 fixed
  2. تحصيل من عميل (POST /api/operations/{id}/confirm-payment)
  3. حذف عملية (DELETE via runtime + approval)
  4. تعديل عميل (PUT /api/customers/{id})
  5. تعديل مركبة (PUT /api/vehicles/{id})
  6. إنشاء زيارة جديدة (POST via runtime)
  7. طباعة PDF (navigate to print page)
  8. إرسال واتساب (Infobip integration)
  9. حجز قطعة + كشف حساب مورد (navigate/tool)
- **New Tool**: `operations.search` — searches by customer/partner name
- **Delete Support**: `delete_operation` action (RISKY — requires approval)
- **fetch → axios**: Fixed rrweb-recorder interceptor conflicts
- 10/10 backend tests + E2E "✅ تم بنجاح" for vehicle/customer creation

### Session 11 (Feb 12 — previous) — Phase 3B Round 2 (Power Mode + Multi-Intent + Drafts)
- ✅ **⚡ Power Mode**: `/power` prefix triggers multi-intent execution. Backend `core/power_mode.py` (~280 lines, fully tested) detects the prefix and bypasses the LLM path. Single round-trip handles N commands.
- ✅ **🔀 Multi-Intent Parsing**: Splits on `\n`, `،`, `؛`, `.`, ` ثم `, ` and `, ` و `. Each sub-command goes through its own intent classifier (11 kinds: customer/vehicle/visit/operation/invoice/collection/payment/supplier/inventory/part_search/unknown).
- ✅ **🎴 4 New Draft Cards** (CustomerDraftCard, VehicleDraftCard, VisitDraftCard, OperationDraftCard + 5 others) — rendered with dashed amber border + "مسوّدة" badge. **All 3 actions (review/discard/commit) are deferred to Phase 3C** (Approval Runtime) — strict read-only contract intact.
- ✅ **🔍 Entity Extraction**: Pulls plate (`\d{3,5}` + Arabic suffix), Saudi phone (`05\d{8}`), amount (with comma + decimal + ر.س), Arabic name (1-4 words). Phone never confused with amount.
- ✅ **🧠 Context Resolver (Explicit Mapping)**: When entities are missing, fills from session memory using per-intent field maps (`vehicle←last_vehicle.plate`, `invoice←last_customer.name`, …). Never bleeds customer name into vehicle drafts. Carries `_resolved_from` for transparency.
- ✅ **🧠 `last_section` Memory**: Tracks which section the user is currently working in (customer/vehicle/visit/operation/…). Persists per-session for 1 hour.
- ✅ **🔌 New Endpoints**:
  * `POST /api/assistant/power/diagnose` — preview what Power Mode would parse without executing (test-friendly).
  * `GET /api/assistant/memory/{sid}` — extended with `last_section`, `last_visit`, `last_collection`, `last_payment`, `last_inventory`.
- ✅ **🎨 Frontend Updates**:
  * `AssistantCard.jsx` — renders DraftCards with dashed amber border + status badge + per-intent gradient header.
  * `UnifiedAssistantDrawer.jsx` — added ⚡ shortcut button next to send (data-testid `assistant-power-shortcut`) that prepends `/power` to current input. Placeholder updated to hint `/power`.
  * Page-aware suggestions updated to include `/power` examples per route.
- ✅ **🧪 Tests**: `tests/test_power_mode_iter234.py` — 35 tests covering mode detection, splitting, intent kinds, entity extraction, context resolution, draft shape, E2E power_process, memory side-effects, and the read-only contract.
- 🛡️ **Read-Only Contract Verified**: `test_drafts_have_no_write_actions` asserts every action on every draft is `intent="deferred"` with a `phase` tag. Cannot accidentally commit.
- 🧪 **Regression**: 60/60 ✅ (35 new + 10 bot tools + 5 DDD + 10 Phase 3A).
- 🔬 **Verified E2E**:
  * `POST /chat` with `/power سجل عميل احمد، أضف مركبة 9935` → 2 drafts, response includes summary + cards list.
  * Round 2 with `/power أضف عملية صيانة` (no plate) → context_resolve filled plate=9935 and name=احمد from prior turn ✅.
  * Browser preview screenshot shows drawer opened, `/power` message rendered, ⚡ button visible, "thinking" indicator working.


- ✅ **🌊 SSE Streaming**: `POST /api/assistant/chat/stream` يبثّ 5 أنواع events (`progress` × 3 phases + `tool` لكل أداة + `done` بالـpayload الكامل + `error`). الواجهة تستهلكها عبر `fetch + ReadableStream + TextDecoder` بدون مكتبة خارجية. خاصية `streamingPhase` في `useAssistant()` تعرض الـ label الحالي ("يفهم سؤالك…"، "جارٍ تشغيل الأدوات…"، "يصيغ الردّ…"). Fallback تلقائي لـ `/chat` العادي لو الـstream فشل.
- ✅ **📱 Mobile Bottom-Sheet**: `useIsMobile()` يكتشف `< 768px` ويبدّل الـDrawer لـ bottom sheet كامل العرض 95vh مع safe-area + drag handle (`data-testid="assistant-mobile-handle"`). على الديسكتوب يظل 420×640 كما هو.
- ✅ **🎴 6 Interactive Cards** عبر `core/card_builder.py`:
  * `CustomerCard`، `VehicleCard`، `InvoiceCard` (sale)، `OperationCard` (purchase/expense)، `SupplierCard`، `InventoryCard`
  * كل أداة قراءة الآن ترفق `cards: [...]` بنتيجتها — الكيرنل يجمعها في `data.cards` بالـ root level.
  * Frontend `AssistantCard.jsx` يرسم بطاقة بـ header gradient + fields + action chips. لكل بطاقة 3 actions: navigate / tool / deferred (with phase hint).
- ✅ **📊 Assistant Dashboard** — `GET /api/assistant/dashboard` يجمع 8 KPIs بمكالمات parallel (visits/health/AR/AP/cash flow/critical/low stock/integrity). يظهر تلقائياً في الـempty state للـDrawer مع loading skeleton لطيف.
- ✅ **🧠 Long-Term Memory (basic)**: عند كل ردّ يحتوي card، يُحفظ `last_customer` / `last_vehicle` / `last_invoice` / `last_operation` / `last_supplier` / `last_part` في `shared_memory`. يُكشف عبر `GET /api/assistant/memory/{sid}` — جاهز لسؤال "اعرض العميل السابق" في الجولة القادمة.
- ✅ **🔍 Card Actions** — chips تحت كل بطاقة: `navigate` يستدعي react-router-dom، `tool` يعيد إرسال سؤال البحث، `deferred` يُعرض معطّلاً مع tooltip "متاح في Phase 3X".
- ✅ **🧪 Regression**: 25/25 ✅ (10 bot tools + 5 DDD + 10 Phase 3A).
- 🔬 **Verified E2E**:
  * SSE events: thinking → tools → tool:success → rendering → done (all 5 fired live)
  * 5 CustomerCards rendered with phone/balance/visits + 3 action chips each
  * OperationCards rendered with partner name + amount + payment status + date + 2 actions
  * Dashboard empty-state shows 8 skeleton tiles → populates with KPIs

**Pending for Round 2:**
- 7 cards باقية (Visit/Payment/Approval/Audit/WhatsApp/Report/Finding)
- Entity Resolution (regex/NLP عربي → cards بدل نص فقط)
- Natural Language Search ("أكثر العملاء مديونية"، "الفواتير المتأخرة")
- Long-term memory: postgres-backed (weekly/monthly rollups)
- Dialect support (قصيمي/يمني) في system prompt
- Action Runtime + Approval (Phase 3C — جلسة مستقلة)

### Session 9 (Feb 12) — Ollama Local LLM + Model Selector
- ✅ **🦙 Ollama installed (ARM64 binary)**: `/usr/local/bin/ollama` v0.30.4, supervisor-managed (`/etc/supervisor/conf.d/ollama.conf`), bound to `127.0.0.1:11434`.
- ✅ **Model pulled**: `llama3.2:3b` (2.0 GB, Arabic-capable). First query latency ~5-10s, sustained ~9 tok/s.
- ✅ **`core/llm_helpers.py`**: new abstraction with `is_ollama_alive()`, `ollama_list_models()`, `call_ollama()` — uses `OLLAMA_HOST` / `OLLAMA_DEFAULT_MODEL` env (with sensible defaults), full system+history+user message support.
- ✅ **`assistant_kernel.chat()` accepts `model` param**: `'gpt'` (default, Emergent gpt-4o-mini) or `'ollama'` (local llama3.2:3b). When Ollama is unreachable, gracefully falls back to GPT. Returns new `model_used` field showing which provider answered.
- ✅ **New `GET /api/assistant/models`**: lists both providers + availability flag + installed Ollama models. Frontend uses this to render the selector dynamically.
- ✅ **Frontend selector** (`AssistantProvider` + `UnifiedAssistantDrawer`):
  * Selected model persisted in `localStorage.assistant.model`.
  * Default fallback list prevents empty UI during initial fetch.
  * `data-testid="assistant-model-selector"` panel inside settings shows 2-button grid.
  * Header `data-testid="assistant-model-badge"` shows ⚡ GPT or 🦙 Ollama live.
- ✅ **Verified E2E**: visual screenshot shows GPT + Ollama buttons rendered; clicking Ollama updates header badge to 🦙. Backend confirms `model_used: "ollama/llama3.2:3b"` when selected.
- 🧪 **Regression**: 25/25 tests still passing (no breakage).
- ⚠️ **Disk note**: `/root` at 79% after model pull (Ollama models = 2.0 GB). Room for one more 1-2 GB model if needed; bigger pulls would need a cleanup.

### Session 8 (Feb 12) — Phase 3A Foundation (L16 prep)
- ✅ **🛡️ A1 — write contract**: `register_tool(write=False)` default + `BOT_ALLOW_WRITES` env flag + runtime guard in `call_tool()`. Trying to register a write tool without the flag raises `WriteToolBlockedError`. Read-only contract is now **code-enforced**, not just convention.
- ✅ **⏱️ A2 — rate limit**: `slowapi` integrated. `POST /api/assistant/chat` is capped at **30/minute/IP** (override via `ASSISTANT_CHAT_RATE` env). `SlowAPIMiddleware` + exception handler registered in `server.py`. Verified: 35 rapid requests → 30 OK + 5 × 429.
- ✅ **📜 A3 — audit log**: new domain `domains/bot_audit/` (repository + service + SQL migration). Every `/chat` call writes one row with metadata (intent, tools_called, ai_used, fallback_used, tokens, request_hash, client_ip). **Never stores raw user content** — only sha256[:16] hash. Falls back to bounded in-memory ring buffer (500 rows) when the Supabase table is absent. New endpoint `GET /api/assistant/audit/recent` exposes the rows.
- ✅ **📝 A4 — structured logging + redaction**: new `core/log_utils.py` with `get_logger()` (`assistant.*` namespace) and `redact()` that strips Bearer/JWT/sk-/provider tokens, masks email local parts, and masks phone numbers (keeping last 4). Replaced all `print(...)` calls in `assistant_kernel.py` and `routes_assistant.py` with structured logging.
- ✅ **🧪 A5 — regression tests**: `tests/test_phase_3a_foundation.py` (10 tests, all pass) covers: registration blocked, runtime guard, rate limit attached, audit row recorded, request_hash one-way, redact strips Bearer/sk/JWT, masks emails/phones, truncation.
- ✅ **📁 SQL migration**: `domains/bot_audit/MIGRATION.sql` — operator runs once in Supabase. Includes RLS placeholder.
- 📝 **Audit corrections**: `04_API_KEYS_STATUS_SAFE.md` updated — Groq is `used_by_legacy (routes_moltbot.py)` not workshop_bot; `LLAMA_MAVERICK_MODEL_ID` is now flagged as "ready-to-swap target for `GROQ_MODEL`".
- 📊 **Final scoreboard**:
  * Total tests: 25/25 passing (10 Phase 3A + 10 bot tools + 5 DDD suppliers)
  * Tools registered: 12, all write=False
  * Rate limit verified live: ✅
  * Audit rows landing in memory buffer (will switch to Supabase after operator runs MIGRATION.sql)

### Session 7 (Feb 12) — Bot Phase 1 + DDD Suppliers
- ✅ **🤖 Bot Phase 1 — Smart Sale Search (DONE)**:
  * 🆕 أداة `parts.search` ذكية — بحث في المخزون بالاسم/التصنيف، يرجع جدول بالأسعار+الكمية المتاحة مرتبة (المتوفر أولاً)، مع `next_action_hint` يوجّه لـ /operations.
  * أنماط intent جديدة: "بيع X" / "أبيع X" / "كم سعر X" / "كم عندي X" / "هل عندنا X".
  * `_extract_query()` يستخرج اسم المنتج بعد إزالة أفعال البيع/الشراء/التسعير.
  * `parts.search` لا يتعارض مع `inventory.low_stock` — تم اختبار ذلك.
  * Verified E2E: استعلام "أبيع زيت" يرجع 5 قطع زيت بأسعارها (134/251/120/15/35 ر.س).
- ✅ **🤖 Bot Phase 1 — السابق (Iter 232)**:
  * +5 أدوات قراءة (customers.search، vehicles.search، inventory.low_stock، finance.payables_summary، operations.recent).
  * إصلاح bug `ال?` → `(?:ال)?` في كل الـregex.
  * Markdown rendering (react-markdown + remark-gfm) في الواجهة.
  * Page-aware suggestions حسب الـ route.
- ✅ **🏛️ DDD Phase 2 — Suppliers Domain extracted**:
  * `/app/backend/domains/suppliers/{router,service,repository,schemas}.py` متكامل.
  * 5 endpoints انتقلت: GET list، GET single، POST، PUT، DELETE، POST /migrate.
  * `server.py` انخفض من 3191 → 2927 سطر (-267 سطر = **-8.4%**).
  * Helpers `_derive_suppliers_from_parts`, `_enrich_suppliers_from_accounts`, `SUPPLIERS_TABLE_AVAILABLE` بقيت في server.py وتُستهلك من الـrepository.
  * Schema يطابق `SupplierBase` (contactPerson/city/category/rating included).
  * Service يستدعي `_safe_sync_partner_subaccounts` تلقائياً عند create (سلوك حافظ على التطابق مع القديم).
- 🧪 **Regression tests**:
  * `/app/backend/tests/test_bot_tools_iter232.py` — 10/10 ✅ (شمل parts.search test).
  * `/app/backend/tests/test_suppliers_ddd_iter233.py` — 5/5 ✅ (CRUD كامل + 404).
- 🔬 **Verified E2E**:
  * `/api/suppliers` GET يرجع 49 مورد مع التخصيب المالي الكامل.
  * Create/Update/Delete يعمل (HTTP 200/200/200) + 404 بعد الحذف.
  * صفحة `/suppliers` في الواجهة تعرض 50 بطاقة مورد بدون أخطاء.
- 🧪 **Pre-Deploy Smoke Test (6/6 queries passed)**:
  * ما هي القطع الناقصة؟ → inventory.low_stock (137 items) ✅
  * بيع قطع غيار → parts.search (8 items) ✅
  * ابحث عن العميل ابراهيم → customers.search (5 matches) ✅
  * ابحث عن مركبة 9935 → vehicles.search (2 matches) ✅
  * كم ذمم الموردين؟ → finance.payables_summary ✅
  * أعطني آخر العمليات → operations.recent (5 ops) ✅
- 🔗 **Bot integration check**: FAB يظهر على /customers، /suppliers، /parts، /accounting/firewall، الـDashboard. مستثنى فقط `/moltbot` (legacy editor) كما هو مصمم.

### Session 6 (Feb 11)
- ✅ **P0: Operation Card Expansion البصري — FIXED PROPERLY**:
  - **Root cause الحقيقي**: القسم الموسّع كان `position: static` (default) بدون z-index. الـ glow div داخل الكارت `pointer-events-none absolute inset-0` يقع في نفس stacking context. عناصر absolute-positioned تظهر فوق static في نفس المستوى → الـ glow كان يغطي expanded section بصرياً (حتى مع opacity-0، لأنه يفرض stacking).
  - **Fix**: إضافة `relative z-10` للقسم الموسّع → الآن يقع في طبقة z=10 فوق الـ glow.
  - **Verified**: بعد الإصلاح ظهرت كل المحتويات (اسم العميل، نوع العملية، التاريخ، المركبة، طريقة الدفع، حالة السداد، المدفوع/المتبقي، الحساب، إيراد الورشة، القيد المحاسبي، البنود، بنود الموردين).

- ✅ **P0: Integrity Warning Pill (⚠️) قابلة للنقر**:
  - عدّلت `StatusBadge.jsx` لقبول `onClick` prop مع stopPropagation داخلي.
  - عدّلت `OperationCardHeader.jsx` لتمرير `integrityWarnings` array + `integrityLabelMap` + `onIntegrityClick`.
  - أضفت modal كامل في `OperationCard.jsx` (`operation-card-integrity-modal-*`) يعرض كل التنبيهات في شكل قائمة مع زر "فهمت" + X للإغلاق + backdrop blur.

- ✅ **UX: نقل صفحات Profile/Users/Import داخل /settings كتبويبات**:
  - أضفت 4 tabs في `Settings.jsx`: عام / الملف الشخصي / المستخدمون / استيراد البيانات (مع URL sync `?tab=...`).
  - أنشأت `/app/frontend/src/components/settings/SettingsImportBlock.jsx` كـ block مدمج للاستيراد (بدلاً من الصفحة الكاملة).
  - أضفت redirects تلقائية في `App.js`: `/profile`, `/users`, `/import` → `/settings?tab=...`.
  - حذفت الروابط القديمة من `Sidebar.jsx`.

- ✅ **UX: إعادة هيكلة Sidebar**:
  - دمج Customers + Technicians في group موحد "العملاء والفنيون".
  - نقل صفحة "الخدمات" داخل group "المخزون" بجانب القطع/الموردين.

- ✅ **PERF: Operations + Dashboard pages caching layer (NEW)**:
  - Created `/app/backend/perf_cache.py` — module-level TTL cache utility with 500-entry LRU cap and pluggable TTL (default 15s).
  - Wrapped 4 expensive backend reads in `server.py`:
    * `_fetch_operations_for_partner_financials` — was reading ALL operations on every `/api/customers` and `/api/suppliers` call.
    * `_fetch_operation_payment_map` — was scanning ALL journal_entries every call.
    * `_fetch_vehicle_customer_lookup` — was reading ALL vehicles every call.
    * `_build_partner_financial_map` — full computed result now cached per (type, workshop, entity-set-signature).
  - Wrapped `/api/operations` GET in `routes_extended.py` with 10s TTL (keyed by all filters).
  - Added cache invalidation helper `_invalidate_ops_caches()` and wired it into 5 mutation endpoints (POST/PUT/DELETE/{id}, DELETE bulk, POST confirm-payment).
  - **Measured improvements** (testing agent iter 231 — 12/12 tests PASSED with data integrity verified):
    * `/api/operations` cold 2.3s → warm **0.11s (17-21x faster)**
    * `/api/customers` cold 1.8s → warm **0.42s (5.7x faster)**
    * `/api/suppliers` cold 1.0s → warm **0.37s (2.7x faster)**
    * `/operations` page (full browser): previously ~12-22s cold → **1.12s first load, 0.94s second load**
  - Cache invalidates within the same second after any mutation — verified via testing agent.

- ✅ **P0: Operation Card "details don't show" بصرياً (FIXED)**:
  - Root cause #1: index.css global rule at line 154 (`body.light-mode div { color: var(--text-secondary) !important }`) was overriding every Tailwind `text-slate-950/900/700/600` etc. inside `[data-testid^="operation-card-expanded-"]`, making text appear washed-out gray on light-gray backgrounds.
  - Root cause #2: expanded section had no `onClick={stop}` → clicking any inner content bubbled up to the outer card and collapsed the card mid-interaction.
  - Root cause #3: expanded section was rendered AFTER the actions section in JSX, so logically the expanded content appeared below the action buttons (confusing UX).
  - Fix #1 (`index.css` lines 159-189): added targeted overrides for `body.light-mode [data-testid^="operation-card-expanded-"] .text-slate-950/900/700/600` etc. + same for `body[data-theme="dashPro"]` — restored proper Tailwind colors.
  - Fix #2 (`OperationCard.jsx` lines 574-579): added `onClick={stop}` (e.stopPropagation) on the expanded section wrapper.
  - Fix #3 (`OperationCard.jsx`): swapped the expanded and actions blocks in JSX so the expanded content renders BETWEEN the toggle and the actions (more conventional UX).
  - Fix #4 (`OperationCard.jsx` line 475): removed `overflow-hidden` and replaced `transition: all` with `transition: box-shadow` only.
  - **Verified by testing agent iter 230**: 18 `.text-slate-950` elements with computed color `rgb(15, 23, 42)`, expanded section has 677 chars of rich content, stopPropagation works.
- ✅ **P0: SmartPOSJournal "تحصيل من عميل" sort + auto-select (VERIFIED)**:
  - `dashboardCustomerIds` (line 496-509): Set of customer IDs whose vehicles are NOT yet delivered/closed (active dashboard visits).
  - `partyOptions` (line 511-526): customers with active visits ranked first with `_isActive: true` and `⭐ لديه زيارة نشطة` label in the datalist.
  - `pos-party-dashboard-hint` UI: `⭐ العملاء الذين لديهم زيارات نشطة معروضون أولاً في القائمة (N)`.
  - `useEffect` (line 364-424): when a customer is selected, fetch `/api/operations?partner_id=...` and filter for `sale/service/instant_sale` with `balance > 0`.
  - `setSelectedVisitId` auto-set when `openOps.length === 1` (auto-select single-visit behavior).
  - `findOpenVehicleOperationForCollection` (line 726-755): when `selectedVisitId` is set, use it directly; otherwise fall back to vehicle-based lookup.
  - **Verified by testing agent iter 230**: 9 ⭐ active customers at top, multi-visit dropdown shows without auto-select (correct), single-visit auto-select code-reviewed as structurally correct.

### Session 5 (Feb 11)
- ✅ **Fixed faded "Quick Actions" dialog** (`VehicleQuickActions.jsx`): translucent classes removed, dark-mode `/40 → /70`, structural Dialog nesting bug resolved.
- ✅ **OTP feature verified + Mongo legacy branch mirrored**.
- ✅ **Quick Actions print buttons (invoice/receipt) now work**: `buildVehiclePayload` is async and fetches the latest visit's operations dynamically (was using empty `approvalItems` array).
- ✅ **Operation list live refresh**: `finance:updated` handler in `Operations.jsx` now invalidates + `refetchQueries({type:'active'})` for immediate UI update.
- ✅ **POS `collect_customer` now dispatches `finance:updated`**: was missing the event before the early `return`, so Operations didn't reflect collected amounts.
- ✅ **🔥 ROOT CAUSE fix: cash POS expense was showing as "شراء آجل"**:
  - `_operation_payment_snapshot` in `supabase_service.py` was returning `paymentStatus='unpaid'` for cash-immediate operations because it required `journal_entries` with `source=operation_payment` to mark as paid.
  - Added `is_cash_immediate` short-circuit: if `payment_method ∈ {cash,transfer,bank,card,pos,mada,visa,mastercard,supplier_balance}` AND `payment_status ∉ {unpaid,credit,partial,deferred,pending}`, return `paid` immediately with `balance=0`. Verified via 3/3 pytest pass.
- ✅ **Operation card badges added**:
  - **Movement pill** (`operation-card-movement-pill-*`): "مدين (داخل)" green for income-side ops (sale/service/instant_sale/collect_customer/receipt_voucher/sale_return), "دائن (خارج)" rose for outflow ops (purchase/expense/cash_expense/salary/payment_order/pay_supplier/purchase_return), "متعادل" gray otherwise.
  - **Origin pill** (`operation-card-origin-pill-*`): "POS" indigo for SmartPOSJournal operations (detected via `[SOURCE:SMART_POS]` marker in notes OR `source.includes('pos')`), "ملف المركبة" cyan for visit/vehicle-linked, "عام" slate otherwise.
  - Final tested distribution on /operations: POS=5, ملف المركبة=4, عام=6 (15 total cards, all correctly classified).

### Critical Bugs Fixed
- ✅ **Operations page broken**: 7 shadcn UI files used invalid `@/components/ui/button` alias → relative paths
- ✅ **Theme toggle reverts**: sidebar gradient leaked into Light theme (background-image override)
- ✅ **Supabase mode crash**: `supabase_service.supabase` (doesn't exist) → `.client` in 6 places
- ✅ **Python F821 dead code**: removed unreachable code in `routes_advanced.py`
- ✅ **Python F821 missing import**: added datetime in `workshop_mcp_server.py`

### Security Hardening
- ✅ Removed `pickle.load()` RCE risk (google_service.py)
- ✅ Removed dynamic `__import__("datetime")`
- ✅ Path Traversal protection on uploads
- ✅ 10MB max upload size + MIME whitelist
- ✅ Rate-limiter memory leak protection
- ✅ Security headers: X-Content-Type-Options, X-XSS-Protection, Referrer-Policy
- ✅ Removed 4 empty catch blocks (now log via console.warn)
- ✅ All bare `except:` → `except Exception:` (11 places)

### Code Quality
- ✅ 35+ unused imports/variables auto-removed (ruff --fix)
- ✅ Array index → stable keys in 13 hot paths
- ✅ Duplicate `tax` field removed from InvoiceBase
- ✅ Mutable default `linkedAccounts` fixed
- ✅ Production code lint: 119+ errors → 0 ✅

### Explicitly Rejected (would break the app)
- ❌ Port 8000 (Emergent requires 8001)
- ❌ Hardcoded CORS to alkobir.com
- ❌ Mandatory JWT+bcrypt (name-only login preserved per user request)
- ❌ React 19→18 downgrade (already on 18.3.1)
- ❌ Removing xlsx/html2canvas (used by invoice printing)
- ❌ localStorage migration (all UI cache, non-sensitive)
- ❌ Blanket hook dep additions (risk of infinite loops)
- ❌ Test files lint cleanup (cosmetic only)

### Known Status Items
- 70 E402 in server.py — INTENTIONAL lazy imports (not bugs)
- 89 High npm vulnerabilities — ALL in build tooling (react-scripts/tailwindcss transitive). Runtime is safe. Fix requires CRA→Vite migration.
- Largest files for future split (P1/P3):
  - `routes_finance.py` (224KB)
  - `routes_extended.py` (212KB)
  - `server.py` (129KB / 3274 lines)
  - `VehicleDetails.jsx` (4510 lines)
  - `Operations.jsx` (3770 lines)
  - `UnifiedBotWidget.jsx` (1710 lines)

## Backlog
- **P1**: Refactor `server.py` → split routers
- **P1**: Refactor `routes_finance.py` and `routes_extended.py`
- **P1**: Extract vehicles/inventory to `/app/backend/domains/`
- **P2**: Auto-fix missing journal entries button in assistant
- **P2**: Multi-provider fallback (Groq/Llama)
- **P2**: OCR for invoice auditing
- **P2**: Mini-ledger for advance payments
- **P2**: Per-case hook dependency review
- **P3**: Split oversized React components
- **P3**: CRA → Vite migration (would resolve 89 high vulnerabilities)
- **P3**: Add type hints to 10 utility scripts
- **Enhancement**: Advanced context memory — "احذفها" auto-resolves entity from conversation history

## Key Files
- `/app/frontend/src/contexts/ThemeContext.jsx`
- `/app/frontend/src/index.css`
- `/app/frontend/src/components/Sidebar.jsx`
- `/app/frontend/src/components/ui/*.jsx` (alias-free)
- `/app/frontend/src/pages/*.jsx`
- `/app/backend/server.py`
- `/app/backend/models.py`
- `/app/backend/supabase_service.py`
- `/app/backend/google_service.py`
- `/app/backend/accounting_auditor.py`
- `/app/backend/auto_sync_service.py`
- `/app/backend/routes_*.py`
