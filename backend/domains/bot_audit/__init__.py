"""bot_audit domain — persistent audit log for the floating assistant.

Records ONE row per `/api/assistant/chat` request. Stores metadata only
(no raw user content). Used for:
  • compliance / "who asked what & when?"
  • visibility into fallback usage (when Groq fallback ships in Phase 3B)
  • LLM budget monitoring (token counts)

Schema (Supabase table `bot_audit_log`):
  • id          uuid primary key (default gen_random_uuid())
  • ts          timestamptz not null default now()
  • session_id  text
  • user_id     text          (nullable until 3C wires user identity)
  • intent      text          (search / report / explain / question / …)
  • tools_called text[]       (e.g. ['customers.search', 'inventory.low_stock'])
  • ai_used     boolean
  • fallback_used boolean default false
  • tokens_in   int           (nullable)
  • tokens_out  int           (nullable)
  • request_hash text         (sha256[:16] of user message — for dedup)
  • client_ip   text          (nullable; populated by the route handler)
"""
from .repository import BotAuditRepository  # noqa: F401
from .service import BotAuditService, audit_service  # noqa: F401
