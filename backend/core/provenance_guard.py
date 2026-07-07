"""🔐 L14-D5 — حارس تطابق بلوك النتائج (أمر علاج L14 بند 1).

أي سطر في رد المساعد يدّعي مخرجات أداة بصيغة `tool.name: {...}` يجب أن يقابله
استدعاء مسجَّل فعلاً في نفس الدورة — وإلا يُحجَب السطر ويُسجَّل خرق provenance.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

_CLAIM_RE = re.compile(r"[•\-\*]?\s*`?([a-z_]+\.[a-z_]+)`?\s*:\s*\{")


def enforce(response_text: str, tool_results: List[Dict[str, Any]]) -> Tuple[str, List[Dict[str, str]]]:
    if not response_text:
        return response_text, []
    executed = {t.get("tool") for t in (tool_results or []) if t.get("tool")}
    violations: List[Dict[str, str]] = []
    out: List[str] = []
    for line in response_text.split("\n"):
        m = _CLAIM_RE.search(line)
        if m and m.group(1) not in executed:
            violations.append({"claimed_tool": m.group(1), "blocked_line": line[:200]})
            out.append(
                f"⚠️ [حُجب بلوك نتائج غير موثّق — الأداة `{m.group(1)}` لم تُنفَّذ في هذه الدورة؛ "
                f"خرق provenance مُسجَّل في الـtrace]"
            )
        else:
            out.append(line)
    return "\n".join(out), violations
