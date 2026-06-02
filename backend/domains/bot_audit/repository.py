"""BotAuditRepository — DB-agnostic writer for `bot_audit_log`.

Strategy: try Supabase; if the table is missing or the client is in mock mode,
fall back to an in-process ring buffer so the bot stays alive while the
operator runs the migration.
"""
from __future__ import annotations

import os
from collections import deque
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional

from core.log_utils import get_logger

_log = get_logger("bot_audit.repo")

# Bounded in-memory fallback (last 500 rows). Lost on restart by design.
_MEMORY_BUFFER: Deque[Dict[str, Any]] = deque(maxlen=500)
_TABLE_MISSING_WARNED: bool = False


def _provider() -> str:
    return os.environ.get("DB_PROVIDER", "supabase").lower()


class BotAuditRepository:
    """Single-table repository for bot_audit_log."""

    TABLE = "bot_audit_log"

    async def insert(self, row: Dict[str, Any]) -> bool:
        """Persist one audit row. Returns True if it landed in Supabase."""
        # Always defensively copy + timestamp normalise
        prepared = dict(row)
        ts = prepared.get("ts") or datetime.now(timezone.utc)
        if isinstance(ts, datetime):
            ts = ts.isoformat()
        prepared["ts"] = ts

        if _provider() != "supabase":
            _MEMORY_BUFFER.append(prepared)
            return False

        try:
            from server import supabase_service
            if not supabase_service.client or supabase_service.mock_mode:
                _MEMORY_BUFFER.append(prepared)
                return False
            supabase_service.client.table(self.TABLE).insert(prepared).execute()
            return True
        except Exception as e:
            # Most likely the table doesn't exist yet — keep going but warn once.
            global _TABLE_MISSING_WARNED
            if not _TABLE_MISSING_WARNED:
                _log.warning(
                    "bot_audit_log insert failed (table may not exist yet); "
                    "using in-memory buffer. error=%s",
                    str(e)[:200],
                )
                _TABLE_MISSING_WARNED = True
            _MEMORY_BUFFER.append(prepared)
            return False

    async def recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return latest audit rows (Supabase if available, else memory)."""
        if _provider() == "supabase":
            try:
                from server import supabase_service
                if supabase_service.client and not supabase_service.mock_mode:
                    res = (
                        supabase_service.client
                        .table(self.TABLE)
                        .select("*")
                        .order("ts", desc=True)
                        .limit(min(limit, 200))
                        .execute()
                    )
                    return res.data or []
            except Exception:
                pass
        return list(_MEMORY_BUFFER)[-limit:][::-1]

    def memory_buffer_size(self) -> int:
        """Diagnostic: how many rows are in the in-memory fallback."""
        return len(_MEMORY_BUFFER)
