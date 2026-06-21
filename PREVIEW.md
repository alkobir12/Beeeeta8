# 🔧 Workshop App — Preview Guide

A bilingual (Arabic/English RTL) auto-repair **workshop management ERP**: vehicles,
visits, customers, suppliers, parts inventory, invoicing, full accounting, and AI assistants.

---

## ▶️ Run it

Both services start independently. No MongoDB is required — the backend falls back to
file-based storage (`backend/uploads/*.json`) when `MONGO_URL` is unset.

### Backend (FastAPI · port 8001)
```bash
cd backend && DB_PROVIDER=memory uvicorn server:app --host 0.0.0.0 --port 8001
```

### Frontend (React · port 3000)
```bash
cd frontend && BROWSER=none PORT=3000 DANGEROUSLY_DISABLE_HOST_CHECK=true yarn start
```

> On Claude Code on the web, open the **Preview** panel on port **3000**.

---

## 🔑 Login

Passwordless quick admin login — type the username and submit:

| Field | Value |
|-------|-------|
| Username (اسم المستخدم) | `مدير` |
| Password | _none — leave blank_ |

The frontend talks to the backend through the dev proxy
(`"proxy": "http://localhost:8001"` in `frontend/package.json`).

---

## ✅ Health checks

```bash
curl http://localhost:8001/api/health   # → {"status":"ok"}
curl -o /dev/null -w "%{http_code}" http://localhost:3000/   # → 200
```

---

## 🗺️ Feature map

| Area | Route | Page |
|------|-------|------|
| Dashboard | `/` | `Dashboard.jsx` |
| Vehicles & visits | `/vehicles/:id` | `VehicleDetails.jsx` |
| Customers | `/customers` | `Customers.jsx` |
| Suppliers | `/suppliers` | `Suppliers.jsx` |
| Parts inventory | `/parts` | `PartsInventory.jsx` |
| Operations | `/operations` | `Operations.jsx` |
| Invoices | `/invoices` | `Invoices.jsx` |
| Invoice designer | `/invoice-designer` | `InvoiceDesignerStudio.jsx` |
| Accounting (comprehensive) | `/accounting/comprehensive` | `ComprehensiveFinancial.jsx` |
| Chart of accounts | `/accounting/chart` | `ChartOfAccountsLiquid.jsx` |
| Journal entries | `/accounting/journal` | `JournalEntries.jsx` |
| AI financial assistant | `/ai-financial` | `AIFinancial.jsx` |
| Settings | `/settings` | `Settings.jsx` |

---

## ⚠️ Notes & limitations

- **AI chat features are stubbed.** The proprietary `emergentintegrations` package
  is not on public PyPI; the session-start hook installs a local stub so imports
  succeed, but live LLM calls raise a clear runtime error. Set the real package +
  provider keys to enable them.
- **External integrations off by default** (Supabase, Twilio/WhatsApp, Google) —
  they run in mock/deeplink mode until credentials are provided via env vars.
- **Memory mode is ephemeral** — data lives in `backend/uploads/` and resets if
  that directory is cleared. Set `MONGO_URL` + `DB_NAME` for persistence.
