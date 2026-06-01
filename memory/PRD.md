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

### Session 7 (Feb 12 — current) — Bot Phase 1 + DDD Suppliers
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
