"""Canonical document-template registry and resolver."""
import asyncio
import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from routes_templates import DOC_TYPES, INDEX_FILE, TEMPLATES_DIR, _builtin_template_content

router = APIRouter(prefix="/api/document-templates", tags=["document-templates"])
db = None
_seed_lock = asyncio.Lock()


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
        return _builtin_template_content(template["document_type"])
    filename = template.get("filename")
    path = TEMPLATES_DIR / str(filename or "")
    if not filename or not path.exists():
        raise HTTPException(status_code=409, detail={"code": "template_content_missing", "message": "ملف القالب المختار غير موجود."})
    if template.get("file_type") != "html":
        raise HTTPException(status_code=409, detail={"code": "template_not_renderable", "message": "هذا القالب ليس HTML ولا يمكن استخدامه للطباعة."})
    return path.read_text(encoding="utf-8")


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
        if template.get("document_type") != doc_type or not template.get("active") or template.get("status") != "valid":
            raise HTTPException(status_code=409, detail={"code": "explicit_template_unavailable", "message": "القالب المختار غير صالح أو لا يطابق نوع المستند."})
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
        if template.get("file_type") != "html" or template.get("status") != "valid" or not template.get("active"):
            raise HTTPException(status_code=409, detail={"code": "template_not_eligible", "message": "لا يمكن تعيين إلا قالب HTML صالح ونشط كافتراضي."})
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