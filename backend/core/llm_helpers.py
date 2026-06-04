"""llm_helpers — shared LLM call helpers for the floating assistant.

Phase 3B foundation: introduce a clean abstraction so the kernel can choose
between providers (Emergent gpt-4o-mini ↔ local Ollama) without growing
a tangle of conditional logic.
"""
from __future__ import annotations

import os
from typing import List, Optional

import httpx

from core.log_utils import get_logger, redact

_log = get_logger("llm_helpers")

# ---------- Provider registry ----------

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
OLLAMA_DEFAULT_MODEL = os.environ.get("OLLAMA_DEFAULT_MODEL", "llama3.2:3b")
OLLAMA_TIMEOUT = float(os.environ.get("OLLAMA_TIMEOUT", "90"))


async def is_ollama_alive() -> bool:
    """Quick health probe of the local Ollama daemon."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{OLLAMA_HOST}/api/version")
            return r.status_code == 200
    except Exception:
        return False


async def ollama_list_models() -> List[str]:
    """List models pulled locally. Empty list on failure."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{OLLAMA_HOST}/api/tags")
            data = r.json() if r.status_code == 200 else {}
        return [m.get("name") for m in (data.get("models") or []) if m.get("name")]
    except Exception:
        return []


async def call_ollama(
    *,
    system_prompt: str,
    user_message: str,
    history: Optional[List[dict]] = None,
    model: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: int = 800,
) -> str:
    """Run a chat completion against the local Ollama daemon.

    Returns the assistant's text reply, or empty string on failure.
    """
    target_model = model or OLLAMA_DEFAULT_MODEL
    messages = [{"role": "system", "content": system_prompt}]
    if history:
        for m in history[-10:]:
            role = m.get("role") or "user"
            content = m.get("content") or ""
            if role in ("user", "assistant", "system") and content:
                messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_message})

    payload = {
        "model": target_model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
            r = await client.post(f"{OLLAMA_HOST}/api/chat", json=payload)
        if r.status_code != 200:
            _log.warning(
                "ollama responded HTTP %s: %s",
                r.status_code,
                redact(r.text, max_len=120),
            )
            return ""
        data = r.json()
        msg = data.get("message") or {}
        return str(msg.get("content") or "").strip()
    except Exception as e:
        _log.warning("ollama call failed: %s", redact(str(e), max_len=120))
        return ""
