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


def _md_compact(text: str, keep_sections: tuple = ()) -> str:
    """يضغط Markdown: كل العناوين تبقى، ومحتوى الأقسام المُدرجة في keep_sections فقط يبقى كاملاً."""
    out: List[str] = []
    keep_mode = False
    for line in (text or "").splitlines():
        if line.startswith("#"):
            title = line.lstrip("# ").strip()
            keep_mode = any(k in title for k in keep_sections)
            out.append(line)
        elif keep_mode and line.strip():
            out.append(line)
    return "\n".join(out)


def _changelog_compact(text: str, keep_last: int = 2) -> str:
    """آخر N إدخالات كاملة + عناوين ما قبلها فقط (الإدخالات تبدأ بـ '## ')."""
    entries: List[List[str]] = []
    cur: List[str] = []
    for line in (text or "").splitlines():
        if line.startswith("## "):
            if cur:
                entries.append(cur)
            cur = [line]
        elif cur:
            cur.append(line)
    if cur:
        entries.append(cur)
    if not entries:
        return ""
    older = [e[0] for e in entries[:-keep_last]]
    recent = ["\n".join(e) for e in entries[-keep_last:]]
    parts = []
    if older:
        parts.append("قرارات/إصلاحات سابقة (عناوين):\n" + "\n".join(older))
    parts.extend(recent)
    return "\n\n".join(parts)


def _api_contracts() -> str:
    """عقود API الحية مضغوطة: دمج methods لكل مسار + حذف بادئة /api."""
    try:
        import sys
        app_mod = sys.modules.get("server")
        app = getattr(app_mod, "app", None)
        if app is None:
            return ""
        by_path: Dict[str, set] = {}
        for r in app.routes:
            path = str(getattr(r, "path", ""))
            if not path.startswith("/api"):
                continue
            methods = {m for m in (getattr(r, "methods", None) or []) if m != "HEAD"}
            by_path.setdefault(path[4:] or "/", set()).update(methods)
        lines = [f"{'|'.join(sorted(ms))} {p}" for p, ms in sorted(by_path.items())]
        return (f"عدد المسارات: {len(lines)} (البادئة /api محذوفة)\n"
                + "\n".join(lines[:250]))
    except Exception as e:
        _log.debug("api contracts failed: %s", redact(str(e), max_len=80))
        return ""


def _db_snapshot() -> str:
    """Schema كأسماء فقط: جدول → أعمدة + عدد الصفوف (بلا أي بيانات)."""
    parts: List[str] = []
    try:
        from supabase_service import SupabaseService
        client = SupabaseService().client
        if client:
            parts.append("Supabase (relational):")
            for t in ("operations", "journal_entries", "customers", "vehicles",
                      "vehicle_visits", "accounts"):
                try:
                    res = client.table(t).select("*", count="exact").limit(1).execute()
                    cols = ", ".join((res.data[0] if res.data else {}).keys())
                    parts.append(f"  • {t} ({res.count} صف): {cols}")
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
        pages = sorted(os.listdir("/app/frontend/src/pages"))[:30]
        comps = sorted(f for f in os.listdir("/app/frontend/src/components") if not f.startswith("."))[:25]
        out.append("frontend/src/pages/: " + ", ".join(pages))
        out.append("frontend/src/components/ (أول 25): " + ", ".join(comps))
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
        ("PRD موجز (عناوين + Backlog + الحالة المعروفة)",
         _md_compact(_read_file(f"{_MEMORY_DIR}/PRD.md"), keep_sections=("Backlog", "Known Status"))),
        ("CHANGELOG (آخر إدخالين كاملين + عناوين السابق)",
         _changelog_compact(_read_file(f"{_MEMORY_DIR}/CHANGELOG.md"), keep_last=2)),
        ("ROADMAP (خارطة الطريق)", _read_file(f"{_MEMORY_DIR}/ROADMAP.md", max_chars=3000)),
        ("بنية الملفات (Architecture)", _architecture_summary()),
        ("عقود API الحية (مضغوطة)", _api_contracts()),
        ("Schema (أسماء جداول/أعمدة فقط)", _db_snapshot()),
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
