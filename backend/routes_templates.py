"""
مسارات إدارة النماذج المخصصة
Custom Templates Management Routes
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, Response
from typing import Optional
from datetime import datetime, timezone
import os
import uuid
from pathlib import Path
import json
from unified_workshop_template import unified_workshop_template
from core import object_storage

router = APIRouter(prefix="/api/templates")

TEMPLATES_DIR = Path(__file__).parent / "custom_templates"
TEMPLATES_DIR.mkdir(exist_ok=True)
INDEX_FILE = Path(__file__).parent / "uploads" / "custom_templates_index.json"
INDEX_FILE.parent.mkdir(exist_ok=True)

DOC_TYPES = ["invoice", "diagnosis", "quote", "receipt"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_templates() -> list:
    try:
        if INDEX_FILE.exists():
            data = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
    except Exception:
        pass
    return []


def _save_templates(items: list) -> None:
    INDEX_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


templates_db = _load_templates()


def _builtin_template_content(doc_type: str) -> str:
    return unified_workshop_template(doc_type)
    titles = {
        "invoice": "فاتورة الورشة — ختم إلكتروني",
        "diagnosis": "تقرير تشخيص — ختم إلكتروني",
        "quote": "عرض سعر — ختم إلكتروني",
        "receipt": "سند زيارة — ختم إلكتروني",
    }
    title = titles.get(doc_type, titles["invoice"])
    return f"""<!doctype html>
<html lang=\"ar\" dir=\"rtl\"><head><meta charset=\"utf-8\" />
<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\" />
<title>{title}</title>
<style>
@page{{size:A4;margin:0}}*{{box-sizing:border-box;letter-spacing:0}}body{{margin:0;background:#f6f7fb;font-family:Tahoma,Arial,sans-serif;color:#172033;direction:rtl}}.sheet{{width:210mm;min-height:297mm;margin:auto;background:white;padding:13mm;position:relative;overflow:hidden}}.top{{position:absolute;inset:0 0 auto;height:8mm;background:linear-gradient(90deg,#172033,#1e3a5f,#2563eb,#0ea5e9)}}.head{{margin-top:8mm;display:flex;justify-content:space-between;gap:10mm;border-bottom:1px solid #dbe4ee;padding-bottom:7mm}}.brand h1{{margin:0;font-size:22px;color:#172033}}.brand p{{margin:3px 0;color:#64748b;font-size:11px}}.seal{{width:36mm;height:36mm;border-radius:50%;border:2px dashed #2563eb;background:#eff6ff;display:grid;place-items:center;text-align:center;color:#1d4ed8;font-weight:900}}.seal span{{display:block;font-size:8px;color:#172033}}.band{{margin-top:6mm;padding:5mm;border:1px solid #dbeafe;border-radius:5mm;background:#f8fbff;display:flex;justify-content:space-between;align-items:center}}.band h2{{margin:0;font-size:24px}}.cards{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:4mm;margin-top:5mm}}.card{{border:1px solid #e2e8f0;border-radius:4mm;padding:4mm}}.card h3{{margin:0 0 2mm;font-size:12px}}.line{{display:flex;justify-content:space-between;border-bottom:1px dashed #edf2f7;padding:1.5mm 0;font-size:10px;gap:3mm}}.line b{{text-align:left}}table{{width:100%;border-collapse:separate;border-spacing:0;margin-top:5mm;border:1px solid #dbe4ee;border-radius:3mm;overflow:hidden;font-size:10px}}th{{background:#172033;color:white;padding:2.5mm}}td{{border-top:1px solid #e2e8f0;border-left:1px solid #e2e8f0;padding:2.4mm;text-align:center;vertical-align:top}}td.desc{{text-align:right}}.bottom{{display:grid;grid-template-columns:1.15fr .85fr;gap:4mm;margin-top:5mm}}.notes{{background:#f8fafc;border:1px solid #e2e8f0;border-radius:4mm;padding:4mm;font-size:10px;line-height:1.8}}.totals{{border:1px solid #dbe4ee;border-radius:4mm;overflow:hidden}}.trow{{display:flex;justify-content:space-between;padding:2.5mm 3mm;border-bottom:1px solid #edf2f7;font-size:10px}}.trow.total{{background:#172033;color:white;font-weight:900}}.signs{{display:grid;grid-template-columns:1fr 1fr 30mm;gap:4mm;margin-top:7mm}}.sig,.qr{{height:24mm;border:1px dashed #94a3b8;border-radius:3mm;display:flex;align-items:flex-end;justify-content:center;padding-bottom:2mm;color:#64748b;font-size:9px}}.qr{{border-style:solid;background:#f8fafc;align-items:center;flex-direction:column}}.qr div{{width:14mm;height:14mm;background:repeating-linear-gradient(45deg,#172033 0 2px,#fff 2px 4px)}}footer{{position:absolute;left:13mm;right:13mm;bottom:9mm;border-top:1px solid #dbe4ee;padding-top:3mm;display:flex;justify-content:space-between;color:#64748b;font-size:9px}}@media print{{body{{background:white}}.sheet{{margin:0;box-shadow:none}}}}
</style></head><body><main class=\"sheet\"><div class=\"top\"></div><header class=\"head\"><section class=\"brand\"><p>ELECTRONICALLY SEALED DOCUMENT</p><h1>{{WORKSHOP_NAME}}</h1><p>{{WORKSHOP_ADDRESS}} · {{WORKSHOP_PHONE}}</p><p>س.ت: {{COMPANY_CR}} · ضريبي: {{COMPANY_TAX}}</p></section><aside class=\"seal\">✓<strong>ختم إلكتروني</strong><span>{{SEAL_CODE}}</span></aside></header><section class=\"band\"><div><p>{title}</p><h2>{{INVOICE_NO}}</h2></div><strong>{{DATE}}</strong></section><section class=\"cards\"><div class=\"card\"><h3>بيانات العميل</h3><div class=\"line\"><span>الاسم</span><b>{{CUSTOMER_NAME}}</b></div><div class=\"line\"><span>الجوال</span><b>{{CUSTOMER_PHONE}}</b></div></div><div class=\"card\"><h3>بيانات المركبة</h3><div class=\"line\"><span>المركبة</span><b>{{VEHICLE_INFO}}</b></div><div class=\"line\"><span>اللوحة</span><b>{{PLATE_NO}}</b></div></div><div class=\"card\"><h3>ملخص</h3><div class=\"line\"><span>الحالة</span><b>{{STATUS_LABEL}}</b></div><div class=\"line\"><span>المتبقي</span><b>{{REMAINING}}</b></div></div></section><table><thead><tr><th>#</th><th>البيان</th><th>الكمية</th><th>السعر</th><th>الخصم</th><th>الإجمالي</th></tr></thead><tbody>{{ITEMS_ROWS}}</tbody></table><section class=\"bottom\"><div class=\"notes\"><b>ملاحظات</b><br>{{NOTES}}<br><br><b>المبلغ كتابةً:</b> {{AMOUNT_WORDS}}</div><div class=\"totals\"><div class=\"trow\"><span>المجموع</span><b>{{SUBTOTAL}}</b></div><div class=\"trow\"><span>الخصم</span><b>{{DISCOUNT}}</b></div><div class=\"trow total\"><span>الإجمالي</span><b>{{TOTAL}}</b></div><div class=\"trow\"><span>المدفوع</span><b>{{PAID}}</b></div><div class=\"trow\"><span>المتبقي</span><b>{{REMAINING}}</b></div></div></section><section class=\"signs\"><div class=\"sig\">توقيع الورشة</div><div class=\"sig\">توقيع العميل</div><div class=\"qr\"><div></div><span>رمز تحقق</span></div></section><footer><span>{{WORKSHOP_PHONE}}</span><strong>تم إصدار المستند عبر داش برو</strong><span>{{SEAL_CODE}}</span></footer></main></body></html>"""


def _builtin_templates() -> list:
    active_by_type = {t.get("type") for t in templates_db if t.get("active", True) and t.get("is_default")}
    labels = {
        "invoice": "فاتورة الورشة — ختم إلكتروني",
        "diagnosis": "تقرير تشخيص — ختم إلكتروني",
        "quote": "عرض سعر — ختم إلكتروني",
        "receipt": "سند زيارة — ختم إلكتروني",
    }
    return [
        {
            "id": f"builtin-dash-sealed-{doc_type}",
            "name": labels[doc_type],
            "description": "النموذج الرسمي الجديد بهوية Dash Pro — بدون التصميم الأزرق القديم",
            "type": doc_type,
            "file_type": "html",
            "original_filename": f"dash-sealed-{doc_type}.html",
            "file_size": len(_builtin_template_content(doc_type).encode("utf-8")),
            "created_at": "2026-07-21T00:00:00+00:00",
            "active": True,
            "isActive": doc_type not in active_by_type,
            "is_default": doc_type not in active_by_type,
            "is_builtin": True,
        }
        for doc_type in DOC_TYPES
    ]


def _find_template(template_id: str):
    builtin = next((t for t in _builtin_templates() if t["id"] == template_id), None)
    if builtin:
        return builtin
    return next((t for t in templates_db if t["id"] == template_id), None)


@router.get("")
async def get_templates():
    """الحصول على جميع النماذج المخصصة"""
    active = [t for t in templates_db if t.get("active", True)]
    return {"templates": _builtin_templates() + active}


@router.post("/upload")
async def upload_template(
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(""),
    type: Optional[str] = Form("invoice"),
    make_default: bool = Form(True),
):
    """رفع نموذج جديد (HTML أو PDF)"""

    # التحقق من نوع الملف
    allowed_extensions = [".html", ".htm", ".pdf"]
    file_ext = os.path.splitext(file.filename)[1].lower()

    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"نوع الملف غير مدعوم. الأنواع المسموحة: {', '.join(allowed_extensions)}",
        )

    if type not in DOC_TYPES:
        type = "invoice"

    template_id = str(uuid.uuid4())

    # حفظ الملف في تخزين دائم (Object Storage) — لا قرص الحاوية
    raw_bytes = await file.read()
    checked = object_storage.validate_upload(
        raw_bytes, file.filename, file.content_type, "document-templates"
    )
    object_key = object_storage.build_object_key("document-templates", type, checked["ext"])
    await object_storage.put_object(object_key, raw_bytes, checked["content_type"])

    is_html = file_ext in (".html", ".htm")
    if make_default and is_html:
        for item in templates_db:
            if item.get("type") == type:
                item["is_default"] = False
                item["isActive"] = False

    template = {
        "id": template_id,
        "name": name or file.filename,
        "description": description or "",
        "type": type,
        "file_type": file_ext[1:],  # html أو pdf
        "storage_backend": "emergent_object_storage",
        "storage_path": object_key,
        "mime_type": checked["content_type"],
        "content_verification": checked["verification_level"],
        "original_filename": object_storage.safe_basename(file.filename or "template"),
        "file_size": len(raw_bytes),
        "created_at": _now_iso(),
        "active": True,
        "isActive": bool(make_default and is_html),
        "is_default": bool(make_default and is_html),
        "is_builtin": False,
        "source": "uploaded_html" if is_html else "uploaded_file",
    }

    templates_db.append(template)
    _save_templates(templates_db)

    return {"success": True, "message": "تم رفع النموذج بنجاح", "template": template}


@router.get("/{template_id}")
async def get_template(template_id: str):
    """الحصول على نموذج معين"""
    template = _find_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="النموذج غير موجود")
    return template


@router.get("/{template_id}/download")
async def download_template(template_id: str):
    """تحميل ملف النموذج"""
    template = _find_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="النموذج غير موجود")

    if template.get("is_builtin"):
        content = _builtin_template_content(template.get("type", "invoice"))
        return Response(
            content=content.encode("utf-8"),
            media_type="text/html",
            headers={"Content-Disposition": f'attachment; filename="{template_id}.html"'},
        )

    storage_path = template.get("storage_path")
    if storage_path:
        payload, detected = await object_storage.get_object(storage_path)
        return Response(
            content=payload,
            media_type=template.get("mime_type") or detected,
            headers={"Content-Disposition": f'attachment; filename="{template_id}.{template.get("file_type", "html")}"'},
        )

    # LEGACY TEMPORARY COMPATIBILITY — pre-migration template files on container disk.
    file_path = TEMPLATES_DIR / str(template.get("filename") or "")
    if not template.get("filename") or not file_path.exists():
        raise HTTPException(status_code=404, detail="ملف النموذج غير موجود")

    return FileResponse(
        path=file_path,
        filename=template["original_filename"],
        media_type="application/octet-stream",
    )


@router.delete("/{template_id}")
async def delete_template(template_id: str):
    """حذف نموذج"""
    global templates_db

    template = next((t for t in templates_db if t["id"] == template_id), None)
    if not template:
        raise HTTPException(status_code=404, detail="النموذج غير موجود")

    # حذف الملف
    file_path = TEMPLATES_DIR / template["filename"]
    if file_path.exists():
        file_path.unlink()

    # حذف من قاعدة البيانات
    templates_db = [t for t in templates_db if t["id"] != template_id]
    _save_templates(templates_db)

    return {"success": True, "message": "تم حذف النموذج"}


@router.put("/{template_id}")
async def update_template(
    template_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    active: Optional[bool] = None,
):
    """تحديث معلومات نموذج"""
    template = next((t for t in templates_db if t["id"] == template_id), None)
    if not template:
        raise HTTPException(status_code=404, detail="النموذج غير موجود")

    if name is not None:
        template["name"] = name
    if description is not None:
        template["description"] = description
    if active is not None:
        template["active"] = active

    template["updated_at"] = datetime.now().isoformat()
    _save_templates(templates_db)

    return {"success": True, "template": template}


@router.post("/{template_id}/make-default")
async def make_template_default(template_id: str):
    """جعل النموذج افتراضياً لنوعه"""
    template = _find_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="النموذج غير موجود")
    doc_type = template.get("type", "invoice")
    for item in templates_db:
        if item.get("type") == doc_type:
            item["is_default"] = False
            item["isActive"] = False
    if not template.get("is_builtin"):
        for item in templates_db:
            if item.get("id") == template_id:
                item["is_default"] = True
                item["isActive"] = True
                item["updated_at"] = _now_iso()
    _save_templates(templates_db)
    return {"success": True, "message": "تم تعيين النموذج افتراضياً", "id": template_id, "type": doc_type}


@router.post("/{template_id}/use")
async def use_template(template_id: str):
    """استخدام نموذج لتوليد مستند"""
    template = _find_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="النموذج غير موجود")

    if template.get("is_builtin"):
        return {
            "success": True,
            "template_id": template_id,
            "content": _builtin_template_content(template.get("type", "invoice")),
            "type": "html",
            "template": template,
        }

    file_path = TEMPLATES_DIR / template["filename"]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="ملف النموذج غير موجود")

    if template.get("file_type") == "pdf":
        raise HTTPException(status_code=400, detail="نماذج PDF للتحميل فقط ولا تُستخدم كقالب HTML للطباعة")

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    return {
        "success": True,
        "template_id": template_id,
        "content": content,
        "type": template["file_type"],
        "template": template,
    }
