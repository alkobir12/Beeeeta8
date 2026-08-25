from fastapi import APIRouter, HTTPException, UploadFile, File, Request
from typing import Dict, Any
from datetime import datetime
import uuid
from core import authz as _authz

router = APIRouter(prefix="/api")
db = None


def set_db(database):
    global db
    db = database


@router.post("/vehicles/{vehicle_id}/upload-file")
async def upload_vehicle_file(
    vehicle_id: str, request: Request, file: UploadFile = File(...), file_type: str = "diagnostic"
):
    """رفع ملف أو فيديو لمركبة"""
    try:
        actor = await _authz.resolve_request_actor(request)
        if not (actor.can("vehicles", "view") or actor.can("archive", "view")):
            raise HTTPException(status_code=403, detail={"error": "vehicle_access_required"})
        from pathlib import Path

        # Check if vehicle exists
        vehicle = await db.vehicles.find_one({"id": vehicle_id})
        if not vehicle:
            raise HTTPException(status_code=404, detail="المركبة غير موجودة")

        # Create vehicle files directory
        UPLOAD_DIR = Path(__file__).parent / "uploads" / "vehicles" / vehicle_id
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

        # Save file
        file_path = UPLOAD_DIR / file.filename
        with open(file_path, "wb") as f:
            f.write(await file.read())

        # Create file record
        file_record = {
            "id": str(uuid.uuid4()),
            "vehicleId": vehicle_id,
            "filename": file.filename,
            "fileType": file_type,  # diagnostic, repair, video, photo
            "filePath": str(file_path),
            "uploadedAt": datetime.utcnow(),
            "uploadedBy": "system",
        }

        await db.vehicle_files.insert_one(file_record)

        file_record.pop("_id", None)
        return file_record
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vehicles/{vehicle_id}/files")
async def get_vehicle_files(vehicle_id: str, request: Request):
    """الحصول على ملفات المركبة"""
    try:
        actor = await _authz.resolve_request_actor(request)
        if not (actor.can("vehicles", "view") or actor.can("archive", "view")):
            raise HTTPException(status_code=403, detail={"error": "vehicle_access_required"})
        files = (
            await db.vehicle_files.find({"vehicleId": vehicle_id})
            .sort("uploadedAt", -1)
            .to_list(length=100)
        )

        for f in files:
            f.pop("_id", None)
            if f.get("uploadedAt") and hasattr(f["uploadedAt"], "isoformat"):
                f["uploadedAt"] = f["uploadedAt"].isoformat()

        return {"files": files, "count": len(files)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/vehicles/compare-diagnostics")
async def compare_vehicle_diagnostics(request: Request, payload: Dict[str, Any]):
    """مقارنة بيانات تشخيص مركبتين"""
    try:
        actor = await _authz.resolve_request_actor(request)
        if not (actor.can("vehicles", "view") or actor.can("archive", "view")):
            raise HTTPException(status_code=403, detail={"error": "vehicle_access_required"})
        import os
        from emergentintegrations.llm.chat import LlmChat, UserMessage

        vehicle1_id = payload.get("vehicle1_id")
        vehicle2_id = payload.get("vehicle2_id")
        payload.get("file1_id")
        payload.get("file2_id")

        # Get vehicles
        v1 = await db.vehicles.find_one({"id": vehicle1_id})
        v2 = await db.vehicles.find_one({"id": vehicle2_id})

        if not v1 or not v2:
            raise HTTPException(status_code=404, detail="مركبة غير موجودة")

        # Get files if specified
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

        # Use AI to compare
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
