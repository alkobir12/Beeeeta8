# Workshop ERP — Product Requirements (PRD)

## Original Problem Statement
نظام إدارة ورشة سيارات متكامل (ERP) يدعم اللغة العربية، يضم وحدات محاسبية صارمة، نظام جرد ذكي، تتبع ذمم، ومدقق مالي بالذكاء الاصطناعي.

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

### Session 9 (Feb 12 — current) — Ollama Local LLM + Model Selector
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
- **P2**: OCR for invoice auditing
- **P2**: Mini-ledger for advance payments
- **P2**: Per-case hook dependency review
- **P3**: Split oversized React components
- **P3**: CRA → Vite migration (would resolve 89 high vulnerabilities)
- **P3**: Add type hints to 10 utility scripts

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
