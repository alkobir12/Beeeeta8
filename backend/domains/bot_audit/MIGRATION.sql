-- 🆕 Phase 3A — bot_audit_log table
--
-- One row per /api/assistant/chat invocation. Metadata only — never stores
-- the raw user message content. The `request_hash` column is a 16-char
-- sha256 prefix usable for deduplication and correlation, but is one-way.
--
-- Run this once in your Supabase SQL editor (or via Supabase CLI).
-- After running, the floating bot will automatically start persisting rows.
-- Until then, rows accumulate in the in-process memory buffer (lost on restart).

CREATE TABLE IF NOT EXISTS bot_audit_log (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ts              timestamptz NOT NULL DEFAULT now(),
    session_id      text,
    user_id         text,            -- nullable until 3C wires user identity
    intent          text,            -- 'search' | 'report' | 'explain' | 'summarize' | 'question' | 'other'
    tools_called    text[] NOT NULL DEFAULT '{}',  -- e.g. ['customers.search','inventory.low_stock']
    ai_used         boolean NOT NULL DEFAULT false,
    fallback_used   boolean NOT NULL DEFAULT false,
    tokens_in       integer,
    tokens_out      integer,
    request_hash    text,            -- sha256(message)[:16], one-way
    client_ip       text             -- populated by the route handler
);

-- Indices for the common queries: "audit rows in the last hour for session X"
CREATE INDEX IF NOT EXISTS idx_bot_audit_log_ts          ON bot_audit_log (ts DESC);
CREATE INDEX IF NOT EXISTS idx_bot_audit_log_session_id  ON bot_audit_log (session_id);
CREATE INDEX IF NOT EXISTS idx_bot_audit_log_user_id     ON bot_audit_log (user_id);
CREATE INDEX IF NOT EXISTS idx_bot_audit_log_intent      ON bot_audit_log (intent);

-- Optional: Row-Level Security policy (admin-only read).
-- Uncomment when an admin role is provisioned in Supabase Auth.
-- ALTER TABLE bot_audit_log ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY bot_audit_admin_read ON bot_audit_log
--     FOR SELECT
--     USING (auth.role() = 'admin');

COMMENT ON TABLE bot_audit_log IS
  'Phase 3A: append-only audit log of floating-bot /chat invocations. Metadata only.';
