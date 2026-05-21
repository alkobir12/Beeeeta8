# Workshop ERP — Product Requirements (PRD)

## Original Problem Statement
نظام إدارة ورشة سيارات متكامل (ERP) يدعم اللغة العربية، يضم وحدات محاسبية صارمة (ميزان مراجعة، دفتر يومية، شجرة حسابات)، نظام جرد ذكي، تتبع ذمم، ومدقق مالي بالذكاء الاصطناعي.

## Core Requirements
- Strict double-entry accounting (Trial Balance, Journal, Chart of Accounts)
- Double-Entry Firewall (real-time integrity guards)
- Smart POS Journal Entries
- Smart Inventory with auto COGS generation
- Idempotency on all financial operations
- AI Auditor with auto-escalation
- Unified Bot
- RBAC (name-only login: `مدير` admin, `فرج1` limited user — no passwords by design)

## User Personas
- **مدير** (Admin) — full access
- **فرج1** — limited user (used for RBAC verification)

## Tech Stack
- React 18.3.1 SPA + FastAPI backend
- Supabase + MongoDB (DB_PROVIDER env switch)
- ThemeContext (Light/Dark/DashPro) with CSS variables
- OpenAI/Anthropic via Emergent Universal LLM Key

## Recent Work (Feb 2026)

### Theme Fix (this session)
- ✅ Fixed sidebar dark gradient leaking into Light theme — overrode `background-image` and `background` shorthand in `body.light-mode .sidebar-modern` and `body[data-theme="dashPro"] .sidebar-modern`

### Security Fixes (this session — applied from Beeeeta7 Fix Prompt)
- ✅ FIX-B002: `supabase_service.supabase` → `.client` (6 places, real bug)
- ✅ FIX-B006: Path Traversal protection on vehicle file uploads
- ✅ FIX-B026: Max upload size (10MB)
- ✅ FIX-B027: MIME type whitelist on uploads
- ✅ FIX-B011: Rate-limiter memory leak protection (`_RATE_STATE_MAX=10000`)
- ✅ FIX-M001: Removed duplicate `tax` field in `InvoiceBase`
- ✅ FIX-M005: Mutable default `linkedAccounts` → `Field(default_factory=list)`
- ✅ FIX-SEC003: Additional security headers (X-Content-Type-Options, X-XSS-Protection, Referrer-Policy)
- ✅ Removed `pickle.load()` from `google_service.py` (RCE risk eliminated)
- ✅ Removed `__import__("datetime")` dynamic import in `routes_alkabeer_bot.py`
- ✅ Empty catch blocks → proper `console.warn/error` (VehicleDetails.jsx ×3, Users.jsx)

### Explicitly Rejected Fixes (would break the app)
- ❌ Port 8000 (Emergent platform requires 8001)
- ❌ Hardcoded CORS to alkobir.com (this app uses different domain via env)
- ❌ Mandatory JWT+bcrypt auth (user explicitly requested keeping name-only login)
- ❌ React 19→18 downgrade (already on 18.3.1)
- ❌ Package removals (xlsx/html2canvas/react-to-print — used by invoice printing)

## Backlog
- **P1**: Refactor `server.py` → split into routers (Vehicles, Customers, Suppliers)
- **P1**: Refactor `routes_extended.py` → split (Visits, Operations, Vehicles)
- **P2**: OCR for automatic invoice auditing
- **P2**: Mini-ledger for advance payments per vehicle/customer
- **P2**: Hook dependency fixes in VehicleDetails/UnifiedBotWidget/PartsInventory
- **P2**: Replace array index keys with stable IDs in critical lists
- **P3**: Split oversized components (UnifiedBotWidget 1419 lines, OperationCard 835 lines)

## Key Files
- `/app/frontend/src/contexts/ThemeContext.jsx`
- `/app/frontend/src/index.css` (theme overrides)
- `/app/frontend/src/components/Sidebar.jsx`
- `/app/frontend/src/pages/Settings.jsx`
- `/app/backend/server.py` (main, security middleware, upload routes)
- `/app/backend/models.py`
- `/app/backend/supabase_service.py`
- `/app/backend/routes_extended.py`
- `/app/backend/routes_finance.py`
- `/app/backend/google_service.py` (pickle removed)
