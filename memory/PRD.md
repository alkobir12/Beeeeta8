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
- RBAC

## User Personas
- **مدير** (Admin) — full access
- **فرج1** — limited user (used for RBAC verification)

## Tech Stack
- React SPA + FastAPI backend
- Supabase + MongoDB
- ThemeContext (Light/Dark/DashPro) with CSS variables
- OpenAI/Anthropic via Emergent Universal LLM Key

## Recent Work (Feb 2026)
- ✅ Fixed VehicleDetails faded colors
- ✅ Restored backend core files from accidental overrides
- ✅ Fixed @/lib/utils alias imports across 41 component files
- ✅ Theme toggle (Light/Dark/DashPro) — instant apply + localStorage persistence
- ✅ Fixed "quick revert" bug — settings save no longer reverts UI
- ✅ **[2026-02] Fixed sidebar dark gradient leaking into Light theme** — overrode `background-image` and `background` shorthand in `body.light-mode .sidebar-modern` and `body[data-theme="dashPro"] .sidebar-modern`

## Backlog
- **P1**: Refactor `server.py` → split into routers (Vehicles, Customers, Suppliers)
- **P1**: Refactor `routes_extended.py` → split (Visits, Operations, Vehicles)
- **P1**: Get actual detailed `Problemss.csv` issue descriptions from user
- **P2**: OCR for automatic invoice auditing
- **P2**: Mini-ledger for advance payments per vehicle/customer

## Key Files
- `/app/frontend/src/contexts/ThemeContext.jsx`
- `/app/frontend/src/index.css` (theme overrides)
- `/app/frontend/src/components/Sidebar.jsx`
- `/app/frontend/src/pages/Settings.jsx`
- `/app/backend/server.py`
- `/app/backend/routes_extended.py`
- `/app/backend/routes_finance.py`
