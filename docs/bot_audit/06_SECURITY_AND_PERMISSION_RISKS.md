# 06 — Security and Permission Risks

**Classification scale**: `LOW` / `MEDIUM` / `HIGH` / `CRITICAL`
**Audit method**: Static read of `core/*`, `routes_assistant.py`, `tool_router.py`,
`assistant_kernel.py`, `AssistantProvider.jsx`, `UnifiedAssistantDrawer.jsx`,
plus live test of 10 read-only queries (zero writes performed).

---

## 1. Permission Matrix

| Check | Status |
|---|---|
| Is there a formal permission matrix for the bot? | ❌ **No** |
| Are tools classified `read` vs `write`? | ⚠️ **Implicitly yes** — the registry has no `write` tools, but there is no schema field/flag enforcing this. A future contributor could register a write-capable handler without any guard. |
| Are tools tagged by agent (Finance / Workshop / Firewall)? | ✅ Yes — `register_tool(..., agent="FinanceAgent")` etc. — **for UI labelling only**, **not for permission enforcement**. |
| Is there role-based access? | ❌ **No** — any authenticated session that can reach `POST /api/assistant/chat` can invoke every tool. |
| Does the bot filter PII for non-admin users? | ❌ **No filtering** — but currently only admin routes mount the bot, so the audience is effectively admin-only. |
| Customer-facing isolation? | ✅ The 4 public routes (`/login`, `/approval/:token`, `/report/:token`, `/track/:trackingId`) are **outside** `<Layout>` → the bot is not rendered there. |

**Risk level**: 🟡 **MEDIUM** — current isolation is correct (admin-only mount),
but enforcement is by-convention (route structure) not by-code (permission
middleware). A future change that mounts `<Layout>` on a public route would
silently expose the bot.

---

## 2. Audit Log

| Check | Status |
|---|---|
| Is each chat request persisted to a DB? | ❌ **No** — `shared_memory` is in-process only. |
| Is each tool call logged? | 🟡 **Per session only** — `shared_memory.track_action(sid, "tool_call", {...})` stores last 30 entries per session, lost on backend restart. |
| Is user identity (user_id) tied to bot logs? | ❌ **No** — `chat()` receives an optional `user_id` field but **does not persist it**. |
| Can the operator answer "who asked X and when?" after a restart? | ❌ **No**. |

**Risk level**: 🟠 **MEDIUM-HIGH** for production — financial environments
typically require an immutable audit trail. The bot reads customer balances,
operation totals, and supplier debt — these queries should be auditable.

---

## 3. Rate Limiting

| Check | Status |
|---|---|
| Is `POST /api/assistant/chat` rate-limited? | ❌ **No** — `routes_assistant.py` has no rate-limit decorator. |
| Is per-IP / per-user throttle enabled at the app level? | ❌ Not in `server.py` middleware chain (only CORS + auto-correction middleware). |
| Could a malicious client exhaust `EMERGENT_LLM_KEY` budget? | ⚠️ **Yes** — a logged-in user could spam `/chat` and burn token budget. |

**Risk level**: 🟠 **MEDIUM-HIGH** — unbounded LLM cost exposure.

---

## 4. Prompt Injection Protection

| Check | Status |
|---|---|
| Does the bot sanitise user input before injecting into the LLM prompt? | ❌ **No** — user text is inserted verbatim into `UserMessage(text=text)`. |
| Are tool results sanitised before being shown to the LLM as a "system" payload? | 🟡 Partial — they are passed via `f"نتائج الأدوات: ```{json.dumps(...)}```"` inside the user message — not as a system role; user input could theoretically inject instructions but the LLM is told to follow the system prompt's read-only rule. |
| Does the system prompt explicitly forbid write actions? | ✅ Yes — `"ممنوع الرد بـ 'لا يمكنني فتح أو تعديل'"` and `"كل الأدوات قراءة فقط"`. |

**Risk level**: 🟡 **MEDIUM** — even with a successful prompt-injection, the
worst case is the LLM **generating text** that claims to do something. There
is no codepath that lets the LLM **execute** writes — tool execution happens
*before* the LLM, based on regex matches against the **user message only**,
not the LLM's output. This is a strong structural safeguard.

---

## 5. Data Disclosure

| Disclosure | Severity | Mitigation |
|---|---|---|
| Customer name + phone + AR balance via `customers.search` | 🟠 MEDIUM-HIGH | Currently mounted in admin-only routes. |
| Vehicle plate + owner name via `vehicles.search` | 🟡 MEDIUM | Same. |
| Supplier name + AP balance via `finance.payables_summary` | 🟡 MEDIUM | Same. |
| Operation totals + payment status via `operations.recent` | 🟡 MEDIUM | Same. |
| Firewall health score + financial-impact-per-alert via `firewall.*` | 🟡 MEDIUM | Same. |
| Part SKU + cost + sell price + stock count via `parts.search` / `inventory.low_stock` | 🟡 MEDIUM | Same. |

If the bot were ever mounted on a customer-facing route (e.g.,
`/track/:trackingId`), every one of the above would leak. The route-level
exclusion is therefore **load-bearing**.

---

## 6. Write Tools / Hidden Mutation Paths

| Check | Result |
|---|---|
| Grep `tool_router.py` for `.insert(` / `.update(` / `.delete(` / `.upsert(` inside any registered handler. | **0 matches** in registered handlers. |
| Grep for `POST` / `PUT` / `DELETE` httpx calls inside handlers. | **0 matches** — only `httpx.get(...)`. |
| Does `assistant_kernel.chat()` call any DB write? | **No** — only reads session memory + writes session memory (in-process). |
| Is `/api/assistant/tool/{name}` a back-door for write tools? | The endpoint exists (`routes_assistant.py` line 51), but it only calls `tool_router.call_tool(name, ...)`. If only read tools are registered, it can only invoke reads. |

**Conclusion**: ✅ No mutation path is reachable through the bot. **However**,
this property is **runtime-determined** by which tools are registered; there
is no static guarantee.

**Risk level**: 🟢 **LOW** *today*, but 🟠 MEDIUM as a *governance* concern —
the codebase needs a contract like `register_tool(..., write=False)` and a
test that asserts no write tools exist.

---

## 7. Risk from `save-parts-and-create-journal` and similar high-impact endpoints

| Endpoint | Touches floating bot? | Risk to bot |
|---|---|---|
| `POST /api/vehicles/{id}/save-parts-and-create-journal` | ❌ **No** — never referenced by `core/*` or `routes_assistant.py`. | None at present. |
| `POST /api/operations` / `PUT /api/operations/{id}` | ❌ No | None. |
| Journal entry creation / approval | ❌ No | None. |

**Risk level**: 🟢 **LOW** — these endpoints are completely separate from the
bot's surface.

---

## 8. Risk of Linking an External Bot in the Future

| Scenario | Risk |
|---|---|
| Connecting an external customer bot (Genspark/WhatsApp/Web widget) to `/api/assistant/chat` directly | 🔴 **HIGH** — would leak admin-grade data to customers immediately. |
| Connecting an external bot to a **new** customer-scoped endpoint that proxies a **subset** of tools | 🟡 MEDIUM — requires per-tool ACL + customer auth. |
| Using OAuth/JWT to scope the bot to a specific tenant | 🟢 LOW (if implemented) |

**Risk level**: 🔴 **HIGH** if implemented carelessly. **Mitigation
required**: introduce a permission matrix + audience tagging *before* any
external integration.

---

## 9. Concurrency / Session Leakage

| Check | Status |
|---|---|
| Are sessions keyed by user id or by client-generated id? | Client generates `sessionId` (UUID) on first interaction; not bound to user. |
| Can two users share a `sessionId`? | Only if they share `localStorage` (same tab/cookie) — unlikely. |
| Is `shared_memory` thread-safe? | Python dicts under asyncio are safe for single-process; not safe under multi-worker uvicorn unless sticky-session is enforced. The current deployment runs 1 worker → OK. |

**Risk level**: 🟢 **LOW** for current single-worker deployment.

---

## 10. Logging / PII in Logs

| Check | Status |
|---|---|
| Does `assistant_kernel.chat()` log user messages? | ⚠️ Indirectly — `print(f"AI generation failed: {e}")` may surface part of the user content. |
| Are tool results logged? | No structured logs; only `print` on error paths. |
| Are LLM responses logged? | No. |

**Risk level**: 🟡 **MEDIUM** — current `print()` calls are benign but could
leak PII into stdout/supervisor logs under error conditions. A move to
structured logging with redaction is recommended.

---

## Risk Summary (Top 5)

| # | Risk | Severity | Notes |
|---|---|---|---|
| 1 | No rate limiting on `/api/assistant/chat` → LLM budget exhaustion | 🟠 MEDIUM-HIGH | Easiest exploit path for an authenticated user. |
| 2 | No persistent audit log of who asked what | 🟠 MEDIUM-HIGH | Required for any financial compliance posture. |
| 3 | No formal permission matrix → mounting bot on public route would expose PII silently | 🔴 HIGH (contingent) | Risk activates only if a future route mistake mounts `<Layout>` publicly. |
| 4 | Bot has no `write=False` contract → future contributor could register a write tool | 🟡 MEDIUM | Governance gap. |
| 5 | `print()`-based error logging may leak partial user input | 🟡 MEDIUM | Replace with structured logger + redaction. |

## Risks classified as LOW (acceptable as-is)

- Write tools / hidden mutation paths (zero exist today).
- Risk from `save-parts-and-create-journal` (no link to bot).
- Concurrency / session leakage (single worker, client UUIDs).
- Prompt injection → write actions (structural firewall: tools fire from regex on user message, not LLM output).
