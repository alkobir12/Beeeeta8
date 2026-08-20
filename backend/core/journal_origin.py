"""باني الإسناد (Origin Resolver) — يحدد «من فعل هذا؟» لكل قيد محاسبي.

قواعد صارمة (قرار المالك):
- المنشئ يؤخذ من دليل موثق فقط: journal_attribution ← accounting_audit.actor ← أدلة كاترينا.
- قيد كاترينا لا يُنسب لمستخدم إلا إذا كان proposer موثقاً فعلياً.
- بلا دليل → «غير مسجل — قيد تاريخي». ممنوع تخمين admin/system.
- مُرحِّل القيد دائماً النظام المحاسبي (نمط الكاتب الوحيد).
- قراءة فقط — لا تعديل على أي قيد تاريخي.
"""
import json
import os
from typing import Any, Dict, List, Optional

_USERS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads", "users.json")
_users_cache: Dict[str, Any] = {"mtime": None, "by_id": {}, "by_username": {}}

ROLE_LABELS_AR = {
    "admin": "مدير نظام",
    "manager": "مدير",
    "supervisor": "مشرف",
    "accountant": "محاسب",
    "technician": "فني",
    "employee": "موظف",
}

SYSTEM_ACTOR_LABELS = {
    "p0e_cleanup_approved_by_owner": "صيانة نظام — معتمدة من المالك",
}

_CHANNEL_BY_SOURCE = {
    "smart_pos": "نقاط البيع",
    "pos_template": "نقاط البيع",
    "pos_instant_sale": "نقاط البيع",
    "operation": "عملية",
    "operation_payment": "عملية",
    "operation_rakan_parts": "عملية",
    "supplier_balance_payment": "سداد مورد",
    "ajel_supplier_purchase": "عملية موردين",
    "vehicle_visit": "ملف مركبة",
    "unified_visit_payment": "ملف مركبة",
    "visit_receipt_voucher": "ملف مركبة",
    "manual": "إدخال يدوي",
    "reversal": "قيد عكسي",
    "period_close": "إقفال فترة",
    "historical_financial_repair": "صيانة نظام",
    "hist_vehicle_ar_repair": "صيانة نظام",
    "active_vehicle_ar_repair": "صيانة نظام",
    "fin_engine_align_v1": "صيانة نظام",
    "financial_reset_opening_receivable": "بدء مالي",
    "archived_financial_period": "فترة مؤرشفة",
}

UNRECORDED_HISTORICAL = "غير مسجل — قيد تاريخي"
POSTER_LABEL = "النظام المحاسبي (المحرك الموحد)"


def _load_users():
    try:
        mtime = os.path.getmtime(_USERS_FILE)
        if _users_cache["mtime"] == mtime:
            return _users_cache["by_id"], _users_cache["by_username"]
        with open(_USERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        users = data if isinstance(data, list) else (data.get("users") or [])
        by_id, by_username = {}, {}
        for u in users:
            if not isinstance(u, dict):
                continue
            uid = str(u.get("id") or "").strip()
            uname = str(u.get("username") or u.get("name") or "").strip()
            if uid:
                by_id[uid] = u
            if uname:
                by_username[uname] = u
        _users_cache.update({"mtime": mtime, "by_id": by_id, "by_username": by_username})
        return by_id, by_username
    except Exception:
        return _users_cache["by_id"], _users_cache["by_username"]


def _mongo_db():
    from core.accounting_engine import get_engine
    return get_engine().identity.collection().database


def _user_label(name: str, role: Optional[str]) -> str:
    role_ar = ROLE_LABELS_AR.get(str(role or "").strip().lower())
    return f"{name} ({role_ar})" if role_ar else str(name)


def _enrich_username(username: str, by_username: Dict[str, Any]) -> str:
    u = by_username.get(username)
    if u:
        return _user_label(u.get("name") or u.get("username") or username, u.get("role"))
    return username


def _compose(source: str, katrina: Optional[Dict[str, Any]], attr: Optional[Dict[str, Any]],
             audit_actor: Optional[str], by_id: Dict[str, Any], by_username: Dict[str, Any]) -> Dict[str, Any]:
    channel = _CHANNEL_BY_SOURCE.get(source, "أخرى")
    if katrina:
        channel = "كاترينا"
        draft = katrina.get("draft") or {}
        requested_by = str(draft.get("requested_by") or draft.get("proposer") or "").strip()
        if requested_by:
            creator_label = f"كاترينا بالنيابة عن {requested_by}"
        else:
            creator_label = "كاترينا — المنشئ غير مسجل"
        creator_kind = "katrina"
        committer = str((katrina.get("execution") or {}).get("committer") or "").strip()
        approval = katrina.get("approval") or {}
        approver = committer or str(approval.get("approver") or "").strip()
        if approver == "auto:policy":
            approver_label = "اعتماد تلقائي حسب السياسة"
        elif approver:
            approver_label = _enrich_username(approver, by_username)
        else:
            approver_label = "غير مسجل"
    else:
        if attr and attr.get("username"):
            uname = str(attr["username"])
            role = attr.get("role") or (by_username.get(uname) or {}).get("role")
            creator_label = _user_label((by_username.get(uname) or {}).get("name") or uname, role)
            creator_kind = "user"
        elif audit_actor:
            u = by_id.get(audit_actor) or by_username.get(audit_actor)
            if u:
                creator_label = _user_label(u.get("name") or u.get("username") or audit_actor, u.get("role"))
                creator_kind = "user"
            elif audit_actor in SYSTEM_ACTOR_LABELS:
                creator_label = SYSTEM_ACTOR_LABELS[audit_actor]
                creator_kind = "system"
            else:
                creator_label = "إجراء نظامي — غير منسوب لمستخدم"
                creator_kind = "system"
        else:
            creator_label = UNRECORDED_HISTORICAL
            creator_kind = "unknown"
        approver_label = "لا يتطلب اعتماد (إجراء مباشر)" if creator_kind == "user" else "غير مسجل"

    return {
        "creator_label": creator_label,
        "creator_kind": creator_kind,
        "approver_label": approver_label,
        "poster_label": POSTER_LABEL,
        "channel_label": channel,
    }


def resolve_origins(entries: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """حلّ إسناد دفعي (Batch) لقائمة قيود — 4 استعلامات Mongo كحد أقصى، بلا N+1."""
    ids = [str(e.get("id") or "") for e in entries if e.get("id")]
    if not ids:
        return {}
    refs = list({str(e.get("reference_id") or "").strip() for e in entries if str(e.get("reference_id") or "").strip()})
    db = _mongo_db()

    attribution: Dict[str, Dict[str, Any]] = {}
    try:
        for doc in db["journal_attribution"].find({"journal_id": {"$in": ids}}):
            attribution[str(doc.get("journal_id"))] = doc
    except Exception:
        pass

    audit_actor: Dict[str, str] = {}
    try:
        for doc in db["accounting_audit"].find(
            {"event": "JOURNAL_POSTED", "journal_id": {"$in": ids}, "actor": {"$nin": [None, ""]}}
        ):
            audit_actor.setdefault(str(doc.get("journal_id")), str(doc.get("actor")))
    except Exception:
        pass

    katrina_by_journal: Dict[str, Dict[str, Any]] = {}
    katrina_by_ref: Dict[str, Dict[str, Any]] = {}
    try:
        or_clauses: List[Dict[str, Any]] = [{"result.journal_id": {"$in": ids}}]
        if refs:
            or_clauses.append({"result.operation_id": {"$in": refs}})
        execs = list(db["assistant_executions"].find({"$or": or_clauses}))
        draft_ids = list({str(e.get("draft_id")) for e in execs if e.get("draft_id")})
        drafts: Dict[str, Dict[str, Any]] = {}
        approvals: Dict[str, Dict[str, Any]] = {}
        if draft_ids:
            for d in db["assistant_drafts"].find({"$or": [{"draft_id": {"$in": draft_ids}}, {"id": {"$in": draft_ids}}]}):
                drafts[str(d.get("draft_id") or d.get("id"))] = d
            for a in db["assistant_approvals"].find(
                {"draft_id": {"$in": draft_ids}, "status": {"$in": ["approved", "executed"]}}
            ):
                approvals[str(a.get("draft_id"))] = a
        for ex in execs:
            d_id = str(ex.get("draft_id") or "")
            evidence = {"execution": ex, "draft": drafts.get(d_id), "approval": approvals.get(d_id)}
            result = ex.get("result") if isinstance(ex.get("result"), dict) else {}
            jid = str(result.get("journal_id") or "")
            opid = str(result.get("operation_id") or "")
            if jid:
                katrina_by_journal[jid] = evidence
            if opid:
                katrina_by_ref[opid] = evidence
    except Exception:
        pass

    by_id, by_username = _load_users()

    origins: Dict[str, Dict[str, Any]] = {}
    for e in entries:
        jid = str(e.get("id") or "")
        if not jid:
            continue
        source = str(e.get("source") or "").strip().lower()
        ref = str(e.get("reference_id") or "").strip()
        evidence = katrina_by_journal.get(jid) or (katrina_by_ref.get(ref) if ref else None)
        origins[jid] = _compose(source, evidence, attribution.get(jid), audit_actor.get(jid), by_id, by_username)
    return origins
