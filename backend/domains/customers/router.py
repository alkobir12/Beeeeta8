"""Customers FastAPI router — thin HTTP layer.

Mounted at `/api/customers/*` via api_router include. All business logic lives
in service.py; all persistence in repository.py.
"""
from __future__ import annotations
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from .schemas import CustomerCreate, CustomerUpdate
from .service import CustomerService

router = APIRouter(prefix="/customers", tags=["Customers"])

_service = CustomerService()


# ---------- READ ----------

@router.get("")
async def list_customers(
    workshop_id: Optional[str] = Query(default=None),
    sync_accounts: bool = Query(default=False, description="If true, sync partner subaccounts in chart of accounts."),
):
    """GET /api/customers — returns enriched customers (with financial summary)."""
    try:
        return await _service.list_customers(workshop_id=workshop_id, sync_accounts=sync_accounts)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{customer_id}")
async def get_customer(customer_id: str):
    """GET /api/customers/{id} — fetch a single customer."""
    row = await _service.get_customer(customer_id)
    if not row:
        raise HTTPException(status_code=404, detail="Customer not found")
    return row


# ---------- WRITE ----------

@router.post("")
async def create_customer(payload: CustomerCreate):
    try:
        data: Dict[str, Any] = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
        return await _service.create_customer(data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{customer_id}")
async def update_customer(customer_id: str, payload: CustomerUpdate):
    """PUT /api/customers/{id} — partial update."""
    try:
        patch = payload.model_dump(exclude_none=True) if hasattr(payload, "model_dump") else payload.dict(exclude_none=True)
        updated = await _service.update_customer(customer_id, patch)
        if not updated:
            raise HTTPException(status_code=404, detail="Customer not found")
        return updated
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{customer_id}")
async def delete_customer(customer_id: str):
    """DELETE /api/customers/{id} — cascade delete linked vehicles + invoices best-effort."""
    try:
        ok = await _service.delete_customer(customer_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Customer not found")
        return {"status": "deleted", "id": customer_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
