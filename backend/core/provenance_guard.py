"""🔐 L14-D5 — حارس تطابق بلوك النتائج + حارس الاختلاق (أمر علاج L14 بند 1).

طبقتان:
  1) enforce():          أي سطر يدّعي مخرجات أداة `tool.name: {...}` بلا استدعاء
                         مسجَّل فعلاً في نفس الدورة → يُحجَب السطر.
  2) enforce_entities(): أي مُعرّف منظَّم في الرد (OP-xxxx-xxxx / INVxxxxx / tr-hex /
                         UUID / id قصير hex) غير موجود في أدلة الدورة (أدوات + سياق +
                         رسالة المستخدم + التاريخ) → يُحجَب المعرّف ويُسجَّل خرق provenance.
إثبات القفل: `OP-2025-0187` يُحجَب (tr-5280697b4448).
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

_CLAIM_RE = re.compile(r"[•\-\*]?\s*`?([a-z_]+\.[a-z_]+)`?\s*:\s*\{")

_BLOCKED_MARK = "⚠️[معرّف حُجب — غير موثّق في trace هذه الدورة]"

# معرّفات منظَّمة فقط — المبالغ/الأسماء خارج النطاق (false positives)
# ملاحظة: lookarounds بدل \b لأن الحروف العربية الملتصقة (مثل «وOP-2025») word chars
_ENTITY_RES: List[re.Pattern] = [
    re.compile(r"(?<![0-9a-zA-Z])OP-\d{4}-\d{2,}(?![0-9a-zA-Z])", re.IGNORECASE),
    re.compile(r"(?<![0-9a-zA-Z])INV\d{4,}(?![0-9a-zA-Z])", re.IGNORECASE),
    re.compile(r"(?<![0-9a-zA-Z])tr-[0-9a-f]{8,}(?![0-9a-zA-Z])"),
    re.compile(r"(?<![0-9a-zA-Z])[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}(?![0-9a-zA-Z])"),
    # id قصير (بادئة UUID/قيد) — يشترط حرفاً hex واحداً على الأقل كي لا تُحجب أرقام/تواريخ
    re.compile(r"(?<![0-9a-zA-Z-])(?=[0-9]*[a-f])[0-9a-f]{8}(?![0-9a-zA-Z-])"),
]


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


def enforce_entities(response_text: str, evidence_text: str) -> Tuple[str, List[Dict[str, str]]]:
    """يحجب أي معرّف منظَّم في الرد لا يظهر حرفياً في أدلة الدورة."""
    if not response_text:
        return response_text, []
    ev = (evidence_text or "").lower()
    violations: List[Dict[str, str]] = []
    out = response_text
    seen: set = set()
    for rx in _ENTITY_RES:
        for m in rx.finditer(response_text):
            val = m.group(0)
            key = val.lower()
            if key in seen:
                continue
            seen.add(key)
            if key in ev or val in _BLOCKED_MARK:
                continue
            violations.append({
                "kind": "fabricated_entity",
                "value": val[:40],
                "reason": "معرّف غير موجود في أدلة الدورة (أدوات/سياق/رسالة/تاريخ)",
            })
            out = out.replace(val, _BLOCKED_MARK)
    return out, violations
