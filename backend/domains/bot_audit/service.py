"""BotAuditService — thin orchestration around BotAuditRepository.

Exposes a singleton `audit_service` so the assistant kernel can call it
without dependency injection plumbing.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.log_utils import get_logger, hash_for_audit

from .repository import BotAuditRepository

_log = get_logger("bot_audit.service")


class BotAuditService:
    def __init__(self, repo: Optional[BotAuditRepository] = None) -> None:
        self.repo = repo or BotAuditRepository()

    async def log_chat(
        self,
        *,
        session_id: Optional[str],
        user_message: Optional[str],
        intent: Optional[str],
        tools_called: List[str],
        ai_used: bool,
        fallback_used: bool = False,
        tokens_in: Optional[int] = None,
        tokens_out: Optional[int] = None,
        user_id: Optional[str] = None,
        client_ip: Optional[str] = None,
    ) -> bool:
        """Records one chat invocation. Returns True iff persisted to Supabase."""
        row: Dict[str, Any] = {
            "session_id": session_id,
            "user_id": user_id,
            "intent": intent or "other",
            "tools_called": list(tools_called or []),
            "ai_used": bool(ai_used),
            "fallback_used": bool(fallback_used),
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "request_hash": hash_for_audit(user_message),
            "client_ip": client_ip,
            "ts": datetime.now(timezone.utc),
        }
        try:
            return await self.repo.insert(row)
        except Exception as e:
            # Never let an audit failure break the chat path.
            _log.warning("audit log failed (non-fatal): %s", str(e)[:200])
            return False

    async def recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        return await self.repo.recent(limit)


# Module-level singleton used by assistant_kernel
audit_service = BotAuditService()
