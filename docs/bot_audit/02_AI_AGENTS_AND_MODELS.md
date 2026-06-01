# 02 — AI Agents and Models

**Source files**:
- `/app/backend/core/assistant_kernel.py`
- `/app/backend/core/tool_router.py`
- `/app/backend/core/ai_context.py`
- `/app/backend/core/shared_memory.py`
- `/app/backend/core/alert_bus.py`
- `/app/backend/routes_assistant.py`

## Multi-agent or single kernel?

| Question | Answer | Evidence |
|---|---|---|
| Is there a real multi-agent system? | **No** | `assistant_kernel.chat()` is the single entry point; it dispatches read-only tools but does not delegate to other LLM-driven agents. |
| Is there a Supervisor Agent? | **No** | No supervisor class exists. `assistant_kernel.detect_agent()` is `@deprecated` and always returns `"Assistant"` (see line 281). |
| Is there an Admin Agent? | **No** | `FinanceAgent`, `WorkshopAgent`, `FirewallAgent` are **string labels** attached to tools for UI categorisation — not separate LLM personas. |
| Is there a Technician Agent? | **No** | Not registered anywhere. |
| Is there a Customer Agent? | **No** | The Genspark customer bot is **external**; nothing inside this codebase serves customers. |
| Is the bot a single `assistant_kernel`? | **Yes** | `kernel_stats()` reports `"mode": "single_assistant_read_only"`. |

### Confirmation from the live runtime
```
GET /api/assistant/stats →
{
  "assistant_name": "Beeeeta8 Assistant",
  "assistant_version": "L5.1",
  "mode": "single_assistant_read_only",
  "memory": { active_sessions, total_messages },
  "alert_bus": { subscribers_count, events_in_log, alerts_tracked },
  "tools_registered": 12,
  "ai_enabled": true
}
```

## LLM model & provider

| Item | Value | Source |
|---|---|---|
| Library | `emergentintegrations.llm.chat.LlmChat` | `assistant_kernel._llm_chat()` line 74 |
| Provider (hardcoded) | `openai` | `_llm_chat(... model_provider="openai" ...)` line 67 |
| Model (hardcoded) | `gpt-4o-mini` | `_llm_chat(... model_name="gpt-4o-mini" ...)` line 68 |
| API key source | `os.getenv("EMERGENT_LLM_KEY")` | `_emergent_llm_key()` line 56 |
| Fallback model | **None** | If LLM call fails or key missing → returns a rule-based canned reply ("النظام يعمل بقواعد محلية حالياً") |

⚠️ The `MOLTBOT_OPENAI_MODEL`, `DEEPSEEK_MODEL`, `GROQ_MODEL` env vars exist but
are consumed by **other bots** (`routes_moltbot.py`, `routes_workshop_bot.py`,
etc.), **not by the floating Unified Assistant**.

## System prompt

| Property | Value |
|---|---|
| Location | `assistant_kernel._system_prompt()` line 101 |
| Dynamic? | **Partially** — base prompt is static; appended dynamically with: (1) `context_to_text(snapshot)` (cash flow, health score, alerts), (2) tool results section if any. |
| Mentions tools? | **Yes** — enumerates all 12 tools by name with a one-line description. |
| Mentions read-only? | **Yes** — explicit rule "لا تستدع أداة تكتب/تعدّل/تحذف". |
| Mentions output style? | Markdown allowed/preferred (tables, bullets, **bold**). |
| Mentions language? | Arabic فصحى مبسطة. |

## Memory

| Layer | Type | Lifetime | Implementation |
|---|---|---|---|
| Conversation memory (per session) | in-process dict | 1 hour TTL after last seen | `shared_memory._sessions` — `messages` list (cap 60 items) |
| Recent actions (per session) | in-process list | 1 hour TTL | `shared_memory._sessions[sid]["actions"]` (cap 30 items) |
| Alerts seen (per session) | in-process set | 1 hour TTL | `shared_memory._sessions[sid]["alerts_seen"]` |
| Context kv (per session) | in-process dict | 1 hour TTL | `shared_memory._sessions[sid]["context"]` |
| Shared global memory | **None** | — | All state is per-session-id. |

⚠️ All memory is **in-process**. A backend restart wipes every session's
history. `localStorage` on the client persists the `session_id` only, so the
client tries to reload its history from `/api/assistant/session/{id}` — if the
server restarted, that endpoint returns an empty list, and the client falls
back to optimistic state.

## Alert bus

| Item | Value |
|---|---|
| Location | `/app/backend/core/alert_bus.py` |
| Subscribers (live, at audit) | 0 |
| Events in log | 0 |
| Alerts tracked | 0 |
| Used by | `assistant_kernel.get_recent_alerts_for_assistant()` reads `get_active_alerts()` — but the **firewall engine does not currently publish** to the bus (it builds alerts on-demand inside `run_full_analysis()`). |

⚠️ The alert_bus is functional but **dormant** — no producer is feeding it.
This means `GET /api/assistant/alerts` always returns `[]` unless something
publishes via `alert_bus.publish_alerts_batch(...)`.

## Streaming

| Item | Value |
|---|---|
| Backend streaming? | **No** — `LlmChat.send_message()` is awaited for a full string. |
| Frontend streaming? | **No** — `AssistantProvider.sendMessage()` awaits the full response and renders once. |
| Typing indicator | Yes — `data-testid="assistant-typing"` shown while `busy=true` (visual placeholder only, not real streaming). |

## Voice

| Item | Value |
|---|---|
| Speech-to-text? | **No** — no STT in any frontend or backend file. |
| Text-to-speech? | **No** — no TTS integration. |
| Audio recording UI? | **No** — input is text-only. |

## Other agents in the codebase (NOT the floating bot)

These exist as **separate route files** and have their own bots/UI, completely
independent from the Unified Assistant:

| File | Purpose | Touches floating bot? |
|---|---|---|
| `routes_alkabeer_bot.py` | Legacy "Al-Kabeer" customer bot (test fixture) | **No** |
| `routes_finance_bot.py` | Pre-L5 finance-only bot | **No** |
| `routes_workshop_bot.py` | Pre-L5 workshop-only bot | **No** |
| `routes_moltbot.py` | In-app code editor / Moltbot studio | **No** |
| `routes_gemini_chat.py` | Gemini chat endpoint (diesel/diagnostics) | **No** |
| `routes_diesel_chat.py` | Diesel-engine Q&A | **No** |
| `routes_whatsapp_bot.py` | WhatsApp webhook (not wired to floating bot) | **No** |
| `routes_nlp_page_assistant.py` | Per-page NLP helper | **No** |

The Unified Floating Assistant uses **only** `routes_assistant.py` + `core/*`.

## Summary

- **Architecture**: Single L5 read-only kernel. No real multi-agent. No supervisor.
- **Model**: `openai/gpt-4o-mini` via Emergent Universal Key.
- **Fallback**: Rule-based canned reply (no second LLM).
- **Memory**: Per-session, in-process, 1-hour TTL.
- **Streaming**: Not implemented.
- **Voice**: Not implemented.
- **Alert bus**: Functional skeleton, currently dormant (no producer).
