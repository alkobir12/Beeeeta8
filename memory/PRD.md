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

## Recent Work — All 4 Sessions Summary (Feb 2026)

### Session 5 (Feb 11 — current)
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
