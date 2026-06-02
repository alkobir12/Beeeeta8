"""log_utils — structured logging helpers + redaction for the floating assistant.

Centralised so that every `core/*` and `routes_assistant.py` log line goes through
the same pipeline. Replaces ad-hoc `print(...)` calls that risked leaking parts
of user messages into supervisor logs.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any, Optional

# ---------- Logger factory ----------

_LEVEL = os.environ.get("ASSISTANT_LOG_LEVEL", "INFO").upper()

# Configure a module-level handler exactly once — additional getLogger() calls
# inherit this configuration.
_root = logging.getLogger("assistant")
if not _root.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    ))
    _root.addHandler(_handler)
    _root.setLevel(getattr(logging, _LEVEL, logging.INFO))
    _root.propagate = False


def get_logger(name: str) -> logging.Logger:
    """Returns a child logger under the `assistant` namespace."""
    return logging.getLogger(f"assistant.{name}")


# ---------- Redaction ----------

# Patterns we never want to surface in logs. Order matters: longest token first.
_REDACT_PATTERNS = [
    # bearer tokens, API keys, JWTs
    (re.compile(r"(Bearer\s+)[A-Za-z0-9._\-]{12,}", re.IGNORECASE), r"\1<redacted>"),
    (re.compile(r"\beyJ[A-Za-z0-9._\-]{20,}\b"), "<jwt-redacted>"),
    (re.compile(r"\bsk-[A-Za-z0-9]{16,}\b"), "<openai-redacted>"),
    (re.compile(r"\b(gsk|emrgnt|emergent|anthropic)_[A-Za-z0-9_\-]{16,}\b", re.IGNORECASE), "<provider-redacted>"),
    # email addresses inside log payloads — mask local part
    (re.compile(r"\b([A-Za-z0-9_.+\-])[A-Za-z0-9_.+\-]*@([A-Za-z0-9.\-]+\.[A-Za-z]{2,})\b"), r"\1***@\2"),
    # phone numbers (Saudi-style, 9–14 digits) — keep last 4
    (re.compile(r"\b(\+?9665\d{6}|05\d{8}|\+?\d{9,14})\b"), lambda m: f"***{m.group(0)[-4:]}"),
]


def redact(text: Any, *, max_len: int = 240) -> str:
    """Returns a safe-for-log version of `text`:

      • removes obvious secrets (Bearer / sk- / JWT / provider keys),
      • masks email local parts,
      • masks phone numbers (keeping last 4 digits),
      • truncates to `max_len` chars.

    NOT for protecting against an adversarial input — this is a defensive
    sanitiser to avoid accidental leakage in stdout/supervisor logs.
    """
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    cleaned = text
    for pat, repl in _REDACT_PATTERNS:
        cleaned = pat.sub(repl, cleaned)
    if max_len and len(cleaned) > max_len:
        cleaned = cleaned[:max_len] + "…"
    return cleaned


def hash_for_audit(text: Optional[str]) -> str:
    """Stable short hash of a user message for the audit log (no PII).

    Used so the audit row can be correlated to a request without storing the
    raw content. Hash is **non-cryptographic** — purpose is dedup/correlation
    only.
    """
    import hashlib
    if not text:
        return ""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
