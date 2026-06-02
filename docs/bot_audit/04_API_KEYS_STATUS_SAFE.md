# 04 — API Keys & Env Vars Status (Safe)

⚠️ **No secret values are exposed in this report.** Status is one of:
`configured` / `missing` / `empty` / `unused` / `unknown`.

## Backend env vars (`/app/backend/.env`)

| Key / Env Name | Type | Status | Used By | Purpose | Secret Exposed? |
|---|---|---|---|---|---|
| `EMERGENT_LLM_KEY` | LLM (universal) | **configured** | `assistant_kernel._emergent_llm_key()` → `LlmChat(api_key=...)` | Primary key for the floating bot's LLM calls (gpt-4o-mini) | **No** |
| `OPENAI_API_KEY` | LLM | **missing** | `server.py::financial_analysis()` (separate endpoint, not floating bot) | Optional fallback for `/api/ai/financial-analysis` (not used by Unified Assistant) | **No** |
| `ANTHROPIC_API_KEY` | LLM | **empty** | none active | Reserved; not consumed by floating bot | **No** |
| `DEEPSEEK_API_KEY` | LLM | **configured** | `routes_moltbot.py` (editor only) | Used by Moltbot editor, **not** by floating bot | **No** |
| `DEEPSEEK_API_BASE_URL` | LLM endpoint | **configured** | `routes_moltbot.py` | same as above | **No** |
| `DEEPSEEK_MODEL` | model id | **configured** | `routes_moltbot.py` | same as above | **No** |
| `GROQ_API_KEY` | LLM | **configured** | `routes_moltbot.py` (reviewer agent only) | Used by Moltbot via OpenAI-compatible HTTP; **not** by floating bot | **No** |
| `GROQ_API_BASE_URL` | LLM endpoint | **configured** | `routes_moltbot.py` | same as above | **No** |
| `GROQ_MODEL` | model id | **configured** (Llama-family model id) | `routes_moltbot.py` | same as above. Swap to `LLAMA_MAVERICK_MODEL_ID` value to activate Llama-4-Maverick. | **No** |
| `BLACKBOX_API_KEY` | LLM | **configured** | `routes_moltbot.py` (code analysis) | Code editor only, **not** floating bot | **No** |
| `BLACKBOX_API_URL` | LLM endpoint | **configured** | `routes_moltbot.py` | same | **No** |
| `BLACKBOX_REPO_URL` | git | **configured** | `routes_moltbot.py` | code editor repository pointer | **No** |
| `BLACKBOX_BRANCH` | git | **configured** | `routes_moltbot.py` | same | **No** |
| `MOLTBOT_OPENAI_MODEL` | model id | **configured** | `routes_moltbot.py` | code editor model | **No** |
| `MOLTBOT_PROJECT_ROOT` | path | **configured** | `routes_moltbot.py` | code editor workspace | **No** |
| `LLAMA_STACK_URL` | LLM endpoint | **configured** | not currently consumed by Unified Assistant | reserved | **No** |
| `LLAMA_SCOUT_MODEL_ID` | model id | **configured** | not consumed by Unified Assistant | reserved — ready-to-swap target for `GROQ_MODEL` (Llama-4-Scout) | **No** |
| `LLAMA_MAVERICK_MODEL_ID` | model id | **configured** | not consumed by Unified Assistant | **ready-to-swap target for `GROQ_MODEL`** (Llama-4-Maverick). See `08_LLAMA_MAVERICK_PROVIDER_AUDIT.md` §1. | **No** |
| `SUPABASE_URL` | DB | **configured** | `supabase_service.SupabaseService.__init__` | Primary DB for all read-only tools | **No** |
| `SUPABASE_SERVICE_ROLE_KEY` | DB | **configured** | `supabase_service.SupabaseService` | Service-role write/read auth (used by tool handlers indirectly via /api/* internal calls) | **No** |
| `DB_PROVIDER` | flag | **configured** (value=`supabase`) | every domain repository | Selects supabase / memory / mongo | **No** |
| `MONGO_URL` | DB | **configured** | `server.py::AsyncIOMotorClient` | Fallback DB | **No** |
| `DB_NAME` | DB | **configured** | `server.py` | Mongo DB name | **No** |
| `DEFAULT_WORKSHOP_ID` | tenant | **configured** | various route files | Default workshop scope | **No** |
| `CORS_ORIGINS` | security | **configured** | `server.py::CORSMiddleware` | Allowed origins | **No** |
| `JWT_SECRET` | security | **configured** | `routes_users.py` / `routes_auth.py` | Token signing for login | **No** |

### External integration env vars (NOT used by floating bot)

| Key | Status | Used By | Touches floating bot? |
|---|---|---|---|
| WhatsApp / Twilio / SMS keys | **unknown** (none found in `/app/backend/.env`) | n/a | **No** |
| Email / SendGrid / Resend | **unknown** | n/a | **No** |
| Stripe / payment | **unknown** | n/a | **No** |
| Maps / Geocoding | **unknown** | n/a | **No** |
| Object storage (S3 / GCS) | **unknown** | n/a | **No** |

## Frontend env vars (`/app/frontend/.env`)

| Key | Status | Used By | Purpose | Secret Exposed? |
|---|---|---|---|---|
| `REACT_APP_BACKEND_URL` | **configured** | `AssistantProvider.jsx::API_URL` | Base URL for all `/api/assistant/*` axios calls | **No** |
| `REACT_APP_WORKSHOP_ID` | **configured** | `AssistantProvider.jsx::WORKSHOP_ID` | Passed in `chat` payload as `workshop_id` | **No** |
| `DISABLE_ESLINT_PLUGIN` | **configured** | build config | dev DX | **No** |
| `HOST` | **configured** | webpack dev server | host binding | **No** |
| `DANGEROUSLY_DISABLE_HOST_CHECK` | **configured** | webpack dev server | preview host bypass | **No** |

## Critical observations

1. ✅ **`EMERGENT_LLM_KEY` is the only LLM key the floating bot uses.** All
   other LLM keys (Groq/DeepSeek/Blackbox/Llama/OpenAI/Anthropic) are wired to
   *other* route files and have no codepath into `assistant_kernel`.

2. ⚠️ **`ANTHROPIC_API_KEY` is empty.** If any future code branch reaches for
   Claude, it must fall back to the Emergent key or fail gracefully.

3. ⚠️ **`OPENAI_API_KEY` is missing.** The standalone
   `/api/ai/financial-analysis` endpoint in `server.py` will return a
   **mock** analysis (by design, line ~3090) when this is absent. This is
   **separate** from the floating bot and does not affect it.

4. 🔐 **No secret values are printed anywhere in this audit.**

5. ✅ **Frontend uses no secret keys.** Only public URLs and feature flags.
