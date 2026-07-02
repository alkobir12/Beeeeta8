"""🧠 Katrina Developer Mode (RRR) — Phase 1

Trigger «rrr» (admin فقط) → تحميل السياق المؤسسي الكامل وحقنه في سياق LLM.
قاعدة صارمة: كاترينا لا تلمس ملفات الكود — أي تغيير مقترح يخرج كـ Proposal تفصيلي
(الملف، الموضع، diff مقترح، المبرر) والتنفيذ يدوي خارج النظام.
"""
from __future__ import annotations

import os
import re
import time
from typing import Any, Dict, List, Optional

from core.log_utils import get_logger, redact

_log = get_logger("developer_mode")

TRIGGER_RE = re.compile(r"^\s*rrr\s*$", re.IGNORECASE)
TRIGGER_OFF_RE = re.compile(r"^\s*rrr\s+(off|خروج|ايقاف|إيقاف)\s*$", re.IGNORECASE)

_MEMORY_DIR = "/app/memory"
_MAX_FILE_CHARS = 15000

# كاش السياق (بناء السياق يقرأ ملفات + يستعلم قواعد بيانات)
_CACHE: Dict[str, Any] = {"ctx": None, "ts": 0.0}
_CACHE_TTL = 300.0


def _read_file(path: str, max_chars: int = _MAX_FILE_CHARS) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            txt = f.read()
        if len(txt) > max_chars:
            txt = txt[:max_chars] + f"\n… [مقتطع — {len(txt):,} حرف كلي]"
        return txt
    except Exception:
        return ""


def _api_contracts() -> str:
    """قائمة مسارات API الحية من تطبيق FastAPI (عقود فعلية لا موثّقة يدوياً)."""
    try:
        import sys
        app_mod = sys.modules.get("server")
        app = getattr(app_mod, "app", None)
        if app is None:
            return ""
        lines: List[str] = []
        for r in app.routes:
            path = getattr(r, "path", "")
            if not str(path).startswith("/api"):
                continue
            methods = ",".join(sorted(m for m in (getattr(r, "methods", None) or []) if m != "HEAD"))
            lines.append(f"{methods} {path}")
        lines.sort(key=lambda s: s.split(" ", 1)[-1])
        return f"عدد المسارات: {len(lines)}\n" + "\n".join(lines[:300])
    except Exception as e:
        _log.debug("api contracts failed: %s", redact(str(e), max_len=80))
        return ""


def _db_snapshot() -> str:
    """أعداد الجداول الحية (Supabase) + مجموعات MongoDB."""
    parts: List[str] = []
    try:
        from supabase_service import SupabaseService
        client = SupabaseService().client
        if client:
            parts.append("Supabase (relational):")
            for t in ("operations", "journal_entries", "customers", "vehicles",
                      "vehicle_visits", "accounts"):
                try:
                    res = client.table(t).select("id", count="exact").limit(1).execute()
                    parts.append(f"  • {t}: {res.count} صف")
                except Exception:
                    parts.append(f"  • {t}: غير متاح")
    except Exception:
        pass
    try:
        from pymongo import MongoClient
        mc = MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=3000)
        db = mc[os.environ["DB_NAME"]]
        colls = sorted(db.list_collection_names())
        parts.append("MongoDB (state/audit): " + ", ".join(
            f"{c}({db[c].estimated_document_count()})" for c in colls[:15]))
    except Exception:
        pass
    return "\n".join(parts)


def _runtime_snapshot() -> str:
    """حالة محرك التنفيذ + آخر أحداث التدقيق."""
    try:
        from core import action_runtime
        st = action_runtime.stats()
        lines = [
            f"drafts: {st.get('drafts')} {st.get('drafts_by_status')}",
            f"approvals: {st.get('approvals')} | executions: {st.get('executions')} | "
            f"audit_events: {st.get('audit_events')} | four_eyes: {st.get('enforce_4eyes')}",
            "آخر أحداث التدقيق:",
        ]
        for ev in action_runtime.get_audit_trail(limit=8):
            lines.append(f"  • {ev.get('event')} — draft={ev.get('draft_id','')} approval={ev.get('approval_id','')}")
        return "\n".join(lines)
    except Exception as e:
        return f"غير متاح: {redact(str(e), max_len=60)}"


def _architecture_summary() -> str:
    """خريطة ملفات مختصرة للباك/الفرونت (أسماء فقط، لا محتوى)."""
    out: List[str] = []
    try:
        be = sorted(f for f in os.listdir("/app/backend") if f.endswith(".py"))
        core = sorted(f for f in os.listdir("/app/backend/core") if f.endswith(".py"))
        out.append("backend/: " + ", ".join(be))
        out.append("backend/core/: " + ", ".join(core))
    except Exception:
        pass
    try:
        pages = sorted(os.listdir("/app/frontend/src/pages"))
        comps = sorted(f for f in os.listdir("/app/frontend/src/components") if not f.startswith("."))
        out.append("frontend/src/pages/: " + ", ".join(pages))
        out.append("frontend/src/components/: " + ", ".join(comps[:40]))
    except Exception:
        pass
    return "\n".join(out)


def build_dev_context(force: bool = False) -> Dict[str, Any]:
    """يبني (أو يرجع من الكاش) السياق المؤسسي الكامل + قياساته."""
    now = time.time()
    if not force and _CACHE["ctx"] and (now - _CACHE["ts"] < _CACHE_TTL):
        return _CACHE["ctx"]

    t0 = time.time()
    sections: List[tuple] = [
        ("PRD (متطلبات المنتج + Backlog)", _read_file(f"{_MEMORY_DIR}/PRD.md")),
        ("CHANGELOG (القرارات/الأخطاء/الإصلاحات السابقة)", _read_file(f"{_MEMORY_DIR}/CHANGELOG.md")),
        ("ROADMAP (خارطة الطريق)", _read_file(f"{_MEMORY_DIR}/ROADMAP.md")),
        ("بنية الملفات (Architecture)", _architecture_summary()),
        ("عقود API الحية", _api_contracts()),
        ("قاعدة البيانات (Schema حية)", _db_snapshot()),
        ("محرك التنفيذ والتدقيق (Runtime)", _runtime_snapshot()),
    ]
    blocks: List[str] = []
    meta: List[Dict[str, Any]] = []
    for name, content in sections:
        content = (content or "").strip()
        meta.append({"name": name, "chars": len(content), "loaded": bool(content)})
        if content:
            blocks.append(f"### {name}\n{content}")
    text = "\n\n".join(blocks)
    load_ms = int((time.time() - t0) * 1000)
    ctx = {
        "text": text,
        "chars": len(text),
        "est_tokens": int(len(text) / 3),
        "load_ms": load_ms,
        "sections": meta,
        "built_at": now,
    }
    _CACHE["ctx"] = ctx
    _CACHE["ts"] = now
    return ctx


def dev_system_addendum() -> str:
    """كتلة تُلحق بـ system prompt عندما يكون وضع المطور مفعّلاً في الجلسة."""
    ctx = build_dev_context()
    rules = (
        "\n══════════ 🧠 DEVELOPER MODE (RRR) — ACTIVE ══════════\n"
        "أنتِ الآن مهندسة النظام الخبيرة — تعرفين المشروع بالكامل من السياق المؤسسي أدناه.\n"
        "قواعد صارمة (غير قابلة للتجاوز):\n"
        "1) أي اقتراح تغيير كود = **Proposal تفصيلي** بهذا الشكل: الملف، الموضع/الدالة، "
        "diff مقترح داخل كتلة كود، المبرر، الخطورة (Low/Med/High)، الفائدة، خطة الاختبار. "
        "**ممنوع الادعاء بتعديل الكود** — التنفيذ يدوي خارج النظام بعد الاعتماد.\n"
        "2) استندي حصراً للسياق أدناه ولنتائج الأدوات — إن نقصت معلومة قولي «أحتاج ملف/معلومة X».\n"
        "3) قواعد الأمان قائمة: لا حذف بيانات، لا تعديل قيود محاسبية، لا تجاوز أربع أعين أو سجل التدقيق.\n"
        "──────── السياق المؤسسي المحمّل ────────\n"
    )
    return rules + ctx["text"]


def is_active(session_id: str) -> bool:
    try:
        from core import shared_memory
        return bool(shared_memory.get_context(session_id, "dev_mode"))
    except Exception:
        return False


def _activation_text(ctx: Dict[str, Any]) -> str:
    lines = ["🧠 **Developer Mode Activated**", ""]
    icons = {True: "✅", False: "⚠️"}
    for s in ctx["sections"]:
        lines.append(f"{icons[s['loaded']]} {s['name']} — {s['chars']:,} حرف")
    lines += [
        "",
        f"📏 حجم السياق: **~{ctx['est_tokens']:,} token** ({ctx['chars']:,} حرف) | "
        f"⏱️ زمن التحميل: **{ctx['load_ms']} ms**",
        "",
        "📐 **قواعد الوضع**: أي تغيير كود يخرج كـ Proposal تفصيلي (ملف/موضع/diff/مبرر) — "
        "لا تنفيذ مباشر، ولا مساس بقواعد الأمان والأربع أعين.",
        "",
        "**Waiting for Instructions...** — اكتب سؤالك أو اطلب تحليلاً. للإنهاء: `rrr off`",
    ]
    return "\n".join(lines)


def handle_trigger(session_id: str, message: str, role: Optional[str]) -> Optional[Dict[str, Any]]:
    """يرجع None إذا لم تكن الرسالة أمر rrr — وإلا dict {text, status}."""
    msg = (message or "").strip()
    from core import shared_memory

    if TRIGGER_OFF_RE.match(msg):
        if shared_memory.get_context(session_id, "dev_mode"):
            shared_memory.set_context(session_id, "dev_mode", False)
            return {"text": "🧠 Developer Mode Deactivated — رجعنا للوضع التشغيلي العادي.", "status": "dev_off"}
        return {"text": "وضع المطور غير مفعّل في هذه الجلسة أصلاً.", "status": "dev_off"}

    if not TRIGGER_RE.match(msg):
        return None

    if (role or "").strip().lower() != "admin":
        _log.info("rrr denied for role=%s", role)
        return {"text": "🚫 وضع المطور (`rrr`) متاح لدور **admin** فقط في هذه المرحلة.",
                "status": "dev_denied"}

    ctx = build_dev_context(force=True)
    shared_memory.set_context(session_id, "dev_mode", True)
    _log.info("developer mode ON session=%s ctx_tokens≈%s load=%sms",
              session_id, ctx["est_tokens"], ctx["load_ms"])
    return {"text": _activation_text(ctx), "status": "dev_on"}
