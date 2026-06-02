# 09 — L16 Floating Assistant Roadmap

**Source**: User-provided spec (2026-02-12), Conversational ERP Operator.
**Target**: Transform `Beeeeta8 Assistant L5.1` (Read-Only) → `L16 Conversational ERP Operator`.
**Current real level**: L3.5 (tool-using, regex-routed, read-only).
**Total estimated effort**: ~25–35 dev-hours across 5 phases.

---

## 0. Vision (one paragraph)

The floating assistant becomes the **primary ERP interface** — every read,
every action, every approval can be done by talking to the bot. Pages stay
as a secondary surface. Replies render as **interactive cards with action
buttons** (preview, approve, send WhatsApp, generate PDF, …). The bot
remembers long-term context (weekly/monthly revenue, last operations, customer
notes), adapts tone per audience (formal for admins, operational for
technicians, Qassimi-friendly for customers), and never exposes secrets.

---

## 1. Phase Map (locked sequence)

| Phase | Title | Effort | Risk | Status |
|---|---|---|---|---|
| **3A** | Foundation: contract, rate limit, audit log, logging | ~2h | 🟢 LOW (additive, no behaviour change) | ✅ **DONE (Session 8)** — 25/25 tests, rate limit live, audit log writing to memory buffer until SQL migration runs |
| **3B** | Interactive Cards + Action Buttons + Entity Resolution | ~4–6h | 🟡 MEDIUM (new UI surface) | ⏳ READY TO START |
| **3C** | ERP Execution Runtime (write tools + Approval + Idempotency + Rollback) | ~8–12h | 🔴 HIGH (accounting impact) | locked behind 3B |
| **3D** | WhatsApp send-invoice / send-receipt / send-PDF from cards | ~4–6h | 🟡 MEDIUM (needs WhatsApp Cloud API credentials) | locked behind 3C |
| **3E** | Mobile UX polish + Streaming responses | ~3–4h | 🟢 LOW | parallel-safe with 3D |
| **3F** | Vehicles / Inventory DDD (extracted from monolith) | TBD | 🟠 MEDIUM (accounting touch) | independent — schedule after 3E |

---

## 2. Phase 3A — Foundation (start here)

### Acceptance criteria

| # | Item | File(s) | DoD |
|---|---|---|---|
| A1 | `register_tool(..., write: bool = False)` contract — default False; assertion in `assistant_kernel.chat()` that no tool with `write=True` is invoked (until 3C opens the gate via a feature flag). | `/app/backend/core/tool_router.py`, `/app/backend/core/assistant_kernel.py` | All 12 existing tools register cleanly. Trying to register `write=True` without `BOT_ALLOW_WRITES=1` raises. |
| A2 | Per-IP rate limit on `POST /api/assistant/chat` (default 30 req/min). | `/app/backend/routes_assistant.py` + `slowapi` (add to requirements) | Hammering the endpoint returns 429 after threshold. |
| A3 | `bot_audit_log` table in Supabase — columns: `id, ts, session_id, user_id?, intent, tools_called[], ai_used, fallback_used, tokens_in?, tokens_out?, request_hash`. Inserted from `chat()` end. **No user message content stored** by default; redact via A4. | new file `/app/backend/domains/bot_audit/{repository,service}.py` + Supabase migration note | Each `/chat` call writes one row. |
| A4 | Replace `print(...)` error paths in `assistant_kernel.py` with `logging.getLogger(__name__)` and add `redact(text)` helper. | `/app/backend/core/assistant_kernel.py`, new `/app/backend/core/log_utils.py` | No raw user content in stdout/stderr. |
| A5 | Regression tests: (1) `register_tool(write=True)` blocked; (2) rate limit fires; (3) audit log row inserted; (4) redacted log line. | new `/app/backend/tests/test_phase_3a_foundation.py` | All 4 tests pass. |

### Out of scope for 3A

- No new UI components.
- No new write tools (A1 just sets the contract).
- No card system yet.
- No WhatsApp.
- No streaming.

### Why this order

3A is **defensive, additive, invisible to users**. It guarantees that
everything after it (cards, writes, approvals) is observable and bounded.
Without 3A, ERP execution in 3C is dangerous.

---

## 3. Phase 3B — Interactive Cards + Action Buttons + Entity Resolution

### Card catalogue (13 types from spec)

| Card | Primary data | Default actions |
|---|---|---|
| `CustomerCard` | name, phone, balance, debt | كشف حساب · فواتير · مركبات · اتصال · واتساب |
| `VehicleCard` | plate, brand, model, owner, last visit | فتح ملف · جدول الصيانة · تاريخ الفواتير |
| `VisitCard` | vehicle, status, parts, total | معاينة · طباعة · إغلاق |
| `OperationCard` | type, total, partner, status | معاينة · فتح · إلغاء |
| `InvoiceCard` | number, customer, total, status | معاينة · إرسال واتساب · طباعة PDF · اعتماد · إلغاء |
| `PaymentCard` | amount, method, partner, status | معاينة · اعتماد · إرسال إشعار |
| `InventoryCard` | name, SKU, qty, price | عرض · حجز · نقل |
| `SupplierCard` | name, balance, contact | كشف · واتساب · إنشاء فاتورة شراء |
| `ApprovalCard` | requester, amount, reason, expires | قبول · رفض · تعليق |
| `WhatsAppCard` | recipient, template, preview | إرسال · جدولة |
| `ReportCard` | period, data summary | فتح · تصدير PDF · مشاركة |
| `AuditCard` | rule, severity, affected | افتح المصدر · تجاهل · أرشفة |
| `FindingCard` | type, evidence, recommendation | اعتماد · رفض · تفصيل |

### Wire protocol (frontend ↔ backend)

Backend tool returns:
```json
{
  "response": "ذمم العملاء هذا الأسبوع …",
  "cards": [
    {
      "type": "CustomerCard",
      "data": { "id": "abc", "name": "إبراهيم", "balance": 3200, ... },
      "actions": [
        { "id": "pdf", "label": "PDF", "intent": "report.customer_statement", "payload": {...} },
        { "id": "wa",  "label": "واتساب", "intent": "whatsapp.send_statement", "payload": {...} }
      ]
    }
  ]
}
```

Frontend in `UnifiedAssistantDrawer.jsx` adds a renderer that walks
`message.cards` and shows a card per item. Actions dispatch to a new
`/api/assistant/action` endpoint (read-only intents only in 3B; write
intents activated in 3C).

### Entity resolution

Add a small NER-lite step in `assistant_kernel.chat()`:
1. Run regex/heuristic over the user message to extract candidate entities (names, plate numbers, amounts, dates).
2. Pass them to the tool as `entities=[…]`.
3. Tool returns matching cards.

Phase 3B keeps the read-only contract; cards merely surface existing
data with richer UI.

---

## 4. Phase 3C — ERP Execution Runtime (HIGH risk)

| Sub-task | File(s) |
|---|---|
| Open the `write=True` gate behind `BOT_ALLOW_WRITES=1` + per-tool ACL | `tool_router.py`, `assistant_kernel.py` |
| Execution Lock: each write operation acquires a distributed lock (Postgres `pg_try_advisory_lock` or Supabase `pg_advisory_xact_lock`) keyed by `entity_id` | new `core/execution_lock.py` |
| Idempotency: client supplies `request_id` (UUID); duplicate replays return cached result | `routes_assistant.py` |
| Audit: every write produces a `bot_audit_log` row with `before`/`after` snapshots | extension of A3 |
| Rollback: each write returns a `rollback_token`; calling `/api/assistant/rollback {token}` reverses the operation if not yet finalised | new endpoint |
| Approval matrix: amounts above thresholds trigger `ApprovalCard` flow (Four-Eyes Principle) | new `core/approval_engine.py` |
| Initial write tools (proposed): `payment.collect_from_customer`, `invoice.send_whatsapp`, `inventory.reserve`, `operation.approve` | new tool handlers |

⚠️ This is the **largest** phase by risk. It must NOT ship without:
- Full pytest coverage of lock + idempotency + rollback
- Production-mirror integration test using a sandbox workshop
- Operator-side kill switch (env var `BOT_ALLOW_WRITES=0` should disable instantly)

---

## 5. Phase 3D — WhatsApp

| Sub-task | Notes |
|---|---|
| Provision WhatsApp Cloud API credentials (`WHATSAPP_TOKEN`, `WHATSAPP_PHONE_ID`) | operator action |
| New tool `whatsapp.send_invoice(customer_id, invoice_id)` (write, requires 3C contract) | calls Cloud API |
| New tool `whatsapp.send_statement(customer_id, period)` | generates PDF + sends |
| `WhatsAppCard` UI with preview + confirm | frontend |
| Webhook for delivery + read receipts | new `/api/whatsapp/webhook` |

---

## 6. Phase 3E — Mobile UX + Streaming

| Sub-task | Files |
|---|---|
| Drawer becomes full-screen on viewports < 768px | `UnifiedAssistantDrawer.jsx` |
| Cards stack vertically on mobile, action buttons wrap | same |
| Streaming via Server-Sent Events: backend yields tokens, frontend renders progressively | `routes_assistant.py` (new `/chat/stream` route), `AssistantProvider.jsx` |
| Voice integration **deferred** per spec | — |

---

## 7. LLM Strategy (resolved from prior audits)

| Layer | Provider | Model | When |
|---|---|---|---|
| Default | Emergent | `openai/gpt-4o-mini` (Phase 3A) → `openai/gpt-4o` (Phase 3B onwards) | always |
| Fallback (Option B) | Groq | Llama-4-Maverick (via existing `GROQ_API_KEY` + swapping `GROQ_MODEL` to `LLAMA_MAVERICK_MODEL_ID`) | when Emergent fails |
| Voice | — | — | **deferred** |

Implementation note: the fallback is wired in Phase 3A code path so that
the foundation can be exercised under provider failure from day one.

---

## 8. Long-Term Memory (Phase 3B + extends in 3C)

| Layer | Mechanism |
|---|---|
| Session memory (existing) | in-process dict, TTL 1h |
| **Long-term memory (new)** | Supabase table `bot_memory_chunks` with: `id, user_id, kind (revenue/operation/note), period_start, period_end, payload_jsonb, created_at`. Read at start of `chat()` and injected into context_snapshot. |
| Pre-aggregated rollups | weekly_revenue, monthly_revenue, monthly_ap, monthly_ar — refreshed by a nightly job (not part of 3A). |

---

## 9. Audience Behaviour (Phase 3B)

| Audience | Detection | Tone |
|---|---|---|
| Admin | default for users in `admin` role | فصحى رسمية، بيانات كاملة |
| Technician | `technician` role | عملي، خطوات قصيرة، لا بيانات مالية حساسة |
| Customer | accessed via `/track/{trackingId}` or external bot endpoint | قصيمي ودود، **لا أرصدة عامة**، فقط حالة المركبة/الفاتورة الخاصة به |

The customer audience requires the permission matrix (3A defers; 3B
opens the surface; the actual exposure happens only when an external
endpoint is added — out of L16 scope unless explicitly requested).

---

## 10. Locked NO-GO list (must not touch in any phase without explicit approval)

- ❌ `POST /api/vehicles/{id}/save-parts-and-create-journal` (accounting risk)
- ❌ Vehicles DDD extraction (carries `save-parts-and-create-journal`)
- ❌ Inventory DDD extraction (deferred)
- ❌ Voice integration
- ❌ Replacing all other bots (Moltbot/Workshop/Al-Kabeer/WhatsApp/OCR keep their current models)
- ❌ Installing Ollama (out of scope per LLM strategy §7)

---

## 11. First-session plan (this session, if user approves)

**Phase 3A only**. Concrete deliverables:

1. ☐ `register_tool(... write=False)` contract + assertion.
2. ☐ Slowapi rate limit on `/api/assistant/chat`.
3. ☐ `bot_audit_log` Supabase table + repository + service.
4. ☐ `logging` + `redact()` instead of `print()`.
5. ☐ Regression tests (4 tests).
6. ☐ Update `04_API_KEYS_STATUS_SAFE.md` with the Groq + Llama-Maverick corrections.
7. ☐ Update PRD/CHANGELOG with 3A delivery.

**No frontend changes. No write tools. No card UI. No WhatsApp.**

After 3A ships and a smoke test passes, the next session can begin 3B.

---

## 12. Approval gate

Before starting 3A, the user must confirm:

1. Default LLM upgrade `gpt-4o-mini → gpt-4o`? (per §7) — yes/no
2. Add Groq fallback in 3A (Option B from audit 08)? — yes/no
3. Approve `bot_audit_log` table creation in Supabase? — yes/no
4. Approve adding `slowapi` to `requirements.txt`? — yes/no
5. Any constraint I missed?
