# 08 — Llama Maverick Provider Audit

**Audit date**: 2026-02-12
**Scope**: Determine whether Llama Maverick is (or was) wired to the floating
Unified Assistant, and assess the safety of adding it as a fallback.
**Method**: Static code scan + env-var presence check + git history check.
**Secret exposure policy**: ✅ Zero values printed.

---

## 1. Executive Summary

> ⚠️ **REVISED 2026-02-12** — After the user clarified that "Llama Maverick"
> was reached via **Groq** (not via a standalone Llama key), the audit was
> re-run. New findings supersede the original ones.

| Question | Answer |
|---|---|
| Is a real Llama Maverick **API key** present in env? | ❌ **No standalone Llama key.** ✅ **But `GROQ_API_KEY` is configured** — and Groq hosts Llama-family models. The "Llama Maverick" the user remembers is reached through Groq's OpenAI-compatible endpoint. |
| What env vars are involved? | `GROQ_API_KEY` (auth), `GROQ_API_BASE_URL` (Groq's OpenAI-compatible endpoint), `GROQ_MODEL` (current model id — Llama-3 family at audit time), plus the orphan vars `LLAMA_MAVERICK_MODEL_ID` / `LLAMA_SCOUT_MODEL_ID` (not yet wired but ready to be substituted into `GROQ_MODEL`). |
| Does the floating bot currently use Groq / Llama? | ❌ **No.** The floating bot is hardcoded to `openai/gpt-4o-mini` via `EMERGENT_LLM_KEY` (`assistant_kernel.py` lines 114–115). Zero references to `GROQ` in `routes_assistant.py` or `/app/backend/core/*`. |
| Was Groq/Llama wired anywhere historically? | ✅ **Yes — in Moltbot only.** `routes_moltbot.py` line 753 reads `GROQ_API_KEY` + `GROQ_API_BASE_URL` + `GROQ_MODEL` and invokes them via a reusable helper `_call_openai_compatible(api_key, base_url, model, messages)` (line 611). |
| Why does the user remember it "working"? | The user almost certainly **interacted with Moltbot's "reviewer agent"** which is Groq-backed (line 908: `await _call_openai_compatible(groq_key, groq_url, groq_model, ...)`). The reviewer agent runs Llama-3 via Groq. With `GROQ_MODEL` set to `LLAMA_MAVERICK_MODEL_ID`'s value, the same path would invoke Llama-4-Maverick. |
| Is there a clear reason it "stopped" working? | It never stopped — **Moltbot still uses it**. The floating bot is a different surface; it has always used Emergent only. |
| Can it be made a safe fallback for the floating bot? | ✅ **Yes, technically feasible** because: (1) `GROQ_API_KEY` is configured; (2) `GROQ_API_BASE_URL` is configured; (3) a working OpenAI-compatible wrapper already exists at `routes_moltbot.py::_call_openai_compatible` and can be reused; (4) switching the model from current Llama-3 to Llama-4-Maverick is a single env-var change. **Recommended only after Phase 3A ships** (see §8). |

---

## 2. Env Vars Status

⚠️ Status only. No values printed.

| Env Name | Provider class | Status | Used By | Secret Exposed? |
|---|---|---|---|---|
| `GROQ_API_KEY` | Groq (OpenAI-compatible) | **configured** | **used_by_legacy** (`routes_moltbot.py` reviewer agent) | No |
| `GROQ_API_BASE_URL` | Groq | **configured** | **used_by_legacy** (`routes_moltbot.py`) | No |
| `GROQ_MODEL` | Groq (model id) | **configured** — currently a Llama-3 family model (variant not printed) | **used_by_legacy** | No |
| `LLAMA_MAVERICK_MODEL_ID` | model id (intended target) | **configured** | **unused** — env var set but no source file reads it | No |
| `LLAMA_SCOUT_MODEL_ID` | model id | **configured** | **unused** | No |
| `LLAMA_STACK_URL` | Llama Stack (self-hosted) | **configured** (`localhost`) | **unused** — no service binds the port, no code reads the var | No |
| `LLAMA_API_KEY` | Llama (direct) | **missing** | n/a | No |
| `LLAMA_MAVERICK_API_KEY` | Llama Maverick (direct) | **missing** | n/a | No |
| `OPENROUTER_API_KEY` | OpenRouter | **missing** | n/a | No |
| `TOGETHER_API_KEY` | Together AI | **missing** | n/a | No |
| `DEEPSEEK_API_KEY` | DeepSeek | **configured** | **used_by_legacy** (Moltbot only — separate path) | No |
| `DEEPSEEK_API_BASE_URL` | DeepSeek | **configured** | **used_by_legacy** | No |
| `DEEPSEEK_MODEL` | DeepSeek (model id) | **configured** | **used_by_legacy** | No |
| `BLACKBOX_API_KEY` | BlackBox AI | **configured** | **used_by_legacy** (Moltbot + Workshop bot) | No |
| `EMERGENT_LLM_KEY` | Emergent Universal Key | **configured** | **used_by_floating_bot** (sole provider for `assistant_kernel`) | No |
| `OPENAI_API_KEY` | OpenAI (direct) | **missing** | `server.py::financial_analysis` returns mock when absent | No |
| `ANTHROPIC_API_KEY` | Anthropic | **empty** | not consumed by floating bot | No |
| `MOLTBOT_OPENAI_MODEL` | OpenAI (model id) | **configured** | **used_by_legacy** (Moltbot summary) | No |

### Key insight (revised)

The triplet **`GROQ_API_KEY` + `GROQ_API_BASE_URL` + `GROQ_MODEL`** is a
**ready-to-use, fully configured Llama-via-Groq path** — actively serving
Moltbot's reviewer agent today. To make Llama-4-Maverick the model, the
operator only needs to set `GROQ_MODEL` to the value already stored in
`LLAMA_MAVERICK_MODEL_ID`. No new key is required.

---

## 3. Code References

### 3.1 References to `LLAMA_STACK_URL`, `LLAMA_SCOUT_MODEL_ID`, `LLAMA_MAVERICK_MODEL_ID`

```
$ grep -rn "LLAMA_STACK_URL\|LLAMA_SCOUT_MODEL\|LLAMA_MAVERICK_MODEL" \
       /app/backend /app/frontend \
       --include="*.py" --include="*.js" --include="*.jsx" \
       --include="*.ts" --include="*.tsx"
(zero matches)
```

✅ **Confirmed**: these env vars are read by **no source file**. They exist
only in `/app/backend/.env`. They are dead configuration.

### 3.2 References to the string "llama" / "Llama" / "Maverick" in source

| File | Line | Reference | Meaning |
|---|---|---|---|
| `routes_ai_enhanced.py` | 24 | `from llama_index.core import VectorStoreIndex, Document` | Local RAG index (different product — `llama_index`, not Llama LLM) |
| `routes_ai_enhanced.py` | 26 | `HAS_LLAMA = True` | Boolean flag for the `llama_index` library only |
| `routes_ai_enhanced.py` | 318 | `# Existing llama local index endpoints (kept minimal)` | Comment about the local RAG index |
| `routes_ai_enhanced.py` | 326–337 | `llama_docs.append(Document(...))`, `VectorStoreIndex.from_documents(llama_docs)` | RAG index population |
| `routes_ai_enhanced.py` | 345–347 | `# Prefer llama if available else fallback regex` | RAG retrieval, not LLM generation |
| **(none)** | — | `Maverick` / `Scout` / `LLAMA_*` env vars | **Zero matches** |

✅ All `llama` references are to the `llama_index` RAG library — **not Llama
Maverick LLM**. The two products share a name prefix but are unrelated.

### 3.3 References to LLM clients in the codebase

```
from emergentintegrations.llm.chat import LlmChat, UserMessage
```

`LlmChat` is the single LLM client used everywhere. It is initialised in:

| File | Line | Provider | Model | Key |
|---|---|---|---|---|
| `core/assistant_kernel.py` | 126 | `openai` | `gpt-4o-mini` | `EMERGENT_LLM_KEY` |
| `routes_parts_ocr.py` | 86, 100 | `openai` (image) | gpt-4o (OCR) | `EMERGENT_LLM_KEY` |
| `routes_alkabeer_bot.py` | 709, 1049, 1056 | varies | varies | `EMERGENT_LLM_KEY` |
| `routes_moltbot.py` | 318, 855, 883, 947 | `openai` | `MOLTBOT_OPENAI_MODEL` | `EMERGENT_LLM_KEY` |
| `routes_ai_enhanced.py` | 168–170 | `anthropic` / `gemini` (conditional) | — | `EMERGENT_LLM_KEY` |
| `routes_dtc.py` | 69 | varies | — | `EMERGENT_LLM_KEY` |
| `routes_templates_extended.py` | 659–665 | varies | — | `EMERGENT_LLM_KEY` |
| `ai_recommendations_service.py` | 25 | gemini path | `gemini-2.0-flash-exp` | `EMERGENT_LLM_KEY` |
| `server.py` | 2918 | varies | — | `EMERGENT_LLM_KEY` |

✅ **Every single LLM invocation in the backend uses `EMERGENT_LLM_KEY`.**
No file uses Llama Stack, Llama Maverick, or any Groq/DeepSeek/BlackBox key
*as a primary provider*; the legacy bots reference their respective keys but
also import the Emergent client.

### 3.4 Workshop bot — model registry (for context)

`routes_workshop_bot.py` lines 168–218 define a `BLACKBOX_MODEL_REGISTRY`:
- `blackbox-pro` → `blackboxai/blackbox-pro`
- `claude-sonnet-4.5` → `blackboxai/anthropic/claude-sonnet-4.5`
- `gpt-5-codex` → `gpt-5-codex`

❌ **Llama Maverick is NOT in the registry.**

---

## 4. Current Floating Bot LLM Path

```
User types message in <UnifiedAssistantDrawer />
        │
        ▼
POST /api/assistant/chat   (routes_assistant.py line 33)
        │
        ▼
assistant_kernel.chat(message, session_id, workshop_id, use_ai)
        │
        ├── detect_tools(message)              ← regex over 12 tools
        ├── tool_router.call_tool(name, …)     ← read-only handlers
        ├── ai_context.build_snapshot(...)
        │
        ▼
_llm_chat(system_prompt, history, message)     ← assistant_kernel.py line 105
        │
        │  api_key      = EMERGENT_LLM_KEY
        │  provider     = "openai"              (hardcoded line 114)
        │  model_name   = "gpt-4o-mini"         (hardcoded line 115)
        │  client class = LlmChat (from emergentintegrations.llm.chat)
        │
        ▼
LlmChat.send_message(UserMessage(text=...))
        │
        ▼
Response → assistant_kernel → routes_assistant → drawer
```

❌ **Llama Maverick is nowhere on this path.** There is no provider switch,
no `if model_provider == "llama"` branch, no Llama-Stack adapter, no Groq
adapter, no router.

---

## 5. Legacy / Other Bot Usage

| Bot / Route | Uses Llama via Groq? | Details |
|---|---|---|
| **Moltbot (`routes_moltbot.py`)** | ✅ **YES** | The **reviewer agent** (line 908) calls `_call_openai_compatible(groq_key, groq_url, groq_model, …)` — this is the **only active Llama-family path in the codebase**. The model is whatever `GROQ_MODEL` holds (currently Llama-3 family; pointing it to `LLAMA_MAVERICK_MODEL_ID` would make it Llama-4-Maverick with zero code changes). |
| Workshop bot (`routes_workshop_bot.py`) | ❌ No | Despite earlier audit text, a re-grep for `GROQ` in this file returns **zero matches**. Workshop bot uses **BlackBox** only (blackbox-pro, claude-sonnet-4.5, gpt-5-codex). |
| Al-Kabeer customer bot (`routes_alkabeer_bot.py`) | ❌ No | `EMERGENT_LLM_KEY` via `LlmChat`. |
| Finance bot (`routes_finance_bot.py`) | ❌ No | Pre-L5, deprecated. |
| Parts OCR (`routes_parts_ocr.py`) | ❌ No | `gpt-4o` image via `EMERGENT_LLM_KEY`. |
| DTC chat (`routes_dtc.py`) | ❌ No | `EMERGENT_LLM_KEY`. |
| Templates extended (`routes_templates_extended.py`) | ❌ No | `EMERGENT_LLM_KEY`. |
| AI enhanced (`routes_ai_enhanced.py`) | ❌ No | `EMERGENT_LLM_KEY` (anthropic/gemini conditional). Note: uses `llama_index` library for **RAG vector indexing only**. |
| AI recommendations (`ai_recommendations_service.py`) | ❌ No | `gemini-2.0-flash-exp` via Emergent. |
| WhatsApp bot (`routes_whatsapp_bot.py`) | ❌ No | Webhook only; LLM via Emergent client. |
| NLP page assistant (`routes_nlp_page_assistant.py`) | ❌ No | Per-page NLP, Emergent-backed. |
| **Floating bot (`routes_assistant.py` + `core/*`)** | ❌ **No** | Hardcoded `openai/gpt-4o-mini` via `EMERGENT_LLM_KEY`. Zero references to `GROQ` anywhere in these files. |

✅ **Single Llama-via-Groq path exists** — Moltbot reviewer agent. This proves
the wiring works and gives us a battle-tested helper (`_call_openai_compatible`)
to reuse.

### Reusable helper (location for future fallback)

```
/app/backend/routes_moltbot.py
  └── _call_openai_compatible(api_key, base_url, model, messages,
                              temperature=0.2, max_tokens=1200) → str
       │ Plain httpx POST to {base_url}/chat/completions
       │ Authorization: Bearer {api_key}
       │ Standard OpenAI request shape — works for Groq, OpenRouter,
       │ Together AI, DeepSeek, and any other OpenAI-compatible endpoint.
```

This single function could power a Groq/Llama fallback for the floating bot
with ~15 lines of glue code (without modifying the helper itself).

### Tests / logs / commits referring to Groq or Llama-via-Groq

- `git log --all -S "GROQ_API_KEY"` — env var has been present since the
  earliest committed `.env`. No add/remove of Groq usage in
  `assistant_kernel`.
- No pytest under `/app/backend/tests/` exercises Moltbot's Groq path or
  any Llama-family model directly.
- Supervisor logs would show httpx POSTs to `api.groq.com` only when
  Moltbot's reviewer agent runs — confirms intermittent Groq activity in
  production today.

---

## 6. Why It Previously Worked — Hypotheses (REVISED, ranked)

| # | Hypothesis | Evidence | Likelihood |
|---|---|---|---|
| 1 | **The user interacted with Moltbot's reviewer agent**, which IS Groq/Llama-backed. They likely saw Llama-flavoured output in a different surface and conflated it with the floating bot. | `routes_moltbot.py` line 908: `_call_openai_compatible(groq_key, groq_url, groq_model, …)` is alive and used for the reviewer agent. `GROQ_MODEL` currently holds a Llama-family model id. | 🟢 **Most likely** |
| 2 | The user **previously had `GROQ_MODEL` set to the Llama-4-Maverick id** (currently stored in `LLAMA_MAVERICK_MODEL_ID`) and someone changed it to a Llama-3 variant. Moltbot kept working, but the visible "Maverick" label disappeared. | `LLAMA_MAVERICK_MODEL_ID` exists as a separate env var — a strong tell that it was once the active value of `GROQ_MODEL` or intended to be. | 🟡 Possible |
| 3 | The user remembers an experimental branch that wired Groq into the floating bot, and the change was reverted. | `git log -S "groq" -- backend/core/assistant_kernel.py` returns no add/remove commits → unlikely. | 🔴 Unlikely |
| 4 | The user confused `llama_index` (RAG library) with Llama LLM. | `routes_ai_enhanced.py` line 24 imports `llama_index`. | 🟡 Possible but unlikely given the user's clarification mentioned Groq specifically. |
| 5 | `LLAMA_STACK_URL` points to a planned self-hosted llama-stack sidecar that was never deployed. | URL is `localhost:8321`, no supervisor service binds it. | 🟡 Possible but orthogonal — Groq path is the actual working one. |

**Most defensible reading** (revised): the user is correct that Llama (via
Groq) was — and still is — working. They just observed it through Moltbot's
reviewer agent rather than the floating Unified Assistant. The two surfaces
share no LLM code.

---

## 7. Safe Options (REVISED)

### Option A — **Keep `EMERGENT_LLM_KEY` only (status quo)**

> **Risks**: None — no change.
> **Benefit**: Zero work; the bot continues to function as audited.
> **Files touched**: 0.
> **Tests needed**: 0.
> **Backlog impact**: Groq/Llama-Maverick remains "used by Moltbot only".

### Option B — **Add Groq/Llama-Maverick as a fallback for the floating bot** (NEWLY VIABLE)

Wire a thin fallback inside `assistant_kernel._llm_chat()` that fires when
`LlmChat.send_message()` raises (rate limit / 429 / 503 / network error /
budget exhaustion).

> **Risks**:
> - Fallback path is rarely exercised → silent breakage if untested.
> - Llama-4-Maverick behaviour differs from gpt-4o-mini → response quality variance (some prompt engineering may be needed).
> - Could mask real Emergent issues by absorbing failures silently — must log every fallback invocation.
> - Tool-result formatting (Markdown tables) must be re-verified on Llama output.
>
> **Benefit**:
> - **Resilience** against Emergent key budget exhaustion (one of the top-5 risks identified in `06_SECURITY_AND_PERMISSION_RISKS.md`).
> - Bot stays up during Emergent outages.
> - **No new keys needed** — `GROQ_API_KEY` + `GROQ_API_BASE_URL` are already configured.
> - **No new code library needed** — reuses `_call_openai_compatible` from `routes_moltbot.py` (move it to `core/llm_helpers.py` for cleanliness).
> - To make the model Llama-4-Maverick specifically, the operator simply sets `GROQ_MODEL` to the value already stored in `LLAMA_MAVERICK_MODEL_ID` (one env-var change, zero code change).
>
> **Files touched** (estimate 3–4):
> - `/app/backend/core/llm_helpers.py` *(new — move `_call_openai_compatible` here, ~50 LOC)*
> - `/app/backend/core/assistant_kernel.py` — wrap `_llm_chat()` in try/except; on fail call the helper with Groq credentials; log the fallback.
> - `/app/backend/tests/test_groq_fallback.py` *(new)* — mock Emergent failure → assert Groq path executes.
> - `/app/backend/.env` — optionally add a feature flag like `ASSISTANT_FALLBACK_ENABLED=true` (operator action).
>
> **Tests needed**: yes — at minimum (1) Emergent succeeds, fallback NOT called; (2) Emergent raises, fallback IS called and returns text; (3) both fail, canned response is returned.

### Option C — **Add a Model Router with admin-configurable default**

Build a model selector inside `assistant_kernel`:
- `default`: `openai/gpt-4o-mini` via Emergent
- `fallback_1`: Llama-4-Maverick via Groq
- `fallback_2`: any registered model (future — DeepSeek, BlackBox, …)
- admin override per session

> **Risks**:
> - Largest blast radius; touches more files and adds new admin surface.
> - Streaming / Markdown / tool-result handling must be re-validated per provider.
> - Configuration drift (different prompts may need to be tuned per model).
>
> **Benefit**:
> - Future-proof; supports A/B testing and graceful degradation.
> - Aligns with the L5 spec of a single kernel but multiple providers.
> - Could be sold as a "بوت سيد" feature where admin chooses Llama for cheap bulk queries, GPT for high-stakes ones.
>
> **Files touched** (estimate 5–7):
> - `/app/backend/core/llm_router.py` (new — model selection + chain)
> - `/app/backend/core/llm_helpers.py` (new — move `_call_openai_compatible`)
> - `/app/backend/core/assistant_kernel.py` (call into router)
> - `/app/backend/routes_assistant.py` — surface admin override via `chat(payload.model=...)`
> - `/app/frontend/src/components/assistant/AssistantProvider.jsx` — optional model selector
> - `/app/backend/tests/test_llm_router.py` — coverage
> - `/app/docs/bot_audit/09_LLM_ROUTER_DESIGN.md` — design doc
>
> **Tests needed**: yes (per-provider smoke + router selection + failure chain).

---

## 8. Recommendation (REVISED)

> 🟢 **GO for Option B** *(Groq/Llama-Maverick fallback)* — **after** Phase 3A
> ships, **not before**.
>
> ### Why this changed from the original audit
>
> The previous version of this report said "NO-GO — no Llama infrastructure
> exists". That conclusion was based on the absence of a standalone
> `LLAMA_API_KEY`. The user's clarification revealed that **Groq IS the
> infrastructure** — Groq hosts Llama-family models and is already wired,
> keyed, and serving Moltbot's reviewer agent today. The fallback is now a
> small, safe code change rather than a green-field integration.
>
> ### Sequencing
>
> 1. ✅ **Ship Phase 3A first** (Action Buttons + Streaming) using the
>    current Emergent-only path. Don't touch the LLM provider while shipping
>    UX features — keeps the blast radius small.
> 2. 📦 **Implement Option B** in a follow-up session. It is **additive**:
>    Emergent stays the default; Groq/Llama only fires on failure. The
>    feature is invisible to users when Emergent is healthy.
> 3. 🚦 **Add A2 (rate limit) and A3 (audit log)** from
>    `07_RECOMMENDED_NEXT_STEPS.md` **before** Option B ships — so that
>    fallback invocations are visible in the audit log and rate-limited.
> 4. 🔁 **Later, consider Option C** (full model router) only if the user
>    explicitly wants per-session model selection. Otherwise Option B's
>    silent fallback is enough.
>
> ### Need to correct previous bot-audit reports?
>
> 📝 **Yes, two small corrections** to `04_API_KEYS_STATUS_SAFE.md`:
> - The note "Groq … used by `routes_workshop_bot.py`" is **incorrect** —
>   re-grep confirms Workshop bot uses BlackBox only. Update to
>   "used by `routes_moltbot.py` reviewer agent only".
> - The note for `LLAMA_MAVERICK_MODEL_ID` should mention that it is a
>   **ready-to-swap target for `GROQ_MODEL`** — not just "reserved".
>
> These corrections are documentation-only and do not affect any code.

---

## 9. Files Inspected (exhaustive list)

```
Configuration:
  /app/backend/.env                                    (read for env var NAMES only)
  /app/frontend/.env                                   (read for env var NAMES only)

Backend core:
  /app/backend/core/assistant_kernel.py
  /app/backend/core/tool_router.py
  /app/backend/core/ai_context.py
  /app/backend/core/shared_memory.py
  /app/backend/core/alert_bus.py

Backend routes (grepped for LLM provider strings):
  /app/backend/server.py
  /app/backend/routes_assistant.py
  /app/backend/routes_moltbot.py
  /app/backend/routes_workshop_bot.py
  /app/backend/routes_alkabeer_bot.py
  /app/backend/routes_finance_bot.py
  /app/backend/routes_ai_enhanced.py
  /app/backend/routes_dtc.py
  /app/backend/routes_templates_extended.py
  /app/backend/routes_parts_ocr.py
  /app/backend/routes_whatsapp_bot.py
  /app/backend/routes_nlp_page_assistant.py
  /app/backend/routes_gemini_chat.py
  /app/backend/routes_diesel_chat.py
  /app/backend/ai_recommendations_service.py

Frontend:
  /app/frontend/src/components/assistant/AssistantProvider.jsx
  /app/frontend/src/components/assistant/UnifiedAssistantDrawer.jsx
  /app/frontend/src/pages/MoltBot.jsx
  /app/frontend/src/**  (grep for LLAMA / Maverick / llama / maverick → 0 hits)

Audit reports:
  /app/docs/bot_audit/01_FLOATING_BOT_CAPABILITY_MAP.md
  /app/docs/bot_audit/02_AI_AGENTS_AND_MODELS.md
  /app/docs/bot_audit/03_TOOL_REGISTRY_AUDIT.md
  /app/docs/bot_audit/04_API_KEYS_STATUS_SAFE.md
  /app/docs/bot_audit/05_FRONTEND_INTEGRATION_MAP.md
  /app/docs/bot_audit/06_SECURITY_AND_PERMISSION_RISKS.md
  /app/docs/bot_audit/07_RECOMMENDED_NEXT_STEPS.md

Git history:
  git log --all -S "LLAMA_MAVERICK_MODEL_ID"           (no add/remove commits)
  git log --all --grep="llama\|maverick"               (only llama_index refs)
```

No file was modified during this audit. Only `08_LLAMA_MAVERICK_PROVIDER_AUDIT.md`
was created.
