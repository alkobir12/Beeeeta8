# 08 — Llama Maverick Provider Audit

**Audit date**: 2026-02-12
**Scope**: Determine whether Llama Maverick is (or was) wired to the floating
Unified Assistant, and assess the safety of adding it as a fallback.
**Method**: Static code scan + env-var presence check + git history check.
**Secret exposure policy**: ✅ Zero values printed.

---

## 1. Executive Summary

| Question | Answer |
|---|---|
| Is a real Llama Maverick **API key** present in env? | ❌ **No.** Neither `LLAMA_API_KEY` nor `LLAMA_MAVERICK_API_KEY` exists in `/app/backend/.env`. |
| What IS present? | Three orphan env vars only: `LLAMA_STACK_URL`, `LLAMA_SCOUT_MODEL_ID`, `LLAMA_MAVERICK_MODEL_ID`. All hold configuration values (URL + model identifiers) — **no auth secret**. |
| Does the floating bot currently use Llama Maverick? | ❌ **No.** Hardcoded path is `openai/gpt-4o-mini` via `EMERGENT_LLM_KEY`. |
| Was there ever a code path that called Llama Maverick? | ❌ **No evidence.** A repository-wide grep for `LLAMA_STACK_URL`, `LLAMA_SCOUT_MODEL_ID`, `LLAMA_MAVERICK_MODEL_ID` returned **zero references** in any `.py`, `.js`, `.jsx`, `.ts`, or `.tsx` file. |
| Are the values used by any other bot (Moltbot, Workshop, legacy)? | ❌ **No.** Moltbot uses `MOLTBOT_OPENAI_MODEL` + `GROQ_MODEL` (OpenAI/Groq). Workshop bot uses BlackBox models (`blackboxai/*`, `gpt-5-codex`, `claude-sonnet-4.5`). Neither references the LLAMA_* env vars. |
| Why might the user remember Llama Maverick "working before"? | Most likely the env vars were **provisioned in advance** for a self-hosted Llama Stack integration that was never wired up. The `LLAMA_STACK_URL` value points to a **localhost** endpoint — suggesting an earlier plan to run llama-stack as a sidecar service that did not ship. |
| Is there a clear reason it stopped working? | It never started working — there is no codepath. The "Llama" strings present in the codebase refer to the unrelated **`llama_index`** Python library (used as a RAG vector index in `routes_ai_enhanced.py`), not to a Llama LLM. |
| Can it be made a safe fallback right now? | Only with **new code** to wire a Llama provider. The current registry has no Llama adapter. See §7 for safe options. |

---

## 2. Env Vars Status

⚠️ Status only. No values printed.

| Env Name | Provider class | Status | Used By | Secret Exposed? |
|---|---|---|---|---|
| `LLAMA_STACK_URL` | Llama Stack (self-hosted) | **configured** | **unused** — no code reads it | No |
| `LLAMA_SCOUT_MODEL_ID` | Llama Scout (model id) | **configured** | **unused** | No |
| `LLAMA_MAVERICK_MODEL_ID` | Llama Maverick (model id) | **configured** | **unused** | No |
| `LLAMA_API_KEY` | Llama (auth) | **missing** | n/a | No |
| `LLAMA_MAVERICK_API_KEY` | Llama Maverick (auth) | **missing** | n/a | No |
| `GROQ_API_KEY` | Groq | **configured** | **used_by_legacy** (`routes_workshop_bot.py`, Moltbot Groq path) | No |
| `GROQ_API_BASE_URL` | Groq | **configured** | **used_by_legacy** | No |
| `GROQ_MODEL` | Groq | **configured** | **used_by_legacy** | No |
| `OPENROUTER_API_KEY` | OpenRouter | **missing** | n/a | No |
| `TOGETHER_API_KEY` | Together AI | **missing** | n/a | No |
| `DEEPSEEK_API_KEY` | DeepSeek | **configured** | **used_by_legacy** (Moltbot only) | No |
| `BLACKBOX_API_KEY` | BlackBox AI | **configured** | **used_by_legacy** (Moltbot + Workshop bot) | No |
| `EMERGENT_LLM_KEY` | Emergent Universal Key | **configured** | **used_by_floating_bot** (sole provider for `assistant_kernel`) | No |
| `OPENAI_API_KEY` | OpenAI (direct) | **missing** | `server.py::financial_analysis` returns mock when absent | No |
| `ANTHROPIC_API_KEY` | Anthropic | **empty** | not consumed by floating bot | No |
| `MOLTBOT_OPENAI_MODEL` | OpenAI (model id) | **configured** | **used_by_legacy** (Moltbot) | No |

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

| Bot / Route | Uses Llama Maverick? | What it actually uses |
|---|---|---|
| Moltbot (`routes_moltbot.py`) | ❌ No | OpenAI (`MOLTBOT_OPENAI_MODEL`), Groq (`GROQ_MODEL`) — both via Emergent client. |
| Workshop bot (`routes_workshop_bot.py`) | ❌ No | BlackBox registry only (blackbox-pro, claude-sonnet-4.5, gpt-5-codex). |
| Al-Kabeer customer bot (`routes_alkabeer_bot.py`) | ❌ No | `EMERGENT_LLM_KEY` via `LlmChat`. |
| Finance bot (`routes_finance_bot.py`) | ❌ No | Pre-L5, deprecated. |
| Parts OCR (`routes_parts_ocr.py`) | ❌ No | `gpt-4o` image via `EMERGENT_LLM_KEY`. |
| DTC chat (`routes_dtc.py`) | ❌ No | `EMERGENT_LLM_KEY`. |
| Templates extended (`routes_templates_extended.py`) | ❌ No | `EMERGENT_LLM_KEY`. |
| AI enhanced (`routes_ai_enhanced.py`) | ❌ No | `EMERGENT_LLM_KEY` (anthropic/gemini conditional). Note: uses `llama_index` library for **RAG vector indexing only**. |
| AI recommendations (`ai_recommendations_service.py`) | ❌ No | `gemini-2.0-flash-exp` via Emergent. |
| WhatsApp bot (`routes_whatsapp_bot.py`) | ❌ No | Webhook only; LLM via Emergent client. |
| NLP page assistant (`routes_nlp_page_assistant.py`) | ❌ No | Per-page NLP, Emergent-backed. |

✅ **No file in the project calls a Llama Maverick endpoint.** Nothing exists
to break, nothing exists to restore.

### Tests / logs / commits referring to Llama Maverick

- `git log --all --pickaxe-regex -S "LLAMA_MAVERICK_MODEL_ID"` — **no commits** (the env var was present in the earliest committed `.env`).
- `git log --all --grep="llama\|maverick"` — only matches commits referencing `llama_index` (RAG) refactors.
- No pytest file under `/app/backend/tests/` mentions Llama, Maverick, Groq, or any non-Emergent provider.
- No `supervisor` log archive contains a `Llama-Stack` startup line (the stack URL is `localhost:8321` — a port that is **not bound** by any service in `/etc/supervisor/conf.d/`).

---

## 6. Why It Previously Worked — Hypotheses (ranked)

| # | Hypothesis | Evidence | Likelihood |
|---|---|---|---|
| 1 | The env vars were **pre-provisioned for a planned Llama Stack sidecar** that was never coded. | `LLAMA_STACK_URL` points to `localhost:8321`; no service binds that port; no code reads the var. | 🟢 **Most likely** |
| 2 | The user remembers a **different bot** (Workshop bot using `blackboxai/anthropic/claude-sonnet-4.5` or Moltbot using Groq) and conflated it with "Llama Maverick". | Moltbot/Workshop bots are visually similar; both have model dropdowns. | 🟡 Possible |
| 3 | An earlier branch / fork wired Llama Maverick but was deleted before the merge. | `git log -S LLAMA_MAVERICK` returned no add/remove commits. | 🔴 Unlikely (no traces) |
| 4 | The `llama_index` RAG library was confused with Llama Maverick LLM. | `routes_ai_enhanced.py` HAS_LLAMA = True. | 🟡 Possible |
| 5 | `EMERGENT_LLM_KEY` was historically rotated and the user remembers the *transition*. | The Emergent key has always been the active path. | 🔴 Unlikely |

**Most defensible reading**: the env vars are dead configuration; Llama
Maverick never actually served traffic in this project.

---

## 7. Safe Options

### Option A — **Keep `EMERGENT_LLM_KEY` only (status quo)**

> **Risks**: None — no change.
> **Benefit**: Zero work; the bot continues to function as audited.
> **Files touched**: 0.
> **Tests needed**: 0.
> **Backlog impact**: Llama remains "configured but unused" forever (or until cleanup).

### Option B — **Make Llama Maverick a fallback if Emergent fails**

Wire a thin Llama provider in `assistant_kernel._llm_chat()` that fires when
`LlmChat.send_message()` raises (rate limit / network error / budget out).

> **Risks**:
> - The local `llama-stack` sidecar (port 8321) is **not running** — would need to be deployed.
> - `LLAMA_API_KEY` is **missing**; would need to be provisioned.
> - Fallback path is rarely exercised → silent breakage if untested.
> - Model behavior differs from gpt-4o-mini → response quality variance.
> - Could mask real Emergent issues by absorbing failures.
>
> **Benefit**:
> - Resilience against Emergent key budget exhaustion (one of the top-5 risks).
> - User can keep using the bot during Emergent outages.
>
> **Files touched** (estimate 3):
> - `/app/backend/core/assistant_kernel.py` — add `_llm_chat_fallback()` + try/except
> - `/app/backend/.env` — provision `LLAMA_API_KEY` (operator action)
> - `/app/backend/tests/test_llama_fallback.py` — new test
>
> **Tests needed**: yes (mock Emergent failure → assert Llama path executes).

### Option C — **Add a Model Router with admin-configurable default**

Build a model selector inside `assistant_kernel`:
- `default`: `openai/gpt-4o-mini` via Emergent
- `fallback`: Llama Maverick via Llama Stack
- `admin override`: any registered model (future)

> **Risks**:
> - Largest blast radius; touches more files and adds new admin surface.
> - Streaming / Markdown / tool-result handling must be re-validated per provider.
> - Configuration drift (different prompts may need to be tuned per model).
>
> **Benefit**:
> - Future-proof; supports A/B testing and graceful degradation.
> - Aligns with the user's "L5 spec" of a single kernel but multiple providers.
>
> **Files touched** (estimate 5–7):
> - `/app/backend/core/assistant_kernel.py`
> - `/app/backend/core/llm_router.py` (new — single-file abstraction)
> - `/app/backend/.env` — multiple keys
> - `/app/backend/routes_assistant.py` — surface admin override via `chat(payload.model=...)`
> - `/app/frontend/src/components/assistant/AssistantProvider.jsx` — optional model selector
> - `/app/backend/tests/test_llm_router.py` — coverage
> - `/app/docs/bot_audit/09_LLM_ROUTER_DESIGN.md` — design doc (optional)
>
> **Tests needed**: yes (per-provider smoke + router selection).

---

## 8. Recommendation

> 🟢 **NO-GO for adding Llama Maverick as a fallback right now** — but for a
> *positive* reason: there is **no Llama infrastructure** in the project to
> fall back to. The env vars are placeholders; no API key, no running
> llama-stack sidecar, no adapter code.
>
> ✅ **GO to continue Phase 3A as planned.** Llama Maverick is not blocking
> any current feature.
>
> 📝 **No correction needed to the previous `04_API_KEYS_STATUS_SAFE.md`** —
> the row for `LLAMA_*` already says **"reserved / not consumed by Unified
> Assistant"**, which is consistent with this deeper audit.
>
> 💡 **Suggested follow-up (optional, after Phase 3A ships)**:
> 1. Remove the three orphan `LLAMA_*` env vars from `/app/backend/.env`
>    *or* clearly comment them as "reserved — not wired", so future agents
>    don't get the same confusion the user reported here.
> 2. If a real Llama fallback is desired, choose **Option B** (the smallest
>    safe surface): provision `LLAMA_API_KEY`, decide on a remote provider
>    (Groq hosts Llama-4 already, so reusing `GROQ_API_KEY` is one viable
>    path), and add a `_llm_chat_fallback()` block guarded by a feature flag.

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
