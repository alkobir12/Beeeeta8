from fastapi import APIRouter, HTTPException, UploadFile, File, Request, Response
from typing import Dict, Any
from datetime import datetime, timezone
from pathlib import Path
import uuid
from core import authz as _authz
from core import object_storage

router = APIRouter(prefix="/api")
db = None


def set_db(database):
    global db
    db = database


async def _require_vehicle_file_access(request: Request):
    actor = await _authz.resolve_request_actor(request)
    if not (actor.can("vehicles", "view") or actor.can("archive", "view")):
        raise HTTPException(status_code=403, detail={"error": "vehicle_access_required"})
    return actor


@router.post("/vehicles/{vehicle_id}/upload-file")
async def upload_vehicle_file(
    vehicle_id: str, request: Request, file: UploadFile = File(...), file_type: str = "diagnostic"
):
    """رفع ملف لمركبة — تخزين دائم في Object Storage (لا قرص الحاوية)."""
    try:
        actor = await _require_vehicle_file_access(request)

        vehicle = await db.vehicles.find_one({"id": vehicle_id})
        if not vehicle:
            raise HTTPException(status_code=404, detail="المركبة غير موجودة")

        data = await file.read()
        checked = object_storage.validate_upload(
            data, file.filename, file.content_type, "vehicle-files"
        )
        object_key = object_storage.build_object_key("vehicle-files", vehicle_id, checked["ext"])
        stored = await object_storage.put_object(object_key, data, checked["content_type"])

        file_record = {
            "id": str(uuid.uuid4()),
            "vehicleId": vehicle_id,
            "filename": object_storage.safe_basename(file.filename or "upload"),
            "fileType": file_type,
            "storage_backend": "emergent_object_storage",
            "storage_path": stored["path"],
            "mime_type": checked["content_type"],
            "content_verification": checked["verification_level"],
            "size": len(data),
            "is_deleted": False,
            "uploadedAt": datetime.now(timezone.utc),
            "uploadedBy": str(getattr(actor, "name", "") or "unknown"),
        }

        await db.vehicle_files.insert_one(dict(file_record))
        file_record["uploadedAt"] = file_record["uploadedAt"].isoformat()
        return file_record
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vehicles/{vehicle_id}/files")
async def get_vehicle_files(vehicle_id: str, request: Request):
    """الحصول على ملفات المركبة"""
    try:
        await _require_vehicle_file_access(request)
        files = (
            await db.vehicle_files.find({"vehicleId": vehicle_id, "is_deleted": {"$ne": True}})
            .sort("uploadedAt", -1)
            .to_list(length=100)
        )

        for f in files:
            f.pop("_id", None)
            if f.get("uploadedAt") and hasattr(f["uploadedAt"], "isoformat"):
                f["uploadedAt"] = f["uploadedAt"].isoformat()

        return {"files": files, "count": len(files)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vehicles/{vehicle_id}/files/{file_id}/download")
async def download_vehicle_file(vehicle_id: str, file_id: str, request: Request):
    """تنزيل ملف مركبة — التفويض على الخادم، ولا يُمرَّر أي توكن في الرابط."""
    await _require_vehicle_file_access(request)
    record = await db.vehicle_files.find_one(
        {"id": file_id, "vehicleId": vehicle_id, "is_deleted": {"$ne": True}}, {"_id": 0}
    )
    if not record:
        raise HTTPException(status_code=404, detail="الملف غير موجود")

    media_type = record.get("mime_type") or "application/octet-stream"
    storage_path = record.get("storage_path")
    if storage_path:
        data, detected = await object_storage.get_object(storage_path)
        return Response(content=data, media_type=media_type or detected)

    # LEGACY TEMPORARY COMPATIBILITY — pre-migration files still on container disk.
    # Read-only fallback, not the target architecture; lost on pod restart.
    legacy_path = record.get("filePath")
    if legacy_path and Path(legacy_path).is_file():
        return Response(content=Path(legacy_path).read_bytes(), media_type=media_type)

    raise HTTPException(
        status_code=410,
        detail={
            "error": "file_content_unavailable",
            "message": "الملف كان مخزناً محلياً وفُقد مع إعادة تشغيل الحاوية.",
        },
    )


@router.post("/vehicles/compare-diagnostics")
async def compare_vehicle_diagnostics(request: Request, payload: Dict[str, Any]):
    """مقارنة بيانات تشخيص مركبتين"""
    try:
        await _require_vehicle_file_access(request)
        import os
        from emergentintegrations.llm.chat import LlmChat, UserMessage

        vehicle1_id = payload.get("vehicle1_id")
        vehicle2_id = payload.get("vehicle2_id")

        # Get vehicles
        v1 = await db.vehicles.find_one({"id": vehicle1_id})
        v2 = await db.vehicles.find_one({"id": vehicle2_id})

        if not v1 or not v2:
            raise HTTPException(status_code=404, detail="مركبة غير موجودة")

        comparison_data = {
            "vehicle1": {
                "brand": v1.get("brand"),
                "model": v1.get("model"),
                "year": v1.get("year"),
                "plateNumber": v1.get("plateNumber"),
                "services": v1.get("services", []),
            },
            "vehicle2": {
                "brand": v2.get("brand"),
                "model": v2.get("model"),
                "year": v2.get("year"),
                "plateNumber": v2.get("plateNumber"),
                "services": v2.get("services", []),
            },
        }

        llm = LlmChat(
            api_key=os.getenv("EMERGENT_LLM_KEY"),
            session_id=str(uuid.uuid4()),
            system_message="You are an automotive diagnostic comparison expert. Compare vehicles and their diagnostic data in Arabic.",
        ).with_model("anthropic", "claude-sonnet-4-20250514")

        prompt = f"""قارن بين هاتين المركبتين بالتفصيل:

المركبة الأولى:
- {comparison_data['vehicle1']['brand']} {comparison_data['vehicle1']['model']} {comparison_data['vehicle1']['year']}
- رقم اللوحة: {comparison_data['vehicle1']['plateNumber']}
- الخدمات: {', '.join(comparison_data['vehicle1']['services'])}

المركبة الثانية:
- {comparison_data['vehicle2']['brand']} {comparison_data['vehicle2']['model']} {comparison_data['vehicle2']['year']}
- رقم اللوحة: {comparison_data['vehicle2']['plateNumber']}
- الخدمات: {', '.join(comparison_data['vehicle2']['services'])}

قدم:
1. المقارنة الفنية
2. الفروقات في المشاكل
3. التوصيات لكل مركبة
4. أيهما بحاجة لعناية أكثر"""

        response = await llm.send_message(UserMessage(text=prompt))
        response_text = response if isinstance(response, str) else response.text

        return {
            "vehicle1": comparison_data["vehicle1"],
            "vehicle2": comparison_data["vehicle2"],
            "comparison": response_text,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
