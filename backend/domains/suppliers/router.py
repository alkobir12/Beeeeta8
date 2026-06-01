"""Suppliers FastAPI router — thin HTTP layer mounted at /api/suppliers."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from .schemas import SupplierCreate, SupplierUpdate
from .service import SupplierService

router = APIRouter(prefix="/suppliers", tags=["Suppliers"])

_service = SupplierService()


@router.get("")
async def list_suppliers(
    workshop_id: Optional[str] = Query(default=None),
    sync_accounts: bool = Query(default=False),
):
    try:
        return await _service.list_suppliers(workshop_id=workshop_id, sync_accounts=sync_accounts)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{supplier_id}")
async def get_supplier(supplier_id: str):
    row = await _service.get_supplier(supplier_id)
    if not row:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return row


@router.post("")
async def create_supplier(payload: SupplierCreate):
    try:
        data: Dict[str, Any] = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
        return await _service.create_supplier(data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{supplier_id}")
async def update_supplier(supplier_id: str, payload: SupplierUpdate):
    try:
        patch = payload.model_dump(exclude_none=True) if hasattr(payload, "model_dump") else payload.dict(exclude_none=True)
        updated = await _service.update_supplier(supplier_id, patch)
        if not updated:
            raise HTTPException(status_code=404, detail="Supplier not found")
        return updated
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{supplier_id}")
async def delete_supplier(supplier_id: str):
    try:
        ok = await _service.delete_supplier(supplier_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Supplier not found")
        return {"status": "deleted", "id": supplier_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
