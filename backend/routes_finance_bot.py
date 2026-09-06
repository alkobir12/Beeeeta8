from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query, Request, Response
from pydantic import BaseModel, Field
from typing import Optional, Any, Dict, List, Tuple
import os
import uuid
import re
from pathlib import Path
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient

from emergentintegrations.llm.chat import LlmChat, UserMessage

from routes_finance import supabase  # reuse existing client
from core import rbac
from core import object_storage

router = APIRouter(prefix="/api/finance-bot", tags=["finance-bot"])


FINANCE_SYSTEM_PROMPT = """
أنت محاسب قانوني خارجي ينفذ جلسة تدقيق حيّة.
- اسأل سؤالًا واحدًا فقط في كل رد.
- لا تنتقل لملاحظة جديدة قبل حسم الحالية (resolved أو escalated).
- ابدأ دائمًا بأعلى ملاحظة خطورة.
- واجه التناقضات بالأرقام مباشرة.
- عند المخاطر العالية لا تقبل تفسيرًا بلا مستند داعم.
- عند اكتشاف تناقض بين تفسير المستخدم والبيانات، واجهه بالرقم الفعلي مباشرةً.
- إذا تم تزويدك بسياق "🛡️ حالة جدار حماية المحاسبة" استخدمه لحظياً:
  • أعطِ أولوية لأي قيد غير متوازن مسرّب في DB.
  • إذا كانت رفضيات الجلسة عالية (≥20)، اسأل عن سبب إدخالات غير متوازنة متكررة.
  • إذا تجاوز الانحراف العشري العتبة، تتبّع مصدر التقريب.
""".strip()


QUESTION_BANK = {
    "elevated": [
        "ما سبب هذا الارتفاع تحديدًا في هذا الحساب؟",
        "ما العامل الذي أدى لهذا التغير مقارنة بالفترة السابقة؟",
        "هل هذا الارتفاع ناتج عن عملية تشغيلية أم تعديل محاسبي؟",
    ],
    "no_financial_match": [
        "لماذا لا توجد حركة نقدية رغم وجود نشاط مرتبط؟",
        "كيف تم تسجيل هذا النشاط محاسبيًا دون أثر مالي واضح؟",
        "هل هناك تأخير في الاعتراف أو تسجيل ناقص؟",
    ],
    "unsupported": [
        "هل يوجد قيد أو فاتورة مرتبطة؟",
        "ما مصدر هذه القيمة في القيود؟",
    ],
    "linked_mismatch": [
        "لماذا لا يتوافق هذا الحساب مع الحساب المرتبط به؟",
        "كيف تفسر الانفصال بين الإيراد والذمم المدينة هنا؟",
        "هل هناك تسوية لم تُسجل بعد؟",
    ],
    "sudden_change": [
        "ما سبب هذا التغير الحاد خلال هذه الفترة تحديدًا؟",
        "هل هناك حدث استثنائي يفسر هذا الانحراف؟",
        "هل التغيير متكرر أم حالة منفردة؟",
    ],
    "evidence_required": [
        "هل يمكنك رفع مستند داعم الآن (فاتورة/قيد) لهذه الملاحظة؟",
    ],
}


SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
INTERACTIVE_ACTIONS = [
    "open_investigation",
    "apply_suggested_fix",
    "view_evidence",
    "escalate",
]
AUDIT_SESSION_MEM: Dict[str, Dict[str, Any]] = {}
_AUDIT_DB = None


async def _require_financial_read(request: Request):
    ident = rbac.extract_identity(request)
    if not ident.get("user_id"):
        raise HTTPException(status_code=401, detail="Not authenticated")
    actor = await rbac.resolve_actor(user_id=ident["user_id"], name=ident["name"], role_hint=ident["role_hint"])
    if not (
        actor.can("journal_entries", "view")
        or actor.can("reports", "view")
        or actor.can("debts", "view")
    ):
        raise HTTPException(status_code=403, detail={"error": "financial_read_required"})
    return actor


async def _require_financial_evidence_upload(request: Request):
    actor = await _require_financial_read(request)
    if not (actor.can("vehicles", "view") or actor.can("archive", "view")):
        raise HTTPException(status_code=403, detail={"error": "file_upload_authorization_required"})
    return actor


def _get_audit_db():
    global _AUDIT_DB
    if _AUDIT_DB is not None:
        return _AUDIT_DB

    try:
        mongo_url = os.environ.get("MONGO_URL")
        db_name = os.environ.get("DB_NAME")
        if not mongo_url or not db_name:
            return None
        _AUDIT_DB = AsyncIOMotorClient(mongo_url)[db_name]
        return _AUDIT_DB
    except Exception:
        return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_severity(value: Any) -> str:
    s = str(value or "").strip().lower()
    if s in {"critical", "high", "medium", "low"}:
        return s
    if s in {"مرتفع", "عالي"}:
        return "high"
    if s in {"متوسط"}:
        return "medium"
    if s in {"منخفض"}:
        return "low"
    return "medium"


def _detect_category(finding: Dict[str, Any]) -> str:
    hay = " ".join(
        [
            str(finding.get("title") or ""),
            str(finding.get("message") or ""),
            str(finding.get("actual_value") or ""),
        ]
    ).lower()
    if any(k in hay for k in ["لا يتوافق", "عدم توازن", "ذمم", "≠", "فرق"]):
        return "linked_mismatch"
    if any(k in hay for k in ["بدون حركة", "دون أثر", "لا توجد حركة نقدية"]):
        return "no_financial_match"
    if any(k in hay for k in ["غير مدعوم", "فاتورة", "مستند", "قيد"]):
        return "unsupported"
    if any(k in hay for k in ["حاد", "مفاجئ", "قفزة", "انحراف"]):
        return "sudden_change"
    return "elevated"


def _pick_single_suggestion(raw: Dict[str, Any]) -> Optional[str]:
    candidates = [
        raw.get("suggested_fix"),
        raw.get("suggestion"),
        raw.get("correction"),
        raw.get("recommended_action"),
    ]
    for value in candidates:
        text = str(value or "").strip()
        if text:
            return text
    return None


def _enforce_single_question(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return "ما التفسير المحدد لهذا الانحراف؟"

    m = re.search(r"(.+?[؟?])", cleaned)
    if m:
        q = m.group(1).strip()
    else:
        q = cleaned.rstrip(".!") + "؟"

    q = q.replace("??", "?").replace("؟؟", "؟")
    q = q.replace("?", "؟")
    if not q.endswith("؟"):
        q = q.rstrip(".") + "؟"
    return q


def _is_vague(text: str) -> bool:
    t = str(text or "").strip().lower()
    if len(t) < 8:
        return True
    vague_tokens = ["لا أعرف", "غير متأكد", "ما أدري", "مدري", "يمكن", "احتمال"]
    return any(tok.lower() in t for tok in vague_tokens)


def _build_next_question(finding: Dict[str, Any], ask_evidence: bool = False) -> str:
    category = str(finding.get("category") or "elevated")
    asked = int(finding.get("question_count") or 0)

    if ask_evidence:
        q = QUESTION_BANK["evidence_required"][0]
    else:
        pool = QUESTION_BANK.get(category) or QUESTION_BANK["elevated"]
        q = pool[min(asked, len(pool) - 1)]

    account = str(finding.get("account") or finding.get("account_code") or "").strip()
    if account:
        q = f"في الحساب {account}: {q}"

    return _enforce_single_question(q)


def _normalize_finding(raw: Dict[str, Any], idx: int) -> Dict[str, Any]:
    finding_id = str(raw.get("finding_id") or raw.get("id") or f"finding_{idx+1}")
    severity = _normalize_severity(raw.get("severity"))
    finding = {
        "finding_id": finding_id,
        "title": str(raw.get("title") or raw.get("finding") or "ملاحظة تدقيق"),
        "account": str(raw.get("account") or raw.get("account_code") or ""),
        "period": str(raw.get("period") or ""),
        "actual_value": raw.get("actual_value") if raw.get("actual_value") is not None else raw.get("actual"),
        "expected_range": raw.get("expected_range") if raw.get("expected_range") is not None else raw.get("expected"),
        "severity": severity,
        "confidence": float(raw.get("confidence") or 0),
        "related_accounts": raw.get("related_accounts") or raw.get("linked_accounts") or [],
        "operation_refs": raw.get("operation_refs") or raw.get("references") or [],
        "message": str(raw.get("message") or ""),
        "status": str(raw.get("status") or "open"),
        "category": _detect_category(raw),
        "question_count": int(raw.get("question_count") or 0),
        "suggested_fix": _pick_single_suggestion(raw),
        "interactive": True,
        "actions": INTERACTIVE_ACTIONS,
        "evidence": raw.get("evidence") or [],
        "history": raw.get("history") or [],
    }
    return finding


def _sort_findings(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(
        findings,
        key=lambda f: (
            SEVERITY_ORDER.get(_normalize_severity(f.get("severity")), 99),
            -float(f.get("confidence") or 0),
        ),
    )


def _build_interactive_card(finding: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(finding, dict):
        return {"enabled": False, "actions": []}
    return {
        "enabled": True,
        "finding_id": finding.get("finding_id"),
        "state": finding.get("status"),
        "suggested_fix": finding.get("suggested_fix"),
        "actions": INTERACTIVE_ACTIONS,
    }


def _find_finding_by_id(findings: List[Dict[str, Any]], finding_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not finding_id:
        return None
    target = str(finding_id).strip()
    for finding in findings:
        if str(finding.get("finding_id") or "").strip() == target:
            return finding
    return None


def _pending_evidence_message(finding: Dict[str, Any]) -> str:
    account = str(finding.get("account") or "").strip()
    prefix = f"في الحساب {account}: " if account else ""
    return f"{prefix}الملاحظة بانتظار مستند داعم. ارفع مرفقًا من الواجهة للمتابعة."


async def _load_session(session_id: str) -> Optional[Dict[str, Any]]:
    audit_db = _get_audit_db()
    if audit_db is not None:
        row = await audit_db.finance_audit_sessions.find_one({"session_id": session_id}, {"_id": 0})
        return row
    return AUDIT_SESSION_MEM.get(session_id)


async def _save_session(session: Dict[str, Any]):
    session["updated_at"] = _now_iso()
    audit_db = _get_audit_db()
    if audit_db is not None:
        await audit_db.finance_audit_sessions.update_one(
            {"session_id": session.get("session_id")},
            {"$set": session},
            upsert=True,
        )
        return
    AUDIT_SESSION_MEM[str(session.get("session_id"))] = session


def _first_open_finding(findings: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for finding in findings:
        if finding.get("status") not in {"resolved", "escalated"}:
            return finding
    return None


def _normalize_findings_from_request(payload: "FinanceBotChatRequest") -> List[Dict[str, Any]]:
    incoming = payload.findings or []
    normalized = [_normalize_finding(f, idx) for idx, f in enumerate(incoming)]
    return _sort_findings(normalized)


class FinanceBotChatRequest(BaseModel):
    message: str = Field("", description="نص سؤال أو طلب المستخدم")
    session_id: Optional[str] = Field(None, description="معرف جلسة التدقيق")
    account_code: Optional[str] = Field(
        None, description="كود الحساب المحاسبي المراد تدقيقه (مثل 411 أو 514)"
    )
    workshop_id: Optional[str] = Field(
        None, description="معرّف الورشة، مثل finmodule-sync"
    )
    conversation_id: Optional[str] = Field(
        None, description="معرّف المحادثة للحفاظ على السياق"
    )
    findings: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Findings القادمة من محرك التحليل الخلفي",
    )
    action: Optional[str] = Field(
        None,
        description="إجراء تفاعلي (open_investigation/apply_suggested_fix/view_evidence/escalate)",
    )
    target_finding_id: Optional[str] = Field(None, description="الملاحظة الهدف للإجراء")
    evidence_id: Optional[str] = Field(None, description="معرف المرفق الداعم")
    evidence_name: Optional[str] = Field(None, description="اسم الملف الداعم")
    # بيانات مالية اختيارية لتمكين التحليل القواعدي (لا تغيّر شكل الرد)
    financial_data: Optional[Dict[str, Any]] = Field(
        None,
        description="ملخص بيانات مالية اختيارية (مثل revenue/expenses/assets/liabilities) لإضافة ملاحظات قواعدية",
    )


class FinanceBotChatResponse(BaseModel):
    response: str
    conversation_id: str
    session_id: str
    finding_id: Optional[str] = None
    finding_status: Optional[str] = None
    state: Optional[str] = None
    interactive: Optional[Dict[str, Any]] = None
    linked_data: Optional[Dict[str, Any]] = None
    contradictions: Optional[List[Dict[str, Any]]] = None
    auto_escalated: Optional[bool] = None
    provider: str = "openai-gpt-5.1"
    timestamp: str


def abu_fahad_safe_analysis(financial_data: Dict[str, Any]) -> Dict[str, List[str]]:
    """تحليل قواعدي بسيط وآمن (بدون LLM) لإضافة تنبيهات سريعة.

    الهدف: إضافة طبقة تدقيق مبدئية حتى لو كانت البيانات محدودة.
    """
    notes: List[str] = []

    try:
        revenue = float(financial_data.get("revenue") or 0)
        expenses = float(financial_data.get("expenses") or 0)
        net_profit = float(
            financial_data.get("net_profit")
            if financial_data.get("net_profit") is not None
            else financial_data.get("netProfit")
            if financial_data.get("netProfit") is not None
            else (revenue - expenses)
        )
        assets = float(financial_data.get("assets") or 0)
        liabilities = float(financial_data.get("liabilities") or 0)

        if revenue > 0:
            margin = (net_profit / revenue) * 100
            if margin < 10:
                notes.append(f"تنبيه: هامش الربح منخفض جداً ({margin:.1f}%). راجع تسعير الخدمات وهوامش قطع الغيار.")
            elif margin < 20:
                notes.append(f"ملاحظة: هامش الربح متوسط ({margin:.1f}%). توجد فرصة لرفع الربحية عبر ضبط المصروفات أو تحسين التسعير.")
        else:
            notes.append("ملاحظة: لا توجد إيرادات مسجلة في البيانات المرسلة. إذا كان هذا غير صحيح، تحقق من تسجيل العمليات والقيود.")

        if revenue > 0 and expenses > revenue:
            notes.append("تنبيه: المصروفات أعلى من الإيرادات في الفترة، وهذا مؤشر خطر على الربحية.")

        if assets > 0 and liabilities > assets * 0.5:
            notes.append("تحذير: نسبة الالتزامات إلى الأصول مرتفعة. راجع السيولة وجدول السداد.")

    except Exception:
        # في حال أي مشكلة تحويل/تنسيق لا نمنع عمل البوت
        pass

    return {"notes": notes}


def build_financial_context(financial_data: Optional[Dict[str, Any]]) -> str:
    if not financial_data:
        return ""
    return (
        "ملخص مالي مختصر:\n"
        f"- الإيرادات: {financial_data.get('revenue', 0)}\n"
        f"- المصروفات: {financial_data.get('expenses', 0)}\n"
        f"- صافي الربح: {financial_data.get('netProfit', financial_data.get('net_profit', 0))}\n"
        f"- هامش الربح: {financial_data.get('profitMargin', financial_data.get('net_margin', 0))}%\n"
        f"- السيولة الحالية: {financial_data.get('current_ratio', '—')}\n"
    )


async def build_firewall_context(workshop_id: Optional[str]) -> str:
    """🛡️ يبني سياقاً لحظياً من جدار حماية المحاسبة لكي يرى المساعد المالي
    حالة التوازن، الرفضيات، COGS، الانحراف العشري."""
    try:
        from routes_firewall import firewall_status
        data = await firewall_status(workshop_id=workshop_id, recent_limit=5)
        if not data or not data.get("success"):
            return ""
        s = data.get("summary") or {}
        drift = data.get("drift") or {}
        recent_rej = data.get("recent_rejections") or []
        rej_lines = "\n".join(
            f"   • {r.get('description', '')[:50]} | drift={r.get('drift')}"
            for r in recent_rej[:3]
        )
        return (
            "🛡️ حالة جدار حماية المحاسبة (لحظي):\n"
            f"- إجمالي القيود: {s.get('total_entries', 0)}\n"
            f"- متوازنة: {s.get('balanced_entries', 0)}\n"
            f"- غير متوازنة بـ DB: {s.get('unbalanced_entries_in_db', 0)}\n"
            f"- نسبة سلامة التوازن: {s.get('balance_health_percent', 100)}%\n"
            f"- رفضيات هذه الجلسة: {s.get('lifetime_rejections', 0)}\n"
            f"- ضربات منع التكرار: {s.get('lifetime_idempotency_hits', 0)}\n"
            f"- قيود COGS مولّدة: {s.get('cogs_entries', 0)} (مبلغ: {s.get('cogs_total_amount', 0)})\n"
            f"- أقصى انحراف عشري: {drift.get('max', 0)} (عتبة: {drift.get('threshold', 0.009)})\n"
            + (f"- آخر الرفضيات:\n{rej_lines}\n" if rej_lines else "")
        )
    except Exception as e:
        print(f"build_firewall_context failed: {e}")
        return ""


def _get_llm_chat(conversation_id: Optional[str]) -> LlmChat:
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="لم يتم ضبط مفتاح EMERGENT_LLM_KEY في الخادم. يرجى التواصل مع المسؤول.",
        )

    session_id = conversation_id or str(uuid.uuid4())

    chat = LlmChat(
        api_key=api_key,
        session_id=session_id,
        system_message=FINANCE_SYSTEM_PROMPT,
    ).with_model("openai", "gpt-5.1")

    return chat


async def _build_account_context(workshop_id: str, account_code: str) -> str:
    """جلب ملخّص عن حساب معيّن من Supabase لتضمينه في سياق الدردشة."""
    if not supabase:
        return ""

    try:
        # جلب بيانات الحساب من دليل الحسابات
        def lookup_account(table_name: str, field: str):
            return (
                supabase.table(table_name)
                .select("id, code, name_ar, name, type, balance")
                .eq("workshop_id", workshop_id)
                .eq(field, account_code)
                .execute()
            )

        account = None
        for table_name in ["chart_of_accounts", "business_accounts"]:
            try:
                coa_res = lookup_account(table_name, "code")
                account = (coa_res.data or [None])[0]
                if not account:
                    coa_res = lookup_account(table_name, "id")
                    account = (coa_res.data or [None])[0]
                if account:
                    break
            except Exception as e:
                print(f"Account lookup error ({table_name}): {e}")
                continue

        # جلب إجمالي المدين والدائن من قيود اليومية لهذا الحساب
        je_res = (
            supabase.table("journal_entries")
            .select("lines")
            .eq("workshop_id", workshop_id)
            .execute()
        )

        total_debit = 0.0
        total_credit = 0.0
        entries_count = 0

        for row in (je_res.data or []):
            for line in row.get("lines", []) or []:
                code = (
                    line.get("account_code")
                    or line.get("account")
                    or line.get("account_id")
                    or line.get("accountId")
                )
                if str(code) == str(account_code) or (account and str(code) == str(account.get("id"))):
                    total_debit += float(line.get("debit", 0) or 0)
                    total_credit += float(line.get("credit", 0) or 0)
                    entries_count += 1

        if not account and entries_count == 0:
            return f"لا توجد بيانات محاسبية متاحة للحساب {account_code}."

        account_name = (
            account.get("name_ar") or account.get("name") if account else f"الحساب {account_code}"
        )
        account_type = account.get("type") if account else "غير محدد"

        parts = [
            f"ملخص الحساب المحاسبي {account_code}:",
        ]

        parts.append(f"- الاسم: {account_name or 'غير معروف'}")
        parts.append(f"- النوع: {account_type or 'غير محدد'}")
        if account and account.get("balance") is not None:
            parts.append(f"- الرصيد المسجّل: {account.get('balance')}")

        parts.append(
            f"- إجمالي المدين من القيود: {total_debit:.2f} | إجمالي الدائن: {total_credit:.2f} | عدد الحركات: {entries_count}"
        )

        return "\n".join(parts)

    except Exception as e:
        # في حال فشل جلب البيانات، لا نمنع الدردشة، فقط نعيد رسالة مختصرة
        return f"تعذّر جلب بيانات مفصّلة للحساب {account_code} بسبب خطأ تقني: {e}"


@router.get("/health")
async def finance_bot_health():
    """فحص صحة إعداد البوت المالي (وجود المفتاح ونموذج LLM)."""
    has_key = bool(os.environ.get("EMERGENT_LLM_KEY"))
    return {
        "status": "ok" if has_key else "missing-key",
        "provider": "openai",
        "model": "gpt-5.1",
        "has_key": has_key,
        "timestamp": datetime.now().isoformat(),
    }


@router.post("/evidence/upload")
async def upload_finance_evidence(
    request: Request,
    file: UploadFile = File(...),
    session_id: str = Form(...),
    finding_id: Optional[str] = Form(None),
):
    """رفع مرفق داعم للتدقيق وربطه بجلسة/ملاحظة (تخزين دائم في Object Storage)."""
    try:
        await _require_financial_evidence_upload(request)
        data = await file.read()
        checked = object_storage.validate_upload(
            data, file.filename, file.content_type, "finance-audit-evidence"
        )

        safe_session = re.sub(r"[^a-zA-Z0-9_-]", "", session_id) or "audit"
        evidence_id = str(uuid.uuid4())
        object_key = object_storage.build_object_key(
            "finance-audit-evidence", safe_session, checked["ext"]
        )
        stored = await object_storage.put_object(object_key, data, checked["content_type"])

        record = {
            "evidence_id": evidence_id,
            "session_id": session_id,
            "finding_id": finding_id,
            "file_name": object_storage.safe_basename(file.filename or "evidence"),
            "storage_backend": "emergent_object_storage",
            "storage_path": stored["path"],
            "mime_type": checked["content_type"],
            "content_verification": checked["verification_level"],
            "size": len(data),
            # Retention-first: audit evidence is never physically deleted.
            "is_deleted": False,
            "uploaded_at": _now_iso(),
        }

        audit_db = _get_audit_db()
        if audit_db is not None:
            await audit_db.finance_audit_evidence.insert_one({**record})

        return {"success": True, "data": record}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"تعذر رفع المرفق: {e}")


@router.get("/evidence/{evidence_id}/download")
async def download_finance_evidence(evidence_id: str, request: Request):
    """تنزيل مرفق تدقيق — التفويض يُفحص على الخادم، ولا يُمرَّر أي توكن في الرابط."""
    await _require_financial_evidence_upload(request)
    audit_db = _get_audit_db()
    if audit_db is None:
        raise HTTPException(status_code=503, detail={"error": "audit_store_unavailable"})

    record = await audit_db.finance_audit_evidence.find_one({"evidence_id": evidence_id}, {"_id": 0})
    if not record:
        raise HTTPException(status_code=404, detail={"error": "evidence_not_found"})

    media_type = record.get("mime_type") or "application/octet-stream"
    storage_path = record.get("storage_path")
    if storage_path:
        data, detected = await object_storage.get_object(storage_path)
        return Response(content=data, media_type=media_type or detected)

    # LEGACY TEMPORARY COMPATIBILITY — evidence uploaded before the object-storage
    # migration still lives on the container filesystem. Read-only fallback; it is
    # NOT the target architecture and disappears with the pod.
    legacy_path = record.get("file_path")
    if legacy_path and Path(legacy_path).is_file():
        return Response(content=Path(legacy_path).read_bytes(), media_type=media_type)

    raise HTTPException(
        status_code=410,
        detail={
            "error": "evidence_content_unavailable",
            "message": "المرفق كان مخزناً محلياً وفُقد مع إعادة تشغيل الحاوية.",
        },
    )


def _response_state_transition(
    finding: Dict[str, Any],
    user_message: str,
    evidence_id: Optional[str],
) -> Dict[str, Any]:
    message = str(user_message or "").strip()
    severity = _normalize_severity(finding.get("severity"))

    if evidence_id:
        finding.setdefault("evidence", []).append(
            {
                "evidence_id": evidence_id,
                "name": finding.get("latest_evidence_name") or "evidence",
                "attached_at": _now_iso(),
            }
        )
        finding["status"] = "resolved"
        return finding

    if _is_vague(message):
        finding["status"] = "probing"
        return finding

    # المخاطر العالية: لا إغلاق بدون دليل
    if severity in {"high", "critical"}:
        finding["status"] = "pending_evidence"
        return finding

    finding["status"] = "resolved"
    return finding


@router.post("/chat", response_model=FinanceBotChatResponse)
async def finance_bot_chat(request: Request, payload: FinanceBotChatRequest):
    """جلسة تدقيق تفاعلية: سؤال واحد فقط + حالة Finding محفوظة في DB."""
    await _require_financial_read(request)

    workshop_id = payload.workshop_id or os.environ.get("DEFAULT_WORKSHOP_ID", "finmodule-sync")
    session_id = payload.session_id or payload.conversation_id or str(uuid.uuid4())
    user_text = (payload.message or "").strip()
    action = str(payload.action or "").strip().lower()

    if not user_text and not action and not payload.evidence_id:
        raise HTTPException(status_code=400, detail="الرسالة مطلوبة")

    session = await _load_session(session_id)
    incoming_findings = _normalize_findings_from_request(payload)

    if not session:
        # fallback Findings من تنبيهات النظام إن لم تصل صراحة
        if not incoming_findings and payload.financial_data and isinstance(payload.financial_data.get("findings"), list):
            incoming_findings = _sort_findings([
                _normalize_finding(f, idx)
                for idx, f in enumerate(payload.financial_data.get("findings") or [])
            ])

        if not incoming_findings:
            # mode fallback: استخدم LLM لكن مع حارس سؤال واحد إجباري
            chat = _get_llm_chat(session_id)
            context_parts = []
            if payload.account_code:
                account_context = await _build_account_context(workshop_id, payload.account_code)
                if account_context:
                    context_parts.append(account_context)
            if payload.financial_data:
                context_parts.append(build_financial_context(payload.financial_data))
            # 🛡️ Always include firewall context (live snapshot)
            try:
                firewall_ctx = await build_firewall_context(workshop_id)
                if firewall_ctx:
                    context_parts.append(firewall_ctx)
            except Exception:
                pass

            full_text = user_text
            if context_parts:
                context_joined = "\n\n".join(context_parts)
                full_text = f"سياق:\n{context_joined}\n\nرسالة المستخدم:\n{user_text}\n\nأعطني سؤال تدقيق واحد فقط."

            try:
                ai_response = await chat.send_message(UserMessage(text=full_text))
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"تعذّر الاتصال بالمساعد المالي: {e}")

            one_q = _enforce_single_question(ai_response)
            return FinanceBotChatResponse(
                response=one_q,
                conversation_id=session_id,
                session_id=session_id,
                finding_id=None,
                finding_status="probing",
                timestamp=datetime.now().isoformat(),
            )

        session = {
            "session_id": session_id,
            "workshop_id": workshop_id,
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "closed_count": 0,
            "findings": incoming_findings,
        }

    findings = session.get("findings") or []
    if not findings:
        raise HTTPException(status_code=400, detail="لا توجد Findings متاحة لبدء جلسة التدقيق.")

    if action and action not in INTERACTIVE_ACTIONS:
        raise HTTPException(status_code=400, detail="إجراء غير مدعوم")

    active = _first_open_finding(findings)
    if not active and not action:
        done_message = "تم إغلاق كل الملاحظات الحالية. يمكنك بدء دورة تدقيق جديدة."
        return FinanceBotChatResponse(
            response=done_message,
            conversation_id=session_id,
            session_id=session_id,
            finding_id=None,
            finding_status="resolved",
            state="resolved",
            interactive={"enabled": False, "actions": []},
            timestamp=datetime.now().isoformat(),
        )

    target_finding = _find_finding_by_id(findings, payload.target_finding_id) if action else active
    if target_finding is None:
        target_finding = active

    if target_finding is None:
        raise HTTPException(status_code=400, detail="لا توجد ملاحظة نشطة لمعالجة الطلب")

    target_finding.setdefault("history", []).append(
        {
            "role": "user",
            "text": user_text,
            "at": _now_iso(),
            "evidence_id": payload.evidence_id,
            "action": action or None,
        }
    )
    if payload.evidence_name:
        target_finding["latest_evidence_name"] = payload.evidence_name

    reply_text = ""

    if action == "open_investigation":
        reply_text, target_finding = await _enriched_open_investigation(
            target_finding, session, workshop_id, payload.financial_data
        )

    elif action == "apply_suggested_fix":
        if not target_finding.get("suggested_fix"):
            target_finding["suggested_fix"] = _pick_single_suggestion(target_finding)
        target_finding["applied_fix"] = target_finding.get("suggested_fix") or "manual_fix_applied"

        if _normalize_severity(target_finding.get("severity")) in {"high", "critical"} and not payload.evidence_id:
            target_finding["status"] = "pending_evidence"
            reply_text = _pending_evidence_message(target_finding)
        else:
            target_finding["status"] = "resolved"
            target_finding["resolved_at"] = _now_iso()
            session["closed_count"] = int(session.get("closed_count") or 0) + 1
            reply_text = "تم تطبيق المعالجة المقترحة وتحديث حالة الملاحظة."

    elif action == "view_evidence":
        evidence = target_finding.get("evidence") or []
        if evidence:
            latest = evidence[-1]
            reply_text = f"آخر مستند مرفوع: {latest.get('name') or latest.get('evidence_id')}."
        else:
            target_finding["status"] = "pending_evidence"
            reply_text = _pending_evidence_message(target_finding)

    elif action == "escalate":
        target_finding["status"] = "escalated"
        target_finding["escalated_at"] = _now_iso()
        reply_text = "تم تصعيد هذه الملاحظة للمراجعة المتقدمة."

    else:
        # التدفق الطبيعي
        if target_finding.get("status") == "open":
            target_finding["status"] = "probing"
            reply_text = _build_next_question(target_finding, ask_evidence=False)
        else:
            _response_state_transition(target_finding, user_text, payload.evidence_id)

            if target_finding.get("status") == "resolved":
                session["closed_count"] = int(session.get("closed_count") or 0) + 1
                target_finding["resolved_at"] = _now_iso()
                next_finding = _first_open_finding(findings)
                if next_finding:
                    next_finding["status"] = "probing"
                    next_finding["question_count"] = int(next_finding.get("question_count") or 0)
                    reply_text = _build_next_question(next_finding, ask_evidence=False)
                    target_finding = next_finding
                else:
                    reply_text = "تم إغلاق كل الملاحظات الحالية. يمكنك بدء دورة تدقيق جديدة."
            elif target_finding.get("status") == "pending_evidence":
                reply_text = _pending_evidence_message(target_finding)
            else:
                reply_text = _build_next_question(target_finding, ask_evidence=False)

    # ─── Auto-Escalation بعد 6 جولات probing بدون حل ───────────────────
    q_count = int(target_finding.get("question_count") or 0) if isinstance(target_finding, dict) else 0
    if (
        isinstance(target_finding, dict)
        and target_finding.get("status") == "probing"
        and q_count >= 5
        and _normalize_severity(target_finding.get("severity")) in {"high", "critical"}
    ):
        target_finding["status"] = "escalated"
        target_finding["escalated_at"] = _now_iso()
        target_finding["auto_escalated"] = True
        reply_text = (
            "⚠️ تم التصعيد التلقائي: تجاوزت هذه الملاحظة 6 جولات تحقيق بدون حل."
            " سيتم توليد تقرير تصعيد كامل. يمكنك مراجعته عبر زر «تقرير التصعيد»."
        )

    # لا نزيد عداد الأسئلة إلا عند probing
    if isinstance(target_finding, dict) and target_finding.get("status") == "probing":
        target_finding["question_count"] = q_count + 1
        reply_text = _enforce_single_question(reply_text)

    target_finding.setdefault("history", []).append(
        {"role": "assistant", "text": reply_text, "at": _now_iso(), "state": target_finding.get("status")}
    )

    await _save_session(session)

    return FinanceBotChatResponse(
        response=reply_text,
        conversation_id=session_id,
        session_id=session_id,
        finding_id=target_finding.get("finding_id") if isinstance(target_finding, dict) else None,
        finding_status=target_finding.get("status") if isinstance(target_finding, dict) else "probing",
        state=target_finding.get("status") if isinstance(target_finding, dict) else "probing",
        interactive=_build_interactive_card(target_finding),
        linked_data=target_finding.get("linked_data") if isinstance(target_finding, dict) else None,
        contradictions=target_finding.get("contradictions") if isinstance(target_finding, dict) else None,
        auto_escalated=target_finding.get("auto_escalated") if isinstance(target_finding, dict) else None,
        timestamp=datetime.now().isoformat(),
    )


# ═══════════════════════════════════════════════════════════════════════════
# 1. AUTO-LINKING ENGINE
# ربط الملاحظة تلقائياً بالقيود والعمليات الفعلية
# ═══════════════════════════════════════════════════════════════════════════

async def _auto_link_finding(
    finding: Dict[str, Any],
    workshop_id: str,
    days_back: int = 90,
) -> Dict[str, Any]:
    """
    يجلب القيود المحاسبية والعمليات المرتبطة بالملاحظة تلقائياً.
    Returns: {journal_entries, operations, accounts_involved, summary_text}
    """
    result: Dict[str, Any] = {
        "journal_entries": [],
        "operations": [],
        "accounts_involved": [],
        "summary_text": "",
    }
    if not supabase:
        return result

    account_code = str(finding.get("account_code") or finding.get("account") or "").strip()
    amount = float(finding.get("actual_value") or finding.get("amount") or 0)
    date_from = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")

    try:
        # جلب قيود اليومية المرتبطة بالحساب
        je_res = (
            supabase.table("journal_entries")
            .select("id, date, description, lines, reference_id, workshop_id")
            .eq("workshop_id", workshop_id)
            .gte("date", date_from)
            .order("date", desc=True)
            .limit(200)
            .execute()
        )
        all_entries = je_res.data or []

        matched_entries = []
        accounts_seen: Dict[str, str] = {}
        for entry in all_entries:
            for line in (entry.get("lines") or []):
                line_acc = str(line.get("account") or line.get("account_code") or "")
                line_name = str(line.get("account_name") or line_acc)
                # ربط بالحساب المذكور في الملاحظة
                acc_match = account_code and (
                    line_acc == account_code
                    or line_acc.startswith(account_code)
                    or account_code.startswith(line_acc)
                )
                # ربط بالمبلغ (هامش ±10%)
                line_amt = float(line.get("debit") or line.get("credit") or 0)
                amt_match = amount > 0 and abs(line_amt - amount) / max(amount, 1) < 0.12
                if acc_match or amt_match:
                    matched_entries.append({
                        "id": entry.get("id"),
                        "date": entry.get("date"),
                        "description": entry.get("description"),
                        "account": line_acc,
                        "account_name": line_name,
                        "debit": line.get("debit", 0),
                        "credit": line.get("credit", 0),
                        "reference_id": entry.get("reference_id"),
                    })
                    accounts_seen[line_acc] = line_name
                    break  # واحد لكل قيد

        result["journal_entries"] = matched_entries[:10]
        result["accounts_involved"] = [
            {"code": k, "name": v} for k, v in list(accounts_seen.items())[:8]
        ]

        # جلب العمليات المرتبطة (تاريخياً)
        ops_res = (
            supabase.table("operations")
            .select("id, date, type, total, payment_method, partner_name, notes, items")
            .eq("workshop_id", workshop_id)
            .gte("date", date_from)
            .order("date", desc=True)
            .limit(200)
            .execute()
        )
        all_ops = ops_res.data or []
        matched_ops = []
        for op in all_ops:
            op_total = float(op.get("total") or 0)
            # ربط بالمبلغ (هامش ±10%)
            if amount > 0 and abs(op_total - amount) / max(amount, 1) < 0.15:
                matched_ops.append({
                    "id": op.get("id"),
                    "date": op.get("date"),
                    "type": op.get("type"),
                    "total": op_total,
                    "payment_method": op.get("payment_method") or op.get("paymentMethod"),
                    "partner_name": op.get("partner_name") or op.get("partnerName"),
                })
        result["operations"] = matched_ops[:5]

    except Exception as e:
        print(f"auto_link_finding error: {e}")

    # نص ملخص للمدقق
    parts = []
    if result["journal_entries"]:
        parts.append(f"عثر على {len(result['journal_entries'])} قيد مرتبط.")
    if result["operations"]:
        parts.append(f"عثر على {len(result['operations'])} عملية مطابقة.")
    if result["accounts_involved"]:
        names = [a["name"] for a in result["accounts_involved"][:3]]
        parts.append(f"الحسابات المرتبطة: {', '.join(names)}.")
    result["summary_text"] = " ".join(parts) if parts else "لم يُعثر على قيود أو عمليات مرتبطة مباشرة."

    return result


@router.post("/auto-link")
async def auto_link_endpoint(request: Request, payload: Dict[str, Any]):
    """
    يربط ملاحظة تدقيق بالقيود والعمليات الفعلية تلقائياً.
    Body: {finding: {...}, workshop_id: str, days_back: int}
    """
    await _require_financial_read(request)
    finding = payload.get("finding") or {}
    workshop_id = str(payload.get("workshop_id") or "finmodule-sync")
    days_back = int(payload.get("days_back") or 90)
    linked = await _auto_link_finding(finding, workshop_id, days_back)
    return {"success": True, "data": linked}


# ═══════════════════════════════════════════════════════════════════════════
# 2. CONTRADICTION ENGINE
# كشف التناقضات بين تفسير المستخدم والبيانات الفعلية
# ═══════════════════════════════════════════════════════════════════════════

def _contradiction_score(expected: float, actual: float) -> float:
    """حساب درجة التناقض (0-1). كلما اقترب من 1 كان التناقض أشد."""
    if expected == 0 and actual == 0:
        return 0.0
    denom = max(abs(expected), abs(actual), 1.0)
    return min(abs(expected - actual) / denom, 1.0)


async def _detect_contradictions(
    findings: List[Dict[str, Any]],
    workshop_id: str,
    financial_data: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    يكشف التناقضات بين الملاحظات والبيانات الفعلية.
    يفحص:
    1. قائمة الدخل (income-statement) مقابل ملاحظات الإيراد
    2. ميزان المراجعة مقابل ملاحظات الأصول/الخصوم
    3. تناقضات داخلية بين الملاحظات (finding A vs finding B)
    """
    contradictions: List[Dict[str, Any]] = []

    # --- فحص 1: قائمة الدخل المسجّلة مقابل الملاحظات ---
    if financial_data:
        recorded_revenue = float(
            (financial_data.get("totals") or {}).get("revenue")
            or financial_data.get("revenue")
            or 0
        )

        for f in findings:
            ftype = str(f.get("type") or f.get("category") or "").lower()
            title = str(f.get("title") or "").lower()
            claimed = float(f.get("expected_value") or f.get("expected_range") or f.get("expected") or 0)

            if "إيراد" in title or "revenue" in ftype:
                if claimed > 0 and recorded_revenue > 0:
                    score = _contradiction_score(claimed, recorded_revenue)
                    if score > 0.15:
                        contradictions.append({
                            "finding_id": f.get("finding_id"),
                            "type": "revenue_mismatch",
                            "description": (
                                f"الملاحظة تشير لإيراد {claimed:,.0f} ر.س "
                                f"بينما قائمة الدخل تسجّل {recorded_revenue:,.0f} ر.س "
                                f"(فرق {abs(claimed-recorded_revenue):,.0f} ر.س)."
                            ),
                            "expected": claimed,
                            "actual": recorded_revenue,
                            "delta": recorded_revenue - claimed,
                            "score": round(score, 3),
                            "severity": "high" if score > 0.4 else "medium",
                        })

    # --- فحص 2: تناقضات داخلية بين الملاحظات ---
    account_findings: Dict[str, List[Dict]] = {}
    for f in findings:
        acc = str(f.get("account_code") or f.get("account") or "")
        if acc:
            account_findings.setdefault(acc, []).append(f)

    for acc, acc_findings in account_findings.items():
        if len(acc_findings) < 2:
            continue
        amounts = [float(f.get("actual_value") or f.get("amount") or 0) for f in acc_findings]
        if max(amounts) > 0 and _contradiction_score(min(amounts), max(amounts)) > 0.3:
            contradictions.append({
                "finding_id": None,
                "type": "inter_finding_conflict",
                "description": (
                    f"ملاحظتان متضاربتان على الحساب {acc}: "
                    f"قيم {amounts[0]:,.0f} و{amounts[1]:,.0f} ر.س."
                ),
                "account": acc,
                "expected": amounts[0],
                "actual": amounts[1],
                "delta": amounts[1] - amounts[0],
                "score": round(_contradiction_score(amounts[0], amounts[1]), 3),
                "severity": "medium",
            })

    # --- فحص 3: Findings بقيمة 0 لكن وصفها يشير لمبالغ ---
    for f in findings:
        actual = float(f.get("actual_value") or 0)
        title = str(f.get("title") or "")
        # نص يذكر مبالغ (أرقام) لكن actual_value = 0
        has_number_in_title = bool(re.search(r"\d[\d,\.]+", title))
        if actual == 0 and has_number_in_title:
            amount_in_title = re.findall(r"\d[\d,\.]+", title)
            contradictions.append({
                "finding_id": f.get("finding_id"),
                "type": "zero_value_with_description",
                "description": (
                    f"الملاحظة تصف مبلغاً ({', '.join(amount_in_title[:2])}) "
                    "لكن القيمة المسجّلة صفر — قد يكون هناك قيد ناقص أو غير مكتمل."
                ),
                "expected": 0,
                "actual": 0,
                "delta": 0,
                "score": 0.5,
                "severity": "medium",
            })

    # ترتيب حسب درجة التناقض
    contradictions.sort(key=lambda x: x.get("score", 0), reverse=True)
    return contradictions


@router.post("/detect-contradictions")
async def detect_contradictions_endpoint(request: Request, payload: Dict[str, Any]):
    """
    يكشف التناقضات في مجموعة findings مقارنةً بالبيانات المالية.
    Body: {findings: [...], workshop_id: str, financial_data: {...}}
    """
    await _require_financial_read(request)
    raw_findings = payload.get("findings") or []
    workshop_id = str(payload.get("workshop_id") or "finmodule-sync")
    financial_data = payload.get("financial_data") or {}
    findings = [_normalize_finding(f, i) for i, f in enumerate(raw_findings)]
    contradictions = await _detect_contradictions(findings, workshop_id, financial_data)
    return {
        "success": True,
        "data": {
            "contradictions": contradictions,
            "count": len(contradictions),
            "has_critical": any(c.get("severity") == "critical" for c in contradictions),
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
# 3. ESCALATION WORKFLOW
# تقرير التصعيد الشامل عند التصعيد
# ═══════════════════════════════════════════════════════════════════════════

def _build_escalation_report(
    session: Dict[str, Any],
    contradictions: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """يبني تقرير تصعيد شامل من بيانات الجلسة."""
    findings = session.get("findings") or []
    escalated = [f for f in findings if f.get("status") == "escalated"]
    resolved = [f for f in findings if f.get("status") == "resolved"]
    open_count = len([f for f in findings if f.get("status") not in {"resolved", "escalated"}])

    report_lines = [
        "تقرير التصعيد المحاسبي",
        f"الجلسة: {session.get('session_id', '—')}",
        f"الورشة: {session.get('workshop_id', '—')}",
        f"التاريخ: {_now_iso()[:10]}",
        "─" * 40,
        f"الملاحظات المصعّدة : {len(escalated)}",
        f"الملاحظات المغلقة : {len(resolved)}",
        f"الملاحظات المفتوحة: {open_count}",
    ]

    if escalated:
        report_lines.append("\nتفاصيل الملاحظات المصعّدة:")
        for f in escalated:
            history = f.get("history") or []
            user_msgs = [h.get("text", "") for h in history if h.get("role") == "user" and h.get("text")]
            evidence = f.get("evidence") or []
            report_lines.append(f"  [{_normalize_severity(f.get('severity'))}] {f.get('title', '—')}")
            if f.get("actual_value"):
                report_lines.append(f"    المبلغ المرصود: {f.get('actual_value'):,.2f} ر.س")
            if f.get("suggested_fix"):
                report_lines.append(f"    الإجراء المقترح: {f.get('suggested_fix')}")
            if user_msgs:
                report_lines.append(f"    توضيح المستخدم: «{user_msgs[-1][:120]}»")
            if evidence:
                report_lines.append(f"    مستندات مرفوعة: {len(evidence)}")
            report_lines.append(f"    تصعيد في: {f.get('escalated_at', '—')[:16]}")

    if contradictions:
        report_lines.append(f"\nالتناقضات المرصودة: {len(contradictions)}")
        for c in contradictions[:5]:
            report_lines.append(f"  • {c.get('description', '')[:100]}")

    report_lines.append("\nتوصية: راجع الملاحظات المصعّدة مع المحاسب القانوني وتأكد من رفع المستندات الداعمة.")

    return {
        "session_id": session.get("session_id"),
        "generated_at": _now_iso(),
        "escalated_count": len(escalated),
        "resolved_count": len(resolved),
        "open_count": open_count,
        "has_contradictions": bool(contradictions),
        "report_text": "\n".join(report_lines),
        "escalated_findings": escalated,
        "contradictions": contradictions or [],
    }


@router.get("/sessions/{session_id}/report")
async def get_escalation_report(
    session_id: str,
    workshop_id: str = Query("finmodule-sync"),
):
    """يولّد تقرير التصعيد الكامل لجلسة تدقيق."""
    session = await _load_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="الجلسة غير موجودة")
    findings = session.get("findings") or []
    financial_data: Dict[str, Any] = {}
    contradictions = await _detect_contradictions(findings, workshop_id, financial_data)
    report = _build_escalation_report(session, contradictions)
    return {"success": True, "data": report}


# ═══════════════════════════════════════════════════════════════════════════
# ENHANCED CHAT: Auto-Link + Contradiction inline in open_investigation
# ═══════════════════════════════════════════════════════════════════════════

async def _enriched_open_investigation(
    finding: Dict[str, Any],
    session: Dict[str, Any],
    workshop_id: str,
    financial_data: Optional[Dict[str, Any]],
) -> Tuple[str, Dict[str, Any]]:
    """
    يُنفّذ open_investigation بشكل مُثرى:
    1. يربط القيود والعمليات تلقائياً
    2. يكشف التناقضات
    3. يُضمّن ملخص النتائج في السؤال
    """
    if finding.get("status") in {"open", "pending_evidence"}:
        finding["status"] = "probing"
    if not finding.get("category"):
        finding["category"] = _detect_category(finding)
    if not finding.get("suggested_fix"):
        finding["suggested_fix"] = _pick_single_suggestion(finding)

    # Auto-linking
    linked = await _auto_link_finding(finding, workshop_id)
    finding["linked_data"] = linked

    # Contradictions
    all_findings = session.get("findings") or [finding]
    contradictions = await _detect_contradictions(all_findings, workshop_id, financial_data)
    finding["contradictions"] = contradictions

    base_question = _build_next_question(finding, ask_evidence=False)
    extras = []
    if linked["journal_entries"]:
        extras.append(f"[مرتبط بـ {len(linked['journal_entries'])} قيد يومية]")
    if contradictions:
        c = contradictions[0]
        extras.append(f"⚠️ تناقض: {c['description'][:80]}")

    reply = f"{base_question}"
    if extras:
        reply = f"{base_question}\n\n{'  '.join(extras)}"

    return reply, finding
