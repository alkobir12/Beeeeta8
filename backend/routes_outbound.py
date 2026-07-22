"""القنوات الصادرة — PDF وواتساب (قوالب رسائل ثابتة + بصمة/كاش المخرجات + سجل تدقيق صارم).

قواعد حاكمة:
- البصمة (SHA-256) تُحسب وتُتحقق في الخلفية حصراً من مواد مثبتة (whitelist).
- سجل التدقيق يسجل حالات دقيقة فقط — ممنوع sent/delivered/read بدون مزود رسمي.
- صيغة المتغيرات هي الصيغة الموحدة الموجودة {{VAR_NAME}} — لا صيغة جديدة.
"""

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth_jwt import get_current_user
from core import llm_traces

router = APIRouter(prefix="/api/outbound", tags=["outbound"])

db = None
_ready = False

MAX_PDF_B64 = 20_000_000
MAX_IMG_B64 = 6_000_000
MAX_MESSAGE_LEN = 4000

KNOWN_STATUSES = {"draft", "unpaid", "partial", "paid", "deferred", "cancelled", "superseded", "*"}
BLOCKED_SHARE_STATUSES = {"superseded"}

STATUS_AR_TO_EN = {
    "مسودة": "draft", "غير مدفوعة": "unpaid", "مدفوعة جزئياً": "partial",
    "مدفوعة": "paid", "آجلة": "deferred", "ملغي": "cancelled", "ملغاة": "cancelled",
    "مستبدل": "superseded", "canceled": "cancelled",
}
STATUS_LABELS_AR = {
    "draft": "مسودة", "unpaid": "غير مدفوعة", "partial": "مدفوعة جزئياً",
    "paid": "مدفوعة", "deferred": "آجلة", "cancelled": "ملغي", "superseded": "مستبدل",
}

MESSAGE_VARIABLES = {
    "WORKSHOP_NAME": "اسم الورشة",
    "WORKSHOP_PHONE": "جوال الورشة",
    "WORKSHOP_ADDRESS": "عنوان الورشة",
    "COMPANY_CR": "السجل التجاري",
    "COMPANY_TAX": "الرقم الضريبي",
    "CUSTOMER_NAME": "اسم العميل",
    "CUSTOMER_PHONE": "جوال العميل",
    "VEHICLE_INFO": "المركبة",
    "PLATE_NO": "رقم اللوحة",
    "INVOICE_NO": "رقم المستند",
    "DATE": "التاريخ",
    "STATUS_LABEL": "حالة المستند",
    "SUBTOTAL": "المجموع قبل الخصم",
    "DISCOUNT": "الخصم",
    "TAX": "الضريبة",
    "TOTAL": "الإجمالي",
    "PAID": "المدفوع",
    "REMAINING": "المتبقي",
    "AMOUNT_WORDS": "المبلغ كتابةً",
    "SEAL_CODE": "الختم الإلكتروني",
    "DOC_TYPE_LABEL": "نوع المستند",
}

DOC_TYPE_LABELS = {"invoice": "فاتورة", "diagnosis": "تقرير تشخيص", "quote": "عرض سعر", "receipt": "سند زيارة"}

ALLOWED_EVENTS = {
    "message_prepared", "pdf_generated", "preview_image_generated", "cache_hit",
    "share_sheet_opened", "whatsapp_opened", "files_downloaded", "text_copied",
    "user_cancelled", "prepare_failed", "phone_saved_to_customer",
}
FORBIDDEN_EVENTS = {"sent", "delivered", "read", "seen", "message_sent", "whatsapp_sent"}

_MATERIAL_KEYS = [
    "tenant_id", "branch_id", "document_id", "document_number", "document_version",
    "doc_type", "status", "locale", "template_id", "template_version",
    "workshop_snapshot", "customer_snapshot", "vehicle_snapshot",
    "line_items", "totals", "taxes",
]

_VAR_RE = re.compile(r"{{\s*([A-Z_]+)\s*}}")
_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def set_db(database):
    global db
    db = database


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _seed_templates() -> List[Dict[str, Any]]:
    common = "\n— {{WORKSHOP_NAME}} · {{WORKSHOP_PHONE}}"
    seal = "\n🔐 رمز التحقق الإلكتروني: {{SEAL_CODE}}"
    defs = [
        ("invoice_paid", "invoice", ["paid"], "فاتورة مدفوعة",
         "مرحباً {{CUSTOMER_NAME}} 👋\nنشكر لكم زيارتكم {{WORKSHOP_NAME}}.\n\n🧾 فاتورتكم رقم {{INVOICE_NO}} بتاريخ {{DATE}}\n🚗 المركبة: {{VEHICLE_INFO}} — لوحة {{PLATE_NO}}\n💰 الإجمالي: {{TOTAL}}\n✅ الحالة: مدفوعة بالكامل" + seal + "\n\nنسعد بخدمتكم دائماً 🌟" + common),
        ("invoice_partial", "invoice", ["partial"], "فاتورة مدفوعة جزئياً",
         "مرحباً {{CUSTOMER_NAME}} 👋\n\n🧾 فاتورتكم رقم {{INVOICE_NO}} بتاريخ {{DATE}}\n🚗 المركبة: {{VEHICLE_INFO}} — لوحة {{PLATE_NO}}\n💰 الإجمالي: {{TOTAL}}\n💵 المدفوع: {{PAID}}\n⏳ المتبقي: {{REMAINING}}\n\nنأمل التكرم باستكمال سداد المبلغ المتبقي." + seal + common),
        ("invoice_unpaid", "invoice", ["unpaid", "deferred"], "فاتورة غير مدفوعة / آجلة",
         "مرحباً {{CUSTOMER_NAME}} 👋\n\n🧾 فاتورتكم رقم {{INVOICE_NO}} بتاريخ {{DATE}}\n🚗 المركبة: {{VEHICLE_INFO}} — لوحة {{PLATE_NO}}\n💰 الإجمالي المستحق: {{TOTAL}}\n⏳ المتبقي: {{REMAINING}}\n\nنأمل التكرم بسداد المبلغ المستحق في أقرب وقت." + seal + common),
        ("invoice_default", "invoice", ["*"], "فاتورة — عام",
         "مرحباً {{CUSTOMER_NAME}} 👋\n\n🧾 مستندكم رقم {{INVOICE_NO}} ({{STATUS_LABEL}}) بتاريخ {{DATE}}\n🚗 المركبة: {{VEHICLE_INFO}} — لوحة {{PLATE_NO}}\n💰 الإجمالي: {{TOTAL}}" + seal + common),
        ("quote_default", "quote", ["*"], "عرض سعر",
         "مرحباً {{CUSTOMER_NAME}} 👋\n\n📋 عرض السعر رقم {{INVOICE_NO}} بتاريخ {{DATE}}\n🚗 المركبة: {{VEHICLE_INFO}} — لوحة {{PLATE_NO}}\n💰 إجمالي العرض: {{TOTAL}}\n\nالعرض ساري لمدة محدودة — بانتظار موافقتكم للبدء بالعمل." + seal + common),
        ("diagnosis_default", "diagnosis", ["*"], "تقرير تشخيص",
         "مرحباً {{CUSTOMER_NAME}} 👋\n\n🔎 تقرير التشخيص رقم {{INVOICE_NO}} بتاريخ {{DATE}}\n🚗 المركبة: {{VEHICLE_INFO}} — لوحة {{PLATE_NO}}\n💰 التكلفة التقديرية: {{TOTAL}}\n\nهذا تقرير تشخيصي فقط — الإصلاح يتطلب موافقتكم." + seal + common),
        ("receipt_default", "receipt", ["*"], "سند زيارة",
         "مرحباً {{CUSTOMER_NAME}} 👋\n\n📄 سند الزيارة رقم {{INVOICE_NO}} بتاريخ {{DATE}}\n🚗 تم استلام المركبة: {{VEHICLE_INFO}} — لوحة {{PLATE_NO}}\n\nسنتواصل معكم فور جاهزية المركبة بإذن الله." + seal + common),
    ]
    now = _now_iso()
    return [
        {
            "id": f"omt-{action_key}",
            "tenant_id": "default",
            "branch_id": None,
            "action_key": action_key,
            "doc_type": doc_type,
            "allowed_statuses": statuses,
            "name": name,
            "body": body,
            "default_body": body,
            "available_variables": sorted(set(_VAR_RE.findall(body))),
            "default_attachments": ["pdf", "image"],
            "allow_edit_before_share": True,
            "enabled": True,
            "version": 1,
            "versions": [],
            "is_seed": True,
            "created_by": "system_seed",
            "created_at": now,
            "updated_at": now,
        }
        for action_key, doc_type, statuses, name, body in defs
    ]


async def _ensure_ready():
    global _ready
    if db is None:
        raise HTTPException(status_code=503, detail="database_unavailable")
    if _ready:
        return
    try:
        await db.outbound_message_templates.create_index(
            [("tenant_id", 1), ("action_key", 1)], unique=True,
            partialFilterExpression={"enabled": True}, name="uniq_active_action_key")
        await db.outbound_message_templates.create_index([("tenant_id", 1), ("doc_type", 1)], name="by_doc_type")
        await db.document_output_assets.create_index(
            [("tenant_id", 1), ("fingerprint", 1)], unique=True, name="uniq_tenant_fingerprint")
        await db.outbound_share_attempts.create_index(
            "idempotency_key", unique=True, sparse=True, name="uniq_idempotency")
        await db.outbound_share_attempts.create_index(
            [("tenant_id", 1), ("document_number", 1), ("created_at", -1)], name="by_document")
        for tpl in _seed_templates():
            await db.outbound_message_templates.update_one(
                {"tenant_id": tpl["tenant_id"], "action_key": tpl["action_key"]},
                {"$setOnInsert": tpl}, upsert=True)
        _ready = True
    except Exception as exc:  # فهرس موجود مسبقاً بمواصفات مطابقة = طبيعي
        if "already exists" in str(exc) or "IndexOptionsConflict" in str(exc):
            _ready = True
        else:
            raise


def _norm_status(value: Optional[str]) -> str:
    raw = str(value or "draft").strip()
    low = raw.lower()
    if low in KNOWN_STATUSES:
        return low
    return STATUS_AR_TO_EN.get(raw, STATUS_AR_TO_EN.get(low, "draft"))


def normalize_phone(raw: Any) -> Dict[str, Any]:
    text = str(raw or "").translate(_AR_DIGITS).strip()
    digits = re.sub(r"\D", "", text)
    e164 = None
    if digits.startswith("00966") and len(digits) == 14:
        e164 = "+" + digits[2:]
    elif digits.startswith("966") and len(digits) == 12:
        e164 = "+" + digits
    elif digits.startswith("05") and len(digits) == 10:
        e164 = "+966" + digits[1:]
    elif digits.startswith("5") and len(digits) == 9:
        e164 = "+966" + digits
    elif text.startswith("+") and 10 <= len(digits) <= 15:
        e164 = "+" + digits
    return {"raw": str(raw or ""), "e164": e164, "wa": e164[1:] if e164 else None, "valid": bool(e164)}


def _canon(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _canon(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))
                if v not in (None, "", [], {})}
    if isinstance(value, list):
        return [_canon(v) for v in value]
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return f"{float(value):.2f}"
    return str(value).strip()


def compute_fingerprint(material: Dict[str, Any]) -> str:
    subset = {k: _canon(material.get(k)) for k in _MATERIAL_KEYS if material.get(k) not in (None, "", [], {})}
    subset["tenant_id"] = str(material.get("tenant_id") or "default")
    canonical = json.dumps(subset, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "fp-" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _money(value: Any) -> str:
    try:
        return f"{float(value or 0):,.2f} ر.س"
    except (TypeError, ValueError):
        return "0.00 ر.س"


def _build_values(doc_type: str, payload: Dict[str, Any]) -> Dict[str, str]:
    settings = payload.get("settings") or {}
    customer = payload.get("customer") or payload.get("client") or {}
    supplier = payload.get("supplier") or {}
    party = customer if customer.get("name") else (supplier if supplier.get("name") else customer)
    vehicle = payload.get("vehicle") or {}
    workshop = payload.get("workshop") or {}
    items = payload.get("items") or []

    subtotal = discount = tax = total = 0.0
    for item in items if isinstance(items, list) else []:
        try:
            qty = float(item.get("quantity") or item.get("qty") or 1)
            price = float(item.get("unit_price") or item.get("price") or item.get("amount") or 0)
            disc = float(item.get("discount") or 0)
            vat_rate = float(item.get("vatRate") or item.get("tax_rate") or item.get("vat") or 0)
        except (TypeError, ValueError):
            continue
        line_sub = qty * price
        after = max(line_sub - disc, 0.0)
        line_tax = round(after * vat_rate) / 100
        subtotal += line_sub
        discount += disc
        tax += line_tax
        total += after + line_tax

    totals_in = settings.get("totals") or payload.get("totals") or {}
    payment = payload.get("payment") or {}
    try:
        paid = float(totals_in.get("paid") or payment.get("paid") or 0)
    except (TypeError, ValueError):
        paid = 0.0
    remaining = total - paid

    doc_number = str(settings.get("document_number") or payload.get("document_number") or "")
    date_str = str(settings.get("date") or payload.get("date") or _now_iso()[:10])
    status = _norm_status(settings.get("status") or payload.get("status"))
    vehicle_info = " ".join(str(vehicle.get(k) or "") for k in ("brand", "model", "year")).strip()

    return {
        "WORKSHOP_NAME": str(workshop.get("name") or workshop.get("business_name") or "الورشة"),
        "WORKSHOP_PHONE": str(workshop.get("phone") or workshop.get("whatsapp") or ""),
        "WORKSHOP_ADDRESS": str(workshop.get("address") or ""),
        "COMPANY_CR": str(workshop.get("commercial_register") or workshop.get("commercialRegister") or ""),
        "COMPANY_TAX": str(workshop.get("tax_number") or workshop.get("taxNumber") or ""),
        "CUSTOMER_NAME": str(party.get("name") or party.get("customerName") or "عميلنا العزيز"),
        "CUSTOMER_PHONE": str(party.get("phone") or party.get("customerPhone") or ""),
        "VEHICLE_INFO": vehicle_info,
        "PLATE_NO": str(vehicle.get("plateNumber") or vehicle.get("plate") or ""),
        "INVOICE_NO": doc_number,
        "DATE": date_str,
        "STATUS_LABEL": STATUS_LABELS_AR.get(status, status),
        "SUBTOTAL": _money(subtotal),
        "DISCOUNT": _money(discount),
        "TAX": _money(tax),
        "TOTAL": _money(total),
        "PAID": _money(paid),
        "REMAINING": _money(remaining),
        "AMOUNT_WORDS": f"فقط {_money(total)} لا غير",
        "SEAL_CODE": str(settings.get("seal_code") or ""),
        "DOC_TYPE_LABEL": DOC_TYPE_LABELS.get(doc_type, "مستند"),
    }


def _resolve_body(body: str, values: Dict[str, str]):
    missing = []

    def _sub(match):
        key = match.group(1)
        val = values.get(key, "")
        if not str(val).strip():
            missing.append(key)
            return ""
        return str(val)

    return _VAR_RE.sub(_sub, body or ""), sorted(set(missing))


def _tpl_public(tpl: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in tpl.items() if k not in ("_id",)}


def _identity(user: dict) -> str:
    return str(user.get("username") or "unknown")


# ============ قوالب الرسائل الصادرة ============

class TemplateUpdateBody(BaseModel):
    name: Optional[str] = None
    body: Optional[str] = None
    action_key: Optional[str] = None
    allowed_statuses: Optional[List[str]] = None
    default_attachments: Optional[List[str]] = None
    allow_edit_before_share: Optional[bool] = None
    enabled: Optional[bool] = None
    tenant_id: Optional[str] = "default"


@router.get("/variables")
async def get_variables(user: dict = Depends(get_current_user)):
    await _ensure_ready()
    return {"success": True, "variables": [{"key": k, "label": v} for k, v in MESSAGE_VARIABLES.items()]}


@router.get("/templates")
async def list_templates(doc_type: Optional[str] = None, tenant_id: str = "default",
                         user: dict = Depends(get_current_user)):
    await _ensure_ready()
    query: Dict[str, Any] = {"tenant_id": tenant_id}
    if doc_type:
        query["doc_type"] = doc_type
    rows = await db.outbound_message_templates.find(query, {"_id": 0}).to_list(200)
    rows.sort(key=lambda r: (r.get("doc_type", ""), r.get("action_key", "")))
    return {"success": True, "templates": rows}


@router.put("/templates/{template_id}")
async def update_template(template_id: str, payload: TemplateUpdateBody,
                          user: dict = Depends(get_current_user)):
    await _ensure_ready()
    tenant = payload.tenant_id or "default"
    tpl = await db.outbound_message_templates.find_one({"id": template_id, "tenant_id": tenant})
    if not tpl:
        raise HTTPException(status_code=404, detail="template_not_found")

    updates: Dict[str, Any] = {}
    if payload.body is not None:
        body = payload.body.strip()
        if not body:
            raise HTTPException(status_code=422, detail={"code": "empty_body", "message": "نص الرسالة لا يمكن أن يكون فارغاً"})
        unknown = sorted(set(_VAR_RE.findall(body)) - set(MESSAGE_VARIABLES))
        if unknown:
            raise HTTPException(status_code=422, detail={
                "code": "unknown_variables", "unknown_variables": unknown,
                "message": f"متغيرات غير معروفة: {', '.join(unknown)}"})
        updates["body"] = body
        updates["available_variables"] = sorted(set(_VAR_RE.findall(body)))
    if payload.name is not None:
        if not payload.name.strip():
            raise HTTPException(status_code=422, detail={"code": "empty_name", "message": "اسم القالب مطلوب"})
        updates["name"] = payload.name.strip()
    if payload.allowed_statuses is not None:
        statuses = [s.strip().lower() for s in payload.allowed_statuses if str(s).strip()]
        bad = sorted(set(statuses) - KNOWN_STATUSES)
        if bad or not statuses:
            raise HTTPException(status_code=422, detail={"code": "invalid_statuses", "message": f"حالات غير صالحة: {bad or 'فارغة'}"})
        updates["allowed_statuses"] = statuses
    if payload.default_attachments is not None:
        atts = [a for a in payload.default_attachments if a in ("pdf", "image")]
        updates["default_attachments"] = atts
    if payload.allow_edit_before_share is not None:
        updates["allow_edit_before_share"] = bool(payload.allow_edit_before_share)
    if payload.enabled is not None:
        updates["enabled"] = bool(payload.enabled)
    if payload.action_key is not None and payload.action_key != tpl.get("action_key"):
        new_key = payload.action_key.strip()
        if not re.fullmatch(r"[a-z0-9_]{3,60}", new_key):
            raise HTTPException(status_code=422, detail={"code": "invalid_action_key", "message": "action_key بصيغة a-z0-9_ فقط"})
        updates["action_key"] = new_key

    will_be_enabled = updates.get("enabled", tpl.get("enabled", True))
    target_key = updates.get("action_key", tpl.get("action_key"))
    if will_be_enabled:
        dup = await db.outbound_message_templates.find_one({
            "tenant_id": tenant, "action_key": target_key, "enabled": True, "id": {"$ne": template_id}})
        if dup:
            raise HTTPException(status_code=409, detail={
                "code": "duplicate_active_action_key",
                "message": f"يوجد قالب نشط آخر بنفس action_key «{target_key}» لنفس السياق"})

    if not updates:
        return {"success": True, "template": _tpl_public(tpl), "changed": False}

    history_entry = {
        "version": tpl.get("version", 1),
        "body": tpl.get("body"),
        "name": tpl.get("name"),
        "allowed_statuses": tpl.get("allowed_statuses"),
        "updated_by": tpl.get("updated_by") or tpl.get("created_by"),
        "updated_at": tpl.get("updated_at"),
    }
    updates["version"] = int(tpl.get("version", 1)) + 1
    updates["updated_at"] = _now_iso()
    updates["updated_by"] = _identity(user)
    await db.outbound_message_templates.update_one(
        {"id": template_id, "tenant_id": tenant},
        {"$set": updates, "$push": {"versions": {"$each": [history_entry], "$slice": -20}}})
    fresh = await db.outbound_message_templates.find_one({"id": template_id, "tenant_id": tenant}, {"_id": 0})
    return {"success": True, "template": fresh, "changed": True}


@router.post("/templates/{template_id}/restore-default")
async def restore_template_default(template_id: str, tenant_id: str = "default",
                                   user: dict = Depends(get_current_user)):
    await _ensure_ready()
    tpl = await db.outbound_message_templates.find_one({"id": template_id, "tenant_id": tenant_id})
    if not tpl:
        raise HTTPException(status_code=404, detail="template_not_found")
    default_body = tpl.get("default_body")
    if not default_body:
        raise HTTPException(status_code=422, detail={"code": "no_default", "message": "لا يوجد نص افتراضي محفوظ لهذا القالب"})
    history_entry = {
        "version": tpl.get("version", 1), "body": tpl.get("body"), "name": tpl.get("name"),
        "allowed_statuses": tpl.get("allowed_statuses"),
        "updated_by": tpl.get("updated_by") or tpl.get("created_by"), "updated_at": tpl.get("updated_at"),
    }
    await db.outbound_message_templates.update_one(
        {"id": template_id, "tenant_id": tenant_id},
        {"$set": {
            "body": default_body,
            "available_variables": sorted(set(_VAR_RE.findall(default_body))),
            "version": int(tpl.get("version", 1)) + 1,
            "updated_at": _now_iso(), "updated_by": _identity(user),
        }, "$push": {"versions": {"$each": [history_entry], "$slice": -20}}})
    fresh = await db.outbound_message_templates.find_one({"id": template_id, "tenant_id": tenant_id}, {"_id": 0})
    return {"success": True, "template": fresh}


# ============ حل الرسالة ============

class ResolveMessageBody(BaseModel):
    doc_type: str = "invoice"
    status: Optional[str] = None
    template_id: Optional[str] = None
    tenant_id: Optional[str] = "default"
    payload: Dict[str, Any] = {}


@router.post("/resolve-message")
async def resolve_message(body: ResolveMessageBody, user: dict = Depends(get_current_user)):
    await _ensure_ready()
    tenant = body.tenant_id or "default"
    status = _norm_status(body.status or (body.payload.get("settings") or {}).get("status"))
    if status in BLOCKED_SHARE_STATUSES:
        raise HTTPException(status_code=409, detail={
            "code": "superseded_document",
            "message": "هذا المستند مستبدل بنسخة أحدث ولا يمكن مشاركته"})

    chosen = None
    if body.template_id:
        chosen = await db.outbound_message_templates.find_one(
            {"id": body.template_id, "tenant_id": tenant, "enabled": True})
        if not chosen:
            raise HTTPException(status_code=404, detail="template_not_found")
        if chosen.get("doc_type") != body.doc_type:
            raise HTTPException(status_code=422, detail={"code": "doc_type_mismatch", "message": "القالب لا يطابق نوع المستند"})
        allowed = chosen.get("allowed_statuses") or []
        if "*" not in allowed and status not in allowed:
            raise HTTPException(status_code=422, detail={"code": "status_not_allowed", "message": "حالة المستند غير مسموح بها لهذا القالب"})
    else:
        rows = await db.outbound_message_templates.find(
            {"tenant_id": tenant, "doc_type": body.doc_type, "enabled": True}).to_list(100)
        exact = [r for r in rows if status in (r.get("allowed_statuses") or [])]
        wildcard = [r for r in rows if "*" in (r.get("allowed_statuses") or [])]
        chosen = (exact or wildcard or [None])[0]
    if not chosen:
        raise HTTPException(status_code=404, detail={
            "code": "no_template", "message": "لا يوجد قالب رسالة نشط لهذا النوع/الحالة"})

    values = _build_values(body.doc_type, body.payload or {})
    message, missing = _resolve_body(chosen.get("body") or "", values)
    phone = normalize_phone(values.get("CUSTOMER_PHONE"))
    return {
        "success": True,
        "template": {
            "id": chosen.get("id"), "action_key": chosen.get("action_key"),
            "name": chosen.get("name"), "version": chosen.get("version", 1),
            "allow_edit_before_share": chosen.get("allow_edit_before_share", True),
            "default_attachments": chosen.get("default_attachments") or ["pdf", "image"],
        },
        "message": message[:MAX_MESSAGE_LEN],
        "missing_variables": missing,
        "phone": phone,
        "status_used": status,
    }


# ============ البصمة وأصول المخرجات ============

class FingerprintBody(BaseModel):
    material: Dict[str, Any]


@router.post("/fingerprint")
async def get_fingerprint(body: FingerprintBody, user: dict = Depends(get_current_user)):
    await _ensure_ready()
    material = body.material or {}
    status = _norm_status(material.get("status"))
    fingerprint = compute_fingerprint(material)
    tenant = str(material.get("tenant_id") or "default")
    asset = await db.document_output_assets.find_one(
        {"tenant_id": tenant, "fingerprint": fingerprint},
        {"_id": 0, "pdf_base64": 0, "preview_image_base64": 0})
    return {
        "success": True,
        "fingerprint": fingerprint,
        "blocked": status in BLOCKED_SHARE_STATUSES,
        "cached": bool(asset),
        "asset": asset,
        "has_pdf": bool(asset and asset.get("pdf_size")),
        "has_image": bool(asset and asset.get("image_size")),
    }


class AssetUploadBody(BaseModel):
    material: Dict[str, Any]
    pdf_base64: Optional[str] = None
    preview_image_base64: Optional[str] = None
    idempotency_key: Optional[str] = None


@router.post("/assets")
async def upload_asset(body: AssetUploadBody, user: dict = Depends(get_current_user)):
    await _ensure_ready()
    material = body.material or {}
    fingerprint = compute_fingerprint(material)
    tenant = str(material.get("tenant_id") or "default")
    if body.pdf_base64 and len(body.pdf_base64) > MAX_PDF_B64:
        raise HTTPException(status_code=413, detail={"code": "pdf_too_large", "message": "ملف PDF أكبر من الحد المسموح"})
    if body.preview_image_base64 and len(body.preview_image_base64) > MAX_IMG_B64:
        raise HTTPException(status_code=413, detail={"code": "image_too_large", "message": "صورة المعاينة أكبر من الحد المسموح"})

    existing = await db.document_output_assets.find_one(
        {"tenant_id": tenant, "fingerprint": fingerprint},
        {"_id": 0, "pdf_base64": 0, "preview_image_base64": 0})
    if existing:
        await db.document_output_assets.update_one(
            {"tenant_id": tenant, "fingerprint": fingerprint},
            {"$set": {"last_used_at": _now_iso()}, "$inc": {"use_count": 1}})
        return {"success": True, "reused": True, "fingerprint": fingerprint, "asset": existing}

    trace_id = llm_traces.start_trace(
        channel="outbound", user=_identity(user), role=user.get("role"),
        message=f"asset_store {material.get('doc_type')} {material.get('document_number')}")
    llm_traces.add_tool_call(
        tool="outbound.asset_store", write=True,
        tool_input={"fingerprint": fingerprint, "doc_type": material.get("doc_type"),
                    "document_number": material.get("document_number")},
        output_raw="stored")
    doc = {
        "id": "asset-" + uuid.uuid4().hex[:12],
        "tenant_id": tenant,
        "branch_id": material.get("branch_id"),
        "fingerprint": fingerprint,
        "doc_type": material.get("doc_type"),
        "document_number": material.get("document_number"),
        "document_version": material.get("document_version"),
        "template_id": material.get("template_id"),
        "template_version": material.get("template_version"),
        "pdf_base64": body.pdf_base64,
        "preview_image_base64": body.preview_image_base64,
        "pdf_size": len(body.pdf_base64 or ""),
        "image_size": len(body.preview_image_base64 or ""),
        "idempotency_key": body.idempotency_key,
        "trace_id": trace_id,
        "created_by": _identity(user),
        "created_at": _now_iso(),
        "last_used_at": _now_iso(),
        "use_count": 0,
    }
    try:
        await db.document_output_assets.insert_one(dict(doc))
    except Exception:  # سباق متزامن على نفس البصمة → أعد الموجود (idempotent)
        llm_traces.finish_trace(status="duplicate_race")
        existing = await db.document_output_assets.find_one(
            {"tenant_id": tenant, "fingerprint": fingerprint},
            {"_id": 0, "pdf_base64": 0, "preview_image_base64": 0})
        return {"success": True, "reused": True, "fingerprint": fingerprint, "asset": existing}
    llm_traces.finish_trace(status="stored", executed={"fingerprint": fingerprint})
    public = {k: v for k, v in doc.items() if k not in ("pdf_base64", "preview_image_base64")}
    return {"success": True, "reused": False, "fingerprint": fingerprint, "asset": public, "trace_id": trace_id}


@router.get("/assets/{fingerprint}")
async def get_asset(fingerprint: str, tenant_id: str = "default", user: dict = Depends(get_current_user)):
    await _ensure_ready()
    asset = await db.document_output_assets.find_one(
        {"tenant_id": tenant_id, "fingerprint": fingerprint}, {"_id": 0})
    if not asset:
        raise HTTPException(status_code=404, detail="asset_not_found")
    await db.document_output_assets.update_one(
        {"tenant_id": tenant_id, "fingerprint": fingerprint},
        {"$set": {"last_used_at": _now_iso()}, "$inc": {"use_count": 1}})
    return {"success": True, "asset": asset}


# ============ سجل محاولات المشاركة (تدقيق صارم) ============

class ShareAttemptBody(BaseModel):
    doc_type: str = "invoice"
    document_number: Optional[str] = None
    document_version: Optional[Any] = None
    fingerprint: Optional[str] = None
    action_key: Optional[str] = None
    template_id: Optional[str] = None
    template_version: Optional[Any] = None
    phone: Optional[str] = None
    message_text: Optional[str] = None
    message_edited: bool = False
    context: Optional[str] = None
    initial_event: str = "message_prepared"
    idempotency_key: Optional[str] = None
    tenant_id: Optional[str] = "default"
    branch_id: Optional[str] = None


def _validate_event(event: str):
    ev = str(event or "").strip().lower()
    if ev in FORBIDDEN_EVENTS:
        raise HTTPException(status_code=422, detail={
            "code": "forbidden_event",
            "message": "لا يمكن تسجيل حالة إرسال/تسليم/قراءة — لا يوجد مزود WhatsApp Business API يقدم إثباتاً فعلياً"})
    if ev not in ALLOWED_EVENTS:
        raise HTTPException(status_code=422, detail={
            "code": "unknown_event", "message": f"حدث غير معروف: {ev}",
            "allowed": sorted(ALLOWED_EVENTS)})
    return ev


_EVENT_CHANNEL = {
    "share_sheet_opened": "web_share",
    "whatsapp_opened": "wa_me",
    "files_downloaded": "download",
    "text_copied": "copy",
}


@router.post("/share-attempts")
async def create_share_attempt(body: ShareAttemptBody, user: dict = Depends(get_current_user)):
    await _ensure_ready()
    event = _validate_event(body.initial_event)
    tenant = body.tenant_id or "default"
    if body.idempotency_key:
        existing = await db.outbound_share_attempts.find_one(
            {"idempotency_key": body.idempotency_key}, {"_id": 0})
        if existing:
            return {"success": True, "reused": True, "attempt": existing}

    phone = normalize_phone(body.phone)
    trace_id = llm_traces.start_trace(
        channel="outbound", user=_identity(user), role=user.get("role"),
        message=f"share_attempt {body.doc_type} {body.document_number or ''} → {phone.get('e164') or 'بدون رقم'}")
    llm_traces.add_tool_call(
        tool="outbound.share_attempt", write=True,
        tool_input={"doc_type": body.doc_type, "document_number": body.document_number,
                    "action_key": body.action_key, "fingerprint": body.fingerprint,
                    "phone_valid": phone["valid"]},
        output_raw=event)
    now = _now_iso()
    attempt = {
        "id": "share-" + uuid.uuid4().hex[:12],
        "tenant_id": tenant,
        "branch_id": body.branch_id,
        "doc_type": body.doc_type,
        "document_number": body.document_number,
        "document_version": body.document_version,
        "fingerprint": body.fingerprint,
        "action_key": body.action_key,
        "template_id": body.template_id,
        "template_version": body.template_version,
        "phone_raw": phone["raw"],
        "phone_e164": phone["e164"],
        "phone_valid": phone["valid"],
        "message_text": (body.message_text or "")[:MAX_MESSAGE_LEN],
        "message_edited": bool(body.message_edited),
        "context": (body.context or "")[:200],
        "channel": None,
        "events": [{"event": event, "ts": now, "by": _identity(user), "meta": {}}],
        "status": event,
        "idempotency_key": body.idempotency_key,
        "trace_id": trace_id,
        "created_by": _identity(user),
        "created_at": now,
        "updated_at": now,
    }
    try:
        await db.outbound_share_attempts.insert_one(dict(attempt))
    except Exception:
        llm_traces.finish_trace(status="duplicate_idempotency")
        existing = await db.outbound_share_attempts.find_one(
            {"idempotency_key": body.idempotency_key}, {"_id": 0})
        if existing:
            return {"success": True, "reused": True, "attempt": existing}
        raise HTTPException(status_code=500, detail="attempt_persist_failed")
    llm_traces.finish_trace(status=event, executed={"attempt_id": attempt["id"]})
    return {"success": True, "reused": False, "attempt": attempt}


class ShareEventBody(BaseModel):
    event: str
    meta: Optional[Dict[str, Any]] = None


@router.post("/share-attempts/{attempt_id}/events")
async def append_share_event(attempt_id: str, body: ShareEventBody,
                             user: dict = Depends(get_current_user)):
    await _ensure_ready()
    event = _validate_event(body.event)
    attempt = await db.outbound_share_attempts.find_one({"id": attempt_id})
    if not attempt:
        raise HTTPException(status_code=404, detail="attempt_not_found")
    meta = {}
    for k, v in (body.meta or {}).items():
        meta[str(k)[:60]] = str(v)[:500]
    entry = {"event": event, "ts": _now_iso(), "by": _identity(user), "meta": meta}
    updates: Dict[str, Any] = {"status": event, "updated_at": entry["ts"]}
    if event in _EVENT_CHANNEL:
        updates["channel"] = _EVENT_CHANNEL[event]
    await db.outbound_share_attempts.update_one(
        {"id": attempt_id}, {"$set": updates, "$push": {"events": entry}})
    return {"success": True, "attempt_id": attempt_id, "event": entry}


@router.get("/share-attempts")
async def list_share_attempts(document_number: Optional[str] = None,
                              fingerprint: Optional[str] = None,
                              tenant_id: str = "default", limit: int = 50,
                              user: dict = Depends(get_current_user)):
    await _ensure_ready()
    query: Dict[str, Any] = {"tenant_id": tenant_id}
    if document_number:
        query["document_number"] = document_number
    if fingerprint:
        query["fingerprint"] = fingerprint
    rows = await db.outbound_share_attempts.find(query, {"_id": 0}).sort(
        "created_at", -1).to_list(min(max(limit, 1), 200))
    return {"success": True, "attempts": rows}
