"""Vehicles FastAPI router — thin HTTP layer mounted at /api/vehicles.

Covers the basic 5 CRUD endpoints. Complex routes (save-parts-and-create-journal,
upload-file, files) remain in server.py for now (Phase 3 split).
"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, HTTPException

from .schemas import Vehicle, VehicleCreate, VehicleUpdate
from .service import VehicleService

router = APIRouter(prefix="/vehicles", tags=["Vehicles"])

_service = VehicleService()


@router.post("", response_model=Vehicle)
async def create_vehicle(payload: VehicleCreate):
    try:
        data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
        row = await _service.create_vehicle(data)
        return Vehicle(**row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=List[Vehicle])
async def list_vehicles():
    rows = await _service.list_vehicles()
    return [Vehicle(**r) for r in rows]


@router.get("/{vehicle_id}", response_model=Vehicle)
async def get_vehicle(vehicle_id: str):
    row = await _service.get_vehicle(vehicle_id)
    return Vehicle(**row)


@router.put("/{vehicle_id}", response_model=Vehicle)
async def update_vehicle(vehicle_id: str, payload: VehicleUpdate):
    raw = payload.model_dump(exclude_unset=True) if hasattr(payload, "model_dump") else payload.dict(exclude_unset=True)
    row = await _service.update_vehicle(vehicle_id, raw)
    return Vehicle(**row)


@router.delete("/{vehicle_id}")
async def delete_vehicle(vehicle_id: str):
    await _service.delete_vehicle(vehicle_id)
    return {"success": True}
