# Workshop ERP — Product Requirements (PRD)

## Original Problem Statement
نظام إدارة ورشة سيارات متكامل (ERP) يدعم اللغة العربية، يضم وحدات محاسبية صارمة (ميزان مراجعة، دفتر يومية، شجرة حسابات)، نظام جرد ذكي، تتبع ذمم، ومدقق مالي بالذكاء الاصطناعي.

## Core Requirements
- Strict double-entry accounting
- Smart POS Journal Entries
- Smart Inventory with auto COGS
- Idempotency on financial operations
- AI Auditor with auto-escalation
- RBAC (name-only login, no passwords by design)

## User Personas
- **مدير** — admin (full access)
- **فرج1** — limited user

## Tech Stack
- React 18.3.1 + FastAPI + Supabase/MongoDB (DB_PROVIDER env switch)
- ThemeContext (Light/Dark/DashPro)
- Emergent Universal LLM Key

## Recent Work (Feb 2026)

### Session 1 — Theme Fix
- ✅ Sidebar dark gradient leaked into Light theme (background shorthand → background-image override)

### Session 2 — Security Fixes (Beeeeta7 Fix Prompt)
- ✅ FIX-B002: `supabase_service.supabase` → `.client` (6 places — real bug for Supabase mode)
- ✅ FIX-B006/B026/B027: Path Traversal + 10MB max + MIME whitelist on uploads
- ✅ FIX-B011: Rate-limiter memory leak protection
- ✅ FIX-M001: Removed duplicate `tax` in InvoiceBase
- ✅ FIX-M005: Mutable default `linkedAccounts` → `Field(default_factory=list)`
- ✅ FIX-SEC003: X-Content-Type-Options + X-XSS-Protection + Referrer-Policy
- ✅ Removed `pickle.load()` (RCE risk) from google_service.py
- ✅ Removed dynamic `__import__("datetime")`
- ✅ Empty catch blocks → proper logging (4 places)

### Session 3 — Code Review Round 2
- ✅ Fixed 2 Python F821 (undefined variable): dead code in `routes_advanced.py` + missing datetime import in `workshop_mcp_server.py`
- ✅ **Critical**: Fixed `@/components/ui/button` alias imports breaking Operations/Form/Calendar/Dialog in 7 shadcn files
- ✅ Array index → stable keys in 13 hotspots (VehicleDetails, Operations, SystemAudit, KnowledgeBase, QuotationGenerator)

### Explicitly Rejected (would break the app)
- ❌ Port 8000 (Emergent requires 8001)
- ❌ Hardcoded CORS to alkobir.com
- ❌ Mandatory JWT+bcrypt auth (user wants name-only login preserved)
- ❌ React 19→18 downgrade (already on 18.3.1)
- ❌ Removing xlsx/html2canvas (used by invoice printing)
- ❌ localStorage migration (all flagged usages are non-sensitive: UI cache/audit/drafts)
- ❌ Blanket hook dependency additions (high risk of infinite loops)

## Backlog
- **P1**: Refactor `server.py` → split into routers (Vehicles, Customers, Suppliers)
- **P1**: Refactor `routes_extended.py` → split (Visits, Operations, Vehicles)
- **P2**: OCR for automatic invoice auditing
- **P2**: Mini-ledger for advance payments per vehicle/customer
- **P2**: Per-case hook dependency review in VehicleDetails/UnifiedBotWidget/PartsInventory
- **P3**: Split oversized components (UnifiedBotWidget 1419 lines, OperationCard 835 lines, ChatWidget 757 lines)
- **P3**: Add type hints to 10 utility scripts (audit_examples.py, etc.)

## Key Files
- `/app/frontend/src/contexts/ThemeContext.jsx`
- `/app/frontend/src/index.css`
- `/app/frontend/src/components/Sidebar.jsx`
- `/app/frontend/src/components/ui/*.jsx` (alias-free imports)
- `/app/frontend/src/pages/Settings.jsx`
- `/app/frontend/src/pages/Operations.jsx`
- `/app/frontend/src/pages/VehicleDetails.jsx`
- `/app/frontend/src/pages/SystemAudit.jsx`
- `/app/frontend/src/pages/KnowledgeBase.jsx`
- `/app/frontend/src/pages/QuotationGenerator.jsx`
- `/app/backend/server.py` (security middleware, upload protection)
- `/app/backend/models.py`
- `/app/backend/supabase_service.py`
- `/app/backend/google_service.py`
- `/app/backend/routes_advanced.py`
- `/app/backend/workshop_mcp_server.py`
