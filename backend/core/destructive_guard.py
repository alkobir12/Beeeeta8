"""Fail-closed guard for bulk-destructive endpoints (P0-DESTRUCTIVE-RESET-HARDENING).

Preview and production share one database, so a destructive reset must satisfy
EVERY condition below. Any missing condition denies the request.

  1. authenticated actor
  2. privileged server-side authorization (admin role)
  3. explicit destructive confirmation phrase
  4. independent double-confirmation token
  5. dedicated enable flag (absent => DENIED)
  6. environment / database authorization
  7. audit trail
  8. correlation id

The enable flag intentionally carries no secret and is NOT set in this
environment: with it absent every destructive route is denied.
"""

import logging
import os
import uuid
from typing import Dict, Optional

from fastapi import HTTPException, Request

from core import authz as _authz

logger = logging.getLogger("security.destructive")

ENABLE_FLAG_ENV = "DESTRUCTIVE_RESET_ENABLED"
ALLOWED_DB_ENV = "DESTRUCTIVE_RESET_ALLOWED_DB"
CONFIRM_PHRASE = "DELETE_ALL"
CONFIRM_HEADER = "X-Destructive-Confirm"
PRIVILEGED_ROLES = {"admin"}

_TRUTHY = {"1", "true", "yes", "on"}


def _deny(code: str, action: str, correlation_id: str, message: str, status_code: int = 403) -> HTTPException:
    logger.warning(
        "destructive_denied action=%s reason=%s correlation_id=%s",
        action,
        code,
        correlation_id,
    )
    return HTTPException(
        status_code=status_code,
        detail={"error": code, "action": action, "correlation_id": correlation_id, "message": message},
    )


def correlation_id_of(request: Request) -> str:
    header = request.headers.get("X-Correlation-ID") or request.headers.get("X-Request-ID")
    return (header or "").strip() or f"dc-{uuid.uuid4().hex[:12]}"


def expected_confirmation_token(action: str) -> str:
    """Server-derived second factor — the caller cannot guess it from the first one."""
    return f"{CONFIRM_PHRASE}:{action}:{os.environ.get('DB_NAME') or 'unknown-db'}"


async def require_destructive_authorization(
    request: Request,
    action: str,
    confirm: Optional[str] = None,
) -> Dict[str, str]:
    """Raise unless every destructive precondition is satisfied. Returns audit context."""
    correlation_id = correlation_id_of(request)

    # 5 — dedicated enable flag
    if (os.environ.get(ENABLE_FLAG_ENV) or "").strip().lower() not in _TRUTHY:
        raise _deny(
            "destructive_operations_disabled",
            action,
            correlation_id,
            "العمليات الهدّامة معطّلة على مستوى البيئة.",
        )

    # 6 — environment / database authorization
    allowed_db = (os.environ.get(ALLOWED_DB_ENV) or "").strip()
    current_db = (os.environ.get("DB_NAME") or "").strip()
    if not allowed_db or not current_db or allowed_db != current_db:
        raise _deny(
            "destructive_database_not_authorized",
            action,
            correlation_id,
            "قاعدة البيانات الحالية غير مُصرَّح لها بالعمليات الهدّامة.",
        )

    # 1 + 2 — authenticated, privileged actor resolved server-side
    actor = await _authz.resolve_request_actor(request)
    role = str(getattr(actor, "role", "") or "").strip().lower()
    if role not in PRIVILEGED_ROLES:
        raise _deny(
            "destructive_privilege_required",
            action,
            correlation_id,
            "هذه العملية تتطلب صلاحية مدير نظام.",
        )

    # 3 — explicit destructive confirmation
    supplied_confirm = confirm if confirm is not None else request.query_params.get("confirm")
    if (supplied_confirm or "").strip() != CONFIRM_PHRASE:
        raise _deny(
            "destructive_confirmation_required",
            action,
            correlation_id,
            f"يجب إرسال confirm={CONFIRM_PHRASE}.",
            status_code=428,
        )

    # 4 — independent double confirmation
    if (request.headers.get(CONFIRM_HEADER) or "").strip() != expected_confirmation_token(action):
        raise _deny(
            "destructive_double_confirmation_required",
            action,
            correlation_id,
            f"يجب إرسال ترويسة {CONFIRM_HEADER} بالقيمة الصحيحة.",
            status_code=428,
        )

    # 7 — audit trail of the authorized attempt
    context = {
        "action": action,
        "correlation_id": correlation_id,
        "actor_name": str(getattr(actor, "name", "") or getattr(actor, "id", "") or "unknown"),
        "actor_role": role,
        "database": current_db,
    }
    logger.warning("destructive_authorized %s", context)
    return context


CLI_CONFIRM_ARG = "--i-understand-this-destroys-data"


def require_destructive_cli(action: str, argv: Optional[list] = None) -> None:
    """Fail-closed gate for stand-alone destructive scripts (no HTTP request).

    Refuses unless the dedicated enable flag is on, the database is explicitly
    authorized, AND the operator passes the confirmation argument. Raises
    SystemExit so a script can never proceed by accident.
    """
    import sys

    args = list(argv if argv is not None else sys.argv[1:])

    if (os.environ.get(ENABLE_FLAG_ENV) or "").strip().lower() not in _TRUTHY:
        raise SystemExit(
            f"REFUSED [{action}]: destructive operations are disabled "
            f"({ENABLE_FLAG_ENV} is not set). Nothing was touched."
        )

    allowed_db = (os.environ.get(ALLOWED_DB_ENV) or "").strip()
    current_db = (os.environ.get("DB_NAME") or "").strip()
    if not allowed_db or not current_db or allowed_db != current_db:
        raise SystemExit(
            f"REFUSED [{action}]: current database is not authorized for destructive "
            f"operations ({ALLOWED_DB_ENV} must equal DB_NAME). Nothing was touched."
        )

    if CLI_CONFIRM_ARG not in args:
        raise SystemExit(
            f"REFUSED [{action}]: pass {CLI_CONFIRM_ARG} to confirm. Nothing was touched."
        )

    logger.warning("destructive_cli_authorized action=%s database=%s", action, current_db)
