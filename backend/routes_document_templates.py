"""Canonical document-template registry and resolver."""
import asyncio
import json
import os
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
import bleach
from bleach.css_sanitizer import CSSSanitizer

from routes_templates import DOC_TYPES, INDEX_FILE, TEMPLATES_DIR, _builtin_template_content

router = APIRouter(prefix="/api/document-templates", tags=["document-templates"])
db = None
_seed_lock = asyncio.Lock()
_ALLOWED_TAGS = ["html", "head", "body", "meta", "title", "style", "main", "section", "article", "header", "footer", "div", "span", "p", "strong", "b", "em", "i", "small", "h1", "h2", "h3", "h4", "table", "thead", "tbody", "tfoot", "tr", "th", "td", "ul", "ol", "li", "br", "hr", "img"]
_ALLOWED_ATTRIBUTES = {"*": ["class", "style", "dir", "lang", "id", "data-testid"], "img": ["src", "alt", "width", "height"], "meta": ["charset", "name", "content"]}
_SANITIZER = bleach.Cleaner(tags=_ALLOWED_TAGS, attributes=_ALLOWED_ATTRIBUTES, protocols=["http", "https", "data"], strip=True, strip_comments=False, css_sanitizer=CSSSanitizer())
_KNOWN_TEMPLATE_VARIABLES = {"WORKSHOP_NAME", "WORKSHOP_ADDRESS", "WORKSHOP_PHONE", "WORKSHOP_EMAIL", "COMPANY_CR", "COMPANY_TAX", "TAX_NUMBER", "CUSTOMER_NAME", "CUSTOMER_PHONE", "VEHICLE_INFO", "PLATE_NO", "VEHICLE_PLATE", "STATUS_LABEL", "INVOICE_NO", "INVOICE_DATE", "DATE", "ITEMS_ROWS", "SUBTOTAL", "DISCOUNT", "TAX", "TOTAL", "PAID", "REMAINING", "NOTES", "AMOUNT_WORDS", "SEAL_CODE"}


def set_db(database):
    global db
    db = database


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _public(doc: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(doc)
    result.pop("_id", None)
    result["type"] = result.get("document_type")
    return result


def _sanitize_html(content: str) -> tuple[str, list[str]]:
    raw = str(content or "")
    if not raw.strip():
        raise HTTPException(status_code=422, detail={"code": "empty_template", "message": "ملف HTML فارغ ولا يمكن معاينته."})
    if len(raw.encode("utf-8")) > 1_000_000:
        raise HTTPException(status_code=422, detail={"code": "template_too_large", "message": "حجم قالب HTML يتجاوز الحد المسموح."})
    cleaned = _SANITIZER.clean(raw)
    notes = []
    if cleaned != raw:
        notes.append("sanitized_unsafe_html")
    if not re.search(r"<([a-z][a-z0-9]*)\b", cleaned, re.IGNORECASE):
        raise HTTPException(status_code=422, detail={"code": "invalid_html", "message": "الملف لا يحتوي HTML صالحاً للعرض."})
    return cleaned, notes


def _unknown_template_variables(content: str) -> list[str]:
    matches = re.findall(r"{{\s*([^{}]+?)\s*}}|\[\[\s*([^\]]+?)\s*\]\]|<%=?\s*([^%]+?)\s*%>|\{([A-Z][A-Z0-9_]*)\}", content or "")
    values = {next((item.strip() for item in match if item.strip()), "") for match in matches}
    return sorted(value for value in values if value and value not in _KNOWN_TEMPLATE_VARIABLES)


def _legacy_rows() -> list:
    try:
        rows = json.loads(INDEX_FILE.read_text(encoding="utf-8")) if INDEX_FILE.exists() else []
        return rows if isinstance(rows, list) else []
    except Exception:
        return []


async def _ensure_registry() -> None:
    if db is None:
        raise HTTPException(status_code=503, detail="template_registry_unavailable")
    async with _seed_lock:
        collection = db.document_templates
        await collection.create_index(
            [("tenant_id", 1), ("document_type", 1), ("locale", 1)],
            unique=True,
            partialFilterExpression={"is_default": True, "active": True, "status": "valid"},
            name="one_active_default_per_tenant_type_locale",
        )
        if await collection.count_documents({}) > 0:
            return

        now = _now()
        seeded = []
        for doc_type in DOC_TYPES:
            seeded.append({
                "id": f"builtin-dash-sealed-{doc_type}",
                "name": {"invoice": "فاتورة الورشة — ختم إلكتروني", "diagnosis": "تقرير تشخيص — ختم إلكتروني", "quote": "عرض سعر — ختم إلكتروني", "receipt": "سند زيارة — ختم إلكتروني"}[doc_type],
                "tenant_id": "system",
                "document_type": doc_type,
                "locale": "ar-SA",
                "version": 1,
                "status": "valid",
                "active": True,
                "is_default": True,
                "file_type": "html",
                "is_builtin": True,
                "source": "system_builtin",
                "created_at": now,
                "updated_at": now,
            })
        for legacy in _legacy_rows():
            file_type = legacy.get("file_type") or "html"
            seeded.append({
                "id": legacy.get("id") or str(uuid.uuid4()),
                "name": legacy.get("name") or "قالب قديم",
                "tenant_id": "default",
                "document_type": legacy.get("type") if legacy.get("type") in DOC_TYPES else "invoice",
                "locale": legacy.get("locale") or "ar-SA",
                "version": int(legacy.get("version") or 1),
                "status": "invalid" if file_type == "pdf" else "needs_fix",
                "active": bool(legacy.get("active", True)),
                "is_default": False,
                "file_type": file_type,
                "filename": legacy.get("filename"),
                "original_filename": legacy.get("original_filename"),
                "file_size": legacy.get("file_size"),
                "is_builtin": False,
                "source": legacy.get("source") or "legacy_index",
                "legacy_id": legacy.get("id"),
                "created_at": legacy.get("created_at") or now,
                "updated_at": legacy.get("updated_at") or legacy.get("created_at") or now,
            })
        if seeded:
            await collection.insert_many(seeded, ordered=True)


async def _content(template: Dict[str, Any]) -> str:
    if template.get("is_builtin") or template.get("source") == "system_default_clone":
        content = _builtin_template_content(template["document_type"])
        return _sanitize_html(content)[0]
    if template.get("inline_content"):
        return _sanitize_html(template["inline_content"])[0]
    filename = template.get("filename")
    path = TEMPLATES_DIR / str(filename or "")
    if not filename or not path.exists():
        raise HTTPException(status_code=409, detail={"code": "template_content_missing", "message": "ملف القالب المختار غير موجود."})
    if template.get("file_type") != "html":
        raise HTTPException(status_code=409, detail={"code": "template_not_renderable", "message": "هذا القالب ليس HTML ولا يمكن استخدامه للطباعة."})
    clean, notes = _sanitize_html(path.read_text(encoding="utf-8"))
    if notes:
        await db.document_templates.update_one({"id": template["id"]}, {"$set": {"sanitization_notes": notes, "sanitized_at": _now(), "updated_at": _now()}})
    return clean


async def resolve_template(payload: Dict[str, Any]) -> Dict[str, Any]:
    await _ensure_registry()
    tenant_id = str(payload.get("tenant_id") or "default")
    doc_type = str(payload.get("document_type") or payload.get("doc_type") or "invoice")
    locale = str(payload.get("locale") or "ar-SA")
    explicit_id = str(payload.get("template_id") or "").strip()
    if doc_type not in DOC_TYPES:
        raise HTTPException(status_code=422, detail={"code": "unsupported_document_type"})

    template = None
    reason = ""
    if explicit_id:
        template = await db.document_templates.find_one({"id": explicit_id}, {"_id": 0})
        if not template:
            raise HTTPException(status_code=404, detail={"code": "explicit_template_not_found", "message": "القالب المختار غير موجود."})
        if template.get("document_type") != doc_type or not template.get("active") or template.get("status") not in {"valid", "needs_fix"}:
            raise HTTPException(status_code=409, detail={"code": "explicit_template_unavailable", "message": "القالب المختار غير صالح أو لا يطابق نوع المستند."})
        if template.get("status") == "needs_fix":
            await _content(template)
            await db.document_templates.update_one({"id": explicit_id}, {"$set": {"status": "valid", "updated_at": _now()}})
            template["status"] = "valid"
        reason = "explicit_document_template"
    else:
        template = await db.document_templates.find_one({
            "tenant_id": tenant_id, "document_type": doc_type, "locale": locale,
            "active": True, "is_default": True, "status": "valid",
        }, {"_id": 0})
        if template:
            reason = "tenant_default"
        else:
            template = await db.document_templates.find_one({
                "tenant_id": "system", "document_type": doc_type, "locale": locale,
                "active": True, "is_default": True, "status": "valid",
            }, {"_id": 0})
            reason = "system_default"
    if not template:
        raise HTTPException(status_code=409, detail={"code": "no_resolvable_template", "message": "لا يوجد قالب افتراضي صالح لهذا المستند."})

    content = await _content(template)
    await db.document_template_resolution_audit.insert_one({
        "id": str(uuid.uuid4()), "template_id": template["id"], "tenant_id": tenant_id,
        "document_type": doc_type, "locale": locale, "selection_reason": reason, "created_at": _now(),
    })
    return {"template": _public(template), "content": content, "selection_reason": reason}


@router.get("")
async def list_templates(tenant_id: str = "default", locale: str = "ar-SA"):
    await _ensure_registry()
    rows = await db.document_templates.find(
        {"locale": locale, "$or": [{"tenant_id": tenant_id}, {"tenant_id": "system"}]}, {"_id": 0}
    ).sort([("tenant_id", 1), ("document_type", 1), ("created_at", -1)]).to_list(1000)
    return {"templates": [_public(row) for row in rows]}


@router.post("/resolve")
async def resolve(payload: Dict[str, Any] = Body(...)):
    return await resolve_template(payload)


@router.post("/events")
async def record_template_event(payload: Dict[str, Any] = Body(...)):
    await _ensure_registry()
    event = str(payload.get("event") or "").strip()
    if event not in {"template_incomplete", "template_load_failed", "template_render_failed"}:
        raise HTTPException(status_code=422, detail={"code": "unsupported_template_event"})
    row = {
        "id": str(uuid.uuid4()), "event": event, "template_id": str(payload.get("template_id") or ""),
        "tenant_id": str(payload.get("tenant_id") or "default"), "document_type": str(payload.get("document_type") or ""),
        "locale": str(payload.get("locale") or "ar-SA"), "reason": str(payload.get("reason") or ""),
        "missing_variables": [str(item) for item in (payload.get("missing_variables") or [])][:50], "created_at": _now(),
    }
    await db.document_template_resolution_audit.insert_one(row)
    return {"success": True, "event_id": row["id"]}


@router.post("/upload")
async def upload_template(
    file: UploadFile = File(...), name: Optional[str] = Form(None),
    description: Optional[str] = Form(""), document_type: Optional[str] = Form("invoice"),
    tenant_id: Optional[str] = Form("default"), locale: Optional[str] = Form("ar-SA"),
):
    await _ensure_registry()
    doc_type = document_type if document_type in DOC_TYPES else "invoice"
    extension = Path(file.filename or "").suffix.lower()
    if extension not in {".html", ".htm", ".pdf"}:
        raise HTTPException(status_code=422, detail={"code": "unsupported_template_file"})
    template_id = str(uuid.uuid4())
    filename = f"{template_id}{extension}"
    target = TEMPLATES_DIR / filename
    if extension in {".html", ".htm"}:
        raw_html = (await file.read()).decode("utf-8", errors="replace")
        clean_html, sanitization_notes = _sanitize_html(raw_html)
        target.write_text(clean_html, encoding="utf-8")
    else:
        sanitization_notes = []
        with target.open("wb") as output:
            shutil.copyfileobj(file.file, output)
    now = _now()
    template = {
        "id": template_id, "name": name or file.filename or "قالب جديد", "description": description or "",
        "tenant_id": tenant_id or "default", "document_type": doc_type, "locale": locale or "ar-SA", "version": 1,
        "status": "valid" if extension in {".html", ".htm"} else "invalid", "active": True, "is_default": False,
        "file_type": "html" if extension in {".html", ".htm"} else "pdf", "filename": filename,
        "original_filename": file.filename, "file_size": target.stat().st_size, "is_builtin": False,
        "source": "uploaded_html" if extension in {".html", ".htm"} else "uploaded_file", "created_at": now, "updated_at": now,
        "sanitization_notes": sanitization_notes,
    }
    await db.document_templates.insert_one(template)
    return {"success": True, "template": _public(template)}


@router.post("/{template_id}/set-default")
async def set_default(template_id: str, payload: Dict[str, Any] = Body(default={})):
    await _ensure_registry()
    tenant_id = str(payload.get("tenant_id") or "default")
    locale = str(payload.get("locale") or "ar-SA")
    async with _seed_lock:
        template = await db.document_templates.find_one({"id": template_id}, {"_id": 0})
        if not template:
            raise HTTPException(status_code=404, detail={"code": "template_not_found"})
        if template.get("file_type") != "html" or not template.get("active"):
            raise HTTPException(status_code=409, detail={"code": "template_not_eligible", "message": "لا يمكن تعيين إلا قالب HTML صالح ونشط كافتراضي."})
        if template.get("status") != "valid":
            try:
                await _content(template)
                await db.document_templates.update_one({"id": template_id}, {"$set": {"status": "valid", "updated_at": _now()}})
                template["status"] = "valid"
            except HTTPException as exc:
                raise HTTPException(status_code=409, detail={"code": "template_validation_failed", "message": "فشل التحقق من القالب قبل تعيينه افتراضياً.", "reason": exc.detail}) from exc
        unknown_variables = _unknown_template_variables(await _content(template))
        if unknown_variables:
            await db.document_templates.update_one({"id": template_id}, {"$set": {"status": "needs_fix", "validation_error": "unknown_placeholders", "validation_variables": unknown_variables, "updated_at": _now()}})
            raise HTTPException(status_code=409, detail={"code": "template_incomplete", "message": "لا يمكن تعيين القالب افتراضياً قبل معالجة المتغيرات غير المعروفة.", "missing_variables": unknown_variables})
        doc_type = template["document_type"]
        target_id = template_id
        if template.get("tenant_id") == "system" and tenant_id != "system":
            target_id = str(uuid.uuid4())
            clone = {**template, "id": target_id, "tenant_id": tenant_id, "locale": locale, "is_default": False, "is_builtin": False, "source": "system_default_clone", "created_at": _now(), "updated_at": _now()}
            await db.document_templates.insert_one(clone)
        await db.document_templates.update_many(
            {"tenant_id": tenant_id, "document_type": doc_type, "locale": locale},
            {"$set": {"is_default": False, "updated_at": _now()}},
        )
        await db.document_templates.update_one(
            {"id": target_id}, {"$set": {"tenant_id": tenant_id, "locale": locale, "is_default": True, "updated_at": _now()}},
        )
        await db.document_template_audit.insert_one({
            "id": str(uuid.uuid4()), "event": "set_default", "template_id": target_id, "tenant_id": tenant_id,
            "document_type": doc_type, "locale": locale, "created_at": _now(),
        })
    fresh = await db.document_templates.find_one({"id": target_id}, {"_id": 0})
    return {"success": True, "template": _public(fresh), "selection_scope": f"{tenant_id}+{doc_type}+{locale}"}


@router.post("/{template_id}/use")
async def use_template(template_id: str, payload: Dict[str, Any] = Body(default={})):
    return await resolve_template({**payload, "template_id": template_id})


@router.get("/{template_id}/download")
async def download_template(template_id: str):
    await _ensure_registry()
    template = await db.document_templates.find_one({"id": template_id}, {"_id": 0})
    if not template:
        raise HTTPException(status_code=404, detail={"code": "template_not_found"})
    if template.get("is_builtin"):
        path = TEMPLATES_DIR / f"{template_id}.html"
        path.write_text(_builtin_template_content(template["document_type"]), encoding="utf-8")
    else:
        path = TEMPLATES_DIR / str(template.get("filename") or "")
    if not path.exists():
        raise HTTPException(status_code=404, detail={"code": "template_content_missing"})
    return FileResponse(path=path, filename=template.get("original_filename") or f"{template['name']}.{template.get('file_type', 'html')}")


@router.delete("/{template_id}")
async def archive_template(template_id: str):
    await _ensure_registry()
    result = await db.document_templates.update_one(
        {"id": template_id, "is_builtin": {"$ne": True}},
        {"$set": {"active": False, "is_default": False, "status": "old", "updated_at": _now()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail={"code": "template_not_found_or_builtin"})
    return {"success": True, "status": "archived"}