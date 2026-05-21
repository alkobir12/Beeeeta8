"""
نظام قاعدة المعرفة للأعطال - التطوير الذاتي
يحفظ الأعطال في Supabase مع دعم ملفات الصوت/الفيديو
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import List, Dict, Optional
import os
import uuid
from datetime import datetime
import base64

router = APIRouter(prefix="/api/faults")

# Supabase setup
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")

supabase_client = None
try:
    from supabase import create_client

    if SUPABASE_URL and SUPABASE_KEY:
        supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("✅ Supabase connected for fault_knowledge")
except Exception as e:
    print(f"⚠️ Supabase not configured: {e}")

# In-memory fallback
fault_knowledge_memory: List[Dict] = []


def use_supabase():
    """Check if we should use Supabase"""
    return supabase_client is not None


@router.get("/list")
async def list_faults(
    vehicle_type: Optional[str] = None, symptom: Optional[str] = None, limit: int = 50
):
    """قائمة الأعطال المحفوظة"""
    try:
        if use_supabase():
            query = (
                supabase_client.table("fault_knowledge")
                .select("*")
                .order("created_at", desc=True)
                .limit(limit)
            )
            if vehicle_type:
                query = query.ilike("vehicle_type", f"%{vehicle_type}%")
            result = query.execute()
            return {"success": True, "faults": result.data or [], "source": "supabase"}
        else:
            faults = fault_knowledge_memory.copy()
            if vehicle_type:
                faults = [
                    f
                    for f in faults
                    if vehicle_type.lower() in f.get("vehicle_type", "").lower()
                ]
            faults.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            return {"success": True, "faults": faults[:limit], "source": "memory"}
    except Exception as e:
        print(f"List faults error: {e}")
        # Fallback to memory
        return {
            "success": True,
            "faults": fault_knowledge_memory[:limit],
            "source": "memory_fallback",
        }


@router.post("/add")
async def add_fault(
    title: str = Form(...),
    vehicle_type: str = Form(...),
    vehicle_model: str = Form(None),
    symptom_description: str = Form(...),
    dtc_codes: str = Form(None),
    diagnosis_steps: str = Form(...),
    solution: str = Form(...),
    parts_needed: str = Form(None),
    estimated_cost: float = Form(None),
    difficulty_level: str = Form("medium"),
    vehicle_id: str = Form(None),
    vehicle_plate: str = Form(None),
    media_file: UploadFile = File(None),
):
    """إضافة عطل جديد لقاعدة المعرفة"""
    try:
        fault_id = str(uuid.uuid4())
        media_url = None
        media_type = None

        # Handle file upload
        if media_file:
            file_content = await media_file.read()
            file_ext = media_file.filename.split(".")[-1].lower()
            media_type = (
                "audio"
                if file_ext in ["mp3", "wav", "ogg", "m4a"]
                else "video" if file_ext in ["mp4", "mov", "avi", "webm"] else "image"
            )

            # Try to upload to Supabase Storage
            if use_supabase():
                try:
                    file_path = f"faults/{fault_id}/{media_file.filename}"
                    supabase_client.storage.from_("fault-media").upload(
                        file_path, file_content
                    )
                    media_url = supabase_client.storage.from_(
                        "fault-media"
                    ).get_public_url(file_path)
                except Exception as e:
                    print(f"Storage upload error: {e}")
                    # Fallback to base64
                    media_url = f"data:{media_file.content_type};base64,{base64.b64encode(file_content).decode()[:100]}..."
            else:
                media_url = f"data:{media_file.content_type};base64,{base64.b64encode(file_content).decode()}"

        # Parse arrays
        dtc_list = [
            code.strip().upper()
            for code in (dtc_codes or "").split(",")
            if code.strip()
        ]
        parts_list = [
            part.strip() for part in (parts_needed or "").split(",") if part.strip()
        ]

        fault_data = {
            "id": fault_id,
            "title": title,
            "vehicle_type": vehicle_type,
            "vehicle_model": vehicle_model,
            "symptom_description": symptom_description,
            "dtc_codes": dtc_list,
            "diagnosis_steps": diagnosis_steps,
            "solution": solution,
            "parts_needed": parts_list,
            "estimated_cost": estimated_cost,
            "difficulty_level": difficulty_level,
            "media_url": media_url,
            "media_type": media_type,
            "vehicle_id": vehicle_id,
            "vehicle_plate": vehicle_plate,
            "usage_count": 0,
            "created_at": datetime.utcnow().isoformat(),
        }

        if use_supabase():
            try:
                result = (
                    supabase_client.table("fault_knowledge")
                    .insert(fault_data)
                    .execute()
                )
                return {
                    "success": True,
                    "fault": result.data[0] if result.data else fault_data,
                    "source": "supabase",
                }
            except Exception as e:
                print(f"Supabase insert error: {e}")
                # Fallback to memory
                fault_knowledge_memory.append(fault_data)
                return {
                    "success": True,
                    "fault": fault_data,
                    "source": "memory_fallback",
                }
        else:
            fault_knowledge_memory.append(fault_data)
            return {"success": True, "fault": fault_data, "source": "memory"}

    except Exception as e:
        print(f"Add fault error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search")
async def search_similar_faults(
    symptom: str = Form(None),
    dtc_code: str = Form(None),
    vehicle_type: str = Form(None),
    media_file: UploadFile = File(None),
):
    """البحث عن أعطال مشابهة"""
    try:
        if use_supabase():
            query = supabase_client.table("fault_knowledge").select("*")

            # Build OR conditions
            conditions = []
            if symptom:
                conditions.append(f"symptom_description.ilike.%{symptom}%")
                conditions.append(f"title.ilike.%{symptom}%")
            if dtc_code:
                conditions.append(f"dtc_codes.cs.{{{dtc_code.upper()}}}")
            if vehicle_type:
                conditions.append(f"vehicle_type.ilike.%{vehicle_type}%")

            if conditions:
                query = query.or_(",".join(conditions))

            result = query.order("usage_count", desc=True).limit(10).execute()
            results = result.data or []

            # Update usage count
            for fault in results[:5]:
                try:
                    supabase_client.table("fault_knowledge").update(
                        {"usage_count": (fault.get("usage_count") or 0) + 1}
                    ).eq("id", fault["id"]).execute()
                except Exception:
                    pass

            return {
                "success": True,
                "results": results,
                "count": len(results),
                "source": "supabase",
            }
        else:
            # Memory search
            results = []
            for fault in fault_knowledge_memory:
                score = 0
                if (
                    symptom
                    and symptom.lower() in fault.get("symptom_description", "").lower()
                ):
                    score += 2
                if symptom and symptom.lower() in fault.get("title", "").lower():
                    score += 2
                if dtc_code and dtc_code.upper() in fault.get("dtc_codes", []):
                    score += 3
                if (
                    vehicle_type
                    and vehicle_type.lower() in fault.get("vehicle_type", "").lower()
                ):
                    score += 1
                if score > 0:
                    results.append({**fault, "match_score": score})

            results.sort(key=lambda x: x.get("match_score", 0), reverse=True)
            return {
                "success": True,
                "results": results[:10],
                "count": len(results),
                "source": "memory",
            }

    except Exception as e:
        print(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{fault_id}")
async def get_fault(fault_id: str):
    """جلب تفاصيل عطل محدد"""
    try:
        if use_supabase():
            result = (
                supabase_client.table("fault_knowledge")
                .select("*")
                .eq("id", fault_id)
                .execute()
            )
            if result.data:
                return {"success": True, "fault": result.data[0]}
        else:
            for fault in fault_knowledge_memory:
                if fault["id"] == fault_id:
                    return {"success": True, "fault": fault}
        raise HTTPException(status_code=404, detail="Fault not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{fault_id}")
async def delete_fault(fault_id: str):
    """حذف عطل"""
    global fault_knowledge_memory
    try:
        if use_supabase():
            supabase_client.table("fault_knowledge").delete().eq(
                "id", fault_id
            ).execute()
        fault_knowledge_memory = [
            f for f in fault_knowledge_memory if f["id"] != fault_id
        ]
        return {"success": True, "message": "Fault deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/summary")
async def get_stats():
    """إحصائيات قاعدة المعرفة"""
    try:
        if use_supabase():
            result = supabase_client.table("fault_knowledge").select("*").execute()
            faults = result.data or []
        else:
            faults = fault_knowledge_memory

        vehicle_types = {}
        dtc_codes = {}

        for fault in faults:
            vt = fault.get("vehicle_type", "Unknown")
            vehicle_types[vt] = vehicle_types.get(vt, 0) + 1

            for code in fault.get("dtc_codes") or []:
                dtc_codes[code] = dtc_codes.get(code, 0) + 1

        return {
            "success": True,
            "stats": {
                "total_faults": len(faults),
                "by_vehicle_type": vehicle_types,
                "top_dtc_codes": dict(
                    sorted(dtc_codes.items(), key=lambda x: x[1], reverse=True)[:10]
                ),
                "with_media": len([f for f in faults if f.get("media_url")]),
            },
            "source": "supabase" if use_supabase() else "memory",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Export function for diesel expert
def get_fault_knowledge_db() -> List[Dict]:
    """Get all faults for diesel expert integration"""
    try:
        if use_supabase():
            result = supabase_client.table("fault_knowledge").select("*").execute()
            return result.data or []
    except Exception as e:
        print(f"Error getting faults: {e}")
    return fault_knowledge_memory
